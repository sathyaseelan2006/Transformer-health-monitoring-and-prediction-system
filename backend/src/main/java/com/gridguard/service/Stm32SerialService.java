package com.gridguard.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fazecast.jSerialComm.SerialPort;
import com.gridguard.config.TransformerConfig;
import com.gridguard.model.TelemetryFrame;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Reads newline-delimited JSON telemetry from the STM32 USB serial port. */
@Service
@RequiredArgsConstructor
@Slf4j
public class Stm32SerialService {

    private final TransformerConfig config;
    private final TelemetryService telemetryService;
    private final ObjectMapper objectMapper;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile boolean running;
    private SerialPort serialPort;

    @PostConstruct
    public void start() {
        running = true;
        executor.submit(this::readLoop);
    }

    private void readLoop() {
        TransformerConfig.STM32Properties settings = config.getStm32();
        serialPort = SerialPort.getCommPort(settings.getSerialPort());
        serialPort.setBaudRate(settings.getBaudRate());
        serialPort.setComPortTimeouts(SerialPort.TIMEOUT_READ_SEMI_BLOCKING, settings.getTimeoutMs(), 0);

        if (!serialPort.openPort()) {
            log.warn("STM32 serial port {} could not be opened", settings.getSerialPort());
            return;
        }

        log.info("STM32 serial telemetry connected on {} at {} baud", settings.getSerialPort(), settings.getBaudRate());
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(serialPort.getInputStream(), StandardCharsets.UTF_8))) {
            while (running) {
                String line = reader.readLine();
                if (line == null || line.isBlank() || !line.trim().startsWith("{")) {
                    continue;
                }
                try {
                    TelemetryFrame frame = objectMapper.readValue(line, TelemetryFrame.class);
                    telemetryService.saveTelemetryFrame(frame);
                } catch (Exception exception) {
                    log.warn("Ignoring invalid STM32 telemetry line: {}", line, exception);
                }
            }
        } catch (Exception exception) {
            if (running) {
                log.error("STM32 serial telemetry reader stopped", exception);
            }
        } finally {
            serialPort.closePort();
        }
    }

    @PreDestroy
    public void stop() {
        running = false;
        if (serialPort != null) {
            serialPort.closePort();
        }
        executor.shutdownNow();
    }
}
