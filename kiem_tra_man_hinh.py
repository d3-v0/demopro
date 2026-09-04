#!/usr/bin/env python3
"""
Kiểm tra chất lượng màn hình máy tính
Yêu cầu: Python 3.8+ (chỉ dùng thư viện có sẵn: tkinter)
Chạy: python kiem_tra_man_hinh.py
"""

import tkinter as tk
from tkinter import font as tkfont
import math

# ===== Cấu hình =====
TESTS = [
    ("black", "1. Màn hình đen", "Tìm điểm sáng / dead pixel sáng"),
    ("white", "2. Màn hình trắng", "Tìm điểm tối / dead pixel tối"),
    ("red", "3. Đỏ thuần", "Kiểm tra subpixel đỏ"),
    ("green", "4. Xanh lá thuần", "Kiểm tra subpixel xanh lá"),
    ("blue", "5. Xanh dương thuần", "Kiểm tra subpixel xanh dương"),
    ("gradient_h", "6. Gradient ngang", "Độ đồng đều sáng & banding"),
    ("gradient_v", "7. Gradient dọc", "Độ đồng đều sáng & banding"),
    ("checker", "8. Caro (Checkerboard)", "Độ nét & pixel"),
    ("grid", "9. Lưới xanh", "Méo hình / geometry"),
    ("sharpness", "0. Độ nét chữ", "ClearType / text rendering"),
    ("ghost", "G. Ghosting / Motion", "Vệt sáng khi chuyển động"),
]

COLORS = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
}


class ScreenTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Kiểm tra chất lượng màn hình")
        self.root.configure(bg="#0d1117")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)

        self.current_index = 0
        self.is_testing = False
        self.hud_visible = True
        self.ghost_job = None
        self.ghost_x = 0
        self.ghost_dir = 1
        self.cycle_job = None
        self.fullscreen = False

        self._build_menu()
        self._bind_keys()

        # Canvas dùng chung khi test
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg="#000")
        self.hud_label = None

    # ---------- Menu ----------
    def _build_menu(self):
        self.menu_frame = tk.Frame(self.root, bg="#0d1117")
        self.menu_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(
            self.menu_frame,
            text="🖥️  Kiểm tra chất lượng màn hình",
            font=("Segoe UI", 22, "bold"),
            fg="#4fc3f7",
            bg="#0d1117",
        )
        title.pack(pady=(30, 8))

        subtitle = tk.Label(
            self.menu_frame,
            text="Dead pixel · Màu sắc · Độ đồng đều · Độ nét · Ghosting\n"
                 "Nhấn phím số hoặc click nút để bắt đầu  ·  F = toàn màn hình",
            font=("Segoe UI", 11),
            fg="#8b949e",
            bg="#0d1117",
            justify=tk.CENTER,
        )
        subtitle.pack(pady=(0, 20))

        # Lưới nút
        grid = tk.Frame(self.menu_frame, bg="#0d1117")
        grid.pack(padx=30, pady=10, fill=tk.BOTH, expand=True)

        for i, (tid, name, desc) in enumerate(TESTS):
            row, col = divmod(i, 2)
            btn = tk.Button(
                grid,
                text=f"{name}\n{desc}",
                font=("Segoe UI", 10),
                fg="#e6edf3",
                bg="#21262d",
                activebackground="#30363d",
                activeforeground="#4fc3f7",
                relief=tk.FLAT,
                bd=0,
                padx=12,
                pady=12,
                anchor="w",
                justify=tk.LEFT,
                cursor="hand2",
                command=lambda idx=i: self.start_test(idx),
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Nút chạy tự động + hướng dẫn
        bottom = tk.Frame(self.menu_frame, bg="#0d1117")
        bottom.pack(pady=16)

        tk.Button(
            bottom,
            text="▶  Chạy tự động 5 màu cơ bản (phím C)",
            font=("Segoe UI", 11, "bold"),
            fg="#0d1117",
            bg="#81c784",
            activebackground="#66bb6a",
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self.start_cycle,
        ).pack()

        hint = tk.Label(
            self.menu_frame,
            text="Phím tắt khi đang test:  ← → / Space = đổi test   ·   F = fullscreen   ·   H = ẩn HUD   ·   Esc / M = về menu",
            font=("Segoe UI", 9),
            fg="#6e7681",
            bg="#0d1117",
        )
        hint.pack(pady=(12, 20))

    def _bind_keys(self):
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Escape>", lambda e: self.back_to_menu())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())

    def _on_key(self, event):
        key = event.keysym.lower()
        char = event.char

        if not self.is_testing:
            # Menu
            key_map = {
                "1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
                "6": 5, "7": 6, "8": 7, "9": 8, "0": 9,
                "g": 10,
            }
            if char in key_map:
                self.start_test(key_map[char])
            elif char in ("c", "C"):
                self.start_cycle()
            elif key == "f":
                self.toggle_fullscreen()
            return

        # Đang test
        if key in ("right", "space", "n"):
            self.next_test(1)
        elif key in ("left", "p"):
            self.next_test(-1)
        elif key == "f":
            self.toggle_fullscreen()
        elif key in ("h",):
            self.toggle_hud()
        elif key in ("escape", "m"):
            self.back_to_menu()

    # ---------- Điều khiển test ----------
    def start_test(self, index: int):
        self.stop_cycle()
        self.current_index = index
        self.is_testing = True

        self.menu_frame.pack_forget()
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._ensure_hud()
        self.render_test()

    def back_to_menu(self):
        self.stop_cycle()
        self.stop_ghost()
        self.is_testing = False

        self.canvas.pack_forget()
        if self.hud_label:
            self.hud_label.place_forget()
        self.menu_frame.pack(fill=tk.BOTH, expand=True)

        if self.fullscreen:
            self.toggle_fullscreen()

    def next_test(self, direction=1):
        self.stop_ghost()
        self.current_index = (self.current_index + direction) % len(TESTS)
        self.render_test()

    def toggle_hud(self):
        self.hud_visible = not self.hud_visible
        if self.hud_label:
            if self.hud_visible:
                self.hud_label.place(x=16, y=self.root.winfo_height() - 70)
            else:
                self.hud_label.place_forget()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _ensure_hud(self):
        if self.hud_label is None:
            self.hud_label = tk.Label(
                self.root,
                text="",
                font=("Segoe UI", 10),
                fg="#e6edf3",
                bg="#000000",
                padx=12,
                pady=8,
                justify=tk.LEFT,
            )
        if self.hud_visible:
            self.root.update_idletasks()
            self.hud_label.place(x=16, y=self.root.winfo_height() - 70)

    # ---------- Vẽ từng bài test ----------
    def render_test(self):
        tid, name, desc = TESTS[self.current_index]
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or self.root.winfo_width()
        h = self.canvas.winfo_height() or self.root.winfo_height()

        if self.hud_label and self.hud_visible:
            self.hud_label.config(
                text=f"Đang chạy: {name}  —  {desc}\n"
                     f"← → / Space = đổi test   ·   F = fullscreen   ·   H = ẩn HUD   ·   Esc = menu"
            )
            self.hud_label.place(x=16, y=h - 70)

        if tid in COLORS:
            self.canvas.configure(bg=COLORS[tid])
            return

        self.canvas.configure(bg="#000000")

        if tid == "gradient_h":
            self._draw_gradient(w, h, horizontal=True)
        elif tid == "gradient_v":
            self._draw_gradient(w, h, horizontal=False)
        elif tid == "checker":
            self._draw_checker(w, h, size=12)
        elif tid == "grid":
            self._draw_grid(w, h, step=50)
        elif tid == "sharpness":
            self._draw_sharpness(w, h)
        elif tid == "ghost":
            self._start_ghost(w, h)

    def _draw_gradient(self, w, h, horizontal=True):
        steps = 256
        if horizontal:
            band = max(1, w // steps)
            for i in range(0, w, band):
                val = int(255 * i / w)
                color = f"#{val:02x}{val:02x}{val:02x}"
                self.canvas.create_rectangle(i, 0, i + band + 1, h, fill=color, outline="")
        else:
            band = max(1, h // steps)
            for i in range(0, h, band):
                val = int(255 * i / h)
                color = f"#{val:02x}{val:02x}{val:02x}"
                self.canvas.create_rectangle(0, i, w, i + band + 1, fill=color, outline="")

    def _draw_checker(self, w, h, size=12):
        for y in range(0, h, size):
            for x in range(0, w, size):
                if ((x // size) + (y // size)) % 2 == 0:
                    self.canvas.create_rectangle(
                        x, y, x + size, y + size, fill="#FFFFFF", outline=""
                    )

    def _draw_grid(self, w, h, step=50):
        for x in range(0, w, step):
            self.canvas.create_line(x, 0, x, h, fill="#00FF00", width=1)
        for y in range(0, h, step):
            self.canvas.create_line(0, y, w, y, fill="#00FF00", width=1)

    def _draw_sharpness(self, w, h):
        self.canvas.configure(bg="#FFFFFF")
        cx, cy = w // 2, h // 2

        items = [
            (cy - 100, 28, "bold", "Kiểm tra độ nét chữ"),
            (cy - 50, 16, "normal",
             "The quick brown fox jumps over the lazy dog.  0123456789"),
            (cy - 20, 15, "normal",
             "áàảãạăắằẳẵặâấầẩẫậ éèẻẽẹêếềểễệ íìỉĩị óòỏõọôốồổỗộơớờởỡợ"),
            (cy + 20, 13, "normal",
             "Hãy nhìn sát: chữ có bị lem, có viền màu lạ ở cạnh không?"),
            (cy + 55, 11, "normal",
             "ClearType (Windows) hoặc font smoothing (macOS) ảnh hưởng kết quả."),
            (cy + 95, 9, "normal",
             "9px: Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
             "The five boxing wizards jump quickly."),
        ]

        for y, size, weight, text in items:
            f = tkfont.Font(family="Segoe UI", size=size, weight=weight)
            self.canvas.create_text(cx, y, text=text, fill="#000000", font=f, anchor="center")

    # ---------- Ghosting ----------
    def _start_ghost(self, w, h):
        self.ghost_x = 0
        self.ghost_dir = 1
        self.bar_id = self.canvas.create_rectangle(
            0, 0, 40, h, fill="#FFFFFF", outline=""
        )
        self._animate_ghost(w, h)

    def _animate_ghost(self, w, h):
        speed = 10
        self.ghost_x += speed * self.ghost_dir
        if self.ghost_x >= w - 40:
            self.ghost_dir = -1
        elif self.ghost_x <= 0:
            self.ghost_dir = 1

        self.canvas.coords(self.bar_id, self.ghost_x, 0, self.ghost_x + 40, h)
        self.ghost_job = self.root.after(16, lambda: self._animate_ghost(w, h))

    def stop_ghost(self):
        if self.ghost_job:
            self.root.after_cancel(self.ghost_job)
            self.ghost_job = None

    # ---------- Cycle ----------
    def start_cycle(self):
        self.start_test(0)
        self._cycle_next()

    def _cycle_next(self):
        # Chỉ cycle 5 màu đầu
        self.current_index = (self.current_index + 1) % 5
        self.render_test()
        self.cycle_job = self.root.after(2500, self._cycle_next)

    def stop_cycle(self):
        if self.cycle_job:
            self.root.after_cancel(self.cycle_job)
            self.cycle_job = None

    # ---------- Resize ----------
    def on_resize(self, event=None):
        if self.is_testing:
            # Vẽ lại khi đổi kích thước / fullscreen
            self.root.after(50, self.render_test)

    def run(self):
        self.canvas.bind("<Configure>", lambda e: self.on_resize())
        self.root.mainloop()


if __name__ == "__main__":
    app = ScreenTester()
    app.run()
