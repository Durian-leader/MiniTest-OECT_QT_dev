"""
进程间通信工具 - ipc.py
提供进程间通信的辅助函数和类
"""

import time
import pickle
import json
import numpy as np
from typing import Any, Dict, Optional, Union

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################
class IPCUtils:
    """进程间通信工具类"""
    
    @staticmethod
    def serialize_data(data: Any) -> bytes:
        """
        序列化数据，优化特殊对象的处理
        
        Args:
            data: 要序列化的数据
            
        Returns:
            序列化后的字节序列
        """
        if isinstance(data, bytes) or isinstance(data, bytearray):
            # 原始字节数据，无需序列化
            return data
        
        elif isinstance(data, (np.ndarray, np.generic)):
            # NumPy数组，使用pickle序列化
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        
        elif isinstance(data, dict) or isinstance(data, list):
            try:
                # 尝试使用JSON序列化，可读性更好且通常较快
                return json.dumps(data).encode('utf-8')
            except (TypeError, ValueError):
                # 如果包含不可JSON序列化的对象，回退到pickle
                return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        
        else:
            # 其他类型使用pickle
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    
    @staticmethod
    def deserialize_data(data: bytes) -> Any:
        """
        反序列化数据
        
        Args:
            data: 要反序列化的字节序列
            
        Returns:
            反序列化后的数据
        """
        if not data:
            return None
        
        # 尝试各种反序列化方法
        try:
            # 先尝试JSON格式
            return json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            try:
                # 再尝试pickle格式
                return pickle.loads(data)
            except pickle.UnpicklingError:
                # 都失败则返回原始数据
                return data
    
    @staticmethod
    def safe_put(queue, item, timeout=1.0) -> bool:
        """
        安全地将项目放入队列，处理超时和各种异常
        
        Args:
            queue: 目标队列
            item: 要放入的项目
            timeout: 超时时间(秒)
            
        Returns:
            是否成功
        """
        try:
            queue.put(item, block=True, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"队列放入操作失败: {str(e)}")
            return False
    
    @staticmethod
    def safe_get(queue, timeout=0.5) -> Optional[Any]:
        """
        安全地从队列获取项目，处理超时和各种异常
        
        Args:
            queue: 源队列
            timeout: 超时时间(秒)
            
        Returns:
            获取的项目，失败则返回None
        """
        try:
            return queue.get(block=True, timeout=timeout)
        except Exception as e:
            # 队列为空或其他异常，不记录日志避免过多输出
            return None
    
    @staticmethod
    def encode_test_data(data: Any, format_hint: str = None) -> Dict[str, Any]:
        """
        编码测试数据，优化IPC传输
        
        Args:
            data: 原始测试数据
            format_hint: 格式提示 ("bytes", "numpy", "json", "pickle")
            
        Returns:
            编码后的消息字典
        """
        message = {
            "timestamp": time.time()
        }
        
        # 数据类型检测和处理
        if isinstance(data, bytes) or isinstance(data, bytearray):
            # 原始二进制数据
            message["data"] = data
            message["format"] = "bytes"
            message["size"] = len(data)
            
        elif isinstance(data, (np.ndarray, np.generic)):
            # NumPy数组，使用pickle或专用编码
            if format_hint == "numpy_raw":
                # 使用NumPy专用二进制格式
                buffer = BytesIO()
                np.save(buffer, data)
                raw_data = buffer.getvalue()
                message["data"] = raw_data
                message["format"] = "numpy_raw"
                message["shape"] = data.shape
                message["dtype"] = str(data.dtype)
                message["size"] = len(raw_data)
            else:
                # 使用pickle
                pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
                message["data"] = pickled
                message["format"] = "pickle"
                message["size"] = len(pickled)
                
        elif isinstance(data, dict) or isinstance(data, list):
            try:
                # 尝试JSON序列化
                json_data = json.dumps(data)
                message["data"] = json_data
                message["format"] = "json"
                message["size"] = len(json_data)
            except (TypeError, ValueError):
                # 回退到pickle
                pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
                message["data"] = pickled
                message["format"] = "pickle"
                message["size"] = len(pickled)
                
        else:
            # 其他类型使用pickle
            pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            message["data"] = pickled
            message["format"] = "pickle"
            message["size"] = len(pickled)
        
        return message
    
    @staticmethod
    def decode_test_data(message: Dict[str, Any]) -> Any:
        """
        解码测试数据
        
        Args:
            message: 编码后的消息字典
            
        Returns:
            解码后的原始数据
        """
        if not message or "data" not in message:
            return None
        
        data = message["data"]
        format_type = message.get("format", "unknown")
        
        if format_type == "bytes":
            # 原始二进制数据，直接返回
            return data
            
        elif format_type == "numpy_raw":
            # NumPy专用格式
            buffer = BytesIO(data)
            return np.load(buffer)
            
        elif format_type == "json":
            # JSON格式
            if isinstance(data, str):
                return json.loads(data)
            else:
                return json.loads(data.decode('utf-8'))
                
        elif format_type == "pickle":
            # Pickle格式
            return pickle.loads(data)
            
        else:
            # 未知格式，尝试自动检测
            return IPCUtils.deserialize_data(data)

# 测试代码
if __name__ == "__main__":
    from io import BytesIO
    
    # 测试序列化和反序列化
    test_data = {
        "name": "测试数据",
        "values": [1, 2, 3, 4, 5],
        "nested": {
            "a": 1,
            "b": "测试"
        }
    }
    
    # 序列化
    serialized = IPCUtils.serialize_data(test_data)
    print(f"序列化后大小: {len(serialized)} 字节")
    
    # 反序列化
    deserialized = IPCUtils.deserialize_data(serialized)
    print(f"反序列化后: {deserialized}")
    
    # 测试NumPy数组
    test_array = np.array([[1, 2, 3], [4, 5, 6]])
    encoded = IPCUtils.encode_test_data(test_array)
    print(f"编码NumPy数组: format={encoded['format']}, size={encoded['size']}")
    
    decoded = IPCUtils.decode_test_data(encoded)
    print(f"解码NumPy数组: shape={decoded.shape}, dtype={decoded.dtype}")
    print(decoded)