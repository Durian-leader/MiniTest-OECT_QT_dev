"""
主窗口 - main_window.py
单设备OECT测试上位机主界面
"""

import asyncio
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QStatusBar, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from ui.config_panel import ConfigPanel
from ui.realtime_plot import RealtimePlotWidget
from test_runner import TestRunner


class IdentifyWorker(QThread):
    """设备识别工作线程"""
    result_ready = pyqtSignal(str)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
    
    def run(self):
        asyncio.run(self._query())
    
    async def _query(self):
        from core.serial_device import AsyncSerialDevice
        device = AsyncSerialDevice(port=self.port)
        try:
            if await device.connect():
                name = await device.query_device_identity(timeout=3.0)
                await device.disconnect()
                self.result_ready.emit(name)
            else:
                self.result_ready.emit("连接失败")
        except Exception as e:
            self.result_ready.emit(f"错误: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.test_runner = None
        self.identify_worker = None
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("单设备OECT瞬态测试 (Loop + Transient)")
        self.setGeometry(100, 100, 1200, 700)
        
        # 中心Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧配置面板
        self.config_panel = ConfigPanel()
        self.config_panel.setMaximumWidth(350)
        self.config_panel.setMinimumWidth(280)
        splitter.addWidget(self.config_panel)
        
        # 右侧绘图区域
        self.plot_widget = RealtimePlotWidget()
        splitter.addWidget(self.plot_widget)
        
        # 设置分割比例
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # 状态栏左侧标签
        self.status_label = QLabel("就绪")
        self.statusBar.addWidget(self.status_label)
        
        # 状态栏右侧进度标签
        self.progress_label = QLabel("")
        self.statusBar.addPermanentWidget(self.progress_label)
        
        # 状态栏右侧字节数标签
        self.bytes_label = QLabel("")
        self.statusBar.addPermanentWidget(self.bytes_label)
    
    def connect_signals(self):
        """连接信号"""
        self.config_panel.start_requested.connect(self.start_test)
        self.config_panel.stop_requested.connect(self.stop_test)
        self.config_panel.identify_requested.connect(self.identify_device)
    
    def identify_device(self, port: str):
        """识别设备"""
        self.identify_worker = IdentifyWorker(port)
        self.identify_worker.result_ready.connect(self._on_identify_result)
        self.identify_worker.start()
    
    def _on_identify_result(self, name: str):
        """处理设备识别结果"""
        self.config_panel.set_device_name(name)
    
    def start_test(self):
        """开始测试"""
        # 检查串口
        port = self.config_panel.get_selected_port()
        if not port:
            QMessageBox.warning(self, "警告", "请选择串口")
            return
        
        # 检查保存路径
        save_path = self.config_panel.get_save_path()
        if not save_path:
            QMessageBox.warning(self, "警告", "请选择数据保存路径")
            return
        
        # 验证transient参数
        errors = self.config_panel.validate_params()
        if errors:
            QMessageBox.warning(self, "参数错误", "\n".join(errors))
            return
        
        # 获取参数
        loop_count = self.config_panel.get_loop_count()
        transient_params = self.config_panel.get_transient_params()
        
        # 清空绘图
        self.plot_widget.clear_data()
        
        # 创建并启动测试运行器
        self.test_runner = TestRunner(
            port=port,
            loop_count=loop_count,
            transient_params=transient_params,
            save_dir=save_path
        )
        
        # 连接信号
        self.test_runner.data_received.connect(self.on_data_received)
        self.test_runner.progress_updated.connect(self.on_progress_updated)
        self.test_runner.status_changed.connect(self.on_status_changed)
        self.test_runner.test_finished.connect(self.on_test_finished)
        self.test_runner.bytes_received.connect(self.on_bytes_received)
        self.test_runner.loop_started.connect(self.on_loop_started)
        
        # 设置UI为测试模式
        self.config_panel.set_testing_mode(True)
        self.status_label.setText("测试进行中...")
        
        # 启动测试
        self.test_runner.start()
    
    def stop_test(self):
        """停止测试"""
        if self.test_runner and self.test_runner.isRunning():
            self.status_label.setText("正在停止...")
            self.test_runner.request_stop()
    
    def on_data_received(self, data):
        """处理接收到的数据"""
        self.plot_widget.add_data(data)
    
    def on_progress_updated(self, current, total):
        """处理进度更新"""
        self.progress_label.setText(f"Loop: {current}/{total}")
        self.plot_widget.set_status(f"Loop {current}/{total}")
    
    def on_status_changed(self, status):
        """处理状态变化"""
        self.status_label.setText(status)
    
    def on_loop_started(self, loop_idx: int):
        """处理新loop开始 - 清空绘图"""
        self.plot_widget.clear_data()
        self.bytes_label.setText("")  # 重置字节计数显示
    
    def on_bytes_received(self, bytes_count):
        """处理字节数更新"""
        if bytes_count >= 1024 * 1024:
            self.bytes_label.setText(f"已接收: {bytes_count / 1024 / 1024:.2f} MB")
        elif bytes_count >= 1024:
            self.bytes_label.setText(f"已接收: {bytes_count / 1024:.1f} KB")
        else:
            self.bytes_label.setText(f"已接收: {bytes_count} B")
    
    def on_test_finished(self, reason):
        """处理测试完成"""
        self.config_panel.set_testing_mode(False)
        self.status_label.setText(f"测试结束: {reason}")
        self.plot_widget.set_status(f"完成: {reason}")
        
        if reason == "测试完成":
            QMessageBox.information(self, "完成", "测试已完成，数据已保存")
        elif reason == "用户停止":
            QMessageBox.information(self, "已停止", "测试已被用户停止，数据已保存")
        elif reason.startswith("错误"):
            QMessageBox.critical(self, "错误", f"测试出错: {reason}")
    
    def closeEvent(self, event):
        """关闭窗口时确保停止测试"""
        if self.test_runner and self.test_runner.isRunning():
            reply = QMessageBox.question(
                self, "确认", 
                "测试正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            self.test_runner.request_stop()
            self.test_runner.wait(3000)  # 最多等待3秒
        
        event.accept()
