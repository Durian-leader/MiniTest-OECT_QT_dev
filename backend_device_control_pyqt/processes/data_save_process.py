"""
数据保存进程模块 - data_save_process.py (多进程版本)
负责将测试数据保存为CSV文件，处理所有文件I/O操作
"""

import os
import multiprocessing as mp
import queue
import time
import json
import signal
import sys
import threading
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

# 导入数据解析模块
from backend_device_control_pyqt.core.serial_data_parser import bytes_to_numpy

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

# 消息类型常量
MSG_SAVE_DATA = "save_data"
MSG_SHUTDOWN = "shutdown"

class DataSaveManager:
    """数据保存管理器，处理数据保存请求"""
    
    def __init__(self, data_save_queue, result_queue):
        """
        初始化数据保存管理器
        
        Args:
            data_save_queue: 接收数据保存请求的队列
            result_queue: 发送保存结果的队列
        """
        self.data_save_queue = data_save_queue
        self.result_queue = result_queue
        self.running = True
        
        # 创建工作线程池
        self.worker_threads = []
        self.work_queue = queue.Queue()
        
        # 统计信息
        self.stats = {
            "total_files": 0,
            "total_bytes": 0,
            "batches_received": 0,
            "total_data_points": 0,
            "files_by_type": {
                "transfer": 0,
                "transient": 0,
                "json": 0,
                "other": 0
            },
            "errors": 0
        }
        
        # 创建互斥锁，用于保护统计信息
        self.stats_lock = threading.Lock()
        
        # 测试累积数据缓存，用于追加模式
        self.test_data_cache = {}  # {file_path: accumulated_data}
        self.cache_lock = threading.Lock()
        
        # 创建数据目录
        os.makedirs("UserData/AutoSave", exist_ok=True)
    
    def start(self, num_workers=4):
        """
        启动数据保存管理器
        
        Args:
            num_workers: 工作线程数量
        """
        logger.info(f"启动数据保存管理器，使用 {num_workers} 个工作线程")
        
        # 创建工作线程
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"DataSaveWorker-{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        # 启动主循环
        self._main_loop()
    
    def _main_loop(self):
        """主循环，从队列接收保存请求并分发到工作线程"""
        logger.info("数据保存管理器主循环启动")
        
        while self.running:
            try:
                # 从队列获取消息，使用短超时避免无限阻塞
                try:
                    message = self.data_save_queue.get(timeout=0.5)
                except (queue.Empty, EOFError, BrokenPipeError):
                    continue
                
                # 检查是否为关闭信号
                if message.get("type") == MSG_SHUTDOWN:
                    logger.info("收到关闭信号")
                    self.running = False
                    break
                
                # 检查是否为数据保存请求
                if message.get("type") == MSG_SAVE_DATA:
                    # 将请求放入工作队列
                    self.work_queue.put(message)
                    
                    # 更新统计信息
                    with self.stats_lock:
                        # 如果是批量数据，记录批次信息
                        if message.get("is_batch"):
                            self.stats["batches_received"] += 1
                            batch_size = message.get("batch_size", 0)
                            self.stats["total_data_points"] += batch_size
                            
            except Exception as e:
                logger.error(f"处理数据保存请求出错: {str(e)}")
                with self.stats_lock:
                    self.stats["errors"] += 1
                continue
        
        # 发送结束信号到工作线程
        for _ in range(len(self.worker_threads)):
            self.work_queue.put(None)
        
        # 等待所有工作线程结束
        for worker in self.worker_threads:
            worker.join(timeout=5)
            if worker.is_alive():
                logger.warning(f"工作线程 {worker.name} 未能在超时时间内结束")
        
        # 输出最终统计信息
        logger.info("数据保存管理器已关闭")
        logger.info(f"统计信息: 总共保存了 {self.stats['total_files']} 个文件，共 {self.stats['total_bytes']} 字节")
        logger.info(f"接收到 {self.stats['batches_received']} 个批次，共 {self.stats['total_data_points']} 个数据点")
        logger.info(f"按类型分: 转移特性={self.stats['files_by_type']['transfer']}, "
                    f"瞬态特性={self.stats['files_by_type']['transient']}, "
                    f"JSON={self.stats['files_by_type']['json']}, "
                    f"其他={self.stats['files_by_type']['other']}")
        logger.info(f"错误次数: {self.stats['errors']}")
    
    def _worker_thread(self):
        """工作线程，处理单个保存请求"""
        thread_name = threading.current_thread().name
        logger.info(f"工作线程 {thread_name} 启动")
        
        while True:
            try:
                # 从工作队列获取请求
                task = self.work_queue.get()
                
                # 检查是否为结束信号
                if task is None:
                    logger.info(f"工作线程 {thread_name} 收到结束信号")
                    break
                
                # 处理保存请求
                file_path = task.get("file_path")
                content = task.get("content")
                mode = task.get("mode", task.get("step_type", "transfer"))
                test_id = task.get("test_id", "unknown")
                transimpedance_ohms = task.get("transimpedance_ohms", 100.0)
                transient_packet_size = task.get("transient_packet_size", 7)
                
                # 如果没有提供文件路径，但有必要的参数，生成一个
                if not file_path and test_id and mode:
                    # 为实时测试数据，自动生成文件路径
                    device_id = task.get("device_id", "unknown")
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    base_dir = f"UserData/AutoSave/{device_id}/{timestamp}_{mode}_{test_id}"
                    os.makedirs(base_dir, exist_ok=True)
                    file_path = f"{base_dir}/{mode}_data.csv"
                    
                    # 添加追加标志，表示数据应该追加到现有文件
                    task["append"] = True
                
                if not file_path or content is None:
                    logger.warning(f"无效的保存请求: 缺少必要参数")
                    with self.stats_lock:
                        self.stats["errors"] += 1
                    
                    # 发送失败结果
                    self._send_result(test_id, "error", file_path, "Missing required parameters")
                    continue
                
                # 保存文件
                is_append = task.get("append", False)
                success, size, error = self._save_file(
                    file_path,
                    content,
                    mode,
                    is_append,
                    transimpedance_ohms=transimpedance_ohms,
                    transient_packet_size=transient_packet_size
                )
                
                # 发送结果
                status = "ok" if success else "error"
                self._send_result(test_id, status, file_path, error)
                
                # 更新统计信息
                with self.stats_lock:
                    if success:
                        self.stats["total_files"] += 1
                        self.stats["total_bytes"] += size
                        
                        if mode == "transfer":
                            self.stats["files_by_type"]["transfer"] += 1
                        elif mode == "transient":
                            self.stats["files_by_type"]["transient"] += 1
                        elif mode == "json":
                            self.stats["files_by_type"]["json"] += 1
                        else:
                            self.stats["files_by_type"]["other"] += 1
                    else:
                        self.stats["errors"] += 1
            except Exception as e:
                logger.error(f"工作线程 {thread_name} 处理保存请求时出错: {str(e)}")
                with self.stats_lock:
                    self.stats["errors"] += 1
            finally:
                # 标记任务完成
                if task is not None:
                    self.work_queue.task_done()
        
        logger.info(f"工作线程 {thread_name} 已退出")
    
    def _send_result(self, test_id: str, status: str, file_path: str, error: Optional[str] = None):
        """
        发送保存结果
        
        Args:
            test_id: 测试ID
            status: 状态（ok或error）
            file_path: 文件路径
            error: 错误信息（如果有）
        """
        result = {
            "type": "save_result",
            "test_id": test_id,
            "status": status,
            "file_path": file_path
        }
        
        if error:
            result["error"] = error
            
        try:
            self.result_queue.put(result)
        except Exception as e:
            logger.error(f"发送保存结果失败: {str(e)}")
    
    def _save_file(
        self,
        file_path: str,
        content: Any,
        mode: str,
        append: bool = False,
        transimpedance_ohms: float = 100.0,
        transient_packet_size: int = 7
    ) -> Tuple[bool, int, Optional[str]]:
        """
        保存文件
        
        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 保存模式 (transfer, transient, json)
            append: 是否追加到现有文件
            
        Returns:
            (成功标志, 文件大小, 错误信息)
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 根据模式处理不同类型的保存
            if mode == "transfer":
                # 转移特性，CSV格式，保存Vg和Id
                if append and file_path in self.test_data_cache:
                    # 追加模式，累积数据
                    with self.cache_lock:
                        # 解析新数据
                        new_data_np = bytes_to_numpy(
                            content,
                            mode=mode,
                            transimpedance_ohms=transimpedance_ohms,
                            transient_packet_size=transient_packet_size
                        )
                        
                        # 获取缓存数据
                        cached_data = self.test_data_cache[file_path]
                        
                        # 合并数据
                        combined_data = np.vstack((cached_data, new_data_np)) if cached_data.size > 0 else new_data_np
                        
                        # 更新缓存
                        self.test_data_cache[file_path] = combined_data
                        
                        # 写入文件
                        np.savetxt(
                            file_path, 
                            combined_data, 
                            delimiter=',', 
                            header='Vg,Id', 
                            comments='',
                            fmt=['%.3f', '%g']  # Vg保留3位小数，Id使用通用格式
                        )
                else:
                    # 新文件或非追加模式
                    transfer_data_np = bytes_to_numpy(
                        content,
                        mode=mode,
                        transimpedance_ohms=transimpedance_ohms
                    )
                    
                    # 写入文件
                    np.savetxt(
                        file_path, 
                        transfer_data_np, 
                        delimiter=',', 
                        header='Vg,Id', 
                        comments='',
                        fmt=['%.3f', '%g']  # Vg保留3位小数，Id使用通用格式
                    )
                    
                    # 如果是追加模式，存入缓存
                    if append:
                        with self.cache_lock:
                            self.test_data_cache[file_path] = transfer_data_np
                
                logger.info(f"保存转移特性数据: {file_path}, 追加模式: {append}")
                return True, os.path.getsize(file_path), None
                
            elif mode == "transient":
                try:
                    transient_packet_size = int(transient_packet_size)
                except (TypeError, ValueError):
                    transient_packet_size = 7
                if transient_packet_size not in (7, 9):
                    transient_packet_size = 7
                if transient_packet_size == 9:
                    header = "Time,Id,Vg"
                    fmt = ['%.3f', '%g', '%.3f']
                else:
                    header = "Time,Id"
                    fmt = ['%.3f', '%g']
                # 瞬态特性，CSV格式，保存Time和Id
                if append and file_path in self.test_data_cache:
                    # 追加模式，累积数据
                    with self.cache_lock:
                        # 解析新数据
                        new_data_np = bytes_to_numpy(
                            content,
                            mode=mode,
                            transimpedance_ohms=transimpedance_ohms
                        )
                        
                        # 获取缓存数据
                        cached_data = self.test_data_cache[file_path]
                        
                        # 合并数据
                        combined_data = np.vstack((cached_data, new_data_np)) if cached_data.size > 0 else new_data_np
                        
                        # 更新缓存
                        self.test_data_cache[file_path] = combined_data
                        
                        # 写入文件
                        np.savetxt(
                            file_path, 
                            combined_data, 
                            delimiter=',', 
                            header=header, 
                            comments='',
                            fmt=fmt
                        )
                else:
                    # 新文件或非追加模式
                    transient_data_np = bytes_to_numpy(
                        content,
                        mode=mode,
                        transimpedance_ohms=transimpedance_ohms,
                        transient_packet_size=transient_packet_size
                    )
                    
                    # 写入文件
                    np.savetxt(
                        file_path, 
                        transient_data_np, 
                        delimiter=',', 
                        header=header, 
                        comments='',
                        fmt=fmt
                    )
                    
                    # 如果是追加模式，存入缓存
                    if append:
                        with self.cache_lock:
                            self.test_data_cache[file_path] = transient_data_np
                
                logger.info(f"保存瞬态特性数据: {file_path}, 追加模式: {append}")
                return True, os.path.getsize(file_path), None
                
            elif mode == "json":
                # JSON格式，直接保存
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"保存JSON数据: {file_path}")
                return True, os.path.getsize(file_path), None
                
            else:
                # 其他格式，二进制保存
                # 如果是追加模式，需要先读取现有内容
                if append and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        existing_content = f.read()
                    
                    # 准备要写入的内容
                    if isinstance(content, str):
                        write_content = existing_content + content.encode('utf-8')
                    else:
                        write_content = existing_content + content
                    
                    # 写入合并后的内容
                    with open(file_path, "wb") as f:
                        f.write(write_content)
                else:
                    # 非追加模式，直接写入
                    with open(file_path, "wb") as f:
                        if isinstance(content, str):
                            f.write(content.encode('utf-8'))
                        else:
                            f.write(content)
                
                logger.info(f"保存其他类型数据: {file_path}, 追加模式: {append}")
                return True, os.path.getsize(file_path), None
                
        except Exception as e:
            error_msg = f"保存文件 {file_path} 失败: {str(e)}"
            logger.error(error_msg)
            return False, 0, error_msg

# 进程入口函数
def run_data_save_process(data_save_queue, result_queue, ready_event, shutdown_event):
    """
    数据保存进程入口函数
    
    Args:
        data_save_queue: 接收数据保存请求的队列
        result_queue: 发送保存结果的队列
        ready_event: 进程就绪事件
        shutdown_event: 关闭事件
    """

    
    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备关闭数据保存管理器")
        shutdown_event.set()
    
    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建关闭检测线程
    def shutdown_monitor():
        while True:
            if shutdown_event.is_set():
                logger.info("检测到关闭事件，通知数据保存管理器")
                # 发送关闭消息到队列
                try:
                    data_save_queue.put({"type": MSG_SHUTDOWN})
                except:
                    pass
                break
            time.sleep(0.1)
    
    try:
        # 启动关闭监控线程
        monitor_thread = threading.Thread(target=shutdown_monitor, daemon=True)
        monitor_thread.start()
        
        # 创建并启动数据保存管理器
        manager = DataSaveManager(data_save_queue, result_queue)
        
        # 设置就绪事件
        ready_event.set()
        logger.info("数据保存进程已就绪")
        
        # 启动管理器
        manager.start(num_workers=4)  # 使用4个工作线程
    except Exception as e:
        logger.error(f"数据保存管理器运行失败: {str(e)}")
    finally:
        logger.info("数据保存进程结束")

if __name__ == "__main__":
    # 测试代码
    print("此模块不应直接运行")
