import asyncio
import serial_asyncio
import serial.tools.list_ports
import platform
import os
from typing import Dict, Optional, Callable, Tuple, Any, Union, List
import time

from app_config import get_serial_read_chunk_size

# 添加停止命令常量
STOP_COMMAND = "FF030100FE"
########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

class SerialPortManager:
    """串口管理器，负责跨平台串口发现和管理"""
    
    @staticmethod
    def get_available_ports() -> List[Dict[str, str]]:
        """
        获取所有可用的串口设备
        
        Returns:
            List[Dict]: 包含串口信息的字典列表
        """
        ports = []
        for port_info in serial.tools.list_ports.comports():
            port_dict = {
                'device': port_info.device,
                'name': port_info.name or 'Unknown',
                'description': port_info.description or 'No description',
                'manufacturer': port_info.manufacturer or 'Unknown',
                'vid': port_info.vid,
                'pid': port_info.pid,
                'serial_number': port_info.serial_number
            }
            ports.append(port_dict)
        return ports
    
    @staticmethod
    def find_port_by_pattern(pattern: str = None) -> Optional[str]:
        """
        根据模式查找串口
        
        Args:
            pattern: 搜索模式，如果为None则根据平台使用默认模式
            
        Returns:
            str: 找到的串口设备路径，如果没找到则返回None
        """
        system = platform.system().lower()
        
        if pattern is None:
            # 根据平台设置默认搜索模式
            if system == 'darwin':  # macOS
                patterns = ['cu.usbserial', 'cu.usbmodem', 'cu.SLAB_USBtoUART']
            elif system == 'linux':
                patterns = ['ttyUSB', 'ttyACM', 'ttyS']
            else:  # Windows
                patterns = ['COM']
        else:
            patterns = [pattern]
        
        ports = SerialPortManager.get_available_ports()
        
        for port_info in ports:
            device = port_info['device']
            for pattern in patterns:
                if pattern.lower() in device.lower():
                    logger.info(f"找到匹配的串口: {device} - {port_info['description']}")
                    return device
        
        return None
    
    @staticmethod
    def check_port_permissions(port: str) -> bool:
        """
        检查串口权限
        
        Args:
            port: 串口设备路径
            
        Returns:
            bool: 是否有访问权限
        """
        try:
            # 在 Unix 系统上检查文件权限
            if platform.system().lower() in ['darwin', 'linux']:
                return os.access(port, os.R_OK | os.W_OK)
            return True  # Windows 不需要特殊权限检查
        except Exception:
            return False


class AsyncSerialDevice:
    """异步串口设备类，负责单个设备的通信（跨平台兼容）"""
    
    def __init__(self, device_id: str, port: str = None, baudrate: int = 512000, 
                 auto_discover: bool = True):
        """
        初始化异步串口设备
        
        Args:
            device_id: 设备唯一标识符
            port: 串口号 (如 "COM1" 或 "/dev/cu.usbserial-xxx")，为None时自动发现
            baudrate: 波特率
            auto_discover: 是否自动发现串口
        """
        self.device_id = device_id
        self.baudrate = baudrate
        self.auto_discover = auto_discover
        self.reader = None
        self.writer = None
        self.is_connected = False
        self.is_busy = False
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self.read_chunk_size = max(256, int(get_serial_read_chunk_size()))
        
        # 处理串口设置
        if port is None and auto_discover:
            self.port = self._discover_port()
        else:
            self.port = port
            
        if self.port is None:
            raise ValueError("无法找到可用的串口设备")
    
    def _discover_port(self) -> Optional[str]:
        """自动发现串口设备"""
        logger.info("开始自动发现串口设备...")
        
        # 显示所有可用串口
        available_ports = SerialPortManager.get_available_ports()
        if not available_ports:
            logger.error("未找到任何串口设备")
            return None
        
        logger.info("可用串口设备:")
        for i, port_info in enumerate(available_ports):
            logger.info(f"  {i+1}. {port_info['device']} - {port_info['description']}")
        
        # 尝试自动选择合适的串口
        port = SerialPortManager.find_port_by_pattern()
        if port:
            # 检查权限
            if not SerialPortManager.check_port_permissions(port):
                logger.warning(f"串口 {port} 权限不足")
                if platform.system().lower() in ['darwin', 'linux']:
                    logger.info("请尝试以下解决方案:")
                    logger.info("1. 运行: sudo chmod 666 " + port)
                    logger.info("2. 将用户添加到 dialout 组: sudo usermod -a -G dialout $USER")
                    logger.info("3. 使用 sudo 运行程序")
            return port
        
        # 如果自动发现失败，返回第一个可用串口
        if available_ports:
            return available_ports[0]['device']
        
        return None
    
    async def connect(self) -> bool:
        """
        异步连接到设备
        
        Returns:
            bool: 连接是否成功
        """
        if self.port is None:
            logger.error(f"设备 {self.device_id} 没有指定串口")
            return False
            
        try:
            # 检查串口权限（仅在Unix系统上）
            if platform.system().lower() in ['darwin', 'linux']:
                if not SerialPortManager.check_port_permissions(self.port):
                    logger.error(f"设备 {self.device_id} 串口 {self.port} 权限不足")
                    return False
            
            # 尝试连接
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, 
                baudrate=self.baudrate,
                timeout=1.0  # 添加超时设置
            )
            self.is_connected = True
            logger.info(f"设备 {self.device_id} (端口: {self.port}) 连接成功")
            return True
            
        except PermissionError as e:
            logger.error(f"设备 {self.device_id} 权限错误: {str(e)}")
            if platform.system().lower() == 'darwin':
                logger.info("macOS 权限解决方案:")
                logger.info(f"  sudo chmod 666 {self.port}")
                logger.info("  或者运行: sudo python your_script.py")
            return False
            
        except FileNotFoundError as e:
            logger.error(f"设备 {self.device_id} 串口设备不存在: {str(e)}")
            # 尝试重新发现串口
            if self.auto_discover:
                logger.info("尝试重新发现串口设备...")
                new_port = self._discover_port()
                if new_port and new_port != self.port:
                    self.port = new_port
                    return await self.connect()
            return False
            
        except Exception as e:
            logger.error(f"设备 {self.device_id} (端口: {self.port}) 连接失败: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """异步断开设备连接"""
        if not self.is_connected:
            return
            
        try:
            if self.writer:
                self.writer.close()
                # 在某些平台上需要等待关闭完成
                if hasattr(self.writer, 'wait_closed'):
                    await self.writer.wait_closed()
                else:
                    await asyncio.sleep(0.1)  # 向后兼容
            self.is_connected = False
            logger.info(f"设备 {self.device_id} (端口: {self.port}) 断开连接")
        except Exception as e:
            logger.error(f"设备 {self.device_id} (端口: {self.port}) 断开连接失败: {str(e)}")
    
    def hex_str_to_bytes(self, hex_str: str) -> bytes:
        """将十六进制字符串转换为字节流"""
        # 移除所有空格
        hex_str = hex_str.replace(" ", "")
        # 确保字符串长度为偶数
        if len(hex_str) % 2 != 0:
            raise ValueError("Hex string length must be even")
        # 转换为字节
        return bytes.fromhex(hex_str)
    
    def bytes_to_hex_str(self, data: bytes) -> str:
        """将字节流转换为十六进制字符串"""
        return data.hex().upper()
    
    async def send_command(self, command: str) -> None:
        """
        异步发送命令
        
        Args:
            command: 十六进制命令字符串
        """
        if not self.is_connected:
            raise ConnectionError(f"设备 {self.device_id} 未连接")
            
        command_bytes = self.hex_str_to_bytes(command)
        async with self._lock:
            self.writer.write(command_bytes)
            await self.writer.drain()
            logger.debug(f"设备 {self.device_id} 发送命令: {command}")
    
    async def receive_data(self, timeout: Optional[float] = None) -> bytes:
        """
        异步接收数据，带超时
        
        Args:
            timeout: 超时时间(秒)，None表示无超时
            
        Returns:
            bytes: 接收到的数据
        """
        if not self.is_connected:
            raise ConnectionError(f"设备 {self.device_id} 未连接")
            
        try:
            if timeout:
                return await asyncio.wait_for(self.reader.read(100), timeout)
            else:
                return await self.reader.read(100)
        except asyncio.TimeoutError:
            logger.warning(f"设备 {self.device_id} 接收数据超时")
            return b''
    
    def stop(self) -> None:
        """请求停止当前操作"""
        try:
            # 异步发送命令，但使用同步调用
            asyncio.create_task(self.send_command(STOP_COMMAND))
            self._stop_event.set()
        except Exception as e:
            logger.error(f"设备 {self.device_id} 停止失败: {str(e)}")
    
    def clear_stop(self) -> None:
        """清除停止请求状态"""
        self._stop_event.clear()
    
    async def send_and_receive_command(
        self,
        command: str,
        end_sequences: Dict[str, str],
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        data_callback: Optional[Callable[[Union[str, bytes], str], None]] = None,
        packet_size: Optional[int] = None
    ) -> Tuple[Union[str, None], str]:
        """
        异步发送命令并接收响应，直到收到结束序列
        
        Args:
            command: 十六进制命令字符串
            end_sequences: 结束序列字典，键为序列名称，值为十六进制字符串
            timeout: 总超时时间(秒)，None表示无超时
            progress_callback: 进度回调函数，参数为(已接收字节数, 设备ID)
            data_callback: 数据回调函数，参数为(接收到的数据(字节或十六进制字符串), 设备ID)
            packet_size: 数据包长度（字节数），如果指定，则按固定长度切分数据包
            
        Returns:
            元组 (接收到的数据的十六进制字符串, 结束原因)
        """
        
        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                return None, "connection_failed"
            
        # 如果设备已在忙碌中，返回错误
        if self.is_busy:
            return None, "device_busy"
            
        self.is_busy = True
        self.clear_stop()  # 清除之前的停止请求
        
        # 设置数据包大小：如果为None则默认为0（不切分）
        if packet_size is None:
            packet_size = 0
            
        # 创建数据缓冲区
        data_buffer = bytearray()
        
        try:
            # 转换结束序列为字节
            end_bytes_dict = {key: self.hex_str_to_bytes(seq) for key, seq in end_sequences.items()}
            
            # 发送命令，只记录一次日志
            logger.info(f"设备 {self.device_id} 发送命令: {command}")
            await self.send_command(command)
            
            # 接收数据
            received_data = bytearray()
            start_time = time.time()
            
            # 读取超时设置为较短时间，以便定期检查停止信号
            read_timeout = 0.5
            
            while True:
                # 检查是否达到总超时时间
                if timeout is not None and (time.time() - start_time > timeout):
                    logger.warning(f"设备 {self.device_id} 超时: {timeout}秒内未收到完整响应")
                    
                    # 发送停止命令
                    await self.send_command(STOP_COMMAND)
                    
                    if received_data:
                        logger.debug(f"设备 {self.device_id} 部分接收到的数据: {received_data[:50].hex().upper()}...")
                        
                    return None, "timeout"
                
                # 检查是否收到停止请求
                if self._stop_event.is_set():
                    logger.info(f"设备 {self.device_id} 收到停止请求，发送停止命令...")
                    
                    # 发送停止命令
                    await self.send_command(STOP_COMMAND)
                    await asyncio.sleep(0.1)  # 等待命令发送完成
                    
                    return received_data, "stopped"
                
                # 尝试读取数据（带短暂超时）
                try:
                    # 适当增加单次读取大小，减少回调频次（可配置）
                    new_data = await asyncio.wait_for(self.reader.read(self.read_chunk_size), read_timeout)
                    
                    if new_data:
                        received_data.extend(new_data)
                        len_received = len(received_data)
                        
                        # 回调进度信息
                        if progress_callback:
                            progress_callback(len_received, self.device_id)
                            
                        # 处理数据回调
                        if data_callback:
                            if packet_size > 0:
                                # 按包大小聚合回调，减少每包回调的调度开销
                                data_buffer.extend(new_data)
                                full_len = (len(data_buffer) // packet_size) * packet_size
                                if full_len:
                                    chunk = bytes(data_buffer[:full_len])
                                    del data_buffer[:full_len]
                                    data_callback(chunk, self.device_id)
                            else:
                                # 如果没有指定包大小，按原方式处理
                                data_callback(new_data, self.device_id)
                            
                        logger.debug(f"设备 {self.device_id} 已接收 {len_received} 字节")
                        
                        # 检查是否收到任意结束序列
                        for seq_name, end_bytes in end_bytes_dict.items():
                            if len(received_data) >= len(end_bytes):
                                if received_data[-len(end_bytes):] == end_bytes:
                                    logger.info(f"设备 {self.device_id} 检测到结束序列: {seq_name}")
                                    return received_data, seq_name
                                    
                except asyncio.TimeoutError:
                    # 短暂超时，继续循环
                    pass

        except Exception as e:
            logger.error(f"设备 {self.device_id} 通信错误: {str(e)}")
            
            # 对于权限错误，尝试重置连接
            if any(keyword in str(e).lower() for keyword in ["permission", "拒绝访问", "access denied"]):
                logger.info(f"设备 {self.device_id} 尝试重置连接...")
                try:
                    if self.writer:
                        self.writer.close()
                        if hasattr(self.writer, 'wait_closed'):
                            await self.writer.wait_closed()
                    self.is_connected = False
                    await asyncio.sleep(0.5)  # 等待串口释放
                except Exception as reset_err:
                    logger.error(f"重置连接失败: {reset_err}")
            
            return None, f"error: {str(e)}"
        finally:
            self.is_busy = False


# 便捷函数
def list_serial_ports():
    """列出所有可用的串口设备"""
    ports = SerialPortManager.get_available_ports()
    if not ports:
        print("未找到任何串口设备")
        return
    
    print("可用串口设备:")
    for i, port_info in enumerate(ports):
        print(f"  {i+1}. {port_info['device']}")
        print(f"     名称: {port_info['name']}")
        print(f"     描述: {port_info['description']}")
        print(f"     制造商: {port_info['manufacturer']}")
        if port_info['vid'] and port_info['pid']:
            print(f"     VID:PID: {port_info['vid']:04X}:{port_info['pid']:04X}")
        print()


if __name__ == "__main__":
    import sys

    async def main():
        # 显示可用串口
        print("当前系统:", platform.system())
        list_serial_ports()
        
        # 自动发现并连接设备
        try:
            device = AsyncSerialDevice(device_id="dev1", auto_discover=True)
            print(f"选择的串口: {device.port}")
            
            success = await device.connect()
            if not success:
                print("连接失败")
                return

            # 示例命令
            test_command = "00000000000000000000000000000000FF010E01000A00000064000000F4016400FE"
            end_sequences = {
                "end1": "FFFFFFFFFFFFFFFF",  # 示例结束序列
            }

            def progress_callback(length, dev_id):
                print(f"[{dev_id}] 已接收 {length} 字节")

            def data_callback(data, dev_id):
                if isinstance(data, bytes):
                    print(f"[{dev_id}] 接收到: {data.hex().upper()}")
                else:
                    print(f"[{dev_id}] 接收到: {data}")

            # 指定数据包长度为7字节
            result, reason = await device.send_and_receive_command(
                command=test_command,
                end_sequences=end_sequences,
                timeout=10,
                progress_callback=progress_callback,
                data_callback=data_callback,
                packet_size=7
            )

            print(f"接收结果：{result}")
            print(f"结束原因：{reason}")

            await device.disconnect()
            
        except ValueError as e:
            print(f"初始化错误: {e}")
        except Exception as e:
            print(f"运行错误: {e}")

    asyncio.run(main())
