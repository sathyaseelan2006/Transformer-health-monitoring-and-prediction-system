const CONFIG = {
    nominalVoltage: 230,
    nominalCurrent: 10,
    nominalTemperature: 30,
    maxTemperature: 80,
    nominalVibration: 0.05,
    maxVibration: 0.5,
    ratedLifeYears: 25,
    warningThi: 70,
    criticalThi: 50
};

const scenarios = [
    {
        name: "Normal Baseline",
        telemetry: { voltage: 231.2, current: 9.8, temperature: 33.4, vibration: 0.052, oil_level: "NORMAL", ambient_temp: 28.2, rel_humidity: 48, wind_speed: 11.6 }
    },
    {
        name: "Overload Drift",
        telemetry: { voltage: 226.8, current: 16.7, temperature: 67.5, vibration: 0.18, oil_level: "NORMAL", ambient_temp: 32.0, rel_humidity: 41, wind_speed: 14.2 }
    },
    {
        name: "Thermal Runaway",
        telemetry: { voltage: 229.5, current: 13.8, temperature: 91.0, vibration: 0.14, oil_level: "LOW", ambient_temp: 39.4, rel_humidity: 24, wind_speed: 21.0 }
    },
    {
        name: "Vibration Anomaly",
        telemetry: { voltage: 232.4, current: 10.9, temperature: 46.5, vibration: 0.64, oil_level: "NORMAL", ambient_temp: 29.6, rel_humidity: 52, wind_speed: 16.8 }
    },
    {
        name: "Wildfire Exposure",
        telemetry: { voltage: 236.0, current: 12.3, temperature: 74.2, vibration: 0.16, oil_level: "LOW", ambient_temp: 43.8, rel_humidity: 13, wind_speed: 38.0 }
    }
];

const history = [];
const signalHistory = { voltage: [], temperature: [], vibration: [] };
const analyticsHistory = { temperature: [], current: [] };
let scenarioIndex = 0;
let usingApi = false;

const $ = (id) => document.getElementById(id);
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const fmt = (value, digits = 1) => Number(value).toFixed(digits);

function nowTime() {
    return new Intl.DateTimeFormat("en", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
    }).format(new Date());
}

function calculateStress(tel) {
    const sV = clamp(Math.abs(tel.voltage - CONFIG.nominalVoltage) / CONFIG.nominalVoltage, 0, 1);
    const sI = clamp(Math.abs(tel.current - CONFIG.nominalCurrent) / CONFIG.nominalCurrent, 0, 1);
    const sT = clamp((tel.temperature - CONFIG.nominalTemperature) / (CONFIG.maxTemperature - CONFIG.nominalTemperature), 0, 1);
    const sVib = clamp((tel.vibration - CONFIG.nominalVibration) / (CONFIG.maxVibration - CONFIG.nominalVibration), 0, 1);
    const weighted = (0.25 * sV) + (0.35 * sI) + (0.25 * sT) + (0.15 * sVib);
    const thi = clamp(100 - (weighted * 100), 0, 100);
    let health = "OPTIMAL / GOOD";

    if (thi < CONFIG.criticalThi) health = "CRITICAL / SEVERE RISK";
    else if (thi < CONFIG.warningThi) health = "WARNING / DEGRADED";
    else if (thi < 85) health = "MODERATE / ACCEPTABLE";

    return { s_v: sV, s_i: sI, s_t: sT, s_vib: sVib, thi, health_status: health };
}

function calculateProtection(tel) {
    const reasons = [];
    if (tel.voltage > 265) reasons.push("Over-voltage");
    if (tel.voltage < 185) reasons.push("Under-voltage");
    if (tel.current > 15) reasons.push("Overload current");
    if (tel.temperature > 85) reasons.push("Thermal trip");
    if (tel.vibration > 0.6) reasons.push("Mechanical vibration");
    if (tel.oil_level === "CRITICAL") reasons.push("Critical oil level");

    return {
        is_tripped: reasons.length > 0,
        relay_state: reasons.length > 0 ? "OPEN / TRIPPED" : "CLOSED / ENERGIZED",
        trip_reason: reasons.length > 0 ? reasons.join(", ") : "Deterministic edge logic normal"
    };
}

function calculateEnvironmentalRisk(tel) {
    const heat = clamp((tel.ambient_temp - 25) / 20, 0, 1) * 35;
    const dryness = clamp((55 - tel.rel_humidity) / 45, 0, 1) * 30;
    const wind = clamp(tel.wind_speed / 45, 0, 1) * 22;
    const transformerHeat = clamp((tel.temperature - 55) / 35, 0, 1) * 13;
    const oilPenalty = tel.oil_level === "LOW" ? 8 : tel.oil_level === "CRITICAL" ? 16 : 0;
    const fwi = clamp(heat + dryness + wind + transformerHeat + oilPenalty, 0, 100);
    let level = "LOW";
    let severity = "Contained";
    let description = "Ambient humidity and temperature are within normal operating margins.";

    if (fwi >= 75) {
        level = "EXTREME";
        severity = "Wildfire disaster risk";
        description = "Hot, dry, windy conditions amplify the consequence of arcing, overheating, or insulation failure.";
    } else if (fwi >= 55) {
        level = "HIGH";
        severity = "Elevated hazard";
        description = "Environmental exposure is high enough to raise maintenance priority above health index alone.";
    } else if (fwi >= 35) {
        level = "MODERATE";
        severity = "Watch condition";
        description = "Site conditions warrant closer observation if transformer stress continues to rise.";
    }

    return { fwi, level, severity, description };
}

function calculatePrediction(stress) {
    const rul = CONFIG.ratedLifeYears * (stress.thi / 100);
    const recent = history.slice(-10);
    let slope = 0.28;

    if (recent.length >= 2) {
        const first = recent[0].thi;
        const last = recent[recent.length - 1].thi;
        slope = clamp((first - last) / Math.max(1, recent.length - 1), 0.05, 1.85);
    } else {
        slope = stress.thi > 85 ? 0.16 : stress.thi > 70 ? 0.34 : stress.thi > 50 ? 0.72 : 1.35;
    }

    const days = Math.max(3, Math.round((stress.thi - CONFIG.warningThi) / slope));
    const service = new Date();
    service.setDate(service.getDate() + clamp(days, 3, 365));

    return {
        rul_years: rul,
        daily_slope: slope,
        projected_service_date: service.toLocaleDateString("en", { day: "2-digit", month: "short", year: "numeric" })
    };
}

function normalizeApiPayload(data) {
    const payload = data.data || data;
    const tel = payload.telemetry || payload;
    const stress = payload.stress || calculateStress(tel);
    const protection = payload.protection || calculateProtection(tel);
    const environmental = payload.environmental_risk || calculateEnvironmentalRisk(tel);
    const prediction = payload.prediction || calculatePrediction(stress);
    const lora = payload.lora || {
        frequency: "433.175 MHz",
        spreading_factor: "SF7 / BW 125 kHz",
        rssi: -78.0,
        snr: 9.2,
        packet_loss: 0.0,
        gateway_status: "ONLINE (P2P Link Active)",
        packet_count: 1
    };
    return { telemetry: tel, stress, protection, environmental, prediction, lora };
}

function simulatedPayload() {
    const base = structuredClone(scenarios[scenarioIndex].telemetry);
    const now = Date.now();
    const drift = Math.sin(now / 1700);
    const loadWave = Math.sin(now / 2300) * 1.25;
    base.voltage += drift * 5.2 + Math.sin(now / 900) * 1.4;
    base.current += loadWave * 1.1;
    base.temperature += Math.sin(now / 3600) * 4.2 + Math.max(0, loadWave) * 1.8;
    base.vibration += Math.max(0, Math.sin(now / 1100)) * 0.065 + Math.abs(Math.sin(now / 2100)) * 0.018;

    const stress = calculateStress(base);
    history.push({ at: Date.now(), thi: stress.thi });
    if (history.length > 80) history.shift();

    return {
        telemetry: base,
        stress,
        protection: calculateProtection(base),
        environmental: calculateEnvironmentalRisk(base),
        prediction: calculatePrediction(stress),
        lora: {
            frequency: "433.175 MHz",
            spreading_factor: "SF7 / BW 125 kHz",
            rssi: -78.0 + (Math.sin(now / 1500) * 1.5),
            snr: 9.2 + (Math.cos(now / 2000) * 0.4),
            packet_loss: 0.0,
            gateway_status: "ONLINE (Simulation)",
            packet_count: history.length
        }
    };
}

async function readTelemetry() {
    try {
        const response = await fetch("/api/telemetry", { cache: "no-store" });
        if (!response.ok) throw new Error("API unavailable");
        usingApi = true;
        $("dataSourcePill").textContent = "Java API live";
        return normalizeApiPayload(await response.json());
    } catch (_error) {
        usingApi = false;
        $("dataSourcePill").textContent = "Static simulation";
        return simulatedPayload();
    }
}

function setRing(thi) {
    const circumference = 552.92;
    const offset = circumference - (circumference * thi / 100);
    const ring = $("thiRing");
    const color = thi < 50 ? "var(--red)" : thi < 70 ? "var(--amber)" : thi < 85 ? "var(--cyan)" : "var(--green)";
    ring.style.strokeDashoffset = offset;
    ring.style.stroke = color;
    $("ringThi").textContent = Math.round(thi);
    $("ringThi").style.color = color;
}

function setStress(id, value) {
    $(`${id}Text`).textContent = value.toFixed(3);
    $(`${id}Bar`).style.width = `${clamp(value * 100, 0, 100)}%`;
}

function updateTwin(tel, protection) {
    const tripped = protection.is_tripped;
    const modelAlert = $("modelAlert");
    if (modelAlert) {
        modelAlert.textContent = tripped ? "PROTECTION TRIPPED" : "PROTECTION ARMED";
        modelAlert.style.color = tripped ? "var(--red)" : "var(--muted)";
    }
    const modelTelemetry = $("modelTelemetry");
    if (modelTelemetry) {
        modelTelemetry.textContent = `OIL ${tel.oil_level} / ${Number(tel.temperature).toFixed(0)} C`;
    }
    const relayBlade = $("relayBlade");
    if (relayBlade) {
        relayBlade.setAttribute("x2", tripped ? "462" : "468");
        relayBlade.setAttribute("y2", tripped ? "130" : "164");
        relayBlade.style.stroke = tripped ? "var(--red)" : "var(--green)";
    }
    const loadLine = $("loadLine");
    if (loadLine) {
        loadLine.style.stroke = tripped ? "rgba(148, 163, 184, 0.36)" : "url(#flowGradient)";
    }

    const oilLevel = $("oilLevel");
    if (oilLevel) {
        if (tel.oil_level === "CRITICAL") {
            oilLevel.setAttribute("y", "204");
            oilLevel.setAttribute("height", "50");
            oilLevel.style.fill = "rgba(239, 68, 68, 0.22)";
        } else if (tel.oil_level === "LOW") {
            oilLevel.setAttribute("y", "150");
            oilLevel.setAttribute("height", "104");
            oilLevel.style.fill = "rgba(245, 158, 11, 0.18)";
        } else {
            oilLevel.setAttribute("y", "92");
            oilLevel.setAttribute("height", "162");
            oilLevel.style.fill = "rgba(56, 189, 248, 0.16)";
        }
    }

    const primaryCoil = $("primaryCoil");
    if (primaryCoil) {
        primaryCoil.style.opacity = tel.temperature > 80 ? "1" : "0.86";
    }
    const tankBody = $("tankBody");
    if (tankBody) {
        tankBody.style.transform = tel.vibration > 0.5 ? "translate(2px, -1px)" : "none";
    }
}

function partsForecast(tel, stress, env) {
    const parts = [
        {
            name: "Insulating oil service",
            priority: tel.oil_level === "NORMAL" ? "Monitor" : "Urgent",
            meta: tel.oil_level === "NORMAL" ? "Sample at next inspection" : "Oil top-up and dielectric test required",
            days: tel.oil_level === "NORMAL" ? 96 : 7
        },
        {
            name: "Cooling and winding inspection",
            priority: stress.s_t > 0.75 ? "Urgent" : stress.s_t > 0.45 ? "Warning" : "Monitor",
            meta: stress.s_t > 0.45 ? "Thermal loading trend above normal" : "No abnormal thermal drift",
            days: stress.s_t > 0.75 ? 5 : stress.s_t > 0.45 ? 24 : 120
        },
        {
            name: "Bushing and terminal check",
            priority: stress.s_v > 0.12 ? "Warning" : "Monitor",
            meta: stress.s_v > 0.12 ? "Voltage deviation suggests connection review" : "Stable voltage profile",
            days: stress.s_v > 0.12 ? 30 : 150
        },
        {
            name: "Mounting and vibration pads",
            priority: stress.s_vib > 0.55 ? "Urgent" : stress.s_vib > 0.25 ? "Warning" : "Monitor",
            meta: stress.s_vib > 0.25 ? "Mechanical signature requires field inspection" : "Mechanical channel stable",
            days: stress.s_vib > 0.55 ? 10 : stress.s_vib > 0.25 ? 40 : 180
        }
    ];

    if (env.level === "HIGH" || env.level === "EXTREME") {
        parts[0].days = Math.min(parts[0].days, 14);
        parts[0].priority = parts[0].priority === "Monitor" ? "Warning" : parts[0].priority;
    }

    return parts;
}

function renderParts(parts) {
    $("partsList").innerHTML = parts.map((part) => {
        const cls = part.priority === "Urgent" ? "urgent" : part.priority === "Warning" ? "warn" : "";
        return `
            <article>
                <div class="part-title">
                    <strong>${part.name}</strong>
                    <span class="part-priority ${cls}">${part.priority}</span>
                </div>
                <span class="part-meta">Estimated action window</span>
                <strong>${part.days} days</strong>
                <span class="part-meta">${part.meta}</span>
            </article>
        `;
    }).join("");
}

function renderTimeline(payload) {
    const scenario = usingApi ? "Live API frame" : scenarios[scenarioIndex].name;
    const events = [
        { title: "Telemetry frame received", body: `${scenario} processed through ESF health calculation.` },
        { title: "Protection logic evaluated", body: payload.protection.trip_reason },
        { title: "Maintenance forecast refreshed", body: `Next service currently projected for ${payload.prediction.projected_service_date}.` }
    ];

    $("timeline").innerHTML = events.map((event, index) => `
        <div class="timeline-item">
            <div class="timeline-time">${index === 0 ? nowTime() : `T+0${index}`}</div>
            <div class="timeline-copy">
                <strong>${event.title}</strong>
                ${event.body}
            </div>
        </div>
    `).join("");
}

function updateSummary(payload) {
    const { telemetry: tel, stress, protection, environmental: env, prediction } = payload;
    const dominant = [
        ["electrical load", stress.s_i],
        ["thermal rise", stress.s_t],
        ["voltage deviation", stress.s_v],
        ["mechanical vibration", stress.s_vib]
    ].sort((a, b) => b[1] - a[1])[0][0];

    $("aiSummary").textContent = protection.is_tripped
        ? `Emergency route recommendation: isolate asset, verify ${protection.trip_reason.toLowerCase()}, inspect oil and winding temperature, then run local RAG technician playbook.`
        : `Omni route would send the latest frame to the RUL predictor and diagnostic model. Dominant degradation factor is ${dominant}; RUL is ${fmt(prediction.rul_years, 1)} years with ${env.level.toLowerCase()} environmental risk.`;

    $("confidenceChip").textContent = tel.vibration > 0.5 ? "88% signal confidence" : "96% signal confidence";
}

function updateSignalGraphs(tel) {
    const signals = [
        { key: "voltage", value: tel.voltage, min: 210, max: 250, trace: "voltageTrace", valueId: "voltageSignalValue", statusId: "voltageSignalStatus", unit: " V", status: tel.voltage < 220 || tel.voltage > 240 ? "Outside nominal envelope" : "Nominal envelope" },
        { key: "temperature", value: tel.temperature, min: 20, max: 100, trace: "temperatureTrace", valueId: "temperatureSignalValue", statusId: "temperatureSignalStatus", unit: " C", status: tel.temperature > 80 ? "Thermal limit approaching" : "Thermal margin healthy" },
        { key: "vibration", value: tel.vibration, min: 0, max: 0.8, trace: "vibrationTrace", valueId: "vibrationSignalValue", statusId: "vibrationSignalStatus", unit: " g", status: tel.vibration > 0.5 ? "Mechanical anomaly detected" : "Stable mechanical profile" }
    ];

    signals.forEach((signal) => {
        const values = signalHistory[signal.key];
        if (values.length === 0) {
            values.push(...Array(8).fill(signal.value));
        } else {
            values.push(signal.value);
        }
        if (values.length > 36) values.shift();
        const points = values.map((value, index) => {
            const x = values.length === 1 ? 0 : (index / (values.length - 1)) * 180;
            const normalized = clamp((value - signal.min) / (signal.max - signal.min), 0, 1);
            return `${x.toFixed(1)},${(40 - normalized * 32).toFixed(1)}`;
        }).join(" ");

        const traceEl = $(signal.trace);
        if (traceEl) traceEl.setAttribute("points", points);

        const areaEl = $(`${signal.key}Area`);
        if (areaEl) areaEl.setAttribute("points", `${points} 180,44 0,44`);

        const valEl = $(signal.valueId);
        if (valEl) valEl.textContent = `${fmt(signal.value, signal.key === "vibration" ? 3 : 1)}${signal.unit}`;

        const statusEl = $(signal.statusId);
        if (statusEl) statusEl.textContent = signal.status;
    });
}

let wavePhase = 0;
let latestPayload = null;

function updateSpatialDynamicGraphs(tel, stress) {
    wavePhase += 0.06;

    // 1. Calculate dynamic wave peak amplitudes based on live telemetry stress
    const vAmp = 14 + (stress.s_v * 24) + Math.sin(wavePhase * 1.2) * 4;
    const iAmp = 12 + (stress.s_i * 20) + Math.cos(wavePhase * 1.5) * 3.5;
    const vibAmp = 10 + (stress.s_vib * 26) + Math.sin(wavePhase * 2.0) * 5;
    const thermalPeakY = clamp(60 - (stress.s_t * 35) + Math.sin(wavePhase * 0.9) * 8, 15, 80);

    // 2. Generate smooth sine wave paths for Graph (a)
    // s-axis (Voltage - Cyan)
    let dMeasuredV = "M 45 45";
    for (let x = 45; x <= 380; x += 15) {
        const y = 45 + Math.sin((x - 45) * 0.05 + wavePhase) * vAmp;
        dMeasuredV += ` L ${x} ${y.toFixed(1)}`;
    }
    let dPredictedV = "M 380 45";
    for (let x = 380; x <= 505; x += 15) {
        const y = 45 + Math.sin((x - 45) * 0.08 + wavePhase * 1.8) * (vAmp * 1.4);
        dPredictedV += ` L ${x} ${y.toFixed(1)}`;
    }

    // y-axis (Current - Lime)
    let dMeasuredI = "M 45 105";
    for (let x = 45; x <= 380; x += 15) {
        const y = 105 + Math.sin((x - 45) * 0.05 + wavePhase + 1.5) * iAmp;
        dMeasuredI += ` L ${x} ${y.toFixed(1)}`;
    }
    let dPredictedI = "M 380 105";
    for (let x = 380; x <= 505; x += 15) {
        const y = 105 + Math.cos((x - 45) * 0.07 + wavePhase * 1.4) * (iAmp * 1.3);
        dPredictedI += ` L ${x} ${y.toFixed(1)}`;
    }

    // z-axis (Vibration - Pink/Purple)
    let dMeasuredVib = "M 45 165";
    for (let x = 45; x <= 380; x += 15) {
        const y = 165 + Math.sin((x - 45) * 0.05 + wavePhase + 3.0) * vibAmp;
        dMeasuredVib += ` L ${x} ${y.toFixed(1)}`;
    }
    let dPredictedVib = "M 380 165";
    for (let x = 380; x <= 505; x += 15) {
        const y = 165 + Math.sin((x - 45) * 0.09 + wavePhase * 2.2) * (vibAmp * 1.5);
        dPredictedVib += ` L ${x} ${y.toFixed(1)}`;
    }

    // Update SVG paths in Graph (a)
    const cardA = document.querySelectorAll(".wave-graph-card")[0];
    if (cardA) {
        const measuredVEl = cardA.querySelector(".wave-path.measured-v");
        const predictedVEl = cardA.querySelector(".wave-path.predicted-v");
        const measuredIEl = cardA.querySelector(".wave-path.measured-i");
        const predictedIEl = cardA.querySelector(".wave-path.predicted-i");
        const measuredVibEl = cardA.querySelector(".wave-path.measured-vib");
        const predictedVibEl = cardA.querySelector(".wave-path.predicted-vib");

        if (measuredVEl) measuredVEl.setAttribute("d", dMeasuredV);
        if (predictedVEl) predictedVEl.setAttribute("d", dPredictedV);
        if (measuredIEl) measuredIEl.setAttribute("d", dMeasuredI);
        if (predictedIEl) predictedIEl.setAttribute("d", dPredictedI);
        if (measuredVibEl) measuredVibEl.setAttribute("d", dMeasuredVib);
        if (predictedVibEl) predictedVibEl.setAttribute("d", dPredictedVib);
    }

    // 3. Dynamic Anomaly Peak Focus Circles Y-positions
    const yPeakA = 45 + Math.sin((435 - 45) * 0.08 + wavePhase * 1.8) * (vAmp * 1.4);
    const yPeakB = 105 + Math.cos((435 - 45) * 0.07 + wavePhase * 1.4) * (iAmp * 1.3);
    const yPeakVib = 165 + Math.sin((435 - 45) * 0.09 + wavePhase * 2.2) * (vibAmp * 1.5);

    const focusGroups = document.querySelectorAll(".graph-peak-focus");
    if (focusGroups[0]) focusGroups[0].setAttribute("transform", `translate(435, ${yPeakA.toFixed(1)})`);
    if (focusGroups[1]) focusGroups[1].setAttribute("transform", `translate(435, ${yPeakB.toFixed(1)})`);
    if (focusGroups[2]) focusGroups[2].setAttribute("transform", `translate(435, ${yPeakVib.toFixed(1)})`);

    // 4. Update Graph (c) Thermal Tension Peak
    const dPredictedThermal = `M 380 125 L 390 125 L 395 ${thermalPeakY.toFixed(1)} L 445 ${thermalPeakY.toFixed(1)} L 450 125 L 505 125`;
    const cardC = document.querySelectorAll(".wave-graph-card")[1];
    if (cardC) {
        const cardCPred = cardC.querySelector(".wave-path.predicted-v");
        if (cardCPred) cardCPred.setAttribute("d", dPredictedThermal);
    }

    if (focusGroups[3]) focusGroups[3].setAttribute("transform", `translate(420, ${thermalPeakY.toFixed(1)})`);

    // 5. Update SVG Leader Lines dynamically to track moving focal circles!
    const lineAEl = document.querySelector(".leader-line.line-a");
    const lineBEl = document.querySelector(".leader-line.line-b");
    const lineCEl = document.querySelector(".leader-line.line-c");

    const lineAyStart = 72 + (yPeakA * 0.55);
    if (lineAEl) lineAEl.setAttribute("d", `M 475 ${lineAyStart.toFixed(1)} C 600 ${lineAyStart.toFixed(1)}, 680 145, 840 145`);

    const lineByStart = 72 + (yPeakB * 0.55);
    if (lineBEl) lineBEl.setAttribute("d", `M 475 ${lineByStart.toFixed(1)} C 610 ${lineByStart.toFixed(1)}, 700 230, 880 230`);

    const lineCyStart = 345 + (thermalPeakY * 0.85);
    if (lineCEl) lineCEl.setAttribute("d", `M 475 ${lineCyStart.toFixed(1)} C 610 ${lineCyStart.toFixed(1)}, 710 425, 860 425`);
}

function updateAnalytics(tel, stress) {
    const temperatureLimit = 85;
    const currentLimit = 15;
    const vibrationLimit = 0.5;
    const temperaturePercent = tel.temperature / temperatureLimit * 100;
    const currentPercent = tel.current / currentLimit * 100;
    analyticsHistory.temperature.push(temperaturePercent);
    analyticsHistory.current.push(currentPercent);
    Object.values(analyticsHistory).forEach((values) => { if (values.length > 24) values.shift(); });

    const trendPath = (values) => values.map((value, index) => {
        const x = 42 + index / Math.max(values.length - 1, 1) * 548;
        const y = 136 - clamp(value, 0, 100) / 100 * 116;
        return `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(" ");
    $("temperatureTrend").setAttribute("d", trendPath(analyticsHistory.temperature));
    $("currentTrend").setAttribute("d", trendPath(analyticsHistory.current));
    $("analyticsTemp").textContent = `${fmt(tel.temperature, 1)} °C · ${fmt(temperaturePercent, 0)}%`;
    $("analyticsCurrent").textContent = `${fmt(tel.current, 1)} A · ${fmt(currentPercent, 0)}%`;
    $("analyticsUpdated").textContent = `Updated ${nowTime()}`;

    const readings = [
        { name: "Voltage deviation", value: tel.voltage, unit: "V", percent: Math.abs(tel.voltage - CONFIG.nominalVoltage) / (CONFIG.nominalVoltage * 0.1) * 100, detail: "230 V nominal · ±10% band", status: Math.abs(tel.voltage - CONFIG.nominalVoltage) > CONFIG.nominalVoltage * 0.1 ? "warning" : "healthy" },
        { name: "Load current", value: tel.current, unit: "A", percent: currentPercent, detail: "15 A limit", status: currentPercent >= 100 ? "critical" : currentPercent >= 85 ? "warning" : "healthy" },
        { name: "Winding temperature", value: tel.temperature, unit: "°C", percent: temperaturePercent, detail: "85 °C trip", status: temperaturePercent >= 100 ? "critical" : temperaturePercent >= 85 ? "warning" : "healthy" },
        { name: "Vibration", value: tel.vibration, unit: "g", percent: tel.vibration / vibrationLimit * 100, detail: "0.50 g limit", status: tel.vibration >= vibrationLimit ? "critical" : tel.vibration >= vibrationLimit * 0.8 ? "warning" : "healthy" }
    ];
    const ticks = (values) => values.map((tick) => `<span>${tick}%</span>`).join("");
    const utilizationBars = readings.map((item) => {
        const width = clamp(item.percent, 0, 120) / 120 * 100;
        const color = item.status === "critical" ? "#ef4444" : item.status === "warning" ? "#f59e0b" : "#22c55e";
        const status = item.status === "healthy" ? "Normal" : item.status === "warning" ? "Near limit" : "At / over limit";
        return `<div class="bar-chart-row"><div class="bar-chart-name"><strong>${item.name}</strong><small>${fmt(item.value, item.unit === "g" ? 3 : 1)} ${item.unit} · ${item.detail}</small></div><div class="bar-plot limit-plot" role="img" aria-label="${item.name}: ${fmt(item.percent, 0)} percent of reference, ${status}"><span style="width:${width.toFixed(1)}%;background:${color}"></span></div><strong class="bar-chart-value">${fmt(item.percent, 0)}%</strong></div>`;
    }).join("");
    $("utilizationChart").innerHTML = `<div class="bar-chart-axis-row"><span></span><div class="bar-chart-axis">${ticks([0, 50, 100, 120])}</div><span></span></div>${utilizationBars}`;

    const oilPenalty = tel.oil_level !== "NORMAL" ? 40 : 0;
    const components = [
        { name: "HV & LV bushings", score: clamp(100 - Math.abs(tel.voltage - CONFIG.nominalVoltage) * 0.8 - tel.vibration * 15, 0, 100) },
        { name: "Winding assembly", score: clamp(100 - (tel.temperature - CONFIG.nominalTemperature) * 1.8 - Math.abs(tel.current - CONFIG.nominalCurrent) * 4, 0, 100) },
        { name: "Oil & cooling", score: clamp(100 - (tel.temperature - CONFIG.nominalTemperature) * 1.2 - oilPenalty, 0, 100) },
        { name: "Paper insulation", score: clamp(stress.thi * 0.95, 0, 100) }
    ];
    const componentBars = components.map(({ name, score }) => {
        const status = score < 40 ? "critical" : score < 70 ? "warning" : "healthy";
        const label = status === "healthy" ? "Healthy" : status === "warning" ? "Warning" : "Critical";
        const color = status === "critical" ? "#ef4444" : status === "warning" ? "#f59e0b" : "#22c55e";
        return `<div class="bar-chart-row"><div class="bar-chart-name"><strong>${name}</strong><small style="color:${color}">${label}</small></div><div class="bar-plot component-plot" role="img" aria-label="${name}: ${fmt(score, 0)} percent, ${label}"><span style="width:${score.toFixed(1)}%;background:${color}"></span><i class="health-threshold threshold-warning"></i><i class="health-threshold threshold-healthy"></i></div><strong class="bar-chart-value">${fmt(score, 0)}%</strong></div>`;
    }).join("");
    $("componentChart").innerHTML = `<div class="bar-chart-axis-row component-axis-row"><span></span><div class="bar-chart-axis">${ticks([0, 25, 50, 75, 100])}</div><span></span></div>${componentBars}`;
}

function render(payload) {
    latestPayload = payload;
    const { telemetry: tel, stress, protection, environmental: env, prediction, lora } = payload;
    const tripped = protection.is_tripped;

    if ($("thiValue")) $("thiValue").textContent = fmt(stress.thi, 1);
    if ($("healthStatus")) $("healthStatus").textContent = stress.health_status;
    if ($("rulValue")) $("rulValue").textContent = fmt(prediction.rul_years, 1);
    if ($("serviceDate")) $("serviceDate").textContent = prediction.projected_service_date;
    if ($("relayState")) $("relayState").textContent = protection.relay_state;
    if ($("tripReason")) $("tripReason").textContent = protection.trip_reason;

    setRing(stress.thi);
    setStress("sv", stress.s_v);
    setStress("si", stress.s_i);
    setStress("st", stress.s_t);
    setStress("svib", stress.s_vib);

    if ($("voltageValue")) $("voltageValue").textContent = `${fmt(tel.voltage, 1)} V`;
    if ($("currentValue")) $("currentValue").textContent = `${fmt(tel.current, 1)} A`;
    if ($("temperatureValue")) $("temperatureValue").textContent = `${fmt(tel.temperature, 1)} C`;
    if ($("vibrationValue")) $("vibrationValue").textContent = `${fmt(tel.vibration, 3)} g`;
    updateSignalGraphs(tel);

    if ($("riskLevel")) {
        $("riskLevel").textContent = env.level;
        $("riskLevel").className = `risk-pill ${env.level.toLowerCase()}`;
    }
    if ($("fwiValue")) $("fwiValue").textContent = fmt(env.fwi, 1);
    if ($("riskMeter")) $("riskMeter").style.width = `${clamp(env.fwi, 0, 100)}%`;
    if ($("ambientValue")) $("ambientValue").textContent = `${fmt(tel.ambient_temp, 1)} C`;
    if ($("humidityValue")) $("humidityValue").textContent = `${fmt(tel.rel_humidity, 0)}%`;
    if ($("windValue")) $("windValue").textContent = `${fmt(tel.wind_speed, 1)} km/h`;
    if ($("riskDescription")) $("riskDescription").textContent = `${env.severity}. ${env.description}`;

    // Update LoRa Communication Telemetry (Module 04)
    if (lora) {
        if ($("loraFreq")) $("loraFreq").textContent = `${lora.frequency} · ${lora.spreading_factor}`;
        if ($("loraLinkQuality")) $("loraLinkQuality").textContent = `RSSI: ${fmt(lora.rssi, 1)} dBm | SNR: ${fmt(lora.snr, 1)} dB`;
        if ($("loraFrameCount")) $("loraFrameCount").textContent = `${lora.packet_count || history.length} frames`;
        if ($("loraStatusBadge")) {
            $("loraStatusBadge").textContent = `SX1278 ${lora.gateway_status ? "ONLINE" : "STANDBY"}`;
        }
    }

    const dangerAwareEl = document.querySelector(".danger-aware");
    if (dangerAwareEl) dangerAwareEl.classList.toggle("tripped", tripped);

    const twinPanelEl = document.querySelector(".twin-panel");
    if (twinPanelEl) twinPanelEl.classList.toggle("tripped", tripped);

    if ($("maintenanceMode")) $("maintenanceMode").textContent = tripped ? "Corrective" : "Predictive";

    updateTwin(tel, protection);
    renderParts(partsForecast(tel, stress, env));
    renderTimeline(payload);
    updateSummary(payload);
    updateSpatialDynamicGraphs(tel, stress);
    updateAnalytics(tel, stress);
}

async function runAiDiagnostics() {
    const modalEl = document.getElementById("aiDiagModal");
    if (!modalEl) return;
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    const loadingEl = $("diagLoadingState");
    const contentEl = $("diagContentState");
    if (loadingEl) loadingEl.style.display = "block";
    if (contentEl) contentEl.style.display = "none";

    try {
        const res = await fetch("/api/diagnose", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ override: false })
        });
        const report = await res.json();

        if (loadingEl) loadingEl.style.display = "none";
        if (contentEl) contentEl.style.display = "block";

        if ($("diagSeverityCode")) $("diagSeverityCode").textContent = report.severity_code;
        if ($("diagTimestamp")) $("diagTimestamp").textContent = report.timestamp;
        if ($("diagLikelyCause")) $("diagLikelyCause").textContent = report.likely_cause;

        const banner = $("diagSeverityBanner");
        if (banner) {
            const sev = String(report.severity_code || "").toUpperCase();
            if (sev.includes("SEV-1") || sev.includes("CRITICAL")) {
                banner.style.background = "rgba(239, 68, 68, 0.18)";
                banner.style.borderColor = "rgba(239, 68, 68, 0.5)";
                if ($("diagSeverityCode")) $("diagSeverityCode").className = "badge bg-danger font-monospace px-2 py-1";
            } else if (sev.includes("SEV-2") || sev.includes("HAZARD")) {
                banner.style.background = "rgba(245, 158, 11, 0.18)";
                banner.style.borderColor = "rgba(245, 158, 11, 0.5)";
                if ($("diagSeverityCode")) $("diagSeverityCode").className = "badge bg-warning text-dark font-monospace px-2 py-1";
            } else {
                banner.style.background = "rgba(34, 197, 94, 0.18)";
                banner.style.borderColor = "rgba(34, 197, 94, 0.5)";
                if ($("diagSeverityCode")) $("diagSeverityCode").className = "badge bg-success font-monospace px-2 py-1";
            }
        }

        const playbookEl = $("diagPlaybookList");
        if (playbookEl && report.technician_playbook) {
            playbookEl.innerHTML = report.technician_playbook.map(step => `
                <li class="list-group-item d-flex justify-content-between align-items-start py-2">
                    <div class="ms-2 me-auto">
                        ${step}
                    </div>
                </li>
            `).join("");
        }

        const instrumentsEl = $("diagInstrumentsList");
        if (instrumentsEl && report.recommended_instruments) {
            instrumentsEl.innerHTML = report.recommended_instruments.map(inst => `
                <span class="badge bg-secondary text-info font-monospace py-2 px-3 border border-info border-opacity-25">${inst}</span>
            `).join("");
        }

        if ($("diagRagReferences")) $("diagRagReferences").textContent = Array.isArray(report.rag_references) ? report.rag_references.join(" · ") : report.rag_references;
        if ($("diagModelUsed")) $("diagModelUsed").textContent = `Engine: ${report.model_used}`;
        if ($("diagDisclaimer")) $("diagDisclaimer").textContent = report.disclaimer;
    } catch (err) {
        if (loadingEl) loadingEl.innerHTML = `<p class="text-danger">Failed to execute AI diagnostics: ${err.message}</p>`;
    }
}

async function tick() {
    const payload = await readTelemetry();
    render(payload);
}

// Event Listeners
if ($("refreshButton")) $("refreshButton").addEventListener("click", tick);
if ($("scenarioButton")) {
    $("scenarioButton").addEventListener("click", () => {
        scenarioIndex = (scenarioIndex + 1) % scenarios.length;
        fetch("/api/scenario", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario: scenarios[scenarioIndex].name.toUpperCase().replace(/\s+/g, "_") })
        }).catch(() => {});
        tick();
    });
}
if ($("topScenarioBtn")) {
    $("topScenarioBtn").addEventListener("click", () => {
        scenarioIndex = (scenarioIndex + 1) % scenarios.length;
        fetch("/api/scenario", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario: scenarios[scenarioIndex].name.toUpperCase().replace(/\s+/g, "_") })
        }).catch(() => {});
        tick();
    });
}
if ($("triggerAiDiagBtn")) $("triggerAiDiagBtn").addEventListener("click", runAiDiagnostics);
if ($("cardDiagnoseBtn")) $("cardDiagnoseBtn").addEventListener("click", runAiDiagnostics);
if ($("diagReRunBtn")) $("diagReRunBtn").addEventListener("click", runAiDiagnostics);

// Smooth scroll for module pills
document.querySelectorAll(".mod-pill").forEach(pill => {
    pill.addEventListener("click", (e) => {
        document.querySelectorAll(".mod-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
    });
});

tick();
setInterval(tick, 1800);

// Smooth 30fps animation loop for dynamic telemetry waveform graphs & tracking leader lines
setInterval(() => {
    if (latestPayload) {
        updateSpatialDynamicGraphs(latestPayload.telemetry, latestPayload.stress);
    }
}, 50);
