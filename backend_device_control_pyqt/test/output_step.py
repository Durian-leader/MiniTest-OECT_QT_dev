from backend_device_control_pyqt.test.step import TestStep, bytes_to_hex
from backend_device_control_pyqt.core.command_gen import gen_output_cmd
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np
import asyncio
import logging

logger = logging.getLogger(__name__)

class OutputStep(TestStep):
    """Output characteristics test step with multiple gate voltages support"""
    
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
        
        # 解析栅极电压列表
        gate_voltage_list = params.get("gateVoltageList", [0])
        if isinstance(gate_voltage_list, list):
            self.gate_voltages = gate_voltage_list
        else:
            self.gate_voltages = [gate_voltage_list]
        
        # 存储所有扫描的数据
        self.all_scan_data = {}  # {vg_value: data_array}
        
        # *** 新增：当前栅极电压跟踪 ***
        self.current_gate_voltage = None
        
    def get_step_type(self) -> str:
        return "output"
        
    def get_data_mode(self) -> str:
        return "output"  # 使用专门的output模式
        
    def get_packet_size(self) -> int:
        return 5  # Output data uses 5-byte packets (2-byte voltage + 3-byte current)
        
    def get_end_sequence(self) -> str:
        return "CDABEFCDABEFCDAB"  # 小端字节序
        
    def calculate_total_bytes(self) -> int:
        """Calculate expected total bytes based on voltage parameters"""
        drain_voltage_start = self.params["drainVoltageStart"]
        drain_voltage_end = self.params["drainVoltageEnd"]
        drain_voltage_step = self.params["drainVoltageStep"]
        is_sweep = self.params["isSweep"]
        
        # Calculate number of data points per gate voltage
        points_per_vg = int(abs(drain_voltage_end - drain_voltage_start) / drain_voltage_step) + 1
        if is_sweep:
            points_per_vg *= 2  # Double if sweep back
        
        # Total points = points per Vg * number of Vg values
        total_points = points_per_vg * len(self.gate_voltages)
        
        return total_points * self.get_packet_size()
        
    def generate_command(self, gate_voltage: int) -> str:
        """Generate command for output test with specific gate voltage"""
        # 创建临时参数，替换栅极电压
        temp_params = self.params.copy()
        temp_params["gateVoltage"] = gate_voltage
        
        cmd_list = gen_output_cmd(temp_params)
        return bytes_to_hex(cmd_list)
    
    def create_enhanced_data_callback(self, gate_voltage: int):
        """
        *** 创建增强的数据回调函数，添加output元数据到hex数据 ***
        """
        def enhanced_data_callback(hex_data, dev_id: str):
            try:
                # *** 关键思路：将元数据编码到hex数据的特殊前缀中 ***
                # 创建一个特殊的标记，让前端能识别这是output数据
                output_metadata = {
                    "gate_voltage": gate_voltage,
                    "gate_voltage_index": self.gate_voltages.index(gate_voltage),
                    "total_gate_voltages": len(self.gate_voltages),
                    "is_output_curve": True
                }
                
                # 将元数据编码为特殊标记字符串
                # 格式: OUTPUT_META:{gate_voltage}:{index}:{total}|{hex_data}
                meta_prefix = f"OUTPUT_META:{gate_voltage}:{self.gate_voltages.index(gate_voltage)}:{len(self.gate_voltages)}|"
                enhanced_hex_data = meta_prefix + hex_data
                
                # 使用原有的data_callback传递增强后的数据
                self.data_callback(enhanced_hex_data, dev_id)
                
                logger.debug(f"发送增强output数据: test_id={self.step_id}, gate_voltage={gate_voltage}mV")
            except Exception as e:
                logger.error(f"发送output数据失败: {str(e)}")
                # 降级：如果失败就发送原始数据
                self.data_callback(hex_data, dev_id)
        
        return enhanced_data_callback
        
    async def execute(self):
        """Execute the output test step for all gate voltages"""
        self.start_time = datetime.now().isoformat()
        
        logger.info(f"开始输出特性测试，栅极电压: {self.gate_voltages}")
        
        # 为每个栅极电压执行一次扫描
        for i, gate_voltage in enumerate(self.gate_voltages):
            logger.info(f"扫描栅极电压 {gate_voltage} mV ({i+1}/{len(self.gate_voltages)})")
            
            # *** 关键修改：设置当前栅极电压 ***
            self.current_gate_voltage = gate_voltage
            
            # 更新进度
            base_progress = i / len(self.gate_voltages)
            
            # 生成命令
            cmd_str = self.generate_command(gate_voltage)
            
            # *** 创建增强的数据回调函数 ***
            enhanced_data_callback = self.create_enhanced_data_callback(gate_voltage)
            
            # 执行单次扫描
            def progress_callback_wrapper(length: int, dev_id: str):
                # 计算当前扫描的进度
                scan_progress = min(length / (self.calculate_total_bytes() / len(self.gate_voltages)), 1.0)
                # 计算总体进度
                total_progress = base_progress + (scan_progress / len(self.gate_voltages))
                self.progress_callback(int(total_progress * self.calculate_total_bytes()), dev_id)
            
            # *** 使用增强的数据回调函数 ***
            data_result, reason = await self.device.send_and_receive_command(
                command=cmd_str,
                end_sequences={self.get_step_type(): self.get_end_sequence()},
                timeout=None,
                packet_size=self.get_packet_size(),
                progress_callback=progress_callback_wrapper,
                data_callback=enhanced_data_callback  # 使用增强回调
            )
            
            # 存储这次扫描的数据，并清理结束序列
            if data_result:
                # 清理结束序列，防止影响下次扫描
                cleaned_data = self.remove_end_sequence(data_result)
                self.all_scan_data[gate_voltage] = cleaned_data
            
            # 检查是否被停止
            if self.device._stop_event.is_set():
                break
                
            # 扫描间隔（可选）
            if i < len(self.gate_voltages) - 1:
                await asyncio.sleep(0.5)  # 500ms间隔
        
        self.end_time = datetime.now().isoformat()
        
        # 合并所有数据
        combined_data = self.combine_all_scan_data()
        
        logger.info(f"输出特性测试完成，共收集 {len(self.all_scan_data)} 组数据")
        
        return combined_data, "completed"

    def remove_end_sequence(self, data: bytes) -> bytes:
        """移除数据末尾的结束序列"""
        end_sequence = bytes.fromhex("CDABEFCDABEFCDAB")  # Output的结束序列
        
        if data.endswith(end_sequence):
            logger.info(f"移除Output结束序列，原长度: {len(data)}")
            cleaned_data = data[:-len(end_sequence)]
            logger.info(f"清理后长度: {len(cleaned_data)}")
            return cleaned_data
        
        return data
    
    def combine_all_scan_data(self) -> bytes:
        """将所有栅极电压的数据合并为CSV格式的字节数据"""
        try:
            from backend_device_control_pyqt.core.serial_data_parser import bytes_to_numpy
            
            # 解析每个栅极电压的数据
            parsed_data = {}
            for vg, raw_data in self.all_scan_data.items():
                if raw_data:
                    # 使用transfer模式解析（因为都是电压+电流格式）
                    data_array = bytes_to_numpy(raw_data, mode='transfer')
                    if len(data_array) > 0:
                        parsed_data[vg] = data_array
            
            if not parsed_data:
                return b''
            
            # 找到所有的漏极电压值（从第一组数据中获取）
            first_vg = list(parsed_data.keys())[0]
            drain_voltages = parsed_data[first_vg][:, 0]  # 第一列是电压
            
            # 创建CSV内容
            csv_lines = []
            
            # 创建表头
            header = ["Vd"]
            for vg in sorted(self.gate_voltages):
                if vg in parsed_data:
                    header.append(f"Id(Vg={vg}mV)")
            csv_lines.append(",".join(header))
            
            # 添加数据行
            for i, vd in enumerate(drain_voltages):
                row = [f"{vd:.3f}"]
                
                for vg in sorted(self.gate_voltages):
                    if vg in parsed_data and i < len(parsed_data[vg]):
                        current = parsed_data[vg][i, 1]  # 第二列是电流
                        row.append(f"{current:g}")
                    else:
                        row.append("")  # 数据缺失
                
                csv_lines.append(",".join(row))
            
            # 转换为字节
            csv_content = "\n".join(csv_lines)
            return csv_content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"合并扫描数据失败: {str(e)}")
            return b''