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

### SOC.py

**Description:**
A Python script for Raspberry Pi that monitors battery State of Charge (SOC) using an ADS1115 analog-to-digital converter and sends real-time battery data to a WebSocket server. The script implements smoothing, calibration, and graceful connection handling.

**Key Features:**
- **Battery Monitoring:** Measures battery voltage using ADS1115 (16-bit ADC) connected via I2C
- **WebSocket Communication:** Asynchronous transmission of battery data to remote server
- **Voltage Calibration:** Converts analog readings (0-3.3V) to actual battery voltage (12.6V nominal)
- **Data Smoothing:** 20-sample rolling buffer to reduce noise and jitter
- **One-Way Logic:** Battery percentage only decreases or stays constant (prevents false increases)
- **Automatic Reconnection:** Handles connection loss and retries every 10 seconds
- **JSON Data Format:** Sends battery percentage and voltage as structured JSON

**Hardware Connections:**
- **I2C Bus:** Standard Raspberry Pi I2C (SDA, SCL)
- **ADS1115 Pin A3:** Battery voltage input (scaled voltage)
- **Address:** Default ADS1115 I2C address (0x48)

**Configuration:**
```python
self.SERVER_URI = "ws://89.213.177.84:1669/ws/pi"  # Change to your server
self.FULL_VOLTAGE = 12.6    # Max battery voltage (100%)
self.EMPTY_VOLTAGE = 10.9   # Min battery voltage (0%)
self.VOLTAGE_CONVERSION_RATIO = 12.6 / 3.1  # ADC scaling factor
self.buffer_size = 20       # Samples for averaging
```

**Data Payload Format:**
```json
{
  "battery": 85.5,
  "voltage": 12.34
}
```

**Installation Requirements:**
```bash
pip3 install websockets adafruit-circuitpython-ads1x15
```

**Usage:**
1. Configure WebSocket server address in the script
2. Ensure ADS1115 is properly connected via I2C
3. Run: `python3 SOC.py`
4. Monitor output for connection status and battery updates

**Output Example:**
```
✅ Connected to WebSocket Server at ws://89.213.177.84:1669/ws/pi
✅ ADS1115 sensor initialized successfully.
Collecting data... (15/20)
Collecting data... (20/20)
📤 Sent data: {"battery": 95.2, "voltage": 12.52}
```

---

## Repository Structure
```
Carmb_rasberry_pi-Client/
├── PICOW.py              # Main firmware for Pico W motor/servo control
├── SOC.py                # Battery monitoring and WebSocket transmission
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

