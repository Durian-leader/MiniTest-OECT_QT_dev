# run_qt.py
import os
import sys
import multiprocessing as mp
import logging
from logger_config import log_manager, get_module_logger
log_manager.set_levels(
    file_level=logging.WARNING,    # 文件记录详细信息
    console_level=logging.WARNING   # 控制台只显示重要信息
)
logger = get_module_logger()

def _setup_qt_plugin_path() -> None:
    """确保打包后 Qt 找得到 platform plugins。"""
    import PyQt5  # 延迟到函数里再 import，防止子进程重复做 GUI 初始化
    plugin_root = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(plugin_root, "platforms")


def _bootstrap():
    """真正的入口：只在主进程里执行一次。"""
    _setup_qt_plugin_path()

    # 延迟导入你的 GUI 代码，避免子进程导入时又启动窗口
    from qt_app.main_window import main as qt_main

    sys.exit(qt_main())


if __name__ == "__main__":
    # —— 1. Finder 双击时把 CWD 改到 .app/Contents/MacOS —— #
    if getattr(sys, 'frozen', False) and sys.platform == "darwin":
        bundle_dir = os.path.dirname(sys.executable)
        os.chdir(bundle_dir)              # 设为工作目录，防止找不到相对路径资源

        # —— 2. 告诉 multiprocessing：用当前 *冻结* 可执行文件做子进程 —— #
        mp.set_executable(sys.executable)  # 关键！否则 Finder 环境下会指向 /usr/bin/python
    mp.freeze_support()                           # ⭐ 关键：给 PyInstaller 子进程“解锁”
    _set_start_method = getattr(mp, "set_start_method", None)
    if _set_start_method is not None:
        _set_start_method("spawn", force=True)
    _bootstrap()
"""
pyinstaller --windowed --icon=my_icon.icns \
  --add-data "/Users/xxx/.venv/lib/python3.11/site-packages/PyQt5/Qt5/plugins/platforms:PyQt5/Qt/plugins/platforms" \
  run_qt_for_macapp.py
"""

