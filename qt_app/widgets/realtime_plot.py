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
    and step separation - 支持output多曲线显示
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
    
    def set_path_readable(self, path):
        """Set the readable workflow path"""
        if path:
            self.path_readable = path
            self.path_label.setText(path)
            self.path_frame.setVisible(True)
        else:
            self.path_frame.setVisible(False)
    
    def parse_output_csv_data(self, csv_data_string):
        """
        解析CSV格式的output数据
        
        Args:
            csv_data_string: CSV格式的字符串数据
            
        Returns:
            dict: 解析后的数据，格式为 {x_values: [...], curves: {curve_name: [y_values]}}
        """
        try:
            lines = csv_data_string.strip().split('\n')
            if len(lines) < 2:
                return None
                
            # 解析表头
            header = lines[0].split(',')
            x_label = header[0]  # 第一列是x轴标签（如Vd）
            curve_labels = header[1:]  # 后续列是各条曲线的标签
            
            # 解析数据
            x_values = []
            curves = {label: [] for label in curve_labels}
            
            for line in lines[1:]:
                values = line.split(',')
                if len(values) == len(header):
                    try:
                        x_val = float(values[0])
                        x_values.append(x_val)
                        
                        for i, label in enumerate(curve_labels):
                            y_val = float(values[i + 1])
                            curves[label].append(y_val)
                    except ValueError:
                        continue
            
            return {
                'x_values': x_values,
                'curves': curves,
                'x_label': x_label
            }
            
        except Exception as e:
            print(f"解析CSV数据失败: {e}")
            return None
    
    def process_message(self, message):
        """处理来自后端的消息 - 步骤分离版本，支持output多曲线"""
        try:
            msg_type = message.get("type")
            self.debug_label.setText(f"Received: {msg_type}")
            
            if msg_type == "test_data":
                # 获取原始数据
                hex_data = message.get("data", "")
                csv_data = message.get("csv_data", "")  # 新增：获取CSV数据
                
                if not hex_data and not csv_data:
                    return
                    
                # 获取步骤类型和索引
                step_type = message.get("step_type", "")
                
                # 获取工作流信息
                workflow_info = message.get("workflow_info", {})
                step_index = workflow_info.get("step_index", -1)
                path_readable = workflow_info.get("path_readable", "")
                
                # 构造唯一的步骤ID
                step_id = f"{step_index}-{step_type}-{path_readable}"
                
                # 检测步骤变化 - 核心改进
                if self.auto_step_reset_check.isChecked() and step_id != self.current_step_id and self.current_step_id:
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
                
                # 关键改进：根据数据类型和步骤类型选择处理方式
                if step_type == 'output' and csv_data:
                    # Output类型优先使用CSV数据绘制多条曲线
                    self.process_output_csv_data(csv_data, step_id)
                elif hex_data:
                    # Transfer和Transient类型，或者没有CSV数据时使用hex数据
                    self.process_traditional_data(hex_data, step_type, step_id)
                elif csv_data:
                    # 如果只有CSV数据但不是output类型，尝试解析为单曲线
                    self.process_csv_as_single_curve(csv_data, step_type, step_id)
                    
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
    
    def process_csv_as_single_curve(self, csv_data, step_type, step_id):
        """处理CSV数据作为单曲线（用于transfer/transient类型）"""
        try:
            from qt_app.utils.decoder import parse_csv_data
            
            parsed_data = parse_csv_data(csv_data)
            if not parsed_data:
                return
                
            x_values = parsed_data['x_values']
            curves = parsed_data['curves']
            
            # 只使用第一条曲线作为单曲线数据
            if curves:
                first_curve_name = list(curves.keys())[0]
                y_values = curves[first_curve_name]
                
                # 更新坐标轴标签
                if step_type == 'transient':
                    self.plot_widget.setLabel('bottom', 'Time (s)')
                    self.plot_widget.setTitle("瞬态测试 - 电流 vs 时间")
                else:  # transfer
                    self.plot_widget.setLabel('bottom', 'Gate Voltage (V)')
                    self.plot_widget.setTitle("转移特性 - 电流 vs 栅压")
                
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
                
                # 添加数据点到缓冲区
                for i, x_val in enumerate(x_values):
                    if i < len(y_values):
                        self.new_point_buffer_x.append(x_val)
                        self.new_point_buffer_y_dict[default_curve].append(y_values[i])
                
                # 更新统计
                self.total_received_points += len(x_values)
                self.debug_label.setText(f"Added {len(x_values)} CSV points as single curve")
                
        except Exception as e:
            print(f"处理CSV单曲线数据失败: {e}")
    
    def process_output_csv_data(self, csv_data, step_id):
        """处理output类型的CSV数据"""
        try:
            from qt_app.utils.decoder import parse_csv_data
            
            # 解析CSV数据
            parsed_data = parse_csv_data(csv_data)
            if not parsed_data:
                return
                
            x_values = parsed_data['x_values']
            curves = parsed_data['curves']
            x_label = parsed_data['x_label']
            
            # 更新坐标轴标签
            self.plot_widget.setLabel('bottom', f'{x_label} (V)')
            self.plot_widget.setTitle("输出特性 - 电流 vs 漏压")
            
            # 存储栅极电压列表用于图例
            self.current_gate_voltages = list(curves.keys())
            
            # 确保有对应的曲线和缓冲区
            for curve_name in curves.keys():
                if curve_name not in self.plot_lines:
                    # 创建新的绘图曲线
                    colors = ['b', 'r', 'g', 'c', 'm', 'y', 'k']
                    color_idx = len(self.plot_lines) % len(colors)
                    
                    line = self.plot_widget.plot([], [], 
                                               pen=pg.mkPen(color=colors[color_idx], width=2),
                                               name=curve_name)
                    self.plot_lines[curve_name] = line
                    
                if curve_name not in self.data_y_dict:
                    self.data_y_dict[curve_name] = np.array([])
                    
                if curve_name not in self.new_point_buffer_y_dict:
                    self.new_point_buffer_y_dict[curve_name] = []
            
            # 添加新数据点到缓冲区
            for i, x_val in enumerate(x_values):
                # 检查x值是否已存在（避免重复添加相同的x值）
                if len(self.new_point_buffer_x) > 0 and abs(self.new_point_buffer_x[-1] - x_val) < 1e-6:
                    continue
                    
                self.new_point_buffer_x.append(x_val)
                
                # 添加各条曲线的y值
                for curve_name, y_values in curves.items():
                    if i < len(y_values):
                        self.new_point_buffer_y_dict[curve_name].append(y_values[i])
            
            # 更新统计
            self.total_received_points += len(x_values)
            self.debug_label.setText(f"Added {len(x_values)} output points ({len(curves)} curves)")
            
        except Exception as e:
            print(f"处理output CSV数据失败: {e}")
            traceback.print_exc()
    
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
        # 检查是否有新数据
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
        
        # 清除图例和曲线
        self.legend.clear()
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        self.update_status_label()
        self.step_info_label.setText("等待数据...")
        self.update_timer.start(100)  # 更新周期