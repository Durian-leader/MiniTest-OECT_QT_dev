from backend_device_control_pyqt.test.step import TestStep, bytes_to_hex
from backend_device_control_pyqt.core.command_gen import gen_output_cmd
from datetime import datetime
from typing import Dict, Any, Optional

class OutputStep(TestStep):
    """Output characteristics test step"""
    
    def __init__(self, device, step_id, command_id, params, 
                 workflow_progress_info: Optional[Dict[str, Any]] = None):
        """
        Initialize output step
        
        Args:
            device: AsyncSerialDevice instance
            step_id: Unique identifier for this step
            command_id: Command identifier for the hardware
            params: Parameters for the output test
            workflow_progress_info: Additional workflow progress context
        """
        super().__init__(device, step_id, params, workflow_progress_info)
        self.command_id = command_id
        
    def get_step_type(self) -> str:
        return "output"
        
    def get_data_mode(self) -> str:
        return "transfer"  # Output使用与Transfer相同的数据格式
        
    def get_packet_size(self) -> int:
        return 5  # Output data uses 5-byte packets (2-byte voltage + 3-byte current)
        
    def get_end_sequence(self) -> str:
        return "CDABEFCDABEFCDAB"  # 使用单片机代码中定义的结束标志
        
    def calculate_total_bytes(self) -> int:
        """Calculate expected total bytes based on voltage parameters"""
        drain_voltage_start = self.params["drainVoltageStart"]
        drain_voltage_end = self.params["drainVoltageEnd"]
        drain_voltage_step = self.params["drainVoltageStep"]
        is_sweep = self.params["isSweep"]
        
        # Calculate number of data points
        total_points = int(abs(drain_voltage_end - drain_voltage_start) / drain_voltage_step) + 1
        if is_sweep:
            total_points *= 2  # Double if sweep back
            
        return total_points * self.get_packet_size()
        
    def generate_command(self) -> str:
        """Generate command for output test"""
        cmd_list = gen_output_cmd(self.params)
        return bytes_to_hex(cmd_list)
        
    async def execute(self):
        """Execute the output test step"""
        self.start_time = datetime.now().isoformat()
        
        cmd_str = self.generate_command()
        data_result, reason = await self.device.send_and_receive_command(
            command=cmd_str,
            end_sequences={self.get_step_type(): self.get_end_sequence()},
            timeout=None,
            packet_size=self.get_packet_size(),
            progress_callback=self.progress_callback,
            data_callback=self.data_callback
        )
        
        self.end_time = datetime.now().isoformat()
        self.result = data_result
        self.reason = reason
        
        return data_result, reason