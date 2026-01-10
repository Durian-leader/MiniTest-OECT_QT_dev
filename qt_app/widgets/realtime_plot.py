import numpy as np
import time
import traceback
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QCheckBox, QPushButton
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from qt_app.i18n import tr
import pyqtgraph as pg
from qt_app.utils.decoder import decode_hex_to_bytes, decode_bytes_to_data

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################
class RealtimePlotWidget(QWidget):
    """
    Widget for displaying real-time test data with sliding window
    and step separation - 修复版本：分离单曲线和多曲线逻辑
    """
    
    def __init__(self, port, test_id=None):
        super().__init__()
        self.port = port
        self.test_id = test_id
        self.current_step_type = "transfer"  # Default step type
        self.data_buffer = ""  # Buffer for hex data
        self.test_completed = False
        self.transient_packet_size = None
        self.path_readable = ""
        self.transimpedance_ohms = 100.0
        self.baseline_current = 0.0
        
        # 步骤跟踪
        self.current_step_index = -1
        self.current_step_id = ""
        
        # 内存安全设置
        self.MAX_POINTS = 10000
        self.use_circular_buffer = True
        
        # === 单曲线数据结构（用于transfer和transient）===
        self.data_x = np.array([])
        self.data_y = np.array([])
        self.new_point_buffer_x = []
        self.new_point_buffer_y = []
        self.last_sample_ts = 0.0
        
        # === 多曲线数据结构（仅用于output）===
        self.output_curves_data = {}  # {curve_name: {'x': [...], 'y': [...]}}
        self.current_output_gate_voltage = None
        self.output_data_buffer = []
        self.expected_gate_voltages = set()
        
        # 数据统计
        self.total_received_points = 0
        
        # 滚动窗口设置
        self.window_size = 10.0
        self.auto_scrolling_enabled = True

        # UI更新节流/绘图优化
        self._last_label_step_type = None
        self._last_step_info_text = None
        self._last_debug_update = 0.0
        self._debug_update_interval = 0.2
        self._last_autorange_update = 0.0
        self._autorange_interval = 0.5
        self.display_max_points = None
        
        # 设置UI
        self.setup_ui()
        
        # 更新计时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)

    def set_transimpedance_ohms(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 100.0
        if value <= 0:
            value = 100.0
        self.transimpedance_ohms = value

    def set_baseline_current(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        self.baseline_current = value
    
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
        
        # 控制面板（已隐藏，但仍保留以防逻辑引用控件）
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        
        # 1. 内存保护选项
        self.circular_buffer_check = QCheckBox(tr("realtime.memory_protection"))
        self.circular_buffer_check.setChecked(self.use_circular_buffer)
        self.circular_buffer_check.setToolTip(tr("realtime.memory_protection_tooltip", max_points=self.MAX_POINTS))
        self.circular_buffer_check.toggled.connect(self.toggle_circular_buffer)
        control_layout.addWidget(self.circular_buffer_check)
        
        # 2. 自动分步选项
        self.auto_step_reset_check = QCheckBox(tr("realtime.step_separation"))
        self.auto_step_reset_check.setChecked(True)
        self.auto_step_reset_check.setToolTip(tr("realtime.step_separation_tooltip"))
        control_layout.addWidget(self.auto_step_reset_check)
        
        # 3. 自动滚动选项
        self.auto_scroll_check = QCheckBox(tr("realtime.time_window"))
        self.auto_scroll_check.setChecked(self.auto_scrolling_enabled)
        self.auto_scroll_check.setToolTip(tr("realtime.time_window_tooltip"))
        self.auto_scroll_check.toggled.connect(self.toggle_auto_scrolling)
        control_layout.addWidget(self.auto_scroll_check)
        
        # 4. 数据点显示选项
        self.symbol_check = QCheckBox(tr("realtime.show_points"))
        self.symbol_check.setChecked(False)
        self.symbol_check.toggled.connect(self.toggle_point_symbols)
        control_layout.addWidget(self.symbol_check, 1)
        
        # 保留在布局中但隐藏，避免控件被销毁导致逻辑访问崩溃
        control_frame.setVisible(False)
        control_frame.setMaximumHeight(1)
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
        self.path_frame.setVisible(False)
        
        # 当前步骤信息
        self.step_info_frame = QFrame()
        self.step_info_frame.setStyleSheet("background-color: #f6ffed; padding: 5px; border-radius: 4px;")
        step_info_layout = QHBoxLayout(self.step_info_frame)
        
        self.step_info_label = QLabel(tr("realtime.waiting_data"))
        step_info_layout.addWidget(self.step_info_label)
        
        self.clear_btn = QPushButton(tr("realtime.clear_button"))
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
        self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
        self.plot_widget.setLabel('bottom', tr("realtime.x_axis_gate_voltage"))
        self.plot_widget.setTitle(tr("realtime.waiting_data_title"))
        
        # 性能设置
        self.plot_widget.setAntialiasing(False)
        self.plot_widget.setClipToView(True)
        
        # 添加图例
        self.legend = self.plot_widget.addLegend()
        
        # === 绘图对象管理 ===
        # 单曲线绘图对象（用于transfer和transient）
        self.single_plot_line = None
        
        # 多曲线绘图对象（用于output）
        self.plot_lines = {}  # {curve_name: PlotDataItem}
        
        layout.addWidget(self.plot_widget)
        
        # Debug area
        debug_frame = QFrame()
        debug_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 4px;")
        debug_layout = QHBoxLayout(debug_frame)
        
        self.debug_label = QLabel(tr("realtime.no_data_received"))
        self.debug_label.setStyleSheet("color: #666; font-size: 10px;")
        debug_layout.addWidget(self.debug_label)
        
        self.data_count_label = QLabel(tr("realtime.points_label", count=0))
        self.data_count_label.setStyleSheet("color: #666; font-size: 10px;")
        self.data_count_label.setAlignment(Qt.AlignRight)
        debug_layout.addWidget(self.data_count_label)
        
        layout.addWidget(debug_frame)

    def _set_debug_message(self, text, force=False):
        """Throttled debug label updates to avoid UI overload."""
        now = time.time()
        if force or (now - self._last_debug_update) >= self._debug_update_interval:
            if self.debug_label.text() != text:
                self.debug_label.setText(text)
            self._last_debug_update = now

    def _update_step_info_label(self, text):
        """Update step info only when it changes."""
        if text != self._last_step_info_text:
            self.step_info_label.setText(text)
            self._last_step_info_text = text

    def _apply_step_labels(self, step_type):
        """Update axis labels/title only when step type changes."""
        if step_type == 'transient':
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_time"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_transient"))
        elif step_type == 'output':
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_drain_voltage"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_output"))
        else:
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_gate_voltage"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_transfer"))
        self._last_label_step_type = step_type

    def _maybe_enable_autorange(self, x=False, y=False, force=False):
        """Limit expensive autorange recalculations."""
        now = time.time()
        if force or (now - self._last_autorange_update) >= self._autorange_interval:
            self.plot_widget.enableAutoRange(x=x, y=y)
            self._last_autorange_update = now
    
    def toggle_circular_buffer(self, enabled):
        """开关环形缓冲区"""
        self.use_circular_buffer = enabled
        if enabled:
            # 如果启用，且当前数据已超过最大值，立即裁剪
            if len(self.data_x) > self.MAX_POINTS:
                self.data_x = self.data_x[-self.MAX_POINTS:]
                self.data_y = self.data_y[-self.MAX_POINTS:]
                self.update_plot()
    
    def toggle_auto_scrolling(self, enabled):
        """切换自动滚动时间窗口功能"""
        self.auto_scrolling_enabled = enabled
    
    def toggle_point_symbols(self, enabled):
        """切换是否显示数据点符号"""
        if self.current_step_type in ['transfer', 'transient'] and self.single_plot_line:
            if enabled:
                self.single_plot_line.setSymbol('o')
                self.single_plot_line.setSymbolSize(4)
                self.single_plot_line.setSymbolBrush(pg.mkBrush('b'))
            else:
                self.single_plot_line.setSymbol(None)
        elif self.current_step_type == 'output':
            for line in self.plot_lines.values():
                if enabled:
                    line.setSymbol('o')
                    line.setSymbolSize(4)
                    line.setSymbolBrush(pg.mkBrush('b'))
                else:
                    line.setSymbol(None)
    
    def clear_data(self):
        """手动清除图表数据"""
        # 清除单曲线数据
        self.data_x = np.array([])
        self.data_y = np.array([])
        self.new_point_buffer_x = []
        self.new_point_buffer_y = []

        # 清除多曲线数据
        self.output_curves_data = {}
        self.current_output_gate_voltage = None
        self.output_data_buffer = []
        self.expected_gate_voltages = set()

        # 重置统计
        self.total_received_points = 0

        # 清除图例
        self.legend.clear()

        # 清除所有绘图对象
        if self.single_plot_line:
            self.single_plot_line.setData([], [])

        for line in self.plot_lines.values():
            line.setData([], [])

        # 更新UI
        self.data_count_label.setText(tr("realtime.points_label", count=0))
        self._set_debug_message(tr("realtime.chart_cleared"), force=True)
    
    def reset_plot_for_step_type(self, step_type):
        """根据步骤类型重置绘图对象"""
        # 清除图例
        self.legend.clear()
        
        # 移除所有现有的绘图对象
        if self.single_plot_line:
            self.plot_widget.removeItem(self.single_plot_line)
            self.single_plot_line = None
        
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        # 根据步骤类型创建相应的绘图对象
        if step_type in ['transfer', 'transient']:
            # 创建单曲线绘图对象
            self.single_plot_line = self.plot_widget.plot([], [], 
                                                        pen=pg.mkPen(color='b', width=2),
                                                        name="Current")
        # output类型的绘图对象会在接收到数据时动态创建
        
        # 关键修复：重置视图范围，启用自动范围调整
        self._maybe_enable_autorange(x=True, y=True, force=True)
        logger.info(f"重置绘图对象并启用自动范围调整: {step_type}")
    
    def update_status_label(self):
        """Update the status label with current info"""
        if not self.test_id:
            self.status_label.setText(tr("realtime.start_test_prompt"))
            self.status_frame.setStyleSheet("background-color: #f1f1f1; border-radius: 4px;")
        elif self.test_completed:
            self.status_label.setText(f"[OK] {tr('realtime.test_completed', test_id=self.test_id)}")
            self.status_frame.setStyleSheet("background-color: #f6ffed; border-radius: 4px;")
        else:
            self.status_label.setText(f"[>] {tr('realtime.collecting_data', test_id=self.test_id)}")
            self.status_frame.setStyleSheet("background-color: #e6f7ff; border-radius: 4px;")
    
    def set_test_id(self, test_id):
        """Set the test ID and reset the plot"""
        self.test_id = test_id
        self.test_completed = False
        self.transient_packet_size = None
        self.data_buffer = ""
        
        # 重置步骤跟踪
        self.current_step_index = -1
        self.current_step_id = ""
        self._last_label_step_type = None
        self._last_step_info_text = None
        
        # 清除所有数据
        self.clear_data()
        
        # 更新UI
        self.update_status_label()
        self.path_frame.setVisible(False)
        self._set_debug_message(f"Test ID set: {test_id}", force=True)
        self.data_count_label.setText(tr("realtime.points_label", count=0))
        self.step_info_label.setText(tr("realtime.waiting_data"))
        self._last_step_info_text = self.step_info_label.text()
        
        # 重置图表
        self.plot_widget.setTitle(tr("realtime.waiting_data_title"))
    
    def set_test_completed(self):
        """标记测试完成"""
        self.test_completed = True
        self.update_status_label()
        
        # 处理所有缓冲的output数据
        if self.current_step_type == 'output':
            self.flush_output_data_buffer()
    
    def set_path_readable(self, path, step_type=None):
        """Set the readable workflow path and localize known step type tokens"""
        if path:
            # Replace common step type names with current language equivalents
            type_map = {
                "转移特性": tr("workflow.test_type.transfer"),
                "瞬态特性": tr("workflow.test_type.transient"),
                "输出特性": tr("workflow.test_type.output"),
                "循环": tr("workflow.test_type.loop"),
                "迭代": tr("workflow.test_type.loop"),
                "Transfer": tr("workflow.test_type.transfer"),
                "Transient": tr("workflow.test_type.transient"),
                "Output": tr("workflow.test_type.output"),
                "Loop": tr("workflow.test_type.loop"),
            }
            localized_path = path
            for src, tgt in type_map.items():
                localized_path = localized_path.replace(src, tgt)

            # If the first segment duplicates current step type, strip it
            segments = [seg.strip() for seg in localized_path.split('>') if seg.strip()]
            type_names = {
                "transfer": tr("workflow.test_type.transfer"),
                "transient": tr("workflow.test_type.transient"),
                "output": tr("workflow.test_type.output"),
                "loop": tr("workflow.test_type.loop"),
            }
            if step_type in type_names and segments:
                first = segments[0]
                # If the first segment starts with the step type name, drop it
                if first.startswith(type_names[step_type]):
                    segments = segments[1:]
            # Remove consecutive duplicates
            collapsed = []
            for seg in segments:
                if not collapsed or collapsed[-1] != seg:
                    collapsed.append(seg)
            if segments:
                localized_path = " > ".join(collapsed)

            if localized_path == self.path_readable and self.path_frame.isVisible():
                return
            self.path_readable = localized_path
            self.path_label.setText(localized_path)
            self.path_frame.setVisible(True)
        else:
            self.path_frame.setVisible(False)
    
    def parse_output_metadata(self, hex_data):
        """解析hex数据中的output元数据前缀"""
        if not isinstance(hex_data, str):
            return None, None, hex_data
            
        # 检查output开始信号
        if hex_data.startswith("OUTPUT_START:"):
            try:
                meta_part = hex_data.rstrip("|")
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
                logger.error(f"解析output开始信号失败: {e}")
        
        # 检查output数据元数据
        elif hex_data.startswith("OUTPUT_META:"):
            try:
                meta_part, actual_hex_data = hex_data.split("|", 1)
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
                logger.error(f"解析output元数据失败: {e}")
        
        return None, None, hex_data
    
    def prepare_output_curve(self, gate_voltage: int, total_gate_voltages: int):
        """提前准备output曲线"""
        curve_name = f"Id(Vg={gate_voltage}mV)"
        
        # 记录预期的栅极电压
        self.expected_gate_voltages.add(gate_voltage)
        
        # 确保有对应的曲线数据结构
        if curve_name not in self.output_curves_data:
            self.output_curves_data[curve_name] = {'x': [], 'y': []}
        
        # 确保有对应的绘图曲线
        if curve_name not in self.plot_lines:
            # 创建新的绘图曲线 - 使用深色高对比度颜色（避免浅色）
            colors = [
                '#0000FF',  # 蓝色
                '#FF0000',  # 红色
                '#00AA00',  # 深绿色
                '#8B4513',  # 棕色
                '#9400D3',  # 深紫色
                '#FF8C00',  # 深橙色
                '#000000',  # 黑色
                '#DC143C',  # 深红色
                '#006400',  # 深绿色
                '#4B0082',  # 靛蓝色
            ]
            color_idx = len(self.plot_lines) % len(colors)

            line = self.plot_widget.plot([], [],
                                       pen=pg.mkPen(color=colors[color_idx], width=2),
                                       name=curve_name)
            self.plot_lines[curve_name] = line
            try:
                # 确保图例同步更新（避免第二次输出测试图例缺失）
                self.legend.addItem(line, curve_name)
            except Exception:
                pass
            
            # 关键修复：创建第一条output曲线时启用自动范围调整
            if len(self.plot_lines) == 1:
                self._maybe_enable_autorange(x=True, y=True, force=True)
                logger.info(f"创建第一条output曲线，启用自动范围调整")
            
            logger.info(f"为栅极电压 {gate_voltage}mV 创建曲线: {curve_name}")
    
    def flush_output_data_buffer(self):
        """处理缓冲的output数据"""
        if self.output_data_buffer:
            logger.info(f"处理缓冲的output数据: {len(self.output_data_buffer)} 条")
            
            for hex_data, output_metadata in self.output_data_buffer:
                self.process_output_realtime_data_immediate(hex_data, output_metadata)
            
            self.output_data_buffer.clear()
    
    def process_message(self, message):
        """处理来自后端的消息 - 修复版本"""
        try:
            msg_type = message.get("type")
            self._set_debug_message(tr("realtime.received", type=msg_type))
            
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
                if step_type == "transient":
                    self.transient_packet_size = workflow_info.get("transient_packet_size")
                
                # 构造唯一的步骤ID
                step_id = f"{step_index}-{step_type}-{path_readable}"
                
                # === 关键修复：步骤变化检测和重置 ===
                step_changed = (self.auto_step_reset_check.isChecked() and 
                              step_id != self.current_step_id and 
                              self.current_step_id)
                
                if step_changed:
                    logger.info(f"步骤变化检测: {self.current_step_type} → {step_type}")
                    # 完全清除数据
                    self.clear_data()
                    # 重置绘图对象
                    self.reset_plot_for_step_type(step_type)
                    self._set_debug_message(tr("realtime.step_changed", old=self.current_step_type, new=step_type), force=True)
                
                # 更新当前步骤信息
                self.current_step_type = step_type
                self.current_step_index = step_index
                self.current_step_id = step_id
                if step_changed or step_type != self._last_label_step_type:
                    self._apply_step_labels(step_type)
                
                # 显示步骤信息
                if path_readable:
                    self.set_path_readable(path_readable, step_type)
                    self._update_step_info_label(tr("realtime.step_info_with_path", type=step_type, index=step_index))
                else:
                    self._update_step_info_label(tr("realtime.step_info", type=step_type))
                
                # 如果是新步骤，确保有正确的绘图对象
                if step_changed or not self.single_plot_line and step_type in ['transfer', 'transient']:
                    self.reset_plot_for_step_type(step_type)
                
                # === 根据步骤类型处理数据 ===
                if step_type == 'output':
                    self.process_output_step(hex_data)
                else:
                    self.process_traditional_step(hex_data, step_type)
                    
            elif msg_type == "test_progress":
                progress = abs(message.get("progress", 0) * 100)
                if progress >= 100:
                    self.set_test_completed()
                else:
                    self.status_label.setText(f"[>] {tr('realtime.collecting_data_progress', progress=f'{progress:.1f}', test_id=self.test_id)}")
            
            elif msg_type == "test_complete" or msg_type == "test_result":
                self.set_test_completed()
        
        except Exception as e:
            self._set_debug_message(tr("realtime.error", error=str(e)), force=True)
            logger.error(f"Error processing message: {str(e)}")
            traceback.print_exc()
    
    def process_traditional_step(self, hex_data, step_type):
        """处理传统步骤（transfer/transient）- 使用单曲线逻辑"""
        if not hex_data:
            return

        mode = 'transient' if step_type == 'transient' else 'transfer'
        
        # 确保有单曲线绘图对象
        if not self.single_plot_line:
            self.single_plot_line = self.plot_widget.plot([], [], 
                                                        pen=pg.mkPen(color='b', width=2),
                                                        name="Current")
        
        # 解析数据
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return

        # 解析新数据点
        new_points = decode_bytes_to_data(
            byte_data,
            mode,
            transimpedance_ohms=self.transimpedance_ohms,
            transient_packet_size=self.transient_packet_size if mode == 'transient' else None,
            baseline_current=self.baseline_current
        )

        # 添加数据点到缓冲区，带数据验证
        if new_points:
            self.total_received_points += len(new_points)
            if mode in ('transfer', 'transient'):
                self.new_point_buffer_x.extend([point[0] for point in new_points])
                self.new_point_buffer_y.extend([point[1] for point in new_points])
                if mode == 'transient':
                    self.last_sample_ts = new_points[-1][0]
                    self._set_debug_message(f"t={self.last_sample_ts:.3f}s | +{len(new_points)} pts")
                else:
                    self._set_debug_message(tr("realtime.added_points", count=len(new_points), mode=mode))
                return
    
    def process_output_step(self, hex_data):
        """处理output步骤 - 使用多曲线逻辑"""
        if not hex_data:
            return
        
        # 关键修复：确保output步骤的视图范围正确
        # 只在第一次进入output步骤时触发
        if not self.plot_lines and not self.output_curves_data:
            self._maybe_enable_autorange(x=True, y=True, force=True)
            logger.info("首次进入output步骤，启用自动范围调整")
        
        # 解析output元数据
        signal_type, output_metadata, clean_hex_data = self.parse_output_metadata(hex_data)
        
        if signal_type == "start":
            # 处理开始信号：提前准备曲线
            gate_voltage = output_metadata["gate_voltage"]
            total_gate_voltages = output_metadata["total_gate_voltages"]
            self.prepare_output_curve(gate_voltage, total_gate_voltages)
            self._set_debug_message(tr("realtime.preparing_curve", voltage=gate_voltage), force=True)
            
        elif signal_type == "data" and output_metadata:
            # 处理实际数据：多曲线模式
            self.process_output_realtime_data(clean_hex_data, output_metadata)
            
        else:
            # 无元数据：向后兼容模式
            self.process_output_fallback(hex_data)
    
    def process_output_realtime_data(self, hex_data, output_metadata):
        """处理output类型的实时hex数据（多曲线模式）"""
        if not hex_data:
            return
            
        gate_voltage = output_metadata.get("gate_voltage", 0)
        curve_name = f"Id(Vg={gate_voltage}mV)"
        
        # 检查曲线是否已准备好
        if curve_name not in self.plot_lines or curve_name not in self.output_curves_data:
            # 曲线还没准备好，缓存数据
            logger.info(f"曲线 {curve_name} 还没准备好，缓存数据")
            self.output_data_buffer.append((hex_data, output_metadata))
            
            # 立即准备曲线
            total_gate_voltages = output_metadata.get("total_gate_voltages", 1)
            self.prepare_output_curve(gate_voltage, total_gate_voltages)
            
            # 然后立即处理缓冲的数据
            self.flush_output_data_buffer()
            return
        
        # 处理实际数据
        self.process_output_realtime_data_immediate(hex_data, output_metadata)
    
    def process_output_realtime_data_immediate(self, hex_data, output_metadata):
        """立即处理output数据"""
        gate_voltage = output_metadata.get("gate_voltage", 0)
        curve_name = f"Id(Vg={gate_voltage}mV)"

        # 解析hex数据
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return

        # 解析新数据点
        new_points = decode_bytes_to_data(
            byte_data,
            mode='transfer',
            transimpedance_ohms=self.transimpedance_ohms,
            baseline_current=self.baseline_current
        )  # output使用transfer格式

        if new_points and curve_name in self.output_curves_data:
            # 添加数据点到对应曲线，并进行额外验证
            valid_points_added = 0
            for point in new_points:
                # 额外的数据验证层：过滤异常值
                voltage = point[0]
                current = point[1]

                # 检查是否为有效数值（不是NaN或Inf）
                if not (np.isfinite(voltage) and np.isfinite(current)):
                    logger.warning(f"跳过非有效数值: voltage={voltage}, current={current}")
                    continue

                # 检查电压范围（根据实际应用调整）
                if abs(voltage) > 5.0:
                    logger.warning(f"跳过异常电压值 {voltage}V in curve {curve_name}")
                    continue

                # 检查电流范围
                if abs(current) > 1.0:
                    logger.warning(f"跳过异常电流值 {current}A in curve {curve_name}")
                    continue

                # 数据有效，添加到曲线
                self.output_curves_data[curve_name]['x'].append(voltage)
                self.output_curves_data[curve_name]['y'].append(current)
                valid_points_added += 1

            # 更新统计（只计数接收到的点，不管是否有效）
            self.total_received_points += len(new_points)

            # 如果有有效数据点被添加
            if valid_points_added > 0:
                # 内存保护
                if self.use_circular_buffer:
                    max_points_per_curve = self.MAX_POINTS // max(1, len(self.output_curves_data))
                    for curve_data in self.output_curves_data.values():
                        if len(curve_data['x']) > max_points_per_curve:
                            curve_data['x'] = curve_data['x'][-max_points_per_curve:]
                            curve_data['y'] = curve_data['y'][-max_points_per_curve:]

                # 立即更新曲线显示
                if curve_name in self.plot_lines and self.output_curves_data[curve_name]['x']:
                    self.plot_lines[curve_name].setData(
                        self.output_curves_data[curve_name]['x'],
                        self.output_curves_data[curve_name]['y']
                    )

                # 关键修复：确保output数据显示时自动调整范围
                # 仅在接收到第一批数据时触发，避免频繁调整
                total_curves_with_data = sum(1 for data in self.output_curves_data.values() if data['x'])
                if total_curves_with_data <= 2 and len(self.output_curves_data[curve_name]['x']) <= 50:
                    self._maybe_enable_autorange(x=True, y=True)

                # 更新数据计数
                total_points = sum(len(data['x']) for data in self.output_curves_data.values())
                curve_count = len(self.output_curves_data)
                self.data_count_label.setText(tr("realtime.points_label_curves", points=total_points, curves=curve_count))

                logger.info(f"添加 {valid_points_added}/{len(new_points)} 个有效数据点到 {curve_name}")
            else:
                logger.warning(f"所有 {len(new_points)} 个数据点都被过滤，未添加到 {curve_name}")
    
    def process_output_fallback(self, hex_data):
        """处理output的向后兼容模式（单曲线）"""
        # 确保有单曲线绘图对象
        if not self.single_plot_line:
            self.single_plot_line = self.plot_widget.plot([], [], 
                                                        pen=pg.mkPen(color='b', width=2),
                                                        name=tr("realtime.output_current_fallback"))
        
        # 解析数据
        byte_data = decode_hex_to_bytes(hex_data)
        if not byte_data:
            return

        new_points = decode_bytes_to_data(
            byte_data,
            mode='transfer',
            transimpedance_ohms=self.transimpedance_ohms,
            baseline_current=self.baseline_current
        )

        if new_points:
            self.total_received_points += len(new_points)
            valid_points = 0

            for point in new_points:
                x_val = point[0]
                y_val = point[1]

                # 数据验证
                if not (np.isfinite(x_val) and np.isfinite(y_val)):
                    logger.warning(f"跳过非有效数值: x={x_val}, y={y_val}")
                    continue

                if abs(x_val) > 5.0:
                    logger.warning(f"跳过异常电压值: {x_val}V")
                    continue

                if abs(y_val) > 1.0:
                    logger.warning(f"跳过异常电流值: {y_val}A")
                    continue

                # 数据有效，添加到缓冲区
                self.new_point_buffer_x.append(x_val)
                self.new_point_buffer_y.append(y_val)
                valid_points += 1

            if valid_points > 0:
                self._set_debug_message(tr("realtime.added_points_fallback", count=valid_points))
    
    def update_plot(self):
        """更新图表绘图"""
        # output多曲线模式不需要这里更新，因为在接收数据时已经实时更新
        if self.current_step_type == 'output' and self.output_curves_data:
            return
            
        # 单曲线模式更新
        if not self.new_point_buffer_x or not self.single_plot_line:
            return
            
        # 使用NumPy高效连接数组
        buffer_x = np.array(self.new_point_buffer_x)
        buffer_y = np.array(self.new_point_buffer_y)
        
        # 如果是新图表，直接设置数据
        if self.data_x.size == 0:
            self.data_x = buffer_x
            self.data_y = buffer_y
            self._maybe_enable_autorange(x=True, y=True, force=True)
        else:
            # 连接到现有数组
            self.data_x = np.append(self.data_x, buffer_x)
            self.data_y = np.append(self.data_y, buffer_y)
        
        # 内存保护（transient启用时间窗口时改为时间裁剪）
        if self.current_step_type == 'transient' and self.auto_scrolling_enabled and self.data_x.size:
            max_time = self.data_x[-1]
            window_start = max_time - self.window_size
            if window_start > 0:
                start_idx = np.searchsorted(self.data_x, window_start, side="left")
                if start_idx > 0:
                    self.data_x = self.data_x[start_idx:]
                    self.data_y = self.data_y[start_idx:]
        elif self.use_circular_buffer and len(self.data_x) > self.MAX_POINTS:
            self.data_x = self.data_x[-self.MAX_POINTS:]
            self.data_y = self.data_y[-self.MAX_POINTS:]
        
        # 清空缓冲区
        self.new_point_buffer_x = []
        self.new_point_buffer_y = []
        
        # 设置符号
        total_points = self.data_x.size
        point_symbols_enabled = self.symbol_check.isChecked()
        
        if total_points > 1000 and not point_symbols_enabled:
            self.single_plot_line.setSymbol(None)
        elif point_symbols_enabled:
            self.single_plot_line.setSymbol('o') 
            self.single_plot_line.setSymbolSize(4)
        
        # 更新图表数据（显示端采样）
        display_x = self.data_x
        display_y = self.data_y
        if self.display_max_points and total_points > self.display_max_points:
            indices = np.linspace(0, total_points - 1, self.display_max_points, dtype=int)
            display_x = self.data_x[indices]
            display_y = self.data_y[indices]
        self.single_plot_line.setData(display_x, display_y)
        
        # 滚动窗口支持
        self.sliding_window()
        
        # 更新数据计数
        if self.current_step_type == 'transient' and self.auto_scrolling_enabled:
            self.data_count_label.setText(tr("realtime.points_label", count=total_points))
        elif self.use_circular_buffer and self.total_received_points > self.MAX_POINTS:
            self.data_count_label.setText(
                tr("realtime.points_label_discarded", 
                   shown=total_points, 
                   total=self.total_received_points, 
                   discarded=self.total_received_points - total_points)
            )
        else:
            self.data_count_label.setText(tr("realtime.points_label", count=total_points))
    
    def sliding_window(self):
        """滚动窗口处理"""
        if self.current_step_type == 'transient' and self.auto_scrolling_enabled:
            if len(self.data_x) > 1:
                max_time = np.max(self.data_x)
                if max_time > self.window_size:
                    min_time = max_time - self.window_size
                    self.plot_widget.setXRange(min_time, max_time)
                    self._maybe_enable_autorange(y=True)
        else:
            # 其他图表类型自动调整范围
            self._maybe_enable_autorange(x=True, y=True)
    
    def start_new_test(self, test_id):
        """开始新的测试"""
        self.test_id = test_id
        self.test_completed = False
        self.transient_packet_size = None
        
        # 重置步骤跟踪
        self.current_step_index = -1
        self.current_step_id = ""
        self._last_label_step_type = None
        self._last_step_info_text = None
        
        # 清除所有数据
        self.clear_data()
        
        self.update_status_label()
        self.step_info_label.setText(tr("realtime.waiting_data"))
        self._last_step_info_text = self.step_info_label.text()
        self.update_timer.start(100)

    def update_translations(self):
        """Update all UI text when language changes"""
        # Control panel
        self.circular_buffer_check.setText(tr("realtime.memory_protection"))
        self.circular_buffer_check.setToolTip(tr("realtime.memory_protection_tooltip", max_points=self.MAX_POINTS))
        self.auto_step_reset_check.setText(tr("realtime.step_separation"))
        self.auto_step_reset_check.setToolTip(tr("realtime.step_separation_tooltip"))
        self.auto_scroll_check.setText(tr("realtime.time_window"))
        self.auto_scroll_check.setToolTip(tr("realtime.time_window_tooltip"))
        self.symbol_check.setText(tr("realtime.show_points"))

        # Step info and clear button
        self.clear_btn.setText(tr("realtime.clear_button"))

        # Plot labels and title
        # The title and labels are updated dynamically in process_message,
        # but we can set a default here.
        if self.current_step_type == 'transient':
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_time"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_transient"))
        elif self.current_step_type == 'output':
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_drain_voltage"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_output"))
        else: # transfer
            self.plot_widget.setLabel('bottom', tr("realtime.x_axis_gate_voltage"))
            self.plot_widget.setLabel('left', tr("realtime.y_axis_current"))
            self.plot_widget.setTitle(tr("realtime.title_transfer"))
            
        if not self.test_id:
             self.plot_widget.setTitle(tr("realtime.waiting_data_title"))

        # Refresh status messages
        self.update_status_label()
        if self.current_step_index < 0:
            self.step_info_label.setText(tr("realtime.waiting_data"))
        elif self.path_readable:
            self.step_info_label.setText(tr("realtime.step_info_with_path", type=self.current_step_type, index=self.current_step_index))
        else:
            self.step_info_label.setText(tr("realtime.step_info", type=self.current_step_type))
        self._last_step_info_text = self.step_info_label.text()

        # Debug area
        if "Received" not in self.debug_label.text():
             self._set_debug_message(tr("realtime.no_data_received"))
        
        # This will be updated on the next data point, but we can update it now
        self.update_plot()
        
        # Fallback name
        if self.single_plot_line and self.single_plot_line.name() == "Output Current":
            self.single_plot_line.setName(tr("realtime.output_current_fallback"))
        self._last_label_step_type = self.current_step_type
