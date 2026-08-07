"""Dark/light theme palettes for the Superba Tunnel Profiler."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    success: str
    danger: str


DARK = Palette(
    background="#1a1d21",
    surface="#22262b",
    surface_alt="#2b3036",
    border="#3a4048",
    text="#e4e7eb",
    text_muted="#8c94a0",
    accent="#3f8cff",
    accent_hover="#5a9dff",
    accent_pressed="#2f6fd6",
    success="#3fbf6f",
    danger="#e0524d",
)

LIGHT = Palette(
    background="#f2f3f5",
    surface="#ffffff",
    surface_alt="#eceef1",
    border="#d3d7dd",
    text="#1a1d21",
    text_muted="#6b7280",
    accent="#3f8cff",
    accent_hover="#2f6fd6",
    accent_pressed="#255bb0",
    success="#1f9d55",
    danger="#c23b38",
)

THEMES: dict[str, Palette] = {"Dark": DARK, "Light": LIGHT}


def build_stylesheet(p: Palette) -> str:
    return f"""
QWidget {{
    background-color: {p.background};
    color: {p.text};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QMainWindow {{
    background-color: {p.background};
}}

QLabel#TitleLabel {{
    font-size: 20px;
    font-weight: 600;
    color: {p.text};
    letter-spacing: 0.5px;
}}

QLabel#SectionLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {p.text_muted};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#HintLabel {{
    font-size: 11px;
    color: {p.text_muted};
}}

QFrame#Card {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
}}

QFrame#UpdateBanner {{
    background-color: {p.surface_alt};
    border: 1px solid {p.accent};
    border-radius: 8px;
}}

QComboBox, QLineEdit {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 22px;
}}

QComboBox:hover, QLineEdit:hover {{
    border-color: {p.accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    selection-background-color: {p.accent};
    outline: none;
}}

QRadioButton {{
    spacing: 8px;
    padding: 4px 0;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid {p.border};
    background-color: {p.surface_alt};
}}

QRadioButton::indicator:checked {{
    border: 2px solid {p.accent};
    background-color: {p.accent};
}}

QPushButton {{
    background-color: {p.accent};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {p.accent_hover};
}}

QPushButton:pressed {{
    background-color: {p.accent_pressed};
}}

QPushButton:disabled {{
    background-color: {p.surface_alt};
    color: {p.text_muted};
}}

QPushButton#SecondaryButton {{
    background-color: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border};
}}

QPushButton#SecondaryButton:hover {{
    border-color: {p.accent};
}}

QListWidget {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 6px;
    outline: none;
}}

QListWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {p.border};
}}

QListWidget::item:selected {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: {p.surface};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {p.border};
    border-radius: 5px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.accent};
}}

QTabWidget::pane {{
    border: 1px solid {p.border};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {p.surface};
    color: {p.text_muted};
    border: 1px solid {p.border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {p.surface_alt};
    color: {p.text};
}}

QTabBar::tab:hover {{
    color: {p.text};
}}

QTableWidget {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 6px;
    gridline-color: {p.border};
    outline: none;
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

QTableWidget::item:selected {{
    background-color: {p.accent};
    color: white;
}}

QHeaderView::section {{
    background-color: {p.surface_alt};
    color: {p.text_muted};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {p.border};
    font-weight: 600;
}}

QCheckBox {{
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid {p.border};
    background-color: {p.surface_alt};
}}

QCheckBox::indicator:checked {{
    border: 2px solid {p.accent};
    background-color: {p.accent};
}}

QDateEdit {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 22px;
}}

QDateEdit:disabled {{
    color: {p.text_muted};
}}

QStatusBar {{
    background-color: {p.surface};
    border-top: 1px solid {p.border};
    color: {p.text_muted};
}}
"""


# Kept for any script that just wants a reasonable default stylesheet
# without theme-switching support (e.g. one-off tools, smoke tests).
STYLESHEET = build_stylesheet(DARK)
