from PyQt5.QtWidgets import (QWidget, QFormLayout, QSpinBox, QCheckBox,
                           QLabel, QGroupBox, QVBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal
# 导入自定义的无滚轮控件
from qt_app.widgets.custom_widgets import NoWheelSpinBox, NoWheelDoubleSpinBox

class StepParamsFormWidget(QWidget):
    """
    Widget for editing step parameters with different form fields based on step type
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
        
        self.params_group = QGroupBox(f"{group_title}参数")
        self.params_layout = QFormLayout(self.params_group)
        
        # Create form fields based on step type
        self.create_form_fields(step_type)
        
        main_layout.addWidget(self.params_group)
    
    def get_step_type_name(self, step_type):
        """Get a display name for step type"""
        type_names = {
            "transfer": "转移特性",
            "transient": "瞬态特性",
            "output": "输出特性",  # 新增
            "loop": "循环"
        }
        return type_names.get(step_type, step_type)
    
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
    
    def create_transfer_fields(self):
        """Create form fields for transfer step"""
        params = self.step.get("params", {})
        
        # isSweep - checkbox
        self.sweep_check = QCheckBox()
        self.sweep_check.setChecked(params.get("isSweep", 1) == 1)
        self.sweep_check.stateChanged.connect(self.on_sweep_changed)
        self.params_layout.addRow("是否扫描:", self.sweep_check)
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 300))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("时间步长:", self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("源电压:", self.source_voltage_spin)
        
        # drainVoltage - 使用无滚轮版本的SpinBox
        self.drain_voltage_spin = NoWheelSpinBox()
        self.drain_voltage_spin.setRange(-2500, 2500)
        self.drain_voltage_spin.setValue(params.get("drainVoltage", 100))
        self.drain_voltage_spin.setSuffix(" mV")
        self.drain_voltage_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("漏电压:", self.drain_voltage_spin)
        
        # gateVoltageStart - 使用无滚轮版本的SpinBox
        self.gate_start_spin = NoWheelSpinBox()
        self.gate_start_spin.setRange(-2500, 2500)
        self.gate_start_spin.setValue(params.get("gateVoltageStart", -300))
        self.gate_start_spin.setSuffix(" mV")
        self.gate_start_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("栅压起点:", self.gate_start_spin)
        
        # gateVoltageEnd - 使用无滚轮版本的SpinBox
        self.gate_end_spin = NoWheelSpinBox()
        self.gate_end_spin.setRange(-2500, 2500)
        self.gate_end_spin.setValue(params.get("gateVoltageEnd", 400))
        self.gate_end_spin.setSuffix(" mV")
        self.gate_end_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("栅压终点:", self.gate_end_spin)
        
        # gateVoltageStep - 使用无滚轮版本的SpinBox
        self.gate_step_spin = NoWheelSpinBox()
        self.gate_step_spin.setRange(-1000, 1000)
        self.gate_step_spin.setValue(params.get("gateVoltageStep", 10))
        self.gate_step_spin.setSuffix(" mV")
        self.gate_step_spin.valueChanged.connect(self.on_transfer_param_changed)
        self.params_layout.addRow("栅压步长:", self.gate_step_spin)


    def create_transient_fields(self):
        """Create form fields for transient step"""
        params = self.step.get("params", {})
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 1))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("时间步长:", self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("源电压:", self.source_voltage_spin)
        
        # drainVoltage - 使用无滚轮版本的SpinBox
        self.drain_voltage_spin = NoWheelSpinBox()
        self.drain_voltage_spin.setRange(-2500, 2500)
        self.drain_voltage_spin.setValue(params.get("drainVoltage", 100))
        self.drain_voltage_spin.setSuffix(" mV")
        self.drain_voltage_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("漏电压:", self.drain_voltage_spin)
        
        # bottomTime - 使用无滚轮版本的SpinBox
        self.bottom_time_spin = NoWheelSpinBox()
        self.bottom_time_spin.setRange(0, 100000)
        self.bottom_time_spin.setValue(params.get("bottomTime", 500))
        self.bottom_time_spin.setSuffix(" ms")
        self.bottom_time_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("底部时间:", self.bottom_time_spin)
        
        # topTime - 使用无滚轮版本的SpinBox
        self.top_time_spin = NoWheelSpinBox()
        self.top_time_spin.setRange(0, 100000)
        self.top_time_spin.setValue(params.get("topTime", 500))
        self.top_time_spin.setSuffix(" ms")
        self.top_time_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("顶部时间:", self.top_time_spin)
        
        # gateVoltageBottom - 使用无滚轮版本的SpinBox
        self.gate_bottom_spin = NoWheelSpinBox()
        self.gate_bottom_spin.setRange(-2500, 2500)
        self.gate_bottom_spin.setValue(params.get("gateVoltageBottom", -300))
        self.gate_bottom_spin.setSuffix(" mV")
        self.gate_bottom_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("底部栅压:", self.gate_bottom_spin)
        
        # gateVoltageTop - 使用无滚轮版本的SpinBox
        self.gate_top_spin = NoWheelSpinBox()
        self.gate_top_spin.setRange(-2500, 2500)
        self.gate_top_spin.setValue(params.get("gateVoltageTop", 400))
        self.gate_top_spin.setSuffix(" mV")
        self.gate_top_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("顶部栅压:", self.gate_top_spin)
        
        # cycles - 使用无滚轮版本的SpinBox
        self.cycles_spin = NoWheelSpinBox()
        self.cycles_spin.setRange(1, 10000)
        self.cycles_spin.setValue(params.get("cycles", 5))
        self.cycles_spin.valueChanged.connect(self.on_transient_param_changed)
        self.params_layout.addRow("循环次数:", self.cycles_spin)

    def create_output_fields(self):
        """Create form fields for output step"""
        params = self.step.get("params", {})
        
        # isSweep - checkbox
        self.sweep_check = QCheckBox()
        self.sweep_check.setChecked(params.get("isSweep", 1) == 1)
        self.sweep_check.stateChanged.connect(self.on_sweep_changed)
        self.params_layout.addRow("是否扫描:", self.sweep_check)
        
        # timeStep - 使用无滚轮版本的SpinBox
        self.time_step_spin = NoWheelSpinBox()
        self.time_step_spin.setRange(1, 10000)
        self.time_step_spin.setValue(params.get("timeStep", 300))
        self.time_step_spin.setSuffix(" ms")
        self.time_step_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("时间步长:", self.time_step_spin)
        
        # sourceVoltage - 使用无滚轮版本的SpinBox
        self.source_voltage_spin = NoWheelSpinBox()
        self.source_voltage_spin.setRange(-2500, 2500)
        self.source_voltage_spin.setValue(params.get("sourceVoltage", 0))
        self.source_voltage_spin.setSuffix(" mV")
        self.source_voltage_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("源电压:", self.source_voltage_spin)
        
        # gateVoltage - 使用无滚轮版本的SpinBox
        self.gate_voltage_spin = NoWheelSpinBox()
        self.gate_voltage_spin.setRange(-2500, 2500)
        self.gate_voltage_spin.setValue(params.get("gateVoltage", 0))
        self.gate_voltage_spin.setSuffix(" mV")
        self.gate_voltage_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("栅电压:", self.gate_voltage_spin)
        
        # drainVoltageStart - 使用无滚轮版本的SpinBox
        self.drain_start_spin = NoWheelSpinBox()
        self.drain_start_spin.setRange(-2500, 2500)
        self.drain_start_spin.setValue(params.get("drainVoltageStart", -100))
        self.drain_start_spin.setSuffix(" mV")
        self.drain_start_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("漏压起点:", self.drain_start_spin)
        
        # drainVoltageEnd - 使用无滚轮版本的SpinBox
        self.drain_end_spin = NoWheelSpinBox()
        self.drain_end_spin.setRange(-2500, 2500)
        self.drain_end_spin.setValue(params.get("drainVoltageEnd", 400))
        self.drain_end_spin.setSuffix(" mV")
        self.drain_end_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("漏压终点:", self.drain_end_spin)
        
        # drainVoltageStep - 使用无滚轮版本的SpinBox
        self.drain_step_spin = NoWheelSpinBox()
        self.drain_step_spin.setRange(-1000, 1000)
        self.drain_step_spin.setValue(params.get("drainVoltageStep", 10))
        self.drain_step_spin.setSuffix(" mV")
        self.drain_step_spin.valueChanged.connect(self.on_output_param_changed)
        self.params_layout.addRow("漏压步长:", self.drain_step_spin)

    def create_loop_fields(self):
        """Create form fields for loop step"""
        # iterations - 使用无滚轮版本的SpinBox
        self.iterations_spin = NoWheelSpinBox()
        self.iterations_spin.setRange(1, 10000)
        self.iterations_spin.setValue(self.step.get("iterations", 1))
        self.iterations_spin.valueChanged.connect(self.on_iterations_changed)
        self.params_layout.addRow("循环次数:", self.iterations_spin)
    
    def set_step(self, step):
        """Set step and update form fields"""
        self.step = step
        
        # Update UI
        step_type = self.step.get("type", "transfer")
        self.params_group.setTitle(f"{self.get_step_type_name(step_type)}参数")
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
    
    def on_output_param_changed(self):
        """Handle output parameter changes"""
        if "params" not in self.step:
            self.step["params"] = {}
        
        params = self.step["params"]
        params["timeStep"] = self.time_step_spin.value()
        params["sourceVoltage"] = self.source_voltage_spin.value()
        params["gateVoltage"] = self.gate_voltage_spin.value()
        params["drainVoltageStart"] = self.drain_start_spin.value()
        params["drainVoltageEnd"] = self.drain_end_spin.value()
        params["drainVoltageStep"] = self.drain_step_spin.value()
        
        self.params_updated.emit()

    def on_iterations_changed(self, value):
        """Handle iterations spinbox change"""
        self.step["iterations"] = value
        self.params_updated.emit()