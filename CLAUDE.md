# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Development mode - run from source
python run_qt.py

# Production mode - run packaged version  
python run_qt_for_exe.py

# macOS version
python run_qt_for_macapp.py
```

### Building Executables
```bash
# Install packaging dependencies
pip install pyinstaller

# Build Windows executable
pyinstaller --onefile --windowed --icon=my_icon.ico run_qt_for_exe.py

# Build with spec file for Windows
pyinstaller run_qt_for_exe.spec

# Build macOS app bundle  
pyinstaller run_qt_for_macapp.spec
```

### Installing Dependencies
```bash
# Install all required packages
pip install -r requirements.txt

# Key dependencies include:
# - PyQt5 (GUI framework)
# - numpy (numerical computing)
# - pyqtgraph (plotting)
# - pyserial, pyserial-asyncio (serial communication)
# - pillow (image processing)
```

### Testing and Debugging
```bash
# Run with debug logging (modify logger_config.py)
# Check logs in the logs/ directory
# Each process creates its own log file with module-specific names:
# - backend_device_control_pyqt.main.log (backend main)
# - backend_device_control_pyqt.processes.test_process.log (device testing)
# - backend_device_control_pyqt.processes.data_transmission_process.log (data processing)
# - backend_device_control_pyqt.processes.data_save_process.log (file operations)
# - qt_app.main_window.log (Qt main window)
# - qt_app.widgets.device_control.log (device control widget)
# - qt_app.widgets.test_history.log (test history widget)
# - qt_app.widgets.realtime_plot.log (real-time plotting)
```

## System Architecture

### Multi-Process Design
The application uses a 4-process architecture for high performance and stability:

1. **Main Process (PyQt)** - `qt_app/main_window.py`
   - User interface and event handling
   - Manages backend communication
   - Real-time data visualization

2. **Test Process** - `backend_device_control_pyqt/processes/test_process.py`
   - Device connection and control
   - Test execution and workflow orchestration
   - Serial communication management

3. **Data Transmission Process** - `backend_device_control_pyqt/processes/data_transmission_process.py`
   - Real-time data processing and routing
   - Batch processing optimization
   - Message distribution between processes

4. **Data Save Process** - `backend_device_control_pyqt/processes/data_save_process.py`
   - File I/O operations
   - CSV data saving
   - Multi-threaded write operations

### Communication Flow
```
Qt Process ↔ Test Process ↔ Data Transmission Process ↔ Data Save Process
     ↑                            ↓
     └─── Real-time Data ────────┘
```

### Key Components

#### Backend System
- **Entry Point**: `backend_device_control_pyqt/main.py` - `MedicalTestBackend` class
- **Process Management**: Uses multiprocessing.Queue for inter-process communication with spawn method
- **Device Communication**: `backend_device_control_pyqt/core/async_serial.py` for async serial I/O
- **Data Bridge**: `backend_device_control_pyqt/comunication/data_bridge.py` for communication abstraction
- **IPC Utilities**: `backend_device_control_pyqt/utils/ipc.py` for inter-process communication helpers

#### Test Types
- **Transfer Step**: `backend_device_control_pyqt/test/transfer_step.py` - Gate voltage sweeps
- **Transient Step**: `backend_device_control_pyqt/test/transient_step.py` - Time-domain response
- **Output Step**: `backend_device_control_pyqt/test/output_step.py` - Multi-gate voltage I-V curves
- **Base Class**: `backend_device_control_pyqt/test/step.py` - Common test step interface

#### Frontend Components
- **Main Window**: `qt_app/main_window.py` - Application entry point and tab management
  - Handles tab switching with state preservation for device control
  - Manages backend communication and status display
- **Device Control**: `qt_app/widgets/device_control.py` - Test configuration and execution
  - Test information input: name, description, chip ID, device number
  - **Per-device state management**: Each device maintains separate test information settings
  - Integrated workflow controls: start/stop test, import/export workflows
  - Workflow import appends to current workflow instead of overwriting
  - Enhanced UI styling with clear input fields and color-coded buttons
  - Device list displays in alphabetical order (A-Z) by device ID
- **Test History**: `qt_app/widgets/test_history.py` - Data analysis and export
  - Displays test metadata including chip ID and device number
  - Advanced drag-and-drop sorting with 6 criteria: time, name, device, chip ID, device number, description
  - Click sorting blocks to toggle ascending/descending order
  - Visual feedback with color-coded blocks (blue for ascending, orange for descending)
- **Real-time Plot**: `qt_app/widgets/realtime_plot.py` - Live data visualization using pyqtgraph
- **Workflow Editor**: `qt_app/widgets/workflow_editor.py` - Complex test sequence configuration
- **Custom Widgets**: `qt_app/widgets/custom_widgets.py` - Reusable UI components
- **Step Node**: `qt_app/widgets/step_node.py` - Workflow step visualization
- **Step Params Form**: `qt_app/widgets/step_params_form.py` - Parameter input forms for test steps

### Data Management

#### File Structure
- **Test Data**: Saved to `UserData/AutoSave/{device_id}/{timestamp}_{test_type}_{test_id}/`
- **Log Files**: Created in `logs/` directory with automatic rotation
- **Configuration**: Qt settings stored via QSettings

#### Data Formats
- **Transfer Test**: CSV with columns Vg (gate voltage), Id (drain current)
- **Transient Test**: CSV with columns Time, Id (drain current)  
- **Output Test**: CSV with Vd (drain voltage) and multiple Id columns for different gate voltages
- **Test Metadata**: JSON files with test parameters and configuration, including:
  - Test name and description
  - Chip ID and device number (optional fields for sample identification)
  - Workflow parameters and device information

### Device Communication

#### Serial Protocol
- **Baud Rate**: 512000 (default)
- **Data Format**: Hexadecimal command/response protocol
- **Device Detection**: Automatic device ID recognition
- **Command Generation**: `backend_device_control_pyqt/core/command_gen.py`
- **Data Parsing**: `backend_device_control_pyqt/core/serial_data_parser.py`
- **Async Communication**: `backend_device_control_pyqt/core/async_serial.py`

### Workflow System

#### Configuration
- **Workflow Models**: `backend_device_control_pyqt/models/workflow_models.py`
- **Execution Engine**: `backend_device_control_pyqt/test/test.py`
- **Step Types**: Supports transfer, transient, output, and loop (for iterations)
- **Nested Structures**: Complex workflows with loops and conditional execution

## Development Guidelines

### Adding New Test Types
1. Create new step class inheriting from `backend_device_control_pyqt/test/step.py`
2. Implement required abstract methods (`get_step_type`, `execute`, etc.)
3. Register in test process workflow system
4. Add UI components in `qt_app/widgets/` as needed
5. Update workflow models if new parameters are required

### Modifying Data Processing
- Data flows through the transmission process before saving
- Modify `data_transmission_process.py` for real-time processing changes
- Update `data_save_process.py` for file format changes
- Consider backward compatibility with existing saved data

### UI Customization  
- Main window uses tabbed interface with splitter layouts
- Real-time plotting uses pyqtgraph for performance
- Custom widgets extend PyQt5 base classes
- Style sheets defined inline or in widget constructors

### Logging Configuration
- Central logging management in `logger_config.py` with `LoggerManager` class
- Each module gets independent log files named by module path
- Configurable log levels and rotation settings (default 10MB per file, 5 backups)
- Use `get_module_logger()` for consistent logging across modules
- Logs are stored in `logs/` directory with automatic rotation

### Build and Distribution
- PyInstaller used for creating executables
- Spec files customize build process and include assets
- Icon files (ico/icns) for different platforms
- Consider dependencies when packaging (especially PyQt5 plugins)

## Common Troubleshooting

### Process Communication Issues
- Check queue timeouts in backend communication
- Verify all processes start successfully (check logs)
- Monitor system resources during high-throughput tests

### Device Connection Problems  
- Verify serial port permissions and availability
- Check device power and cable connections
- Confirm correct baud rate and protocol settings
- Use device manager to verify driver installation

### Data Loss or Corruption
- Check available disk space for data saving
- Verify file permissions in UserData directory
- Monitor data save process logs for errors
- Consider increasing queue sizes for high-frequency data

### Performance Optimization
- Adjust batch sizes in data transmission process
- Monitor memory usage during long tests
- Consider data decimation for display vs. storage
- Tune timer intervals in Qt widgets for responsiveness