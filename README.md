# 🎓 ระบบนับจำนวนบัณฑิตพิธีรับปริญญาบัตรอัตโนมัติ (Graduation Live Ceremony AI Counter)

ระบบตรวจจับนับจำนวนบัณฑิตที่เข้ารับปริญญาบัตรแบบอัตโนมัติจากสัญญาณไลฟ์สด (YouTube Live, RTMP/RTSP, หรือกล้อง/Capture Card) พร้อมจับเวลาต่อคน เวลาเฉลี่ย คำนวณเวลาคาดว่าจะเสร็จสิ้น (ETA) และยิงกราฟิก Real-time ขึ้น **OBS Studio / vMix** ด้วย Browser Source พื้นหลังโปร่งใส

---

## 🌟 ฟีเจอร์หลัก (Key Features)

1. **AI Pose & Hand Interaction Detection**:
   - ใช้โมเดล **MediaPipe Pose** ตรวจจับจังหวะการเอื้อมมือ/ข้อมือ (`RIGHT_WRIST`, `RIGHT_INDEX`) เข้าสู่แท่นรับปริญญาบัตร (Conferment Dais)
   - มี **Hybrid Motion Tracking** สำรองกรณีมุมกล้องไกลหรือแสงมืด เพื่อให้ความแม่นยำสูงสุด
   - ระบบ **State Machine & Cooldown Buffer** ป้องกันการนับซ้ำ (Anti-Double Counting) ต่อคน
2. **Real-time Live Pacing Analytics**:
   - นับจำนวนบัณฑิตปัจจุบันเทียบกับเป้าหมายทั้งหมด (เช่น 845 / 2,000 คน)
   - คำนวณ **เวลาต่อคนล่าสุด** (เช่น 2.8 วินาที)
   - คำนวณ **ความเร็วเฉลี่ย (Rolling Average)** และ **อัตราความเร็ว (คน/นาที)**
   - ประมาณการ **เวลาที่จะเสร็จสิ้นพิธี (ETA: Estimated Finish Time)** แบบเรียลไทม์
3. **OBS Studio Broadcast Overlay (Browser Source)**:
   - ออกแบบระดับพรีเมียม สไตล์สถานีโทรทัศน์ / งานพิธีพระราชทานปริญญาบัตร (Royal Navy & Gold Theme)
   - พื้นหลังโปร่งใส (Transparent) ขนาดมาตรฐาน 1920x1080
   - แอนิเมชันตัวเลขนับขึ้นแบบ Pulse Bump เมื่อมีบัณฑิตรับเสร็จ
4. **Director Control Center (Admin Dashboard)**:
   - จอแสดงภาพสัญญาณสดพร้อมแสดงกระดูก AI Skeleton และกรอบ Handover ROI Zone
   - แถบสลับสัญญาณภาพ 5 โหมด:
     - 📁 **ไฟล์วิดีโอคลิป (.mp4)**: อัปโหลดหรือเลือกคลิปวิดีโองานซ้อมมาเปิดทดสอบได้ทันที (เล่นวนลูปอัตโนมัติ)
     - 🤖 **จำลองภาพ (Demo Simulation)**: จำลองเหตุการณ์แบบสังเคราะห์พร้อมใช้งานทันทีโดยไม่ต้องมีไฟล์
     - 🔴 **YouTube Live**: ดึงสัญญาณไลฟ์สดออนไลน์
     - 📷 **กล้อง USB / HDMI Capture Card**: ต่อสัญญาณสดจากกล้องหน้างานโดยตรง
     - 🌐 **RTSP / RTMP**: สตรีมผ่านโครงข่ายภายใน
   - ปรับตำแหน่งและขนาดกล่อง ROI Zone ได้ง่ายผ่านแถบเลื่อน
   - ปุ่มแก้ไขด่วน: `+1 คน`, `-1 คน`, `⏸️ พักการนับ`, `🔄 รีเซ็ตเริ่มรอบใหม่`

---

## 🚀 วิธีเริ่มต้นใช้งาน (Quick Start)

### วิธีที่ 1: ดับเบิ้ลคลิกไฟล์รัน
ดับเบิ้ลคลิกที่ไฟล์:
```text
C:\Users\ACER\.gemini\antigravity-ide\scratch\graduation-live-counter\run.bat
```

### วิธีที่ 2: รันผ่าน Terminal / PowerShell
```powershell
cd C:\Users\ACER\.gemini\antigravity-ide\scratch\graduation-live-counter
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
เปิดเบราว์เซอร์ไปที่:
- **หน้าควบคุม (Admin Dashboard)**: [http://localhost:8000/admin](http://localhost:8000/admin)
- **กราฟิกสำหรับ OBS (Overlay)**: [http://localhost:8000/overlay](http://localhost:8000/overlay)

---

## 📺 วิธีนำกราฟิกขึ้น OBS Studio

1. เปิดโปรแกรม **OBS Studio**
2. ในช่อง **Sources** ด้านล่าง กดเครื่องหมาย **`+`** แล้วเลือก **`Browser`**
3. ตั้งชื่อ เช่น `Graduation Counter Overlay`
4. ตั้งค่าคุณสมบัติ:
   - **URL**: `http://localhost:8000/overlay`
   - **Width**: `1920`
   - **Height**: `1080`
   - ติ๊กถูกที่: `Shutdown source when not visible` และ `Refresh browser when scene becomes active`
5. กด **OK** กราฟิก Lower Third จะแสดงบนหน้าจอไลฟ์สดพร้อมข้อมูลอัปเดตแบบ Real-time ทันที!

---

## 🎯 คำแนะนำการตั้งค่ากรอบ ROI หน้างานจริง

1. ในหน้า **Admin Dashboard** เลือกแหล่งสัญญาณภาพ (เช่น วางลิงก์ YouTube Live หรือเลือกกล้อง HDMI Capture Card)
2. ปรับตัวเลื่อน **X Min / X Max / Y Min / Y Max** ให้กรอบสี่เหลี่ยมสีฟ้าครอบคลุมบริเวณ **"พานหรือแท่นรับปริญญาบัตร"** ที่บัณฑิตจะต้องยื่นมือเข้ามาสัมผัส
3. กดปุ่ม **"บันทึกพิกัด ROI"**
4. เมื่อบัณฑิตยื่นมือเข้าไปในกรอบ กรอบจะเปลี่ยนเป็นสีเหลือง (`RECEIVING...`) และเมื่อรับเสร็จจะเปลี่ยนเป็นสีเขียว (`DIPLOMA RECEIVED! +1`) พร้อมนับจำนวนและจับเวลาอัตโนมัติ
