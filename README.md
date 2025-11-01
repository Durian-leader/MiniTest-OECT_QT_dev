# MiniTest-OECT 测试系统

<p align="center">
  <img src="my_icon.ico" alt="MiniTest-OECT Logo" width="128"/>
</p>

## 📋 项目简介

MiniTest-OECT 是一款专业的有机电化学晶体管（OECT）电学特性测试软件，为科研人员提供高效、稳定的器件测试解决方案。系统采用多进程架构设计，支持高速数据采集、实时可视化和复杂测试工作流编排。

### 主要特性

- 🚀 **高性能采集**: 支持1000+点/秒的高速数据采集
- 📊 **实时可视化**: 基于pyqtgraph的高性能实时绘图
- 🔄 **工作流编排**: 可视化工作流编辑器，支持循环和嵌套结构
- 🔗 **同步执行**: 支持多设备同步测试，步骤级精确同步
- 💾 **数据管理**: 自动保存测试数据，支持CSV导出和历史查看
- 🖥️ **跨平台支持**: Windows、macOS、Linux全平台兼容
- 🔧 **模块化设计**: 易于扩展新的测试类型和功能

## 🎯 支持的测试类型

### Transfer特性测试（转移特性）
- 栅极电压扫描测量漏极电流
- 支持单向扫描和往返扫描
- 输出数据：Vg-Id曲线

### Transient特性测试（瞬态响应）
- 时域响应特性测量
- 支持多周期循环测试
- 输出数据：Time-Id曲线

### Output特性测试（输出特性）
- 多栅压条件下的I-V特性曲线
- 支持多组栅压同时测量
- 输出数据：Vd-Id曲线族

## 🛠️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     PyQt5 用户界面                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  设备控制     │  │  实时绘图     │  │  历史查看     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                     多进程后端系统                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   测试进程    │→│  数据传输进程  │→│  数据保存进程  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                     硬件设备层                           │
│              串口通信 (512000 baud)                      │
└─────────────────────────────────────────────────────────┘
```

## 📦 快速开始

### 系统要求

- Python 3.8 或更高版本
- Windows 10/11, macOS 10.14+, Ubuntu 20.04+
- 至少4GB内存
- USB串口驱动（CH340/CP2102等）

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/Durian-leader/MiniTest-OECT_QT_dev.git
cd MiniTest-OECT_QT_dev
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **运行程序**
```bash
python run_qt.py
```

详细安装说明请参见 [INSTALL.md](INSTALL.md)

## 💻 使用指南

### 基本工作流程

1. **连接设备**: 启动程序后，系统自动扫描可用设备
2. **选择设备**: 从设备列表选择要测试的设备
3. **配置测试**: 
   - 输入测试信息（名称、描述、芯片ID、器件编号）
   - 使用工作流编辑器配置测试步骤
4. **开始测试**: 点击"开始测试"按钮
5. **查看结果**: 
   - 实时查看测试曲线
   - 测试完成后在"历史测试"标签页查看和导出数据

### 工作流编辑器

- **添加步骤**: 点击"添加步骤"按钮选择测试类型
- **配置参数**: 点击步骤卡片配置具体参数
- **拖拽排序**: 支持拖拽调整步骤顺序
- **循环结构**: 添加Loop步骤实现重复测试
- **同步执行**: 勾选"所有设备同步执行工作流"实现多设备步骤级同步测试
  - 所有设备使用相同工作流配置
  - 每个步骤等待所有设备就绪后同时开始
  - 步骤完成后等待所有设备完成才进入下一步
  - 测试信息（名称、描述等）各设备独立维护
- **导入/导出**: 支持工作流配置的保存和共享

### 同步测试模式

实现多个设备的精确同步测试：

1. **启用同步模式**: 勾选"所有设备同步执行工作流"复选框
2. **配置工作流**: 编辑工作流步骤（所有设备将使用相同配置）
3. **设置设备信息**: 切换不同设备，分别设置测试信息（可选）
4. **启动同步测试**: 点击"开始测试"，所有连接的设备将：
   - 同时开始每个测试步骤
   - 等待所有设备完成当前步骤
   - 同步进入下一个步骤
5. **查看结果**: 每个设备的数据独立保存和显示

### 数据管理

测试数据自动保存在 `UserData/AutoSave/{设备ID}/` 目录下：
- `test_info.json`: 测试元数据
- `workflow.json`: 工作流配置
- `*.csv`: 测试数据文件

## 🔨 开发者指南

### 项目结构

```
MiniTest-OECT_QT_dev/
├── qt_app/                      # PyQt5前端应用
│   ├── main_window.py          # 主窗口
│   └── widgets/                # UI组件
├── backend_device_control_pyqt/ # 后端系统
│   ├── main.py                 # 后端入口
│   ├── processes/              # 多进程实现
│   ├── core/                   # 核心功能
│   └── test/                   # 测试类型实现
├── UserData/                   # 用户数据
├── logs/                       # 日志文件
└── requirements.txt            # 依赖列表
```

### 扩展新测试类型

1. 在 `backend_device_control_pyqt/test/` 创建新的测试步骤类
2. 在 `backend_device_control_pyqt/core/command_gen.py` 添加命令生成函数
3. 更新UI组件以支持新测试类型
4. 在测试进程中注册新测试类型

### 📚 详细文档

- **主项目开发指南**: [CLAUDE.md](CLAUDE.md) - Claude Code AI开发助手指南
- **前端模块文档**: 
  - [qt_app/README.md](qt_app/README.md) - Qt前端详细说明
  - [qt_app/CLAUDE.md](qt_app/CLAUDE.md) - Qt前端AI开发指南
- **后端模块文档**: 
  - [backend_device_control_pyqt/README.md](backend_device_control_pyqt/README.md) - 后端系统详细说明
  - [backend_device_control_pyqt/CLAUDE.md](backend_device_control_pyqt/CLAUDE.md) - 后端系统AI开发指南

## 📊 性能指标

- **数据采集速率**: 1000+ 点/秒
- **实时绘图刷新**: 20-100 FPS
- **内存占用**: < 500MB（典型使用）
- **启动时间**: < 3秒
- **文件I/O**: 10MB/s

## 🐛 问题反馈

如遇到问题，请通过以下方式反馈：

1. 查看 `logs/` 目录下的日志文件
2. 在 [GitHub Issues](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/issues) 提交问题
3. 提供以下信息：
   - 操作系统版本
   - Python版本
   - 错误日志
   - 复现步骤

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📮 联系方式

- 项目主页: [GitHub](https://github.com/Durian-leader/MiniTest-OECT_QT_dev)
- 问题反馈: [Issues](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/issues)
- 作者: lidonghao
- 邮箱: lidonghao100@outlook.com

## 🙏 致谢

感谢所有为本项目做出贡献的开发者和用户！

特别感谢以下开源项目：
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- [pyqtgraph](http://www.pyqtgraph.org/)
- [NumPy](https://numpy.org/)
- [pySerial](https://github.com/pyserial/pyserial)

---

**版本**: 1.1.0 | **更新日期**: 2025-08-08