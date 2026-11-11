import os
import json
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

SESSION_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions_config.json")

DEFAULT_SESSIONS = {
    "morning": {
        "title": "ม.ราชภัฏบุรีรัมย์ และ ม.ราชภัฏชัยภูมิ",
        "session_label": "รอบเช้า",
        "start_time": "08:30",
        "finish_time": "11:45",
        "time_range": "08:30 - 11:45",
        "total_target": 1383,
        "pre_break_range": "1-887",
        "post_break_range": "888-1,383"
    },
    "afternoon": {
        "title": "ม.ราชภัฏนครราชสีมา",
        "session_label": "รอบบ่าย",
        "start_time": "13:30",
        "finish_time": "16:45",
        "time_range": "13:30 - 16:45",
        "total_target": 1520,
        "pre_break_range": "1-950",
        "post_break_range": "951-1,520"
    }
}

class GraduationAnalytics:
    def __init__(self, total_target: int = 1500):
        self.current_count = 0
        self.is_paused = False
        self.counting_mode = 'auto'  # 'auto' | 'manual'

        # Load Sessions (Morning & Afternoon)
        self.active_session_key = "morning"
        self.sessions = self._load_sessions_config()
        self.theme = self.sessions.get("theme", "purple-yellow")
        cur = self.sessions.get(self.active_session_key, DEFAULT_SESSIONS["morning"])

        self.total_target = cur.get("total_target", total_target)
        self.ceremony_title: str = cur.get("title", "ม.ราชภัฏบุรีรัมย์ และ ม.ราชภัฏชัยภูมิ")
        self.session_name: str = cur.get("session_label", "รอบเช้า")
        self.pre_break_range: str = cur.get("pre_break_range", "1-887")
        self.post_break_range: str = cur.get("post_break_range", "888-1,383")
        self.planned_finish_time: Optional[str] = cur.get("finish_time", "11:45")

        # OBS Overlay Settings (ตำแหน่ง ขนาด ระยะขอบ)
        self.obs_settings: Dict = self.sessions.get("obs_settings", {
            "position": "bottom-left",
            "scale": 1.0,
            "pad_x": 48,
            "pad_y": 36
        })

        # Manual override pace (วินาที/คน) — None = ใช้ auto
        self.manual_pace_sec: Optional[float] = None

        self.start_timestamp = time.time()
        self.start_datetime = datetime.now()
        self.end_datetime: Optional[datetime] = None
        self.last_confer_timestamp: Optional[float] = None

        # Durations history
        self.raw_durations: List[float] = []        # ค่าดิบทุกค่า
        self.active_durations: List[float] = []     # ค่าที่กรองช่วงหยุดพักออก (1.5s - 8.0s)
        self.recent_events: List[Dict] = []         # 20 คนล่าสุดสำหรับ Visualizer Sparkline
        self.session_events: List[Dict] = []        # บันทึกประวัติบัณฑิตทุกคนตลอดทั้งพิธีสำหรับออกรายงาน

        # Pause & intermission tracking
        self.total_pause_time_sec = 0.0
        self.intermission_count = 0
        self.break_taken: bool = False             # บ่งชี้ว่าประธานสั่งพักแถวแล้วหรือยัง (ล็อกจุดพัก)
        self.auto_deduct_excess: bool = True       # หักลดยอดช่วงหลัง/รอบหลังให้อัตโนมัติเมื่อรับเกินเป้า

        # Multi-session State Memory (สำหรับกู้คืนกรณีกดลั่น / สลับรอบไปมาโดยยอดเดิมไม่หาย)
        self.session_states: Dict[str, Dict] = {}
        self.last_switched_from: Optional[str] = None

        # Configuration thresholds for realistic ceremony pacing
        self.MIN_CADENCE_SEC = 1.5   # ต่ำกว่านี้ถือเป็น glitch / เบิ้ล
        self.MAX_CADENCE_SEC = 8.0   # เกินกว่านี้ถือเป็นการพักแถว/เปลี่ยนคณะ (Intermission)

    def _load_sessions_config(self) -> Dict:
        """โหลดข้อมูลรอบเช้า/รอบบ่ายจาก JSON ถ้ามี"""
        if os.path.exists(SESSION_CONFIG_FILE):
            try:
                with open(SESSION_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "morning" in data and "afternoon" in data:
                        return data
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULT_SESSIONS))

    def _save_sessions_config(self):
        """บันทึกข้อมูลรอบเช้า/รอบบ่ายลง JSON ป้องกันข้อมูลหาย"""
        try:
            with open(SESSION_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_sessions_info(self) -> Dict:
        return {
            "active_session": self.active_session_key,
            "sessions": self.sessions,
            "theme": getattr(self, "theme", "purple-yellow")
        }

    def set_theme(self, theme: str) -> Dict:
        """บันทึกธีมสีของเว็บ (เช่น 'purple-yellow' หรือ 'default')"""
        self.theme = theme
        self.sessions["theme"] = theme
        self._save_sessions_config()
        return self.get_summary()

    def set_obs_settings(self, settings: Dict) -> Dict:
        """บันทึกการตั้งค่าตำแหน่งและขนาดของ OBS Overlay"""
        pos = settings.get("position", self.obs_settings.get("position", "bottom-left"))
        valid_positions = ("bottom-left", "bottom-center", "bottom-right", "top-left", "top-center", "top-right", "center")
        if pos not in valid_positions:
            pos = "bottom-left"

        try:
            scale = float(settings.get("scale", self.obs_settings.get("scale", 1.0)))
            scale = max(0.5, min(1.8, scale))
        except (ValueError, TypeError):
            scale = 1.0

        try:
            pad_x = int(settings.get("pad_x", self.obs_settings.get("pad_x", 48)))
            pad_x = max(0, min(300, pad_x))
        except (ValueError, TypeError):
            pad_x = 48

        try:
            pad_y = int(settings.get("pad_y", self.obs_settings.get("pad_y", 36)))
            pad_y = max(0, min(300, pad_y))
        except (ValueError, TypeError):
            pad_y = 36

        self.obs_settings = {
            "position": pos,
            "scale": round(scale, 2),
            "pad_x": pad_x,
            "pad_y": pad_y
        }
        self.sessions["obs_settings"] = self.obs_settings
        self._save_sessions_config()
        return self.obs_settings

    def update_session(self, session_key: str, data: Dict) -> Dict:
        """อัปเดตข้อมูลรอบเช้าหรือรอบบ่าย (มหาวิทยาลัย, เวลาเริ่ม-จบ, จำนวนคน, ลำดับก่อน-หลังพัก)"""
        if session_key not in ("morning", "afternoon"):
            return self.get_summary()

        sess = self.sessions.setdefault(session_key, {})
        for field in ("title", "session_label", "start_time", "finish_time", "total_target", "pre_break_range", "post_break_range"):
            if field in data and data[field] is not None:
                if field == "total_target":
                    sess[field] = max(1, int(data[field]))
                else:
                    sess[field] = str(data[field]).strip()

        st = sess.get("start_time", "")
        fn = sess.get("finish_time", "")
        if st and fn:
            sess["time_range"] = f"{st} - {fn}"

        # ถ้ามีการส่ง universities มาด้วย ให้ซิงก์คิวมหาวิทยาลัยด้วย
        if "universities" in data and isinstance(data["universities"], list) and data["universities"]:
            self.update_session_universities(session_key, data["universities"])
        elif "universities" in sess and len(sess["universities"]) == 1:
            sess["universities"][0]["name"] = sess.get("title", sess["universities"][0].get("name", ""))
            sess["universities"][0]["target"] = sess.get("total_target", sess["universities"][0].get("target", 1000))

        self._save_sessions_config()

        # หากกำลังใช้งานรอบนี้อยู่ ให้ซิงก์ค่าปัจจุบันทันที
        if self.active_session_key == session_key:
            self.total_target = sess.get("total_target", self.total_target)
            self.ceremony_title = sess.get("title", self.ceremony_title)
            self.session_name = sess.get("session_label", self.session_name)
            self.pre_break_range = sess.get("pre_break_range", self.pre_break_range)
            self.post_break_range = sess.get("post_break_range", self.post_break_range)
            self.planned_finish_time = sess.get("finish_time", self.planned_finish_time)
            if sess.get("universities"):
                self.universities = sess["universities"]

        return self.get_summary()

    def update_session_universities(self, session_key: str, universities: List[Dict]) -> Dict:
        """
        บันทึกรายการคิวมหาวิทยาลัย/คณะย่อยในรอบพิธี
        - คำนวณช่วงลำดับ (เช่น 1-500, 501-1,020, 1,021-1,220)
        - รวมยอดเป้าหมายของรอบอัตโนมัติ
        - คำนวณจุดตัดพักอัตโนมัติ
        """
        if session_key not in ("morning", "afternoon"):
            return self.get_summary()

        sess = self.sessions.setdefault(session_key, {})
        valid_unis = []
        for u in universities:
            name = str(u.get("name", "")).strip()
            try:
                target = max(1, int(u.get("target", 0)))
            except (ValueError, TypeError):
                target = 100
            if name:
                valid_unis.append({"name": name, "target": target})

        sess["universities"] = valid_unis
        if valid_unis:
            tot = sum(u["target"] for u in valid_unis)
            sess["total_target"] = tot
            if not getattr(self, "break_taken", False):
                half = max(1, int(tot * 0.6))
                sess["pre_break_range"] = f"1-{half:,}"
                sess["post_break_range"] = f"{half + 1:,}-{tot:,}"
            else:
                pre_start, pre_end, post_start, _ = self._parse_break_targets()
                sess["post_break_range"] = f"{post_start:,}-{tot:,}"

        self._save_sessions_config()

        if self.active_session_key == session_key:
            if valid_unis:
                self.total_target = sess["total_target"]
                self.pre_break_range = sess.get("pre_break_range", self.pre_break_range)
                self.post_break_range = sess.get("post_break_range", self.post_break_range)

        return self.get_summary()

    def switch_active_session(self, session_key: str, reset_count: bool = False, restore_saved_state: bool = True) -> Dict:
        """
        สลับรอบพิธี (รอบเช้า / รอบบ่าย)
        - ทำการบันทึก snapshot ยอดนับและเวลาของรอบเดิมไว้เสมอ (ป้องกันการกดผิด / กดลั่น สามารถกู้คืนได้ 100%)
        - หากรอบที่จะสลับไปเคยมียอดที่นับค้างไว้ และ restore_saved_state = True จะกู้คืนยอดเดิมให้ทันที
        """
        if session_key not in ("morning", "afternoon"):
            return self.get_summary()

        prev_key = self.active_session_key

        # บันทึกสถานะรอบเดิมไว้เสมอเพื่อความปลอดภัย
        if not hasattr(self, "session_states"):
            self.session_states = {}

        self.session_states[prev_key] = {
            "current_count": self.current_count,
            "break_taken": getattr(self, "break_taken", False),
            "start_timestamp": self.start_timestamp,
            "start_datetime": self.start_datetime,
            "last_confer_timestamp": self.last_confer_timestamp,
            "raw_durations": list(self.raw_durations),
            "active_durations": list(self.active_durations),
            "session_events": list(self.session_events),
            "recent_events": list(self.recent_events),
            "total_pause_time_sec": self.total_pause_time_sec,
            "intermission_count": self.intermission_count
        }
        self.last_switched_from = prev_key

        self.active_session_key = session_key
        cur = self.sessions.get(session_key, DEFAULT_SESSIONS.get(session_key, {}))

        self.total_target = cur.get("total_target", self.total_target)
        self.ceremony_title = cur.get("title", self.ceremony_title)
        self.session_name = cur.get("session_label", "รอบเช้า" if session_key == "morning" else "รอบบ่าย")
        self.pre_break_range = cur.get("pre_break_range", "")
        self.post_break_range = cur.get("post_break_range", "")
        self.planned_finish_time = cur.get("finish_time", None)

        if reset_count:
            # เริ่มรอบนี้ใหม่ที่ 0
            self.reset()
        elif restore_saved_state and session_key in self.session_states:
            # กู้คืนสถานะเดิมของรอบนี้ที่เคยนับไว้
            saved = self.session_states[session_key]
            self.current_count = saved.get("current_count", 0)
            self.break_taken = saved.get("break_taken", False)
            self.start_timestamp = saved.get("start_timestamp", time.time())
            self.start_datetime = saved.get("start_datetime", datetime.now())
            self.last_confer_timestamp = saved.get("last_confer_timestamp", None)
            self.raw_durations = list(saved.get("raw_durations", []))
            self.active_durations = list(saved.get("active_durations", []))
            self.session_events = list(saved.get("session_events", []))
            self.recent_events = list(saved.get("recent_events", []))
            self.total_pause_time_sec = saved.get("total_pause_time_sec", 0.0)
            self.intermission_count = saved.get("intermission_count", 0)
        else:
            self.current_count = 0
            self.break_taken = False

        return self.get_summary()

    def undo_session_switch(self) -> Dict:
        """กู้คืนกลับไปยังรอบก่อนหน้าทันที (Undo การสลับรอบ กรณีกดลั่น)"""
        if getattr(self, "last_switched_from", None):
            prev = self.last_switched_from
            return self.switch_active_session(prev, reset_count=False, restore_saved_state=True)
        return self.get_summary()

    def _auto_handle_excess(self):
        """
        หักลดยอดช่วงหลัง/รอบหลังอัตโนมัติเมื่อรับเกิน (Auto-Deduct Excess):
        1. หากยังไม่สั่งพักแถว (not break_taken) และคนรับเกินช่วงก่อนพัก (pre_end):
           ขยายช่วงก่อนพักเป็นเลขคนปัจจุบันทันที และหักลดยอดช่วงหลังพัก (post-break) ลงอัตโนมัติ
        2. หากยอดของรอบเช้ารับเกินเป้าหมายทั้งหมด:
           ขยายเป้าหมายรอบเช้า และหักลดยอดรอบบ่ายลงอัตโนมัติ โดยยอดรวมทั้งวันคงที่
        """
        if not getattr(self, "auto_deduct_excess", True):
            return

        pre_start, pre_end, post_start, post_end = self._parse_break_targets()

        # 1. ช่วงก่อนพักรับเกินเป้า (และประธานยังไม่ได้สั่งพักแถว)
        if not getattr(self, "break_taken", False) and self.current_count > pre_end and self.current_count <= self.total_target:
            actual_cut = self.current_count
            self.pre_break_range = f"{pre_start}-{actual_cut:,}"
            self.post_break_range = f"{actual_cut + 1:,}-{self.total_target:,}"
            if self.active_session_key in self.sessions:
                self.sessions[self.active_session_key]["pre_break_range"] = self.pre_break_range
                self.sessions[self.active_session_key]["post_break_range"] = self.post_break_range
                self._save_sessions_config()

        # 2. รอบเช้ารับเกินเป้าหมายรวม
        if self.active_session_key == "morning" and self.current_count > self.total_target:
            excess = self.current_count - self.total_target
            self.total_target = self.current_count
            if "morning" in self.sessions:
                self.sessions["morning"]["total_target"] = self.total_target
                p_start, p_end, po_start, _ = self._parse_break_targets()
                self.post_break_range = f"{po_start:,}-{self.total_target:,}"
                self.sessions["morning"]["post_break_range"] = self.post_break_range

            if "afternoon" in self.sessions:
                cur_a = self.sessions["afternoon"]["total_target"]
                new_a = max(1, cur_a - excess)
                self.sessions["afternoon"]["total_target"] = new_a
                a_half = int(new_a * 0.6)
                self.sessions["afternoon"]["pre_break_range"] = f"1-{a_half:,}"
                self.sessions["afternoon"]["post_break_range"] = f"{a_half + 1:,}-{new_a:,}"

            self._save_sessions_config()

    def record_graduate(self) -> Dict:
        """บันทึกเมื่อบัณฑิตรับปริญญาสำเร็จ 1 คน"""
        if self.is_paused:
            return self.get_summary()

        now = time.time()
        self.current_count += 1
        self._auto_handle_excess()
        dur = 0.0
        event_type = "normal"  # "fast", "normal", "slow", "intermission"

        if self.last_confer_timestamp is not None:
            dur = now - self.last_confer_timestamp
            # รับเฉพาะค่าที่เป็นไปได้ในโลกจริง (0.5s - 120s)
            if 0.5 <= dur <= 120.0:
                self.raw_durations.append(dur)

                if dur > self.MAX_CADENCE_SEC:
                    # ช่วงหยุดพัก / เปลี่ยนคณะ / ประธานพัก
                    event_type = "intermission"
                    self.intermission_count += 1
                    self.total_pause_time_sec += dur
                elif dur < self.MIN_CADENCE_SEC:
                    event_type = "fast"
                    self.active_durations.append(dur)
                else:
                    # ช่วงจังหวะการรับปริญญาปกติ
                    if dur <= 2.6:
                        event_type = "fast"
                    elif dur <= 4.2:
                        event_type = "normal"
                    else:
                        event_type = "slow"
                    self.active_durations.append(dur)
        else:
            # คนแรกของรอบ
            dur = self.manual_pace_sec if self.manual_pace_sec else 3.5
            self.raw_durations.append(dur)
            self.active_durations.append(dur)

        steady_pace, _, _ = self._calculate_robust_cadence()
        cur_rate = round(60.0 / steady_pace, 1) if steady_pace > 0 else 0.0
        now_dt = datetime.now()
        time_str = now_dt.strftime("%H:%M:%S")
        full_dt_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # บันทึกลง Session Log ทั้งหมดสำหรับ Export Report & CSV
        self.session_events.append({
            "index": self.current_count,
            "timestamp": full_dt_str,
            "time_str": time_str,
            "duration_sec": round(dur, 1),
            "event_type": event_type,
            "running_pace": round(steady_pace, 1),
            "running_rate": cur_rate,
            "action": "ai_confer",
            "notes": "บัณฑิตรับปริญญา" if event_type != "intermission" else f"ช่วงหยุดพักแถว/เปลี่ยนรอบ ({round(dur, 1)}s)"
        })

        # เก็บ 20 คนล่าสุดสำหรับแสดงผล Real-time Cadence Strip
        self.recent_events.append({
            "count": self.current_count,
            "duration": round(dur, 1),
            "type": event_type,
            "time": time_str
        })
        if len(self.recent_events) > 20:
            self.recent_events.pop(0)

        # ป้องกันเมมโมรี่บวมในส่วนของ array กรองความเร็ว (เก็บ 300 คนล่าสุด)
        if len(self.active_durations) > 300:
            self.active_durations = self.active_durations[-150:]
        if len(self.raw_durations) > 300:
            self.raw_durations = self.raw_durations[-150:]

        self.last_confer_timestamp = now
        return self.get_summary()

    def manual_adjust(self, delta: int) -> Dict:
        """ปรับเพิ่ม/ลบจำนวนคนด้วยมือ"""
        self.current_count = max(0, self.current_count + delta)
        self._auto_handle_excess()
        self.last_confer_timestamp = None
        steady_pace, _, _ = self._calculate_robust_cadence()
        self.session_events.append({
            "index": self.current_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time_str": datetime.now().strftime("%H:%M:%S"),
            "duration_sec": 0.0,
            "event_type": "manual",
            "running_pace": round(steady_pace, 1),
            "running_rate": round(60.0 / steady_pace, 1) if steady_pace > 0 else 0.0,
            "action": "manual_adjust",
            "notes": f"แอดมินปรับยอดแมนนวล ({'+' if delta > 0 else ''}{delta} คน)"
        })
        return self.get_summary()

    def set_current_count(self, count: int) -> Dict:
        """ตั้งค่ายอดคนปัจจุบันโดยตรง"""
        self.current_count = max(0, count)
        self._auto_handle_excess()
        self.last_confer_timestamp = None
        steady_pace, _, _ = self._calculate_robust_cadence()
        self.session_events.append({
            "index": self.current_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time_str": datetime.now().strftime("%H:%M:%S"),
            "duration_sec": 0.0,
            "event_type": "manual",
            "running_pace": round(steady_pace, 1),
            "running_rate": round(60.0 / steady_pace, 1) if steady_pace > 0 else 0.0,
            "action": "set_count",
            "notes": f"แอดมินตั้งค่ายอดคนปัจจุบันเป็น {count} คน"
        })
        return self.get_summary()

    def set_total_target(self, target: int) -> Dict:
        """ตั้งเป้าหมายบัณฑิตทั้งหมดในรอบนี้ (ซิงก์ลงเซสชันรอบที่กำลังใช้งานอัตโนมัติ)"""
        self.total_target = max(1, target)
        if self.active_session_key in self.sessions:
            sess = self.sessions[self.active_session_key]
            sess["total_target"] = self.total_target
            # ถ้ามีคิวมหาวิทยาลัย 1 แห่ง ให้ซิงก์ยอดของมหาวิทยาลัยนั้นตามไปด้วย 100%
            if "universities" in sess and len(sess["universities"]) == 1:
                sess["universities"][0]["target"] = self.total_target

            # ถ้ายังไม่ได้กดตัดพักจริง ให้คำนวณแบ่งช่วงก่อน-หลังพัก 60/40 อัตโนมัติให้ลงตัว
            if not getattr(self, "break_taken", False):
                half = max(1, int(self.total_target * 0.6))
                self.pre_break_range = f"1-{half:,}"
                self.post_break_range = f"{half + 1:,}-{self.total_target:,}"
            else:
                # ถ้าเคยตัดพักไปแล้ว ให้คงช่วงก่อนพักไว้ และขยายช่วงหลังพักให้ถึงเป้าหมายใหม่
                pre_start, pre_end, post_start, _ = self._parse_break_targets()
                self.post_break_range = f"{post_start:,}-{self.total_target:,}"

            self.sessions[self.active_session_key]["pre_break_range"] = self.pre_break_range
            self.sessions[self.active_session_key]["post_break_range"] = self.post_break_range
            self._save_sessions_config()
        return self.get_summary()

    def set_manual_pace(self, pace_sec: float) -> Dict:
        """บังคับใช้เวลาเฉลี่ยตามที่ผู้ใช้กำหนด (Override Auto)"""
        self.manual_pace_sec = max(0.5, min(30.0, float(pace_sec)))
        return self.get_summary()

    def clear_manual_pace(self) -> Dict:
        """กลับสู่โหมดคำนวณอัตโนมัติจากสถิติจริง"""
        self.manual_pace_sec = None
        return self.get_summary()

    def set_planned_finish(self, time_str: Optional[str]) -> Dict:
        """ตั้งเวลาตามแผนงานที่ต้องเสร็จ เช่น '12:30'"""
        val = time_str.strip() if time_str and time_str.strip() else None
        self.planned_finish_time = val

        # ซิงก์เวลาสิ้นสุดและช่วงเวลา (time_range) ลงในรอบพิธีปัจจุบันทันที
        if self.active_session_key in self.sessions:
            sess = self.sessions[self.active_session_key]
            if val:
                sess["finish_time"] = val
                st = sess.get("start_time", "08:30" if self.active_session_key == "morning" else "13:30")
                sess["time_range"] = f"{st} - {val}"
            else:
                sess["finish_time"] = ""
            self._save_sessions_config()

        return self.get_summary()

    def set_ceremony_info(self, title: Optional[str] = None, session_name: Optional[str] = None,
                          pre_break: Optional[str] = None, post_break: Optional[str] = None) -> Dict:
        """ตั้งค่าข้อมูลพิธีการสำหรับแสดงบนจอหน้างาน (Stage / On-site Display)"""
        if title is not None and title.strip():
            self.ceremony_title = title.strip()
        if session_name is not None and session_name.strip():
            self.session_name = session_name.strip()
        if pre_break is not None and pre_break.strip():
            self.pre_break_range = pre_break.strip()
        if post_break is not None and post_break.strip():
            self.post_break_range = post_break.strip()
        return self.get_summary()

    def _parse_break_targets(self) -> Tuple[int, int, int, int]:
        """
        แยกเป้าหมายตัวเลขก่อนพักและหลังพักจาก string เช่น '1-887' และ '888-1,383'
        Returns: (pre_start, pre_end, post_start, post_end)
        """
        pre_str = str(self.pre_break_range).replace(',', '').strip()
        post_str = str(self.post_break_range).replace(',', '').strip()

        pre_nums = [int(n) for n in re.findall(r'\d+', pre_str)]
        if len(pre_nums) >= 2:
            pre_start, pre_end = pre_nums[0], pre_nums[1]
        elif len(pre_nums) == 1:
            pre_start, pre_end = 1, pre_nums[0]
        else:
            pre_start, pre_end = 1, int(self.total_target * 0.6)

        post_nums = [int(n) for n in re.findall(r'\d+', post_str)]
        if len(post_nums) >= 2:
            post_start, post_end = post_nums[0], post_nums[1]
        elif len(post_nums) == 1:
            post_start, post_end = pre_end + 1, post_nums[0]
        else:
            post_start, post_end = pre_end + 1, self.total_target

        if post_end <= pre_end:
            post_end = max(self.total_target, pre_end + 1)

        return pre_start, pre_end, post_start, post_end

    def set_break_cutoff(self, cutoff_count: Optional[int] = None) -> Dict:
        """
        ปรับจุดตัดพักแถวอัตโนมัติตามยอดจริง (กรณีประธานพักก่อนหรือหลังกำหนด):
        ถ้าไม่ระบุ cutoff_count จะใช้ current_count ณ วินาทีนี้ทันที
        และล็อกว่าเข้าสู่ช่วงพักแล้ว (break_taken = True) เพื่อให้คนถัดไปนับเป็นช่วงหลังพัก
        """
        actual_cut = max(1, cutoff_count if cutoff_count is not None else self.current_count)
        self.break_taken = True
        self.pre_break_range = f"1-{actual_cut:,}"
        next_start = actual_cut + 1
        total_str = f"{self.total_target:,}"
        self.post_break_range = f"{next_start:,}-{total_str}"

        # บันทึกปรับลงเซสชันปัจจุบัน
        if self.active_session_key in self.sessions:
            self.sessions[self.active_session_key]["pre_break_range"] = self.pre_break_range
            self.sessions[self.active_session_key]["post_break_range"] = self.post_break_range
            self._save_sessions_config()

        return self.get_summary()

    def toggle_break_phase(self) -> Dict:
        """สลับสถานะว่าเข้าสู่ช่วงหลังพักแล้วหรือไม่"""
        self.break_taken = not getattr(self, "break_taken", False)
        return self.get_summary()

    def sync_target_to_current(self) -> Dict:
        """
        ปรับเป้าหมายทั้งหมดให้ตรงกับยอดจริง (กรณีคนขาดหรือไม่ครบ หรือมีคนเกิน):
        """
        if self.current_count > 0:
            diff = self.current_count - self.total_target
            self.total_target = self.current_count
            if self.active_session_key in self.sessions:
                self.sessions[self.active_session_key]["total_target"] = self.total_target
                pre_start, pre_end, post_start, _ = self._parse_break_targets()
                if self.total_target > pre_end:
                    self.post_break_range = f"{post_start:,}-{self.total_target:,}"
                else:
                    self.pre_break_range = f"1-{self.total_target:,}"
                    self.post_break_range = f"{self.total_target:,}-{self.total_target:,}"
                self.sessions[self.active_session_key]["pre_break_range"] = self.pre_break_range
                self.sessions[self.active_session_key]["post_break_range"] = self.post_break_range

                # หากเป็นรอบเช้า และมีรอบบ่าย ให้หักส่วนต่างจากรอบบ่ายอัตโนมัติ (ยอดรวมทั้งวันคงที่)
                if self.active_session_key == "morning" and "afternoon" in self.sessions and diff != 0:
                    cur_a = self.sessions["afternoon"]["total_target"]
                    new_a = max(1, cur_a - diff)
                    self.sessions["afternoon"]["total_target"] = new_a
                    a_half = int(new_a * 0.6)
                    self.sessions["afternoon"]["pre_break_range"] = f"1-{a_half:,}"
                    self.sessions["afternoon"]["post_break_range"] = f"{a_half + 1:,}-{new_a:,}"

                self._save_sessions_config()
        return self.get_summary()

    def split_day_total(self, day_total: int, morning_target: int) -> Dict:
        """
        แบ่งยอดทั้งวัน เช่น ทั้งวันมี 2,000 คน ตัดรอบเช้า 900 คน -> รอบบ่ายจะเหลือ 1,100 คน อัตโนมัติ!
        """
        day_total = max(2, int(day_total))
        morning_target = max(1, min(day_total - 1, int(morning_target)))
        afternoon_target = day_total - morning_target

        # ปรับยอดรอบเช้า (มีช่วงก่อนพัก-หลังพักในตัว)
        m_half = int(morning_target * 0.6)
        self.sessions["morning"]["total_target"] = morning_target
        self.sessions["morning"]["pre_break_range"] = f"1-{m_half:,}"
        self.sessions["morning"]["post_break_range"] = f"{m_half + 1:,}-{morning_target:,}"

        # ปรับยอดรอบบ่าย (มียอด 1,100 คน พร้อมช่วงก่อนพัก-หลังพักในตัว)
        a_half = int(afternoon_target * 0.6)
        self.sessions["afternoon"]["total_target"] = afternoon_target
        self.sessions["afternoon"]["pre_break_range"] = f"1-{a_half:,}"
        self.sessions["afternoon"]["post_break_range"] = f"{a_half + 1:,}-{afternoon_target:,}"

        self._save_sessions_config()

        # ซิงก์รอบที่กำลังแอคทีฟ
        if self.active_session_key == "morning":
            self.total_target = morning_target
            self.pre_break_range = self.sessions["morning"]["pre_break_range"]
            self.post_break_range = self.sessions["morning"]["post_break_range"]
        else:
            self.total_target = afternoon_target
            self.pre_break_range = self.sessions["afternoon"]["pre_break_range"]
            self.post_break_range = self.sessions["afternoon"]["post_break_range"]

        return self.get_summary()

    def reset(self):
        """รีเซ็ตระบบเริ่มรอบใหม่"""
        self.current_count = 0
        self.break_taken = False
        self.start_timestamp = time.time()
        self.start_datetime = datetime.now()
        self.end_datetime = None
        self.last_confer_timestamp = None
        self.raw_durations.clear()
        self.active_durations.clear()
        self.recent_events.clear()
        self.session_events.clear()
        self.is_paused = False
        self.counting_mode = 'auto'  # 'auto' | 'manual'
        self.manual_pace_sec = None
        self.total_pause_time_sec = 0.0
        self.intermission_count = 0

    def set_counting_mode(self, mode: str) -> Dict:
        """สลับโหมดการนับ: 'auto' (ระบบอัตโนมัติ AI) หรือ 'manual' (ระบบนับด้วยมือ)"""
        if mode in ("auto", "manual"):
            self.counting_mode = mode
            if mode == "manual":
                self.is_paused = True  # หยุดระบบนับอัตโนมัติทันที
            else:
                self.is_paused = False # กลับมาเปิดระบบอัตโนมัติ
        return self.get_summary()

    def toggle_pause(self) -> bool:
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self.counting_mode = "auto"
        return self.is_paused

    def _calculate_robust_cadence(self) -> Tuple[float, float, str]:
        """
        คำนวณความเร็วที่เสถียรและใช้งานได้จริงในพิธีการ:
        - steady_pace: ใช้สำหรับคำนวณ ETA (ตัด outlier ออก ไม่แกว่งตามการหยุดพัก)
        - instant_pace: สปีดของ 5 คนล่าสุด (บอกสปีด ณ ตอนนี้)
        - trend: "FAST" | "OPTIMAL" | "SLOW" | "STABLE"
        """
        if self.manual_pace_sec is not None:
            return self.manual_pace_sec, self.manual_pace_sec, "MANUAL"

        if not self.active_durations:
            return 3.5, 3.5, "OPTIMAL"

        # 1. Steady Pace: ตัด 15% ต่ำสุดและสูงสุด (Trimmed Mean) ของ 30 คนล่าสุด
        recent_active = self.active_durations[-35:]
        n = len(recent_active)
        if n >= 6:
            sorted_d = sorted(recent_active)
            trim_count = max(1, int(n * 0.15))
            trimmed = sorted_d[trim_count:-trim_count]
            steady_pace = sum(trimmed) / len(trimmed) if trimmed else (sum(recent_active) / n)
        else:
            steady_pace = sum(recent_active) / n

        # 2. Instant Pace: 5 คนล่าสุด (weighted ให้คนหลังสุดมีน้ำหนักมากสุด)
        last_5 = self.active_durations[-5:]
        if last_5:
            weights = [1.0 + (i * 0.25) for i in range(len(last_5))]
            instant_pace = sum(d * w for d, w in zip(last_5, weights)) / sum(weights)
        else:
            instant_pace = steady_pace

        # 3. Trend evaluation
        diff = instant_pace - steady_pace
        if diff < -0.4:
            trend = "ACCELERATING"   # กำลังเร่งฝีเท้าขึ้น (ใช้เวลาน้อยลง)
        elif diff > 0.4:
            trend = "SLOWING"        # กำลังชะลอลง (ใช้เวลาต่อคนมากขึ้น)
        else:
            trend = "STABLE"

        return round(steady_pace, 2), round(instant_pace, 2), trend

    def get_summary(self) -> Dict:
        now = time.time()
        last_dur = self.raw_durations[-1] if self.raw_durations else 0.0

        steady_pace, instant_pace, trend = self._calculate_robust_cadence()
        is_auto = (self.manual_pace_sec is None)

        # Rate calculations
        rate_per_min = (60.0 / steady_pace) if steady_pace > 0 else 0.0
        instant_rate = (60.0 / instant_pace) if instant_pace > 0 else 0.0

        # Progress & Over/Under Target Calculations (รองรับทั้งกรณีรับน้อยกว่าหรือรับเกินเป้า)
        is_over_target = self.current_count > self.total_target
        over_target_count = max(0, self.current_count - self.total_target)
        under_target_count = max(0, self.total_target - self.current_count)
        remaining = under_target_count
        progress_pct = round((self.current_count / self.total_target) * 100, 1) if self.total_target > 0 else 0.0

        if is_over_target:
            remaining_label = f"เกินเป้า +{over_target_count:,} คน"
        elif remaining == 0:
            remaining_label = "ครบตามเป้าหมาย 100%"
        else:
            remaining_label = f"คงเหลือ {remaining:,} คน"

        # ETA Prediction based on robust steady pace
        if is_over_target or remaining == 0:
            est_seconds_left = 0
            eta_formatted = datetime.now().strftime("%H:%M:%S")
            remaining_text = f"เกินเป้าหมาย +{over_target_count:,} คน (100%++ 🎉)" if is_over_target else "ครบตามเป้าหมายแล้ว 🎉"
        else:
            est_seconds_left = int(remaining * steady_pace)
            finish_dt = datetime.now() + timedelta(seconds=est_seconds_left)
            eta_formatted = finish_dt.strftime("%H:%M:%S")

            # Human-readable remaining time
            rem_hours = est_seconds_left // 3600
            rem_mins = (est_seconds_left % 3600) // 60
            rem_secs = est_seconds_left % 60

            if rem_hours > 0:
                remaining_text = f"อีก {rem_hours} ชม. {rem_mins} นาที"
            elif rem_mins > 0:
                remaining_text = f"อีก {rem_mins} นาที {rem_secs} วิ"
            else:
                remaining_text = f"อีก {rem_secs} วินาที"

        # Cadence status level
        if steady_pace < 2.6:
            pacing_status = "FAST"
            pacing_label = "⚡ เร็วมาก (กระชั้นชิด)"
            pacing_color = "#38BDF8"  # Blue
        elif steady_pace <= 4.2:
            pacing_status = "OPTIMAL"
            pacing_label = "✅ จังหวะมาตรฐาน (เหมาะสม)"
            pacing_color = "#10B981"  # Green
        elif steady_pace <= 5.5:
            pacing_status = "RELAXED"
            pacing_label = "⚠️ ค่อนข้างช้า"
            pacing_color = "#F59E0B"  # Amber
        else:
            pacing_status = "SLOW"
            pacing_label = "⛔ ช้ากว่าเกณฑ์"
            pacing_color = "#EF4444"  # Red

        # Schedule Adherence Comparison (ถ้าผู้ใช้ตั้งเวลาเสร็จตามแผน)
        schedule_status = "NONE"
        schedule_diff_min = 0.0
        schedule_text = ""
        target_pace_needed = None

        if self.planned_finish_time:
            try:
                # Parse planned finish (HH:MM or HH:MM:SS)
                t_parts = [int(p) for p in self.planned_finish_time.split(":")[:2]]
                now_dt = datetime.now()
                target_dt = now_dt.replace(hour=t_parts[0], minute=t_parts[1], second=0, microsecond=0)
                # Only roll over to next day if truly an overnight ceremony (late evening to early morning)
                if target_dt < now_dt and now_dt.hour >= 20 and t_parts[0] <= 6:
                    target_dt += timedelta(days=1)

                seconds_available = (target_dt - now_dt).total_seconds()
                diff_sec = seconds_available - est_seconds_left
                schedule_diff_min = round(diff_sec / 60.0, 1)

                if remaining > 0 and seconds_available > 10:
                    target_pace_needed = round(seconds_available / remaining, 1)

                if schedule_diff_min >= 2.0:
                    schedule_status = "AHEAD"
                    schedule_text = f"เร็วกว่าแผน {abs(schedule_diff_min):.0f} นาที"
                elif schedule_diff_min <= -2.0:
                    schedule_status = "BEHIND"
                    schedule_text = f"ช้ากว่าแผน {abs(schedule_diff_min):.0f} นาที"
                else:
                    schedule_status = "ON_TIME"
                    schedule_text = "ตรงตามแผนงาน (±1 นาที)"
            except Exception:
                pass

        # Elapsed time
        elapsed_sec = int(now - self.start_timestamp)
        elapsed_formatted = str(timedelta(seconds=elapsed_sec))

        # Real-time Break Batches (คำนวณยอดช่วงก่อนพัก และ หลังพัก แบบเรียลไทม์)
        pre_start, pre_end, post_start, post_end = self._parse_break_targets()
        pre_target = max(1, pre_end - pre_start + 1)
        post_target = max(1, post_end - post_start + 1)

        is_break_done = getattr(self, "break_taken", False)

        if not is_break_done:
            # 1. ยังอยู่ในช่วงก่อนพัก (ประธานยังไม่ได้สั่งพักแถว)
            pre_current = min(self.current_count, pre_end)
            pre_remaining = max(0, pre_end - self.current_count)
            pre_pct = round((pre_current / pre_target) * 100, 1) if pre_target > 0 else 0.0

            # ช่วงหลังพักยังไม่เริ่ม
            post_current = 0
            post_remaining = post_target
            post_pct = 0.0

            if self.current_count == 0:
                stage_status = "PRE_BREAK"
                stage_label = "ยังไม่เริ่มพิธี"
            elif self.current_count < pre_end:
                stage_status = "PRE_BREAK"
                stage_label = f"ช่วงก่อนพัก ({pre_current:,}/{pre_target:,} คน)"
            else:
                stage_status = "PRE_BREAK_EXCESS"
                stage_label = f"ช่วงก่อนพัก (รับเกินเดิม นับต่อเป็น {pre_current:,} คน)"
        else:
            # 2. เข้าสู่ช่วงหลังพักแล้ว (ประธานสั่งพักแถวเรียบร้อย)
            pre_current = pre_target
            pre_remaining = 0
            pre_pct = 100.0

            post_current = max(0, min(self.current_count - pre_end, post_target))
            post_remaining = max(0, post_target - post_current)
            post_pct = round((post_current / post_target) * 100, 1) if post_target > 0 else 0.0

            if self.current_count <= pre_end:
                stage_status = "AT_BREAK"
                stage_label = "⏸️ จุดพักแถว / กำลังรอเริ่มช่วงหลังพัก"
            elif self.current_count < self.total_target:
                stage_status = "POST_BREAK"
                stage_label = f"ช่วงหลังพัก ({post_current:,}/{post_target:,} คน)"
            else:
                stage_status = "COMPLETED"
                stage_label = "พิธีเสร็จสิ้นครบถ้วนสมบูรณ์ 🎉"

        # 4. เวลาคาดการณ์ที่จะถึงจุดพักแถว (Break ETA)
        break_est_time = None
        break_remaining_text = ""
        if not is_break_done and pre_remaining > 0:
            sec_to_break = int(pre_remaining * steady_pace)
            b_dt = datetime.now() + timedelta(seconds=sec_to_break)
            break_est_time = b_dt.strftime("%H:%M:%S")
            b_hours = sec_to_break // 3600
            b_mins = (sec_to_break % 3600) // 60
            b_secs = sec_to_break % 60
            if b_hours > 0:
                break_remaining_text = f"อีก {b_hours} ชม. {b_mins} นาที"
            elif b_mins > 0:
                break_remaining_text = f"อีก {b_mins} นาที {b_secs} วิ"
            else:
                break_remaining_text = f"อีก {b_secs} วินาที"
        elif not is_break_done and pre_remaining == 0 and self.current_count > 0:
            break_remaining_text = "ขยายรับช่วงแรกต่อ"
        else:
            break_remaining_text = "ผ่านจุดพักแล้ว"

        # 5. คำนวณคิวมหาวิทยาลัย/คณะย่อย (Multi-University Queue)
        active_sess = self.sessions.get(self.active_session_key, {})
        uni_list = active_sess.get("universities", [])
        active_uni = None
        uni_list_with_ranges = []
        display_ceremony_title = self.ceremony_title

        if uni_list and len(uni_list) > 0:
            cum = 0
            for idx, u in enumerate(uni_list):
                u_name = str(u.get("name", f"สถาบันที่ {idx+1}")).strip()
                try:
                    u_target = max(1, int(u.get("target", 0)))
                except (ValueError, TypeError):
                    u_target = 100
                start_num = cum + 1
                end_num = cum + u_target
                cum = end_num

                is_done = self.current_count >= end_num
                is_current = (start_num <= self.current_count <= end_num) or (self.current_count == 0 and idx == 0) or (self.current_count > cum and idx == len(uni_list) - 1)

                sub_count = 0
                if self.current_count >= end_num:
                    sub_count = u_target
                elif self.current_count >= start_num:
                    sub_count = self.current_count - start_num + 1

                sub_rem = max(0, u_target - sub_count)
                sub_pct = round((sub_count / max(1, u_target)) * 100, 1)
                next_name = str(uni_list[idx + 1].get("name", "")).strip() if idx + 1 < len(uni_list) else ""

                uni_obj = {
                    "index": idx + 1,
                    "total_units": len(uni_list),
                    "name": u_name,
                    "target": u_target,
                    "range_str": f"{start_num:,} - {end_num:,}",
                    "start_num": start_num,
                    "end_num": end_num,
                    "sub_count": sub_count,
                    "sub_remaining": sub_rem,
                    "sub_percent": sub_pct,
                    "is_done": is_done,
                    "is_current": is_current,
                    "next_university_name": next_name
                }
                uni_list_with_ranges.append(uni_obj)
                if is_current and active_uni is None:
                    active_uni = uni_obj

            if active_uni:
                display_ceremony_title = active_uni["name"]
                self.ceremony_title = active_uni["name"]

        return {
            "theme":                    getattr(self, "theme", "purple-yellow"),
            "current_count":            self.current_count,
            "total_target":             self.total_target,
            "remaining":                remaining,
            "progress_percent":         progress_pct,
            "last_duration_sec":        round(last_dur, 1),
            "avg_duration_sec":         round(steady_pace, 1),
            "instant_duration_sec":     round(instant_pace, 1),
            "pace_trend":               trend,                # "STABLE" | "ACCELERATING" | "SLOWING"
            "pacing_status":            pacing_status,        # "FAST" | "OPTIMAL" | "RELAXED" | "SLOW"
            "pacing_label":             pacing_label,
            "pacing_color":             pacing_color,
            "rate_per_min":             round(rate_per_min, 1),
            "instant_rate_per_min":     round(instant_rate, 1),
            "estimated_finish_time":    eta_formatted,
            "estimated_remaining_time": remaining_text,
            "est_seconds_left":         est_seconds_left,
            "elapsed_time":             elapsed_formatted,
            "is_paused":                self.is_paused,
            "counting_mode":            getattr(self, "counting_mode", "auto"),
            "manual_pace_sec":          self.manual_pace_sec,
            "planned_finish_time":      self.planned_finish_time,
            "schedule_status":          schedule_status,
            "schedule_diff_min":        schedule_diff_min,
            "schedule_text":            schedule_text,
            "target_pace_needed":       target_pace_needed,
            "samples_collected":        len(self.active_durations),
            "intermission_count":       self.intermission_count,
            "recent_events":            self.recent_events,
            "timestamp":                datetime.now().strftime("%H:%M:%S"),
            "active_session":           self.active_session_key,
            "ceremony_title":           display_ceremony_title,
            "session_title":            display_ceremony_title,
            "active_university":        active_uni,
            "universities_queue":       uni_list_with_ranges,
            "session_name":             self.session_name,
            "session_time_range":       self.sessions.get(self.active_session_key, {}).get("time_range", ""),
            "pre_break_range":          self.pre_break_range,
            "post_break_range":         self.post_break_range,
            "pre_break_start":          pre_start,
            "pre_break_end":            pre_end,
            "pre_break_target":         pre_target,
            "pre_break_current":        pre_current,
            "pre_break_remaining":      pre_remaining,
            "pre_break_percent":        min(100.0, pre_pct),
            "post_break_start":         post_start,
            "post_break_end":           post_end,
            "post_break_target":        post_target,
            "post_break_current":       post_current,
            "post_break_remaining":     post_remaining,
            "post_break_percent":       min(100.0, post_pct),
            "stage_status":             stage_status,
            "is_over_target":           is_over_target,
            "over_target_count":        over_target_count,
            "under_target_count":       under_target_count,
            "remaining_label":          remaining_label,
            "break_est_time":           break_est_time,
            "break_remaining_text":     break_remaining_text,
            "break_taken":              getattr(self, "break_taken", False),
            "auto_deduct_excess":       getattr(self, "auto_deduct_excess", True),
            "last_switched_from":       getattr(self, "last_switched_from", None),
            "can_undo_switch":          bool(getattr(self, "last_switched_from", None)),
            "saved_session_counts":     {k: v.get("current_count", 0) for k, v in getattr(self, "session_states", {}).items()},
            "obs_settings":             getattr(self, "obs_settings", {"position": "bottom-left", "scale": 1.0, "pad_x": 48, "pad_y": 36}),
            "sessions":                 self.sessions,
        }

    def get_ceremony_report(self) -> Dict:
        """
        ประมวลผลสรุปรายงานภาพรวมของพิธี (Post-Ceremony Executive Report):
        สถิติเวลาทั้งหมด, เวลาที่รับจริง, เวลาหยุดพัก, ความเร็วเฉลี่ย, สัดส่วนความเร็ว, ประวัติทุกคน
        """
        now = time.time()
        elapsed_sec = max(1, int(now - self.start_timestamp))
        elapsed_str = str(timedelta(seconds=elapsed_sec))

        steady_pace, _, _ = self._calculate_robust_cadence()
        avg_rate = round(60.0 / steady_pace, 1) if steady_pace > 0 else 0.0

        # สถิติ Fast / Normal / Slow / Intermission
        dist = {"fast": 0, "normal": 0, "slow": 0, "intermission": 0, "manual": 0}
        for ev in self.session_events:
            t = ev.get("event_type", "normal")
            if t in dist:
                dist[t] += 1
            else:
                dist["normal"] += 1

        active_durations_clean = [d for d in self.active_durations if 0.5 <= d <= self.MAX_CADENCE_SEC]
        fastest_pace = round(min(active_durations_clean), 1) if active_durations_clean else 0.0
        slowest_active = round(max(active_durations_clean), 1) if active_durations_clean else 0.0
        active_time_sec = round(sum(active_durations_clean), 1)
        active_time_str = str(timedelta(seconds=int(active_time_sec)))
        pause_time_sec = round(self.total_pause_time_sec, 1)
        pause_time_str = str(timedelta(seconds=int(pause_time_sec)))

        progress_pct = round((self.current_count / self.total_target) * 100, 1) if self.total_target > 0 else 0.0

        return {
            "ceremony_title": "พิธีพระราชทานปริญญาบัตร / พิธีประสาทปริญญาบัตร",
            "start_time": self.start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_elapsed_sec": elapsed_sec,
            "total_elapsed_str": elapsed_str,
            "active_time_sec": active_time_sec,
            "active_time_str": active_time_str,
            "pause_time_sec": pause_time_sec,
            "pause_time_str": pause_time_str,
            "total_graduates": self.current_count,
            "total_target": self.total_target,
            "progress_percent": progress_pct,
            "intermission_count": self.intermission_count,
            "avg_pace_sec": steady_pace,
            "avg_rate_per_min": avg_rate,
            "fastest_pace_sec": fastest_pace,
            "slowest_active_pace_sec": slowest_active,
            "distribution": dist,
            "planned_finish_time": self.planned_finish_time,
            "total_events_count": len(self.session_events),
            "events": self.session_events
        }

    def generate_csv_string(self) -> str:
        """
        สร้างไฟล์ CSV สำหรับเปิดด้วย Microsoft Excel / Google Sheets
        ใส่ BOM (\ufeff) ป้องกันภาษาไทยเพี้ยน/เป็นภาษาต่างดาวใน Excel
        """
        import io, csv
        report = self.get_ceremony_report()
        output = io.StringIO()
        writer = csv.writer(output)

        # Header Metadata
        writer.writerow(["=== รายงานสรุปสถิติพิธีพระราชทานปริญญาบัตร (Ceremony Analytics Report) ==="])
        writer.writerow(["วันเวลาเริ่มพิธี", report["start_time"]])
        writer.writerow(["วันเวลาสิ้นสุด/ปัจจุบัน", report["end_time"]])
        writer.writerow(["ระยะเวลาทั้งหมดในพิธี", report["total_elapsed_str"]])
        writer.writerow(["เวลาที่บัณฑิตรับจริง (Active Time)", report["active_time_str"]])
        writer.writerow(["เวลาหยุดพัก/เปลี่ยนแถว (Intermission)", f"{report['pause_time_str']} ({report['intermission_count']} ครั้ง)"])
        writer.writerow(["จำนวนบัณฑิตที่รับแล้วทั้งหมด", f"{report['total_graduates']} คน จากเป้าหมาย {report['total_target']} คน ({report['progress_percent']}%)"])
        writer.writerow(["เวลาเฉลี่ยที่ใช้ต่อคน (Steady Pace)", f"{report['avg_pace_sec']} วินาที/คน"])
        writer.writerow(["อัตราความเร็วเฉลี่ย (Cadence Rate)", f"{report['avg_rate_per_min']} คน/นาที"])
        writer.writerow(["ช่วงเวลาที่เร็วที่สุด", f"{report['fastest_pace_sec']} วินาที"])
        writer.writerow(["ช่วงเวลาที่ช้าที่สุด (ปกติ)", f"{report['slowest_active_pace_sec']} วินาที"])
        if report["planned_finish_time"]:
            writer.writerow(["เวลาตามแผนงาน", report["planned_finish_time"]])
        writer.writerow([])
        writer.writerow(["สัดส่วนจังหวะการรับปริญญา"])
        d = report["distribution"]
        writer.writerow(["จังหวะเร็วมาก (< 2.6s)", f"{d.get('fast', 0)} คน"])
        writer.writerow(["จังหวะมาตรฐาน (2.6s - 4.2s)", f"{d.get('normal', 0)} คน"])
        writer.writerow(["จังหวะช้า (> 4.2s)", f"{d.get('slow', 0)} คน"])
        writer.writerow(["ช่วงหยุดพัก/เปลี่ยนแถว (> 8s)", f"{d.get('intermission', 0)} ครั้ง"])
        writer.writerow(["การปรับแมนนวล", f"{d.get('manual', 0)} ครั้ง"])
        writer.writerow([])

        # Table of Events
        writer.writerow(["ลำดับที่", "วัน-เวลา (Timestamp)", "เวลาที่รับ (HH:MM:SS)", "เวลาที่ใช้ (วินาที)", "ระดับความเร็ว", "ความเร็วเฉลี่ยสะสม (วิ/คน)", "อัตราสะสม (คน/นาที)", "ประเภท", "หมายเหตุ"])
        
        type_labels = {
            "fast": "เร็วมาก (⚡)",
            "normal": "มาตรฐาน (✅)",
            "slow": "ช้า (⚠️)",
            "intermission": "หยุดพัก/เปลี่ยนแถว (⏸️)",
            "manual": "ปรับแมนนวล (⚙️)"
        }

        for ev in self.session_events:
            idx = ev.get("index", "")
            ts = ev.get("timestamp", "")
            t_str = ev.get("time_str", "")
            dur = ev.get("duration_sec", 0.0)
            etype = ev.get("event_type", "normal")
            elabel = type_labels.get(etype, etype)
            pace = ev.get("running_pace", "")
            rate = ev.get("running_rate", "")
            action = ev.get("action", "")
            notes = ev.get("notes", "")
            writer.writerow([idx, ts, t_str, dur, elabel, pace, rate, action, notes])

        return output.getvalue()
