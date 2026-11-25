import os
import re
import cv2
import time
import json
import asyncio
import logging
from typing import List, Optional
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response, RedirectResponse
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

# ==============================================================================
# 🔐 AUTHENTICATION & ACCESS CONTROL (PERSISTED USER & SESSION STORE)
# ==============================================================================
class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = True

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: str
    role: str = "operator"

class UpdateUserRequest(BaseModel):
    new_username: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None

AUTH_SESSIONS_FILE = os.path.join(BASE_DIR, "auth_sessions.json")
AUTH_USERS_FILE = os.path.join(BASE_DIR, "auth_users.json")

def load_users() -> dict:
    if os.path.exists(AUTH_USERS_FILE):
        try:
            with open(AUTH_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    return data
        except Exception as e:
            logger.warning(f"Failed to load users: {e}")
    # Default initial admin account if not configured
    default_users = {
        "admin": {
            "password": "admin1234",
            "name": "ผู้ดูแลระบบส่วนกลาง (Admin)",
            "role": "admin",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    save_users(default_users)
    return default_users

def save_users(users: dict):
    try:
        with open(AUTH_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save users: {e}")

def load_active_sessions() -> tuple:
    sessions = set()
    user_map = {}
    if os.path.exists(AUTH_SESSIONS_FILE):
        try:
            with open(AUTH_SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions = set(data.get("sessions", []))
                user_map = data.get("user_sessions", {})
        except Exception:
            pass
    return sessions, user_map

def save_active_sessions(sessions: set, user_map: dict = None):
    if user_map is None:
        user_map = ACTIVE_SESSION_USERS
    try:
        with open(AUTH_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "sessions": list(sessions),
                "user_sessions": user_map
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist sessions: {e}")

ACTIVE_SESSIONS, ACTIVE_SESSION_USERS = load_active_sessions()

def authenticate_user_db(username: str, password: str) -> Optional[dict]:
    """Authenticate user against persisted user store (auth_users.json)."""
    users = load_users()
    user = users.get(username)
    if user and user.get("password") == password:
        return {
            "username": username,
            "name": user.get("name", username),
            "role": user.get("role", "operator"),
            "created_at": user.get("created_at", "-")
        }
    return None

def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from cookie or Authorization header."""
    token = request.cookies.get("grad_auth_session")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    return token

def is_authenticated(request: Request) -> bool:
    """Check if request has a valid session token."""
    token = get_session_token(request)
    return bool(token and token in ACTIVE_SESSIONS)

def get_current_user(request: Request) -> Optional[dict]:
    """Retrieve full user profile for current authenticated request."""
    token = get_session_token(request)
    if token and token in ACTIVE_SESSIONS:
        username = ACTIVE_SESSION_USERS.get(token, "admin")
        users = load_users()
        user_info = users.get(username)
        if user_info:
            return {
                "username": username,
                "name": user_info.get("name", username),
                "role": user_info.get("role", "admin"),
                "created_at": user_info.get("created_at", "-")
            }
        return {"username": username, "name": username, "role": "admin"}
    return None


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
        webbrowser.open("http://localhost:8088/admin")

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

class ClientRestoreRequest(BaseModel):
    current_count: int
    total_target: Optional[int] = None
    active_session: Optional[str] = None

@app.post("/api/state/restore_client_backup")
async def restore_client_backup(req: ClientRestoreRequest):
    """กู้คืนข้อมูลที่นับไว้จาก Cookie / LocalStorage ของเบราว์เซอร์"""
    if req.current_count > 0:
        analytics.set_current_count(req.current_count)
        if req.total_target and req.total_target > 0:
            analytics.set_total_target(req.total_target)
        if req.active_session in ("morning", "afternoon") and req.active_session != analytics.active_session_key:
            analytics.switch_active_session(req.active_session)
        await broadcast_stats()
    return {"status": "ok", "current_count": analytics.current_count}

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
    pos_x_pct: Optional[float] = None
    pos_y_pct: Optional[float] = None

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

# ==============================================================================
# 🔐 AUTHENTICATION ENDPOINTS
# ==============================================================================
@app.post("/api/auth/login")
def api_login(req: LoginRequest, response: Response):
    user = authenticate_user_db(req.username, req.password)
    if not user:
        return Response(
            content=json.dumps({"success": False, "detail": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}),
            status_code=401,
            media_type="application/json"
        )
    token = f"grad_sess_{uuid.uuid4().hex}"
    ACTIVE_SESSIONS.add(token)
    ACTIVE_SESSION_USERS[token] = req.username
    save_active_sessions(ACTIVE_SESSIONS, ACTIVE_SESSION_USERS)

    max_age = (86400 * 30) if req.remember else 86400  # 30 days or 1 day
    response.set_cookie(
        key="grad_auth_session",
        value=token,
        max_age=max_age,
        path="/",
        httponly=False,
        samesite="lax"
    )
    return {
        "success": True,
        "token": token,
        "user": user
    }

@app.post("/api/auth/logout")
def api_logout(request: Request, response: Response):
    token = get_session_token(request)
    if token and token in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.remove(token)
        ACTIVE_SESSION_USERS.pop(token, None)
        save_active_sessions(ACTIVE_SESSIONS, ACTIVE_SESSION_USERS)
    response.delete_cookie(key="grad_auth_session", path="/")
    return {"success": True, "message": "ออกจากระบบเรียบร้อย"}

@app.get("/api/auth/check")
def api_auth_check(request: Request):
    user = get_current_user(request)
    if user:
        return {
            "authenticated": True,
            "username": user["username"],
            "name": user["name"],
            "role": user["role"]
        }
    return {"authenticated": False}

# ==============================================================================
# 👥 USER & OPERATOR ACCOUNTS MANAGEMENT ENDPOINTS
# ==============================================================================
@app.get("/api/auth/users")
def get_users_list(request: Request):
    if not is_authenticated(request):
        return Response(
            content=json.dumps({"success": False, "detail": "กรุณาเข้าสู่ระบบก่อน"}),
            status_code=401,
            media_type="application/json"
        )
    users = load_users()
    user_list = []
    for uname, data in users.items():
        user_list.append({
            "username": uname,
            "name": data.get("name", uname),
            "role": data.get("role", "operator"),
            "created_at": data.get("created_at", "-")
        })
    return {"success": True, "users": user_list}

@app.post("/api/auth/users")
def create_new_user(req: CreateUserRequest, request: Request):
    if not is_authenticated(request):
        return Response(
            content=json.dumps({"success": False, "detail": "กรุณาเข้าสู่ระบบก่อน"}),
            status_code=401,
            media_type="application/json"
        )
    
    username = req.username.strip()
    if not re.match(r'^[a-zA-Z0-9_\-\.]{3,30}$', username):
        return Response(
            content=json.dumps({"success": False, "detail": "ชื่อผู้ใช้ต้องเป็นตัวอักษรภาษาอังกฤษ ตัวเลข ขีดล่าง หรือขีดกลาง ความยาว 3-30 ตัวอักษร"}),
            status_code=400,
            media_type="application/json"
        )
    
    if len(req.password) < 4:
        return Response(
            content=json.dumps({"success": False, "detail": "รหัสผ่านต้องมีความยาวอย่างน้อย 4 ตัวอักษร"}),
            status_code=400,
            media_type="application/json"
        )
    
    if not req.name.strip():
        return Response(
            content=json.dumps({"success": False, "detail": "กรุณากรอกชื่อ-นามสกุล หรือชื่อตำแหน่งแสดงผล"}),
            status_code=400,
            media_type="application/json"
        )
    
    role = req.role if req.role in ("admin", "operator") else "operator"
    
    users = load_users()
    if username in users:
        return Response(
            content=json.dumps({"success": False, "detail": f"ชื่อผู้ใช้ '{username}' มีอยู่ในระบบแล้ว กรุณาเลือกชื่ออื่น"}),
            status_code=400,
            media_type="application/json"
        )
    
    users[username] = {
        "password": req.password,
        "name": req.name.strip(),
        "role": role,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_users(users)
    logger.info(f"Created new user account '{username}' with role '{role}'")
    return {
        "success": True,
        "message": f"เพิ่มผู้ใช้งาน '{username}' สำเร็จแล้ว",
        "user": {
            "username": username,
            "name": req.name.strip(),
            "role": role,
            "created_at": users[username]["created_at"]
        }
    }

@app.put("/api/auth/users/{username}")
def update_user(username: str, req: UpdateUserRequest, request: Request):
    if not is_authenticated(request):
        return Response(
            content=json.dumps({"success": False, "detail": "กรุณาเข้าสู่ระบบก่อน"}),
            status_code=401,
            media_type="application/json"
        )
    
    users = load_users()
    if username not in users:
        return Response(
            content=json.dumps({"success": False, "detail": f"ไม่พบผู้ใช้ '{username}' ในระบบ"}),
            status_code=404,
            media_type="application/json"
        )
    
    user_record = users[username]
    target_username = username

    # If renaming username
    if req.new_username and req.new_username.strip() != username:
        new_uname = req.new_username.strip()
        if not re.match(r'^[a-zA-Z0-9_\-\.]{3,30}$', new_uname):
            return Response(
                content=json.dumps({"success": False, "detail": "ชื่อผู้ใช้ใหม่ต้องเป็นภาษาอังกฤษ ตัวเลข ขีดล่าง หรือขีดกลาง 3-30 ตัวอักษร"}),
                status_code=400,
                media_type="application/json"
            )
        if new_uname in users:
            return Response(
                content=json.dumps({"success": False, "detail": f"ชื่อผู้ใช้ใหม่ '{new_uname}' มีผู้อื่นใช้งานแล้ว"}),
                status_code=400,
                media_type="application/json"
            )
        
        # Migrate sessions
        for tok, u in list(ACTIVE_SESSION_USERS.items()):
            if u == username:
                ACTIVE_SESSION_USERS[tok] = new_uname
        save_active_sessions(ACTIVE_SESSIONS, ACTIVE_SESSION_USERS)
        
        del users[username]
        users[new_uname] = user_record
        target_username = new_uname

    # Role guard: ensure at least one admin remains
    if req.role and req.role in ("admin", "operator"):
        if user_record.get("role") == "admin" and req.role == "operator":
            admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
            if admin_count <= 1:
                return Response(
                    content=json.dumps({"success": False, "detail": "ไม่สามารถเปลี่ยนสิทธิ์ผู้ดูแลระบบคนสุดท้ายให้เป็นเจ้าหน้าที่ทั่วไปได้"}),
                    status_code=400,
                    media_type="application/json"
                )
        users[target_username]["role"] = req.role

    if req.name is not None and req.name.strip():
        users[target_username]["name"] = req.name.strip()

    if req.password is not None and req.password.strip():
        if len(req.password.strip()) < 4:
            return Response(
                content=json.dumps({"success": False, "detail": "รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 4 ตัวอักษร"}),
                status_code=400,
                media_type="application/json"
            )
        users[target_username]["password"] = req.password.strip()

    save_users(users)
    logger.info(f"Updated user account '{username}' -> '{target_username}'")
    return {
        "success": True,
        "message": f"อัปเดตข้อมูลผู้ใช้ '{target_username}' สำเร็จแล้ว",
        "user": {
            "username": target_username,
            "name": users[target_username].get("name"),
            "role": users[target_username].get("role")
        }
    }

@app.delete("/api/auth/users/{username}")
def delete_user(username: str, request: Request):
    if not is_authenticated(request):
        return Response(
            content=json.dumps({"success": False, "detail": "กรุณาเข้าสู่ระบบก่อน"}),
            status_code=401,
            media_type="application/json"
        )
    
    users = load_users()
    if username not in users:
        return Response(
            content=json.dumps({"success": False, "detail": f"ไม่พบผู้ใช้ '{username}' ในระบบ"}),
            status_code=404,
            media_type="application/json"
        )
    
    curr_user = get_current_user(request)
    if curr_user and curr_user.get("username") == username:
        return Response(
            content=json.dumps({"success": False, "detail": "ไม่สามารถลบบัญชีที่ท่านกำลังใช้งานเข้าสู่ระบบอยู่ได้ กรุณาใช้บัญชีผู้ดูแลอื่นเพื่อทำการลบ"}),
            status_code=400,
            media_type="application/json"
        )
    
    # Check if deleting last admin
    if users[username].get("role") == "admin":
        admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
        if admin_count <= 1:
            return Response(
                content=json.dumps({"success": False, "detail": "ไม่สามารถลบผู้ดูแลระบบคนสุดท้ายได้ เพื่อป้องกันระบบถูกล็อค"}),
                status_code=400,
                media_type="application/json"
            )
    
    del users[username]
    save_users(users)
    
    # Remove any active sessions for this user
    for tok, u in list(ACTIVE_SESSION_USERS.items()):
        if u == username:
            ACTIVE_SESSION_USERS.pop(tok, None)
            if tok in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS.remove(tok)
    save_active_sessions(ACTIVE_SESSIONS, ACTIVE_SESSION_USERS)
    
    logger.info(f"Deleted user account '{username}'")
    return {"success": True, "message": f"ลบบัญชี '{username}' สำเร็จแล้ว"}

# ==============================================================================
# 🔊 NATURAL THAI HUMAN VOICE TTS SERVICE (PRE-CACHED & ON-DEMAND)
# ==============================================================================
import urllib.request
import urllib.parse

AUDIO_CACHE_DIR = os.path.join(STATIC_DIR, "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

THAI_DIGITS = ['', 'หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า']
THAI_POSITIONS = ['', 'สิบ', 'ร้อย', 'พัน', 'หมื่น', 'แสน', 'ล้าน']

def num_to_thai_speech(num: int) -> str:
    if num == 0:
        return 'ศูนย์'
    n = abs(int(num))
    s = str(n)
    l = len(s)
    res = ''
    for i, c in enumerate(s):
        d = int(c)
        p = l - i - 1
        if d != 0:
            if p == 1 and d == 1:
                res += 'สิบ'
            elif p == 1 and d == 2:
                res += 'ยี่สิบ'
            elif p == 0 and d == 1 and l > 1 and s[-2] != '0':
                res += 'เอ็ด'
            else:
                res += THAI_DIGITS[d] + THAI_POSITIONS[p]
    return res

def fetch_and_cache_tts(num: int) -> Optional[str]:
    filepath = os.path.join(AUDIO_CACHE_DIR, f"th_{num}.mp3")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filepath
    
    thai_text = num_to_thai_speech(num)
    try:
        url = 'https://translate.google.com/translate_tts?ie=UTF-8&tl=th&client=tw-ob&q=' + urllib.parse.quote(thai_text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = resp.read()
            with open(filepath, 'wb') as f:
                f.write(data)
        return filepath
    except Exception as e:
        logger.warning(f"Google TTS fetch failed for {num}: {e}")
    return None

@app.get("/api/audio/tts")
async def get_thai_tts_audio(num: int = 1):
    """Serve pre-cached or on-demand natural Thai human voice counting MP3."""
    filepath = os.path.join(AUDIO_CACHE_DIR, f"th_{num}.mp3")
    if not (os.path.exists(filepath) and os.path.getsize(filepath) > 0):
        loop = asyncio.get_running_loop()
        filepath = await loop.run_in_executor(None, fetch_and_cache_tts, num)
    
    if filepath and os.path.exists(filepath):
        try:
            loop = asyncio.get_running_loop()
            for next_n in range(num + 1, num + 4):
                next_fp = os.path.join(AUDIO_CACHE_DIR, f"th_{next_n}.mp3")
                if not os.path.exists(next_fp):
                    loop.run_in_executor(None, fetch_and_cache_tts, next_n)
        except Exception:
            pass
        return FileResponse(filepath, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})
    
    return Response(status_code=404)

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

@app.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    login_path = os.path.join(STATIC_DIR, "login.html")
    with open(login_path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def get_admin_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login?redirect=/admin", status_code=303)
    with open(os.path.join(STATIC_DIR, "admin.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/manual", response_class=HTMLResponse)
@app.get("/hand", response_class=HTMLResponse)
def get_manual_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login?redirect=/manual", status_code=303)
    manual_path = os.path.join(STATIC_DIR, "manual.html")
    if not os.path.exists(manual_path):
        return HTMLResponse("<h1>Manual Page Loading...</h1>", status_code=200)
    with open(manual_path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/settings", response_class=HTMLResponse)
@app.get("/tools", response_class=HTMLResponse)
def get_settings_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login?redirect=/settings", status_code=303)
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
    uvicorn.run("main:app", host="0.0.0.0", port=8088, reload=False)
