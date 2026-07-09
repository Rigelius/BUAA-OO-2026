# BUAA-OO

北京航空航天大学《面向对象设计与构造》课程作业整理与本地评测工具。

仓库包含四个单元的作业源码、单元博客、课程指导书归档，以及一个统一的 PyQt5 图形化评测器。评测器覆盖 12 次代码作业，支持固定样例、随机样例和自定义样例，也支持同时评测多个源码目录或 jar 包目标。

## 目录结构

```text
BUAA-OO/
├── U1/                  # 表达式化简
│   ├── hw1/
│   ├── hw2/
│   ├── hw3/
│   └── hw4/
├── U2/                  # 多线程电梯
│   ├── hw5/
│   ├── hw6/
│   ├── hw7/
│   └── hw8/
├── U3/                  # JML 社交网络
│   ├── hw9/
│   ├── hw10/
│   ├── hw11/
│   └── hw12/
├── U4/                  # UML 图书馆管理系统
│   ├── hw13/
│   ├── hw14/
│   ├── hw15/
│   └── hw16/
├── docs/guidebooks/     # 课程指导书
├── judge/               # 统一评测器
├── requirements.txt
└── LICENSE
```

## 环境要求

- Python 3.9+
- JDK 8+
- Windows / macOS / Linux 均可运行，Windows 下建议使用 PowerShell 或 Windows Terminal

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

## 运行评测器

在仓库根目录执行：

```bash
python -m judge
```

启动后在顶部选择单元和作业。每个作业页面左侧为评测配置和自定义样例，右侧为样例列表、目标输出和运行日志。

常用填写方式：

- `目标路径`：填写待扫描的根目录，例如 `U1/hw1` 或 `submissions/hw1`。
- `我的目标`：填写自己的目标名称或匹配规则，例如 `src`。
- `其余目标`：填写其他待比较目标的匹配规则，可用于互测、对拍或性能分比较。

评测器会在目标路径下查找匹配的源码目录或 jar 包，并对勾选的固定、随机、自定义样例进行评测。

## 覆盖范围

| 单元 | 作业 | 内容 |
| :--- | :--- | :--- |
| U1 | hw1 / hw2 / hw3 | 表达式化简、自定义函数、求导 |
| U2 | hw5 / hw6 / hw7 | 多线程电梯调度 |
| U3 | hw9 / hw10 / hw11 | JML 社交网络 |
| U4 | hw13 / hw14 / hw15 | 图书馆管理系统 |

## License

MIT License. See [LICENSE](LICENSE).
