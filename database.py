"""
Database Management System for Transformer Health & Risk Monitor.
Supports MySQL 8.0+ via PyMySQL with transparent local SQLite/in-memory fallback.
"""
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import pymysql
from pymysql.cursors import DictCursor

from config import CONFIG

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.mysql_enabled = False
        self.mysql_pool = None
        self.sqlite_conn = None
        self._init_sqlite()
        self._try_connect_mysql()

    def _init_sqlite(self):
        """Initializes embedded fallback SQLite database for resilient local operations."""
        try:
            self.sqlite_conn = sqlite3.connect("scratch/local_gridguard.db", check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            cursor = self.sqlite_conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transformers (
                transformer_id TEXT PRIMARY KEY,
                substation_name TEXT,
                feeder_id TEXT,
                status TEXT DEFAULT 'ACTIVE_NOMINAL'
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_frames (
                frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id TEXT,
                voltage_v REAL,
                current_a REAL,
                winding_temp_c REAL,
                vibration_g REAL,
                oil_level TEXT,
                ambient_temp_c REAL,
                rel_humidity_pct REAL,
                wind_speed_kmh REAL,
                relay_status TEXT,
                recorded_at TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id INTEGER,
                transformer_id TEXT,
                thi REAL,
                health_category TEXT,
                rul_years REAL,
                assessed_at TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS classified_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id TEXT,
                severity TEXT,
                category TEXT,
                alert_code TEXT,
                alert_title TEXT,
                alert_message TEXT,
                trigger_value TEXT,
                threshold_limit TEXT,
                is_tripped INTEGER DEFAULT 0,
                is_acknowledged INTEGER DEFAULT 0,
                acknowledged_by TEXT,
                triggered_at TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS kafka_event_stream (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_name TEXT,
                partition_id INTEGER,
                offset_num INTEGER,
                payload_json TEXT,
                ingested_at TEXT
            )
            """)

            self.sqlite_conn.commit()
            logger.info("SQLite local fallback database initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite fallback: {e}")

    def _try_connect_mysql(self):
        """Attempts connection to MySQL server."""
        try:
            conn = pymysql.connect(
                host=CONFIG.MYSQL_HOST,
                port=CONFIG.MYSQL_PORT,
                user=CONFIG.MYSQL_USER,
                password=CONFIG.MYSQL_PASSWORD,
                charset='utf8mb4',
                cursorclass=DictCursor,
                connect_timeout=2
            )
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{CONFIG.MYSQL_DATABASE}` CHARACTER SET utf8mb4;")
            conn.select_db(CONFIG.MYSQL_DATABASE)
            
            # Execute schema initialization
            try:
                with open("db_schema.sql", "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                # Run individual statements
                for stmt in schema_sql.split(";"):
                    cleaned = stmt.strip()
                    if cleaned and not cleaned.startswith("--") and not cleaned.startswith("/*"):
                        try:
                            cursor.execute(cleaned)
                        except Exception:
                            pass
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not auto-apply db_schema.sql to MySQL: {e}")

            conn.close()
            self.mysql_enabled = True
            logger.info(f"Connected to MySQL database '{CONFIG.MYSQL_DATABASE}' on {CONFIG.MYSQL_HOST}:{CONFIG.MYSQL_PORT}")
        except Exception as e:
            logger.warning(f"MySQL connection unavailable ({e}). Using embedded local database engine.")
            self.mysql_enabled = False

    def get_mysql_connection(self):
        if not self.mysql_enabled:
            return None
        try:
            return pymysql.connect(
                host=CONFIG.MYSQL_HOST,
                port=CONFIG.MYSQL_PORT,
                user=CONFIG.MYSQL_USER,
                password=CONFIG.MYSQL_PASSWORD,
                database=CONFIG.MYSQL_DATABASE,
                charset='utf8mb4',
                cursorclass=DictCursor,
                connect_timeout=2
            )
        except Exception:
            self.mysql_enabled = False
            return None

    def record_telemetry_and_events(
        self,
        telemetry: Dict[str, Any],
        stress: Dict[str, Any],
        env: Dict[str, Any],
        protection: Dict[str, Any],
        alerts: List[Dict[str, Any]],
        kafka_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Saves telemetry, health analytics, alerts and kafka events in database."""
        now_ts = datetime.now()
        now_str = now_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        tx_id = telemetry.get("device_id", "STM32-TX01")

        # 1. Save to MySQL if available
        conn = self.get_mysql_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Insert telemetry frame
                    cur.execute("""
                        INSERT INTO telemetry_frames (
                            transformer_id, voltage_v, current_a, winding_temp_c, vibration_g,
                            oil_level, ambient_temp_c, rel_humidity_pct, wind_speed_kmh,
                            device_id, relay_status, recorded_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tx_id, telemetry.get("voltage", 230.0), telemetry.get("current", 10.0),
                        telemetry.get("temperature", 34.0), telemetry.get("vibration", 0.05),
                        telemetry.get("oil_level", "NORMAL"), telemetry.get("ambient_temp", 28.0),
                        telemetry.get("rel_humidity", 45.0), telemetry.get("wind_speed", 12.0),
                        tx_id, "OPEN_TRIPPED" if protection.get("is_tripped") else "CLOSED",
                        now_str
                    ))
                    frame_id = cur.lastrowid

                    # Insert health assessment
                    cur.execute("""
                        INSERT INTO health_assessments (
                            frame_id, transformer_id, voltage_stress_sv, current_stress_si,
                            thermal_stress_st, vibration_stress_svib, transformer_health_index_thi,
                            health_category, rul_years_predicted, daily_degradation_slope,
                            projected_service_date, assessed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        frame_id, tx_id, stress.get("s_v", 0.0), stress.get("s_i", 0.0),
                        stress.get("s_t", 0.0), stress.get("s_vib", 0.0), stress.get("thi", 95.0),
                        stress.get("health_status", "OPTIMAL / GOOD").replace(" / ", "_").replace(" ", "_"),
                        24.0, 0.15, "Standard Cycle", now_str
                    ))

                    # Insert environmental risk
                    cur.execute("""
                        INSERT INTO environmental_risks (
                            frame_id, transformer_id, fire_weather_index_fwi, risk_level,
                            consequence_severity, risk_narrative, assessed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        frame_id, tx_id, env.get("fwi", 20.0), env.get("level", "LOW"),
                        env.get("severity", "LOW RISK"), env.get("description", "Normal conditions"),
                        now_str
                    ))

                    # Insert classified alerts
                    for a in alerts:
                        cur.execute("""
                            INSERT INTO classified_alerts (
                                transformer_id, severity, category, alert_code, alert_title,
                                alert_message, trigger_value, threshold_limit, is_tripped,
                                triggered_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            tx_id, a.get("severity", "INFO"), a.get("category", "ELECTRICAL"),
                            a.get("code", "ALT-001"), a.get("title", "Telemetry Event"),
                            a.get("message", "Telemetry received"), str(a.get("value", "")),
                            str(a.get("threshold", "")), 1 if a.get("is_tripped") else 0,
                            now_str
                        ))

                    # Insert Kafka event stream logs
                    if kafka_events:
                        for ke in kafka_events:
                            cur.execute("""
                                INSERT INTO kafka_event_stream (
                                    topic_name, partition_id, offset_num, message_key, payload_json, ingested_at
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                ke.get("topic", "transformer.telemetry.raw"),
                                ke.get("partition", 0),
                                ke.get("offset", 0),
                                tx_id,
                                json.dumps(ke.get("payload", {})),
                                now_str
                            ))

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error persisting to MySQL: {e}")

        # 2. Save to SQLite fallback
        try:
            cur = self.sqlite_conn.cursor()
            cur.execute("""
                INSERT INTO telemetry_frames (
                    transformer_id, voltage_v, current_a, winding_temp_c, vibration_g,
                    oil_level, ambient_temp_c, rel_humidity_pct, wind_speed_kmh, relay_status, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, telemetry.get("voltage", 230.0), telemetry.get("current", 10.0),
                telemetry.get("temperature", 34.0), telemetry.get("vibration", 0.05),
                telemetry.get("oil_level", "NORMAL"), telemetry.get("ambient_temp", 28.0),
                telemetry.get("rel_humidity", 45.0), telemetry.get("wind_speed", 12.0),
                "OPEN_TRIPPED" if protection.get("is_tripped") else "CLOSED", now_str
            ))
            frame_id = cur.lastrowid

            for a in alerts:
                cur.execute("""
                    INSERT INTO classified_alerts (
                        transformer_id, severity, category, alert_code, alert_title,
                        alert_message, trigger_value, threshold_limit, is_tripped, triggered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx_id, a.get("severity", "INFO"), a.get("category", "ELECTRICAL"),
                    a.get("code", "ALT-001"), a.get("title", "Telemetry Event"),
                    a.get("message", "Telemetry received"), str(a.get("value", "")),
                    str(a.get("threshold", "")), 1 if a.get("is_tripped") else 0, now_str
                ))

            self.sqlite_conn.commit()
        except Exception as e:
            logger.error(f"Error persisting to SQLite: {e}")

        return {"status": "ok", "db_engine": "MySQL" if self.mysql_enabled else "SQLite (Local Embedded)"}

    def get_classified_alerts(self, limit: int = 30, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves recent classified alerts from active database."""
        conn = self.get_mysql_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    if severity and severity.upper() != "ALL":
                        cur.execute("""
                            SELECT alert_id, transformer_id, severity, category, alert_code,
                                   alert_title, alert_message, trigger_value, threshold_limit,
                                   is_tripped, is_acknowledged, triggered_at
                            FROM classified_alerts
                            WHERE severity = %s
                            ORDER BY alert_id DESC LIMIT %s
                        """, (severity.upper(), limit))
                    else:
                        cur.execute("""
                            SELECT alert_id, transformer_id, severity, category, alert_code,
                                   alert_title, alert_message, trigger_value, threshold_limit,
                                   is_tripped, is_acknowledged, triggered_at
                            FROM classified_alerts
                            ORDER BY alert_id DESC LIMIT %s
                        """, (limit,))
                    rows = cur.fetchall()
                conn.close()
                for r in rows:
                    if isinstance(r.get("triggered_at"), datetime):
                        r["triggered_at"] = r["triggered_at"].strftime("%Y-%m-%d %H:%M:%S")
                return rows
            except Exception as e:
                logger.error(f"Error querying MySQL alerts: {e}")

        # Fallback to SQLite
        try:
            cur = self.sqlite_conn.cursor()
            if severity and severity.upper() != "ALL":
                cur.execute("""
                    SELECT alert_id, transformer_id, severity, category, alert_code,
                           alert_title, alert_message, trigger_value, threshold_limit,
                           is_tripped, is_acknowledged, triggered_at
                    FROM classified_alerts
                    WHERE severity = ?
                    ORDER BY alert_id DESC LIMIT ?
                """, (severity.upper(), limit))
            else:
                cur.execute("""
                    SELECT alert_id, transformer_id, severity, category, alert_code,
                           alert_title, alert_message, trigger_value, threshold_limit,
                           is_tripped, is_acknowledged, triggered_at
                    FROM classified_alerts
                    ORDER BY alert_id DESC LIMIT ?
                """, (limit,))
            rows = [dict(row) for row in cur.fetchall()]
            return rows
        except Exception as e:
            logger.error(f"Error querying SQLite alerts: {e}")
            return []

    def acknowledge_alert(self, alert_id: int, operator_name: str = "Control Room Operator") -> bool:
        """Marks an alert as acknowledged in database."""
        conn = self.get_mysql_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE classified_alerts
                        SET is_acknowledged = 1, acknowledged_by = %s, acknowledged_at = NOW()
                        WHERE alert_id = %s
                    """, (operator_name, alert_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error acknowledging in MySQL: {e}")

        try:
            cur = self.sqlite_conn.cursor()
            cur.execute("""
                UPDATE classified_alerts
                SET is_acknowledged = 1, acknowledged_by = ?
                WHERE alert_id = ?
            """, (operator_name, alert_id))
            self.sqlite_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error acknowledging in SQLite: {e}")
            return False

    def get_database_status(self) -> Dict[str, Any]:
        """Returns database connectivity and operational statistics."""
        return {
            "mysql_connected": self.mysql_enabled,
            "mysql_host": f"{CONFIG.MYSQL_HOST}:{CONFIG.MYSQL_PORT}",
            "mysql_database": CONFIG.MYSQL_DATABASE,
            "engine": "MySQL 8.0 (Active)" if self.mysql_enabled else "SQLite Embedded Engine (Active)",
            "schema_version": "2.4-enterprise",
            "workbench_ready": True
        }

DB = DatabaseManager()
