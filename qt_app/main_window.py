import sys
import os

from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, 
                           QVBoxLayout, QWidget, QSplitter, QLabel, 
                           QStatusBar, QMessageBox)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtGui import QIcon

# Import our custom widgets
from qt_app.widgets.device_control import DeviceControlWidget
from qt_app.widgets.test_history import TestHistoryWidget
from backend_device_control_pyqt.main import MedicalTestBackend

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self, backend):
        super().__init__()
        self.setWindowTitle("MiniTest-OECT 上位机")
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowIcon(QIcon("my_icon.ico"))  # your_icon.ico 放在资源目录下或指定绝对路径
        
        # Store backend
        self.backend = backend
        
        # 状态标记
        self.prev_tab_index = 0  # 用于跟踪之前的标签页
        
        # Setup UI
        self.setup_ui()
        
        # Load settings
        self.settings = QSettings("OECT", "TestApp")
        self.restore_geometry()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create header
        header = QLabel("OECT 测试上位机")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("background-color: #f1f1f1; padding: 10px;")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(header)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.device_control = DeviceControlWidget(self.backend)
        self.test_history = TestHistoryWidget(self.backend)
        
        self.tab_widget.addTab(self.device_control, "设备控制")
        self.tab_widget.addTab(self.test_history, "历史测试查看")
        
        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def on_tab_changed(self, index):
        """Handle tab change events"""
        # 切换标签页前，通知当前标签页保存状态
        if self.prev_tab_index == 0:  # 从设备控制标签页切出
            self.device_control.prepare_for_tab_change()
        
        # 切换到新标签页后，根据需要进行刷新
        if index == 0:  # Device Control tab
            # 如果从其他标签页切换到设备控制标签页，恢复状态
            if self.prev_tab_index != 0:
                self.device_control.restore_after_tab_change()
            
            # 我们避免在此处调用refresh_devices，这会导致工作流被重置
            # 只有当用户手动点击"刷新设备"按钮时才刷新设备列表
        elif index == 1:  # Test History tab
            self.test_history.refresh_devices()
        
        # 更新前一个标签页索引
        self.prev_tab_index = index
    
    def restore_geometry(self):
        """Restore window geometry from settings"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
    
    def save_geometry(self):
        """Save window geometry to settings"""
        self.settings.setValue("geometry", self.saveGeometry())
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Save geometry
        self.save_geometry()
        
        # Shutdown backend
        self.backend.shutdown()
        
        # Accept the event
        event.accept()

def exception_hook(exctype, value, traceback):
    """Custom exception hook to show error dialogs"""
    # Print the error to console
    sys.__excepthook__(exctype, value, traceback)
    
    # Show error message box
    error_msg = f"{exctype.__name__}: {value}"
    QMessageBox.critical(None, "Error", error_msg)

def main():
    """Main application entry point"""
    logger.info("应用程序启动")
    
    # Set exception hook
    sys.excepthook = exception_hook
    
    # Create application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for consistent look
    
    # Initialize backend
    try:
        backend = MedicalTestBackend()
        backend.start()
        logger.info("后端系统已启动")
    except Exception as e:
        logger.error(f"后端系统启动失败: {str(e)}")
        QMessageBox.critical(None, "错误", f"后端系统启动失败: {str(e)}")
        sys.exit(1)
    
    # Create and show main window
    window = MainWindow(backend)
    window.show()
    
    # Start application event loop
    return_code = app.exec_()
    
    # Clean up backend on exit
    try:
        backend.shutdown()
        logger.info("后端系统已关闭")
    except Exception as e:
        logger.error(f"后端系统关闭失败: {str(e)}")
    
    logger.info("应用程序退出")
    sys.exit(return_code)

if __name__ == "__main__":
    main()