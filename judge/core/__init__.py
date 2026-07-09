"""统一评测机公共层。

提供:
- Launcher: 主启动器窗口，用下拉框在不同 hw 之间切换。
- 公共 UI 小部件与主题（供各 hw 插件复用）。
"""

from .launcher import Launcher, main  # noqa: F401
