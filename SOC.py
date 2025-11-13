#!/usr/bin/env python3
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import asyncio      # <-- เพิ่ม
import websockets   # <-- เพิ่ม
import json         # <-- เพิ่ม

class BatteryMonitor:
    def __init__(self):
        print("Starting Battery Monitor (WebSocket Mode with Countdown Logic)...")

        # --- 2. ส่วนการตั้งค่า WebSocket ---
        # --- ⚠️ แก้ไข IP Address และ Port ให้เป็นของ Server ของคุณ ---
        self.SERVER_URI = "ws://89.213.177.84:1669/ws/pi"

        # --- ค่า Calibration ---
        self.VOLTAGE_CONVERSION_RATIO = 12.6 / 3.1  # แปลงจาก 3.1V → 12.6V
        self.FULL_VOLTAGE = 12.6
        self.EMPTY_VOLTAGE = 10.9

        # --- Buffer ---
        self.voltage_buffer = []
        self.buffer_size = 20
        # นี่คือค่าเปอร์เซ็นต์ล่าสุดที่แสดงผล (เริ่มต้นที่ 100)
        # ค่านี้จะถูกอัปเดต "เฉพาะเมื่อมันลดลง" เท่านั้น
        self.last_percent_displayed = 100.0  

        try:
            # --- สร้าง I2C Bus และตั้งค่า ADS1115 ---
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c)
            self.ads.gain = 1
            
            # [FIX] ใช้ Pin 3 ตามที่คุณแก้ไขมา
            self.chan = AnalogIn(self.ads, 3)
            
            print("✅ ADS1115 sensor initialized successfully.")
        except Exception as e:
            print(f"❌ Failed to initialize I2C or ADS1115 sensor: {e}")
            print("    Will run in simulation mode (if sensor not found).")
            self.chan = None # ตั้งค่า chan เป็น None ถ้าเริ่มต้นไม่สำเร็จ

    def read_a0_voltage(self):
        """อ่านค่า A0 แล้วคืนค่า raw voltage (0-3.3V)"""
        if self.chan:
            return self.chan.voltage
        else:
            # ถ้าเซ็นเซอร์ไม่ทำงาน ให้ส่งค่าจำลอง (เช่น 12.6V)
            # ค่า A0 ที่สัมพันธ์กับ 12.6V คือ 3.1V
            return 3.1 

    def calculate_battery_percent(self, voltage):
        """คำนวณเปอร์เซ็นต์แบตจากแรงดันจริง (12.6V = 100%)"""
        percent = (voltage - self.EMPTY_VOLTAGE) / (self.FULL_VOLTAGE - self.EMPTY_VOLTAGE) * 100
        return max(0.0, min(100.0, percent))

    async def async_run_loop(self):
        """
        ลูปหลักที่ทำงานตลอดเวลา (เวอร์ชัน WebSocket)
        """
        # ลูปนี้จะพยายามเชื่อมต่อใหม่หากหลุด
        while True: 
            try:
                # ใช้ async with เพื่อจัดการการเชื่อมต่อและปิดการเชื่อมต่ออัตโนมัติ
                async with websockets.connect(self.SERVER_URI) as websocket:
                    print(f"✅ Connected to WebSocket Server at {self.SERVER_URI}")

                    # ลูปนี้จะส่งข้อมูลตราบเท่าที่การเชื่อมต่อยังอยู่
                    while True: 
                        # --- 1. อ่านค่าและหาค่าเฉลี่ย (ตรรกะเดิม) ---
                        a0_voltage = self.read_a0_voltage()
                        self.voltage_buffer.append(a0_voltage)

                        if len(self.voltage_buffer) > self.buffer_size:
                            self.voltage_buffer.pop(0)

                        # ถ้ายังเก็บข้อมูลไม่ครบ buffer ให้รอรอบถัดไป
                        if len(self.voltage_buffer) < self.buffer_size:
                            print(f"Collecting data... ({len(self.voltage_buffer)}/{self.buffer_size})")
                            await asyncio.sleep(2.0) # <-- ใช้ asyncio.sleep
                            continue  

                        avg_a0 = sum(self.voltage_buffer) / len(self.voltage_buffer)
                        battery_voltage = avg_a0 * self.VOLTAGE_CONVERSION_RATIO
                        
                        # --- 2. คำนวณเปอร์เซ็นต์ดิบ (ตรรกะเดิม) ---
                        current_percent_raw = self.calculate_battery_percent(battery_voltage)

                        # --- 3. [อัปเกรด] ตรรกะการนับเฉพาะตอนลด (ตรรกะเดิม) ---
                        if current_percent_raw < self.last_percent_displayed:
                            self.last_percent_displayed = current_percent_raw

                        # --- 4. จัดรูปแบบและส่งข้อมูล ---
                        # เราจะส่ง "last_percent_displayed" เสมอ
                        # ซึ่งค่านี้จะลดลงหรือคงที่เท่านั้น จะไม่เด้งขึ้น
                        data_payload = {
                            "battery": float(f"{self.last_percent_displayed:.1f}"),
                            "voltage": float(f"{battery_voltage:.2f}") # ส่งค่า voltage ไปด้วย (เผื่อมีประโยชน์)
                        }
                        
                        # แปลง Dictionary เป็น JSON string
                        message = json.dumps(data_payload)

                        # ส่งข้อมูลไปที่ Server
                        await websocket.send(message)
                        print(f"📤 Sent data: {message}")

                        # หน่วงเวลา 2 วินาที (เหมือนโค้ดเดิม)
                        await asyncio.sleep(2.0) 

            except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError) as e:
                print(f"⚠️ Connection lost or refused: {e}. Retrying in 10 seconds...")
            except Exception as e:
                print(f"⚠️ An unexpected error occurred: {e}. Retrying in 10 seconds...")
            
            # รอ 10 วินาทีก่อนที่จะพยายามเชื่อมต่อใหม่
            await asyncio.sleep(10)


def main(args=None):
    # --- คำแนะนำในการติดตั้ง ---
    # ก่อนรันไฟล์นี้ ให้ติดตั้ง library ที่จำเป็นก่อน:
    # pip3 install websockets adafruit-circuitpython-ads1x15
    
    monitor = BatteryMonitor()
    try:
        # เริ่มการทำงานของโปรแกรม (เวอร์ชัน async)
        asyncio.run(monitor.async_run_loop())
    except KeyboardInterrupt:
        print("\n🛑 Program stopped by user.")
    finally:
        print("Shutting down.")

if __name__ == '__main__':
    main()
