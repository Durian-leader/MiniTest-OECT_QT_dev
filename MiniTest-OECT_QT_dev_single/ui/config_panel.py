"""
参数配置面板 - config_panel.py
用于配置串口、loop次数、transient参数和保存路径
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QLineEdit,
    QFileDialog, QFrame
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QIntValidator

from core.serial_device import SerialPortManager


class ConfigPanel(QWidget):
    """参数配置面板"""
    
    # 信号
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    identify_requested = pyqtSignal(str)  # 参数是串口名称
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_ports()
        self._update_max_cycles()  # 初始化时计算最大cycles
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # ========== 串口配置 ==========
        port_group = QGroupBox("串口配置")
        port_vbox = QVBoxLayout(port_group)
        
        # 串口选择行
        port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        port_layout.addWidget(QLabel("串口:"))
        port_layout.addWidget(self.port_combo, 1)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_btn)
        
        self.identify_btn = QPushButton("识别")
        self.identify_btn.setToolTip("查询设备名称")
        self.identify_btn.clicked.connect(self._on_identify_clicked)
        port_layout.addWidget(self.identify_btn)
        
        port_vbox.addLayout(port_layout)
        
        # 设备名称显示
        self.device_name_label = QLabel("设备: 未识别")
        self.device_name_label.setStyleSheet("color: #666; font-style: italic;")
        port_vbox.addWidget(self.device_name_label)
        
        layout.addWidget(port_group)
        
        # ========== Loop配置 ==========
        loop_group = QGroupBox("循环配置")
        loop_layout = QFormLayout(loop_group)
        
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(1, 10000)
        self.loop_spin.setValue(1)
        self.loop_spin.setToolTip("外层loop的循环次数")
        loop_layout.addRow("Loop次数:", self.loop_spin)
        
        layout.addWidget(loop_group)
        
        # ========== Transient参数 ==========
        trans_group = QGroupBox("Transient参数")
        trans_layout = QFormLayout(trans_group)
        
        # 采样间隔
        self.time_step_edit = QLineEdit("1")
        self.time_step_edit.setValidator(QIntValidator(1, 65535))
        self.time_step_edit.setToolTip("采样间隔 1-65535 ms")
        trans_layout.addRow("采样间隔 (ms):", self.time_step_edit)
        
        # 源极电压
        self.source_voltage_edit = QLineEdit("0")
        self.source_voltage_edit.setValidator(QIntValidator(-32768, 32767))
        self.source_voltage_edit.setToolTip("源极电压 -32768 ~ 32767 mV")
        trans_layout.addRow("源极电压 (mV):", self.source_voltage_edit)
        
        # 漏极电压
        self.drain_voltage_edit = QLineEdit("100")
        self.drain_voltage_edit.setValidator(QIntValidator(-32768, 32767))
        self.drain_voltage_edit.setToolTip("漏极电压 -32768 ~ 32767 mV")
        trans_layout.addRow("漏极电压 (mV):", self.drain_voltage_edit)
        
        # 低电平时间
        self.bottom_time_edit = QLineEdit("500")
        self.bottom_time_edit.setValidator(QIntValidator(1, 65535))
        self.bottom_time_edit.setToolTip("低电平持续时间 1-65535 ms")
        self.bottom_time_edit.textChanged.connect(self._update_max_cycles)
        trans_layout.addRow("低电平时间 (ms):", self.bottom_time_edit)
        
        # 高电平时间
        self.top_time_edit = QLineEdit("500")
        self.top_time_edit.setValidator(QIntValidator(1, 65535))
        self.top_time_edit.setToolTip("高电平持续时间 1-65535 ms")
        self.top_time_edit.textChanged.connect(self._update_max_cycles)
        trans_layout.addRow("高电平时间 (ms):", self.top_time_edit)
        
        # 栅极低电平
        self.gate_bottom_edit = QLineEdit("-300")
        self.gate_bottom_edit.setValidator(QIntValidator(-32768, 32767))
        self.gate_bottom_edit.setToolTip("栅极低电平 -32768 ~ 32767 mV")
        trans_layout.addRow("栅极低电平 (mV):", self.gate_bottom_edit)
        
        # 栅极高电平
        self.gate_top_edit = QLineEdit("500")
        self.gate_top_edit.setValidator(QIntValidator(-32768, 32767))
        self.gate_top_edit.setToolTip("栅极高电平 -32768 ~ 32767 mV")
        trans_layout.addRow("栅极高电平 (mV):", self.gate_top_edit)
        
        # cycles (动态显示最大值)
        self.cycles_edit = QLineEdit("5")
        self.cycles_edit.setValidator(QIntValidator(1, 65535))
        self.cycles_edit.setToolTip("每次transient的循环次数")
        trans_layout.addRow("Cycles:", self.cycles_edit)
        
        # 最大cycles提示标签
        self.max_cycles_label = QLabel("")
        self.max_cycles_label.setStyleSheet("color: #666; font-size: 11px;")
        trans_layout.addRow("", self.max_cycles_label)
        
        # 周期警告标签
        self.period_warning_label = QLabel("")
        self.period_warning_label.setStyleSheet("color: #f44336; font-size: 11px;")
        trans_layout.addRow("", self.period_warning_label)
        
        layout.addWidget(trans_group)
        
        # ========== 保存路径 ==========
        save_group = QGroupBox("数据保存")
        save_layout = QHBoxLayout(save_group)
        
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText("选择保存目录...")
        save_layout.addWidget(self.save_path_edit, 1)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_save_path)
        save_layout.addWidget(self.browse_btn)
        
        layout.addWidget(save_group)
        
        # ========== 控制按钮 ==========
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始测试")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_btn.clicked.connect(self.start_requested.emit)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止测试")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self.stop_btn)
        
        layout.addLayout(btn_layout)
        
        # 添加弹性空间
        layout.addStretch()
    
    def refresh_ports(self):
        """刷新串口列表"""
        self.port_combo.clear()
        ports = SerialPortManager.get_available_ports()
        for port in ports:
            display_text = f"{port['device']} - {port['description']}"
            self.port_combo.addItem(display_text, port['device'])
        self.device_name_label.setText("设备: 未识别")
    
    def _on_identify_clicked(self):
        """识别按钮点击"""
        port = self.get_selected_port()
        if port:
            self.device_name_label.setText("设备: 正在识别...")
            self.identify_requested.emit(port)
    
    def set_device_name(self, name: str):
        """设置设备名称显示"""
        self.device_name_label.setText(f"设备: {name}")
        self.device_name_label.setStyleSheet("color: #2196F3; font-weight: bold;")
    
    def browse_save_path(self):
        """浏览选择保存路径"""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_path_edit.setText(path)
    
    def get_selected_port(self) -> str:
        """获取选中的串口"""
        return self.port_combo.currentData() or ""
    
    def get_loop_count(self) -> int:
        """获取loop次数"""
        return self.loop_spin.value()
    
    def get_transient_params(self) -> dict:
        """获取transient参数"""
        return {
            "timeStep": int(self.time_step_edit.text() or 10),
            "sourceVoltage": int(self.source_voltage_edit.text() or 0),
            "drainVoltage": int(self.drain_voltage_edit.text() or -100),
            "bottomTime": int(self.bottom_time_edit.text() or 5000),
            "topTime": int(self.top_time_edit.text() or 5000),
            "gateVoltageBottom": int(self.gate_bottom_edit.text() or 0),
            "gateVoltageTop": int(self.gate_top_edit.text() or 500),
            "cycles": int(self.cycles_edit.text() or 3),
        }
    
    def get_save_path(self) -> str:
        """获取保存路径"""
        return self.save_path_edit.text()
    
    def _update_max_cycles(self):
        """动态更新最大cycles显示"""
        try:
            bottom_time = int(self.bottom_time_edit.text() or 1)
            top_time = int(self.top_time_edit.text() or 1)
            period = bottom_time + top_time
            
            # 约束①: 周期不能超过65535
            if period > 65535:
                self.period_warning_label.setText(f"⚠ 周期 {period} ms 超过 65535 ms!")
                self.max_cycles_label.setText("")
            else:
                self.period_warning_label.setText("")
                # 约束②: 总时长不超过 4,294,967,295 ms
                max_cycles = min(65535, 4294967295 // period)
                self.max_cycles_label.setText(f"最大Cycles: {max_cycles}")
        except ValueError:
            self.max_cycles_label.setText("")
            self.period_warning_label.setText("")
    
    def validate_params(self) -> list:
        """验证所有transient参数，返回错误列表"""
        errors = []
        
        try:
            time_step = int(self.time_step_edit.text() or 0)
            bottom_time = int(self.bottom_time_edit.text() or 0)
            top_time = int(self.top_time_edit.text() or 0)
            cycles = int(self.cycles_edit.text() or 0)
            source_voltage = int(self.source_voltage_edit.text() or 0)
            drain_voltage = int(self.drain_voltage_edit.text() or 0)
            gate_bottom = int(self.gate_bottom_edit.text() or 0)
            gate_top = int(self.gate_top_edit.text() or 0)
        except ValueError as e:
            return [f"参数格式错误: {str(e)}"]
        
        # 基础范围校验
        if not (1 <= time_step <= 65535):
            errors.append("采样间隔必须在 1-65535 ms")
        if not (1 <= bottom_time <= 65535):
            errors.append("低电平时间必须在 1-65535 ms")
        if not (1 <= top_time <= 65535):
            errors.append("高电平时间必须在 1-65535 ms")
        if not (1 <= cycles <= 65535):
            errors.append("Cycles必须在 1-65535")
        
        for name, val in [('源极电压', source_voltage), 
                          ('漏极电压', drain_voltage),
                          ('栅极低电平', gate_bottom), 
                          ('栅极高电平', gate_top)]:
            if not (-32768 <= val <= 32767):
                errors.append(f"{name}必须在 -32768 ~ 32767 mV")
        
        # 约束①：周期时长不溢出
        period = bottom_time + top_time
        if period > 65535:
            errors.append(f"低电平+高电平 = {period} ms 超过 65535 ms")
        
        # 约束②：总时长不溢出
        total_time = period * cycles
        if total_time > 4294967295:
            max_cycles = 4294967295 // period if period > 0 else 0
            errors.append(f"总时长超限，当前周期下Cycles最大为 {max_cycles}")
        
        return errors
    
    def set_testing_mode(self, testing: bool):
        """设置测试模式（启用/禁用控件）"""
        self.start_btn.setEnabled(not testing)
        self.stop_btn.setEnabled(testing)
        self.port_combo.setEnabled(not testing)
        self.refresh_btn.setEnabled(not testing)
        self.identify_btn.setEnabled(not testing)
        self.loop_spin.setEnabled(not testing)
        self.browse_btn.setEnabled(not testing)
        
        # 禁用所有参数编辑框
        for widget in [self.time_step_edit, self.source_voltage_edit,
                      self.drain_voltage_edit, self.bottom_time_edit,
                      self.top_time_edit, self.gate_bottom_edit,
                      self.gate_top_edit, self.cycles_edit]:
            widget.setEnabled(not testing)
