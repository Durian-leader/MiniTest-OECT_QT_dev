from backend_device_control_pyqt.test.step import TestStep, bytes_to_hex
from backend_device_control_pyqt.core.command_gen import gen_transient_cmd
from datetime import datetime
from typing import Dict, Any, Optional

class TransientStep(TestStep):
    """Transient characteristics test step"""
    
    def __init__(self, device, step_id, command_id, params,
                 workflow_progress_info: Optional[Dict[str, Any]] = None):
        """
        Initialize transient step
        
        Args:
            device: AsyncSerialDevice instance
            step_id: Unique identifier for this step
            command_id: Command identifier for the hardware
            params: Parameters for the transient test
            workflow_progress_info: Additional workflow progress context
        """
        super().__init__(device, step_id, params, workflow_progress_info)
        self.command_id = command_id
        packet_size = params.get("transient_packet_size", 7)
        try:
            packet_size = int(packet_size)
        except (TypeError, ValueError):
            packet_size = 7
        if packet_size not in (7, 9):
            packet_size = 7
        self.packet_size = packet_size
        
    def get_step_type(self) -> str:
        return "transient"
        
    def get_data_mode(self) -> str:
        return "transient"
        
    def get_packet_size(self) -> int:
        return self.packet_size  # Transient data uses 7-byte or 9-byte packets
        
    def get_end_sequence(self) -> str:
        return "FEFEFEFEFEFEFEFE"
        
    def calculate_total_bytes(self) -> int:
        """Calculate expected total bytes based on timing parameters"""
        time_step = self.params["timeStep"]
        bottom_time = self.params["bottomTime"]
        top_time = self.params["topTime"]
        cycles = self.params["cycles"]
        
        # Calculate number of data points
        total_points = int((bottom_time + top_time) / time_step) * cycles
        return total_points * self.get_packet_size()
        
    def generate_command(self) -> str:
        """Generate command for transient test"""
        cmd_list = gen_transient_cmd(self.params)
        return bytes_to_hex(cmd_list)
        
    async def execute(self):
        """Execute the transient test step"""
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
