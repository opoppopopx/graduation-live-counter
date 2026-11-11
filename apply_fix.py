# -*- coding: utf-8 -*-
"""
Apply responsive cross-browser layout & font enlargement to static/stage.html
Solves:
1. Layout overlap / scattering in other browsers (Firefox, Edge, Safari, OBS).
2. Enlarges all fonts and numbers significantly for auditorium/projector display.
3. Adds robust media queries for short/small screens so it never overflows or collides.
"""
import re

target_file = r'c:\Users\ACER\.gemini\antigravity-ide\scratch\graduation-live-counter\static\stage.html'

with open(target_file, 'r', encoding='utf-8') as f:
    html = f.read()

# New perfected CSS
new_css = """
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        :root {
            --bg-color: #0B1120;
            --card-bg: #FFFFFF;
            --text-dark: #1E293B;
            --green-primary: #059669;
            --green-light: #DEF7EC;
            --green-text: #03543F;
            --red-primary: #C81E1E;
            --red-light: #FDE8E8;
            --blue-primary: #0284C7;
            --yellow-badge: #F59E0B;
        }

        /* ธีมม่วง-ราชภัฏบุรีรัมย์ (BRU Orchid Purple & White) */
        body.theme-purple-yellow {
            --bg-color: #F6EEF8;
            background: #F6EEF8 !important;
            color: #2A122D !important;
        }

        body.theme-purple-yellow .top-banner {
            background: #FFFFFF !important;
            border-top: 6px solid #8E3890 !important;
            border-bottom: 2px solid #F59E0B !important;
            box-shadow: 0 6px 20px rgba(142, 56, 144, 0.15) !important;
        }

        body.theme-purple-yellow .ceremony-main-title {
            color: #6E2271 !important;
        }

        body.theme-purple-yellow .hero-card {
            background: #FFFFFF !important;
            border: 2px solid rgba(142, 56, 144, 0.22) !important;
            box-shadow: 0 8px 24px rgba(142, 56, 144, 0.08) !important;
        }

        body.theme-purple-yellow .hero-card:first-child {
            border-top: 6px solid #059669 !important;
        }

        body.theme-purple-yellow .hero-card:last-child {
            border-top: 6px solid #F59E0B !important;
        }

        body.theme-purple-yellow .hero-card:last-child .hero-num {
            color: #D97706 !important;
        }

        body.theme-purple-yellow .break-track-container {
            border-top: 2px solid rgba(142, 56, 144, 0.25) !important;
        }

        body.theme-purple-yellow #pill-mode {
            background: linear-gradient(135deg, #8E3890, #6E2271) !important;
            border: 1px solid rgba(245, 158, 11, 0.5) !important;
        }

        body {
            background-color: var(--bg-color);
            font-family: 'Kanit', 'Sarabun', sans-serif;
            color: var(--text-dark);
            height: 100vh;
            width: 100vw;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 10px 22px 8px 22px;
            user-select: none;
            transition: all 0.2s ease;
        }

        /* 1. Top Header Banner */
        .top-banner {
            background: var(--card-bg);
            border-radius: 18px;
            padding: 8px 24px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            position: relative;
            flex-shrink: 0;
        }

        .ceremony-main-title {
            font-size: clamp(32px, 3.4vw, 52px);
            font-weight: 900;
            color: #0F172A;
            letter-spacing: 0.5px;
            line-height: 1.12;
        }

        .ceremony-sub-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: clamp(8px, 1.3vw, 22px);
            font-size: clamp(14px, 1.3vw, 22px);
            font-weight: 700;
            flex-wrap: nowrap;
            white-space: nowrap;
            max-width: 100%;
            overflow: hidden;
        }

        .sub-item {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }

        .sub-item.green { color: #059669; }
        .sub-item.red { color: #DC2626; }
        .sub-item.dark { color: #334155; }
        .sub-item.blue { color: #0284C7; }

        .divider {
            color: #CBD5E1;
            font-weight: 400;
            font-size: 16px;
            padding: 0 2px;
        }

        /* Real-time Break Batches Strip */
        .break-progress-strip {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 6px 20px;
            box-shadow: 0 5px 18px rgba(0, 0, 0, 0.28);
            margin-top: 6px;
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 14px;
            align-items: center;
            flex-shrink: 0;
        }

        .break-col {
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 0;
        }

        .break-col-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 8px;
            white-space: nowrap;
            overflow: hidden;
        }

        .break-tag {
            font-size: clamp(14px, 1.25vw, 20px);
            font-weight: 800;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }

        .break-tag.tag-green { color: #059669; }
        .break-tag.tag-red { color: #DC2626; }

        .break-stat-text {
            font-size: clamp(13px, 1.2vw, 19px);
            color: #334155;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .break-track-bar {
            height: 14px;
            background: #E2E8F0;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .break-fill-bar {
            height: 100%;
            border-radius: 10px;
            transition: width 0.35s ease-out;
        }

        .fill-green {
            background: linear-gradient(90deg, #34D399, #059669);
        }

        .fill-red {
            background: linear-gradient(90deg, #F87171, #DC2626);
        }

        .break-checkpoint-pill {
            background: #F8FAFC;
            border: 2px dashed #94A3B8;
            padding: 5px 12px;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 800;
            color: #475569;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-width: 82px;
            text-align: center;
            transition: all 0.3s;
            flex-shrink: 0;
        }

        .break-checkpoint-pill.active {
            background: #FEF3C7;
            border-color: #F59E0B;
            color: #B45309;
            box-shadow: 0 0 16px rgba(245, 158, 11, 0.6);
            transform: scale(1.05);
        }

        /* 2. Main 2 Hero KPI Cards (Left: Conferred, Right: Remaining) */
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: minmax(0, 1fr); /* CRITICAL for Firefox, Edge & WebKit */
            gap: 16px;
            flex: 1 1 0%;
            margin: 8px 0;
            min-height: 0;
            min-width: 0;
        }

        .hero-card {
            background: var(--card-bg);
            border-radius: 24px;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            position: relative;
            padding: 14px 24px 12px 24px;
            min-height: 0;
            min-width: 0;
        }

        .hero-header {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            font-size: clamp(26px, 2.7vw, 42px);
            font-weight: 800;
            flex-shrink: 0;
            white-space: nowrap;
        }

        .hero-card.left .hero-header {
            color: var(--green-primary);
        }

        .hero-card.right .hero-header {
            color: var(--red-primary);
        }

        .hero-num-box {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1 1 0%;
            min-height: 0;
            min-width: 0;
            overflow: hidden;
        }

        .hero-num {
            font-family: 'Outfit', 'Kanit', sans-serif;
            font-size: clamp(75px, min(30vh, 22vw), 260px);
            font-weight: 900;
            line-height: 0.88;
            letter-spacing: -2px;
            text-align: center;
            white-space: nowrap;
            transition: transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .hero-card.left .hero-num {
            color: #059669;
        }

        .hero-card.right .hero-num {
            color: #C81E1E;
        }

        .hero-footer-bar {
            border-radius: 12px;
            padding: 6px 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            font-size: clamp(16px, 1.6vw, 26px);
            font-weight: 800;
            flex-shrink: 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .hero-card.left .hero-footer-bar {
            background: var(--green-light);
            color: var(--green-text);
        }

        .hero-card.right .hero-footer-bar {
            background: var(--red-light);
            color: #991B1B;
        }

        /* 3. Bottom 3 Small KPI Cards */
        .bottom-grid {
            display: grid;
            grid-template-columns: 1fr 1.35fr 1fr;
            gap: 14px;
            margin-bottom: 6px;
            flex-shrink: 0; /* CRITICAL: Never overlap hero cards */
        }

        .bottom-card {
            background: var(--card-bg);
            border-radius: 16px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
            padding: 8px 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2px;
            text-align: center;
            min-width: 0;
        }

        .bottom-card-title {
            font-size: clamp(14px, 1.35vw, 22px);
            font-weight: 700;
            color: #475569;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }

        .bottom-card-val {
            font-family: 'Outfit', 'Kanit', sans-serif;
            font-size: clamp(34px, 3.8vw, 58px);
            font-weight: 900;
            line-height: 1.05;
            white-space: nowrap;
        }

        .bottom-card-sub {
            font-size: clamp(13px, 1.2vw, 18px);
            font-weight: 700;
            white-space: nowrap;
        }

        /* 🌟 EXTRA-LARGE AUDIENCE CINEMA MODE (ขยายตัวหนังสือและตัวเลขใหญ่พิเศษ สำหรับหอประชุม) */
        body.text-xl .ceremony-main-title {
            font-size: clamp(36px, 4vw, 62px) !important;
        }
        body.text-xl .ceremony-sub-row {
            font-size: clamp(16px, 1.55vw, 25px) !important;
        }
        body.text-xl .break-tag {
            font-size: clamp(16px, 1.45vw, 23px) !important;
        }
        body.text-xl .break-stat-text {
            font-size: clamp(15px, 1.35vw, 22px) !important;
        }
        body.text-xl .hero-header {
            font-size: clamp(32px, 3.2vw, 48px) !important;
        }
        body.text-xl .hero-num {
            font-size: clamp(85px, min(34vh, 24vw), 290px) !important;
            line-height: 0.85 !important;
        }
        body.text-xl .hero-footer-bar {
            font-size: clamp(18px, 1.9vw, 30px) !important;
        }
        body.text-xl .bottom-card-title {
            font-size: clamp(16px, 1.55vw, 24px) !important;
        }
        body.text-xl .bottom-card-val {
            font-size: clamp(38px, 4.4vw, 68px) !important;
        }

        .btn-toggle-font {
            background: rgba(255, 255, 255, 0.15);
            color: #CBD5E1;
            border: 1px solid rgba(255, 255, 255, 0.25);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            backdrop-filter: blur(4px);
            transition: all 0.2s;
            margin-right: 8px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-toggle-font:hover {
            background: rgba(245, 158, 11, 0.25);
            border-color: #F59E0B;
            color: #FDE68A;
        }

        .val-clock {
            color: #E02424; /* Red clock */
        }

        .val-eta {
            color: #0284C7; /* Blue ETA */
        }

        .val-rate {
            color: #2563EB; /* Royal Blue rate */
        }

        /* 4. Bottom Status Pills */
        .status-bar-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            position: relative;
            flex-shrink: 0;
            min-height: 32px;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 16px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            transition: all 0.25s ease;
            white-space: nowrap;
        }

        .pill-pause {
            background: #F59E0B;
            color: #000000;
        }

        .pill-pause.active {
            background: #EF4444;
            color: #FFFFFF;
            animation: pulse-pause 1.2s infinite;
        }

        @keyframes pulse-pause {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { transform: scale(1.05); box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        .pill-mode {
            background: #0284C7;
            color: #FFFFFF;
        }

        .btn-fullscreen {
            position: absolute;
            right: 0;
            background: rgba(255, 255, 255, 0.15);
            color: #CBD5E1;
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            backdrop-filter: blur(4px);
            transition: all 0.2s;
        }

        .btn-fullscreen:hover {
            background: rgba(255, 255, 255, 0.3);
            color: #fff;
        }

        .btn-back-admin {
            position: absolute;
            left: 0;
            color: #64748B;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: color 0.2s;
        }

        .btn-back-admin:hover {
            color: #94A3B8;
        }

        /* Number pulse animation on confer */
        .bump-anim {
            animation: bump 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        @keyframes bump {
            0% { transform: scale(1); }
            50% { transform: scale(1.08); }
            100% { transform: scale(1); }
        }

        /* Offline overlay warning */
        #offline-alert {
            display: none;
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #EF4444;
            color: #fff;
            padding: 8px 20px;
            border-radius: 30px;
            font-size: 14px;
            font-weight: 700;
            box-shadow: 0 8px 24px rgba(239, 68, 68, 0.5);
            z-index: 999;
        }

        /* 📱 RESPONSIVE ADAPTATIONS: ป้องกันการทับซ้อนเมื่อจอเตี้ย หรือเปิดในเบราว์เซอร์ที่มีแท็บ/แถบเครื่องมือเยอะ */
        @media (max-height: 650px) {
            body {
                padding: 4px 14px 4px 14px;
            }
            .top-banner {
                padding: 4px 16px;
                gap: 2px;
                border-radius: 12px;
            }
            .top-banner img {
                height: 38px !important;
            }
            .ceremony-main-title {
                font-size: clamp(24px, 2.8vw, 34px) !important;
            }
            .ceremony-sub-row {
                font-size: clamp(12px, 1.1vw, 15px) !important;
                gap: 8px;
            }
            .break-progress-strip {
                padding: 4px 14px;
                margin-top: 3px;
                gap: 8px;
                border-radius: 12px;
            }
            .break-track-bar {
                height: 8px;
            }
            .break-checkpoint-pill {
                padding: 2px 8px;
                min-width: 60px;
                font-size: 11px;
            }
            .hero-grid {
                gap: 10px;
                margin: 4px 0;
            }
            .hero-card {
                padding: 6px 14px 5px 14px;
                border-radius: 14px;
            }
            .hero-header {
                font-size: clamp(20px, 2.4vw, 28px) !important;
            }
            .hero-num {
                font-size: clamp(65px, 25vh, 160px) !important;
                line-height: 0.9 !important;
            }
            body.text-xl .hero-num {
                font-size: clamp(75px, 27vh, 175px) !important;
            }
            .hero-footer-bar {
                padding: 3px 10px;
                font-size: clamp(12px, 1.2vw, 16px) !important;
                border-radius: 8px;
            }
            .bottom-grid {
                gap: 8px;
                margin-bottom: 3px;
            }
            .bottom-card {
                padding: 4px 10px;
                border-radius: 12px;
            }
            .bottom-card-title {
                font-size: clamp(12px, 1.2vw, 15px) !important;
            }
            .bottom-card-val {
                font-size: clamp(24px, 3.2vw, 38px) !important;
            }
            body.text-xl .bottom-card-val {
                font-size: clamp(26px, 3.5vw, 42px) !important;
            }
            .bottom-card-sub {
                font-size: 11px !important;
            }
            .status-bar-row {
                gap: 8px;
                min-height: 26px;
            }
            .status-pill {
                padding: 2px 10px;
                font-size: 11px;
            }
            .btn-toggle-font, .btn-fullscreen, .btn-back-admin {
                font-size: 11px;
                padding: 3px 8px;
            }
        }

        @media (max-width: 1000px) {
            .ceremony-sub-row {
                font-size: 12px !important;
                gap: 6px;
            }
            .break-stat-text {
                font-size: 12px !important;
            }
        }
"""

# Replace style block
pattern = r'<style>[\s\S]*?</style>'
html = re.sub(pattern, f'<style>{new_css}\n    </style>', html, count=1)

# Ensure #eta-sub and #cadence-sub have class bottom-card-sub
html = html.replace('id="eta-sub"', 'id="eta-sub" class="bottom-card-sub"')
html = html.replace('id="cadence-sub"', 'id="cadence-sub" class="bottom-card-sub"')

with open(target_file, 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: Updated stage.html with perfected cross-browser responsive layout & extra-large font scaling!")
