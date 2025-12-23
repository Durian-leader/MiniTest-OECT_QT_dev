"""
串口通信模块 - serial_device.py
负责单设备的串口通信（简化版）
"""

import asyncio
import serial_asyncio
import serial.tools.list_ports
import platform
from typing import Dict, Optional, Callable, Tuple, List
import time

# 停止命令常量
STOP_COMMAND = "FF030100FE"


class SerialPortManager:
    """串口管理器，负责跨平台串口发现"""
    
    @staticmethod
    def get_available_ports() -> List[Dict[str, str]]:
        """获取所有可用的串口设备"""
        ports = []
        for port_info in serial.tools.list_ports.comports():
            port_dict = {
                'device': port_info.device,
                'name': port_info.name or 'Unknown',
                'description': port_info.description or 'No description',
            }
            ports.append(port_dict)
        return ports


class AsyncSerialDevice:
    """异步串口设备类，负责单个设备的通信"""
    
    def __init__(self, port: str, baudrate: int = 512000):
        """
        初始化异步串口设备
        
        Args:
            port: 串口号 (如 "COM1" 或 "/dev/cu.usbserial-xxx")
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        self.reader = None
        self.writer = None
        self.is_connected = False
        self.is_busy = False
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
    
    async def connect(self) -> bool:
        """异步连接到设备"""
        if self.port is None:
            return False
            
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, 
                baudrate=self.baudrate,
                timeout=1.0
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"连接失败: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """异步断开设备连接"""
        if not self.is_connected:
            return
            
        try:
            if self.writer:
                self.writer.close()
                if hasattr(self.writer, 'wait_closed'):
                    await self.writer.wait_closed()
                else:
                    await asyncio.sleep(0.1)
            self.is_connected = False
        except Exception as e:
            print(f"断开连接失败: {str(e)}")
    
    def hex_str_to_bytes(self, hex_str: str) -> bytes:
        """将十六进制字符串转换为字节流"""
        hex_str = hex_str.replace(" ", "")
        if len(hex_str) % 2 != 0:
            raise ValueError("Hex string length must be even")
        return bytes.fromhex(hex_str)
    
    def bytes_to_hex_str(self, data: bytes) -> str:
        """将字节流转换为十六进制字符串"""
        return data.hex().upper()
    
    async def send_command(self, command: str) -> None:
        """异步发送命令"""
        if not self.is_connected:
            raise ConnectionError("设备未连接")
            
        command_bytes = self.hex_str_to_bytes(command)
        async with self._lock:
            self.writer.write(command_bytes)
            await self.writer.drain()
    
    def stop(self) -> None:
        """请求停止当前操作 - 只设置标志，由异步循环处理发送停止命令"""
        self._stop_event.set()
    
    def clear_stop(self) -> None:
        """清除停止请求状态"""
        self._stop_event.clear()
    
    async def query_device_identity(self, timeout: float = 3.0) -> str:
        """
        查询设备身份
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            设备身份字符串
        """
        from core.command_gen import gen_who_are_you_cmd, bytes_to_hex
        from core.data_parser import decode_identity_response
        
        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                return "连接失败"
        
        # 生成命令
        cmd = bytes_to_hex(gen_who_are_you_cmd())
        
        # 发送并接收（使用特殊结束序列）
        end_sequences = {
            "identity_end1": "DEADBEEFC0FFEE00",
            "identity_end2": "FEFEFEFEFEFEFEFE",
        }
        
        try:
            await self.send_command(cmd)
            
            received_data = bytearray()
            import time
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    import asyncio
                    new_data = await asyncio.wait_for(self.reader.read(256), 0.5)
                    if new_data:
                        received_data.extend(new_data)
                        
                        # 检查结束序列
                        for seq_name, end_seq in end_sequences.items():
                            end_bytes = self.hex_str_to_bytes(end_seq)
                            if received_data.endswith(end_bytes):
                                return decode_identity_response(bytes(received_data))
                except asyncio.TimeoutError:
                    pass
            
            if received_data:
                return decode_identity_response(bytes(received_data))
            return "查询超时"
            
        except Exception as e:
            return f"查询失败: {str(e)}"
    
    async def send_and_receive_command(
        self,
        command: str,
        end_sequence: str,
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        data_callback: Optional[Callable[[str], None]] = None,
        packet_size: int = 7
    ) -> Tuple[bytes, str]:
        """
        异步发送命令并接收响应，直到收到结束序列
        
        Args:
            command: 十六进制命令字符串
            end_sequence: 结束序列十六进制字符串
            timeout: 总超时时间(秒)，None表示无超时
            progress_callback: 进度回调函数，参数为已接收字节数
            data_callback: 数据回调函数，参数为接收到的数据十六进制字符串
            packet_size: 数据包长度（字节数）
            
        Returns:
            元组 (接收到的数据, 结束原因)
        """
        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                return b'', "connection_failed"
            
        if self.is_busy:
            return b'', "device_busy"
            
        self.is_busy = True
        self.clear_stop()
        
        data_buffer = bytearray()
        
        try:
            end_bytes = self.hex_str_to_bytes(end_sequence)
            
            await self.send_command(command)
            
            received_data = bytearray()
            start_time = time.time()
            read_timeout = 0.5
            
            while True:
                # 检查是否达到总超时时间
                if timeout is not None and (time.time() - start_time > timeout):
                    await self.send_command(STOP_COMMAND)
                    return received_data, "timeout"
                
                # 检查是否收到停止请求
                if self._stop_event.is_set():
                    await self.send_command(STOP_COMMAND)
                    await asyncio.sleep(0.1)
                    return received_data, "stopped"
                
                # 尝试读取数据
                try:
                    new_data = await asyncio.wait_for(self.reader.read(1024), read_timeout)
                    
                    if new_data:
                        received_data.extend(new_data)
                        len_received = len(received_data)
                        
                        if progress_callback:
                            progress_callback(len_received)
                            
                        if data_callback:
                            if packet_size > 0:
                                data_buffer.extend(new_data)
                                while len(data_buffer) >= packet_size:
                                    packet = data_buffer[:packet_size]
                                    data_buffer = data_buffer[packet_size:]
                                    data_callback(self.bytes_to_hex_str(packet))
                            else:
                                data_callback(new_data)
                        
                        # 检查是否收到结束序列
                        if len(received_data) >= len(end_bytes):
                            if received_data[-len(end_bytes):] == end_bytes:
                                # 在返回前处理data_buffer中残留的完整数据包
                                if data_callback and packet_size > 0:
                                    while len(data_buffer) >= packet_size:
                                        packet = data_buffer[:packet_size]
                                        data_buffer = data_buffer[packet_size:]
                                        data_callback(self.bytes_to_hex_str(packet))
                                return received_data, "completed"
                                
                except asyncio.TimeoutError:
                    pass

        except Exception as e:
            return b'', f"error: {str(e)}"
        finally:
            self.is_busy = False
