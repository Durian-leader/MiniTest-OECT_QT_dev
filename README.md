# MiniTest-OECT 有机电化学晶体管测试系统

一个专业的OECT（有机电化学晶体管）测试系统，提供完整的设备控制、数据采集、实时可视化和数据分析功能。系统采用PyQt5前端界面和多进程后端架构，支持多设备并行测试和复杂工作流编排。

- 安装教程及使用：[INSTALL.md](INSTALL.md)

## 🌟 主要特性

### 测试功能
- 🔬 **三种测试模式**：转移特性、瞬态特性、输出特性
- 🔄 **工作流编排**：支持循环、嵌套等复杂测试序列
- 📊 **实时数据可视化**：动态图表显示测试进度和结果
- 💾 **自动数据保存**：CSV格式存储，支持批量导出
- 🎯 **多设备并发**：同时控制多台设备进行测试
- 🏷️ **样品信息管理**：支持芯片ID、器件编号等标识信息记录

### 系统架构
- 🏗️ **多进程设计**：四进程架构确保高性能和稳定性
- 🔌 **异步串口通信**：高效稳定的设备通信
- 📈 **实时数据流处理**：毫秒级数据采集和显示
- 🛡️ **进程隔离**：故障隔离，单设备故障不影响整体系统

## 📁 项目结构

```
MiniTest-OECT/
├── qt_app/                          # PyQt5前端界面
│   ├── main_window.py              # 主窗口和应用入口
│   ├── widgets/                    # UI组件
│   │   ├── device_control.py       # 设备控制界面
│   │   ├── test_history.py         # 历史测试查看
│   │   ├── realtime_plot.py        # 实时数据绘图
│   │   ├── workflow_editor.py      # 工作流编辑器
│   │   ├── step_node.py            # 测试步骤节点
│   │   ├── step_params_form.py     # 参数配置表单
│   │   └── custom_widgets.py       # 自定义UI组件
│   └── utils/                      # 工具模块
│       └── decoder.py              # 数据解码工具
├── backend_device_control_pyqt/     # 多进程后端系统
│   ├── main.py                     # 后端主控制器
│   ├── processes/                  # 进程模块
│   │   ├── test_process.py         # 测试执行进程
│   │   ├── data_transmission_process.py  # 数据传输进程
│   │   └── data_save_process.py    # 数据保存进程
│   ├── test/                       # 测试步骤实现
│   │   ├── transfer_step.py        # 转移特性测试
│   │   ├── transient_step.py       # 瞬态特性测试
│   │   ├── output_step.py          # 输出特性测试
│   │   ├── step.py                 # 测试步骤基类
│   │   └── test.py                 # 测试编排类
│   ├── core/                       # 核心功能
│   │   ├── async_serial.py         # 异步串口通信
│   │   ├── command_gen.py          # 测试命令生成
│   │   └── serial_data_parser.py   # 数据解析器
│   └── comunication/               # 通信模块
│       └── data_bridge.py          # 数据桥接层
├── run_qt.py                       # 开发环境启动脚本
├── run_qt_for_exe.py              # 打包版本启动脚本
├── requirements.txt                # 项目依赖
├── logs/                           # 日志目录
└── UserData/AutoSave/             # 测试数据存储目录
```

## 🚀 快速开始

### 环境要求

- **Python**: 3.8+
- **操作系统**: Windows 10+, macOS 10.14+, Linux
- **内存**: 建议4GB以上
- **存储**: 建议1GB以上可用空间

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone git@github.com:Durian-leader/MiniTest-OECT_QT_dev.git
   cd MiniTest-OECT
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动系统**
   ```bash
   python run_qt.py
   ```

### 首次运行

系统首次启动时会自动创建必要的目录结构：
- `logs/` - 系统日志
- `UserData/AutoSave/` - 测试数据存储

## 💡 使用指南

### 1. 设备连接

1. 连接OECT测试设备到计算机串口
2. 在"设备控制"标签页点击"刷新设备"
3. 选择对应的设备（系统会自动识别设备ID）

### 2. 配置测试

#### 转移特性测试
```
栅极电压扫描，测量漏极电流变化
• 栅压范围：-1000mV ~ 1000mV
• 漏极电压：固定值（如100mV）
• 支持正向/反向扫描
```

#### 瞬态特性测试
```
时间域响应测试
• 栅极电压脉冲：低电平 ↔ 高电平
• 时间控制：底部时间、顶部时间、循环次数
• 采样间隔：1ms ~ 10s
```

#### 输出特性测试
```
多栅极电压下的输出特性曲线族
• 栅极电压列表：如[0, 200, 400, 600, 800]mV
• 漏极电压扫描：起点、终点、步长
• 自动生成多条I-V曲线
```

### 3. 工作流编排

支持复杂的测试序列：

```json
{
  "测试步骤": [
    {
      "type": "transfer",
      "params": { "gateVoltageStart": -300, "gateVoltageEnd": 400 }
    },
    {
      "type": "loop",
      "iterations": 3,
      "steps": [
        { "type": "transient", "params": {...} },
        { "type": "output", "params": {...} }
      ]
    }
  ]
}
```

### 4. 实时监测

- **动态图表**：实时显示测试数据和进度
- **多曲线支持**：输出特性自动显示多条曲线
- **鼠标交互**：悬停显示精确坐标值
- **自动缩放**：智能调整显示范围

### 5. 历史数据分析

- **多选操作**：批量选择测试进行导出或删除
- **数据可视化**：重新绘制历史测试曲线
- **参数查看**：详细显示测试条件和参数
- **文件管理**：组织和备份测试数据

## 🔧 系统架构

### 多进程设计

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   主进程(Qt)    │───▶│    测试进程       │───▶│   数据传输进程   │───▶│   数据保存进程    │
│  PyQt5界面      │    │  设备控制        │    │  实时数据处理    │    │   文件IO操作     │
│  用户交互       │    │  测试执行        │    │  数据分发       │    │   CSV保存       │
│  实时显示       │    │  命令生成        │    │  批处理优化      │    │   数据完整性     │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────────┘
```

### 数据流

1. **命令生成** → 测试进程根据参数生成硬件命令
2. **设备通信** → 异步串口发送命令并接收原始数据
3. **数据解析** → 将原始字节流解析为电压/电流值
4. **实时传输** → 数据传输进程批处理并分发数据
5. **界面更新** → Qt进程接收数据并更新图表显示
6. **数据保存** → 数据保存进程将数据写入CSV文件

## 📊 数据格式

### 转移特性数据
```csv
Vg,Id
-0.300,1.23e-06
-0.290,1.45e-06
-0.280,1.67e-06
...
```

### 瞬态特性数据
```csv
Time,Id
0.000,1.23e-06
0.001,1.25e-06
0.002,1.27e-06
...
```

### 输出特性数据
```csv
Vd,Id(Vg=0mV),Id(Vg=200mV),Id(Vg=400mV)
0.000,1.23e-06,2.45e-06,3.67e-06
0.010,1.25e-06,2.47e-06,3.69e-06
0.020,1.27e-06,2.49e-06,3.71e-06
...
```

## 🛠️ 开发与扩展

### 添加新的测试类型

1. **创建测试步骤类**
   ```python
   from backend_device_control_pyqt.test.step import TestStep
   
   class CustomStep(TestStep):
       def get_step_type(self) -> str:
           return "custom"
       
       async def execute(self):
           # 实现测试逻辑
           pass
   ```

2. **注册到工作流系统**
   - 在`step_node.py`中添加新类型选项
   - 在`step_params_form.py`中添加参数表单
   - 在`test_process.py`中注册步骤类

### 自定义数据处理

```python
# 扩展数据解析器
from qt_app.utils.decoder import decode_bytes_to_data

def custom_data_parser(byte_data, mode='custom'):
    # 实现自定义数据解析逻辑
    return decoded_data
```

### 界面定制

- **自定义组件**：继承`QWidget`创建专用控件
- **样式修改**：通过StyleSheet调整界面外观
- **布局调整**：修改splitter比例和面板组织

## 📦 打包部署

### 创建可执行文件

```bash
# 安装打包工具
pip install pyinstaller

# 生成可执行文件
pyinstaller --onefile --windowed --icon=my_icon.ico run_qt_for_exe.py

# 输出位置：dist/run_qt_for_exe.exe
```

### 部署注意事项

- 确保目标系统安装了必要的Visual C++运行库
- 首次运行需要管理员权限（用于创建目录）
- 建议在干净的虚拟环境中测试打包结果

## 🔧 故障排除

### 常见问题

**1. 设备连接失败**
```
检查事项：
• 串口是否被其他程序占用
• 设备电源和连接线是否正常
• 波特率设置是否正确（默认512000）
```

**2. 数据显示异常**
```
解决方法：
• 检查设备固件版本
• 验证数据格式和结束序列
• 查看日志文件中的错误信息
```

**3. 进程启动超时**
```
可能原因：
• 系统资源不足
• 杀毒软件拦截
• Python环境配置问题
```

### 日志系统

系统提供详细的日志记录：

```
logs/
├── main.log              # 主程序日志
├── test_process.log      # 测试进程日志
├── data_transmission.log # 数据传输日志
├── data_save.log         # 数据保存日志
└── ...                   # 等所有文件都对应一个日志文件
```

日志级别可通过`logger_config.py`调整。

## 🎯 性能优化

### 系统调优

- **内存管理**：实时图表使用循环缓冲区，限制内存占用
- **数据处理**：批处理模式减少进程间通信开销
- **文件IO**：多线程异步写入，避免阻塞主流程
- **界面响应**：100ms定时器平衡实时性和性能

### 推荐配置

```
高性能配置：
• CPU: 4核心以上
• 内存: 8GB以上
• 存储: SSD固态硬盘
• 串口: USB 3.0转串口适配器

标准配置：
• CPU: 双核心
• 内存: 4GB
• 存储: 机械硬盘
• 串口: USB 2.0转串口适配器
```

## 📖 API参考

### 后端API

```python
from backend_device_control_pyqt.main import MedicalTestBackend

# 初始化后端
backend = MedicalTestBackend()
backend.start()

# 获取设备列表
devices = backend.list_serial_ports()

# 启动测试
result = backend.start_workflow(params)

# 获取实时数据
data = backend.get_real_time_data()

# 停止测试
backend.stop_test(test_id="test_001")

# 关闭系统
backend.shutdown()
```

### 工作流配置

```python
workflow_params = {
    "test_id": "test_001",
    "device_id": "OECT_Device_001", 
    "port": "COM3",
    "baudrate": 512000,
    "name": "综合特性测试",
    "description": "包含转移、瞬态、输出特性的完整测试",
    "steps": [
        {
            "type": "transfer",
            "command_id": 1,
            "params": {
                "gateVoltageStart": -1000,
                "gateVoltageEnd": 1000,
                "gateVoltageStep": 50,
                "drainVoltage": 100,
                "isSweep": 1
            }
        }
    ]
}
```

## 🤝 贡献指南

1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 技术支持

- **文档**：[后端文档](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/blob/main/backend_device_control_pyqt/README.md)
- **Issues**：在GitHub上提交问题报告

---

**MiniTest-OECT** - 专业的OECT测试解决方案 🧪⚡