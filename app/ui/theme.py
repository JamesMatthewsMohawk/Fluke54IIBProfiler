"""Dark, industrial theme for the Superba Tunnel Profiler."""

BACKGROUND = "#1a1d21"
SURFACE = "#22262b"
SURFACE_ALT = "#2b3036"
BORDER = "#3a4048"
TEXT = "#e4e7eb"
TEXT_MUTED = "#8c94a0"
ACCENT = "#3f8cff"
ACCENT_HOVER = "#5a9dff"
ACCENT_PRESSED = "#2f6fd6"
SUCCESS = "#3fbf6f"
DANGER = "#e0524d"

STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QMainWindow {{
    background-color: {BACKGROUND};
}}

QLabel#TitleLabel {{
    font-size: 20px;
    font-weight: 600;
    color: {TEXT};
    letter-spacing: 0.5px;
}}

QLabel#SectionLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#HintLabel {{
    font-size: 11px;
    color: {TEXT_MUTED};
}}

QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QComboBox, QLineEdit {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 22px;
}}

QComboBox:hover, QLineEdit:hover {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
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
    border: 2px solid {BORDER};
    background-color: {SURFACE_ALT};
}}

QRadioButton::indicator:checked {{
    border: 2px solid {ACCENT};
    background-color: {ACCENT};
}}

QPushButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton:disabled {{
    background-color: {SURFACE_ALT};
    color: {TEXT_MUTED};
}}

QPushButton#SecondaryButton {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QPushButton#SecondaryButton:hover {{
    border-color: {ACCENT};
}}

QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
}}

QListWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {BORDER};
}}

QListWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QScrollBar:vertical {{
    background: {SURFACE};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QTableWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    outline: none;
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

QTableWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QHeaderView::section {{
    background-color: {SURFACE_ALT};
    color: {TEXT_MUTED};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}

QCheckBox {{
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid {BORDER};
    background-color: {SURFACE_ALT};
}}

QCheckBox::indicator:checked {{
    border: 2px solid {ACCENT};
    background-color: {ACCENT};
}}

QDateEdit {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    min-height: 22px;
}}

QDateEdit:disabled {{
    color: {TEXT_MUTED};
}}

QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}
"""
