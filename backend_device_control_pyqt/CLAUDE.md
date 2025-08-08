# CLAUDE.md - Backend Device Control PyQt

This file provides guidance to Claude Code (claude.ai/code) when working with the backend_device_control_pyqt module.

## Module Overview

This is a high-performance backend system for OECT (Organic Electrochemical Transistor) testing, using a 4-process architecture for real-time data acquisition, processing, and storage.

## Architecture Summary

### Process Architecture
```
Qt Process ↔ Test Process ↔ Data Transmission Process ↔ Data Save Process
```

- **Test Process**: Device communication, test execution, workflow orchestration
- **Data Transmission Process**: Real-time data routing, batching, format conversion  
- **Data Save Process**: File I/O operations, CSV/JSON storage
- **Qt Process**: UI and visualization (implemented in qt_app module)

### Key Design Patterns

1. **Async/Await**: All device communication uses asyncio for non-blocking operations
2. **Queue-Based IPC**: Inter-process communication via multiprocessing.Queue
3. **Step-Aware Buffering**: Prevents data corruption during test step transitions
4. **Worker Thread Pools**: Data save process uses 4 worker threads for file I/O

## Common Development Tasks

### Adding a New Test Type

When asked to add a new test type, follow these steps:

1. **Create Step Class** in `test/` directory:
```python
# test/new_test_step.py
from backend_device_control_pyqt.test.step import Step

class NewTestStep(Step):
    def __init__(self, params):
        super().__init__(params)
    
    async def execute(self, device, callbacks):
        # Implementation
        pass
    
    def generate_command(self):
        # Use command_gen functions
        pass
    
    def get_step_type(self):
        return "new_test"
```

2. **Add Command Generation** in `core/command_gen.py`:
```python
def gen_new_test_cmd(params):
    # TLV protocol: [0xFF][Type][Length][Value][0xFE]
    # 16-byte null prefix for alignment
    pass
```

3. **Update Data Parser** in `core/serial_data_parser.py` if needed

4. **Register in Test Process** (`processes/test_process.py`):
```python
# In TestManager.run_test_step()
if step_type == "new_test":
    from backend_device_control_pyqt.test.new_test_step import NewTestStep
    step = NewTestStep(params)
```

5. **Update Workflow Models** in `models/workflow_models.py`:
```python
class NewTestStepConfig(BaseModel):
    # Pydantic model for validation
    pass
```

### Modifying Data Processing

When asked to modify data processing:

1. **Real-time Processing** - Edit `processes/data_transmission_process.py`:
   - Modify `_handle_test_data()` for processing logic
   - Adjust `DATA_BATCH_SIZE` for performance tuning
   - Update `_combine_data_points()` for batching

2. **File Storage** - Edit `processes/data_save_process.py`:
   - Modify `_save_file()` for new formats
   - Update CSV column headers in respective methods
   - Maintain backward compatibility

3. **Data Parsing** - Edit `core/serial_data_parser.py`:
   - Update `bytes_to_numpy()` for new data formats
   - Adjust bias current compensation if needed

### Debugging Device Communication

When troubleshooting device issues:

1. **Check Serial Connection** (`core/async_serial.py`):
```python
# Enable debug logging
logger.debug(f"Sending command: {command.hex()}")
logger.debug(f"Received data: {data.hex()}")
```

2. **Verify Command Generation** (`core/command_gen.py`):
```python
# Test command generation
cmd = gen_transfer_cmd(params)
print(f"Generated command: {cmd.hex()}")
```

3. **Monitor Queue Communication**:
```python
# Add queue size monitoring
logger.info(f"Queue size: {queue.qsize()}")
```

### Performance Optimization

When asked to optimize performance:

1. **Batch Size Tuning**:
```python
# In data_transmission_process.py
DATA_BATCH_SIZE = 100  # Adjust based on data rate
```

2. **Worker Thread Count**:
```python
# In data_save_process.py
num_workers = 4  # Increase for more parallelism
```

3. **Queue Timeout Adjustment**:
```python
# Reduce timeout for faster response
data = queue.get(timeout=0.01)
```

## Critical Files and Their Roles

### Core System Files
- `main.py`: System entry point, API methods for Qt frontend
- `processes/test_process.py`: Device management, test execution
- `processes/data_transmission_process.py`: Data routing and batching
- `processes/data_save_process.py`: File I/O operations

### Device Communication
- `core/async_serial.py`: Async serial communication, device discovery
- `core/command_gen.py`: TLV protocol command generation
- `core/serial_data_parser.py`: Raw data to scientific units conversion

### Test Implementation
- `test/step.py`: Abstract base class for all test steps
- `test/transfer_step.py`: Gate voltage sweep tests (Vg vs Id)
- `test/transient_step.py`: Time-domain measurements (Time vs Id)
- `test/output_step.py`: Multi-gate I-V curves (Vd vs Id @ multiple Vg)

### Data Models
- `models/workflow_models.py`: Pydantic models for configuration validation
- `comunication/data_bridge.py`: Queue-based communication abstraction
- `utils/ipc.py`: IPC helper functions

## Data Flow and Formats

### Test Data Flow
```
Device → Test Process → Data Transmission → Qt (display)
                              ↓
                        Data Save (storage)
```

### Data Packet Formats

**Transfer Test** (5-byte packets):
- Data: Gate voltage + Drain current measurements
- End sequence: `FFFFFFFFFFFFFFFF`
- CSV: `Vg,Id`

**Transient Test** (7-byte packets):
- Data: Time + Drain current measurements
- End sequence: `FEFEFEFEFEFEFEFE`
- CSV: `Time,Id`

**Output Test** (5-byte packets):
- Data: Drain voltage + Multiple drain currents
- End sequence: `CDABEFCDABEFCDAB`
- CSV: `Vd,Id_Vg=-0.5,Id_Vg=-0.4,...`

## Important Constants and Settings

### Serial Communication
- Default baudrate: `512000`
- Stop command: `FF030100FE`
- Identity query: `FF040100FE`

### Data Processing
- Batch size: `100` data points
- Worker threads: `4` for file I/O
- Queue timeout: `0.01` seconds default
- Bias current compensation: `-1.2868e-06` A

### File Paths
- Data directory: `UserData/AutoSave/{device_id}/`
- Log directory: `logs/`
- Test info file: `test_info.json`
- Workflow config: `workflow.json`

## Error Handling Guidelines

### Process Communication Errors
- Always use try/except around queue operations
- Implement timeout handling for all blocking calls
- Log errors with context for debugging

### Device Connection Errors
- Automatic reconnection attempts
- Graceful degradation on connection loss
- Clear error messages to frontend

### Data Integrity
- Step-aware buffering prevents corruption
- Validate data before saving
- Maintain data caches for recovery

## Testing Guidelines

### Unit Testing
```python
# Test individual components
async def test_device_connection():
    device = AsyncSerialDevice(port, baudrate)
    await device.connect()
    assert device.is_connected
```

### Integration Testing
```python
# Test process communication
def test_queue_communication():
    queue = mp.Queue()
    queue.put({"type": "test_data", "data": "..."})
    result = queue.get(timeout=1)
    assert result["type"] == "test_data"
```

### Performance Testing
```python
# Monitor processing rates
start = time.time()
for _ in range(1000):
    process_data_point(data)
rate = 1000 / (time.time() - start)
logger.info(f"Processing rate: {rate} points/sec")
```

## Common Issues and Solutions

### Issue: Process startup timeout
**Solution**: Check system resources, verify Python environment, review logs

### Issue: Device not detected
**Solution**: Check serial permissions, verify baudrate, ensure device powered

### Issue: Data loss during high-speed acquisition
**Solution**: Increase batch size, add more worker threads, optimize queue sizes

### Issue: Memory usage growing
**Solution**: Clear data caches periodically, implement data decimation

## Code Style and Conventions

1. **Async Functions**: Use `async def` for all device operations
2. **Logging**: Use module logger for all output
3. **Error Handling**: Always catch specific exceptions
4. **Type Hints**: Use type hints for function parameters
5. **Docstrings**: Document all public methods
6. **Constants**: Define at module level in UPPER_CASE

## Security Considerations

- Never log sensitive data or passwords
- Validate all input parameters
- Sanitize file paths to prevent directory traversal
- Use safe serialization (avoid pickle for untrusted data)

## Performance Benchmarks

- Target data rate: 1000+ points/second
- Queue latency: < 10ms
- File write throughput: 10MB/s minimum
- Process startup time: < 2 seconds

## Maintenance Notes

- Log rotation configured at 10MB per file, 5 backups
- Clean up old test data periodically
- Monitor queue sizes to prevent memory issues
- Regular testing with different device configurations