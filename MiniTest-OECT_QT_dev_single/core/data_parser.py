"""
数据解析模块 - data_parser.py
负责解析从设备接收的原始数据
"""

import numpy as np
import struct


def ADS_CalVoltage(data):
    """将 24-bit 原始 ADC 数据转换为电压值"""
    if data & 0x00800000:  # 最高位为1，表示负数
        data = (((~data) & 0x007FFFFF) + 0x00000001)
        voltage = -((data / 8388608.0) * 2.048)
    else:  # 正数情况
        voltage = (data / 8388607.0) * 2.048
    return voltage


# 偏置电流
bias_current = -1.2868e-06


def bytes_to_numpy(byte_data, mode='transient'):
    """
    直接将字节数组转换为numpy数组
    
    Args:
        byte_data: 字节数组
        mode: 数据模式，'transient' (7字节一组)
    
    Returns:
        numpy数组，每行包含两列 [timestamp, current]
    """
    # 移除可能的结束序列（如果存在）
    end_sequences = [
        b'\xFE\xFE\xFE\xFE\xFE\xFE\xFE\xFE',  # Transient结束序列
    ]
    
    for end_seq in end_sequences:
        if byte_data.endswith(end_seq):
            byte_data = byte_data[:-len(end_seq)]
            break
    
    # Transient模式使用7字节一组: 4字节时间戳 + 3字节电流
    packet_size = 7
    
    # 计算能被完整处理的字节数，丢弃不完整的尾部数据
    complete_bytes = (len(byte_data) // packet_size) * packet_size
    if complete_bytes < len(byte_data):
        # 截取完整的部分
        byte_data = byte_data[:complete_bytes]
    
    # 如果没有完整的包，返回空数组
    if len(byte_data) == 0:
        return np.zeros((0, 2))
    
    # 创建结果数组
    num_entries = len(byte_data) // packet_size
    result = np.zeros((num_entries, 2))
    
    # 处理每一组数据
    for i in range(num_entries):
        offset = i * packet_size
        
        # 处理时间戳 (4字节，需要字节序调整)
        ts_bytes = byte_data[offset:offset+4]
        # 反转字节序 (小端到大端)
        ts_bytes_swapped = bytes(reversed(ts_bytes))
        timestamp = struct.unpack('>i', ts_bytes_swapped)[0]  # 大端有符号整数
        
        # 处理电流 (3字节)
        current_bytes = byte_data[offset+4:offset+7]
        # 补齐到4字节以便解析
        current_raw = int.from_bytes(b'\x00' + current_bytes, byteorder='big')
        current_value = - ADS_CalVoltage(current_raw) / 100.0  # 这里的电流要加负号，硬件设计的原因 
        result[i, 0] = timestamp / 1000  # 时间戳单位从ms转为s
        result[i, 1] = current_value - bias_current
    
    return result


def hex_to_numpy(hex_data: str) -> np.ndarray:
    """
    将十六进制字符串转换为numpy数组
    
    Args:
        hex_data: 十六进制字符串
        
    Returns:
        numpy数组，每行包含两列 [timestamp_s, current_A]
    """
    # 过滤掉结束序列的字节（全部是FE的包）
    # 这样可以避免在每个step结束时出现跳点
    if all(c in 'FEfe' for c in hex_data):
        return np.zeros((0, 2))
    
    byte_data = bytes.fromhex(hex_data)
    return bytes_to_numpy(byte_data, mode='transient')


def decode_identity_response(byte_data: bytes) -> str:
    """
    解码设备身份字符串，自动去除自定义结束符
    """
    # 支持多种结束符
    end_flags = [
        b'\xDE\xAD\xBE\xEF\xC0\xFF\xEE\x00',  # 自定义16进制结束符
        b'DONE!!!',
        b'\xFE\xFE\xFE\xFE\xFE\xFE\xFE\xFE',
        b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    ]

    for end_seq in end_flags:
        if byte_data.endswith(end_seq):
            byte_data = byte_data[:-len(end_seq)]
            break

    try:
        return byte_data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return f"未知设备 ({byte_data.hex()[:16]}...)"

