# 医疗测试系统后端 - 多进程架构

本项目是医疗测试系统后端的多进程架构实现，专为高吞吐量场景设计，能够处理每秒1000个数据点的并发测试，支持多达10个同时运行的设备。

## 架构概述

系统采用四个专门的进程处理不同任务，优化高负载场景下的性能：

1. **Qt接口进程** (主进程) - 处理PyQt前端接口和用户请求
2. **测试进程** - 管理设备连接和测试执行
3. **数据传输进程** - 处理实时数据流和数据分发
4. **数据保存进程** - 负责文件操作和数据持久化

进程间通信使用`multiprocessing.Queue`，避免了原来多线程架构中的全局锁限制。

## 目录结构

```
backend_device_control_pyqt/
├── __init__.py                    # 包初始化文件
├── processes/                     # 进程模块目录
│   ├── __init__.py                # 进程包初始化文件
│   ├── test_process.py            # 测试进程模块
│   ├── data_transmission_process.py  # 数据传输进程模块
│   └── data_save_process.py       # 数据保存进程模块
└── main.py                        # 主程序入口
```

## 进程职责说明

### Qt接口进程 (主进程)

- 处理用户界面请求
- 启动和管理其他三个子进程
- 将用户命令转发到测试进程
- 从数据传输进程接收实时数据并更新界面

### 测试进程

- 管理设备连接和通信
- 执行测试步骤和工作流
- 采集数据并发送到数据传输进程
- 处理用户测试命令和控制请求

### 数据传输进程

- 接收来自测试进程的原始数据
- 批处理数据以提高效率
- 分发实时数据更新到Qt进程
- 发送数据到保存进程进行持久化

### 数据保存进程

- 处理所有文件I/O操作
- 将测试数据保存为CSV文件
- 支持数据批量追加以提高性能
- 向数据传输进程报告保存结果

## 性能优化特性

1. **数据批处理** - 数据传输进程会缓冲和批处理数据点，减少进程间通信开销
2. **异步IO** - 数据保存使用多线程处理文件IO，避免阻塞
3. **进程间负载均衡** - 每个进程专注于特定任务，避免相互干扰
4. **缓存优化** - 数据保存进程缓存测试数据，优化追加操作
5. **高效序列化** - 使用numpy等高性能库进行数据处理

## 使用方法

### 启动系统

```python
from backend_device_control_pyqt.main import MedicalTestBackend

# 创建后端实例
backend = MedicalTestBackend()

# 启动后端系统（将启动所有子进程）
backend.start()

# 在Qt应用中使用后端提供的接口
ports = backend.list_serial_ports()
```

### 获取实时数据

```python
# 在Qt应用循环中定期调用
def update_ui():
    data = backend.get_real_time_data()
    if data:
        # 处理数据更新UI
        update_display(data)
```

### 启动工作流测试

```python
# 准备测试参数
params = {
    "test_id": "test123",
    "device_id": "device001",
    "port": "COM3",
    "baudrate": 512000,
    "name": "转移特性测试",
    "description": "测试描述",
    "steps": [...]  # 测试步骤配置
}

# 启动工作流
result = backend.start_workflow(params)
```

### 停止测试

```python
# 停止指定的测试
result = backend.stop_test(test_id="test123")

# 或停止指定设备的所有测试
result = backend.stop_test(device_id="device001")
```

### 系统关闭

```python
# 关闭后端系统
backend.shutdown()
```

## 系统要求

- Python 3.8+
- PyQt 5.15+
- NumPy
- PySerial

## 注意事项

1. 启动系统时，会等待所有进程就绪，超时时间为10秒
2. 文件保存路径默认在 `UserData/AutoSave/` 目录下
3. 日志文件保存在 `logs/` 目录下
4. 进程间通信使用队列，避免共享内存带来的复杂性