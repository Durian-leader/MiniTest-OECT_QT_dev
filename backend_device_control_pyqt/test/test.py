from typing import List, Dict, Any, Optional
from backend_device_control_pyqt.test.step import TestStep
import asyncio
import json
from datetime import datetime
import os
########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

class Test:
    """Class to orchestrate a sequence of test steps"""
    
    def __init__(self, test_id: str, device_id: str, test_type: str, 
                 port: str = None, baudrate: int = None, 
                 name: str = None, description: str = None, 
                 metadata: Dict[str, Any] = None):
        """
        Initialize a test sequence
        
        Args:
            test_id: Unique identifier for this test
            device_id: Device identifier
            test_type: Type of test (e.g., 'transfer', 'transient', 'stability', 'workflow')
            port: Serial port used
            baudrate: Baud rate
            name: Test name
            description: Test description
            metadata: Additional metadata
        """
        self.test_id = test_id
        self.device_id = device_id
        self.test_type = test_type
        self.port = port
        self.baudrate = baudrate
        self.name = name or f"{test_type.capitalize()} Test {test_id}"
        self.description = description or ""
        self.metadata = metadata or {}
        self.steps = []
        self.created_at = datetime.now().isoformat()
        self.completed_at = None
        self.test_dir = None
        
    def add_step(self, step: TestStep):
        """Add a step to the test sequence"""
        self.steps.append(step)
        
    def add_steps(self, steps: List[TestStep]):
        """Add multiple steps to the test sequence"""
        self.steps.extend(steps)
        
    def create_test_directory(self):
        """Create a directory for test results"""
        test_time = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.test_dir = f"UserData/AutoSave/{self.device_id}/{test_time}_{self.test_type}_{self.test_id}"
        os.makedirs(self.test_dir, exist_ok=True)
        return self.test_dir
        
    async def execute(self, save_file_async_fn):
        """
        Execute all steps in the test sequence
        
        Args:
            save_file_async_fn: Function to save files asynchronously
                
        Returns:
            Dict: Test information
        """
        if not self.test_dir:
            self.create_test_directory()
                
        test_info = {
            "test_id": self.test_id,
            "device_id": self.device_id,
            "test_type": self.test_type,
            "port": self.port,
            "baudrate": self.baudrate,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "steps": []
        }
        
        was_stopped = False
        completed_steps = 0
        
        for i, step in enumerate(self.steps):
            # 在每个步骤开始前检查停止标志
            if step.device._stop_event.is_set():
                logger.info(f"Test {self.test_id} stopped at step {i+1}")
                was_stopped = True
                break
                    
            logger.info(f"Executing {step.get_step_type()} step {i+1} of test {self.test_id}")
                    
            # 执行步骤
            data, reason = await step.execute()
            completed_steps += 1
            
            # 检查步骤后是否设置了停止标志（步骤执行期间可能被设置）
            if step.device._stop_event.is_set():
                logger.info(f"Test {self.test_id} stopped after step {i+1}")
                was_stopped = True
                
            # 保存数据（如果有）
            if data:
                # 确定文件名
                if i == len(self.steps) - 1 and self.test_type == "stability" and step.get_step_type() == "transfer":
                    file_name = "final_transfer.csv"
                else:
                    file_name = f"{i+1}_{step.get_step_type()}.csv"
                        
                # 保存文件
                save_file_async_fn(f"{self.test_dir}/{file_name}", data, step.get_data_mode())
                    
                # 添加步骤信息
                step_info = step.get_step_info()
                step_info["data_file"] = file_name
                test_info["steps"].append(step_info)
                
                # 每完成一个步骤就保存一次测试信息的临时副本
                # 这确保即使在下一步开始时崩溃，也能有部分信息
                temp_test_info = test_info.copy()
                temp_test_info["status"] = "in_progress"
                temp_test_info["last_updated"] = datetime.now().isoformat()
                temp_test_info["completed_steps"] = completed_steps
                temp_test_info["total_steps"] = len(self.steps)
                
                save_file_async_fn(f"{self.test_dir}/test_info_temp.json", 
                                json.dumps(temp_test_info, indent=4, ensure_ascii=False), 
                                'json')
            
            # 如果是停止状态，跳出循环
            if was_stopped:
                break
            
        # 设置完成时间和状态
        self.completed_at = datetime.now().isoformat()
        test_info["completed_at"] = self.completed_at
        
        # 根据测试是否被中断设置状态
        if was_stopped:
            test_info["status"] = "stopped"
        else:
            test_info["status"] = "completed"
        
        # 添加执行摘要
        test_info["summary"] = {
            "completed_steps": completed_steps,
            "total_steps": len(self.steps),
            "completion_percentage": round(completed_steps / len(self.steps) * 100, 1) if len(self.steps) > 0 else 0
        }
        
        # 保存最终测试信息
        save_file_async_fn(f"{self.test_dir}/test_info.json", 
                        json.dumps(test_info, indent=4, ensure_ascii=False), 
                        'json')
        
        if was_stopped:
            logger.info(f"Test {self.test_id} was stopped after completing {completed_steps} of {len(self.steps)} steps")
        else:
            logger.info(f"Test {self.test_id} completed successfully ({completed_steps} steps)")
            
        return test_info