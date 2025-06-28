"""
数据桥接模块 - data_bridge.py
用于替代原来的WebSocket通信，直接通过队列传递数据
"""


import json
import asyncio
from typing import Dict, Any, Optional
from queue import Queue  # Import Queue from queue module instead

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

# 数据队列
data_queue = None

# 初始化标志
initialized = False

def initialize(queue):
    """
    初始化数据桥接层
    
    Args:
        queue: 数据消息队列
    """
    global data_queue, initialized
    data_queue = queue
    initialized = True
    logger.info("数据桥接层已初始化")

async def send_message(identifier: str, message: Dict[str, Any], is_test_id: bool = True):
    """
    发送消息到数据队列
    
    Args:
        identifier: 测试ID或设备ID
        message: 要发送的消息
        is_test_id: 是否为测试ID
    """
    global data_queue, initialized
    
    if not initialized:
        logger.warning("数据桥接层未初始化")
        return
        
    # 将消息放入数据队列
    if data_queue is not None:
        try:
            # 确保消息中包含test_id或device_id，以便正确路由
            if is_test_id and "test_id" not in message:
                message["test_id"] = identifier
            elif not is_test_id and "device_id" not in message:
                message["device_id"] = identifier
                
            # 放入队列
            data_queue.put(message)
            logger.debug(f"消息已发送到数据队列: type={message.get('type')}, id={identifier}")
            
        except Exception as e:
            logger.error(f"发送消息到数据队列失败: {str(e)}")

# 添加便捷函数
async def send_progress(test_id: str, progress: float, step_type: str, device_id: Optional[str] = None,
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
    await send_message(test_id, message, is_test_id=True)

async def send_data(test_id: str, data: Any, step_type: str, device_id: Optional[str] = None,
                  workflow_info: Optional[Dict[str, Any]] = None, 
                  output_metadata: Optional[Dict[str, Any]] = None):
    """
    发送数据消息的便捷函数 - *** 新增output_metadata支持 ***
    
    Args:
        test_id: 测试ID
        data: 数据内容
        step_type: 步骤类型
        device_id: 设备ID(可选)
        workflow_info: 工作流信息(可选)
        output_metadata: output类型特有的元数据(可选)
    """
    # 构建数据消息
    message = {
        "type": "test_data",
        "test_id": test_id,
        "step_type": step_type,
        "data": data
    }
    
    # 添加设备ID
    if device_id:
        message["device_id"] = device_id
    
    # 添加工作流信息
    if workflow_info:
        message["is_workflow"] = True
        message["workflow_info"] = workflow_info
    
    # *** 新增：添加output元数据 ***
    if output_metadata:
        message["output_metadata"] = output_metadata
    
    # 发送消息
    await send_message(test_id, message, is_test_id=True)

async def send_test_result(test_id: str, status: str, info: Optional[Dict[str, Any]] = None, 
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
    await send_message(test_id, message, is_test_id=True)

async def send_device_status(device_id: str, status: str, details: Optional[Dict[str, Any]] = None):
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
    await send_message(device_id, message, is_test_id=False)

# 导出数据桥接实例
data_bridge = {
    "initialize": initialize,
    "send_message": send_message,
    "send_progress": send_progress,
    "send_data": send_data,
    "send_test_result": send_test_result,
    "send_device_status": send_device_status
}