"""
测试进程模块 - test_process.py (多进程版本)
负责设备连接和测试执行，将原始数据发送到数据传输进程
修改: 实时数据只发送到数据传输进程，测试完成后再保存数据
"""

import os
import multiprocessing as mp
import queue
import time
import json
import uuid
import signal
import sys
import asyncio
import re
import numpy as np
from typing import Dict, List, Any, Optional, Set, Tuple
import serial.tools.list_ports
import serial_asyncio
from datetime import datetime

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

# 导入测试相关模块
from backend_device_control_pyqt.core.command_gen import gen_transfer_cmd, gen_transient_cmd
from backend_device_control_pyqt.core.async_serial import AsyncSerialDevice
from backend_device_control_pyqt.core.serial_data_parser import bytes_to_numpy
from backend_device_control_pyqt.test.test import Test
from backend_device_control_pyqt.test.transfer_step import TransferStep
from backend_device_control_pyqt.test.transient_step import TransientStep
from backend_device_control_pyqt.test.output_step import OutputStep


# 消息类型常量
MSG_START_TEST = "start_test"
MSG_STOP_TEST = "stop_test"
MSG_LIST_DEVICES = "list_devices"
MSG_GET_TEST_STATUS = "get_test_status"
MSG_CLIENT_MESSAGE = "client_message"
MSG_TEST_DATA = "test_data"
MSG_TEST_PROGRESS = "test_progress"
MSG_TEST_RESULT = "test_result"
MSG_TEST_ERROR = "test_error"
MSG_SAVE_DATA = "save_data"
MSG_DEVICE_STATUS = "device_status"
MSG_SHUTDOWN = "shutdown"
MSG_CALIBRATE = "calibrate"
STOP_WAIT_TIMEOUT = 3.0
DEFAULT_TRANSIMPEDANCE_OHMS = 100.0

class ProcessDataBridge:
    """进程间数据桥接器，替代原websocket桥接器"""
    
    def __init__(self, data_queue):
        """
        初始化数据桥接器
        
        Args:
            data_queue: 发送到数据传输进程的队列
        """
        self.data_queue = data_queue
        logger.info("进程数据桥接器已初始化")
    
    async def send_message(self, identifier: str, message: Dict[str, Any], is_test_id: bool = True):
        """
        发送消息到数据队列
        
        Args:
            identifier: 测试ID或设备ID
            message: 要发送的消息
            is_test_id: 是否为测试ID
        """
        # 将消息放入数据队列
        try:
            # 确保消息中包含test_id或device_id，以便正确路由
            if is_test_id and "test_id" not in message:
                message["test_id"] = identifier
            elif not is_test_id and "device_id" not in message:
                message["device_id"] = identifier
                
            # 放入队列
            # put 可能会阻塞（跨进程队列需要pickle），放到线程里避免阻塞事件循环
            await asyncio.to_thread(self.data_queue.put, message)
            logger.debug(f"消息已发送到数据队列: type={message.get('type')}, id={identifier}")
            
        except Exception as e:
            logger.error(f"发送消息到数据队列失败: {str(e)}")
    
    async def send_progress(self, test_id: str, progress: float, step_type: str, device_id: Optional[str] = None,
                          workflow_info: Optional[Dict[str, Any]] = None):
        """
        发送进度消息的便捷函数
        
        Args:
            test_id: 测试ID
            progress: 进度值(0.0-1.0)
            step_type: 步骤类型
            device_id: 设备ID(可选)
            workflow_info: 工作流信息(可选)
        """
        # 构建进度消息
        message = {
            "type": "test_progress",
            "test_id": test_id,
            "step_type": step_type,
            "progress": progress
        }
        
        # 添加设备ID
        if device_id:
            message["device_id"] = device_id
        
        # 添加工作流信息
        if workflow_info:
            message["is_workflow"] = True
            message["workflow_info"] = workflow_info
        
        # 发送消息
        await self.send_message(test_id, message, is_test_id=True)
    
    async def send_data(self, test_id: str, data: Any, step_type: str, device_id: Optional[str] = None,
                      workflow_info: Optional[Dict[str, Any]] = None, recv_ts: Optional[float] = None,
                      batch_points: Optional[int] = None):
        """
        发送数据消息的便捷函数 - 只发送到数据传输进程，不再发送到保存进程
        
        Args:
            test_id: 测试ID
            data: 数据内容
            step_type: 步骤类型
            device_id: 设备ID(可选)
            workflow_info: 工作流信息(可选)
        """
        # 构建数据消息
        message = {
            "type": "test_data",
            "test_id": test_id,
            "step_type": step_type,
            "data": data
        }
        if recv_ts:
            message["recv_ts"] = recv_ts
        if batch_points is not None:
            message["batch_points"] = batch_points
        
        # 添加设备ID
        if device_id:
            message["device_id"] = device_id
        
        # 添加工作流信息
        if workflow_info:
            message["is_workflow"] = True
            message["workflow_info"] = workflow_info
        
        # 发送消息
        await self.send_message(test_id, message, is_test_id=True)
    
    async def send_test_result(self, test_id: str, status: str, info: Optional[Dict[str, Any]] = None, 
                             device_id: Optional[str] = None):
        """
        发送测试结果消息的便捷函数
        
        Args:
            test_id: 测试ID
            status: 状态
            info: 结果信息(可选)
            device_id: 设备ID(可选)
        """
        # 构建结果消息
        message = {
            "type": "test_result",
            "test_id": test_id,
            "status": status
        }
        
        # 添加信息
        if info:
            message["info"] = info
        
        # 添加设备ID
        if device_id:
            message["device_id"] = device_id
        
        # 发送消息
        await self.send_message(test_id, message, is_test_id=True)
    
    async def send_device_status(self, device_id: str, status: str, details: Optional[Dict[str, Any]] = None):
        """
        发送设备状态消息的便捷函数
        
        Args:
            device_id: 设备ID
            status: 状态
            details: 状态详情(可选)
        """
        # 构建状态消息
        message = {
            "type": "device_status",
            "device_id": device_id,
            "status": status
        }
        
        # 添加详情
        if details:
            message.update(details)
        
        # 发送消息
        await self.send_message(device_id, message, is_test_id=False)

class TestManager:
    """测试管理器，处理设备连接、测试执行和状态跟踪"""
    
    def __init__(self, qt_command_queue, qt_result_queue, data_queue):
        """
        初始化测试管理器
        
        Args:
            qt_command_queue: 接收来自Qt进程的命令队列
            qt_result_queue: 发送结果到Qt进程的队列
            data_queue: 发送数据到数据传输进程的队列
        """
        self.qt_command_queue = qt_command_queue
        self.qt_result_queue = qt_result_queue
        self.data_queue = data_queue
        
        # 跟踪活跃设备和测试
        self.active_devices = {}  # {device_id: AsyncSerialDevice}
        self.active_tests = {}    # {test_id: Test}
        self.test_to_device = {}  # {test_id: device_id}
        self.device_baselines = {}  # {device_id or port: baseline_current}
        
        # 测试数据缓存 - 新增：为每个测试收集完整数据，测试完成后再保存
        self.test_data_cache = {}  # {test_id: {step_index: raw_data}}
        
        # 异步事件循环
        self.loop = None
        self.running = True
        
        # 测试结果记录
        self.test_results = {}  # {test_id: result_dict}
        self.device_status = {}  # {device_id: status_dict}
        self.test_tasks = {}  # {test_id: asyncio.Task}
        self.stop_tasks = set()
        self.calibration_tasks = set()
        
        # 同步执行相关
        self.sync_batches = {}  # {batch_id: {test_id: device_id}}
        self.sync_step_status = {}  # {batch_id: {step_index: {test_id: ready}}}
        self.sync_locks = {}  # {batch_id: asyncio.Lock}
        
        # 初始化自定义数据桥接器
        self.data_bridge = ProcessDataBridge(data_queue)
        
        # 初始化测试步骤类，注入自定义数据桥接器
        initialize_test_step_classes(self.data_bridge)
        
        logger.info("测试管理器已初始化")
    
    def start(self):
        """启动测试管理器"""
        logger.info("启动测试管理器")
        
        try:
            # 创建异步事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 启动主循环
            self.loop.run_until_complete(self.main_loop())
        except Exception as e:
            logger.error(f"测试管理器异常: {str(e)}")
        finally:
            # 清理资源
            self.shutdown()
    
    def shutdown(self):
        """关闭测试管理器并清理资源"""
        logger.info("关闭测试管理器")
        
        self.running = False
        
        # 停止所有测试
        for test_id in list(self.active_tests.keys()):
            try:
                asyncio.run_coroutine_threadsafe(self.stop_test(test_id=test_id), self.loop)
            except:
                pass
        
        # 关闭所有设备连接
        for device_id in list(self.active_devices.keys()):
            try:
                device = self.active_devices[device_id]
                asyncio.run_coroutine_threadsafe(device.disconnect(), self.loop)
            except:
                pass
        
        # 清理字典
        self.active_devices.clear()
        self.active_tests.clear()
        self.test_to_device.clear()
        self.test_data_cache.clear()
        self.test_tasks.clear()
        
        # 关闭事件循环
        if self.loop and self.loop.is_running():
            try:
                self.loop.stop()
            except:
                pass
        
        logger.info("测试管理器已关闭")

    def _start_test_task(self, test: Test) -> None:
        """Schedule a test and track the task for graceful stop."""
        task = asyncio.create_task(self.run_test(test))
        self.test_tasks[test.test_id] = task

        def _cleanup(_task, test_id=test.test_id):
            self.test_tasks.pop(test_id, None)

        task.add_done_callback(_cleanup)
    
    async def main_loop(self):
        """主事件循环，处理队列消息和测试执行"""
        logger.info("测试管理器主循环启动")
        
        while self.running:
            try:
                # 非阻塞检查队列，避免阻塞事件循环
                try:
                    # 使用短超时，避免无限阻塞
                    message = self.qt_command_queue.get(block=True, timeout=0.1)
                    await self.process_message(message)
                except queue.Empty:
                    # 队列为空，继续循环
                    await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                logger.info("测试管理器主循环被取消")
                break
            except Exception as e:
                logger.error(f"处理测试队列消息出错: {str(e)}")
                await asyncio.sleep(0.1)
    
    async def process_message(self, message: Dict[str, Any]):
        """
        处理队列消息
        
        Args:
            message: 接收到的消息字典
        """
        message_type = message.get("type")
        logger.info(f"处理消息: type={message_type}, request_id={message.get('request_id')}")
        
        if message_type == MSG_SHUTDOWN:
            logger.info("收到关闭信号")
            self.running = False
            return
        
        elif message_type == MSG_START_TEST:
            # 启动新测试
            test_type = message.get("test_type")
            params = message.get("params", {})
            request_id = message.get("request_id")
            
            result = None
            
            if test_type == "transfer":
                result = await self.start_transfer_test(params)
            elif test_type == "transient":
                result = await self.start_transient_test(params)
            elif test_type == "workflow":
                result = await self.start_workflow(params)
            elif test_type == "output":
                result = await self.start_output_test(params)
            else:
                result = {"status": "fail", "reason": f"Unknown test type: {test_type}"}
            
            # 如果有请求ID，返回结果
            if request_id:
                result["request_id"] = request_id
                self.qt_result_queue.put(result)
        
        elif message_type == MSG_STOP_TEST:
            # 停止测试
            device_id = message.get("device_id")
            test_id = message.get("test_id")
            request_id = message.get("request_id")
            async def _run_stop():
                try:
                    result = await self.stop_test(device_id, test_id)
                except Exception as e:
                    result = {"status": "fail", "reason": str(e)}
                if request_id:
                    result["request_id"] = request_id
                self.qt_result_queue.put(result)

            task = asyncio.create_task(_run_stop())
            self.stop_tasks.add(task)
            task.add_done_callback(lambda t: self.stop_tasks.discard(t))
        
        elif message_type == MSG_LIST_DEVICES:
            # 列出可用设备
            request_id = message.get("request_id")
            
            # 获取可用串口列表
            ports = await list_available_serial_ports()
            
            result = {
                "status": "ok",
                "data": ports
            }
            
            # 如果有请求ID，返回结果
            if request_id:
                result["request_id"] = request_id
                self.qt_result_queue.put(result)
        
        elif message_type == MSG_GET_TEST_STATUS:
            # 获取测试状态
            test_id = message.get("test_id")
            request_id = message.get("request_id")
            
            # 获取测试状态
            status = self.get_test_status(test_id)
            
            # 如果有请求ID，返回结果
            if request_id:
                status["request_id"] = request_id
                self.qt_result_queue.put(status)
        
        elif message_type == MSG_CALIBRATE:
            port = message.get("port")
            device_id = message.get("device_id")
            baudrate = message.get("baudrate", 512000)
            transimpedance_ohms = message.get("transimpedance_ohms", 100.0)
            transient_packet_size = message.get("transient_packet_size", 7)
            request_id = message.get("request_id")
            async def _run_calibration():
                try:
                    result = await self.calibrate_device(
                        port,
                        baudrate,
                        device_id,
                        transimpedance_ohms=transimpedance_ohms,
                        transient_packet_size=transient_packet_size
                    )
                except Exception as e:
                    result = {"status": "fail", "reason": str(e)}
                if request_id:
                    result["request_id"] = request_id
                self.qt_result_queue.put(result)

            task = asyncio.create_task(_run_calibration())
            self.calibration_tasks.add(task)
            task.add_done_callback(lambda t: self.calibration_tasks.discard(t))
    
    async def get_or_create_device(self, device_id: str, port: str, baudrate: int) -> Tuple[bool, Optional[AsyncSerialDevice]]:
        """
        获取或创建设备实例，并连接
        
        Args:
            device_id: 设备唯一标识符
            port: 串口
            baudrate: 波特率
            
        Returns:
            (成功标志, 设备实例或None)
        """
        # 如果设备已存在，直接返回
        if device_id in self.active_devices:
            return True, self.active_devices[device_id]
        
        # 创建新设备
        device = AsyncSerialDevice(device_id=device_id, port=port, baudrate=baudrate)
        
        # 连接设备
        success = await device.connect()
        
        if success:
            # 添加到活跃设备列表
            self.active_devices[device_id] = device
            
            # 更新设备状态
            self.device_status[device_id] = {
                "connected": True,
                "port": port,
                "baudrate": baudrate,
                "last_updated": time.time()
            }
            
            # 发送设备状态更新
            await self.data_bridge.send_device_status(
                device_id=device_id,
                status="connected",
                details={
                    "port": port,
                    "baudrate": baudrate
                }
            )
            
            return True, device
        else:
            # 更新设备状态
            self.device_status[device_id] = {
                "connected": False,
                "port": port,
                "baudrate": baudrate,
                "last_updated": time.time(),
                "error": "Connection failed"
            }
            
            # 发送设备状态更新
            await self.data_bridge.send_device_status(
                device_id=device_id,
                status="disconnected",
                details={
                    "port": port,
                    "baudrate": baudrate,
                    "error": "Connection failed"
                }
            )
            
            return False, None
    
    async def start_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        启动自定义工作流
        
        Args:
            params: 工作流参数
            
        Returns:
            工作流启动结果
        """
        # 提取必要参数
        device_id = params.get("device_id")
        port = params.get("port")
        baudrate = params.get("baudrate")
        test_id = params.get("test_id")
        transimpedance_ohms = params.get("transimpedance_ohms", 100.0)
        baseline_current = params.get("baseline_current", self.device_baselines.get(device_id, 0.0))
        baseline_current = params.get("baseline_current", self.device_baselines.get(device_id, 0.0))
        transient_packet_size = params.get("transient_packet_size", 7)
        try:
            transient_packet_size = int(transient_packet_size)
        except (TypeError, ValueError):
            transient_packet_size = 7
        if transient_packet_size not in (7, 9):
            transient_packet_size = 7
        name = params.get("name", "自定义工作流")
        description = params.get("description", "")
        chip_id = params.get("chip_id", "")
        device_number = params.get("device_number", "")
        steps = params.get("steps", [])
        sync_mode = params.get("sync_mode", False)
        batch_id = params.get("batch_id", None)
        
        # 检查必要参数
        if not all([device_id, port, baudrate, test_id, steps]):
            return {
                "status": "fail", 
                "reason": "Missing required parameters"
            }
        
        # 获取设备
        success, device = await self.get_or_create_device(device_id, port, baudrate)
        if not success:
            return {
                "status": "fail", 
                "reason": "Device connection failed"
            }
        
        # 记录测试与设备的映射关系
        self.test_to_device[test_id] = device_id
        
        # 如果是同步模式，注册到批次
        if sync_mode and batch_id:
            if batch_id not in self.sync_batches:
                self.sync_batches[batch_id] = {}
                self.sync_step_status[batch_id] = {}
                self.sync_locks[batch_id] = asyncio.Lock()
            self.sync_batches[batch_id][test_id] = device_id
            logger.info(f"Test {test_id} registered to sync batch {batch_id}")
        
        # 计算总步骤数
        total_steps = count_total_steps(steps)
        
        # 创建测试对象
        test = Test(
            test_id=test_id, 
            device_id=device_id, 
            test_type="workflow",
            port=port,
            baudrate=baudrate,
            name=name,
            description=description,
            metadata={
                "raw_params": params,
                "total_steps": total_steps,
                "chip_id": chip_id,
                "device_number": device_number,
                "sync_mode": sync_mode,
                "batch_id": batch_id,
                "transimpedance_ohms": transimpedance_ohms,
                "transient_packet_size": transient_packet_size,
                "baseline_current": baseline_current
            }
        )
        
        # 初始化测试数据缓存
        self.test_data_cache[test_id] = {}
        
        # 处理工作流步骤
        await self.process_workflow_steps(test, device, test_id, steps, sync_mode=sync_mode, batch_id=batch_id)
        
        # 添加到活跃测试列表
        self.active_tests[test_id] = test
        
        # 异步执行测试
        self._start_test_task(test)
        
        return {
            "status": "ok", 
            "msg": "workflow_started", 
            "test_id": test_id,
            "name": name,
            "description": description,
            "total_steps": total_steps
        }
    
    async def process_workflow_steps(self, test, device, test_id, steps, iteration_info=None, current_path=None, sync_mode=False, batch_id=None):
        """
        处理工作流中的步骤
        
        Args:
            test: Test实例
            device: 设备实例
            test_id: 测试ID
            steps: 步骤列表
            iteration_info: 循环信息(如果是循环中的步骤)
            current_path: 当前工作流路径 (用于跟踪嵌套路径)
            sync_mode: 是否为同步模式
            batch_id: 同步批次ID
        """
        # 初始化路径跟踪，如果未提供
        if current_path is None:
            current_path = []
        transimpedance_ohms = test.metadata.get("transimpedance_ohms", 100.0)
        baseline_current = test.metadata.get("baseline_current", 0.0)
        transient_packet_size = test.metadata.get("transient_packet_size", 7)
        try:
            transient_packet_size = int(transient_packet_size)
        except (TypeError, ValueError):
            transient_packet_size = 7
        if transient_packet_size not in (7, 9):
            transient_packet_size = 7
        
        for i, step_config in enumerate(steps):
            step_type = step_config.get("type")
            current_position = {"index": i+1, "total": len(steps), "type": step_type}
            
            # 构建当前步骤的完整路径
            step_path = current_path + [current_position]
            
            # 根据步骤类型创建不同的测试步骤
            if step_type == "transfer":
                # 创建额外的工作流进度信息
                workflow_progress_info = {
                    "workflow_path": step_path,
                    "iteration_info": iteration_info,
                    "step_index": i+1,
                    "total_steps": len(steps)
                }
                
                # 创建转移特性测试步骤
                step_params = dict(step_config.get("params", {}))
                step_params["transimpedance_ohms"] = transimpedance_ohms
                step = TransferStep(
                    device=device,
                    step_id=test_id,
                    command_id=step_config["command_id"],
                    params=step_params,
                    workflow_progress_info=workflow_progress_info
                )
                test.add_step(step)
                
            elif step_type == "transient":
                # 创建额外的工作流进度信息
                workflow_progress_info = {
                    "workflow_path": step_path,
                    "iteration_info": iteration_info,
                    "step_index": i+1,
                    "total_steps": len(steps)
                }
                
                # 创建瞬态特性测试步骤
                step_params = dict(step_config.get("params", {}))
                step_params["transimpedance_ohms"] = transimpedance_ohms
                step_params["transient_packet_size"] = transient_packet_size
                step = TransientStep(
                    device=device,
                    step_id=test_id,
                    command_id=step_config["command_id"],
                    params=step_params,
                    workflow_progress_info=workflow_progress_info
                )
                test.add_step(step)

            elif step_type == "output":
                # 创建额外的工作流进度信息
                workflow_progress_info = {
                    "workflow_path": step_path,
                    "iteration_info": iteration_info,
                    "step_index": i+1,
                    "total_steps": len(steps)
                }
                
                # 创建输出特性测试步骤
                step_params = dict(step_config.get("params", {}))
                step_params["transimpedance_ohms"] = transimpedance_ohms
                step_params["baseline_current"] = baseline_current
                step = OutputStep(
                    device=device,
                    step_id=test_id,
                    command_id=step_config["command_id"],
                    params=step_params,
                    workflow_progress_info=workflow_progress_info
                )
                test.add_step(step)   

            elif step_type == "loop":
                # 处理循环步骤
                iterations = step_config["iterations"]
                loop_steps = step_config["steps"]
                
                # 记录当前循环的嵌套信息
                current_iteration_info = {
                    "type": "loop",
                    "parent": iteration_info,
                    "total": iterations
                }
                
                # 添加循环节点到路径
                loop_path = step_path
                
                # 执行循环指定的次数
                for iteration in range(iterations):
                    current_iteration_info["current"] = iteration + 1
                    
                    # 添加循环迭代信息到路径
                    iteration_path = loop_path + [{
                        "type": "iteration", 
                        "current": iteration+1, 
                        "total": iterations
                    }]
                    
                    # 递归处理循环中的步骤
                    await self.process_workflow_steps(
                        test, device, test_id, loop_steps, 
                        current_iteration_info, 
                        iteration_path,
                        sync_mode, 
                        batch_id
                    )
    
    async def send_message_to_qt(self, message: Dict[str, Any]):
        """
        发送消息到Qt进程
        
        Args:
            message: 要发送的消息字典
        """
        try:
            self.qt_result_queue.put(message)
        except Exception as e:
            logger.error(f"Failed to send message to Qt: {e}")
    
    async def wait_for_sync_with_completion(self, batch_id: str, test_id: str, step_index):
        """
        增强的同步等待方法，支持步骤开始前和完成后的同步
        
        Args:
            batch_id: 批次ID
            test_id: 测试ID
            step_index: 步骤索引或完成标记（如 "complete_0"）
        """
        if batch_id not in self.sync_batches:
            return
        
        # 确定同步键
        sync_key = step_index
        is_completion = False
        if isinstance(step_index, str) and step_index.startswith("complete_"):
            is_completion = True
            sync_key = step_index
        
        async with self.sync_locks[batch_id]:
            # 初始化步骤状态
            if sync_key not in self.sync_step_status[batch_id]:
                self.sync_step_status[batch_id][sync_key] = {}
            
            # 标记当前测试已就绪
            self.sync_step_status[batch_id][sync_key][test_id] = True
            
            # 获取批次中所有测试
            batch_tests = self.sync_batches[batch_id]
            
            # 检查是否所有测试都已就绪
            all_ready = all(
                tid in self.sync_step_status[batch_id][sync_key] and 
                self.sync_step_status[batch_id][sync_key][tid]
                for tid in batch_tests.keys()
            )
            
            status_type = "completion" if is_completion else "start"
            logger.info(f"Sync status for batch {batch_id}, step {sync_key} ({status_type}): "
                       f"{len(self.sync_step_status[batch_id][sync_key])}/{len(batch_tests)} ready")
        
        # 如果还有设备未就绪，等待
        while not all_ready:
            await asyncio.sleep(0.1)
            
            async with self.sync_locks[batch_id]:
                # 重新检查状态
                all_ready = all(
                    tid in self.sync_step_status[batch_id][sync_key] and 
                    self.sync_step_status[batch_id][sync_key][tid]
                    for tid in batch_tests.keys()
                )
        
        logger.info(f"All devices in batch {batch_id} ready at sync point {sync_key}, proceeding")
        
        # 注意：不要立即清理状态，因为其他设备可能还在检查
        # 状态会在下一个同步点初始化时自然覆盖
    
    async def wait_for_sync(self, batch_id: str, test_id: str, step_index: int):
        """
        等待同批次所有设备到达同一步骤
        
        Args:
            batch_id: 批次ID
            test_id: 测试ID
            step_index: 步骤索引
        """
        if batch_id not in self.sync_batches:
            return
        
        async with self.sync_locks[batch_id]:
            # 初始化步骤状态
            if step_index not in self.sync_step_status[batch_id]:
                self.sync_step_status[batch_id][step_index] = {}
            
            # 标记当前测试已就绪
            self.sync_step_status[batch_id][step_index][test_id] = True
            
            # 获取批次中所有测试
            batch_tests = self.sync_batches[batch_id]
            
            # 检查是否所有测试都已就绪
            all_ready = all(
                tid in self.sync_step_status[batch_id][step_index] and 
                self.sync_step_status[batch_id][step_index][tid]
                for tid in batch_tests.keys()
            )
            
            logger.info(f"Sync status for batch {batch_id}, step {step_index}: "
                       f"{len(self.sync_step_status[batch_id][step_index])}/{len(batch_tests)} ready")
        
        # 如果还有设备未就绪，等待
        while not all_ready:
            await asyncio.sleep(0.1)
            
            async with self.sync_locks[batch_id]:
                # 重新检查状态
                all_ready = all(
                    tid in self.sync_step_status[batch_id][step_index] and 
                    self.sync_step_status[batch_id][step_index][tid]
                    for tid in batch_tests.keys()
                )
        
        logger.info(f"All devices in batch {batch_id} ready for step {step_index}, proceeding")
        
        # 发送同步完成消息到Qt
        await self.send_message_to_qt({
            "type": "sync_step_ready",
            "batch_id": batch_id,
            "step_index": step_index,
            "test_id": test_id
        })
    
    async def stop_test(self, device_id: str = None, test_id: str = None) -> Dict[str, Any]:
        """
        停止测试并保存已完成的测试信息
        
        Args:
            device_id: 设备ID (可选)
            test_id: 测试ID (可选)
            
        Returns:
            操作结果
        """
        # Prefer test_id when provided.
        if test_id and test_id in self.test_to_device:
            device_id = self.test_to_device[test_id]

        if not device_id or device_id not in self.active_devices:
            return {"status": "fail", "reason": "device_or_test_not_found"}

        device = self.active_devices[device_id]

        # Allow the running test task to finish and persist data.
        device.stop()
        await asyncio.sleep(0.1)

        if test_id:
            test_ids = [test_id]
        else:
            test_ids = [tid for tid, did in self.test_to_device.items() if did == device_id]

        if not test_ids:
            return {"status": "fail", "reason": "device_or_test_not_found"}

        tasks_by_id = {tid: self.test_tasks.get(tid) for tid in test_ids if self.test_tasks.get(tid) is not None}

        if tasks_by_id:
            done, pending = await asyncio.wait(
                list(tasks_by_id.values()),
                timeout=STOP_WAIT_TIMEOUT
            )

            if pending:
                pending_ids = [tid for tid, task in tasks_by_id.items() if task in pending]
                logger.warning(f"Stop requested for device {device_id}, pending tests: {pending_ids}")
                return {"status": "ok", "msg": "stop_pending", "pending_tests": pending_ids}

        return {"status": "ok", "msg": "stopped"}

    async def calibrate_device(self, port: str, baudrate: int, device_id: Optional[str] = None,
                               transimpedance_ohms: float = 100.0,
                               transient_packet_size: int = 7) -> Dict[str, Any]:
        """
        通过Transient测量获取基线并返回
        """
        if not port:
            return {"status": "fail", "reason": "no_port"}

        if device_id:
            for tid, did in self.test_to_device.items():
                if did == device_id:
                    return {"status": "fail", "reason": "device_busy"}

        dev_key = device_id or port
        device = None
        ok, device = await self.get_or_create_device(dev_key, port, baudrate)
        if not ok or device is None:
            return {"status": "fail", "reason": "connect_failed"}

        if device.is_busy:
            return {"status": "fail", "reason": "device_busy"}

        try:
            try:
                transient_packet_size = int(transient_packet_size)
            except (TypeError, ValueError):
                transient_packet_size = 7
            if transient_packet_size not in (7, 9):
                transient_packet_size = 7

            cmd_params = {
                "timeStep": 1,
                "sourceVoltage": 0,
                "drainVoltage": 0,
                "bottomTime": 2500,
                "topTime": 2500,
                "gateVoltageBottom": 0,
                "gateVoltageTop": 0,
                "cycles": 1
            }
            cmd_list = gen_transient_cmd(cmd_params)
            cmd_hex = bytes(cmd_list).hex().upper()

            data_result, reason = await device.send_and_receive_command(
                command=cmd_hex,
                end_sequences={"transient": "FEFEFEFEFEFEFEFE"},
                timeout=10,
                packet_size=transient_packet_size
            )
            if not data_result:
                return {"status": "fail", "reason": reason or "no_data"}

            data_np = bytes_to_numpy(
                data_result,
                mode="transient",
                transimpedance_ohms=transimpedance_ohms,
                transient_packet_size=transient_packet_size,
                baseline_current=0.0
            )
            if data_np.size == 0:
                baseline = 0.0
            else:
                baseline = float(np.mean(data_np[:, 1]))

            self.device_baselines[dev_key] = baseline
            return {"status": "ok", "baseline": baseline}
        except asyncio.TimeoutError:
            return {"status": "fail", "reason": "timeout"}
        except Exception as e:
            logger.error(f"校零失败: {e}")
            return {"status": "fail", "reason": str(e)}
        finally:
            # 校零结束后释放串口，避免刷新设备时占用端口
            if device is not None:
                try:
                    in_use = any(did == dev_key for did in self.test_to_device.values())
                    if not in_use:
                        await device.disconnect()
                        self.active_devices.pop(dev_key, None)
                        self.device_status[dev_key] = {
                            "connected": False,
                            "port": port,
                            "baudrate": baudrate,
                            "last_updated": time.time()
                        }
                        await self.data_bridge.send_device_status(
                            device_id=dev_key,
                            status="disconnected"
                        )
                except Exception as cleanup_err:
                    logger.error(f"校零后释放设备失败: {cleanup_err}")

    async def run_test(self, test: Test):
        """
        运行测试并清理
        
        Args:
            test: 要运行的测试实例
        """
        test_id = test.test_id
        device_id = test.device_id
        transimpedance_ohms = test.metadata.get("transimpedance_ohms", 100.0)
        baseline_current = test.metadata.get("baseline_current", 0.0)
        
        # 如果是同步模式，设置同步回调
        if test.sync_mode:
            test.sync_callback = self.wait_for_sync_with_completion
        
        try:
            logger.info(f"开始执行测试 {test_id} ({test.test_type})")
            
            # 创建测试目录
            test_dir = test.create_test_directory()

            # 【新增】如果是工作流测试，保存工作流配置
            if test.test_type == "workflow" and "raw_params" in test.metadata:
                # 从测试元数据中获取原始参数
                raw_params = test.metadata.get("raw_params", {})
                # 获取步骤数组
                steps = raw_params.get("steps", [])
                
                # 保存工作流配置
                if steps:
                    self.data_queue.put({
                        "type": MSG_SAVE_DATA,
                        "file_path": f"{test_dir}/workflow.json",
                        "content": json.dumps(steps, indent=2, ensure_ascii=False),
                        "mode": "json",
                        "test_id": test_id
                    })
                    logger.info(f"工作流配置已保存到 {test_dir}/workflow.json")


            
            # 保存文件的回调函数 - 维持原有接口
            def save_file_callback(file_path, content, mode, **kwargs):
                # 发送到数据传输进程，由其转发给保存进程
                message = {
                    "type": MSG_SAVE_DATA,
                    "file_path": file_path,
                    "content": content,
                    "mode": mode,
                    "test_id": test_id,
                    "transimpedance_ohms": transimpedance_ohms,
                    "baseline_current": baseline_current
                }
                if mode == "transient":
                    transient_packet_size = kwargs.get("transient_packet_size")
                    if transient_packet_size:
                        message["transient_packet_size"] = transient_packet_size
                self.data_queue.put(message)
            
            # 执行测试
            test_info = await test.execute(save_file_callback)
            
            # 记录测试结果
            self.test_results[test_id] = {
                "status": test_info.get("status", "completed"),
                "info": test_info,
                "test_dir": test_dir,
                "completed_at": time.time()
            }
            
            # 发送测试结果
            await self.data_bridge.send_test_result(
                test_id=test_id,
                status=test_info.get("status", "completed"),
                info=test_info,
                device_id=device_id
            )
            
            logger.info(f"测试 {test_id} ({test.test_type}) 已完成，状态: {test_info.get('status', 'completed')}")
            
        except Exception as e:
            import traceback
            logger.error(f"测试 {test_id} 执行失败: {str(e)}\n{traceback.format_exc()}")
            
            # 记录测试错误
            self.test_results[test_id] = {
                "status": "error",
                "error": str(e),
                "completed_at": time.time()
            }
            
            # 发送测试错误
            await self.data_bridge.send_message(
                test_id,
                {
                    "type": MSG_TEST_ERROR,
                    "test_id": test_id,
                    "device_id": device_id,
                    "error": str(e)
                },
                is_test_id=True
            )
            
        finally:
            # 清理测试与设备的映射
            if test_id in self.test_to_device:
                device_id = self.test_to_device[test_id]
                del self.test_to_device[test_id]
                    
                # 如果设备不再被其他测试使用，可以考虑断开连接
                if device_id in self.active_devices and not any(device_id == did for tid, did in self.test_to_device.items()):
                    device = self.active_devices[device_id]
                    
                    # 断开设备连接
                    await device.disconnect()
                    
                    # 从活跃设备列表中移除
                    if device_id in self.active_devices:
                        del self.active_devices[device_id]
                    
                    # 更新设备状态
                    self.device_status[device_id] = {
                        "connected": False,
                        "last_updated": time.time()
                    }
                    
                    # 发送设备状态更新
                    await self.data_bridge.send_device_status(
                        device_id=device_id,
                        status="disconnected"
                    )
                    
                    logger.info(f"设备 {device_id} 已断开连接并从设备池移除")
            
            # 从活跃测试列表中移除
            if test_id in self.active_tests:
                del self.active_tests[test_id]
            
            # 清理测试数据缓存
            if test_id in self.test_data_cache:
                del self.test_data_cache[test_id]
            
            # 清理同步相关数据
            for batch_id, batch_tests in list(self.sync_batches.items()):
                if test_id in batch_tests:
                    del batch_tests[test_id]
                    # 如果批次中没有测试了，清理整个批次
                    if not batch_tests:
                        del self.sync_batches[batch_id]
                        if batch_id in self.sync_step_status:
                            del self.sync_step_status[batch_id]
                        if batch_id in self.sync_locks:
                            del self.sync_locks[batch_id]
                
            logger.info(f"测试 {test_id} 已清理")
    
    def get_test_status(self, test_id: str) -> Dict[str, Any]:
        """
        获取测试状态
        
        Args:
            test_id: 测试ID
            
        Returns:
            测试状态信息
        """
        # 检查测试是否存在
        if test_id in self.active_tests:
            # 测试仍在运行
            test = self.active_tests[test_id]
            device_id = self.test_to_device.get(test_id)
            
            return {
                "status": "ok",
                "test_id": test_id,
                "device_id": device_id,
                "test_type": test.test_type,
                "name": test.name,
                "description": test.description,
                "state": "running",
                "created_at": test.created_at,
                "steps_completed": sum(1 for step in test.steps if step.end_time is not None),
                "total_steps": len(test.steps)
            }
        
        # 检查测试结果
        if test_id in self.test_results:
            # 测试已完成或失败
            result = self.test_results[test_id]
            
            return {
                "status": "ok",
                "test_id": test_id,
                "state": result["status"],
                "info": result.get("info", {}),
                "error": result.get("error"),
                "completed_at": result["completed_at"]
            }
        
        # 测试不存在
        return {
            "status": "fail",
            "reason": "test_not_found"
        }
    async def start_output_test(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        启动输出特性测试
        
        Args:
            params: 测试参数
            
        Returns:
            测试启动结果
        """
        # 提取必要参数
        device_id = params.get("device_id")
        port = params.get("port")
        baudrate = params.get("baudrate")
        test_id = params.get("test_id")
        transimpedance_ohms = params.get("transimpedance_ohms", 100.0)
        
        # 检查必要参数
        if not all([device_id, port, baudrate, test_id]):
            return {
                "status": "fail", 
                "reason": "Missing required parameters"
            }
        
        # 获取设备
        success, device = await self.get_or_create_device(device_id, port, baudrate)
        if not success:
            return {
                "status": "fail", 
                "reason": "Device connection failed"
            }
        
        # 记录测试与设备的映射关系
        self.test_to_device[test_id] = device_id
        
        # 创建测试对象
        test = Test(
            test_id=test_id, 
            device_id=device_id, 
            test_type="output",
            port=port,
            baudrate=baudrate,
            name=params.get("name", "输出特性测试"),
            description=params.get("description", ""),
            metadata={
                "raw_params": params,
                "transimpedance_ohms": transimpedance_ohms,
                "baseline_current": baseline_current
            }
        )
        
        # 初始化测试数据缓存
        self.test_data_cache[test_id] = {}
        
        # 创建输出特性测试步骤
        step_params = dict(params.get("step_params", params))
        step_params["transimpedance_ohms"] = transimpedance_ohms
        step_params["baseline_current"] = baseline_current
        step = OutputStep(
            device=device,
            step_id=test_id,
            command_id=params.get("command_id", 1),
            params=step_params
        )
        test.add_step(step)
        
        # 添加到活跃测试列表
        self.active_tests[test_id] = test
        
        # 异步执行测试
        self._start_test_task(test)
        
        return {
            "status": "ok", 
            "msg": "output_test_started", 
            "test_id": test_id
        }
# 修复步骤切换时的数据缓冲问题

def initialize_test_step_classes(data_bridge):
    """
    初始化测试步骤类，注入步骤感知的数据缓冲机制
    """
    from backend_device_control_pyqt.test.step import TestStep
    import time
    from collections import defaultdict, deque
    from app_config import (
        get_buffer_flush_packet_count,
        get_buffer_flush_interval_sec,
    )
    
    # 步骤感知的数据缓冲器
    class StepAwareDataBuffer:
        def __init__(self):
            # 按test_id和step_type分别缓冲
            self.buffers = defaultdict(lambda: defaultdict(lambda: {
                'data': deque(),
                'last_flush': time.time(),
                'last_progress': time.time(),
                'step_info': None
            }))
        
        def add_data(self, test_id, step_type, hex_data, workflow_info):
            """添加数据到对应步骤的缓冲区"""
            buffer = self.buffers[test_id][step_type]
            recv_ts = time.time()
            
            # 检测步骤变化 - 如果step_index变了，立即刷新旧缓冲区
            current_step_index = workflow_info.get('step_index', 0) if workflow_info else 0
            if (buffer['step_info'] and 
                buffer['step_info'].get('step_index', 0) != current_step_index):
                
                logger.info(f"检测到步骤变化: {buffer['step_info'].get('step_index')} -> {current_step_index}")
                self.flush_all_buffers_for_test(test_id)
            
            # 添加数据
            buffer['data'].append({
                'hex_data': hex_data,
                'workflow_info': workflow_info,
                'timestamp': recv_ts,
                'recv_ts': recv_ts
            })
            buffer['step_info'] = workflow_info
            
            flush_count = max(10, int(get_buffer_flush_packet_count()))
            flush_interval = max(0.05, float(get_buffer_flush_interval_sec()))
            should_flush = (
                len(buffer['data']) >= flush_count or
                time.time() - buffer['last_flush'] >= flush_interval
            )
            
            if should_flush:
                self.flush_buffer(test_id, step_type)
        
        def flush_all_buffers_for_test(self, test_id):
            """刷新指定测试的所有缓冲区（步骤切换时调用）"""
            if test_id in self.buffers:
                for step_type in list(self.buffers[test_id].keys()):
                    self.flush_buffer(test_id, step_type)
        
        def flush_buffer(self, test_id, step_type):
            """刷新指定测试和步骤类型的缓冲区"""
            buffer = self.buffers[test_id][step_type]
            if not buffer['data']:
                return
                
            # 合并同一步骤类型的数据
            hex_chunks = []
            byte_chunks = []
            mixed_types = False
            first_info = None
            latest_info = None
            first_recv_ts = None
            total_bytes = 0
            
            while buffer['data']:
                item = buffer['data'].popleft()
                hex_data = item['hex_data']
                
                if isinstance(hex_data, str):
                    if byte_chunks:
                        mixed_types = True
                    if " " in hex_data:
                        hex_chunks.append(hex_data.replace(" ", ""))
                    else:
                        hex_chunks.append(hex_data)
                    total_bytes += len(hex_chunks[-1]) // 2
                elif isinstance(hex_data, (bytes, bytearray)):
                    if hex_chunks:
                        mixed_types = True
                    byte_chunks.append(bytes(hex_data))
                    total_bytes += len(byte_chunks[-1])
                
                if first_info is None:
                    first_info = item['workflow_info']
                    first_recv_ts = item.get('recv_ts')
                latest_info = item['workflow_info']

            combined_data = None
            if mixed_types and hex_chunks:
                # 混合类型时回退到hex字符串，保证兼容性
                for chunk in byte_chunks:
                    hex_chunks.append(chunk.hex().upper())
                combined_data = "".join(hex_chunks)
            elif hex_chunks:
                combined_data = "".join(hex_chunks)
            elif byte_chunks:
                combined_data = b"".join(byte_chunks)
            
            # 估算这个批次的数据点数量，方便前端算速率
            packet_size = 5
            if step_type == "transient":
                try:
                    packet_size = int(first_info.get("transient_packet_size", 7))
                except Exception:
                    packet_size = 7
                if packet_size not in (7, 9):
                    packet_size = 7
            bytes_len = total_bytes if combined_data is not None else 0
            if isinstance(combined_data, str):
                bytes_len = len(combined_data) // 2
            batch_points = bytes_len // packet_size if packet_size else 0

            # 发送合并数据 - 使用第一个数据包的工作流信息确保步骤正确性
            if combined_data is not None and combined_data != b"" and combined_data != "" and first_info:
                try:
                    asyncio.create_task(
                        data_bridge.send_data(
                            test_id=test_id,
                            data=combined_data,
                            step_type=step_type,  # 使用明确的步骤类型
                            device_id=first_info.get('device_id', ''),
                            workflow_info=first_info,  # 使用第一个数据包的信息
                            recv_ts=first_recv_ts,
                            batch_points=batch_points
                        )
                    )
                    logger.debug(f"发送缓冲数据: test_id={test_id}, step_type={step_type}, data_len={len(combined_data)}")
                except RuntimeError:
                    # 如果没有事件循环，直接发送
                    pass
                except Exception as e:
                    logger.debug(f"发送缓冲数据失败: {e}")
            
            buffer['last_flush'] = time.time()
        
        def should_send_progress(self, test_id):
            """检查是否应该发送进度（全局节流）"""
            # 使用test_id的第一个缓冲区来记录进度时间
            if test_id in self.buffers:
                for step_type_buffers in self.buffers[test_id].values():
                    current_time = time.time()
                    if current_time - step_type_buffers['last_progress'] >= 0.1:  # 100ms节流
                        step_type_buffers['last_progress'] = current_time
                        return True
                    return False
            return True
    
    # 创建全局缓冲器
    global_buffer = StepAwareDataBuffer()
    
    # 重写进度回调
    def step_aware_progress_callback(self, length: int, dev_id: str):
        test_id = self.step_id
        
        # 进度节流
        if not global_buffer.should_send_progress(test_id):
            return
            
        progress = min(length / self.calculate_total_bytes(), 1.0)
        
        # 构造工作流信息
        workflow_info = None
        if self.workflow_progress_info:
            workflow_path = self.workflow_progress_info.get("workflow_path", [])
            workflow_info = {
                "step_index": self.workflow_progress_info.get("step_index", 0),
                "total_steps": self.workflow_progress_info.get("total_steps", 0),
                "path": workflow_path,
                "path_readable": self.format_workflow_path(workflow_path),
                "iteration_info": self.workflow_progress_info.get("iteration_info")
            }
        
        try:
            asyncio.create_task(
                data_bridge.send_progress(
                    test_id=test_id,
                    progress=progress,
                    step_type=self.get_step_type(),
                    device_id=dev_id,
                    workflow_info=workflow_info
                )
            )
        except RuntimeError:
            # 如果没有事件循环，跳过
            pass
        except Exception as e:
            logger.error(f"发送进度失败: {e}")
    
    # 重写数据回调
    def step_aware_data_callback(self, hex_data, dev_id: str):
        test_id = self.step_id
        step_type = self.get_step_type()  # 获取当前步骤类型
        
        # 构造工作流信息
        workflow_info = {
            'step_type': step_type,
            'device_id': dev_id
        }
        if step_type == "transient":
            workflow_info["transient_packet_size"] = self.get_packet_size()
        
        if self.workflow_progress_info:
            workflow_path = self.workflow_progress_info.get("workflow_path", [])
            workflow_info.update({
                "step_index": self.workflow_progress_info.get("step_index", 0),
                "total_steps": self.workflow_progress_info.get("total_steps", 0),
                "path": workflow_path,
                "path_readable": self.format_workflow_path(workflow_path),
                "iteration_info": self.workflow_progress_info.get("iteration_info")
            })
        
        # 添加到对应步骤类型的缓冲区
        global_buffer.add_data(test_id, step_type, hex_data, workflow_info)
    
    # 应用补丁
    TestStep.progress_callback = step_aware_progress_callback
    TestStep.data_callback = step_aware_data_callback
    
    logger.info("测试步骤类已应用步骤感知的缓冲机制")


# ============================================================================
# 使用说明
# ============================================================================

"""
修复要点：

1. 按步骤类型分别缓冲数据
   - transfer数据只与transfer数据合并
   - transient数据只与transient数据合并

2. 步骤变化检测
   - 监控step_index变化
   - 步骤切换时立即刷新所有缓冲区

3. 工作流信息保护
   - 使用第一个数据包的工作流信息
   - 确保步骤类型正确传递

4. 调试信息
   - 添加了print语句帮助调试
   - 可以看到何时检测到步骤变化

修改步骤：
1. 在 test_process.py 中替换 initialize_test_step_classes 函数
2. 运行测试，观察控制台输出
3. 应该能看到 "检测到步骤变化" 和 "发送缓冲数据" 的日志

这样应该能解决步骤切换时的显示问题。
"""

# 其他辅助函数保持不变
async def list_available_serial_ports():
    """
    获取可用的串口列表
    
    Returns:
        List[Dict]: 每个端口的信息，包括设备端口名称、描述、硬件ID、设备ID
    """
    logger.info("处理获取串口列表请求 - 含设备识别")
    try:
        import serial.tools.list_ports
        port_list = serial.tools.list_ports.comports()
        ports = []

        # 并发查询所有设备身份
        async def enrich_port(port):
            port_info = {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "device_id": "",
                "transimpedance_ohms": DEFAULT_TRANSIMPEDANCE_OHMS,
                "protocol_version": None,
                "supports_transient_vg": False,
                "transient_packet_size": 7
            }

            try:
                # 查询设备身份并确保连接正确关闭
                identity = await query_device_identity_once_raw(port.device)
                device_id, transimpedance_ohms, protocol_version = parse_identity_with_transimpedance(
                    identity,
                    DEFAULT_TRANSIMPEDANCE_OHMS
                )
                port_info["device_id"] = device_id or ""
                port_info["transimpedance_ohms"] = transimpedance_ohms
                port_info["protocol_version"] = protocol_version
                port_info["supports_transient_vg"] = bool(protocol_version is not None and protocol_version >= 2.0)
                port_info["transient_packet_size"] = 9 if port_info["supports_transient_vg"] else 7
            except Exception as e:
                logger.error(f"识别 {port.device} 身份失败: {e}")
                port_info["device_id"] = ""
                port_info["transimpedance_ohms"] = DEFAULT_TRANSIMPEDANCE_OHMS
                port_info["protocol_version"] = None
                port_info["supports_transient_vg"] = False
                port_info["transient_packet_size"] = 7

            return port_info

        # 批量并发运行所有串口识别
        ports = await asyncio.gather(*(enrich_port(p) for p in port_list))
        
        # 确保所有连接都已释放
        await asyncio.sleep(0.2)  # 给一点时间让串口连接完全关闭

        logger.info(f"找到 {len(ports)} 个串口设备")
        for p in ports:
            logger.info(f"串口: {p['device']}, 身份: {p['device_id']}")

        return ports

    except Exception as e:
        logger.error(f"获取串口列表失败: {str(e)}")
        return []

async def query_device_identity_once_raw(port: str, baudrate: int = 512000, timeout: float = 3.0) -> str:
    """
    使用原始串口方式查询设备身份（发送0x04指令，接收DONE!!!结尾）
    
    Args:
        port (str): 串口端口（如 'COM3'）
        baudrate (int): 波特率
        timeout (float): 超时时间（秒）

    Returns:
        str: 设备返回的身份字符串（去掉 DONE!!!），失败则返回空字符串
    """
    reader = None
    writer = None
    
    try:
        # 打开串口连接
        reader, writer = await serial_asyncio.open_serial_connection(url=port, baudrate=baudrate)
        logger.debug(f"串口 {port} 打开成功，发送命令")

        # 发送"你是谁"命令
        writer.write(WHO_AM_I_COMMAND)
        await writer.drain()

        buffer = bytearray()
        start_time = asyncio.get_event_loop().time()

        while True:
            # 超时判断
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.debug(f"超时，未收到完整DONE!!!")
                break

            try:
                data = await asyncio.wait_for(reader.read(64), timeout=0.5)
                if data:
                    logger.debug(f"收到: {data}")
                    buffer.extend(data)

                    if buffer.endswith(DONE_FLAG):
                        identity = buffer[:-len(DONE_FLAG)].decode("utf-8", errors="ignore").strip()
                        return identity
            except asyncio.TimeoutError:
                continue  # 等待下一轮接收

        return ""
    
    except Exception as e:
        logger.error(f"打开串口或通信失败: {e}")
        return ""
    finally:
        # 重要：确保关闭写入器，这会关闭串口连接
        if writer:
            try:
                writer.close()
                # 在某些情况下，需要等待写入器真正关闭
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"关闭串口失败: {e}")

def parse_identity_with_transimpedance(identity: str,
                                      default_ohms: float = DEFAULT_TRANSIMPEDANCE_OHMS
                                      ) -> Tuple[str, float, Optional[float]]:
    """
    解析身份字符串，提取设备名称和跨阻大小
    格式示例："Test Unit G2|R=100"
    """
    if not identity:
        return "", default_ohms, None

    transimpedance_ohms = default_ohms
    name = identity.strip()
    protocol_version = None
    match = re.search(r"(?:^|[|;,\s])R\s*=\s*([0-9]+(?:\.[0-9]+)?)", identity, flags=re.IGNORECASE)
    match_pv = re.search(r"(?:^|[|;,\s])PV\s*=\s*([0-9]+(?:\.[0-9]+)?)", identity, flags=re.IGNORECASE)
    if match_pv:
        try:
            protocol_version = float(match_pv.group(1))
        except (TypeError, ValueError):
            protocol_version = None
    if match:
        try:
            transimpedance_ohms = float(match.group(1))
        except (TypeError, ValueError):
            transimpedance_ohms = default_ohms
        if transimpedance_ohms <= 0:
            transimpedance_ohms = default_ohms
    cut_positions = []
    if match:
        cut_positions.append(match.start())
    if match_pv:
        cut_positions.append(match_pv.start())
    if cut_positions:
        name = identity[:min(cut_positions)].strip(" |;,")
        if not name:
            name = identity.strip()

    return name, transimpedance_ohms, protocol_version

def count_total_steps(steps):
    """
    递归计算工作流中的总步骤数（包括嵌套循环中的步骤）
    
    Args:
        steps: 步骤列表
        
    Returns:
        总步骤数
    """
    count = 0
    for step in steps:
        if step.get("type") == "loop":
            # 循环步骤，递归计算子步骤并乘以迭代次数
            count += step.get("iterations", 1) * count_total_steps(step.get("steps", []))
        else:
            # 普通步骤
            count += 1
    return count

# 常量定义
DONE_FLAG = b'DONE!!!'
WHO_AM_I_COMMAND = bytes.fromhex("00" * 16 + "FF0400FE")

# 进程入口函数
def run_test_process(command_queue, result_queue, data_queue, ready_event, shutdown_event):
    """
    测试进程入口函数
    
    Args:
        command_queue: 接收命令的队列
        result_queue: 发送结果的队列
        data_queue: 发送数据的队列
        ready_event: 进程就绪事件
        shutdown_event: 关闭事件
    """
    
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info(f"测试进程收到信号 {sig}，准备关闭")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建并启动测试管理器
    try:
        manager = TestManager(command_queue, result_queue, data_queue)
        
        # 设置就绪事件
        ready_event.set()
        logger.info("测试进程已就绪")
        
        # 启动测试管理器
        manager.start()
        
    except Exception as e:
        logger.error(f"测试进程发生异常: {str(e)}")
    finally:
        logger.info("测试进程结束")
