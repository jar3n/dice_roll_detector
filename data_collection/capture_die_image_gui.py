#!/usr/bin/env python3
"""
dice_capture_gui.py

A live-preview GUI for collecting labeled training images for a dice roll
classifier on a Raspberry Pi. Shows a real-time camera feed and lets you pick
die number, tray position, orientation, and side-up with buttons, then saves
a full-resolution image with one click.

Uses OpenCV (V4L2) to talk to the camera, so it works with USB/UVC webcams
(this is the right tool for a USB webcam -- picamera2/libcamera targets the
Pi's own CSI camera module and only has limited, single-stream UVC support).

Filename format (matches capture_die_image.py / the tracker spreadsheet):
    die<DIE>_pos<POSITION>_rot<ORIENTATION>_side<SIDE>_<TIMESTAMP>.jpg

Requires:
    sudo apt install -y python3-opencv python3-pil python3-pil.imagetk python3-tk
    (or: pip install opencv-python --break-system-packages)

Usage:
    python3 dice_capture_gui.py
    python3 dice_capture_gui.py --outdir ./data --die 2 --camera-index 0
    python3 dice_capture_gui.py --list-cameras
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
# Requested capture resolution -- OpenCV will fall back to the webcam's
# closest supported resolution if this exact size isn't available.
CAPTURE_SIZE = (1920, 1080)
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
    p.add_argument("--camera-index", type=int, default=0,
                    help="OpenCV camera index, e.g. matches /dev/video0 (default: 0)")
    p.add_argument("--list-cameras", action="store_true",
                    help="Probe /dev/video0.. and print which indices open successfully, then exit")
    return p.parse_args()


def list_cameras(max_index=10):
    import cv2
    print("Probing camera indices...")
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ok, _ = cap.read()
            print(f"  index {i}: {'opens and reads a frame' if ok else 'opens but no frame'}")
            found.append(i)
        cap.release()
    if not found:
        print("  No camera indices responded. Check `ls /dev/video*` and cable/USB connection.")
    else:
        print(f"Working indices: {found}. Use --camera-index <N> to pick one.")


class DiceCaptureApp:
    def __init__(self, root: tk.Tk, outdir: Path, initial_die: int, camera_index: int):
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

        self.cap = None
        self.photo_image = None  # keep a reference or Tkinter will garbage-collect it

        self._init_camera(camera_index)
        self._build_ui()
        self._update_preview()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------
    # Camera setup
    # ---------------------------------------------------------------
    def _init_camera(self, camera_index: int):
        try:
            import cv2
        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "opencv-python is not installed.\n\nOn Raspberry Pi OS run:\n"
                "sudo apt install -y python3-opencv\n"
                "or: pip install opencv-python --break-system-packages",
            )
            sys.exit(1)

        self.cv2 = cv2
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            messagebox.showerror(
                "Camera not found",
                f"Could not open camera index {camera_index}.\n\n"
                "Run this script with --list-cameras to see which indices work, "
                "or check `ls /dev/video*` and that the webcam is plugged in.",
            )
            sys.exit(1)

        # Ask for a higher resolution; the webcam will silently clamp to the
        # closest mode it actually supports.
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_SIZE[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_SIZE[1])

        # Warm up: discard the first few frames while auto-exposure settles.
        for _ in range(5):
            self.cap.read()
            time.sleep(0.05)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.actual_capture_size = (actual_w, actual_h)

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

        self.status_var = tk.StringVar(
            value=f"Camera ready. Capturing at {self.actual_capture_size[0]}x{self.actual_capture_size[1]}."
        )
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
            ok, frame = self.cap.read()
            if ok:
                rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb).resize(PREVIEW_SIZE)
                self.photo_image = ImageTk.PhotoImage(image)
                self.preview_label.configure(image=self.photo_image)
            else:
                self.status_var.set("Preview: no frame received from camera.")
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

        # Grab a fresh frame at full resolution rather than reusing the
        # (possibly stale) preview frame.
        ok, frame = self.cap.read()
        if not ok:
            messagebox.showerror("Capture failed", "Camera did not return a frame.")
            return

        try:
            self.cv2.imwrite(str(filepath), frame)
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
            if self.cap is not None:
                self.cap.release()
        finally:
            self.root.destroy()


def main():
    args = parse_args()
    if args.list_cameras:
        list_cameras()
        return
    root = tk.Tk()
    app = DiceCaptureApp(root, Path(args.outdir), args.die, args.camera_index)
    root.mainloop()


if __name__ == "__main__":
    main()