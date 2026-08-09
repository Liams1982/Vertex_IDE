#!/usr/bin/env python3
# vertex_ide.py - Vertex IDE (Delphi-style form designer)
# Uses external VCL file (vcl.vtx) via Import.

import os
import sys
import json
import subprocess
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_NAME = "Vertex IDE"
APP_VERSION = "1.0"

CONFIG_FILE = "vertex_ide.json"
DEFAULT_CONFIG = {
    "vertexc_path": "vertexc",
    "gpp_path": "g++",
    "output_dir": ".",
    "static_linking": True,
    "gui_app": False,
    "theme": "dark",
    "auto_detect_gui": True,
    "sidebar_width": 250,
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Could not save config: {e}", file=sys.stderr)

# ---------- Tooltip ----------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hide_tip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.show_tip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", "8"))
        label.pack()

    def hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# ---------- Syntax highlighting, keywords, etc. ----------
KEYWORDS = {
    "Enter", "Exit", "Run", "Stop", "Import", "Const", "Type", "Var",
    "Func", "Proc", "Class", "Record", "Extends", "Private", "Public",
    "Virtual", "Override", "If", "Then", "Else", "For", "To", "Downto", "Do",
    "While", "Repeat", "Until", "With", "Attempt", "Recover", "Break", "Continue",
    "New", "Dispose", "Asm", "Absolute", "Print", "ReadLn", "SizeOf", "OffsetOf",
    "Array", "Of", "End", "And", "Or", "Xor", "Not", "Div", "Mod", "Shl", "Shr",
    "Constructor", "Destructor", "True", "False",
}
FLOW_KEYWORDS = {"Enter", "Run", "Stop", "Exit"}
TYPES = {
    "Integer", "Real", "Boolean", "String", "Char", "Byte",
    "HWND", "MSG", "WNDCLASSEX", "LRESULT", "UINT", "WPARAM", "LPARAM",
    "HINSTANCE", "HINST", "HMENU", "HDC", "RECT",
}

# Palette: (type_id, label, default_w, default_h, default_caption, icon)
PALETTE = [
    ("select", "Select", 0, 0, "", "↖"),
    ("button", "Button", 100, 32, "Button", "🔘"),
    ("edit", "Edit", 140, 28, "", "✏️"),
    ("label", "Label", 120, 20, "Label", "🏷️"),
    ("memo", "Memo", 180, 80, "", "📝"),
    ("checkbox", "CheckBox", 120, 24, "CheckBox", "☑️"),
    ("radio", "Radio", 120, 24, "Radio", "⭕"),
    ("listbox", "ListBox", 140, 100, "", "📋"),
    ("combo", "ComboBox", 140, 28, "", "🔽"),
    ("groupbox", "GroupBox", 200, 120, "Group", "📦"),
    ("panel", "Panel", 200, 100, "", "▭"),
    ("comport", "ComPort", 100, 28, "COM1", "🔌"),
]

# Named colors for the property dropdown (label, designer hex, (r,g,b))
COLOR_CHOICES = [
    ("(default)", "", None),
    ("White", "#ffffff", (255, 255, 255)),
    ("Ivory", "#fffff0", (255, 255, 240)),
    ("Snow", "#FFFAFA", (255, 250, 250)),
    ("Cream", "#fffdd0", (255, 253, 208)),
    ("Beige", "#f5f5dc", (245, 245, 220)),
    ("Light Gray", "#dcdcdc", (220, 220, 220)),
    ("Silver", "#c0c0c0", (192, 192, 192)),
    ("Gray", "#808080", (128, 128, 128)),
    ("Dim Gray", "#696969", (105, 105, 105)),
    ("Dark Gray", "#404040", (64, 64, 64)),
    ("Charcoal", "#2f2f2f", (47, 47, 47)),
    ("Black", "#000000", (0, 0, 0)),
    ("Red", "#ff0000", (255, 0, 0)),
    ("Crimson", "#dc143c", (220, 20, 60)),
    ("Scarlet", "#ff2400", (255, 36, 0)),
    ("Tomato", "#ff6347", (255, 99, 71)),
    ("Coral", "#ff7f50", (255, 127, 80)),
    ("Salmon", "#fa8072", (250, 128, 114)),
    ("Light Coral", "#f08080", (240, 128, 128)),
    ("Pink", "#ffc0cb", (255, 192, 203)),
    ("Hot Pink", "#ff69b4", (255, 105, 180)),
    ("Deep Pink", "#ff1493", (255, 20, 147)),
    ("Maroon", "#800000", (128, 0, 0)),
    ("Brown", "#8b4513", (139, 69, 19)),
    ("Sienna", "#a0522d", (160, 82, 45)),
    ("Chocolate", "#d2691e", (210, 105, 30)),
    ("Orange", "#ffa500", (255, 165, 0)),
    ("Dark Orange", "#ff8c00", (255, 140, 0)),
    ("Gold", "#ffd700", (255, 215, 0)),
    ("Yellow", "#ffff00", (255, 255, 0)),
    ("Khaki", "#f0e68c", (240, 230, 140)),
    ("Olive", "#808000", (128, 128, 0)),
    ("Lime", "#00ff00", (0, 255, 0)),
    ("Lime Green", "#32cd32", (50, 205, 50)),
    ("Spring Green", "#00ff7f", (0, 255, 127)),
    ("Light Green", "#90ee90", (144, 238, 144)),
    ("Pale Green", "#98fb98", (152, 251, 152)),
    ("Sea Green", "#2e8b57", (46, 139, 87)),
    ("Green", "#008000", (0, 128, 0)),
    ("Forest Green", "#228b22", (34, 139, 34)),
    ("Dark Green", "#006400", (0, 100, 0)),
    ("Olive Drab", "#6b8e23", (107, 142, 35)),
    ("Aqua", "#00ffff", (0, 255, 255)),
    ("Cyan", "#00ffff", (0, 255, 255)),
    ("Turquoise", "#40e0d0", (64, 224, 208)),
    ("Teal", "#008080", (0, 128, 128)),
    ("Sky", "#87ceeb", (135, 206, 235)),
    ("Light Blue", "#add8e6", (173, 216, 230)),
    ("Steel Blue", "#4682b4", (70, 130, 180)),
    ("Dodger Blue", "#1e90ff", (30, 144, 255)),
    ("Royal Blue", "#4169e1", (65, 105, 225)),
    ("Blue", "#0000ff", (0, 0, 255)),
    ("Medium Blue", "#0000cd", (0, 0, 205)),
    ("Navy", "#000080", (0, 0, 128)),
    ("Midnight Blue", "#191970", (25, 25, 112)),
    ("Lavender", "#e6e6fa", (230, 230, 250)),
    ("Plum", "#dda0dd", (221, 160, 221)),
    ("Orchid", "#da70d6", (218, 112, 214)),
    ("Fuchsia", "#ff00ff", (255, 0, 255)),
    ("Magenta", "#ff00ff", (255, 0, 255)),
    ("Violet", "#ee82ee", (238, 130, 238)),
    ("Blue Violet", "#8a2be2", (138, 43, 226)),
    ("Purple", "#800080", (128, 0, 128)),
    ("Indigo", "#4b0082", (75, 0, 130)),
]
COLOR_LABELS = [c[0] for c in COLOR_CHOICES]
COLOR_BY_LABEL = {c[0]: c for c in COLOR_CHOICES}
COLOR_BY_HEX = {c[1].lower(): c for c in COLOR_CHOICES if c[1]}


def color_label_from_stored(value: str) -> str:
    if not value:
        return "(default)"
    v = value.strip()
    if v in COLOR_BY_LABEL:
        return v
    low = v.lower()
    if low in COLOR_BY_HEX:
        return COLOR_BY_HEX[low][0]
    if not low.startswith("#") and len(low) == 6:
        low = "#" + low
        if low in COLOR_BY_HEX:
            return COLOR_BY_HEX[low][0]
    if low.startswith("#") and len(low) == 7:
        if low in COLOR_BY_HEX:
            return COLOR_BY_HEX[low][0]
        return low
    return "(default)"

def color_rgb_from_stored(value: str):
    if not value:
        return None
    v = value.strip()
    label = color_label_from_stored(v)
    entry = COLOR_BY_LABEL.get(label)
    if entry and entry[2] is not None:
        return entry[2]
    low = v.lower() if v.startswith("#") else label.lower()
    if low.startswith("#") and len(low) == 7:
        try:
            return (int(low[1:3], 16), int(low[3:5], 16), int(low[5:7], 16))
        except ValueError:
            return None
    return None

def color_hex_from_label(label: str) -> str:
    entry = COLOR_BY_LABEL.get(label)
    if entry:
        return entry[1] or ""
    if label and label.startswith("#") and len(label) == 7:
        return label.lower()
    return ""

def color_hex_from_rgb(r: int, g: int, b: int) -> str:
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    best = None
    best_dist = 10**9
    for label, hexv, rgb in COLOR_CHOICES:
        if not rgb:
            continue
        dr = rgb[0] - r
        dg = rgb[1] - g
        db = rgb[2] - b
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best = hexv
            if dist == 0:
                break
    if best_dist == 0 and best:
        return best
    return f"#{r:02x}{g:02x}{b:02x}"

THEMES = {
    "dark": {
        "bg": "#1e1e1e", "fg": "#d4d4d4", "insertbg": "#ffffff",
        "select_bg": "#264f78", "toolbar_bg": "#2d2d30", "toolbar_fg": "#cccccc",
        "btn_bg": "#3e3e42", "btn_fg": "#ffffff", "btn_active": "#505054",
        "status_bg": "#007acc", "status_fg": "#ffffff",
        "output_bg": "#1e1e1e", "output_fg": "#d4d4d4",
        "line_bg": "#252526", "line_fg": "#858585",
        "splash_bg": "#1e1e1e", "splash_fg": "#569cd6",
        "success": "#4ec9b0", "error": "#f44747",
        "palette_bg": "#2d2d30",
        "form_bg": "#dcdcdc",
        "form_border": "#6a6a6a",
        "prop_bg": "#2d2d30",
        "keyword": {"fg": "#569cd6", "bold": True},
        "flow": {"fg": "#ffffff", "bold": True},
        "type": {"fg": "#4ec9b0", "bold": False},
        "string": {"fg": "#ce9178"},
        "comment": {"fg": "#6a9955", "italic": True},
        "commentline": {"fg": "#6a9955", "italic": True},
        "number": {"fg": "#b5cea8"},
    },
    "light": {
        "bg": "#ffffff", "fg": "#1e1e1e", "insertbg": "#000000",
        "select_bg": "#add6ff", "toolbar_bg": "#f3f3f3", "toolbar_fg": "#333333",
        "btn_bg": "#d0d0d0", "btn_fg": "#1e1e1e", "btn_active": "#b0b0b0",
        "status_bg": "#0078d4", "status_fg": "#ffffff",
        "output_bg": "#f8f8f8", "output_fg": "#1e1e1e",
        "line_bg": "#f0f0f0", "line_fg": "#6e6e6e",
        "splash_bg": "#ffffff", "splash_fg": "#0078d4",
        "success": "#107c10", "error": "#d13438",
        "palette_bg": "#e8e8e8",
        "form_bg": "#dcdcdc",
        "form_border": "#808080",
        "prop_bg": "#f5f5f5",
        "keyword": {"fg": "#0000ff", "bold": True},
        "flow": {"fg": "#000000", "bold": True},
        "type": {"fg": "#2b91af", "bold": False},
        "string": {"fg": "#a31515"},
        "comment": {"fg": "#008000", "italic": True},
        "commentline": {"fg": "#008000", "italic": True},
        "number": {"fg": "#098658"},
    },
    "monokai": {
        "bg": "#272822", "fg": "#f8f8f2", "insertbg": "#ffffff",
        "select_bg": "#49483e", "toolbar_bg": "#3e3d32", "toolbar_fg": "#f8f8f2",
        "btn_bg": "#3e3d32", "btn_fg": "#f8f8f2", "btn_active": "#5e5d52",
        "status_bg": "#a6e22e", "status_fg": "#272822",
        "output_bg": "#272822", "output_fg": "#f8f8f2",
        "line_bg": "#3e3d32", "line_fg": "#75715e",
        "splash_bg": "#272822", "splash_fg": "#a6e22e",
        "success": "#a6e22e", "error": "#f92672",
        "palette_bg": "#3e3d32",
        "form_bg": "#dcdcdc",
        "form_border": "#75715e",
        "prop_bg": "#3e3d32",
        "keyword": {"fg": "#f92672", "bold": True},
        "flow": {"fg": "#ffffff", "bold": True},
        "type": {"fg": "#66d9ef", "bold": False},
        "string": {"fg": "#e6db74"},
        "comment": {"fg": "#75715e", "italic": True},
        "commentline": {"fg": "#75715e", "italic": True},
        "number": {"fg": "#ae81ff"},
    },
}

# ---------- Helpers ----------
def highlight(text_widget):
    end_pos = text_widget.index(tk.END)
    for tag in ("keyword", "flow", "type", "string", "comment", "commentline", "number"):
        text_widget.tag_remove(tag, "1.0", end_pos)
    content = text_widget.get("1.0", end_pos)
    if not content.strip():
        return
    lines = content.splitlines()
    in_comment = False
    for line_num, line in enumerate(lines, start=1):
        idx = 0
        line_len = len(line)
        if in_comment:
            while idx < line_len and line[idx] != "}":
                idx += 1
            if idx < line_len and line[idx] == "}":
                idx += 1
                in_comment = False
            text_widget.tag_add("comment", f"{line_num}.0", f"{line_num}.{idx}")
            if in_comment:
                continue
        while idx < line_len:
            ch = line[idx]
            start_pos = f"{line_num}.{idx}"
            if not in_comment and ch == '"':
                idx += 1
                while idx < line_len and line[idx] != '"':
                    idx += 1
                if idx < line_len and line[idx] == '"':
                    idx += 1
                text_widget.tag_add("string", start_pos, f"{line_num}.{idx}")
                continue
            if not in_comment and ch == "/" and idx + 1 < line_len and line[idx + 1] == "/":
                text_widget.tag_add("commentline", start_pos, f"{line_num}.{line_len}")
                break
            if not in_comment and ch == "{":
                while idx < line_len and line[idx] != "}":
                    idx += 1
                if idx < line_len and line[idx] == "}":
                    idx += 1
                    text_widget.tag_add("comment", start_pos, f"{line_num}.{idx}")
                    continue
                else:
                    text_widget.tag_add("comment", start_pos, f"{line_num}.{line_len}")
                    in_comment = True
                    break
            if not in_comment and ch.isdigit():
                while idx < line_len and (line[idx].isdigit() or line[idx] == "."):
                    idx += 1
                text_widget.tag_add("number", start_pos, f"{line_num}.{idx}")
                continue
            if not in_comment and (ch.isalpha() or ch == "_"):
                start = idx
                while idx < line_len and (line[idx].isalnum() or line[idx] == "_"):
                    idx += 1
                word = line[start:idx]
                end_p = f"{line_num}.{idx}"
                if word in FLOW_KEYWORDS:
                    text_widget.tag_add("flow", start_pos, end_p)
                elif word in KEYWORDS:
                    text_widget.tag_add("keyword", start_pos, end_p)
                elif word in TYPES:
                    text_widget.tag_add("type", start_pos, end_p)
                continue
            idx += 1

def looks_like_gui(source: str) -> bool:
    patterns = [
        r'Import\s*[<"]\s*windows\.h', r'Import\s*"vcl\.vtx"', r'Import\s*"vcl\.h"',
        r'\bHWND\b', r'\bCreateWindow\b', r'\bCreateWindowEx\b', r'\bGetMessage\b',
        r'\bWndProc\b', r'\bRunApp\s*\(', r'\bMessageBox\b',
        r'\bButton\s*\(', r'\bEdit\s*\(', r'\bLabel\s*\(',
    ]
    return any(re.search(p, source, re.IGNORECASE) for p in patterns)

def clean_run_env(gpp_path: str) -> dict:
    env = os.environ.copy()
    gpp_dir = os.path.dirname(os.path.abspath(gpp_path)) if gpp_path else ""
    windir = env.get("WINDIR", r"C:\Windows")
    parts = []
    if gpp_dir and os.path.isdir(gpp_dir):
        parts.append(gpp_dir)
    parts.append(os.path.join(windir, "System32"))
    parts.append(windir)
    for item in env.get("PATH", "").split(os.pathsep):
        if not item:
            continue
        low = item.replace("/", "\\").lower()
        if any(x in low for x in ("\\mingw32", "\\mingw64\\", "\\msys64\\usr\\", "\\msys2\\usr\\")):
            continue
        if "\\ucrt64\\" in low or "\\clang64\\" in low:
            if item not in parts:
                parts.append(item)
            continue
        if "windows" in low or "system32" in low:
            if item not in parts:
                parts.append(item)
    env["PATH"] = os.pathsep.join(parts)
    return env

def find_executable(exe_name: str, source_file: str, output_dir: str):
    candidates = []
    out_dir = os.path.abspath(output_dir or ".")
    candidates.append(os.path.join(out_dir, exe_name))
    if source_file:
        src_dir = os.path.dirname(os.path.abspath(source_file))
        candidates.append(os.path.join(src_dir, exe_name))
    candidates.append(os.path.join(os.getcwd(), exe_name))
    seen, unique = set(), []
    for c in candidates:
        ap = os.path.abspath(c)
        if ap not in seen:
            seen.add(ap)
            unique.append(ap)
    for path in unique:
        if os.path.isfile(path):
            return path, os.path.dirname(path)
    return None, None

# ---------- DesignControl ----------
class DesignControl:
    _counter = 0
    def __init__(self, ctype, x, y, w, h, caption="", color=""):
        DesignControl._counter += 1
        self.ctype = ctype
        self.name = f"{ctype}{DesignControl._counter}"
        self.x, self.y, self.w, self.h = x, y, w, h
        self.caption = caption if caption is not None else ""
        self.color = color if color is not None else ""
        self.widget = None
        self.selected = False

    def to_vtf(self):
        return f"{self.name}:{self.ctype}:{self.x}:{self.y}:{self.w}:{self.h}:{self.caption}:{self.color}"

    @staticmethod
    def from_vtf(line):
        parts = line.strip().split(':', 7)
        if len(parts) < 7:
            return None
        name, ctype, x, y, w, h, caption = parts[:7]
        color = parts[7] if len(parts) > 7 else ""
        ctrl = DesignControl(ctype, int(x), int(y), int(w), int(h), caption, color)
        ctrl.name = name
        return ctrl

# ---------- SplashScreen ----------
class SplashScreen(tk.Toplevel):
    def __init__(self, parent, theme_name="dark"):
        super().__init__(parent)
        self.overrideredirect(True)
        theme = THEMES.get(theme_name, THEMES["dark"])
        self.configure(bg=theme["splash_bg"])

        splash_width, splash_height = 300, 200
        self.image = None
        logo_path = os.path.join(os.getcwd(), "logo.jpg")
        has_image = False
        img = None
        scale = 0.25

        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path)
                w, h = img.size
                new_w = int(w * scale)
                new_h = int(h * scale)
                if new_w < 80:
                    new_w = 80
                if new_h < 60:
                    new_h = 60
                max_w = self.winfo_screenwidth() - 40
                max_h = self.winfo_screenheight() - 100
                if new_w > max_w or new_h > max_h:
                    ratio = min(max_w / new_w, max_h / new_h)
                    new_w = int(new_w * ratio)
                    new_h = int(new_h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                self.image = ImageTk.PhotoImage(img)
                has_image = True
                splash_width = new_w + 40
                splash_height = new_h + 80
            except Exception:
                pass

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{splash_width}x{splash_height}+{(sw - splash_width)//2}+{(sh - splash_height)//2}")

        if has_image and self.image:
            label = tk.Label(self, image=self.image, bg=theme["splash_bg"])
            label.place(x=20, y=20, width=new_w, height=new_h)
        else:
            tk.Frame(self, bg=theme["splash_fg"], height=4).pack(fill=tk.X, side=tk.TOP)
            tk.Label(self, text="VERTEX", font=("Segoe UI", 22, "bold"),
                     fg=theme["splash_fg"], bg=theme["splash_bg"]).pack(pady=(40,0))
            tk.Label(self, text="The Peak of Precision", font=("Segoe UI", 9),
                     fg=theme["toolbar_fg"], bg=theme["splash_bg"]).pack(pady=(4,10))

        self.progress = tk.Label(self, text="Loading…", font=("Segoe UI", 8),
                                 fg=theme["line_fg"], bg=theme["splash_bg"])
        self.progress.place(x=splash_width//2, y=splash_height-36, anchor=tk.CENTER)

        self.bar_frame = tk.Frame(self, bg=theme["line_bg"], height=6, width=min(300, splash_width-40))
        self.bar_frame.place(x=splash_width//2, y=splash_height-16, anchor=tk.CENTER)
        self.bar = tk.Frame(self.bar_frame, bg=theme["splash_fg"], width=0, height=6)
        self.bar.place(x=0, y=0, height=6)

        self.attributes("-topmost", True)
        self.update()

    def set_progress(self, value, text=None):
        value = max(0.0, min(1.0, value))
        bar_width = self.bar_frame.winfo_width()
        if bar_width < 10:
            bar_width = 300
        self.bar.place(width=int(bar_width * value))
        if text:
            self.progress.config(text=text)
        self.update()

# ---------- VertexIDE ----------
class VertexIDE:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.config = load_config()
        self.current_theme = self.config.get("theme", "dark")
        self.gui_mode = bool(self.config.get("gui_app", False))
        self.current_file = None
        self._last_exe_path = None
        self._highlight_job = None
        self.toolbar_buttons = []
        self.design_controls = []
        self.selected_control = None
        self.selected_form = False
        self.palette_tool = "select"
        self.form_title = "Form1"
        self.form_color = ""
        self.form_width = 480
        self.form_height = 320
        self._drag = None
        self._resize = None
        self._form_resize = None
        self.handle_size = 6
        self.show_grid = True
        self.grid_size = 5
        self._updating_form_size = False   # recursion guard

        try:
            from PIL import Image, ImageTk
            icon_path = os.path.join(os.getcwd(), "icone.ico")
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                img = img.resize((32, 32), Image.LANCZOS)
                icon = ImageTk.PhotoImage(img)
                self.root.iconphoto(False, icon)
                self.icon_image = icon
        except Exception:
            pass

        self.splash = SplashScreen(root, self.current_theme)
        self.root.after(100, self._boot)

    def _boot(self):
        steps = [(0.25,"Loading…"),(0.55,"Building interface…"),
                 (0.8,"Form designer…"),(1.0,"Done")]
        def run_steps(i=0):
            if i < len(steps):
                self.splash.set_progress(steps[i][0], steps[i][1])
                self.root.after(150, lambda: run_steps(i+1))
            else:
                self.root.after(180, self._finish_boot)
        run_steps()

    def _finish_boot(self):
        self.splash.destroy()
        self._build_ui()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _build_ui(self):
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1280x760")
        self.root.minsize(960, 600)
        theme = THEMES[self.current_theme]

        # Menubar
        menubar = tk.Menu(self.root, tearoff=0, bg=theme["toolbar_bg"],
                          fg=theme["toolbar_fg"], activebackground=theme["btn_active"])
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open…", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As…", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="Settings…", command=self.settings_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        form_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        form_menu.add_command(label="New Form", command=self.new_form)
        form_menu.add_command(label="Generate VCL Code", command=lambda: self.generate_vcl_code(switch_to_code=True))
        form_menu.add_command(label="Clear Form", command=self.clear_form)
        form_menu.add_command(label="Sync from Code", command=self.sync_from_code)
        menubar.add_cascade(label="Form", menu=form_menu)

        view_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        self.theme_var = tk.StringVar(value=self.current_theme)
        for name in THEMES:
            view_menu.add_radiobutton(label=name.capitalize(), variable=self.theme_var,
                                      value=name, command=lambda t=name: self.switch_theme(t))
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        help_menu.add_command(label="Documentation…", command=self.open_documentation)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=help_menu)

        # Toolbar
        self.toolbar = tk.Frame(self.root, height=44, bg=theme["toolbar_bg"])
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.toolbar.pack_propagate(False)

        brand = tk.Frame(self.toolbar, bg=theme["toolbar_bg"])
        brand.pack(side=tk.LEFT, padx=(8, 4), pady=4)
        self._brand_icon = None
        try:
            from PIL import Image, ImageTk
            icon_path = os.path.join(os.getcwd(), "icon.jpg")
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                img = img.resize((28, 28), Image.LANCZOS)
                self._brand_icon = ImageTk.PhotoImage(img)
                tk.Label(brand, image=self._brand_icon, bg=theme["toolbar_bg"]).pack(side=tk.LEFT, padx=(0, 6))
        except Exception:
            pass
        tk.Label(brand, text=f"{APP_NAME}  v{APP_VERSION}", font=("Segoe UI", 11, "bold"),
                 fg=theme["splash_fg"], bg=theme["toolbar_bg"]).pack(side=tk.LEFT)

        tk.Frame(self.toolbar, width=1, bg=theme.get("form_border", "#555555")).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)

        self._make_toolbar_buttons(theme)

        # Status + output
        bottom = tk.Frame(self.root, bg=theme["toolbar_bg"])
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        status_row = tk.Frame(bottom, bg=theme["status_bg"], height=26)
        status_row.pack(side=tk.TOP, fill=tk.X)
        status_row.pack_propagate(False)
        self.status_label = tk.Label(status_row, text=f"Ready  |  {APP_NAME} v{APP_VERSION}", anchor=tk.W,
                                     bg=theme["status_bg"], fg=theme["status_fg"],
                                     font=("Segoe UI", 9), padx=10)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cursor_label = tk.Label(status_row, text="Ln 1, Col 1", anchor=tk.E,
                                     bg=theme["status_bg"], fg=theme["status_fg"],
                                     font=("Segoe UI", 9), padx=10, width=16)
        self.cursor_label.pack(side=tk.RIGHT)
        self.output_text = scrolledtext.ScrolledText(
            bottom, height=7, font=("Consolas", 9), relief=tk.FLAT, bd=0, padx=8, pady=5,
            bg=theme["output_bg"], fg=theme["output_fg"])
        self.output_text.pack(side=tk.BOTTOM, fill=tk.X)
        self.output_text.config(state=tk.DISABLED)
        self.output_text.tag_config("success", foreground=theme["success"])
        self.output_text.tag_config("error", foreground=theme["error"])
        self.output_text.tag_config("info", foreground=theme["toolbar_fg"])

        # Main paned
        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6,
                                        bg=theme["toolbar_bg"], sashrelief=tk.FLAT,
                                        sashpad=1)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        center = tk.Frame(self.main_pane, bg=theme["bg"])
        self.main_pane.add(center, stretch="always", minsize=420)

        self.notebook = ttk.Notebook(center)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Code tab
        code_tab = tk.Frame(self.notebook, bg=theme["bg"])
        self.notebook.add(code_tab, text="  Code  ")
        editor_frame = tk.Frame(code_tab, bg=theme["bg"])
        editor_frame.pack(fill=tk.BOTH, expand=True)

        self.vscroll = tk.Scrollbar(editor_frame, orient=tk.VERTICAL)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.line_numbers = tk.Text(
            editor_frame, width=5, padx=6, takefocus=0, border=0,
            background=theme["line_bg"], foreground=theme["line_fg"],
            state="disabled", font=("Consolas", 12), yscrollcommand=self._on_line_scroll)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = tk.Text(
            editor_frame, undo=True, font=("Consolas", 12), relief=tk.FLAT, bd=0,
            padx=12, pady=8, wrap=tk.NONE, background=theme["bg"], foreground=theme["fg"],
            insertbackground=theme["insertbg"], selectbackground=theme["select_bg"],
            yscrollcommand=self._on_editor_scroll, exportselection=False)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vscroll.config(command=self._on_scrollbar)
        self._configure_tags(theme)

        self.editor.bind("<KeyRelease>", self._on_key_release)
        self.editor.bind("<ButtonRelease-1>", self._on_cursor_move)
        self.editor.bind("<MouseWheel>", self._on_mousewheel)
        self.editor.bind("<Button-4>", self._on_mousewheel)
        self.editor.bind("<Button-5>", self._on_mousewheel)
        self.editor.bind("<<Modified>>", self._on_modified)

        # Design tab
        design_tab = tk.Frame(self.notebook, bg=theme["toolbar_bg"])
        self.notebook.add(design_tab, text="  Form Designer  ")
        self.design_tab_index = self.notebook.index(design_tab)

        design_top = tk.Frame(design_tab, bg=theme["toolbar_bg"], height=28)
        design_top.pack(side=tk.TOP, fill=tk.X)

        # Form Title
        tk.Label(design_top, text="Form:", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(8,2))
        self.form_title_var = tk.StringVar(value=self.form_title)
        self.form_title_var.trace_add("write", lambda *args: self._apply_form_size())
        title_entry = tk.Entry(design_top, textvariable=self.form_title_var, width=16,
                               bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        title_entry.pack(side=tk.LEFT, padx=2)
        title_entry.bind("<Return>", lambda e: self._apply_form_size())
        title_entry.bind("<FocusOut>", lambda e: self._apply_form_size())

        # Width
        tk.Label(design_top, text="W:", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"]).pack(side=tk.LEFT, padx=(8,0))
        self.form_w_var = tk.StringVar(value=str(self.form_width))
        self.form_w_var.trace_add("write", lambda *args: self._apply_form_size())
        w_entry = tk.Entry(design_top, textvariable=self.form_w_var, width=5,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        w_entry.pack(side=tk.LEFT)
        w_entry.bind("<Return>", lambda e: self._apply_form_size())
        w_entry.bind("<FocusOut>", lambda e: self._apply_form_size())

        # Height
        tk.Label(design_top, text="H:", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"]).pack(side=tk.LEFT)
        self.form_h_var = tk.StringVar(value=str(self.form_height))
        self.form_h_var.trace_add("write", lambda *args: self._apply_form_size())
        h_entry = tk.Entry(design_top, textvariable=self.form_h_var, width=5,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        h_entry.pack(side=tk.LEFT)
        h_entry.bind("<Return>", lambda e: self._apply_form_size())
        h_entry.bind("<FocusOut>", lambda e: self._apply_form_size())

        # Apply button (kept for convenience)
        tk.Button(design_top, text="✓ Apply", command=self._apply_form_size,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=6)

        # Grid & Sync
        tk.Button(design_top, text="▦ Grid", command=self.toggle_grid,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=6)
        tk.Button(design_top, text="↻ Sync", command=self.sync_from_code,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=6)
        ToolTip(design_top.winfo_children()[-1], "Sync form from code")

        canvas_holder = tk.Frame(design_tab, bg="#808080")
        canvas_holder.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.form_canvas = tk.Canvas(canvas_holder, bg=theme["form_bg"],
                                     highlightthickness=2, highlightbackground=theme["form_border"],
                                     width=self.form_width, height=self.form_height)
        self.form_canvas.pack(anchor=tk.NW)
        self.form_canvas.bind("<Button-1>", self._form_click)
        self.form_canvas.bind("<Double-Button-1>", self._form_double_click)
        self.form_canvas.bind("<B1-Motion>", self._form_drag)
        self.form_canvas.bind("<ButtonRelease-1>", self._form_release)

        # Right panel (sidebar ~250px default)
        sidebar_w = int(self.config.get("sidebar_width", 250) or 250)
        right = tk.Frame(self.main_pane, bg=theme["palette_bg"], width=sidebar_w)
        self.main_pane.add(right, minsize=220, width=sidebar_w)
        right_split = tk.PanedWindow(right, orient=tk.VERTICAL, sashwidth=5,
                                     bg=theme["toolbar_bg"], sashrelief=tk.FLAT)
        right_split.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Palette
        self.palette = tk.Frame(right_split, bg=theme["palette_bg"])
        right_split.add(self.palette, minsize=160)
        tk.Label(self.palette, text="  Standard", bg=theme["palette_bg"], fg=theme["splash_fg"],
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 6), padx=8, anchor=tk.W)

        grid_frame = tk.Frame(self.palette, bg=theme["palette_bg"])
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.palette_btns = {}
        row = 0
        col = 0
        for ctype, label, dw, dh, cap, icon in PALETTE:
            b = tk.Button(
                grid_frame,
                text=f"{icon}\n{label}",
                bg=theme["btn_bg"], fg=theme["btn_fg"],
                activebackground=theme["btn_active"],
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                padx=4, pady=4,
                width=8, height=3,
                justify=tk.CENTER,
                command=lambda t=ctype: self._select_tool(t)
            )
            b.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            self.palette_btns[ctype] = b
            col += 1
            if col >= 4:
                col = 0
                row += 1

        for c in range(4):
            grid_frame.columnconfigure(c, weight=1)

        # Separator
        tk.Frame(self.palette, height=4, bg=theme["form_border"]).pack(fill=tk.X, padx=6, pady=4)

        # Action buttons
        tk.Button(self.palette, text="🗔 New Form", command=self.new_form,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  font=("Segoe UI",9), padx=8, pady=5).pack(fill=tk.X, padx=6, pady=2)
        tk.Button(self.palette, text="⚙ Generate Code", command=lambda: self.generate_vcl_code(switch_to_code=True),
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  font=("Segoe UI",9), padx=8, pady=5).pack(fill=tk.X, padx=6, pady=2)
        tk.Button(self.palette, text="🗑 Clear Form", command=self.clear_form,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  font=("Segoe UI",9), padx=8, pady=5).pack(fill=tk.X, padx=6, pady=2)

        # Component Editor
        comp_outer = tk.Frame(right_split, bg=theme["prop_bg"])
        right_split.add(comp_outer, minsize=200)
        tk.Label(comp_outer, text="Component Editor", bg=theme["prop_bg"],
                 fg=theme["splash_fg"], font=("Segoe UI", 10, "bold")).pack(
                     pady=(8, 2), padx=6, anchor=tk.W)

        comp_scroll = tk.Scrollbar(comp_outer, orient=tk.VERTICAL)
        comp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.comp_canvas = tk.Canvas(comp_outer, bg=theme["prop_bg"], highlightthickness=0,
                                     yscrollcommand=comp_scroll.set)
        self.comp_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        comp_scroll.config(command=self.comp_canvas.yview)

        self.comp_editor = tk.Frame(self.comp_canvas, bg=theme["prop_bg"])
        self._comp_win = self.comp_canvas.create_window((0, 0), window=self.comp_editor, anchor=tk.NW)

        def _sync_comp_scroll(event=None):
            self.comp_canvas.configure(scrollregion=self.comp_canvas.bbox("all"))
            try:
                self.comp_canvas.itemconfigure(self._comp_win, width=self.comp_canvas.winfo_width())
            except Exception:
                pass

        self.comp_editor.bind("<Configure>", _sync_comp_scroll)
        self.comp_canvas.bind("<Configure>",
            lambda e: self.comp_canvas.itemconfigure(self._comp_win, width=max(e.width, 180)))

        def _comp_wheel(event):
            if event.delta:
                self.comp_canvas.yview_scroll(int(-event.delta / 120), "units")
            elif getattr(event, "num", None) == 4:
                self.comp_canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                self.comp_canvas.yview_scroll(3, "units")

        self.comp_canvas.bind("<MouseWheel>", _comp_wheel)
        self.comp_canvas.bind("<Button-4>", _comp_wheel)
        self.comp_canvas.bind("<Button-5>", _comp_wheel)
        self.comp_editor.bind("<MouseWheel>", _comp_wheel)
        self.comp_editor.bind("<Button-4>", _comp_wheel)
        self.comp_editor.bind("<Button-5>", _comp_wheel)

        self.comp_sel_label = tk.Label(self.comp_editor, text="(none selected)",
                                       bg=theme["prop_bg"], fg=theme["line_fg"],
                                       font=("Segoe UI", 8), anchor=tk.W)
        self.comp_sel_label.pack(fill=tk.X, padx=8, pady=(0, 4))

        self.prop_vars = {}
        prop_fields = [("name","Name"),("caption","Caption"),("left","Left"),
                       ("top","Top"),("width","Width"),("height","Height")]
        for key, lab in prop_fields:
            row = tk.Frame(self.comp_editor, bg=theme["prop_bg"])
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=lab, width=8, anchor=tk.W, bg=theme["prop_bg"],
                     fg=theme["line_fg"], font=("Segoe UI",8)).pack(side=tk.LEFT)
            var = tk.StringVar()
            self.prop_vars[key] = var
            e = tk.Entry(row, textvariable=var, bg=theme["btn_bg"], fg=theme["btn_fg"],
                         relief=tk.FLAT, font=("Segoe UI",9))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            e.bind("<Return>", lambda ev: self._apply_props())
            e.bind("<FocusOut>", lambda ev: self._apply_props())

        # Color picker
        color_row = tk.Frame(self.comp_editor, bg=theme["prop_bg"])
        color_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(color_row, text="Color", width=8, anchor=tk.W, bg=theme["prop_bg"],
                 fg=theme["line_fg"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.prop_vars["color"] = tk.StringVar(value="(default)")
        self.color_swatch = tk.Canvas(color_row, width=18, height=18, highlightthickness=1,
                                      highlightbackground=theme["form_border"], bg="#dcdcdc")
        self.color_swatch.pack(side=tk.LEFT, padx=(0, 4))
        self.color_btn = tk.Button(
            color_row, text="(default)  ▼", anchor=tk.W,
            bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
            font=("Segoe UI", 9), command=self._open_color_picker
        )
        self.color_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._color_popup = None
        self._refresh_color_swatch()

        btn_row = tk.Frame(self.comp_editor, bg=theme["prop_bg"])
        btn_row.pack(fill=tk.X, padx=6, pady=8)
        tk.Button(btn_row, text="✓ Apply", command=self._apply_props,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="🗑 Delete", command=self._delete_selected,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="⚡ Event", command=self._goto_default_event,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                  padx=10).pack(side=tk.LEFT, padx=2)

        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<F5>", lambda e: self.compile_file())
        self.root.bind("<F6>", lambda e: self.run_program())
        self.root.bind("<Delete>", lambda e: self._delete_selected())

        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])
        else:
            self.new_file()
        self.update_line_numbers()
        self.update_cursor_position()
        self._update_ui_mode()
        self.root.after(80, self._place_sidebar_sash)

    def _refresh_color_swatch(self):
        if not hasattr(self, "color_swatch"):
            return
        label = self.prop_vars.get("color").get() if self.prop_vars.get("color") else "(default)"
        entry = COLOR_BY_LABEL.get(label)
        hexv = entry[1] if entry and entry[1] else None
        theme = THEMES[self.current_theme]
        bg = hexv if hexv else theme.get("form_bg", "#dcdcdc")
        try:
            self.color_swatch.configure(bg=bg)
            self.color_swatch.delete("all")
            if not hexv:
                self.color_swatch.create_line(3, 3, 15, 15, fill="#888")
                self.color_swatch.create_line(15, 3, 3, 15, fill="#888")
        except Exception:
            pass
        if hasattr(self, "color_btn"):
            self.color_btn.config(text=f"{label}  ▼")

    def _set_color_choice(self, label):
        self.prop_vars["color"].set(label)
        self._refresh_color_swatch()
        if self._color_popup is not None:
            try:
                self._color_popup.destroy()
            except Exception:
                pass
            self._color_popup = None
        self._apply_props()

    def _open_color_picker(self):
        if self._color_popup is not None:
            try:
                self._color_popup.destroy()
            except Exception:
                pass
            self._color_popup = None
            return

        theme = THEMES[self.current_theme]
        pop = tk.Toplevel(self.root)
        pop.wm_overrideredirect(True)
        pop.configure(bg=theme.get("form_border", "#666666"))
        self._color_popup = pop

        pop_w, pop_h = 260, 320
        try:
            bx = self.color_btn.winfo_rootx()
            by = self.color_btn.winfo_rooty() + self.color_btn.winfo_height() + 2
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            if bx + pop_w > sw - 8:
                bx = max(8, sw - pop_w - 8)
            if by + pop_h > sh - 40:
                by = max(8, self.color_btn.winfo_rooty() - pop_h - 2)
            if bx < 8:
                bx = 8
            pop.geometry(f"{pop_w}x{pop_h}+{bx}+{by}")
        except Exception:
            pop.geometry(f"{pop_w}x{pop_h}+200+200")

        outer = tk.Frame(pop, bg=theme["prop_bg"], highlightthickness=1,
                         highlightbackground=theme.get("form_border", "#666"))
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Label(outer, text="Choose color", anchor=tk.W,
                          bg=theme["prop_bg"], fg=theme.get("splash_fg", theme["btn_fg"]),
                          font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        header.pack(fill=tk.X)

        list_frame = tk.Frame(outer, bg=theme["prop_bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

        scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(list_frame, bg=theme["prop_bg"], highlightthickness=0,
                           yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=canvas.yview)

        inner = tk.Frame(canvas, bg=theme["prop_bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def _sync_scroll(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            try:
                canvas.itemconfigure(win_id, width=canvas.winfo_width())
            except Exception:
                pass

        inner.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=max(e.width, 200)))

        def _wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        for w in (pop, outer, list_frame, canvas, inner):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)

        current = self.prop_vars["color"].get()
        for label, hexv, rgb in COLOR_CHOICES:
            row = tk.Frame(inner, bg=theme["prop_bg"], cursor="hand2")
            row.pack(fill=tk.X, padx=2, pady=1)

            sw = tk.Canvas(row, width=22, height=16, highlightthickness=1,
                           highlightbackground="#666666")
            if hexv:
                sw.configure(bg=hexv)
            else:
                sw.configure(bg=theme["prop_bg"])
                sw.create_line(2, 2, 20, 14, fill="#888")
                sw.create_line(20, 2, 2, 14, fill="#888")
            sw.pack(side=tk.LEFT, padx=(6, 8), pady=3)

            font = ("Segoe UI", 9, "bold") if label == current else ("Segoe UI", 9)
            lbl = tk.Label(row, text=label, anchor=tk.W, bg=theme["prop_bg"],
                           fg=theme["btn_fg"], font=font)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            def bind_pick(widget, name=label):
                widget.bind("<Button-1>", lambda e, n=name: self._set_color_choice(n))
                widget.bind("<MouseWheel>", _wheel)
                widget.bind("<Button-4>", _wheel)
                widget.bind("<Button-5>", _wheel)

            hover_bg = theme.get("btn_active", "#505054")
            base_bg = theme["prop_bg"]

            def on_enter(e, r=row, hb=hover_bg):
                r.configure(bg=hb)
                for ch in r.winfo_children():
                    if isinstance(ch, tk.Label):
                        ch.configure(bg=hb)

            def on_leave(e, r=row, bb=base_bg):
                r.configure(bg=bb)
                for ch in r.winfo_children():
                    if isinstance(ch, tk.Label):
                        ch.configure(bg=bb)

            for w in (row, sw, lbl):
                bind_pick(w)
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

        def _close(event=None):
            if self._color_popup is not None:
                try:
                    self._color_popup.destroy()
                except Exception:
                    pass
                self._color_popup = None

        pop.bind("<Escape>", _close)
        pop.after(100, lambda: self._safe_grab(pop))
        pop.focus_force()
        _sync_scroll()

    def _safe_grab(self, pop):
        try:
            if pop.winfo_exists():
                pop.grab_set_global()
        except Exception:
            try:
                pop.grab_set()
            except Exception:
                pass

    def _place_sidebar_sash(self):
        try:
            if not hasattr(self, "main_pane"):
                return
            self.root.update_idletasks()
            total = self.main_pane.winfo_width()
            if total < 200:
                return
            sidebar_w = int(self.config.get("sidebar_width", 250) or 250)
            pos = max(400, total - sidebar_w)
            self.main_pane.sash_place(0, pos, 0)
        except Exception:
            pass

    # ---------- UI mode ----------
    def _update_ui_mode(self):
        source = self.editor.get("1.0","end-1c") if hasattr(self,"editor") else ""
        auto = self.config.get("auto_detect_gui", True)
        use_gui = self.gui_mode if not auto else (self.gui_mode or looks_like_gui(source))
        if hasattr(self,"mode_btn"):
            self.mode_btn.config(text="GUI" if use_gui else "Console")
        if hasattr(self,"notebook") and hasattr(self,"design_tab_index"):
            if use_gui:
                self.notebook.tab(self.design_tab_index, state="normal")
            else:
                self.notebook.tab(self.design_tab_index, state="hidden")
        if self.config.get("gui_app") != use_gui:
            self.config["gui_app"] = use_gui
            save_config(self.config)

    # ---------- Toolbar ----------
    def _make_toolbar_buttons(self, theme):
        for w in self.toolbar.winfo_children():
            w.destroy()
        self.toolbar_buttons.clear()
        style = dict(bg=theme["btn_bg"], fg=theme["btn_fg"], activebackground=theme["btn_active"],
                     relief=tk.FLAT, borderwidth=0, padx=10, pady=5, font=("Segoe UI",9), cursor="hand2")
        def add(text, cmd, tip=None):
            b = tk.Button(self.toolbar, text=text, command=cmd, **style)
            b.pack(side=tk.LEFT, padx=2, pady=4)
            self.toolbar_buttons.append(b)
            if tip:
                b.bind("<Enter>", lambda e,t=tip: self.status(t))
                b.bind("<Leave>", lambda e: self.status("Ready"))
                ToolTip(b, tip)
            return b

        add("⚙ Compile", self.compile_file, "Compile (F5)")
        add("▶ Run", self.run_program, "Run (F6)")
        add("📁 Folder", self.show_folder, "Open output folder")
        tk.Frame(self.toolbar, width=6, bg=theme["toolbar_bg"]).pack(side=tk.LEFT)
        add("📄 New", self.new_file, "New file (Ctrl+N)")
        add("📂 Open", self.open_file, "Open file (Ctrl+O)")
        add("💾 Save", self.save_file, "Save (Ctrl+S)")
        tk.Frame(self.toolbar, width=6, bg=theme["toolbar_bg"]).pack(side=tk.LEFT)
        add("🗔 New Form", self.new_form, "Create a blank form")
        add("⚙ Gen Code", lambda: self.generate_vcl_code(switch_to_code=True), "Generate Vertex VCL from form")
        add("↻ Sync", self.sync_from_code, "Sync form from code")
        tk.Frame(self.toolbar, width=6, bg=theme["toolbar_bg"]).pack(side=tk.LEFT)
        self.mode_btn = add("GUI" if self.gui_mode else "Console", self.toggle_mode,
                            "Toggle GUI / Console")
        tk.Label(self.toolbar, text=f" {self.current_theme.capitalize()} ",
                 bg=theme["toolbar_bg"], fg=theme["line_fg"], font=("Segoe UI",8)).pack(side=tk.RIGHT, padx=6)

    def _configure_tags(self, theme):
        self.editor.tag_config("keyword", foreground=theme["keyword"]["fg"],
                               font=("Consolas",12,"bold" if theme["keyword"].get("bold") else "normal"))
        self.editor.tag_config("flow", foreground=theme["flow"]["fg"], font=("Consolas",12,"bold"))
        self.editor.tag_config("type", foreground=theme["type"]["fg"])
        self.editor.tag_config("string", foreground=theme["string"]["fg"])
        self.editor.tag_config("comment", foreground=theme["comment"]["fg"],
                               font=("Consolas",11,"italic"))
        self.editor.tag_config("commentline", foreground=theme["commentline"]["fg"],
                               font=("Consolas",11,"italic"))
        self.editor.tag_config("number", foreground=theme["number"]["fg"])

    # ---------- Grid ----------
    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self._redraw_all()
        self.status(f"Grid {'on' if self.show_grid else 'off'}")

    def _draw_grid(self):
        w = self.form_width
        h = self.form_height
        gs = self.grid_size
        for x in range(0, w, gs):
            for y in range(0, h, gs):
                self.form_canvas.create_rectangle(x, y, x+1, y+1, fill="#888888", outline="")

    # ---------- Redraw ----------
    def _ctrl_tag(self, ctrl):
        return f"c_{id(ctrl)}"

    def _redraw_all(self):
        self.form_canvas.delete("all")
        if self.show_grid:
            self._draw_grid()
        for c in self.design_controls:
            self._draw_control(c)
        if self.selected_control:
            self._draw_resize_handles(self.selected_control)
        if self.selected_form:
            self._draw_form_handles()

    def _redraw_control_only(self, ctrl):
        """Redraw a single control and its handles (fast path for resize)."""
        if not ctrl:
            return
        self.form_canvas.delete(self._ctrl_tag(ctrl))
        self.form_canvas.delete("handle")
        self._draw_control(ctrl)
        if ctrl.selected:
            self._draw_resize_handles(ctrl)

    def _move_control_visual(self, ctrl, dx, dy):
        """Move canvas items for one control without full redraw."""
        if not ctrl or (dx == 0 and dy == 0):
            return
        tag = self._ctrl_tag(ctrl)
        self.form_canvas.move(tag, dx, dy)
        if ctrl.selected:
            self.form_canvas.delete("handle")
            self._draw_resize_handles(ctrl)

    # ---------- Resize handles for controls ----------
    def _draw_resize_handles(self, ctrl):
        x, y, w, h = ctrl.x, ctrl.y, ctrl.w, ctrl.h
        hs = self.handle_size
        handles = [
            (x, y, "nw"), (x + w//2, y, "n"), (x + w, y, "ne"),
            (x, y + h//2, "w"), (x + w, y + h//2, "e"),
            (x, y + h, "sw"), (x + w//2, y + h, "s"), (x + w, y + h, "se")
        ]
        for hx, hy, tag in handles:
            self.form_canvas.create_rectangle(hx - hs//2, hy - hs//2, hx + hs//2, hy + hs//2,
                                              fill="#0078d4", outline="#ffffff", tags=("handle", tag))

    def _start_resize(self, ctrl, handle, event):
        self._resize = (ctrl, handle, event.x, event.y, ctrl.x, ctrl.y, ctrl.w, ctrl.h)
        self.form_canvas.config(cursor="sizing")

    def _resize_drag(self, event):
        if not self._resize:
            return
        ctrl, handle, ox, oy, orig_x, orig_y, orig_w, orig_h = self._resize
        dx = event.x - ox
        dy = event.y - oy
        new_x, new_y, new_w, new_h = orig_x, orig_y, orig_w, orig_h
        if handle in ("nw","n","ne"):
            new_y = orig_y + dy
            new_h = orig_h - dy
            if handle in ("nw","ne"):
                new_x = orig_x + dx
                new_w = orig_w - dx
        if handle in ("sw","s","se"):
            new_h = orig_h + dy
            if handle in ("sw","se"):
                new_w = orig_w + dx
                if handle == "sw":
                    new_x = orig_x + dx
                    new_w = orig_w - dx
        if handle in ("w","e"):
            new_w = orig_w + dx
            if handle == "w":
                new_x = orig_x + dx
        if handle == "e":
            new_w = orig_w + dx
        if new_w < 10: new_w = 10
        if new_h < 10: new_h = 10
        ctrl.x, ctrl.y, ctrl.w, ctrl.h = new_x, new_y, new_w, new_h
        self._redraw_control_only(ctrl)
        if "left" in self.prop_vars:
            self.prop_vars["left"].set(str(ctrl.x))
            self.prop_vars["top"].set(str(ctrl.y))
            self.prop_vars["width"].set(str(ctrl.w))
            self.prop_vars["height"].set(str(ctrl.h))

    def _resize_release(self, event):
        if self._resize:
            self._resize = None
            self.form_canvas.config(cursor="arrow")
            if self.selected_control:
                ctrl = self.selected_control
                # Cancel any pending timer from drag
                if hasattr(self, "_update_timer") and self._update_timer:
                    self.root.after_cancel(self._update_timer)
                    self._update_timer = None
                # Update code immediately
                self._update_code_for_property(ctrl, "left", ctrl.x)

    # ---------- Form resize handles ----------
    def _draw_form_handles(self):
        x, y = 0, 0
        w, h = self.form_width, self.form_height
        hs = self.handle_size
        handles = [
            (x, y, "nw"), (x + w//2, y, "n"), (x + w, y, "ne"),
            (x, y + h//2, "w"), (x + w, y + h//2, "e"),
            (x, y + h, "sw"), (x + w//2, y + h, "s"), (x + w, y + h, "se")
        ]
        for hx, hy, tag in handles:
            self.form_canvas.create_rectangle(hx - hs//2, hy - hs//2, hx + hs//2, hy + hs//2,
                                              fill="#ff0000", outline="#ffffff", tags=("form_handle", tag))

    def _start_form_resize(self, handle, event):
        self._form_resize = (handle, event.x, event.y, self.form_width, self.form_height)
        self.form_canvas.config(cursor="sizing")

    def _form_resize_drag(self, event):
        if not self._form_resize:
            return
        handle, ox, oy, orig_w, orig_h = self._form_resize
        dx = event.x - ox
        dy = event.y - oy
        new_w, new_h = orig_w, orig_h
        if handle in ("nw","n","ne"):
            new_h = orig_h - dy
        if handle in ("sw","s","se"):
            new_h = orig_h + dy
        if handle in ("nw","w","sw"):
            new_w = orig_w - dx
        if handle in ("ne","e","se"):
            new_w = orig_w + dx
        if new_w < 100: new_w = 100
        if new_h < 80: new_h = 80
        self.form_width, self.form_height = new_w, new_h
        self.form_canvas.config(width=self.form_width, height=self.form_height)
        self.form_w_var.set(str(new_w))
        self.form_h_var.set(str(new_h))
        self._redraw_all()

    def _form_resize_release(self, event):
        if self._form_resize:
            self._form_resize = None
            self.form_canvas.config(cursor="arrow")
            self._apply_form_size()

    # ---------- Designer ----------
    def _select_tool(self, ctype):
        self.palette_tool = ctype
        theme = THEMES[self.current_theme]
        for t,b in self.palette_btns.items():
            if t == ctype:
                b.config(bg=theme["splash_fg"], fg="#ffffff")
            else:
                b.config(bg=theme["btn_bg"], fg=theme["btn_fg"])
        self.status(f"Tool: {ctype}")

    def new_form(self):
        self.clear_form()
        self.form_title = "Form1"
        self.form_color = ""
        self.form_title_var.set(self.form_title)
        self.form_width, self.form_height = 480, 320
        self.form_w_var.set("480")
        self.form_h_var.set("320")
        self._apply_form_size()
        self.notebook.select(self.design_tab_index)
        self.gui_mode = True
        self.config["gui_app"] = True
        self.config["auto_detect_gui"] = True
        save_config(self.config)
        if hasattr(self,"mode_btn"):
            self.mode_btn.config(text="GUI")
        self._update_ui_mode()
        self.status("New form ready - pick a control, click on the form to place it")

    def clear_form(self):
        for c in self.design_controls:
            if c.widget:
                if isinstance(c.widget,(list,tuple)):
                    for i in c.widget:
                        self.form_canvas.delete(i)
                else:
                    self.form_canvas.delete(c.widget)
        self.design_controls.clear()
        self.selected_control = None
        self.selected_form = False
        DesignControl._counter = 0
        self.form_canvas.delete("all")
        self.status("Form cleared")
        self.comp_sel_label.config(text="(none selected)")
        for k in self.prop_vars:
            self.prop_vars[k].set("")

    def _apply_form_size(self):
        if self._updating_form_size:
            return
        self._updating_form_size = True
        try:
            try:
                new_w = max(100, int(self.form_w_var.get()))
                new_h = max(80, int(self.form_h_var.get()))
            except ValueError:
                return
            new_title = self.form_title_var.get().strip() or "Form1"

            changed = False

            if new_title != self.form_title:
                self.form_title = new_title
                self._update_form_code("title", new_title)
                changed = True

            if new_w != self.form_width or new_h != self.form_height:
                self.form_width = new_w
                self.form_height = new_h
                self.form_canvas.config(width=self.form_width, height=self.form_height)
                self._update_form_code("size", None)
                changed = True

            if self.selected_form:
                self._load_form_props()

            self._redraw_all()
            if changed:
                self.status("Form properties updated")
        finally:
            self._updating_form_size = False

    def _form_click(self, event):
        items = self.form_canvas.find_overlapping(event.x-5, event.y-5, event.x+5, event.y+5)
        for item in items:
            tags = self.form_canvas.gettags(item)
            if "form_handle" in tags:
                for tag in tags:
                    if tag in ("nw","n","ne","w","e","sw","s","se"):
                        self._start_form_resize(tag, event)
                        return
        items = self.form_canvas.find_overlapping(event.x-5, event.y-5, event.x+5, event.y+5)
        for item in items:
            tags = self.form_canvas.gettags(item)
            if "handle" in tags:
                for tag in tags:
                    if tag in ("nw","n","ne","w","e","sw","s","se"):
                        if self.selected_control:
                            self._start_resize(self.selected_control, tag, event)
                            return

        tool = self.palette_tool
        if tool == "select":
            hit = None
            for c in reversed(self.design_controls):
                if c.x <= event.x <= c.x+c.w and c.y <= event.y <= c.y+c.h:
                    hit = c
                    break
            if hit:
                self._select_control(hit)
                self._drag = (hit, event.x-hit.x, event.y-hit.y)
            else:
                self._select_form()
            return
        meta = next((p for p in PALETTE if p[0]==tool), None)
        if not meta:
            return
        _, _, dw, dh, cap, _ = meta
        x = max(0, min(event.x, self.form_width-dw))
        y = max(0, min(event.y, self.form_height-dh))
        ctrl = DesignControl(tool, x, y, dw, dh, cap)
        self.design_controls.append(ctrl)
        self._redraw_all()
        self._select_control(ctrl)
        self._select_tool("select")
        self.status(f"Placed {ctrl.name}")
        # Insert code for the new control
        self._insert_code_for_control(ctrl)

    def _form_drag(self, event):
        if self._resize:
            self._resize_drag(event)
            return
        if self._form_resize:
            self._form_resize_drag(event)
            return
        if not self._drag:
            return
        ctrl, ox, oy = self._drag
        nx = max(0, min(event.x-ox, self.form_width-ctrl.w))
        ny = max(0, min(event.y-oy, self.form_height-ctrl.h))
        if nx != ctrl.x or ny != ctrl.y:
            dx, dy = nx - ctrl.x, ny - ctrl.y
            ctrl.x, ctrl.y = nx, ny
            self._move_control_visual(ctrl, dx, dy)
            if "left" in self.prop_vars:
                self.prop_vars["left"].set(str(ctrl.x))
            if "top" in self.prop_vars:
                self.prop_vars["top"].set(str(ctrl.y))
            if self._update_timer:
                self.root.after_cancel(self._update_timer)
            self._update_timer = self.root.after(180, lambda c=ctrl: self._update_code_for_property(c, "left", c.x))

    def _form_release(self, event):
        # Cancel any pending drag update
        if hasattr(self, "_update_timer") and self._update_timer:
            self.root.after_cancel(self._update_timer)
            self._update_timer = None
        self._resize_release(event)
        self._form_resize_release(event)
        self._drag = None

    def _hit_test(self, x, y):
        for c in reversed(self.design_controls):
            if c.x <= x <= c.x+c.w and c.y <= y <= c.y+c.h:
                return c
        return None

    def _form_double_click(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit:
            self._select_control(hit)
            self._goto_default_event()
        else:
            self.status("Double-click a control to edit its event")

    def _default_event_for(self, ctrl):
        name = ctrl.name
        if ctrl.ctype == "button":
            return (f"{name}Click", [f'  ShowMessage("Clicked {name}", "Event");'])
        if ctrl.ctype == "edit":
            return (f"{name}Change",
                    [f'  {{ text changed in {name} }}',
                     f'  ShowMessage("Edit changed", "{name}");'])
        if ctrl.ctype in ("checkbox","radio"):
            return (f"{name}Click", [f'  ShowMessage("Toggled {name}", "Event");'])
        if ctrl.ctype == "listbox":
            return (f"{name}Click", [f'  ShowMessage("ListBox {name}", "Event");'])
        if ctrl.ctype == "combo":
            return (f"{name}Change", [f'  ShowMessage("Combo {name}", "Event");'])
        if ctrl.ctype == "memo":
            return (f"{name}Change", [f'  {{ memo {name} changed }}'])
        return (f"{name}Click", [f'  ShowMessage("{name}", "Event");'])

    def _goto_default_event(self):
        ctrl = self.selected_control
        if not ctrl:
            self.status("Select a component first")
            return
        handler, body = self._default_event_for(ctrl)
        src = self.editor.get("1.0","end-1c")
        proc_header = "Proc %s(hCtrl: HWND);" % handler
        if proc_header not in src:
            stub = "\n" + proc_header + "\nRun\n" + "\n".join(body) + "\nStop;\n\n"
            lines = src.splitlines(keepends=True)
            idx = None
            for i,line in enumerate(lines):
                if "Window(" in line:
                    for j in range(i,-1,-1):
                        if lines[j].strip() == "Run":
                            idx = j
                            break
                    break
            if idx is not None:
                lines.insert(idx, stub)
                new_src = "".join(lines)
            elif "Exit." in src:
                new_src = src.replace("Exit.", stub + "Exit.", 1)
            else:
                new_src = src + stub
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", new_src)
            if ctrl.ctype == "button":
                s2 = self.editor.get("1.0","end-1c")
                if "OnClick(@" not in s2 and "RunApp()" in s2:
                    s2 = s2.replace("  RunApp();", "  OnClick(@%s);\n  RunApp();" % handler)
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", s2)
            self.root.after(20, lambda: highlight(self.editor))
            self.update_line_numbers()
        self.notebook.select(0)
        self.root.update_idletasks()
        pos = self.editor.search("Proc %s" % handler, "1.0", tk.END)
        if pos:
            self.editor.mark_set(tk.INSERT, pos)
            self.editor.see(pos)
            line = pos.split(".")[0]
            self.editor.tag_remove("sel","1.0",tk.END)
            self.editor.tag_add("sel", f"{line}.0", f"{line}.end")
            self.editor.focus_set()
            self.status(f"Event: {handler}")
        else:
            self.status(f"Could not find {handler}")

    def _draw_control(self, ctrl):
        theme = THEMES[self.current_theme]
        x, y, w, h = ctrl.x, ctrl.y, ctrl.w, ctrl.h
        outline = "#000000" if not ctrl.selected else "#0078d4"
        width = 2 if ctrl.selected else 1
        items = []
        fill = ctrl.color if ctrl.color else None

        if ctrl.ctype == "button":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#e1e1e1", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.caption or ctrl.name, font=("Segoe UI", 9)))
        elif ctrl.ctype == "edit":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+6, y+h//2,
                          text=ctrl.caption or "", anchor=tk.W,
                          font=("Segoe UI", 9), fill="#666"))
        elif ctrl.ctype == "label":
            items.append(self.form_canvas.create_text(x+2, y+h//2,
                          text=ctrl.caption or ctrl.name, anchor=tk.W,
                          font=("Segoe UI", 9), fill=ctrl.color or "#000"))
            if ctrl.selected:
                items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                              outline=outline, width=width))
        elif ctrl.ctype == "memo":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            # draw some fake text lines
            for i in range(3):
                yy = y + 12 + i*16
                if yy < y+h-8:
                    items.append(self.form_canvas.create_line(x+8, yy, x+w-8, yy,
                                  fill="#cccccc", width=1))
            items.append(self.form_canvas.create_text(x+8, y+8,
                          text="Memo", anchor=tk.NW,
                          font=("Segoe UI", 8), fill="#888"))
        elif ctrl.ctype == "listbox":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            for i in range(4):
                yy = y + 8 + i*18
                if yy < y+h-10:
                    items.append(self.form_canvas.create_rectangle(x+6, yy, x+w-6, yy+14,
                                  fill="#e8e8e8" if i%2==0 else "#f0f0f0", outline=""))
                    items.append(self.form_canvas.create_text(x+10, yy+2,
                                  text=f"Item {i+1}", anchor=tk.W,
                                  font=("Segoe UI", 7), fill="#444"))
        elif ctrl.ctype == "combo":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            items.append(self.form_canvas.create_rectangle(x+w-18, y, x+w, y+h,
                          fill=fill or "#e1e1e1", outline=outline))
            items.append(self.form_canvas.create_text(x+6, y+h//2,
                          text="Combo", anchor=tk.W,
                          font=("Segoe UI", 8), fill="#888"))
            # dropdown arrow
            points = [x+w-15, y+6, x+w-6, y+6, x+w-10, y+15]
            items.append(self.form_canvas.create_polygon(points, fill="#888"))
        elif ctrl.ctype == "checkbox":
            items.append(self.form_canvas.create_rectangle(x, y+4, x+14, y+18,
                          fill=fill or "#fff", outline="#000", width=1))
            if ctrl.caption and ctrl.caption.startswith("√"):
                items.append(self.form_canvas.create_text(x+7, y+11,
                              text="✓", font=("Segoe UI", 10), fill="#000"))
            items.append(self.form_canvas.create_text(x+20, y+h//2,
                          text=ctrl.caption or ctrl.name, anchor=tk.W,
                          font=("Segoe UI", 9)))
            if ctrl.selected:
                items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                              outline=outline, width=width))
        elif ctrl.ctype == "radio":
            items.append(self.form_canvas.create_oval(x+2, y+6, x+14, y+18,
                          fill=fill or "#fff", outline="#000", width=1))
            if ctrl.caption and ctrl.caption.startswith("•"):
                items.append(self.form_canvas.create_oval(x+5, y+9, x+11, y+15,
                              fill="#000", outline=""))
            items.append(self.form_canvas.create_text(x+20, y+h//2,
                          text=ctrl.caption or ctrl.name, anchor=tk.W,
                          font=("Segoe UI", 9)))
            if ctrl.selected:
                items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                              outline=outline, width=width))
        elif ctrl.ctype == "groupbox":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#f0f0f0", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+10, y+2,
                          text=ctrl.caption or ctrl.ctype, anchor=tk.NW,
                          font=("Segoe UI", 8)))
        elif ctrl.ctype == "panel":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#f0f0f0", outline=outline, width=width))
        elif ctrl.ctype == "comport":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#1a1a2e", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.caption or "COM1", anchor=tk.CENTER,
                          font=("Segoe UI", 8, "bold"), fill="#7fdbff"))
        elif ctrl.ctype == "statusbar":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#e0e0e0", outline=outline, width=width))
            items.append(self.form_canvas.create_line(x+2, y+h-2, x+w-2, y+h-2,
                          fill="#aaa"))
            # resize grip
            for i in range(3):
                dx = x+w - 10 - i*4
                dy = y+h - 10 - i*4
                items.append(self.form_canvas.create_line(dx, dy+h-2, dx+h-2, dy,
                              fill="#aaa"))
            items.append(self.form_canvas.create_text(x+6, y+h//2,
                          text=ctrl.caption or "Status", anchor=tk.W,
                          font=("Segoe UI", 8), fill="#333"))
        else:
            # fallback for unknown control types
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.name, font=("Segoe UI", 8)))

        tag = self._ctrl_tag(ctrl)
        for item in items:
            self.form_canvas.addtag_withtag(tag, item)
            self.form_canvas.addtag_withtag("control", item)
        ctrl.widget = items

    def _select_control(self, ctrl):
        if self.selected_control and self.selected_control is not ctrl:
            self.selected_control.selected = False
        self.selected_control = ctrl
        self.selected_form = False
        if ctrl:
            ctrl.selected = True
            self._redraw_all()
            self._load_props(ctrl)
            self.comp_sel_label.config(text=f"{ctrl.name}  [{ctrl.ctype}]")
            self.status(f"Selected {ctrl.name}")
        else:
            self.comp_sel_label.config(text="(none selected)")
            for k in self.prop_vars:
                self.prop_vars[k].set("")

    def _select_form(self):
        self.selected_control = None
        self.selected_form = True
        self.comp_sel_label.config(text="Form: " + self.form_title)
        self._load_form_props()
        self.status("Form selected")
        self._redraw_all()

    def _load_form_props(self):
        self.prop_vars["name"].set("Form")
        self.prop_vars["caption"].set(self.form_title)
        self.prop_vars["left"].set("0")
        self.prop_vars["top"].set("0")
        self.prop_vars["width"].set(str(self.form_width))
        self.prop_vars["height"].set(str(self.form_height))
        self.prop_vars["color"].set(color_label_from_stored(getattr(self, "form_color", "") or ""))
        self._refresh_color_swatch()

    def _load_props(self, ctrl):
        self.prop_vars["name"].set(ctrl.name)
        self.prop_vars["caption"].set(ctrl.caption)
        self.prop_vars["left"].set(str(ctrl.x))
        self.prop_vars["top"].set(str(ctrl.y))
        self.prop_vars["width"].set(str(ctrl.w))
        self.prop_vars["height"].set(str(ctrl.h))
        self.prop_vars["color"].set(color_label_from_stored(ctrl.color or ""))
        self._refresh_color_swatch()

    def _apply_props(self):
        if self.selected_form:
            try:
                new_title = self.prop_vars["caption"].get().strip()
                if new_title and new_title != self.form_title:
                    self.form_title = new_title
                    self.form_title_var.set(new_title)
                    self._update_form_code("title", new_title)
                w = int(self.prop_vars["width"].get())
                h = int(self.prop_vars["height"].get())
                if w >= 100 and h >= 80:
                    if w != self.form_width or h != self.form_height:
                        self.form_width = w
                        self.form_height = h
                        self.form_w_var.set(str(w))
                        self.form_h_var.set(str(h))
                        self.form_canvas.config(width=w, height=h)
                        self._update_form_code("size", None)
            except ValueError:
                pass
            label = self.prop_vars["color"].get().strip()
            new_color = color_hex_from_label(label)
            if new_color != self.form_color:
                self.form_color = new_color
                try:
                    if self.form_color:
                        self.form_canvas.config(bg=self.form_color)
                    else:
                        theme = THEMES[self.current_theme]
                        self.form_canvas.config(bg=theme.get("form_bg", "#dcdcdc"))
                except Exception:
                    pass
                self._update_form_code("color", self.form_color)
            self.status("Form properties updated")
            self._redraw_all()
            return
        ctrl = self.selected_control
        if not ctrl:
            return
        old_name = ctrl.name
        old_caption = ctrl.caption
        old_x, old_y, old_w, old_h = ctrl.x, ctrl.y, ctrl.w, ctrl.h
        old_color = ctrl.color
        try:
            new_name = self.prop_vars["name"].get().strip() or ctrl.name
            new_caption = self.prop_vars["caption"].get()
            new_x = max(0, int(self.prop_vars["left"].get()))
            new_y = max(0, int(self.prop_vars["top"].get()))
            new_w = max(10, int(self.prop_vars["width"].get()))
            new_h = max(10, int(self.prop_vars["height"].get()))
            new_color = color_hex_from_label(self.prop_vars["color"].get().strip())
        except ValueError:
            messagebox.showwarning("Properties", "Invalid numeric value")
            return

        if new_name != old_name:
            ctrl.name = new_name
            self._update_code_for_control(ctrl)
        if new_caption != old_caption:
            ctrl.caption = new_caption
            self._update_code_for_property(ctrl, "caption", new_caption)
        if new_x != old_x or new_y != old_y or new_w != old_w or new_h != old_h:
            ctrl.x, ctrl.y, ctrl.w, ctrl.h = new_x, new_y, new_w, new_h
            self._update_code_for_property(ctrl, "left", new_x)
        if new_color != old_color:
            ctrl.color = new_color
            self._update_code_for_property(ctrl, "color", new_color)

        self._redraw_all()
        self.status(f"Updated {ctrl.name}")

    def _delete_selected(self):
        if self.selected_form:
            self.status("Cannot delete the form.")
            return
        ctrl = self.selected_control
        if not ctrl:
            return
        self.design_controls = [c for c in self.design_controls if c is not ctrl]
        self.selected_control = None
        for k in self.prop_vars:
            self.prop_vars[k].set("")
        self.comp_sel_label.config(text="(none selected)")
        self.status("Control deleted")
        self._redraw_all()
        self._remove_lines_for_control(ctrl.name)

    # ---------- Code updates for properties ----------
    def _update_code_for_property(self, ctrl, prop, value):
        if prop == "name":
            old_name = ctrl.name
            source = self.editor.get("1.0", "end-1c")
            start_marker = "// --- FORM START ---"
            end_marker = "// --- FORM END ---"
            if start_marker in source and end_marker in source:
                lines = source.splitlines()
                in_form = False
                new_lines = []
                for line in lines:
                    if line.strip() == start_marker:
                        in_form = True
                    if in_form:
                        new_line = re.sub(r'\b' + re.escape(old_name) + r'\b', value, line)
                        new_lines.append(new_line)
                    else:
                        new_lines.append(line)
                    if line.strip() == end_marker:
                        in_form = False
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(new_lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
            return

        if prop == "caption":
            old_pattern = r'^(\s*)SetText\s*\(\s*' + re.escape(ctrl.name) + r'\s*,\s*".*?"\s*\)\s*;'
            new_line = f'  SetText({ctrl.name}, "{value}");'
            if not self._replace_line_in_code(old_pattern, new_line, re.IGNORECASE):
                creation_pattern = r'^(\s*)' + re.escape(ctrl.name) + r'\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel)\s*\('
                source = self.editor.get("1.0", "end-1c")
                lines = source.splitlines()
                for i, line in enumerate(lines):
                    if re.search(creation_pattern, line, re.IGNORECASE):
                        lines.insert(i+1, f'  SetText({ctrl.name}, "{value}");')
                        break
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
            return

        if prop in ("left","top","width","height"):
            ctype_map = {
                "button": "Button", "edit": "Edit", "label": "Label",
                "memo": "Memo", "checkbox": "CheckBox", "radio": "Radio",
                "listbox": "ListBox", "combo": "ComboBox",
                "groupbox": "GroupBox", "panel": "Panel",
            }
            if ctrl.ctype == "comport":
                port = (ctrl.caption or "COM1").split("@")[0].strip() or "COM1"
                baud = "9600"
                if "@" in (ctrl.caption or ""):
                    baud = (ctrl.caption or "").split("@")[-1].strip() or "9600"
                new_creation = f'  {ctrl.name} <- ComOpen("{port}", {baud});'
            else:
                ctype = ctype_map.get(ctrl.ctype, "Label")
                new_creation = f'  {ctrl.name} <- {ctype}(MainWindow, {ctrl.w}, {ctrl.h}, {ctrl.x}, {ctrl.y});'
            pattern = r'^(\s*)' + re.escape(ctrl.name) + r'\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel)\s*\([^)]*\)\s*;'
            self._replace_line_in_code(pattern, new_creation, re.IGNORECASE)
            return

        if prop == "color":
            hex_col = ctrl.color if ctrl.color else ""
            if hex_col:
                rgb = color_rgb_from_stored(hex_col)
                if rgb:
                    r, g, b = rgb
                    new_line = f'  SetBackColor({ctrl.name}, ColorRGB({r}, {g}, {b}));'
                else:
                    new_line = f'  SetBackColor({ctrl.name}, {hex_col});'
            else:
                pattern = r'^(\s*)SetBackColor\s*\(\s*' + re.escape(ctrl.name) + r'\s*,.*\)\s*;'
                source = self.editor.get("1.0", "end-1c")
                lines = [line for line in source.splitlines() if not re.search(pattern, line, re.IGNORECASE)]
                if len(lines) != len(source.splitlines()):
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", "\n".join(lines))
                    self.root.after(20, lambda: highlight(self.editor))
                    self.update_line_numbers()
                return
            pattern = r'^(\s*)SetBackColor\s*\(\s*' + re.escape(ctrl.name) + r'\s*,.*\)\s*;'
            if not self._replace_line_in_code(pattern, new_line, re.IGNORECASE):
                creation_pattern = r'^(\s*)' + re.escape(ctrl.name) + r'\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel)\s*\('
                source = self.editor.get("1.0", "end-1c")
                lines = source.splitlines()
                insert_after = None
                for i, line in enumerate(lines):
                    if re.search(creation_pattern, line, re.IGNORECASE):
                        insert_after = i
                        break
                if insert_after is not None:
                    lines.insert(insert_after+1, new_line)
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", "\n".join(lines))
                    self.root.after(20, lambda: highlight(self.editor))
                    self.update_line_numbers()
            return

    def _update_form_code(self, prop, value):
        if prop == "title":
            new_line = f'  SetWindowTitle("{value}");'
            pattern = r'^(\s*)SetWindowTitle\s*\(\s*".*?"\s*\)\s*;'
            self._replace_line_in_code(pattern, new_line, re.IGNORECASE)
        elif prop == "size":
            new_line = f'  Window({self.form_width}, {self.form_height}, 120, 100);'
            pattern = r'^(\s*)Window\s*\(\s*\d+\s*,\s*\d+\s*,'
            self._replace_line_in_code(pattern, new_line, re.IGNORECASE)
        elif prop == "color":
            rgb = color_rgb_from_stored(value)
            if rgb:
                r, g, b = rgb
                new_line = f'  SetFormColor(ColorRGB({r}, {g}, {b}));'
            else:
                pattern = r'^(\s*)SetFormColor\s*\(.*\)\s*;'
                source = self.editor.get("1.0", "end-1c")
                lines = [line for line in source.splitlines() if not re.search(pattern, line, re.IGNORECASE)]
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
                return
            pattern = r'^(\s*)SetFormColor\s*\(.*\)\s*;'
            self._replace_line_in_code(pattern, new_line, re.IGNORECASE)

    def _update_code_for_control(self, ctrl):
        try:
            source = self.editor.get("1.0", "end-1c")
            lines = source.splitlines()
            type_map = {
                "button": "Button",
                "edit": "Edit",
                "label": "Label",
                "memo": "Memo",
                "listbox": "ListBox",
                "combo": "ComboBox",
                "checkbox": "CheckBox",
                "radio": "Radio",
                "groupbox": "GroupBox",
                "panel": "Panel",
                "comport": "ComOpen",
            }
            code_type = type_map.get(ctrl.ctype.lower(), ctrl.ctype.capitalize())
            for i, line in enumerate(lines):
                if re.search(r'^\s*' + re.escape(ctrl.name) + r'\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel|ComOpen)\s*\(', line, re.IGNORECASE):
                    new_line = re.sub(
                        r'(\w+)\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel)\s*\(\s*\w+\s*,\s*)\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)\s*;',
                        f"{ctrl.name} <- {code_type}(MainWindow, {ctrl.w}, {ctrl.h}, {ctrl.x}, {ctrl.y});",
                        line,
                        flags=re.IGNORECASE
                    )
                    lines[i] = new_line
                    break
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "\n".join(lines))
            self.root.after(20, lambda: highlight(self.editor))
            self.update_line_numbers()
        except Exception:
            pass

    def _replace_line_in_code(self, old_pattern, new_line, flags=0):
        source = self.editor.get("1.0", "end-1c")
        lines = source.splitlines()
        modified = False
        for i, line in enumerate(lines):
            if re.search(old_pattern, line, flags):
                lines[i] = new_line
                modified = True
                break
        if modified:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "\n".join(lines))
            self.root.after(20, lambda: highlight(self.editor))
            self.update_line_numbers()
            return True
        return False

    def _insert_code_for_control(self, ctrl):
        lines = []
        ctype_map = {
            "button": "Button",
            "edit": "Edit",
            "label": "Label",
            "memo": "Memo",
            "listbox": "ListBox",
            "combo": "ComboBox",
            "checkbox": "CheckBox",
            "radio": "Radio",
            "groupbox": "GroupBox",
            "panel": "Panel",
        }
        if ctrl.ctype == "comport":
            port = (ctrl.caption or "COM1").split("@")[0].strip() or "COM1"
            baud = "9600"
            if "@" in (ctrl.caption or ""):
                baud = (ctrl.caption or "").split("@")[-1].strip() or "9600"
            lines.append(f'  {{ ComPort {ctrl.name} {ctrl.x} {ctrl.y} {ctrl.w} {ctrl.h} }}')
            lines.append(f'  {ctrl.name} <- ComOpen("{port}", {baud});')
        else:
            ctype = ctype_map.get(ctrl.ctype, "Label")
            lines.append(f'  {ctrl.name} <- {ctype}(MainWindow, {ctrl.w}, {ctrl.h}, {ctrl.x}, {ctrl.y});')
            if ctrl.caption and ctrl.ctype not in ("listbox", "combo", "statusbar"):
                lines.append(f'  SetText({ctrl.name}, "{ctrl.caption}");')
            if ctrl.color:
                rgb = color_rgb_from_stored(ctrl.color)
                if rgb:
                    r, g, b = rgb
                    lines.append(f'  SetBackColor({ctrl.name}, ColorRGB({r}, {g}, {b}));')
        # Ensure Var declaration exists
        self._ensure_var_decl(ctrl)
        self._insert_lines_in_form_section(lines, before_pattern=r'// --- FORM END ---')

    def _ensure_var_decl(self, ctrl):
        """Add '  name: HWND;' or '  name: Integer;' under Var if missing."""
        source = self.editor.get("1.0", "end-1c")
        if re.search(r'\b' + re.escape(ctrl.name) + r'\s*:', source):
            return
        vtype = "Integer" if ctrl.ctype == "comport" else "HWND"
        decl = f'  {ctrl.name}: {vtype};'
        lines = source.splitlines()
        # Insert after 'Var' line
        for i, line in enumerate(lines):
            if line.strip() == "Var" or line.strip().startswith("Var "):
                # skip blank / comment lines after Var
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("{")):
                    j += 1
                lines.insert(j, decl)
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
                return
            # Also handle multi-line Var blocks - insert before first blank after other decls
        # Fallback: no Var section — nothing to do (full Generate will create it)

    def _insert_lines_in_form_section(self, lines_to_insert, before_pattern=None):
        source = self.editor.get("1.0", "end-1c")
        start_marker = "// --- FORM START ---"
        end_marker = "// --- FORM END ---"
        if start_marker not in source or end_marker not in source:
            return False
        lines = source.splitlines()
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if line.strip() == start_marker:
                start_idx = i
            elif line.strip() == end_marker:
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            return False
        insert_pos = end_idx
        if before_pattern:
            for i in range(start_idx+1, end_idx):
                if re.search(before_pattern, lines[i]):
                    insert_pos = i
                    break
        new_lines = lines[:insert_pos] + lines_to_insert + lines[insert_pos:]
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", "\n".join(new_lines))
        self.root.after(20, lambda: highlight(self.editor))
        self.update_line_numbers()
        return True

    def _remove_lines_for_control(self, ctrl_name):
        source = self.editor.get("1.0", "end-1c")
        lines = source.splitlines()
        new_lines = []
        for line in lines:
            if not re.search(r'\b' + re.escape(ctrl_name) + r'\b', line):
                new_lines.append(line)
        if len(new_lines) != len(lines):
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "\n".join(new_lines))
            self.root.after(20, lambda: highlight(self.editor))
            self.update_line_numbers()
            return True
        return False

    def _remove_all_control_code(self):
        source = self.editor.get("1.0", "end-1c")
        lines = source.splitlines()
        new_lines = []
        in_form_section = False
        for line in lines:
            if line.strip() == "// --- FORM START ---":
                in_form_section = True
                new_lines.append(line)
                continue
            if line.strip() == "// --- FORM END ---":
                in_form_section = False
                new_lines.append(line)
                continue
            if in_form_section:
                if re.search(r'^\s*Window\s*\(|^\s*SetWindowTitle\s*\(|^\s*SetFormColor\s*\(|^\s*//', line):
                    new_lines.append(line)
            else:
                new_lines.append(line)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", "\n".join(new_lines))
        self.root.after(20, lambda: highlight(self.editor))
        self.update_line_numbers()

    # ---------- Sync from code ----------
    def sync_from_code(self):
        try:
            if not hasattr(self, "editor") or not hasattr(self, "form_canvas"):
                return
            source = self.editor.get("1.0", "end-1c")
            if not source or not source.strip():
                self.status("No code to sync")
                return

            pattern = re.compile(
                r'(\w+)\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel)\s*\(\s*(\w+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            assignments = {}
            captions = {}
            colors = {}
            type_counts = {
                "button": 0, "edit": 0, "label": 0, "memo": 0, "checkbox": 0, "radio": 0,
                "listbox": 0, "combo": 0, "groupbox": 0, "panel": 0, "comport": 0,
            }
            # Map VCL factory names to designer type ids
            vcl_to_ctype = {
                "button": "button", "edit": "edit", "label": "label", "memo": "memo",
                "checkbox": "checkbox", "radio": "radio", "listbox": "listbox",
                "combobox": "combo", "groupbox": "groupbox", "panel": "panel",
            }
            for match in pattern.finditer(source):
                var_name, ctype_raw, parent, w, h, x, y = match.groups()
                ctype = vcl_to_ctype.get(ctype_raw.lower(), ctype_raw.lower())
                try:
                    w, h, x, y = int(w), int(h), int(x), int(y)
                except ValueError:
                    continue
                assignments[var_name] = (ctype, x, y, w, h)
                if ctype in type_counts:
                    type_counts[ctype] += 1

            # ComPort: name <- ComOpen("COMx", baud);  optional design comment
            comport_pat = re.compile(
                r'(\w+)\s*<-\s*ComOpen\s*\(\s*"([^"]*)"\s*,\s*(\d+)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            for match in comport_pat.finditer(source):
                var_name, port, baud = match.groups()
                # place non-visual ports in a cascade if no geometry comment
                x, y, w, h = 8, 8 + 32 * type_counts.get("comport", 0), 100, 28
                geo = re.search(
                    rf'\{{\s*ComPort\s+{re.escape(var_name)}\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)',
                    source, re.IGNORECASE
                )
                if geo:
                    try:
                        x, y, w, h = map(int, geo.groups())
                    except ValueError:
                        pass
                assignments[var_name] = ("comport", x, y, w, h)
                captions[var_name] = f"{port}@{baud}"
                type_counts["comport"] = type_counts.get("comport", 0) + 1

            settext_pattern = re.compile(
                r'SetText\s*\(\s*(\w+)\s*,\s*"([^"]*)"\s*\)\s*;', re.MULTILINE
            )
            for match in settext_pattern.finditer(source):
                var, cap = match.groups()
                captions[var] = cap

            color_pat = re.compile(
                r'SetBackColor\s*\(\s*(\w+)\s*,\s*ColorRGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            for match in color_pat.finditer(source):
                var, r, g, b = match.groups()
                try:
                    colors[var] = color_hex_from_rgb(int(r), int(g), int(b))
                except ValueError:
                    pass

            form_color_hex = ""
            form_pat = re.compile(
                r'SetFormColor\s*\(\s*ColorRGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            fm = form_pat.search(source)
            if fm:
                try:
                    form_color_hex = color_hex_from_rgb(int(fm.group(1)), int(fm.group(2)), int(fm.group(3)))
                except ValueError:
                    form_color_hex = ""

            win_match = re.search(r'Window\s*\(\s*(\d+)\s*,\s*(\d+)\s*,', source)
            if win_match:
                try:
                    fw, fh = int(win_match.group(1)), int(win_match.group(2))
                    if fw >= 100 and fh >= 80:
                        self.form_width = fw
                        self.form_height = fh
                        if hasattr(self, "form_w_var"):
                            self.form_w_var.set(str(fw))
                            self.form_h_var.set(str(fh))
                        self.form_canvas.config(width=fw, height=fh)
                except Exception:
                    pass
            title_match = re.search(r'SetWindowTitle\s*\(\s*"([^"]*)"\s*\)', source)
            if title_match:
                self.form_title = title_match.group(1)
                if hasattr(self, "form_title_var"):
                    self.form_title_var.set(self.form_title)

            self.form_color = form_color_hex
            try:
                if form_color_hex:
                    self.form_canvas.config(bg=form_color_hex)
                else:
                    theme = THEMES[self.current_theme]
                    self.form_canvas.config(bg=theme.get("form_bg", "#dcdcdc"))
            except Exception:
                pass

            if not assignments:
                # Do not wipe the designer if code has no controls yet
                self.status("No controls in code — designer left unchanged (Generate Code first)")
                self._redraw_all()
                return

            prev_sel = self.selected_control.name if self.selected_control else None
            # Keep designer-only controls that are not present in code
            designer_only = []
            for c in list(self.design_controls):
                if c.name not in assignments:
                    designer_only.append(c)

            for c in self.design_controls:
                if c.widget:
                    if isinstance(c.widget, (list, tuple)):
                        for i in c.widget:
                            self.form_canvas.delete(i)
                    else:
                        self.form_canvas.delete(c.widget)
            self.design_controls.clear()
            self.selected_control = None
            DesignControl._counter = 0
            try:
                if self.form_color:
                    self.form_canvas.config(bg=self.form_color)
            except Exception:
                pass

            for var_name, (ctype, x, y, w, h) in assignments.items():
                cap = captions.get(var_name, "")
                col = colors.get(var_name, "")
                ctrl = DesignControl(ctype, x, y, w, h, cap, col)
                ctrl.name = var_name
                self.design_controls.append(ctrl)

            # Re-attach designer-only controls so Sync does not delete ungenerated drops
            for c in designer_only:
                c.widget = None
                c.selected = False
                self.design_controls.append(c)

            self._redraw_all()
            if prev_sel:
                for c in self.design_controls:
                    if c.name == prev_sel:
                        self._select_control(c)
                        break

            msg = f"Synced {len(self.design_controls)} controls"
            if sum(type_counts.values()) > 0:
                parts = [f"{cnt} {name}" for name, cnt in type_counts.items() if cnt > 0]
                msg += " (" + ", ".join(parts) + ")"
            self.status(msg)
        except Exception as e:
            self.status(f"Sync error: {e}")

    # ---------- Tab change ----------
    def _on_tab_changed(self, event=None):
        try:
            if not hasattr(self, "notebook") or not hasattr(self, "design_tab_index"):
                return
            current = self.notebook.index(self.notebook.select())
            if current == self.design_tab_index:
                self.root.after(30, self.sync_from_code)
        except Exception:
            pass

    # ---------- Code generation ----------
    def generate_vcl_code(self, switch_to_code=True):
        self._apply_form_size()
        title = self.form_title_var.get().strip() or "Form1"
        fw, fh = self.form_width, self.form_height

        lines = []
        lines.append('{ Auto-generated by Vertex IDE v1.0 Form Designer }')
        lines.append('Import "vcl.vtx";')
        lines.append('')
        lines.append(f'Enter {title};')
        lines.append('')
        lines.append('Var')
        for c in self.design_controls:
            lines.append(f'  {c.name}: HWND;')
        if not self.design_controls:
            lines.append('  { no controls yet }')
        lines.append('')

        buttons = [c for c in self.design_controls if c.ctype == "button"]
        if buttons:
            lines.append('Proc OnControlClick(hCtrl: HWND);')
            lines.append('Run')
            first = True
            for c in buttons:
                kw = 'If' if first else 'Else If'
                first = False
                lines.append(f'  {kw} hCtrl = {c.name} Then')
                lines.append(f'    ShowMessage("Clicked {c.name}", "{title}");')
            lines.append('Stop;')
            lines.append('')

        lines.append('Run')
        lines.append(f'  Window({fw}, {fh}, 120, 100);')
        lines.append(f'  SetWindowTitle("{title}");')
        form_rgb = color_rgb_from_stored(getattr(self, "form_color", "") or "")
        if form_rgb:
            r, g, b = form_rgb
            lines.append(f'  SetFormColor(ColorRGB({r}, {g}, {b}));')
        lines.append('')

        for c in self.design_controls:
            parent = "MainWindow"

            if c.ctype == "button":
                lines.append(f'  {c.name} <- Button({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "edit":
                lines.append(f'  {c.name} <- Edit({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "label":
                lines.append(f'  {c.name} <- Label({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "memo":
                lines.append(f'  {c.name} <- Memo({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "listbox":
                lines.append(f'  {c.name} <- ListBox({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "combo":
                lines.append(f'  {c.name} <- ComboBox({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "checkbox":
                lines.append(f'  {c.name} <- CheckBox({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "radio":
                lines.append(f'  {c.name} <- Radio({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "groupbox":
                lines.append(f'  {c.name} <- GroupBox({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "panel":
                lines.append(f'  {c.name} <- Panel({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "statusbar":
                lines.append(f'  {c.name} <- Label({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
                lines.append(f'  {{ StatusBar mapped to Label }}')
            else:
                lines.append(f'  {c.name} <- Label({parent}, {c.w}, {c.h}, {c.x}, {c.y});')

            # Common properties
            if c.caption and c.ctype not in ("listbox", "combo", "statusbar"):
                lines.append(f'  SetText({c.name}, "{c.caption}");')
            rgb = color_rgb_from_stored(c.color or "")
            if rgb:
                r, g, b = rgb
                lines.append(f'  SetBackColor({c.name}, ColorRGB({r}, {g}, {b}));')
            lines.append('')

        if buttons:
            lines.append('  OnClick(@OnControlClick);')
            lines.append('')
        lines.append('  RunApp();')
        lines.append('Stop')
        lines.append('Exit.')
        lines.append('')

        code = "\n".join(lines)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", code)
        if switch_to_code:
            self.notebook.select(0)
        self.root.after(30, lambda: highlight(self.editor))
        self.update_line_numbers()
        self.status(f"Generated VCL code for {title} ({len(self.design_controls)} controls)")
        self._append_output(f"Generated form '{title}' with {len(self.design_controls)} control(s).\n", "success")

    # ---------- Editor helpers ----------
    def _on_editor_scroll(self, *args):
        self.vscroll.set(*args)
        self.line_numbers.yview_moveto(args[0])

    def _on_line_scroll(self, *args):
        pass

    def _on_scrollbar(self, *args):
        self.editor.yview(*args)
        self.line_numbers.yview(*args)

    def _on_mousewheel(self, event):
        self.root.after_idle(self._sync_line_numbers_view)

    def _sync_line_numbers_view(self):
        try:
            self.line_numbers.yview_moveto(self.editor.yview()[0])
        except Exception:
            pass

    def update_line_numbers(self):
        try:
            self.line_numbers.config(state="normal")
            self.line_numbers.delete("1.0", tk.END)
            lines = self.editor.get("1.0","end-1c").count("\n") + 1
            self.line_numbers.insert("1.0", "\n".join(str(i) for i in range(1, lines+1)))
            self.line_numbers.config(state="disabled")
            self._sync_line_numbers_view()
        except Exception:
            pass

    def update_cursor_position(self):
        try:
            line, col = self.editor.index(tk.INSERT).split(".")
            self.cursor_label.config(text=f"Ln {line}, Col {int(col)+1}")
        except Exception:
            pass

    def _on_key_release(self, event):
        self.update_line_numbers()
        self.update_cursor_position()
        if self._highlight_job:
            self.root.after_cancel(self._highlight_job)
        self._highlight_job = self.root.after(80, lambda: highlight(self.editor))

    def _on_cursor_move(self, event=None):
        self.update_cursor_position()

    def _on_modified(self, event=None):
        self.editor.edit_modified(False)
        self.update_line_numbers()

    def toggle_mode(self):
        self.gui_mode = not self.gui_mode
        self.config["auto_detect_gui"] = False
        self.config["gui_app"] = self.gui_mode
        save_config(self.config)
        self._update_ui_mode()
        self.status(f"Mode → {'GUI' if self.gui_mode else 'Console'} (auto-detect disabled)")

    def switch_theme(self, theme_name):
        self.current_theme = theme_name
        self.config["theme"] = theme_name
        save_config(self.config)
        messagebox.showinfo("Theme", "Restart the IDE to fully apply the theme.")
        self.status(f"Theme → {theme_name} (restart to apply)")

    # ---------- Files ----------
    def new_file(self):
        self.clear_form() 
        self.current_file = None
        self.editor.delete("1.0", tk.END)
        template = (
            'Import "vcl.vtx";\n\n'
            'Enter App;\n\n'
            'Var\n'
            '  hLabel: HWND;\n'
            '  hEdit: HWND;\n'
            '  hBtn: HWND;\n\n'
            'Proc OnBtn(hCtrl: HWND);\n'
            'Run\n'
            '  ShowMessage("Hello!", "Vertex");\n'
            'Stop;\n\n'
            'Run\n'
            '  // --- FORM START ---\n'
            '  Window(360, 180, 120, 120);\n'
            '  SetWindowTitle("Vertex App");\n'
            '  hLabel <- Label(MainWindow, 280, 20, 30, 20);\n'
            '  SetText(hLabel, "Name:");\n'
            '  hEdit <- Edit(MainWindow, 220, 28, 30, 50);\n'
            '  SetText(hEdit, "Type something...");\n'
            '  hBtn <- Button(MainWindow, 120, 36, 120, 100);\n'
            '  SetText(hBtn, "OK");\n'
            '  OnClick(@OnBtn);\n'
            '  RunApp();\n'
            '  // --- FORM END ---\n'
            'Stop\n'
            'Exit.\n'
        )
        self.editor.insert("1.0", template)
        self.root.title(f"{APP_NAME} v{APP_VERSION} - Untitled")
        self.gui_mode = True
        self.config["gui_app"] = True
        self.config["auto_detect_gui"] = True
        save_config(self.config)
        if hasattr(self, "mode_btn"):
            self.mode_btn.config(text="GUI")
        self._update_ui_mode()
        self.root.after(30, lambda: highlight(self.editor))
        self.update_line_numbers()
        self.status("New file (Import vcl.vtx)")

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Vertex files", "*.vtx"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path):
        self.clear_form() 
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.current_file = path
            self.root.title(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(path)}")
            if self.config.get("auto_detect_gui", True) and looks_like_gui(content):
                self.gui_mode = True
                self.config["gui_app"] = True
                save_config(self.config)
                if hasattr(self, "mode_btn"):
                    self.mode_btn.config(text="GUI")
            self._update_ui_mode()
            self.root.after(30, lambda: highlight(self.editor))
            self.update_line_numbers()
            self.status(f"Loaded {os.path.basename(path)}")
            if self.config.get("auto_detect_gui", True) and looks_like_gui(content):
                self.root.after(300, self.sync_from_code)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_file(self):
        if self.current_file:
            self._save_to(self.current_file)
        else:
            self.save_as_file()

    def save_as_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".vtx",
                                            filetypes=[("Vertex files", "*.vtx")])
        if path:
            self._save_to(path)

    def _save_to(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end-1c"))
            self.current_file = path
            self.root.title(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(path)}")
            self.status(f"Saved {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------- Compile / Run ----------
    def _append_output(self, text, tag=None):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text, tag if tag else ())
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def compile_file(self):
        if not self.current_file:
            messagebox.showinfo("No file", "Save your file first.")
            return
        self.save_file()
        source = self.editor.get("1.0","end-1c")
        auto = self.config.get("auto_detect_gui", True)
        use_gui = self.gui_mode if not auto else (self.gui_mode or looks_like_gui(source))
        self._update_ui_mode()

        src_dir = os.path.dirname(os.path.abspath(self.current_file)) or "."
        out_dir = self.config.get("output_dir", ".") or "."
        if out_dir.strip() in (".", ""):
            out_dir = src_dir
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        base = os.path.splitext(os.path.basename(self.current_file))[0]
        exe_name = base + (".exe" if sys.platform == "win32" else "")
        exe_path = os.path.join(out_dir, exe_name)

        if os.path.exists(exe_path) and sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", exe_name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except Exception:
                pass

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        mode = "gui" if use_gui else "console"
        self._append_output("=== Compilation started ===\n", "info")
        self._append_output(f"Mode: {mode.upper()}\n", "info")
        self.status("Compiling...")
        self.root.update()

        vertexc = self.config.get("vertexc_path", "vertexc")
        gpp_path = self.config.get("gpp_path", "g++")
        static = bool(self.config.get("static_linking", True))

        build_script = None
        for cand in (
            os.path.join(os.getcwd(), "vertex_build.py"),
            os.path.join(src_dir, "vertex_build.py"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "vertex_build.py") if "__file__" in dir() else "",
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "vertex_build.py"),
        ):
            if cand and os.path.isfile(cand):
                build_script = cand
                break

        try:
            if build_script:
                cmd = [
                    sys.executable, build_script,
                    self.current_file,
                    "--mode", mode,
                    "--output-dir", out_dir,
                    "--vertexc", vertexc,
                    "--gpp", gpp_path,
                ]
                if not static:
                    cmd.append("--no-static")
                self._append_output(f"> {' '.join(cmd)}\n", "info")
                self.root.update()
                proc = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=src_dir
                )
                raw = (proc.stdout or "") + (proc.stderr or "")
                result = None
                try:
                    result = json.loads(proc.stdout)
                except Exception:
                    try:
                        start_j = proc.stdout.find("{")
                        end_j = proc.stdout.rfind("}")
                        if start_j >= 0 and end_j > start_j:
                            result = json.loads(proc.stdout[start_j:end_j + 1])
                    except Exception:
                        result = None

                if result is None:
                    self._append_output(raw + "\n", "error")
                    self._append_output("\nERROR: build script did not return JSON\n", "error")
                    self._set_status_color("error")
                    return

                if result.get("raw_output"):
                    self._append_output(result["raw_output"] + "\n", "info")
                if result.get("gpp_cmd"):
                    self._append_output("Link: " + " ".join(result["gpp_cmd"]) + "\n", "info")

                if result.get("success"):
                    exe = result.get("executable") or exe_path
                    self._last_exe_path = os.path.abspath(exe)
                    self._append_output("\n=== SUCCESS ===\n", "success")
                    self._append_output(f"Executable: {exe}\n", "success")
                    self.status("Compilation successful")
                    self._set_status_color("success")
                else:
                    for err in result.get("errors") or []:
                        line = err.get("line")
                        msg = err.get("message") or err.get("raw_line") or "error"
                        stage = err.get("stage") or "?"
                        prefix = f"[{stage}]"
                        if line:
                            prefix += f" line {line}"
                        self._append_output(f"{prefix}: {msg}\n", "error")
                    if not result.get("errors"):
                        self._append_output(raw + "\n", "error")
                    self._append_output(f"\nERROR: build failed at stage {result.get('stage')}\n", "error")
                    self._set_status_color("error")
                return

            # Fallback: inline build
            env = os.environ.copy()
            gpp_dir = os.path.dirname(gpp_path)
            if gpp_dir:
                env["PATH"] = gpp_dir + os.pathsep + env.get("PATH", "")
            self._run_command([vertexc, self.current_file], "vertexc", src_dir, env)
            cpp_candidates = [
                os.path.join(src_dir, "output.cpp"),
                os.path.join(out_dir, "output.cpp"),
                os.path.abspath("output.cpp"),
            ]
            cpp_path = next((c for c in cpp_candidates if os.path.exists(c)), None)
            if not cpp_path:
                self._append_output("\nERROR: output.cpp was not generated.\n", "error")
                self._set_status_color("error")
                return
            dest_cpp = os.path.join(out_dir, "output.cpp")
            if os.path.abspath(cpp_path) != os.path.abspath(dest_cpp):
                try:
                    open(dest_cpp, "wb").write(open(cpp_path, "rb").read())
                    cpp_path = dest_cpp
                except Exception:
                    pass
            cmd = [gpp_path, "-O2", "-std=c++17", cpp_path, "-o", exe_path]
            if use_gui:
                cmd += ["-mwindows"]
                if static:
                    cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
                cmd += ["-luser32", "-lgdi32", "-lcomdlg32", "-lwinmm", "-ladvapi32"]
            else:
                if static:
                    cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
            self._append_output(f"\nLink: {' '.join(cmd)}\n", "info")
            self._run_command(cmd, "g++", out_dir, env)
            if os.path.exists(exe_path):
                self._last_exe_path = os.path.abspath(exe_path)
                self._append_output("\n=== SUCCESS ===\n", "success")
                self._append_output(f"Executable: {exe_path}\n", "success")
                self.status("Compilation successful")
                self._set_status_color("success")
            else:
                self._append_output("\nERROR: EXE not created.\n", "error")
                self._set_status_color("error")
        except Exception as e:
            self._append_output(f"\nERROR: {e}\n", "error")
            self._set_status_color("error")

    def _set_status_color(self, kind):
        theme = THEMES[self.current_theme]
        if kind == "success":
            self.status_label.config(bg=theme["success"], fg="#fff")
            self.cursor_label.config(bg=theme["success"], fg="#fff")
        elif kind == "error":
            self.status_label.config(bg=theme["error"], fg="#fff")
            self.cursor_label.config(bg=theme["error"], fg="#fff")
        else:
            self.status_label.config(bg=theme["status_bg"], fg=theme["status_fg"])
            self.cursor_label.config(bg=theme["status_bg"], fg=theme["status_fg"])
        self.root.after(4000, lambda: self._set_status_color("normal"))

    def _run_command(self, cmd, name, cwd=None, env=None):
        self._append_output(f"\n> {' '.join(cmd)}\n", "info")
        self.root.update()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, cwd=cwd, env=env)
        for line in proc.stdout:
            tag = "error" if any(k in line.lower() for k in ("error","failed","undefined")) else None
            self._append_output(line, tag)
            self.root.update()
        proc.wait()
        if proc.returncode != 0:
            self._append_output(f"\n*** {name} exited with code {proc.returncode} ***\n", "error")
            raise RuntimeError(f"{name} returned {proc.returncode}")

    def run_program(self):
        if not self.current_file:
            return
        exe_name = os.path.splitext(os.path.basename(self.current_file))[0] + ".exe"
        out_dir = self.config.get("output_dir", ".") or "."
        last = getattr(self, "_last_exe_path", None)
        if last and os.path.isfile(last):
            exe_path, run_cwd = last, os.path.dirname(last)
        else:
            exe_path, run_cwd = find_executable(exe_name, self.current_file, out_dir)
        if not exe_path:
            messagebox.showinfo("Not built", "Compile first.")
            return
        source = self.editor.get("1.0","end-1c")
        auto = self.config.get("auto_detect_gui", True)
        use_gui = self.gui_mode if not auto else (self.gui_mode or looks_like_gui(source))

        self._append_output(f"\n=== Running {exe_path} ===\n", "info")
        env = clean_run_env(self.config.get("gpp_path", "g++"))
        try:
            if sys.platform == "win32":
                if use_gui:
                    subprocess.Popen([exe_path], cwd=run_cwd, env=env, close_fds=True)
                else:
                    subprocess.Popen(
                        f'start "Vertex" cmd /k "cd /d "{run_cwd}" && "{exe_path}" & pause"',
                        cwd=run_cwd, env=env, shell=True)
            else:
                subprocess.Popen([exe_path], cwd=run_cwd, env=env)
            self._append_output("Process started.\n", "success")
        except Exception as e:
            messagebox.showerror("Run", str(e))

    def show_folder(self):
        out_dir = os.path.abspath(self.config.get("output_dir",".") or ".")
        if os.path.exists(out_dir):
            if sys.platform == "win32":
                os.startfile(out_dir)
            else:
                subprocess.run(["xdg-open", out_dir])

    def settings_dialog(self):
        theme = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("560x280")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=theme["bg"])
        frame = tk.Frame(win, padx=14, pady=12, bg=theme["bg"])
        frame.pack(fill=tk.BOTH, expand=True)

        def row(r, label, entry, browse):
            tk.Label(frame, text=label, fg=theme["fg"], bg=theme["bg"]).grid(row=r, column=0, sticky=tk.W)
            entry.grid(row=r, column=1, padx=6, pady=4)
            tk.Button(frame, text="Browse", command=browse, bg=theme["btn_bg"],
                      fg=theme["btn_fg"], relief=tk.FLAT).grid(row=r, column=2)

        e_vc = tk.Entry(frame, width=42, bg=theme["line_bg"], fg=theme["fg"])
        e_vc.insert(0, self.config.get("vertexc_path", "vertexc"))
        row(0, "vertexc:", e_vc, lambda: self._browse_file(e_vc))
        e_gpp = tk.Entry(frame, width=42, bg=theme["line_bg"], fg=theme["fg"])
        e_gpp.insert(0, self.config.get("gpp_path", "g++"))
        row(1, "g++:", e_gpp, lambda: self._browse_file(e_gpp))
        e_out = tk.Entry(frame, width=42, bg=theme["line_bg"], fg=theme["fg"])
        e_out.insert(0, self.config.get("output_dir", "."))
        row(2, "Output:", e_out, lambda: self._browse_dir(e_out))
        static_var = tk.BooleanVar(value=self.config.get("static_linking", True))
        tk.Checkbutton(frame, text="Static linking", variable=static_var,
                       bg=theme["bg"], fg=theme["fg"], selectcolor=theme["line_bg"]).grid(
            row=3, column=0, columnspan=2, sticky=tk.W)
        auto_var = tk.BooleanVar(value=self.config.get("auto_detect_gui", True))
        tk.Checkbutton(frame, text="Auto-detect GUI", variable=auto_var,
                       bg=theme["bg"], fg=theme["fg"], selectcolor=theme["line_bg"]).grid(
            row=4, column=0, columnspan=2, sticky=tk.W)

        def save():
            self.config["vertexc_path"] = e_vc.get().strip()
            self.config["gpp_path"] = e_gpp.get().strip()
            self.config["output_dir"] = e_out.get().strip() or "."
            self.config["static_linking"] = static_var.get()
            self.config["auto_detect_gui"] = auto_var.get()
            save_config(self.config)
            win.destroy()
            self.status("Settings saved")

        tk.Button(frame, text="Save", command=save, bg=theme["btn_bg"],
                  fg=theme["btn_fg"], relief=tk.FLAT, padx=16).grid(row=5, column=1, sticky=tk.E, pady=10)

    def _browse_file(self, entry):
        path = filedialog.askopenfilename()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _browse_dir(self, entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def status(self, msg):
        if hasattr(self, "status_label"):
            self.status_label.config(text=msg)
            self.root.update_idletasks()

    def open_documentation(self):
        doc_path = os.path.join(os.getcwd(), "documentation.pdf")
        if not os.path.isfile(doc_path):
            messagebox.showinfo(
                "Documentation",
                "documentation.pdf was not found in the application folder.\n\n"
                f"Expected path:\n{doc_path}"
            )
            return
        try:
            if sys.platform == "win32":
                os.startfile(doc_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", doc_path], check=False)
            else:
                subprocess.run(["xdg-open", doc_path], check=False)
            self.status("Opened documentation.pdf")
        except Exception as e:
            messagebox.showerror("Documentation", f"Could not open documentation.pdf:\n{e}")

    def about(self):
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME}  -  Delphi-inspired form designer\n\n"
            "Features:\n"
            "  - Form Designer and Component Palette\n"
            "  - VCL code generation (Button, Edit, Label, ...)\n"
            "  - Compile and Run with GUI auto-detect\n"
            "  - Designer grid (15 px) and resize handles\n"
            "  - Code <-> Designer sync (tab switch and manual)\n"
            "  - Live code update on resize and property apply\n"
            "  - Branding icon, ~250 px sidebar, tooltips\n"
            "  - Help -> Documentation (documentation.pdf)\n"
            "  - Themes: dark, light, monokai\n\n"
            f"Version {APP_VERSION}\n"
            "Language: Vertex  |  Compiler: vertexc  |  Library: vcl.vtx"
        )

# ---------- Main ----------
if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass
    app = VertexIDE(root)
    root.mainloop()