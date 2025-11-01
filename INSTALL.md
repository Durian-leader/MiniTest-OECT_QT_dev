# MiniTest-OECT 安装指南

## 目录

- [系统要求](#系统要求)
- [安装步骤](#安装步骤)
  - [Windows安装](#windows安装)
  - [macOS安装](#macos安装)
  - [Linux安装](#linux安装)
- [从源码运行](#从源码运行)
- [打包为可执行文件](#打包为可执行文件)
- [硬件配置](#硬件配置)
- [常见问题](#常见问题)
- [卸载](#卸载)

## 系统要求

### 最低配置
- **操作系统**: Windows 10, macOS 10.14, Ubuntu 20.04
- **Python**: 3.8 或更高版本
- **内存**: 4GB RAM
- **存储**: 500MB 可用空间
- **显示**: 1280x800 分辨率

### 推荐配置
- **操作系统**: Windows 11, macOS 12+, Ubuntu 22.04
- **Python**: 3.10 或更高版本
- **内存**: 8GB RAM
- **存储**: 2GB 可用空间
- **显示**: 1920x1080 分辨率

## 安装步骤

### Windows安装

#### 方法一：使用预编译版本（推荐）

1. 从 [Releases](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/releases) 下载最新的 `.exe` 文件
2. 双击运行即可，无需安装Python

#### 方法二：从源码安装

1. **安装Python**
   ```powershell
   # 从 python.org 下载并安装Python 3.8+
   # 确保勾选"Add Python to PATH"选项
   ```

2. **安装Git**（可选）
   ```powershell
   winget install Git.Git
   ```

3. **克隆仓库**
   ```powershell
   git clone https://github.com/Durian-leader/MiniTest-OECT_QT_dev.git
   cd MiniTest-OECT_QT_dev
   ```
   
   或者直接下载ZIP文件并解压

4. **创建虚拟环境**（推荐）
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

5. **安装依赖**
   ```powershell
   pip install -r requirements.txt
   ```

6. **安装串口驱动**
   - CH340驱动: [下载链接](http://www.wch.cn/downloads/CH341SER_EXE.html)
   - CP2102驱动: [下载链接](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)

7. **运行程序**
   ```powershell
   python run_qt.py
   ```

### macOS安装

#### 方法一：使用预编译版本

1. 从 [Releases](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/releases) 下载 `.dmg` 文件
2. 打开DMG文件，将应用拖到Applications文件夹
3. 首次运行时，右键点击应用选择"打开"以绕过Gatekeeper

#### 方法二：从源码安装

1. **安装Homebrew**（如未安装）
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **安装Python和Git**
   ```bash
   brew install python@3.10 git
   ```

3. **克隆仓库**
   ```bash
   git clone https://github.com/Durian-leader/MiniTest-OECT_QT_dev.git
   cd MiniTest-OECT_QT_dev
   ```

4. **创建虚拟环境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

6. **安装串口驱动**
   - 大多数USB串口芯片在macOS上自动识别
   - 如需CH340驱动: [下载链接](http://www.wch.cn/downloads/CH341SER_MAC_ZIP.html)

7. **运行程序**
   ```bash
   python run_qt_for_macapp.py
   ```

### Linux安装

#### Ubuntu/Debian

1. **安装系统依赖**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv python3-dev
   sudo apt install git build-essential
   ```

2. **安装Qt依赖**
   ```bash
   sudo apt install python3-pyqt5 pyqt5-dev-tools
   sudo apt install libxcb-xinerama0 libxcb-icccm4 libxcb-image0
   ```

3. **克隆仓库**
   ```bash
   git clone https://github.com/Durian-leader/MiniTest-OECT_QT_dev.git
   cd MiniTest-OECT_QT_dev
   ```

4. **创建虚拟环境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

6. **配置串口权限**
   ```bash
   # 将用户添加到dialout组
   sudo usermod -a -G dialout $USER
   # 需要重新登录生效
   ```

7. **运行程序**
   ```bash
   python run_qt.py
   ```

#### Fedora/RHEL

```bash
sudo dnf install python3-pip python3-devel
sudo dnf install python3-qt5 python3-qt5-devel
# 其他步骤同Ubuntu
```

#### Arch Linux

```bash
sudo pacman -S python python-pip python-pyqt5
sudo pacman -S base-devel git
# 其他步骤同Ubuntu
```

## 从源码运行

### 开发模式运行

```bash
# 激活虚拟环境
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 运行程序
python run_qt.py
```

### 调试模式运行

```bash
# 设置日志级别为DEBUG
python run_qt.py --debug

# 或修改logger_config.py中的默认级别
```

## 打包为可执行文件

### Windows打包

1. **安装PyInstaller**
   ```powershell
   pip install pyinstaller
   ```

2. **使用spec文件打包**
   ```powershell
   pyinstaller run_qt_for_exe.spec
   ```

3. **或手动打包**
   ```powershell
   pyinstaller --onefile --windowed --icon=my_icon.ico run_qt_for_exe.py
   ```

4. **输出位置**
   - 可执行文件在 `dist/` 目录

### macOS打包

1. **安装PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **使用spec文件打包**
   ```bash
   pyinstaller run_qt_for_macapp.spec
   ```

3. **创建DMG**（可选）
   ```bash
   # 使用create-dmg工具
   brew install create-dmg
   create-dmg \
     --volname "MiniTest-OECT" \
     --window-pos 200 120 \
     --window-size 600 400 \
     --icon-size 100 \
     --app-drop-link 450 185 \
     "MiniTest-OECT.dmg" \
     "dist/MiniTest-OECT.app"
   ```

### Linux打包

```bash
# 创建AppImage
pip install pyinstaller
pyinstaller --onefile run_qt.py

# 或使用系统包管理器创建deb/rpm包
```

## 硬件配置

### 串口设备识别

1. **Windows**
   - 打开设备管理器
   - 查看"端口(COM和LPT)"
   - 记录COM端口号（如COM3）

2. **macOS**
   ```bash
   ls /dev/tty.usb*
   # 或
   ls /dev/cu.*
   ```

3. **Linux**
   ```bash
   ls /dev/ttyUSB*
   # 或
   ls /dev/ttyACM*
   ```

### 波特率设置

默认波特率：512000
如需修改，在设备连接时指定：
- 支持的波特率：9600, 19200, 38400, 57600, 115200, 230400, 460800, 512000, 921600

## 常见问题

### Q1: ImportError: No module named 'PyQt5'

**解决方案**：
```bash
pip install --upgrade PyQt5
```

### Q2: 串口权限被拒绝（Linux）

**解决方案**：
```bash
sudo usermod -a -G dialout $USER
# 重新登录后生效
```

### Q3: Windows防火墙警告

**解决方案**：
- 允许程序通过防火墙
- 或添加防火墙例外规则

### Q4: macOS无法打开应用（未识别的开发者）

**解决方案**：
```bash
# 方法1：右键点击应用，选择"打开"
# 方法2：系统偏好设置 > 安全性与隐私 > 允许打开

# 方法3：命令行
xattr -cr /Applications/MiniTest-OECT.app
```

### Q5: 找不到设备

**解决方案**：
1. 检查USB连接
2. 安装正确的串口驱动
3. 确认设备电源开启
4. 检查串口权限（Linux/macOS）

### Q6: PyInstaller打包失败

**解决方案**：
```bash
# 清理缓存
pyinstaller --clean run_qt_for_exe.spec

# 或手动删除build和dist目录
rm -rf build dist
```

### Q7: 程序启动缓慢

**解决方案**：
- 使用SSD硬盘
- 关闭杀毒软件实时扫描
- 预编译Python文件：`python -m compileall .`

## 环境变量配置

### 可选环境变量

```bash
# 设置日志级别
export OECT_LOG_LEVEL=DEBUG

# 设置数据目录
export OECT_DATA_DIR=/path/to/data

# 设置默认串口
export OECT_DEFAULT_PORT=COM3  # Windows
export OECT_DEFAULT_PORT=/dev/ttyUSB0  # Linux
```

## 更新升级

### 从Git更新

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 备份数据

更新前建议备份：
- `UserData/` 目录（测试数据）
- 导出的工作流配置文件

## 卸载

### Windows
1. 删除程序文件夹
2. 删除 `%APPDATA%\OECT` 目录（可选）

### macOS
1. 将应用从Applications拖到垃圾桶
2. 删除 `~/Library/Preferences/com.oect.*` 文件（可选）
3. 删除 `~/Library/Application Support/OECT/` 目录（可选）

### Linux
1. 删除程序文件夹
2. 删除 `~/.config/OECT/` 目录（可选）

### 清理Python虚拟环境

```bash
# Windows
rmdir /s venv

# macOS/Linux
rm -rf venv
```

## 获取帮助

- 查看日志：`logs/` 目录
- GitHub Issues: [问题反馈](https://github.com/Durian-leader/MiniTest-OECT_QT_dev/issues)
- 文档：[CLAUDE.md](CLAUDE.md) 和 [README.md](README.md)
- 作者：lidonghao
- 邮箱：lidonghao100@outlook.com

## 许可证

本软件基于MIT许可证发布。详见 [LICENSE](LICENSE) 文件。