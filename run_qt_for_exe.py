# run_qt.py
import os
import sys
import logging
import multiprocessing as mp

logging.basicConfig(level=logging.DEBUG)      # 全局日志控制

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
    mp.freeze_support()                           # ⭐ 关键：给 PyInstaller 子进程“解锁”
    _bootstrap()

# pyinstaller --onefile --windowed --noconfirm run_qt_for_exe.py
# pyinstaller --onefile --windowed --icon=my_icon.ico --add-data="my_icon.ico;." run_qt_for_exe.py
