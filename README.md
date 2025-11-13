# Carmb Raspberry Pi Client

## Overview
This repository contains firmware and client code for controlling a Raspberry Pi-based vehicle platform with motor and servo control capabilities via UART communication.

---

## Files

### PICOW.py

**Description:**
A MicroPython script designed for Raspberry Pi Pico W that controls DC motor and servo via UART communication. This script provides real-time motor speed and servo angle control by receiving commands from a remote client.

**Key Features:**
- **Motor Control (ESC):** PWM-based speed control with range from -1.0 (full reverse) to 1.0 (full forward)
- **Servo Control:** Angle control with range from 0° to 180°
- **UART Communication:** Receives commands at 115200 baud rate
- **Command Format:** `angle,pwm` (comma-separated values)
  - Example: `90,0.5` sets servo to 90° and motor to 50% speed
- **Error Handling:** Robust parsing with validation and error logging
- **Real-time Feedback:** Console output showing actual pulse widths in microseconds

**Hardware Connections:**
- **Servo:** GPIO 15 (PWM)
- **Motor/ESC:** GPIO 14 (PWM)
- **UART:** TX on GPIO 0, RX on GPIO 1, Baud rate: 115200

**PWM Specifications:**
- **Frequency:** 50 Hz (standard for servo and ESC)
- **Motor PWM Calculation:** 1500 µs (center) ± 500 µs based on speed value
- **Servo PWM Calculation:** 500 µs (0°) to 2400 µs (180°)

**Usage:**
1. Upload this script to Raspberry Pi Pico W as `main.py`
2. Send commands via UART in format: `angle,speed` (e.g., `90,-0.3`)
3. Monitor console output for confirmation and feedback

**Protocol Example:**
```
Send: 45,0.75
Receive: 🛞 PWM: 0.75 (1875 µs) | เลี้ยว: 45.0° (1000 µs)
```

---

## Repository Structure
```
Carmb_rasberry_pi-Client/
├── PICOW.py              # Main firmware for Pico W motor/servo control
└── README.md             # This file
```

---

## Requirements
- Raspberry Pi Pico W
- MicroPython firmware installed
- DC Motor with ESC
- Servo motor
- UART communication interface

---

## Notes
- All PWM duty cycles are normalized to 16-bit range (0-65535)
- Invalid commands are logged but don't affect current state
- Servo and motor angles/speeds are clamped to safe ranges
- Minimum sleep interval: 10ms to prevent UART buffer overflow

