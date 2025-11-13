#!/usr/bin/env python3
import socket
import websocket # ใช้ websocket-client ไม่ใช่ websockets
import threading
import json
import serial
import time
import math
from gpiozero import DigitalInputDevice

# === 1. การตั้งค่า (Configuration) ===
SERVER_IP = '89.213.177.84'
TCP_SERVER_PORT = 1112  # Port สำหรับรับคำสั่ง (TCP)
WEBSOCKET_URL = f"ws://{SERVER_IP}:2222/ws/pi"  # URL สำหรับส่งข้อมูล (WebSocket)
SERIAL_PORT = '/dev/serial0'
BAUDRATE = 115200

# === 2. สร้างตัวแปรกลางสำหรับแชร์ข้อมูลระหว่าง Thread ===
data_lock = threading.Lock()
latest_speed_kmh = 0.0
latest_gear = 'N'  # ค่าเริ่มต้น N (เกียร์ว่าง)
integral_error = 0.0 # ตัวแปรส่วนรวมสำหรับ Integral error

# === 3. การตั้งค่า Hardware ===
WHEEL_DIAMETER = 0.1
PULSES_PER_REV = 6
pulse_count = 0

try:
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    hall_a = DigitalInputDevice(17)
    hall_b = DigitalInputDevice(22) # <-- แก้ไขจากโค้ดอ้างอิง (27 -> 22)
    hall_c = DigitalInputDevice(27) # <-- แก้ไขจากโค้ดอ้างอิง (22 -> 27)

    def count_pulse():
        global pulse_count
        pulse_count += 1

    hall_a.when_activated = count_pulse
    hall_b.when_activated = count_pulse
    hall_c.when_activated = count_pulse
    print("✅ GPIO and Serial initialized.")
except Exception as e:
    print(f"❌ Error initializing peripherals: {e}")
    ser = None

# === 4. การตั้งค่า SMC (จากโค้ดอ้างอิง) ===
# ค่า PWM สูงสุดสำหรับแต่ละเกียร์ (ปรับค่าตามโค้ด SMC)
max_speed_map = {
    'R': -0.2,   # 0: R (Reverse)
    'N': 0.0,    # 1: N (Neutral)
    '1': 0.2,    # 2: Forward 1
    '2': 0.35,   # 3: Forward 2
    '3': 0.45    # 4: Forward 3
}

# ความเร็วเป้าหมาย (km/h) สำหรับแต่ละเกียร์ (ปรับค่าตามโค้ด SMC)
speed_targets = {
    'R': 8,
    'N': 0,
    '1': 15,
    '2': 30,
    '3': 45,
}

K = 0.1   # Proportional Gain
Ki = 0.02 # Integral Gain

# === 5. ฟังก์ชันการทำงานต่างๆ ===
def calc_pwm_from_gear(y, gear):
    """คำนวณ Open-Loop PWM จากคันเร่ง (Y) และเกียร์"""
    throttle = abs(min(0.0, y)) # ถ้า y เป็น -1.0 (เหยียบสุด), throttle จะเป็น 1.0
    max_pwm = max_speed_map.get(gear, 0.0)
    pwm = throttle * abs(max_pwm)
    if gear == 'R':
        pwm = -pwm
    return pwm

def get_speed_kmh(dt):
    """คำนวณความเร็ว (km/h) จาก Hall Sensors"""
    global pulse_count
    if dt <= 0: return 0.0
    revs_per_sec = (pulse_count / PULSES_PER_REV) / dt
    speed_mps = revs_per_sec * math.pi * WHEEL_DIAMETER
    speed_kmh = speed_mps * 3.6
    pulse_count = 0
    return speed_kmh

# === 6. ฟังก์ชันสำหรับ Thread ที่จะส่งข้อมูลผ่าน WebSocket (ไม่ต้องแก้ไข) ===
def websocket_sender():
    """
    ฟังก์ชันนี้จะทำงานใน Thread แยกต่างหาก
    เพื่อเชื่อมต่อและส่งข้อมูล Speed/Gear ไปยัง Dashboard
    """
    global latest_speed_kmh, latest_gear
    
    while True:
        try:
            # ใช้ websocket-client (create_connection)
            ws = websocket.create_connection(WEBSOCKET_URL)
            print(f"✅ Connected to WebSocket Server at {WEBSOCKET_URL}")
            
            while True:
                # ล็อคตัวแปรเพื่อป้องกันการอ่าน/เขียนพร้อมกัน
                with data_lock:
                    speed_to_send = latest_speed_kmh
                    gear_to_send = latest_gear

                data_to_send = {
                    "speed": round(speed_to_send),
                    "gear": gear_to_send
                }
                ws.send(json.dumps(data_to_send))
                # print(f"🚀 Sent via WebSocket: {data_to_send}")
                
                # หน่วงเวลาเล็กน้อยก่อนส่งครั้งถัดไป
                time.sleep(0.08) # 80ms

        except Exception as e:
            print(f"⚠️ WebSocket connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# === 7. ฟังก์ชันสำหรับ Thread ที่จะรับคำสั่ง TCP และใช้ SMC (*** ส่วนที่รวมโค้ด ***) ===
def tcp_receiver():
    """
    ฟังก์ชันนี้จะทำงานใน Thread แยกต่างหาก
    เพื่อรับคำสั่ง Control, คำนวณ SMC, และส่งไปที่ Pico
    """
    global latest_speed_kmh, latest_gear, integral_error
    
    # สร้าง Dictionary สำหรับแปลงค่าเกียร์ (จากโค้ดตัวแรก)
    gear_map = {
        '0': 'R',  # 0 คือเกียร์ถอยหลัง
        '1': 'N',  # 1 คือเกียร์ว่าง
        '2': '1',  # 2 คือเกียร์ 1
        '3': '2',  # 3 คือเกียร์ 2
        '4': '3'   # 4 คือเกียร์ 3
    }
    
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER_IP, TCP_SERVER_PORT))
            print(f"✅ Connected to TCP Server at Port {TCP_SERVER_PORT}")

            last_time = time.time()
            while True:
                data = sock.recv(1024)
                if not data:
                    print("⚠️ TCP connection closed by server. Reconnecting...")
                    break
                decoded = data.decode('utf-8').strip()

                try:
                    x_str, y_str, gear_input = decoded.split(',')
                    x = float(x_str)
                    y = float(y_str)
                    
                    # 1. แปลงค่าเกียร์ที่รับมา ('0'-'4') เป็นเกียร์ที่ใช้ ('R'-'3')
                    gear = gear_map.get(gear_input, 'N')

                    # 2. คำนวณความเร็วปัจจุบัน
                    now = time.time()
                    dt = now - last_time
                    last_time = now
                    speed_kmh = get_speed_kmh(dt)

                    # 3. อัปเดตตัวแปรกลาง (สำหรับ Thread WebSocket)
                    with data_lock:
                        latest_speed_kmh = speed_kmh
                        latest_gear = gear
                    
                    # --- 4. ตรรกะ SMC (จากโค้ดตัวที่สอง) ---
                    speed_ref = speed_targets.get(gear, 0) # ความเร็วเป้าหมาย
                    error = speed_ref - speed_kmh          # ข้อผิดพลาด
                    
                    # คำนวณ PWM พื้นฐานจากคันเร่ง
                    pwm_open_loop = calc_pwm_from_gear(y, gear)

                    pwm_smc = 0.0
                    # ใช้ SMC เมื่อ:
                    # 1. คันเร่งเหยียบสุด (y == -1.0)
                    # 2. ความเร็วปัจจุบัน ต่ำกว่า เป้าหมาย
                    # 3. เป้าหมายไม่ใช่เกียร์ว่าง (speed_ref != 0)
                    if y == -1.0 and speed_kmh < speed_ref and speed_ref != 0:
                        integral_error += error * dt
                        pwm_smc = (K * error) + (Ki * integral_error)
                    else:
                        # รีเซ็ตค่า Integral เมื่อไม่ได้อยู่ P
                        integral_error = 0.0

                    # รวม PWM
                    pwm = pwm_open_loop + pwm_smc
                    pwm = max(min(pwm, 1.0), -1.0) # จำกัดค่า PWM ให้อยู่ระหว่าง -1.0 ถึง 1.0

                    # 5. ส่งคำสั่งไปที่ PICO
                    angle = 90 + (x * 90)
                    message_to_pico = f"{angle:.1f},{pwm:.2f}"
                    if ser:
                        ser.write((message_to_pico + '\n').encode('utf-8'))

                    # แสดงผล Log (รวมข้อมูล SMC)
                    print(f"📩 Recv: {decoded} → Gear: {gear} | Speed: {speed_kmh:.2f} (Ref: {speed_ref}) | Error: {error:.2f} | PWM: {pwm:.2f} (OL: {pwm_open_loop:.2f}, SMC: {pwm_smc:.2f}) | UART: {message_to_pico}")

                except Exception as e:
                    print(f"⚠️ Error processing TCP message: '{decoded}' -> {e}")
            
            sock.close()

        except Exception as e:
            print(f"❌ TCP connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# === 8. เริ่มการทำงานของทุก Thread ===
if __name__ == "__main__":
    # ตรวจสอบว่าได้ติดตั้ง websocket-client
    # pip3 install websocket-client gpiozero
    
    ws_thread = threading.Thread(target=websocket_sender)
    ws_thread.daemon = True
    ws_thread.start()

    tcp_thread = threading.Thread(target=tcp_receiver)
    tcp_thread.daemon = True
    tcp_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping program.")
    finally:
        if ser:
            ser.close()
