"""
Decoder utilities for processing raw device data
Converts hex strings to bytes and parses them into usable data
支持output类型的多曲线数据处理
"""

import sys
import traceback
import numpy as np

########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################

def ads_cal_voltage(data):
    """
    Calculate voltage from 24-bit ADC data
    
    Args:
        data: 24-bit ADC data
        
    Returns:
        float: Calculated voltage
    """
    if data & 0x00800000:  # Highest bit set (negative)
        data = (((~data) & 0x007FFFFF) + 0x00000001)
        return -((data / 8388608.0) * 2.048)
    else:  # Positive
        return (data / 8388607.0) * 2.048

def remove_end_sequences(hex_string):
    """
    Remove end sequence markers from hex data
    
    Args:
        hex_string: Hex string data
        
    Returns:
        str: Cleaned hex string
    """
    # Define end sequence markers - *** 新增output结束序列 ***
    end_sequences = [
        'FFFFFFFFFFFFFFFF',  # Transfer结束序列
        'FEFEFEFEFEFEFEFE',  # Transient结束序列
        'CDABEFCDABEFCDAB'   # Output结束序列（小端字节序）
    ]
    
    # Remove markers if found
    cleaned_hex = hex_string
    for seq in end_sequences:
        if cleaned_hex.endswith(seq):
            logger.debug(f"检测到结束标识符: {seq}")
            cleaned_hex = cleaned_hex[:-len(seq)]
            break  # 只移除一次
    
    return cleaned_hex

def decode_hex_to_bytes(hex_string):
    """
    Convert hex string to bytes
    
    Args:
        hex_string: Hex string data
        
    Returns:
        bytes: Decoded bytes
    """
    try:
        # Check if we got a string or bytes
        if isinstance(hex_string, bytes):
            return hex_string
            
        # Remove end sequences BEFORE converting to bytes
        cleaned_hex = remove_end_sequences(hex_string)
        
        # Remove any whitespace
        cleaned_hex = cleaned_hex.replace(" ", "")
        
        # Ensure valid hex string (even length)
        if len(cleaned_hex) % 2 != 0:
            cleaned_hex += '0'
        
        try:
            return bytes.fromhex(cleaned_hex)
        except ValueError as e:
            logger.debug(f"解码失败 (值错误): {e}")
            return b''
    except Exception as e:
        logger.debug(f"解码失败 (其他错误): {e}")
        traceback.print_exc()
        return b''

def decode_bytes_to_data(byte_data, mode='transfer'):
    """
    Decode bytes to data points - *** 改进output支持 ***
    
    Args:
        byte_data: Raw byte data
        mode: 'transfer', 'transient', or 'output'
        
    Returns:
        list: List of [x, y] data points
    """
    # Define packet size based on mode
    packet_size = 7 if mode == 'transient' else 5
    
    # Define bias current correction
    bias_current = -1.2868e-6
    
    # Initialize result list
    result = []
    
    # Check for empty data
    if not byte_data or len(byte_data) < packet_size:
        logger.debug(f"解码: 数据为空或长度不足 ({len(byte_data) if byte_data else 0} 字节)")
        return result
    
    try:
        # Print some debug info
        logger.debug(f"解码: 模式={mode}, 数据长度={len(byte_data)}字节, 包大小={packet_size}字节")
        
        # *** 改进：检查是否包含output结束序列 ***
        if contains_output_end_sequence(byte_data):
            logger.debug("检测到output结束序列，将在处理中跳过")
        elif contains_end_sequence(byte_data):
            logger.debug("检测到其他结束序列，将在处理中跳过")
        
        # Process each packet
        packets_processed = 0
        for i in range(0, len(byte_data) - packet_size + 1, packet_size):
            # *** 改进：跳过各种类型的结束序列 ***
            if is_any_end_sequence(byte_data, i, packet_size):
                logger.debug(f"跳过结束序列在位置 {i}")
                continue
            
            try:
                if mode == 'transient':
                    # Process transient data
                    # Time stamp (4 bytes, little endian)
                    ts = int.from_bytes(byte_data[i:i+4], byteorder='little', signed=False)
                    
                    # Current (3 bytes)
                    current_raw = int.from_bytes(b'\x00' + byte_data[i+4:i+7], byteorder='big')
                    current_value = -ads_cal_voltage(current_raw) / 100.0 - bias_current
                    
                    # Add data point - convert ms to seconds for time
                    result.append([ts / 1000.0, current_value])
                    
                else:  # transfer or output
                    # Process transfer/output data
                    # Voltage (2 bytes, little endian, signed)
                    voltage_raw = int.from_bytes(byte_data[i:i+2], byteorder='little', signed=True)
                    
                    if mode == 'output':
                        # For output, this is drain voltage
                        voltage = voltage_raw / 1000.0  # Convert to volts
                    else:
                        # For transfer, this is gate voltage
                        voltage = voltage_raw / 1000.0  # Convert to volts
                    
                    # Current (3 bytes)
                    current_raw = int.from_bytes(b'\x00' + byte_data[i+2:i+5], byteorder='big')
                    current_value = -ads_cal_voltage(current_raw) / 100.0 - bias_current
                    
                    # Add data point
                    result.append([voltage, current_value])
                    
                    packets_processed += 1
                    
                    # Print the first few data points for debugging
                    if packets_processed <= 3:
                        logger.debug(f"数据点 {packets_processed}: Voltage={voltage}V, Current={current_value}A")
                        
            except Exception as e:
                logger.warning(f"解析数据包 {i//packet_size} 时出错: {e}")
                continue
    
    except Exception as e:
        logger.error(f"解码过程中出错: {e}")
        traceback.print_exc()
    
    # Print summary
    logger.debug(f"解码完成: 生成了 {len(result)} 个数据点")
    return result

def contains_end_sequence(byte_data):
    """
    Check if byte data contains end sequences
    
    Args:
        byte_data: Raw byte data
        
    Returns:
        bool: True if end sequences are found
    """
    if len(byte_data) < 8:
        return False
    
    # Check for common end sequence patterns
    end_patterns = [
        b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',  # 8 bytes of 0xFF (transfer)
        b'\xFE\xFE\xFE\xFE\xFE\xFE\xFE\xFE',  # 8 bytes of 0xFE (transient)
        b'\xCD\xAB\xEF\xCD\xAB\xEF\xCD\xAB',  # Output结束序列（小端字节序）
    ]
    
    for pattern in end_patterns:
        if pattern in byte_data:
            return True
    
    return False

def contains_output_end_sequence(byte_data):
    """
    *** 新增：专门检查output结束序列 ***
    
    Args:
        byte_data: Raw byte data
        
    Returns:
        bool: True if output end sequence is found
    """
    if len(byte_data) < 8:
        return False
    
    # Output特有的结束序列
    output_end_pattern = b'\xCD\xAB\xEF\xCD\xAB\xEF\xCD\xAB'
    
    return output_end_pattern in byte_data

def is_end_sequence(byte_data, index, packet_size):
    """
    Check if bytes at index represent an end sequence (transfer/transient)
    
    Args:
        byte_data: Raw byte data
        index: Current index
        packet_size: Packet size
        
    Returns:
        bool: True if this is an end sequence
    """
    # Check if we have enough bytes
    if index + packet_size > len(byte_data):
        return False
    
    # Get first byte
    first_byte = byte_data[index]
    
    # Check if all bytes in the packet are the same
    for i in range(1, packet_size):
        if index + i >= len(byte_data) or byte_data[index + i] != first_byte:
            return False
    
    # It's an end sequence if all bytes match and are either 0xFF or 0xFE
    return first_byte in (0xFF, 0xFE)

def is_output_end_sequence(byte_data, index, packet_size):
    """
    *** 新增：检查output结束序列 ***
    
    Args:
        byte_data: Raw byte data
        index: Current index
        packet_size: Packet size
        
    Returns:
        bool: True if this is an output end sequence
    """
    # Output结束序列：CDABEFCDABEFCDAB (8字节)
    output_end = b'\xCD\xAB\xEF\xCD\xAB\xEF\xCD\xAB'
    
    # 检查是否有足够的字节来匹配结束序列
    if index + len(output_end) > len(byte_data):
        return False
    
    # 检查是否匹配output结束序列
    return byte_data[index:index + len(output_end)] == output_end

def is_any_end_sequence(byte_data, index, packet_size):
    """
    *** 新增：检查任何类型的结束序列 ***
    
    Args:
        byte_data: Raw byte data
        index: Current index
        packet_size: Packet size
        
    Returns:
        bool: True if this is any type of end sequence
    """
    # 首先检查output结束序列（优先级最高）
    if is_output_end_sequence(byte_data, index, packet_size):
        return True
    
    # 然后检查传统的结束序列
    return is_end_sequence(byte_data, index, packet_size)

def parse_csv_data(csv_string):
    """
    Parse CSV format data from backend (especially for output measurements)
    
    Args:
        csv_string: CSV formatted string data
        
    Returns:
        dict: Parsed data with structure {x_values: [...], curves: {curve_name: [y_values]}}
    """
    try:
        lines = csv_string.strip().split('\n')
        if len(lines) < 2:
            logger.warning("CSV数据行数不足")
            return None
            
        # Parse header
        header = lines[0].split(',')
        x_label = header[0]  # First column is x-axis label
        curve_labels = header[1:]  # Subsequent columns are curve labels
        
        logger.debug(f"CSV解析: x轴={x_label}, 曲线数={len(curve_labels)}")
        
        # Parse data
        x_values = []
        curves = {label: [] for label in curve_labels}
        
        for line_num, line in enumerate(lines[1:], 1):
            values = line.strip().split(',')
            if len(values) == len(header):
                try:
                    x_val = float(values[0])
                    x_values.append(x_val)
                    
                    for i, label in enumerate(curve_labels):
                        y_val = float(values[i + 1])
                        curves[label].append(y_val)
                        
                except ValueError as e:
                    logger.warning(f"CSV第{line_num}行数据解析失败: {e}")
                    continue
            else:
                logger.warning(f"CSV第{line_num}行列数不匹配: 期望{len(header)}列，实际{len(values)}列")
        
        logger.debug(f"CSV解析完成: {len(x_values)}个x值, {len(curves)}条曲线")
        
        return {
            'x_values': x_values,
            'curves': curves,
            'x_label': x_label
        }
        
    except Exception as e:
        logger.error(f"解析CSV数据失败: {e}")
        traceback.print_exc()
        return None

# Test function to simulate decoding
def test_decode():
    # Sample transfer data (mock)
    transfer_hex = "7001E803E5036C01DC02E5038201FC03B503" + "FFFFFFFFFFFFFFFF"
    transient_hex = "03000000E50310000000E50320000000E503" + "FEFEFEFEFEFEFEFE"
    output_hex = "7001E803E5036C01DC02E5038201FC03B503" + "CDABEFCDABEFCDAB"  # *** 新增output测试数据 ***
    
    print("Testing Transfer Decoding:")
    transfer_bytes = decode_hex_to_bytes(transfer_hex)
    transfer_data = decode_bytes_to_data(transfer_bytes, 'transfer')
    logger.info(f"Decoded {len(transfer_data)} points from transfer data")
    
    print("\nTesting Transient Decoding:")
    transient_bytes = decode_hex_to_bytes(transient_hex)
    transient_data = decode_bytes_to_data(transient_bytes, 'transient')
    logger.info(f"Decoded {len(transient_data)} points from transient data")
    
    print("\nTesting Output Decoding:")
    output_bytes = decode_hex_to_bytes(output_hex)
    output_data = decode_bytes_to_data(output_bytes, 'output')
    logger.info(f"Decoded {len(output_data)} points from output data")
    
    print("\nTesting CSV Parsing:")
    csv_test = """Vd,Id(Vg=0mV),Id(Vg=200mV),Id(Vg=400mV)
-0.100,1.3576e-06,9.69417e-07,1.23065e-06
0.000,1.63104e-06,7.76546e-07,4.27425e-07
0.100,5.90999e-07,8.64437e-07,1.42108e-06"""
    
    csv_data = parse_csv_data(csv_test)
    if csv_data:
        logger.info(f"Parsed CSV: {len(csv_data['x_values'])} points, {len(csv_data['curves'])} curves")

if __name__ == "__main__":
    # 设置调试日志级别
    logging.basicConfig(level=logging.DEBUG)
    test_decode()