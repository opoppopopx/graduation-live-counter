# -*- coding: utf-8 -*-
import re

target_file = r'c:\Users\ACER\.gemini\antigravity-ide\scratch\graduation-live-counter\static\stage.html'

with open(target_file, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Base CSS to directly have the beautiful XL typography
html = html.replace(
    ".ceremony-main-title {\n            font-size: clamp(26px, 2.8vw, 44px);",
    ".ceremony-main-title {\n            font-size: clamp(30px, 3.4vw, 52px);"
)

html = html.replace(
    ".ceremony-sub-row {\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            gap: clamp(8px, 1.4vw, 20px);\n            font-size: clamp(14px, 1.3vw, 20px);",
    ".ceremony-sub-row {\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            gap: clamp(8px, 1.4vw, 20px);\n            font-size: clamp(15px, 1.45vw, 22px);"
)

html = html.replace(
    ".break-tag {\n            font-size: clamp(14px, 1.3vw, 19px);",
    ".break-tag {\n            font-size: clamp(15px, 1.4vw, 21px);"
)

html = html.replace(
    ".break-stat-text {\n            font-size: clamp(13px, 1.25vw, 18px);",
    ".break-stat-text {\n            font-size: clamp(14px, 1.35vw, 20px);"
)

html = html.replace(
    ".hero-header {\n            display: flex;\n            justify-content: center;\n            align-items: center;\n            gap: 6px;\n            font-size: clamp(24px, 2.6vw, 42px);",
    ".hero-header {\n            display: flex;\n            justify-content: center;\n            align-items: center;\n            gap: 6px;\n            font-size: clamp(26px, 2.9vw, 46px);"
)

html = html.replace(
    ".hero-num {\n            font-family: 'Outfit', 'Kanit', sans-serif;\n            font-weight: 900;\n            line-height: 0.92;\n            letter-spacing: -2px;\n            text-align: center;\n            white-space: nowrap;\n            font-size: clamp(90px, 20vh, 200px);",
    ".hero-num {\n            font-family: 'Outfit', 'Kanit', sans-serif;\n            font-weight: 900;\n            line-height: 0.92;\n            letter-spacing: -2px;\n            text-align: center;\n            white-space: nowrap;\n            font-size: clamp(100px, 22vh, 215px);"
)

html = html.replace(
    ".hero-footer-bar {\n            border-radius: 10px;\n            padding: 5px 14px;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            gap: 6px;\n            font-size: clamp(16px, 1.6vw, 25px);",
    ".hero-footer-bar {\n            border-radius: 10px;\n            padding: 5px 14px;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            gap: 6px;\n            font-size: clamp(17px, 1.7vw, 27px);"
)

html = html.replace(
    ".bottom-card-title {\n            font-size: clamp(15px, 1.45vw, 22px);",
    ".bottom-card-title {\n            font-size: clamp(16px, 1.55vw, 24px);"
)

html = html.replace(
    ".bottom-card-val {\n            font-family: 'Outfit', 'Kanit', sans-serif;\n            font-size: clamp(30px, 3.6vw, 56px);",
    ".bottom-card-val {\n            font-family: 'Outfit', 'Kanit', sans-serif;\n            font-size: clamp(34px, 4vw, 62px);"
)

html = html.replace(
    ".bottom-card-sub {\n            font-size: clamp(13px, 1.25vw, 18px);",
    ".bottom-card-sub {\n            font-size: clamp(14px, 1.3vw, 19px);"
)

# 2. Put class="text-xl" directly on <body> tag
html = html.replace('<body>', '<body class="text-xl">')

# 3. Always force XL in JavaScript so Chrome clears any old 'false' setting in localStorage
old_storage_init = """        // Default to Extra Large (XL) as requested by user
        try {
            const savedPref = localStorage.getItem('stage_font_xl');
            const shouldBeXl = (savedPref === null || savedPref === 'true');
            setTextSize(shouldBeXl);
        } catch(e) {
            setTextSize(true);
        }"""

new_storage_init = """        // Default and enforce Extra Large (XL) across all browsers (Chrome, Edge, etc.)
        setTextSize(true);
        try { localStorage.setItem('stage_font_xl', 'true'); } catch(e) {}"""

html = html.replace(old_storage_init, new_storage_init)

with open(target_file, 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: Unified base CSS and enforced XL styling identically across Chrome and Edge!")
