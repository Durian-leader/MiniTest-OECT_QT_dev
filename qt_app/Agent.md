# CLAUDE.md - Qt Application Module

This file provides guidance to Claude Code (claude.ai/code) when working with the qt_app module.

## Module Overview

This is the PyQt5-based graphical user interface for the OECT testing system. It provides device control, real-time data visualization, workflow editing, and historical data analysis capabilities.

## Architecture Summary

### Widget Hierarchy
```
MainWindow
├── DeviceControlWidget (Tab 1)
│   ├── Device List
│   ├── WorkflowEditorWidget
│   │   └── StepNodeWidget[]
│   │       └── StepParamsFormWidget
│   └── RealtimePlotWidget
└── TestHistoryWidget (Tab 2)
    ├── Test List
    ├── Step List
    └── Data Plot/Details
```

### Key Design Patterns

1. **Signal-Slot Architecture**: All inter-widget communication via Qt signals
2. **State Preservation**: Per-device settings saved independently
3. **Custom Delegates**: Rich rendering for complex list items
4. **Dynamic Forms**: Parameter forms generated based on step type

## Common Development Tasks

### Adding a New Tab to Main Window

When asked to add a new tab:

```python
# In main_window.py
def _init_ui(self):
    # Add new tab
    self.new_widget = NewWidget(self.backend)
    self.tab_widget.addTab(self.new_widget, "New Feature")
    
    # Handle tab switching if needed
    def on_tab_changed(self, index):
        if index == 2:  # New tab index
            self.new_widget.refresh_data()
```

### Adding a New Test Type to UI

When asked to support a new test type in the UI:

1. **Update Step Parameters Form** (`step_params_form.py`):
```python
def _create_new_test_form(self):
    # Add input fields for new test type
    self.new_param = NoWheelDoubleSpinBox()
    self.new_param.setRange(-10.0, 10.0)
    layout.addRow("New Parameter:", self.new_param)
    
def get_params(self):
    elif self.step_type == "new_test":
        return {
            "new_param": self.new_param.value(),
            # ...
        }
```

2. **Update Step Node** (`step_node.py`):
```python
# Add to step type dropdown
self.type_combo.addItems(["Transfer", "Transient", "Output", "Loop", "New Test"])

# Update parameter preview
def _get_preview_text(self):
    elif step_type == "new_test":
        return f"Param: {params.get('new_param', 0)}"
```

3. **Update Real-time Plot** (`realtime_plot.py`):
```python
def handle_test_data(self, message):
    elif step_type == "new_test":
        # Handle new test type data
        self._update_new_test_plot(decoded_data)
```

4. **Update Data Decoder** (`utils/decoder.py`):
```python
def decode_bytes_to_data(data_bytes, mode):
    elif mode == "new_test":
        # Parse new test data format
        pass
```

### Modifying Device List Behavior

When working with device list in `device_control.py`:

```python
# Custom rendering in DeviceItemDelegate
def paint(self, painter, option, index):
    # Modify visual appearance
    if is_special_device:
        painter.fillRect(option.rect, QColor("#special_color"))
    
# Device selection handling
def on_device_selected(self):
    # Load device-specific settings
    self.test_info_per_device[device_id] = {
        "name": "",
        "description": "",
        "chip_id": "",
        "device_number": ""
    }
```

### Improving Real-time Plot Performance

When optimizing plot performance:

```python
# In realtime_plot.py
# 1. Adjust buffer size
self.max_points = 5000  # Reduce for better performance

# 2. Optimize update frequency
self.update_timer = QTimer()
self.update_timer.setInterval(100)  # Increase interval

# 3. Use downsampling
if len(self.data_x) > 1000:
    # Downsample for display
    indices = np.linspace(0, len(self.data_x)-1, 1000, dtype=int)
    display_x = self.data_x[indices]
    display_y = self.data_y[indices]
```

### Adding Keyboard Shortcuts

When implementing keyboard shortcuts:

```python
# In any widget
def __init__(self):
    # Create shortcuts
    self.start_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
    self.start_shortcut.activated.connect(self.start_test)
    
    self.stop_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
    self.stop_shortcut.activated.connect(self.stop_test)
```

### Implementing Drag and Drop

For drag and drop functionality (see `step_node.py` for example):

```python
def mousePressEvent(self, event):
    if event.button() == Qt.LeftButton:
        # Start drag
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.step_index))
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

def dropEvent(self, event):
    # Handle drop
    source_index = int(event.mimeData().text())
    # Reorder items
```

## Critical Files and Their Roles

### Main Application
- `main_window.py`: Application entry, tab management, backend initialization
  - Key methods: `_init_backend()`, `_on_tab_changed()`, `closeEvent()`
  - Settings: Window geometry saved via QSettings

### Device Control
- `device_control.py`: Core testing interface
  - State management: `test_info_per_device`, `workflow_per_device`
  - Key signals: `device_selected`, `test_started`, `test_stopped`
  - Real-time updates: `_real_time_data_timer` (10ms interval)

### Data Visualization
- `realtime_plot.py`: Live data plotting
  - Plot modes: Single curve (transfer/transient), Multi-curve (output)
  - Memory management: Circular buffer with configurable limits
  - Step transitions: Automatic clearing between workflow steps

### Test History
- `test_history.py`: Historical data management
  - Sorting: 6 criteria with drag-drop reordering
  - Multi-selection: Ctrl/Shift support for batch operations
  - Data export: CSV export with directory selection

### Workflow System
- `workflow_editor.py`: Visual workflow creation
  - State preservation: Maintains collapse states
  - Integration: Embeds step nodes and parameter forms

- `step_node.py`: Individual workflow steps
  - Types: Transfer, Transient, Output, Loop
  - Nesting: Loop steps contain child steps
  - Validation: Type-specific parameter validation

- `step_params_form.py`: Dynamic parameter forms
  - Form generation: Based on step type
  - Validation: Range and format checking
  - Signals: Real-time parameter updates

### Utilities
- `utils/decoder.py`: Data decoding functions
  - Hex to bytes conversion
  - End sequence removal
  - Mode-specific parsing
  - Bias current correction

- `custom_widgets.py`: Reusable UI components
  - NoWheel variants prevent accidental scrolling

## State Management

### Per-Device State Structure
```python
# In device_control.py
self.test_info_per_device = {
    "device_id": {
        "name": str,
        "description": str,
        "chip_id": str,
        "device_number": str
    }
}

self.workflow_per_device = {
    "device_id": {
        "steps": [...]
    }
}

self.device_running_status = {
    "device_id": bool
}
```

### UI State Persistence
```python
# Settings saved automatically
QSettings("YourCompany", "OECT测试系统")
- Window geometry
- Splitter positions
- Selected options
```

## Signal-Slot Connections

### Common Patterns
```python
# Emit signal
self.data_updated.emit(data)

# Connect to slot
widget.data_updated.connect(self.on_data_update)

# Disconnect if needed
widget.data_updated.disconnect()

# Block signals temporarily
widget.blockSignals(True)
# ... modify widget
widget.blockSignals(False)
```

### Thread Safety
```python
# Use QTimer for thread-safe updates
QTimer.singleShot(0, lambda: self.update_ui())

# Or use signals from worker threads
self.update_signal.emit(data)  # Thread-safe
```

## Error Handling

### Message Boxes
```python
# Error dialog
QMessageBox.critical(self, "错误", "Error message")

# Warning dialog
QMessageBox.warning(self, "警告", "Warning message")

# Info dialog
QMessageBox.information(self, "信息", "Info message")

# Confirmation dialog
reply = QMessageBox.question(self, "确认", "Are you sure?")
if reply == QMessageBox.Yes:
    # Proceed
```

### Exception Handling
```python
# Global exception hook in main_window.py
def exception_hook(exc_type, exc_value, exc_traceback):
    # Show error dialog
    # Log exception
```

## Styling Guidelines

### Color Scheme
```python
# Dark theme colors
BACKGROUND = "#2b2b2b"
SELECTED = "#0d47a1"
RUNNING = "#1b5e20"
HOVER = "#424242"
TEXT = "white"
```

### Custom Styling
```python
# Inline styles
widget.setStyleSheet("""
    QWidget {
        background-color: #2b2b2b;
        color: white;
    }
    QPushButton:hover {
        background-color: #424242;
    }
""")

# Dynamic styling
style = SELECTED_STYLE if selected else NORMAL_STYLE
widget.setStyleSheet(style)
```

## Performance Considerations

### Update Frequencies
- Real-time data: 10ms (100Hz)
- Plot updates: 50-100ms
- Device list: On change only
- History refresh: Manual trigger

### Memory Management
- Max plot points: 10,000 default
- Clear data between steps
- Use numpy arrays for efficiency
- Implement circular buffers

### UI Responsiveness
- Use QTimer for periodic updates
- Avoid blocking operations in UI thread
- Process data in batches
- Implement lazy loading for large datasets

## Testing Guidelines

### UI Testing
```python
# Test widget creation
def test_widget_creation():
    widget = DeviceControlWidget(mock_backend)
    assert widget.device_list.count() == 0
    
# Test signal emission
def test_signal_emission():
    widget.test_started.connect(callback)
    widget.start_test_button.click()
    assert callback.called
```

### Integration Testing
```python
# Test backend communication
def test_backend_integration():
    backend = Mock()
    widget = DeviceControlWidget(backend)
    widget.start_test()
    backend.start_workflow.assert_called()
```

## Common Issues and Solutions

### Issue: Widget not updating
**Solution**: Check signal connections, ensure timer is running, verify data format

### Issue: Plot performance degradation
**Solution**: Reduce max_points, increase update interval, enable downsampling

### Issue: Device list not refreshing
**Solution**: Call `refresh_device_list()`, check backend connection

### Issue: Workflow not saving
**Solution**: Verify `workflow_per_device` dict, check state preservation logic

### Issue: Memory leak in plots
**Solution**: Clear old data, limit buffer size, ensure proper cleanup

## Debugging Tips

### Enable Debug Output
```python
# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"Data received: {data}")
```

### Qt Object Inspector
```python
# Print widget tree
def print_widget_tree(widget, indent=0):
    print("  " * indent + str(widget))
    for child in widget.findChildren(QWidget):
        print_widget_tree(child, indent + 1)
```

### Signal Debugging
```python
# Monitor signal emissions
from PyQt5.QtCore import pyqtSignal

def log_signal(signal_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"Signal {signal_name} emitted")
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## Code Conventions

1. **Naming**: Use snake_case for methods, CamelCase for classes
2. **Signals**: Name as `action_performed` (past tense)
3. **Slots**: Name as `on_action` or `handle_action`
4. **Private methods**: Prefix with underscore `_method_name`
5. **Constants**: UPPER_CASE for module-level constants

## Security Considerations

- Validate all user inputs before processing
- Sanitize file paths in import/export operations
- Don't store sensitive data in QSettings
- Use proper error messages without exposing internals

## Maintenance Notes

- Regular testing on different screen resolutions
- Monitor memory usage during long tests
- Update PyQt5 and dependencies carefully
- Test with various data rates and device counts
- Maintain backward compatibility with saved workflows