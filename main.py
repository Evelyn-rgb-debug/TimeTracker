# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import os
import random
import sqlite3
import sys
import time
import ctypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, QDate, QDateTime, QTime, QEvent, QLocale
from PySide6.QtGui import (
    QColor,
    QBrush,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QRadialGradient,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QDateTimeEdit,
    QHBoxLayout,
    QHeaderView,
    QAbstractItemView,
    QCheckBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QColorDialog,
    QSlider,
    QSizeGrip,
    QSizePolicy,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Time Tracker :)"
DEFAULT_CATEGORIES = ["Work", "Study", "Meal", "Fun", "Commute", "Exercise", "Rest", "Other"]
DEFAULT_TASK_PLACEHOLDER = "(No details)"
CURRENT_CATEGORY_ORDER: list[str] = DEFAULT_CATEGORIES[:]

CATEGORY_ALIASES = {
    "工作": "Work",
    "学习": "Study",
    "吃饭": "Meal",
    "娱乐": "Fun",
    "通勤": "Commute",
    "运动": "Exercise",
    "休息": "Rest",
    "其他": "Other",
    "Work": "Work",
    "Study": "Study",
    "Meal": "Meal",
    "Fun": "Fun",
    "Commute": "Commute",
    "Exercise": "Exercise",
    "Rest": "Rest",
    "Other": "Other",
}

DEFAULT_MINT = QColor(134, 231, 220)
DEFAULT_PURPLE = QColor(107, 113, 217)
MINT = QColor(DEFAULT_MINT)
PURPLE = QColor(DEFAULT_PURPLE)
TEXT = QColor(33, 42, 60)
SUBTEXT = QColor(90, 100, 120)
WEEKEND = QColor(191, 132, 139)

BASE_WIDTH = 1450.0
BASE_HEIGHT = 860.0

DEFAULT_GLASS_OPACITY_SCALE = 1.18
CALENDAR_GLASS_OPACITY_SCALE = DEFAULT_GLASS_OPACITY_SCALE
CURRENT_GLASS_OPACITY_SCALE = DEFAULT_GLASS_OPACITY_SCALE


def ui_scale_for(widget) -> float:
    try:
        win = widget.window() if widget is not None else None
        if win is not None and hasattr(win, "ui_scale"):
            return float(win.ui_scale())
    except Exception:
        pass
    return 1.0


def sp(widget, value: float, minimum: int = 1) -> int:
    return max(int(minimum), int(round(float(value) * ui_scale_for(widget))))


def ui_font(widget, size: float, weight: int = QFont.Normal) -> QFont:
    return QFont("Segoe UI", max(1, int(round(float(size) * ui_scale_for(widget)))), weight)


def try_enable_native_blur(widget):
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = int(widget.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int), ("GradientColor", ctypes.c_uint32), ("AnimationId", ctypes.c_int)]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]

        # AccentState 3 = blur behind. Safer than acrylic across Windows versions.
        accent = ACCENTPOLICY(3, 2, 0x20FFFFFF, 0)
        data = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.addressof(accent), ctypes.sizeof(accent))
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

        class MARGINS(ctypes.Structure):
            _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int), ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]

        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except Exception:
        pass



# ---------------- helpers ----------------
def now_local() -> datetime:
    return datetime.now()


def dt_to_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def str_to_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def fmt_hms(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def script_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def app_icon_path() -> str:
    p = os.path.join(script_dir(), "icon.png")
    return p if os.path.exists(p) else ""


def hide_windows_console():
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


_SINGLE_INSTANCE_HANDLE = None


def ensure_single_instance() -> bool:
    global _SINGLE_INSTANCE_HANDLE
    if not sys.platform.startswith("win"):
        return True
    try:
        mutex_name = r"Local\TimeTrackerGlassSingleton"
        _SINGLE_INSTANCE_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        already_exists = ctypes.windll.kernel32.GetLastError() == 183
        return not already_exists
    except Exception:
        return True


def apply_windows_toolwindow_style(widget):
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = int(widget.winId())
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style = (ex_style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass


def startup_script_path() -> str:
    base = os.environ.get("APPDATA") or ""
    if not base:
        return ""
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Time Tracker.vbs")


def build_launch_command(tray_mode: bool = False) -> str:
    args = []
    if getattr(sys, "frozen", False):
        args.append(f'"{sys.executable}"')
    else:
        py_exe = sys.executable
        if tray_mode and py_exe.lower().endswith("python.exe"):
            alt = py_exe[:-10] + "pythonw.exe"
            if os.path.exists(alt):
                py_exe = alt
        args.append(f'"{py_exe}"')
        args.append(f'"{os.path.abspath(__file__)}"')
    if tray_mode:
        args.append("--tray")
    return " ".join(args)


def ensure_windows_autostart():
    if not sys.platform.startswith("win"):
        return
    try:
        target = startup_script_path()
        if not target:
            return

        os.makedirs(os.path.dirname(target), exist_ok=True)

        command = build_launch_command(tray_mode=True).replace('"', '""')

        content = 'Set WshShell = CreateObject("WScript.Shell")\r\n'
        content += f'WshShell.Run "{command}", 0, False\r\n'

        Path(target).write_text(content, encoding="utf-8")
    except Exception as e:
        print("[AUTOSTART ERROR]", e)


def apply_rounded_window_mask(widget, radius: int = 28):
    try:
        path = QPainterPath()
        path.addRoundedRect(QRectF(widget.rect()), radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        widget.setMask(region)
    except Exception:
        pass


def app_data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or ""
    if base:
        p = os.path.join(base, "TimeTrackerGlass")
        os.makedirs(p, exist_ok=True)
        return p
    return os.path.abspath(os.path.dirname(__file__))


def db_path() -> str:
    return os.path.join(app_data_dir(), "tracker.db")


def blend(c1: QColor, c2: QColor, t: float, alpha: int | None = None) -> QColor:
    t = max(0.0, min(1.0, float(t)))
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
    a = alpha if alpha is not None else int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
    return QColor(r, g, b, a)


def clamp_glass_opacity_scale(scale: float) -> float:
    try:
        value = float(scale)
    except Exception:
        value = DEFAULT_GLASS_OPACITY_SCALE
    return max(0.70, min(1.85, value))


def scaled_alpha(alpha: int, scale: float | None = None) -> int:
    base = max(0, int(alpha))
    scale = clamp_glass_opacity_scale(CURRENT_GLASS_OPACITY_SCALE if scale is None else scale)
    return max(0, min(255, int(round(base * scale))))


def glass_scale_for(widget=None) -> float:
    try:
        if widget is not None:
            win = widget.window()
            if win is not None and hasattr(win, "glass_opacity_scale"):
                return clamp_glass_opacity_scale(getattr(win, "glass_opacity_scale"))
    except Exception:
        pass
    return clamp_glass_opacity_scale(CURRENT_GLASS_OPACITY_SCALE)


def ga(widget, alpha: int) -> int:
    return scaled_alpha(alpha, glass_scale_for(widget))


def color_with_alpha(color: QColor, alpha: int, widget=None) -> QColor:
    if widget is None:
        return QColor(color.red(), color.green(), color.blue(), scaled_alpha(alpha))
    return QColor(color.red(), color.green(), color.blue(), ga(widget, alpha))


def css_rgba(color: QColor, alpha: int, scale: float | None = None) -> str:
    return f"rgba({color.red()},{color.green()},{color.blue()},{scaled_alpha(alpha, scale)})"


def color_to_hex(color: QColor) -> str:
    return color.name().upper()


def parse_color(value: str, fallback: QColor) -> QColor:
    c = QColor(str(value or "").strip())
    return c if c.isValid() else QColor(fallback)


def rebuild_category_colors(categories=None) -> dict[str, QColor]:
    global CAT_COLORS, CURRENT_CATEGORY_ORDER
    CURRENT_CATEGORY_ORDER = normalize_categories(categories if categories is not None else CURRENT_CATEGORY_ORDER)
    ordered = CURRENT_CATEGORY_ORDER[:] or DEFAULT_CATEGORIES[:]
    CAT_COLORS = {}

    n = len(ordered)
    if n == 1:
        CAT_COLORS[ordered[0]] = blend(MINT, PURPLE, 0.5)
        return CAT_COLORS

    for idx, cat in enumerate(ordered):
        # 取每一段的中心，而不是直接取 0 和 1 两端
        t = (idx + 0.5) / n
        CAT_COLORS[cat] = blend(MINT, PURPLE, t)

    return CAT_COLORS


def set_theme_colors(mint: QColor, purple: QColor, categories=None):
    global MINT, PURPLE
    MINT = QColor(mint)
    PURPLE = QColor(purple)
    rebuild_category_colors(categories)


def start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def clamp_item_to_range(item: dict, range_start: datetime, range_end: datetime) -> dict | None:
    try:
        item_start = str_to_dt(item["start"])
        item_end = str_to_dt(item["end"])
    except Exception:
        return None
    clip_start = max(item_start, range_start)
    clip_end = min(item_end, range_end)
    if clip_end <= clip_start:
        return None
    clipped = dict(item)
    clipped["start"] = dt_to_str(clip_start)
    clipped["end"] = dt_to_str(clip_end)
    clipped["duration_sec"] = max(0, int((clip_end - clip_start).total_seconds()))
    return clipped


def split_item_by_day(item: dict, range_start: datetime | None = None, range_end: datetime | None = None) -> list[dict]:
    raw = dict(item)
    clipped = dict(item)
    if range_start is not None and range_end is not None:
        clipped = clamp_item_to_range(clipped, range_start, range_end)
        if clipped is None:
            return []

    try:
        true_start = str_to_dt(raw["start"])
        true_end = str_to_dt(raw["end"])
        seg_start = str_to_dt(clipped["start"])
        seg_end = str_to_dt(clipped["end"])
    except Exception:
        return []

    if seg_end <= seg_start:
        return []

    pieces: list[dict] = []
    cursor = seg_start
    while cursor < seg_end:
        next_midnight = start_of_day(cursor) + timedelta(days=1)
        piece_end = min(seg_end, next_midnight)
        piece = dict(clipped)
        piece["start"] = dt_to_str(cursor)
        piece["end"] = dt_to_str(piece_end)
        piece["true_start"] = dt_to_str(true_start)
        piece["true_end"] = dt_to_str(true_end)
        piece["duration_sec"] = max(0, int((piece_end - cursor).total_seconds()))
        if piece["duration_sec"] > 0:
            pieces.append(piece)
        cursor = piece_end

    return pieces


def hours_in_day_span(start_dt: datetime, end_dt: datetime) -> tuple[float, float]:
    start_hour = start_dt.hour + start_dt.minute / 60 + start_dt.second / 3600
    if end_dt.date() > start_dt.date():
        end_hour = 24.0
    else:
        end_hour = end_dt.hour + end_dt.minute / 60 + end_dt.second / 3600
    return start_hour, end_hour


def week_start(dt: datetime) -> datetime:
    return start_of_day(dt) - timedelta(days=dt.weekday())


def month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_months(dt: datetime, delta: int) -> datetime:
    y = dt.year + (dt.month - 1 + delta) // 12
    m = (dt.month - 1 + delta) % 12 + 1
    return dt.replace(year=y, month=m, day=1)


def last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def safe_replace_year(dt: datetime, year: int) -> datetime:
    day = min(dt.day, last_day_of_month(year, dt.month))
    return dt.replace(year=year, day=day)


def safe_add_months_preserve_day(dt: datetime, delta: int) -> datetime:
    month_index = (dt.month - 1) + int(delta)
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, last_day_of_month(year, month))
    return dt.replace(year=year, month=month, day=day)


def is_all_day_span(start_dt: datetime, end_dt: datetime) -> bool:
    return (
        start_dt.hour == 0 and start_dt.minute == 0 and start_dt.second == 0
        and end_dt.hour == 23 and end_dt.minute == 59
    )


def recurrence_matches(rule: str, anchor_start: datetime, target_day: datetime) -> bool:
    rule = str(rule or '').strip().lower()
    if not rule or rule == 'none':
        return start_of_day(anchor_start) == start_of_day(target_day)

    anchor_day = start_of_day(anchor_start)
    target_day = start_of_day(target_day)
    if target_day < anchor_day:
        return False

    if rule == 'weekly':
        return anchor_day.weekday() == target_day.weekday()
    if rule == 'monthly':
        desired_day = min(anchor_start.day, last_day_of_month(target_day.year, target_day.month))
        return target_day.day == desired_day
    if rule == 'yearly':
        desired_day = min(anchor_start.day, last_day_of_month(target_day.year, anchor_start.month))
        return target_day.month == anchor_start.month and target_day.day == desired_day
    return False



def previous_day_text(day_text: str) -> str:
    try:
        return (datetime.strptime(str(day_text), '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    except Exception:
        return ''


def same_day_text(a: str, b: str) -> bool:
    try:
        return datetime.strptime(str(a), '%Y-%m-%d').date() == datetime.strptime(str(b), '%Y-%m-%d').date()
    except Exception:
        return False


def iter_plan_occurrences(plan_row: dict, range_start: datetime, range_end: datetime) -> list[dict]:
    try:
        base_start = str_to_dt(plan_row['start'])
        base_end = str_to_dt(plan_row['end'])
    except Exception:
        return []

    if base_end <= base_start:
        return []

    recurrence = str(plan_row.get('recurrence', 'none') or 'none').strip().lower()
    is_all_day = bool(plan_row.get('is_all_day', 0))
    duration = base_end - base_start

    recur_range_start_raw = str(plan_row.get('recurrence_range_start', '') or '').strip()
    recur_range_end_raw = str(plan_row.get('recurrence_range_end', '') or '').strip()
    recur_range_start = start_of_day(base_start)
    recur_range_end = start_of_day(base_start)
    if recur_range_start_raw:
        try:
            recur_range_start = start_of_day(datetime.strptime(recur_range_start_raw, '%Y-%m-%d'))
        except Exception:
            recur_range_start = start_of_day(base_start)
    if recur_range_end_raw:
        try:
            recur_range_end = start_of_day(datetime.strptime(recur_range_end_raw, '%Y-%m-%d'))
        except Exception:
            recur_range_end = start_of_day(base_start)
    if recur_range_end < recur_range_start:
        recur_range_end = recur_range_start

    def make_occurrence(start_dt: datetime, end_dt: datetime) -> dict:
        item = dict(plan_row)
        item['start'] = dt_to_str(start_dt)
        item['end'] = dt_to_str(end_dt)
        item['duration_sec'] = max(0, int((end_dt - start_dt).total_seconds()))
        item['is_all_day'] = is_all_day
        item['recurrence'] = recurrence
        item['series_start'] = base_start.strftime('%Y-%m-%d %H:%M:%S')
        item['occurrence_start'] = start_dt.strftime('%Y-%m-%d %H:%M:%S')
        item['occurrence_day'] = start_of_day(start_dt).strftime('%Y-%m-%d')
        item['recurrence_range_start'] = recur_range_start.strftime('%Y-%m-%d')
        item['recurrence_range_end'] = recur_range_end.strftime('%Y-%m-%d')
        return item

    if recurrence in {'', 'none'}:
        if base_start <= range_end and base_end >= range_start:
            return [make_occurrence(base_start, base_end)]
        return []

    occurrences = []
    cursor_day = max(start_of_day(range_start), recur_range_start)
    end_day = min(start_of_day(range_end), recur_range_end)
    while cursor_day <= end_day:
        if recurrence_matches(recurrence, base_start, cursor_day):
            if recurrence == 'weekly':
                occ_start = cursor_day.replace(hour=base_start.hour, minute=base_start.minute, second=base_start.second, microsecond=0)
            elif recurrence == 'monthly':
                occ_start = safe_add_months_preserve_day(base_start, (cursor_day.year - base_start.year) * 12 + (cursor_day.month - base_start.month))
            else:  # yearly
                occ_start = safe_replace_year(base_start, cursor_day.year)
            occ_day = start_of_day(occ_start)
            if occ_day < recur_range_start or occ_day > recur_range_end:
                cursor_day += timedelta(days=1)
                continue
            occ_end = occ_start + duration
            if occ_start <= range_end and occ_end >= range_start:
                occurrences.append(make_occurrence(occ_start, occ_end))
        cursor_day += timedelta(days=1)
    return occurrences


def normalize_category(cat: str) -> str:
    s = str(cat or "").strip()
    if not s:
        return "Other"
    return CATEGORY_ALIASES.get(s, s)


def normalize_categories(items) -> list[str]:
    out = []
    seen = set()
    for x in items or []:
        n = normalize_category(x)
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out or DEFAULT_CATEGORIES[:]


def normalize_task_text(text_value: str) -> str:
    s = str(text_value or "").strip()
    return DEFAULT_TASK_PLACEHOLDER if s in {"", "(未填写)", DEFAULT_TASK_PLACEHOLDER} else s


def day_key_from(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value or "").strip()
    if len(s) >= 10:
        return s[:10]
    return start_of_day(now_local()).strftime("%Y-%m-%d")


def aggregate_category_totals(items) -> tuple[list[tuple[str, int]], int, dict[str, int]]:
    totals: dict[str, int] = {}
    total = 0
    for s in items or []:
        sec = max(0, int(s.get("duration_sec", 0) or 0))
        if sec <= 0:
            continue
        cat = normalize_category(s.get("category", "Other"))
        totals[cat] = totals.get(cat, 0) + sec
        total += sec
    ordered = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return ordered, total, totals


# ---------------- noise texture ----------------
_NOISE_PIXMAP: QPixmap | None = None


def get_noise_pixmap() -> QPixmap:
    global _NOISE_PIXMAP
    if _NOISE_PIXMAP is not None:
        return _NOISE_PIXMAP
    w, h = 256, 256
    img = QImage(w, h, QImage.Format_ARGB32)
    rng = random.Random(20260306)
    for y in range(h):
        for x in range(w):
            v = rng.randint(135, 175)
            img.setPixelColor(x, y, QColor(v, v, v, 7))
    _NOISE_PIXMAP = QPixmap.fromImage(img)
    return _NOISE_PIXMAP


# ---------------- DB ----------------
class TrackerDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init()

    def _init(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts TEXT NOT NULL,
                end_ts TEXT NOT NULL,
                duration_sec INTEGER NOT NULL,
                category TEXT NOT NULL,
                task_text TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state(
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts TEXT NOT NULL,
                end_ts TEXT NOT NULL,
                category TEXT NOT NULL,
                task_text TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_todos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_date TEXT NOT NULL,
                task_text TEXT NOT NULL,
                is_done INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_ts TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS month_todos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_key TEXT NOT NULL,
                task_text TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_ts TEXT NOT NULL
            );
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_todos_task_date ON daily_todos(task_date, sort_order, id);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_month_todos_month_key ON month_todos(month_key, sort_order, id);")

        cols_daily = {row[1] for row in self.conn.execute("PRAGMA table_info(daily_todos);").fetchall()}
        if "completed_ts" not in cols_daily:
            self.conn.execute("ALTER TABLE daily_todos ADD COLUMN completed_ts TEXT DEFAULT '';" )

        cols_plans = {row[1] for row in self.conn.execute("PRAGMA table_info(plans);").fetchall()}
        if "recurrence" not in cols_plans:
            self.conn.execute("ALTER TABLE plans ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'none';")
        if "is_all_day" not in cols_plans:
            self.conn.execute("ALTER TABLE plans ADD COLUMN is_all_day INTEGER NOT NULL DEFAULT 0;")
        if "recurrence_range_start" not in cols_plans:
            self.conn.execute("ALTER TABLE plans ADD COLUMN recurrence_range_start TEXT NOT NULL DEFAULT '';")
        if "recurrence_range_end" not in cols_plans:
            self.conn.execute("ALTER TABLE plans ADD COLUMN recurrence_range_end TEXT NOT NULL DEFAULT '';")
        self.conn.commit()

    def set_state(self, k: str, v: str):
        self.conn.execute(
            "INSERT INTO app_state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v;",
            (k, v),
        )
        self.conn.commit()

    def get_state(self, k: str, default: str = "") -> str:
        cur = self.conn.execute("SELECT v FROM app_state WHERE k=?;", (k,))
        row = cur.fetchone()
        return row[0] if row else default

    def add_session(self, start_dt: datetime, end_dt: datetime, category: str, task_text: str):
        dur = max(0, int((end_dt - start_dt).total_seconds()))
        cur = self.conn.execute(
            "INSERT INTO sessions(start_ts,end_ts,duration_sec,category,task_text) VALUES(?,?,?,?,?);",
            (dt_to_str(start_dt), dt_to_str(end_dt), dur, category, task_text),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_session(self, sid: int, start_dt: datetime, end_dt: datetime, category: str, task_text: str):
        dur = max(0, int((end_dt - start_dt).total_seconds()))
        self.conn.execute(
            "UPDATE sessions SET start_ts=?, end_ts=?, duration_sec=?, category=?, task_text=? WHERE id=?;",
            (dt_to_str(start_dt), dt_to_str(end_dt), dur, category, task_text, sid),
        )
        self.conn.commit()

    def delete_session(self, sid: int):
        self.conn.execute("DELETE FROM sessions WHERE id=?;", (sid,))
        self.conn.commit()

    def get_session_by_id(self, sid: int):
        cur = self.conn.execute(
            "SELECT id,start_ts,end_ts,category,task_text FROM sessions WHERE id=?;",
            (sid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "start": row[1],
            "end": row[2],
            "category": row[3],
            "task_text": row[4],
        }

    def get_sessions_in_range(self, start_dt: datetime, end_dt: datetime):
        cur = self.conn.execute(
            "SELECT id,start_ts,end_ts,duration_sec,category,task_text FROM sessions WHERE start_ts <= ? AND end_ts >= ? ORDER BY start_ts ASC;",
            (dt_to_str(end_dt), dt_to_str(start_dt)),
        )
        rows = cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "start": r[1],
                "end": r[2],
                "duration_sec": int(r[3]),
                "category": r[4],
                "task_text": r[5],
            }
            for r in rows
        ]

    def add_plan(self, start_dt: datetime, end_dt: datetime, category: str, task_text: str, recurrence: str = "none", is_all_day: bool = False, recurrence_range_start: str = "", recurrence_range_end: str = ""):
        cur = self.conn.execute(
            "INSERT INTO plans(start_ts,end_ts,category,task_text,recurrence,is_all_day,recurrence_range_start,recurrence_range_end) VALUES(?,?,?,?,?,?,?,?);",
            (dt_to_str(start_dt), dt_to_str(end_dt), category, task_text, str(recurrence or 'none'), 1 if is_all_day else 0, str(recurrence_range_start or ''), str(recurrence_range_end or '')),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_plan(self, pid: int, start_dt: datetime, end_dt: datetime, category: str, task_text: str, recurrence: str = "none", is_all_day: bool = False, recurrence_range_start: str = "", recurrence_range_end: str = ""):
        self.conn.execute(
            "UPDATE plans SET start_ts=?, end_ts=?, category=?, task_text=?, recurrence=?, is_all_day=?, recurrence_range_start=?, recurrence_range_end=? WHERE id=?;",
            (dt_to_str(start_dt), dt_to_str(end_dt), category, task_text, str(recurrence or 'none'), 1 if is_all_day else 0, str(recurrence_range_start or ''), str(recurrence_range_end or ''), pid),
        )
        self.conn.commit()

    def delete_plan(self, pid: int):
        self.conn.execute("DELETE FROM plans WHERE id=?;", (pid,))
        self.conn.commit()

    def get_plan_by_id(self, pid: int):
        cur = self.conn.execute(
            "SELECT id,start_ts,end_ts,category,task_text,COALESCE(recurrence,'none'),COALESCE(is_all_day,0),COALESCE(recurrence_range_start,''),COALESCE(recurrence_range_end,'') FROM plans WHERE id=?;",
            (pid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "start": row[1],
            "end": row[2],
            "category": row[3],
            "task_text": row[4],
            "recurrence": row[5],
            "is_all_day": bool(row[6]),
            "recurrence_range_start": row[7],
            "recurrence_range_end": row[8],
        }

    def get_plans_in_range(self, start_dt: datetime, end_dt: datetime):
        cur = self.conn.execute(
            "SELECT id,start_ts,end_ts,category,task_text,COALESCE(recurrence,'none'),COALESCE(is_all_day,0),COALESCE(recurrence_range_start,''),COALESCE(recurrence_range_end,'') FROM plans ORDER BY start_ts ASC;",
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            row = {
                "id": int(r[0]),
                "start": r[1],
                "end": r[2],
                "category": r[3],
                "task_text": r[4],
                "recurrence": r[5],
                "is_all_day": bool(r[6]),
                "recurrence_range_start": r[7],
                "recurrence_range_end": r[8],
            }
            out.extend(iter_plan_occurrences(row, start_dt, end_dt))
        out.sort(key=lambda item: item.get("start", ""))
        return out

    def add_daily_todo(self, task_date: datetime | str, task_text: str):
        day_key = day_key_from(task_date)
        clean_text = str(task_text or "").strip()
        if not clean_text:
            return None
        cur = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM daily_todos WHERE task_date=?;",
            (day_key,),
        )
        next_order = int((cur.fetchone() or [1])[0] or 1)
        cur = self.conn.execute(
            "INSERT INTO daily_todos(task_date,task_text,is_done,sort_order,created_ts,completed_ts) VALUES(?,?,?,?,?,?);",
            (day_key, clean_text, 0, next_order, dt_to_str(now_local()), ""),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_daily_todos(self, task_date: datetime | str):
        day_key = day_key_from(task_date)
        cur = self.conn.execute(
            "SELECT id,task_date,task_text,is_done,sort_order,created_ts,COALESCE(completed_ts,'') FROM daily_todos WHERE task_date=? ORDER BY sort_order ASC, id ASC;",
            (day_key,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "task_date": r[1],
                "task_text": r[2],
                "is_done": bool(r[3]),
                "sort_order": int(r[4]),
                "created_ts": r[5],
                "completed_ts": r[6],
            }
            for r in rows
        ]

    def get_daily_todos_for_display(self, task_date: datetime | str):
        day_key = day_key_from(task_date)
        cur = self.conn.execute(
            """
            SELECT id,task_date,task_text,is_done,sort_order,created_ts,COALESCE(completed_ts,'')
            FROM daily_todos
            WHERE task_date <= ?
            ORDER BY task_date ASC, sort_order ASC, id ASC;
            """,
            (day_key,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "task_date": r[1],
                "task_text": r[2],
                "is_done": bool(r[3]),
                "sort_order": int(r[4]),
                "created_ts": r[5],
                "completed_ts": r[6],
                "is_carryover": (r[1] != day_key),
            }
            for r in rows
        ]

    def add_month_todo(self, anchor_date: datetime | str, task_text: str):
        month_key = day_key_from(anchor_date)[:7]
        clean_text = str(task_text or "").strip()
        if not clean_text:
            return None
        cur = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM month_todos WHERE month_key=?;",
            (month_key,),
        )
        next_order = int((cur.fetchone() or [1])[0] or 1)
        cur = self.conn.execute(
            "INSERT INTO month_todos(month_key,task_text,sort_order,created_ts) VALUES(?,?,?,?);",
            (month_key, clean_text, next_order, dt_to_str(now_local())),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_month_todos_for_display(self, anchor_date: datetime | str):
        month_key = day_key_from(anchor_date)[:7]
        cur = self.conn.execute(
            """
            SELECT id,month_key,task_text,sort_order,created_ts
            FROM month_todos
            WHERE month_key <= ?
            ORDER BY month_key ASC, sort_order ASC, id ASC;
            """,
            (month_key,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "month_key": r[1],
                "task_text": r[2],
                "is_done": False,
                "sort_order": int(r[3]),
                "created_ts": r[4],
                "is_carryover": (r[1] != month_key),
            }
            for r in rows
        ]

    def delete_daily_todo(self, todo_id: int):
        self.conn.execute("DELETE FROM daily_todos WHERE id=?;", (int(todo_id),))
        self.conn.commit()

    def delete_month_todo(self, todo_id: int):
        self.conn.execute("DELETE FROM month_todos WHERE id=?;", (int(todo_id),))
        self.conn.commit()

    def purge_expired_completed_daily_todos(self, anchor_dt: datetime | str | None = None):
        anchor = start_of_day(now_local() if anchor_dt is None else (anchor_dt if isinstance(anchor_dt, datetime) else str_to_dt(str(anchor_dt) + " 00:00:00") if len(str(anchor_dt)) == 10 else now_local()))
        cutoff = dt_to_str(anchor)
        self.conn.execute(
            "DELETE FROM daily_todos WHERE is_done=1 AND COALESCE(completed_ts,'') <> '' AND completed_ts < ?;",
            (cutoff,),
        )
        self.conn.commit()

    def toggle_daily_todo_done(self, todo_id: int, is_done: bool | None = None):
        cur = self.conn.execute("SELECT is_done FROM daily_todos WHERE id=?;", (int(todo_id),))
        row = cur.fetchone()
        if not row:
            return
        if is_done is None:
            is_done = not bool(row[0])
        completed_ts = dt_to_str(now_local()) if bool(is_done) else ""
        self.conn.execute(
            "UPDATE daily_todos SET is_done=?, completed_ts=? WHERE id=?;",
            (1 if bool(is_done) else 0, completed_ts, int(todo_id)),
        )
        self.conn.commit()

    def toggle_month_todo_done(self, todo_id: int, is_done: bool | None = None):
        self.delete_month_todo(todo_id)

    def update_daily_todo(self, todo_id: int, task_text: str):
        self.conn.execute(
            "UPDATE daily_todos SET task_text=? WHERE id=?;",
            (normalize_task_text(task_text), int(todo_id)),
        )
        self.conn.commit()

    def update_month_todo(self, todo_id: int, task_text: str):
        self.conn.execute(
            "UPDATE month_todos SET task_text=? WHERE id=?;",
            (normalize_task_text(task_text), int(todo_id)),
        )
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


CAT_COLORS: dict[str, QColor] = {}
rebuild_category_colors()


def color_for_category(cat: str) -> QColor:
    normalized = normalize_category(cat)
    if normalized in CAT_COLORS:
        return CAT_COLORS[normalized]
    fingerprint = sum((idx + 1) * ord(ch) for idx, ch in enumerate(normalized))
    ratio = (fingerprint % 1000) / 999.0 if normalized else 0.5

    # 避免未知类别贴边到 A 或 B
    ratio = 0.1 + ratio * 0.8
    return blend(MINT, PURPLE, ratio)



# ---------------- background ----------------
class LightWallpaperBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if r.width() <= 10 or r.height() <= 10:
            return

        outer = QPainterPath()
        outer.addRoundedRect(r, 38, 38)
        # keep the thick glass edge mostly near the outside so the inner white plate stays large
        rim1_r = r.adjusted(5, 5, -5, -5)
        rim1 = QPainterPath()
        rim1.addRoundedRect(rim1_r, 34, 34)
        rim2_r = r.adjusted(10, 10, -10, -10)
        rim2 = QPainterPath()
        rim2.addRoundedRect(rim2_r, 30, 30)
        panel_r = r.adjusted(16, 16, -16, -16)
        panel = QPainterPath()
        panel.addRoundedRect(panel_r, 24, 24)

        band_outer = outer.subtracted(rim1)
        band_mid = rim1.subtracted(rim2)
        band_inner = rim2.subtracted(panel)

        # very thick outer glass edge
        g_outer = QLinearGradient(r.topLeft(), r.bottomRight())
        g_outer.setColorAt(0.00, QColor(255, 255, 255, ga(self, 220)))
        g_outer.setColorAt(0.14, QColor(255, 255, 255, ga(self, 138)))
        g_outer.setColorAt(0.55, QColor(255, 255, 255, ga(self, 82)))
        g_outer.setColorAt(1.00, QColor(255, 255, 255, ga(self, 190)))
        p.fillPath(band_outer, g_outer)

        g_mid = QLinearGradient(r.topLeft(), r.bottomRight())
        g_mid.setColorAt(0.00, QColor(255, 255, 255, ga(self, 120)))
        g_mid.setColorAt(0.36, QColor(210, 238, 236, ga(self, 66)))
        g_mid.setColorAt(0.74, QColor(205, 210, 246, ga(self, 52)))
        g_mid.setColorAt(1.00, QColor(255, 255, 255, ga(self, 96)))
        p.fillPath(band_mid, g_mid)

        g_inner = QLinearGradient(r.topLeft(), r.bottomRight())
        g_inner.setColorAt(0.00, QColor(255, 255, 255, ga(self, 58)))
        g_inner.setColorAt(0.50, QColor(255, 255, 255, ga(self, 22)))
        g_inner.setColorAt(1.00, QColor(255, 255, 255, ga(self, 42)))
        p.fillPath(band_inner, g_inner)

        fill = QLinearGradient(panel_r.topLeft(), panel_r.bottomRight())
        fill.setColorAt(0.0, QColor(248, 251, 252, ga(self, 148)))
        fill.setColorAt(0.45, QColor(245, 249, 251, ga(self, 132)))
        fill.setColorAt(1.0, QColor(249, 247, 252, ga(self, 142)))
        p.fillPath(panel, fill)

        p.save()
        p.setClipPath(outer)

        blobs = [
            (QPointF(r.left() + r.width() * 0.08, r.top() + r.height() * 0.18), min(r.width(), r.height()) * 0.26, color_with_alpha(MINT, 36, self)),
            (QPointF(r.right() - r.width() * 0.10, r.top() + r.height() * 0.22), min(r.width(), r.height()) * 0.24, color_with_alpha(PURPLE, 34, self)),
            (QPointF(r.left() + r.width() * 0.16, r.bottom() - r.height() * 0.10), min(r.width(), r.height()) * 0.28, color_with_alpha(MINT, 28, self)),
            (QPointF(r.right() - r.width() * 0.12, r.bottom() - r.height() * 0.12), min(r.width(), r.height()) * 0.26, color_with_alpha(PURPLE, 26, self)),
            (QPointF(r.left() + r.width() * 0.52, r.bottom() - r.height() * 0.04), min(r.width(), r.height()) * 0.22, QColor(255, 255, 255, ga(self, 34))),
        ]
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        for center, rad, col in blobs:
            g = QRadialGradient(center, rad)
            g.setColorAt(0.0, col)
            g.setColorAt(0.55, QColor(col.red(), col.green(), col.blue(), int(col.alpha() * 0.16)))
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(center, rad, rad)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        top_gloss = QLinearGradient(r.left(), r.top(), r.left(), r.top() + r.height() * 0.34)
        top_gloss.setColorAt(0.00, QColor(255, 255, 255, ga(self, 108)))
        top_gloss.setColorAt(0.30, QColor(255, 255, 255, ga(self, 28)))
        top_gloss.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.fillRect(r.toRect(), top_gloss)

        # refractive bright rails near edges
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 228)), 1.6))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 36, 36)
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 116)), 1.1))
        p.drawRoundedRect(r.adjusted(6, 6, -6, -6), 32, 32)
        p.setPen(QPen(color_with_alpha(MINT, 46, self), 1.0))
        p.drawLine(int(r.left() + 18), int(r.bottom() - 28), int(r.left() + r.width() * 0.36), int(r.bottom() - 28))
        p.setPen(QPen(color_with_alpha(PURPLE, 42, self), 1.0))
        p.drawLine(int(r.right() - r.width() * 0.28), int(r.top() + 24), int(r.right() - 24), int(r.top() + 24))

        p.setOpacity(0.014 * glass_scale_for(self))
        noise = get_noise_pixmap()
        for yy in range(int(r.top()), int(r.bottom()), noise.height()):
            for xx in range(int(r.left()), int(r.right()), noise.width()):
                p.drawPixmap(xx, yy, noise)
        p.restore()


# ---------------- glass card ----------------
class LightGlassCard(QWidget):
    def __init__(self, radius: int = 30, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if r.width() <= 10 or r.height() <= 10:
            return

        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(QRectF(r.adjusted(0, 11, 0, 14)), self.radius, self.radius)
        p.fillPath(shadow_path, QColor(0, 0, 0, ga(self, 18)))

        outer = QPainterPath()
        outer.addRoundedRect(r, self.radius, self.radius)
        rim_outer_r = r.adjusted(6, 6, -6, -6)
        rim_outer = QPainterPath()
        rim_outer.addRoundedRect(rim_outer_r, max(8, self.radius - 5), max(8, self.radius - 5))
        rim_mid_r = r.adjusted(11, 11, -11, -11)
        rim_mid = QPainterPath()
        rim_mid.addRoundedRect(rim_mid_r, max(8, self.radius - 10), max(8, self.radius - 10))
        panel_r = r.adjusted(16, 16, -16, -16)
        panel = QPainterPath()
        panel.addRoundedRect(panel_r, max(8, self.radius - 15), max(8, self.radius - 15))

        band_outer = outer.subtracted(rim_outer)
        band_mid = rim_outer.subtracted(rim_mid)
        band_inner = rim_mid.subtracted(panel)

        g_outer = QLinearGradient(r.topLeft(), r.bottomRight())
        g_outer.setColorAt(0.00, QColor(255, 255, 255, ga(self, 205)))
        g_outer.setColorAt(0.18, QColor(255, 255, 255, 118))
        g_outer.setColorAt(0.52, QColor(255, 255, 255, ga(self, 72)))
        g_outer.setColorAt(1.00, QColor(255, 255, 255, ga(self, 170)))
        p.fillPath(band_outer, g_outer)

        g_mid = QLinearGradient(r.topLeft(), r.bottomRight())
        g_mid.setColorAt(0.00, QColor(255, 255, 255, ga(self, 92)))
        g_mid.setColorAt(0.55, QColor(255, 255, 255, ga(self, 34)))
        g_mid.setColorAt(1.00, QColor(255, 255, 255, ga(self, 70)))
        p.fillPath(band_mid, g_mid)

        g_inner = QLinearGradient(r.topLeft(), r.bottomRight())
        g_inner.setColorAt(0.00, QColor(255, 255, 255, ga(self, 50)))
        g_inner.setColorAt(1.00, QColor(255, 255, 255, ga(self, 18)))
        p.fillPath(band_inner, g_inner)

        fill = QLinearGradient(panel_r.topLeft(), panel_r.bottomRight())
        fill.setColorAt(0.00, QColor(255, 255, 255, ga(self, 132)))
        fill.setColorAt(0.35, QColor(255, 255, 255, ga(self, 96)))
        fill.setColorAt(1.00, QColor(255, 255, 255, ga(self, 82)))
        p.fillPath(panel, fill)

        clip = QPainterPath()
        clip.addRoundedRect(r, self.radius, self.radius)
        p.save()
        p.setClipPath(clip)

        top_glow = QLinearGradient(r.left(), r.top(), r.left(), r.top() + r.height() * 0.46)
        top_glow.setColorAt(0.0, QColor(255, 255, 255, ga(self, 176)))
        top_glow.setColorAt(0.28, QColor(255, 255, 255, ga(self, 58)))
        top_glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(r.toRect(), top_glow)

        lower_pool = QLinearGradient(r.left(), r.bottom(), r.right(), r.top())
        lower_pool.setColorAt(0.0, color_with_alpha(MINT, 28, self))
        lower_pool.setColorAt(0.5, QColor(255, 255, 255, 0))
        lower_pool.setColorAt(1.0, color_with_alpha(PURPLE, 24, self))
        p.fillRect(r.toRect(), lower_pool)

        edge_lights = [
            (QPointF(r.left() + r.width() * 0.10, r.bottom() - r.height() * 0.10), color_with_alpha(MINT, 66, self), r.width() * 0.20),
            (QPointF(r.right() - r.width() * 0.12, r.top() + r.height() * 0.12), color_with_alpha(PURPLE, 58, self), r.width() * 0.18),
            (QPointF(r.right() - r.width() * 0.10, r.bottom() - r.height() * 0.10), color_with_alpha(PURPLE, 40, self), r.width() * 0.18),
            (QPointF(r.left() + r.width() * 0.52, r.bottom() - r.height() * 0.04), QColor(255, 255, 255, ga(self, 44)), r.width() * 0.22),
        ]
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        for center, col, rad in edge_lights:
            g = QRadialGradient(center, rad)
            g.setColorAt(0.0, col)
            g.setColorAt(0.50, QColor(col.red(), col.green(), col.blue(), int(col.alpha() * 0.18)))
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            p.setBrush(g)
            p.setPen(Qt.NoPen)
            p.drawEllipse(center, rad, rad)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        p.setPen(QPen(QColor(255, 255, 255, 138), 1.2))
        p.drawLine(QPointF(panel_r.left() + 18, panel_r.top() + 4), QPointF(panel_r.right() - 20, panel_r.top() + 4))
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 62)), 1.0))
        p.drawLine(QPointF(panel_r.left() + 4, panel_r.top() + 18), QPointF(panel_r.left() + 4, panel_r.bottom() - 20))
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 48)), 1.0))
        p.drawLine(QPointF(panel_r.left() + 28, panel_r.bottom() - 6), QPointF(panel_r.right() - 28, panel_r.bottom() - 6))

        p.setOpacity(0.014 * glass_scale_for(self))
        noise = get_noise_pixmap()
        for yy in range(int(r.top()), int(r.bottom()), noise.height()):
            for xx in range(int(r.left()), int(r.right()), noise.width()):
                p.drawPixmap(xx, yy, noise)
        p.restore()

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 238)), 1.45))
        p.drawRoundedRect(r, self.radius, self.radius)
        p.setPen(QPen(QColor(255, 255, 255, ga(self, 110)), 1.0))
        p.drawRoundedRect(r.adjusted(4, 4, -4, -4), self.radius - 3, self.radius - 3)
        p.setPen(QPen(QColor(170, 195, 255, ga(self, 26)), 0.9))
        p.drawRoundedRect(panel_r.adjusted(1, 1, -1, -1), max(8, self.radius - 16), max(8, self.radius - 16))


# ---------------- shared button styles ----------------
def glass_button_style(active: bool = False) -> str:
    if active:
        bg0 = css_rgba(MINT, 160)
        bg1 = css_rgba(PURPLE, 145)
        border = css_rgba(QColor(255, 255, 255), 220)
    else:
        bg0 = css_rgba(QColor(255, 255, 255), 136)
        bg1 = css_rgba(QColor(255, 255, 255), 88)
        border = css_rgba(QColor(255, 255, 255), 200)
    hover_border = css_rgba(QColor(255, 255, 255), 235)
    pressed_bg = css_rgba(QColor(255, 255, 255), 145)
    return f'''
        QPushButton{{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {bg0}, stop:1 {bg1});
            color:rgba(28,38,55,235);
            border:1px solid {border};
            border-radius:14px;
            padding:8px 14px;
            font-weight:800;
        }}
        QPushButton:hover{{border:1px solid {hover_border};}}
        QPushButton:pressed{{background:{pressed_bg};}}
    '''


def glass_tiny_button_style(active: bool = False) -> str:
    if active:
        bg0 = css_rgba(MINT, 160)
        bg1 = css_rgba(PURPLE, 145)
        border = css_rgba(QColor(255, 255, 255), 220)
    else:
        bg0 = css_rgba(QColor(255, 255, 255), 136)
        bg1 = css_rgba(QColor(255, 255, 255), 88)
        border = css_rgba(QColor(255, 255, 255), 200)
    hover_border = css_rgba(QColor(255, 255, 255), 235)
    pressed_bg = css_rgba(QColor(255, 255, 255), 145)
    return f'''
        QPushButton{{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {bg0}, stop:1 {bg1});
            color:rgba(28,38,55,235);
            border:1px solid {border};
            border-radius:12px;
            padding:0px 8px;
            font-weight:800;
            font-size:9px;
        }}
        QPushButton:hover{{border:1px solid {hover_border};}}
        QPushButton:pressed{{background:{pressed_bg};}}
    '''

# ---------------- timer widget ----------------
class TimerWidget(LightGlassCard):
    def __init__(self, parent=None):
        super().__init__(radius=30, parent=parent)
        self.running = False
        self.elapsed_sec = 0
        self._anim = 0.0
        self.on_start = None
        self.on_stop = None

        self.btn = QPushButton("Start", self)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet(glass_button_style())
        self.btn.clicked.connect(self._on_button)

        self._tick = QTimer(self)
        self._tick.setInterval(40)
        self._tick.timeout.connect(self._animate)
        self._tick.start()

    def _animate(self):
        self._anim = (self._anim + 1.0) % 360.0
        self.update()

    def resizeEvent(self, e):
        bw = min(sp(self, 300), max(sp(self, 180), int(self.width() * 0.52)))
        self.btn.setGeometry((self.width() - bw) // 2, self.height() - sp(self, 82), bw, sp(self, 54))
        super().resizeEvent(e)

    def _on_button(self):
        if self.running:
            if self.on_stop:
                self.on_stop()
        else:
            if self.on_start:
                self.on_start()

    def set_running(self, running: bool):
        self.running = running
        self.btn.setText("Log" if running else "Start")
        self.btn.setStyleSheet(glass_button_style(active=running))

    def set_elapsed(self, sec: int):
        self.elapsed_sec = max(0, int(sec))
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(18, 18, -18, -18)
        p.setPen(TEXT)
        p.setFont(ui_font(self, 12, QFont.Bold))
        p.drawText(QRectF(r.left(), r.top(), r.width(), 24), Qt.AlignLeft | Qt.AlignVCenter, "Timer")

        cx = r.center().x()
        cy = r.top() + r.height() * 0.42
        radius = min(r.width(), r.height()) * 0.22
        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        a0 = self._anim

        p.setPen(QPen(QColor(MINT.red(), MINT.green(), MINT.blue(), 54), 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect, int((-a0) * 16), int(124 * 16))
        p.setPen(QPen(QColor(PURPLE.red(), PURPLE.green(), PURPLE.blue(), 48), 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect, int((-(a0 + 146)) * 16), int(124 * 16))

        p.setPen(QPen(QColor(MINT.red(), MINT.green(), MINT.blue(), 220), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect, int((-a0) * 16), int(124 * 16))
        p.setPen(QPen(QColor(PURPLE.red(), PURPLE.green(), PURPLE.blue(), 215), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect, int((-(a0 + 146)) * 16), int(124 * 16))

        p.setPen(QPen(QColor(255, 255, 255, 112), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect.adjusted(4, 4, -4, -4), int((-(a0 + 14)) * 16), int(96 * 16))

        tr = QRectF(cx - 170, cy - 28, 340, 56)
        f = ui_font(self, 25, QFont.Black)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(f)
        p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 235))
        p.drawText(tr, Qt.AlignCenter, fmt_hms(self.elapsed_sec))


# ---------------- stats widget ----------------
# ---------------- stats widget ----------------
class StatsWidget(LightGlassCard):
    VIEW_DAY = "day"
    VIEW_SUMMARY = "summary"
    SCOPE_DAY = "day"
    SCOPE_WEEK = "week"
    SCOPE_MONTH = "month"

    def __init__(self, parent=None):
        super().__init__(radius=30, parent=parent)
        self.items = []
        self.summary_items = []
        self.selected_date = start_of_day(now_local())
        self.summary_anchor_date = self.selected_date
        self.view_mode = self.VIEW_DAY
        self.summary_scope_mode = self.SCOPE_MONTH
        self.on_summary_scope_changed = None
        self.hovered_cat: str | None = None
        self._segment_meta: list[dict] = []
        self._ring_center = QPointF(0.0, 0.0)
        self._ring_inner_radius = 0.0
        self._ring_outer_radius = 0.0
        self._controls_left = 0
        self.setMouseTracking(True)

        self.btn_summary_toggle = QPushButton("Work Summary", self)
        self.btn_summary_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_summary_toggle.clicked.connect(self._toggle_summary_view)

        self.btn_day_scope = QPushButton("Day", self)
        self.btn_week_scope = QPushButton("Week", self)
        self.btn_month_scope = QPushButton("Month", self)
        self._scope_buttons = {
            self.SCOPE_DAY: self.btn_day_scope,
            self.SCOPE_WEEK: self.btn_week_scope,
            self.SCOPE_MONTH: self.btn_month_scope,
        }
        for mode, btn in self._scope_buttons.items():
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, m=mode: self.set_summary_scope_mode(m, emit=True))

        self._sync_controls()

    def _compact_button_style(self, active: bool = False) -> str:
        if active:
            bg0 = f"rgba({MINT.red()},{MINT.green()},{MINT.blue()},160)"
            bg1 = f"rgba({PURPLE.red()},{PURPLE.green()},{PURPLE.blue()},145)"
            border = "rgba(255,255,255,220)"
        else:
            bg0 = "rgba(255,255,255,126)"
            bg1 = "rgba(255,255,255,82)"
            border = "rgba(255,255,255,192)"
        return f"""
            QPushButton{{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {bg0}, stop:1 {bg1});
                color:rgba(28,38,55,235);
                border:1px solid {border};
                border-radius:10px;
                padding:0px 6px;
                font-size:9px;
                font-weight:800;
            }}
            QPushButton:hover{{border:1px solid rgba(255,255,255,232);}}
            QPushButton:pressed{{background:rgba(255,255,255,145);}}
        """

    def _layout_controls(self):
        margin_x = sp(self, 14)

        # 标题单独占第一行，按钮放到下面一行
        title_top = sp(self, 12)
        title_h = sp(self, 24)
        top_y = title_top + title_h + sp(self, 20)

        btn_h = sp(self, 22)#按钮高度
        gap = sp(self, 4)

        # 尽量小一点，但保证能装下文字
        toggle_w = sp(self, 70 if self.view_mode == self.VIEW_SUMMARY else 120)
        scope_w = sp(self, 50) #Day、Week 的宽度
        scope_month_w = sp(self, 60) #Month 的宽度

        right_x = self.width() - margin_x - toggle_w
        self.btn_summary_toggle.setGeometry(right_x, top_y, toggle_w, btn_h)

        x = right_x - gap
        if self.view_mode == self.VIEW_SUMMARY:
            for mode in (self.SCOPE_MONTH, self.SCOPE_WEEK, self.SCOPE_DAY):
                btn = self._scope_buttons[mode]
                w = scope_month_w if mode == self.SCOPE_MONTH else scope_w
                x -= w
                btn.setGeometry(x, top_y, w, btn_h)
                x -= gap
            self._controls_left = x + gap
        else:
            self._controls_left = right_x

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout_controls()

    def _toggle_summary_view(self):
        self.set_summary_visible(self.view_mode != self.VIEW_SUMMARY)

    def set_summary_visible(self, visible: bool):
        self.view_mode = self.VIEW_SUMMARY if visible else self.VIEW_DAY
        self.hovered_cat = None
        self._sync_controls()

    def _sync_controls(self):
        summary_open = self.view_mode == self.VIEW_SUMMARY
        self.btn_summary_toggle.setText("Back" if summary_open else "Work Summary")
        self.btn_summary_toggle.setStyleSheet(self._compact_button_style(active=summary_open))
        for mode, btn in self._scope_buttons.items():
            btn.setVisible(summary_open)
            btn.setStyleSheet(self._compact_button_style(active=(summary_open and mode == self.summary_scope_mode)))
        self._layout_controls()
        self.updateGeometry()
        self.update()

    def set_day_items(self, day_dt: datetime, items):
        self.selected_date = start_of_day(day_dt)
        self.items = list(items or [])
        self.hovered_cat = None
        self.update()

    def set_summary_items(self, anchor_dt: datetime, items):
        self.summary_anchor_date = start_of_day(anchor_dt)
        self.summary_items = list(items or [])
        self.hovered_cat = None
        self.update()

    def set_summary_scope_mode(self, mode: str, emit: bool = False):
        if mode not in (self.SCOPE_DAY, self.SCOPE_WEEK, self.SCOPE_MONTH):
            mode = self.SCOPE_MONTH
        self.summary_scope_mode = mode
        self.hovered_cat = None
        self._sync_controls()
        if emit and self.on_summary_scope_changed:
            self.on_summary_scope_changed(self.summary_scope_mode)

    def set_sessions(self, sessions):
        self.set_day_items(self.selected_date, sessions)

    def _summary_period_text(self) -> str:
        if self.summary_scope_mode == self.SCOPE_DAY:
            return self.summary_anchor_date.strftime("%Y-%m-%d")
        if self.summary_scope_mode == self.SCOPE_WEEK:
            st = week_start(self.summary_anchor_date)
            ed = st + timedelta(days=6)
            return f"{st.strftime('%Y-%m-%d')}  ~  {ed.strftime('%m-%d')}"
        return month_start(self.summary_anchor_date).strftime("%Y-%m")

    def _active_title(self) -> str:
        if self.view_mode == self.VIEW_SUMMARY:
            return "Work Summary"
        return f"Stats  ·  {self.selected_date.strftime('%Y-%m-%d')}"

    def _active_items(self):
        return self.summary_items if self.view_mode == self.VIEW_SUMMARY else self.items

    def _default_center_sub(self) -> str:
        if self.view_mode == self.VIEW_SUMMARY:
            return ""
        return "Recorded Today"

    @staticmethod
    def _norm_angle(deg_value: float) -> float:
        return deg_value % 360.0
    @staticmethod
    def _angle_delta(a: float, b: float) -> float:
        return abs((a - b + 180.0) % 360.0 - 180.0)

    def _distance_to_arc_centerline(self, point: QPointF, seg: dict) -> float:
        px = float(point.x())
        py = float(point.y())
        cx = float(self._ring_center.x())
        cy = float(self._ring_center.y())
        radius = float(seg["radius"])

        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)

        return abs(dist - radius)
    def _angle_in_span(self, angle: float, start_deg: float, extent_deg: float) -> bool:
        if extent_deg >= 360.0:
            return True
        a = self._norm_angle(angle)
        s = self._norm_angle(start_deg)
        e = self._norm_angle(start_deg + extent_deg)
        if s <= e:
            return s <= a <= e
        return a >= s or a <= e

    def _distance_to_segment_centerline(self, point: QPointF, seg: dict) -> float:
        px = float(point.x())
        py = float(point.y())
        cx = float(self._ring_center.x())
        cy = float(self._ring_center.y())
        radius = float(seg.get("radius", max(1.0, (self._ring_inner_radius + self._ring_outer_radius) * 0.5)))
        start_deg = float(seg["start_deg"])
        extent_deg = float(seg["extent_deg"])

        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        angle = self._norm_angle(math.degrees(math.atan2(dy, dx)))

        if self._angle_in_span(angle, start_deg, extent_deg):
            return abs(dist - radius)

        end_deg = start_deg + extent_deg
        best = float("inf")
        for a in (start_deg, end_deg):
            rad = math.radians(a)
            ex = cx + radius * math.cos(rad)
            ey = cy + radius * math.sin(rad)
            best = min(best, math.hypot(px - ex, py - ey))
        return best

    def _cat_at_pos(self, pos) -> str | None:
        if not self._segment_meta:
            return None

        dx = float(pos.x() - self._ring_center.x())
        dy = float(pos.y() - self._ring_center.y())
        dist = math.hypot(dx, dy)

        # 只让“接近真正色环”的位置可命中，不把外面整圈发光都算进去
        ring_mid = (self._ring_inner_radius + self._ring_outer_radius) * 0.5
        radial_tol = 7.5
        if abs(dist - ring_mid) > radial_tol:
            return None

        # 关键：Qt 圆弧坐标系要用 -dy，不能直接 atan2(dy, dx)
        angle = self._norm_angle(math.degrees(math.atan2(-dy, dx)))

        best_cat = None
        best_score = None

        for seg in self._segment_meta:
            extent = max(0.2, float(seg["extent_deg"]))
            center = self._norm_angle(seg["start_deg"] + extent * 0.5)

            # 给小扇区一点额外容差，但不让大扇区无限抢占
            angular_tol = min(6.0, 18.0 / extent)
            half_span = extent * 0.5 + angular_tol

            ang_diff = self._angle_delta(angle, center)
            if ang_diff <= half_span:
                radial_diff = abs(dist - ring_mid)

                # 越靠近该扇区中心越优先；小扇区给一点点轻微优先
                score = ang_diff * 2.0 + radial_diff * 0.35 - min(1.2, 10.0 / extent)

                if best_score is None or score < best_score:
                    best_score = score
                    best_cat = seg["cat"]

        return best_cat

    def _cat_at_pos(self, pos) -> str | None:
        if not self._segment_meta:
            return None

        point = QPointF(float(pos.x()), float(pos.y()))

        best_seg = None
        best_score = None

        for seg in self._segment_meta:
            hit_path = seg.get("hit_path")
            if hit_path is None:
                continue
            if not hit_path.contains(point):
                continue

            extent = max(0.2, float(seg["extent_deg"]))
            dist_score = self._distance_to_arc_centerline(point, seg)

            # 小色块给一点轻微优先，但不要过强
            tiny_bonus = min(1.2, 8.0 / extent)

            score = dist_score - tiny_bonus
            if best_score is None or score < best_score:
                best_score = score
                best_seg = seg

        return None if best_seg is None else best_seg["cat"]

    def mouseMoveEvent(self, e):
        hovered = self._cat_at_pos(e.position())
        if hovered != self.hovered_cat:
            self.hovered_cat = hovered
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self.hovered_cat is not None:
            self.hovered_cat = None
            self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(18, 18, -18, -18)
        p.setPen(TEXT)
        p.setFont(ui_font(self, 12, QFont.Bold))
        title_right = max(r.left() + 140, self._controls_left - sp(self, 10))
        title_rect = QRectF(r.left(), r.top(), max(120, title_right - r.left()), 24)
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self._active_title())

        active_items = self._active_items()
        ordered, total, totals = aggregate_category_totals(active_items)

        cx = r.center().x()
        cy = r.top() + r.height() * 0.42
        radius = min(r.width(), r.height()) * 0.24
        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        self._ring_center = QPointF(cx, cy)
        self._ring_inner_radius = radius - 3
        self._ring_outer_radius = radius + 3
        self._segment_meta = []

        p.setPen(QPen(QColor(255, 255, 255, 120), 18, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect, 0, 360 * 16)

        if total <= 0:
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 140))
            p.setFont(ui_font(self, 10, QFont.Bold))
            p.drawText(QRectF(cx - 110, cy - 10, 220, 20), Qt.AlignCenter, "No Records")
            return

        start_deg = -90.0
        for cat, sec in ordered:
            extent = 360.0 * sec / total
            col = color_for_category(cat)
            hovered = cat == self.hovered_cat

            # 视觉绘制仍然保留 glow
            draw_rect = arc_rect.adjusted(-4, -4, 4, 4) if hovered else arc_rect
            halo_width = 24 if hovered else 18
            stroke_width = 10 if hovered else 7

            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 70 if hovered else 46), halo_width, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(draw_rect, int(start_deg * 16), int(extent * 16))

            p.setPen(QPen(col, stroke_width, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(draw_rect, int(start_deg * 16), int(extent * 16))

            # 命中路径只围绕“真正的实心圆环”，不要用 glow 宽度
            hit_arc = QPainterPath()
            hit_arc.arcMoveTo(arc_rect, start_deg)
            hit_arc.arcTo(arc_rect, start_deg, extent)

            stroker = QPainterPathStroker()
            stroker.setCapStyle(Qt.RoundCap)
            stroker.setJoinStyle(Qt.RoundJoin)

            # 命中宽度只比实心环略宽一点，仍然贴着真正圆环
            hit_width = 12.0 if extent >= 14.0 else 16.0
            stroker.setWidth(hit_width)

            self._segment_meta.append({
                "cat": cat,
                "sec": sec,
                "start_deg": start_deg,
                "extent_deg": extent,
                "color": col,
                "radius": radius,
                "hit_path": stroker.createStroke(hit_arc),
            })

            start_deg += extent

        p.setPen(QPen(QColor(255, 255, 255, 128), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc_rect.adjusted(5, 5, -5, -5), int(-50 * 16), int(96 * 16))

        hub = QRadialGradient(QPointF(cx, cy), radius * 0.58)
        hub.setColorAt(0.0, QColor(255, 255, 255, 175 if self.hovered_cat else 165))
        hub.setColorAt(1.0, QColor(255, 255, 255, 86 if self.hovered_cat else 80))
        p.setBrush(hub)
        p.setPen(QPen(QColor(255, 255, 255, 145), 1.1))
        p.drawEllipse(QRectF(cx - radius * 0.49, cy - radius * 0.49, radius * 0.98, radius * 0.98))

        center_text = fmt_hms(total)
        center_sub = self._default_center_sub()
        if self.hovered_cat and self.hovered_cat in totals:
            hover_sec = totals[self.hovered_cat]
            share = hover_sec / total * 100.0 if total else 0.0
            center_text = fmt_hms(hover_sec)
            center_sub = f"{self.hovered_cat} · {share:.1f}%"

        p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 235))
        p.setFont(ui_font(self, 11, QFont.Bold))
        p.drawText(QRectF(cx - 100, cy - 14, 200, 22), Qt.AlignCenter, center_text)

        if center_sub:
            p.setPen(QColor(SUBTEXT.red(), SUBTEXT.green(), SUBTEXT.blue(), 190))
            p.setFont(ui_font(self, 8.8, QFont.Medium))
            p.drawText(QRectF(cx - 110, cy + 8, 220, 18), Qt.AlignCenter, center_sub)

        y = int(cy + radius + 14)
        x = r.left() + 10
        for cat, sec in ordered[:4]:
            col = color_for_category(cat)
            dot_size = 12 if cat == self.hovered_cat else 10
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, y + (5 if dot_size == 10 else 4), dot_size, dot_size), dot_size / 2, dot_size / 2)
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 215 if cat == self.hovered_cat else 205))
            p.setFont(ui_font(self, 9, QFont.Bold if cat == self.hovered_cat else QFont.Medium))
            share = sec / total * 100.0 if total else 0.0
            p.drawText(QRectF(x + 18, y, 240, 20), Qt.AlignLeft | Qt.AlignVCenter, f"{cat}  {fmt_hms(sec)}  ·  {share:.1f}%")
            y += 20


class RangeStatsCard(LightGlassCard):
    MODE_DAY = "day"
    MODE_WEEK = "week"
    MODE_MONTH = "month"

    def __init__(self, parent=None):
        super().__init__(radius=28, parent=parent)
        self.scope_mode = self.MODE_MONTH
        self.anchor_date = start_of_day(now_local())
        self.items = []
        self.on_scope_changed = None
        self.setMinimumHeight(170)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        self.lbl_title = QLabel("Work Summary")
        self.lbl_title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800;")
        lay.addWidget(self.lbl_title)

        self.lbl_period = QLabel("")
        self.lbl_period.setStyleSheet("color:rgba(90,100,120,200); font-weight:600;")
        lay.addWidget(self.lbl_period)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_day_scope = QPushButton("Day")
        self.btn_week_scope = QPushButton("Week")
        self.btn_month_scope = QPushButton("Month")
        self._scope_buttons = {
            self.MODE_DAY: self.btn_day_scope,
            self.MODE_WEEK: self.btn_week_scope,
            self.MODE_MONTH: self.btn_month_scope,
        }
        for mode, btn in self._scope_buttons.items():
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda checked=False, m=mode: self.set_scope_mode(m, emit=True))
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self.lbl_value = QLabel("00:00:00")
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setStyleSheet("color:rgba(33,42,60,235); font-weight:900; font-size:22px;")
        lay.addWidget(self.lbl_value)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setAlignment(Qt.AlignCenter)
        self.lbl_meta.setStyleSheet("color:rgba(33,42,60,205); font-weight:700;")
        lay.addWidget(self.lbl_meta)

        self.lbl_detail = QLabel("")
        self.lbl_detail.setAlignment(Qt.AlignCenter)
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color:rgba(90,100,120,195);")
        lay.addWidget(self.lbl_detail)

        self.set_scope_mode(self.scope_mode, emit=False)

    def set_scope_mode(self, mode: str, emit: bool = False):
        if mode not in (self.MODE_DAY, self.MODE_WEEK, self.MODE_MONTH):
            mode = self.MODE_MONTH
        self.scope_mode = mode
        for key, btn in self._scope_buttons.items():
            btn.setStyleSheet(glass_button_style(active=(key == self.scope_mode)))
        if emit and self.on_scope_changed:
            self.on_scope_changed(self.scope_mode)

    def set_scope_items(self, anchor_dt: datetime, items):
        self.anchor_date = start_of_day(anchor_dt)
        self.items = list(items or [])
        self._refresh_labels()

    def _period_text(self) -> str:
        if self.scope_mode == self.MODE_DAY:
            return self.anchor_date.strftime("%Y-%m-%d")
        if self.scope_mode == self.MODE_WEEK:
            st = week_start(self.anchor_date)
            ed = st + timedelta(days=6)
            return f"{st.strftime('%Y-%m-%d')}  ~  {ed.strftime('%m-%d')}"
        return month_start(self.anchor_date).strftime("%Y-%m")

    def _refresh_labels(self):
        ordered, total, totals = aggregate_category_totals(self.items)
        work_sec = totals.get("Work", 0)
        work_share = work_sec / total * 100.0 if total else 0.0
        work_count = 0
        for item in self.items:
            sec = max(0, int(item.get("duration_sec", 0) or 0))
            if sec > 0 and normalize_category(item.get("category", "Other")) == "Work":
                work_count += 1
        self.lbl_period.setText(self._period_text())
        self.lbl_value.setText(fmt_hms(work_sec))
        self.lbl_meta.setText(f"Total  {fmt_hms(total)}   ·   Work Items  {work_count}")
        if ordered:
            top_cat, top_sec = ordered[0]
            self.lbl_detail.setText(f"Work Share  {work_share:.1f}%   ·   All Items  {len(self.items)}   ·   Top Category  {top_cat} {fmt_hms(top_sec)}")
        else:
            self.lbl_detail.setText("No records in this range")


# ---------------- task dialog ----------------
class GlassDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        bg = QLinearGradient(r.topLeft(), r.bottomRight())
        bg.setColorAt(0.0, QColor(248, 251, 250, 240))
        bg.setColorAt(0.55, QColor(246, 249, 251, 232))
        bg.setColorAt(1.0, QColor(249, 247, 252, 238))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 18, 18)
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.15))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 18, 18)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(r), 18, 18)
        p.save()
        p.setClipPath(clip)
        blobs = [
            (QPointF(r.width() * 0.18, r.height() * 0.20), QColor(MINT.red(), MINT.green(), MINT.blue(), 34), r.width() * 0.35),
            (QPointF(r.width() * 0.84, r.height() * 0.22), QColor(PURPLE.red(), PURPLE.green(), PURPLE.blue(), 28), r.width() * 0.32),
            (QPointF(r.width() * 0.80, r.height() * 0.84), QColor(PURPLE.red(), PURPLE.green(), PURPLE.blue(), 24), r.width() * 0.34),
        ]
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        for center, col, rad in blobs:
            g = QRadialGradient(center, rad)
            g.setColorAt(0.0, col)
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            p.setBrush(g)
            p.setPen(Qt.NoPen)
            p.drawEllipse(center, rad, rad)
        p.restore()


class DialogTitleBar(QWidget):
    def __init__(self, dialog: QDialog, title: str):
        super().__init__(dialog)
        self.dialog = dialog
        self._dragging = False
        self._offset = QPoint(0, 0)
        self.setFixedHeight(34)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 4, 0)
        lay.setSpacing(8)

        self.lbl = QLabel(title)
        self.lbl.setStyleSheet("color:rgba(33,42,60,235); font-weight:900; font-size:13px;")
        lay.addWidget(self.lbl)
        lay.addStretch(1)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(glass_tiny_button_style())
        self.btn_close.setFont(ui_font(self, 8.0, QFont.Bold))
        self.btn_close.clicked.connect(self.dialog.reject)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.btn_close.geometry().contains(e.position().toPoint()):
            self._dragging = True
            self._offset = e.globalPosition().toPoint() - self.dialog.frameGeometry().topLeft()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._dragging:
            self.dialog.move(e.globalPosition().toPoint() - self._offset)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._dragging = False
        e.accept()


class SettingsDialog(GlassDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.win = parent
        self.setWindowTitle("Settings")
        self.resize(560, 520)

        self.original_scale = float(parent.glass_opacity_scale)
        self.original_mint = QColor(MINT)
        self.original_purple = QColor(PURPLE)
        self.current_scale = float(parent.glass_opacity_scale)
        self.current_mint = QColor(MINT)
        self.current_purple = QColor(PURPLE)
        self.original_categories = normalize_categories(parent.categories)
        self.current_categories = self.original_categories[:]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(12)
        lay.addWidget(DialogTitleBar(self, "Settings"))

        intro = QLabel("Adjust glass opacity, replace the default purple-green gradient, and define your own task categories.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:rgba(36,44,62,210); font-size:12px;")
        lay.addWidget(intro)

        opacity_title = QLabel("Glass opacity")
        opacity_title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800; font-size:13px;")
        lay.addWidget(opacity_title)

        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(10)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(70, 185)
        self.opacity_slider.setValue(int(round(self.current_scale * 100)))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider, 1)
        self.lbl_opacity = QLabel()
        self.lbl_opacity.setFixedWidth(58)
        self.lbl_opacity.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_opacity.setStyleSheet("color:rgba(33,42,60,235); font-weight:800;")
        opacity_row.addWidget(self.lbl_opacity)
        lay.addLayout(opacity_row)

        color_title = QLabel("Gradient colors")
        color_title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800; font-size:13px;")
        lay.addWidget(color_title)

        color_row = QHBoxLayout()
        color_row.setSpacing(10)
        self.btn_color_1 = QPushButton("Color A")
        self.btn_color_2 = QPushButton("Color B")
        self.btn_color_1.clicked.connect(lambda: self._pick_color(1))
        self.btn_color_2.clicked.connect(lambda: self._pick_color(2))
        color_row.addWidget(self.btn_color_1)
        color_row.addWidget(self.btn_color_2)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self._reset_defaults)
        color_row.addWidget(self.btn_reset)
        lay.addLayout(color_row)

        self.preview = QLabel("Gradient preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(84)
        lay.addWidget(self.preview)

        category_title = QLabel("Task categories")
        category_title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800; font-size:13px;")
        lay.addWidget(category_title)

        category_hint = QLabel("One category per line. Duplicates are removed automatically when you save.")
        category_hint.setWordWrap(True)
        category_hint.setStyleSheet("color:rgba(90,100,120,205); font-size:12px;")
        lay.addWidget(category_hint)

        self.txt_categories = QTextEdit()
        self.txt_categories.setPlaceholderText("Work\nStudy\nCommute")
        self.txt_categories.setFixedHeight(118)
        self.txt_categories.setPlainText("\n".join(self.current_categories))
        self.txt_categories.setStyleSheet(
            "QTextEdit{"
            "background:rgba(255,255,255,78); color:rgba(33,42,60,235);"
            "border:1px solid rgba(255,255,255,138); border-radius:16px; padding:10px 12px; font-size:12px; }"
        )
        lay.addWidget(self.txt_categories)

        category_row = QHBoxLayout()
        category_row.setSpacing(10)
        self.btn_reset_categories = QPushButton("Default task types")
        self.btn_reset_categories.clicked.connect(self._reset_categories_defaults)
        self.btn_reset_categories.setCursor(Qt.PointingHandCursor)
        self.btn_reset_categories.setStyleSheet(glass_button_style())
        category_row.addWidget(self.btn_reset_categories)
        category_row.addStretch(1)
        lay.addLayout(category_row)

        lay.addStretch(1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        for btn in (self.btn_color_1, self.btn_color_2, self.btn_reset):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(glass_button_style())
        for btn in btns.buttons():
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(glass_button_style())

        self._update_preview(push_preview=True)

    def _color_chip_style(self, color: QColor) -> str:
        rgba = f"rgba({color.red()},{color.green()},{color.blue()},230)"
        return (
            "QPushButton{" 
            f"background:{rgba}; color:rgba(20,28,40,235); border:1px solid rgba(255,255,255,210); "
            "border-radius:14px; padding:8px 14px; font-weight:800;}"
            "QPushButton:hover{border:1px solid rgba(255,255,255,235);}"
        )

    def _on_opacity_changed(self, value: int):
        self.current_scale = clamp_glass_opacity_scale(value / 100.0)
        self._update_preview(push_preview=True)

    def _pick_color(self, which: int):
        current = self.current_mint if which == 1 else self.current_purple
        color = QColorDialog.getColor(current, self, "Choose color")
        if not color.isValid():
            return
        if which == 1:
            self.current_mint = QColor(color)
        else:
            self.current_purple = QColor(color)
        self._update_preview(push_preview=True)

    def _reset_defaults(self):
        self.current_scale = DEFAULT_GLASS_OPACITY_SCALE
        self.current_mint = QColor(DEFAULT_MINT)
        self.current_purple = QColor(DEFAULT_PURPLE)
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(int(round(self.current_scale * 100)))
        self.opacity_slider.blockSignals(False)
        self._update_preview(push_preview=True)

    def _reset_categories_defaults(self):
        self.current_categories = DEFAULT_CATEGORIES[:]
        self.txt_categories.setPlainText("\n".join(self.current_categories))

    def _parsed_categories(self) -> list[str]:
        raw_lines = [line.strip() for line in self.txt_categories.toPlainText().splitlines()]
        filtered = [line for line in raw_lines if line]
        return normalize_categories(filtered)

    def _update_preview(self, push_preview: bool):
        self.lbl_opacity.setText(f"{int(round(self.current_scale * 100))}%")
        self.btn_color_1.setStyleSheet(self._color_chip_style(self.current_mint))
        self.btn_color_2.setStyleSheet(self._color_chip_style(self.current_purple))
        g0 = css_rgba(self.current_mint, 210, self.current_scale)
        g1 = css_rgba(self.current_purple, 210, self.current_scale)
        border = css_rgba(QColor(255, 255, 255), 220, self.current_scale)
        self.preview.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {g0}, stop:1 {g1});"
            f"border:1px solid {border}; border-radius:18px;"
            "color:rgba(20,28,40,235); font-weight:900; font-size:13px;"
        )
        if push_preview:
            self.win.apply_theme_settings(self.current_scale, self.current_mint, self.current_purple, persist=False)

    def accept(self):
        categories = self._parsed_categories()
        if not categories:
            QMessageBox.information(self, "Categories required", "Please keep at least one task category.")
            return
        self.current_categories = categories
        self.win.apply_category_settings(self.current_categories, persist=True)
        self.win.apply_theme_settings(self.current_scale, self.current_mint, self.current_purple, persist=True)
        super().accept()

    def reject(self):
        self.win.apply_theme_settings(self.original_scale, self.original_mint, self.original_purple, persist=False)
        super().reject()


class TaskDialog(GlassDialog):
    def __init__(self, parent, start_dt: datetime, end_dt: datetime, categories, preset_cat=None, preset_task=None, title="Log Task"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 340)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(DialogTitleBar(self, title))

        meta = QLabel(
            f"Start: {dt_to_str(start_dt)}\n"
            f"End: {dt_to_str(end_dt)}\n"
            f"Duration: {fmt_hms(int((end_dt - start_dt).total_seconds()))}"
        )
        meta.setStyleSheet("color:rgba(36,44,62,220); font-size:13px;")
        lay.addWidget(meta)

        self.cmb = QComboBox()
        category_items = normalize_categories(categories)
        if preset_cat:
            preset_normalized = normalize_category(preset_cat)
            if preset_normalized not in category_items:
                category_items.append(preset_normalized)
        self.cmb.addItems(category_items)
        if preset_cat:
            self.cmb.setCurrentText(normalize_category(preset_cat))
        lay.addWidget(self.cmb)

        self.txt = QTextEdit()
        self.txt.setPlaceholderText("What are you working on…")
        preset_task = normalize_task_text(preset_task or "")
        if preset_task != DEFAULT_TASK_PLACEHOLDER:
            self.txt.setPlainText(preset_task)
        lay.addWidget(self.txt, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        if allow_delete:
            self.btn_delete = btns.addButton(delete_label, QDialogButtonBox.DestructiveRole)
            self.btn_delete.clicked.connect(self._request_delete)
        else:
            self.btn_delete = None
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.setStyleSheet(
            '''
            QDialog{
                background:transparent;
                border:none;
            }
            QComboBox, QTextEdit{
                background:rgba(255,255,255,24);
                color:rgba(28,38,55,235);
                border:1px solid rgba(255,255,255,175);
                border-radius:14px;
                padding:8px;
                font-size:13px;
            }
            QComboBox::drop-down{border:0; width:28px;}
            QDialogButtonBox QPushButton{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(255,255,255,86),
                    stop:1 rgba(255,255,255,42));
                color:rgba(28,38,55,245);
                border:1px solid rgba(255,255,255,210);
                border-radius:12px;
                padding:8px 14px;
                font-weight:800;
                min-width:72px;
            }
            QDialogButtonBox QPushButton:hover{border:1px solid rgba(255,255,255,235);}
            '''
        )

    def category(self) -> str:
        return normalize_category(self.cmb.currentText().strip() or DEFAULT_CATEGORIES[0])

    def task_text(self) -> str:
        return normalize_task_text(self.txt.toPlainText())


class PlanDialog(GlassDialog):
    TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    RECURRENCE_OPTIONS = [("None", "none"), ("Every Week", "weekly"), ("Every Month", "monthly"), ("Every Year", "yearly")]

    def __init__(self, parent, start_dt: datetime, end_dt: datetime, categories, preset_cat=None, preset_task=None, title="Plan Task", preset_recurrence: str = "none", preset_all_day: bool = False, preset_recurrence_range_start: str = "", preset_recurrence_range_end: str = "", allow_delete: bool = False, delete_label: str = "Delete"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 520)
        self.delete_requested = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(DialogTitleBar(self, title))

        self.start_date_edit = QDateEdit(QDate(start_dt.year, start_dt.month, start_dt.day))
        self.end_date_edit = QDateEdit(QDate(end_dt.year, end_dt.month, end_dt.day))
        for w in (self.start_date_edit, self.end_date_edit):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.setButtonSymbols(QDateEdit.UpDownArrows)
            w.setKeyboardTracking(False)

        self.start_time_combo = self._make_time_combo(start_dt)
        self.end_time_combo = self._make_time_combo(end_dt)

        for w in (self.start_date_edit, self.end_date_edit):
            w.setMinimumWidth(150)
        for w in (self.start_time_combo, self.end_time_combo):
            w.setMinimumWidth(96)

        lbl_start = QLabel("Start")
        lbl_end = QLabel("End")
        lbl_start.setFixedWidth(40)
        lbl_end.setFixedWidth(32)

        meta = QHBoxLayout()
        meta.setSpacing(10)
        meta.addWidget(lbl_start, 0)
        meta.addWidget(self.start_date_edit, 3)
        meta.addWidget(self.start_time_combo, 2)
        meta.addSpacing(10)
        meta.addWidget(lbl_end, 0)
        meta.addWidget(self.end_date_edit, 3)
        meta.addWidget(self.end_time_combo, 2)
        lay.addLayout(meta)

        self.chk_all_day = QCheckBox("All day")
        self.chk_all_day.setChecked(bool(preset_all_day or is_all_day_span(start_dt, end_dt)))
        self.chk_all_day.toggled.connect(self._sync_all_day_state)
        lay.addWidget(self.chk_all_day)

        recur_row = QHBoxLayout()
        recur_row.setSpacing(10)
        recur_label = QLabel("Repeat")
        recur_label.setFixedWidth(52)
        recur_row.addWidget(recur_label, 0)
        self.cmb_recurrence = QComboBox()
        for label, value in self.RECURRENCE_OPTIONS:
            self.cmb_recurrence.addItem(label, value)
        preset_recurrence = str(preset_recurrence or 'none').strip().lower()
        idx = max(0, self.cmb_recurrence.findData(preset_recurrence))
        self.cmb_recurrence.setCurrentIndex(idx)
        recur_row.addWidget(self.cmb_recurrence, 1)
        lay.addLayout(recur_row)

        self.repeat_range_wrap = QWidget()
        range_row = QHBoxLayout(self.repeat_range_wrap)
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.setSpacing(8)
        range_label = QLabel("Range")
        range_label.setFixedWidth(44)
        range_row.addWidget(range_label, 0)

        try:
            preset_range_start_dt = datetime.strptime(str(preset_recurrence_range_start or ''), '%Y-%m-%d')
        except Exception:
            preset_range_start_dt = start_of_day(start_dt)
        try:
            preset_range_end_dt = datetime.strptime(str(preset_recurrence_range_end or ''), '%Y-%m-%d')
        except Exception:
            if preset_recurrence and str(preset_recurrence).strip().lower() != 'none':
                preset_range_end_dt = start_of_day(start_dt)
            else:
                preset_range_end_dt = start_of_day(end_dt)

        self.recur_start_date_edit = QDateEdit(QDate(preset_range_start_dt.year, preset_range_start_dt.month, preset_range_start_dt.day))
        self.recur_end_date_edit = QDateEdit(QDate(preset_range_end_dt.year, preset_range_end_dt.month, preset_range_end_dt.day))
        for w in (self.recur_start_date_edit, self.recur_end_date_edit):
            w.setCalendarPopup(True)
            w.setDisplayFormat('yyyy-MM-dd')
            w.setButtonSymbols(QDateEdit.UpDownArrows)
            w.setKeyboardTracking(False)
            w.setMinimumWidth(118)
            w.setMaximumWidth(132)
            w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            w.setFocusPolicy(Qt.StrongFocus)
        range_row.addWidget(self.recur_start_date_edit, 0)
        range_to = QLabel('to')
        range_to.setFixedWidth(14)
        range_to.setAlignment(Qt.AlignCenter)
        range_row.addWidget(range_to, 0)
        range_row.addWidget(self.recur_end_date_edit, 0)
        range_row.addStretch(1)
        lay.addWidget(self.repeat_range_wrap)

        recur_hint = QLabel("Tip: birthdays can be saved as all-day yearly recurring tasks. They will appear as small labels instead of occupying the whole day block.")
        recur_hint.setWordWrap(True)
        recur_hint.setStyleSheet("color:rgba(90,100,120,205); font-size:12px; font-weight:600;")
        lay.addWidget(recur_hint)

        self.cmb = QComboBox()
        category_items = normalize_categories(categories)
        if preset_cat:
            preset_normalized = normalize_category(preset_cat)
            if preset_normalized not in category_items:
                category_items.append(preset_normalized)
        self.cmb.addItems(category_items)
        if preset_cat:
            self.cmb.setCurrentText(normalize_category(preset_cat))
        lay.addWidget(self.cmb)

        self.txt = QTextEdit()
        self.txt.setPlaceholderText("What are you planning to do…")
        preset_task = normalize_task_text(preset_task or "")
        if preset_task != DEFAULT_TASK_PLACEHOLDER:
            self.txt.setPlainText(preset_task)
        lay.addWidget(self.txt, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        if allow_delete:
            self.btn_delete = btns.addButton(delete_label, QDialogButtonBox.DestructiveRole)
            self.btn_delete.clicked.connect(self._request_delete)
        else:
            self.btn_delete = None
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.setStyleSheet(
            """
            QDialog{
                background:transparent;
                border:none;
            }
            QLabel, QCheckBox{
                color:rgba(36,44,62,220);
                font-size:13px;
                font-weight:800;
            }
            QComboBox, QTextEdit, QDateTimeEdit, QDateEdit{
                background:rgba(255,255,255,24);
                color:rgba(28,38,55,235);
                border:1px solid rgba(255,255,255,175);
                border-radius:14px;
                padding:8px;
                font-size:13px;
            }
            QCheckBox::indicator{width:16px; height:16px;}
            QComboBox::drop-down{border:0; width:28px;}
            QDateTimeEdit::drop-down, QDateEdit::drop-down{border:0; width:26px;}
            QDialogButtonBox QPushButton{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(255,255,255,86),
                    stop:1 rgba(255,255,255,42));
                color:rgba(28,38,55,245);
                border:1px solid rgba(255,255,255,210);
                border-radius:12px;
                padding:8px 14px;
                font-weight:800;
                min-width:72px;
            }
            QDialogButtonBox QPushButton:hover{border:1px solid rgba(255,255,255,235);}
            """
        )

        self.cmb_recurrence.currentIndexChanged.connect(self._sync_recurrence_range_state)
        self._sync_all_day_state(self.chk_all_day.isChecked())
        self._sync_recurrence_range_state()

    def _make_time_combo(self, dt: datetime) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self.TIME_OPTIONS)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.lineEdit().setPlaceholderText("HH:mm")
        combo.setCurrentText(f"{dt.hour:02d}:{dt.minute:02d}")
        return combo

    def _parse_time_text(self, combo: QComboBox, label: str) -> QTime:
        text = combo.currentText().strip().replace(".", ":")
        for fmt in ("HH:mm", "H:mm", "HHmm", "Hmm"):
            qtime = QTime.fromString(text, fmt)
            if qtime.isValid():
                combo.setCurrentText(qtime.toString("HH:mm"))
                return qtime
        raise ValueError(f"{label} time must be in HH:mm format.")

    def _sync_all_day_state(self, checked: bool):
        if checked:
            self.start_time_combo.setCurrentText("00:00")
            self.end_time_combo.setCurrentText("23:59")
        self.start_time_combo.setEnabled(not checked)
        self.end_time_combo.setEnabled(not checked)

    def _sync_recurrence_range_state(self):
        enabled = self.recurrence() != 'none'
        self.repeat_range_wrap.setVisible(enabled)
        self.recur_start_date_edit.setEnabled(enabled)
        self.recur_end_date_edit.setEnabled(enabled)

    def _request_delete(self):
        self.delete_requested = True
        super().accept()

    def accept(self):
        if self.delete_requested:
            super().accept()
            return
        try:
            start_dt = self.start_datetime()
            end_dt = self.end_datetime()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Time", str(exc))
            return
        if end_dt <= start_dt:
            QMessageBox.warning(self, "Invalid Time", "End time must be later than start time.")
            return
        if self.recurrence() != 'none' and self.recurrence_range_end_date() < self.recurrence_range_start_date():
            QMessageBox.warning(self, "Invalid Repeat Range", "Repeat end date must be on or after repeat start date.")
            return
        super().accept()

    def start_datetime(self) -> datetime:
        qd = self.start_date_edit.date()
        if self.is_all_day():
            return datetime(qd.year(), qd.month(), qd.day(), 0, 0, 0)
        qt = self._parse_time_text(self.start_time_combo, "Start")
        return datetime(qd.year(), qd.month(), qd.day(), qt.hour(), qt.minute())

    def end_datetime(self) -> datetime:
        qd = self.end_date_edit.date()
        if self.is_all_day():
            return datetime(qd.year(), qd.month(), qd.day(), 23, 59, 0)
        qt = self._parse_time_text(self.end_time_combo, "End")
        return datetime(qd.year(), qd.month(), qd.day(), qt.hour(), qt.minute())

    def is_all_day(self) -> bool:
        return bool(self.chk_all_day.isChecked())

    def recurrence(self) -> str:
        return str(self.cmb_recurrence.currentData() or 'none')

    def recurrence_range_start_date(self) -> datetime:
        qd = self.recur_start_date_edit.date()
        return datetime(qd.year(), qd.month(), qd.day())

    def recurrence_range_end_date(self) -> datetime:
        qd = self.recur_end_date_edit.date()
        return datetime(qd.year(), qd.month(), qd.day())

    def recurrence_range_start(self) -> str:
        if self.recurrence() == 'none':
            return ''
        return self.recurrence_range_start_date().strftime('%Y-%m-%d')

    def recurrence_range_end(self) -> str:
        if self.recurrence() == 'none':
            return ''
        return self.recurrence_range_end_date().strftime('%Y-%m-%d')

    def category(self) -> str:
        return normalize_category(self.cmb.currentText().strip() or DEFAULT_CATEGORIES[0])

    def task_text(self) -> str:
        return normalize_task_text(self.txt.toPlainText())




class JumpDateCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        selected = date == self.selectedDate()
        today = date == QDate.currentDate()
        in_month = (date.month() == self.monthShown() and date.year() == self.yearShown())

        if selected:
            bg_rect = QRectF(rect).adjusted(4, 3, -4, -3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(176, 182, 192, 150))
            painter.drawRoundedRect(bg_rect, 10, 10)
        elif today:
            bg_rect = QRectF(rect).adjusted(6, 5, -6, -5)
            painter.setPen(QPen(QColor(160, 168, 180, 135), 1.4))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(bg_rect, 9, 9)

        txt_color = QColor(33, 42, 60, 240) if in_month else QColor(120, 128, 140, 180)
        if selected:
            txt_color = QColor(28, 38, 55, 248)

        painter.setPen(txt_color)
        font = painter.font()
        font.setFamily('Segoe UI')
        font.setPointSize(max(9, font.pointSize()))
        font.setBold(selected)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))
        painter.restore()

class DateJumpDialog(GlassDialog):
    def __init__(self, parent, current_dt: datetime):
        super().__init__(parent)
        self.setWindowTitle("Choose Date")
        self.resize(330, 318)
        self.selected_dt = start_of_day(current_dt)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(DialogTitleBar(self, "Choose Date"))

        self.cal = JumpDateCalendar()
        self.cal.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setSelectedDate(QDate(current_dt.year, current_dt.month, current_dt.day))
        self.cal.clicked.connect(self._on_date_clicked)
        self.cal.setStyleSheet(
            """
            QCalendarWidget{
                background: rgba(255,255,255,46);
                border: none;
                border-radius: 16px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar{
                background: rgba(255,255,255,92);
                border: 1px solid rgba(255,255,255,210);
                border-radius: 14px;
            }
            QCalendarWidget QToolButton{
                color: rgba(28,38,55,235);
                background: transparent;
                border: none;
                padding: 6px 10px;
                font-weight: 800;
            }
            QCalendarWidget QMenu{
                background: rgba(248,250,252,238);
                color: rgba(28,38,55,235);
                border: 1px solid rgba(255,255,255,220);
                border-radius: 10px;
            }
            QCalendarWidget QSpinBox{
                background: rgba(255,255,255,110);
                color: rgba(28,38,55,235);
                border: 1px solid rgba(255,255,255,210);
                border-radius: 10px;
                padding: 3px 8px;
            }
            QCalendarWidget QWidget#qt_calendar_calendarview{
                background: rgba(255,255,255,86);
                border: none;
            }
            QCalendarWidget QAbstractItemView,
            QCalendarWidget QTableView{
                background: rgba(255,255,255,86);
                color: rgba(28,38,55,235);
                selection-background-color: rgba(255,255,255,0);
                selection-color: rgba(28,38,55,235);
                alternate-background-color: rgba(255,255,255,86);
                outline: 0;
                border: none;
                gridline-color: rgba(120,130,150,28);
            }
            QCalendarWidget QAbstractItemView::item{
                background: rgba(255,255,255,0);
            }
            QCalendarWidget QAbstractItemView::item:selected{
                background: rgba(255,255,255,0);
                color: rgba(28,38,55,240);
            }
            QCalendarWidget QHeaderView::section{
                background: rgba(255,255,255,0);
                border: none;
                color: rgba(33,42,60,215);
                font-weight: 800;
            }
            """
        )
        cal_view = self.cal.findChild(QWidget, "qt_calendar_calendarview")
        if cal_view is not None:
            cal_view.setAutoFillBackground(True)
            cal_view.setStyleSheet("background: rgba(255,255,255,86); border:none;")
            if hasattr(cal_view, "viewport") and cal_view.viewport() is not None:
                cal_view.viewport().setAutoFillBackground(True)
                cal_view.viewport().setStyleSheet("background: rgba(255,255,255,86);")
        lay.addWidget(self.cal, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        today_btn = QPushButton("Today")
        btns.addButton(today_btn, QDialogButtonBox.ActionRole)
        today_btn.clicked.connect(self._jump_today)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.setStyleSheet(
            """
            QDialogButtonBox QPushButton{
                background:rgba(255,255,255,72);
                color:rgba(28,38,55,235);
                border:1px solid rgba(255,255,255,220);
                border-radius:14px;
                padding:8px 16px;
                font-weight:800;
                min-width:68px;
            }
            """
        )

    def _on_date_clicked(self, qd: QDate):
        self.selected_dt = datetime(qd.year(), qd.month(), qd.day())

    def _jump_today(self):
        now = now_local()
        qd = QDate(now.year, now.month, now.day)
        self.cal.setSelectedDate(qd)
        self.cal.setCurrentPage(now.year, now.month)
        self.selected_dt = start_of_day(now)

    def selected_datetime(self) -> datetime:
        qd = self.cal.selectedDate()
        return datetime(qd.year(), qd.month(), qd.day())


# ---------------- titlebar ----------------
class TitleBar(QWidget):
    def __init__(self, win: QMainWindow):
        super().__init__(win)
        self.win = win
        self._dragging = False
        self._offset = QPoint(0, 0)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.left_spacer = QWidget()
        self.left_spacer.setFixedWidth(140)
        lay.addWidget(self.left_spacer)
        lay.addStretch(1)

        self.lbl = QLabel(APP_NAME)
        self.lbl.setStyleSheet("color:rgba(33,42,60,235); font-weight:900;")
        lay.addWidget(self.lbl, 0, Qt.AlignCenter)
        lay.addStretch(1)

        self.right_box = QWidget()
        right_lay = QHBoxLayout(self.right_box)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.win.open_settings_dialog)
        right_lay.addWidget(self.btn_settings)

        self.btn_pin = QPushButton()
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.clicked.connect(self.win.toggle_window_locked)
        right_lay.addWidget(self.btn_pin)

        self.btn_close = QPushButton("✕")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.win.close)
        right_lay.addWidget(self.btn_close)
        lay.addWidget(self.right_box)

        self.apply_scale()
        self.refresh_theme()

    def _sync_center(self):
        self.left_spacer.setFixedWidth(max(10, self.right_box.sizeHint().width()))

    def apply_scale(self):
        self.setFixedHeight(sp(self, 38))
        self.lbl.setFont(ui_font(self, 17, QFont.Black))
        self.btn_settings.setFixedSize(sp(self, 28), sp(self, 26))
        self.btn_pin.setFixedSize(sp(self, 60), sp(self, 26))
        self.btn_close.setFixedSize(sp(self, 28), sp(self, 26))
        self.btn_settings.setFont(ui_font(self, 9.6, QFont.Bold))
        self.btn_pin.setFont(ui_font(self, 8.8, QFont.Bold))
        self.btn_close.setFont(ui_font(self, 8.0, QFont.Bold))

    def refresh_theme(self):
        self.btn_settings.setStyleSheet(glass_tiny_button_style())
        self.btn_close.setStyleSheet(glass_tiny_button_style())
        self.refresh_lock_button()

    def refresh_lock_button(self):
        locked = self.win.is_window_locked() if hasattr(self.win, "is_window_locked") else False
        self.btn_pin.setText("Fixed" if locked else "Pin")
        if locked:
            self.btn_pin.setStyleSheet(glass_tiny_button_style(active=True))
        else:
            self.btn_pin.setStyleSheet(glass_tiny_button_style())
        self._sync_center()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_center()

    def mousePressEvent(self, e):
        if getattr(self.win, "window_locked", False):
            return
        blocked = (
            self.btn_close.geometry().contains(e.position().toPoint())
            or self.btn_pin.geometry().contains(e.position().toPoint())
            or self.btn_settings.geometry().contains(e.position().toPoint())
        )
        if e.button() == Qt.LeftButton and not blocked:
            self._dragging = True
            self._offset = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if getattr(self.win, "window_locked", False):
            return
        if self._dragging:
            self.win.move(e.globalPosition().toPoint() - self._offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._dragging = False
        e.accept()


@dataclass
class RunningSession:
    start_dt: datetime
    start_monotonic: float


# ---------------- calendar canvas ----------------
class CalendarCanvas(LightGlassCard):
    MODE_MONTH = 0
    MODE_WEEK = 1
    MODE_DAY = 2

    def __init__(self, parent=None):
        super().__init__(radius=30, parent=parent)
        self.glass_opacity_scale = CALENDAR_GLASS_OPACITY_SCALE
        self.setFocusPolicy(Qt.StrongFocus)
        self.selected_date = start_of_day(now_local())
        self.mode = self.MODE_MONTH
        self.view_start_hour = 9.0
        self.visible_hours = 3.0
        self.hovered_date: datetime | None = None
        self.get_sessions_callback = None
        self.get_plans_callback = None
        self.on_selected_date_changed = None
        self.on_mode_changed = None
        self.on_edit_session = None
        self.on_edit_plan = None
        self.on_add_plan_requested = None
        self.on_pick_month_year = None
        self.on_duplicate_item_requested = None
        self.on_delete_item_requested = None
        self.on_resize_item_requested = None
        self.on_undo_requested = None
        self._title_hit = QRectF()
        self._month_cells: list[tuple[QRectF, datetime]] = []
        self._week_day_rects: list[tuple[QRectF, datetime]] = []
        self._item_hits: list[dict] = []
        self._grid_rect: QRectF | None = None
        self.focus_item_source: str | None = None
        self.focus_item_id: int | None = None
        self._duplicate_drag_hit: dict | None = None
        self._duplicate_drag_start: datetime | None = None
        self._duplicate_drag_end: datetime | None = None
        self._duplicate_drag_rect: QRectF | None = None
        self._resize_drag_hit: dict | None = None
        self._resize_drag_edge: str | None = None
        self._resize_drag_start: datetime | None = None
        self._resize_drag_end: datetime | None = None
        self._resize_drag_rect: QRectF | None = None
        self._resize_hover_edge: str | None = None
        self.setMouseTracking(True)

    def set_sessions_callback(self, fn):
        self.get_sessions_callback = fn

    def set_plans_callback(self, fn):
        self.get_plans_callback = fn

    def set_selected_date(self, dt: datetime):
        self.selected_date = start_of_day(dt)
        self.update()

    def set_mode(self, mode: int):
        mode = max(self.MODE_MONTH, min(self.MODE_DAY, int(mode)))
        if self.mode != mode:
            self.mode = mode
            if self.on_mode_changed:
                self.on_mode_changed(mode)
        self.update()

    def visible_title(self) -> str:
        if self.mode == self.MODE_MONTH:
            return self.selected_date.strftime("%Y-%m")
        if self.mode == self.MODE_WEEK:
            st = week_start(self.selected_date)
            ed = st + timedelta(days=6)
            return f"{st.strftime('%Y-%m-%d')}  ~  {ed.strftime('%m-%d')}"
        return self.selected_date.strftime("%Y-%m-%d")

    def _sessions_in_range(self, start_dt: datetime, end_dt: datetime):
        if self.get_sessions_callback:
            return self.get_sessions_callback(start_dt, end_dt)
        return []

    def _plans_in_range(self, start_dt: datetime, end_dt: datetime):
        if self.get_plans_callback:
            return self.get_plans_callback(start_dt, end_dt)
        return []

    def _combined_items_in_range(self, start_dt: datetime, end_dt: datetime):
        items = []
        for s in self._sessions_in_range(start_dt, end_dt):
            x = dict(s)
            x["source"] = "session"
            items.extend(split_item_by_day(x, start_dt, end_dt))
        for s in self._plans_in_range(start_dt, end_dt):
            x = dict(s)
            x["source"] = "plan"
            items.extend(split_item_by_day(x, start_dt, end_dt))
        items.sort(key=lambda item: item.get("start", ""))
        return items

    def set_focus_item(self, source: str | None, sid: int | None):
        self.focus_item_source = source
        self.focus_item_id = int(sid) if sid is not None else None
        self.update()

    def _item_title_text(self, item: dict) -> str:
        text = normalize_task_text(item.get("task_text", ""))
        if text == DEFAULT_TASK_PLACEHOLDER:
            return normalize_category(item.get("category", "Other"))
        return text

    def _item_time_text(self, item: dict) -> str:
        try:
            ss = str_to_dt(item["start"])
            ee = str_to_dt(item["end"])
        except Exception:
            return ""
        if bool(item.get("is_all_day", False)):
            recur = str(item.get("recurrence", "none") or "none")
            if recur == "yearly":
                return "All day · yearly"
            if recur == "monthly":
                return "All day · monthly"
            if recur == "weekly":
                return "All day · weekly"
            return "All day"
        return f"{ss.strftime('%H:%M')}-{ee.strftime('%H:%M')}"

    def _calendar_item_detail_text(self, item: dict, include_category: bool = False) -> str:
        detail = self._item_time_text(item)
        if include_category:
            detail = f"{detail}   {normalize_category(item.get('category', 'Other'))}"
        return detail

    def _calendar_item_show_detail(self, rect: QRectF, mode: str = 'week', include_category: bool = False) -> bool:
        width = float(rect.width())
        height = float(rect.height())
        if include_category:
            return width >= 180.0 and height >= 56.0
        if mode == 'day':
            return width >= 140.0 and height >= 46.0
        return width >= 78.0 and height >= 38.0

    def _is_all_day_item(self, item: dict) -> bool:
        return bool(item.get("is_all_day", False))

    def _paint_all_day_chip(self, p: QPainter, rect: QRectF, item: dict, compact: bool = False):
        col = color_for_category(item.get("category", "Other"))
        focused = self._is_focused_item(item)
        if focused:
            p.setPen(QPen(QColor(255, 255, 255, 235), 1.6))
            p.setBrush(QColor(255, 255, 255, 28))
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 8, 8)
        self._pill(p, rect, self._item_title_text(item)[:(12 if compact else 22)], col)
        hit = dict(item)
        hit["rect"] = QRectF(rect)
        hit["resizable"] = False
        self._item_hits.append(hit)

    def _is_focused_item(self, item: dict) -> bool:
        return (
            self.focus_item_source is not None
            and self.focus_item_id is not None
            and str(item.get("source", "")) == str(self.focus_item_source)
            and int(item.get("id", -1)) == int(self.focus_item_id)
        )

    def _hit_item_at(self, pos):
        for hit in reversed(self._item_hits):
            rect = hit.get("rect")
            if rect is not None and rect.contains(pos):
                return hit
        return None

    def _edge_hit_for_item(self, pos, hit: dict | None = None) -> tuple[dict | None, str | None]:
        if self.mode not in (self.MODE_WEEK, self.MODE_DAY):
            return None, None
        target = hit if hit is not None else self._hit_item_at(pos)
        if target is None:
            return None, None
        rect = target.get("rect")
        if rect is None or not rect.contains(pos):
            return None, None

        handle_h = max(8.0, min(14.0, rect.height() * 0.28))
        top_zone = QRectF(rect.left(), rect.top(), rect.width(), handle_h)
        bottom_zone = QRectF(rect.left(), rect.bottom() - handle_h, rect.width(), handle_h)
        if top_zone.contains(pos):
            return target, "start"
        if bottom_zone.contains(pos):
            return target, "end"
        return target, None

    def _update_resize_cursor(self, pos):
        if self._resize_drag_hit is not None:
            self.setCursor(Qt.SizeVerCursor)
            return
        _hit, edge = self._edge_hit_for_item(pos)
        self._resize_hover_edge = edge
        self.setCursor(Qt.SizeVerCursor if edge else Qt.ArrowCursor)

    def _snapped_datetime_from_position(self, pos, base_dt: datetime | None = None) -> datetime:
        dt = start_of_day(base_dt or self._date_at_position(pos) or self.selected_date)
        hour = self._hour_at_position(pos)
        total_minutes = int(round(hour * 60.0))
        total_minutes = max(0, min(24 * 60, total_minutes))
        if total_minutes >= 24 * 60:
            return dt + timedelta(days=1)
        hh = total_minutes // 60
        mm = total_minutes % 60
        return dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    def _proposal_from_resize_hit(self, pos, item: dict, edge: str):
        rect = item.get("rect")
        if rect is None or self._grid_rect is None:
            return None, None, None
        piece_start = str_to_dt(item.get("start"))
        true_start = str_to_dt(item.get("true_start", item.get("start")))
        true_end = str_to_dt(item.get("true_end", item.get("end")))
        moving_dt = self._snapped_datetime_from_position(pos, piece_start)
        min_delta = timedelta(minutes=1)

        if edge == "start":
            new_start = min(moving_dt, true_end - min_delta)
            new_end = true_end
        else:
            new_start = true_start
            new_end = max(moving_dt, true_start + min_delta)

        if new_end <= new_start:
            return None, None, None

        display_start = max(new_start, start_of_day(piece_start))
        display_end = min(new_end, start_of_day(piece_start) + timedelta(days=1))
        if display_end <= display_start:
            return new_start, new_end, None

        start_hour, end_hour = hours_in_day_span(display_start, display_end)
        view_end = self.view_start_hour + self.visible_hours
        if end_hour <= self.view_start_hour or start_hour >= view_end:
            return new_start, new_end, None

        if self.mode == self.MODE_WEEK:
            hour_w = 72
            col_w = (self._grid_rect.width() - hour_w) / 7.0
            col_index = (start_of_day(piece_start) - week_start(self.selected_date)).days
            if col_index < 0 or col_index > 6:
                return new_start, new_end, None
            y1 = self._grid_rect.top() + (max(self.view_start_hour, start_hour) - self.view_start_hour) / self.visible_hours * self._grid_rect.height()
            y2 = self._grid_rect.top() + (min(view_end, end_hour) - self.view_start_hour) / self.visible_hours * self._grid_rect.height()
            if y2 < y1 + 20:
                y2 = y1 + 20
            x = self._grid_rect.left() + hour_w + col_index * col_w + 6
            rect = QRectF(x, y1 + 4, col_w - 12, max(18.0, y2 - y1 - 8))
            return new_start, new_end, rect

        grid = self._grid_rect
        label_w = 82
        content_x = grid.left() + label_w
        y1 = grid.top() + (max(self.view_start_hour, start_hour) - self.view_start_hour) / self.visible_hours * grid.height()
        y2 = grid.top() + (min(view_end, end_hour) - self.view_start_hour) / self.visible_hours * grid.height()
        visible_h = max(4.0, y2 - y1)
        box_h = max(24.0, visible_h - 12)
        rect_y = y1 + 6
        if visible_h < 36:
            if end_hour > view_end and start_hour >= self.view_start_hour:
                rect_y = y1 + 6
            elif start_hour < self.view_start_hour and end_hour <= view_end:
                rect_y = y2 - box_h - 6
            else:
                rect_y = y1 + max(2.0, (visible_h - box_h) * 0.5)
        rect = QRectF(content_x + 10, rect_y, grid.width() - label_w - 20, box_h)
        return new_start, new_end, rect

    def _proposal_from_drag_hit(self, pos, item: dict):
        if self.mode != self.MODE_WEEK or self._grid_rect is None or not self._grid_rect.contains(pos):
            return None, None, None
        base_dt = self._date_at_position(pos)
        if base_dt is None:
            return None, None, None
        start_dt, _ = self._proposal_from_position(pos, base_dt)
        duration_sec = max(60, int(item.get("duration_sec", 0) or 0))
        end_dt = start_dt + timedelta(seconds=duration_sec)
        ss = str_to_dt(item["start"])
        ee = str_to_dt(item["end"])
        start_hour, end_hour = hours_in_day_span(start_dt, end_dt)
        view_end = self.view_start_hour + self.visible_hours
        col_index = (start_of_day(start_dt) - week_start(self.selected_date)).days
        if col_index < 0 or col_index > 6:
            return start_dt, end_dt, None
        y1 = self._grid_rect.top() + (max(self.view_start_hour, start_hour) - self.view_start_hour) / self.visible_hours * self._grid_rect.height()
        y2 = self._grid_rect.top() + (min(view_end, end_hour) - self.view_start_hour) / self.visible_hours * self._grid_rect.height()
        if y2 < y1 + 20:
            y2 = y1 + 20
        hour_w = 72
        col_w = (self._grid_rect.width() - hour_w) / 7.0
        x = self._grid_rect.left() + hour_w + col_index * col_w + 6
        rect = QRectF(x, y1 + 4, col_w - 12, max(18.0, y2 - y1 - 8))
        return start_dt, end_dt, rect

    def _emit_selection(self, dt: datetime):
        self.selected_date = start_of_day(dt)
        if self.on_selected_date_changed:
            self.on_selected_date_changed(self.selected_date)
        self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._duplicate_drag_hit is not None:
            self.hovered_date = self._date_at_position(pos)
            self._duplicate_drag_start, self._duplicate_drag_end, self._duplicate_drag_rect = self._proposal_from_drag_hit(pos, self._duplicate_drag_hit)
            self.update()
            e.accept()
            return
        if self._resize_drag_hit is not None and self._resize_drag_edge is not None:
            self.hovered_date = self._date_at_position(pos)
            self._resize_drag_start, self._resize_drag_end, self._resize_drag_rect = self._proposal_from_resize_hit(pos, self._resize_drag_hit, self._resize_drag_edge)
            self.setCursor(Qt.SizeVerCursor)
            self.update()
            e.accept()
            return
        self.hovered_date = self._date_at_position(pos)
        self._update_resize_cursor(pos)
        self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hovered_date = None
        self._resize_hover_edge = None
        if self._duplicate_drag_hit is None and self._resize_drag_hit is None:
            self.setCursor(Qt.ArrowCursor)
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = e.position()
            if self._title_hit.contains(pos):
                if self.on_pick_month_year:
                    self.on_pick_month_year(self.selected_date)
                return
            edge_hit, edge = self._edge_hit_for_item(pos)
            if edge_hit is not None:
                self.setFocus(Qt.MouseFocusReason)
                self.set_focus_item(edge_hit.get("source"), edge_hit.get("id"))
                try:
                    self._emit_selection(start_of_day(str_to_dt(edge_hit.get("start"))))
                except Exception:
                    self.update()
                if edge is not None:
                    self._resize_drag_hit = dict(edge_hit)
                    self._resize_drag_edge = edge
                    self._resize_drag_start = None
                    self._resize_drag_end = None
                    self._resize_drag_rect = QRectF(edge_hit.get("rect")) if edge_hit.get("rect") is not None else None
                    self.setCursor(Qt.SizeVerCursor)
                    e.accept()
                    return
                if self.mode == self.MODE_WEEK and (e.modifiers() & Qt.AltModifier):
                    self._duplicate_drag_hit = dict(edge_hit)
                    self._duplicate_drag_start = None
                    self._duplicate_drag_end = None
                    self._duplicate_drag_rect = None
                e.accept()
                return
            dt = self._date_at_position(pos)
            if dt:
                self.setFocus(Qt.MouseFocusReason)
                self._emit_selection(dt)
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        pos = e.position()
        hit = self._hit_item_at(pos)
        if hit is not None:
            self.setFocus(Qt.MouseFocusReason)
            self.set_focus_item(hit.get("source"), hit.get("id"))
            try:
                self._emit_selection(start_of_day(str_to_dt(hit.get("start"))))
            except Exception:
                self.update()
            source = str(hit.get("source", "session"))
            sid = int(hit.get("id", -1))
            if source == "session" and self.on_edit_session:
                self.on_edit_session(sid)
            elif source == "plan" and self.on_edit_plan:
                self.on_edit_plan(sid, str(hit.get("occurrence_start") or hit.get("start") or ""))
            e.accept()
            return

        dt = self._date_at_position(pos)
        if dt:
            self._emit_selection(dt)
        if self.mode == self.MODE_MONTH:
            if dt:
                self.set_mode(self.MODE_WEEK)
                e.accept()
                return
        else:
            can_add = False
            if self.mode == self.MODE_DAY:
                can_add = self._grid_rect is not None and self._grid_rect.contains(pos)
            elif self.mode == self.MODE_WEEK:
                can_add = dt is not None
            if self.on_add_plan_requested and can_add:
                base_dt = dt or self.selected_date
                start_dt, end_dt = self._proposal_from_position(pos, base_dt)
                self.on_add_plan_requested(start_dt, end_dt)
                e.accept()
                return
        super().mouseDoubleClickEvent(e)


    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._resize_drag_hit is not None:
            ret = None
            if self.on_resize_item_requested and self._resize_drag_start is not None and self._resize_drag_end is not None:
                ret = self.on_resize_item_requested(dict(self._resize_drag_hit), self._resize_drag_start, self._resize_drag_end)
            self._resize_drag_hit = None
            self._resize_drag_edge = None
            self._resize_drag_start = None
            self._resize_drag_end = None
            self._resize_drag_rect = None
            self.setCursor(Qt.ArrowCursor)
            if isinstance(ret, tuple) and len(ret) == 2:
                self.set_focus_item(ret[0], ret[1])
            self.update()
            e.accept()
            return
        if e.button() == Qt.LeftButton and self._duplicate_drag_hit is not None:
            ret = None
            if self.on_duplicate_item_requested and self._duplicate_drag_start is not None and self._duplicate_drag_end is not None:
                ret = self.on_duplicate_item_requested(dict(self._duplicate_drag_hit), self._duplicate_drag_start, self._duplicate_drag_end)
            self._duplicate_drag_hit = None
            self._duplicate_drag_start = None
            self._duplicate_drag_end = None
            self._duplicate_drag_rect = None
            if isinstance(ret, tuple) and len(ret) == 2:
                self.set_focus_item(ret[0], ret[1])
            self.update()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        if delta == 0:
            e.ignore()
            return
        steps = 1 if delta < 0 else -1

        if self.mode in (self.MODE_DAY, self.MODE_WEEK):
            if e.modifiers() & Qt.ControlModifier:
                anchor = self._hour_at_position(e.position())
                self._zoom_visible_hours(anchor, zoom_in=(delta > 0))
            else:
                step_hours = 1.0 if self.visible_hours <= 8 else max(1.0, round(self.visible_hours / 6.0, 2))
                self.view_start_hour = max(0.0, min(24.0 - self.visible_hours, self.view_start_hour + (step_hours if delta < 0 else -step_hours)))
                self._normalize_view_window()
            self.update()
            e.accept()
            return

        if self.mode == self.MODE_MONTH:
            base = month_start(self.selected_date)
            new_dt = add_months(base, steps)
            day = min(self.selected_date.day, 28)
            self._emit_selection(new_dt.replace(day=day))
            self.update()
            e.accept()
            return

        e.ignore()

    def keyPressEvent(self, e):
        if (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_Z:
            if self.on_undo_requested:
                self.on_undo_requested()
                e.accept()
                return
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.focus_item_source is not None and self.focus_item_id is not None and self.on_delete_item_requested:
                self.on_delete_item_requested(self.focus_item_source, self.focus_item_id)
                e.accept()
                return
        super().keyPressEvent(e)

    def _normalize_view_window(self):
        step = 0.25
        self.visible_hours = max(2.0, min(24.0, round(self.visible_hours / step) * step))
        max_start = max(0.0, 24.0 - self.visible_hours)
        self.view_start_hour = max(0.0, min(max_start, round(self.view_start_hour / step) * step))

    def _fmt_axis_time(self, hour_value: float) -> str:
        total_minutes = int(round(hour_value * 60)) % (24 * 60)
        hh = total_minutes // 60
        mm = total_minutes % 60
        return f"{hh:02d}:{mm:02d}"

    def _zoom_visible_hours(self, anchor_hour: float, zoom_in: bool):
        old_hours = float(self.visible_hours)
        new_hours = max(2.0, round(old_hours * 0.82, 2)) if zoom_in else min(24.0, round(old_hours * 1.22 + 0.05, 2))
        if abs(new_hours - old_hours) < 0.01:
            return
        ratio = 0.5 if old_hours <= 0 else (anchor_hour - self.view_start_hour) / old_hours
        ratio = max(0.0, min(1.0, ratio))
        new_start = anchor_hour - ratio * new_hours
        self.visible_hours = new_hours
        self.view_start_hour = max(0.0, min(24.0 - self.visible_hours, new_start))
        self._normalize_view_window()

    def _hour_at_position(self, pos) -> float:
        if not self._grid_rect or not self._grid_rect.contains(pos):
            return self.view_start_hour + self.visible_hours * 0.5
        rel = (pos.y() - self._grid_rect.top()) / max(1.0, self._grid_rect.height())
        rel = max(0.0, min(1.0, rel))
        return self.view_start_hour + rel * self.visible_hours

    def _date_at_position(self, pos) -> datetime | None:
        if self.mode == self.MODE_MONTH:
            for rect, dt in self._month_cells:
                if rect.contains(pos):
                    return dt
        elif self.mode == self.MODE_WEEK:
            if self._grid_rect is not None:
                for rect, dt in self._week_day_rects:
                    hit_rect = QRectF(rect.left(), self._grid_rect.top(), rect.width(), self._grid_rect.height())
                    if hit_rect.contains(pos):
                        return dt
            for rect, dt in self._week_day_rects:
                if rect.contains(pos):
                    return dt
        else:
            if self._grid_rect is not None and self._grid_rect.contains(pos):
                return self.selected_date
            if self._week_day_rects:
                return self.selected_date
        return None

    def _proposal_from_position(self, pos, fallback_dt: datetime | None = None):
        dt = fallback_dt or self._date_at_position(pos) or self.selected_date
        hour = self._hour_at_position(pos)
        minute = int(round((hour - int(hour)) * 60.0))
        hour_int = int(hour)
        if minute >= 60:
            hour_int += 1
            minute = 0
        hour_int = max(0, min(23, hour_int))
        start_dt = start_of_day(dt).replace(hour=hour_int, minute=minute, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=1)
        if start_of_day(end_dt) != start_of_day(start_dt):
            end_dt = start_of_day(start_dt) + timedelta(hours=23, minutes=59)
        return start_dt, end_dt

    def _pill(self, painter: QPainter, rect: QRectF, text: str, color: QColor):
        if rect.height() < 10 or rect.width() < 18:
            return
        bg = QColor(color.red(), color.green(), color.blue(), 72)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor(36, 46, 64, 220))
        f = ui_font(self, 8, QFont.Bold)
        painter.setFont(f)
        painter.drawText(rect.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(18, 16, -18, -18)
        self._month_cells.clear()
        self._week_day_rects.clear()
        self._item_hits.clear()
        self._grid_rect = None

        p.setPen(TEXT)
        p.setFont(ui_font(self, 12, QFont.Bold))
        p.drawText(QRectF(r.left(), r.top(), r.width(), 24), Qt.AlignLeft | Qt.AlignVCenter, "Calendar")

        chip_w = 170 if self.mode == self.MODE_MONTH else 236
        title_rect = QRectF(r.left(), r.top() + 30, chip_w, 36)
        self._title_hit = title_rect
        p.setPen(QPen(QColor(255, 255, 255, 210), 1.0))
        p.setBrush(QColor(255, 255, 255, 112))
        p.drawRoundedRect(title_rect, 18, 18)
        p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 230))
        p.setFont(ui_font(self, 13, QFont.Bold))
        p.drawText(title_rect.adjusted(14, 0, -24, 0), Qt.AlignLeft | Qt.AlignVCenter, self.visible_title())
        p.setFont(ui_font(self, 10, QFont.Bold))
        p.drawText(title_rect.adjusted(title_rect.width() - 24, 0, -10, 0), Qt.AlignCenter, "▾")

        if self.mode == self.MODE_DAY:
            hint = "Click item: select · Double-click item: edit · Empty double-click: add plan"
        elif self.mode == self.MODE_WEEK:
            hint = "Click item: select · Double-click item: edit · Empty double-click: add plan"
        else:
            hint = "Click item: select · Double-click item: edit · Double-click date: open week"
        p.setPen(QColor(SUBTEXT.red(), SUBTEXT.green(), SUBTEXT.blue(), 165))
        p.setFont(ui_font(self, 9))
        p.drawText(QRectF(r.right() - 320, r.top() + 36, 320, 22), Qt.AlignRight | Qt.AlignVCenter, hint)

        content = QRectF(r.left(), r.top() + 78, r.width(), r.height() - 80)
        if self.mode == self.MODE_MONTH:
            self._paint_month(p, content)
        elif self.mode == self.MODE_WEEK:
            self._paint_week(p, content)
        else:
            self._paint_day(p, content)

    def _paint_month(self, p: QPainter, area: QRectF):
        headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header_h = 28
        cell_w = area.width() / 7.0
        cell_h = (area.height() - header_h) / 6.0

        for i, name in enumerate(headers):
            hr = QRectF(area.left() + i * cell_w, area.top(), cell_w, header_h)
            col = WEEKEND if i >= 5 else QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 215)
            p.setPen(col)
            p.setFont(ui_font(self, 10, QFont.Bold))
            p.drawText(hr, Qt.AlignCenter, name)

        first = month_start(self.selected_date)
        grid_start = first - timedelta(days=first.weekday())
        grid_end = grid_start + timedelta(days=41, hours=23, minutes=59)
        sessions = self._combined_items_in_range(grid_start, grid_end)
        by_day = {}
        for s in sessions:
            st = str_to_dt(s["start"])
            by_day.setdefault(start_of_day(st), []).append(s)

        for idx in range(42):
            dt = grid_start + timedelta(days=idx)
            row = idx // 7
            col = idx % 7
            rect = QRectF(area.left() + col * cell_w, area.top() + header_h + row * cell_h, cell_w, cell_h)
            self._month_cells.append((rect, dt))

            hovered = self.hovered_date and start_of_day(self.hovered_date) == dt
            is_selected = start_of_day(self.selected_date) == dt
            is_today = start_of_day(now_local()) == dt
            is_other = dt.month != self.selected_date.month

            if hovered:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 36))
                p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 14, 14)

            if is_selected:
                p.setPen(QPen(QColor(255, 255, 255, 240), 2.2))
                p.setBrush(QColor(255, 255, 255, 26))
                p.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 15, 15)
            elif is_today:
                p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect.adjusted(7, 7, -7, -7), 14, 14)

            num_col = QColor(175, 180, 194) if is_other else QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 212)
            if dt.weekday() >= 5 and not is_other:
                num_col = WEEKEND
            if is_selected:
                num_col = QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 235)
            p.setPen(num_col)
            pf = ui_font(self, 12, QFont.Bold if is_selected or is_today else QFont.Medium)
            p.setFont(pf)
            p.drawText(QRectF(rect.left() + 10, rect.top() + 8, rect.width() - 16, 20), Qt.AlignLeft | Qt.AlignTop, str(dt.day))

            day_items = by_day.get(dt, [])
            all_day_items = [s for s in day_items if self._is_all_day_item(s)]
            timed_items = [s for s in day_items if not self._is_all_day_item(s)]
            line_y = rect.top() + 34
            for s in all_day_items[:2]:
                pr = QRectF(rect.left() + 8, line_y, rect.width() - 16, 16)
                self._paint_all_day_chip(p, pr, s, compact=True)
                line_y += 18
            for s in timed_items[: max(0, 4 - min(2, len(all_day_items)))]:
                label = self._item_title_text(s)[:12]
                pr = QRectF(rect.left() + 8, line_y, rect.width() - 16, 16)
                if self._is_focused_item(s):
                    p.setPen(QPen(QColor(255, 255, 255, 235), 1.6))
                    p.setBrush(QColor(255, 255, 255, ga(self, 28)))
                    p.drawRoundedRect(pr.adjusted(-1, -1, 1, 1), 8, 8)
                self._pill(p, pr, label, color_for_category(s["category"]))
                hit = dict(s)
                hit["rect"] = QRectF(pr)
                hit["resizable"] = False
                self._item_hits.append(hit)
                line_y += 18

    def _paint_week(self, p: QPainter, area: QRectF):
        st = week_start(self.selected_date)
        ed = st + timedelta(days=6, hours=23, minutes=59)
        sessions = self._combined_items_in_range(st, ed)
        by_day = {}
        for s in sessions:
            d = start_of_day(str_to_dt(s["start"]))
            by_day.setdefault(d, []).append(s)

        head_h = 54
        all_day_h = 22
        hour_w = 72
        grid = QRectF(area.left(), area.top() + head_h + all_day_h, area.width(), area.height() - head_h - all_day_h)
        self._grid_rect = grid
        col_w = (grid.width() - hour_w) / 7.0

        for i in range(7):
            dt = st + timedelta(days=i)
            rect = QRectF(grid.left() + hour_w + i * col_w, area.top(), col_w, head_h)
            self._week_day_rects.append((rect, dt))
            if start_of_day(self.selected_date) == dt:
                p.setPen(QPen(QColor(255, 255, 255, 230), 2.0))
                p.setBrush(QColor(255, 255, 255, ga(self, 34)))
                p.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 14, 14)
            p.setPen(WEEKEND if i >= 5 else QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 220))
            p.setFont(ui_font(self, 10, QFont.Bold))
            p.drawText(QRectF(rect.left(), rect.top() + 6, rect.width(), 16), Qt.AlignCenter, dt.strftime("%a"))
            p.setFont(ui_font(self, 12, QFont.Bold if start_of_day(self.selected_date) == dt else QFont.Medium))
            p.drawText(QRectF(rect.left(), rect.top() + 24, rect.width(), 20), Qt.AlignCenter, dt.strftime("%m-%d"))

            all_day_items = [s for s in by_day.get(dt, []) if self._is_all_day_item(s)]
            if all_day_items:
                chip_rect = QRectF(grid.left() + hour_w + i * col_w + 6, area.top() + head_h + 2, col_w - 12, 16)
                self._paint_all_day_chip(p, chip_rect, all_day_items[0], compact=True)

        p.setPen(QPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 38), 1))
        for idx in range(int(self.visible_hours) + 1):
            hour = self.view_start_hour + idx
            y = grid.top() + (hour - self.view_start_hour) / max(0.0001, self.visible_hours) * grid.height()
            p.drawLine(int(grid.left() + hour_w), int(y), int(grid.right()), int(y))
            p.setPen(QColor(SUBTEXT.red(), SUBTEXT.green(), SUBTEXT.blue(), 180))
            p.setFont(ui_font(self, 10))
            p.drawText(QRectF(grid.left(), y - 8, hour_w - 10, 20), Qt.AlignRight | Qt.AlignVCenter, self._fmt_axis_time(hour))
            p.setPen(QPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 38), 1))
        for cc in range(8):
            x = grid.left() + hour_w + cc * col_w
            p.drawLine(int(x), int(grid.top()), int(x), int(grid.bottom()))

        view_end = self.view_start_hour + self.visible_hours
        for i in range(7):
            dt = st + timedelta(days=i)
            items = by_day.get(dt, [])
            for s in items:
                if self._is_all_day_item(s):
                    continue
                ss = str_to_dt(s["start"])
                ee = str_to_dt(s["end"])
                start_hour, end_hour = hours_in_day_span(ss, ee)
                if end_hour <= self.view_start_hour or start_hour >= view_end:
                    continue
                y1 = grid.top() + (max(self.view_start_hour, start_hour) - self.view_start_hour) / self.visible_hours * grid.height()
                y2 = grid.top() + (min(view_end, end_hour) - self.view_start_hour) / self.visible_hours * grid.height()
                if y2 < y1 + 20:
                    y2 = y1 + 20
                x = grid.left() + hour_w + i * col_w + 6
                rect = QRectF(x, y1 + 4, col_w - 12, max(18.0, y2 - y1 - 8))
                col = color_for_category(s["category"])
                focused = self._is_focused_item(s)
                if focused:
                    p.setPen(QPen(QColor(255, 255, 255, 235), 2.4))
                    p.setBrush(Qt.NoBrush)
                    p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 14, 14)
                if s.get("source") == "plan":
                    p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 220), 2.2 if focused else 1.3, Qt.DashLine))
                    p.setBrush(QColor(col.red(), col.green(), col.blue(), 58 if focused else 52))
                else:
                    p.setPen(QPen(QColor(255, 255, 255, 190 if focused else 145), 1.8 if focused else 1.0))
                    p.setBrush(QColor(col.red(), col.green(), col.blue(), 112 if focused else 98))
                p.drawRoundedRect(rect, 12, 12)
                show_detail = self._calendar_item_show_detail(rect, mode='week', include_category=False)
                p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 225))
                p.setFont(ui_font(self, 9, QFont.Bold))
                title_rect = rect.adjusted(8, 4, -8, -18) if show_detail else rect.adjusted(8, 4, -8, -6)
                p.drawText(title_rect, Qt.TextWordWrap, self._item_title_text(s)[:28])
                if show_detail:
                    p.setFont(ui_font(self, 8))
                    p.drawText(rect.adjusted(8, rect.height() - 18, -8, -4), Qt.AlignLeft | Qt.AlignBottom, self._calendar_item_detail_text(s))
                hit = dict(s)
                hit["rect"] = QRectF(rect)
                hit["resizable"] = True
                self._item_hits.append(hit)

        if self._duplicate_drag_rect is not None and self._duplicate_drag_hit is not None and self._duplicate_drag_start is not None and self._duplicate_drag_end is not None:
            col = color_for_category(self._duplicate_drag_hit.get("category", "Other"))
            rect = self._duplicate_drag_rect
            p.setPen(QPen(QColor(255, 255, 255, 235), 2.0, Qt.DashLine))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 42))
            p.drawRoundedRect(rect, 12, 12)
            show_detail = self._calendar_item_show_detail(rect, mode='week', include_category=False)
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 220))
            p.setFont(ui_font(self, 9, QFont.Bold))
            title_rect = rect.adjusted(8, 4, -8, -18) if show_detail else rect.adjusted(8, 4, -8, -6)
            p.drawText(title_rect, Qt.TextWordWrap, self._item_title_text(self._duplicate_drag_hit)[:28])
            if show_detail:
                p.setFont(ui_font(self, 8))
                p.drawText(rect.adjusted(8, rect.height() - 18, -8, -4), Qt.AlignLeft | Qt.AlignBottom, f"{self._duplicate_drag_start.strftime('%H:%M')}-{self._duplicate_drag_end.strftime('%H:%M')}")

        if self._resize_drag_rect is not None and self._resize_drag_hit is not None and self._resize_drag_start is not None and self._resize_drag_end is not None:
            col = color_for_category(self._resize_drag_hit.get("category", "Other"))
            rect = self._resize_drag_rect
            p.setPen(QPen(QColor(255, 255, 255, 240), 2.0, Qt.DashLine))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 52))
            p.drawRoundedRect(rect, 12, 12)
            show_detail = self._calendar_item_show_detail(rect, mode='week', include_category=False)
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 220))
            p.setFont(ui_font(self, 9, QFont.Bold))
            title_rect = rect.adjusted(8, 4, -8, -18) if show_detail else rect.adjusted(8, 4, -8, -6)
            p.drawText(title_rect, Qt.TextWordWrap, self._item_title_text(self._resize_drag_hit)[:28])
            if show_detail:
                p.setFont(ui_font(self, 8))
                p.drawText(rect.adjusted(8, rect.height() - 18, -8, -4), Qt.AlignLeft | Qt.AlignBottom, f"{self._resize_drag_start.strftime('%H:%M')}-{self._resize_drag_end.strftime('%H:%M')}")

    def _paint_day(self, p: QPainter, area: QRectF):
        d0 = start_of_day(self.selected_date)
        d1 = end_of_day(self.selected_date)
        sessions = self._combined_items_in_range(d0, d1)
        self._week_day_rects = [(area, self.selected_date)]

        header = QRectF(area.left(), area.top(), area.width(), 40)
        p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 230))
        p.setFont(ui_font(self, 13, QFont.Bold))
        p.drawText(header, Qt.AlignCenter, self.selected_date.strftime("%Y-%m-%d  %A"))

        all_day_h = 24
        grid = QRectF(area.left(), area.top() + 48 + all_day_h, area.width(), area.height() - 48 - all_day_h)
        self._grid_rect = grid
        label_w = 82
        content_x = grid.left() + label_w

        all_day_items = [s for s in sessions if self._is_all_day_item(s)]
        chip_x = content_x + 10
        chip_y = area.top() + 52
        for s in all_day_items[:3]:
            chip_rect = QRectF(chip_x, chip_y, min(220.0, area.width() - label_w - 24), 16)
            self._paint_all_day_chip(p, chip_rect, s, compact=False)
            chip_x += chip_rect.width() + 8

        p.setPen(QPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 36), 1))
        for idx in range(int(self.visible_hours) + 1):
            hour = self.view_start_hour + idx
            y = grid.top() + (hour - self.view_start_hour) / max(0.0001, self.visible_hours) * grid.height()
            if y < grid.top() - 20 or y > grid.bottom() + 20:
                continue
            p.drawLine(int(content_x), int(y), int(grid.right()), int(y))
            p.setPen(QColor(SUBTEXT.red(), SUBTEXT.green(), SUBTEXT.blue(), 180))
            p.setFont(ui_font(self, 11))
            p.drawText(QRectF(grid.left(), y - 10, label_w - 10, 24), Qt.AlignRight | Qt.AlignVCenter, self._fmt_axis_time(hour))
            p.setPen(QPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 36), 1))

        view_end = self.view_start_hour + self.visible_hours
        for s in sessions:
            if self._is_all_day_item(s):
                continue
            ss = str_to_dt(s["start"])
            ee = str_to_dt(s["end"])
            start_h, end_h = hours_in_day_span(ss, ee)
            if end_h <= self.view_start_hour or start_h >= view_end:
                continue
            y1 = grid.top() + (max(self.view_start_hour, start_h) - self.view_start_hour) / self.visible_hours * grid.height()
            y2 = grid.top() + (min(view_end, end_h) - self.view_start_hour) / self.visible_hours * grid.height()
            visible_h = max(4.0, y2 - y1)
            box_h = max(24.0, visible_h - 12)
            rect_y = y1 + 6
            if visible_h < 36:
                if end_h > view_end and start_h >= self.view_start_hour:
                    rect_y = y1 + 6
                elif start_h < self.view_start_hour and end_h <= view_end:
                    rect_y = y2 - box_h - 6
                else:
                    rect_y = y1 + max(2.0, (visible_h - box_h) * 0.5)
            rect = QRectF(content_x + 10, rect_y, grid.width() - label_w - 20, box_h)
            col = color_for_category(s["category"])
            focused = self._is_focused_item(s)
            if focused:
                p.setPen(QPen(QColor(255, 255, 255, 235), 2.4))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 14, 14)
            if s.get("source") == "plan":
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 220), 2.2 if focused else 1.4, Qt.DashLine))
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 56 if focused else 50))
            else:
                p.setPen(QPen(QColor(255, 255, 255, 190 if focused else 150), 1.8 if focused else 1.1))
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 108 if focused else 92))
            p.drawRoundedRect(rect, 12, 12)
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(rect.left() + 8, rect.top() + 8, 4, rect.height() - 16), 2, 2)
            show_detail = self._calendar_item_show_detail(rect, mode='day', include_category=True)
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 230))
            p.setFont(ui_font(self, 11, QFont.Bold))
            title_rect = rect.adjusted(18, 8, -10, -28) if show_detail else rect.adjusted(18, 8, -10, -10)
            p.drawText(title_rect, Qt.TextWordWrap, self._item_title_text(s))
            if show_detail:
                p.setFont(ui_font(self, 9))
                p.drawText(rect.adjusted(18, rect.height() - 24, -10, -8), Qt.AlignLeft | Qt.AlignBottom, self._calendar_item_detail_text(s, include_category=True))
            hit = dict(s)
            hit["rect"] = QRectF(rect)
            hit["resizable"] = True
            self._item_hits.append(hit)

        if self._resize_drag_rect is not None and self._resize_drag_hit is not None and self._resize_drag_start is not None and self._resize_drag_end is not None:
            col = color_for_category(self._resize_drag_hit.get("category", "Other"))
            rect = self._resize_drag_rect
            p.setPen(QPen(QColor(255, 255, 255, 240), 2.0, Qt.DashLine))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 52))
            p.drawRoundedRect(rect, 12, 12)
            show_detail = self._calendar_item_show_detail(rect, mode='day', include_category=True)
            p.setPen(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 220))
            p.setFont(ui_font(self, 11, QFont.Bold))
            title_rect = rect.adjusted(18, 8, -10, -28) if show_detail else rect.adjusted(18, 8, -10, -10)
            p.drawText(title_rect, Qt.TextWordWrap, self._item_title_text(self._resize_drag_hit))
            if show_detail:
                p.setFont(ui_font(self, 9))
                p.drawText(rect.adjusted(18, rect.height() - 24, -10, -8), Qt.AlignLeft | Qt.AlignBottom, f"{self._resize_drag_start.strftime('%H:%M')}-{self._resize_drag_end.strftime('%H:%M')}   {normalize_category(self._resize_drag_hit['category'])}")


# ---------------- task list ----------------
class TaskTableCard(LightGlassCard):
    def __init__(self, parent=None):
        super().__init__(radius=28, parent=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        self.title = QLabel("Task Details")
        self.title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800;")
        lay.addWidget(self.title)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Source", "ID", "Start", "End", "Duration", "Type", "Task"])
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(1, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setStyleSheet(
            '''
            QTableWidget{
                background:rgba(255,255,255,74);
                color:rgba(33,42,60,235);
                border:1px solid rgba(255,255,255,165);
                border-radius:14px;
                gridline-color:rgba(100,110,125,40);
                selection-background-color:rgba(176,182,192,118);
                selection-color:rgba(33,42,60,235);
            }
            QHeaderView::section{
                background:rgba(255,255,255,56);
                color:rgba(33,42,60,235);
                border:0;
                padding:6px;
                font-weight:800;
            }
            QTableWidget::item:selected{
                background:rgba(176,182,192,118);
                color:rgba(33,42,60,235);
            }
            '''
        )
        lay.addWidget(self.table, 1)


# ---------------- today task card ----------------
class TodayTaskCard(LightGlassCard):
    MODE_TODAY = "today"
    MODE_MONTH = "month"

    def __init__(self, parent=None):
        super().__init__(radius=28, parent=parent)
        self.view_mode = self.MODE_TODAY
        self.anchor_date = start_of_day(now_local())
        self.on_mode_changed = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self.title = QLabel("Today's Tasks")
        self.title.setStyleSheet("color:rgba(33,42,60,235); font-weight:800;")
        header_row.addWidget(self.title)
        header_row.addStretch(1)

        self.btn_today = QPushButton("Today")
        self.btn_month = QPushButton("Month")
        for btn in (self.btn_today, self.btn_month):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            header_row.addWidget(btn)
        lay.addLayout(header_row)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a today task…")
        self.input.setClearButtonEnabled(True)
        self.input.setStyleSheet(
            """
            QLineEdit{
                background:rgba(255,255,255,74);
                color:rgba(33,42,60,235);
                border:1px solid rgba(255,255,255,165);
                border-radius:14px;
                padding:8px 12px;
            }
            """
        )
        input_row.addWidget(self.input, 1)

        self.btn_add = QPushButton("Add")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(glass_button_style())
        input_row.addWidget(self.btn_add)

        lay.addLayout(input_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "", "Task"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setStyleSheet(
            """
            QTableWidget{
                background:rgba(255,255,255,74);
                color:rgba(33,42,60,235);
                border:1px solid rgba(255,255,255,165);
                border-radius:14px;
                selection-background-color:rgba(176,182,192,88);
                selection-color:rgba(33,42,60,235);
            }
            QTableWidget::item{
                border:none;
                padding:6px 4px;
            }
            QTableWidget::item:selected{
                background:rgba(176,182,192,88);
                color:rgba(33,42,60,235);
            }
            """
        )
        lay.addWidget(self.table, 1)

        self.btn_today.clicked.connect(lambda: self.set_view_mode(self.MODE_TODAY, emit=True))
        self.btn_month.clicked.connect(lambda: self.set_view_mode(self.MODE_MONTH, emit=True))
        self._sync_mode_controls()

    def _compact_button_style(self, active: bool = False) -> str:
        if active:
            bg0 = f"rgba({MINT.red()},{MINT.green()},{MINT.blue()},160)"
            bg1 = f"rgba({PURPLE.red()},{PURPLE.green()},{PURPLE.blue()},145)"
            border = "rgba(255,255,255,220)"
        else:
            bg0 = "rgba(255,255,255,126)"
            bg1 = "rgba(255,255,255,82)"
            border = "rgba(255,255,255,192)"
        return f"""
            QPushButton{{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {bg0}, stop:1 {bg1});
                color:rgba(28,38,55,235);
                border:1px solid {border};
                border-radius:10px;
                padding:0px 8px;
                font-size:9px;
                font-weight:800;
            }}
            QPushButton:hover{{border:1px solid rgba(255,255,255,232);}}
            QPushButton:pressed{{background:rgba(255,255,255,145);}}
        """

    def set_view_mode(self, mode: str, emit: bool = False):
        if mode not in (self.MODE_TODAY, self.MODE_MONTH):
            mode = self.MODE_TODAY
        self.view_mode = mode
        self._sync_mode_controls()
        if emit and self.on_mode_changed:
            self.on_mode_changed(self.view_mode)

    def _sync_mode_controls(self):
        self.btn_today.setStyleSheet(self._compact_button_style(active=(self.view_mode == self.MODE_TODAY)))
        self.btn_month.setStyleSheet(self._compact_button_style(active=(self.view_mode == self.MODE_MONTH)))
        if self.view_mode == self.MODE_MONTH:
            self.input.setPlaceholderText("Type a month task…")
        else:
            self.input.setPlaceholderText("Type a today task…")

    def set_tasks(self, day_dt: datetime, tasks, mode: str | None = None):
        if mode is not None:
            self.set_view_mode(mode, emit=False)
        self.anchor_date = start_of_day(day_dt)
        if self.view_mode == self.MODE_MONTH:
            self.title.setText(f"Month Tasks  ·  {self.anchor_date.strftime('%Y-%m')}")
        else:
            self.title.setText(f"Today's Tasks  ·  {day_key_from(self.anchor_date)}")
        self.table.setRowCount(0)
        for task in tasks or []:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 34)

            id_item = QTableWidgetItem(str(task["id"]))
            mark_item = QTableWidgetItem("●" if task.get("is_done") else "○")

            task_text = str(task.get("task_text", "")).strip()
            if self.view_mode == self.MODE_MONTH:
                prefix = str(task.get("task_date", ""))[5:10]
                task_text = f"[{prefix}] {task_text}" if prefix else task_text
            elif task.get("is_carryover"):
                prefix = str(task.get("task_date", ""))[5:10]
                task_text = f"↺ [{prefix}] {task_text}" if prefix else f"↺ {task_text}"
            text_item = QTableWidgetItem(task_text)

            mark_item.setTextAlignment(Qt.AlignCenter)
            for item in (id_item, mark_item, text_item):
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            mark_font = mark_item.font()
            mark_font.setBold(True)
            mark_item.setFont(mark_font)

            text_font = text_item.font()
            if task.get("is_done"):
                text_font.setStrikeOut(True)
                text_item.setFont(text_font)
                mark_item.setForeground(QColor(150, 156, 166))
                text_item.setForeground(QColor(150, 156, 166))
            elif task.get("is_carryover"):
                mark_item.setForeground(QColor(MINT.red(), MINT.green(), MINT.blue(), 225))
                text_item.setForeground(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 215))
            else:
                mark_item.setForeground(QColor(PURPLE.red(), PURPLE.green(), PURPLE.blue(), 220))
                text_item.setForeground(QColor(TEXT.red(), TEXT.green(), TEXT.blue(), 235))

            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, mark_item)
            self.table.setItem(row, 2, text_item)



# ---------------- main window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = TrackerDB(db_path())
        self.categories = self._load_categories()
        rebuild_category_colors(self.categories)
        self.selected_date = start_of_day(now_local())
        self.running: RunningSession | None = None
        self.window_locked = self.db.get_state("window_locked", "0") == "1"
        self.glass_opacity_scale = DEFAULT_GLASS_OPACITY_SCALE
        self._win_style_applied = False
        self._quitting = False
        self._start_hidden_to_tray = "--tray" in sys.argv
        self.range_stats_scope_mode = StatsWidget.SCOPE_MONTH
        self.today_task_date = start_of_day(now_local())
        self.today_task_mode = self.db.get_state("today_task_mode", TodayTaskCard.MODE_TODAY) or TodayTaskCard.MODE_TODAY
        self._today_task_day_key = day_key_from(self.today_task_date)
        self._undo_stack: list[list[dict]] = []

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        icon_path = app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self._load_theme_settings()
        self._set_initial_centered_geometry()
        self._build_ui()
        self._setup_tray()
        ensure_windows_autostart()
        self._apply_dynamic_scale()
        apply_rounded_window_mask(self, 34)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(200)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

        self.refresh_all()
    def send_to_back(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            HWND_BOTTOM = 1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_BOTTOM,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
        except Exception as e:
            print("[SEND_TO_BACK ERROR]", e)
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.send_to_back)
        QTimer.singleShot(80, self.send_to_back)
    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            QTimer.singleShot(0, self.send_to_back)
    def showEvent(self, e):
        super().showEvent(e)
        apply_rounded_window_mask(self, 34)

        if not self._win_style_applied:
            self._win_style_applied = True
            QTimer.singleShot(0, lambda: apply_windows_toolwindow_style(self))

        QTimer.singleShot(0, self.send_to_back)
        QTimer.singleShot(80, self.send_to_back)
        QTimer.singleShot(200, self.send_to_back)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_dynamic_scale()
        apply_rounded_window_mask(self, 34)

    def closeEvent(self, e):
        self._save_window_state()
        if getattr(self, "tray", None) is not None and self.tray.isVisible() and not self._quitting:
            self.hide()
            e.ignore()
            return
        try:
            self.db.close()
        except Exception:
            pass
        super().closeEvent(e)

    def _ensure_visible_on_screen(self):
        g = self.geometry()
        app = QApplication.instance()
        screen = app.screenAt(g.center()) if app is not None else None
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()
        min_w = min(900, max(320, avail.width()))
        min_h = min(600, max(240, avail.height()))
        w = min(max(g.width(), min_w), avail.width())
        h = min(max(g.height(), min_h), avail.height())

        x = g.x()
        y = g.y()
        if x + 80 > avail.right() or x + w - 80 < avail.x():
            x = avail.x() + (avail.width() - w) // 2
        if y + 80 > avail.bottom() or y + h - 80 < avail.y():
            y = avail.y() + (avail.height() - h) // 2

        x = max(avail.x(), min(x, avail.right() - w + 1))
        y = max(avail.y(), min(y, avail.bottom() - h + 1))
        self.setGeometry(x, y, w, h)

    def _set_initial_centered_geometry(self):
        saved = self.db.get_state("main_geometry", "")
        if saved:
            try:
                x, y, w, h = [int(v) for v in saved.split(",")]
                self.setGeometry(x, y, w, h)
                self._ensure_visible_on_screen()
                return
            except Exception:
                pass
        screen = QApplication.primaryScreen()
        if not screen:
            self.setGeometry(120, 80, 1450, 860)
            self._ensure_visible_on_screen()
            return
        avail = screen.availableGeometry()
        w = max(1280, int(avail.width() * 0.82))
        h = max(800, int(avail.height() * 0.82))
        w = min(w, int(avail.width() * 0.95))
        h = min(h, int(avail.height() * 0.93))
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self._ensure_visible_on_screen()

    def _load_categories(self):
        raw = self.db.get_state("categories", "")
        if raw:
            try:
                cats = json.loads(raw)
                if isinstance(cats, list) and cats:
                    return [str(x) for x in cats]
            except Exception:
                pass
        self.db.set_state("categories", json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False))
        return DEFAULT_CATEGORIES[:]

    def _load_theme_settings(self):
        global CURRENT_GLASS_OPACITY_SCALE
        scale_raw = self.db.get_state("glass_opacity_scale", f"{DEFAULT_GLASS_OPACITY_SCALE:.2f}")
        try:
            self.glass_opacity_scale = clamp_glass_opacity_scale(float(scale_raw))
        except Exception:
            self.glass_opacity_scale = DEFAULT_GLASS_OPACITY_SCALE
        CURRENT_GLASS_OPACITY_SCALE = self.glass_opacity_scale

        mint = parse_color(self.db.get_state("theme_color_a", color_to_hex(DEFAULT_MINT)), DEFAULT_MINT)
        purple = parse_color(self.db.get_state("theme_color_b", color_to_hex(DEFAULT_PURPLE)), DEFAULT_PURPLE)
        set_theme_colors(mint, purple, self.categories)

    def apply_theme_settings(self, glass_scale: float, mint: QColor, purple: QColor, persist: bool = True):
        global CURRENT_GLASS_OPACITY_SCALE
        self.glass_opacity_scale = clamp_glass_opacity_scale(glass_scale)
        CURRENT_GLASS_OPACITY_SCALE = self.glass_opacity_scale
        set_theme_colors(mint, purple, self.categories)
        if persist:
            self.db.set_state("glass_opacity_scale", f"{self.glass_opacity_scale:.3f}")
            self.db.set_state("theme_color_a", color_to_hex(MINT))
            self.db.set_state("theme_color_b", color_to_hex(PURPLE))
        self._refresh_theme_widgets()

    def apply_category_settings(self, categories, persist: bool = True):
        self.categories = normalize_categories(categories)
        rebuild_category_colors(self.categories)
        if persist:
            self.db.set_state("categories", json.dumps(self.categories, ensure_ascii=False))
        self.refresh_all()
        self._refresh_theme_widgets()

    def _refresh_theme_widgets(self):
        if hasattr(self, "title_bar"):
            self.title_bar.refresh_theme()
        if hasattr(self, "btn_month"):
            self._update_mode_buttons(self.calendar.mode)
        if hasattr(self, "timer") and getattr(self.timer, "btn", None) is not None:
            self.timer.btn.setStyleSheet(glass_button_style(active=self.timer.running))
        self.update()
        if hasattr(self, "calendar"):
            self.calendar.update()
        if hasattr(self, "stats"):
            self.stats.update()
        if hasattr(self, "task_card"):
            self.task_card.update()
        if hasattr(self, "today_task_card"):
            self.today_task_card.btn_add.setStyleSheet(glass_button_style())
            self.today_task_card._sync_mode_controls()
            self.today_task_card.update()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.move(self.geometry().center() - dlg.rect().center())
        dlg.exec()

    def ui_scale(self) -> float:
        w = max(900.0, float(self.width() or BASE_WIDTH))
        h = max(600.0, float(self.height() or BASE_HEIGHT))
        return max(0.72, min(1.45, min(w / BASE_WIDTH, h / BASE_HEIGHT)))

    def _save_window_state(self):
        g = self.geometry()
        self.db.set_state("main_geometry", f"{g.x()},{g.y()},{g.width()},{g.height()}")
        self.db.set_state("window_locked", "1" if self.window_locked else "0")

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = app_icon_path()
        self.tray.setIcon(QIcon(icon_path) if icon_path else self.windowIcon())
        menu = QMenu(self)
        act_show = menu.addAction("Show")
        act_hide = menu.addAction("Hide")
        menu.addSeparator()
        act_quit = menu.addAction("Quit")
        act_show.triggered.connect(self.show_from_tray)
        act_hide.triggered.connect(self.hide)
        act_quit.triggered.connect(self.quit_from_tray)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_from_tray()

    def show_from_tray(self):
        self._ensure_visible_on_screen()
        state = self.windowState()
        state = state & ~Qt.WindowMinimized
        self.setWindowState(state)
        self.showNormal()
        self.show()
        self.send_to_back()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self.raise_)
        QTimer.singleShot(0, self.activateWindow)

    def quit_from_tray(self):
        self._quitting = True
        self._save_window_state()
        self.hide()
        if getattr(self, "tray", None) is not None:
            self.tray.hide()
        self.close()
        QApplication.instance().quit()

    def _apply_dynamic_scale(self):
        if not hasattr(self, "title_bar"):
            return
        scale = self.ui_scale()
        base_font = ui_font(self, 10.5)
        if self.centralWidget() is not None:
            self.centralWidget().setFont(base_font)

        def apply_scaled_font(widget, fallback_size: float | None = None):
            if widget is None:
                return
            f = widget.font()
            base_pt = widget.property("_base_point_size")
            if base_pt is None:
                base_pt = f.pointSizeF() if f.pointSizeF() > 0 else (fallback_size or 10.5)
                widget.setProperty("_base_point_size", float(base_pt))
            f.setPointSizeF(max(1.0, float(base_pt) * scale))
            widget.setFont(f)

        self.title_bar.apply_scale()
        for btn in (self.btn_month, self.btn_week, self.btn_day):
            btn.setFixedHeight(sp(self, 34))
            apply_scaled_font(btn, 10.5)
        apply_scaled_font(self.timer.btn, 11)
        apply_scaled_font(self.task_card.title, 12)
        apply_scaled_font(self.task_card.table, 10)
        if hasattr(self, "today_task_card"):
            apply_scaled_font(self.today_task_card.title, 12)
            apply_scaled_font(self.today_task_card.input, 10.5)
            apply_scaled_font(self.today_task_card.btn_add, 10.5)
            apply_scaled_font(self.today_task_card.btn_today, 9.2)
            apply_scaled_font(self.today_task_card.btn_month, 9.2)
            self.today_task_card.btn_today.setFixedHeight(sp(self, 24))
            self.today_task_card.btn_month.setFixedHeight(sp(self, 24))
            apply_scaled_font(self.today_task_card.table, 10)
            self.today_task_card.table.verticalHeader().setDefaultSectionSize(sp(self, 34))
        apply_scaled_font(self.task_card.table.horizontalHeader(), 10)
        apply_scaled_font(self.task_card.table.verticalHeader(), 10)
        self.task_card.table.verticalHeader().setDefaultSectionSize(sp(self, 28))
        for btn, fallback in (
            (getattr(self.stats, "btn_summary_toggle", None), 8.2),
            (getattr(self.stats, "btn_day_scope", None), 7.8),
            (getattr(self.stats, "btn_week_scope", None), 7.8),
            (getattr(self.stats, "btn_month_scope", None), 7.8),
        ):
            if btn is not None:
                apply_scaled_font(btn, fallback)

        for widget, fallback in (
            (getattr(self.title_bar, "lbl", None), 17),
            (getattr(self.title_bar, "btn_settings", None), 9.6),
            (getattr(self.title_bar, "btn_pin", None), 8.8),
            (getattr(self.title_bar, "btn_close", None), 8.0),
        ):
            apply_scaled_font(widget, fallback)

        self.calendar.update()
        self.timer.update()
        self.stats.update()

    def is_window_locked(self) -> bool:
        return bool(self.window_locked)

    def set_window_locked(self, locked: bool):
        self.window_locked = bool(locked)
        self.db.set_state("window_locked", "1" if self.window_locked else "0")
        if hasattr(self, "title_bar"):
            self.title_bar.refresh_lock_button()

    def toggle_window_locked(self):
        self.set_window_locked(not self.window_locked)

    def _build_ui(self):
        bg = LightWallpaperBackground()
        self.setCentralWidget(bg)

        outer = QVBoxLayout(bg)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)
        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, 1)

        # left / calendar
        self.calendar = CalendarCanvas()
        self.calendar.set_sessions_callback(self._sessions_in_range)
        self.calendar.set_plans_callback(self._plans_in_range)
        self.calendar.on_selected_date_changed = self._on_calendar_selected_date_changed
        self.calendar.on_mode_changed = self._on_calendar_mode_changed
        self.calendar.on_edit_session = self.edit_session_by_id
        self.calendar.on_edit_plan = self.edit_plan_by_id
        self.calendar.on_add_plan_requested = self.add_planned_item
        self.calendar.on_pick_month_year = self.pick_calendar_month
        self.calendar.on_duplicate_item_requested = self.duplicate_calendar_item
        self.calendar.on_delete_item_requested = self.delete_calendar_item
        self.calendar.on_undo_requested = self.undo_last_delete
        self.calendar.on_resize_item_requested = self.resize_calendar_item

        left_wrap = QVBoxLayout()
        left_wrap.setContentsMargins(0, 0, 0, 0)
        left_wrap.setSpacing(0)

        self.left_card = self.calendar
        body.addWidget(self.left_card, 7)

        # right column
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(12)
        body.addLayout(right_col, 5)

        # toolbar buttons
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)
        self.btn_month = QPushButton("Month")
        self.btn_week = QPushButton("Week")
        self.btn_day = QPushButton("Day")
        for btn in (self.btn_month, self.btn_week, self.btn_day):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(34)
            ctrl_row.addWidget(btn)
        ctrl_row.addStretch(1)
        right_col.addLayout(ctrl_row)

        self.btn_month.clicked.connect(lambda: self.calendar.set_mode(CalendarCanvas.MODE_MONTH))
        self.btn_week.clicked.connect(lambda: self.calendar.set_mode(CalendarCanvas.MODE_WEEK))
        self.btn_day.clicked.connect(lambda: self.calendar.set_mode(CalendarCanvas.MODE_DAY))

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        right_col.addLayout(top_row, 3)

        self.timer = TimerWidget()
        self.timer.on_start = self.start_timer
        self.timer.on_stop = self.stop_timer
        top_row.addWidget(self.timer, 1)

        stats_col = QVBoxLayout()
        stats_col.setContentsMargins(0, 0, 0, 0)
        stats_col.setSpacing(12)
        top_row.addLayout(stats_col, 1)

        self.stats = StatsWidget()
        self.stats.set_summary_scope_mode(self.range_stats_scope_mode, emit=False)
        self.stats.on_summary_scope_changed = self._on_range_stats_scope_changed
        stats_col.addWidget(self.stats, 1)

        self.today_task_card = TodayTaskCard()
        right_col.addWidget(self.today_task_card, 2)

        self.task_card = TaskTableCard()
        right_col.addWidget(self.task_card, 2)

        self.today_task_card.set_view_mode(self.today_task_mode, emit=False)
        self.today_task_card.on_mode_changed = self._on_today_task_mode_changed
        self.today_task_card.btn_add.clicked.connect(self.add_today_task)
        self.today_task_card.input.returnPressed.connect(self.add_today_task)
        self.today_task_card.table.cellClicked.connect(self._on_today_task_cell_clicked)
        self.today_task_card.table.customContextMenuRequested.connect(self._on_today_task_menu)
        self.today_task_card.table.installEventFilter(self)

        self.task_card.table.customContextMenuRequested.connect(self._on_table_menu)
        self.task_card.table.cellClicked.connect(self._on_table_cell_clicked)
        self.task_card.table.cellDoubleClicked.connect(lambda r, c: self._edit_row(r))
        self.task_card.table.installEventFilter(self)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip = QSizeGrip(bg)
        grip.setFixedSize(18, 18)
        grip_row.addWidget(grip)
        outer.addLayout(grip_row)

        self._update_mode_buttons(self.calendar.mode)

    def _update_mode_buttons(self, mode: int):
        self.btn_month.setStyleSheet(glass_button_style(active=(mode == CalendarCanvas.MODE_MONTH)))
        self.btn_week.setStyleSheet(glass_button_style(active=(mode == CalendarCanvas.MODE_WEEK)))
        self.btn_day.setStyleSheet(glass_button_style(active=(mode == CalendarCanvas.MODE_DAY)))

    def _on_calendar_mode_changed(self, mode: int):
        self._update_mode_buttons(mode)

    def _on_calendar_selected_date_changed(self, dt: datetime):
        self.selected_date = start_of_day(dt)
        self.refresh_all()

    def _sessions_in_range(self, start_dt: datetime, end_dt: datetime):
        return self.db.get_sessions_in_range(start_dt, end_dt)

    def _sessions_for_selected_day(self):
        return self.db.get_sessions_in_range(start_of_day(self.selected_date), end_of_day(self.selected_date))

    def _plans_in_range(self, start_dt: datetime, end_dt: datetime):
        return self.db.get_plans_in_range(start_dt, end_dt)

    def _items_for_selected_day(self):
        day_start = start_of_day(self.selected_date)
        day_end = end_of_day(self.selected_date)
        items = []
        for s in self._sessions_for_selected_day():
            x = dict(s)
            x["source"] = "session"
            x = clamp_item_to_range(x, day_start, day_end)
            if x is not None:
                items.append(x)
        for s in self._plans_in_range(day_start, day_end):
            x = dict(s)
            x["source"] = "plan"
            x = clamp_item_to_range(x, day_start, day_end)
            if x is not None:
                items.append(x)
        items.sort(key=lambda item: item.get("start", ""))
        return items

    def _items_in_range(self, range_start: datetime, range_end: datetime):
        items = []
        for s in self._sessions_in_range(range_start, range_end):
            x = dict(s)
            x["source"] = "session"
            x = clamp_item_to_range(x, range_start, range_end)
            if x is not None:
                items.append(x)
        for s in self._plans_in_range(range_start, range_end):
            x = dict(s)
            x["source"] = "plan"
            x = clamp_item_to_range(x, range_start, range_end)
            if x is not None:
                items.append(x)
        items.sort(key=lambda item: item.get("start", ""))
        return items

    def _scope_range(self, scope_mode: str) -> tuple[datetime, datetime]:
        if scope_mode == StatsWidget.SCOPE_DAY:
            return start_of_day(self.selected_date), end_of_day(self.selected_date)
        if scope_mode == StatsWidget.SCOPE_WEEK:
            st = week_start(self.selected_date)
            return st, st + timedelta(days=6, hours=23, minutes=59, seconds=59)
        st = month_start(self.selected_date)
        return st, add_months(st, 1) - timedelta(seconds=1)

    def _refresh_range_stats(self):
        if not hasattr(self, "stats"):
            return
        range_start, range_end = self._scope_range(self.range_stats_scope_mode)
        scope_items = self._items_in_range(range_start, range_end)
        self.stats.set_summary_items(self.selected_date, scope_items)

    def _on_range_stats_scope_changed(self, mode: str):
        self.range_stats_scope_mode = mode
        self._refresh_range_stats()

    def _on_today_task_mode_changed(self, mode: str):
        self.today_task_mode = mode if mode in (TodayTaskCard.MODE_TODAY, TodayTaskCard.MODE_MONTH) else TodayTaskCard.MODE_TODAY
        self.db.set_state("today_task_mode", self.today_task_mode)
        self.refresh_all()

    def _today_task_items(self):
        self.today_task_date = start_of_day(now_local())
        self.db.purge_expired_completed_daily_todos(self.today_task_date)
        if self.today_task_mode == TodayTaskCard.MODE_MONTH:
            return self.db.get_month_todos_for_display(self.today_task_date)
        return self.db.get_daily_todos_for_display(self.today_task_date)

    def add_today_task(self):
        if not hasattr(self, "today_task_card"):
            return
        text_value = self.today_task_card.input.text().strip()
        if not text_value:
            return
        anchor = start_of_day(now_local())
        if self.today_task_mode == TodayTaskCard.MODE_MONTH:
            self.db.add_month_todo(anchor, text_value)
        else:
            self.db.add_daily_todo(anchor, text_value)
        self.today_task_card.input.clear()
        self.refresh_all()

    def _toggle_today_task_by_row(self, row: int):
        if row < 0 or not hasattr(self, "today_task_card"):
            return
        item = self.today_task_card.table.item(row, 0)
        if item is None:
            return
        todo_id = int(item.text())
        if self.today_task_mode == TodayTaskCard.MODE_MONTH:
            self.db.toggle_month_todo_done(todo_id)
        else:
            self.db.toggle_daily_todo_done(todo_id)
        self.refresh_all()

    def _selected_today_task_ids(self) -> list[int]:
        table = self.today_task_card.table
        rows = sorted({idx.row() for idx in table.selectionModel().selectedRows()})
        out = []
        for row in rows:
            item = table.item(row, 0)
            if item is not None:
                out.append(int(item.text()))
        return out

    def _today_task_row_data(self, row: int):
        if row < 0 or not hasattr(self, "today_task_card"):
            return None
        table = self.today_task_card.table
        id_item = table.item(row, 0)
        text_item = table.item(row, 2)
        if id_item is None or text_item is None:
            return None
        return {
            "id": int(id_item.text()),
            "task_text": text_item.text(),
        }

    def edit_selected_today_task(self):
        if not hasattr(self, "today_task_card"):
            return
        row = self.today_task_card.table.currentRow()
        if row < 0:
            selected = self.today_task_card.table.selectionModel().selectedRows()
            if selected:
                row = selected[0].row()
        self._edit_today_task_by_row(row)

    def _edit_today_task_by_row(self, row: int):
        task = self._today_task_row_data(row)
        if not task:
            return
        value, ok = QInputDialog.getText(
            self,
            "Edit Task",
            "Task text:",
            text=str(task.get("task_text", "")),
        )
        if not ok:
            return
        new_text = str(value or "").strip()
        if not new_text:
            QMessageBox.information(self, "Task text required", "Task text cannot be empty.")
            return
        if self.today_task_mode == TodayTaskCard.MODE_MONTH:
            self.db.update_month_todo(int(task["id"]), new_text)
        else:
            self.db.update_daily_todo(int(task["id"]), new_text)
        self.refresh_all()
        table = self.today_task_card.table
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item is not None and int(item.text()) == int(task["id"]):
                table.selectRow(r)
                break

    def _delete_today_task_ids(self, todo_ids: list[int]):
        if not todo_ids:
            return
        for todo_id in todo_ids:
            if self.today_task_mode == TodayTaskCard.MODE_MONTH:
                self.db.delete_month_todo(int(todo_id))
            else:
                self.db.delete_daily_todo(int(todo_id))
        self.refresh_all()

    def _on_today_task_cell_clicked(self, row: int, col: int):
        self._toggle_today_task_by_row(row)

    def _on_today_task_menu(self, pos):
        table = self.today_task_card.table
        row = table.rowAt(pos.y())
        if row >= 0 and row not in {idx.row() for idx in table.selectionModel().selectedRows()}:
            table.clearSelection()
            table.selectRow(row)
        todo_ids = self._selected_today_task_ids()
        if not todo_ids:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("Edit")
        act_toggle = menu.addAction("Toggle Done")
        act_delete = menu.addAction("Delete")
        action = menu.exec(table.mapToGlobal(pos))
        if action == act_edit:
            self._edit_today_task_by_row(table.currentRow())
        elif action == act_toggle:
            self._toggle_today_task_by_row(table.currentRow())
        elif action == act_delete:
            self._delete_today_task_ids(todo_ids)

    def start_timer(self):
        if self.running:
            return
        self.running = RunningSession(start_dt=now_local(), start_monotonic=time.monotonic())
        self.timer.set_running(True)

    def stop_timer(self):
        if not self.running:
            return
        start_dt = self.running.start_dt
        end_dt = now_local()
        self.running = None
        self.timer.set_running(False)

        dlg = TaskDialog(self, start_dt, end_dt, self.categories, title="Log Task")
        dlg.move(self.geometry().center() - dlg.rect().center())
        if dlg.exec() == QDialog.Accepted:
            self.db.add_session(start_dt, end_dt, dlg.category(), dlg.task_text())
            self.selected_date = start_of_day(start_dt)
            self.calendar.set_selected_date(self.selected_date)
            self.refresh_all()

    def add_planned_item(self, start_dt: datetime | None = None, end_dt: datetime | None = None):
        base = start_of_day(self.selected_date)
        start_dt = start_dt or base.replace(hour=9, minute=0)
        end_dt = end_dt or (start_dt + timedelta(hours=1))
        dlg = PlanDialog(self, start_dt, end_dt, self.categories, title="Add Planned Task")
        dlg.move(self.geometry().center() - dlg.rect().center())
        if dlg.exec() == QDialog.Accepted:
            self.db.add_plan(dlg.start_datetime(), dlg.end_datetime(), dlg.category(), dlg.task_text(), dlg.recurrence(), dlg.is_all_day(), dlg.recurrence_range_start(), dlg.recurrence_range_end())
            self.selected_date = start_of_day(dlg.start_datetime())
            self.calendar.set_selected_date(self.selected_date)
            self.refresh_all()


    def _split_recurring_plan_from_occurrence(self, pid: int, occurrence_day: str, new_start: datetime, new_end: datetime, category: str, task_text: str, recurrence: str, is_all_day: bool, recurrence_range_end: str):
        original = self.db.get_plan_by_id(pid)
        if not original:
            return
        prev_day = previous_day_text(occurrence_day)
        if prev_day:
            self.db.update_plan(
                pid,
                str_to_dt(original['start']),
                str_to_dt(original['end']),
                normalize_category(original.get('category', DEFAULT_CATEGORIES[0])),
                normalize_task_text(original.get('task_text', '')),
                original.get('recurrence', 'none'),
                bool(original.get('is_all_day', False)),
                original.get('recurrence_range_start', ''),
                prev_day,
            )
        self.db.add_plan(new_start, new_end, category, task_text, recurrence, is_all_day, occurrence_day, recurrence_range_end)

    def _delete_recurring_plan_from_occurrence(self, pid: int, occurrence_day: str):
        original = self.db.get_plan_by_id(pid)
        if not original:
            return
        series_start = str(original.get('recurrence_range_start', '') or '')
        try:
            base_start_day = str_to_dt(original['start']).strftime('%Y-%m-%d')
        except Exception:
            base_start_day = ''
        if same_day_text(occurrence_day, series_start or base_start_day):
            self.db.delete_plan(pid)
            return
        prev_day = previous_day_text(occurrence_day)
        if not prev_day:
            self.db.delete_plan(pid)
            return
        self.db.update_plan(
            pid,
            str_to_dt(original['start']),
            str_to_dt(original['end']),
            normalize_category(original.get('category', DEFAULT_CATEGORIES[0])),
            normalize_task_text(original.get('task_text', '')),
            original.get('recurrence', 'none'),
            bool(original.get('is_all_day', False)),
            original.get('recurrence_range_start', ''),
            prev_day,
        )

    def _replace_recurring_occurrence_with_single_override(self, pid: int, occurrence_day: str, new_start: datetime, new_end: datetime, category: str, task_text: str):
        original = self.db.get_plan_by_id(pid)
        if not original:
            return None
        recurrence = str(original.get('recurrence', 'none') or 'none').strip().lower()
        if recurrence in {'', 'none'}:
            self.db.update_plan(pid, new_start, new_end, category, task_text, 'none', bool(original.get('is_all_day', False)), '', '')
            return int(pid)

        try:
            occ_day_dt = datetime.strptime(str(occurrence_day), '%Y-%m-%d')
        except Exception:
            self.db.update_plan(pid, new_start, new_end, category, task_text, 'none', bool(original.get('is_all_day', False)), '', '')
            return int(pid)

        series_start_raw = str(original.get('recurrence_range_start', '') or '').strip()
        series_end_raw = str(original.get('recurrence_range_end', '') or '').strip()
        try:
            series_start_dt = datetime.strptime(series_start_raw, '%Y-%m-%d') if series_start_raw else start_of_day(str_to_dt(original['start']))
        except Exception:
            series_start_dt = start_of_day(str_to_dt(original['start']))
        try:
            series_end_dt = datetime.strptime(series_end_raw, '%Y-%m-%d') if series_end_raw else series_start_dt
        except Exception:
            series_end_dt = series_start_dt

        before_end_dt = occ_day_dt - timedelta(days=1)
        after_start_dt = occ_day_dt + timedelta(days=1)

        if before_end_dt >= series_start_dt:
            self.db.update_plan(
                pid,
                str_to_dt(original['start']),
                str_to_dt(original['end']),
                normalize_category(original.get('category', DEFAULT_CATEGORIES[0])),
                normalize_task_text(original.get('task_text', '')),
                recurrence,
                bool(original.get('is_all_day', False)),
                series_start_dt.strftime('%Y-%m-%d'),
                before_end_dt.strftime('%Y-%m-%d'),
            )
        else:
            self.db.delete_plan(pid)

        if after_start_dt <= series_end_dt:
            self.db.add_plan(
                str_to_dt(original['start']),
                str_to_dt(original['end']),
                normalize_category(original.get('category', DEFAULT_CATEGORIES[0])),
                normalize_task_text(original.get('task_text', '')),
                recurrence,
                bool(original.get('is_all_day', False)),
                after_start_dt.strftime('%Y-%m-%d'),
                series_end_dt.strftime('%Y-%m-%d'),
            )

        return int(self.db.add_plan(new_start, new_end, category, task_text, 'none', False, '', ''))

    def edit_plan_by_id(self, pid: int, occurrence_start_text: str = ""):
        sess = self.db.get_plan_by_id(pid)
        if not sess:
            return
        start_dt = str_to_dt(sess["start"])
        end_dt = str_to_dt(sess["end"])
        recurrence = str(sess.get("recurrence", "none") or "none").strip().lower()
        occurrence_start_dt = None
        if occurrence_start_text:
            try:
                occurrence_start_dt = str_to_dt(str(occurrence_start_text))
            except Exception:
                occurrence_start_dt = None
        if occurrence_start_dt is None:
            occurrence_start_dt = start_dt
        occurrence_day = start_of_day(occurrence_start_dt).strftime('%Y-%m-%d')
        is_following_edit = recurrence != 'none' and occurrence_day != start_of_day(start_dt).strftime('%Y-%m-%d')
        dialog_start = occurrence_start_dt
        dialog_end = occurrence_start_dt + (end_dt - start_dt)
        delete_label = "Delete This & Following" if recurrence != 'none' else "Delete"
        dlg = PlanDialog(
            self,
            dialog_start,
            dialog_end,
            self.categories,
            preset_cat=normalize_category(sess["category"]),
            preset_task=normalize_task_text(sess["task_text"]),
            title=f"Edit Planned Task (ID {pid})",
            preset_recurrence=sess.get("recurrence", "none"),
            preset_all_day=bool(sess.get("is_all_day", False)),
            preset_recurrence_range_start=(occurrence_day if is_following_edit else sess.get("recurrence_range_start", "")),
            preset_recurrence_range_end=sess.get("recurrence_range_end", ""),
            allow_delete=True,
            delete_label=delete_label,
        )
        dlg.move(self.geometry().center() - dlg.rect().center())
        if dlg.exec() != QDialog.Accepted:
            return

        if dlg.delete_requested:
            if recurrence != 'none' and is_following_edit:
                if QMessageBox.question(self, "Delete Recurring Events", "Delete this occurrence and all following occurrences?") == QMessageBox.Yes:
                    self._delete_recurring_plan_from_occurrence(pid, occurrence_day)
            else:
                if QMessageBox.question(self, "Delete Planned Task", "Delete this planned task?") == QMessageBox.Yes:
                    self.db.delete_plan(pid)
            self.calendar.set_focus_item(None, None)
            self.refresh_all()
            return

        new_start = dlg.start_datetime()
        new_end = dlg.end_datetime()
        if recurrence != 'none' and is_following_edit:
            choice = QMessageBox(self)
            choice.setWindowTitle("Recurring Event")
            choice.setText("Apply this change to the whole series, or from this occurrence forward?")
            whole_btn = choice.addButton("Whole Series", QMessageBox.AcceptRole)
            following_btn = choice.addButton("This & Following", QMessageBox.ActionRole)
            cancel_btn = choice.addButton(QMessageBox.Cancel)
            choice.exec()
            clicked = choice.clickedButton()
            if clicked == cancel_btn or clicked is None:
                return
            if clicked == following_btn:
                self._split_recurring_plan_from_occurrence(
                    pid,
                    occurrence_day,
                    new_start,
                    new_end,
                    dlg.category(),
                    dlg.task_text(),
                    dlg.recurrence(),
                    dlg.is_all_day(),
                    dlg.recurrence_range_end(),
                )
            else:
                self.db.update_plan(pid, new_start, new_end, dlg.category(), dlg.task_text(), dlg.recurrence(), dlg.is_all_day(), dlg.recurrence_range_start(), dlg.recurrence_range_end())
        else:
            self.db.update_plan(pid, new_start, new_end, dlg.category(), dlg.task_text(), dlg.recurrence(), dlg.is_all_day(), dlg.recurrence_range_start(), dlg.recurrence_range_end())
        self.selected_date = start_of_day(new_start)
        self.calendar.set_selected_date(self.selected_date)
        self.refresh_all()

    def _tick(self):
        if self.running:
            self.timer.set_elapsed(int(time.monotonic() - self.running.start_monotonic))
        else:
            self.timer.set_elapsed(0)

        current_day_key = day_key_from(now_local())
        if current_day_key != self._today_task_day_key:
            self._today_task_day_key = current_day_key
            self.db.purge_expired_completed_daily_todos(start_of_day(now_local()))
            self.refresh_all()

    def refresh_table(self, sessions):
        table = self.task_card.table
        table.setRowCount(0)
        for s in sessions:
            st = str_to_dt(s["start"]).strftime("%H:%M")
            en = str_to_dt(s["end"]).strftime("%H:%M")
            source = str(s.get("source", "session"))
            type_text = normalize_category(s["category"])
            values = [source, s["id"], st, en, fmt_hms(s["duration_sec"]), type_text, normalize_task_text(s["task_text"])]
            row = table.rowCount()
            table.insertRow(row)
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 5:
                    c = color_for_category(str(s["category"]))
                    item.setBackground(QColor(c.red(), c.green(), c.blue(), 62 if source == "plan" else 88))
                table.setItem(row, col, item)

    def _edit_row(self, row: int):
        source_item = self.task_card.table.item(row, 0)
        sid_item = self.task_card.table.item(row, 1)
        if source_item and sid_item:
            if source_item.text() == "plan":
                self.edit_plan_by_id(int(sid_item.text()))
            else:
                self.edit_session_by_id(int(sid_item.text()))

    def _focus_row_in_calendar(self, row: int):
        table = self.task_card.table
        source_item = table.item(row, 0)
        sid_item = table.item(row, 1)
        start_item = table.item(row, 2)
        if not source_item or not sid_item or not start_item:
            return
        try:
            # Hidden row source/id are authoritative; selected day already scopes the date.
            refs = self._items_for_selected_day()
            source = source_item.text()
            sid = int(sid_item.text())
            target = next((x for x in refs if str(x.get("source", "session")) == source and int(x.get("id", -1)) == sid), None)
            if target:
                self.selected_date = start_of_day(str_to_dt(target["start"]))
                self.calendar.set_selected_date(self.selected_date)
                self.calendar.set_focus_item(source, sid)
                self.calendar.update()
        except Exception:
            pass

    def _on_table_cell_clicked(self, row: int, col: int):
        if col == 6:
            self._focus_row_in_calendar(row)

    def _selected_row_refs(self) -> list[tuple[str, int]]:
        table = self.task_card.table
        rows = sorted({idx.row() for idx in table.selectionModel().selectedRows()})
        refs = []
        for row in rows:
            source_item = table.item(row, 0)
            id_item = table.item(row, 1)
            if source_item and id_item:
                refs.append((source_item.text(), int(id_item.text())))
        return refs

    def _snapshot_refs_for_undo(self, refs: list[tuple[str, int]]) -> list[dict]:
        snapshots: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for source, rid in refs:
            key = (str(source), int(rid))
            if key in seen:
                continue
            seen.add(key)
            if source == "plan":
                record = self.db.get_plan_by_id(int(rid))
            else:
                record = self.db.get_session_by_id(int(rid))
            if not record:
                continue
            snapshots.append(
                {
                    "source": "plan" if source == "plan" else "session",
                    "start": record["start"],
                    "end": record["end"],
                    "category": normalize_category(record.get("category", DEFAULT_CATEGORIES[0])),
                    "task_text": normalize_task_text(record.get("task_text", "")),
                    "recurrence": record.get("recurrence", "none"),
                    "is_all_day": bool(record.get("is_all_day", False)),
                    "recurrence_range_start": record.get("recurrence_range_start", ""),
                    "recurrence_range_end": record.get("recurrence_range_end", ""),
                }
            )
        return snapshots

    def _push_deleted_items_undo(self, snapshots: list[dict]):
        clean = [dict(item) for item in snapshots if item]
        if not clean:
            return
        self._undo_stack.append(clean)
        if len(self._undo_stack) > 30:
            self._undo_stack = self._undo_stack[-30:]

    def undo_last_delete(self):
        if not self._undo_stack:
            return
        snapshots = self._undo_stack.pop()
        last_ref = None
        for item in snapshots:
            try:
                start_dt = str_to_dt(item["start"])
                end_dt = str_to_dt(item["end"])
            except Exception:
                continue
            category = normalize_category(item.get("category", DEFAULT_CATEGORIES[0]))
            task_text = normalize_task_text(item.get("task_text", ""))
            if item.get("source") == "plan":
                new_id = self.db.add_plan(start_dt, end_dt, category, task_text, item.get("recurrence", "none"), bool(item.get("is_all_day", False)), item.get("recurrence_range_start", ""), item.get("recurrence_range_end", ""))
                last_ref = ("plan", new_id)
            else:
                new_id = self.db.add_session(start_dt, end_dt, category, task_text)
                last_ref = ("session", new_id)
        if last_ref is not None:
            self.selected_date = start_of_day(str_to_dt(snapshots[-1]["start"]))
            self.calendar.set_selected_date(self.selected_date)
            self.calendar.set_focus_item(last_ref[0], last_ref[1])
        self.refresh_all()

    def _delete_selected_refs(self, refs: list[tuple[str, int]]):
        if not refs:
            return
        label = "item" if len(refs) == 1 else "items"
        if QMessageBox.question(self, "Confirm Delete", f"Delete {len(refs)} selected {label}?") != QMessageBox.Yes:
            return
        snapshots = self._snapshot_refs_for_undo(refs)
        for source, rid in refs:
            if source == "plan":
                self.db.delete_plan(rid)
            else:
                self.db.delete_session(rid)
        self._push_deleted_items_undo(snapshots)
        self.refresh_all()

    def _on_table_menu(self, pos):
        table = self.task_card.table
        row = table.rowAt(pos.y())
        selected_rows = {idx.row() for idx in table.selectionModel().selectedRows()}
        if row >= 0 and row not in selected_rows:
            table.clearSelection()
            table.selectRow(row)

        selected_refs = self._selected_row_refs()
        if not selected_refs:
            return

        menu = QMenu(self)
        act_edit = menu.addAction("Edit")
        if len(selected_refs) != 1:
            act_edit.setEnabled(False)
        act_del = menu.addAction("Delete Selected" if len(selected_refs) > 1 else "Delete")
        action = menu.exec(table.mapToGlobal(pos))
        if action == act_edit and len(selected_refs) == 1:
            source, rid = selected_refs[0]
            if source == "plan":
                self.edit_plan_by_id(rid)
            else:
                self.edit_session_by_id(rid)
        elif action == act_del:
            self._delete_selected_refs(selected_refs)

    def request_delete_selected(self):
        self._delete_selected_refs(self._selected_row_refs())

    def eventFilter(self, obj, event):
        if obj is self.task_card.table and event.type() == QEvent.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Z:
                self.undo_last_delete()
                return True
            if event.key() == Qt.Key_Delete:
                self.request_delete_selected()
                return True
        if hasattr(self, "today_task_card") and obj is self.today_task_card.table and event.type() == QEvent.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Z:
                self.undo_last_delete()
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
                self._toggle_today_task_by_row(self.today_task_card.table.currentRow())
                return True
            if event.key() == Qt.Key_F2:
                self.edit_selected_today_task()
                return True
            if event.key() == Qt.Key_Delete:
                self._delete_today_task_ids(self._selected_today_task_ids())
                return True
        return super().eventFilter(obj, event)

    def pick_calendar_month(self, current_dt: datetime):
        dlg = DateJumpDialog(self, current_dt)
        dlg.move(self.geometry().center() - dlg.rect().center())
        if dlg.exec() == QDialog.Accepted:
            picked = dlg.selected_datetime()
            self.selected_date = start_of_day(picked)
            self.calendar.set_selected_date(self.selected_date)
            self.refresh_all()

    def edit_session_by_id(self, sid: int):
        sess = self.db.get_session_by_id(sid)
        if not sess:
            return
        start_dt = str_to_dt(sess["start"])
        end_dt = str_to_dt(sess["end"])
        dlg = PlanDialog(
            self,
            start_dt,
            end_dt,
            self.categories,
            preset_cat=normalize_category(sess["category"]),
            preset_task=normalize_task_text(sess["task_text"]),
            title=f"Edit Task (ID {sid})",
            preset_recurrence="none",
            preset_all_day=is_all_day_span(start_dt, end_dt),
        )
        dlg.move(self.geometry().center() - dlg.rect().center())
        if dlg.exec() == QDialog.Accepted:
            new_start = dlg.start_datetime()
            new_end = dlg.end_datetime()
            self.db.update_session(sid, new_start, new_end, dlg.category(), dlg.task_text())
            self.selected_date = start_of_day(new_start)
            self.calendar.set_selected_date(self.selected_date)
            self.calendar.set_focus_item("session", sid)
            self.refresh_all()

    def resize_calendar_item(self, item: dict, start_dt: datetime, end_dt: datetime):
        if end_dt <= start_dt:
            return None
        source = str(item.get("source", "session"))
        rid = int(item.get("id", -1))
        if rid < 0:
            return None
        if source == "plan":
            original = self.db.get_plan_by_id(rid)
        else:
            original = self.db.get_session_by_id(rid)
        if not original:
            return None
        category = normalize_category(original.get("category", DEFAULT_CATEGORIES[0]))
        task_text = normalize_task_text(original.get("task_text", ""))
        focus_source = source
        focus_id = rid
        if source == "plan":
            recurrence = str(original.get("recurrence", "none") or "none").strip().lower()
            occurrence_day = str(item.get("occurrence_day", "") or "").strip()
            if recurrence not in {"", "none"} and occurrence_day:
                focus_id = self._replace_recurring_occurrence_with_single_override(rid, occurrence_day, start_dt, end_dt, category, task_text)
            else:
                self.db.update_plan(rid, start_dt, end_dt, category, task_text, original.get("recurrence", "none"), bool(original.get("is_all_day", False)), original.get("recurrence_range_start", ""), original.get("recurrence_range_end", ""))
        else:
            self.db.update_session(rid, start_dt, end_dt, category, task_text)
        self.selected_date = start_of_day(start_dt)
        self.calendar.set_selected_date(self.selected_date)
        self.calendar.set_focus_item(focus_source, focus_id)
        self.refresh_all()
        return (focus_source, focus_id)

    def duplicate_calendar_item(self, item: dict, start_dt: datetime, end_dt: datetime):
        if end_dt <= start_dt:
            return None
        source = str(item.get("source", "plan"))
        category = normalize_category(item.get("category", DEFAULT_CATEGORIES[0]))
        task_text = normalize_task_text(item.get("task_text", ""))
        if source == "session":
            new_id = self.db.add_session(start_dt, end_dt, category, task_text)
        else:
            new_id = self.db.add_plan(start_dt, end_dt, category, task_text, item.get("recurrence", "none"), bool(item.get("is_all_day", False)))
        self.selected_date = start_of_day(start_dt)
        self.calendar.set_selected_date(self.selected_date)
        self.calendar.set_focus_item(source, new_id)
        self.refresh_all()
        return (source, new_id)

    def delete_calendar_item(self, source: str, rid: int):
        snapshots = self._snapshot_refs_for_undo([(source, int(rid))])
        if source == "plan":
            self.db.delete_plan(int(rid))
        else:
            self.db.delete_session(int(rid))
        self._push_deleted_items_undo(snapshots)
        self.calendar.set_focus_item(None, None)
        self.refresh_all()

    def keyPressEvent(self, e):
        if (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_Z:
            self.undo_last_delete()
            e.accept()
            return
        super().keyPressEvent(e)

    def refresh_all(self):
        items = self._items_for_selected_day()
        self.refresh_table(items)
        self.stats.set_day_items(self.selected_date, items)
        self._refresh_range_stats()
        if hasattr(self, "today_task_card"):
            self.today_task_card.set_tasks(start_of_day(now_local()), self._today_task_items(), mode=self.today_task_mode)
        self.calendar.update()
        self.task_card.title.setText(f"Task Details  ·  {self.selected_date.strftime('%Y-%m-%d')}")
        self._apply_dynamic_scale()


def main():
    if not ensure_single_instance():
        return
    hide_windows_console()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon_path = app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    w = MainWindow()
    if w._start_hidden_to_tray:
        w.hide()
    else:
        w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
