import numpy as np
import traceback
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QCheckBox, QPushButton
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

import pyqtgraph as pg
from qt_app.utils.decoder import decode_hex_to_bytes, decode_bytes_to_data

class RealtimePlotWidget(QWidget):
    """
    Widget for displaying real-time test data with sliding window
    and step separation - 支持output多曲线实时显示（修复时序版本）
    """
    
    def __init__(self, port, test_id=None):
        super().__init__()
        self.port = port
        self.test_id = test_id
        self.current_step_type = "transfer"  # Default step type
        self.data_buffer = ""  # Buffer for hex data
        self.test_completed = False
        self.path_readable = ""
        
        # 步骤跟踪 - 新增
        self.current_step_index = -1
        self.current_step_id = ""
        
        # 内存安全设置
        self.MAX_POINTS = 100000  # 最大存储点数
        self.use_circular_buffer = True  # 是否使用环形缓冲区限制内存使用
        
        # 使用NumPy数组保存数据 - 支持多曲线
        self.data_x = np.array([])
        self.data_y_dict = {}  # 字典存储多条y数据，key为栅电压值或曲线名
        
        # *** 新增：Output类型特有的数据管理 ***
        self.output_curves_data = {}  # {gate_voltage: {'x': [...], 'y': [...]}}
        self.current_output_gate_voltage = None  # 当前正在接收的栅极电压
        
        # *** 新增：时序修复相关 ***
        self.output_data_buffer = []  # 缓存等待处理的output数据
        self.expected_gate_voltages = set()  # 预期的栅极电压集合
        
        # 数据统计
        self.total_received_points = 0  # 总接收点数（包括被丢弃的）
        
        # 数据缓冲机制 - 支持多曲线
        self.new_point_buffer_x = []
        self.new_point_buffer_y_dict = {}  # 字典存储多条y缓冲区
        self.buffer_size_threshold = 50  # 缓冲区阈值
        
        # 滚动窗口设置
        self.window_size = 10.0  # 10秒滑动窗口
        self.auto_scrolling_enabled = True
        
        # 当前步骤的栅电压列表（用于output类型）
        self.current_gate_voltages = []
        
        # 设置UI
        self.setup_ui()
        
        # 更新计时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)  # 50ms更新
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Status bar
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.StyledPanel)
        self.status_frame.setStyleSheet("background-color: #f1f1f1; border-radius: 4px;")
        status_layout = QVBoxLayout(self.status_frame)
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        self.update_status_label()
        
        layout.addWidget(self.status_frame)
        
        # 控制面板
        control_frame = QFrame()
        control_frame.setStyleSheet("background-color: #f0f2f5; padding: 5px; border-radius: 4px;")
        control_layout = QHBoxLayout(control_frame)
        
        # 1. 内存保护选项
        self.circular_buffer_check = QCheckBox("内存保护")
        self.circular_buffer_check.setChecked(self.use_circular_buffer)
        self.circular_buffer_check.setToolTip(f"实时图表中只保留最新的{self.MAX_POINTS}个数据点，防止内存溢出（但数据会在后端妥善保存不会丢失）")
        self.circular_buffer_check.toggled.connect(self.toggle_circular_buffer)
        control_layout.addWidget(self.circular_buffer_check)
        
        # 2. 新增：自动分步选项
        self.auto_step_reset_check = QCheckBox("步骤间分离")
        self.auto_step_reset_check.setChecked(True)
        self.auto_step_reset_check.setToolTip("不同步骤的数据将在独立图表中显示")
        control_layout.addWidget(self.auto_step_reset_check)
        
        # 3. 自动滚动选项
        self.auto_scroll_check = QCheckBox("时间窗口")
        self.auto_scroll_check.setChecked(self.auto_scrolling_enabled)
        self.auto_scroll_check.setToolTip("启用10秒滚动时间窗口（谨慎关闭，最好保持打开，防止图表渲染过多的数据点导致程序崩溃）")
        self.auto_scroll_check.toggled.connect(self.toggle_auto_scrolling)
        control_layout.addWidget(self.auto_scroll_check)
        
        # 4. 数据点显示选项
        self.symbol_check = QCheckBox("显示数据点")
        self.symbol_check.setChecked(False)
        self.symbol_check.toggled.connect(self.toggle_point_symbols)
        control_layout.addWidget(self.symbol_check,1)
        
        layout.addWidget(control_frame)
        
        # Path bar for workflow path
        self.path_frame = QFrame()
        self.path_frame.setFrameShape(QFrame.NoFrame)
        self.path_frame.setStyleSheet("background-color: #e6f7ff; padding: 5px; border-radius: 4px;")
        path_layout = QVBoxLayout(self.path_frame)
        
        self.path_label = QLabel()
        self.path_label.setAlignment(Qt.AlignLeft)
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label)
        
        layout.addWidget(self.path_frame)
        self.path_frame.setVisible(False)  # Hide initially
        
        # 当前步骤信息 - 新增
        self.step_info_frame = QFrame()
        self.step_info_frame.setStyleSheet("background-color: #f6ffed; padding: 5px; border-radius: 4px;")
        step_info_layout = QHBoxLayout(self.step_info_frame)
        
        self.step_info_label = QLabel("等待数据...")
        step_info_layout.addWidget(self.step_info_label)
        
        self.clear_btn = QPushButton("清除图表")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_data)
        step_info_layout.addWidget(self.clear_btn)
        
        layout.addWidget(self.step_info_frame)
        
        # Plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Current (A)')
        self.plot_widget.setLabel('bottom', 'Gate Voltage (V)')
        self.plot_widget.setTitle("Waiting for data...")
        
        # 性能设置
        self.plot_widget.setAntialiasing(False)  # 关闭抗锯齿
        self.plot_widget.setClipToView(True)  # 只渲染可见区域
        
        # 添加图例
        self.legend = self.plot_widget.addLegend()
        
        # 配置曲线字典 - 支持多条曲线
        self.plot_lines = {}  # key: 曲线名, value: PlotDataItem
        
        layout.addWidget(self.plot_widget)
        
        # Debug area
        debug_frame = QFrame()
        debug_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 4px;")
        debug_layout = QHBoxLayout(debug_frame)
        
        self.debug_label = QLabel("No data received yet")
        self.debug_label.setStyleSheet("color: #666; font-size: 10px;")
        debug_layout.addWidget(self.debug_label)
        
        self.data_count_label = QLabel("Points: 0")
        self.data_count_label.setStyleSheet("color: #666; font-size: 10px;")
        self.data_count_label.setAlignment(Qt.AlignRight)
        debug_layout.addWidget(self.data_count_label)
        
        layout.addWidget(debug_frame)
    
    def toggle_circular_buffer(self, enabled):
        """开关环形缓冲区"""
        self.use_circular_buffer = enabled
        if enabled:
            # 如果启用，且当前数据已超过最大值，立即裁剪
            if len(self.data_x) > self.MAX_POINTS:
                self.data_x = self.data_x[-self.MAX_POINTS:]
                for key in self.data_y_dict:
                    self.data_y_dict[key] = self.data_y_dict[key][-self.MAX_POINTS:]
                self.update_plot()
    
    def toggle_auto_scrolling(self, enabled):
        """切换自动滚动时间窗口功能"""
        self.auto_scrolling_enabled = enabled
    
    def toggle_point_symbols(self, enabled):
        """切换是否显示数据点符号"""
        for line in self.plot_lines.values():
            if enabled:
                line.setSymbol('o')
                line.setSymbolSize(4)
                line.setSymbolBrush(pg.mkBrush('b'))
            else:
                line.setSymbol(None)
    
    def clear_data(self):
        """手动清除图表数据"""
        self.data_x = np.array([])
        self.data_y_dict = {}
        self.new_point_buffer_x = []
        self.new_point_buffer_y_dict = {}
        self.total_received_points = 0
        
        # *** 清除output特有数据 ***
        self.output_curves_data = {}
        self.current_output_gate_voltage = None
        self.output_data_buffer = []
        self.expected_gate_voltages = set()
        
        # 清除所有绘图曲线
        for line in self.plot_lines.values():
            line.setData([], [])
        
        self.data_count_label.setText("Points: 0")
        self.debug_label.setText("图表已手动清除")
    
    def update_status_label(self):
        """Update the status label with current info"""
        if not self.test_id:
            self.status_label.setText("请开始测试以显示数据")
            self.status_frame.setStyleSheet("background-color: #f1f1f1; border-radius: 4px;")
        elif self.test_completed:
            self.status_label.setText(f"✅ 测试已完成 (ID: {self.test_id})")
            self.status_frame.setStyleSheet("background-color: #f6ffed; border-radius: 4px;")
        else:
            self.status_label.setText(f"📊 正在采集 (ID: {self.test_id})")
            self.status_frame.setStyleSheet("background-color: #e6f7ff; border-radius: 4px;")
    
    def set_test_id(self, test_id):
        """Set the test ID and reset the plot"""
        self.test_id = test_id
        self.test_completed = False
        self.data_buffer = ""
        
        # 重置步骤跟踪
        self.current_step_index = -1
        self.current_step_id = ""
        self.current_gate_voltages = []
        
        # 重置数据
        self.data_x = np.array([])
        self.data_y_dict = {}
        self.new_point_buffer_x = []
        self.new_point_buffer_y_dict = {}
        self.total_received_points = 0
        
        # *** 重置output特有数据 ***
        self.output_curves_data = {}
        self.current_output_gate_voltage = None
        self.output_data_buffer = []
        self.expected_gate_voltages = set()
        
        # 清除图例和曲线
        self.legend.clear()
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        # 更新UI
        self.update_status_label()
        self.path_frame.setVisible(False)
        self.debug_label.setText(f"Test ID set: {test_id}")
        self.data_count_label.setText("Points: 0")
        self.step_info_label.setText("等待数据...")
        
        # 重置图表
        self.plot_widget.setTitle("Waiting for data...")
    
    def set_test_completed(self):
        """标记测试完成但不立即停止更新"""
        self.test_completed = True
        self.update_status_label()
        
        # *** 测试完成时，处理所有缓冲的数据 ***
        self.flush_output_data_buffer()
    
    def set_path_readable(self, path):
        """Set the readable workflow path"""
        if path:
            self.path_readable = path
            self.path_label.setText(path)
            self.path_frame.setVisible(True)
        else:
            self.path_frame.setVisible(False)
    
    def parse_output_metadata(self, hex_data):
        """
        *** 解析hex数据中的output元数据前缀（支持开始信号） ***
        
        Args:
            hex_data: 可能包含元数据前缀的hex数据字符串
            
        Returns:
            tuple: (signal_type, output_metadata_dict, clean_hex_data)
        """
        if not isinstance(hex_data, str):
            return None, None, hex_data
            
        # 检查是否有output开始信号：OUTPUT_START:{gate_voltage}:{index}:{total}|
        if hex_data.startswith("OUTPUT_START:"):
            try:
                # 分割前缀（开始信号没有实际数据部分）
                meta_part = hex_data.rstrip("|")
                
                # 解析元数据：OUTPUT_START:{gate_voltage}:{index}:{total}
                meta_parts = meta_part.split(":")
                if len(meta_parts) == 4 and meta_parts[0] == "OUTPUT_START":
                    gate_voltage = int(meta_parts[1])
                    gate_voltage_index = int(meta_parts[2])
                    total_gate_voltages = int(meta_parts[3])
                    
                    output_metadata = {
                        "gate_voltage": gate_voltage,
                        "gate_voltage_index": gate_voltage_index,
                        "total_gate_voltages": total_gate_voltages,
                        "is_output_curve": True
                    }
                    
                    return "start", output_metadata, ""
                    
            except (ValueError, IndexError) as e:
                print(f"解析output开始信号失败: {e}")
        
        # 检查是否有output元数据前缀：OUTPUT_META:{gate_voltage}:{index}:{total}|
        elif hex_data.startswith("OUTPUT_META:"):
            try:
                # 分割前缀和实际数据
                meta_part, actual_hex_data = hex_data.split("|", 1)
                
                # 解析元数据：OUTPUT_META:{gate_voltage}:{index}:{total}
                meta_parts = meta_part.split(":")
                if len(meta_parts) == 4 and meta_parts[0] == "OUTPUT_META":
                    gate_voltage = int(meta_parts[1])
                    gate_voltage_index = int(meta_parts[2])
                    total_gate_voltages = int(meta_parts[3])
                    
                    output_metadata = {
                        "gate_voltage": gate_voltage,
                        "gate_voltage_index": gate_voltage_index,
                        "total_gate_voltages": total_gate_voltages,
                        "is_output_curve": True
                    }
                    
                    return "data", output_metadata, actual_hex_data
                    
            except (ValueError, IndexError) as e:
                print(f"解析output元数据失败: {e}")
        
        return None, None, hex_data
    
    def prepare_output_curve(self, gate_voltage: int, total_gate_voltages: int):
        """
        *** 新增：提前准备output曲线，避免时序问题 ***
        """
        curve_name = f"Id(Vg={gate_voltage}mV)"
        
        # 记录预期的栅极电压
        self.expected_gate_voltages.add(gate_voltage)
        
        # 确保有对应的曲线数据结构
        if curve_name not in self.output_curves_data:
            self.output_curves_data[curve_name] = {'x': [], 'y': []}
        
        # 确保有对应的绘图曲线
        if curve_name not in self.plot_lines:
            # 创建新的绘图曲线
            colors = ['b', 'r', 'g', 'c', 'm', 'y', 'k', 'orange', 'purple', 'brown']
            color_idx = len(self.plot_lines) % len(colors)
            
            line = self.plot_widget.plot([], [], 
                                       pen=pg.mkPen(color=colors[color_idx], width=2),
                                       name=curve_name)
            self.plot_lines[curve_name] = line
            
            print(f"为栅极电压 {gate_voltage}mV 创建曲线: {curve_name}")
        
        # 更新坐标轴标签
        self.plot_widget.setLabel('bottom', 'Drain Voltage (V)')
        self.plot_widget.setLabel('left', 'Current (A)')
        self.plot_widget.setTitle('输出特性曲线（实时）')
    
    def flush_output_data_buffer(self):
        """
        *** 新增：处理缓冲的output数据 ***
        """
        if self.output_data_buffer:
            print(f"处理缓冲的output数据: {len(self.output_data_buffer)} 条")
            
            for hex_data, output_metadata in self.output_data_buffer:
                self.process_output_realtime_data_immediate(hex_data, output_metadata)
            
            self.output_data_buffer.clear()
    
    def process_message(self, message):
        """处理来自后端的消息 - 步骤分离版本，支持output多曲线实时hex数据（修复时序版）"""
        try:
            msg_type = message.get("type")
            self.debug_label.setText(f"Received: {msg_type}")
            
            if msg_type == "test_data":
                # 获取原始数据
                hex_data = message.get("data", "")
                
                if not hex_data:
                    return
                    
                # 获取步骤类型和索引
                step_type = message.get("step_type", "")
                
                # 获取工作流信息
                workflow_info = message.get("workflow_info", {})
                step_index = workflow_info.get("step_index", -1)
                path_readable = workflow_info.get("path_readable", "")
                
                # 构造唯一的步骤ID
                step_id = f"{step_index}-{step_type}-{path_readable}"
                
                # *** 修改：更保守的步骤变化检测，避免在同一步骤内重置 ***
                if (self.auto_step_reset_check.isChecked() and 
                    step_id != self.current_step_id and 
                    self.current_step_id and 
                    step_index != self.current_step_index):  # 增加步骤索引检查
                    # 步骤发生变化，重置图表
                    self.clear_data()
                    self.debug_label.setText(f"步骤变化: {self.current_step_type} → {step_type}")
                
                # 更新当前步骤信息
                self.current_step_type = step_type
                self.current_step_index = step_index
                self.current_step_id = step_id
                
                # 显示步骤信息
                if path_readable:
                    self.set_path_readable(path_readable)
                    self.step_info_label.setText(f"当前: {step_type}模式 - 步骤{step_index}")
                else:
                    self.step_info_label.setText(f"当前: {step_type}模式")
                
                # *** 关键改进：解析output元数据和开始信号 ***
                if step_type == 'output':
                    # 尝试解析output元数据
                    signal_type, output_metadata, clean_hex_data = self.parse_output_metadata(hex_data)
                    
                    if signal_type == "start":
                        # 处理开始信号：提前准备曲线
                        gate_voltage = output_metadata["gate_voltage"]
                        total_gate_voltages = output_metadata["total_gate_voltages"]
                        self.prepare_output_curve(gate_voltage, total_gate_voltages)
                        self.debug_label.setText(f"准备output曲线: Vg={gate_voltage}mV")
                        
                    elif signal_type == "data" and output_metadata:
                        # 处理实际数据：多曲线模式
                        self.process_output_realtime_data(clean_hex_data, output_metadata, step_id)
                        
                    else:
                        # 无元数据：单曲线模式（向后兼容）
                        self.process_output_as_single_curve(hex_data, step_id)
                        
                elif step_type == 'transient':
                    # Transient类型：传统处理方式
                    self.process_traditional_data(hex_data, step_type, step_id)
                else:  # transfer
                    # Transfer类型：传统处理方式
                    self.process_traditional_data(hex_data, step_type, step_id)
                    
            elif msg_type == "test_progress":
                progress = abs(message.get("progress", 0) * 100)
                if progress >= 100:
                    self.set_test_completed()
                else:
                    self.status_label.setText(f"📊 正在采集: {progress:.1f}% (ID: {self.test_id})")
            
            elif msg_type == "test_complete" or msg_type == "test_result":
                self.set_test_completed()
                self.update_plot()  # 确保最终数据被绘制
        
        except Exception as e:
            self.debug_label.setText(f"Error: {str(e)}")
            print(f"Error processing message: {str(e)}")
            traceback.print_exc()
    
    def process_output_as_single_curve(self, hex_data, step_id):
        """
        *** 将output当作单曲线处理（向后兼容） ***
        """
        if not hex_data:
            return
            
        # 更新坐标轴标签为output模式
        self.plot_widget.setLabel('bottom', 'Drain Voltage (V)')
        self.plot_widget.setLabel('left', 'Current (A)')
        self.plot_widget.setTitle("输出特性 - 电流 vs 漏压")
        
        # # 确保有默认曲线
        # default_curve = "Output Current"
        # if default_curve not in self.plot_lines:
        #     line = self.plot_widget.plot([], [], 
        #                                pen=pg.mkPen(color='b', width=2),
        #                                name=default_curve)
        #     self.plot_lines[default_curve] = line
            
        # if default_curve not in self.data_y_dict:
        #     self.data_y_dict[default_curve] = np.array([])
            
        # if default_curve not in self.new_point_buffer_y_dict:
        #     self.new_point_buffer_y_dict[default_curve] = []
        
        # 解析数据（output和transfer格式相同）
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return
        
        # 解析新数据点 - 使用transfer模式（因为格式相同）
        new_points = decode_bytes_to_data(byte_data, mode='transfer')
        
        # 批量添加数据点到缓冲区
        if new_points:
            # 更新总接收点数
            self.total_received_points += len(new_points)
            
            # 添加到临时缓冲区
            for point in new_points:
                self.new_point_buffer_x.append(point[0])
                self.new_point_buffer_y_dict[default_curve].append(point[1])
            
            # 更新调试信息
            self.debug_label.setText(f"Added {len(new_points)} output points (single curve)")
    
    def process_output_realtime_data(self, hex_data, output_metadata, step_id):
        """
        *** 处理output类型的实时hex数据（多曲线模式，修复时序） ***
        """
        if not hex_data:
            return
            
        # 获取栅极电压信息
        gate_voltage = output_metadata.get("gate_voltage", 0)
        gate_voltage_index = output_metadata.get("gate_voltage_index", 0)
        total_gate_voltages = output_metadata.get("total_gate_voltages", 1)
        
        curve_name = f"Id(Vg={gate_voltage}mV)"
        
        # *** 关键修复：检查曲线是否已准备好 ***
        if curve_name not in self.plot_lines or curve_name not in self.output_curves_data:
            # 曲线还没准备好，缓存数据
            print(f"曲线 {curve_name} 还没准备好，缓存数据")
            self.output_data_buffer.append((hex_data, output_metadata))
            
            # 立即准备曲线
            self.prepare_output_curve(gate_voltage, total_gate_voltages)
            
            # 然后立即处理缓冲的数据
            self.flush_output_data_buffer()
            return
        
        # 处理实际数据
        self.process_output_realtime_data_immediate(hex_data, output_metadata)
    
    def process_output_realtime_data_immediate(self, hex_data, output_metadata):
        """
        *** 立即处理output数据（不检查时序） ***
        """
        # 获取栅极电压信息
        gate_voltage = output_metadata.get("gate_voltage", 0)
        gate_voltage_index = output_metadata.get("gate_voltage_index", 0)
        total_gate_voltages = output_metadata.get("total_gate_voltages", 1)
        
        curve_name = f"Id(Vg={gate_voltage}mV)"
        
        # 更新当前栅极电压
        if self.current_output_gate_voltage != gate_voltage:
            self.current_output_gate_voltage = gate_voltage
            self.debug_label.setText(f"Output扫描: Vg={gate_voltage}mV ({gate_voltage_index+1}/{total_gate_voltages})")
        
        # 解析hex数据
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return
        
        # 解析新数据点 - 使用transfer模式（因为output和transfer数据格式相同）
        new_points = decode_bytes_to_data(byte_data, mode='transfer')
        
        if new_points and curve_name in self.output_curves_data:
            # 添加数据点到对应曲线
            for point in new_points:
                self.output_curves_data[curve_name]['x'].append(point[0])
                self.output_curves_data[curve_name]['y'].append(point[1])
            
            # 更新统计
            self.total_received_points += len(new_points)
            
            # 内存保护：限制每条曲线的数据点数
            if self.use_circular_buffer:
                max_points_per_curve = self.MAX_POINTS // max(1, len(self.output_curves_data))
                for curve_data in self.output_curves_data.values():
                    if len(curve_data['x']) > max_points_per_curve:
                        curve_data['x'] = curve_data['x'][-max_points_per_curve:]
                        curve_data['y'] = curve_data['y'][-max_points_per_curve:]
            
            # 更新曲线显示
            for curve_name_update, curve_data in self.output_curves_data.items():
                if curve_name_update in self.plot_lines and curve_data['x']:
                    self.plot_lines[curve_name_update].setData(curve_data['x'], curve_data['y'])
            
            # 更新数据计数
            total_points = sum(len(data['x']) for data in self.output_curves_data.values())
            curve_count = len(self.output_curves_data)
            self.data_count_label.setText(f"显示: {total_points} 点 ({curve_count} 曲线)")
            
            print(f"添加 {len(new_points)} 个数据点到 {curve_name}")
    
    def process_traditional_data(self, hex_data, step_type, step_id):
        """处理传统的hex数据（transfer和transient）"""
        if not hex_data:
            return
            
        # 更新坐标轴标签
        if step_type == 'transient':
            self.plot_widget.setLabel('bottom', 'Time (s)')
            self.plot_widget.setTitle("瞬态测试 - 电流 vs 时间")
            mode = 'transient'
        else:  # transfer
            self.plot_widget.setLabel('bottom', 'Gate Voltage (V)')
            self.plot_widget.setTitle("转移特性 - 电流 vs 栅压")
            mode = 'transfer'
        
        # 确保有默认曲线
        default_curve = "Current"
        if default_curve not in self.plot_lines:
            line = self.plot_widget.plot([], [], 
                                       pen=pg.mkPen(color='b', width=2),
                                       name=default_curve)
            self.plot_lines[default_curve] = line
            
        if default_curve not in self.data_y_dict:
            self.data_y_dict[default_curve] = np.array([])
            
        if default_curve not in self.new_point_buffer_y_dict:
            self.new_point_buffer_y_dict[default_curve] = []
        
        # 解析数据
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return
        
        # 解析新数据点
        new_points = decode_bytes_to_data(byte_data, mode)
        
        # 批量添加数据点到缓冲区
        if new_points:
            # 更新总接收点数
            self.total_received_points += len(new_points)
            
            # 添加到临时缓冲区
            for point in new_points:
                self.new_point_buffer_x.append(point[0])
                self.new_point_buffer_y_dict[default_curve].append(point[1])
            
            # 更新调试信息
            self.debug_label.setText(f"Added {len(new_points)} points")
    
    def update_plot(self):
        """更新图表绘图 - 支持多曲线"""
        # 对于output多曲线类型，数据已经在process_output_realtime_data中直接更新了
        if self.current_step_type == 'output' and self.output_curves_data:
            return
            
        # 检查是否有新数据（传统模式）
        if not self.new_point_buffer_x:
            return
            
        # 使用NumPy高效连接数组
        buffer_x = np.array(self.new_point_buffer_x)
        
        # 如果是新图表，直接设置数据
        if self.data_x.size == 0:
            self.data_x = buffer_x
            for curve_name, buffer_y in self.new_point_buffer_y_dict.items():
                if buffer_y:  # 确保有数据
                    self.data_y_dict[curve_name] = np.array(buffer_y)
            self.plot_widget.enableAutoRange(x=True, y=True)
        else:
            # 连接到现有数组
            self.data_x = np.append(self.data_x, buffer_x)
            for curve_name, buffer_y in self.new_point_buffer_y_dict.items():
                if buffer_y and curve_name in self.data_y_dict:  # 确保有数据且曲线存在
                    self.data_y_dict[curve_name] = np.append(self.data_y_dict[curve_name], buffer_y)
        
        # 内存保护：使用环形缓冲区
        if self.use_circular_buffer and len(self.data_x) > self.MAX_POINTS:
            # 只保留最新的MAX_POINTS个点
            self.data_x = self.data_x[-self.MAX_POINTS:]
            for curve_name in self.data_y_dict:
                self.data_y_dict[curve_name] = self.data_y_dict[curve_name][-self.MAX_POINTS:]
        
        # 清空缓冲区
        self.new_point_buffer_x = []
        self.new_point_buffer_y_dict = {key: [] for key in self.new_point_buffer_y_dict}
        
        # 数据量很大时自动隐藏符号
        total_points = self.data_x.size
        point_symbols_enabled = self.symbol_check.isChecked()
        
        # 更新所有曲线的图表数据
        for curve_name, line in self.plot_lines.items():
            if curve_name in self.data_y_dict and len(self.data_y_dict[curve_name]) > 0:
                # 确保x和y数据长度匹配
                y_data = self.data_y_dict[curve_name]
                min_len = min(len(self.data_x), len(y_data))
                
                line.setData(self.data_x[:min_len], y_data[:min_len])
                
                # 设置符号
                if total_points > 1000 and not point_symbols_enabled:
                    line.setSymbol(None)
                elif point_symbols_enabled:
                    line.setSymbol('o') 
                    line.setSymbolSize(4)
        
        # 滚动窗口支持
        self.sliding_window()
        
        # 更新数据计数 - 显示保留点数和总接收点数
        if self.use_circular_buffer and self.total_received_points > self.MAX_POINTS:
            # 显示已被丢弃的数据点信息
            self.data_count_label.setText(
                f"显示: {total_points}/{self.total_received_points} 点 (已丢弃: {self.total_received_points - total_points}点)"
            )
        else:
            self.data_count_label.setText(f"Points: {total_points}")
    
    def sliding_window(self):
        if self.current_step_type == 'transient' and self.auto_scrolling_enabled:
            if len(self.data_x) > 1:
                max_time = np.max(self.data_x)
                if max_time > self.window_size:
                    min_time = max_time - self.window_size
                    self.plot_widget.setXRange(min_time, max_time)
                    self.plot_widget.enableAutoRange(y=True)
        else:
            # 其他图表类型自动调整范围
            self.plot_widget.enableAutoRange(x=True, y=True)
    
    def start_new_test(self, test_id):
        """开始新的测试"""
        self.test_id = test_id
        self.test_completed = False
        
        # 重置步骤跟踪
        self.current_step_index = -1
        self.current_step_id = ""
        self.current_gate_voltages = []
        
        # 重置数据
        self.data_x = np.array([])
        self.data_y_dict = {}
        self.new_point_buffer_x = []
        self.new_point_buffer_y_dict = {}
        self.total_received_points = 0
        
        # *** 重置output特有数据 ***
        self.output_curves_data = {}
        self.current_output_gate_voltage = None
        self.output_data_buffer = []
        self.expected_gate_voltages = set()
        
        # 清除图例和曲线
        self.legend.clear()
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        self.update_status_label()
        self.step_info_label.setText("等待数据...")
        self.update_timer.start(100)  # 更新周期