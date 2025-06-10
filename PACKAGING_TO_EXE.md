# 打包应用程序为可执行文件 (Windows)

本文档为初学者提供将本项目打包为 `.exe` 文件的基本步骤。我们使用 [PyInstaller](https://pyinstaller.org/) 工具，它可以将 Python 程序连同依赖打包成独立的可执行文件。

## 1. 准备环境

1. 安装 Python 3.8 及以上版本，并确保已将 `python` 加入系统环境变量。
2. 打开命令行 (CMD 或 PowerShell)，切换到项目根目录，即包含 `run_qt.py` 的文件夹。
3. 建议创建并激活虚拟环境：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
4. 安装项目依赖：
   ```bash
   pip install -r requirements.txt
   ```
5. 安装 PyInstaller：
   ```bash
   pip install pyinstaller
   ```

## 2. 生成可执行文件

在项目根目录执行以下命令：
```bash
pyinstaller --noconfirm --windowed --name MedicalTestApp run_qt.py
```
- `--noconfirm`：覆盖旧的构建，无需确认。
- `--windowed`：生成无控制台窗口的 GUI 应用。
- `--name`：指定生成的 exe 文件名称。
- `run_qt.py`：程序入口脚本。

运行成功后，会在 `dist/MedicalTestApp/` 目录下看到生成的 `MedicalTestApp.exe` 以及相关库文件。

## 3. 测试和分发

1. 在 `dist/MedicalTestApp/` 中双击 `MedicalTestApp.exe`，确认程序能够正常启动。
2. 将整个 `dist/MedicalTestApp/` 文件夹打包 (如压缩为 zip) 后即可分发给其他用户。

## 4. 常见问题

- **运行时提示缺失 Qt 插件**：确保 `run_qt.py` 中设置的 `QT_QPA_PLATFORM_PLUGIN_PATH` 正确，且 `dist` 目录下的 `platforms/` 文件夹完整。
- **杀毒软件报毒**：由于 exe 是从脚本打包而来，某些杀毒软件可能会误报。可尝试在可信目录运行或添加白名单。
- **体积较大**：PyInstaller 会打包 Python 解释器及所有依赖，体积通常在数百 MB 属正常现象。

按照以上步骤即可在 Windows 平台生成可执行文件并进行分发。如果需要在其他系统上创建可执行文件，请在对应系统上运行 PyInstaller 生成。 
