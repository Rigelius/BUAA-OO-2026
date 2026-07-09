"""统一评测机主启动器。

用一个 QMainWindow 承载全部作业。顶部一个下拉框（按单元分组）切换到对应
作业的评测页面，每个页面由对应插件的 ``build_page(parent)`` 提供。

插件契约
--------
每个 ``judge.plugins.hwN`` 包必须暴露:
    PLUGIN = {
        "hw_id":       "hw6",
        "title":       "HW6 电梯 (临时检修)",
        "unit":        2,
        "order":       6,
        "build_page":  callable(parent: QWidget) -> QWidget,
    }
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PyQt5 import sip
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# Plugin discovery

@dataclass
class PluginInfo:
    hw_id: str
    title: str
    unit: int
    order: int
    build_page: Callable[[QWidget], QWidget]
    error: Optional[str] = None
    _page: Optional[QWidget] = field(default=None, repr=False)


_HW_ORDER = {"hw1": 1, "hw2": 2, "hw3": 3, "hw5": 5, "hw6": 6, "hw7": 7,
             "hw9": 9, "hw10": 10, "hw11": 11, "hw13": 13, "hw14": 14, "hw15": 15}

_UNIT_NAMES: Dict[int, str] = {
    1: "表达式化简",
    2: "电梯调度",
    3: "社交网络",
    4: "图书馆管理",
}

_HW_SHORT = {
    "hw1":  "基础",
    "hw2":  "三目 · 函数",
    "hw3":  "多变量 · 求导",
    "hw5":  "基础",
    "hw6":  "检修",
    "hw7":  "双轿厢",
    "hw9":  "基础",
    "hw10": "消息",
    "hw11": "推荐",
    "hw13": "基础",
    "hw14": "预约",
    "hw15": "信用",
}


def _wrap_window_class(window_cls) -> Callable[[QWidget], QWidget]:
    """把 QMainWindow 子类改造成 build_page: 抽出 centralWidget 作为页面。"""
    def build(parent: QWidget) -> QWidget:
        try:
            win = window_cls(parent)
        except TypeError:
            win = window_cls()
            win.setParent(parent, Qt.Widget)
        page = win.takeCentralWidget()
        if page is None:
            page = QWidget()
        page.setStyleSheet(win.styleSheet())
        page.setFont(win.font())
        page.setParent(parent)
        win.hide()
        win.setParent(page, Qt.Widget)
        # 保持 window 对象存活，避免 GC 掉 signals/threads
        page._owner_window = win  # type: ignore[attr-defined]
        return page
    return build


def _discover_plugins() -> List[PluginInfo]:
    """扫描 ``judge.plugins`` 下的每个子包，收集其 PLUGIN 元数据。

    兼容两种插件契约:
    (A) 新契约: {hw_id, title, unit, order, build_page}
    (B) 旧契约: {id, name, unit, window_class}  —— window_class 是 QMainWindow 子类
    """
    import judge.plugins as plugins_pkg  # 延迟导入避免循环
    infos: List[PluginInfo] = []
    for mod_info in pkgutil.iter_modules(plugins_pkg.__path__):
        if not mod_info.ispkg:
            continue
        mod_name = f"judge.plugins.{mod_info.name}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            infos.append(PluginInfo(
                hw_id=mod_info.name,
                title=f"{mod_info.name} (加载失败)",
                unit=99,
                order=999,
                build_page=lambda p, m=mod_info.name, e=exc: _error_page(p, m, e),
                error=str(exc),
            ))
            continue
        meta = getattr(mod, "PLUGIN", None)
        if not isinstance(meta, dict):
            continue
        try:
            hw_id = meta.get("hw_id") or meta.get("id") or mod_info.name
            title = meta.get("title") or meta.get("name") or hw_id
            unit = int(meta.get("unit", 0))
            order = int(meta.get("order", _HW_ORDER.get(hw_id, 999)))
            if "build_page" in meta:
                build_page = meta["build_page"]
            elif "window_class" in meta:
                build_page = _wrap_window_class(meta["window_class"])
            else:
                raise KeyError("plugin must provide build_page or window_class")
            infos.append(PluginInfo(
                hw_id=hw_id, title=title, unit=unit, order=order,
                build_page=build_page,
            ))
        except Exception as exc:
            infos.append(PluginInfo(
                hw_id=mod_info.name,
                title=f"{mod_info.name} (元数据错误)",
                unit=99,
                order=999,
                build_page=lambda p, m=mod_info.name, e=exc: _error_page(p, m, e),
                error=str(exc),
            ))
    infos.sort(key=lambda p: (p.unit, p.order))
    return infos


def _error_page(parent: QWidget, name: str, exc: Exception) -> QWidget:
    w = QWidget(parent)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 24, 24, 24)
    title = QLabel(f"插件 {name} 加载失败")
    title.setStyleSheet("color:#E05C6A;font-size:16pt;font-weight:600;")
    lay.addWidget(title)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    body = QLabel(tb)
    body.setStyleSheet("color:#E6EBF7;font-family:Consolas;")
    body.setTextInteractionFlags(Qt.TextSelectableByMouse)
    body.setWordWrap(True)
    lay.addWidget(body, 1)
    return w


# Launcher window

class Launcher(QMainWindow):
    """主启动器窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BUAA-OO 统一评测机")
        self._adapt_window_size()

        self.plugins: List[PluginInfo] = _discover_plugins()
        self._build_ui()
        self._apply_theme()

        # `_build_ui` 已经在末尾自动选中了首个 unit 与其首个 hw；此处无需再动。

    def _adapt_window_size(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1440, 900)
            return
        geo = screen.availableGeometry()
        w = min(1720, max(1240, int(geo.width() * 0.85)))
        h = min(1000, max(800, int(geo.height() * 0.88)))
        self.resize(w, h)
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 顶栏 1: 品牌 + 状态
        brand_row = QFrame()
        brand_row.setObjectName("brandRow")
        br = QHBoxLayout(brand_row)
        br.setContentsMargins(24, 14, 24, 12)
        br.setSpacing(0)

        brand = QLabel()
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.RichText)
        # QLabel 不支持 CSS class 选择器：用 RichText 内联样式实现 BUAA / OO 分色
        # BUAA 是学校，OO 是"Object-Oriented"这门课本身——分色是语义化，不是装饰。
        brand.setText(
            '<span style="color:#E6EBF7;letter-spacing:3px;font-weight:800;font-size:16pt;">BUAA</span>'
            '<span style="color:#485162;font-size:16pt;">&nbsp;·&nbsp;</span>'
            '<span style="color:#6C63FF;letter-spacing:3px;font-weight:800;font-size:16pt;">OO</span>'
        )
        br.addWidget(brand)

        subtitle = QLabel("统一评测机")
        subtitle.setObjectName("brandSub")
        br.addSpacing(14)
        br.addWidget(subtitle)

        br.addStretch(1)

        self.lbl_count_num = QLabel(str(len(self.plugins)))
        self.lbl_count_num.setObjectName("countNum")
        self.lbl_count_label = QLabel("插件已加载")
        self.lbl_count_label.setObjectName("countLabel")
        br.addWidget(self.lbl_count_num)
        br.addSpacing(6)
        br.addWidget(self.lbl_count_label)

        br.addSpacing(20)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("statusHint")
        br.addWidget(self.lbl_status)

        br.addStretch(1)

        btn_about = QPushButton("关于")
        btn_about.setObjectName("aboutBtn")
        btn_about.clicked.connect(self._show_about)
        br.addWidget(btn_about)

        v.addWidget(brand_row)

        # 顶栏 2: 单元 tab + hw chip
        nav_row = QFrame()
        nav_row.setObjectName("navRow")
        nv = QHBoxLayout(nav_row)
        nv.setContentsMargins(24, 4, 24, 0)
        nv.setSpacing(0)

        # 单元分组：只显示实际存在插件的单元
        self._units: List[int] = sorted({p.unit for p in self.plugins})
        self._unit_btns: Dict[int, QPushButton] = {}
        unit_wrap = QHBoxLayout()
        unit_wrap.setSpacing(0)
        for u in self._units:
            btn = QPushButton(f"U{u}  {_UNIT_NAMES.get(u, '')}")
            btn.setObjectName("unitTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, unit=u: self._on_unit_selected(unit))
            self._unit_btns[u] = btn
            unit_wrap.addWidget(btn)
        nv.addLayout(unit_wrap)

        # 单元与 hw 之间的竖分隔
        sep = QFrame()
        sep.setObjectName("navSep")
        sep.setFrameShape(QFrame.VLine)
        nv.addSpacing(14)
        nv.addWidget(sep)
        nv.addSpacing(14)

        # hw chip 容器：跟随 unit 切换刷新
        self._chip_wrap = QHBoxLayout()
        self._chip_wrap.setSpacing(8)
        self._hw_btns: Dict[str, QPushButton] = {}
        nv.addLayout(self._chip_wrap)

        nv.addStretch(1)

        v.addWidget(nav_row)

        # 顶栏与内容区之间的一条极细分隔
        hair = QFrame()
        hair.setObjectName("hair")
        hair.setFixedHeight(1)
        v.addWidget(hair)

        # 中间: 页面堆栈
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)

        # 初始化默认 unit：选第一个存在的单元
        self._active_unit: Optional[int] = None
        self._active_hw_id: Optional[str] = None
        if self._units:
            self._on_unit_selected(self._units[0], _emit=False)

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
        QMainWindow { background: #1A1D27; }

        /* 顶栏 1: 品牌 */
        QFrame#brandRow {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1E2233, stop:1 #22273D);
        }
        QLabel { color: #C8CFE3; font-size: 10pt; }
        QLabel#brandSub {
            color: #8A96B5;
            font-size: 11pt;
            font-weight: 400;
            letter-spacing: 0.5px;
        }
        QLabel#countNum {
            color: #E6EBF7;
            font-size: 13pt;
            font-weight: 700;
        }
        QLabel#countLabel {
            color: #8A96B5;
            font-size: 9pt;
            letter-spacing: 0.5px;
        }
        QLabel#statusHint {
            color: #A9B4CE;
            font-size: 10pt;
        }
        QPushButton#aboutBtn {
            background: transparent;
            color: #8A96B5;
            border: 1px solid #2E3555;
            border-radius: 6px;
            padding: 5px 14px;
            font-size: 9pt;
            letter-spacing: 1px;
        }
        QPushButton#aboutBtn:hover {
            border-color: #6C63FF;
            color: #E6EBF7;
        }

        /* 顶栏 2: 导航 */
        QFrame#navRow {
            background: #1B1F2C;
            border-top: 1px solid #262B3E;
        }

        /* 单元 tab：底部下划线激活态 */
        QPushButton#unitTab {
            background: transparent;
            color: #8A96B5;
            border: none;
            border-bottom: 2px solid transparent;
            padding: 12px 18px 10px 18px;
            margin: 0;
            font-size: 10pt;
            font-weight: 600;
            letter-spacing: 1px;
        }
        QPushButton#unitTab:hover {
            color: #E6EBF7;
        }
        QPushButton#unitTab:checked {
            color: #E6EBF7;
            border-bottom: 2px solid #6C63FF;
        }

        QFrame#navSep {
            color: #2E3555;
            background: #2E3555;
            max-width: 1px;
            margin: 10px 0;
        }

        /* hw chip：胶囊；激活态用紫蓝渐变 */
        QPushButton#hwChip {
            background: transparent;
            color: #A9B4CE;
            border: 1px solid #2E3555;
            border-radius: 14px;
            padding: 5px 14px;
            margin: 8px 0;
            font-size: 9pt;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        QPushButton#hwChip:hover {
            color: #E6EBF7;
            border-color: #485162;
        }
        QPushButton#hwChip:checked {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #6C63FF, stop:1 #5B8DEF);
            color: #FFFFFF;
            border: none;
            padding: 6px 15px;
        }

        QFrame#hair {
            background: #22273D;
            border: none;
        }
        """)

    def _on_unit_selected(self, unit: int, *, _emit: bool = True) -> None:
        """切换 unit tab：刷新下方的 hw chip 行，并自动选中该单元首个 hw。"""
        if self._active_unit == unit and _emit:
            return
        self._active_unit = unit
        for u, btn in self._unit_btns.items():
            btn.setChecked(u == unit)
        self._rebuild_chip_row(unit)
        # 自动落到该单元第一个 hw（或保留原本 active hw 若仍在此单元）
        hw_in_unit = [p for p in self.plugins if p.unit == unit]
        if not hw_in_unit:
            return
        preferred = None
        if self._active_hw_id:
            for p in hw_in_unit:
                if p.hw_id == self._active_hw_id:
                    preferred = p
                    break
        target = preferred or hw_in_unit[0]
        self._on_hw_selected(target.hw_id)

    def _rebuild_chip_row(self, unit: int) -> None:
        """按当前 unit 重建 hw chip 行。"""
        # 清空旧 chip
        while self._chip_wrap.count():
            item = self._chip_wrap.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._hw_btns.clear()

        for p in [pi for pi in self.plugins if pi.unit == unit]:
            label = f"{p.hw_id.upper()}"
            sub = _HW_SHORT.get(p.hw_id, "")
            btn = QPushButton(f"{label}  {sub}".rstrip())
            btn.setObjectName("hwChip")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, hid=p.hw_id: self._on_hw_selected(hid))
            self._hw_btns[p.hw_id] = btn
            self._chip_wrap.addWidget(btn)

    def _on_hw_selected(self, hw_id: str) -> None:
        pi = next((p for p in self.plugins if p.hw_id == hw_id), None)
        if pi is None:
            return
        self._hide_orphan_tooltips()
        self._active_hw_id = hw_id
        for hid, btn in self._hw_btns.items():
            btn.setChecked(hid == hw_id)
        if pi._page is not None and sip.isdeleted(pi._page):
            pi._page = None
        if pi._page is None:
            try:
                pi._page = pi.build_page(self.stack)
            except Exception as exc:
                pi._page = _error_page(self.stack, pi.hw_id, exc)
                pi.error = str(exc)
            self.stack.addWidget(pi._page)
            self._hide_orphan_tooltips()
        self.stack.setCurrentWidget(pi._page)
        self._hide_orphan_tooltips()
        sub = _HW_SHORT.get(pi.hw_id, "")
        status_body = f"{pi.hw_id.upper()}"
        if sub:
            status_body += f" · {sub}"
        self.lbl_status.setText(f"— {status_body}")
        self.setWindowTitle(f"BUAA-OO 统一评测机 — {pi.hw_id.upper()} {sub}".rstrip())

    def _hide_orphan_tooltips(self) -> None:
        for widget in QApplication.topLevelWidgets():
            if widget is self or widget.parent() is not None:
                continue
            if widget.windowFlags() & Qt.ToolTip:
                widget.hide()

    def _show_about(self) -> None:
        text = (
            "<b>BUAA-OO 统一评测机</b><br><br>"
            "北航面向对象设计与构造 (2026 春季) 全部代码作业的对拍/评测工具。<br><br>"
            "作者: 丁一博<br>"
            "架构: 单窗口 + 可插拔 hw 插件 (QStackedWidget)<br>"
            "许可: MIT<br><br>"
            f"当前已加载 {len(self.plugins)} 个作业插件。"
        )
        QMessageBox.about(self, "关于", text)


# Entry point

def main() -> None:
    # 让相对导入 (judge.plugins.hw*) 可用: 把 BUAA-OO 目录放到 sys.path
    buaa_root = Path(__file__).resolve().parent.parent.parent
    if str(buaa_root) not in sys.path:
        sys.path.insert(0, str(buaa_root))

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#1A1D27"))
    palette.setColor(QPalette.WindowText, QColor("#E6EBF7"))
    palette.setColor(QPalette.Base, QColor("#1C2035"))
    palette.setColor(QPalette.AlternateBase, QColor("#252A40"))
    palette.setColor(QPalette.Text, QColor("#E6EBF7"))
    palette.setColor(QPalette.Button, QColor("#252A40"))
    palette.setColor(QPalette.ButtonText, QColor("#E6EBF7"))
    palette.setColor(QPalette.Highlight, QColor("#5B8DEF"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    win = Launcher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
