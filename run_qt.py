# run_qt.py

import sys
import os, sys, PyQt5
plugin_root = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(plugin_root, "platforms")
# 设置日志等级
import logging
logging.basicConfig(level=logging.ERROR)

# 确保当前目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 启动Qt应用
from qt_app.main_window import main

if __name__ == "__main__":
    sys.exit(main())