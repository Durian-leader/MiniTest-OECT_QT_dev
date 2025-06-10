"""
Decoder utilities for processing raw device data
Converts hex strings to bytes and parses them into usable data
"""

import sys
import traceback
import numpy as np
# 日志记录器
import logging
logger = logging.getLogger(__name__)

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
    # Define end sequence markers
    end_sequences = ['FFFFFFFFFFFFFFFF', 'FEFEFEFEFEFEFEFE']
    
    # Remove markers if found
    cleaned_hex = hex_string
    for seq in end_sequences:
        if cleaned_hex.endswith(seq):
            logger.info(f"检测到结束标识符: {seq}")
            cleaned_hex = cleaned_hex[:-len(seq)]
    
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
            
        # Remove end sequences
        cleaned_hex = remove_end_sequences(hex_string)
        
        # Remove any whitespace
        cleaned_hex = cleaned_hex.replace(" ", "")
        
        # Ensure valid hex string (even length)
        if len(cleaned_hex) % 2 != 0:
            cleaned_hex += '0'
        
        try:
            return bytes.fromhex(cleaned_hex)
        except ValueError as e:
            logger.info(f"解码失败 (值错误): {e}")
            return b''
    except Exception as e:
        logger.info(f"解码失败 (其他错误): {e}")
        traceback.print_exc()
        return b''

def decode_bytes_to_data(byte_data, mode='transfer'):
    """
    Decode bytes to data points
    
    Args:
        byte_data: Raw byte data
        mode: 'transfer' or 'transient'
        
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
        logger.info(f"解码: 数据为空或长度不足 ({len(byte_data) if byte_data else 0} 字节)")
        return result
    
    try:
        # Print some debug info
        logger.info(f"解码: 模式={mode}, 数据长度={len(byte_data)}字节, 包大小={packet_size}字节")
        
        # Process each packet
        for i in range(0, len(byte_data) - packet_size + 1, packet_size):
            # Skip possible end sequence markers
            if is_end_sequence(byte_data, i, packet_size):
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
                    
                else:  # transfer
                    # Process transfer data
                    # Gate voltage (2 bytes, little endian, signed)
                    voltage_raw = int.from_bytes(byte_data[i:i+2], byteorder='little', signed=True)
                    voltage = voltage_raw / 1000.0  # Convert to volts
                    
                    # Current (3 bytes)
                    current_raw = int.from_bytes(b'\x00' + byte_data[i+2:i+5], byteorder='big')
                    current_value = -ads_cal_voltage(current_raw) / 100.0 - bias_current
                    
                    # Add data point
                    result.append([voltage, current_value])
                    
                    # Print the first few data points for debugging
                    if len(result) <= 5:
                        logger.info(f"数据点 {len(result)}: Voltage={voltage}V, Current={current_value}A")
                        
            except Exception as e:
                logger.info(f"解析数据包 {i//packet_size} 时出错: {e}")
                continue
    
    except Exception as e:
        logger.info(f"解码过程中出错: {e}")
        traceback.print_exc()
    
    # Print summary
    logger.info(f"解码完成: 生成了 {len(result)} 个数据点")
    return result

def is_end_sequence(byte_data, index, packet_size):
    """
    Check if bytes at index represent an end sequence
    
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

# Test function to simulate decoding
def test_decode():
    # Sample transfer data (mock)
    transfer_hex = "7001E803E5036C01DC02E5038201FC03B503" + "FFFFFFFFFFFFFFFF"
    transient_hex = "03000000E50310000000E50320000000E503" + "FEFEFEFEFEFEFEFE"
    
    print("Testing Transfer Decoding:")
    transfer_bytes = decode_hex_to_bytes(transfer_hex)
    transfer_data = decode_bytes_to_data(transfer_bytes, 'transfer')
    logger.info(f"Decoded {len(transfer_data)} points from transfer data")
    
    print("\nTesting Transient Decoding:")
    transient_bytes = decode_hex_to_bytes(transient_hex)
    transient_data = decode_bytes_to_data(transient_bytes, 'transient')
    logger.info(f"Decoded {len(transient_data)} points from transient data")

if __name__ == "__main__":
    test_decode()