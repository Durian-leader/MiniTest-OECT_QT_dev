"""
数据传输进程模块 - data_transmission_process.py
负责接收测试数据，处理并分发到Qt进程和数据保存进程
修改：优化数据处理，确保实时数据正确发送到前端
"""

import os
import multiprocessing as mp
import queue
import time
import json
import signal
import sys
import threading
from typing import Dict, Any, Optional, List, Union, Tuple
import numpy as np

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

# 消息类型常量
MSG_TEST_DATA = "test_data"
MSG_TEST_PROGRESS = "test_progress"
MSG_TEST_RESULT = "test_result"
MSG_TEST_ERROR = "test_error"
MSG_SAVE_DATA = "save_data"
MSG_DEVICE_STATUS = "device_status"
MSG_SHUTDOWN = "shutdown"

# 数据批处理大小
DATA_BATCH_SIZE = 100  # 每次处理的数据点数量

class DataTransmissionManager:
    """数据传输管理器，处理测试数据的分发和处理"""
    
    def __init__(self, test_queue, qt_queue, save_queue, save_result_queue):
        """
        初始化数据传输管理器
        
        Args:
            test_queue: 从测试进程接收数据的队列
            qt_queue: 发送到Qt进程的队列
            save_queue: 发送到数据保存进程的队列
            save_result_queue: 接收数据保存进程结果的队列
        """
        self.test_queue = test_queue
        self.qt_queue = qt_queue
        self.save_queue = save_queue
        self.save_result_queue = save_result_queue
        
        # 运行标志
        self.running = True
        
        # 待处理数据缓冲区 - 用于数据批处理
        self.data_buffer = {}  # {test_id: [data_points]}
        self.data_buffer_lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            "received_messages": 0,
            "forwarded_to_qt": 0,
            "forwarded_to_save": 0,
            "processed_data_points": 0,
            "batched_data_points": 0,
            "errors": 0
        }
        self.stats_lock = threading.Lock()
        
        # 最近活动的测试
        self.active_tests = {}  # {test_id: last_activity_time}
        
        logger.info("数据传输管理器初始化完成")

    def start(self):
        """启动数据传输管理器"""
        logger.info("启动数据传输管理器")
        
        # 创建工作线程
        # 1. 主线程: 处理来自测试进程的数据
        # 2. 缓冲区处理线程: 定期处理数据缓冲区
        # 3. 保存结果处理线程: 处理来自保存进程的结果
        
        # 启动缓冲区处理线程
        buffer_thread = threading.Thread(
            target=self._buffer_processor_thread,
            name="BufferProcessor",
            daemon=True
        )
        buffer_thread.start()
        
        # 启动保存结果处理线程
        save_result_thread = threading.Thread(
            target=self._save_result_processor_thread,
            name="SaveResultProcessor",
            daemon=True
        )
        save_result_thread.start()
        
        # 主线程处理来自测试进程的数据
        self._main_processor_loop()
        
        logger.info("数据传输管理器已关闭")
        logger.info(f"统计信息: 接收消息 {self.stats['received_messages']}, " 
                    f"转发到Qt {self.stats['forwarded_to_qt']}, "
                    f"转发到保存 {self.stats['forwarded_to_save']}, "
                    f"处理数据点 {self.stats['processed_data_points']}, "
                    f"批处理数据点 {self.stats['batched_data_points']}, "
                    f"错误 {self.stats['errors']}")
    
    def _main_processor_loop(self):
        """主处理循环，处理来自测试进程的数据"""
        logger.info("主数据处理循环启动")
        
        while self.running:
            try:
                # 获取来自测试进程的消息，使用短超时避免无限阻塞
                try:
                    message = self.test_queue.get(block=True, timeout=0.1)
                except queue.Empty:
                    continue
                
                # 检查是否为关闭消息
                if message.get("type") == MSG_SHUTDOWN:
                    logger.info("收到关闭消息")
                    self.running = False
                    break
                
                # 更新统计信息
                with self.stats_lock:
                    self.stats["received_messages"] += 1
                
                # 处理不同类型的消息
                self._process_message(message)
                
            except Exception as e:
                logger.error(f"处理数据消息时发生错误: {e}")
                with self.stats_lock:
                    self.stats["errors"] += 1
    
    def _process_message(self, message: Dict[str, Any]):
        """
        处理单个消息
        
        Args:
            message: 消息字典
        """
        message_type = message.get("type")
        test_id = message.get("test_id")
        
        if test_id:
            # 更新测试活动时间
            self.active_tests[test_id] = time.time()
        
        try:
            # 基于消息类型进行处理
            if message_type == MSG_TEST_DATA:
                # 测试数据 - 总是立即发送到Qt进程
                self._handle_test_data(message)
                
            elif message_type == MSG_TEST_PROGRESS:
                # 进度消息 - 直接转发到Qt
                self._forward_to_qt(message)
                
            elif message_type == MSG_TEST_RESULT or message_type == MSG_TEST_ERROR:
                # 结果或错误 - 转发到Qt和保存
                self._forward_to_qt(message)
                
                # 测试结果不再自动转发到保存进程
                # 测试完成后数据会由测试进程一次性保存
                
            elif message_type == MSG_SAVE_DATA:
                # 保存请求 - 转发到保存进程
                self._forward_to_save(message)
                
            elif message_type == MSG_DEVICE_STATUS:
                # 设备状态 - 转发到Qt
                self._forward_to_qt(message)
                
            else:
                # 未知消息类型 - 直接转发到Qt
                logger.warning(f"未知消息类型: {message_type}")
                self._forward_to_qt(message)
                
        except Exception as e:
            logger.error(f"处理消息 {message_type} 时出错: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
    
    def _handle_test_data(self, message: Dict[str, Any]):
        """
        处理测试数据消息 - 增强版，改进数据处理以确保实时显示
        
        Args:
            message: 测试数据消息
        """
        test_id = message.get("test_id")
        data = message.get("data")
        
        if not test_id or data is None:
            logger.warning("无效的测试数据消息: 缺少test_id或data")
            return
        
        # 确保消息中的数据是字符串形式
        if isinstance(data, bytes) or isinstance(data, bytearray):
            # 将二进制数据转换为十六进制字符串
            message["data"] = data.hex().upper()
        
        # 转发实时数据到Qt界面
        self._forward_to_qt(message)
        
        # 更新统计信息
        with self.stats_lock:
            self.stats["processed_data_points"] += 1
    
    def _buffer_processor_thread(self):
        """缓冲区处理线程，定期处理积累的数据"""
        logger.info("缓冲区处理线程启动")
        
        while self.running:
            try:
                # 定期处理缓冲区 (每50毫秒检查一次)
                time.sleep(0.05)
                
                # 获取并处理缓冲区数据
                with self.data_buffer_lock:
                    # 复制缓冲区以便处理，然后清空原缓冲区
                    buffer_copy = self.data_buffer.copy()
                    self.data_buffer.clear()
                
                # 处理每个测试的数据批次
                for test_id, data_points in buffer_copy.items():
                    if not data_points:
                        continue
                    
                    # 按步骤类型分组处理
                    step_groups = {}
                    for point in data_points:
                        step_type = point.get("step_type", "unknown")
                        if step_type not in step_groups:
                            step_groups[step_type] = []
                        step_groups[step_type].append(point)
                    
                    # 处理每种步骤类型的数据
                    for step_type, points in step_groups.items():
                        # 如果达到批处理阈值，将数据发送到保存进程
                        if len(points) >= DATA_BATCH_SIZE:
                            # 组合所有数据
                            combined_data = self._combine_data_points(points)
                            
                            # 创建保存请求
                            save_message = {
                                "type": MSG_SAVE_DATA,
                                "test_id": test_id,
                                "step_type": step_type,
                                "data": combined_data,
                                "device_id": points[0].get("device_id"),
                                "workflow_info": points[0].get("workflow_info"),
                                "is_batch": True,
                                "batch_size": len(points),
                                "timestamp": time.time()
                            }
                            
                            # 发送到保存进程
                            self._forward_to_save(save_message)
                            
                            # 更新统计信息
                            with self.stats_lock:
                                self.stats["batched_data_points"] += len(points)
                        else:
                            # 如果数据点数量不够，将它们一个一个发送
                            for point in points:
                                save_message = {
                                    "type": MSG_SAVE_DATA,
                                    "test_id": test_id,
                                    "step_type": step_type,
                                    "data": point["data"],
                                    "device_id": point.get("device_id"),
                                    "workflow_info": point.get("workflow_info"),
                                    "timestamp": point.get("timestamp", time.time())
                                }
                                self._forward_to_save(save_message)
                
            except Exception as e:
                logger.error(f"缓冲区处理线程错误: {e}")
                with self.stats_lock:
                    self.stats["errors"] += 1
    
    def _combine_data_points(self, data_points: List[Dict[str, Any]]) -> bytes:
        """
        合并多个数据点为一个数据块
        
        Args:
            data_points: 数据点列表
            
        Returns:
            合并后的数据
        """
        # 提取所有数据
        all_data = []
        for point in data_points:
            data = point.get("data")
            if data is not None:
                if isinstance(data, (bytes, bytearray)):
                    all_data.append(data)
                elif isinstance(data, str):
                    # 尝试将十六进制字符串转换为字节
                    try:
                        # 移除可能的空格
                        data = data.replace(" ", "")
                        # 确保字符串长度为偶数
                        if len(data) % 2 != 0:
                            data = "0" + data
                        all_data.append(bytes.fromhex(data))
                    except ValueError:
                        # 如果不是有效的十六进制，则以UTF-8编码
                        all_data.append(data.encode('utf-8'))
        
        # 合并所有数据
        if all_data:
            return b''.join(all_data)
        return b''
    
    def _save_result_processor_thread(self):
        """保存结果处理线程，处理来自保存进程的结果"""
        logger.info("保存结果处理线程启动")
        
        while self.running:
            try:
                # 获取来自保存进程的结果
                try:
                    result = self.save_result_queue.get(block=True, timeout=0.5)
                except queue.Empty:
                    continue
                
                # 检查是否为关闭消息
                if result.get("type") == MSG_SHUTDOWN:
                    logger.debug("收到保存进程关闭消息")
                    continue
                
                # 处理保存结果
                test_id = result.get("test_id")
                status = result.get("status")
                file_path = result.get("file_path")
                
                if test_id and status:
                    # 构建结果消息
                    result_message = {
                        "type": "save_result",
                        "test_id": test_id,
                        "status": status,
                        "file_path": file_path,
                        "timestamp": time.time()
                    }
                    
                    # 如果有错误信息，添加到消息中
                    if result.get("error"):
                        result_message["error"] = result.get("error")
                    
                    # 转发到Qt
                    self._forward_to_qt(result_message)
                
            except Exception as e:
                logger.error(f"保存结果处理线程错误: {e}")
                with self.stats_lock:
                    self.stats["errors"] += 1
    
    def _forward_to_qt(self, message: Dict[str, Any]):
        """
        转发消息到Qt进程
        
        Args:
            message: 要转发的消息
        """
        try:
            # 添加调试信息
            if message.get("type") == MSG_TEST_DATA:
                logger.debug(f"转发测试数据到前端: test_id={message.get('test_id')}, data_type={type(message.get('data'))}")
            
            # 在消息中添加时间戳，如果没有的话
            if "timestamp" not in message:
                message["timestamp"] = time.time()
                
            self.qt_queue.put(message)
            with self.stats_lock:
                self.stats["forwarded_to_qt"] += 1
        except Exception as e:
            logger.error(f"转发消息到Qt进程失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1
    
    def _forward_to_save(self, message: Dict[str, Any]):
        """
        转发消息到保存进程
        
        Args:
            message: 要转发的消息
        """
        try:
            # 确保数据完整性
            if message.get("type") == MSG_SAVE_DATA:
                # 检查必要参数
                if not message.get("file_path") and not (message.get("test_id") and message.get("step_type")):
                    logger.warning(f"跳过无效的保存请求: 缺少必要参数")
                    return
                    
                # 检查数据是否存在
                if message.get("content") is None and message.get("data") is None:
                    logger.warning(f"跳过无效的保存请求: 缺少内容数据")
                    return
                    
                # 如果message中有data但没有content，将data复制到content
                if "content" not in message and "data" in message:
                    message["content"] = message["data"]
            
            self.save_queue.put(message)
            with self.stats_lock:
                self.stats["forwarded_to_save"] += 1
        except Exception as e:
            logger.error(f"转发消息到保存进程失败: {e}")
            with self.stats_lock:
                self.stats["errors"] += 1

# 进程入口函数
def run_data_transmission_process(test_queue, qt_queue, save_queue, save_result_queue, ready_event, shutdown_event):
    """
    数据传输进程入口函数
    
    Args:
        test_queue: 从测试进程接收数据的队列
        qt_queue: 发送到Qt进程的队列
        save_queue: 发送到数据保存进程的队列
        save_result_queue: 接收数据保存进程结果的队列
        ready_event: 进程就绪事件
        shutdown_event: 关闭事件
    """
    
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info(f"数据传输进程收到信号 {sig}，准备关闭")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建并启动数据传输管理器
    try:
        # 创建关闭检测线程
        def shutdown_monitor():
            while True:
                if shutdown_event.is_set():
                    logger.info("检测到关闭事件，通知数据传输管理器")
                    # 发送关闭消息到队列
                    try:
                        test_queue.put({"type": MSG_SHUTDOWN})
                    except:
                        pass
                    break
                time.sleep(0.1)
        
        # 启动关闭监控线程
        monitor_thread = threading.Thread(target=shutdown_monitor, daemon=True)
        monitor_thread.start()
        
        # 创建数据传输管理器
        manager = DataTransmissionManager(test_queue, qt_queue, save_queue, save_result_queue)
        
        # 设置就绪事件
        ready_event.set()
        logger.info("数据传输进程已就绪")
        
        # 启动管理器
        manager.start()
        
    except Exception as e:
        logger.error(f"数据传输进程发生异常: {str(e)}")
    finally:
        logger.info("数据传输进程结束")


if __name__ == "__main__":
    # 用于测试的代码
    print("此模块不应直接运行")