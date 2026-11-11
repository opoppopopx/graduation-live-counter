import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('analytics.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add self.counting_mode = "auto"
text = text.replace(
    "self.is_paused = False\n",
    "self.is_paused = False\n        self.counting_mode = 'auto'  # 'auto' | 'manual'\n"
)

# 2. Add set_counting_mode method
method_code = """    def set_counting_mode(self, mode: str) -> Dict:
        \"\"\"สลับโหมดการนับ: 'auto' (ระบบอัตโนมัติ AI) หรือ 'manual' (ระบบนับด้วยมือ)\"\"\"
        if mode in ("auto", "manual"):
            self.counting_mode = mode
            if mode == "manual":
                self.is_paused = True  # หยุดระบบนับอัตโนมัติทันที
            else:
                self.is_paused = False # กลับมาเปิดระบบอัตโนมัติ
        return self.get_summary()

    def toggle_pause(self) -> bool:"""

text = text.replace("    def toggle_pause(self) -> bool:", method_code)

# 3. Add counting_mode to get_summary dictionary
text = text.replace(
    '"is_paused":                self.is_paused,\n',
    '"is_paused":                self.is_paused,\n            "counting_mode":            getattr(self, "counting_mode", "auto"),\n'
)

with open('analytics.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("analytics.py updated successfully!")
