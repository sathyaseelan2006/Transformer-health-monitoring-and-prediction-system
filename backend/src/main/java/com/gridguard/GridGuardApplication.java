package com.gridguard;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * GridGuard OS - Main Spring Boot Application
 * Transformer Health Monitoring & Predictive Maintenance System
 */
@SpringBootApplication
@EnableScheduling
public class GridGuardApplication {

    public static void main(String[] args) {
        SpringApplication.run(GridGuardApplication.class, args);
    }
}
