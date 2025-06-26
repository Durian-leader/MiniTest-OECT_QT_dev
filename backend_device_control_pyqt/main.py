"""
医疗测试系统后端 - 多进程架构版本
使用四个专门的进程处理不同任务，优化高负载场景的性能
"""

import os
import logging
import multiprocessing as mp
import time
import json
import uuid
import signal
import sys
from typing import Dict, List, Any, Optional, Tuple
if not os.path.exists("logs"):
    os.makedirs("logs", exist_ok=True)
# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/backend.log')
    ]
)
logger = logging.getLogger(__name__)

# 消息类型常量
MSG_START_TEST = "start_test"
MSG_STOP_TEST = "stop_test"
MSG_LIST_DEVICES = "list_devices"
MSG_GET_TEST_STATUS = "get_test_status"
MSG_TEST_DATA = "test_data"
MSG_TEST_PROGRESS = "test_progress"
MSG_TEST_RESULT = "test_result"
MSG_TEST_ERROR = "test_error"
MSG_SAVE_DATA = "save_data"
MSG_DEVICE_STATUS = "device_status"
MSG_SHUTDOWN = "shutdown"

# 进程信号常量
SIGNAL_READY = "ready"
SIGNAL_TERMINATE = "terminate"
SIGNAL_ERROR = "error"

class MedicalTestBackend:
    """医疗测试系统后端主类，为PyQt应用提供接口"""
    
    def __init__(self):
        """初始化后端"""
        # 初始化多进程相关资源
        mp.set_start_method('spawn', force=True)  # 使用spawn方式启动进程，确保Windows兼容性
        
        # 用于进程间通信的队列
        self.qt_to_test_queue = mp.Queue()      # Qt进程到测试进程
        self.test_to_qt_queue = mp.Queue()      # 测试进程到Qt进程
        self.test_to_data_queue = mp.Queue()    # 测试进程到数据处理进程
        self.data_to_qt_queue = mp.Queue()      # 数据处理进程到Qt进程
        self.data_to_save_queue = mp.Queue()    # 数据处理进程到保存进程
        self.save_to_data_queue = mp.Queue()    # 保存进程到数据处理进程
        
        # 进程控制事件
        self.shutdown_event = mp.Event()
        self.test_ready_event = mp.Event()
        self.data_ready_event = mp.Event()
        self.save_ready_event = mp.Event()
        
        # 进程对象
        self.test_process = None
        self.data_process = None
        self.save_process = None
        
        # 初始化状态
        self.is_running = False
        
        # 创建必要目录
        os.makedirs("logs", exist_ok=True)
        os.makedirs("UserData/AutoSave", exist_ok=True)
    
    def start(self):
        """启动后端系统"""
        if self.is_running:
            logger.warning("后端已经在运行中")
            return
            
        logger.info("正在启动后端系统 (多进程版)")
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        # 启动数据保存进程
        from backend_device_control_pyqt.processes.data_save_process import run_data_save_process
        self.save_process = mp.Process(
            target=run_data_save_process,
            args=(self.data_to_save_queue, self.save_to_data_queue, self.save_ready_event, self.shutdown_event),
            name="DataSaveProcess",
            daemon=True
        )
        self.save_process.start()
        
        # 启动数据传输进程
        from backend_device_control_pyqt.processes.data_transmission_process import run_data_transmission_process
        self.data_process = mp.Process(
            target=run_data_transmission_process,
            args=(self.test_to_data_queue, self.data_to_qt_queue, 
                  self.data_to_save_queue, self.save_to_data_queue,
                  self.data_ready_event, self.shutdown_event),
            name="DataTransmissionProcess",
            daemon=True
        )
        self.data_process.start()
        
        # 启动测试进程
        from backend_device_control_pyqt.processes.test_process import run_test_process
        self.test_process = mp.Process(
            target=run_test_process,
            args=(self.qt_to_test_queue, self.test_to_qt_queue, 
                  self.test_to_data_queue, self.test_ready_event, 
                  self.shutdown_event),
            name="TestProcess",
            daemon=True
        )
        self.test_process.start()
        
        # 等待所有进程准备就绪
        logger.info("等待所有进程准备就绪...")
        timeout = 10  # 最多等待10秒
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.test_ready_event.is_set() and self.data_ready_event.is_set() and self.save_ready_event.is_set():
                break
            time.sleep(0.1)
        
        if not (self.test_ready_event.is_set() and self.data_ready_event.is_set() and self.save_ready_event.is_set()):
            logger.error("一个或多个进程未能在超时时间内准备就绪")
            self.shutdown()
            raise RuntimeError("启动后端系统失败：进程准备超时")
        
        self.is_running = True
        logger.info("后端系统已启动 (所有进程就绪)")
        
    def shutdown(self):
        """关闭后端系统"""
        if not self.is_running:
            logger.warning("后端系统未运行")
            return
            
        logger.info("正在关闭后端系统...")
        
        # 设置关闭事件
        self.shutdown_event.set()
        
        # 向各队列发送关闭消息，确保各进程能跳出阻塞状态
        try:
            self.qt_to_test_queue.put_nowait({"type": MSG_SHUTDOWN})
            self.test_to_data_queue.put_nowait({"type": MSG_SHUTDOWN})
            self.data_to_save_queue.put_nowait({"type": MSG_SHUTDOWN})
        except:
            pass
        
        # 等待进程结束
        if self.test_process:
            self.test_process.join(timeout=5)
            if self.test_process.is_alive():
                logger.warning("测试进程未能正常退出，尝试终止")
                self.test_process.terminate()
        
        if self.data_process:
            self.data_process.join(timeout=5)
            if self.data_process.is_alive():
                logger.warning("数据传输进程未能正常退出，尝试终止")
                self.data_process.terminate()
        
        if self.save_process:
            self.save_process.join(timeout=5)
            if self.save_process.is_alive():
                logger.warning("数据保存进程未能正常退出，尝试终止")
                self.save_process.terminate()
        
        # 清理资源
        for queue in [self.qt_to_test_queue, self.test_to_qt_queue, self.test_to_data_queue, 
                    self.data_to_qt_queue, self.data_to_save_queue, self.save_to_data_queue]:
            queue.close()
            queue.join_thread()
        
        self.is_running = False
        logger.info("后端系统已关闭")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(sig, frame):
            logger.info(f"收到信号 {sig}，准备关闭系统")
            self.shutdown()
            sys.exit(0)
        
        # 注册信号处理函数
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    # ==== 以下是供PyQt调用的API ====
    
    def get_real_time_data(self, timeout: float = 0.01) -> Optional[Dict[str, Any]]:
        """
        获取实时数据（非阻塞）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            数据字典，如果队列为空则返回None
        """
        if not self.is_running:
            return None
            
        try:
            return self.data_to_qt_queue.get(block=True, timeout=timeout)
        except (mp.queues.Empty, ConnectionError, BrokenPipeError, EOFError):
            return None
    
    def list_serial_ports(self) -> List[Dict[str, Any]]:
        """
        获取可用串口列表，带设备ID识别
        
        Returns:
            串口列表，每项包含device, description, hwid, device_id
        """
        if not self.is_running:
            return []
            
        logger.info("获取串口列表")
        
        # 生成请求ID
        request_id = str(uuid.uuid4())
        
        # 向测试进程发送请求
        self.qt_to_test_queue.put({
            "type": MSG_LIST_DEVICES,
            "request_id": request_id
        })
        
        # 等待响应
        start_time = time.time()
        timeout = 5  # 5秒超时
        
        while time.time() - start_time < timeout:
            try:
                response = self.test_to_qt_queue.get(block=True, timeout=0.5)
                if response.get("request_id") == request_id:
                    return response.get("data", [])
            except (mp.queues.Empty, ConnectionError, BrokenPipeError, EOFError):
                pass
        
        logger.warning(f"获取串口列表超时")
        return []
    
    def start_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        启动工作流测试
        
        Args:
            params: 工作流参数，包含：
                - test_id: 测试ID
                - device_id: 设备ID
                - port: 串口
                - baudrate: 波特率
                - name: 测试名称
                - description: 测试描述
                - steps: 测试步骤列表
        
        Returns:
            启动结果
        """
        if not self.is_running:
            return {"status": "fail", "reason": "Backend not running"}
            
        # 生成请求ID
        request_id = str(uuid.uuid4())
        logger.info(f"启动工作流: test_id={params.get('test_id')}, request_id={request_id}")
        
        # 向测试进程发送请求
        self.qt_to_test_queue.put({
            "type": MSG_START_TEST,
            "test_type": "workflow",
            "params": params,
            "request_id": request_id
        })
        
        # 等待响应
        start_time = time.time()
        timeout = 5  # 5秒超时
        
        while time.time() - start_time < timeout:
            try:
                response = self.test_to_qt_queue.get(block=True, timeout=0.5)
                if response.get("request_id") == request_id:
                    return response
            except (mp.queues.Empty, ConnectionError, BrokenPipeError, EOFError):
                pass
        
        # 超时，返回默认响应
        return {
            "status": "ok", 
            "msg": "workflow_started",
            "test_id": params.get("test_id"),
            "name": params.get("name", "未命名"),
            "description": params.get("description", ""),
            "note": "Request accepted, no immediate response"
        }
    
    def stop_test(self, device_id: Optional[str] = None, test_id: Optional[str] = None) -> Dict[str, Any]:
        """
        停止测试
        
        Args:
            device_id: 设备ID（可选）
            test_id: 测试ID（可选）
            
        Returns:
            停止结果
        """
        if not self.is_running:
            return {"status": "fail", "reason": "Backend not running"}
            
        if not device_id and not test_id:
            raise ValueError("必须提供device_id或test_id")
            
        # 生成请求ID
        request_id = str(uuid.uuid4())
        logger.info(f"停止测试: device_id={device_id}, test_id={test_id}, request_id={request_id}")
        
        # 向测试进程发送请求
        self.qt_to_test_queue.put({
            "type": MSG_STOP_TEST,
            "device_id": device_id,
            "test_id": test_id,
            "request_id": request_id
        })
        
        # 等待响应
        start_time = time.time()
        timeout = 5  # 5秒超时
        
        while time.time() - start_time < timeout:
            try:
                response = self.test_to_qt_queue.get(block=True, timeout=0.5)
                if response.get("request_id") == request_id:
                    return response
            except (mp.queues.Empty, ConnectionError, BrokenPipeError, EOFError):
                pass
        
        # 超时，返回默认响应
        return {
            "status": "ok",
            "msg": "stop_request_sent",
            "note": "Stop request accepted, but no immediate confirmation"
        }
    
    def get_test_status(self, test_id: str) -> Dict[str, Any]:
        """
        获取测试状态
        
        Args:
            test_id: 测试ID
            
        Returns:
            测试状态信息
        """
        if not self.is_running:
            return {"status": "unknown", "reason": "Backend not running"}
            
        # 生成请求ID
        request_id = str(uuid.uuid4())
        logger.info(f"获取测试状态: test_id={test_id}, request_id={request_id}")
        
        # 向测试进程发送请求
        self.qt_to_test_queue.put({
            "type": MSG_GET_TEST_STATUS,
            "test_id": test_id,
            "request_id": request_id
        })
        
        # 等待响应
        start_time = time.time()
        timeout = 5  # 5秒超时
        
        while time.time() - start_time < timeout:
            try:
                response = self.test_to_qt_queue.get(block=True, timeout=0.5)
                if response.get("request_id") == request_id:
                    return response
            except (mp.queues.Empty, ConnectionError, BrokenPipeError, EOFError):
                pass
        
        # 超时，返回默认响应
        return {
            "status": "unknown",
            "test_id": test_id,
            "note": "Status request sent, but no immediate response"
        }
    
    def get_saved_test_data(self, test_dir: str) -> Dict[str, Any]:
        """
        获取已保存的测试数据
        
        Args:
            test_dir: 测试目录路径
            
        Returns:
            测试数据
        """
        info_path = os.path.join(test_dir, "test_info.json")
        
        try:
            if not os.path.exists(info_path):
                return {"status": "error", "reason": "Test info file not found"}
                
            with open(info_path, "r", encoding="utf-8") as f:
                test_info = json.load(f)
                
            # 创建结果数据结构
            result = {
                "status": "ok",
                "test_info": test_info,
                "files": []
            }
            
            # 获取所有步骤数据文件
            for item in os.listdir(test_dir):
                if item.endswith(".csv"):
                    file_path = os.path.join(test_dir, item)
                    try:
                        # 获取文件大小
                        size = os.path.getsize(file_path)
                        # 添加到文件列表
                        result["files"].append({
                            "name": item,
                            "path": file_path,
                            "size": size
                        })
                    except:
                        pass
            
            return result
            
        except Exception as e:
            logger.error(f"获取测试数据失败: {str(e)}")
            return {"status": "error", "reason": str(e)}
    
    def list_saved_tests(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出已保存的测试
        
        Args:
            device_id: 设备ID（可选，如果提供则只获取该设备的测试）
            
        Returns:
            测试列表
        """
        base_dir = "UserData/AutoSave"
        result = []
        
        try:
            # 如果指定了设备ID，只列出该设备的测试
            if device_id:
                device_dir = os.path.join(base_dir, device_id)
                if os.path.exists(device_dir) and os.path.isdir(device_dir):
                    for test_dir in os.listdir(device_dir):
                        test_path = os.path.join(device_dir, test_dir)
                        if os.path.isdir(test_path):
                            info_path = os.path.join(test_path, "test_info.json")
                            if os.path.exists(info_path):
                                try:
                                    with open(info_path, "r", encoding="utf-8") as f:
                                        test_info = json.load(f)
                                    result.append({
                                        "device_id": device_id,
                                        "test_id": test_info.get("test_id", "unknown"),
                                        "test_type": test_info.get("test_type", "unknown"),
                                        "name": test_info.get("name", "未命名"),
                                        "created_at": test_info.get("created_at", ""),
                                        "completed_at": test_info.get("completed_at", ""),
                                        "dir_path": test_path
                                    })
                                except:
                                    pass
            else:
                # 列出所有设备的测试
                for device_id in os.listdir(base_dir):
                    device_dir = os.path.join(base_dir, device_id)
                    if os.path.isdir(device_dir):
                        for test_dir in os.listdir(device_dir):
                            test_path = os.path.join(device_dir, test_dir)
                            if os.path.isdir(test_path):
                                info_path = os.path.join(test_path, "test_info.json")
                                if os.path.exists(info_path):
                                    try:
                                        with open(info_path, "r", encoding="utf-8") as f:
                                            test_info = json.load(f)
                                        result.append({
                                            "device_id": device_id,
                                            "test_id": test_info.get("test_id", "unknown"),
                                            "test_type": test_info.get("test_type", "unknown"),
                                            "name": test_info.get("name", "未命名"),
                                            "created_at": test_info.get("created_at", ""),
                                            "completed_at": test_info.get("completed_at", ""),
                                            "dir_path": test_path
                                        })
                                    except:
                                        pass
            
            # 按创建时间排序（最新的在前）
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return result
            
        except Exception as e:
            logger.error(f"列出已保存测试失败: {str(e)}")
            return []


if __name__ == "__main__":
    # 测试启动和关闭
    backend = MedicalTestBackend()
    try:
        backend.start()
        print("后端系统已启动，按Ctrl+C退出")
        
        # 主循环
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
            
    except Exception as e:
        print(f"运行错误: {e}")
    finally:
        backend.shutdown()
        print("后端系统已关闭")