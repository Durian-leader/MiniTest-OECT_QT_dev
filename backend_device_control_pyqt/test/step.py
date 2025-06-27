from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, Any, Tuple, Optional, Callable, List
from datetime import datetime
import json
from backend_device_control_pyqt.core.async_serial import AsyncSerialDevice

# 使用新的数据桥接器
from backend_device_control_pyqt.comunication.data_bridge import data_bridge

# 正确的日志设置
logger = logging.getLogger(__name__)

def bytes_to_hex(data) -> str:
    """Convert byte data to hex string"""
    if isinstance(data, list):
        return ''.join(f"{x:02X}" for x in data)
    return data.hex().upper()

class TestStep(ABC):
    """Base class for test steps"""
    
    def __init__(self, device: AsyncSerialDevice, step_id: str, params: Dict[str, Any], 
                 workflow_progress_info: Optional[Dict[str, Any]] = None):
        """
        Initialize a test step
        
        Args:
            device: AsyncSerialDevice instance for communication
            step_id: Unique identifier for this step/test
            params: Step parameters
            workflow_progress_info: Additional workflow progress context (for nested workflows)
        """
        self.device = device
        self.step_id = step_id
        self.params = params
        self.start_time = None
        self.end_time = None
        self.result = None
        self.reason = None
        self.workflow_progress_info = workflow_progress_info or {}
        
    @abstractmethod
    async def execute(self) -> Tuple[bytes, str]:
        """Execute the step and return result data and reason"""
        pass
        
    @abstractmethod
    def calculate_total_bytes(self) -> int:
        """Calculate expected total bytes for progress tracking"""
        pass
        
    @abstractmethod
    def generate_command(self) -> str:
        """Generate command string to send to device"""
        pass
        
    @abstractmethod
    def get_step_type(self) -> str:
        """Return the step type identifier"""
        pass
        
    @abstractmethod
    def get_data_mode(self) -> str:
        """Return data mode for saving (e.g. 'transfer', 'transient')"""
        pass
        
    @abstractmethod
    def get_packet_size(self) -> int:
        """Return packet size for data parsing"""
        pass
        
    @abstractmethod
    def get_end_sequence(self) -> str:
        """Return end sequence for this step type"""
        pass
        
    def format_workflow_path(self, path: List[Dict[str, Any]]) -> str:
        """
        将工作流路径格式化为可读字符串
        
        Args:
            path: 工作流路径
            
        Returns:
            格式化后的路径字符串
        """
        if not path:
            return ""
            
        parts = []
        for node in path:
            if node.get("type") == "loop":
                parts.append(f"循环[{node['index']}/{node['total']}]")
            elif node.get("type") == "iteration":
                parts.append(f"迭代{node['current']}/{node['total']}")
            else:
                step_type = "转移特性" if node.get("type") == "transfer" else \
                            "瞬态特性" if node.get("type") == "transient" else \
                            "输出特性" if node.get("type") == "output" else \
                            "步骤"
                parts.append(f"{step_type}[{node['index']}/{node['total']}]")
                
        return " > ".join(parts)
        
    def progress_callback(self, length: int, dev_id: str):
        """
        Default progress callback implementation
        This is a regular function that creates a task for the async operation
        """
        # 基本进度数据
        progress_data = {
            "type": "test_progress",  # 使用标准化的消息类型名称
            "step_type": self.get_step_type(),
            "progress": min(length / self.calculate_total_bytes(), 1.0),
            "step_id": self.step_id,
            "test_id": self.step_id,  # 确保包含test_id
            "device_id": dev_id
        }
        
        # 如果有工作流进度信息，添加到进度数据中
        workflow_info = None
        if self.workflow_progress_info:
            workflow_path = self.workflow_progress_info.get("workflow_path", [])
            
            # 工作流进度信息
            workflow_info = {
                "step_index": self.workflow_progress_info.get("step_index", 0),
                "total_steps": self.workflow_progress_info.get("total_steps", 0),
                "path": workflow_path,
                "path_readable": self.format_workflow_path(workflow_path),
                "iteration_info": self.workflow_progress_info.get("iteration_info")
            }
            
            progress_data.update({
                "is_workflow": True,
                "workflow_info": workflow_info
            })
        
        try:
            # 使用数据桥接器发送消息
            # 创建异步任务来发送
            asyncio.create_task(
                data_bridge["send_progress"](
                    test_id=self.step_id,
                    progress=progress_data["progress"],
                    step_type=self.get_step_type(),
                    device_id=dev_id,
                    workflow_info=workflow_info
                )
            )
            logger.debug(f"进度数据已发送: test_id={self.step_id}, progress={progress_data['progress']*100:.1f}%")
        except Exception as e:
            logger.error(f"发送进度数据失败: {str(e)}")
        
    def data_callback(self, hex_data, dev_id: str, **kwargs):
        """
        Default data callback implementation - *** 新增kwargs支持 ***
        This is a regular function that creates a task for the async operation
        """
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
        
        # *** 新增：从kwargs中提取output_metadata ***
        output_metadata = kwargs.get('output_metadata', None)
        
        try:
            # 使用数据桥接器发送数据
            # 创建异步任务来发送
            asyncio.create_task(
                data_bridge["send_data"](
                    test_id=self.step_id,
                    data=hex_data,
                    step_type=self.get_step_type(),
                    device_id=dev_id,
                    workflow_info=workflow_info,
                    output_metadata=output_metadata  # *** 新增：传递output元数据 ***
                )
            )
            logger.debug(f"数据已发送: test_id={self.step_id}, data_length={len(str(hex_data)) if isinstance(hex_data, str) else 'binary'}")
        except Exception as e:
            logger.error(f"发送数据失败: {str(e)}")
        
    def get_step_info(self) -> Dict[str, Any]:
        """Return step information for reporting"""
        step_info = {
            "type": self.get_step_type(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "params": self.params,
            "reason": self.reason
        }
        
        # 添加工作流信息到步骤信息中
        if self.workflow_progress_info:
            workflow_path = self.workflow_progress_info.get("workflow_path", [])
            
            step_info["workflow_info"] = {
                "step_index": self.workflow_progress_info.get("step_index", 0),
                "total_steps": self.workflow_progress_info.get("total_steps", 0),
                "path": workflow_path,
                "path_readable": self.format_workflow_path(workflow_path),
                "iteration_info": self.workflow_progress_info.get("iteration_info")
            }
            
        return step_info