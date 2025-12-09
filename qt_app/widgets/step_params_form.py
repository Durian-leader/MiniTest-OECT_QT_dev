from PyQt5.QtWidgets import (QWidget, QFormLayout, QSpinBox, QCheckBox,
                           QLabel, QGroupBox, QVBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal
# 导入自定义的无滚轮控件
from qt_app.widgets.custom_widgets import NoWheelSpinBox
# 导入翻译支持
from qt_app.i18n.translator import tr

class StepParamsFormWidget(QWidget):
    """
    Widget for editing step parameters with different form fields based on step type
    支持正确显示output类型的栅极电压列表
    """
    
    # Signal when parameters are updated
    params_updated = pyqtSignal()
    
    def __init__(self, step):
        super().__init__()
        self.step = step
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create group box for parameters
        step_type = self.step.get("type", "transfer")
        group_title = self.get_step_type_name(step_type)

        self.params_group = QGroupBox(f"{group_title}{tr('workflow.params.title_suffix')}")
        self.params_layout = QFormLayout(self.params_group)

        # Create form fields based on step type
        self.create_form_fields(step_type)

        main_layout.addWidget(self.params_group)

    def get_step_type_name(self, step_type):
        """Get a display name for step type"""
        type_keys = {
            "transfer": "workflow.test_type.transfer",
            "transient": "workflow.test_type.transient",
            "output": "workflow.test_type.output",
            "loop": "workflow.test_type.loop"
        }
        key = type_keys.get(step_type, step_type)
        return tr(key) if step_type in type_keys else step_type
        
    def create_form_fields(self, step_type):
            """Create form fields based on step type"""
            # Clear existing form fields
            self.clear_form_fields()
            
            if step_type == "transfer":
                self.create_transfer_fields()
            elif step_type == "transient":
                self.create_transient_fields()
            elif step_type == "output":  # 确保这一行存在
                self.create_output_fields()
            elif step_type == "loop":
                self.create_loop_fields()
        
    def clear_form_fields(self):
        """Clear all form fields"""
        # Remove all widgets from form layout
        while self.params_layout.rowCount() > 0:
            self.params_layout.removeRow(0)

        # Drop references to removed widgets to avoid accessing deleted Qt objects
        for attr in [
            "sweep_check", "sweep_label",
            "time_step_spin", "time_step_label",
            "source_voltage_spin", "source_voltage_label",
            "drain_voltage_spin", "drain_voltage_label",
            "gate_start_spin", "gate_start_label",
            "gate_end_spin", "gate_end_label",
            "gate_step_spin", "gate_step_label",
            "bottom_time_spin", "bottom_time_label",
            "top_time_spin", "top_time_label",
            "gate_bottom_spin", "gate_bottom_label",
            "gate_top_spin", "gate_top_label",
            "cycles_spin", "cycles_label",
            "gate_voltage_edit", "gate_voltage_list_label",
            "scan_info_label", "gate_info_label",
            "drain_start_spin", "drain_start_label",
            "drain_end_spin", "drain_end_label",
            "drain_step_spin", "drain_step_label",
            "iterations_spin", "iterations_label",
        ]:
            if hasattr(self, attr):
                setattr(self, attr, None)
    
    def create_transfer_fields(self):
        """Create form fields for transfer step"""
        params = self.step.get("params", {})
        
        # isSweep - checkbox
        self.sweep_check = QCheckBox()
        self.sweep_check.setChecked(params.get("isSweep", 1) == 1)
        self.sweep_check.stateChanged.connect(self.on_sweep_changed)
        self.sweep_label = QLabel(tr("workflow.params.is_sweep"))
        self.params_layout.addRow(self.sweep_label, self.sweep_check)
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 300))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.time_step_label = QLabel(tr("workflow.params.time_step"))
        self.params_layout.addRow(self.time_step_label, self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.source_voltage_label = QLabel(tr("workflow.params.source_voltage"))
        self.params_layout.addRow(self.source_voltage_label, self.source_voltage_spin)
        
        # drainVoltage - 使用无滚轮版本的SpinBox
        self.drain_voltage_spin = NoWheelSpinBox()
        self.drain_voltage_spin.setRange(-2500, 2500)
        self.drain_voltage_spin.setValue(params.get("drainVoltage", 100))
        self.drain_voltage_spin.setSuffix(" mV")
        self.drain_voltage_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.drain_voltage_label = QLabel(tr("workflow.params.drain_voltage"))
        self.params_layout.addRow(self.drain_voltage_label, self.drain_voltage_spin)
        
        # gateVoltageStart - 使用无滚轮版本的SpinBox
        self.gate_start_spin = NoWheelSpinBox()
        self.gate_start_spin.setRange(-2500, 2500)
        self.gate_start_spin.setValue(params.get("gateVoltageStart", -300))
        self.gate_start_spin.setSuffix(" mV")
        self.gate_start_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.gate_start_label = QLabel(tr("workflow.params.gate_voltage_start"))
        self.params_layout.addRow(self.gate_start_label, self.gate_start_spin)
        
        # gateVoltageEnd - 使用无滚轮版本的SpinBox
        self.gate_end_spin = NoWheelSpinBox()
        self.gate_end_spin.setRange(-2500, 2500)
        self.gate_end_spin.setValue(params.get("gateVoltageEnd", 400))
        self.gate_end_spin.setSuffix(" mV")
        self.gate_end_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.gate_end_label = QLabel(tr("workflow.params.gate_voltage_end"))
        self.params_layout.addRow(self.gate_end_label, self.gate_end_spin)
        
        # gateVoltageStep - 使用无滚轮版本的SpinBox
        self.gate_step_spin = NoWheelSpinBox()
        self.gate_step_spin.setRange(-1000, 1000)
        self.gate_step_spin.setValue(params.get("gateVoltageStep", 10))
        self.gate_step_spin.setSuffix(" mV")
        self.gate_step_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.gate_step_label = QLabel(tr("workflow.params.gate_voltage_step"))
        self.params_layout.addRow(self.gate_step_label, self.gate_step_spin)


    def create_transient_fields(self):
        """Create form fields for transient step"""
        params = self.step.get("params", {})
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 1))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_transient_param_changed)
        self.time_step_label = QLabel(tr("workflow.params.time_step"))
        self.params_layout.addRow(self.time_step_label, self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_transient_param_changed)
        self.source_voltage_label = QLabel(tr("workflow.params.source_voltage"))
        self.params_layout.addRow(self.source_voltage_label, self.source_voltage_spin)
        
        # drainVoltage - 使用无滚轮版本的SpinBox
        self.drain_voltage_spin = NoWheelSpinBox()
        self.drain_voltage_spin.setRange(-2500, 2500)
        self.drain_voltage_spin.setValue(params.get("drainVoltage", 100))
        self.drain_voltage_spin.setSuffix(" mV")
        self.drain_voltage_spin.valueChanged.connect(self.on_transient_param_changed)
        self.drain_voltage_label = QLabel(tr("workflow.params.drain_voltage"))
        self.params_layout.addRow(self.drain_voltage_label, self.drain_voltage_spin)
        
        # bottomTime - 使用无滚轮版本的SpinBox
        self.bottom_time_spin = NoWheelSpinBox()
        self.bottom_time_spin.setRange(0, 100000)
        self.bottom_time_spin.setValue(params.get("bottomTime", 500))
        self.bottom_time_spin.setSuffix(" ms")
        self.bottom_time_spin.valueChanged.connect(self.on_transient_param_changed)
        self.bottom_time_label = QLabel(tr("workflow.params.bottom_time"))
        self.params_layout.addRow(self.bottom_time_label, self.bottom_time_spin)
        
        # topTime - 使用无滚轮版本的SpinBox
        self.top_time_spin = NoWheelSpinBox()
        self.top_time_spin.setRange(0, 100000)
        self.top_time_spin.setValue(params.get("topTime", 500))
        self.top_time_spin.setSuffix(" ms")
        self.top_time_spin.valueChanged.connect(self.on_transient_param_changed)
        self.top_time_label = QLabel(tr("workflow.params.top_time"))
        self.params_layout.addRow(self.top_time_label, self.top_time_spin)
        
        # gateVoltageBottom - 使用无滚轮版本的SpinBox
        self.gate_bottom_spin = NoWheelSpinBox()
        self.gate_bottom_spin.setRange(-2500, 2500)
        self.gate_bottom_spin.setValue(params.get("gateVoltageBottom", -300))
        self.gate_bottom_spin.setSuffix(" mV")
        self.gate_bottom_spin.valueChanged.connect(self.on_transient_param_changed)
        self.gate_bottom_label = QLabel(tr("workflow.params.gate_voltage_bottom"))
        self.params_layout.addRow(self.gate_bottom_label, self.gate_bottom_spin)
        
        # gateVoltageTop - 使用无滚轮版本的SpinBox
        self.gate_top_spin = NoWheelSpinBox()
        self.gate_top_spin.setRange(-2500, 2500)
        self.gate_top_spin.setValue(params.get("gateVoltageTop", 400))
        self.gate_top_spin.setSuffix(" mV")
        self.gate_top_spin.valueChanged.connect(self.on_transient_param_changed)
        self.gate_top_label = QLabel(tr("workflow.params.gate_voltage_top"))
        self.params_layout.addRow(self.gate_top_label, self.gate_top_spin)
        
        # cycles - 使用无滚轮版本的SpinBox
        self.cycles_spin = NoWheelSpinBox()
        self.cycles_spin.setRange(1, 10000)
        self.cycles_spin.setValue(params.get("cycles", 5))
        self.cycles_spin.valueChanged.connect(self.on_transient_param_changed)
        self.cycles_label = QLabel(tr("workflow.params.cycles"))
        self.params_layout.addRow(self.cycles_label, self.cycles_spin)

    def create_output_fields(self):
        """Create form fields for output step - 修改版本，支持栅极电压列表显示"""
        params = self.step.get("params", {})
        
        # isSweep - checkbox
        self.sweep_check = QCheckBox()
        self.sweep_check.setChecked(params.get("isSweep", 1) == 1)
        self.sweep_check.stateChanged.connect(self.on_sweep_changed)
        self.sweep_label = QLabel(tr("workflow.params.is_sweep"))
        self.params_layout.addRow(self.sweep_label, self.sweep_check)
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 300))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_output_param_changed)
        self.time_step_label = QLabel(tr("workflow.params.time_step"))
        self.params_layout.addRow(self.time_step_label, self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_output_param_changed)
        self.source_voltage_label = QLabel(tr("workflow.params.source_voltage"))
        self.params_layout.addRow(self.source_voltage_label, self.source_voltage_spin)
        
        # gateVoltageList - 改为文本输入框，支持列表
        from qt_app.widgets.custom_widgets import NoWheelLineEdit
        self.gate_voltage_edit = NoWheelLineEdit()
        # 设置默认值或从参数中获取
        gate_voltages = params.get("gateVoltageList", [0, 200, 400])
        if isinstance(gate_voltages, list):
            gate_voltage_text = ",".join(map(str, gate_voltages))
        else:
            gate_voltage_text = str(gate_voltages)
        self.gate_voltage_edit.setText(gate_voltage_text)
        self.gate_voltage_edit.setPlaceholderText(tr("workflow.params.gate_voltage_list_placeholder"))
        self.gate_voltage_edit.textChanged.connect(self.on_output_param_changed)
        self.gate_voltage_list_label = QLabel(tr("workflow.params.gate_voltage_list"))
        self.params_layout.addRow(self.gate_voltage_list_label, self.gate_voltage_edit)
        
        # 显示栅压扫描信息
        self.gate_info_label = QLabel()
        self.update_gate_voltage_info()
        self.scan_info_label = QLabel(tr("workflow.params.scan_info"))
        self.params_layout.addRow(self.scan_info_label, self.gate_info_label)
        
        # drainVoltageStart - 使用无滚轮版本的SpinBox
        self.drain_start_spin = NoWheelSpinBox()
        self.drain_start_spin.setRange(-2500, 2500)
        self.drain_start_spin.setValue(params.get("drainVoltageStart", -100))
        self.drain_start_spin.setSuffix(" mV")
        self.drain_start_spin.valueChanged.connect(self.on_output_param_changed)
        self.drain_start_label = QLabel(tr("workflow.params.drain_voltage_start"))
        self.params_layout.addRow(self.drain_start_label, self.drain_start_spin)
        
        # drainVoltageEnd - 使用无滚轮版本的SpinBox
        self.drain_end_spin = NoWheelSpinBox()
        self.drain_end_spin.setRange(-2500, 2500)
        self.drain_end_spin.setValue(params.get("drainVoltageEnd", 400))
        self.drain_end_spin.setSuffix(" mV")
        self.drain_end_spin.valueChanged.connect(self.on_output_param_changed)
        self.drain_end_label = QLabel(tr("workflow.params.drain_voltage_end"))
        self.params_layout.addRow(self.drain_end_label, self.drain_end_spin)
        
        # drainVoltageStep - 使用无滚轮版本的SpinBox
        self.drain_step_spin = NoWheelSpinBox()
        self.drain_step_spin.setRange(-1000, 1000)
        self.drain_step_spin.setValue(params.get("drainVoltageStep", 10))
        self.drain_step_spin.setSuffix(" mV")
        self.drain_step_spin.valueChanged.connect(self.on_output_param_changed)
        self.drain_step_label = QLabel(tr("workflow.params.drain_voltage_step"))
        self.params_layout.addRow(self.drain_step_label, self.drain_step_spin)

    def parse_gate_voltage_list(self, text):
        """解析栅极电压列表"""
        try:
            # 移除空格并按逗号分割
            values = [int(float(x.strip())) for x in text.split(',') if x.strip()]  # 先转float再转int
            # 验证范围
            for val in values:
                if not -2500 <= val <= 2500:
                    return None, tr("workflow.errors.gate_voltage_out_of_range", value=val)
            return values, None
        except ValueError:
            return None, tr("workflow.errors.gate_voltage_format_error")

    def update_gate_voltage_info(self):
        """更新栅极电压信息显示"""
        if hasattr(self, 'gate_voltage_edit'):
            text = self.gate_voltage_edit.text()
            values, error = self.parse_gate_voltage_list(text)
            
            if error:
                self.gate_info_label.setText(f"[X] {error}")
                self.gate_info_label.setStyleSheet("color: red;")
            elif values:
                # 更加详细的信息显示
                min_vg = min(values) / 1000.0  # 转换为V
                max_vg = max(values) / 1000.0
                info_text = f"[OK] {tr('workflow.info.num_curves', count=len(values))}"
                if len(values) > 1:
                    info_text += f" ({tr('workflow.info.vg_range', min=f'{min_vg:.3f}', max=f'{max_vg:.3f}')})"
                else:
                    info_text += f" ({tr('workflow.info.vg_single', value=f'{min_vg:.3f}')})"
                    
                self.gate_info_label.setText(info_text)
                self.gate_info_label.setStyleSheet("color: green;")
            else:
                self.gate_info_label.setText(f"[!] {tr('workflow.info.enter_valid_gate_voltage')}")
                self.gate_info_label.setStyleSheet("color: orange;")

    def on_output_param_changed(self):
        """Handle output parameter changes"""
        if "params" not in self.step:
            self.step["params"] = {}
        
        params = self.step["params"]
        params["timeStep"] = self.time_step_spin.value()
        params["sourceVoltage"] = self.source_voltage_spin.value()
        params["drainVoltageStart"] = self.drain_start_spin.value()
        params["drainVoltageEnd"] = self.drain_end_spin.value()
        params["drainVoltageStep"] = self.drain_step_spin.value()
        
        # 处理栅极电压列表
        if hasattr(self, 'gate_voltage_edit'):
            gate_text = self.gate_voltage_edit.text()
            gate_values, error = self.parse_gate_voltage_list(gate_text)
            if gate_values:
                params["gateVoltageList"] = gate_values
            else:
                params["gateVoltageList"] = [0]  # 默认值
            
            # 更新信息显示
            self.update_gate_voltage_info()
        
        self.params_updated.emit()

    def create_loop_fields(self):
        """Create form fields for loop step"""
        # iterations - 使用无滚轮版本的SpinBox
        self.iterations_spin = NoWheelSpinBox()
        self.iterations_spin.setRange(1, 10000)
        self.iterations_spin.setValue(self.step.get("iterations", 1))
        self.iterations_spin.valueChanged.connect(self.on_iterations_changed)
        self.iterations_label = QLabel(tr("workflow.params.iterations"))
        self.params_layout.addRow(self.iterations_label, self.iterations_spin)
    
    def set_step(self, step):
        """Set step and update form fields"""
        self.step = step
        
        # Update UI
        step_type = self.step.get("type", "transfer")
        group_title = self.get_step_type_name(step_type)
        self.params_group.setTitle(f"{group_title}{tr('workflow.params.title_suffix')}")
        self.create_form_fields(step_type)
    
    def on_sweep_changed(self, state):
        """Handle is_sweep checkbox change"""
        if "params" not in self.step:
            self.step["params"] = {}
        
        self.step["params"]["isSweep"] = 1 if state == Qt.Checked else 0
        self.params_updated.emit()
    
    def on_transfer_param_changed(self):
        """Handle transfer parameter changes"""
        if "params" not in self.step:
            self.step["params"] = {}
        
        params = self.step["params"]
        params["timeStep"] = self.time_step_spin.value()
        params["sourceVoltage"] = self.source_voltage_spin.value()
        params["drainVoltage"] = self.drain_voltage_spin.value()
        params["gateVoltageStart"] = self.gate_start_spin.value()
        params["gateVoltageEnd"] = self.gate_end_spin.value()
        params["gateVoltageStep"] = self.gate_step_spin.value()
        
        self.params_updated.emit()
    
    def on_transient_param_changed(self):
        """Handle transient parameter changes"""
        if "params" not in self.step:
            self.step["params"] = {}
        
        params = self.step["params"]
        params["timeStep"] = self.time_step_spin.value()
        params["sourceVoltage"] = self.source_voltage_spin.value()
        params["drainVoltage"] = self.drain_voltage_spin.value()
        params["bottomTime"] = self.bottom_time_spin.value()
        params["topTime"] = self.top_time_spin.value()
        params["gateVoltageBottom"] = self.gate_bottom_spin.value()
        params["gateVoltageTop"] = self.gate_top_spin.value()
        params["cycles"] = self.cycles_spin.value()
        
        self.params_updated.emit()

    def on_iterations_changed(self, value):
        """Handle iterations spinbox change"""
        self.step["iterations"] = value
        self.params_updated.emit()

    def update_translations(self):
        """Update all UI text when language changes"""
        step_type = self.step.get("type", "transfer")
        group_title = self.get_step_type_name(step_type)
        self.params_group.setTitle(f"{group_title}{tr('workflow.params.title_suffix')}")

        # Update all form labels
        self.update_form_labels()

    def update_form_labels(self):
        """Update text of all form labels."""
        # Guard against accessing deleted Qt objects by checking for None
        if getattr(self, 'sweep_label', None):
            self.sweep_label.setText(tr("workflow.params.is_sweep"))
        if getattr(self, 'time_step_label', None):
            self.time_step_label.setText(tr("workflow.params.time_step"))
        if getattr(self, 'source_voltage_label', None):
            self.source_voltage_label.setText(tr("workflow.params.source_voltage"))
        if getattr(self, 'drain_voltage_label', None):
            self.drain_voltage_label.setText(tr("workflow.params.drain_voltage"))
        if getattr(self, 'gate_start_label', None):
            self.gate_start_label.setText(tr("workflow.params.gate_voltage_start"))
        if getattr(self, 'gate_end_label', None):
            self.gate_end_label.setText(tr("workflow.params.gate_voltage_end"))
        if getattr(self, 'gate_step_label', None):
            self.gate_step_label.setText(tr("workflow.params.gate_voltage_step"))
        if getattr(self, 'bottom_time_label', None):
            self.bottom_time_label.setText(tr("workflow.params.bottom_time"))
        if getattr(self, 'top_time_label', None):
            self.top_time_label.setText(tr("workflow.params.top_time"))
        if getattr(self, 'gate_bottom_label', None):
            self.gate_bottom_label.setText(tr("workflow.params.gate_voltage_bottom"))
        if getattr(self, 'gate_top_label', None):
            self.gate_top_label.setText(tr("workflow.params.gate_voltage_top"))
        if getattr(self, 'cycles_label', None):
            self.cycles_label.setText(tr("workflow.params.cycles"))
        if getattr(self, 'gate_voltage_list_label', None):
            self.gate_voltage_list_label.setText(tr("workflow.params.gate_voltage_list"))
        if getattr(self, 'gate_voltage_edit', None):
            self.gate_voltage_edit.setPlaceholderText(tr("workflow.params.gate_voltage_list_placeholder"))
        if getattr(self, 'scan_info_label', None):
            self.scan_info_label.setText(tr("workflow.params.scan_info"))
        if getattr(self, 'drain_start_label', None):
            self.drain_start_label.setText(tr("workflow.params.drain_voltage_start"))
        if getattr(self, 'drain_end_label', None):
            self.drain_end_label.setText(tr("workflow.params.drain_voltage_end"))
        if getattr(self, 'drain_step_label', None):
            self.drain_step_label.setText(tr("workflow.params.drain_voltage_step"))
        if getattr(self, 'iterations_label', None):
            self.iterations_label.setText(tr("workflow.params.iterations"))
        
        # Re-validate/update info text which may contain translatable strings
        if getattr(self, 'gate_info_label', None):
            self.update_gate_voltage_info()
