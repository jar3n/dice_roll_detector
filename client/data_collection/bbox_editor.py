#!/home/jenglander/Documents/665.681_Application_of_Sensor_Systems/course_project/code/.venv/bin/python
"""
bbox_editor.py

Visualize, create, and correct YOLO-format bounding box labels for the dice
object detection dataset.  By default it annotates the raw capture images
in place, writing one "<image>.txt" label next to each "<image>.jpg":

    data/source/obj/<name>.jpg
    data/source/obj/<name>.txt   one "class cx cy w h" per line (normalized 0-1)

When the source images are labeled, copy the pairs into the dataset splits
(data/datasets/images/{train,val} + labels/{train,val}) to build the YOLO
training set, or open the split directories directly with --split.

Usage:
    python3 bbox_editor.py                       # annotate data/source/obj in place
    python3 bbox_editor.py --split train         # edit a dataset split instead
    python3 bbox_editor.py --split val
    python3 bbox_editor.py --images-dir ../data/source/obj --labels-dir ../data/source/labels
    python3 bbox_editor.py --classes die,dice

    # use the project venv (code/.venv), which has tkinter + Pillow
    # (with ImageTk) installed:
    ../.venv/bin/python bbox_editor.py

Controls:
    Mouse
        drag on empty area     draw a new box
        drag inside a box      move it
        drag a corner handle   resize it
        right-click a box      delete it
    Keys
        Left / Right           previous / next image
        Delete / Backspace     delete the selected box
        Ctrl+Z                 undo last box edit
        s                      save current image's label
        S or Ctrl+S            save all labels

    The die's class is built from the two attribute text boxes:
    sides + face-up combine into a class like "d6_up5".
"""

import argparse
import sys
from pathlib import Path
from typing import NotRequired, TypedDict

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

ACCENT = "#305496"
ACCENT_LIGHT = "#D9E1F2"
SELECTED = "#4CAF50"
BG = "#F2F2F2"
BOX_FILL = "#FFD600"
BOX_FILL_SEL = "#FF3D00"
HANDLE_SIZE = 8


def parse_args():
    project_root = Path(__file__).resolve().parents[3]
    source = project_root / "data" / "source" / "obj"
    dataset = project_root / "data" / "datasets"

    p = argparse.ArgumentParser(description="Visualize and correct YOLO bbox labels.")
    p.add_argument("--split", type=str, choices=["train", "val"], default=None,
                   help="Edit a dataset split instead of the source images: "
                        "images and labels under data/datasets/{images,labels}/<split>")
    p.add_argument("--images-dir", type=str, default=None,
                   help="Directory of images to review (default: <project>/data/source/obj)")
    p.add_argument("--labels-dir", type=str, default=None,
                   help="Directory of YOLO label files (default: same as --images-dir, "
                        "i.e. label files are written next to the images)")
    p.add_argument("--classes", type=str, default="die",
                   help="Comma-separated class names (default: die)")
    args = p.parse_args()

    if args.split is not None:
        if args.images_dir is None:
            args.images_dir = str(dataset / "images" / args.split)
        if args.labels_dir is None:
            args.labels_dir = str(dataset / "labels" / args.split)
    else:
        if args.images_dir is None:
            args.images_dir = str(source)
        if args.labels_dir is None:
            args.labels_dir = args.images_dir
    return args


def load_boxes(path: Path):
    boxes = []
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            cls, x, y, w, h = parts
            boxes.append({"cls": int(cls), "x": float(x), "y": float(y),
                          "w": float(w), "h": float(h)})
    return boxes


def save_boxes(path: Path, boxes):
    lines = [f"{b['cls']} {b['x']:.6f} {b['y']:.6f} {b['w']:.6f} {b['h']:.6f}" for b in boxes]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" if lines else "")


class DragState(TypedDict):
    """Mouse drag state for drawing, moving, or resizing a box."""
    mode: str
    corner: NotRequired[int]
    ox: NotRequired[float]
    oy: NotRequired[float]
    dx: NotRequired[float]
    dy: NotRequired[float]
    sx: NotRequired[float]
    sy: NotRequired[float]
    cx: NotRequired[float]
    cy: NotRequired[float]


class BBoxEditor:
    def __init__(self, root: tk.Tk, images_dir: Path, labels_dir: Path, classes):
        self.root = root
        self.images_dir = Path(images_dir)
        self.labels_dir = Path(labels_dir)
        self.classes = classes

        self.image_paths = sorted(
            p for p in self.images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS
        )
        if not self.image_paths:
            raise SystemExit(f"No images found in {self.images_dir}")

        self.index = 0
        self.img: Image.Image
        self.photo = None
        self.disp_w = self.disp_h = 0
        self.scale = 1.0
        self.offset_x = self.offset_y = 0
        self.boxes = []
        self.selected = -1
        self.history = []
        self.drag: DragState | None = None
        self.sides_var = tk.StringVar(value="6")
        self.side_up_var = tk.StringVar(value="1")

        self._build_ui()
        self._load_image()

        self.canvas.bind("<Configure>", lambda e: self._refit())
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self._bind_keys()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        bold = tkfont.Font(family="Arial", size=11, weight="bold")
        self.root.title("Dice BBox Editor")
        self.root.configure(bg=BG)
        self.root.geometry("1400x900")
        self.root.minsize(900, 600)

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(left, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        right = tk.Frame(main, width=320, bg=BG)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self.file_var = tk.StringVar()
        tk.Label(right, text="Current Image", font=bold, bg=BG, fg=ACCENT).pack(anchor="w", pady=(10, 2))
        tk.Label(right, textvariable=self.file_var, font=("Arial", 9), bg=BG, fg="#333333",
                 wraplength=300, justify="left").pack(anchor="w", fill="x")

        self.boxes_var = tk.StringVar()
        tk.Label(right, textvariable=self.boxes_var, font=("Arial", 11, "bold"),
                 bg=BG, fg="#333333").pack(anchor="w", pady=(8, 2))

        tk.Label(right, text="Die Attributes", font=bold, bg=BG, fg=ACCENT).pack(anchor="w", pady=(10, 2))

        tk.Label(right, text="Number of sides", font=("Arial", 9), bg=BG, fg="#333333").pack(anchor="w")
        self.sides_entry = tk.Entry(right, textvariable=self.sides_var, font=("Arial", 11))
        self.sides_entry.pack(fill="x", pady=(0, 4))

        tk.Label(right, text="Side face up", font=("Arial", 9), bg=BG, fg="#333333").pack(anchor="w")
        self.side_up_combo = ttk.Combobox(
            right, textvariable=self.side_up_var, state="readonly", font=("Arial", 11))
        self.side_up_combo.pack(fill="x", pady=(0, 4))
        self.side_up_combo.bind("<<ComboboxSelected>>", lambda e: self._on_class_change())
        self.sides_entry.bind("<Return>", lambda e: self._on_sides_change())
        self.sides_entry.bind("<FocusOut>", lambda e: self._on_sides_change())
        self._update_side_options()
        tk.Label(right, text="Sides + face-up combine into the class (Enter to apply to the selected box)",
                 font=("Arial", 8), bg=BG, fg="#666666", wraplength=300, justify="left").pack(anchor="w")

        tk.Label(right, text="Edit", font=bold, bg=BG, fg=ACCENT).pack(anchor="w", pady=(14, 2))

        btn_frame = tk.Frame(right, bg=BG)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="◀ Prev", font=("Arial", 10, "bold"), bg=ACCENT_LIGHT,
                  command=self._prev).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(btn_frame, text="Next ▶", font=("Arial", 10, "bold"), bg=ACCENT_LIGHT,
                  command=self._next).pack(side="left", fill="x", expand=True)

        tk.Button(right, text="Delete Selected Box", font=("Arial", 10), bg=ACCENT_LIGHT,
                  command=self._delete_selected).pack(fill="x", pady=(6, 0))
        tk.Button(right, text="Save Label", font=("Arial", 10, "bold"), bg=ACCENT, fg="white",
                  command=self._save_current).pack(fill="x", pady=(10, 0))
        tk.Button(right, text="Save All Labels", font=("Arial", 10), bg=ACCENT_LIGHT,
                  command=self._save_all).pack(fill="x", pady=(4, 0))

        tk.Label(right, text=(
            "Draw: drag on empty area\n"
            "Move: drag inside a box\n"
            "Resize: drag a corner handle\n"
            "Delete: right-click a box\n"
            "Set class: edit the two text boxes above\n"
            "Undo: Ctrl+Z   Save: s"),
            font=("Arial", 9), bg=BG, fg="#666666", justify="left").pack(anchor="w", pady=(18, 0))

        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var, font=("Arial", 9),
                 bg=ACCENT_LIGHT, fg="#333333", anchor="w").pack(side="bottom", fill="x")

    def _bind_keys(self):
        self.root.bind("<Left>", lambda e: self._prev())
        self.root.bind("<Right>", lambda e: self._next())
        self.root.bind("<Delete>", lambda e: self._delete_selected())
        self.root.bind("<BackSpace>", lambda e: self._delete_selected())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("s", lambda e: self._save_current())
        self.root.bind("<Control-s>", lambda e: self._save_all())

    # ------------------------------------------------------------------
    # Image / label loading
    # ------------------------------------------------------------------
    def _label_path(self):
        return self.labels_dir / (self.image_paths[self.index].stem + ".txt")

    def _load_image(self):
        path = self.image_paths[self.index]
        self.img = Image.open(path).convert("RGB")
        self.boxes = load_boxes(self._label_path())
        self.selected = -1
        self.history = []
        self.drag = None
        self._refit()
        self._update_info()

    def _refit(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        img_w, img_h = self.img.size
        self.scale = min(cw / img_w, ch / img_h)
        self.disp_w = int(img_w * self.scale)
        self.disp_h = int(img_h * self.scale)
        self.offset_x = (cw - self.disp_w) // 2
        self.offset_y = (ch - self.disp_h) // 2
        from PIL import ImageTk  # pyright: ignore[reportAttributeAccessIssue]
        self.photo = ImageTk.PhotoImage(self.img.resize((self.disp_w, self.disp_h), Image.Resampling.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.photo,
                                 anchor="nw", tags=("bg",))
        self._redraw()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _norm_to_canvas(self, b):
        w, h = self.img.size
        return (
            self.offset_x + (b["x"] - b["w"] / 2) * w * self.scale,
            self.offset_y + (b["y"] - b["h"] / 2) * h * self.scale,
            self.offset_x + (b["x"] + b["w"] / 2) * w * self.scale,
            self.offset_y + (b["y"] + b["h"] / 2) * h * self.scale,
        )

    def _canvas_to_img(self, cx, cy):
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    def _handles(self, b):
        x1, y1, x2, y2 = self._norm_to_canvas(b)
        return [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]

    def _hit_test(self, cx, cy):
        for i in range(len(self.boxes) - 1, -1, -1):
            x1, y1, x2, y2 = self._norm_to_canvas(self.boxes[i])
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return i
        return -1

    def _hit_handle(self, cx, cy):
        if not (0 <= self.selected < len(self.boxes)):
            return -1
        for i, (hx, hy) in enumerate(self._handles(self.boxes[self.selected])):
            if abs(cx - hx) <= HANDLE_SIZE / 2 + 4 and abs(cy - hy) <= HANDLE_SIZE / 2 + 4:
                return i
        return -1

    def _redraw(self, temp_rect=None):
        self.canvas.delete("overlay")
        for i, b in enumerate(self.boxes):
            x1, y1, x2, y2 = self._norm_to_canvas(b)
            sel = i == self.selected
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=BOX_FILL_SEL if sel else BOX_FILL,
                width=3 if sel else 2, tags=("overlay",))
            cls = b["cls"]
            label = self.classes[cls] if 0 <= cls < len(self.classes) else str(cls)
            self.canvas.create_text(
                (x1 + x2) / 2, y1 - 4, text=label,
                fill=BOX_FILL_SEL if sel else BOX_FILL,
                font=("Arial", 11, "bold"), anchor="s", tags=("overlay",))
            if sel:
                for hx, hy in self._handles(b):
                    self.canvas.create_rectangle(
                        hx - HANDLE_SIZE // 2, hy - HANDLE_SIZE // 2,
                        hx + HANDLE_SIZE // 2, hy + HANDLE_SIZE // 2,
                        fill="white", outline="black", tags=("overlay",))
        if temp_rect:
            self.canvas.create_rectangle(*temp_rect, outline=BOX_FILL_SEL, width=2,
                                         dash=(4, 4), tags=("overlay",))

    # ------------------------------------------------------------------
    # Mouse interactions
    # ------------------------------------------------------------------
    def _on_press(self, event):
        cx, cy = event.x, event.y
        handle = self._hit_handle(cx, cy)
        if handle >= 0:
            self._snapshot()
            b = self.boxes[self.selected]
            x1, y1, x2, y2 = self._norm_to_canvas(b)
            corners = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
            self.drag = {"mode": "resize", "corner": handle,
                         "ox": corners[3 - handle][0], "oy": corners[3 - handle][1]}
            return
        hit = self._hit_test(cx, cy)
        if hit >= 0:
            self._snapshot()
            self.selected = hit
            self._set_class_from_box(self.boxes[hit]["cls"])
            b = self.boxes[hit]
            x1, y1, x2, y2 = self._norm_to_canvas(b)
            self.drag = {"mode": "move", "dx": cx - (x1 + x2) / 2, "dy": cy - (y1 + y2) / 2}
            self._redraw()
            self._update_info()
            return
        self.selected = -1
        self.drag = {"mode": "draw", "sx": cx, "sy": cy, "cx": cx, "cy": cy}
        self._redraw((cx, cy, cx, cy))
        self._update_info()

    def _on_drag(self, event):
        if not self.drag:
            return
        cx, cy = event.x, event.y
        mode = self.drag["mode"]
        if mode == "move":
            b = self.boxes[self.selected]
            dx = self.drag.get("dx", 0.0)
            dy = self.drag.get("dy", 0.0)
            ix, iy = self._canvas_to_img(cx - dx, cy - dy)
            b["x"] = max(0.0, min(1.0, ix / self.img.size[0]))
            b["y"] = max(0.0, min(1.0, iy / self.img.size[1]))
            self._redraw()
        elif mode == "resize":
            self._drag_resize(cx, cy)
            self._redraw()
        elif mode == "draw":
            self.drag["cx"], self.drag["cy"] = cx, cy
            sx = self.drag.get("sx", 0.0)
            sy = self.drag.get("sy", 0.0)
            self._redraw((sx, sy, cx, cy))

    def _drag_resize(self, cx, cy):
        assert self.drag is not None
        b = self.boxes[self.selected]
        ox = self.drag.get("ox", 0.0)
        oy = self.drag.get("oy", 0.0)
        oxi = (ox - self.offset_x) / self.scale
        oyi = (oy - self.offset_y) / self.scale
        cxi, cyi = self._canvas_to_img(cx, cy)
        W, H = self.img.size
        x1 = max(0.0, min(oxi, cxi)); x2 = min(W, max(oxi, cxi))
        y1 = max(0.0, min(oyi, cyi)); y2 = min(H, max(oyi, cyi))
        if x2 - x1 < 2:
            x2 = min(W, x1 + 2)
        if y2 - y1 < 2:
            y2 = min(H, y1 + 2)
        b["x"] = (x1 + x2) / 2 / W
        b["w"] = (x2 - x1) / W
        b["y"] = (y1 + y2) / 2 / H
        b["h"] = (y2 - y1) / H

    def _on_release(self, event):
        if not self.drag or self.drag["mode"] != "draw":
            self.drag = None
            return
        sx = self.drag.get("sx", 0.0)
        sy = self.drag.get("sy", 0.0)
        ex, ey = event.x, event.y
        self.drag = None
        self._redraw()
        ix1, iy1 = self._canvas_to_img(sx, sy)
        ix2, iy2 = self._canvas_to_img(ex, ey)
        x1, x2 = min(ix1, ix2), max(ix1, ix2)
        y1, y2 = min(iy1, iy2), max(iy1, iy2)
        W, H = self.img.size
        if x2 - x1 < 5 or y2 - y1 < 5:
            return
        self._snapshot()
        self.boxes.append({
            "cls": self._class_index(),
            "x": (x1 + x2) / 2 / W,
            "y": (y1 + y2) / 2 / H,
            "w": (x2 - x1) / W,
            "h": (y2 - y1) / H,
        })
        self.selected = len(self.boxes) - 1
        self._redraw()
        self._update_info()

    def _on_right_click(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit >= 0:
            self._snapshot()
            del self.boxes[hit]
            self.selected = -1
            self._redraw()
            self._update_info()

    # ------------------------------------------------------------------
    # Editing operations
    # ------------------------------------------------------------------
    def _snapshot(self):
        self.history.append([dict(b) for b in self.boxes])
        if len(self.history) > 50:
            self.history.pop(0)

    def _undo(self):
        if not self.history:
            return
        self.boxes = self.history.pop()
        self.selected = -1
        self._redraw()
        self._update_info()

    def _delete_selected(self):
        if not (0 <= self.selected < len(self.boxes)):
            return
        self._snapshot()
        del self.boxes[self.selected]
        self.selected = -1
        self._redraw()
        self._update_info()

    def _class_name(self):
        sides = self.sides_var.get().strip() or "6"
        up = self.side_up_var.get().strip()
        return f"d{sides}_up{up}"

    def _class_index(self, name=None):
        name = name or self._class_name()
        if name in self.classes:
            return self.classes.index(name)
        self.classes.append(name)
        return len(self.classes) - 1

    def _update_side_options(self):
        try:
            n = max(2, int(self.sides_var.get().strip() or "6"))
        except ValueError:
            n = 6
        options = [str(i) for i in range(1, n + 1)]
        self.side_up_combo["values"] = options
        if self.side_up_var.get() not in options:
            self.side_up_var.set(options[0])

    def _on_sides_change(self):
        self._update_side_options()
        self._on_class_change()

    def _set_class_from_box(self, cls):
        if not (0 <= cls < len(self.classes)):
            return
        name = self.classes[cls]
        try:
            sides, up = name.split("_up", 1)
            if sides.startswith("d"):
                self.sides_var.set(sides[1:])
            self.side_up_var.set(up)
        except (ValueError, IndexError):
            self.sides_var.set("6")
            self.side_up_var.set("")
        self._update_side_options()

    def _on_class_change(self):
        if 0 <= self.selected < len(self.boxes):
            self._snapshot()
            self.boxes[self.selected]["cls"] = self._class_index()
            self._redraw()
            self._update_info()

    # ------------------------------------------------------------------
    # Navigation / save
    # ------------------------------------------------------------------
    def _prev(self):
        self._goto(self.index - 1)

    def _next(self):
        self._goto(self.index + 1)

    def _goto(self, idx):
        idx = max(0, min(len(self.image_paths) - 1, idx))
        if idx != self.index:
            self.index = idx
            self._load_image()

    def _save_current(self):
        save_boxes(self._label_path(), self.boxes)
        self._update_info(save_note="saved")

    def _save_all(self):
        n = 0
        for path in self.image_paths:
            label = self.labels_dir / (path.stem + ".txt")
            boxes = load_boxes(label)
            save_boxes(label, boxes)
            n += 1
        self._update_info(save_note=f"saved all {n}")

    def _update_info(self, save_note=None):
        path = self.image_paths[self.index]
        label = self._label_path()
        exists = label.exists()
        self.file_var.set(f"{path.name}\n{self.img.size[0]}x{self.img.size[1]}\nlabel: {label.name}"
                          + ("" if exists else "  (no label yet)"))
        self.boxes_var.set(f"Boxes: {len(self.boxes)}")
        status = f"{self.index + 1}/{len(self.image_paths)}  |  {path.name}  |  boxes: {len(self.boxes)}"
        if save_note:
            status += f"  |  {save_note}"
        self.status_var.set(status)

    def _on_close(self):
        self.root.destroy()


def main():
    args = parse_args()
    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    if not classes:
        raise SystemExit("--classes must contain at least one class name")

    images_dir = Path(args.images_dir)
    labels_dir = Path(args.labels_dir)

    if not images_dir.exists():
        messagebox.showerror("Not found", f"Images directory does not exist:\n{images_dir}")
        sys.exit(1)

    root = tk.Tk()
    BBoxEditor(root, images_dir, labels_dir, classes)
    root.mainloop()


if __name__ == "__main__":
    main()
