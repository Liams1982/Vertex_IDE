#!/usr/bin/env python3
# vertex_ide.py - Vertex IDE v1.2 (Patched for PyScripter compatibility)
# Scrollable palette + realistic SevenSeg designer preview + SetSevenSegDigits/Color
# Uses external VCL file (vcl.vtx) via Import.

import os
import sys
import json
import subprocess
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_NAME = "Vertex IDE"
APP_VERSION = "1.7.2"

CONFIG_FILE = "vertex_ide.json"
DEFAULT_CONFIG = {
    "vertexc_path": "vertexc",
    "gpp_path": "g++",
    "output_dir": ".",
    "static_linking": True,
    "gui_app": False,
    "theme": "dark",
    "auto_detect_gui": True,
    "sidebar_width": 280,
    "palette_height": 280,
    "default_icon": "",
    "embed_icon": True,
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
        try:
            bbox = None
            try:
                bbox = self.widget.bbox("insert")
            except Exception:
                bbox = None
            if bbox:
                x, y = bbox[0], bbox[1]
            else:
                x, y = 0, self.widget.winfo_height()
        except Exception:
            x, y = 0, 20
        x = self.widget.winfo_rootx() + x + 16
        y = self.widget.winfo_rooty() + y + 8
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", "8"), padx=6, pady=3)
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

# Completions for editor (methods / procs / common APIs)
COMPLETIONS = sorted(set(list(KEYWORDS) + list(TYPES) + [
    "Window", "RunApp", "SetWindowTitle", "ShowMessage",
    "Button", "Edit", "Label", "Memo", "CheckBox", "Radio",
    "ListBox", "ComboBox", "GroupBox", "Panel",
    "SetText", "GetText", "SetBounds", "ShowCtrl", "HideCtrl",
    "EnableCtrl", "DisableCtrl", "OnClick", "OnChange",
    "OnMouseDown", "OnMouseUp", "OnMouseMove", "OnKeyDown",
    "SetChecked", "GetChecked", "AddItem", "ClearItems",
    "GetItemCount", "GetItemIndex", "SetItemIndex",
    "ColorRGB", "SetFormColor", "SetBackColor", "SetCtrlTextColor",
    "CanvasBegin", "CanvasEnd", "CanvasMoveTo", "CanvasLineTo",
    "CanvasLine", "CanvasRectangle", "CanvasEllipse", "CanvasCircle",
    "CanvasTriangle", "CanvasFillRect", "CanvasTextOut", "CanvasClear",
    "SetPenColor", "SetPenWidth", "SetPenStyle",
    "SetBrushColor", "SetBrushStyle",
    "ComOpen", "ComClose", "ComWrite", "ComRead", "ComBytesAvailable",
    "MainWindow", "IntToStr", "StrToInt", "FloatToStr", "StrToFloat",
    "Length", "True", "False", "Integer", "Real", "Boolean", "String",
    "StartEngine", "StopEngine", "DisplayInfo", "Drift", "EcoMode",
    "Inherited", "Self", "Create", "Destroy",
    "StatusBar", "HyperTerm", "SevenSeg", "TermWrite", "TermClear",
    "SetSevenSeg", "SetSevenSegDigits", "SetSevenSegColor", "StartTimer", "StopTimer", "OnTimer",
]))

MEMBER_COMPLETIONS = sorted({
    "StartEngine", "StopEngine", "DisplayInfo", "IsEngineRunning",
    "ToggleTurbo", "ToggleHybrid", "Drift", "EcoMode",
    "Create", "Destroy",
    "Make", "Model", "Year", "EngineRunning", "HorsePower", "HasTurbo", "Hybrid",
    "FMake", "FModel", "FYear", "FEngineRunning", "FHasTurbo", "FHybrid",
    "FHorsePower", "FSafetyPackage",
})

# Palette (type_id, label, default_w, default_h, default_caption, icon)
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
    ("statusbar", "StatusBar", 200, 24, "Ready", "📶"),
    ("hyperterm", "HyperTerm", 280, 140, "", "💻"),
    ("timer", "Timer", 90, 28, "1000ms", "⏱"),
    ("sevenseg", "SevenSeg", 70, 90, "0", "🔢"),
]

# Per-control property & event catalog (for Events tab)
COMPONENT_INFO = {
    "button": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height", "Color"],
        "events": ["OnClick"],
    },
    "edit": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height", "Color"],
        "events": ["OnChange", "OnKeyDown"],
    },
    "label": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height", "Color"],
        "events": [],
    },
    "memo": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height", "Color"],
        "events": ["OnChange", "OnKeyDown"],
    },
    "checkbox": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height"],
        "events": ["OnClick"],
    },
    "radio": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height"],
        "events": ["OnClick"],
    },
    "listbox": {
        "props": ["Name", "Left", "Top", "Width", "Height"],
        "events": ["OnClick"],
    },
    "combo": {
        "props": ["Name", "Left", "Top", "Width", "Height"],
        "events": ["OnChange"],
    },
    "groupbox": {
        "props": ["Name", "Caption", "Left", "Top", "Width", "Height"],
        "events": [],
    },
    "panel": {
        "props": ["Name", "Left", "Top", "Width", "Height", "Color"],
        "events": ["OnMouseDown", "OnMouseUp", "OnMouseMove"],
    },
    "comport": {
        "props": ["Name", "Caption (PORT@baud)", "Left", "Top", "Width", "Height"],
        "events": [],
    },
    "statusbar": {
        "props": ["Name", "Caption", "Height"],
        "events": [],
    },
    "hyperterm": {
        "props": ["Name", "Left", "Top", "Width", "Height"],
        "events": [],
        "notes": "TermWrite / TermClear",
    },
    "timer": {
        "props": ["Name", "Interval (ms) via Caption"],
        "events": ["OnTimer"],
        "notes": "StartTimer / StopTimer",
    },
    "sevenseg": {
        "props": ["Name", "Caption (value)", "Left", "Top", "Width", "Height", "Color"],
        "events": [],
        "notes": "SetSevenSeg(h, value)",
    },
    "form": {
        "props": ["Title", "Width", "Height", "Color"],
        "events": ["OnMouseDown", "OnMouseUp", "OnMouseMove", "OnKeyDown", "OnTimer"],
    },
}

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
        "bg": "#0f1117",
        "ac_bg": "#1c2330", "ac_fg": "#e6edf3", "ac_sel": "#3b82f6",
        "ac_border": "#3b82f6", "accent": "#3b82f6", "accent2": "#22c55e",
        "fg": "#e6edf3", "insertbg": "#60a5fa",
        "select_bg": "#1e3a5f", "toolbar_bg": "#161b22", "toolbar_fg": "#8b9bb4",
        "btn_bg": "#222a38", "btn_fg": "#e6edf3", "btn_active": "#2c3648",
        "btn_hover": "#2c3648", "btn_hover_fg": "#ffffff",
        "status_bg": "#3b82f6", "status_fg": "#ffffff",
        "output_bg": "#0d1017", "output_fg": "#8b9bb4",
        "line_bg": "#161b22", "line_fg": "#5c6b82",
        "splash_bg": "#0f1117", "splash_fg": "#3b82f6",
        "success": "#22c55e", "error": "#ef4444",
        "palette_bg": "#161b22",
        "form_bg": "#c5cdd8",
        "form_border": "#2a3344",
        "prop_bg": "#161b22",
        "sash": "#2a3344",
        "elevated": "#222a38",
        "fg_muted": "#8b9bb4",
        "keyword": {"fg": "#60a5fa", "bold": True},
        "flow": {"fg": "#e879f9", "bold": True},
        "type": {"fg": "#2dd4bf", "bold": False},
        "string": {"fg": "#4ade80"},
        "comment": {"fg": "#5c6b82", "italic": True},
        "commentline": {"fg": "#5c6b82", "italic": True},
        "number": {"fg": "#fb923c"},
    },
    "light": {
        "bg": "#fafbff",
        "ac_bg": "#ffffff", "ac_fg": "#1a1a2e", "ac_sel": "#3b82f6",
        "ac_border": "#3b82f6", "accent": "#2563eb", "accent2": "#059669",
        "fg": "#1e293b", "insertbg": "#0f172a",
        "select_bg": "#bfdbfe", "toolbar_bg": "#eff6ff", "toolbar_fg": "#1e3a5f",
        "btn_bg": "#dbeafe", "btn_fg": "#1e3a8a", "btn_active": "#93c5fd",
        "btn_hover": "#60a5fa", "btn_hover_fg": "#ffffff",
        "status_bg": "#2563eb", "status_fg": "#ffffff",
        "output_bg": "#f8fafc", "output_fg": "#334155",
        "line_bg": "#e0e7ff", "line_fg": "#64748b",
        "splash_bg": "#eff6ff", "splash_fg": "#2563eb",
        "success": "#059669", "error": "#dc2626",
        "palette_bg": "#f0f9ff",
        "form_bg": "#f1f5f9",
        "form_border": "#94a3b8",
        "prop_bg": "#f8fafc",
        "sash": "#cbd5e1",
        "elevated": "#e2e8f0",
        "fg_muted": "#64748b",
        "keyword": {"fg": "#2563eb", "bold": True},
        "flow": {"fg": "#7c3aed", "bold": True},
        "type": {"fg": "#0d9488", "bold": False},
        "string": {"fg": "#b45309"},
        "comment": {"fg": "#16a34a", "italic": True},
        "commentline": {"fg": "#16a34a", "italic": True},
        "number": {"fg": "#db2777"},
    },
    "monokai": {
        "bg": "#272822",
        "ac_bg": "#3e3d32", "ac_fg": "#f8f8f2", "ac_sel": "#f92672",
        "ac_border": "#a6e22e", "accent": "#a6e22e", "accent2": "#66d9ef",
        "fg": "#f8f8f2", "insertbg": "#ffffff",
        "select_bg": "#49483e", "toolbar_bg": "#1d1e19", "toolbar_fg": "#f8f8f2",
        "btn_bg": "#3e3d32", "btn_fg": "#f8f8f2", "btn_active": "#5e5d52",
        "btn_hover": "#75715e", "btn_hover_fg": "#ffffff",
        "status_bg": "#a6e22e", "status_fg": "#272822",
        "output_bg": "#1d1e19", "output_fg": "#f8f8f2",
        "line_bg": "#3e3d32", "line_fg": "#75715e",
        "splash_bg": "#272822", "splash_fg": "#a6e22e",
        "success": "#a6e22e", "error": "#f92672",
        "palette_bg": "#3e3d32",
        "form_bg": "#e6e6e6",
        "form_border": "#75715e",
        "prop_bg": "#3e3d32",
        "sash": "#49483e",
        "elevated": "#3e3d32",
        "fg_muted": "#75715e",
        "keyword": {"fg": "#f92672", "bold": True},
        "flow": {"fg": "#ffffff", "bold": True},
        "type": {"fg": "#66d9ef", "bold": False},
        "string": {"fg": "#e6db74"},
        "comment": {"fg": "#75715e", "italic": True},
        "commentline": {"fg": "#75715e", "italic": True},
        "number": {"fg": "#ae81ff"},
    },
}


def bind_button_hover(btn, theme, normal_bg=None, normal_fg=None, hover_bg=None, hover_fg=None):
    """Hover feedback; always restores this button's own colors (no sticky highlight)."""
    nb = normal_bg if normal_bg is not None else theme.get("btn_bg", "#3e3e42")
    nf = normal_fg if normal_fg is not None else theme.get("btn_fg", "#ffffff")
    hb = hover_bg if hover_bg is not None else theme.get("btn_hover", theme.get("btn_active", "#505054"))
    hf = hover_fg if hover_fg is not None else theme.get("btn_hover_fg", nf)
    # slightly darker press
    def _shade(hex_color, factor=0.85):
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r, g, b = int(r * factor), int(g * factor), int(b * factor)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color
    ab = _shade(hb, 0.8)
    btn._v_normal_bg = nb
    btn._v_normal_fg = nf
    btn._v_hover_bg = hb
    btn._v_hover_fg = hf

    def on_enter(e, b=btn):
        try:
            if str(b.cget("state")) == "disabled":
                return
            b.configure(bg=b._v_hover_bg, fg=b._v_hover_fg, relief=tk.FLAT)
        except Exception:
            pass

    def on_leave(e, b=btn):
        try:
            b.configure(bg=b._v_normal_bg, fg=b._v_normal_fg, relief=tk.FLAT)
        except Exception:
            pass

    def on_press(e, b=btn, pbg=ab):
        try:
            b.configure(bg=pbg)
        except Exception:
            pass

    def on_release(e, b=btn):
        try:
            # pointer still over button?
            x, y = b.winfo_pointerxy()
            wx, wy = b.winfo_rootx(), b.winfo_rooty()
            if wx <= x <= wx + b.winfo_width() and wy <= y <= wy + b.winfo_height():
                b.configure(bg=b._v_hover_bg, fg=b._v_hover_fg)
            else:
                b.configure(bg=b._v_normal_bg, fg=b._v_normal_fg)
        except Exception:
            try:
                b.configure(bg=b._v_normal_bg, fg=b._v_normal_fg)
            except Exception:
                pass


def soft_button(parent, text, command=None, bg=None, fg=None, padx=12, pady=6,
                font=("Segoe UI", 9, "bold"), hover=None):
    """Template-style flat pill (Label) — no raised relief."""
    btn = tk.Label(parent, text=text, bg=bg, fg=fg, font=font,
                   padx=padx, pady=pady, cursor="hand2")
    btn._bg = bg
    btn._hover = hover or bg
    btn._fg = fg

    def on_enter(_):
        try:
            btn.configure(bg=btn._hover)
        except Exception:
            pass

    def on_leave(_):
        try:
            btn.configure(bg=btn._bg)
        except Exception:
            pass

    def on_click(_):
        if command:
            command()

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.bind("<Button-1>", on_click)
    return btn


def section_header(parent, title, theme):
    fr = tk.Frame(parent, bg=theme.get("palette_bg", theme.get("prop_bg", theme["bg"])))
    tk.Label(
        fr, text=title.upper(),
        bg=theme.get("palette_bg", theme.get("prop_bg", theme["bg"])),
        fg=theme.get("fg_muted", theme.get("line_fg", "#8b9bb4")),
        font=("Segoe UI", 8, "bold"),
    ).pack(side=tk.LEFT, padx=10, pady=(10, 4))
    return fr


# ---------- Helpers ----------
def is_frozen():
    """True when running as PyInstaller / cx_Freeze / etc. packaged EXE."""
    return bool(getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"))

def _looks_like_ide_exe(path):
    """True if path is this IDE (EXE or script) — must never be used as python/vertexc."""
    if not path:
        return False
    name = os.path.basename(str(path)).lower()
    if "vertex_ide" in name:
        return True
    if name in ("vertexide.exe", "vertexide", "vertex_ide.exe", "vertex_ide.py"):
        return True
    return False

def app_dir():
    """Directory of the running app (EXE folder when frozen, else script dir)."""
    if is_frozen() or _looks_like_ide_exe(sys.executable):
        return os.path.dirname(os.path.abspath(sys.executable))
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

def find_python_interpreter():
    """Real CPython for helpers. Never return the Vertex IDE executable."""
    import shutil
    candidates = []
    # Prefer known Windows install paths first when frozen / IDE exe
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        for ver in ("Python312", "Python311", "Python310", "Python39"):
            candidates.append(os.path.join(local, "Programs", "Python", ver, "python.exe"))
        candidates += [
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
        ]
    if not is_frozen() and not _looks_like_ide_exe(sys.executable):
        candidates.insert(0, sys.executable)
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    # Avoid `py` launcher — it can resolve poorly next to a frozen EXE
    seen = set()
    for cand in candidates:
        if not cand:
            continue
        ap = os.path.abspath(cand)
        if ap in seen:
            continue
        seen.add(ap)
        if _looks_like_ide_exe(ap):
            continue
        try:
            if os.path.samefile(ap, os.path.abspath(sys.executable)):
                continue
        except Exception:
            if ap == os.path.abspath(sys.executable):
                continue
        if os.path.isfile(ap) or shutil.which(cand):
            return ap if os.path.isfile(ap) else cand
    return None



def find_windres(gpp_path):
    import shutil
    if gpp_path:
        d = os.path.dirname(os.path.abspath(gpp_path))
        for name in ("windres.exe", "windres"):
            cand = os.path.join(d, name)
            if os.path.isfile(cand):
                return cand
    return shutil.which("windres") or shutil.which("windres.exe")


def resolve_project_icon(src_path, default_icon=""):
    """Prefer unit.ico / app.ico next to source, else Settings default_icon."""
    if not src_path:
        return None
    src_dir = os.path.dirname(os.path.abspath(src_path)) or "."
    base = os.path.splitext(os.path.basename(src_path))[0]
    for name in (base + ".ico", "app.ico", "icon.ico", "default.ico"):
        pth = os.path.join(src_dir, name)
        if os.path.isfile(pth):
            return pth
    if default_icon and os.path.isfile(default_icon):
        return default_icon
    return None


def build_icon_object(ico_path, out_dir, gpp_path, env=None):
    """Compile .ico to COFF object via windres. Returns (obj_path|None, log)."""
    if not ico_path or not os.path.isfile(ico_path):
        return None, "no icon"
    windres = find_windres(gpp_path)
    if not windres:
        return None, "windres not found (place next to g++, e.g. msys64/ucrt64/bin/windres.exe)"
    os.makedirs(out_dir, exist_ok=True)
    rc_path = os.path.join(out_dir, "_vertex_app_icon.rc")
    obj_path = os.path.join(out_dir, "_vertex_app_icon.o")
    ico_esc = os.path.abspath(ico_path).replace("\\", "/")
    try:
        with open(rc_path, "w", encoding="utf-8") as f:
            f.write('IDI_ICON1 ICON "%s"\n' % ico_esc)
    except Exception as e:
        return None, str(e)
    try:
        proc = subprocess.run(
            [windres, rc_path, "-O", "coff", "-o", obj_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=out_dir, env=env,
        )
        if proc.returncode != 0 or not os.path.isfile(obj_path):
            return None, (proc.stdout or ("windres exit %s" % proc.returncode)).strip()
        return obj_path, "Icon embedded: %s" % ico_path
    except Exception as e:
        return None, str(e)


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
    def __init__(self, ctype, x, y, w, h, caption="", color="", text_color="", enabled=True, visible=True):
        DesignControl._counter += 1
        self.ctype = ctype
        self.name = f"{ctype}{DesignControl._counter}"
        self.x, self.y, self.w, self.h = x, y, w, h
        self.caption = caption if caption is not None else ""
        self.color = color if color is not None else ""          # background / SetBackColor
        self.text_color = text_color if text_color is not None else ""  # SetCtrlTextColor
        self.enabled = bool(enabled)
        self.visible = bool(visible)
        self.widget = None
        self.selected = False

    def to_vtf(self):
        return f"{self.name}:{self.ctype}:{self.x}:{self.y}:{self.w}:{self.h}:{self.caption}:{self.color}"

    def to_dict(self):
        d = {
            "name": self.name,
            "type": self.ctype,
            "left": int(self.x),
            "top": int(self.y),
            "width": int(self.w),
            "height": int(self.h),
            "caption": self.caption or "",
            "color": self.color or "",
            "text_color": getattr(self, "text_color", "") or "",
            "enabled": bool(getattr(self, "enabled", True)),
            "visible": bool(getattr(self, "visible", True)),
        }
        # also emit RGB triples when possible (portable for other tools)
        rgb = color_rgb_from_stored(d["color"]) if d["color"] else None
        if rgb:
            d["color_rgb"] = list(rgb)
        trgb = color_rgb_from_stored(d["text_color"]) if d["text_color"] else None
        if trgb:
            d["text_color_rgb"] = list(trgb)
        return d

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

    @staticmethod
    def from_dict(d):
        ctype = d.get("type") or d.get("ctype") or "label"
        color = d.get("color", "") or ""
        if not color and d.get("color_rgb"):
            try:
                r, g, b = d["color_rgb"]
                color = color_hex_from_rgb(int(r), int(g), int(b))
            except Exception:
                color = ""
        text_color = d.get("text_color", "") or ""
        if not text_color and d.get("text_color_rgb"):
            try:
                r, g, b = d["text_color_rgb"]
                text_color = color_hex_from_rgb(int(r), int(g), int(b))
            except Exception:
                text_color = ""
        ctrl = DesignControl(
            ctype,
            int(d.get("left", d.get("x", 0))),
            int(d.get("top", d.get("y", 0))),
            int(d.get("width", d.get("w", 80))),
            int(d.get("height", d.get("h", 28))),
            d.get("caption", ""),
            color,
            text_color,
            d.get("enabled", True),
            d.get("visible", True),
        )
        if d.get("name"):
            ctrl.name = d["name"]
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
        self._undo_stack = []          # list of full text snapshots (max 10)
        self._redo_stack = []
        self._undo_max = 10
        self._dirty = False
        self._allow_designer_code_write = False  # designer → .vform only (Delphi-style)
        self.current_vform_path = None  # Delphi-style .vform next to .vtx
        self._last_snapshot = None     # text before last key change
        self._suspend_undo = False     # skip push during undo/redo apply
        self.toolbar_buttons = []
        self.design_controls = []
        self.selected_control = None
        self.selected_form = False
        self.palette_tool = "select"
        self.form_title = "Form1"
        self.form_color = ""
        self.form_width = 480
        self.form_height = 320
        self.form_left = 120
        self.form_top = 100
        self._drag = None
        self._resize = None
        self._form_resize = None
        self.handle_size = 6
        self.show_grid = True
        self.grid_size = 5
        self._updating_form_size = False
        self._explorer_update_id = None

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

        # ---------- File menu ----------
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

        # ---------- Edit menu ----------
        edit_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=self.copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find / Replace…", command=self.show_find_dialog, accelerator="Ctrl+F")
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # ---------- Form menu ----------
        form_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        form_menu.add_command(label="New Form", command=self.new_form)
        form_menu.add_command(label="Save Form (.vform)", command=self.save_vform)
        form_menu.add_command(label="Open Form (.vform)", command=self.open_vform)
        form_menu.add_separator()
        # Generate removed — layout lives in .vform + live designer→code sync
        form_menu.add_command(label="Clear Form", command=self.clear_form)
        form_menu.add_command(label="Sync from Code", command=self.sync_from_code)
        form_menu.add_command(label="Generate / Refresh .vform", command=self._ensure_vform_from_code)
        form_menu.add_command(label="Show Form Resource Tab", command=self._goto_form_tab)
        menubar.add_cascade(label="Form", menu=form_menu)

        # ---------- View menu ----------
        view_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        self.theme_var = tk.StringVar(value=self.current_theme)
        for name in THEMES:
            view_menu.add_radiobutton(label=name.capitalize(), variable=self.theme_var,
                                      value=name, command=lambda t=name: self.switch_theme(t))
        menubar.add_cascade(label="View", menu=view_menu)

        # ---------- Help menu ----------
        help_menu = tk.Menu(menubar, tearoff=0, bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
        help_menu.add_command(label="How the IDE works…", command=self.show_ide_guide)
        help_menu.add_command(label="Documentation…", command=self.open_documentation)
        help_menu.add_command(label="Shortcuts", command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=help_menu)

        # Bind global shortcuts
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-Z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-Y>", lambda e: self.redo())
        self.root.bind("<Control-x>", lambda e: self.cut(e))
        self.root.bind("<Control-X>", lambda e: self.cut(e))
        self.root.bind("<Control-c>", lambda e: self.copy())
        self.root.bind("<Control-C>", lambda e: self.copy())
        self.root.bind("<Control-v>", lambda e: self.paste(e))
        self.root.bind("<Control-f>", lambda e: self.show_find_dialog())
        self.root.bind("<Control-F>", lambda e: self.show_find_dialog())
        self.root.bind("<Control-h>", lambda e: self.show_find_dialog(replace=True))
        self.root.bind("<Control-H>", lambda e: self.show_find_dialog(replace=True))
        self.root.bind("<Control-V>", lambda e: self.paste(e))
        self.root.bind("<Control-a>", lambda e: self.select_all())
        self.root.bind("<Control-A>", lambda e: self.select_all())

        # <-- CHANGED: Register window close handler for save-on-close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Toolbar
        self.toolbar = tk.Frame(self.root, height=48, bg=theme["toolbar_bg"])
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.toolbar.pack_propagate(False)

        brand = tk.Frame(self.toolbar, bg=theme["toolbar_bg"])
        brand._v_brand = True
        brand.pack(side=tk.LEFT, padx=(12, 8), pady=8)
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
        tk.Label(brand, text="◆", font=("Segoe UI", 14, "bold"),
                 fg=theme["accent"], bg=theme["toolbar_bg"]).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(brand, text="Vertex", font=("Segoe UI", 12, "bold"),
                 fg=theme["fg"], bg=theme["toolbar_bg"]).pack(side=tk.LEFT)
        tk.Label(brand, text=f"  v{APP_VERSION}", font=("Segoe UI", 9),
                 fg=theme.get("fg_muted", theme["toolbar_fg"]), bg=theme["toolbar_bg"]).pack(side=tk.LEFT)

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

        self._setup_output_context_menu()

        # Main paned
        self.main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL,
            sashwidth=8, sashpad=2, sashrelief=tk.FLAT,
            bg=theme.get("sash", theme["toolbar_bg"]),
            opaqueresize=True,
        )
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.main_pane.bind("<ButtonRelease-1>", self._on_main_sash_release)

        # LEFT — Palette (template layout)
        left_w = int(self.config.get("palette_width", 200) or 200)
        left = tk.Frame(self.main_pane, bg=theme["palette_bg"], width=left_w)
        self.main_pane.add(left, minsize=160, width=left_w)
        self.left_pane = left

        # CENTER — Code / Designer / Explorer
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
            editor_frame, undo=False, font=("Consolas", 12), relief=tk.FLAT, bd=0,
            padx=12, pady=8, wrap=tk.NONE, background=theme["bg"], foreground=theme["fg"],
            insertbackground=theme["insertbg"], selectbackground=theme["select_bg"],
            yscrollcommand=self._on_editor_scroll, exportselection=False,
            maxundo=10)                                                              # <-- CHANGED
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vscroll.config(command=self._on_scrollbar)
        self._configure_tags(theme)

        self.editor.bind("<KeyPress>", self._on_key_press)
        self.editor.bind("<KeyRelease>", self._on_key_release)
        self.editor.bind("<Control-v>", self.paste)
        self.editor.bind("<Control-V>", self.paste)
        self.editor.bind("<Control-x>", self.cut)
        self.editor.bind("<Control-X>", self.cut)

        self._setup_editor_context_menu()


        def _accel_undo(event=None):
            self.undo()
            return "break"
        def _accel_redo(event=None):
            self.redo()
            return "break"
        self.editor.bind("<Control-z>", _accel_undo)
        self.editor.bind("<Control-Z>", _accel_undo)
        self.editor.bind("<Control-y>", _accel_redo)
        self.editor.bind("<Control-Y>", _accel_redo)
        # Windows sometimes uses Control-Shift-Z for redo
        self.editor.bind("<Control-Shift-Z>", _accel_redo)
        self.editor.bind("<Control-Shift-z>", _accel_redo)

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
        tk.Label(design_top, text="Client W:", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(8,0))
        self.form_w_var = tk.StringVar(value=str(self.form_width))
        self.form_w_var.trace_add("write", lambda *args: self._apply_form_size())
        w_entry = tk.Entry(design_top, textvariable=self.form_w_var, width=5,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        w_entry.pack(side=tk.LEFT)
        w_entry.bind("<Return>", lambda e: self._apply_form_size())
        w_entry.bind("<FocusOut>", lambda e: self._apply_form_size())

        # Height
        tk.Label(design_top, text="H:", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.form_h_var = tk.StringVar(value=str(self.form_height))
        self.form_h_var.trace_add("write", lambda *args: self._apply_form_size())
        h_entry = tk.Entry(design_top, textvariable=self.form_h_var, width=5,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        h_entry.pack(side=tk.LEFT)
        h_entry.bind("<Return>", lambda e: self._apply_form_size())
        h_entry.bind("<FocusOut>", lambda e: self._apply_form_size())

        # Apply button (kept for convenience)
        for _txt, _cmd, _tip in (
            ("✓ Apply", self._apply_form_size, "Apply form size/title"),
            ("▦ Grid", self.toggle_grid, "Toggle designer grid"),
            ("↻ Sync", self.sync_from_code, "Sync form from code"),
        ):
            _b = tk.Button(design_top, text=_txt, command=_cmd,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=8)
            _b.pack(side=tk.LEFT, padx=6)
            bind_button_hover(_b, theme)
            ToolTip(_b, _tip)

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

        # RIGHT — Properties / Events (template layout)
        sidebar_w = int(self.config.get("sidebar_width", 260) or 260)
        right = tk.Frame(self.main_pane, bg=theme["prop_bg"], width=sidebar_w)
        self.main_pane.add(right, minsize=200, width=sidebar_w)
        self.right_pane = right

        # Palette lives on the LEFT pane
        self.palette = tk.Frame(self.left_pane, bg=theme["palette_bg"])
        self.palette.pack(fill=tk.BOTH, expand=True)
        section_header(self.palette, "Palette", theme).pack(fill=tk.X)
        tk.Frame(self.palette, bg=theme.get("form_border", "#2a3344"), height=1).pack(fill=tk.X)

        pal_scroll_host = tk.Frame(self.palette, bg=theme["palette_bg"])
        pal_scroll_host.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.palette_vscroll = tk.Scrollbar(pal_scroll_host, orient=tk.VERTICAL)
        self.palette_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.palette_canvas = tk.Canvas(
            pal_scroll_host, bg=theme["palette_bg"], highlightthickness=0,
            yscrollcommand=self.palette_vscroll.set)
        self.palette_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.palette_vscroll.config(command=self.palette_canvas.yview)

        self.palette_inner = tk.Frame(self.palette_canvas, bg=theme["palette_bg"])
        self._palette_win = self.palette_canvas.create_window(
            (0, 0), window=self.palette_inner, anchor=tk.NW)

        def _sync_palette_scroll(event=None):
            self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox("all"))
            try:
                self.palette_canvas.itemconfigure(
                    self._palette_win, width=self.palette_canvas.winfo_width())
            except Exception:
                pass

        self.palette_inner.bind("<Configure>", _sync_palette_scroll)
        self.palette_canvas.bind(
            "<Configure>",
            lambda e: self.palette_canvas.itemconfigure(
                self._palette_win, width=max(e.width, 160)))

        def _palette_wheel(event):
            if event.delta:
                self.palette_canvas.yview_scroll(int(-event.delta / 120), "units")
            elif getattr(event, "num", None) == 4:
                self.palette_canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                self.palette_canvas.yview_scroll(3, "units")

        for w in (self.palette_canvas, self.palette_inner):
            w.bind("<MouseWheel>", _palette_wheel)
            w.bind("<Button-4>", _palette_wheel)
            w.bind("<Button-5>", _palette_wheel)

        grid_frame = tk.Frame(self.palette_inner, bg=theme["palette_bg"])
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.palette_btns = {}
        elevated = theme.get("elevated", theme["btn_bg"])
        border = theme.get("form_border", "#2a3344")
        row = 0
        col = 0
        for ctype, label, dw, dh, cap, icon in PALETTE:
            cell = tk.Frame(
                grid_frame, bg=elevated,
                highlightthickness=1, highlightbackground=border,
                cursor="hand2",
            )
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            ic = tk.Label(cell, text=icon, bg=elevated, fg=theme["fg"],
                          font=("Segoe UI", 14), cursor="hand2")
            ic.pack(pady=(10, 0))
            lb = tk.Label(cell, text=label, bg=elevated,
                          fg=theme.get("fg_muted", theme["toolbar_fg"]),
                          font=("Segoe UI", 8), cursor="hand2")
            lb.pack(pady=(0, 10))
            self.palette_btns[ctype] = cell

            def _pick(e=None, t=ctype):
                self._select_tool(t)

            def _enter(e, c=cell, bd=border):
                c.configure(highlightbackground=theme["accent"])

            def _leave(e, c=cell, bd=border):
                # restore unless selected
                if getattr(self, "palette_tool", None) != getattr(c, "_ctype", None):
                    c.configure(highlightbackground=bd)

            cell._ctype = ctype
            for w in (cell, ic, lb):
                w.bind("<Button-1>", _pick)
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<MouseWheel>", _palette_wheel)
                w.bind("<Button-4>", _palette_wheel)
                w.bind("<Button-5>", _palette_wheel)
            col += 1
            if col >= 2:
                col = 0
                row += 1
        for c in range(2):
            grid_frame.columnconfigure(c, weight=1)

        # Separator (fixed under scroll area)
        tk.Frame(self.palette, height=4, bg=theme["form_border"]).pack(fill=tk.X, padx=6, pady=4)

        # Action buttons (always visible)
        for _txt, _cmd in (
            ("🗔 New Form", self.new_form),
            ("🗑 Clear Form", self.clear_form),
        ):
            _b = tk.Button(self.palette, text=_txt, command=_cmd,
                           bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT,
                           font=("Segoe UI", 9), padx=8, pady=5)
            _b.pack(fill=tk.X, padx=6, pady=2)
            bind_button_hover(_b, theme)

        # Component Editor + Events (RIGHT pane)
        comp_outer = tk.Frame(self.right_pane, bg=theme["prop_bg"])
        comp_outer.pack(fill=tk.BOTH, expand=True)
        self.prop_notebook = ttk.Notebook(comp_outer)
        self.prop_notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        props_tab = tk.Frame(self.prop_notebook, bg=theme["prop_bg"])
        events_tab = tk.Frame(self.prop_notebook, bg=theme["prop_bg"])
        self.prop_notebook.add(props_tab, text="  Properties  ")
        self.prop_notebook.add(events_tab, text="  Events  ")
        # keep name comp_outer for scroll host = props_tab
        comp_outer_props = props_tab
        tk.Label(props_tab, text="Component Editor", bg=theme["prop_bg"],
                 fg=theme["splash_fg"], font=("Segoe UI", 10, "bold")).pack(
                     pady=(8, 2), padx=6, anchor=tk.W)

        comp_scroll = tk.Scrollbar(props_tab, orient=tk.VERTICAL)
        comp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.comp_canvas = tk.Canvas(props_tab, bg=theme["prop_bg"], highlightthickness=0,
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

        section_header(self.comp_editor, "Properties", theme).pack(fill=tk.X)
        tk.Frame(self.comp_editor, bg=theme.get("form_border", "#2a3344"), height=1).pack(fill=tk.X)
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

        # ----- Events tab (only events, with scrollbar) -----
        tk.Label(events_tab, text="Events for selection", bg=theme["prop_bg"],
                 fg=theme["splash_fg"], font=("Segoe UI", 9, "bold")).pack(
                     anchor=tk.W, padx=8, pady=(8, 2))
        self.events_sel = tk.Label(events_tab, text="(none selected)", bg=theme["prop_bg"],
                                   fg=theme["line_fg"], font=("Segoe UI", 8), anchor=tk.W)
        self.events_sel.pack(fill=tk.X, padx=8)

        # Frame for list + scrollbar
        events_frame = tk.Frame(events_tab, bg=theme["prop_bg"])
        events_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        events_scroll = tk.Scrollbar(events_frame, orient=tk.VERTICAL)
        events_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.events_list = tk.Listbox(events_frame, height=6, font=("Consolas", 10),
                                      bg=theme.get("ac_bg", theme["btn_bg"]),
                                      fg=theme.get("ac_fg", theme["btn_fg"]),
                                      selectbackground=theme.get("accent", theme["select_bg"]),
                                      relief=tk.FLAT,
                                      yscrollcommand=events_scroll.set)
        self.events_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        events_scroll.config(command=self.events_list.yview)

        self.events_list.bind("<Double-Button-1>", lambda e: self._goto_default_event())
        _eb = tk.Button(events_tab, text="⚡ Create / Jump to Handler",
                        command=self._goto_default_event,
                        bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT)
        _eb.pack(fill=tk.X, padx=8, pady=6)
        bind_button_hover(_eb, theme)

        # ---------- Code Explorer tab ----------
        explorer_tab = tk.Frame(self.notebook, bg=theme["bg"])
        self.notebook.add(explorer_tab, text="  Code Explorer  ")

        # Form (.vform) resource tab — auto-filled for GUI projects
        form_res_tab = tk.Frame(self.notebook, bg=theme["bg"])
        self.notebook.add(form_res_tab, text="  Form (.vform)  ")
        self.form_tab_index = self.notebook.index(form_res_tab)
        fr_top = tk.Frame(form_res_tab, bg=theme["toolbar_bg"], height=32)
        fr_top.pack(fill=tk.X)
        fr_top.pack_propagate(False)
        tk.Label(fr_top, text="  .vform layout resource", bg=theme["toolbar_bg"],
                 fg=theme.get("fg_muted", theme["toolbar_fg"]),
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)
        soft_button(fr_top, "  Refresh  ", command=self._refresh_vform_tab,
                    bg=theme.get("elevated", theme["btn_bg"]), fg=theme["fg"],
                    hover=theme.get("btn_hover", "#2c3648"), padx=10, pady=4).pack(side=tk.LEFT, padx=4, pady=4)
        soft_button(fr_top, "  Generate from Code  ", command=self._ensure_vform_from_code,
                    bg="#0d9488", fg="#ffffff", hover="#14b8a6", padx=10, pady=4).pack(side=tk.LEFT, padx=4, pady=4)
        soft_button(fr_top, "  Open Designer  ", command=self._goto_designer_tab,
                    bg="#4f46e5", fg="#ffffff", hover="#6366f1", padx=10, pady=4).pack(side=tk.LEFT, padx=4, pady=4)
        vf_body = tk.Frame(form_res_tab, bg=theme["bg"])
        vf_body.pack(fill=tk.BOTH, expand=True)
        vf_scroll_y = tk.Scrollbar(vf_body, orient=tk.VERTICAL)
        vf_scroll_x = tk.Scrollbar(vf_body, orient=tk.HORIZONTAL)
        self.vform_text = tk.Text(
            vf_body, font=("Consolas", 10), relief=tk.FLAT, bd=0, padx=10, pady=8,
            bg=theme["bg"], fg=theme["fg"], insertbackground=theme["insertbg"],
            wrap=tk.NONE,
            yscrollcommand=vf_scroll_y.set,
            xscrollcommand=vf_scroll_x.set)
        vf_scroll_y.config(command=self.vform_text.yview)
        vf_scroll_x.config(command=self.vform_text.xview)
        vf_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        vf_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.vform_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vform_text.insert("1.0", "{ no .vform loaded — open a GUI unit or click Generate from Code }")
        self.vform_text.config(state=tk.DISABLED)

        explorer_frame = tk.Frame(explorer_tab, bg=theme["bg"])
        explorer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.explorer_tree = ttk.Treeview(explorer_frame, columns=("type",), show="tree headings", selectmode="browse")
        self.explorer_tree.heading("#0", text="Symbol")
        self.explorer_tree.column("#0", width=250, minwidth=150)
        self.explorer_tree.heading("type", text="Kind")
        self.explorer_tree.column("type", width=120, minwidth=80, anchor="w")

        explorer_vscroll = ttk.Scrollbar(explorer_frame, orient=tk.VERTICAL, command=self.explorer_tree.yview)
        self.explorer_tree.configure(yscrollcommand=explorer_vscroll.set)

        self.explorer_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        explorer_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.explorer_tree.bind("<Double-Button-1>", self._explorer_goto)
        self.explorer_tree.bind("<<TreeviewSelect>>", self._explorer_select)

        # store current explorer items for navigation
        self._explorer_items = {}  # iid -> (line, col, name, kind)

        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-z>", lambda e: (self.undo(), "break")[1])
        self.root.bind("<Control-y>", lambda e: (self.redo(), "break")[1])
        self.root.bind("<Control-Z>", lambda e: (self.undo(), "break")[1])
        self.root.bind("<Control-Y>", lambda e: (self.redo(), "break")[1])
        self.root.bind("<Control-Shift-Z>", lambda e: (self.redo(), "break")[1])
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

    # ---------- Edit menu commands + undo/redo (10 levels) ----------
    def _base_title(self):
        if self.current_file:
            return f"{APP_NAME} v{APP_VERSION} - {os.path.basename(self.current_file)}"
        return f"{APP_NAME} v{APP_VERSION} - Untitled"

    def _update_window_title(self):
        title = self._base_title()
        if self._dirty:
            title += " *"
        try:
            self.root.title(title)
        except Exception:
            pass

    def _mark_dirty(self, dirty=True):
        self._dirty = bool(dirty)
        self._update_window_title()
        # Do NOT touch edit_modified here — it can fire <<Modified>> and wipe redo.

    def _push_undo_snapshot(self, snapshot=None):
        """Store text *before* a user edit. Max 10. Clears redo (new branch)."""
        if getattr(self, "_suspend_undo", False):
            return
        if snapshot is None:
            snapshot = self.editor.get("1.0", "end-1c")
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        # New user edit invalidates redo
        self._redo_stack.clear()

    def _apply_editor_text(self, content, mark_dirty=True):
        """Replace editor text during undo/redo without touching history stacks."""
        self._suspend_undo = True
        try:
            try:
                cursor = self.editor.index(tk.INSERT)
            except Exception:
                cursor = "1.0"
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            try:
                self.editor.mark_set(tk.INSERT, cursor)
                self.editor.see(cursor)
            except Exception:
                pass
            try:
                self.editor.edit_modified(False)
            except Exception:
                pass
            self._last_snapshot = content
            if mark_dirty:
                self._mark_dirty(True)
            self.root.after(10, lambda: highlight(self.editor))
            self.update_line_numbers()
        finally:
            # Keep suspended briefly so delayed <<Modified>> cannot clear redo
            def _end_suspend():
                self._suspend_undo = False
                try:
                    self.editor.edit_modified(False)
                except Exception:
                    pass
            self.root.after(100, _end_suspend)

    def undo(self):
        """Revert to previous snapshot; current text becomes the next Redo."""
        if not self._undo_stack:
            self.status("Nothing to undo")
            return
        current = self.editor.get("1.0", "end-1c")
        prev = self._undo_stack.pop()
        # Remember what we just undid so Redo can put it back
        self._redo_stack.append(current)
        while len(self._redo_stack) > self._undo_max:
            self._redo_stack.pop(0)
        self._apply_editor_text(prev, mark_dirty=True)
        self.status("Undo restored earlier text  |  Redo available: %d" % len(self._redo_stack))

    def redo(self):
        """Restore the text that was removed by the last Undo (or sequence)."""
        if not self._redo_stack:
            self.status("Nothing to redo — undo something first")
            return
        current = self.editor.get("1.0", "end-1c")
        # Last undone state is on top of redo stack
        restored = self._redo_stack.pop()
        # Current view goes back onto undo so you can undo the redo
        self._undo_stack.append(current)
        while len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._apply_editor_text(restored, mark_dirty=True)
        self.status("Redo restored last undo  |  Redo left: %d" % len(self._redo_stack))



    def show_find_dialog(self, replace=False):
        """Find / Replace dialog for the code editor."""
        if getattr(self, "_find_win", None) is not None:
            try:
                self._find_win.lift()
                self._find_win.focus_force()
                return
            except Exception:
                self._find_win = None

        theme = THEMES.get(self.current_theme, THEMES["dark"])
        win = tk.Toplevel(self.root)
        self._find_win = win
        win.title("Find / Replace")
        win.configure(bg=theme.get("surface", theme["toolbar_bg"]))
        win.resizable(False, False)
        win.transient(self.root)
        try:
            win.geometry("+%d+%d" % (self.root.winfo_rootx() + 120, self.root.winfo_rooty() + 120))
        except Exception:
            pass

        tk.Label(win, text="Find:", bg=theme.get("surface", theme["toolbar_bg"]),
                 fg=theme["fg"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        find_var = tk.StringVar(value=getattr(self, "_find_last", ""))
        find_entry = tk.Entry(win, textvariable=find_var, width=36,
                              bg=theme.get("elevated", theme["btn_bg"]), fg=theme["fg"],
                              insertbackground=theme["fg"], relief=tk.FLAT)
        find_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=(12, 4), sticky="ew")

        tk.Label(win, text="Replace:", bg=theme.get("surface", theme["toolbar_bg"]),
                 fg=theme["fg"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        repl_var = tk.StringVar(value=getattr(self, "_replace_last", ""))
        repl_entry = tk.Entry(win, textvariable=repl_var, width=36,
                              bg=theme.get("elevated", theme["btn_bg"]), fg=theme["fg"],
                              insertbackground=theme["fg"], relief=tk.FLAT)
        repl_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=4, sticky="ew")

        case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text="Match case", variable=case_var,
                       bg=theme.get("surface", theme["toolbar_bg"]), fg=theme["fg"],
                       activebackground=theme.get("surface", theme["toolbar_bg"]),
                       selectcolor=theme.get("elevated", theme["btn_bg"]),
                       font=("Segoe UI", 9)).grid(row=2, column=1, sticky="w", padx=10, pady=4)

        status = tk.Label(win, text="", bg=theme.get("surface", theme["toolbar_bg"]),
                          fg=theme.get("fg_muted", theme["toolbar_fg"]), font=("Segoe UI", 8))
        status.grid(row=3, column=0, columnspan=3, sticky="w", padx=10)

        def _flags():
            return 0 if case_var.get() else tk.IGNORECASE if False else 1  # use str methods

        def find_next(from_start=False):
            needle = find_var.get()
            if not needle:
                status.config(text="Enter text to find")
                return
            self._find_last = needle
            self.notebook.select(0)  # Code tab
            content = self.editor.get("1.0", "end-1c")
            start_idx = "1.0" if from_start else self.editor.index(tk.INSERT)
            # If selection matches, start after it
            try:
                if self.editor.tag_ranges("sel"):
                    start_idx = self.editor.index("sel.last")
            except Exception:
                pass
            pos = self.editor.search(needle, start_idx, stopindex=tk.END,
                                     nocase=not case_var.get())
            if not pos and start_idx != "1.0":
                pos = self.editor.search(needle, "1.0", stopindex=tk.END,
                                         nocase=not case_var.get())
            if pos:
                end = f"{pos}+{len(needle)}c"
                self.editor.tag_remove("sel", "1.0", tk.END)
                self.editor.tag_add("sel", pos, end)
                self.editor.mark_set(tk.INSERT, end)
                self.editor.see(pos)
                self.editor.focus_set()
                status.config(text=f"Found at {pos}")
            else:
                status.config(text="Not found")

        def replace_one():
            needle = find_var.get()
            repl = repl_var.get()
            self._replace_last = repl
            if not needle:
                return
            try:
                if self.editor.tag_ranges("sel"):
                    sel = self.editor.get("sel.first", "sel.last")
                    ok = sel == needle if case_var.get() else sel.lower() == needle.lower()
                    if ok:
                        self._push_undo_snapshot()
                        self.editor.delete("sel.first", "sel.last")
                        self.editor.insert(tk.INSERT, repl)
                        self._mark_dirty(True)
            except Exception:
                pass
            find_next()

        def replace_all():
            needle = find_var.get()
            repl = repl_var.get()
            self._find_last = needle
            self._replace_last = repl
            if not needle:
                return
            self.notebook.select(0)
            content = self.editor.get("1.0", "end-1c")
            if case_var.get():
                count = content.count(needle)
                new_content = content.replace(needle, repl)
            else:
                # case-insensitive replace
                import re as _re
                new_content, count = _re.subn(_re.escape(needle), lambda m: repl, content, flags=_re.IGNORECASE)
            if count:
                self._push_undo_snapshot()
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", new_content)
                self._mark_dirty(True)
                self.root.after(10, lambda: highlight(self.editor))
                self.update_line_numbers()
            status.config(text=f"Replaced {count} occurrence(s)")

        btn_bg = theme.get("elevated", theme["btn_bg"])
        bf = tk.Frame(win, bg=theme.get("surface", theme["toolbar_bg"]))
        bf.grid(row=4, column=0, columnspan=3, pady=12, padx=10, sticky="e")
        for lab, cmd in (("Find Next", lambda: find_next()),
                         ("Replace", replace_one),
                         ("Replace All", replace_all),
                         ("Close", win.destroy)):
            soft_button(bf, f"  {lab}  ", command=cmd,
                        bg=theme["accent"] if lab == "Find Next" else btn_bg,
                        fg="#ffffff" if lab == "Find Next" else theme["fg"],
                        hover=theme.get("btn_hover", "#2c3648"), padx=10, pady=5).pack(side=tk.LEFT, padx=3)

        find_entry.focus_set()
        win.bind("<Return>", lambda e: find_next())
        win.bind("<Escape>", lambda e: win.destroy())
        win.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "_find_win", None), win.destroy()))
        def _on_close():
            self._find_win = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _goto_designer_tab(self):
        try:
            if hasattr(self, "design_tab_index"):
                self.notebook.tab(self.design_tab_index, state="normal")
                self.notebook.select(self.design_tab_index)
        except Exception:
            pass

    def _goto_form_tab(self):
        try:
            if hasattr(self, "form_tab_index"):
                self.notebook.select(self.form_tab_index)
                self._refresh_vform_tab()
        except Exception:
            pass

    def _ensure_vform_from_code(self):
        """If GUI project has no .vform, build designer from code and write .vform."""
        if not self._is_gui_project():
            messagebox.showinfo("Form", "Current unit does not look like a GUI project.")
            return
        try:
            self._sync_from_code_impl()
        except Exception as e:
            self.status(f"Sync from code failed: {e}")
        path = self.current_vform_path or self._vform_path_for_unit()
        if not path:
            messagebox.showinfo("Form", "Save the .vtx file first so a .vform path can be determined.")
            return
        try:
            self._save_vform_disk_only(path)
            self.current_vform_path = path
            try:
                self._ensure_vform_import_comment(path)
            except Exception:
                pass
            self._refresh_vform_tab()
            self.status(f"Generated {os.path.basename(path)} from code")
            messagebox.showinfo("Form", f"Generated:\n{path}")
        except Exception as e:
            messagebox.showerror("Form", str(e))

    def _refresh_vform_tab(self):
        """Load current .vform JSON into the Form resource tab (generate if missing)."""
        if not hasattr(self, "vform_text"):
            return
        path = self.current_vform_path or self._vform_path_for_unit()
        text_body = ""
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text_body = f.read()
                self.current_vform_path = path
            except Exception as e:
                text_body = f"{{ \"error\": \"{e}\" }}"
        elif self._is_gui_project() and path:
            # auto-generate from code
            try:
                self._sync_from_code_impl()
                self._save_vform_disk_only(path)
                self.current_vform_path = path
                with open(path, "r", encoding="utf-8") as f:
                    text_body = f.read()
                try:
                    self._ensure_vform_import_comment(path)
                except Exception:
                    pass
            except Exception as e:
                text_body = (
                    '{ "format": "VertexForm", "note": "Could not generate from code", '
                    f'"error": "{e}" }}'
                )
        else:
            text_body = (
                "{\n"
                '  "format": "VertexForm",\n'
                '  "note": "No GUI unit / no path — save a .vtx with Window() or open a GUI project"\n'
                "}"
            )
        try:
            self.vform_text.config(state=tk.NORMAL)
            self.vform_text.delete("1.0", tk.END)
            self.vform_text.insert("1.0", text_body)
            self.vform_text.config(state=tk.DISABLED)
        except Exception:
            pass

    def _setup_editor_context_menu(self):
        """Right-click menu for the code editor."""
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        menu = tk.Menu(self.root, tearoff=0,
                       bg=theme.get("elevated", theme["btn_bg"]),
                       fg=theme["fg"],
                       activebackground=theme["accent"],
                       activeforeground="#ffffff",
                       bd=0)
        menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        menu.add_separator()
        menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut)
        menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy)
        menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste)
        menu.add_separator()
        menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all)
        menu.add_separator()
        menu.add_command(label="Find line…", command=self._ctx_goto_line)
        menu.add_command(label="Compile", accelerator="F5", command=self.compile_file)
        menu.add_command(label="Run", accelerator="F6", command=self.run_program)
        self._editor_ctx_menu = menu

        def show_menu(event):
            try:
                self.editor.focus_set()
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
            return "break"

        self.editor.bind("<Button-3>", show_menu)
        # macOS Ctrl-click
        self.editor.bind("<Control-Button-1>", show_menu)

    def _setup_output_context_menu(self):
        """Right-click menu for the compilation / output pane."""
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        menu = tk.Menu(self.root, tearoff=0,
                       bg=theme.get("elevated", theme["btn_bg"]),
                       fg=theme["fg"],
                       activebackground=theme["accent"],
                       activeforeground="#ffffff",
                       bd=0)
        menu.add_command(label="Copy", command=self._output_copy)
        menu.add_command(label="Copy All", command=self._output_copy_all)
        menu.add_separator()
        menu.add_command(label="Select All", command=self._output_select_all)
        menu.add_separator()
        menu.add_command(label="Clear Output", command=self._output_clear)
        self._output_ctx_menu = menu

        def show_menu(event):
            try:
                # temporarily enable to allow selection ops
                self.output_text.config(state=tk.NORMAL)
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
                try:
                    self.output_text.config(state=tk.DISABLED)
                except Exception:
                    pass
            return "break"

        self.output_text.bind("<Button-3>", show_menu)
        self.output_text.bind("<Control-Button-1>", show_menu)

    def _ctx_goto_line(self):
        from tkinter import simpledialog
        try:
            line = simpledialog.askinteger("Go to line", "Line number:", parent=self.root, minvalue=1)
            if line:
                self.editor.mark_set(tk.INSERT, f"{line}.0")
                self.editor.see(f"{line}.0")
                self.editor.focus_set()
        except Exception:
            pass

    def _output_copy(self):
        try:
            self.output_text.config(state=tk.NORMAL)
            try:
                text = self.output_text.get("sel.first", "sel.last")
            except Exception:
                text = ""
            if text:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
            self.output_text.config(state=tk.DISABLED)
        except Exception:
            try:
                self.output_text.config(state=tk.DISABLED)
            except Exception:
                pass

    def _output_copy_all(self):
        try:
            self.output_text.config(state=tk.NORMAL)
            text = self.output_text.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.output_text.config(state=tk.DISABLED)
            self.status("Output copied to clipboard")
        except Exception:
            try:
                self.output_text.config(state=tk.DISABLED)
            except Exception:
                pass

    def _output_select_all(self):
        try:
            self.output_text.config(state=tk.NORMAL)
            self.output_text.tag_add("sel", "1.0", "end-1c")
            self.output_text.mark_set(tk.INSERT, "1.0")
            # leave enabled briefly so selection shows; next click/clear will disable
            self.root.after(50, lambda: self.output_text.config(state=tk.DISABLED))
        except Exception:
            try:
                self.output_text.config(state=tk.DISABLED)
            except Exception:
                pass

    def _output_clear(self):
        try:
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.config(state=tk.DISABLED)
            self.status("Output cleared")
        except Exception:
            pass

    def cut(self, event=None):
        try:
            self._push_undo_snapshot()
            self.editor.event_generate("<<Cut>>")
            self._mark_dirty(True)
            self._last_snapshot = self.editor.get("1.0", "end-1c")
        except Exception:
            pass
        return "break"

    def copy(self, event=None):
        try:
            self.editor.event_generate("<<Copy>>")
        except Exception:
            pass
        return "break"

    def paste(self, event=None):
        """Paste once only. Return 'break' so Tk does not paste a second time."""
        try:
            self._push_undo_snapshot()
            try:
                clip = self.root.clipboard_get()
            except Exception:
                clip = ""
            if clip:
                try:
                    self.editor.delete("sel.first", "sel.last")
                except Exception:
                    pass
                self.editor.insert(tk.INSERT, clip)
            self._mark_dirty(True)
            after = self.editor.get("1.0", "end-1c")
            # If paste created a second full program, keep the first only
            fixed = self._first_program_only(after)
            if fixed != after and self._count_programs(after) > 1:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", fixed)
                try:
                    self.status("Paste: removed duplicate program block")
                except Exception:
                    pass
            self._last_snapshot = self.editor.get("1.0", "end-1c")
            self.root.after(10, lambda: highlight(self.editor))
            self.update_line_numbers()
        except Exception:
            pass
        return "break"

    def select_all(self):
        try:
            self.editor.tag_add("sel", "1.0", "end-1c")
            self.editor.mark_set(tk.INSERT, "end-1c")
            self.editor.see(tk.INSERT)
        except Exception:
            pass

    # ---------- Code Explorer methods ----------
    def _update_code_explorer(self):
        """Parse editor content into a hierarchical Code Explorer tree."""
        if not hasattr(self, "explorer_tree"):
            return
        tree = self.explorer_tree
        tree.delete(*tree.get_children())
        self._explorer_items = {}  # iid -> (line, col, name, kind)

        src = self.editor.get("1.0", "end-1c")
        if not src.strip():
            self.status("Code Explorer: (empty)")
            return

        src_lines = src.splitlines()

        def line_of(pos):
            return src[:pos].count("\n") + 1

        class_hdr = re.compile(r'(?im)^\s*(\w+)\s*=\s*Class(?:\s*\(\s*(\w+)\s*\))?\s*$')
        end_re = re.compile(r'(?im)^\s*End\s*;\s*$')
        field_re = re.compile(r'(?im)^\s*(\w+)\s*:\s*([\w\^\[\]\.0-9]+)\s*;')
        meth_decl = re.compile(
            r'(?im)^\s*(Constructor|Destructor|Proc|Func|Procedure|Function)\s+'
            r'(?:(\w+)\.)?(\w+)\s*(?:\(|;|:)'
        )
        section_re = re.compile(r'(?im)^\s*(Private|Public|Protected)\s*$')

        classes = []
        i = 0
        while i < len(src_lines):
            m = class_hdr.match(src_lines[i])
            if not m:
                i += 1
                continue
            cname = m.group(1)
            base = m.group(2) or ""
            start_i = i
            depth = 1
            j = i + 1
            body_end = len(src_lines) - 1
            while j < len(src_lines):
                if class_hdr.match(src_lines[j]):
                    depth += 1
                elif end_re.match(src_lines[j]):
                    depth -= 1
                    if depth == 0:
                        body_end = j
                        break
                j += 1
            fields, methods = [], []
            section = "Public"
            for k in range(start_i + 1, body_end):
                sm = section_re.match(src_lines[k])
                if sm:
                    section = sm.group(1)
                    continue
                mm = meth_decl.match(src_lines[k])
                if mm:
                    methods.append((mm.group(3), mm.group(1), section, k + 1))
                    continue
                fm = field_re.match(src_lines[k])
                if fm:
                    fname = fm.group(1)
                    if fname.lower() not in ("proc", "func", "constructor", "destructor", "end", "var", "type"):
                        fields.append((fname, fm.group(2), section, k + 1))
            classes.append({
                "name": cname, "base": base, "start": start_i + 1, "end": body_end + 1,
                "fields": fields, "methods": methods,
            })
            i = body_end + 1

        class_names = {c["name"] for c in classes}

        impl_methods = []
        impl_re = re.compile(
            r'(?im)^\s*(Constructor|Destructor|Proc|Func|Procedure|Function)\s+'
            r'(?:(\w+)\.)?(\w+)\s*(?:\(|;|:)'
        )
        for idx, line in enumerate(src_lines):
            mm = impl_re.match(line)
            if not mm:
                continue
            impl_methods.append((mm.group(2), mm.group(3), mm.group(1), idx + 1))

        enter_m = re.search(r'(?im)^\s*Enter\s+(\w+)\s*;', src)
        prog_name = enter_m.group(1) if enter_m else "Program"
        prog_line = line_of(enter_m.start()) if enter_m else 1

        globals_vars = []
        var_block = re.search(r'(?im)^\s*Var\b', src)
        if var_block:
            start_pos = var_block.end()
            stop = re.search(r'(?im)^\s*(Run|Proc|Func|Type|Enter|Exit|Constructor|Destructor)\b', src[start_pos:])
            block = src[start_pos: start_pos + stop.start()] if stop else src[start_pos:]
            for vm in re.finditer(r'(?im)^\s*(\w+)\s*:\s*([\w\^\[\]\.0-9]+)\s*;', block):
                globals_vars.append((vm.group(1), vm.group(2), line_of(start_pos + vm.start())))

        imports = []
        for im in re.finditer(r'(?im)^\s*Import\s+("[^"]+"|<[^>]+>)\s*;', src):
            imports.append((im.group(1), line_of(im.start())))

        uid = [0]
        def add(parent, text_label, kind, line, col=0):
            uid[0] += 1
            iid = "e%d" % uid[0]
            tree.insert(parent, "end", iid=iid, text=text_label, values=(kind,), open=True)
            self._explorer_items[iid] = (line, col, text_label, kind)
            return iid

        root_id = add("", "📁 %s" % prog_name, "Program", prog_line)

        if imports:
            imp_node = add(root_id, "📦 Imports", "Group", imports[0][1])
            for name, ln in imports:
                add(imp_node, name, "Import", ln)

        if classes:
            types_node = add(root_id, "📂 Types / Classes", "Group", classes[0]["start"])
            for c in classes:
                label = c["name"]
                if c["base"]:
                    label = "%s (%s)" % (c["name"], c["base"])
                cnode = add(types_node, "🔷 %s" % label, "Class", c["start"])
                if c["fields"]:
                    fnode = add(cnode, "Fields", "Group", c["fields"][0][3])
                    for fname, ftype, section, ln in c["fields"]:
                        add(fnode, "%s: %s" % (fname, ftype), "Field/%s" % section, ln)
                if c["methods"]:
                    mnode = add(cnode, "Methods", "Group", c["methods"][0][3])
                    for mname, kind, section, ln in c["methods"]:
                        kl = kind.lower()
                        icon = "⚙" if kl in ("proc", "procedure") else ("ƒ" if kl in ("func", "function") else "★")
                        add(mnode, "%s %s" % (icon, mname), "%s/%s" % (kind, section), ln)
                extra = [im for im in impl_methods if im[0] == c["name"]]
                if extra:
                    inode = add(cnode, "Implementations", "Group", extra[0][3])
                    for cls, mname, kind, ln in extra:
                        add(inode, "→ %s %s" % (kind, mname), "Impl", ln)

        standalone = []
        seen = set()
        for cls, name, kind, ln in impl_methods:
            key = (name, ln)
            if key in seen:
                continue
            seen.add(key)
            inside = any(c["start"] <= ln <= c["end"] for c in classes)
            if inside:
                continue
            if cls and cls in class_names:
                continue
            standalone.append((cls, name, kind, ln))
        if standalone:
            rout_node = add(root_id, "📂 Routines", "Group", standalone[0][3])
            for cls, name, kind, ln in standalone:
                label = "%s.%s" % (cls, name) if cls else name
                add(rout_node, "⚙ %s" % label, kind, ln)

        if globals_vars:
            vnode = add(root_id, "📂 Variables", "Group", globals_vars[0][2])
            for name, vtype, ln in globals_vars:
                add(vnode, "%s: %s" % (name, vtype), "Var", ln)

        self.status("Code Explorer: %d symbols" % len(self._explorer_items))

    def _explorer_goto(self, event=None):
        sel = self.explorer_tree.selection()
        if not sel:
            return
        iid = sel[0]
        info = self._explorer_items.get(iid)
        if not info:
            return
        line, col, text_label, kind = info
        if kind == "Group":
            return
        try:
            self.notebook.select(0)
        except Exception:
            pass
        self.editor.focus_set()
        pos = "%d.%d" % (line, col)
        self.editor.mark_set(tk.INSERT, pos)
        self.editor.see(pos)
        self.editor.tag_remove("sel", "1.0", tk.END)
        self.editor.tag_add("sel", "%d.0" % line, "%d.end" % line)
        self.update_cursor_position()
        self.status("Jumped to %s  (line %d)" % (text_label, line))

    def _explorer_select(self, event=None):
        sel = self.explorer_tree.selection()
        if not sel:
            return
        iid = sel[0]
        info = self._explorer_items.get(iid)
        if info:
            line, col, text_label, kind = info
            self.status("%s: %s  — line %d" % (kind, text_label, line))
        else:
            self.status("Symbol: %s" % self.explorer_tree.item(sel[0], "text"))

    def _refresh_color_swatch(self):
        if not hasattr(self, "color_swatch"):
            return
        label = "(default)"
        try:
            if self.prop_vars.get("color"):
                label = self.prop_vars["color"].get() or "(default)"
        except Exception:
            pass
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
            try:
                self.color_btn.config(text=f"{label}  ▼")
            except Exception:
                pass

    def _set_color_choice(self, label):
        if "color" in self.prop_vars:
            self.prop_vars["color"].set(label)
        self._refresh_color_swatch()
        if getattr(self, "_color_popup", None) is not None:
            try:
                self._color_popup.destroy()
            except Exception:
                pass
            self._color_popup = None
        try:
            self._apply_props()
        except Exception:
            pass

    def _open_color_picker(self):
        if getattr(self, "_color_popup", None) is not None:
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

        tk.Label(outer, text="Choose color", anchor=tk.W,
                 bg=theme["prop_bg"], fg=theme.get("splash_fg", theme["btn_fg"]),
                 font=("Segoe UI", 9, "bold"), padx=8, pady=4).pack(fill=tk.X)

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
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(3, "units")

        for w in (pop, outer, list_frame, canvas, inner):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)

        current = self.prop_vars["color"].get() if "color" in self.prop_vars else "(default)"
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
        # click-away: bind root once
        def _click_away(event):
            if self._color_popup is None:
                return
            try:
                wx = self._color_popup.winfo_rootx()
                wy = self._color_popup.winfo_rooty()
                ww = self._color_popup.winfo_width()
                wh = self._color_popup.winfo_height()
                if not (wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh):
                    _close()
            except Exception:
                _close()
        self.root.bind("<Button-1>", _click_away, add="+")
        pop.focus_force()
        _sync_scroll()



    def _place_sidebar_sash(self):
        """Place left (palette) and right (properties) sashes from saved widths."""
        try:
            self.root.update_idletasks()
            total = self.main_pane.winfo_width()
            if total < 200:
                self.root.after(120, self._place_sidebar_sash)
                return
            left_w = int(self.config.get("palette_width", 200) or 200)
            right_w = int(self.config.get("sidebar_width", 260) or 260)
            left_w = max(160, min(left_w, 360))
            right_w = max(200, min(right_w, 420))
            # ensure center has room
            if left_w + right_w > total - 300:
                scale = (total - 300) / max(left_w + right_w, 1)
                left_w = max(160, int(left_w * scale))
                right_w = max(200, int(right_w * scale))
            self.main_pane.sash_place(0, left_w, 0)
            self.main_pane.sash_place(1, max(left_w + 300, total - right_w), 0)
        except Exception:
            pass


    def _on_main_sash_release(self, event=None):
        """Persist left palette width and right properties width."""
        try:
            self.root.update_idletasks()
            total = self.main_pane.winfo_width()
            x0 = self.main_pane.sash_coord(0)[0]
            x1 = self.main_pane.sash_coord(1)[0]
            left_w = max(160, x0)
            right_w = max(200, total - x1)
            self.config["palette_width"] = int(left_w)
            self.config["sidebar_width"] = int(right_w)
            save_config(self.config)
            self.status(f"Panels: palette {left_w}px · properties {right_w}px")
        except Exception:
            pass

    def _on_right_sash_release(self, event=None):
        """No vertical split in template layout (kept for compatibility)."""
        pass


    def _update_ui_mode(self):
        source = self.editor.get("1.0","end-1c") if hasattr(self,"editor") else ""
        auto = self.config.get("auto_detect_gui", True)
        use_gui = self.gui_mode if not auto else (self.gui_mode or looks_like_gui(source))
        if hasattr(self, "mode_btn") and self.mode_btn is not None:
            try:
                theme = THEMES[self.current_theme]
                elevated = theme.get("elevated", theme["btn_bg"])
                muted = theme.get("fg_muted", theme["toolbar_fg"])
                if use_gui:
                    self.mode_btn.configure(text="  🖥 GUI  ", bg="#1e3a5f", fg="#60a5fa")
                    self.mode_btn._bg, self.mode_btn._hover = "#1e3a5f", "#2563eb"
                else:
                    self.mode_btn.configure(text="  💻 Console  ", bg=elevated, fg=muted)
                    self.mode_btn._bg, self.mode_btn._hover = elevated, "#2c3648"
            except Exception:
                pass
        if hasattr(self,"notebook") and hasattr(self,"design_tab_index"):
            if use_gui:
                self.notebook.tab(self.design_tab_index, state="normal")
            else:
                self.notebook.tab(self.design_tab_index, state="hidden")
        if self.config.get("gui_app") != use_gui:
            self.config["gui_app"] = use_gui
            save_config(self.config)

    def _make_toolbar_buttons(self, theme):
        """Rebuild template-style action pills; keep brand (◆ Vertex) on the left."""
        for w in list(self.toolbar.winfo_children()):
            if getattr(w, "_v_brand", False):
                continue
            try:
                txt = ""
                if w.winfo_class() == "Label":
                    txt = str(w.cget("text"))
                if "Vertex" in txt or txt == "◆":
                    continue
            except Exception:
                pass
            if w.winfo_class() == "Frame" and getattr(w, "_v_brand", False):
                continue
            # keep brand frame: marked or first icon frame without toolbar item flag
            if w.winfo_class() == "Frame" and not getattr(w, "_v_toolbar_item", False):
                if any(getattr(k, "_v_brand", False) for k in (w.winfo_children() or [])):
                    continue
                # brand frame itself
                if getattr(w, "_v_brand", False):
                    continue
                # Heuristic: frame that only holds labels (brand)
                kids = w.winfo_children()
                if kids and all(k.winfo_class() == "Label" for k in kids):
                    continue
            try:
                w.destroy()
            except Exception:
                pass
        self.toolbar_buttons = []

        elevated = theme.get("elevated", theme["btn_bg"])
        muted = theme.get("fg_muted", theme["toolbar_fg"])
        border = theme.get("form_border", "#2a3344")

        def _sep():
            s = tk.Frame(self.toolbar, width=1, height=22, bg=border)
            s._v_toolbar_item = True
            s.pack(side=tk.LEFT, padx=8, pady=12)

        def _add(text, cmd, bg, fg, hover, tip="", side=tk.LEFT):
            b = soft_button(self.toolbar, text, command=cmd, bg=bg, fg=fg,
                            hover=hover, padx=12, pady=7)
            b._v_toolbar_item = True
            b.pack(side=side, padx=3, pady=8)
            self.toolbar_buttons.append(b)
            if tip:
                ToolTip(b, tip)
            return b

        _add("  Compile  ", self.compile_file, theme["accent"], "#ffffff",
             "#60a5fa", "Compile (F5)")
        _add("  ▶ Run  ", self.run_program, "#15803d", "#ffffff", "#22c55e", "Run (F6)")
        _sep()
        _add("  New  ", self.new_file, elevated, theme["fg"], "#2c3648", "New (Ctrl+N)")
        _add("  Open  ", self.open_file, elevated, theme["fg"], "#2c3648", "Open (Ctrl+O)")
        _add("  Save  ", self.save_file, "#b45309", "#ffffff", "#f59e0b", "Save (Ctrl+S)")
        _sep()
        _add("  Form  ", self.new_form, "#db2777", "#ffffff", "#ec4899", "New form")
        _add("  Sync  ", self.sync_from_code, "#4f46e5", "#ffffff", "#6366f1", "Sync from code")
        _add("  Find  ", self.show_find_dialog, "#0d9488", "#ffffff", "#14b8a6", "Find / Replace (Ctrl+F)")
        _sep()
        if self.gui_mode:
            self.mode_btn = _add("  GUI  ", self.toggle_mode, "#1e3a5f", "#60a5fa", "#2563eb",
                                 "Toggle GUI / Console", side=tk.RIGHT)
        else:
            self.mode_btn = _add("  Console  ", self.toggle_mode, elevated, muted, "#2c3648",
                                 "Toggle GUI / Console", side=tk.RIGHT)
        try:
            self.mode_btn.pack_forget()
            self.mode_btn.pack(side=tk.RIGHT, padx=12, pady=8)
        except Exception:
            pass

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
                if hasattr(self, "_update_timer") and self._update_timer:
                    self.root.after_cancel(self._update_timer)
                    self._update_timer = None
                self._update_code_for_control(ctrl)
                self._schedule_live_code_sync()

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
            try:
                self.form_w_var.set(str(int(self.form_width)))
                self.form_h_var.set(str(int(self.form_height)))
            except Exception:
                pass
            try:
                self.form_canvas.config(width=int(self.form_width), height=int(self.form_height))
            except Exception:
                pass
            self._redraw_all()
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                pass


    def _select_tool(self, ctype):
        self.palette_tool = ctype
        theme = THEMES[self.current_theme]
        border = theme.get("form_border", "#2a3344")
        elevated = theme.get("elevated", theme["btn_bg"])
        for t, cell in self.palette_btns.items():
            try:
                if t == ctype:
                    cell.configure(highlightbackground=theme["accent"], highlightthickness=2,
                                   bg=theme.get("select_bg", elevated))
                    for ch in cell.winfo_children():
                        ch.configure(bg=theme.get("select_bg", elevated))
                else:
                    cell.configure(highlightbackground=border, highlightthickness=1, bg=elevated)
                    for ch in cell.winfo_children():
                        ch.configure(bg=elevated)
            except Exception:
                pass
        self.status(f"Tool: {ctype}")


    # ---------- .vform (Delphi-style form resource, JSON) ----------

    def _is_gui_project(self):
        """True when form / .vform is relevant (GUI mode or designer has controls / Window)."""
        if getattr(self, "gui_mode", False):
            return True
        try:
            if getattr(self, "design_controls", None) and len(self.design_controls) > 0:
                return True
        except Exception:
            pass
        try:
            if getattr(self, "current_vform_path", None):
                return True
        except Exception:
            pass
        try:
            # Designer was used (non-default size) or form tab exists
            if int(getattr(self, "form_width", 0) or 0) not in (0, 480) or int(getattr(self, "form_height", 0) or 0) not in (0, 320):
                return True
        except Exception:
            pass
        try:
            src = self.editor.get("1.0", "end-1c") if hasattr(self, "editor") else ""
            if looks_like_gui(src):
                return True
        except Exception:
            pass
        return False

    def _vform_path_for_unit(self, vtx_path=None):
        """Unit1.vtx -> Unit1.vform (same folder)."""
        path = vtx_path or self.current_file
        if not path:
            return None
        base, _ = os.path.splitext(path)
        return base + ".vform"

    def form_to_document(self):
        """Serialize designer to a Delphi-DFM-like JSON document (all visual properties)."""
        # Always pull latest size from the designer fields if present
        try:
            if hasattr(self, "form_w_var"):
                self.form_width = max(100, int(self.form_w_var.get() or self.form_width))
            if hasattr(self, "form_h_var"):
                self.form_height = max(80, int(self.form_h_var.get() or self.form_height))
        except Exception:
            pass
        try:
            if hasattr(self, "form_title_var") and self.form_title_var.get().strip():
                self.form_title = self.form_title_var.get().strip()
        except Exception:
            pass
        form_color = self.form_color or ""
        form_rgb = color_rgb_from_stored(form_color) if form_color else None
        left = int(getattr(self, "form_left", 120) or 120)
        top = int(getattr(self, "form_top", 100) or 100)
        width = int(self.form_width)
        height = int(self.form_height)
        form_block = {
            "name": self.form_title or "Form1",
            "caption": self.form_title or "Form1",
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "client_width": width,
            "client_height": height,
            "color": form_color,
        }
        if form_rgb:
            form_block["color_rgb"] = list(form_rgb)
        return {
            "format": "VertexForm",
            "version": 2,
            "unit": os.path.splitext(os.path.basename(self.current_file or "Form1.vtx"))[0],
            # Explicit form dimensions (also nested under "form" for compatibility)
            "width": width,
            "height": height,
            "left": left,
            "top": top,
            "form": form_block,
            "controls": [c.to_dict() for c in self.design_controls],
        }

    def form_from_document(self, doc):
        """Load designer state from a .vform document."""
        if not isinstance(doc, dict):
            raise ValueError("Invalid .vform document")
        form = doc.get("form") or {}
        self.form_title = form.get("caption") or form.get("name") or self.form_title or "Form1"
        # Prefer form.* then top-level width/height
        self.form_width = int(
            form.get("width") or form.get("client_width") or doc.get("width") or self.form_width or 480
        )
        self.form_height = int(
            form.get("height") or form.get("client_height") or doc.get("height") or self.form_height or 320
        )
        self.form_left = int(form.get("left") or doc.get("left") or getattr(self, "form_left", 120) or 120)
        self.form_top = int(form.get("top") or doc.get("top") or getattr(self, "form_top", 100) or 100)
        self.form_color = form.get("color") or ""
        if hasattr(self, "form_title_var"):
            self.form_title_var.set(self.form_title)
        if hasattr(self, "form_w_var"):
            self.form_w_var.set(str(self.form_width))
            self.form_h_var.set(str(self.form_height))
        if hasattr(self, "form_canvas"):
            self.form_canvas.config(width=self.form_width, height=self.form_height)
            try:
                if self.form_color:
                    self.form_canvas.config(bg=self.form_color)
            except Exception:
                pass
        self.design_controls.clear()
        self.selected_control = None
        DesignControl._counter = 0
        for item in doc.get("controls") or []:
            try:
                ctrl = DesignControl.from_dict(item)
                self.design_controls.append(ctrl)
                DesignControl._counter = max(
                    DesignControl._counter,
                    int("".join(ch for ch in ctrl.name if ch.isdigit()) or "0")
                )
            except Exception:
                continue
        self._redraw_all()

    def _save_vform_disk_only(self, path):
        """Write .vform JSON to disk without changing the code editor at all."""
        if not path:
            return False
        try:
            folder = os.path.dirname(path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder, exist_ok=True)
            try:
                if hasattr(self, "form_w_var"):
                    self.form_width = max(100, int(self.form_w_var.get() or self.form_width or 480))
                if hasattr(self, "form_h_var"):
                    self.form_height = max(80, int(self.form_h_var.get() or self.form_height or 320))
            except Exception:
                pass
            doc = self.form_to_document()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
            self.current_vform_path = path
            return True
        except Exception as e:
            try:
                self.status(f"vform write failed: {e}")
            except Exception:
                pass
            return False


    def save_vform(self, path=None, silent=False):
        """Write layout to .vform (JSON). Like saving a Delphi .dfm.
        Skipped entirely for pure console projects."""
        if not self._is_gui_project():
            if not silent:
                self.status("Console mode — .vform not used")
            return False
        path = path or self.current_vform_path or self._vform_path_for_unit()
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".vform",
                filetypes=[("Vertex Form", "*.vform"), ("JSON", "*.json"), ("All", "*.*")],
                title="Save Form (.vform)",
            )
            if not path:
                return False
        try:
            doc = self.form_to_document()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
            self.current_vform_path = path
            # Only inject {$FORM} comment when user explicitly saves form (not silent autosave)
            if not silent:
                self._ensure_vform_import_comment(path)
                self.status(f"Form saved: {os.path.basename(path)}")
            return True
        except Exception as e:
            if not silent:
                messagebox.showerror("Save Form", str(e))
            return False

    def open_vform(self, path=None):
        """Load a .vform into the designer."""
        if not path:
            path = filedialog.askopenfilename(
                filetypes=[("Vertex Form", "*.vform"), ("JSON", "*.json"), ("All", "*.*")],
                title="Open Form (.vform)",
            )
        if not path or not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            self.form_from_document(doc)
            self.current_vform_path = path
            self.status(f"Form loaded: {os.path.basename(path)}")
            # Do NOT write back to the code editor — layout preview only
            return True
        except Exception as e:
            messagebox.showerror("Open Form", str(e))
            return False


    def _ensure_vform_import_comment(self, vform_path):
        """Ensure {$FORM} link + ApplyVForm(...) before RunApp (layout from .vform at runtime).
        Does not rewrite handlers or control creation lines."""
        if not hasattr(self, "editor"):
            return
        rel = os.path.basename(vform_path)
        form_line = '{$FORM "' + rel + '"}  { layout resource — edit in Form Designer }'
        source = self.editor.get("1.0", "end-1c")
        lines = source.splitlines()
        changed = False

        # 1) {$FORM} near top
        form_idx = None
        for idx, ln in enumerate(lines):
            if "{$FORM" in ln or "$FORM" in ln:
                form_idx = idx
                if lines[idx] != form_line:
                    lines[idx] = form_line
                    changed = True
                break
        if form_idx is None:
            insert_at = 0
            for idx, ln in enumerate(lines):
                s = ln.strip()
                if s.startswith("Import ") or s.startswith("{") or s.startswith("//") or s == "":
                    insert_at = idx + 1
                    continue
                break
            lines.insert(insert_at, form_line)
            changed = True

        # 2) ApplyVForm before RunApp (once)
        has_apply = any("ApplyVForm" in ln for ln in lines)
        if not has_apply:
            for idx, ln in enumerate(lines):
                if re.search(r"\bRunApp\s*\(", ln):
                    indent = re.match(r"^(\s*)", ln).group(1)
                    lines.insert(idx, indent + 'ApplyVForm("' + rel + '");')
                    changed = True
                    break

        if changed:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "\n".join(lines))
            try:
                self.root.after(20, lambda: highlight(self.editor))
            except Exception:
                pass


    def _persist_form_resource(self, silent=False):
        """Delphi-style: write layout to .vform and ensure {$FORM \"...\"} link in source.
        Never rewrites control creation or event handlers."""
        # 1) Sync designer fields into memory
        try:
            if hasattr(self, "form_w_var"):
                self.form_width = max(100, int(self.form_w_var.get() or self.form_width or 480))
            if hasattr(self, "form_h_var"):
                self.form_height = max(80, int(self.form_h_var.get() or self.form_height or 320))
            if hasattr(self, "form_title_var") and (self.form_title_var.get() or "").strip():
                self.form_title = self.form_title_var.get().strip()
        except Exception:
            pass

        # 2) Need a path (unit must be saved once)
        path = self.current_vform_path or self._vform_path_for_unit()
        if not path:
            if not silent:
                try:
                    self.status("Save the .vtx once so .vform can be created next to it")
                except Exception:
                    pass
            return False

        # 3) Write .vform (full layout JSON)
        ok = False
        try:
            ok = bool(self._save_vform_disk_only(path))
        except Exception as e:
            if not silent:
                try:
                    self.status(f"vform save failed: {e}")
                except Exception:
                    pass
            return False

        # 4) Ensure {$FORM "..."} link in editor (one line only — does not touch handlers)
        try:
            self._ensure_vform_import_comment(path)
        except Exception:
            pass

        # 5) Refresh Form tab preview
        try:
            self._refresh_vform_tab()
        except Exception:
            pass

        if ok and not silent:
            try:
                self.status(f"Form resource saved: {os.path.basename(path)}")
            except Exception:
                pass
        return ok

    def _autosave_vform(self):
        """Silent persist of .vform layout resource."""
        try:
            self._persist_form_resource(silent=True)
        except Exception:
            path = self.current_vform_path or self._vform_path_for_unit()
            if path:
                self._save_vform_disk_only(path)


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
            self.mode_btn.configure(text="  🖥 GUI  ")
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

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        try:
            w = int(self.form_w_var.get())
            h = int(self.form_h_var.get())
        except Exception:
            return
        if w < 100:
            w = 100
        if h < 80:
            h = 80
        self.form_width, self.form_height = w, h
        try:
            title = self.form_title_var.get().strip()
            if title:
                self.form_title = title
        except Exception:
            pass
        try:
            self.form_canvas.config(width=w, height=h)
        except Exception:
            pass
        self._redraw_all()
        # Persist dimensions into .vtx Window(...) and .vform
        try:
            left = int(getattr(self, "form_left", 120) or 120)
            top = int(getattr(self, "form_top", 100) or 100)
            source = self.editor.get("1.0", "end-1c")
            lines = source.splitlines()
            changed = False
            for i, line in enumerate(lines):
                if re.match(r'^\s*Window\s*\(', line):
                    indent = re.match(r'^(\s*)', line).group(1)
                    lines[i] = f"{indent}Window({w}, {h}, {left}, {top});"
                    changed = True
                if re.match(r'^\s*SetWindowTitle\s*\(', line):
                    indent = re.match(r'^(\s*)', line).group(1)
                    lines[i] = f'{indent}SetWindowTitle("{self.form_title}");'
                    changed = True
            if changed:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
                try:
                    self._mark_dirty(True)
                except Exception:
                    pass
            self._autosave_vform()
        except Exception:
            pass


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
        if tool == "sevenseg":
            dw, dh = 70, 90
            cap = "0"
            x = max(0, min(event.x, self.form_width - dw))
            y = max(0, min(event.y, self.form_height - dh))
        ctrl = DesignControl(tool, x, y, dw, dh, cap)
        if tool == "sevenseg":
            ctrl.caption = "0"
        self.design_controls.append(ctrl)
        self._redraw_all()
        self._select_control(ctrl)
        self._select_tool("select")
        self.status(f"Placed {ctrl.name}")
        self._insert_code_for_control(ctrl)
        self._schedule_live_code_sync()

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
            self._update_timer = self.root.after(150, lambda c=ctrl: self._update_code_for_control(c))

    def _form_release(self, event):
        if hasattr(self, "_update_timer") and self._update_timer:
            self.root.after_cancel(self._update_timer)
            self._update_timer = None
        dragged = self._drag[0] if self._drag else None
        resized = self._resize[0] if getattr(self, "_resize", None) else None
        self._resize_release(event)
        self._form_resize_release(event)
        self._drag = None
        # Live code update after move/resize (no Generate click required)
        target = dragged or resized
        if target is not None:
            try:
                self._update_code_for_control(target)
            except Exception:
                pass
        self._schedule_live_code_sync()

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
        elif ctrl.ctype == "statusbar":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#e8eef7", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+8, y+h//2,
                          text=ctrl.caption or "Ready", anchor=tk.W,
                          font=("Segoe UI", 8), fill="#1e3a5f"))
        elif ctrl.ctype == "hyperterm":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#0b1020", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+8, y+10,
                          text="HyperTerm>", anchor=tk.NW,
                          font=("Consolas", 8), fill="#3ddc97"))
        elif ctrl.ctype == "timer":
            items.append(self.form_canvas.create_oval(x, y, x+w, y+h,
                          fill=fill or "#fff7ed", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.caption or "⏱", font=("Segoe UI", 9), fill="#c2410c"))
        elif ctrl.ctype == "sevenseg":
            # Realistic multi-digit LED seven-segment preview
            bg = fill or "#0f0808"
            items.append(self.form_canvas.create_rectangle(
                x, y, x + w, y + h, fill=bg, outline=outline or "#3f1a1a", width=max(width, 2)))
            cap = "".join(ch for ch in (ctrl.caption or "0") if ch.isdigit()) or "0"
            n = max(1, min(6, len(cap)))
            self._draw_seven_seg_multi(items, x, y, w, h, cap[-n:], theme)
        elif ctrl.ctype == "comport":
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#1a1a2e", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.caption or "COM1", anchor=tk.CENTER,
                          font=("Segoe UI", 8, "bold"), fill="#7fdbff"))
        else:
            items.append(self.form_canvas.create_rectangle(x, y, x+w, y+h,
                          fill=fill or "#ffffff", outline=outline, width=width))
            items.append(self.form_canvas.create_text(x+w//2, y+h//2,
                          text=ctrl.name, font=("Segoe UI", 8)))

        tag = self._ctrl_tag(ctrl)
        for item in items:
            self.form_canvas.addtag_withtag(tag, item)
            self.form_canvas.addtag_withtag("control", item)
        ctrl.widget = items

    def _draw_seven_seg_multi(self, items, x, y, w, h, digits, theme):
        """Draw one or more LED-style seven-segment digits."""
        digits = digits or "0"
        n = len(digits)
        pad = max(4, min(w, h) // 16)
        gap = max(3, w // (n * 12 + 1))
        dig_w = max(12, (w - 2 * pad - (n - 1) * gap) // n)
        dig_h = max(16, h - 2 * pad)
        x0 = x + pad
        y0 = y + pad
        for i, ch in enumerate(digits):
            d = int(ch) if ch.isdigit() else -1
            self._draw_seven_seg(items, x0 + i * (dig_w + gap), y0, dig_w, dig_h, d, theme)

    def _draw_seven_seg(self, items, x, y, w, h, digit, theme):
        """Draw a single digit with tapered hexagonal LED segments (real 7-seg shape)."""
        segments_map = {
            0: (1, 1, 1, 1, 1, 1, 0),
            1: (0, 1, 1, 0, 0, 0, 0),
            2: (1, 1, 0, 1, 1, 0, 1),
            3: (1, 1, 1, 1, 0, 0, 1),
            4: (0, 1, 1, 0, 0, 1, 1),
            5: (1, 0, 1, 1, 0, 1, 1),
            6: (1, 0, 1, 1, 1, 1, 1),
            7: (1, 1, 1, 0, 0, 0, 0),
            8: (1, 1, 1, 1, 1, 1, 1),
            9: (1, 1, 1, 1, 0, 1, 1),
        }
        seg = (0, 0, 0, 0, 0, 0, 0) if digit < 0 else segments_map.get(digit, (0, 0, 0, 0, 0, 0, 0))
        t = max(2, min(w, h) // 8)
        d = max(1, t // 2)
        mid = y + h // 2
        on, off = "#ff2e2e", "#3a1010"

        def hex_h(x1, y0, x2, th, color):
            # horizontal hexagon: pointed ends
            pts = [
                x1 + d, y0,
                x2 - d, y0,
                x2, y0 + d,
                x2 - d, y0 + th,
                x1 + d, y0 + th,
                x1, y0 + d,
            ]
            items.append(self.form_canvas.create_polygon(pts, fill=color, outline=color, width=0))

        def hex_v(x0, y1, y2, th, color):
            # vertical hexagon: pointed ends
            pts = [
                x0 + d, y1,
                x0 + th, y1 + d,
                x0 + th, y2 - d,
                x0 + d, y2,
                x0, y2 - d,
                x0, y1 + d,
            ]
            items.append(self.form_canvas.create_polygon(pts, fill=color, outline=color, width=0))

        xR = x + w - t
        yB = y + h - t
        # A B C D E F G
        hex_h(x + t, y, x + w - t, t, on if seg[0] else off)
        hex_v(xR, y + t, mid, t, on if seg[1] else off)
        hex_v(xR, mid, yB, t, on if seg[2] else off)
        hex_h(x + t, yB, x + w - t, t, on if seg[3] else off)
        hex_v(x, mid, yB, t, on if seg[4] else off)
        hex_v(x, y + t, mid, t, on if seg[5] else off)
        hex_h(x + t, mid - t // 2, x + w - t, t, on if seg[6] else off)

    def _refresh_events_panel(self, ctrl=None):
        """Fill Events tab with event list for selected control or form."""
        if not hasattr(self, "events_list"):
            return
        self.events_list.delete(0, tk.END)
        title = "(none selected)"
        events = []
        if self.selected_form:
            title = "Form: " + self.form_title
            info = COMPONENT_INFO.get("form", {})
            events = info.get("events", [])
        elif ctrl is not None:
            title = "%s  [%s]" % (ctrl.name, ctrl.ctype)
            info = COMPONENT_INFO.get(ctrl.ctype, {})
            events = list(info.get("events", []))
        elif self.selected_control is not None:
            return self._refresh_events_panel(self.selected_control)
        if hasattr(self, "events_sel"):
            self.events_sel.config(text=title)
        if not events:
            self.events_list.insert(tk.END, "(no events)")
        else:
            for ev in events:
                self.events_list.insert(tk.END, ev)

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
            self._refresh_events_panel(ctrl)
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
        self._refresh_events_panel(None)
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
        if ctrl.ctype == "sevenseg":
            # only one digit 0-9
            digs = "".join(ch for ch in new_caption if ch.isdigit())
            if not digs:
                digs = "0"
            new_caption = digs[-1]  # single digit 0-9
            if "caption" in self.prop_vars:
                self.prop_vars["caption"].set(new_caption)
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
        self._schedule_live_code_sync()

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
    def _schedule_live_code_sync(self):
        """Debounce: push designer state into source. Designer tab only."""
        if getattr(self, "_suspend_live_sync", False):
            return
        if not self._on_designer_tab():
            return
        if hasattr(self, "_live_sync_job") and self._live_sync_job:
            try:
                self.root.after_cancel(self._live_sync_job)
            except Exception:
                pass
        self._live_sync_job = self.root.after(250, self._live_sync_all_controls)

    def _live_sync_all_controls(self):
        """Update form lines only while the Designer tab is active."""

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        self._live_sync_job = None
        if getattr(self, "_suspend_live_sync", False):
            return
        if not self._on_designer_tab():
            return
        try:
            for c in list(self.design_controls):
                self._update_code_for_control(c)
            # form size/title
            self._sync_form_header_to_code()
            if not getattr(self, "_dirty", False):
                self._mark_dirty(True)
            self._autosave_vform()
        except Exception as e:
            self.status(f"Live sync: {e}")

    def _sync_form_header_to_code(self):
        """Patch Window(...) and SetWindowTitle in editor to match designer."""

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        try:
            source = self.editor.get("1.0", "end-1c")
            lines = source.splitlines()
            changed = False
            for i, line in enumerate(lines):
                m = re.match(r'^(\s*)Window\s*\(\s*\d+\s*,\s*\d+\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*;', line)
                if m:
                    indent, x, y = m.group(1), m.group(2), m.group(3)
                    lines[i] = f"{indent}Window({self.form_width}, {self.form_height}, {x}, {y});"
                    changed = True
                m2 = re.match(r'^(\s*)SetWindowTitle\s*\(\s*"[^"]*"\s*\)\s*;', line)
                if m2:
                    lines[i] = f'{m2.group(1)}SetWindowTitle("{self.form_title}");'
                    changed = True
            if changed:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
        except Exception:
            pass

    def _update_code_for_property(self, ctrl, prop, value):

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return

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
            if ctrl.ctype == "sevenseg":
                digs = "".join(ch for ch in str(value) if ch.isdigit()) or "0"
                value = digs[-1]
                old_pattern = r'^(\s*)SetSevenSeg(?:Digits)?\s*\(\s*' + re.escape(ctrl.name) + r'\s*,\s*\d+'
                # replace whole SetSevenSeg line
                source = self.editor.get("1.0", "end-1c")
                lines = source.splitlines()
                found = False
                for i, line in enumerate(lines):
                    if re.search(r'SetSevenSeg(?:Digits)?\s*\(\s*' + re.escape(ctrl.name) + r'\b', line, re.I):
                        lines[i] = f'  SetSevenSeg({ctrl.name}, {value});'
                        found = True
                        break
                if found:
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", "\n".join(lines))
                    self.root.after(20, lambda: highlight(self.editor))
                    self.update_line_numbers()
                elif not self._replace_line_in_code(
                    r'^(\s*)SetText\s*\(\s*' + re.escape(ctrl.name) + r'\s*,\s*".*?"\s*\)\s*;',
                    f'  SetSevenSeg({ctrl.name}, {value});', re.IGNORECASE
                ):
                    self._insert_lines_in_form_section([f'  SetSevenSeg({ctrl.name}, {value});'])
                return
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

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
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
        """Write this control's geometry into the .vtx source.
        Only while Form Designer tab is active — never when user is editing Code."""

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        try:
            if not self._on_designer_tab():
                return
            if self._code_looks_duplicated():
                self.status("Code has multiple Enter/Exit — designer will not modify it")
                return
            type_map = {
                "button": "Button", "edit": "Edit", "label": "Label", "memo": "Memo",
                "listbox": "ListBox", "combo": "ComboBox", "checkbox": "CheckBox",
                "radio": "Radio", "groupbox": "GroupBox", "panel": "Panel",
                "sevenseg": "SevenSeg", "hyperterm": "HyperTerm", "statusbar": "StatusBar",
            }
            code_type = type_map.get(ctrl.ctype.lower(), ctrl.ctype.capitalize())
            source = self.editor.get("1.0", "end-1c")
            lines = source.splitlines()
            name = re.escape(ctrl.name)

            # Pattern for creation line: name <- Type(..., w, h, x, y);
            pat = re.compile(
                r'^(\s*)' + name + r'\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel|SevenSeg|HyperTerm)\s*\(\s*\w+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)\s*;',
                re.IGNORECASE
            )
            status_pat = re.compile(
                r'^(\s*)' + name + r'\s*<-\s*StatusBar\s*\(\s*\w+\s*,\s*\d+\s*\)\s*;',
                re.IGNORECASE
            )

            # Find if a line already exists; if yes, replace it and also remove any other duplicates
            existing_indices = []
            for i, line in enumerate(lines):
                if pat.match(line) or status_pat.match(line):
                    existing_indices.append(i)

            if existing_indices:
                # Keep only the first occurrence, remove the rest
                keep_idx = existing_indices[0]
                # Remove all other duplicates (reverse order to preserve indices)
                for i in sorted(existing_indices[1:], reverse=True):
                    del lines[i]
                # Now replace the first occurrence with the new line
                indent = ""
                m = pat.match(lines[keep_idx]) or status_pat.match(lines[keep_idx])
                if m:
                    indent = m.group(1) or ""
                if ctrl.ctype == "statusbar":
                    new_line = f"{indent}{ctrl.name} <- StatusBar(MainWindow, {ctrl.h});"
                else:
                    new_line = f"{indent}{ctrl.name} <- {code_type}(MainWindow, {ctrl.w}, {ctrl.h}, {ctrl.x}, {ctrl.y});"
                lines[keep_idx] = new_line
                updated = True
            else:
                # No existing line – insert it
                self._insert_code_for_control(ctrl)
                return

            # Update SetSevenSeg / SetText for caption when present
            if ctrl.ctype == "sevenseg":
                dig = "".join(ch for ch in (ctrl.caption or "0") if ch.isdigit()) or "0"
                dig = dig[-1]
                for i, line in enumerate(lines):
                    if re.search(r'SetSevenSeg(?:Digits)?\s*\(\s*' + name + r'\b', line, re.I):
                        lines[i] = f"  SetSevenSeg({ctrl.name}, {dig});"
                        break
            elif ctrl.caption is not None and ctrl.ctype not in ("listbox", "combo", "timer", "comport"):
                for i, line in enumerate(lines):
                    if re.search(r'SetText\s*\(\s*' + name + r'\s*,', line, re.I):
                        lines[i] = f'  SetText({ctrl.name}, "{ctrl.caption}");'
                        break

            # SetBackColor
            if ctrl.color:
                rgb = color_rgb_from_stored(ctrl.color)
                if rgb:
                    r, g, b = rgb
                    newc = f'  SetBackColor({ctrl.name}, ColorRGB({r}, {g}, {b}));'
                    found = False
                    for i, line in enumerate(lines):
                        if re.search(r'^\s*SetBackColor\s*\(\s*' + name + r'\b', line, re.I):
                            lines[i] = newc
                            found = True
                            break
                    if not found:
                        # Insert after creation line
                        for i, line in enumerate(lines):
                            if re.search(r'^\s*' + name + r'\s*<-\s*', line):
                                lines.insert(i + 1, newc)
                                break
            tc = getattr(ctrl, "text_color", "") or ""
            if tc:
                rgb = color_rgb_from_stored(tc)
                if rgb:
                    r, g, b = rgb
                    newc = f'  SetCtrlTextColor({ctrl.name}, ColorRGB({r}, {g}, {b}));'
                    found = False
                    for i, line in enumerate(lines):
                        if re.search(r'^\s*SetCtrlTextColor\s*\(\s*' + name + r'\b', line, re.I):
                            lines[i] = newc
                            found = True
                            break
                    if not found:
                        for i, line in enumerate(lines):
                            if re.search(r'^\s*' + name + r'\s*<-\s*', line):
                                lines.insert(i + 1, newc)
                                break

            # Write back
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", "\n".join(lines))
            try:
                self._mark_dirty(True)
            except Exception:
                pass
            self.root.after(20, lambda: highlight(self.editor))
            self.update_line_numbers()
        except Exception as e:
            try:
                self.status(f"Code update failed: {e}")
            except Exception:
                pass


    def _replace_line_in_code(self, old_pattern, new_line, flags=0):

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
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

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        if not self._on_designer_tab():
            return
        if self._code_looks_duplicated():
            return
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
            "sevenseg": "SevenSeg",
            "hyperterm": "HyperTerm",
            "statusbar": "StatusBar",
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
            if ctrl.ctype == "sevenseg":
                dig = "".join(ch for ch in (ctrl.caption or "0") if ch.isdigit()) or "0"
                lines.append(f'  SetSevenSeg({ctrl.name}, {dig[-1]});')
            elif ctrl.caption and ctrl.ctype not in ("listbox", "combo", "statusbar", "timer"):
                lines.append(f'  SetText({ctrl.name}, "{ctrl.caption}");')
            if ctrl.color:
                rgb = color_rgb_from_stored(ctrl.color)
                if rgb:
                    r, g, b = rgb
                    lines.append(f'  SetBackColor({ctrl.name}, ColorRGB({r}, {g}, {b}));')
            tc = getattr(ctrl, "text_color", "") or ""
            if tc:
                rgb = color_rgb_from_stored(tc)
                if rgb:
                    r, g, b = rgb
                    lines.append(f'  SetCtrlTextColor({ctrl.name}, ColorRGB({r}, {g}, {b}));')
            if not getattr(ctrl, "enabled", True):
                lines.append(f'  DisableCtrl({ctrl.name});')
            if not getattr(ctrl, "visible", True):
                lines.append(f'  HideCtrl({ctrl.name});')
        self._ensure_var_decl(ctrl)
        self._insert_lines_in_form_section(lines, before_pattern=r'// --- FORM END ---')

    def _ensure_var_decl(self, ctrl):
        source = self.editor.get("1.0", "end-1c")
        if re.search(r'\b' + re.escape(ctrl.name) + r'\s*:', source):
            return
        vtype = "Integer" if ctrl.ctype == "comport" else "HWND"
        decl = f'  {ctrl.name}: {vtype};'
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == "Var" or line.strip().startswith("Var "):
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("{")):
                    j += 1
                lines.insert(j, decl)
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
                return
        for i, line in enumerate(lines):
            if line.strip().startswith("Enter "):
                lines.insert(i + 1, "Var")
                lines.insert(i + 2, decl)
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", "\n".join(lines))
                self.root.after(20, lambda: highlight(self.editor))
                self.update_line_numbers()
                return


    def _insert_lines_in_form_section(self, lines_to_insert, before_pattern=None):
        """Insert control lines AFTER Window(...) and BEFORE RunApp()/OnClick.
        Wrong order (before Window or after RunApp) makes controls invisible at runtime.
        """
        source = self.editor.get("1.0", "end-1c")
        for new_line in lines_to_insert:
            stripped_new = new_line.strip()
            if stripped_new and stripped_new in source:
                return False

        lines = source.splitlines()
        start_marker = "// --- FORM START ---"
        end_marker = "// --- FORM END ---"
        insert_pos = None

        # 1) Prefer explicit FORM section
        if start_marker in source and end_marker in source:
            start_idx = end_idx = None
            for i, line in enumerate(lines):
                if line.strip() == start_marker:
                    start_idx = i
                elif line.strip() == end_marker:
                    end_idx = i
                    break
            if start_idx is not None and end_idx is not None:
                insert_pos = end_idx
                # after Window / title / color if present inside section
                last_setup = start_idx
                for i in range(start_idx + 1, end_idx):
                    if re.search(
                        r'^\s*(Window|SetWindowTitle|SetFormColor)\s*\(',
                        lines[i],
                    ):
                        last_setup = i
                insert_pos = last_setup + 1
                if before_pattern:
                    for i in range(start_idx + 1, end_idx):
                        if re.search(before_pattern, lines[i]):
                            insert_pos = i
                            break

        # 2) No markers: place after last Window/SetWindowTitle/SetFormColor,
        #    and before OnClick / RunApp
        if insert_pos is None:
            last_setup = -1
            first_tail = None
            for i, line in enumerate(lines):
                if re.search(
                    r'^\s*(Window|SetWindowTitle|SetFormColor)\s*\(',
                    line,
                ):
                    last_setup = i
                if first_tail is None and re.search(
                    r'^\s*(OnClick|RunApp)\s*\(',
                    line,
                ):
                    first_tail = i
            if last_setup >= 0:
                insert_pos = last_setup + 1
                if first_tail is not None and first_tail > last_setup:
                    insert_pos = first_tail
            elif first_tail is not None:
                insert_pos = first_tail

        if insert_pos is None:
            for i, line in enumerate(lines):
                if line.strip().startswith("Exit"):
                    for j in range(i - 1, -1, -1):
                        if lines[j].strip() in ("Stop", "Stop;"):
                            insert_pos = j
                            break
                    break
        if insert_pos is None:
            insert_pos = len(lines)

        new_lines = lines[:insert_pos] + list(lines_to_insert) + lines[insert_pos:]
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", "\n".join(new_lines))
        try:
            self._mark_dirty(True)
        except Exception:
            pass
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
        self._suspend_live_sync = True
        try:
            self._sync_from_code_impl()
        finally:
            self._suspend_live_sync = False

    def _sync_from_code_impl(self):

        try:
            if not hasattr(self, "editor") or not hasattr(self, "form_canvas"):
                return
            source = self.editor.get("1.0", "end-1c")
            if not source or not source.strip():
                self.status("No code to sync")
                return

            pattern = re.compile(
                r'(\w+)\s*<-\s*(Button|Edit|Label|Memo|CheckBox|Radio|ListBox|ComboBox|GroupBox|Panel|SevenSeg|HyperTerm)\s*\(\s*(\w+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            assignments = {}
            captions = {}
            colors = {}
            type_counts = {
                "button": 0, "edit": 0, "label": 0, "memo": 0, "checkbox": 0, "radio": 0,
                "listbox": 0, "combo": 0, "groupbox": 0, "panel": 0, "comport": 0,
                "sevenseg": 0, "hyperterm": 0, "statusbar": 0, "timer": 0,
            }
            vcl_to_ctype = {
                "button": "button", "edit": "edit", "label": "label", "memo": "memo",
                "checkbox": "checkbox", "radio": "radio", "listbox": "listbox",
                "combobox": "combo", "groupbox": "groupbox", "panel": "panel",
                "sevenseg": "sevenseg", "hyperterm": "hyperterm",
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

            comport_pat = re.compile(
                r'(\w+)\s*<-\s*ComOpen\s*\(\s*"([^"]*)"\s*,\s*(\d+)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            for match in comport_pat.finditer(source):
                var_name, port, baud = match.groups()
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


            status_pat = re.compile(
                r'(\w+)\s*<-\s*StatusBar\s*\(\s*(\w+)\s*,\s*(\d+)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            for match in status_pat.finditer(source):
                var_name, parent, height = match.groups()
                try:
                    hh = int(height)
                except ValueError:
                    hh = 24
                assignments[var_name] = ("statusbar", 0, max(0, self.form_height - hh), self.form_width, hh)
                captions[var_name] = captions.get(var_name, "Ready")
                type_counts["statusbar"] = type_counts.get("statusbar", 0) + 1

            settext_pattern = re.compile(
                r'SetText\s*\(\s*(\w+)\s*,\s*"([^"]*)"\s*\)\s*;', re.MULTILINE
            )
            for match in settext_pattern.finditer(source):
                var, cap = match.groups()
                captions[var] = cap

            seven_pat = re.compile(
                r'SetSevenSeg(?:Digits)?\s*\(\s*(\w+)\s*,\s*(\d+)',
                re.MULTILINE | re.IGNORECASE
            )
            for match in seven_pat.finditer(source):
                var, val = match.groups()
                dig = val[-1] if val else "0"
                captions[var] = dig

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

            text_color_pat = re.compile(
                r'SetCtrlTextColor\s*\(\s*(\w+)\s*,\s*ColorRGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)\s*;',
                re.MULTILINE | re.IGNORECASE
            )
            text_colors = {}
            for match in text_color_pat.finditer(source):
                var, r, g, b = match.groups()
                try:
                    text_colors[var] = color_hex_from_rgb(int(r), int(g), int(b))
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

            win_match = re.search(
                r'Window\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
                source
            )
            if not win_match:
                win_match = re.search(r'Window\s*\(\s*(\d+)\s*,\s*(\d+)\s*,', source)
            if win_match:
                try:
                    fw, fh = int(win_match.group(1)), int(win_match.group(2))
                    if fw >= 100 and fh >= 80:
                        self.form_width = fw
                        self.form_height = fh
                        if win_match.lastindex and win_match.lastindex >= 4:
                            self.form_left = int(win_match.group(3))
                            self.form_top = int(win_match.group(4))
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
                self.status("No controls in code — designer left unchanged (Generate Code first)")
                self._redraw_all()
                return

            prev_sel = self.selected_control.name if self.selected_control else None
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
                tcol = text_colors.get(var_name, "")
                ctrl = DesignControl(ctype, x, y, w, h, cap, col, tcol)
                ctrl.name = var_name
                self.design_controls.append(ctrl)

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
            if not hasattr(self, "notebook"):
                return
            current = self.notebook.index(self.notebook.select())
            prev = getattr(self, "_prev_tab_index", None)
            self._prev_tab_index = current

            # Leaving Form Designer → snapshot .vform only (never rewrite .vtx here)
            if prev is not None and hasattr(self, "design_tab_index") and prev == self.design_tab_index:
                if current != self.design_tab_index:
                    try:
                        self._autosave_vform()
                    except Exception:
                        pass

            # Entering Form Designer → build designer from current code (code is source of truth)
            if hasattr(self, "design_tab_index") and current == self.design_tab_index:
                self.root.after(40, self._sync_from_code_impl)
                self.root.after(100, self._autosave_vform)

            try:
                tab_text = self.notebook.tab(current, "text")
            except Exception:
                tab_text = ""
            if "Explorer" in str(tab_text):
                self.root.after(40, self._update_code_explorer)
            if "vform" in str(tab_text).lower() or "Form (" in str(tab_text):
                self.root.after(40, self._refresh_vform_tab)
        except Exception:
            pass

    def _flush_designer_to_storage(self):
        """Persist designer geometry to .vtx only on Designer tab; always may snapshot .vform."""

        # Layout resource model: designer writes .vform only (like Delphi .dfm).
        # Do not rewrite hand-written .vtx logic unless explicitly allowed.
        if not getattr(self, "_allow_designer_code_write", False):
            try:
                self._persist_form_resource(silent=True)
            except Exception:
                try:
                    self._autosave_vform()
                except Exception:
                    pass
            return
        try:
            if not self._is_gui_project() and not getattr(self, "design_controls", None):
                return
            if self._on_designer_tab():
                for c in list(getattr(self, "design_controls", []) or []):
                    self._update_code_for_control(c)
                try:
                    self._sync_form_header_to_code()
                except Exception:
                    pass
            if self._is_gui_project():
                path = self.current_vform_path or self._vform_path_for_unit()
                if path:
                    self._save_vform_disk_only(path)
            self.status("Designer layout saved")
        except Exception as e:
            self.status(f"Flush failed: {e}")


    def _reload_designer_from_storage(self):
        """Prefer code editor layout; .vform only if code has no form section."""
        try:
            source = ""
            try:
                source = self.editor.get("1.0", "end-1c")
            except Exception:
                pass
            has_form_in_code = bool(
                source and (
                    "Window(" in source
                    or "// --- FORM START ---" in source
                    or "SevenSeg(" in source
                    or "Button(" in source
                )
            )
            if has_form_in_code:
                self.sync_from_code()
                # keep .vform in sync with code
                try:
                    self._autosave_vform()
                except Exception:
                    pass
                return
            vform = self.current_vform_path or self._vform_path_for_unit()
            if vform and os.path.isfile(vform):
                self._suspend_live_sync = True
                try:
                    with open(vform, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    self.form_from_document(doc)
                    self.current_vform_path = vform
                    self.status(f"Designer loaded from {os.path.basename(vform)}")
                finally:
                    self._suspend_live_sync = False
                return
            self.sync_from_code()
        except Exception as e:
            try:
                self.sync_from_code()
            except Exception:
                self.status(f"Reload designer: {e}")


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
                lines.append(f'  {c.name} <- StatusBar({parent}, {c.h});')
                if c.caption:
                    lines.append(f'  SetText({c.name}, "{c.caption}");')
            elif c.ctype == "hyperterm":
                lines.append(f'  {c.name} <- HyperTerm({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
            elif c.ctype == "timer":
                lines.append(f'  {{ Timer {c.name} — interval from caption }}')
                try:
                    interval = int(''.join(ch for ch in (c.caption or "1000") if ch.isdigit()) or "1000")
                except Exception:
                    interval = 1000
                lines.append(f'  OnTimer(@OnControlTimer);')
                lines.append(f'  StartTimer({interval});')
            elif c.ctype == "sevenseg":
                lines.append(f'  {c.name} <- SevenSeg({parent}, {c.w}, {c.h}, {c.x}, {c.y});')
                digits = ''.join(ch for ch in (c.caption or "0") if ch.isdigit()) or "0"
                try:
                    val = int(digits)
                except Exception:
                    val = 0
                nd = max(1, min(6, len(digits)))
                if nd > 1:
                    lines.append(f'  SetSevenSegDigits({c.name}, {val}, {nd});')
                else:
                    lines.append(f'  SetSevenSeg({c.name}, {val});')
                rgb = color_rgb_from_stored(c.color or "")
                if rgb:
                    r, g, b = rgb
                    # on / off / bg derived from chosen color
                    lines.append(
                        f'  SetSevenSegColor({c.name}, ColorRGB({r}, {g}, {b}), '
                        f'ColorRGB({max(r//6, 8)}, {max(g//6, 4)}, {max(b//6, 4)}), '
                        f'ColorRGB({max(r//12, 4)}, {max(g//12, 2)}, {max(b//12, 2)}));'
                    )
            else:
                lines.append(f'  {c.name} <- Label({parent}, {c.w}, {c.h}, {c.x}, {c.y});')

            if c.caption and c.ctype not in ("listbox", "combo", "statusbar", "sevenseg", "timer", "comport"):
                lines.append(f'  SetText({c.name}, "{c.caption}");')
            if c.ctype != "sevenseg":
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
        self._mark_dirty(True)
        self._last_snapshot = self.editor.get("1.0", "end-1c")
        self._append_output(f"Generated form '{title}' with {len(self.design_controls)} control(s).\n", "success")
        self.root.after(100, self._update_code_explorer)

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

    def _on_key_press(self, event):
        """Before each key, remember text so we can push undo after the change."""
        if self._suspend_undo:
            return
        # ignore pure modifiers / navigation that don't change text alone
        if event.keysym in (
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
            "Escape", "Caps_Lock", "Num_Lock", "Scroll_Lock",
        ):
            return
        # Ctrl shortcuts handled elsewhere
        if event.state & 0x4:  # Control
            return
        self._last_snapshot = self.editor.get("1.0", "end-1c")

    def _on_key_release(self, event):
        self.update_line_numbers()
        self.update_cursor_position()
        if self._highlight_job:
            try:
                self.root.after_cancel(self._highlight_job)
            except Exception:
                pass
        self._highlight_job = self.root.after(80, lambda: highlight(self.editor))
        try:
            self._editor_keyrelease_ac(event)
        except Exception:
            pass
        # After key, if text changed vs snapshot → push undo + dirty
        if self._suspend_undo:
            return
        if event.keysym in (
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
            "Escape",
        ):
            return
        if event.state & 0x4:
            return
        try:
            current = self.editor.get("1.0", "end-1c")
            if self._last_snapshot is not None and current != self._last_snapshot:
                self._push_undo_snapshot(self._last_snapshot)
                self._mark_dirty(True)
                self._last_snapshot = current
            elif self._last_snapshot is None:
                self._last_snapshot = current
        except Exception:
            pass


    def _on_cursor_move(self, event=None):
        self.update_cursor_position()

    def _on_modified(self, event=None):
        try:
            self.editor.edit_modified(False)
        except Exception:
            pass
        # Ignore during undo/redo apply
        if getattr(self, "_suspend_undo", False):
            return
        self.update_line_numbers()


    def toggle_mode(self):
        self.gui_mode = not self.gui_mode
        self.config["gui_app"] = self.gui_mode
        save_config(self.config)
        theme = THEMES[self.current_theme]
        elevated = theme.get("elevated", theme["btn_bg"])
        muted = theme.get("fg_muted", theme["toolbar_fg"])
        if hasattr(self, "mode_btn") and self.mode_btn is not None:
            try:
                if self.gui_mode:
                    self.mode_btn.configure(text="  🖥 GUI  ", bg="#1e3a5f", fg="#60a5fa")
                    self.mode_btn._bg = "#1e3a5f"
                    self.mode_btn._hover = "#2563eb"
                else:
                    self.mode_btn.configure(text="  💻 Console  ", bg=elevated, fg=muted)
                    self.mode_btn._bg = elevated
                    self.mode_btn._hover = "#2c3648"
            except Exception:
                pass
        self._update_ui_mode()
        self.status("Mode: " + ("GUI" if self.gui_mode else "Console"))


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
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_snapshot = self.editor.get("1.0", "end-1c")
        self._mark_dirty(False)
        self.root.title(f"{APP_NAME} v{APP_VERSION} - Untitled")
        self.gui_mode = True
        self.config["gui_app"] = True
        self.config["auto_detect_gui"] = True
        save_config(self.config)
        if hasattr(self, "mode_btn"):
            self.mode_btn.configure(text="  🖥 GUI  ")
        self._update_ui_mode()
        self.root.after(30, lambda: highlight(self.editor))
        self.update_line_numbers()
        self.status("New file (Import vcl.vtx)")
        self.root.after(100, self._update_code_explorer)

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
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._last_snapshot = content
            self._mark_dirty(False)
            self.current_file = path
            self.root.title(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(path)}")
            if self.config.get("auto_detect_gui", True) and looks_like_gui(content):
                self.gui_mode = True
                self.config["gui_app"] = True
                save_config(self.config)
                if hasattr(self, "mode_btn"):
                    self.mode_btn.configure(text="  🖥 GUI  ")
            self._update_ui_mode()
            self.root.after(30, lambda: highlight(self.editor))
            self.update_line_numbers()
            self.root.after(60, self._update_code_explorer)
            self.status(f"Loaded {os.path.basename(path)}")
            if looks_like_gui(content) or self.gui_mode:
                vform = self._vform_path_for_unit(path)
                if vform and os.path.isfile(vform):
                    self.current_vform_path = vform
                    self.root.after(200, lambda: self.open_vform(self.current_vform_path))
                    self.root.after(250, self._refresh_vform_tab)
                else:
                    self.current_vform_path = vform
                    # No .vform yet → sync designer from code and generate file
                    def _auto_vform():
                        try:
                            self._sync_from_code_impl()
                            if vform:
                                self._save_vform_disk_only(vform)
                                self.current_vform_path = vform
                                try:
                                    self._ensure_vform_import_comment(vform)
                                except Exception:
                                    pass
                            self._refresh_vform_tab()
                            self.status(f"Generated {os.path.basename(vform) if vform else '.vform'} from code")
                        except Exception as ex:
                            self.status(f"vform generate: {ex}")
                    self.root.after(300, _auto_vform)
            else:
                self.current_vform_path = None
            self.root.after(100, self._update_code_explorer)
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def _code_looks_duplicated(self):
        """True if buffer contains more than one program terminator (catastrophic double)."""
        try:
            src = self.editor.get("1.0", "end-1c")
            return self._count_programs(src) > 1
        except Exception:
            return False

    def _count_programs(self, src):
        if not src:
            return 0
        exits = len(re.findall(r'(?m)^\s*Exit\s*\.', src))
        enters = len(re.findall(r'(?m)^\s*Enter\s+\w+', src))
        return max(exits, enters)

    def _first_program_only(self, src):
        """If multiple Enter/Exit programs were concatenated, keep the first only."""
        if not src or self._count_programs(src) <= 1:
            return src
        lines = src.splitlines(keepends=True)
        out = []
        for line in lines:
            out.append(line)
            if re.match(r'^\s*Exit\s*\.', line):
                break
        return "".join(out)


    def _on_designer_tab(self):
        """True if Form Designer tab is currently selected."""
        try:
            if not hasattr(self, "notebook") or not hasattr(self, "design_tab_index"):
                return False
            return self.notebook.index(self.notebook.select()) == self.design_tab_index
        except Exception:
            return False

    def save_file(self):
        """Save .vtx as typed + .vform layout resource (Delphi unit + dfm model)."""
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
        """Write editor buffer to .vtx, then write matching .vform layout resource."""
        try:
            content = self.editor.get("1.0", "end-1c")
            if hasattr(self, "_first_program_only"):
                fixed = self._first_program_only(content)
                if fixed != content:
                    content = fixed
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", content)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.current_file = path
            self._last_snapshot = content
            self._mark_dirty(False)
            try:
                self.editor.edit_modified(False)
            except Exception:
                pass

            # Pair .vform with this unit (layout only)
            self.current_vform_path = self._vform_path_for_unit(path)
            vform_ok = False
            try:
                vform_ok = bool(self._persist_form_resource(silent=True))
            except Exception:
                try:
                    vform_ok = bool(self._save_vform_disk_only(self.current_vform_path))
                except Exception:
                    vform_ok = False

            base = os.path.basename(path)
            if vform_ok:
                self.status(f"Saved {base} + {os.path.basename(self.current_vform_path)}")
            else:
                self.status(f"Saved {base}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


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
        # Ensure .vform is on disk with latest designer layout before build
        try:
            self._autosave_vform()
        except Exception:
            pass
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

        # Locate optional vertex_build.py (only useful if we have a real Python)
        build_script = None
        for cand in (
            os.path.join(app_dir(), "vertex_build.py"),
            os.path.join(os.getcwd(), "vertex_build.py"),
            os.path.join(src_dir, "vertex_build.py"),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "vertex_build.py"),
        ):
            if cand and os.path.isfile(cand):
                build_script = cand
                break

        py_interp = find_python_interpreter()
        if py_interp and _looks_like_ide_exe(py_interp):
            py_interp = None
        if py_interp and os.path.abspath(py_interp) == os.path.abspath(sys.executable):
            if is_frozen() or _looks_like_ide_exe(sys.executable):
                py_interp = None

        # CRITICAL: never "vertex_ide.exe vertex_build.py ..." (opens second IDE).
        # Prefer direct vertexc + g++ whenever we are the IDE EXE.
        running_as_ide_exe = is_frozen() or _looks_like_ide_exe(sys.executable)
        use_build_script = bool(
            build_script and py_interp and not running_as_ide_exe
            and not _looks_like_ide_exe(py_interp)
        )
        if running_as_ide_exe:
            use_build_script = False
            self._append_output(
                "Compile path: vertexc + g++ (IDE EXE — not spawning Python/IDE)\n", "info"
            )
        elif use_build_script:
            self._append_output(f"Build host Python: {py_interp}\n", "info")
        else:
            self._append_output("Compile path: vertexc + g++ (direct)\n", "info")

        try:
            if use_build_script:
                cmd = [
                    py_interp, build_script,
                    self.current_file,
                    "--mode", mode,
                    "--output-dir", out_dir,
                    "--vertexc", vertexc,
                    "--gpp", gpp_path,
                ]
                if not static:
                    cmd.append("--no-static")
                if self.config.get("embed_icon", True):
                    ico = resolve_project_icon(
                        self.current_file, self.config.get("default_icon", ""))
                    if ico:
                        cmd += ["--icon", ico]
                else:
                    cmd.append("--no-icon")
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

            # Fallback: inline build (vertexc → g++)
            env = os.environ.copy()
            gpp_dir = os.path.dirname(gpp_path)
            if gpp_dir:
                env["PATH"] = gpp_dir + os.pathsep + env.get("PATH", "")
            if _looks_like_ide_exe(vertexc):
                raise RuntimeError(
                    "vertexc_path points at the IDE executable. "
                    "Set Settings → vertexc to vertexc.exe (compiler), not Vertex IDE."
                )
            if not vertexc or vertexc.strip() in (".", ""):
                raise RuntimeError("vertexc_path is empty — set it in Settings.")
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
            icon_obj = None
            if self.config.get("embed_icon", True):
                ico = resolve_project_icon(
                    self.current_file, self.config.get("default_icon", ""))
                if ico:
                    icon_obj, ilog = build_icon_object(ico, out_dir, gpp_path, env)
                    self._append_output((ilog or "") + "\n", "info" if icon_obj else "error")
            cmd = [gpp_path, "-O2", "-std=c++17", cpp_path]
            if icon_obj:
                cmd.append(icon_obj)
            cmd += ["-o", exe_path]
            if use_gui:
                cmd += ["-mwindows"]
                if static:
                    cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
                cmd += ["-luser32", "-lgdi32", "-lcomdlg32", "-lwinmm", "-ladvapi32"]
            else:
                if static:
                    cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
            self._append_output("Link: " + " ".join(cmd) + "\n", "info")
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
        win.geometry("560x380")
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
        e_ico = tk.Entry(frame, width=42, bg=theme["line_bg"], fg=theme["fg"])
        e_ico.insert(0, self.config.get("default_icon", ""))
        row(3, "Default icon:", e_ico, lambda: self._browse_icon(e_ico))
        static_var = tk.BooleanVar(value=self.config.get("static_linking", True))
        tk.Checkbutton(frame, text="Static linking", variable=static_var,
                       bg=theme["bg"], fg=theme["fg"], selectcolor=theme["line_bg"]).grid(
            row=4, column=0, columnspan=2, sticky=tk.W)
        auto_var = tk.BooleanVar(value=self.config.get("auto_detect_gui", True))
        tk.Checkbutton(frame, text="Auto-detect GUI", variable=auto_var,
                       bg=theme["bg"], fg=theme["fg"], selectcolor=theme["line_bg"]).grid(
            row=5, column=0, columnspan=2, sticky=tk.W)
        embed_var = tk.BooleanVar(value=self.config.get("embed_icon", True))
        tk.Checkbutton(frame, text="Embed EXE icon when .ico found", variable=embed_var,
                       bg=theme["bg"], fg=theme["fg"], selectcolor=theme["line_bg"]).grid(
            row=6, column=0, columnspan=2, sticky=tk.W)

        def save():
            self.config["vertexc_path"] = e_vc.get().strip()
            self.config["gpp_path"] = e_gpp.get().strip()
            self.config["output_dir"] = e_out.get().strip() or "."
            self.config["default_icon"] = e_ico.get().strip()
            self.config["static_linking"] = static_var.get()
            self.config["auto_detect_gui"] = auto_var.get()
            self.config["embed_icon"] = embed_var.get()
            save_config(self.config)
            win.destroy()
            self.status("Settings saved")

        tk.Button(frame, text="Save", command=save, bg=theme["btn_bg"],
                  fg=theme["btn_fg"], relief=tk.FLAT, padx=16).grid(row=7, column=1, sticky=tk.E, pady=10)

    def _browse_file(self, entry):
        path = filedialog.askopenfilename()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _browse_icon(self, entry):
        path = filedialog.askopenfilename(
            title="Select EXE icon",
            filetypes=[("Icon files", "*.ico"), ("All files", "*.*")])
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _browse_dir(self, entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    # ---------- Autocomplete (word + member after . / ^.) ----------
    def _editor_keyrelease_ac(self, event=None):
        if event is None:
            self.root.after(30, self._show_completion)
            return
        if event.keysym == "Escape":
            self._hide_completion()
            return
        if event.keysym in ("Return", "Tab"):
            try:
                if getattr(self, "_ac_win", None) and self._ac_win.winfo_viewable():
                    self._accept_completion()
                    return "break"
            except Exception:
                pass
            self._hide_completion()
            return
        if event.keysym in ("Up", "Down"):
            try:
                if getattr(self, "_ac_win", None) and self._ac_win.winfo_viewable():
                    lb = self._ac_list
                    cur = lb.curselection()
                    idx = cur[0] if cur else 0
                    if event.keysym == "Down":
                        idx = min(idx + 1, max(lb.size() - 1, 0))
                    else:
                        idx = max(idx - 1, 0)
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(idx)
                    lb.see(idx)
                    return "break"
            except Exception:
                pass
        self.root.after(40, self._show_completion)

    def _completion_context(self):
        """Return (mode, prefix): mode is 'word' or 'member'."""
        try:
            idx = self.editor.index("insert")
            line_start = self.editor.index("%s linestart" % idx)
            prefix = self.editor.get(line_start, idx)
            i = len(prefix) - 1
            while i >= 0 and (prefix[i].isalnum() or prefix[i] == "_"):
                i -= 1
            word = prefix[i + 1:]
            if i >= 0 and prefix[i] == ".":
                return "member", word
            if i >= 1 and prefix[i - 1:i + 1] == "^.":
                return "member", word
            return "word", word
        except Exception:
            return "word", ""

    def _scan_buffer_symbols(self):
        try:
            src = self.editor.get("1.0", "end-1c")
            found = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{1,40})\b", src))
            return sorted(found)
        except Exception:
            return []

    def _show_completion(self):
        mode, word = self._completion_context()
        low = (word or "").lower()
        matches = []
        if mode == "member":
            pool = list(MEMBER_COMPLETIONS) + self._scan_buffer_symbols()
            if low:
                matches = [c for c in pool if c.lower().startswith(low) and c.lower() != low]
            else:
                matches = list(MEMBER_COMPLETIONS)
            matches = sorted(set(matches), key=str.lower)[:16]
        else:
            if len(word) < 2:
                self._hide_completion()
                return
            pool = list(COMPLETIONS) + self._scan_buffer_symbols()
            matches = [c for c in sorted(set(pool), key=str.lower)
                       if c.lower().startswith(low) and c.lower() != low][:12]
        if not matches:
            self._hide_completion()
            return
        theme = THEMES[self.current_theme]
        if not hasattr(self, "_ac_win") or self._ac_win is None:
            self._ac_win = tk.Toplevel(self.root)
            self._ac_win.wm_overrideredirect(True)
            border = theme.get("ac_border", theme.get("splash_fg", "#007acc"))
            self._ac_win.configure(bg=border)
            frame = tk.Frame(self._ac_win, bg=border, padx=1, pady=1)
            frame.pack(fill=tk.BOTH, expand=True)
            self._ac_list = tk.Listbox(
                frame, height=min(10, max(4, len(matches))), font=("Consolas", 11),
                activestyle="dotbox", exportselection=False,
                bg=theme.get("ac_bg", theme["btn_bg"]),
                fg=theme.get("ac_fg", theme["btn_fg"]),
                selectbackground=theme.get("ac_sel", theme["select_bg"]),
                selectforeground="#ffffff",
                relief=tk.FLAT, highlightthickness=0,
            )
            self._ac_list.pack()
            self._ac_list.bind("<Double-Button-1>", self._accept_completion)
            self._ac_list.bind("<Return>", self._accept_completion)
            self._ac_list.bind("<Escape>", lambda e: self._hide_completion())
        else:
            try:
                self._ac_list.configure(
                    bg=theme.get("ac_bg", theme["btn_bg"]),
                    fg=theme.get("ac_fg", theme["btn_fg"]),
                    selectbackground=theme.get("ac_sel", theme["select_bg"]),
                    height=min(10, max(4, len(matches))),
                )
            except Exception:
                pass
        self._ac_list.delete(0, tk.END)
        for mitem in matches:
            self._ac_list.insert(tk.END, mitem)
        self._ac_list.selection_set(0)
        try:
            bbox = self.editor.bbox("insert")
            if not bbox:
                self._hide_completion()
                return
            x, y, w, h = bbox
            abs_x = self.editor.winfo_rootx() + x
            abs_y = self.editor.winfo_rooty() + y + h + 2
            self._ac_win.geometry("+%d+%d" % (abs_x, abs_y))
            self._ac_win.deiconify()
            self._ac_win.lift()
        except Exception:
            self._hide_completion()

    def _hide_completion(self, event=None):
        if hasattr(self, "_ac_win") and self._ac_win is not None:
            try:
                self._ac_win.withdraw()
            except Exception:
                pass

    def _accept_completion(self, event=None):
        if not hasattr(self, "_ac_list"):
            return
        sel = self._ac_list.curselection()
        if not sel:
            self._hide_completion()
            return
        choice = self._ac_list.get(sel[0])
        mode, word = self._completion_context()
        idx = self.editor.index("insert")
        if word:
            start = self.editor.index("%s - %dc" % (idx, len(word)))
            self.editor.delete(start, idx)
            self.editor.insert(start, choice)
        else:
            self.editor.insert(idx, choice)
        self._hide_completion()
        self.root.after(10, lambda: highlight(self.editor))

    # ---------- New save-on-close handler ----------
    def _on_close(self):
        """Prompt to save if there are unsaved changes (* in title / dirty flag)."""
        if self._dirty or (hasattr(self, "editor") and self.editor.edit_modified()):
            name = os.path.basename(self.current_file) if self.current_file else "Untitled"
            response = messagebox.askyesnocancel(
                "Save changes?",
                f'"{name}" has unsaved changes.\n\nDo you want to save before closing?'
            )
            if response is None:
                return  # Cancel — keep IDE open
            if response:
                self.save_file()
                if self._dirty:
                    return  # save cancelled or failed
        self.root.destroy()

    def status(self, msg):
        if hasattr(self, "status_label"):
            self.status_label.config(text=msg)
            self.root.update_idletasks()

    def show_ide_guide(self):
        """Help -> How the IDE works - full guide window."""
        theme = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("How Vertex IDE Works")
        win.geometry("720x560")
        win.minsize(520, 360)
        win.configure(bg=theme["bg"])
        try:
            win.transient(self.root)
        except Exception:
            pass

        top = tk.Frame(win, bg=theme["toolbar_bg"], padx=10, pady=8)
        top.pack(fill=tk.X)
        tk.Label(
            top,
            text="Vertex IDE - User Guide",
            font=("Segoe UI", 12, "bold"),
            bg=theme["toolbar_bg"],
            fg=theme.get("accent", theme["fg"]),
        ).pack(side=tk.LEFT)
        tk.Button(
            top, text="Close", command=win.destroy,
            bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=12,
        ).pack(side=tk.RIGHT)

        body = tk.Frame(win, bg=theme["bg"], padx=8, pady=8)
        body.pack(fill=tk.BOTH, expand=True)
        txt = scrolledtext.ScrolledText(
            body,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=theme.get("output_bg", theme["bg"]),
            fg=theme["fg"],
            insertbackground=theme.get("insertbg", theme["fg"]),
            relief=tk.FLAT,
            padx=12,
            pady=10,
        )
        txt.pack(fill=tk.BOTH, expand=True)

        guide = self._ide_guide_text()
        txt.insert("1.0", guide)
        txt.config(state=tk.DISABLED)
        try:
            txt.focus_set()
        except Exception:
            pass

    def _ide_guide_text(self):
        """Full IDE guide body for Help -> How the IDE works."""
        return (
            'VERTEX IDE - HOW EVERYTHING WORKS\n================================\n\nVertex IDE is a code editor plus an optional Form Designer for the Vertex language.\nYou can build GUI apps in pure code with VCL, or use the designer to edit layout\nstored in a .vform file (similar to a Delphi .dfm).\n\n1) MAIN WINDOW LAYOUT\n--------------------\n- Toolbar (top): New, Open, Save, Compile (F5), Run (F6), Settings, the'
            +
            'me, GUI mode.\n- Left sidebar: Component Palette and Properties / Events panel.\n- Center tabs: Code (.vtx), Form Designer, Code Explorer, Form (.vform) resource.\n- Output panel (bottom): compiler and run messages.\n- Status bar: file name, cursor position, short status text.\n\n2) CODE EDITOR\n-------------\n- Edit Vertex source: Import, Enter, Var, Proc, Run/Stop, Exit.\n- Syntax highlighting and autoco'
            +
            'mplete (words; members after . or ^.).\n- Ctrl+Z/Y undo/redo, Ctrl+X/C/V cut/copy/paste, Ctrl+A select all.\n- Save (Ctrl+S) writes the editor text as-is to the .vtx file.\n- You can build full VCL GUI apps here without using the Form Designer.\n\n3) COMPONENT PALETTE\n-------------------\n- Tools: Button, Edit, Label, Memo, CheckBox, Radio, ListBox, ComboBox,\n  GroupBox, Panel, ComPort, StatusBar, Hyper'
            +
            'Term, Timer, SevenSeg, Select.\n- Choose a tool, then click the form canvas to place a control.\n- Select tool: click to select, drag to move, handles to resize.\n- Palette scrolls when the list is long.\n\n4) FORM DESIGNER\n---------------\n- Canvas = main window client area; grid helps alignment.\n- Click empty form area to edit form title, width, height, color.\n- Click a control to edit Name, Caption, '
            +
            'Left, Top, Width, Height, Color.\n- Red handles on the form border resize the form.\n\nLayout model (important):\n  - Designer saves layout to a .vform file next to your .vtx.\n  - The .vtx still creates controls in code with default sizes/positions/colors.\n  - At run time ApplyVForm("YourUnit.vform") applies designer layout on top.\n  - Designer does not rewrite your event-handler logic in the code edi'
            +
            'tor.\n\n5) .vform AND {$FORM}\n--------------------\n- .vform = JSON layout (form size, control positions, captions, colors).\n- IDE may add: {$FORM "UnitName.vform"} near the top (link for the IDE only).\n- Your code must call ApplyVForm("UnitName.vform") after creating controls\n  and before RunApp - that is what loads .vform at run time.\n\nForm menu:\n  - Save Form (.vform) - write designer state to dis'
            +
            'k\n  - Open Form (.vform) - load layout into the designer\n  - Sync from Code - bootstrap designer from Window/Button lines (if no .vform yet)\n  - Generate / Refresh .vform - create/update .vform for the unit\n\n6) PROPERTIES & EVENTS\n---------------------\n- Edit selected form/control fields; Apply updates the designer (.vform on save).\n- Events (OnClick, OnChange, ...) are implemented in Code, e.g. O'
            +
            'nClick(@MyProc).\n\n7) CODE EXPLORER\n---------------\n- Lists symbols in the current buffer.\n- Double-click a name to jump to it in the code editor.\n\n8) FORM (.vform) TAB\n-------------------\n- Shows the JSON layout file; Refresh reloads from disk.\n\n9) BUILD & RUN\n-------------\n- F5 Compile: vertexc then g++ (paths in Settings).\n- F6 Run: starts the built .exe.\n- GUI mode / auto-detect selects -mwindo'
            +
            'ws and Win32 libraries when needed.\n- Output panel shows build errors and messages.\n\n10) TOOLBAR\n----------\n- New / Open / Save - .vtx (and .vform snapshot for GUI units).\n- Compile / Run / Folder / Settings / Theme / GUI toggle.\n\n11) WORKFLOWS\n------------\nA) Code-only: write Window/Button/logic in the editor; no designer needed.\n\nB) Code + designer:\n   1. Create controls + logic in Code (keep de'
            +
            'faults in code).\n   2. Save .vtx once.\n   3. Adjust layout in Form Designer; Save writes .vform.\n   4. ApplyVForm("....vform") before RunApp.\n   5. Compile and Run.\n\n12) SHORTCUTS\n------------\nCtrl+N New   Ctrl+O Open   Ctrl+S Save\nCtrl+Z/Y Undo/Redo   Ctrl+X/C/V Cut/Copy/Paste   Ctrl+A Select All\nF5 Compile   F6 Run\nSee also Help -> Shortcuts.\n'
        )

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

    def show_shortcuts(self):
        shortcuts = """
Keyboard Shortcuts:

File:
  Ctrl+N   New file
  Ctrl+O   Open file
  Ctrl+S   Save file

Edit:
  Ctrl+Z   Undo
  Ctrl+Y   Redo
  Ctrl+X   Cut
  Ctrl+C   Copy
  Ctrl+V   Paste
  Ctrl+A   Select All

Build & Run:
  F5       Compile
  F6       Run

Form Designer:
  Delete   Delete selected control
  Double-click a control to create an event handler
  Click form to select it (properties appear)

Code Explorer:
  Double-click any symbol to jump to its definition
        """
        messagebox.showinfo("Keyboard Shortcuts", shortcuts.strip())

    def about(self):
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME}  -  Delphi-inspired form designer\n"
            "Author: Smail Lotmani\n\n"
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