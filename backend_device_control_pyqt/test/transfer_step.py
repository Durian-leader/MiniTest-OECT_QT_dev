from backend_device_control_pyqt.test.step import TestStep, bytes_to_hex
from backend_device_control_pyqt.core.command_gen import gen_transfer_cmd
from datetime import datetime
from typing import Dict, Any, Optional

class TransferStep(TestStep):
    """Transfer characteristics test step"""
    
    def __init__(self, device, step_id, command_id, params, 
                 workflow_progress_info: Optional[Dict[str, Any]] = None):
        """
        Initialize transfer step
        
        Args:
            device: AsyncSerialDevice instance
            step_id: Unique identifier for this step
            command_id: Command identifier for the hardware
            params: Parameters for the transfer test
            workflow_progress_info: Additional workflow progress context
        """
        super().__init__(device, step_id, params, workflow_progress_info)
        self.command_id = command_id
        
    def get_step_type(self) -> str:
        return "transfer"
        
    def get_data_mode(self) -> str:
        return "transfer"
        
    def get_packet_size(self) -> int:
        return 5  # Transfer data uses 5-byte packets
        
    def get_end_sequence(self) -> str:
        return "FFFFFFFFFFFFFFFF"
        
    def calculate_total_bytes(self) -> int:
        """Calculate expected total bytes based on voltage parameters"""
        gate_voltage_start = self.params["gateVoltageStart"]
        gate_voltage_end = self.params["gateVoltageEnd"]
        gate_voltage_step = self.params["gateVoltageStep"]
        is_sweep = self.params["isSweep"]
        
        # Calculate number of data points
        total_points = int(abs(gate_voltage_end - gate_voltage_start) / gate_voltage_step) + 1
        if is_sweep:
            total_points *= 2  # Double if sweep back
            
        return total_points * self.get_packet_size()
        
    def generate_command(self) -> str:
        """Generate command for transfer test"""
        cmd_list = gen_transfer_cmd(self.params)
        return bytes_to_hex(cmd_list)
        
    async def execute(self):
        """Execute the transfer test step"""
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