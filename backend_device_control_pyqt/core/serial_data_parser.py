import numpy as np
import struct

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################
from app_config import get_bias_current, get_bias_reference_transimpedance

def ADS_CalVoltage(data):
    """将 24-bit 原始 ADC 数据转换为电压值"""
    if data & 0x00800000:  # 最高位为1，表示负数
        data = (((~data) & 0x007FFFFF) + 0x00000001)
        voltage = -((data / 8388608.0) * 2.048)
    else:  # 正数情况
        voltage = (data / 8388607.0) * 2.048
    return voltage

def bytes_to_numpy(byte_data, mode='transient', transimpedance_ohms=100.0, transient_packet_size: int = 7):
    """Convert byte data to a numpy array."""
    end_sequences = [
        b'\xFE\xFE\xFE\xFE\xFE\xFE\xFE\xFE',
        b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
        b'\xCD\xAB\xEF\xCD\xAB\xEF\xCD\xAB',
    ]

    for end_seq in end_sequences:
        if byte_data.endswith(end_seq):
            byte_data = byte_data[:-len(end_seq)]
            break

    try:
        transimpedance_ohms = float(transimpedance_ohms)
    except (TypeError, ValueError):
        transimpedance_ohms = 100.0
    if transimpedance_ohms <= 0:
        transimpedance_ohms = 100.0

    bias_current = 0.0

    if mode == 'transient':
        try:
            transient_packet_size = int(transient_packet_size)
        except (TypeError, ValueError):
            transient_packet_size = 7
        if transient_packet_size not in (7, 9):
            transient_packet_size = 7
        packet_size = transient_packet_size
    else:
        packet_size = 5

    complete_bytes = (len(byte_data) // packet_size) * packet_size
    if complete_bytes < len(byte_data):
        discarded_bytes = len(byte_data) - complete_bytes
        logger.warning(f"Discarded {discarded_bytes} bytes of partial packet")
        byte_data = byte_data[:complete_bytes]

    if len(byte_data) == 0:
        num_columns = 3 if mode == 'transient' and packet_size == 9 else 2
        return np.zeros((0, num_columns))

    num_entries = len(byte_data) // packet_size
    num_columns = 3 if mode == 'transient' and packet_size == 9 else 2
    result = np.zeros((num_entries, num_columns))

    for i in range(num_entries):
        offset = i * packet_size

        if mode == 'transient':
            ts_bytes = byte_data[offset:offset+4]
            ts_bytes_swapped = bytes(reversed(ts_bytes))
            timestamp = struct.unpack('>i', ts_bytes_swapped)[0]
            if packet_size == 9:
                vg_bytes = byte_data[offset+4:offset+6]
                vg_bytes_swapped = bytes(reversed(vg_bytes))
                gate_voltage = struct.unpack('>h', vg_bytes_swapped)[0] / 1000.0
                current_bytes = byte_data[offset+6:offset+9]
            else:
                gate_voltage = None
                current_bytes = byte_data[offset+4:offset+7]
            current_raw = int.from_bytes(b'\x00' + current_bytes, byteorder='big')
            current_value = - ADS_CalVoltage(current_raw) / transimpedance_ohms
            result[i, 0] = timestamp / 1000
            result[i, 1] = current_value - bias_current
            if gate_voltage is not None and num_columns > 2:
                result[i, 2] = gate_voltage
        else:
            voltage_bytes = byte_data[offset:offset+2]
            voltage_bytes_swapped = bytes(reversed(voltage_bytes))
            voltage = struct.unpack('>h', voltage_bytes_swapped)[0]
            current_bytes = byte_data[offset+2:offset+5]
            current_raw = int.from_bytes(b'\x00' + current_bytes, byteorder='big')
            current_value = - ADS_CalVoltage(current_raw) / transimpedance_ohms
            result[i, 0] = voltage / 1000
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
