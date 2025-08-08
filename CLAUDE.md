# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供项目开发指导。

## 项目概述

MiniTest-OECT 是一个用于有机电化学晶体管 (OECT) 电学特性测试的专业测试系统。采用 PyQt5 + 多进程架构，支持高速数据采集、实时可视化和复杂工作流编排。

## 系统架构

### 多进程设计
```
Qt进程 (UI) ↔ 测试进程 ↔ 数据传输进程 ↔ 数据保存进程
```

**进程职责：**
- **Qt进程**: PyQt5界面、实时绘图、用户交互
- **测试进程**: 设备通信、测试执行、工作流控制
- **数据传输进程**: 数据路由、批处理、格式转换
- **数据保存进程**: 文件I/O、CSV/JSON持久化

### 目录结构
```
MiniTest-OECT_QT_dev/
├── qt_app/                      # PyQt5前端
│   ├── main_window.py          # 主窗口
│   └── widgets/                # UI组件
│       ├── device_control.py   # 设备控制
│       ├── test_history.py     # 历史查看
│       ├── realtime_plot.py    # 实时绘图
│       └── workflow_editor.py  # 工作流编辑
├── backend_device_control_pyqt/  # 后端系统
│   ├── main.py                 # 后端入口
│   ├── processes/              # 进程实现
│   ├── core/                   # 核心功能
│   └── test/                   # 测试类型
├── UserData/AutoSave/          # 测试数据
├── logs/                       # 日志文件
└── logger_config.py            # 日志配置
```

## 开发命令

### 运行应用
```bash
# 开发模式 - 从源码运行
python run_qt.py

# 生产模式 - 打包版本
python run_qt_for_exe.py

# macOS版本
python run_qt_for_macapp.py
```

### 构建可执行文件
```bash
# Windows可执行文件
pyinstaller run_qt_for_exe.spec

# macOS应用包
pyinstaller run_qt_for_macapp.spec

# 单文件打包
pyinstaller --onefile --windowed --icon=my_icon.ico run_qt_for_exe.py
```

### 测试和调试
```bash
# 查看日志文件
tail -f logs/qt_app.main_window.log
tail -f logs/backend_device_control_pyqt.main.log

# 调整日志级别（在logger_config.py中）
log_manager.set_levels(
    file_level=logging.DEBUG,     # 文件详细日志
    console_level=logging.WARNING  # 控制台简洁输出
)
```

## 核心功能模块

### 测试类型

#### Transfer测试（转移特性）
- **用途**: 测量栅极电压扫描下的漏极电流
- **数据格式**: CSV (Vg, Id)
- **关键参数**: gateVoltageStart/End/Step, drainVoltage
- **实现**: `backend_device_control_pyqt/test/transfer_step.py`

#### Transient测试（瞬态响应）
- **用途**: 测量时域响应特性
- **数据格式**: CSV (Time, Id)
- **关键参数**: bottomTime, topTime, gateVoltageBottom/Top, cycles
- **实现**: `backend_device_control_pyqt/test/transient_step.py`

#### Output测试（输出特性）
- **用途**: 多栅压下的I-V曲线
- **数据格式**: CSV (Vd, Id_Vg1, Id_Vg2, ...)
- **关键参数**: drainVoltageStart/End/Step, gateVoltage
- **实现**: `backend_device_control_pyqt/test/output_step.py`

### 设备通信

#### 串口协议
- **波特率**: 512000（默认）
- **数据格式**: TLV协议（Type-Length-Value）
- **命令结构**: `[0xFF][Type][Length][Value][0xFE]`
- **16字节前缀**: 用于对齐和同步
- **结束序列**: 每种测试类型特定的结束标记

#### 异步通信
```python
# backend_device_control_pyqt/core/async_serial.py
async def send_and_receive_command(
    command: str,
    end_sequences: Dict[str, str],
    packet_size: int,
    data_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None
)
```

### 工作流系统

#### 工作流结构
```python
workflow = {
    "steps": [
        {"type": "transfer", "params": {...}},
        {"type": "loop", "iterations": 3, "steps": [
            {"type": "transient", "params": {...}}
        ]},
        {"type": "output", "params": {...}}
    ]
}
```

#### 状态管理
- 每个设备独立的测试信息
- 工作流配置按设备保存
- 支持导入/导出工作流（JSON格式）
- 导入模式：追加而非覆盖

### 数据管理

#### 文件组织
```
UserData/AutoSave/
└── {device_id}/
    └── {timestamp}_{test_type}_{test_id}/
        ├── test_info.json      # 测试元数据
        ├── workflow.json       # 工作流配置
        ├── 1_transfer.csv      # 测试数据
        └── 2_transient.csv     # 测试数据
```

#### 测试元数据
```json
{
    "test_id": "uuid",
    "test_name": "测试名称",
    "test_description": "描述",
    "chip_id": "芯片ID",
    "device_number": "器件编号",
    "device_id": "Test Unit A1",
    "timestamp": "2025-01-01 10:00:00",
    "workflow": {...}
}
```

## 常见开发任务

### 添加新测试类型

1. **创建测试步骤类**（`backend_device_control_pyqt/test/`）:
```python
from backend_device_control_pyqt.test.step import TestStep

class NewTestStep(TestStep):
    def get_step_type(self) -> str:
        return "new_test"
    
    def get_packet_size(self) -> int:
        return 5  # 数据包大小
    
    def get_end_sequence(self) -> str:
        return "FFFFFFFF"  # 结束标记
    
    async def execute(self):
        # 实现测试逻辑
        pass
```

2. **添加命令生成**（`backend_device_control_pyqt/core/command_gen.py`）:
```python
def gen_new_test_cmd(params):
    # 生成TLV格式命令
    return command_bytes
```

3. **更新UI组件**:
   - `qt_app/widgets/step_params_form.py`: 添加参数表单
   - `qt_app/widgets/step_node.py`: 更新步骤类型下拉框
   - `qt_app/widgets/realtime_plot.py`: 处理新数据类型

4. **注册到测试进程**（`backend_device_control_pyqt/processes/test_process.py`）

### 修改UI界面

#### 添加新标签页
```python
# qt_app/main_window.py
def setup_ui(self):
    self.new_widget = NewWidget(self.backend)
    self.tab_widget.addTab(self.new_widget, "新功能")
```

#### 自定义控件样式
```python
widget.setStyleSheet("""
    QWidget {
        background-color: #2b2b2b;
        color: white;
    }
    QPushButton:hover {
        background-color: #424242;
    }
""")
```

### 性能优化

#### 数据处理优化
```python
# backend_device_control_pyqt/processes/data_transmission_process.py
DATA_BATCH_SIZE = 100  # 调整批处理大小
BATCH_TIMEOUT = 0.01   # 调整超时时间
```

#### 绘图性能优化
```python
# qt_app/widgets/realtime_plot.py
self.max_points = 10000     # 限制最大点数
self.update_interval = 50   # 更新间隔(ms)
```

## 调试技巧

### 启用详细日志
```python
# 在需要调试的模块中
from logger_config import get_module_logger
logger = get_module_logger()
logger.debug(f"Debug info: {data}")
```

### 监控进程通信
```python
# 查看队列状态
logger.info(f"Queue size: {queue.qsize()}")
```

### 串口调试
```python
# backend_device_control_pyqt/core/async_serial.py
logger.debug(f"TX: {command.hex()}")
logger.debug(f"RX: {data.hex()}")
```

## 性能指标

- **数据采集率**: 1000+ 点/秒
- **队列延迟**: < 10ms
- **文件写入**: 10MB/s
- **进程启动**: < 2秒
- **内存使用**: < 500MB（典型测试）

## 故障排除

### 进程启动失败
- 检查Python环境和依赖
- 查看logs/目录下的错误日志
- 确认端口权限（串口访问）

### 设备连接问题
- 验证串口驱动安装
- 检查设备电源和连接
- 确认波特率设置（512000）

### 数据丢失
- 增加批处理大小
- 调整队列超时时间
- 检查磁盘空间

### UI响应缓慢
- 减少绘图点数
- 增加更新间隔
- 启用数据抽样

## 安全注意事项

- 不记录敏感信息到日志
- 验证所有用户输入
- 文件路径防止目录遍历
- 避免使用pickle序列化

## 代码规范

- **命名**: 方法用snake_case，类用CamelCase
- **信号**: 命名为`action_performed`（过去式）
- **槽函数**: 命名为`on_action`或`handle_action`
- **私有方法**: 前缀下划线`_method_name`
- **常量**: 模块级用UPPER_CASE
- **类型提示**: 所有公共函数添加类型注解
- **文档字符串**: 所有公共方法添加docstring

## 维护注意事项

- 定期清理UserData/AutoSave/下的旧数据
- 日志文件自动轮转（5MB/文件，保留5个）
- 测试不同分辨率屏幕的UI显示
- 保持工作流格式向后兼容
- 更新依赖时注意PyQt5版本兼容性