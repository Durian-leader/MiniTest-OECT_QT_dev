# OECT测试系统后端模块

一个高性能的有机电化学晶体管(OECT)测试系统后端，采用多进程架构设计，支持多设备并发测试和复杂工作流编排。

## 系统概述

该系统为PyQt前端应用提供完整的设备控制和测试管理功能，支持转移特性、瞬态特性、输出特性等多种测试模式，以及自定义工作流编排。采用四进程架构确保高负载场景下的稳定性和性能。

### 核心特性

- 🔧 **多进程架构** - 测试、数据传输、保存分离，避免阻塞
- 📊 **实时数据流** - 支持高频数据采集和实时显示
- 🔄 **工作流编排** - 支持循环、嵌套等复杂测试序列
- 🎯 **多测试模式** - 转移、瞬态、输出特性测试
- 💾 **智能数据管理** - 批处理、缓存优化、自动保存
- 🔌 **异步串口通信** - 高效稳定的设备通信

## 架构设计

### 多进程架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│   主进程(Qt)    │───▶│    测试进程       │───▶│   数据传输进程       │───▶│   数据保存进程    │
│  用户接口管理    │    │  设备连接控制     │    │  数据处理分发       │    │   文件IO操作     │
│  命令分发       │    │  测试步骤执行     │    │  实时数据流         │    │   CSV保存       │
│  实时数据显示    │    │  工作流编排       │    │  批处理优化         │    │   批量写入       │
└─────────────────┘    └──────────────────┘    └─────────────────────┘    └──────────────────┘
```

### 进程职责

#### 主进程 (`main.py`)
- **MedicalTestBackend类** - 系统主控制器
- PyQt接口管理和用户请求处理
- 子进程生命周期管理
- 实时数据获取和分发

#### 测试进程 (`test_process.py`)
- **TestManager类** - 测试执行核心
- 串口设备连接和通信管理
- 测试步骤执行和工作流编排
- 设备状态监控和错误处理

#### 数据传输进程 (`data_transmission_process.py`)
- **DataTransmissionManager类** - 数据流控制
- 实时数据接收和分发
- 数据批处理和缓存优化
- 消息路由和状态同步

#### 数据保存进程 (`data_save_process.py`)
- **DataSaveManager类** - 文件IO专用
- CSV文件保存和管理
- 多线程文件写入优化
- 数据完整性保证

## 测试类型支持

### 1. 转移特性测试 (`transfer_step.py`)
```python
# 栅极电压扫描，测量漏极电流变化
params = {
    "gateVoltageStart": -1000,  # 起始电压(mV)
    "gateVoltageEnd": 1000,     # 结束电压(mV)
    "gateVoltageStep": 50,      # 步进电压(mV)
    "drainVoltage": 100,        # 漏极电压(mV)
    "sourceVoltage": 0,         # 源极电压(mV)
    "isSweep": 1,               # 是否回扫
    "timeStep": 100             # 时间步长(ms)
}
```

### 2. 瞬态特性测试 (`transient_step.py`)
```python
# 时间域电流响应测试
params = {
    "timeStep": 10,             # 采样间隔(ms)
    "bottomTime": 1000,         # 低电平时间(ms)
    "topTime": 1000,            # 高电平时间(ms)
    "gateVoltageBottom": 0,     # 栅极低电平(mV)
    "gateVoltageTop": 1000,     # 栅极高电平(mV)
    "cycles": 3,                # 循环次数
    "drainVoltage": 100,        # 漏极电压(mV)
    "sourceVoltage": 0          # 源极电压(mV)
}
```

### 3. 输出特性测试 (`output_step.py`)
```python
# 多栅极电压下的输出特性曲线
params = {
    "gateVoltageList": [0, 200, 400, 600, 800],  # 栅极电压列表(mV)
    "drainVoltageStart": 0,     # 漏极起始电压(mV)
    "drainVoltageEnd": 1000,    # 漏极结束电压(mV)
    "drainVoltageStep": 50,     # 漏极步进电压(mV)
    "sourceVoltage": 0,         # 源极电压(mV)
    "isSweep": 0,               # 是否回扫
    "timeStep": 100             # 时间步长(ms)
}
```

## 工作流系统

### 工作流配置 (`workflow_models.py`)

支持复杂的测试序列编排，包括循环、嵌套等结构：

```python
workflow_config = {
    "test_id": "complex_workflow_001",
    "device_id": "device_001", 
    "port": "COM3",
    "baudrate": 512000,
    "name": "复合特性测试",
    "description": "包含多种测试模式的综合工作流",
    "steps": [
        {
            "type": "transfer",
            "command_id": 1,
            "params": {...}  # 转移特性参数
        },
        {
            "type": "loop",
            "iterations": 3,
            "steps": [
                {
                    "type": "transient", 
                    "command_id": 2,
                    "params": {...}  # 瞬态特性参数
                },
                {
                    "type": "output",
                    "command_id": 3, 
                    "params": {...}  # 输出特性参数
                }
            ]
        }
    ]
}
```

## 目录结构

```
backend_device_control_pyqt/
├── main.py                        # 系统主入口
├── ipc.py                        # 进程间通信工具
├── processes/                    # 进程模块
│   ├── test_process.py          # 测试执行进程
│   ├── data_transmission_process.py  # 数据传输进程
│   └── data_save_process.py     # 数据保存进程
├── test/                        # 测试步骤实现
│   ├── step.py                  # 测试步骤基类
│   ├── test.py                  # 测试编排类
│   ├── transfer_step.py         # 转移特性测试
│   ├── transient_step.py        # 瞬态特性测试
│   └── output_step.py           # 输出特性测试
├── core/                        # 核心功能模块
│   ├── async_serial.py          # 异步串口通信
│   ├── command_gen.py           # 测试命令生成
│   └── serial_data_parser.py    # 数据解析器
├── comunication/                # 通信模块
│   └── data_bridge.py           # 数据桥接层
├── models/                      # 数据模型
│   └── workflow_models.py       # 工作流模型定义
└── README.md                    # 系统说明文档
```

## 快速开始

### 1. 系统初始化

```python
from backend_device_control_pyqt.main import MedicalTestBackend

# 创建后端实例
backend = MedicalTestBackend()

try:
    # 启动多进程系统
    backend.start()
    print("OECT测试系统已启动")
    
except RuntimeError as e:
    print(f"系统启动失败: {e}")
```

### 2. 设备检测

```python
# 获取可用串口设备列表（带设备ID识别）
ports = backend.list_serial_ports()

for port in ports:
    print(f"端口: {port['device']}")
    print(f"描述: {port['description']}")
    print(f"设备ID: {port['device_id']}")
    print("---")
```

### 3. 启动测试

```python
# 转移特性测试
transfer_params = {
    "test_id": "transfer_001",
    "device_id": "device_001",
    "port": "COM3",
    "baudrate": 512000,
    "name": "转移特性测试",
    "step_params": {
        "gateVoltageStart": -1000,
        "gateVoltageEnd": 1000,
        "gateVoltageStep": 50,
        "drainVoltage": 100,
        "sourceVoltage": 0,
        "isSweep": 1,
        "timeStep": 100
    }
}

result = backend.start_transfer_test(transfer_params)
print(f"测试启动结果: {result}")
```

### 4. 实时数据获取

```python
# 在Qt应用的定时器中调用
def update_real_time_data():
    data = backend.get_real_time_data(timeout=0.01)
    if data:
        # 处理不同类型的消息
        msg_type = data.get("type")
        
        if msg_type == "test_data":
            # 处理测试数据
            handle_test_data(data)
        elif msg_type == "test_progress":
            # 更新进度显示
            update_progress(data)
        elif msg_type == "test_result":
            # 处理测试完成
            handle_test_completion(data)
```

### 5. 工作流执行

```python
# 复杂工作流测试
workflow_params = {
    "test_id": "workflow_001",
    "device_id": "device_001", 
    "port": "COM3",
    "baudrate": 512000,
    "name": "综合性能测试",
    "description": "包含转移、瞬态、输出特性的完整测试流程",
    "steps": [
        {
            "type": "transfer",
            "command_id": 1,
            "params": {
                "gateVoltageStart": -1000,
                "gateVoltageEnd": 1000,
                "gateVoltageStep": 100,
                "drainVoltage": 100,
                "sourceVoltage": 0,
                "isSweep": 1,
                "timeStep": 100
            }
        },
        {
            "type": "transient", 
            "command_id": 2,
            "params": {
                "timeStep": 10,
                "bottomTime": 1000,
                "topTime": 1000,
                "gateVoltageBottom": 0,
                "gateVoltageTop": 1000,
                "cycles": 3,
                "drainVoltage": 100,
                "sourceVoltage": 0
            }
        },
        {
            "type": "output",
            "command_id": 3,
            "params": {
                "gateVoltageList": [0, 200, 400, 600, 800],
                "drainVoltageStart": 0,
                "drainVoltageEnd": 1000,
                "drainVoltageStep": 50,
                "sourceVoltage": 0,
                "isSweep": 0,
                "timeStep": 100
            }
        }
    ]
}

result = backend.start_workflow(workflow_params)
```

### 6. 测试控制

```python
# 获取测试状态
status = backend.get_test_status("test_001")
print(f"测试状态: {status}")

# 停止测试
stop_result = backend.stop_test(test_id="test_001")
print(f"停止结果: {stop_result}")

# 系统关闭
backend.shutdown()
```

## 数据格式

### 实时数据消息格式

```python
# 测试数据消息
{
    "type": "test_data",
    "test_id": "test_001",
    "device_id": "device_001", 
    "step_type": "transfer",
    "data": "FF0102...",  # 十六进制数据
    "timestamp": 1672531200.123,
    "is_workflow": True,
    "workflow_info": {
        "step_index": 1,
        "total_steps": 3,
        "path": [...],
        "iteration_info": {...}
    }
}

# 进度消息
{
    "type": "test_progress", 
    "test_id": "test_001",
    "step_type": "transfer",
    "progress": 0.65,  # 0.0-1.0
    "device_id": "device_001"
}

# 测试结果消息
{
    "type": "test_result",
    "test_id": "test_001", 
    "status": "completed",  # completed/stopped/error
    "info": {...}  # 详细测试信息
}
```

### 保存的数据文件

测试数据自动保存到 `UserData/AutoSave/{device_id}/{timestamp}_{test_type}_{test_id}/` 目录：

- **转移特性**: `transfer.csv` - 包含栅极电压(Vg)和漏极电流(Id)
- **瞬态特性**: `transient.csv` - 包含时间(Time)和漏极电流(Id)  
- **输出特性**: `output.csv` - 包含漏极电压(Vd)和不同栅极电压下的电流
- **测试信息**: `test_info.json` - 测试元数据和参数
- **工作流配置**: `workflow.json` - 工作流步骤配置(仅工作流测试)

## 性能优化

### 数据处理优化

1. **批处理机制** - 数据传输进程缓冲数据包，减少通信开销
2. **异步IO** - 数据保存使用多线程，避免阻塞主流程
3. **内存管理** - 智能缓存和及时清理，控制内存占用
4. **进程隔离** - 独立进程避免相互影响，提高稳定性

### 通信优化

1. **队列通信** - 使用multiprocessing.Queue代替共享内存
2. **消息压缩** - 大数据块使用高效序列化
3. **超时控制** - 所有通信操作设置合理超时
4. **错误恢复** - 进程异常自动重启和状态恢复

## 系统要求

### 环境依赖

- **Python**: 3.8+ 
- **PyQt**: 5.15+
- **NumPy**: 1.19+
- **PySerial**: 3.5+
- **Pydantic**: 1.8+ (用于数据模型验证)

### 硬件要求

- **内存**: 建议4GB以上
- **处理器**: 支持多核，提升并发性能
- **串口**: USB转串口或板载串口
- **存储**: 足够空间存储测试数据

## 故障排除

### 常见问题

1. **进程启动超时**
   - 检查系统资源占用
   - 确认Python环境完整性
   - 查看日志文件获取详细错误信息

2. **设备连接失败** 
   - 验证串口号和波特率
   - 检查设备电源和连接
   - 确认串口未被其他程序占用

3. **数据丢失或错误**
   - 检查磁盘空间
   - 验证文件权限
   - 查看数据保存进程日志

### 日志系统

系统使用统一的日志配置，日志文件位于 `logs/` 目录：

- 每个进程独立记录日志
- 支持日志级别控制
- 自动日志轮转和归档

## 扩展开发

### 添加新测试类型

1. 继承 `TestStep` 基类
2. 实现必要的抽象方法
3. 在测试进程中注册新步骤类型
4. 更新工作流模型定义

### 自定义数据处理

1. 扩展数据传输进程的处理逻辑
2. 修改数据保存格式和方式
3. 添加新的数据分析功能

## 许可证

本项目采用MIT许可证，详情请查看LICENSE文件。

## 技术支持

如有问题或建议，请通过以下方式联系：

- 创建GitHub Issue
- 查看项目Wiki文档
- 联系开发团队