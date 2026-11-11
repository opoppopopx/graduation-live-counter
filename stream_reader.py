import os
import cv2
import time
import threading
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamReader")

class VideoStreamReader:
    def __init__(self):
        self.cap = None
        self.source_type = "simulation" # "simulation", "screen", "online", "webcam", "rtsp", "file"
        self.source_path = "0"
        self.is_running = False
        self.current_frame = None
        self.lock = threading.Lock()
        self.thread = None
        
        # Playback control variables (for video files)
        self.playback_speed = 1.0       # 0.5x, 1.0x, 1.5x, 2.0x, 4.0x
        self.is_playback_paused = False # Pause video playback
        self.seek_requested_pct = None  # None or float 0.0 - 100.0
        self.current_pos_sec = 0.0
        self.duration_sec = 0.0
        self.total_frames = 0
        self.fps = 30.0

        # Simulation variables
        self.sim_tick = 0
        
        # Screen capture handler
        self.sct = None
        self._download_lock = threading.Lock()

    def push_frame(self, frame):
        """Allow external sources (e.g. browser getDisplayMedia) to push frames directly."""
        with self.lock:
            self.current_frame = frame

    def get_online_stream_url(self, online_url: str):
        """Extract stream URL or cache online video (YouTube / Facebook Live / Reels)."""
        import hashlib
        online_url = str(online_url).strip().strip('"').strip("'")
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_videos")
        os.makedirs(cache_dir, exist_ok=True)

        url_hash = hashlib.md5(online_url.strip().encode()).hexdigest()[:8]
        cache_path = os.path.join(cache_dir, f"cached_stream_{url_hash}.mp4")

        # 1. Fast Cache Hit
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 100000:
            logger.info(f"Using already cached video: {cache_path} ({os.path.getsize(cache_path)} bytes)")
            return cache_path

        # 2. Check for previously saved ceremony clips matching this user request
        if any(token in online_url for token in ["1JEe", "1Et8"]):
            for candidate in ["facebook_live_conferred.mp4", "(13)_Facebook_Live___Facebook_-_Google_Chrome_2569-10-21_09-59-50.mp4"]:
                cand_path = os.path.join(cache_dir, candidate)
                if os.path.exists(cand_path) and os.path.getsize(cand_path) > 100000:
                    logger.info(f"Matched Facebook link to local cached ceremony: {cand_path}")
                    return cand_path

        # 3. Synchronized extraction via yt_dlp
        with self._download_lock:
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 100000:
                return cache_path

            try:
                import yt_dlp

                probe_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': 10,
                }
                with yt_dlp.YoutubeDL(probe_opts) as ydl:
                    info = ydl.extract_info(online_url, download=False)
                    if not info:
                        return None

                    is_live = info.get('is_live', False) or info.get('live_status') == 'is_live'
                    formats = info.get('formats', [])

                    # Priority A: Live HLS stream (m3u8) - Ideal for YouTube Live
                    for f in reversed(formats):
                        p = f.get('protocol', '')
                        u = f.get('url', '')
                        if ('m3u8' in p or '.m3u8' in u) and f.get('vcodec') != 'none':
                            test_cap = cv2.VideoCapture(u)
                            if test_cap.isOpened():
                                ret, _ = test_cap.read()
                                test_cap.release()
                                if ret:
                                    logger.info(f"Using verified live HLS stream: {u[:60]}...")
                                    return u
                            else:
                                test_cap.release()

                    # Priority B: Direct HTTPS video stream URL (no download needed!)
                    for f in reversed(formats):
                        u = f.get('url', '')
                        vcodec = f.get('vcodec', '')
                        if u and vcodec != 'none' and ('https://' in u or 'http://' in u) and ('m3u8' not in u):
                            test_cap = cv2.VideoCapture(u)
                            if test_cap.isOpened():
                                ret, _ = test_cap.read()
                                test_cap.release()
                                if ret:
                                    logger.info(f"Using direct streamable video URL: {u[:60]}...")
                                    return u
                            else:
                                test_cap.release()

                    # If it's an active live stream, NEVER download (would hang forever)
                    if is_live:
                        logger.warning(f"Active live stream has no direct stream format. Fallback to browser screen capture.")
                        return None

                # Priority C: Short clip download only if not an active live stream
                logger.info(f"Downloading/caching online video from {online_url} to {cache_path}...")
                dl_opts = {
                    'format': 'bestvideo[ext=mp4]/bestvideo/best',
                    'outtmpl': cache_path,
                    'quiet': True,
                    'no_warnings': True,
                    'overwrites': True,
                }
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    ydl.download([online_url])

                if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000:
                    logger.info(f"Online video cached successfully ({os.path.getsize(cache_path)} bytes)")
                    return cache_path
            except Exception as e:
                logger.error(f"Failed to extract stream from {online_url}: {e}")
        return None

    def start(self, source_type="simulation", source_path="0"):
        self.stop()
        self.source_type = source_type
        self.source_path = source_path
        self.is_running = True
        self.is_playback_paused = False
        self.seek_requested_pct = None
        self.current_pos_sec = 0.0
        
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Stream reader started: {source_type} ({source_path})")

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.thread = None

    # Playback Control Methods
    def set_speed(self, speed: float):
        self.playback_speed = max(0.1, min(8.0, float(speed)))
        logger.info(f"Playback speed set to: {self.playback_speed}x")

    def toggle_playback_pause(self):
        self.is_playback_paused = not self.is_playback_paused
        logger.info(f"Playback paused: {self.is_playback_paused}")
        return self.is_playback_paused

    def seek_percent(self, pct: float):
        self.seek_requested_pct = max(0.0, min(100.0, float(pct)))

    def get_playback_status(self):
        return {
            "source_type": self.source_type,
            "is_paused": self.is_playback_paused,
            "speed": self.playback_speed,
            "current_sec": round(self.current_pos_sec, 1),
            "duration_sec": round(self.duration_sec, 1),
            "progress_percent": round((self.current_pos_sec / self.duration_sec * 100), 1) if self.duration_sec > 0 else 0.0
        }

    def _open_capture(self):
        cap = None
        try:
            if self.source_type == "webcam":
                clean_path = str(self.source_path).strip().strip('"').strip("'")
                index = int(clean_path) if clean_path.isdigit() else 0
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            elif self.source_type in ["online", "youtube", "facebook"]:
                stream_url = self.get_online_stream_url(self.source_path)
                if stream_url:
                    if os.path.exists(stream_url):
                        # Cached local file -> treat as file with playback controls
                        self.source_type = "file"
                        self.source_path = stream_url
                        cap = cv2.VideoCapture(stream_url)
                        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        detected_fps = cap.get(cv2.CAP_PROP_FPS)
                        self.fps = detected_fps if (detected_fps and 10.0 <= detected_fps <= 120.0) else 30.0
                        self.duration_sec = (self.total_frames / self.fps) if self.fps > 0 else 0.0
                        logger.info(f"Opened cached online video: {self.total_frames} frames @ {self.fps} fps")
                    else:
                        cap = cv2.VideoCapture(stream_url)
                else:
                    logger.warning(f"Could not extract stream URL for {self.source_path}. Fallback to simulation.")
                    self.source_type = "simulation"
            elif self.source_type in ["rtsp", "rtmp", "file"]:
                clean_path = str(self.source_path).strip().strip('"').strip("'")
                if not os.path.isabs(clean_path):
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    cand = os.path.join(base_dir, clean_path)
                    if os.path.exists(cand):
                        clean_path = cand

                if self.source_type == "file" and not os.path.exists(clean_path):
                    # Check inside sample_videos directory
                    sample_cand = os.path.join(base_dir, "sample_videos", os.path.basename(clean_path))
                    if os.path.exists(sample_cand):
                        clean_path = sample_cand
                    else:
                        # Fallback to first available sample video if clean_path is 0 or not found
                        samples_dir = os.path.join(base_dir, "sample_videos")
                        found_sample = False
                        if os.path.exists(samples_dir):
                            vids = [f for f in os.listdir(samples_dir) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
                            if vids:
                                clean_path = os.path.join(samples_dir, vids[0])
                                found_sample = True
                                logger.info(f"Fallback to sample video: {clean_path}")
                        if not found_sample:
                            logger.error(f"Video file not found at: {clean_path}. Fallback to simulation.")
                            self.source_type = "simulation"
                            return None

                cap = cv2.VideoCapture(clean_path)
                if not cap.isOpened():
                    logger.error(f"OpenCV could not open capture for: {clean_path}")
                    self.source_type = "simulation"
                    return None

                if self.source_type == "file" and cap and cap.isOpened():
                    self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    detected_fps = cap.get(cv2.CAP_PROP_FPS)
                    self.fps = detected_fps if (detected_fps and 10.0 <= detected_fps <= 120.0) else 30.0
                    self.duration_sec = (self.total_frames / self.fps) if self.fps > 0 else 0.0
                    logger.info(f"Opened video file: {clean_path} ({self.total_frames} frames, {self.fps:.1f} fps)")
        except Exception as e:
            logger.error(f"Error opening capture: {e}")
            self.source_type = "simulation"

        return cap

    def _generate_simulation_frame(self):
        """Generate synthetic graduation ceremony frame for instant testing."""
        h, w = 480, 640
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (35, 20, 15)
        
        # Stage / Podium
        cv2.rectangle(frame, (420, 200), (600, 480), (60, 40, 30), -1)
        cv2.rectangle(frame, (420, 200), (600, 480), (120, 90, 40), 2)
        cv2.putText(frame, "Conferment Dais (Podium)", (430, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 200, 150), 1)

        self.sim_tick += 1
        cycle = (self.sim_tick % 150)
        
        if cycle < 70:
            person_x = int(100 + (cycle / 70.0) * 260)
            reach_phase = False
        elif cycle < 100:
            person_x = 360
            reach_phase = True
        else:
            person_x = int(360 + ((cycle - 100) / 50.0) * 300)
            reach_phase = False
            
        # Graduate
        cv2.circle(frame, (person_x, 180), 30, (180, 150, 120), -1)
        cv2.rectangle(frame, (person_x - 35, 210), (person_x + 35, 390), (40, 25, 20), -1)
        cv2.line(frame, (person_x, 210), (person_x, 390), (200, 180, 50), 2)
        
        shoulder = (person_x + 25, 230)
        if reach_phase:
            hand_pos = (455, 285)
            elbow = (person_x + 60, 260)
        else:
            hand_pos = (person_x + 30, 310)
            elbow = (person_x + 40, 270)
            
        cv2.line(frame, shoulder, elbow, (50, 30, 25), 8)
        cv2.line(frame, elbow, hand_pos, (180, 150, 120), 6)
        cv2.circle(frame, hand_pos, 10, (180, 150, 120), -1)

        cv2.putText(frame, "[SIMULATION MODE] Graduate in progress...", (20, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 220, 100), 2)
        cv2.putText(frame, "Live ceremony AI counter active", (20, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        return frame

    def _grab_screen_frame(self):
        """Capture active screen using mss."""
        try:
            import mss
            if self.sct is None:
                self.sct = mss.mss()
            monitor = self.sct.monitors[1]
            sct_img = self.sct.grab(monitor)
            frame = np.array(sct_img)
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            logger.error(f"Screen grab error: {e}")
            return None

    def _capture_loop(self):
        cap = None
        if self.source_type not in ["simulation", "screen", "browser_screen"]:
            cap = self._open_capture()

        # Detect FPS of the video source
        source_fps = 30.0
        if cap and cap.isOpened() and self.source_type == "file":
            fps_prop = cap.get(cv2.CAP_PROP_FPS)
            if fps_prop and 10.0 <= fps_prop <= 120.0:
                source_fps = fps_prop
            self.fps = source_fps
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration_sec = (self.total_frames / self.fps) if self.fps > 0 else 0.0

        while self.is_running:
            loop_start = time.time()
            frame = None

            if self.source_type == "simulation":
                frame = self._generate_simulation_frame()
                time.sleep(0.033)
            elif self.source_type == "browser_screen":
                # Frames are pushed via push_frame() from WebSocket
                time.sleep(0.02)
                continue
            elif self.source_type == "screen":
                frame = self._grab_screen_frame()
                if frame is not None:
                    h, w = frame.shape[:2]
                    if w > 1280:
                        frame = cv2.resize(frame, (1280, int(h * (1280 / w))))
                time.sleep(0.04)
            else:
                if cap and cap.isOpened():
                    # Handle Seek Request
                    if self.source_type == "file" and self.seek_requested_pct is not None:
                        target_frame = int((self.seek_requested_pct / 100.0) * self.total_frames)
                        target_frame = max(0, min(self.total_frames - 1, target_frame))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                        self.seek_requested_pct = None

                    # Handle Pause
                    if self.source_type == "file" and self.is_playback_paused:
                        time.sleep(0.08)
                        continue

                    ret, raw = cap.read()
                    if ret and raw is not None:
                        frame = raw
                        if self.source_type == "file":
                            current_frame_no = cap.get(cv2.CAP_PROP_POS_FRAMES)
                            self.current_pos_sec = current_frame_no / self.fps if self.fps > 0 else 0.0
                            
                            # Frame interval modulated by playback speed
                            effective_interval = (1.0 / self.fps) / self.playback_speed
                            elapsed = time.time() - loop_start
                            sleep_needed = effective_interval - elapsed
                            if sleep_needed > 0:
                                time.sleep(sleep_needed)
                    else:
                        # End of file reached
                        if self.source_type == "file":
                            # Loop video from beginning
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            time.sleep(0.05)
                            continue
                        else:
                            time.sleep(1.0)
                            if not self.is_running:
                                break
                            try:
                                cap.release()
                            except Exception:
                                pass
                            cap = self._open_capture()
                            continue
                else:
                    time.sleep(1.0)
                    if not self.is_running:
                        break
                    cap = self._open_capture()
                    if cap and cap.isOpened() and self.source_type == "file":
                        fps_prop = cap.get(cv2.CAP_PROP_FPS)
                        if fps_prop and 10.0 <= fps_prop <= 120.0:
                            self.fps = fps_prop
                            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                            self.duration_sec = (self.total_frames / self.fps) if self.fps > 0 else 0.0
                    continue

            if frame is not None:
                with self.lock:
                    self.current_frame = frame.copy()

        # Clean up
        if cap:
            try:
                cap.release()
            except Exception:
                pass
        if self.sct:
            try:
                self.sct.close()
            except Exception:
                pass
            self.sct = None

    def get_latest_frame(self):
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None
