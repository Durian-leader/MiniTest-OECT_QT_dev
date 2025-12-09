# MiniTest-OECT UI双语支持实施方案

## 一、技术架构设计

### 1.1 国际化方案选择

**方案：轻量级JSON翻译文件 + 自定义翻译管理器**

**理由：**
- PyQt5原生QTranslator需要.ts/.qm文件，需要Qt Linguist工具链，增加复杂度
- gettext适合大型多语言项目，本项目仅需中英双语
- JSON方案简单直观，易于维护和扩展，无需额外工具

**优势：**
- 零额外依赖（JSON为Python标准库）
- 易于手工编辑和审核翻译
- 支持运行时动态切换
- 符合项目现有技术栈（已使用JSON存储工作流和配置）

### 1.2 文件组织结构

```
MiniTest-OECT_QT_dev/
├── locales/                    # 新增翻译文件目录
│   ├── zh_CN.json             # 简体中文翻译
│   ├── en_US.json             # 英文翻译
│   └── README.md              # 翻译键命名规范说明
├── qt_app/
│   ├── i18n/                  # 新增国际化模块
│   │   ├── __init__.py
│   │   ├── translator.py      # 翻译管理器
│   │   └── loader.py          # 翻译文件加载器
│   ├── main_window.py         # 添加语言切换菜单
│   └── widgets/               # 各组件更新
└── ...
```

### 1.3 翻译键命名规范

**分层命名策略：**
```
{module}.{component}.{element}
```

**示例：**
- `main.window_title` → "MiniTest-OECT 上位机"
- `device_control.refresh_button` → "刷新设备"
- `workflow.test_type.transfer` → "转移特性"
- `dialog.confirm_close.title` → "确认关闭"

**特殊处理：**
- 动态文本（包含变量）：使用Python格式化字符串
- 复数形式：分别定义单数/复数键
- 长文本：使用数组拆分段落

## 二、核心组件设计

### 2.1 翻译管理器 (translator.py)

```python
# qt_app/i18n/translator.py
import json
import os
from typing import Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal

class TranslationManager(QObject):
    """
    轻量级翻译管理器
    - 支持运行时切换语言
    - 支持格式化字符串（含变量）
    - 支持缺失键回退到默认语言
    """
    
    # 信号：语言切换时触发，通知所有组件更新UI
    language_changed = pyqtSignal(str)  # new_locale
    
    _instance = None  # 单例模式
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self._initialized = True
        
        self.current_locale = "zh_CN"  # 默认中文
        self.fallback_locale = "zh_CN"
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.locales_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "locales"
        )
        
        # 加载所有翻译文件
        self._load_translations()
    
    def _load_translations(self):
        """加载所有语言的翻译文件"""
        for locale in ["zh_CN", "en_US"]:
            filepath = os.path.join(self.locales_dir, f"{locale}.json")
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.translations[locale] = json.load(f)
    
    def set_language(self, locale: str) -> bool:
        """切换语言"""
        if locale not in self.translations:
            return False
        
        old_locale = self.current_locale
        self.current_locale = locale
        
        # 持久化用户选择
        from PyQt5.QtCore import QSettings
        settings = QSettings("OECT", "TestApp")
        settings.setValue("language", locale)
        
        # 触发信号
        if old_locale != locale:
            self.language_changed.emit(locale)
        
        return True
    
    def tr(self, key: str, **kwargs) -> str:
        """
        翻译函数
        
        Args:
            key: 翻译键 (例如 "main.window_title")
            **kwargs: 格式化参数 (例如 device="COM3")
        
        Returns:
            翻译后的文本
        """
        # 尝试从当前语言获取
        translation = self._get_nested(
            self.translations.get(self.current_locale, {}), 
            key
        )
        
        # 回退到默认语言
        if translation is None and self.current_locale != self.fallback_locale:
            translation = self._get_nested(
                self.translations.get(self.fallback_locale, {}), 
                key
            )
        
        # 最终回退到键本身
        if translation is None:
            translation = key
        
        # 格式化字符串
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError):
                pass  # 格式化失败，返回原文本
        
        return translation
    
    def _get_nested(self, data: Dict, key: str) -> Optional[str]:
        """获取嵌套键的值"""
        keys = key.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value if isinstance(value, str) else None
    
    def get_available_languages(self) -> Dict[str, str]:
        """获取可用语言列表"""
        return {
            "zh_CN": "简体中文",
            "en_US": "English"
        }

# 全局单例
_translator = TranslationManager()

def tr(key: str, **kwargs) -> str:
    """全局翻译函数快捷方式"""
    return _translator.tr(key, **kwargs)
```

### 2.2 翻译文件结构

**locales/zh_CN.json**（部分示例）：
```json
{
  "main": {
    "window_title": "MiniTest-OECT 上位机",
    "app_header": "OECT 测试上位机",
    "status_ready": "就绪",
    "tab_device_control": "设备控制",
    "tab_test_history": "历史测试查看"
  },
  "device_control": {
    "device_panel": "设备看板",
    "refresh_button": "刷新设备",
    "workflow_config": "工作流配置",
    "auto_naming": "自动生成测试名称",
    "sync_workflow": "所有设备同步执行工作流",
    "sync_workflow_tooltip": "勾选后，所有设备将使用相同的工作流，并且每个步骤同步执行",
    "test_name": "测试名称",
    "test_name_placeholder": "输入测试名称",
    "test_description": "测试描述",
    "test_description_placeholder": "输入测试描述（可选）",
    "chip_id": "芯片ID",
    "chip_id_placeholder": "输入芯片ID（可选）",
    "device_number": "器件编号",
    "device_number_placeholder": "输入器件编号（可选）",
    "start_test": "开始测试",
    "stop_test": "停止测试",
    "export_workflow": "导出工作流",
    "import_workflow": "导入工作流",
    "realtime_monitor": "实时监测",
    "select_device": "请选择一个设备",
    "select_device_and_start": "请选择设备并开始测试",
    "current_device": "当前设备",
    "device_id": "设备 ID",
    "test_id": "测试 ID",
    "test_name_label": "测试名称",
    "port": "端口",
    "description": "描述",
    "unknown_device": "未知设备",
    "testing": "正在测试",
    "auto_generate_name": "（点击开始测试生成）"
  },
  "workflow": {
    "test_type": {
      "transfer": "转移特性",
      "transient": "瞬态特性",
      "output": "输出特性",
      "loop": "循环"
    },
    "params": {
      "is_sweep": "是否扫描",
      "time_step": "时间步长",
      "source_voltage": "源电压",
      "drain_voltage": "漏电压",
      "gate_voltage_start": "栅压起点",
      "gate_voltage_end": "栅压终点",
      "gate_voltage_step": "栅压步长",
      "gate_voltage_list": "栅压列表 (mV)",
      "gate_voltage_list_placeholder": "输入栅压值，用逗号分隔，如: 0,200,400",
      "scan_info": "扫描信息",
      "drain_voltage_start": "漏压起点",
      "drain_voltage_end": "漏压终点",
      "drain_voltage_step": "漏压步长",
      "bottom_time": "底部时间",
      "top_time": "顶部时间",
      "gate_voltage_bottom": "底部栅压",
      "gate_voltage_top": "顶部栅压",
      "cycles": "循环次数",
      "iterations": "循环次数"
    },
    "step_node": {
      "step_number": "步骤 {number}",
      "add_step": "添加步骤",
      "remove_step": "删除",
      "move_up": "上移",
      "move_down": "下移",
      "collapse": "折叠",
      "expand": "展开"
    },
    "editor": {
      "add_step_button": "添加步骤",
      "empty_state": "点击"添加步骤"按钮开始配置工作流"
    }
  },
  "dialog": {
    "confirm_close": {
      "title": "确认关闭",
      "message": "确定要关闭MiniTest-OECT上位机吗？\n所有正在运行的测试将被停止。",
      "yes": "是",
      "no": "否"
    },
    "device_testing": {
      "title": "设备正在测试中",
      "message": "设备 {device} 正在进行测试 (ID: {test_id})\n\n您可以选择:\n• 点击'是'停止当前测试并开启新的测试\n• 点击'否'保持当前测试"
    },
    "warning": {
      "title": "警告",
      "select_device_first": "请先选择一个设备",
      "configure_workflow_first": "请先配置工作流步骤",
      "no_active_test": "该设备没有正在运行的测试",
      "no_workflow_steps": "没有要导出的工作流步骤",
      "invalid_workflow_format": "工作流文件格式无效"
    },
    "error": {
      "title": "错误",
      "get_device_info_failed": "无法获取设备信息",
      "get_device_list_failed": "获取设备列表失败: {error}",
      "start_test_failed": "测试启动失败: {reason}",
      "stop_test_failed": "停止测试失败: {reason}",
      "export_workflow_failed": "导出工作流时发生错误: {error}",
      "import_workflow_failed": "导入工作流时发生错误: {error}"
    },
    "success": {
      "title": "成功",
      "test_stopped": "测试已停止",
      "workflow_exported": "工作流已保存到 {path}",
      "workflow_imported": "工作流已导入并添加到当前工作流后面 (添加了 {count} 个步骤)",
      "sync_tests_stopped": "已停止 {count} 个设备的同步测试"
    },
    "info": {
      "sync_test_started": "已为 {count} 个设备启动同步测试"
    }
  },
  "test_history": {
    "sort": {
      "time": "测试时间",
      "name": "测试名称",
      "device": "测试设备",
      "chip_id": "芯片ID",
      "device_number": "器件编号",
      "description": "测试描述",
      "drag_help": "拖拽调整排序优先级，点击切换升/降序"
    },
    "toolbar": {
      "delete_selected": "删除所选测试",
      "export_data": "导出数据"
    },
    "buttons": {
      "load_selected": "加载选中测试",
      "export_csv": "导出CSV"
    }
  },
  "realtime_plot": {
    "memory_protection": "内存保护",
    "memory_protection_tooltip": "实时图表中只保留最新的{max_points}个数据点，防止内存溢出",
    "step_separation": "步骤间分离",
    "step_separation_tooltip": "不同步骤的数据将在独立图表中显示",
    "time_window": "时间窗口",
    "time_window_tooltip": "启用10秒滚动时间窗口",
    "show_data_points": "显示数据点",
    "clear_plot": "清除图表",
    "waiting_data": "等待数据..."
  }
}
```

**locales/en_US.json**（部分示例）：
```json
{
  "main": {
    "window_title": "MiniTest-OECT Host PC",
    "app_header": "OECT Test Host PC",
    "status_ready": "Ready",
    "tab_device_control": "Device Control",
    "tab_test_history": "Test History"
  },
  "device_control": {
    "device_panel": "Device Dashboard",
    "refresh_button": "Refresh Devices",
    "workflow_config": "Workflow Configuration",
    "auto_naming": "Auto-generate Test Name",
    "sync_workflow": "Sync Workflow Execution for All Devices",
    "sync_workflow_tooltip": "When checked, all devices will use the same workflow and execute each step synchronously",
    "test_name": "Test Name",
    "test_name_placeholder": "Enter test name",
    "test_description": "Description",
    "test_description_placeholder": "Enter description (optional)",
    "chip_id": "Chip ID",
    "chip_id_placeholder": "Enter chip ID (optional)",
    "device_number": "Device Number",
    "device_number_placeholder": "Enter device number (optional)",
    "start_test": "Start Test",
    "stop_test": "Stop Test",
    "export_workflow": "Export Workflow",
    "import_workflow": "Import Workflow",
    "realtime_monitor": "Real-time Monitor",
    "select_device": "Please select a device",
    "select_device_and_start": "Please select a device and start testing",
    "current_device": "Current Device",
    "device_id": "Device ID",
    "test_id": "Test ID",
    "test_name_label": "Test Name",
    "port": "Port",
    "description": "Description",
    "unknown_device": "Unknown Device",
    "testing": "Testing",
    "auto_generate_name": "(Click Start Test to generate)"
  },
  "workflow": {
    "test_type": {
      "transfer": "Transfer",
      "transient": "Transient",
      "output": "Output",
      "loop": "Loop"
    },
    "params": {
      "is_sweep": "Sweep",
      "time_step": "Time Step",
      "source_voltage": "Source Voltage",
      "drain_voltage": "Drain Voltage",
      "gate_voltage_start": "Gate Voltage Start",
      "gate_voltage_end": "Gate Voltage End",
      "gate_voltage_step": "Gate Voltage Step",
      "gate_voltage_list": "Gate Voltage List (mV)",
      "gate_voltage_list_placeholder": "Enter gate voltages separated by commas, e.g.: 0,200,400",
      "scan_info": "Scan Info",
      "drain_voltage_start": "Drain Voltage Start",
      "drain_voltage_end": "Drain Voltage End",
      "drain_voltage_step": "Drain Voltage Step",
      "bottom_time": "Bottom Time",
      "top_time": "Top Time",
      "gate_voltage_bottom": "Gate Voltage Bottom",
      "gate_voltage_top": "Gate Voltage Top",
      "cycles": "Cycles",
      "iterations": "Iterations"
    },
    "step_node": {
      "step_number": "Step {number}",
      "add_step": "Add Step",
      "remove_step": "Remove",
      "move_up": "Move Up",
      "move_down": "Move Down",
      "collapse": "Collapse",
      "expand": "Expand"
    },
    "editor": {
      "add_step_button": "Add Step",
      "empty_state": "Click 'Add Step' button to start configuring workflow"
    }
  },
  "dialog": {
    "confirm_close": {
      "title": "Confirm Close",
      "message": "Are you sure you want to close MiniTest-OECT?\nAll running tests will be stopped.",
      "yes": "Yes",
      "no": "No"
    },
    "device_testing": {
      "title": "Device is Testing",
      "message": "Device {device} is running test (ID: {test_id})\n\nYou can:\n• Click 'Yes' to stop current test and start a new one\n• Click 'No' to keep current test"
    },
    "warning": {
      "title": "Warning",
      "select_device_first": "Please select a device first",
      "configure_workflow_first": "Please configure workflow steps first",
      "no_active_test": "This device has no running test",
      "no_workflow_steps": "No workflow steps to export",
      "invalid_workflow_format": "Invalid workflow file format"
    },
    "error": {
      "title": "Error",
      "get_device_info_failed": "Failed to get device information",
      "get_device_list_failed": "Failed to get device list: {error}",
      "start_test_failed": "Test start failed: {reason}",
      "stop_test_failed": "Stop test failed: {reason}",
      "export_workflow_failed": "Error exporting workflow: {error}",
      "import_workflow_failed": "Error importing workflow: {error}"
    },
    "success": {
      "title": "Success",
      "test_stopped": "Test stopped",
      "workflow_exported": "Workflow saved to {path}",
      "workflow_imported": "Workflow imported and appended (added {count} steps)",
      "sync_tests_stopped": "Stopped {count} synchronized tests"
    },
    "info": {
      "sync_test_started": "Started synchronized tests for {count} devices"
    }
  },
  "test_history": {
    "sort": {
      "time": "Test Time",
      "name": "Test Name",
      "device": "Device",
      "chip_id": "Chip ID",
      "device_number": "Device Number",
      "description": "Description",
      "drag_help": "Drag to adjust sort priority, click to toggle ascending/descending"
    },
    "toolbar": {
      "delete_selected": "Delete Selected",
      "export_data": "Export Data"
    },
    "buttons": {
      "load_selected": "Load Selected",
      "export_csv": "Export CSV"
    }
  },
  "realtime_plot": {
    "memory_protection": "Memory Protection",
    "memory_protection_tooltip": "Keep only the latest {max_points} data points to prevent memory overflow",
    "step_separation": "Step Separation",
    "step_separation_tooltip": "Data from different steps will be displayed in separate plots",
    "time_window": "Time Window",
    "time_window_tooltip": "Enable 10-second rolling time window",
    "show_data_points": "Show Data Points",
    "clear_plot": "Clear Plot",
    "waiting_data": "Waiting for data..."
  }
}
```

### 2.3 语言切换UI组件

**在主窗口添加语言菜单：**

```python
# qt_app/main_window.py 修改片段
from PyQt5.QtWidgets import QMenuBar, QMenu, QAction, QActionGroup

class MainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        # ... 现有代码 ...
        self.setup_menu_bar()  # 新增
        
    def setup_menu_bar(self):
        """设置菜单栏"""
        from qt_app.i18n.translator import _translator
        
        menubar = self.menuBar()
        
        # 语言菜单
        language_menu = menubar.addMenu(_translator.tr("menu.language"))
        
        # 语言选项组（单选）
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        
        for locale, display_name in _translator.get_available_languages().items():
            action = QAction(display_name, self, checkable=True)
            action.setData(locale)
            
            if locale == _translator.current_locale:
                action.setChecked(True)
            
            action.triggered.connect(lambda checked, l=locale: self.change_language(l))
            language_group.addAction(action)
            language_menu.addAction(action)
        
        # 连接语言切换信号
        _translator.language_changed.connect(self.on_language_changed)
    
    def change_language(self, locale: str):
        """切换语言"""
        from qt_app.i18n.translator import _translator
        _translator.set_language(locale)
    
    def on_language_changed(self, locale: str):
        """语言切换后更新UI"""
        from qt_app.i18n.translator import tr
        
        # 更新窗口标题
        self.setWindowTitle(tr("main.window_title"))
        
        # 更新头部
        # 需要保存对header控件的引用
        if hasattr(self, 'header'):
            self.header.setText(tr("main.app_header"))
        
        # 更新标签页标题
        self.tab_widget.setTabText(0, tr("main.tab_device_control"))
        self.tab_widget.setTabText(1, tr("main.tab_test_history"))
        
        # 更新状态栏
        self.status_bar.showMessage(tr("main.status_ready"))
        
        # 通知子组件更新
        self.device_control.update_translations()
        self.test_history.update_translations()
```

## 三、组件改造策略

### 3.1 最小化代码侵入性原则

**策略1：添加翻译更新方法**
- 每个自定义Widget添加`update_translations()`方法
- 在语言切换时调用，重新设置所有文本

**策略2：集中化文本管理**
- 在`setup_ui()`中集中调用`tr()`函数
- 避免硬编码字符串散落各处

**策略3：向后兼容**
- 翻译文件缺失时优雅降级到中文
- 不影响现有功能

### 3.2 代码改造模式

**模式1：简单文本替换**
```python
# 改造前
header = QLabel("设备看板")

# 改造后
from qt_app.i18n.translator import tr
header = QLabel(tr("device_control.device_panel"))
```

**模式2：动态文本（含变量）**
```python
# 改造前
info_text = f"当前设备: {device['description']}"

# 改造后
info_text = tr("device_control.current_device") + f": {device['description']}"
# 或更好的方式：
info_text = tr("device_control.current_device_info", 
               description=device['description'])
# 翻译文件中：
# "current_device_info": "当前设备: {description}"
```

**模式3：组件更新方法**
```python
class DeviceControlWidget(QWidget):
    def setup_ui(self):
        from qt_app.i18n.translator import tr
        
        # 使用tr()函数
        self.refresh_btn = QPushButton(tr("device_control.refresh_button"))
        # ...
    
    def update_translations(self):
        """语言切换时更新所有文本"""
        from qt_app.i18n.translator import tr
        
        # 更新按钮文本
        self.refresh_btn.setText(tr("device_control.refresh_button"))
        self.start_btn.setText(tr("device_control.start_test"))
        self.stop_btn.setText(tr("device_control.stop_test"))
        
        # 更新标签
        self.device_header.setText(tr("device_control.device_panel"))
        
        # 更新占位符
        self.test_name_edit.setPlaceholderText(
            tr("device_control.test_name_placeholder")
        )
        
        # 更新复选框
        self.auto_naming_check.setText(tr("device_control.auto_naming"))
        
        # ... 所有UI文本
```

### 3.3 特殊组件处理

**下拉框（QComboBox）：**
```python
# 测试类型下拉框
def setup_type_combo(self):
    from qt_app.i18n.translator import tr
    
    self.type_combo.clear()
    self.type_combo.addItem(
        tr("workflow.test_type.transfer"), 
        "transfer"
    )
    self.type_combo.addItem(
        tr("workflow.test_type.transient"), 
        "transient"
    )
    # ...

def update_translations(self):
    # 保存当前选择的值
    current_data = self.type_combo.currentData()
    
    # 重新填充
    self.setup_type_combo()
    
    # 恢复选择
    index = self.type_combo.findData(current_data)
    if index >= 0:
        self.type_combo.setCurrentIndex(index)
```

**对话框：**
```python
# QMessageBox
from qt_app.i18n.translator import tr

reply = QMessageBox.warning(
    self,
    tr("dialog.confirm_close.title"),
    tr("dialog.confirm_close.message"),
    QMessageBox.Yes | QMessageBox.No,
    QMessageBox.No
)
```

## 四、实施步骤

### 阶段1：基础设施搭建（优先级：高）

**文件：**
1. `locales/zh_CN.json` - 提取所有中文字符串
2. `locales/en_US.json` - 对应英文翻译
3. `qt_app/i18n/translator.py` - 翻译管理器
4. `qt_app/i18n/__init__.py` - 导出tr函数

**任务：**
- [ ] 创建翻译管理器
- [ ] 提取main_window.py中的所有中文字符串到zh_CN.json
- [ ] 翻译为英文到en_US.json
- [ ] 测试翻译管理器基本功能

### 阶段2：主窗口和菜单（优先级：高）

**文件：**
- `qt_app/main_window.py`

**任务：**
- [ ] 添加语言菜单到菜单栏
- [ ] 实现语言切换逻辑
- [ ] 添加语言选择持久化（QSettings）
- [ ] 更新窗口标题、标签页、状态栏文本
- [ ] 添加`update_translations()`方法

### 阶段3：设备控制组件（优先级：高）

**文件：**
- `qt_app/widgets/device_control.py`

**任务：**
- [ ] 提取所有中文字符串（按钮、标签、占位符、对话框）
- [ ] 替换为tr()调用
- [ ] 实现`update_translations()`方法
- [ ] 特别处理：
  - 设备列表自定义渲染（DeviceItemDelegate）
  - 动态状态信息
  - 测试信息表单

### 阶段4：工作流编辑器（优先级：高）

**文件：**
- `qt_app/widgets/workflow_editor.py`
- `qt_app/widgets/step_node.py`
- `qt_app/widgets/step_params_form.py`

**任务：**
- [ ] 工作流编辑器：按钮、空状态提示
- [ ] 步骤节点：步骤编号、按钮、测试类型下拉框
- [ ] 参数表单：所有参数标签、单位、帮助文本
- [ ] 测试类型映射表（transfer/transient/output/loop）

### 阶段5：实时绘图和历史查看（优先级：中）

**文件：**
- `qt_app/widgets/realtime_plot.py`
- `qt_app/widgets/test_history.py`

**任务：**
- [ ] 实时绘图：复选框、按钮、状态标签
- [ ] 历史查看：排序标签、工具栏按钮、对话框

### 阶段6：对话框和消息（优先级：中）

**任务：**
- [ ] 统一所有QMessageBox调用使用tr()
- [ ] 确认对话框
- [ ] 警告对话框
- [ ] 错误提示
- [ ] 成功通知

### 阶段7：测试和优化（优先级：中）

**任务：**
- [ ] 完整测试所有UI界面
- [ ] 测试语言切换流程
- [ ] 测试缺失翻译时的回退机制
- [ ] 性能测试（语言切换响应时间）
- [ ] 检查文本截断和布局问题

### 阶段8：文档和维护（优先级：低）

**任务：**
- [ ] 更新CLAUDE.md添加国际化指南
- [ ] 创建locales/README.md说明翻译键规范
- [ ] 添加贡献翻译的指南
- [ ] 记录已知问题和限制

## 五、关键技术决策

### 5.1 不使用PyQt5原生QTranslator的原因

1. **复杂度**：需要Qt Linguist工具链，.ts/.qm文件编译流程
2. **灵活性**：JSON更易于编辑和版本控制
3. **项目规模**：仅需中英双语，轻量方案更合适
4. **维护性**：开发者可直接编辑JSON，无需额外工具

### 5.2 运行时切换 vs 重启应用

**选择：运行时动态切换**

**原因：**
- 用户体验更好，无需重启
- 技术可行（通过信号槽机制通知所有组件）
- 测试数据不受影响（仅UI文本改变）

**实现：**
- TranslationManager发出`language_changed`信号
- 所有组件连接信号并实现`update_translations()`方法
- 动态更新所有可见文本

### 5.3 翻译文件加载时机

**选择：应用启动时加载所有语言**

**原因：**
- 翻译文件小（估计每个文件<100KB）
- 避免切换语言时的延迟
- 简化错误处理

### 5.4 缺失翻译处理

**策略：**
1. 优先使用当前语言翻译
2. 回退到默认语言（中文）
3. 最终回退到键名本身（便于调试）

## 六、代码示例

### 示例1：main_window.py完整改造

```python
# qt_app/main_window.py
import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, 
                           QVBoxLayout, QWidget, QLabel, 
                           QStatusBar, QMessageBox, QMenuBar, QMenu, 
                           QAction, QActionGroup)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QFont

from qt_app.widgets.device_control import DeviceControlWidget
from qt_app.widgets.test_history import TestHistoryWidget
from backend_device_control_pyqt.main import MedicalTestBackend
from qt_app.i18n.translator import tr, _translator

from logger_config import get_module_logger
logger = get_module_logger() 

class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.prev_tab_index = 0
        
        # Load saved language preference
        settings = QSettings("OECT", "TestApp")
        saved_locale = settings.value("language", "zh_CN")
        _translator.set_language(saved_locale)
        
        # Setup UI
        self.setup_ui()
        self.setup_menu_bar()
        
        # Restore geometry
        self.restore_geometry()
        
        # Connect translation updates
        _translator.language_changed.connect(self.update_translations)
        
    def setup_ui(self):
        """Setup the user interface"""
        # Set window properties
        self.setWindowTitle(tr("main.window_title"))
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowIcon(QIcon("my_icon.ico"))
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create header
        self.header = QLabel(tr("main.app_header"))
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("background-color: #f1f1f1; padding: 10px;")
        self.header.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(self.header)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.device_control = DeviceControlWidget(self.backend)
        self.test_history = TestHistoryWidget(self.backend)
        
        self.tab_widget.addTab(self.device_control, tr("main.tab_device_control"))
        self.tab_widget.addTab(self.test_history, tr("main.tab_test_history"))
        
        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("main.status_ready"))
    
    def setup_menu_bar(self):
        """Setup menu bar with language selection"""
        menubar = self.menuBar()
        
        # Language menu
        self.language_menu = menubar.addMenu(tr("menu.language"))
        
        # Language action group
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        
        for locale, display_name in _translator.get_available_languages().items():
            action = QAction(display_name, self, checkable=True)
            action.setData(locale)
            
            if locale == _translator.current_locale:
                action.setChecked(True)
            
            action.triggered.connect(
                lambda checked, l=locale: self.change_language(l)
            )
            language_group.addAction(action)
            self.language_menu.addAction(action)
    
    def change_language(self, locale: str):
        """Change application language"""
        _translator.set_language(locale)
    
    def update_translations(self):
        """Update all UI texts when language changes"""
        # Update window title
        self.setWindowTitle(tr("main.window_title"))
        
        # Update header
        self.header.setText(tr("main.app_header"))
        
        # Update tab titles
        self.tab_widget.setTabText(0, tr("main.tab_device_control"))
        self.tab_widget.setTabText(1, tr("main.tab_test_history"))
        
        # Update status bar
        self.status_bar.showMessage(tr("main.status_ready"))
        
        # Update menu
        self.language_menu.setTitle(tr("menu.language"))
        
        # Notify child widgets
        self.device_control.update_translations()
        self.test_history.update_translations()
    
    def on_tab_changed(self, index):
        """Handle tab change events"""
        if self.prev_tab_index == 0:
            self.device_control.prepare_for_tab_change()
        
        if index == 0:
            if self.prev_tab_index != 0:
                self.device_control.restore_after_tab_change()
        elif index == 1:
            self.test_history.refresh_devices()
        
        self.prev_tab_index = index
    
    def restore_geometry(self):
        """Restore window geometry from settings"""
        settings = QSettings("OECT", "TestApp")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
    
    def save_geometry(self):
        """Save window geometry to settings"""
        settings = QSettings("OECT", "TestApp")
        settings.setValue("geometry", self.saveGeometry())
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.warning(
            self,
            tr("dialog.confirm_close.title"),
            tr("dialog.confirm_close.message"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.save_geometry()
            self.backend.shutdown()
            event.accept()
        else:
            event.ignore()
```

### 示例2：DeviceControlWidget部分改造

```python
# qt_app/widgets/device_control.py (部分代码)
from qt_app.i18n.translator import tr

class DeviceControlWidget(QWidget):
    def setup_ui(self):
        """Setup the user interface"""
        # ... layout setup ...
        
        # Device panel
        device_header = QLabel(tr("device_control.device_panel"))
        device_header.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(device_header)
        
        # Device list
        self.device_list = QListWidget()
        # ...
        left_layout.addWidget(self.device_list)
        
        # Refresh button
        self.refresh_btn = QPushButton(tr("device_control.refresh_button"))
        self.refresh_btn.clicked.connect(self.refresh_devices)
        left_layout.addWidget(self.refresh_btn)
        
        # Workflow config group
        workflow_header = QGroupBox(tr("device_control.workflow_config"))
        # ...
        
        # Auto-naming checkbox
        self.auto_naming_check = QCheckBox(tr("device_control.auto_naming"))
        self.auto_naming_check.setChecked(self.auto_naming)
        self.auto_naming_check.toggled.connect(self.toggle_auto_naming)
        form_layout.addRow("", self.auto_naming_check)
        
        # Sync workflow checkbox
        self.sync_workflow_check = QCheckBox(tr("device_control.sync_workflow"))
        self.sync_workflow_check.setChecked(False)
        self.sync_workflow_check.toggled.connect(self.toggle_sync_workflow)
        self.sync_workflow_check.setToolTip(tr("device_control.sync_workflow_tooltip"))
        form_layout.addRow("", self.sync_workflow_check)
        
        # Test name field
        self.test_name_edit = QLineEdit()
        self.test_name_edit.setPlaceholderText(tr("device_control.test_name_placeholder"))
        form_layout.addRow(tr("device_control.test_name") + ":", self.test_name_edit)
        
        # Buttons
        self.start_btn = QPushButton(tr("device_control.start_test"))
        self.start_btn.clicked.connect(self.start_workflow)
        
        self.stop_btn = QPushButton(tr("device_control.stop_test"))
        self.stop_btn.clicked.connect(self.stop_workflow)
        
        # ... more UI setup ...
    
    def update_translations(self):
        """Update all UI texts when language changes"""
        # Update labels and buttons
        # 需要在setup_ui中保存对所有控件的引用
        if hasattr(self, 'device_header'):
            self.device_header.setText(tr("device_control.device_panel"))
        
        self.refresh_btn.setText(tr("device_control.refresh_button"))
        self.start_btn.setText(tr("device_control.start_test"))
        self.stop_btn.setText(tr("device_control.stop_test"))
        self.export_btn.setText(tr("device_control.export_workflow"))
        self.import_btn.setText(tr("device_control.import_workflow"))
        
        # Update checkboxes
        self.auto_naming_check.setText(tr("device_control.auto_naming"))
        self.sync_workflow_check.setText(tr("device_control.sync_workflow"))
        self.sync_workflow_check.setToolTip(tr("device_control.sync_workflow_tooltip"))
        
        # Update form labels and placeholders
        self.test_name_edit.setPlaceholderText(tr("device_control.test_name_placeholder"))
        self.test_desc_edit.setPlaceholderText(tr("device_control.test_description_placeholder"))
        self.chip_id_edit.setPlaceholderText(tr("device_control.chip_id_placeholder"))
        self.device_number_edit.setPlaceholderText(tr("device_control.device_number_placeholder"))
        
        # Update plot header
        if hasattr(self, 'plot_header'):
            self.plot_header.setText(tr("device_control.realtime_monitor"))
        
        # Update device info if selected
        if self.selected_port:
            self.on_device_selected(
                self.device_list.currentItem(),
                None
            )
        
        # Notify child widgets
        self.workflow_editor.update_translations()
        for plot_widget in self.plot_widgets.values():
            plot_widget.update_translations()
```

## 七、性能和限制考虑

### 7.1 性能指标目标

- **翻译文件加载时间**: < 50ms
- **语言切换响应时间**: < 200ms
- **内存占用增加**: < 1MB（两个JSON文件）

### 7.2 已知限制

1. **动态生成的文本**：部分测试数据中的文本不翻译（如设备ID、文件路径）
2. **PyQtGraph图表**：坐标轴标签需要特殊处理
3. **日志消息**：保持英文或中文，不纳入翻译范围
4. **数据文件**：CSV和JSON数据文件不翻译

### 7.3 布局兼容性

**挑战：**
- 英文文本通常比中文长
- 可能导致按钮和标签被截断

**解决方案：**
1. 使用QLabel的自动换行：`setWordWrap(True)`
2. 使用布局管理器的弹性策略
3. 必要时调整最小宽度
4. 测试关键界面在两种语言下的显示效果

## 八、测试策略

### 8.1 单元测试

```python
# tests/test_translator.py
import pytest
from qt_app.i18n.translator import TranslationManager

def test_translation_basic():
    tm = TranslationManager()
    tm.set_language("zh_CN")
    assert tm.tr("main.window_title") == "MiniTest-OECT 上位机"
    
    tm.set_language("en_US")
    assert tm.tr("main.window_title") == "MiniTest-OECT Host PC"

def test_translation_with_params():
    tm = TranslationManager()
    tm.set_language("zh_CN")
    result = tm.tr("device_control.current_device_info", 
                   description="Test Device")
    assert "Test Device" in result

def test_missing_key_fallback():
    tm = TranslationManager()
    assert tm.tr("nonexistent.key") == "nonexistent.key"
```

### 8.2 集成测试清单

- [ ] 启动应用，默认语言为中文
- [ ] 切换到英文，所有UI文本更新
- [ ] 切换回中文，所有UI文本恢复
- [ ] 重启应用，语言选择被保存
- [ ] 测试所有对话框
- [ ] 测试所有表单输入
- [ ] 测试工作流编辑器
- [ ] 测试实时绘图界面
- [ ] 测试历史查看界面
- [ ] 检查文本截断和布局问题

## 九、维护指南

### 9.1 添加新翻译键

1. 在`locales/zh_CN.json`中添加中文文本
2. 在`locales/en_US.json`中添加对应英文翻译
3. 在代码中使用`tr("category.key")`调用
4. 更新对应组件的`update_translations()`方法

### 9.2 翻译键命名最佳实践

- 使用小写和下划线
- 采用模块化分类
- 描述性而非通用（避免`button1`，使用`refresh_button`）
- 一致的层级结构

### 9.3 向后兼容性

- 翻译文件缺失时，应用仍能正常运行
- 新增翻译键不影响旧版本
- 语言设置错误时，回退到默认中文

## 十、交付清单

### 核心文件
- [ ] `locales/zh_CN.json` - 中文翻译文件
- [ ] `locales/en_US.json` - 英文翻译文件
- [ ] `locales/README.md` - 翻译维护指南
- [ ] `qt_app/i18n/__init__.py`
- [ ] `qt_app/i18n/translator.py` - 翻译管理器
- [ ] `qt_app/i18n/loader.py` - 翻译加载器（可选）

### 更新的组件
- [ ] `qt_app/main_window.py`
- [ ] `qt_app/widgets/device_control.py`
- [ ] `qt_app/widgets/workflow_editor.py`
- [ ] `qt_app/widgets/step_node.py`
- [ ] `qt_app/widgets/step_params_form.py`
- [ ] `qt_app/widgets/realtime_plot.py`
- [ ] `qt_app/widgets/test_history.py`

### 文档
- [ ] 更新`CLAUDE.md`添加国际化指南
- [ ] 更新`qt_app/CLAUDE.md`
- [ ] 创建`locales/README.md`
PLAN_EOF
echo "Plan created successfully"