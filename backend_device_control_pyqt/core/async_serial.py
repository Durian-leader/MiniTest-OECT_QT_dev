import asyncio
import serial_asyncio
import logging
from typing import Dict, Optional, Callable, Tuple, Any, Union
import time

# 添加停止命令常量
STOP_COMMAND = "FF030100FE"

# 配置logger - 修复日志重复问题
logger = logging.getLogger(__name__)
# 检查是否已有处理器，避免重复添加
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # 避免日志传播到根日志器，防止重复
    logger.propagate = False

class AsyncSerialDevice:
    """异步串口设备类，负责单个设备的通信"""
    
    def __init__(self, device_id: str, port: str, baudrate: int = 512000):
        """
        初始化异步串口设备
        
        Args:
            device_id: 设备唯一标识符
            port: 串口号 (如 "COM1")
            baudrate: 波特率
        """
        self.device_id = device_id
        self.port = port
        self.baudrate = baudrate
        self.reader = None
        self.writer = None
        self.is_connected = False
        self.is_busy = False
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
    
    async def connect(self) -> bool:
        """
        异步连接到设备
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, 
                baudrate=self.baudrate
            )
            self.is_connected = True
            logger.info(f"设备 {self.device_id} (端口: {self.port}) 连接成功")
            return True
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
                await asyncio.sleep(0.1)  # 给予关闭操作一些时间
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
        data_callback: Optional[Callable[[str, str], None]] = None,
        packet_size: Optional[int] = None  # 新增参数，指定数据包长度（字节数）
    ) -> Tuple[Union[str, None], str]:
        """
        异步发送命令并接收响应，直到收到结束序列
        
        Args:
            command: 十六进制命令字符串
            end_sequences: 结束序列字典，键为序列名称，值为十六进制字符串
            timeout: 总超时时间(秒)，None表示无超时
            progress_callback: 进度回调函数，参数为(已接收字节数, 设备ID)
            data_callback: 数据回调函数，参数为(接收到的数据十六进制字符串, 设备ID)
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
                    new_data = await asyncio.wait_for(self.reader.read(1024), read_timeout)
                    
                    if new_data:
                        received_data.extend(new_data)
                        len_received = len(received_data)
                        
                        # 回调进度信息
                        if progress_callback:
                            progress_callback(len_received, self.device_id)
                            
                        # 处理数据回调
                        if data_callback:
                            if packet_size > 0:
                                # 按照指定的包大小处理数据
                                data_buffer.extend(new_data)
                                
                                # 处理完整的数据包
                                while len(data_buffer) >= packet_size:
                                    packet = data_buffer[:packet_size]
                                    data_buffer = data_buffer[packet_size:]
                                    data_callback(self.bytes_to_hex_str(packet), self.device_id)
                            else:
                                # 如果没有指定包大小，按原方式处理
                                # data_callback(self.bytes_to_hex_str(new_data), self.device_id)
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
            if "PermissionError" in str(e) or "拒绝访问" in str(e):
                logger.info(f"设备 {self.device_id} 尝试重置连接...")
                try:
                    if self.writer:
                        self.writer.close()
                    self.is_connected = False
                    await asyncio.sleep(0.5)  # 等待串口释放
                except Exception as reset_err:
                    logger.error(f"重置连接失败: {reset_err}")
            
            return None, f"error: {str(e)}"
        finally:
            self.is_busy = False


if __name__ == "__main__":
    import sys

    async def main():
        port = 'COM3'
        device = AsyncSerialDevice(device_id="dev1", port=port)

        success = await device.connect()
        if not success:
            return

        # 示例命令
        test_command = "00000000000000000000000000000000FF010E01000A00000064000000F4016400FE"
        end_sequences = {
            "end1": "FFFFFFFFFFFFFFFF",  # 示例结束序列
        }

        def progress_callback(length, dev_id):
            print(f"[{dev_id}] 已接收 {length} 字节")

        def data_callback(data_hex, dev_id):
            print(f"[{dev_id}] 接收到: {data_hex}")

        # 指定数据包长度为7字节
        result, reason = await device.send_and_receive_command(
            command=test_command,
            end_sequences=end_sequences,
            timeout=1000,
            progress_callback=progress_callback,
            data_callback=data_callback,
            packet_size=7  # 直接指定数据包长度
        )

        print(f"接收结果：{result}")
        print(f"结束原因：{reason}")

        await device.disconnect()

    asyncio.run(main())