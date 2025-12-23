"""
实时绘图组件 - realtime_plot.py
使用pyqtgraph显示实时测试数据
"""

import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QCheckBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import pyqtgraph as pg


class RealtimePlotWidget(QWidget):
    """实时绘图组件 - 带节流刷新"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 数据存储
        self.timestamps = []
        self.currents = []
        self.time_window = 10  # 时间窗口（秒）- 只保留最后10秒数据
        self.auto_scroll = True
        
        # 数据缓冲区（用于批量更新）
        self.pending_timestamps = []
        self.pending_currents = []
        self._needs_update = False
        
        self.setup_ui()
        
        # 设置刷新定时器（30fps = 33ms）
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._throttled_update)
        self.refresh_timer.start(33)  # 30fps
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 控制栏
        control_layout = QHBoxLayout()
        
        # 自动滚动复选框
        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.stateChanged.connect(self.toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_cb)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignRight)
        control_layout.addWidget(self.status_label)
        
        layout.addLayout(control_layout)
        
        # 创建绘图区域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', '电流', units='A')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setTitle('实时电流曲线')
        
        # 创建曲线
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#2196F3', width=2),
            name='电流'
        )
        
        layout.addWidget(self.plot_widget)
        
        # 数据点计数标签
        self.count_label = QLabel("数据点: 0")
        self.count_label.setFont(QFont("Consolas", 9))
        layout.addWidget(self.count_label)
    
    def toggle_auto_scroll(self, state):
        """切换自动滚动"""
        self.auto_scroll = state == Qt.Checked
    
    def clear_data(self):
        """清除所有数据"""
        self.timestamps.clear()
        self.currents.clear()
        self.pending_timestamps.clear()
        self.pending_currents.clear()
        self._needs_update = False
        self.curve.setData([], [])
        self.count_label.setText("数据点: 0")
        self.status_label.setText("就绪")
    
    def add_data(self, data: np.ndarray):
        """
        添加新数据到缓冲区（不立即更新绘图）
        
        Args:
            data: numpy数组，形状为(n, 2)，每行是[timestamp, current]
        """
        if len(data) == 0:
            return
            
        # 添加到缓冲区
        self.pending_timestamps.extend(data[:, 0].tolist())
        self.pending_currents.extend(data[:, 1].tolist())
        self._needs_update = True
    
    def _throttled_update(self):
        """节流更新 - 由定时器调用"""
        if not self._needs_update:
            return
            
        self._needs_update = False
        
        # 将缓冲区数据合并到主数据
        if self.pending_timestamps:
            self.timestamps.extend(self.pending_timestamps)
            self.currents.extend(self.pending_currents)
            self.pending_timestamps.clear()
            self.pending_currents.clear()
        
        # 只保留最近10秒的数据
        if len(self.timestamps) > 0:
            max_time = self.timestamps[-1]
            cutoff_time = max_time - self.time_window
            
            # 使用二分查找优化（近似）
            cutoff_idx = 0
            for i, t in enumerate(self.timestamps):
                if t >= cutoff_time:
                    cutoff_idx = i
                    break
            
            if cutoff_idx > 0:
                self.timestamps = self.timestamps[cutoff_idx:]
                self.currents = self.currents[cutoff_idx:]
        
        # 更新曲线
        self.update_plot()
    
    def update_plot(self):
        """更新绘图"""
        if not self.timestamps:
            return
            
        # 更新曲线数据
        self.curve.setData(self.timestamps, self.currents)
        
        # 自动滚动
        if self.auto_scroll and len(self.timestamps) > 0:
            max_time = self.timestamps[-1]
            min_time = max(0, max_time - self.time_window)
            self.plot_widget.setXRange(min_time, max_time, padding=0.02)
        
        # 更新计数
        self.count_label.setText(f"数据点: {len(self.timestamps)}")
    
    def set_status(self, status: str):
        """设置状态标签"""
        self.status_label.setText(status)
    
    def set_time_window(self, seconds: float):
        """设置时间窗口（秒）"""
        self.time_window = seconds

