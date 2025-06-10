# MiniTest-OECT 多设备控制系统

该仓库提供一个分离架构的多设备控制与测试平台，前端基于 PyQt5，后端采用多进程设计，主要用于有机电化学晶体管（OECT）等设备的自动化测试。本项目包含一个图形界面程序和一套后端库，可在多个设备上并行运行高吞吐量测试。

## 项目结构

```
.
├── backend_device_control_pyqt/    # 后端模块，提供多进程设备控制逻辑
├── qt_app/                         # PyQt 前端界面实现
├── run_qt.py                       # 启动图形界面入口脚本
├── requirements.txt                # 项目依赖
└── logs/                           # 默认日志目录
```

后端部分的详细说明见 `backend_device_control_pyqt/README.md`，安装说明参见 `backend_device_control_pyqt/INSTALL.md`。

## 快速开始

1. 安装 Python 3.8 及以上版本。
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   pip install -r backend_device_control_pyqt/requirements.txt
   ```
3. 运行界面程序：
   ```bash
   python run_qt.py
   ```
   首次启动会在 `logs/` 及 `UserData/AutoSave/` 下创建必要目录。

## 系统架构概览

后端采用四个独立进程协同工作，通过 `multiprocessing.Queue` 进行通信：

1. **Qt 主进程**：负责界面交互与用户请求。
2. **测试进程**：管理设备连接并执行具体测试逻辑。
3. **数据传输进程**：批量处理测试数据并将实时数据推送给界面，同时转发至保存进程。
4. **数据保存进程**：处理文件写入，将数据持久化为 CSV 等格式。

这种解耦设计能够在每秒 1000 个数据点的高吞吐场景下同时控制多达十台设备。

## 运行与使用

- 在界面中可选择串口并配置测试参数，点击开始后端会自动启动所需子进程并开始数据采集。
- 实时数据通过前端的 `realtime_plot` 组件绘制，可在“历史测试查看”标签页中浏览测试记录。
- 若需要在代码中直接调用后端，可参考下列示例：

```python
from backend_device_control_pyqt.main import MedicalTestBackend

backend = MedicalTestBackend()
backend.start()
ports = backend.list_serial_ports()
# 进一步的测试调用参见 backend_device_control_pyqt/README.md
```

关闭程序时，前端会通知后端依次关闭各进程并清理资源。

## 日志与数据

- 运行产生的日志位于 `logs/` 目录。
- 测试数据默认保存到 `UserData/AutoSave/`，路径可在后端配置中调整。

## 参考文档

- `backend_device_control_pyqt/README.md` – 后端架构、API 与示例代码。
- `backend_device_control_pyqt/INSTALL.md` – 完整的依赖与安装说明。