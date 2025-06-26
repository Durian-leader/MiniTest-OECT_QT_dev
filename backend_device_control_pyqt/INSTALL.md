# 多进程OECT测试系统后端 - 安装指南

本文档提供详细的安装步骤和依赖要求，帮助您成功部署多进程OECT测试系统后端。

## 系统要求

- **操作系统**：Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **Python版本**：Python 3.8 或更高版本
- **内存要求**：至少4GB RAM（推荐8GB以上）
- **存储空间**：至少500MB可用空间

## 依赖项

主要依赖包括：

- **PyQt5** (5.15+): 用户界面框架
- **NumPy** (1.19+): 数据处理
- **PySerial** (3.5+): 串口通信
- **matplotlib** (可选): 用于数据可视化

## 安装步骤

### 1. 准备Python环境

建议使用虚拟环境隔离项目依赖：

```bash
# 创建虚拟环境
python -m venv medical_test_env

# 激活虚拟环境
# Windows
medical_test_env\Scripts\activate.bat
# Linux/macOS
source medical_test_env/bin/activate
```

### 2. 克隆或下载代码

```bash
# 使用Git克隆
git clone https://yourrepository.com/medical-test-system.git
cd medical-test-system
```

### 3. 安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt
```

如果`requirements.txt`不存在，可以手动安装主要依赖：

```bash
pip install pyqt5>=5.15.0 numpy>=1.19.0 pyserial>=3.5 matplotlib>=3.3.0
```

### 4. 系统配置

1. 创建必要的目录结构：

```bash
mkdir -p logs UserData/AutoSave
```

2. 检查串口权限（仅Linux/macOS）：

```bash
# Linux系统确保当前用户在dialout组中
sudo usermod -a -G dialout $USER
# 需要注销后重新登录才能生效
```

### 5. 验证安装

运行测试脚本验证安装是否成功：

```bash
python -m backend_device_control_pyqt.test.verify_installation
```

如果一切正常，您将看到以下输出：

```
验证环境:
Python 版本: 3.8.x (或更高)
依赖项检查: OK
PyQt 版本: 5.15.x (或更高)
NumPy 版本: 1.19.x (或更高)
PySerial 版本: 3.5.x (或更高)
系统检查: OK
目录结构: OK
权限检查: OK

验证成功: 系统已准备就绪。
```

## 常见问题

### 串口权限错误

**症状**: `PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'`

**解决方案**: 
- Linux: 添加用户到dialout组 `sudo usermod -a -G dialout $USER`
- Windows: 确保没有其他程序占用串口
- macOS: 检查系统偏好设置中的安全性与隐私

### 无法导入PyQt5

**症状**: `ModuleNotFoundError: No module named 'PyQt5'`

**解决方案**: 重新安装PyQt5 `pip install pyqt5`

### 多进程启动失败

**症状**: `RuntimeError: 启动后端系统失败：进程准备超时`

**解决方案**: 
1. 检查系统资源占用情况
2. 增大超时时间（在`main.py`中修改）
3. 检查是否有防火墙或安全软件阻止进程通信

## 更新系统

要更新到最新版本，请执行：

```bash
# 激活虚拟环境
source medical_test_env/bin/activate  # Linux/macOS
medical_test_env\Scripts\activate.bat  # Windows

# 更新代码
git pull

# 更新依赖
pip install -r requirements.txt --upgrade
```

## 卸载

要卸载系统，只需删除项目目录和虚拟环境：

```bash
# 删除项目目录
rm -rf medical-test-system  # Linux/macOS
rmdir /S /Q medical-test-system  # Windows

# 删除虚拟环境
rm -rf medical_test_env  # Linux/macOS
rmdir /S /Q medical_test_env  # Windows
```

## 联系支持

如有安装问题，请联系：

- 技术支持邮箱: support@example.com
- 项目主页: https://yourrepository.com/medical-test-system

## 许可证

本软件依照[LICENSE](LICENSE)文件中的条款分发。