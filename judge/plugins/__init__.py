"""每次作业的评测机插件包。

每个 ``hwN`` 子包应导出一个 ``PLUGIN`` 常量, 结构如下::

    PLUGIN = {
        "hw_id":  "hw6",           # 短标识
        "unit":   2,               # 所属单元 (1-4)
        "title":  "HW6 电梯 迭代二",  # 下拉框中的显示名
        "factory": <callable>,     # () -> QMainWindow, 由 launcher 调用
    }

Launcher 会在启动时依次探测 ``hw1``..``hw15`` 子包并载入。
"""

__all__: list[str] = []
