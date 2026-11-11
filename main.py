import os
import cv2
import time
import json
import asyncio
import logging
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import shutil
import numpy as np

from stream_reader import VideoStreamReader
from pose_detector import GraduationPoseDetector
from analytics import GraduationAnalytics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GraduationServer")

app = FastAPI(title="Graduation Live Ceremony Counter")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
VIDEOS_DIR = os.path.join(BASE_DIR, "sample_videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Core Modules
stream_reader = VideoStreamReader()
pose_detector = GraduationPoseDetector()
analytics = GraduationAnalytics(total_target=1500)

# Active WebSocket connections
active_websockets: List[WebSocket] = []

async def broadcast_stats():
    """Broadcast latest analytics stats to all connected OBS overlays and Admin dashboards."""
    data = analytics.get_summary()
    message = json.dumps({"type": "STATS_UPDATE", "data": data})
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

def on_graduate_detected():
    """Callback fired by AI detector when diploma handover completes."""
    if analytics.is_paused or getattr(analytics, 'counting_mode', 'auto') == 'manual':
        return
    logger.info(">>> GRADUATE CONFERRED! Recording stats...")
    analytics.record_graduate()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_stats())
    except RuntimeError:
        pass

# Bind callback
pose_detector.on_graduate_received = on_graduate_detected

# Background heartbeat task to keep ETA & Elapsed time ticking every second
@app.on_event("startup")
async def startup_event():
    # Start default stream reader (Simulation mode ready out-of-the-box)
    stream_reader.start(source_type="simulation")

    async def periodic_timer():
        while True:
            await asyncio.sleep(1.0)
            await broadcast_stats()

    asyncio.create_task(periodic_timer())

    # Automatically open browser after server is up and listening
    def open_browser():
        import time, webbrowser
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000/admin")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

@app.on_event("shutdown")
def shutdown_event():
    stream_reader.stop()

# Frame generator for Admin Live Monitor
def generate_mjpeg_frames():
    while True:
        try:
            frame = stream_reader.get_latest_frame()
            if frame is not None:
                annotated_frame, _ = pose_detector.process_frame(frame)
                if annotated_frame is not None:
                    ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            logger.error(f"Error in frame generation: {e}")
        time.sleep(0.020) # ~30-40fps smooth streaming

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Immediately send current state
        await websocket.send_text(json.dumps({"type": "STATS_UPDATE", "data": analytics.get_summary()}))
        while True:
            text = await websocket.receive_text()
            # Can receive ping or client commands
    except (WebSocketDisconnect, ConnectionResetError, Exception):
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

@app.websocket("/ws/browser_stream")
async def browser_stream_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Browser Screen Stream WebSocket connected.")
    stream_reader.start(source_type="browser_screen", source_path="browser")
    try:
        while True:
            data = await websocket.receive_bytes()
            if data:
                np_arr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    stream_reader.push_frame(frame)
    except WebSocketDisconnect:
        logger.info("Browser Screen Stream WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Browser stream error: {e}")

# REST API Models
class SourceConfig(BaseModel):
    source_type: str # "youtube", "webcam", "rtsp", "simulation"
    source_path: str # URL or camera index

class ROIConfig(BaseModel):
    zone: str = "hand" # "person" or "hand"
    x_min: float
    y_min: float
    x_max: float
    y_max: float

class TargetConfig(BaseModel):
    total_target: int

@app.post("/api/source")
async def change_source(config: SourceConfig):
    logger.info(f"Changing source to {config.source_type}: {config.source_path}")
    stream_reader.start(source_type=config.source_type, source_path=config.source_path)
    return {"status": "ok", "source_type": config.source_type}

@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file for testing and automatically switch the source."""
    safe_filename = file.filename.replace(" ", "_")
    target_path = os.path.join(VIDEOS_DIR, safe_filename)
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info(f"Uploaded video saved to: {target_path}")
    # Switch stream source to this uploaded file
    stream_reader.start(source_type="file", source_path=target_path)
    return {"status": "ok", "filename": safe_filename, "path": target_path}

@app.get("/api/sample_videos")
async def get_sample_videos():
    """List available video files in sample_videos directory with file sizes."""
    valid_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    items = []
    if os.path.exists(VIDEOS_DIR):
        for f in os.listdir(VIDEOS_DIR):
            if f.lower().endswith(valid_exts):
                fp = os.path.join(VIDEOS_DIR, f)
                try:
                    sz_mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
                except Exception:
                    sz_mb = 0.0
                items.append({
                    "filename": f,
                    "path": f"sample_videos/{f}",
                    "size_mb": sz_mb
                })
    return {"videos": [item["filename"] for item in items], "items": items}

# Video Playback Control APIs
@app.post("/api/video/pause")
async def toggle_video_pause():
    is_paused = stream_reader.toggle_playback_pause()
    return {"status": "ok", "is_paused": is_paused}

@app.post("/api/video/speed")
async def set_video_speed(speed: float):
    stream_reader.set_speed(speed)
    return {"status": "ok", "speed": stream_reader.playback_speed}

@app.post("/api/video/seek")
async def seek_video(percent: float):
    stream_reader.seek_percent(percent)
    return {"status": "ok", "percent": percent}

@app.get("/api/video/status")
async def get_video_status():
    return stream_reader.get_playback_status()

@app.post("/api/roi")
async def update_roi(config: ROIConfig):
    if config.zone == "person":
        pose_detector.set_roi_person(config.x_min, config.y_min, config.x_max, config.y_max)
    elif config.zone == "exclude":
        pose_detector.set_roi_exclude(config.x_min, config.y_min, config.x_max, config.y_max)
    else:
        pose_detector.set_roi_hand(config.x_min, config.y_min, config.x_max, config.y_max)
    return {"status": "ok", "rois": pose_detector.get_all_rois()}

@app.get("/api/roi")
async def get_roi():
    return pose_detector.get_all_rois()

class TuningConfig(BaseModel):
    sensitivity: float = 2.0
    cooldown: float = 1.8
    mode: str = "hand_priority"  # "hand_priority" | "arm_raise" | "dual" | "tripwire"

@app.post("/api/tuning")
async def update_tuning(config: TuningConfig):
    pose_detector.set_tuning(config.sensitivity, config.cooldown, config.mode)
    return {"status": "ok", "tuning": pose_detector.get_all_rois()}

class CountConfig(BaseModel):
    current_count: int

class PaceConfig(BaseModel):
    pace_sec: float

@app.post("/api/set_count")
async def set_current_count(config: CountConfig):
    analytics.set_current_count(config.current_count)
    await broadcast_stats()
    return {"status": "ok", "current_count": analytics.current_count}

@app.post("/api/set_pace")
async def set_pace(config: PaceConfig):
    analytics.set_manual_pace(config.pace_sec)
    await broadcast_stats()
    return {"status": "ok", "pace_sec": config.pace_sec}

@app.post("/api/clear_pace")
async def clear_pace():
    """ล้าง manual pace กลับสู่การคำนวณอัตโนมัติจากข้อมูลจริง"""
    analytics.clear_manual_pace()
    await broadcast_stats()
    return {"status": "ok", "auto_mode": True}

@app.post("/api/target")
async def set_target(config: TargetConfig):
    analytics.set_total_target(config.total_target)
    await broadcast_stats()
    return {"status": "ok", "total_target": analytics.total_target}

class PlannedFinishConfig(BaseModel):
    planned_time: str = ""

PlannedFinishConfig.model_rebuild()

class CeremonyInfoConfig(BaseModel):
    title: str = ""
    session_name: str = ""
    pre_break: str = ""
    post_break: str = ""

CeremonyInfoConfig.model_rebuild()

class SessionDataConfig(BaseModel):
    session_key: str = "morning"  # "morning" | "afternoon"
    title: str = ""
    session_label: str = ""
    start_time: str = ""
    finish_time: str = ""
    total_target: int = 1500
    pre_break_range: str = ""
    post_break_range: str = ""
    universities: Optional[List[dict]] = None

SessionDataConfig.model_rebuild()

class UniversitiesConfig(BaseModel):
    session_key: str = "morning"
    universities: List[dict]

UniversitiesConfig.model_rebuild()

class SessionSwitchConfig(BaseModel):
    session_key: str = "morning"
    reset_count: bool = False

SessionSwitchConfig.model_rebuild()

class ObsSettingsConfig(BaseModel):
    position: Optional[str] = "bottom-left"
    scale: Optional[float] = 1.0
    pad_x: Optional[int] = 48
    pad_y: Optional[int] = 36

ObsSettingsConfig.model_rebuild()

class DaySplitConfig(BaseModel):
    day_total: int = 2000
    morning_target: int = 900

DaySplitConfig.model_rebuild()

class ThemeConfig(BaseModel):
    theme: str = "purple-yellow"

ThemeConfig.model_rebuild()

@app.post("/api/theme")
async def set_theme_api(config: ThemeConfig):
    """เปลี่ยนธีมสีของทั้งระบบ (ม่วง-เหลือง / คลาสสิก) และกระจายไปยังทุกหน้าจอ"""
    analytics.set_theme(config.theme)
    await broadcast_stats()
    return {"status": "ok", "theme": config.theme}

@app.get("/api/sessions")
async def get_sessions():
    """ดึงข้อมูลรอบเช้าและรอบบ่าย"""
    return analytics.get_sessions_info()

@app.post("/api/sessions/universities")
async def update_universities_api(config: UniversitiesConfig):
    """บันทึกและคำนวณคิวมหาวิทยาลัย/คณะย่อยในรอบพิธี"""
    analytics.update_session_universities(config.session_key, config.universities)
    await broadcast_stats()
    return {"status": "ok", "active_session": analytics.active_session_key, "universities": config.universities}

@app.post("/api/sessions/split_day")
async def split_day_api(config: DaySplitConfig):
    """แบ่งยอดรวมทั้งวันอัตโนมัติ เช่น 2,000 คน ตัดเช้า 900 -> บ่ายเหลือ 1,100"""
    analytics.split_day_total(config.day_total, config.morning_target)
    await broadcast_stats()
    return {"status": "ok", "morning": analytics.sessions.get("morning"), "afternoon": analytics.sessions.get("afternoon")}

@app.post("/api/sessions/update")
async def update_session_api(config: SessionDataConfig):
    """บันทึกข้อมูลรอบเช้าหรือรอบบ่าย (มหาวิทยาลัย, เวลา, ยอดคน)"""
    analytics.update_session(config.session_key, config.dict())
    await broadcast_stats()
    return {"status": "ok", "active_session": analytics.active_session_key}

@app.post("/api/sessions/switch")
async def switch_session_api(config: SessionSwitchConfig):
    """สลับรอบพิธี (รอบเช้า / รอบบ่าย) พร้อมซิงก์ข้อมูลขึ้นทุกหน้าจอทันที"""
    analytics.switch_active_session(config.session_key, reset_count=config.reset_count)
    await broadcast_stats()
    return {"status": "ok", "active_session": analytics.active_session_key}

@app.post("/api/sessions/undo_switch")
async def undo_switch_api():
    """กู้คืนกลับไปยังรอบพิธีก่อนหน้าทันที (กรณีกดสลับรอบผิด / กดลั่น)"""
    analytics.undo_session_switch()
    await broadcast_stats()
    return {"status": "ok", "active_session": analytics.active_session_key}

@app.post("/api/ceremony_info")
async def set_ceremony_info(config: CeremonyInfoConfig):
    analytics.set_ceremony_info(
        title=config.title,
        session_name=config.session_name,
        pre_break=config.pre_break,
        post_break=config.post_break
    )
    await broadcast_stats()
    return {
        "status": "ok",
        "ceremony_title": analytics.ceremony_title,
        "session_name": analytics.session_name,
        "pre_break_range": analytics.pre_break_range,
        "post_break_range": analytics.post_break_range
    }

@app.post("/api/planned_finish")
async def set_planned_finish(config: PlannedFinishConfig):
    analytics.set_planned_finish(config.planned_time)
    await broadcast_stats()
    return {"status": "ok", "planned_finish_time": analytics.planned_finish_time}

@app.post("/api/obs/settings")
async def update_obs_settings_api(config: ObsSettingsConfig):
    """บันทึกและปรับตำแหน่ง/ขนาดป้าย OBS Overlay สด"""
    res = analytics.set_obs_settings(config.dict())
    await broadcast_stats()
    return {"status": "ok", "obs_settings": res}

@app.get("/api/obs/settings")
def get_obs_settings_api():
    """ดึงการตั้งค่าตำแหน่ง OBS ล่าสุด"""
    return getattr(analytics, "obs_settings", {"position": "bottom-left", "scale": 1.0, "pad_x": 48, "pad_y": 36})

@app.post("/api/adjust")
async def manual_adjust(delta: int):
    analytics.manual_adjust(delta)
    await broadcast_stats()
    return {"status": "ok", "count": analytics.current_count}

@app.post("/api/reset")
async def reset_counter():
    analytics.reset()
    await broadcast_stats()
    return {"status": "ok", "count": analytics.current_count}

class ModeConfig(BaseModel):
    mode: str = "auto"  # "auto" | "manual"

@app.post("/api/mode")
async def set_counting_mode(config: ModeConfig):
    mode = config.mode if config.mode in ("auto", "manual") else "auto"
    analytics.set_counting_mode(mode)
    await broadcast_stats()
    return {"status": "ok", "mode": analytics.counting_mode, "is_paused": analytics.is_paused}

@app.get("/api/mode")
async def get_counting_mode():
    return {"mode": getattr(analytics, "counting_mode", "auto"), "is_paused": analytics.is_paused}

@app.post("/api/pause")
async def toggle_pause():
    paused = analytics.toggle_pause()
    if not paused:
        analytics.set_counting_mode("auto")
    await broadcast_stats()
    return {"status": "ok", "is_paused": analytics.is_paused, "mode": analytics.counting_mode}

@app.post("/api/break_cutoff")
async def set_break_cutoff_api(cutoff_count: Optional[int] = None):
    """ตัดจุดพักแถวตามยอดจริง (กรณีประธานพักก่อนหรือหลังกำหนด)"""
    analytics.set_break_cutoff(cutoff_count)
    await broadcast_stats()
    return {"status": "ok", "pre_break_range": analytics.pre_break_range, "post_break_range": analytics.post_break_range}

@app.post("/api/toggle_break_phase")
async def toggle_break_phase_api():
    """สลับสถานะว่าเริ่มช่วงหลังพักแล้วหรือยัง"""
    analytics.toggle_break_phase()
    await broadcast_stats()
    return {"status": "ok", "break_taken": analytics.break_taken}

@app.post("/api/auto_deduct_excess")
async def set_auto_deduct_excess_api(enabled: bool):
    """เปิด/ปิดโหมดหักลดยอดช่วงหลังอัตโนมัติเมื่อรับเกิน"""
    analytics.auto_deduct_excess = enabled
    await broadcast_stats()
    return {"status": "ok", "auto_deduct_excess": analytics.auto_deduct_excess}

@app.post("/api/target_sync_actual")
async def sync_target_actual_api():
    """ปรับยอดเป้าหมายให้เท่ากับยอดบัณฑิตที่รับจริง (กรณีคนขาดหรือไม่ครบ หรือมีคนเกิน)"""
    analytics.sync_target_to_current()
    await broadcast_stats()
    return {"status": "ok", "total_target": analytics.total_target}

# Ceremony Report & CSV Export Endpoints
@app.get("/api/report/summary")
async def get_report_summary():
    """ดึงข้อมูลสรุปสถิติภาพรวมพิธีสำหรับแดชบอร์ดรายงาน"""
    return analytics.get_ceremony_report()

@app.get("/api/report/export_csv")
async def export_ceremony_csv():
    """ดาวน์โหลดไฟล์ Excel/CSV สรุปสถิติบัตฑิตทุกคนพร้อม BOM รองรับภาษาไทย"""
    csv_content = analytics.generate_csv_string()
    now_str = time.strftime("%Y%m%d_%H%M%S")
    filename = f"Graduation_Report_{now_str}.csv"
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

# Web Page Routes
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/favicon.ico")
def get_favicon():
    favicon_path = os.path.join(STATIC_DIR, "logo.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/png")
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def get_admin_page():
    with open(os.path.join(STATIC_DIR, "admin.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/manual", response_class=HTMLResponse)
@app.get("/hand", response_class=HTMLResponse)
def get_manual_page():
    manual_path = os.path.join(STATIC_DIR, "manual.html")
    if not os.path.exists(manual_path):
        return HTMLResponse("<h1>Manual Page Loading...</h1>", status_code=200)
    with open(manual_path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/settings", response_class=HTMLResponse)
@app.get("/tools", response_class=HTMLResponse)
def get_settings_page():
    with open(os.path.join(STATIC_DIR, "settings.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/overlay", response_class=HTMLResponse)
def get_overlay_page():
    with open(os.path.join(STATIC_DIR, "overlay.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/stage", response_class=HTMLResponse)
@app.get("/display", response_class=HTMLResponse)
@app.get("/live", response_class=HTMLResponse)
@app.get("/screen", response_class=HTMLResponse)
@app.get("/tv", response_class=HTMLResponse)
def get_stage_page():
    with open(os.path.join(STATIC_DIR, "stage.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
