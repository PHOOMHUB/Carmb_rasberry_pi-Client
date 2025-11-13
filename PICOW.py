from machine import Pin, PWM, UART
import time

servo = PWM(Pin(15))  # เลี้ยว
motor = PWM(Pin(14))  # ESC
servo.freq(50)
motor.freq(50)

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
print("UART Motor Controller Initialized. Waiting for data...")

def set_motor_speed(value):
    value = max(-1.0, min(1.0, value))
    pulse_width = 1500 + (value * 500)
    duty = int(pulse_width * (65535 / 20000))
    motor.duty_u16(duty)
    # เราจะปิด print() ที่นี่ เพื่อลด log ให้น้อยลง
    # print(f"Duty (16-bit): {duty}")
    # print(f"Duty %: {(duty / 65535) * 100:.2f}%")
    return pulse_width


def set_servo_angle(angle):
    angle = max(0, min(180, angle))
    pulse_width = 500 + (angle / 180) * (2400 - 500)
    duty = int(pulse_width * 65535 / 20000)
    servo.duty_u16(duty)
    return pulse_width

while True:
    if uart.any():
        data = uart.readline()
        if not data:
            continue  # ถ้าข้อมูลเป็น None ให้ข้ามไป

        try:
            # 1. ถอดรหัสและตัดช่องว่าง
            decoded = data.decode().strip()
            
            # 2. ถ้าเป็นบรรทัดว่าง ก็ข้ามไป
            if not decoded:
                continue

            # 3. [จุดแก้ไขสำคัญ] แยกข้อมูลด้วยจุลภาค
            parts = decoded.split(',')

            # 4. [จุดแก้ไขสำคัญ] ตรวจสอบว่ามี 2 ส่วนหรือไม่
            if len(parts) == 2:
                # ถ้ามี 2 ส่วน ค่อยลองแปลงเป็นตัวเลข
                angle = float(parts[0])
                pwm = float(parts[1])

                servo_us = set_servo_angle(angle)
                motor_us = set_motor_speed(pwm)

                # พิมพ์เฉพาะเมื่อได้รับคำสั่งที่ถูกต้องเท่านั้น
                print(f"🛞 PWM: {pwm:.2f} ({motor_us:.0f} µs) | เลี้ยว: {angle:.1f}° ({servo_us:.0f} µs)")
            
            else:
                # ถ้าไม่มี 2 ส่วน (เป็นข้อมูลขยะ) ให้พิมพ์เป็นคำเตือน
                print(f"⚠️ Received non-command data: '{decoded}'")

        except (ValueError, IndexError) as e:
            # Error นี้จะเกิดขึ้นถ้าข้อมูลมี 2 ส่วน แต่แปลงเป็น float ไม่ได้ (เช่น "abc,def")
            print(f"⚠️ Error parsing command: '{decoded}' | Error: {e}")
        except Exception as e:
            # Error อื่นๆ ที่ไม่คาดคิด
            print(f"⚠️ An general error occurred: {e}")
            
    time.sleep(0.01)
