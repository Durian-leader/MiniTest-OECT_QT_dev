# Qt Application Module

OECT测试系统的图形用户界面，基于PyQt5构建，提供设备控制、实时数据可视化、工作流编辑和历史数据分析功能。

## 系统概述

本模块是OECT测试系统的前端应用，采用模块化设计，通过与后端多进程系统通信实现完整的测试功能。应用支持多设备管理、复杂工作流编排、实时数据显示和历史数据分析。

### 核心特性

- 🎨 **现代化UI设计** - 基于PyQt5的响应式界面
- 📊 **实时数据可视化** - 使用PyQtGraph的高性能绘图
- 🔄 **设备状态管理** - 每个设备独立的配置和状态
- 🛠️ **可视化工作流编辑** - 拖拽式工作流创建
- 📈 **历史数据分析** - 高级排序和批量操作
- 💾 **状态持久化** - 自动保存用户设置和界面状态

## 架构设计

### 应用架构

```
┌─────────────────────────────────────────────┐
│                Main Window                   │
│  ┌─────────────────┬────────────────────┐  │
│  │  Device Control │  Test History       │  │
│  │                 │                     │  │
│  │  ┌──────────┐  │  ┌──────────────┐  │  │
│  │  │ Device   │  │  │ Test List    │  │  │
│  │  │ List     │  │  │              │  │  │
│  │  ├──────────┤  │  ├──────────────┤  │  │
│  │  │ Workflow │  │  │ Step List    │  │  │
│  │  │ Editor   │  │  │              │  │  │
│  │  ├──────────┤  │  ├──────────────┤  │  │
│  │  │ Realtime │  │  │ Data Plot    │  │  │
│  │  │ Plot     │  │  │              │  │  │
│  │  └──────────┘  │  └──────────────┘  │  │
│  └─────────────────┴────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 模块结构

```
qt_app/
├── main_window.py           # 主窗口和应用入口
├── widgets/                 # UI组件
│   ├── device_control.py   # 设备控制界面
│   ├── test_history.py     # 历史数据界面
│   ├── realtime_plot.py    # 实时绘图组件
│   ├── workflow_editor.py  # 工作流编辑器
│   ├── step_node.py        # 工作流步骤节点
│   ├── step_params_form.py # 参数输入表单
│   └── custom_widgets.py   # 自定义控件
├── utils/                   # 工具函数
│   └── decoder.py          # 数据解码器
└── styles/                  # 样式表（如有）
```

## 核心组件

### 1. 主窗口 (main_window.py)

应用程序的主入口和协调器：

```python
from qt_app.main_window import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()
```

**主要功能**：
- 标签页管理（设备控制、历史测试）
- 后端系统初始化和管理
- 应用设置持久化
- 全局异常处理

### 2. 设备控制 (device_control.py)

核心测试控制界面，管理设备连接和测试执行：

**功能特点**：
- **多设备管理**: 支持多个设备同时连接，按字母顺序显示
- **独立状态**: 每个设备维护独立的测试信息和工作流
- **测试信息**: 包含名称、描述、芯片ID、设备编号等元数据
- **工作流集成**: 内嵌工作流编辑器，支持导入/导出
- **实时监控**: 集成实时数据绘图和状态显示

**界面布局**：
```
[设备列表] | [工作流配置] | [实时绘图]
   30%     |     35%      |    35%
```

### 3. 实时绘图 (realtime_plot.py)

高性能实时数据可视化组件：

**支持的绘图模式**：
- **传输特性**: 单曲线 (Vg vs Id)
- **瞬态特性**: 单曲线 (Time vs Id)
- **输出特性**: 多曲线 (Vd vs Id @ 不同Vg)

**性能优化**：
- 循环缓冲区（默认10,000点）
- 内存保护机制
- 步骤间自动清理
- 高效的NumPy数据处理

**控制选项**：
```python
# 显示控制
show_data_points: bool  # 显示数据点
time_window: bool       # 时间窗口模式
memory_protection: bool # 内存保护
```

### 4. 测试历史 (test_history.py)

历史数据管理和分析界面：

**高级排序系统**：
- 6种排序标准：时间、名称、设备、芯片ID、设备编号、描述
- 拖拽式排序块重排
- 点击切换升序/降序
- 视觉反馈（蓝色升序、橙色降序）

**批量操作**：
- 多选支持（Ctrl/Shift）
- 批量导出到指定目录
- 批量删除（带确认）
- 数据完整性保护

### 5. 工作流编辑器 (workflow_editor.py)

可视化工作流创建和编辑：

**工作流结构**：
```python
workflow = {
    "steps": [
        {"type": "transfer", "params": {...}},
        {"type": "loop", "iterations": 3, "steps": [
            {"type": "transient", "params": {...}},
            {"type": "output", "params": {...}}
        ]}
    ]
}
```

**功能特性**：
- 拖拽重排步骤
- 嵌套循环支持
- 折叠/展开界面
- 参数预览显示
- 状态持久化

### 6. 步骤节点 (step_node.py)

单个工作流步骤的可视化表示：

**支持的步骤类型**：
- **Transfer**: 传输特性测试
- **Transient**: 瞬态特性测试
- **Output**: 输出特性测试
- **Loop**: 循环容器（可嵌套）

**交互特性**：
- 点击折叠/展开
- 拖拽重排（同级别内）
- 参数实时预览
- 删除确认对话框

### 7. 参数表单 (step_params_form.py)

动态参数输入表单生成：

**传输特性参数**：
```python
gate_start: float      # 起始栅压 (V)
gate_end: float        # 结束栅压 (V)
gate_points: int       # 测量点数
drain_voltage: float   # 漏极电压 (V)
sampling_rate: float   # 采样率 (Hz)
is_sweep: bool         # 是否往返扫描
```

**瞬态特性参数**：
```python
gate_voltage: float    # 栅极电压 (V)
drain_voltage: float   # 漏极电压 (V)
measurement_time: float # 测量时间 (s)
sampling_rate: float   # 采样率 (Hz)
cycle_times: int       # 循环次数
```

**输出特性参数**：
```python
gate_voltages: List[float] # 栅压列表 (V)
drain_start: float     # 漏压起始 (V)
drain_end: float       # 漏压结束 (V)
drain_points: int      # 测量点数
sampling_rate: float   # 采样率 (Hz)
```

## 数据流

### 实时数据流程

```
后端系统 → 设备控制 → 实时绘图
    ↓         ↓
消息解析 → 数据解码 → 曲线更新
```

### 消息处理

```python
# 测试数据消息
{
    "type": "test_data",
    "test_id": "xxx",
    "step_type": "transfer",
    "data": "FF01...",  # 十六进制数据
    "workflow_info": {
        "path": ["Root", "Loop_1", "Step_2"],
        "step_index": 2,
        "total_steps": 5
    }
}

# 进度消息
{
    "type": "test_progress",
    "progress": 0.65,
    "test_id": "xxx"
}

# 测试结果
{
    "type": "test_result",
    "status": "completed",
    "info": {...}
}
```

## 数据解码

### 解码工具 (utils/decoder.py)

处理原始设备数据的转换：

**数据格式**：
- **传输/输出**: 5字节数据包
- **瞬态**: 7字节数据包
- **偏置校正**: -1.2868e-06 A

**结束序列**：
- 传输: `FFFFFFFFFFFFFFFF`
- 瞬态: `FEFEFEFEFEFEFEFE`
- 输出: `CDABEFCDABEFCDAB`

## 状态管理

### 设备独立状态

每个设备维护独立的：
- 测试信息（名称、描述、芯片ID等）
- 工作流配置
- 运行状态
- 历史数据

### UI状态持久化

- 窗口几何尺寸
- 分割器位置
- 折叠状态
- 排序偏好
- 显示选项

## 样式和主题

### 自定义样式

应用使用内联样式和样式表定义UI外观：

```python
# 设备列表项样式
NORMAL_STYLE = "background-color: #2b2b2b; color: white;"
SELECTED_STYLE = "background-color: #0d47a1; color: white;"
RUNNING_STYLE = "background-color: #1b5e20; color: white;"
```

### 颜色方案

- 背景: `#2b2b2b` (深灰)
- 选中: `#0d47a1` (蓝色)
- 运行: `#1b5e20` (绿色)
- 升序: `#2196f3` (亮蓝)
- 降序: `#ff9800` (橙色)

## 使用示例

### 基础使用

```python
import sys
from PyQt5.QtWidgets import QApplication
from qt_app.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("OECT测试系统")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
```

### 自定义集成

```python
# 创建独立的设备控制组件
from qt_app.widgets.device_control import DeviceControlWidget

widget = DeviceControlWidget(backend)
widget.show()

# 监听测试完成
widget.test_completed.connect(on_test_complete)
```

## 依赖要求

```
PyQt5>=5.15.0          # GUI框架
pyqtgraph>=0.12.0      # 高性能绘图
numpy>=1.19.0          # 数值计算
```

## 性能优化

### 绘图优化
- 使用PyQtGraph代替matplotlib
- 批量更新数据点
- 限制最大数据点数
- 步骤间清理内存

### UI响应优化
- 异步后端通信
- 定时器批量更新
- 延迟加载大数据
- 虚拟化长列表

## 故障排除

### 常见问题

**界面无响应**
- 检查后端进程状态
- 验证消息队列连接
- 查看日志错误信息

**绘图性能差**
- 启用内存保护
- 减少显示数据点
- 调整更新频率

**设备未显示**
- 验证串口权限
- 检查设备连接
- 刷新设备列表

## 开发指南

### 添加新组件

1. 在`widgets/`创建新文件
2. 继承适当的Qt基类
3. 实现必要的信号槽
4. 在主窗口集成

### 修改数据处理

1. 更新`decoder.py`解码逻辑
2. 修改绘图组件数据接收
3. 调整消息处理流程

### 自定义样式

1. 修改组件内联样式
2. 或创建`styles/`样式表
3. 应用到相应组件

## 许可证

本项目为专有软件，版权所有。

## 技术支持

如有问题或需要帮助，请联系开发团队。