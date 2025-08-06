import sys
import json
import uuid
import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QListWidget, QListWidgetItem, QSplitter, QMessageBox,
                            QFileDialog, QFrame, QGroupBox,
                            QLineEdit, QFormLayout, QCheckBox, QStyledItemDelegate, QStyle)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QRect
from PyQt5.QtGui import QIcon, QColor, QBrush, QFont

from qt_app.widgets.workflow_editor import WorkflowEditorWidget
from qt_app.widgets.realtime_plot import RealtimePlotWidget

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

class DeviceItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering device list items"""
    
    def sizeHint(self, option, index):
        """Return the size needed to display the item"""
        return QSize(option.rect.width(), 60)  # Altura para mostrar toda la información
        
    def paint(self, painter, option, index):
        """Custom painting for device items"""
        # Obtener los datos del dispositivo
        device = index.data(Qt.UserRole + 1)
        if not device:
            super().paint(painter, option, index)
            return
            
        # Preparar el rectángulo de dibujo
        rect = option.rect
        
        # Verificar si el elemento está seleccionado o tiene un test activo
        has_active_test = index.data(Qt.UserRole + 2)
        
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
            sec_color = QColor(text_color)
            sec_color.setAlpha(180)
        elif has_active_test:
            # Color azul claro para tests activos
            painter.fillRect(rect, QColor(230, 247, 255))
            text_color = option.palette.text().color()
            sec_color = QColor(150, 150, 150)
        else:
            painter.fillRect(rect, option.palette.base())
            text_color = option.palette.text().color()
            sec_color = QColor(150, 150, 150)
            
        # Dibujar ID del dispositivo con fuente grande en negrita (PRIORIDAD)
        painter.setPen(text_color)
        id_font = QFont(option.font)
        id_font.setPointSize(id_font.pointSize() + 1)
        id_font.setBold(True)
        painter.setFont(id_font)
        
        # Obtener ID del dispositivo - PRIORIDAD
        device_id = device.get('device_id', "")
        if not device_id:
            device_id = device.get('device', "Unknown device")
            
        id_rect = QRect(rect.left() + 10, rect.top() + 5, rect.width() - 20, 20)
        painter.drawText(id_rect, Qt.AlignLeft | Qt.AlignVCenter, device_id)
        
        # Dibujar descripción del dispositivo con fuente normal (SECUNDARIO)
        desc_font = QFont(option.font)
        painter.setFont(desc_font)
        painter.setPen(sec_color)
        
        # Obtener descripción del dispositivo
        device_desc = device.get('description', "")
        if not device_desc:
            device_desc = "未知设备"
            
        desc_rect = QRect(rect.left() + 10, rect.top() + 25, rect.width() - 20, 20)
        painter.drawText(desc_rect, Qt.AlignLeft | Qt.AlignVCenter, f"描述: {device_desc}")
        
        # Si hay un test activo, mostrar información en la parte inferior
        if has_active_test:
            test_font = QFont(option.font)
            test_font.setItalic(True)
            painter.setFont(test_font)
            painter.setPen(QColor(0, 128, 255))  # Azul para test activo
            
            test_info = f"正在测试: {has_active_test}"
            test_rect = QRect(rect.left() + 10, rect.top() + 40, rect.width() - 20, 20)
            painter.drawText(test_rect, Qt.AlignLeft | Qt.AlignVCenter, test_info)
        else:
            # Mostrar información del puerto
            port_font = QFont(option.font)
            port_font.setPointSize(port_font.pointSize() - 1)
            painter.setFont(port_font)
            painter.setPen(sec_color)
            
            port_info = f"端口: {device.get('device', '')}"
            port_rect = QRect(rect.left() + 10, rect.top() + 40, rect.width() - 20, 20)
            painter.drawText(port_rect, Qt.AlignLeft | Qt.AlignVCenter, port_info)

class DeviceControlWidget(QWidget):
    """
    Widget for device control including device list, workflow configuration, and real-time plotting
    """
    
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        
        # Store device-specific data
        self.workflows = {}  # {device_port: workflow_steps}
        self.current_test_ids = {}  # {device_port: test_id}
        self.plot_widgets = {}  # {device_port: RealtimePlotWidget}
        self.test_info = {}  # {device_port: test_info_dict}
        
        # Current selections
        self.selected_port = None
        self.previous_port = None  # 新增：跟踪上一个选择的设备端口
        
        # Auto-naming setting
        self.auto_naming = True
        
        # Data handling
        self.last_data_time = 0
        self.data_count = 0
        
        # Setup UI
        self.setup_ui()
        
        # Setup update timer for real-time data
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_real_time_data)
        self.update_timer.start(100)  # 100ms interval for more responsive updates
        
        # *** 新增：设备状态更新定时器 ***
        self.device_status_timer = QTimer(self)
        self.device_status_timer.timeout.connect(self.update_device_status)
        self.device_status_timer.start(500)  # 500ms间隔，每半秒更新一次
        
        # 缓存设备信息，避免重复扫描硬件
        self.cached_devices = []
        self.last_device_scan = 0
        self.device_scan_interval = None  # 10秒重新扫描一次硬件

        # Initial refresh
        self.refresh_devices()

        # 是否显示测试完成通知（可以通过设置控制）
        self.show_completion_notification = False  # 设置为True可启用通知
    
    def update_device_status(self):
        """
        实时更新设备状态显示（不重新扫描硬件）
        """
        try:
            # 检查是否需要重新扫描硬件设备
            current_time = time.time()
            if self.device_scan_interval == None:
                pass
            else:
                if current_time - self.last_device_scan > self.device_scan_interval:
                    # 10秒扫描一次硬件，检查是否有新设备
                    self.refresh_devices()
                    return
            
            # 仅更新现有设备的状态显示
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if not item:
                    continue
                    
                port = item.data(Qt.UserRole)
                device_data = item.data(Qt.UserRole + 1)
                
                if not port or not device_data:
                    continue
                
                # 检查该设备是否有活跃测试
                has_active_test = port in self.current_test_ids
                current_test_id = self.current_test_ids.get(port, None)
                
                # 获取当前项的活跃测试状态
                item_active_test = item.data(Qt.UserRole + 2)
                
                # 如果状态发生变化，更新显示
                if (has_active_test and not item_active_test) or \
                (not has_active_test and item_active_test) or \
                (has_active_test and item_active_test != current_test_id):
                    
                    # 更新背景色和测试状态
                    if has_active_test:
                        item.setBackground(QBrush(QColor("#e6f7ff")))
                        item.setData(Qt.UserRole + 2, current_test_id)
                        logger.info(f"设备 {port} 开始测试: {current_test_id}")
                    else:
                        item.setBackground(QBrush())  # 清除背景色
                        item.setData(Qt.UserRole + 2, None)
                        logger.info(f"设备 {port} 测试结束")
                    
                    # 强制重绘该项
                    self.device_list.update(self.device_list.indexFromItem(item))
            # 可选：每10秒打印一次状态（调试用）
            if logger.isEnabledFor(logging.DEBUG):
                if hasattr(self, '_last_status_print'):
                    if time.time() - self._last_status_print > 10:
                        self.monitor_test_status()
                        self._last_status_print = time.time()
                else:
                    self._last_status_print = time.time()
        except Exception as e:
            # 静默处理错误，避免影响UI
            pass

    def setup_ui(self):
        """Setup the user interface"""
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for three panels
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel - Device list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        device_header = QLabel("设备看板")
        device_header.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(device_header)
        
        # Improved device list with custom delegate
        self.device_list = QListWidget()
        self.device_list.setMinimumWidth(200)
        self.device_list.setItemDelegate(DeviceItemDelegate())
        self.device_list.setSpacing(5)  # Add spacing between items
        self.device_list.currentItemChanged.connect(self.on_device_selected)
        left_layout.addWidget(self.device_list)
        
        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(self.refresh_devices)
        left_layout.addWidget(refresh_btn)
        
        # Middle panel - Workflow configuration
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        
        workflow_header = QGroupBox("工作流配置")
        workflow_layout = QVBoxLayout(workflow_header)
        
        # Test information section with auto-naming option
        test_info_frame = QFrame()
        test_info_frame.setFrameShape(QFrame.StyledPanel)
        test_info_frame.setStyleSheet("background-color: #f6f6f6; border-radius: 4px; padding: 8px;")
        test_info_layout = QVBoxLayout(test_info_frame)
        
        # Form layout for input fields
        form_layout = QFormLayout()
        
        # Auto-naming checkbox
        self.auto_naming_check = QCheckBox("自动生成测试名称")
        self.auto_naming_check.setChecked(self.auto_naming)
        self.auto_naming_check.toggled.connect(self.toggle_auto_naming)
        form_layout.addRow("", self.auto_naming_check)
        
        # Test name field with improved styling
        self.test_name_edit = QLineEdit()
        self.test_name_edit.setPlaceholderText("输入测试名称")
        self.test_name_edit.setEnabled(False)  # 初始化时禁用，因为默认启用自动命名
        self.test_name_edit.setStyleSheet("QLineEdit { border: 2px solid #ddd; border-radius: 4px; padding: 5px; }")
        self.test_name_edit.textChanged.connect(self.on_test_name_changed)
        form_layout.addRow("测试名称:", self.test_name_edit)
        
        # Test description field with improved styling
        self.test_desc_edit = QLineEdit()
        self.test_desc_edit.setPlaceholderText("输入测试描述（可选）")
        self.test_desc_edit.setStyleSheet("QLineEdit { border: 2px solid #ddd; border-radius: 4px; padding: 5px; background-color: white; }")
        form_layout.addRow("测试描述:", self.test_desc_edit)
        
        # Chip ID field with improved styling
        self.chip_id_edit = QLineEdit()
        self.chip_id_edit.setPlaceholderText("输入芯片ID（可选）")
        self.chip_id_edit.setStyleSheet("QLineEdit { border: 2px solid #ddd; border-radius: 4px; padding: 5px; background-color: white; }")
        form_layout.addRow("芯片ID:", self.chip_id_edit)
        
        # Device number field with improved styling
        self.device_number_edit = QLineEdit()
        self.device_number_edit.setPlaceholderText("输入器件编号（可选）")
        self.device_number_edit.setStyleSheet("QLineEdit { border: 2px solid #ddd; border-radius: 4px; padding: 5px; background-color: white; }")
        form_layout.addRow("器件编号:", self.device_number_edit)
        
        # Add form layout to test info layout
        test_info_layout.addLayout(form_layout)
        
        # Button toolbar for workflow operations - moved inside test info frame
        button_toolbar_layout = QHBoxLayout()
        
        start_btn = QPushButton("开始测试")
        start_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        start_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; background-color: #4CAF50; color: white; border: none; border-radius: 4px; } QPushButton:hover { background-color: #45a049; }")
        start_btn.clicked.connect(self.start_workflow)
        button_toolbar_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("停止测试")
        stop_btn.setIcon(QIcon.fromTheme("media-playback-stop"))
        stop_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; background-color: #f44336; color: white; border: none; border-radius: 4px; } QPushButton:hover { background-color: #da190b; }")
        stop_btn.clicked.connect(self.stop_workflow)
        button_toolbar_layout.addWidget(stop_btn)
        
        # Add some spacing
        button_toolbar_layout.addSpacing(20)
        
        export_btn = QPushButton("导出工作流")
        export_btn.setIcon(QIcon.fromTheme("document-save"))
        export_btn.setStyleSheet("QPushButton { padding: 8px 16px; background-color: #2196F3; color: white; border: none; border-radius: 4px; } QPushButton:hover { background-color: #1976D2; }")
        export_btn.clicked.connect(self.export_workflow)
        button_toolbar_layout.addWidget(export_btn)
        
        import_btn = QPushButton("导入工作流")
        import_btn.setIcon(QIcon.fromTheme("document-open"))
        import_btn.setStyleSheet("QPushButton { padding: 8px 16px; background-color: #FF9800; color: white; border: none; border-radius: 4px; } QPushButton:hover { background-color: #F57C00; }")
        import_btn.clicked.connect(self.import_workflow)
        button_toolbar_layout.addWidget(import_btn)
        
        # Add stretch to left-align buttons
        button_toolbar_layout.addStretch()
        
        # Add button toolbar to test info layout
        test_info_layout.addLayout(button_toolbar_layout)
        
        workflow_layout.addWidget(test_info_frame)
        
        # Workflow editor
        self.workflow_editor = WorkflowEditorWidget()
        self.workflow_editor.workflow_updated.connect(self.on_workflow_updated)  # 新增：监听工作流更新
        workflow_layout.addWidget(self.workflow_editor)
        
        middle_layout.addWidget(workflow_header)
        
        # Device info section
        self.device_info = QLabel("请选择一个设备")
        self.device_info.setAlignment(Qt.AlignCenter)
        self.device_info.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        middle_layout.addWidget(self.device_info)
        
        # Status label for data reception
        self.data_status = QLabel("No data received")
        self.data_status.setAlignment(Qt.AlignCenter)
        self.data_status.setStyleSheet("font-size: 10px; color: #888;")
        middle_layout.addWidget(self.data_status)
        
        # Right panel - Real-time plot
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        plot_header = QLabel("实时监测")
        plot_header.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(plot_header)
        
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initial placeholder
        self.placeholder_label = QLabel("请选择设备并开始测试")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888; font-size: 14px;")
        self.plot_layout.addWidget(self.placeholder_label)
        
        right_layout.addWidget(self.plot_container)
        
        # Add panels to splitter
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(middle_panel)
        self.splitter.addWidget(right_panel)
        
        # Set default sizes
        self.splitter.setSizes([200, 400, 600])
    
    def toggle_auto_naming(self, enabled):
        """Toggle automatic test naming"""
        self.auto_naming = enabled
        self.test_name_edit.setEnabled(not enabled)
        
        # Save the change to the current device's test info
        if self.selected_port:
            if self.selected_port in self.test_info:
                self.test_info[self.selected_port]['auto_naming'] = enabled
            
            # Update test name based on auto-naming setting
            if enabled:
                self.test_name_edit.setText('（点击开始测试生成）')
            elif not self.test_name_edit.text() or self.test_name_edit.text() == '（点击开始测试生成）':
                # If enabling manual naming and no custom name exists, provide a default
                self.test_name_edit.setText(f"测试-{self.selected_port}")
    
    def on_test_name_changed(self, text):
        """Handle manual changes to test name"""
        # If user is typing, disable auto-naming
        if text and self.auto_naming and not self.test_name_edit.isEnabled():
            return
            
        if text and self.auto_naming and self.test_name_edit.isEnabled():
            self.auto_naming = False
            self.auto_naming_check.setChecked(False)
    
    def on_workflow_updated(self):
        """当工作流被更新时保存当前工作流"""
        if self.selected_port:
            # 保存当前工作流到字典中
            self.workflows[self.selected_port] = self.workflow_editor.get_steps()
            # 记录工作流被修改的标记
            logger.info(f"已保存设备 {self.selected_port} 的工作流配置，共 {len(self.workflows[self.selected_port])} 个步骤")
    
    def save_current_workflow(self):
        """保存当前设备的工作流配置"""
        if self.selected_port:
            current_steps = self.workflow_editor.get_steps()
            if current_steps:  # 只在有步骤时保存，避免覆盖已有配置
                self.workflows[self.selected_port] = current_steps
                logger.info(f"保存设备 {self.selected_port} 的工作流配置，共 {len(current_steps)} 个步骤")
    
    def save_current_test_info(self):
        """保存当前设备的测试信息"""
        if self.selected_port:
            test_info = {
                'test_name': self.test_name_edit.text(),
                'test_desc': self.test_desc_edit.text(),
                'chip_id': self.chip_id_edit.text(),
                'device_number': self.device_number_edit.text(),
                'auto_naming': self.auto_naming
            }
            self.test_info[self.selected_port] = test_info
            logger.info(f"保存设备 {self.selected_port} 的测试信息")
    
    def load_test_info_for_device(self, port):
        """加载指定设备的测试信息"""
        if port in self.test_info:
            # 恢复已保存的测试信息
            info = self.test_info[port]
            self.test_name_edit.setText(info.get('test_name', ''))
            self.test_desc_edit.setText(info.get('test_desc', ''))
            self.chip_id_edit.setText(info.get('chip_id', ''))
            self.device_number_edit.setText(info.get('device_number', ''))
            self.auto_naming = info.get('auto_naming', True)
            self.auto_naming_check.setChecked(self.auto_naming)
            self.test_name_edit.setEnabled(not self.auto_naming)
            logger.info(f"加载设备 {port} 的测试信息")
        else:
            # 初始化新设备的默认测试信息
            self.initialize_default_test_info(port)
    
    def initialize_default_test_info(self, port):
        """为新设备初始化默认测试信息"""
        self.test_name_edit.setText('（点击开始测试生成）')
        self.test_desc_edit.setText('')
        self.chip_id_edit.setText('')
        self.device_number_edit.setText('')
        self.auto_naming = True
        self.auto_naming_check.setChecked(True)
        self.test_name_edit.setEnabled(False)
        
        # 保存默认设置
        default_info = {
            'test_name': '（点击开始测试生成）',
            'test_desc': '',
            'chip_id': '',
            'device_number': '',
            'auto_naming': True
        }
        self.test_info[port] = default_info
        logger.info(f"为设备 {port} 初始化默认测试信息")
    
    def refresh_devices(self):
        """Refresh the device list"""
        # 保存当前设备的工作流配置和测试信息，防止刷新导致丢失
        self.save_current_workflow()
        self.save_current_test_info()
        
        try:
            # 获取设备列表
            devices = self.backend.list_serial_ports()
            
            # 更新缓存
            self.cached_devices = devices
            self.last_device_scan = time.time()
            
            # Save current selection and device information
            current_port = None
            current_devices = {}  # 保存当前设备列表信息
            
            # 先保存当前设备列表的信息
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item:
                    device_data = item.data(Qt.UserRole + 1)
                    if device_data:
                        port = device_data['device']
                        current_devices[port] = device_data
            
            if self.device_list.currentItem():
                current_port = self.device_list.currentItem().data(Qt.UserRole)
            
            # Clear and repopulate list
            self.device_list.clear()
            
            # Create a comprehensive device list that merges current info with new scan results
            final_devices = []
            for device in devices:
                port = device['device']
                # 重要修改：如果设备已经在测试中，优先使用保存的设备信息
                if port in self.current_test_ids and port in current_devices:
                    # 使用之前保存的设备信息（包含设备ID）
                    device_for_display = current_devices[port]
                else:
                    # 使用新查询的设备信息
                    device_for_display = device
                final_devices.append(device_for_display)
            
            # Sort devices alphabetically by device_id or device port
            devices_sorted = sorted(final_devices, key=lambda d: d.get('device_id', d.get('device', '')).upper())
            
            for device_for_display in devices_sorted:
                item = QListWidgetItem()
                port = device_for_display['device']
                
                # Device display name
                display_name = f"{device_for_display['description']}"
                if device_for_display.get('device_id'):
                    display_name += f" (ID: {device_for_display['device_id']})"
                else:
                    display_name += f" ({port})"
                
                item.setText(display_name)
                item.setData(Qt.UserRole, port)
                item.setData(Qt.UserRole + 1, device_for_display)
                
                # If device has an active test, highlight it
                if port in self.current_test_ids:
                    item.setBackground(QBrush(QColor("#e6f7ff")))
                    item.setData(Qt.UserRole + 2, self.current_test_ids[port])
                
                self.device_list.addItem(item)
            
            # Restore selection if possible
            if current_port:
                for i in range(self.device_list.count()):
                    if self.device_list.item(i).data(Qt.UserRole) == current_port:
                        self.device_list.setCurrentRow(i)
                        break
            elif self.device_list.count() > 0:
                self.device_list.setCurrentRow(0)
                
            logger.info(f"设备列表已刷新: {len(devices)} 个设备")
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"获取设备列表失败: {str(e)}")
    def force_refresh_devices(self):
        """强制重新扫描设备硬件（原刷新按钮的行为）"""
        self.last_device_scan = 0  # 强制重新扫描
        self.refresh_devices()
    def on_device_selected(self, current, previous):
        """Handle device selection"""
        # 保存上一个设备的工作流配置和测试信息
        if self.selected_port:
            self.previous_port = self.selected_port
            self.save_current_workflow()
            self.save_current_test_info()
        
        if not current:
            self.selected_port = None
            self.device_info.setText("请选择一个设备")
            self.workflow_editor.clear()
            return
        
        # Get port and device info
        port = current.data(Qt.UserRole)
        device = current.data(Qt.UserRole + 1)
        
        # Update selected port
        self.selected_port = port
        
        # Update device info
        info_text = f"当前设备: {device['description']}"
        if device['device_id']:
            info_text += f"<br><small>设备 ID: {device['device_id']}</small>"
        if port in self.current_test_ids:
            info_text += f"<br><small>测试 ID: {self.current_test_ids[port]}</small>"
        
        self.device_info.setText(info_text)
        
        # Update workflow editor with device-specific workflow
        if port not in self.workflows:
            self.workflows[port] = []
        
        self.workflow_editor.set_steps(self.workflows[port])
        
        # Load device-specific test information
        self.load_test_info_for_device(port)
        
        # Update plot visibility - hide all and show only the current one
        self.update_plot_visibility()
    
    def update_plot_visibility(self):
        """Update plot visibility based on selected device"""
        # Clear the placeholder if needed
        if self.placeholder_label.parent():
            self.placeholder_label.setParent(None)
        
        # Hide all plots
        for port, plot in self.plot_widgets.items():
            plot.setVisible(False)
        
        # Show only the selected one if it exists
        if self.selected_port in self.plot_widgets:
            self.plot_widgets[self.selected_port].setVisible(True)
        else:
            # Show placeholder if no plot for this device
            self.plot_layout.addWidget(self.placeholder_label)
            self.placeholder_label.setVisible(True)
    
    def start_workflow(self):
        """Start workflow for the selected device"""
        if not self.selected_port:
            QMessageBox.warning(self, "Warning", "请先选择一个设备")
            return
        # *** 新增：检查设备是否已在测试中 ***
        if self.selected_port in self.current_test_ids:
            current_test_id = self.current_test_ids[self.selected_port]
            
            # 获取设备信息用于显示
            device_info = None
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.data(Qt.UserRole) == self.selected_port:
                    device_info = item.data(Qt.UserRole + 1)
                    break
            
            device_name = device_info.get('device_id', self.selected_port) if device_info else self.selected_port
            
            # 弹出警告对话框
            reply = QMessageBox.question(
                self, 
                "设备正在测试中", 
                f"设备 {device_name} 正在进行测试 (ID: {current_test_id})\n\n"
                f"您可以选择:\n"
                f"• 点击'是'停止当前测试并开启新的测试\n"
                f"• 点击'否'保持当前测试", 
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 用户选择停止当前测试
                self.stop_workflow()
                # 等待一下确保停止完成
                QTimer.singleShot(500, self._start_workflow_after_stop)
                return
            else:
                # 用户选择不停止，直接返回
                return
            # 继续原有的启动流程
        self._execute_start_workflow()
    def _start_workflow_after_stop(self):
        """停止测试后启动新测试"""
        # 检查是否确实停止了
        if self.selected_port not in self.current_test_ids:
            self._execute_start_workflow()
        else:
            QMessageBox.warning(self, "Warning", "停止测试失败，请稍后重试")
    
    def _execute_start_workflow(self):
        """执行启动工作流的实际逻辑（原start_workflow的主要部分）"""
        # Get workflow steps
        steps = self.workflow_editor.get_steps()
        if not steps:
            QMessageBox.warning(self, "Warning", "请先配置工作流步骤")
            return
        
        # Store the workflow for this device
        self.workflows[self.selected_port] = steps
        
        # Generate test ID
        test_id = f"test_{time.strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Get device info
        device_info = None
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.data(Qt.UserRole) == self.selected_port:
                device_info = item.data(Qt.UserRole + 1)
                break
        
        if not device_info:
            QMessageBox.warning(self, "Error", "无法获取设备信息")
            return
        
        # 在这里处理测试名称 - 如果启用了自动命名，生成新名称
        if self.auto_naming:
            device_id = device_info.get('device_id', self.selected_port)
            timestamp = time.strftime('%Y%m%d%H%M%S')
            test_name = f"{device_id}_{timestamp}"
            self.test_name_edit.setText(test_name)
        
        # Get test name and description from input fields
        test_name = self.test_name_edit.text().strip()
        if not test_name:  # If empty, use default
            test_name = f"测试-{device_info['device_id'] or self.selected_port}"
            self.test_name_edit.setText(test_name)
            
        test_description = self.test_desc_edit.text().strip()
        chip_id = self.chip_id_edit.text().strip()
        device_number = self.device_number_edit.text().strip()
        
        # Prepare workflow parameters
        device_id = device_info['device_id'] or self.selected_port
        params = {
            "test_id": test_id,
            "device_id": device_id,
            "port": self.selected_port,
            "baudrate": 512000,
            "name": test_name,
            "description": test_description,
            "chip_id": chip_id,
            "device_number": device_number,
            "steps": steps,
        }
        
        try:
            # Start workflow
            result = self.backend.start_workflow(params)
            
            if result.get("status") == "ok":
                # Reset data counters
                self.last_data_time = time.time()
                self.data_count = 0
                
                # Store test ID for this device
                self.current_test_ids[self.selected_port] = test_id
                
                # Create or update plot widget
                if self.selected_port not in self.plot_widgets:
                    plot_widget = RealtimePlotWidget(self.selected_port, test_id)
                    self.plot_widgets[self.selected_port] = plot_widget
                    self.plot_layout.addWidget(plot_widget)
                else:
                    self.plot_widgets[self.selected_port].set_test_id(test_id)
                
                # Update plot visibility
                self.update_plot_visibility()
                
                # Update device info to show test ID
                if device_info:
                    info_text = f"当前设备: {device_info['description']}"
                    if device_info['device_id']:
                        info_text += f"<br><small>设备 ID: {device_info['device_id']}</small>"
                    info_text += f"<br><small>测试 ID: {test_id}</small>"
                    info_text += f"<br><small>测试名称: {test_name}</small>"
                    self.device_info.setText(info_text)
                
                
                # Note: Keep test description, chip_id, and device_number fields for reuse
            else:
                QMessageBox.warning(self, "Error", f"测试启动失败: {result.get('reason', '未知错误')}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"启动测试时发生错误: {str(e)}")
    def stop_workflow(self):
        """Stop workflow for the selected device"""
        if not self.selected_port:
            QMessageBox.warning(self, "Warning", "请先选择一个设备")
            return
        
        if self.selected_port not in self.current_test_ids:
            QMessageBox.warning(self, "Warning", "该设备没有正在运行的测试")
            return
        
        try:
            # Stop test
            result = self.backend.stop_test(test_id=self.current_test_ids[self.selected_port])
            
            if result.get("status") == "ok":
                # Update test status in plot widget
                if self.selected_port in self.plot_widgets:
                    self.plot_widgets[self.selected_port].set_test_completed()
                
                # Remove test ID
                del self.current_test_ids[self.selected_port]
                
                # Update device list
                # self.force_refresh_devices()
                
                # Update device info
                device_info = None
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item.data(Qt.UserRole) == self.selected_port:
                        device_info = item.data(Qt.UserRole + 1)
                        break
                
                if device_info:
                    info_text = f"当前设备: {device_info['description']}"
                    if device_info['device_id']:
                        info_text += f"<br><small>设备 ID: {device_info['device_id']}</small>"
                    self.device_info.setText(info_text)
                
                QMessageBox.information(self, "Success", "测试已停止")
            else:
                QMessageBox.warning(self, "Error", f"停止测试失败: {result.get('reason', '未知错误')}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"停止测试时发生错误: {str(e)}")
    
    def export_workflow(self):
        """Export workflow to JSON file"""
        if not self.selected_port:
            QMessageBox.warning(self, "Warning", "请先选择一个设备")
            return
        
        steps = self.workflow_editor.get_steps()
        if not steps:
            QMessageBox.warning(self, "Warning", "没有要导出的工作流步骤")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出工作流", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Make sure it has the .json extension
                if not file_path.endswith('.json'):
                    file_path += '.json'
                
                with open(file_path, 'w') as f:
                    json.dump(steps, f, indent=2)
                
                QMessageBox.information(self, "Success", f"工作流已保存到 {file_path}")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"导出工作流时发生错误: {str(e)}")
    
    def import_workflow(self):
        """Import workflow from JSON file"""
        if not self.selected_port:
            QMessageBox.warning(self, "Warning", "请先选择一个设备")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入工作流", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    steps = json.load(f)
                
                # Validate steps
                if not isinstance(steps, list):
                    raise ValueError("工作流文件格式无效")
                
                # Get current steps and append imported steps
                current_steps = self.workflow_editor.get_steps()
                combined_steps = current_steps + steps
                
                # Set combined steps to workflow editor
                self.workflow_editor.set_steps(combined_steps)
                
                # Store for current device
                self.workflows[self.selected_port] = combined_steps
                
                QMessageBox.information(self, "Success", f"工作流已导入并添加到当前工作流后面 (添加了 {len(steps)} 个步骤)")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"导入工作流时发生错误: {str(e)}")
    
    
    def update_real_time_data(self):
        """Update real-time data for active plots - 批量处理版本 + 测试完成检测"""
        # 批量处理队列中的所有消息
        processed = 0
        max_process = 500  # 一次循环中最多处理500条消息，避免无限循环
        
        while processed < max_process:
            # 非阻塞方式获取数据
            data = self.backend.get_real_time_data(timeout=0.001)  # 使用较小超时
            if not data:
                break  # 队列为空，退出循环
            
            # *** 新增：检查测试完成消息 ***
            self.handle_backend_message(data)
            
            # 处理数据
            test_id = data.get('test_id')
            if not test_id:
                processed += 1
                continue
                
            # 找到对应的设备
            device_port = None
            for port, tid in self.current_test_ids.items():
                if tid == test_id:
                    device_port = port
                    break
            
            # 如果找到设备且有活跃的图表
            if device_port and device_port in self.plot_widgets:
                plot_widget = self.plot_widgets[device_port]
                plot_widget.process_message(data)
                
            processed += 1
        
        # 更新数据统计
        now = time.time()
        time_diff = now - self.last_data_time
        if time_diff > 1.0:  # 每秒更新一次统计
            data_rate = self.data_count / time_diff
            self.data_status.setText(f"Data rate: {data_rate:.1f} msgs/sec | Processed batch: {processed}")
            self.last_data_time = now
            self.data_count = 0
        else:
            self.data_count += processed
    
    def prepare_for_tab_change(self):
        """在切换标签页前保存当前工作流配置和测试信息"""
        self.save_current_workflow()
        self.save_current_test_info()
        
    def restore_after_tab_change(self):
        """在标签页切换回来后恢复工作流配置和测试信息"""
        # 这里不需要特别处理，因为on_device_selected已经负责从workflows字典中加载配置
        # 但我们确保选择状态被保持
        if self.selected_port:
            # 确保当前选择的设备配置被加载
            if self.selected_port in self.workflows:
                self.workflow_editor.set_steps(self.workflows[self.selected_port])
                logger.info(f"恢复设备 {self.selected_port} 的工作流配置，共 {len(self.workflows[self.selected_port])} 个步骤")
            
            # 确保当前选择的设备测试信息被加载
            self.load_test_info_for_device(self.selected_port)


    def handle_backend_message(self, message):
        """
        处理来自后端的各种消息，包括测试完成通知
        
        Args:
            message: 从后端接收到的消息
        """
        msg_type = message.get("type")
        test_id = message.get("test_id")
        
        try:
            if msg_type == "test_result":
                # 测试结果消息 - 表示测试已完成
                self.handle_test_completion(test_id, message)
                
            elif msg_type == "test_complete":
                # 测试完成消息
                self.handle_test_completion(test_id, message)
                
            elif msg_type == "test_error":
                # 测试错误消息 - 也表示测试结束
                self.handle_test_error(test_id, message)
                
            # elif msg_type == "test_progress":
            #     # 检查进度是否为100%
            #     progress = message.get("progress", 0)
            #     if progress >= 1.0:  # 100%完成
            #         # 注意：不要在这里立即标记完成，因为可能还有后续数据
            #         # 设置一个延迟检查
            #         self.schedule_completion_check(test_id)
                    
        except Exception as e:
            logger.error(f"处理后端消息时出错: {e}")


    def handle_test_completion(self, test_id, message):
        """
        处理测试完成
        
        Args:
            test_id: 完成的测试ID
            message: 完成消息
        """
        if not test_id:
            return
            
        # 查找对应的设备端口
        device_port = None
        for port, tid in list(self.current_test_ids.items()):
            if tid == test_id:
                device_port = port
                break
        
        if device_port:
            logger.info(f"检测到测试完成: {test_id} (设备: {device_port})")
            
            # 更新图表状态
            if device_port in self.plot_widgets:
                self.plot_widgets[device_port].set_test_completed()
            
            # *** 关键：从活跃测试列表中移除 ***
            del self.current_test_ids[device_port]
            
            # 更新设备信息显示
            if device_port == self.selected_port:
                self.update_selected_device_info()
            
            # 可选：显示完成通知
            if hasattr(self, 'show_completion_notification') and self.show_completion_notification:
                QMessageBox.information(self, "测试完成", f"测试 {test_id} 已自动完成")
        else:
            logger.warning(f"警告：收到未知测试的完成消息: {test_id}")


    def handle_test_error(self, test_id, message):
        """
        处理测试错误
        
        Args:
            test_id: 出错的测试ID
            message: 错误消息
        """
        if not test_id:
            return
            
        # 查找对应的设备端口
        device_port = None
        for port, tid in list(self.current_test_ids.items()):
            if tid == test_id:
                device_port = port
                break
        
        if device_port:
            error_msg = message.get("error", "未知错误")
            logger.error(f"检测到测试错误: {test_id} (设备: {device_port}) - {error_msg}")
            
            # 更新图表状态
            if device_port in self.plot_widgets:
                self.plot_widgets[device_port].set_test_completed()
            
            # *** 关键：从活跃测试列表中移除 ***
            del self.current_test_ids[device_port]
            
            # 更新设备信息显示
            if device_port == self.selected_port:
                self.update_selected_device_info()
            
            # 显示错误通知
            QMessageBox.warning(self, "测试错误", f"测试 {test_id} 发生错误: {error_msg}")

    def update_selected_device_info(self):
        """更新当前选中设备的信息显示"""
        if not self.selected_port:
            return
            
        # 获取设备信息
        device_info = None
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item and item.data(Qt.UserRole) == self.selected_port:
                device_info = item.data(Qt.UserRole + 1)
                break
        
        if device_info:
            info_text = f"当前设备: {device_info['description']}"
            if device_info['device_id']:
                info_text += f"<br><small>设备 ID: {device_info['device_id']}</small>"
            
            # 检查是否还有活跃测试
            if self.selected_port in self.current_test_ids:
                test_id = self.current_test_ids[self.selected_port]
                info_text += f"<br><small>测试 ID: {test_id}</small>"
            
            self.device_info.setText(info_text)

    def monitor_test_status(self):
        """
        监控并打印当前测试状态（用于调试）
        """
        if self.current_test_ids:
            logger.debug("=== 当前活跃测试 ===")
            for port, test_id in self.current_test_ids.items():
                logger.debug(f"设备 {port}: {test_id}")
        else:
            logger.debug("当前没有活跃测试")