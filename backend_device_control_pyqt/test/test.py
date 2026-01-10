from typing import List, Dict, Any, Optional
from backend_device_control_pyqt.test.step import TestStep
import asyncio
import json
from datetime import datetime
import os
import time

from app_config import get_incremental_save_interval_sec


class IncrementalStepSaver:
    """Stream test data to disk periodically to avoid large in-memory buffers."""

    def __init__(self, file_path: str, mode: str, interval_sec: float, save_fn, save_kwargs: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.mode = mode
        self.interval_sec = max(interval_sec, 0.1)
        self.save_fn = save_fn
        self.save_kwargs = save_kwargs or {}
        self.buffer = bytearray()
        self.last_flush = time.time()
        self.has_written = False

    def feed(self, chunk: Any):
        """Buffer incoming chunk and flush on interval."""
        if chunk is None:
            return
        try:
            if isinstance(chunk, str):
                chunk_bytes = bytes.fromhex(chunk.replace(" ", ""))
            else:
                chunk_bytes = bytes(chunk)
        except Exception:
            # Fallback to utf-8 to avoid losing data
            chunk_bytes = str(chunk).encode("utf-8")

        self.buffer.extend(chunk_bytes)
        if time.time() - self.last_flush >= self.interval_sec:
            self.flush()

    def flush(self, force: bool = False, final: bool = False):
        """Flush buffered data to disk via save_fn."""
        if not self.buffer:
            if final and self.has_written:
                self.save_fn(
                    self.file_path,
                    b"",
                    self.mode,
                    append=True,
                    streaming=True,
                    final_chunk=True,
                    **self.save_kwargs,
                )
            return
        self.save_fn(
            self.file_path,
            bytes(self.buffer),
            self.mode,
            append=True,
            streaming=True,
            final_chunk=final,
            **self.save_kwargs,
        )
        self.buffer.clear()
        self.last_flush = time.time()
        self.has_written = True
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
        
        # 同步执行相关
        self.sync_mode = metadata.get('sync_mode', False) if metadata else False
        self.batch_id = metadata.get('batch_id', None) if metadata else None
        self.sync_callback = None  # 将由TestManager设置
        
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
            try:
                # 预先确定文件名，便于增量保存
                if i == len(self.steps) - 1 and self.test_type == "stability" and step.get_step_type() == "transfer":
                    file_name = "final_transfer.csv"
                else:
                    file_name = f"{i+1}_{step.get_step_type()}.csv"

                # 配置增量保存（仅适用于瞬态，且配置间隔>0）
                incremental_interval = get_incremental_save_interval_sec()
                streaming_saver = None
                if step.get_step_type() == "transient" and incremental_interval > 0:
                    save_kwargs = {"transient_packet_size": step.get_packet_size()}
                    streaming_saver = IncrementalStepSaver(
                        file_path=os.path.join(self.test_dir, file_name),
                        mode=step.get_data_mode(),
                        interval_sec=incremental_interval,
                        save_fn=save_file_async_fn,
                        save_kwargs=save_kwargs
                    )
                    step.streaming_saver = streaming_saver

                # 在每个步骤开始前检查停止标志
                if step.device._stop_event.is_set():
                    logger.info(f"Test {self.test_id} stopped at step {i+1}")
                    was_stopped = True
                    break
                
                # 如果是同步模式，等待所有设备到达此步骤
                if self.sync_mode and self.sync_callback:
                    logger.info(f"Test {self.test_id} waiting for sync at step {i+1}")
                    await self.sync_callback(self.batch_id, self.test_id, i)
                    logger.info(f"Test {self.test_id} sync complete, executing step {i+1}")
                        
                logger.info(f"Executing {step.get_step_type()} step {i+1} of test {self.test_id}")
                        
                # 执行步骤
                data, reason = await step.execute()
                completed_steps += 1
                
                # 如果是同步模式，等待所有设备完成此步骤
                if self.sync_mode and self.sync_callback:
                    logger.info(f"Test {self.test_id} completed step {i+1}, waiting for others")
                    await self.sync_callback(self.batch_id, self.test_id, f"complete_{i}")
                    
            except Exception as e:
                logger.error(f"Error executing step {i+1} in test {self.test_id}: {e}")
                # 继续抛出异常，让上层处理
                raise
            finally:
                # 确保增量缓存刷盘
                if streaming_saver:
                    streaming_saver.flush(force=True, final=True)
            
            # 检查步骤后是否设置了停止标志（步骤执行期间可能被设置）
            if step.device._stop_event.is_set():
                logger.info(f"Test {self.test_id} stopped after step {i+1}")
                was_stopped = True
                
            # 保存数据（如果有）
            data_saved = False
            if streaming_saver and streaming_saver.has_written:
                # 增量模式下数据已落盘，记录文件名
                step_info = step.get_step_info()
                step_info["data_file"] = file_name
                test_info["steps"].append(step_info)
                data_saved = True
            elif data:
                # 保存文件
                save_kwargs = {}
                if step.get_step_type() == "transient":
                    save_kwargs["transient_packet_size"] = step.get_packet_size()
                save_file_async_fn(f"{self.test_dir}/{file_name}", data, step.get_data_mode(), **save_kwargs)
                    
                # 添加步骤信息
                step_info = step.get_step_info()
                step_info["data_file"] = file_name
                test_info["steps"].append(step_info)
                data_saved = True
            
            # 每完成一个步骤就保存一次测试信息的临时副本
            # 这确保即使在下一步开始时崩溃，也能有部分信息
            if data_saved:
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
            # 清理流式保存引用
            if streaming_saver:
                step.streaming_saver = None
            
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
