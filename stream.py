import cv2
import base64
import asyncio
import websockets
import time  # <-- ตรวจสอบว่ามี import time
import numpy as np
from picamera2 import Picamera2

async def stream_video():
    uri = "ws://89.213.177.84:8765/pi_stream"
    
    picam2 = Picamera2()
    camera_config = picam2.create_video_configuration(main={"size": (846, 480), "format": "XBGR8888"})
    picam2.configure(camera_config)
    
    # --- ⬇️ เปลี่ยนวิธีปลุก Autofocus สำหรับโหมดไม่มีหน้าจอ ⬇️ ---

    # 1. เริ่มการทำงานของกล้องก่อน
    picam2.start()
    print("✅ Camera sensor started.")
    
    # 2. ตั้งค่า Autofocus เป็นโหมดต่อเนื่อง
    picam2.set_controls({"AfMode": 2, "AfTrigger": 0})
    print("📸 Autofocus set to continuous mode. Waiting for it to settle...")

    # 3. "รอ" ให้กล้องมีเวลาปรับโฟกัสเอง 2 วินาที
    #    วิธีนี้จะปลอดภัยกว่าและไม่พยายามสร้างหน้าต่าง GUI
    time.sleep(2)
    
    print("👍 Autofocus should be settled. Starting stream.")
    
    # --- ⬆️ จบส่วนที่แก้ไข ⬆️ ---

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to server at {uri}")
            
            while True:
                frame_raw = picam2.capture_array() 
                frame_processed = cv2.cvtColor(frame_raw, cv2.COLOR_RGBA2BGR)
                
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY),75] 
                ret, buffer = cv2.imencode('.jpg', frame_processed, encode_param) 
                if not ret:
                    continue

                base64_frame = base64.b64encode(buffer).decode('utf-8')

                try:
                    await websocket.send(base64_frame)
                    await websocket.recv()
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Connection closed by server.")
                    break
                
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        picam2.stop()
        print("Picamera2 stopped.")

if __name__ == "__main__":
    print("Starting Raspberry Pi video streaming client...")
    asyncio.run(stream_video())
    print("Client stopped.")
