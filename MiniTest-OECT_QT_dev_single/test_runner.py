"""
测试运行器模块 - test_runner.py
负责执行 loop + transient 工作流
"""

import asyncio
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

from core.serial_device import AsyncSerialDevice
from core.command_gen import gen_transient_cmd, bytes_to_hex
from core.data_parser import hex_to_numpy


class DataSaver:
    """数据保存器，负责增量保存数据到CSV"""
    
    def __init__(self, save_dir: str, filename: str):
        self.save_dir = save_dir
        self.filename = filename
        self.filepath = os.path.join(save_dir, filename)
        self.buffer = []
        self.header_written = False
        
        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)
    
    def add_data(self, data):
        """添加数据到缓冲区"""
        if hasattr(data, 'tolist'):
            self.buffer.extend(data.tolist())
        else:
            self.buffer.extend(data)
    
    def flush_to_file(self):
        """将缓冲区数据写入文件"""
        if not self.buffer:
            return
            
        try:
            mode = 'a' if self.header_written else 'w'
            with open(self.filepath, mode, encoding='utf-8') as f:
                if not self.header_written:
                    f.write("timestamp_s,current_A\n")
                    self.header_written = True
                    
                for row in self.buffer:
                    f.write(f"{row[0]:.6f},{row[1]:.12e}\n")
            self.buffer.clear()
        except Exception as e:
            print(f"保存数据失败: {e}")
    
    def finalize(self):
        """完成保存，写入所有剩余数据"""
        self.flush_to_file()


class TestRunner(QThread):
    """测试运行线程，执行loop+transient工作流"""
    
    # 信号定义
    data_received = pyqtSignal(object)  # 实时数据信号 (numpy array)
    progress_updated = pyqtSignal(int, int)  # (当前loop, 总loop)
    status_changed = pyqtSignal(str)  # 状态变化信号
    test_finished = pyqtSignal(str)  # 测试完成信号 (原因)
    bytes_received = pyqtSignal(int)  # 已接收字节数
    loop_started = pyqtSignal(int)  # 新loop开始信号 (loop索引)
    
    def __init__(self, port: str, loop_count: int, transient_params: Dict[str, Any], 
                 save_dir: str, parent=None):
        super().__init__(parent)
        self.port = port
        self.loop_count = loop_count
        self.transient_params = transient_params
        self.save_dir = save_dir
        
        self.device: Optional[AsyncSerialDevice] = None
        self.data_saver: Optional[DataSaver] = None
        self._stop_requested = False
        self._last_save_time = 0
        self.save_interval = 10  # 秒
        
    def request_stop(self):
        """请求停止测试"""
        self._stop_requested = True
        if self.device:
            self.device.stop()
    
    def run(self):
        """运行测试工作流"""
        asyncio.run(self._run_async())
    
    async def _run_async(self):
        """异步运行测试"""
        try:
            # 初始化设备
            self.device = AsyncSerialDevice(port=self.port)
            self.status_changed.emit("正在连接设备...")
            
            if not await self.device.connect():
                self.test_finished.emit("连接失败")
                return
            
            self.status_changed.emit("设备已连接")
            
            # 生成基础时间戳（用于文件名）
            base_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 执行loop
            for loop_idx in range(self.loop_count):
                if self._stop_requested:
                    break
                    
                self.loop_started.emit(loop_idx + 1)  # 通知UI清空绘图
                self.progress_updated.emit(loop_idx + 1, self.loop_count)
                self.status_changed.emit(f"执行第 {loop_idx + 1}/{self.loop_count} 轮")
                
                # 为每个loop创建单独的数据保存器
                filename = f"transient_{base_timestamp}_loop{loop_idx + 1:03d}.csv"
                self.data_saver = DataSaver(self.save_dir, filename)
                self._last_save_time = time.time()
                
                # 执行transient测试
                reason = await self._run_transient()
                
                # 保存当前loop的剩余数据
                if self.data_saver:
                    self.data_saver.finalize()
                
                if reason == "stopped":
                    break
                elif reason != "completed":
                    self.status_changed.emit(f"测试异常: {reason}")
                    break
                
            # 断开设备
            await self.device.disconnect()
            
            if self._stop_requested:
                self.test_finished.emit("用户停止")
            else:
                self.test_finished.emit("测试完成")
                
        except Exception as e:
            self.test_finished.emit(f"错误: {str(e)}")
    
    async def _run_transient(self) -> str:
        """执行单次transient测试"""
        # 生成命令
        cmd_list = gen_transient_cmd(self.transient_params)
        cmd_str = bytes_to_hex(cmd_list)
        
        # 定义回调
        def progress_callback(length: int):
            self.bytes_received.emit(length)
            
            # 检查是否需要保存数据
            current_time = time.time()
            if current_time - self._last_save_time >= self.save_interval:
                if self.data_saver:
                    self.data_saver.flush_to_file()
                self._last_save_time = current_time
        
        def data_callback(hex_data: str):
            # 解析数据
            data = hex_to_numpy(hex_data)
            if len(data) > 0:
                # 发送到UI
                self.data_received.emit(data)
                # 添加到保存缓冲区
                if self.data_saver:
                    self.data_saver.add_data(data)
        
        # 发送命令并接收数据
        _, reason = await self.device.send_and_receive_command(
            command=cmd_str,
            end_sequence="FEFEFEFEFEFEFEFE",
            timeout=None,
            progress_callback=progress_callback,
            data_callback=data_callback,
            packet_size=7
        )
        
        return reason
