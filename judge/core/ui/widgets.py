"""Reusable widgets shared by judge pages."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CopyButton(QPushButton):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("⧉", parent)
        self.setObjectName("copyBtn")
        self.setFixedHeight(24)

    def flash_done(self) -> None:
        self.setText("✓")
        self.setEnabled(False)
        QTimer.singleShot(800, self._restore)

    def _restore(self) -> None:
        self.setText("⧉")
        self.setEnabled(True)


class BadgeLabel(QLabel):
    """Pill-shaped status badge."""

    PALETTES = {
        "neutral": ("#3A4252", "#D8DEE9"),
        "ok": ("#2D6A4F", "#B7E4C7"),
        "warn": ("#7B5E00", "#FFE08A"),
        "bad": ("#7B1D1D", "#FFBABA"),
        "info": ("#1A3A6B", "#9EC8FF"),
        "ac": ("#1B5E20", "#A5D6A7"),
        "wa": ("#7B1D1D", "#EF9A9A"),
        "tle": ("#4A3000", "#FFCC80"),
        "re": ("#4A004A", "#CE93D8"),
    }

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignCenter)

    def set_badge(self, text: str, kind: str) -> None:
        bg, fg = self.PALETTES.get(kind, self.PALETTES["neutral"])
        self.setText(text)
        self.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:10px;"
            f"padding:3px 10px;font-weight:700;font-size:9pt;"
        )


class StatusChip(QLabel):
    """Inline chip for target status."""

    STATUS_STYLES = {
        "AC": ("background:#1B5E20;color:#C8E6C9;", "AC"),
        "WA": ("background:#7B1D1D;color:#FFCDD2;", "WA"),
        "TLE": ("background:#4A3000;color:#FFE0B2;", "TLE"),
        "RE": ("background:#4A004A;color:#E1BEE7;", "RE"),
        "IE": ("background:#283593;color:#C5CAE9;", "IE"),
        "...": ("background:#37474F;color:#B0BEC5;", "..."),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("...", parent)
        self.setAlignment(Qt.AlignCenter)
        self._apply("...")

    def _apply(self, key: str) -> None:
        style, label = self.STATUS_STYLES.get(key, self.STATUS_STYLES["..."])
        self.setText(label)
        self.setStyleSheet(
            style + "border-radius:8px;padding:2px 8px;font-weight:800;"
            "font-size:9pt;min-width:28px;"
        )

    def set_status(self, key: str, score: Optional[float] = None) -> None:
        self._apply(key)


class CaseEditorCard(QFrame):
    remove_requested = pyqtSignal(str)

    def __init__(
        self,
        card_id: str,
        title: str,
        code_font: QFont,
        text: str = "",
        placeholder: str = "",
    ) -> None:
        super().__init__()
        self.card_id = card_id
        self.setObjectName("caseEditorCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        top.addWidget(self.title_label)
        top.addStretch(1)
        self.copy_btn = CopyButton()
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("removeBtn")
        self.remove_btn.setFixedSize(24, 24)
        top.addWidget(self.copy_btn)
        top.addWidget(self.remove_btn)
        root.addLayout(top)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setFont(code_font)
        self.editor.setPlaceholderText(placeholder or "输入完整样例内容")
        self.editor.setPlainText(text)
        root.addWidget(self.editor)

        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.card_id))

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def get_text(self) -> str:
        return self.editor.toPlainText()


class TargetOutputCard(QFrame):
    """Card for one target's output."""

    def __init__(
        self,
        target_name: str,
        code_font: QFont,
        show_metrics: bool = False,
        show_score: bool = False,
        show_reason: bool = False,
        append_shorter_candidate: bool = False,
        metric_labels: Sequence[str] = ("Tr", "Ta", "W"),
    ) -> None:
        super().__init__()
        self.target_name = target_name
        self.show_metrics = show_metrics
        self.show_score = show_score
        self.show_reason = show_reason
        self.append_shorter_candidate = append_shorter_candidate
        self.metric_labels = tuple(metric_labels)
        self.setObjectName("targetCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.title_label = QLabel(target_name)
        self.title_label.setObjectName("targetTitle")
        top.addWidget(self.title_label)

        self.status_chip = QLabel("···")
        self.status_chip.setAlignment(Qt.AlignCenter)
        self._set_chip("···", "#37474F", "#B0BEC5")
        top.addWidget(self.status_chip)

        self.score_label = QLabel("")
        self.score_label.setStyleSheet(
            "color:#90CAF9;font-weight:700;font-size:9pt;background:transparent;"
        )
        self.metrics_frame = QFrame()
        self.metrics_frame.setObjectName("metricsFrame")
        mf_layout = QHBoxLayout(self.metrics_frame)
        mf_layout.setContentsMargins(0, 0, 0, 0)
        mf_layout.setSpacing(4)

        self.metric_widgets: list[QLabel] = []
        for idx, name in enumerate(self.metric_labels):
            if idx:
                mf_layout.addWidget(self._sep())
            lbl = self._make_metric(name, "—")
            self.metric_widgets.append(lbl)
            mf_layout.addWidget(lbl)
        mf_layout.addStretch(1)
        top.addWidget(self.metrics_frame)
        self.metrics_frame.setVisible(show_metrics)

        self.score_label.setVisible(show_score)
        top.addWidget(self.score_label)
        top.addStretch(1)

        self.copy_btn = CopyButton()
        top.addWidget(self.copy_btn)
        root.addLayout(top)

        self.reason_label = QLabel("")
        self.reason_label.setObjectName("cardTitle")
        self.reason_label.setWordWrap(True)
        self.reason_label.setVisible(False)
        root.addWidget(self.reason_label)

        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setObjectName("output")
        self.output_edit.setFont(code_font)
        root.addWidget(self.output_edit)

    @staticmethod
    def _sep() -> QLabel:
        s = QLabel("·")
        s.setStyleSheet("color:#485162;background:transparent;")
        return s

    @staticmethod
    def _make_metric(name: str, val: str) -> QLabel:
        lbl = QLabel(f"{name}  {val}")
        lbl.setObjectName("metricPill")
        lbl.setStyleSheet(
            "background:#262C3A;color:#8FA8C8;border-radius:6px;"
            "padding:2px 8px;font-size:8pt;font-weight:600;"
        )
        return lbl

    def _update_metric(self, lbl: QLabel, name: str, val: str, highlight: bool = False) -> None:
        color = "#E2F0FF" if highlight else "#8FA8C8"
        lbl.setText(f"{name}  {val}")
        lbl.setStyleSheet(
            f"background:#262C3A;color:{color};border-radius:6px;"
            "padding:2px 8px;font-size:8pt;font-weight:600;"
        )

    def set_running(self) -> None:
        self._set_chip("···", "#37474F", "#B0BEC5")
        self.score_label.setText("")
        self.reason_label.setVisible(False)
        for lbl, name in zip(self.metric_widgets, self.metric_labels):
            self._update_metric(lbl, name, "—")
        self.output_edit.setPlainText("")

    def set_result(
        self,
        rr: Optional[Any],
        output_text: str,
        status_key: str,
        score: Optional[float] = None,
        metrics: Optional[list[tuple[str, str, bool]]] = None,
    ) -> None:
        status_map = {
            "AC": ("#1B5E20", "#C8E6C9"),
            "WA": ("#7B1D1D", "#FFCDD2"),
            "TLE": ("#4A3000", "#FFE0B2"),
            "RE": ("#4A004A", "#E1BEE7"),
            "IE": ("#283593", "#C5CAE9"),
        }
        bg, fg = status_map.get(status_key, ("#37474F", "#B0BEC5"))
        self._set_chip(status_key, bg, fg)

        if self.show_score and score is not None:
            self.score_label.setVisible(True)
            self.score_label.setText(f"S: {score:.2f}")
            s_color = "#69F0AE" if score >= 12 else "#FFD740" if score >= 8 else "#FF5252"
            self.score_label.setStyleSheet(
                f"color:{s_color};font-weight:700;font-size:9pt;background:transparent;"
            )
        else:
            self.score_label.setText("")
            self.score_label.setVisible(self.show_score)

        if self.show_metrics and metrics is not None:
            for lbl, (name, val, highlight) in zip(self.metric_widgets, metrics):
                self._update_metric(lbl, name, val, highlight)
        elif self.show_metrics and rr is not None:
            values = {
                "Time": getattr(rr, "elapsed_sec", None),
                "Tr": getattr(rr, "sim_time", None),
                "Ta": getattr(rr, "avg_time", None),
                "W": getattr(rr, "power", None),
            }
            for lbl, name in zip(self.metric_widgets, self.metric_labels):
                value = values.get(name)
                if name in {"Time", "Tr", "Ta"}:
                    text = f"{value:.3f}s" if value is not None else "—"
                else:
                    text = f"{value:.2f}" if value is not None else "—"
                self._update_metric(lbl, name, text, value is not None)
        else:
            for lbl, name in zip(self.metric_widgets, self.metric_labels):
                self._update_metric(lbl, name, "—")

        reason = getattr(rr, "reason", "") if rr is not None else ""
        if self.show_reason and reason and status_key != "AC":
            self.reason_label.setText(reason)
            self.reason_label.setVisible(True)
        else:
            self.reason_label.setVisible(False)

        body = output_text
        shorter = getattr(rr, "shorter_candidate", "") if rr is not None else ""
        if self.append_shorter_candidate and shorter:
            body += f"\n\n[更短等价候选]\n{shorter}"
        self.output_edit.setPlainText(body)

    def _set_chip(self, text: str, bg: str, fg: str) -> None:
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:8px;"
            "padding:2px 8px;font-weight:800;font-size:9pt;min-width:30px;"
        )
