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

bias_current = -1.2868e-06

def bytes_to_numpy(byte_data, mode='transient'):
    """
    直接将字节数组转换为numpy数组
    
    Args:
        byte_data: 字节数组
        mode: 数据模式，'transient' (7字节一组) 或 'transfer' (5字节一组)
    
    Returns:
        numpy数组，每行包含两列 [timestamp/voltage, current]
    """
    # 移除可能的结束序列（如果存在）
    for end_seq in [b'\xFE\xFE\xFE\xFE\xFE\xFE\xFE\xFE', b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF']:
        if byte_data.endswith(end_seq):
            byte_data = byte_data[:-len(end_seq)]
            break
    
    # 确定包大小和处理方式
    if mode == 'transient':
        packet_size = 7  # 4字节时间戳 + 3字节电流
    else:  # transfer模式
        packet_size = 5  # 2字节电压 + 3字节电流
    
    # 修改：计算能被完整处理的字节数，丢弃不完整的尾部数据
    complete_bytes = (len(byte_data) // packet_size) * packet_size
    if complete_bytes < len(byte_data):
        # 记录丢弃的字节数
        discarded_bytes = len(byte_data) - complete_bytes
        print(f"警告: 丢弃 {discarded_bytes} 字节不完整的数据包")
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
        
        if mode == 'transient':
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
            result[i, 0] = timestamp / 1000  # 时间戳单位为ms
            result[i, 1] = current_value - bias_current
            
        else:  # transfer模式
            # 处理电压 (2字节，需要字节序调整)
            voltage_bytes = byte_data[offset:offset+2]
            # 反转字节序
            voltage_bytes_swapped = bytes(reversed(voltage_bytes))
            voltage = struct.unpack('>h', voltage_bytes_swapped)[0]  # 大端有符号短整数
            
            # 处理电流 (3字节)
            current_bytes = byte_data[offset+2:offset+5]
            # 补齐到4字节以便解析
            current_raw = int.from_bytes(b'\x00' + current_bytes, byteorder='big')
            current_value = - ADS_CalVoltage(current_raw) / 100.0  # 这里的电流要加负号，硬件设计的原因 
            
            result[i, 0] = voltage / 1000  # 电压单位为V
            result[i, 1] = current_value - bias_current
    
    return result

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
    except UnicodeDecodeError as e:
        raise ValueError(f"解码失败: {e}, 原始数据: {byte_data.hex()}")


if __name__ == "__main__":
    identity_response = bytes.fromhex('64 65 76 69 63 65 32 30 32 35 30 34 31 33 30 30 31')
    print(decode_identity_response(identity_response))
