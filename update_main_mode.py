import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update on_graduate_detected to guarantee auto mode only
old_cb = """def on_graduate_detected():
    \"\"\"Callback fired by AI detector when diploma handover completes.\"\"\"
    if analytics.is_paused:
        return"""

new_cb = """def on_graduate_detected():
    \"\"\"Callback fired by AI detector when diploma handover completes.\"\"\"
    if analytics.is_paused or getattr(analytics, 'counting_mode', 'auto') == 'manual':
        return"""

text = text.replace(old_cb, new_cb)

# 2. Add Mode API endpoints
mode_api_code = """class ModeConfig(BaseModel):
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

@app.post("/api/pause")"""

text = text.replace('@app.post("/api/pause")', mode_api_code)

# 3. Add /manual and /hand routes
html_routes = """@app.get("/manual", response_class=HTMLResponse)
@app.get("/hand", response_class=HTMLResponse)
def get_manual_page():
    manual_path = os.path.join(STATIC_DIR, "manual.html")
    if not os.path.exists(manual_path):
        return HTMLResponse("<h1>Manual Page Loading...</h1>", status_code=200)
    with open(manual_path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html", headers=NO_CACHE_HEADERS)

@app.get("/settings", response_class=HTMLResponse)"""

text = text.replace('@app.get("/settings", response_class=HTMLResponse)', html_routes)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("main.py updated successfully!")
