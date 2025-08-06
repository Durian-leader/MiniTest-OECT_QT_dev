from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union, Literal

class TransferStepConfig(BaseModel):
    """转移特性测试步骤配置"""
    type: Literal["transfer"] = "transfer"
    command_id: int
    params: Dict[str, Any] = {
        "isSweep": 0,
        "timeStep": 0,
        "sourceVoltage": 0,
        "drainVoltage": 0,
        "gateVoltageStart": 0,
        "gateVoltageEnd": 0,
        "gateVoltageStep": 0
    }

class TransientStepConfig(BaseModel):
    """瞬态特性测试步骤配置"""
    type: Literal["transient"] = "transient"
    command_id: int
    params: Dict[str, Any] = {
        "timeStep": 0,
        "sourceVoltage": 0,
        "drainVoltage": 0,
        "bottomTime": 0,
        "topTime": 0,
        "gateVoltageBottom": 0,
        "gateVoltageTop": 0,
        "cycles": 0
    }


class OutputStepConfig(BaseModel):
    """输出特性测试步骤配置"""
    type: Literal["output"] = "output"
    command_id: int
    params: Dict[str, Any] = {
        "isSweep": 0,
        "timeStep": 0,
        "sourceVoltage": 0,
        "gateVoltage": 0,
        "drainVoltageStart": 0,
        "drainVoltageEnd": 0,
        "drainVoltageStep": 0
    }

# 循环配置
class LoopConfig(BaseModel):
    """循环配置"""
    type: Literal["loop"] = "loop"
    iterations: int = Field(..., gt=0, description="循环次数")
    steps: List[Union["TransferStepConfig", "TransientStepConfig", "OutputStepConfig", "LoopConfig"]]

# 工作流参数
class WorkflowParams(BaseModel):
    """工作流参数"""
    test_id: str
    device_id: str
    port: str
    baudrate: int
    name: str = "自定义工作流"
    description: str = ""
    chip_id: str = ""
    device_number: str = ""
    steps: List[Union[TransferStepConfig, TransientStepConfig, OutputStepConfig, LoopConfig]]