#!/usr/bin/env python3
"""
dice_capture_gui.py

A live-preview GUI for collecting labeled training images for a dice roll
classifier on a Raspberry Pi. Shows a real-time camera feed and lets you pick
die number, tray position, orientation, and side-up with buttons, then saves
a full-resolution image with one click.

Filename format (matches capture_die_image.py / the tracker spreadsheet):
    die<DIE>_pos<POSITION>_rot<ORIENTATION>_side<SIDE>_<TIMESTAMP>.jpg

Requires (Raspberry Pi OS, Bookworm or later):
    sudo apt install -y python3-picamera2 python3-pil python3-tk

Run with a monitor/touchscreen attached, or over VNC (not plain SSH X-forwarding
-- the preview uses picamera2's array capture, which works fine either way).

Usage:
    python3 dice_capture_gui.py
    python3 dice_capture_gui.py --outdir ./data --die 2
"""

import argparse
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

ORIENTATIONS = [0, 60, 120, 180, 240, 300]
SIDES = [1, 2, 3, 4, 5, 6]
DICE = [1, 2, 3, 4, 5, 6]

# (row, col) -> position number, matching the tracker spreadsheet's 3x3 grid
POSITION_GRID = {
    (0, 0): (1, "Top-Left"),  (0, 1): (2, "Top-Mid"),  (0, 2): (3, "Top-Right"),
    (1, 0): (4, "Mid-Left"),  (1, 1): (9, "Center"),   (1, 2): (5, "Mid-Right"),
    (2, 0): (6, "Bot-Left"),  (2, 1): (7, "Bot-Mid"),  (2, 2): (8, "Bot-Right"),
}

PREVIEW_SIZE = (640, 480)
CAPTURE_SIZE = (1640, 1232)
PREVIEW_FPS_MS = 66  # ~15 fps, easy on the Pi's CPU

ACCENT = "#305496"
ACCENT_LIGHT = "#D9E1F2"
SELECTED = "#4CAF50"
BG = "#F2F2F2"


def parse_args():
    p = argparse.ArgumentParser(description="Live-preview capture GUI for dice classifier data.")
    p.add_argument("--outdir", type=str, default="./captures",
                    help="Directory to save images into (default: ./captures)")
    p.add_argument("--die", type=int, default=1, choices=DICE,
                    help="Initial die number selection (default: 1)")
    return p.parse_args()


class DiceCaptureApp:
    def __init__(self, root: tk.Tk, outdir: Path, initial_die: int):
        self.root = root
        self.outdir = outdir
        self.outdir.mkdir(parents=True, exist_ok=True)

        self.root.title("Dice Classifier — Capture Tool")
        self.root.configure(bg=BG)
        self.root.geometry("1150x650")

        self.die_var = tk.IntVar(value=initial_die)
        self.position_var = tk.IntVar(value=9)
        self.position_name_var = tk.StringVar(value="Center")
        self.orientation_var = tk.IntVar(value=0)
        self.side_var = tk.IntVar(value=1)
        self.session_count = 0

        self.picam2 = None
        self.photo_image = None  # keep a reference or Tkinter will garbage-collect it

        self._init_camera()
        self._build_ui()
        self._update_preview()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------
    # Camera setup
    # ---------------------------------------------------------------
    def _init_camera(self):
        try:
            from picamera2 import Picamera2
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "picamera2 is not installed.\n\nOn Raspberry Pi OS run:\n"
                "sudo apt install -y python3-picamera2",
            )
            sys.exit(1)

        self.Picamera2 = Picamera2
        self.picam2 = Picamera2()
        # 'main' = full-res stream used for saved captures
        # 'lores' = small stream used for the live preview, so the preview
        # loop stays fast regardless of the save resolution.
        config = self.picam2.create_still_configuration(
            main={"size": CAPTURE_SIZE},
            lores={"size": PREVIEW_SIZE, "format": "RGB888"},
            display="lores",
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(1.0)  # let AE/AWB settle

    # ---------------------------------------------------------------
    # UI layout
    # ---------------------------------------------------------------
    def _build_ui(self):
        bold = tkfont.Font(family="Arial", size=11, weight="bold")
        title_font = tkfont.Font(family="Arial", size=15, weight="bold")

        # --- Left: live preview ---
        left = tk.Frame(self.root, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        tk.Label(left, text="Live Preview", font=title_font, bg=BG, fg=ACCENT).pack(anchor="w")
        self.preview_label = tk.Label(left, bg="black", width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1])
        self.preview_label.pack(pady=8)

        self.status_var = tk.StringVar(value="Camera ready.")
        tk.Label(left, textvariable=self.status_var, font=("Arial", 10), bg=BG, fg="#333333",
                 anchor="w", justify="left", wraplength=PREVIEW_SIZE[0]).pack(fill="x")

        self.log_text = tk.Text(left, height=8, font=("Courier", 9), state="disabled",
                                  bg="white", relief="solid", borderwidth=1)
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

        # --- Right: controls ---
        right = tk.Frame(self.root, bg=BG, width=380)
        right.pack(side="right", fill="y", padx=12, pady=12)

        tk.Label(right, text="Capture Settings", font=title_font, bg=BG, fg=ACCENT).pack(anchor="w")

        # Die number
        tk.Label(right, text="Die Number", font=bold, bg=BG).pack(anchor="w", pady=(12, 2))
        die_frame = tk.Frame(right, bg=BG)
        die_frame.pack(anchor="w")
        for d in DICE:
            tk.Radiobutton(die_frame, text=str(d), variable=self.die_var, value=d,
                            font=("Arial", 10), bg=BG, indicatoron=True).pack(side="left", padx=2)

        # Position grid (visually matches the tray layout)
        tk.Label(right, text="Tray Position", font=bold, bg=BG).pack(anchor="w", pady=(14, 2))
        pos_frame = tk.Frame(right, bg=BG)
        pos_frame.pack(anchor="w")
        self.position_buttons = {}
        for (row, col), (num, name) in POSITION_GRID.items():
            btn = tk.Button(
                pos_frame, text=f"{num}\n{name}", width=10, height=2,
                font=("Arial", 9), bg=ACCENT_LIGHT,
                command=lambda n=num, nm=name: self._select_position(n, nm),
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            self.position_buttons[num] = btn
        self._select_position(9, "Center")  # default highlight

        # Orientation
        tk.Label(right, text="Orientation (deg about Z)", font=bold, bg=BG).pack(anchor="w", pady=(14, 2))
        ori_frame = tk.Frame(right, bg=BG)
        ori_frame.pack(anchor="w")
        for o in ORIENTATIONS:
            tk.Radiobutton(ori_frame, text=f"{o}°", variable=self.orientation_var, value=o,
                            font=("Arial", 10), bg=BG, indicatoron=True).pack(side="left", padx=3)

        # Side up
        tk.Label(right, text="Side Facing Up", font=bold, bg=BG).pack(anchor="w", pady=(14, 2))
        side_frame = tk.Frame(right, bg=BG)
        side_frame.pack(anchor="w")
        for s in SIDES:
            tk.Radiobutton(side_frame, text=str(s), variable=self.side_var, value=s,
                            font=("Arial", 10), bg=BG, indicatoron=True).pack(side="left", padx=3)

        # Capture button
        capture_btn = tk.Button(
            right, text="📸  CAPTURE", font=("Arial", 16, "bold"),
            bg=ACCENT, fg="white", activebackground="#24406e", activeforeground="white",
            height=2, command=self._on_capture,
        )
        capture_btn.pack(fill="x", pady=(24, 6))

        # Session counter
        self.count_var = tk.StringVar(value="Captured this session: 0")
        tk.Label(right, textvariable=self.count_var, font=("Arial", 10), bg=BG, fg="#333333").pack(anchor="w")

        # Output dir display
        tk.Label(right, text=f"Saving to: {self.outdir.resolve()}", font=("Arial", 9),
                 bg=BG, fg="#666666", wraplength=360, justify="left").pack(anchor="w", pady=(10, 0))

        # Keyboard shortcut: spacebar captures
        self.root.bind("<space>", lambda e: self._on_capture())

    def _select_position(self, num, name):
        self.position_var.set(num)
        self.position_name_var.set(name)
        for n, btn in self.position_buttons.items():
            btn.configure(bg=SELECTED if n == num else ACCENT_LIGHT,
                          fg="white" if n == num else "black")

    # ---------------------------------------------------------------
    # Live preview loop
    # ---------------------------------------------------------------
    def _update_preview(self):
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "Pillow is not installed.\n\nOn Raspberry Pi OS run:\n"
                "sudo apt install -y python3-pil python3-pil.imagetk",
            )
            sys.exit(1)

        try:
            frame = self.picam2.capture_array("lores")
            image = Image.fromarray(frame)
            self.photo_image = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.photo_image)
        except Exception as exc:  # keep the GUI alive even if a frame grab hiccups
            self.status_var.set(f"Preview error: {exc}")

        self.root.after(PREVIEW_FPS_MS, self._update_preview)

    # ---------------------------------------------------------------
    # Capture
    # ---------------------------------------------------------------
    def _on_capture(self):
        die = self.die_var.get()
        pos = self.position_var.get()
        ori = self.orientation_var.get()
        side = self.side_var.get()

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"die{die}_pos{pos}_rot{ori}_side{side}_{timestamp}.jpg"
        filepath = self.outdir / filename

        try:
            self.picam2.capture_file(str(filepath), name="main")
        except Exception as exc:
            messagebox.showerror("Capture failed", str(exc))
            return

        self.session_count += 1
        self.count_var.set(f"Captured this session: {self.session_count}")
        self.status_var.set(f"Saved: {filename}")
        self._log(f"[{time.strftime('%H:%M:%S')}] die={die} pos={pos} "
                   f"({self.position_name_var.get()}) rot={ori} side={side} -> {filename}")

    def _log(self, line: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---------------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------------
    def _on_close(self):
        try:
            if self.picam2 is not None:
                self.picam2.stop()
        finally:
            self.root.destroy()


def main():
    args = parse_args()
    root = tk.Tk()
    app = DiceCaptureApp(root, Path(args.outdir), args.die)
    root.mainloop()


if __name__ == "__main__":
    main()