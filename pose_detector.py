import cv2
import time
import numpy as np
from collections import deque


class GraduationPoseDetector:
    def __init__(self):
        # Zone 1: Person / Body ROI
        self.roi_person = {
            "x_min": 0.25, "y_min": 0.20,
            "x_max": 0.58, "y_max": 0.88
        }

        # Zone 2: Hand / Diploma Handover ROI
        self.roi_hand = {
            "x_min": 0.58, "y_min": 0.42,
            "x_max": 0.88, "y_max": 0.75
        }

        # Zone 3: Presenter / Chairman Exclusion ROI
        self.roi_exclude = {
            "x_min": 0.12, "y_min": 0.30,
            "x_max": 0.38, "y_max": 0.88
        }
        self.exclude_enabled = True

        # ── Tunable parameters ──────────────────────────────────────────────
        self.sensitivity    = 2.0
        self.cooldown_sec   = 1.8
        self.detection_mode = "hand_priority"  # "hand_priority" | "dual" | "tripwire" | "arm_raise"

        # ── State machine ────────────────────────────────────────────────────
        self.state = "IDLE"
        self.confirmed_ts       = 0.0
        self.last_trigger_ts    = 0.0
        self.last_trigger_timestamp = 0.0

        # ── Callback ─────────────────────────────────────────────────────────
        self.on_graduate_received = None

        # ── Background subtractors ─────────────────────────────────────────
        self.bg_sub_person = cv2.createBackgroundSubtractorMOG2(
            history=120, varThreshold=32, detectShadows=False)
        self.bg_sub_hand   = cv2.createBackgroundSubtractorMOG2(
            history=80,  varThreshold=28, detectShadows=False)
        # Extra subtractor for the exclusion zone to measure presenter motion
        self.bg_sub_exclude = cv2.createBackgroundSubtractorMOG2(
            history=80,  varThreshold=28, detectShadows=False)

        # ── Prev-frame ────────────────────────────────────────────────────
        self._prev_gray_hand   = None
        self._prev_gray_person = None
        self._prev_gray_exclude = None

        # ── Consecutive-frame counters ────────────────────────────────────
        self._hand_confirm_frames = 0
        self._hand_absent_frames  = 0
        self.CONFIRM_FRAMES_NEEDED = 3
        self.ABSENT_FRAMES_RESET   = 2

        # ── Camera Shake & Anti-Jitter Filter ─────────────────────────────
        self._prev_global_gray = None
        self.camera_shake_detected = False
        self.anti_shake_enabled = True
        self.SHAKE_PIXEL_THRESHOLD = 0.85
        self._morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        # ── Arm-raise tracking (for arm_raise mode) ───────────────────────
        self.ARM_UP_RATIO   = 0.62
        self.ARM_DOWN_RATIO = 0.72
        self.ARM_UP_FRAMES  = 1
        self._arm_up_frames    = 0
        self._arm_down_frames  = 0
        self._arm_peak_y_ratio = 1.0
        self._centroid_y_buf   = deque(maxlen=5)

    # ── ROI setters ──────────────────────────────────────────────────────

    def set_roi_person(self, x_min, y_min, x_max, y_max):
        self.roi_person["x_min"] = max(0.0, min(1.0, float(x_min)))
        self.roi_person["y_min"] = max(0.0, min(1.0, float(y_min)))
        self.roi_person["x_max"] = max(self.roi_person["x_min"] + 0.05, min(1.0, float(x_max)))
        self.roi_person["y_max"] = max(self.roi_person["y_min"] + 0.05, min(1.0, float(y_max)))

    def set_roi_hand(self, x_min, y_min, x_max, y_max):
        self.roi_hand["x_min"] = max(0.0, min(1.0, float(x_min)))
        self.roi_hand["y_min"] = max(0.0, min(1.0, float(y_min)))
        self.roi_hand["x_max"] = max(self.roi_hand["x_min"] + 0.05, min(1.0, float(x_max)))
        self.roi_hand["y_max"] = max(self.roi_hand["y_min"] + 0.05, min(1.0, float(y_max)))

    def set_roi_exclude(self, x_min, y_min, x_max, y_max):
        self.roi_exclude["x_min"] = max(0.0, min(1.0, float(x_min)))
        self.roi_exclude["y_min"] = max(0.0, min(1.0, float(y_min)))
        self.roi_exclude["x_max"] = max(self.roi_exclude["x_min"] + 0.05, min(1.0, float(x_max)))
        self.roi_exclude["y_max"] = max(self.roi_exclude["y_min"] + 0.05, min(1.0, float(y_max)))

    def set_tuning(self, sensitivity: float = None, cooldown: float = None, mode: str = None):
        if sensitivity is not None:
            self.sensitivity = max(0.5, min(5.0, float(sensitivity)))
        if cooldown is not None:
            self.cooldown_sec = max(0.3, min(10.0, float(cooldown)))
        if mode in ["dual", "hand_priority", "tripwire", "arm_raise"]:
            self.detection_mode = mode

    def get_all_rois(self):
        return {
            "person":          self.roi_person,
            "hand":            self.roi_hand,
            "exclude":         self.roi_exclude,
            "exclude_enabled": self.exclude_enabled,
            "sensitivity":     self.sensitivity,
            "cooldown_sec":    self.cooldown_sec,
            "detection_mode":  self.detection_mode,
        }

    # ── Core zone motion analysis ──────────────────────────────────────────

    def _analyze_zone(self, frame, roi, bg_sub, prev_attr, mask_roi=None):
        """
        Returns (mog_ratio, diff_ratio, best_contour, x1, y1, x2, y2, centroid_y_ratio)
        mask_roi: if given, pixels in that region are EXCLUDED (set to 0) in fg mask.
        """
        h, w = frame.shape[:2]
        x1 = max(0, int(roi["x_min"] * w));  y1 = max(0, int(roi["y_min"] * h))
        x2 = max(0, int(roi["x_max"] * w));  y2 = max(0, int(roi["y_max"] * h))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0, 0.0, None, x1, y1, x2, y2, None

        mask = None
        if mask_roi and getattr(self, "exclude_enabled", True):
            ex1 = max(0, int(mask_roi["x_min"] * w))
            ey1 = max(0, int(mask_roi["y_min"] * h))
            ex2 = max(0, int(mask_roi["x_max"] * w))
            ey2 = max(0, int(mask_roi["y_max"] * h))
            ix1 = max(x1, ex1); iy1 = max(y1, ey1)
            ix2 = min(x2, ex2); iy2 = min(y2, ey2)
            if ix1 < ix2 and iy1 < iy2:
                mask = np.ones((y2 - y1, x2 - x1), dtype=np.uint8) * 255
                mask[iy1 - y1 : iy2 - y1, ix1 - x1 : ix2 - x1] = 0

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        fg   = bg_sub.apply(crop)
        if mask is not None:
            fg = cv2.bitwise_and(fg, fg, mask=mask)
        if hasattr(self, "_morph_kernel") and self._morph_kernel is not None:
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._morph_kernel)

        zone_area = float(cv2.countNonZero(mask)) if mask is not None else float(crop.shape[0] * crop.shape[1])
        if zone_area < 1:
            zone_area = 1.0

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mog_score = 0.0
        best_c = None
        for c in contours:
            a = cv2.contourArea(c)
            if a > mog_score:
                mog_score = a
                best_c = c
        mog_ratio = mog_score / zone_area

        motion_vx = 0.0
        motion_vy = 0.0
        norm_cx = 0.5
        prev_gray = getattr(self, prev_attr)
        diff_ratio = 0.0
        if prev_gray is not None and prev_gray.shape == gray.shape:
            diff = cv2.absdiff(prev_gray, gray)
            if mask is not None:
                diff = cv2.bitwise_and(diff, diff, mask=mask)
            m_mask = diff > 18
            diff_ratio = np.count_nonzero(m_mask) / zone_area
            # Ultra-fast motion direction via centroid tracking (0.02ms, zero lag)
            if diff_ratio > 0.003 and np.count_nonzero(m_mask) > 12:
                y_idx, x_idx = np.nonzero(m_mask)
                if len(x_idx) > 0:
                    curr_cx = float(np.mean(x_idx))
                    curr_cy = float(np.mean(y_idx))
                    crop_w = float(crop.shape[1])
                    norm_cx = curr_cx / crop_w if crop_w > 0 else 0.5
                    prev_c = getattr(self, prev_attr + "_centroid", None)
                    if prev_c is not None:
                        motion_vx = curr_cx - prev_c[0]
                        motion_vy = curr_cy - prev_c[1]
                    setattr(self, prev_attr + "_centroid", (curr_cx, curr_cy))
            else:
                setattr(self, prev_attr + "_centroid", None)
        setattr(self, prev_attr, gray)

        centroid_y_ratio = None
        if best_c is not None:
            M = cv2.moments(best_c)
            if M["m00"] > 0:
                cy_local = M["m01"] / M["m00"]
                zone_h = y2 - y1
                centroid_y_ratio = cy_local / zone_h if zone_h > 0 else None

        return mog_ratio, diff_ratio, best_c, x1, y1, x2, y2, centroid_y_ratio, motion_vx, motion_vy, norm_cx

    # ── Exclusion zone motion level ────────────────────────────────────────

    def _exclude_motion_ratio(self, frame):
        """Returns the motion level inside the exclusion zone (0..1)."""
        if not self.exclude_enabled:
            return 0.0
        h, w = frame.shape[:2]
        roi = self.roi_exclude
        x1 = max(0, int(roi["x_min"] * w)); y1 = max(0, int(roi["y_min"] * h))
        x2 = max(0, int(roi["x_max"] * w)); y2 = max(0, int(roi["y_max"] * h))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        fg = self.bg_sub_exclude.apply(crop)
        area = float(crop.shape[0] * crop.shape[1])
        return np.count_nonzero(fg) / area if area > 0 else 0.0

    # ── Main per-frame processing ──────────────────────────────────────────

    def process_frame(self, frame):
        if frame is None:
            return None, False

        h, w = frame.shape[:2]
        now  = time.time()
        triggered = False
        s = self.sensitivity

        P_MOG_THRESH  = max(0.004, 0.025 / s)
        P_DIFF_THRESH = max(0.003, 0.012 / s)
        H_MOG_THRESH  = max(0.005, 0.020 / s)
        H_DIFF_THRESH = max(0.004, 0.012 / s)

        # ── Global Camera Shake / Jitter Filter (Phase Correlation) ───────
        self.camera_shake_detected = False
        small_gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 120))
        if self._prev_global_gray is not None and getattr(self, "anti_shake_enabled", True):
            shift, resp = cv2.phaseCorrelate(
                self._prev_global_gray.astype(np.float32), 
                small_gray.astype(np.float32)
            )
            shake_mag = float(np.hypot(shift[0], shift[1]))
            # If the entire image shifted globally by > 0.85 pixel with good correlation response:
            if shake_mag > self.SHAKE_PIXEL_THRESHOLD and resp > 0.08:
                self.camera_shake_detected = True
        self._prev_global_gray = small_gray

        # ── Analyze zones ─────────────────────────────────────────────────
        p_mog, p_diff, p_best, px1, py1, px2, py2, p_cy, _, _, _ = self._analyze_zone(
            frame, self.roi_person, self.bg_sub_person, "_prev_gray_person")

        h_mog, h_diff, h_best, hx1, hy1, hx2, hy2, _, h_vx, h_vy, h_norm_cx = self._analyze_zone(
            frame, self.roi_hand, self.bg_sub_hand, "_prev_gray_hand",
            mask_roi=self.roi_exclude)

        # ── Presenter motion level ─────────────────────────────────────────
        excl_motion = self._exclude_motion_ratio(frame)
        EXCL_SUPPRESS_THRESH = max(0.06, 0.12 / s)
        presenter_active = self.exclude_enabled and (excl_motion > EXCL_SUPPRESS_THRESH)

        # ── Fast Direction analysis (relative to Exclusion Box) ───────────
        ex_cx = (self.roi_exclude["x_min"] + self.roi_exclude["x_max"]) / 2.0
        hd_cx = (self.roi_hand["x_min"] + self.roi_hand["x_max"]) / 2.0
        chairman_on_left = ex_cx < hd_cx

        dir_proj = h_vx if chairman_on_left else -h_vx
        dir_from_presenter = False
        dir_from_graduate = False

        if self.exclude_enabled:
            if chairman_on_left:
                # Chairman is on the LEFT of the hand box.
                # Any motion in the left half (h_norm_cx < 0.50) OR moving rightward (h_vx > 0.15) is from the Chairman!
                if h_norm_cx < 0.50 or h_vx > 0.15:
                    dir_from_presenter = True
                # Graduate is on the RIGHT: must be in the right half (h_norm_cx >= 0.50)
                if h_norm_cx >= 0.50 and h_vx <= 0.10:
                    dir_from_graduate = True
            else:
                # Chairman on right
                if h_norm_cx > 0.50 or h_vx < -0.15:
                    dir_from_presenter = True
                if h_norm_cx <= 0.50 and h_vx >= -0.10:
                    dir_from_graduate = True

        person_present = (p_mog >= P_MOG_THRESH) or (p_diff >= P_DIFF_THRESH)

        # ─────────────────────────────────────────────────────────────────
        # HAND PRIORITY / DUAL MODES (default)
        # ─────────────────────────────────────────────────────────────────
        in_cooldown = (now - self.last_trigger_ts) < self.cooldown_sec

        if self.detection_mode in ("hand_priority", "dual"):
            if self._prev_gray_hand is not None:
                hand_raw = (h_mog >= H_MOG_THRESH) or (h_diff >= H_DIFF_THRESH)
            else:
                hand_raw = h_mog >= H_MOG_THRESH

            # Reject tiny noise / jitter slivers (hand must be at least 1.0% of zone area)
            if h_best is not None and hand_raw:
                zone_px = float((hy2 - hy1) * (hx2 - hx1))
                if cv2.contourArea(h_best) < (zone_px * 0.010):
                    hand_raw = False

            # ── CAMERA SHAKE SUPPRESSION ──
            if self.camera_shake_detected:
                hand_raw = False
                person_present = False

            # ── STRICT DIRECTION FILTER ──
            # 1. If motion is from the Chairman side -> suppress completely!
            if dir_from_presenter and hand_raw:
                hand_raw = False

            # 2. Motion MUST be on the graduate's half to count as a handover
            if self.exclude_enabled and not dir_from_graduate and hand_raw:
                hand_raw = False

            # 3. If Chairman zone is active, suppress unless clearly from graduate
            if presenter_active and not dir_from_graduate and hand_raw:
                hand_raw = False

            # Centroid suppression
            hand_point = None
            if h_best is not None and hand_raw:
                M = cv2.moments(h_best)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"]) + hx1
                    cy_abs = int(M["m01"] / M["m00"]) + hy1
                    if self.exclude_enabled:
                        ex1 = int(self.roi_exclude["x_min"] * w)
                        ey1 = int(self.roi_exclude["y_min"] * h)
                        ex2 = int(self.roi_exclude["x_max"] * w)
                        ey2 = int(self.roi_exclude["y_max"] * h)
                        if ex1 <= cx <= ex2 and ey1 <= cy_abs <= ey2:
                            hand_raw = False
                    if hand_raw:
                        hand_point = (cx, cy_abs)

            if hand_raw:
                self._hand_confirm_frames += 1
                self._hand_absent_frames   = 0
            else:
                self._hand_absent_frames  += 1
                self._hand_confirm_frames  = 0

            # If camera shook, reset any partial dwell counter so it doesn't trigger falsely
            if self.camera_shake_detected:
                self._hand_confirm_frames = 0
                if self.state == "HAND_DWELL":
                    self.state = "IDLE"

            hand_entered  = self._hand_confirm_frames >= self.CONFIRM_FRAMES_NEEDED
            # "เดินออก" / ดึงมือออก: เมื่อมือไม่อยู่ในจุดรับแล้วอย่างน้อย 2 เฟรม
            hand_departed = self._hand_absent_frames >= self.ABSENT_FRAMES_RESET

            if in_cooldown:
                self.state = "COOLDOWN"
            elif self.state == "COOLDOWN":
                self.state = "IDLE"
            else:
                require_person = (self.detection_mode in ("hand_priority", "dual"))
                if self.state == "IDLE":
                    # จังหวะที่ 1: บัณฑิตยื่นมือเข้ามารับ -> เข้าสู่สถานะ HAND_DWELL (ยังไม่นับ! รอนับตอนเดินออก)
                    if hand_entered and ((not require_person) or person_present):
                        self.state        = "HAND_DWELL"
                        self.confirmed_ts = now
                elif self.state == "HAND_DWELL":
                    # จังหวะที่ 2: นับเมื่อ "เดินออก" (มือดึงออก / ก้าวออกจากจุดรับ)
                    dwell_time = now - self.confirmed_ts
                    # ป้องกันการนับ noise ชั่ววูบ: ต้องรับอย่างน้อย 0.2 วินาที
                    if dwell_time >= 0.20:
                        # นับเมื่อเดินออก (hand_departed) หรือถ้าบัณฑิตค้างเกิน 1.8 วินาที
                        if hand_departed or dwell_time >= 1.8:
                            triggered = True
                            self.last_trigger_ts = self.last_trigger_timestamp = now
                            self.state = "COOLDOWN"
                            self._hand_confirm_frames = 0
                            self._hand_absent_frames  = 0
                            if self.on_graduate_received:
                                self.on_graduate_received()

            if hand_point:
                cv2.circle(frame, hand_point, 12, (0, 255, 255), 2)
                cv2.circle(frame, hand_point,  5, (0,   0, 255), -1)

        # ─────────────────────────────────────────────────────────────────
        # TRIPWIRE MODE
        # ─────────────────────────────────────────────────────────────────
        elif self.detection_mode == "tripwire":
            if in_cooldown:
                self.state = "COOLDOWN"
            elif self.state == "COOLDOWN":
                self.state = "IDLE"
            elif person_present and self.state == "IDLE":
                self.state = "HAND_DWELL"
            elif not person_present and self.state == "HAND_DWELL":
                triggered = True
                self.last_trigger_ts = self.last_trigger_timestamp = now
                self.state = "COOLDOWN"
                if self.on_graduate_received:
                    self.on_graduate_received()
            elif not person_present:
                self.state = "IDLE"

        # ─────────────────────────────────────────────────────────────────
        # ARM-RAISE MODE
        # ─────────────────────────────────────────────────────────────────
        elif self.detection_mode == "arm_raise":
            smoothed_cy = None
            if p_cy is not None and person_present:
                self._centroid_y_buf.append(p_cy)
                smoothed_cy = sum(self._centroid_y_buf) / len(self._centroid_y_buf)
            else:
                self._centroid_y_buf.clear()

            arm_is_up   = (smoothed_cy is not None) and (smoothed_cy < self.ARM_UP_RATIO)
            arm_is_down = (smoothed_cy is None) or (smoothed_cy > self.ARM_DOWN_RATIO)

            if arm_is_up:
                self._arm_up_frames   += 1
                self._arm_down_frames  = 0
                if smoothed_cy < self._arm_peak_y_ratio:
                    self._arm_peak_y_ratio = smoothed_cy
            elif arm_is_down:
                self._arm_down_frames += 1
                self._arm_up_frames    = 0
            else:
                self._arm_down_frames = 0

            arm_up_confirmed   = self._arm_up_frames   >= self.ARM_UP_FRAMES
            arm_down_confirmed = self._arm_down_frames >= 2

            if in_cooldown:
                self.state = "COOLDOWN"
            elif self.state == "COOLDOWN":
                self.state = "IDLE"
                self._arm_up_frames = 0; self._arm_down_frames = 0
                self._arm_peak_y_ratio = 1.0; self._centroid_y_buf.clear()
            elif self.state == "IDLE":
                if arm_up_confirmed:
                    self.state = "ARM_UP"; self.confirmed_ts = now
                    self._arm_peak_y_ratio = smoothed_cy
            elif self.state == "ARM_UP":
                dwell = now - self.confirmed_ts
                if arm_down_confirmed or dwell >= 1.5:
                    triggered = True
                    self.last_trigger_ts = self.last_trigger_timestamp = now
                    self.state = "COOLDOWN"
                    self._arm_up_frames = 0; self._arm_down_frames = 0
                    self._arm_peak_y_ratio = 1.0; self._centroid_y_buf.clear()
                    if self.on_graduate_received:
                        self.on_graduate_received()
                elif arm_is_up:
                    if smoothed_cy < self._arm_peak_y_ratio:
                        self._arm_peak_y_ratio = smoothed_cy

        # ── Draw feedback ─────────────────────────────────────────────────

        # Person zone
        p_color = (200, 100, 255) if person_present else (100, 60, 130)
        cv2.rectangle(frame, (px1, py1), (px2, py2), p_color, 2)
        cv2.rectangle(frame, (px1, max(0, py1 - 22)), (px1 + 200, py1), (20, 15, 30), -1)
        cv2.putText(frame, "1. คน: ตรวจพบ" if person_present else "1. คน: รอ...",
                    (px1 + 4, py1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, p_color, 1)

        # Hand zone state display
        state_colors = {
            "COOLDOWN":   (80,  80,  80),
            "ARM_UP":     (0,   215, 255),
            "HAND_DWELL": (0,   215, 255),
            "IDLE":       (0,   160, 255),
        }
        state_labels = {
            "COOLDOWN":   "COOLDOWN (นับแล้ว/รอคนถัดไป...)",
            "ARM_UP":     f"แขนยก! [{self._arm_up_frames}f]",
            "HAND_DWELL": f"มือ: กำลังรับ (รอนับตอนเดินออก) [{self._hand_confirm_frames}f]",
            "IDLE":       "2. มือ: รอ...",
        }
        # Hand zone label with direction indicator
        dir_suffix = ""
        if dir_from_presenter:
            dir_suffix = " [🚫 ทิศประธาน]"
        elif dir_from_graduate:
            dir_suffix = " [✅ ทิศบัณฑิต]"

        h_color = state_colors.get(self.state, (0, 160, 255))
        h_label = state_labels.get(self.state, "2. มือ: รอ...") + dir_suffix

        cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), h_color, 2)
        overlay = frame.copy()
        cv2.rectangle(overlay, (hx1, hy1), (hx2, hy2), h_color, -1)
        cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
        cv2.rectangle(frame, (hx1, max(0, hy1 - 22)), (hx1 + 300, hy1), (20, 20, 20), -1)
        cv2.putText(frame, h_label, (hx1 + 4, hy1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, h_color, 1)

        # Draw motion direction arrow inside the hand zone
        if abs(h_vx) > 0.20 or abs(h_vy) > 0.20:
            center_x = (hx1 + hx2) // 2
            center_y = (hy1 + hy2) // 2
            scale = 14.0
            end_x = int(center_x + np.clip(h_vx * scale, -45, 45))
            end_y = int(center_y + np.clip(h_vy * scale, -45, 45))
            arrow_color = (60, 60, 240) if dir_from_presenter else ((50, 220, 80) if dir_from_graduate else (0, 215, 255))
            cv2.arrowedLine(frame, (center_x, center_y), (end_x, end_y), arrow_color, 2, tipLength=0.35)

        # Debug overlay
        dir_stat = "BLOCK" if dir_from_presenter else ("OK" if dir_from_graduate else "--")
        cv2.putText(frame,
                    f"H MOG:{h_mog:.3f} Diff:{h_diff:.3f} Dir:{dir_proj:+.2f}({dir_stat}) Conf:{self._hand_confirm_frames} Excl:{excl_motion:.3f}({'BLOCK' if presenter_active else 'ok'})",
                    (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (200, 200, 200), 1)
        cv2.putText(frame,
                    f"P MOG:{p_mog:.3f} Diff:{p_diff:.3f} State:{self.state} Mode:{self.detection_mode}",
                    (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (180, 180, 180), 1)

        if getattr(self, "camera_shake_detected", False):
            cv2.rectangle(frame, (6, 44), (280, 68), (0, 0, 180), -1)
            cv2.putText(frame, "🛡️ ANTI-SHAKE: JITTER FILTERED", (10, 61),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

        # Exclusion zone
        if self.exclude_enabled:
            ex1 = max(0, int(self.roi_exclude["x_min"] * w))
            ey1 = max(0, int(self.roi_exclude["y_min"] * h))
            ex2 = max(0, int(self.roi_exclude["x_max"] * w))
            ey2 = max(0, int(self.roi_exclude["y_max"] * h))
            ex_color = (60, 60, 240)
            cv2.rectangle(frame, (ex1, ey1), (ex2, ey2), ex_color, 2)
            cv2.rectangle(frame, (ex1, max(0, ey1 - 22)), (ex1 + 245, ey1), (25, 20, 60), -1)
            cv2.putText(frame, f"3. ท่านประธาน (excl:{excl_motion:.2f})", (ex1 + 4, ey1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, ex_color, 1)

        return frame, triggered
