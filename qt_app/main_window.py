import sys
import os

from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget,
                           QVBoxLayout, QWidget, QSplitter, QLabel,
                           QStatusBar, QMessageBox, QAction, QActionGroup)
from PyQt5.QtCore import Qt, QSettings, QUrl
from PyQt5.QtGui import QIcon, QFont, QDesktopServices

# Import our custom widgets
from qt_app.widgets.device_control import DeviceControlWidget
from qt_app.widgets.test_history import TestHistoryWidget
from qt_app.widgets.overview_realtime import OverviewRealtimeWidget
from backend_device_control_pyqt.main import MedicalTestBackend

# Import translation support
from qt_app.i18n.translator import tr, _translator

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self, backend):
        super().__init__()
        self.setWindowTitle(tr("main.window_title"))
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowIcon(QIcon("my_icon.ico"))  # your_icon.ico 放在资源目录下或指定绝对路径

        # Store backend
        self.backend = backend

        # 状态标记
        self.prev_tab_index = 0  # 用于跟踪之前的标签页

        # Setup UI
        self.setup_ui()
        self.setup_menu_bar()

        # Connect language change signal
        _translator.language_changed.connect(self.update_translations)

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
        self.header = QLabel(tr("main.app_header"))
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("background-color: #f1f1f1; padding: 10px;")
        self.header.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(self.header)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.device_control = DeviceControlWidget(self.backend)
        self.test_history = TestHistoryWidget(self.backend)
        self.overview = OverviewRealtimeWidget()

        self.tab_widget.addTab(self.device_control, tr("main.tab_device_control"))
        self.tab_widget.addTab(self.test_history, tr("main.tab_test_history"))
        self.tab_widget.addTab(self.overview, tr("main.tab_overview"))

        # Wire real-time data to overview tab
        self.device_control.real_time_data.connect(self.overview.handle_real_time_data)
        self.device_control.test_started.connect(self.overview.handle_test_started)
        self.device_control.test_completed.connect(self.overview.handle_test_completed)
        self.device_control.devices_updated.connect(self.overview.update_device_list)
        # Initialize overview device list with already-detected devices on startup
        if getattr(self.device_control, "cached_devices", None):
            try:
                self.overview.update_device_list(self.device_control.cached_devices)
            except Exception:
                pass

        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("main.status_ready"))
    
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

    def setup_menu_bar(self):
        """Setup the menu bar with language selection"""
        menubar = self.menuBar()

        # Language menu (显示为中英文双语，确保任何语言下都能识别)
        language_menu = menubar.addMenu("Language / 语言")

        # Create action group for exclusive selection
        language_group = QActionGroup(self)
        language_group.setExclusive(True)

        # Add language options
        for locale, display_name in _translator.get_available_languages().items():
            action = QAction(display_name, self, checkable=True)
            action.setData(locale)

            # Check current language
            if locale == _translator.get_current_language():
                action.setChecked(True)

            # Connect to language change handler
            action.triggered.connect(lambda checked, l=locale: _translator.set_language(l))

            language_group.addAction(action)
            language_menu.addAction(action)

        # About menu
        self.about_menu = menubar.addMenu(tr("main.menu.about"))
        self.about_action = QAction(tr("main.menu.about"), self)
        self.about_action.triggered.connect(self.show_about_dialog)
        self.about_menu.addAction(self.about_action)

        # Help menu with documentation links
        self.help_menu = menubar.addMenu(tr("main.menu.help"))
        self.doc_action_en = QAction(tr("main.help.doc_en"), self)
        self.doc_action_en.triggered.connect(lambda: self.open_url("https://ai.feishu.cn/wiki/UrQ8w1QWlieUFSklFIuc6Whyn6c"))
        self.help_menu.addAction(self.doc_action_en)

        self.doc_action_zh = QAction(tr("main.help.doc_zh"), self)
        self.doc_action_zh.triggered.connect(lambda: self.open_url("https://ai.feishu.cn/wiki/BpQzwwMGIizQWXkaGRZcLipFnYb"))
        self.help_menu.addAction(self.doc_action_zh)

    def show_about_dialog(self):
        """Show developer information"""
        QMessageBox.information(
            self,
            tr("main.about.title"),
            tr("main.about.message")
        )

    def open_url(self, url: str):
        """Open a URL in the default browser."""
        QDesktopServices.openUrl(QUrl(url))

    def update_translations(self):
        """Update all UI text when language changes"""
        # Update window title and header
        self.setWindowTitle(tr("main.window_title"))
        self.header.setText(tr("main.app_header"))

        # Update tab titles
        self.tab_widget.setTabText(0, tr("main.tab_device_control"))
        self.tab_widget.setTabText(1, tr("main.tab_test_history"))
        self.tab_widget.setTabText(2, tr("main.tab_overview"))

        # Update status bar
        self.status_bar.showMessage(tr("main.status_ready"))

        # Update about menu text
        if hasattr(self, "about_menu"):
            self.about_menu.setTitle(tr("main.menu.about"))
        if hasattr(self, "about_action"):
            self.about_action.setText(tr("main.menu.about"))
        if hasattr(self, "help_menu"):
            self.help_menu.setTitle(tr("main.menu.help"))
        if hasattr(self, "doc_action_en"):
            self.doc_action_en.setText(tr("main.help.doc_en"))
        if hasattr(self, "doc_action_zh"):
            self.doc_action_zh.setText(tr("main.help.doc_zh"))

        # Notify child widgets to update their translations
        self.device_control.update_translations()
        self.test_history.update_translations()
        self.overview.update_translations()

    def closeEvent(self, event):
        """Handle window close event"""
        # Show confirmation dialog
        reply = QMessageBox.warning(
            self,
            tr("main.dialog.confirm_close.title"),
            tr("main.dialog.confirm_close.message"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Attempt to stop all active tests before shutdown
            self.stop_all_active_tests()

            # Save geometry
            self.save_geometry()
            
            # Shutdown backend
            self.backend.shutdown()
            
            # Accept the event
            event.accept()
        else:
            # Ignore the event (cancel closing)
            event.ignore()

    def stop_all_active_tests(self):
        """Send stop commands to all active tests before closing the app."""
        if not hasattr(self, "device_control") or not hasattr(self, "backend"):
            return

        active = list(getattr(self.device_control, "current_test_ids", {}).items())
        if not active:
            return

        items = [{"port": port, "test_id": test_id} for port, test_id in active]
        try:
            results = self.backend.stop_tests(items, timeout_per_device=3.0)
            stopped = [item.get("port") for item, res in results if res.get("status") == "ok"]
            if stopped:
                logger.info(f"Stopped tests before exit: {', '.join(stopped)}")
        except Exception as exc:
            logger.error(f"Failed to stop active tests on exit: {exc}")

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
        QMessageBox.critical(None, tr("main.dialog.error"), f"{tr('main.log.backend_failed')} {str(e)}")
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
