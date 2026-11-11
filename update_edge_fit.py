# -*- coding: utf-8 -*-
import re

target_file = r'c:\Users\ACER\.gemini\antigravity-ide\scratch\graduation-live-counter\static\stage.html'

with open(target_file, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update CSS
css_replacement = """
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
            border-top: 5px solid #8E3890 !important;
            border-bottom: 2px solid #F59E0B !important;
            box-shadow: 0 5px 18px rgba(142, 56, 144, 0.15) !important;
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
            padding: 8px 18px 6px 18px;
            user-select: none;
            transition: all 0.2s ease;
        }

        /* 1. Top Header Banner */
        .top-banner {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 6px 20px;
            box-shadow: 0 5px 16px rgba(0, 0, 0, 0.3);
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 3px;
            position: relative;
            flex-shrink: 0;
            width: 100%;
        }

        .ceremony-main-title {
            font-size: clamp(28px, 3.2vw, 48px);
            font-weight: 900;
            color: #0F172A;
            letter-spacing: 0.5px;
            line-height: 1.1;
        }

        .ceremony-sub-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: clamp(6px, 1.2vw, 16px);
            font-size: clamp(13px, 1.2vw, 18px);
            font-weight: 700;
            flex-wrap: wrap;
            width: 100%;
            padding: 0 4px;
        }

        .sub-item {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            white-space: nowrap;
        }

        .sub-item.green { color: #059669; }
        .sub-item.red { color: #DC2626; }
        .sub-item.dark { color: #334155; }
        .sub-item.blue { color: #0284C7; }

        .divider {
            color: #CBD5E1;
            font-weight: 400;
            font-size: 15px;
            padding: 0 1px;
        }

        /* Real-time Break Batches Strip */
        .break-progress-strip {
            background: var(--card-bg);
            border-radius: 14px;
            padding: 6px 18px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
            margin-top: 5px;
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 12px;
            align-items: center;
            flex-shrink: 0;
            width: 100%;
        }

        .break-col {
            display: flex;
            flex-direction: column;
            gap: 3px;
            min-width: 0;
        }

        .break-col-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }

        .break-tag {
            font-size: clamp(13px, 1.2vw, 18px);
            font-weight: 800;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            white-space: nowrap;
        }

        .break-tag.tag-green { color: #059669; }
        .break-tag.tag-red { color: #DC2626; }

        .break-stat-text {
            font-size: clamp(12px, 1.15vw, 17px);
            color: #334155;
            font-weight: 700;
            white-space: nowrap;
        }

        .break-track-bar {
            height: 12px;
            background: #E2E8F0;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }

        .break-fill-bar {
            height: 100%;
            border-radius: 8px;
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
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 12px;
            font-weight: 800;
            color: #475569;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-width: 76px;
            text-align: center;
            transition: all 0.3s;
            flex-shrink: 0;
        }

        .break-checkpoint-pill.active {
            background: #FEF3C7;
            border-color: #F59E0B;
            color: #B45309;
            box-shadow: 0 0 14px rgba(245, 158, 11, 0.6);
            transform: scale(1.05);
        }

        /* 2. Main 2 Hero KPI Cards (Left: Conferred, Right: Remaining) */
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr;
            gap: 14px;
            flex: 1 1 0%;
            margin: 6px 0;
            min-height: 0;
            min-width: 0;
        }

        .hero-card {
            background: var(--card-bg);
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            position: relative;
            padding: 10px 20px 8px 20px;
            min-height: 0;
            min-width: 0;
        }

        .hero-header {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 6px;
            font-size: clamp(22px, 2.4vw, 38px);
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
            padding: 2px 0;
        }

        .hero-num {
            font-family: 'Outfit', 'Kanit', sans-serif;
            font-weight: 900;
            line-height: 0.9;
            letter-spacing: -2px;
            text-align: center;
            white-space: nowrap;
            transition: transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            /* Font size is smoothly autosized by fitHeroNumbers() to exactly fill the card without overlapping */
            font-size: clamp(55px, 20vh, 260px);
        }

        .hero-card.left .hero-num {
            color: #059669;
        }

        .hero-card.right .hero-num {
            color: #C81E1E;
        }

        .hero-footer-bar {
            border-radius: 10px;
            padding: 5px 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            font-size: clamp(14px, 1.4vw, 22px);
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
            gap: 12px;
            margin-bottom: 4px;
            flex-shrink: 0;
        }

        .bottom-card {
            background: var(--card-bg);
            border-radius: 14px;
            box-shadow: 0 5px 16px rgba(0, 0, 0, 0.25);
            padding: 6px 14px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2px;
            text-align: center;
            min-width: 0;
        }

        .bottom-card-title {
            font-size: clamp(13px, 1.25vw, 19px);
            font-weight: 700;
            color: #475569;
            display: flex;
            align-items: center;
            gap: 5px;
            white-space: nowrap;
        }

        .bottom-card-val {
            font-family: 'Outfit', 'Kanit', sans-serif;
            font-size: clamp(28px, 3.4vw, 54px);
            font-weight: 900;
            line-height: 1.05;
            white-space: nowrap;
        }

        .bottom-card-sub {
            font-size: clamp(12px, 1.1vw, 16px);
            font-weight: 700;
            white-space: nowrap;
        }

        /* 🌟 EXTRA-LARGE AUDIENCE CINEMA MODE (ขยายใหญ่พิเศษ สำหรับหอประชุม) */
        body.text-xl .ceremony-main-title {
            font-size: clamp(32px, 3.8vw, 56px) !important;
        }
        body.text-xl .ceremony-sub-row {
            font-size: clamp(14px, 1.35vw, 22px) !important;
        }
        body.text-xl .break-tag {
            font-size: clamp(14px, 1.3vw, 20px) !important;
        }
        body.text-xl .break-stat-text {
            font-size: clamp(13px, 1.2vw, 18px) !important;
        }
        body.text-xl .hero-header {
            font-size: clamp(26px, 2.8vw, 44px) !important;
        }
        body.text-xl .hero-footer-bar {
            font-size: clamp(15px, 1.6vw, 26px) !important;
        }
        body.text-xl .bottom-card-title {
            font-size: clamp(14px, 1.35vw, 21px) !important;
        }
        body.text-xl .bottom-card-val {
            font-size: clamp(32px, 3.8vw, 62px) !important;
        }

        .btn-toggle-font {
            background: rgba(255, 255, 255, 0.15);
            color: #CBD5E1;
            border: 1px solid rgba(255, 255, 255, 0.25);
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            backdrop-filter: blur(4px);
            transition: all 0.2s;
            margin-right: 6px;
            display: inline-flex;
            align-items: center;
            gap: 5px;
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
            gap: 10px;
            position: relative;
            flex-shrink: 0;
            min-height: 28px;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
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
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 11px;
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
            font-size: 11px;
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
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            background: #EF4444;
            color: #fff;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
            z-index: 999;
        }

        /* Responsive adaptations for compact screens (e.g. non-fullscreen window, Edge/Chrome with tabs) */
        @media (max-height: 650px) {
            body {
                padding: 4px 12px 4px 12px;
            }
            .top-banner {
                padding: 4px 14px;
                gap: 2px;
                border-radius: 12px;
            }
            .top-banner img {
                height: 36px !important;
            }
            .ceremony-main-title {
                font-size: clamp(22px, 2.6vw, 32px) !important;
            }
            .ceremony-sub-row {
                font-size: clamp(11px, 1vw, 14px) !important;
                gap: 6px;
            }
            .break-progress-strip {
                padding: 3px 12px;
                margin-top: 3px;
                gap: 8px;
                border-radius: 10px;
            }
            .break-track-bar {
                height: 8px;
            }
            .break-checkpoint-pill {
                padding: 2px 6px;
                min-width: 58px;
                font-size: 11px;
            }
            .hero-grid {
                gap: 8px;
                margin: 3px 0;
            }
            .hero-card {
                padding: 5px 12px 5px 12px;
                border-radius: 12px;
            }
            .hero-header {
                font-size: clamp(18px, 2.2vw, 26px) !important;
            }
            .hero-footer-bar {
                padding: 2px 8px;
                font-size: clamp(11px, 1.1vw, 15px) !important;
                border-radius: 6px;
            }
            .bottom-grid {
                gap: 6px;
                margin-bottom: 2px;
            }
            .bottom-card {
                padding: 3px 8px;
                border-radius: 10px;
            }
            .bottom-card-title {
                font-size: clamp(11px, 1.1vw, 14px) !important;
            }
            .bottom-card-val {
                font-size: clamp(22px, 2.8vw, 34px) !important;
            }
            .bottom-card-sub {
                font-size: 10px !important;
            }
            .status-bar-row {
                gap: 6px;
                min-height: 24px;
            }
            .status-pill {
                padding: 2px 8px;
                font-size: 10px;
            }
            .btn-toggle-font, .btn-fullscreen, .btn-back-admin {
                font-size: 10px;
                padding: 2px 6px;
            }
        }
"""

html = re.sub(r'<style>[\s\S]*?</style>', f'<style>{css_replacement}\n    </style>', html, count=1)

# 2. Update ceremony sub-row HTML to be clean and never clip
clean_sub_row = """        <div class="ceremony-sub-row">
            <div class="sub-item green">
                <span>✅</span> ลำดับก่อนพัก: <span id="pre-break-range">1-887</span>
                <span id="pre-break-mini-badge" style="background: rgba(16,185,129,0.18); color:#059669; padding: 2px 8px; border-radius: 8px; font-size: 13px; font-weight: 800;">0/887</span>
            </div>
            <div class="divider">|</div>
            <div class="sub-item red">
                <span>⏰</span> ลำดับหลังพัก: <span id="post-break-range">888-1,383</span>
                <span id="post-break-mini-badge" style="background: rgba(239,68,68,0.14); color:#DC2626; padding: 2px 8px; border-radius: 8px; font-size: 13px; font-weight: 800;">รอเริ่ม</span>
            </div>
            <div class="divider">|</div>
            <div class="sub-item dark">
                <span>รอบการรับ:</span> <span id="session-name">รอบเช้า</span> <span id="session-time" style="color: #0284C7; font-weight: 800;">(08:30 - 11:45)</span>
            </div>
            <div class="divider">|</div>
            <div class="sub-item blue">
                <span>เป้าหมาย:</span> <span id="total-target-text" style="font-weight: 900;">1,383</span> คน
            </div>
        </div>"""

html = re.sub(r'<div class="ceremony-sub-row">[\s\S]*?</div>\s*</div>\s*<!-- Real-time Break Progress Banner -->', 
              f'{clean_sub_row}\n    </div>\n\n    <!-- Real-time Break Progress Banner -->', html, count=1)

# 3. Add fitHeroNumbers JavaScript and attach to resize & updates
fit_script = """
        // Dynamic Font Auto-Fit Sizer (Never overlaps or touches card header/footer)
        function fitHeroNumbers() {
            const ids = ['conferred-count', 'remaining-count'];
            const isXl = document.body.classList.contains('text-xl');
            ids.forEach(id => {
                const el = document.getElementById(id);
                if (!el || !el.parentElement) return;
                const box = el.parentElement;
                const boxH = box.clientHeight;
                const boxW = box.clientWidth;
                if (boxH <= 15 || boxW <= 15) return;

                // Target size is 84% in XL mode and 76% in Normal mode of available box height
                const ratio = isXl ? 0.84 : 0.74;
                let targetSize = Math.floor(boxH * ratio);

                // Prevent wide text (e.g. 2,499 or 10,000) from overflowing sideways
                const textLen = (el.textContent || '').trim().length;
                if (textLen > 0) {
                    const maxByWidth = Math.floor((boxW * 0.90) / (textLen * 0.58));
                    targetSize = Math.min(targetSize, maxByWidth);
                }

                // Bounds
                const minSize = 48;
                const maxSize = isXl ? 280 : 210;
                targetSize = Math.max(minSize, Math.min(maxSize, targetSize));

                el.style.fontSize = targetSize + 'px';
                el.style.lineHeight = '0.9';
            });
        }

        window.addEventListener('resize', () => {
            fitHeroNumbers();
        });
"""

# Insert fit_script right after setTextSize definition
html = html.replace('function toggleTextSize() {', f'{fit_script}\n\n        function toggleTextSize() {{')

# Call fitHeroNumbers inside setTextSize
html = html.replace("try { localStorage.setItem('stage_font_xl', isXl ? 'true' : 'false'); } catch(e) {}",
                    "try { localStorage.setItem('stage_font_xl', isXl ? 'true' : 'false'); } catch(e) {}\n            setTimeout(fitHeroNumbers, 30);")

# Call fitHeroNumbers at the end of updateStageUI
html = html.replace("modePill.style.background = '#0284C7';\n            }",
                    "modePill.style.background = '#0284C7';\n            }\n            fitHeroNumbers();")

# Call fitHeroNumbers after DOM load
html = html.replace("connectWS();", "connectWS();\n        setTimeout(fitHeroNumbers, 50);\n        setTimeout(fitHeroNumbers, 300);")

# Also simplify verbose preMini / postMini in updateStageUI
html = html.replace("preMini.textContent = `${preCur.toLocaleString()}/${preTar.toLocaleString()} (เหลือ ${preRem.toLocaleString()})`;",
                    "preMini.textContent = `${preCur.toLocaleString()}/${preTar.toLocaleString()}`;")
html = html.replace("postMini.textContent = `รอเริ่ม (${postTar.toLocaleString()} คน)`;",
                    "postMini.textContent = `รอเริ่ม`;")

with open(target_file, 'w', encoding='utf-8') as f:
    f.write(html)

print("Applied perfected layout and fitHeroNumbers successfully!")
