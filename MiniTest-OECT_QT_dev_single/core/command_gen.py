"""
命令生成模块 - command_gen.py
负责生成Transient测试命令
"""

from typing import List, Dict, Any


def gen_transient_cmd(params: Dict[str, Any]) -> List[int]:
    """
    生成符合 TLV 协议的 Transient 命令数据帧
    
    Args:
        params: 命令参数字典，包含以下字段:
            - timeStep: 采样间隔(毫秒)
            - sourceVoltage: 源极电压
            - drainVoltage: 漏极电压
            - bottomTime: 低电平时间
            - topTime: 高电平时间
            - gateVoltageBottom: 栅极低电平
            - gateVoltageTop: 栅极高电平
            - cycles: 循环次数
            
    Returns:
        List[int]: 生成的二进制数据帧
    """
    # 检查必要参数
    required_params = [
        "timeStep", "sourceVoltage", "drainVoltage", "bottomTime",
        "topTime", "gateVoltageBottom", "gateVoltageTop", "cycles"
    ]
    
    for param in required_params:
        if param not in params:
            raise ValueError(f"Missing required parameter: {param}")
    
    # 帧头(1) + Type(1) + Length(1) + Value(16) + 帧尾(1)
    ret = [0] * 20
    
    ret[0] = 0xFF  # 帧头
    ret[1] = 2   # Type
    ret[2] = 16    # Length（Transient 指令固定 16 字节）
    
    # 按小端序填充数据
    ret[3] = params["timeStep"] & 0x00FF
    ret[4] = (params["timeStep"] & 0xFF00) >> 8
    
    ret[5] = params["sourceVoltage"] & 0x00FF
    ret[6] = (params["sourceVoltage"] & 0xFF00) >> 8
    
    ret[7] = params["drainVoltage"] & 0x00FF
    ret[8] = (params["drainVoltage"] & 0xFF00) >> 8
    
    ret[9] = params["bottomTime"] & 0x00FF
    ret[10] = (params["bottomTime"] & 0xFF00) >> 8
    
    ret[11] = params["topTime"] & 0x00FF
    ret[12] = (params["topTime"] & 0xFF00) >> 8
    
    ret[13] = params["gateVoltageBottom"] & 0x00FF
    ret[14] = (params["gateVoltageBottom"] & 0xFF00) >> 8
    
    ret[15] = params["gateVoltageTop"] & 0x00FF
    ret[16] = (params["gateVoltageTop"] & 0xFF00) >> 8
    
    ret[17] = params["cycles"] & 0x00FF
    ret[18] = (params["cycles"] & 0xFF00) >> 8
    
    ret[19] = 0xFE  # 帧尾
    
    # 在指令前添加 16 个字节的 0x00
    ret = [0x00] * 16 + ret
    
    return ret


def bytes_to_hex(data) -> str:
    """Convert byte data to hex string"""
    if isinstance(data, list):
        return ''.join(f"{x:02X}" for x in data)
    return data.hex().upper()


def gen_who_are_you_cmd() -> list:
    """
    生成用于询问设备身份的命令数据帧（Type=0x04）
    
    Returns:
        List[int]: 生成的二进制数据帧
    """
    ret = [0] * 4
    ret[0] = 0xFF    # 帧头
    ret[1] = 0x04    # Type（自定义，表示"你是谁？"）
    ret[2] = 0x00    # Length = 0（无附加参数）
    ret[3] = 0xFE    # 帧尾

    # 前面补 16 个 0x00，以兼容数据包结构
    return [0x00] * 16 + ret

