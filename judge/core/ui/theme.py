"""Shared dark theme for all judge pages."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QAbstractScrollArea, QPushButton, QTableWidget, QWidget


DARK_COLORS = {
    "bg": "#1A1D27",
    "panel": "#21253A",
    "panel_alt": "#252A40",
    "card": "#1E2235",
    "line": "#2E3555",
    "text": "#E6EBF7",
    "muted": "#8A96B5",
    "primary": "#5B8DEF",
    "primary_hover": "#4A7CE0",
    "danger": "#E05C6A",
    "danger_hover": "#CC4A58",
    "input": "#1C2035",
    "ok": "#52B788",
    "warn": "#E9C46A",
    "bad": "#E05C6A",
    "info": "#56B4D3",
    "chip": "#2E3555",
    "accent": "#6C63FF",
}


def _default_check_icon() -> str:
    return (Path(__file__).resolve().parents[2] / "assets" / "check_mark.svg").as_posix()


def _default_spin_up_icon() -> str:
    return (Path(__file__).resolve().parents[2] / "assets" / "spin_up.svg").as_posix()


def _default_spin_down_icon() -> str:
    return (Path(__file__).resolve().parents[2] / "assets" / "spin_down.svg").as_posix()


def build_dark_stylesheet(
    colors: Optional[Mapping[str, str]] = None,
    check_icon: Optional[str] = None,
) -> str:
    c = dict(DARK_COLORS)
    if colors:
        c.update(colors)
    icon = check_icon or _default_check_icon()
    spin_up_icon = _default_spin_up_icon()
    spin_down_icon = _default_spin_down_icon()

    return f"""
        QWidget {{
            background: {c['bg']};
            color: {c['text']};
            font-family: 'Segoe UI';
        }}
        QAbstractScrollArea, QAbstractScrollArea::viewport,
        QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget,
        QTableView, QTableView::viewport, QTableWidget, QTableWidget::viewport,
        QPlainTextEdit, QPlainTextEdit::viewport, QTextEdit, QTextEdit::viewport {{
            background: {c['bg']};
            color: {c['text']};
        }}
        QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTableWidget {{
            font-family: 'Consolas';
            font-size: 10pt;
        }}
        QGroupBox {{
            border: 1px solid {c['line']};
            border-radius: 12px;
            margin-top: 14px;
            padding-top: 8px;
            background: {c['panel']};
            font-weight: 700;
            font-size: 10pt;
        }}
        QGroupBox::title {{
            left: 14px;
            top: -9px;
            color: {c['muted']};
            background: transparent;
            padding: 0 6px;
            font-size: 9pt;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        QLabel, QCheckBox {{
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {c['line']};
            border-radius: 4px;
            background: {c['input']};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {c['primary']};
            background: {c['accent']};
            image: url({icon});
        }}
        QLabel#muted {{
            color: {c['muted']};
            background: transparent;
        }}
        QLabel#subTitle {{
            font-weight: 700;
            font-size: 11pt;
            background: transparent;
        }}
        QLabel#targetTitle {{
            font-weight: 700;
            font-size: 10pt;
            background: transparent;
            color: {c['text']};
        }}
        QLabel#cardTitle {{
            font-weight: 600;
            font-size: 9pt;
            color: {c['muted']};
            background: transparent;
        }}
        QLineEdit, QSpinBox, QComboBox {{
            background: {c['input']};
            color: {c['text']};
            border: 1px solid {c['line']};
            border-radius: 8px;
            padding: 5px 8px;
            selection-background-color: {c['primary']};
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border: 1px solid {c['primary']};
        }}
        QSpinBox {{
            padding-right: 22px;
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            subcontrol-origin: border;
            width: 18px;
            background: {c['panel_alt']};
            border-left: 1px solid {c['line']};
        }}
        QSpinBox::up-button {{
            subcontrol-position: top right;
            border-top-right-radius: 8px;
        }}
        QSpinBox::down-button {{
            subcontrol-position: bottom right;
            border-bottom-right-radius: 8px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background: {c['primary']};
        }}
        QSpinBox::up-arrow {{
            image: url({spin_up_icon});
            width: 10px;
            height: 8px;
        }}
        QSpinBox::down-arrow {{
            image: url({spin_down_icon});
            width: 10px;
            height: 8px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background: {c['panel_alt']};
            color: {c['text']};
            selection-background-color: {c['primary']};
            border: 1px solid {c['line']};
        }}
        QPlainTextEdit {{
            background: {c['input']};
            color: {c['text']};
            border: 1px solid {c['line']};
            border-radius: 8px;
            padding: 6px;
            selection-background-color: {c['primary']};
        }}
        QPlainTextEdit#output {{
            background: {c['card']};
            border: 1px solid {c['line']};
            color: #C8D8F0;
        }}
        QPlainTextEdit#output::viewport {{
            background: {c['card']};
        }}
        QTableWidget {{
            background: {c['input']};
            border: 1px solid {c['line']};
            border-radius: 8px;
            gridline-color: {c['line']};
            alternate-background-color: {c['panel_alt']};
        }}
        QTableWidget::viewport {{
            background: {c['input']};
        }}
        QTableWidget::item {{
            background: transparent;
            color: {c['text']};
        }}
        QTableCornerButton::section {{
            background: {c['panel_alt']};
            border: 1px solid {c['line']};
        }}
        QHeaderView::section {{
            background: {c['panel_alt']};
            color: {c['muted']};
            border: none;
            border-bottom: 1px solid {c['line']};
            border-right: 1px solid {c['line']};
            padding: 6px 8px;
            font-weight: 600;
            font-size: 9pt;
        }}
        QTableWidget::item:selected {{
            background: {c['primary']};
            color: #fff;
        }}
        QPushButton {{
            border: 1px solid {c['line']};
            border-radius: 8px;
            padding: 6px 14px;
            background: {c['panel_alt']};
            color: {c['text']};
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {c['chip']};
        }}
        QPushButton#primaryBtn {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {c['accent']}, stop:1 {c['primary']});
            border: none;
            color: #fff;
        }}
        QPushButton#primaryBtn:hover {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #5A5CD0, stop:1 {c['primary_hover']});
        }}
        QPushButton#dangerBtn {{
            background: {c['danger']};
            border: none;
            color: #fff;
        }}
        QPushButton#dangerBtn:hover {{
            background: {c['danger_hover']};
        }}
        QPushButton#ghostBtn {{
            background: transparent;
            border: 1px solid {c['line']};
            color: {c['muted']};
        }}
        QPushButton#ghostBtn:hover {{
            background: {c['chip']};
            color: {c['text']};
        }}
        QPushButton:disabled {{
            background: {c['panel_alt']};
            color: {c['muted']};
            border: 1px solid {c['line']};
        }}
        QPushButton#copyBtn {{
            min-width: 28px;
            max-width: 36px;
            padding: 2px 4px;
            border-radius: 6px;
            background: {c['panel_alt']};
            color: {c['muted']};
            border: 1px solid {c['line']};
            font-size: 10pt;
        }}
        QPushButton#copyBtn:hover {{
            background: {c['chip']};
            color: {c['text']};
        }}
        QPushButton#removeBtn {{
            border-radius: 12px;
            background: {c['panel_alt']};
            color: {c['muted']};
            border: 1px solid {c['line']};
            font-size: 9pt;
            padding: 0;
        }}
        QPushButton#removeBtn:hover {{
            background: {c['danger']};
            color: #fff;
            border: none;
        }}
        QFrame#caseEditorCard {{
            border: 1px solid {c['line']};
            border-radius: 10px;
            background: {c['panel_alt']};
        }}
        QFrame#targetCard {{
            border: 1px solid {c['line']};
            border-radius: 12px;
            background: {c['card']};
        }}
        QFrame#targetCard:hover {{
            border: 1px solid {c['primary']};
        }}
        QFrame#metricsFrame {{
            background: transparent;
        }}
        QScrollArea#customScroll {{
            border: 1px solid {c['line']};
            border-radius: 8px;
            background: {c['input']};
        }}
        QScrollArea#customScroll > QWidget,
        QScrollArea#customScroll > QWidget > QWidget,
        QScrollArea#customScroll QWidget#qt_scrollarea_viewport {{
            background: {c['input']};
        }}
        QScrollBar:vertical {{
            background: {c['panel']};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {c['line']};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['muted']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QSplitter::handle {{
            background: {c['line']};
            width: 1px;
        }}
    """


def apply_dark_palette(root: QWidget, colors: Optional[Mapping[str, str]] = None) -> None:
    c = dict(DARK_COLORS)
    if colors:
        c.update(colors)

    def palette(base: str) -> QPalette:
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(c["bg"]))
        pal.setColor(QPalette.WindowText, QColor(c["text"]))
        pal.setColor(QPalette.Base, QColor(base))
        pal.setColor(QPalette.AlternateBase, QColor(c["panel_alt"]))
        pal.setColor(QPalette.Text, QColor(c["text"]))
        pal.setColor(QPalette.Button, QColor(c["panel_alt"]))
        pal.setColor(QPalette.ButtonText, QColor(c["text"]))
        pal.setColor(QPalette.Highlight, QColor(c["primary"]))
        pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        return pal

    input_pal = palette(c["input"])
    card_pal = palette(c["card"])
    root.setPalette(palette(c["bg"]))
    for child in root.findChildren(QWidget):
        child.setPalette(input_pal)
    for area in root.findChildren(QAbstractScrollArea):
        pal = card_pal if area.objectName() == "output" else input_pal
        area.setPalette(pal)
        area.viewport().setPalette(pal)
        area.viewport().setAutoFillBackground(True)
    for table in root.findChildren(QTableWidget):
        table.setPalette(input_pal)
        table.viewport().setPalette(input_pal)
        table.viewport().setAutoFillBackground(True)
        table.horizontalHeader().setPalette(input_pal)
        table.verticalHeader().setPalette(input_pal)
    for button in root.findChildren(QPushButton):
        button.setPalette(input_pal)
