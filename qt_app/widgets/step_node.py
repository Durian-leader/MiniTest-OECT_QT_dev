import uuid
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QGroupBox, QLabel, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from qt_app.widgets.step_params_form import StepParamsFormWidget
# 导入自定义下拉框
# from qt_app.widgets.custom_combobox import CustomComboBox  # 假设你将自定义下拉框保存在这个路径
from PyQt5.QtWidgets import QComboBox, QApplication, QListView, QFrame, QAbstractItemView
from PyQt5.QtCore import QPoint, Qt, QEvent, QSize
from PyQt5.QtGui import QPalette

class CustomComboBox(QComboBox):
    """
    自定义ComboBox，修改下拉菜单的弹出位置和显示内容，
    使其不受父控件缩进和样式的影响，同时禁用鼠标滚轮事件
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(120)  # 设置最小宽度确保显示完整
        
        # 创建自定义视图并配置
        self.view = QListView()
        self.view.setTextElideMode(Qt.ElideNone)  # 不省略文本
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 需要时显示水平滚动条
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 需要时显示垂直滚动条
        self.view.setMinimumWidth(200)  # 确保足够宽度
        
        # 重要：设置足够的高度以显示所有项
        self.view.setMinimumHeight(150)  # 确保足够高度显示所有选项
        
        # 设置视图的调色板，避免继承父控件的样式
        palette = QPalette()
        palette.setColor(QPalette.Window, Qt.white)  # 背景色为白色
        palette.setColor(QPalette.Base, Qt.white)  # 项目背景色为白色
        palette.setColor(QPalette.Text, Qt.black)  # 文本颜色为黑色
        palette.setColor(QPalette.Highlight, Qt.lightGray)  # 选中项的背景色
        palette.setColor(QPalette.HighlightedText, Qt.black)  # 选中项的文本颜色
        self.view.setPalette(palette)
        
        # 设置视图的样式表，完全覆盖继承的样式
        self.view.setStyleSheet("""
            QListView {
                border: 1px solid #d9d9d9;
                background-color: white;
                margin: 0px;  /* 重要：去除所有外边距 */
                padding: 5px;
                selection-background-color: #e6f7ff;
                text-align: left;  /* 确保文本左对齐 */
            }
            QListView::item {
                height: 30px;  /* 明确设置每项的高度 */
                padding: 5px;
                margin-left: 0px;  /* 重要：明确设置为0，防止继承缩进 */
                border: none;
            }
        """)
        
        # 设置下拉列表视图
        self.setView(self.view)
        
        # 禁用样式表继承
        self.view.setAttribute(Qt.WA_StyledBackground, True)
        
        # 监视事件，确保不继承父窗口样式，并禁用滚轮事件
        self.installEventFilter(self)
        
        # 设置滚动区域高度策略
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    
    def showPopup(self):
        """重写showPopup方法，修改下拉菜单位置和样式"""
        # 预先计算弹出窗口大小
        itemCount = self.count()
        itemHeight = 30  # 与样式表中设置的项高度一致
        popupHeight = (itemCount * itemHeight) + 10  # 加上一些额外空间用于内边距
        
        # 先调用父类方法创建popup
        super().showPopup()
        
        # 获取popup窗口
        popup = self.findChild(QFrame)
        if popup:
            # 计算新位置 - 使用全局坐标，确保在适当位置显示
            pos = self.mapToGlobal(QPoint(0, self.height()))
            
            # 设置足够的高度以显示所有选项，避免滚动条
            popup.setMinimumHeight(popupHeight)
            
            # 重新应用样式，确保没有继承父控件的样式
            popup.setStyleSheet("""
                QFrame {
                    border: 1px solid #d9d9d9;
                    background-color: white;
                    padding: 0px;
                    margin: 0px;
                }
            """)
            
            # 设置弹出窗口位置
            popup.move(pos.x(), pos.y())
    
    def wheelEvent(self, event):
        """重写wheelEvent方法，禁用鼠标滚轮事件"""
        # 完全忽略滚轮事件，不做任何处理
        event.ignore()
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于进一步控制样式和行为"""
        if event.type() == QEvent.Show and obj == self:
            # 当控件显示时，确保视图样式正确
            if self.view:
                self.view.setStyleSheet(self.view.styleSheet())
        # 确保列表视图也不响应滚轮事件
        elif event.type() == QEvent.Wheel and (obj == self or obj == self.view):
            return True  # 阻止事件传递
        return super().eventFilter(obj, event)
    
    def sizeHint(self):
        """重写sizeHint以提供足够大小的窗口"""
        # 这有助于确保下拉框足够大
        baseSize = super().sizeHint()
        return QSize(max(baseSize.width(), 200), baseSize.height())

class StepNodeWidget(QWidget):
    """
    Widget for editing a single step in the workflow, supporting nested steps for loops
    """
    
    # Signals
    step_updated = pyqtSignal()
    step_removed = pyqtSignal(int)
    
    def __init__(self, step, parent_list, index, parent_widget=None, depth=0):
        super().__init__()
        self.step = step
        self.parent_list = parent_list
        self.index = index
        self.parent_widget = parent_widget
        self.depth = depth  # For nested steps
        self.child_widgets = []  # Store child step widgets
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Step frame with indent based on depth
        step_frame = QFrame()
        step_frame.setFrameShape(QFrame.StyledPanel)
        step_frame.setLineWidth(1)
        step_frame.setStyleSheet(f"""
            QFrame {{
                border-left: {3 if self.depth > 0 else 1}px solid {'#1890ff' if self.depth > 0 else '#d9d9d9'};
                margin-left: {20 * self.depth}px;
                background-color: {'#f6f6f6' if self.depth > 0 else 'white'};
                border-radius: 4px;
            }}
        """)
        
        step_layout = QVBoxLayout(step_frame)
        
        # Header with type selector and buttons
        header_layout = QHBoxLayout()
        
        # Step number label
        num_label = QLabel(f"步骤 {self.index + 1}")
        num_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(num_label)
        
        # Type selector - 使用自定义下拉框替代QComboBox
        self.type_combo = CustomComboBox()
        self.type_combo.addItem("Transfer 特性", "transfer")
        self.type_combo.addItem("Transient 特性", "transient")
        self.type_combo.addItem("Output 特性", "output")  # 新增
        self.type_combo.addItem("循环", "loop")

        # Set current type
        current_type = self.step.get("type", "transfer")
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == current_type:
                self.type_combo.setCurrentIndex(i)
                break
        
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        header_layout.addWidget(self.type_combo)
        
        # Add child button (for loop type)
        self.add_child_btn = QPushButton("添加子步骤")
        self.add_child_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_child_btn.clicked.connect(self.add_child_step)
        self.add_child_btn.setVisible(current_type == "loop")
        header_layout.addWidget(self.add_child_btn)
        
        header_layout.addStretch()
        
        # Remove button
        remove_btn = QPushButton("删除")
        remove_btn.setIcon(QIcon.fromTheme("list-remove"))
        remove_btn.clicked.connect(self.on_remove)
        header_layout.addWidget(remove_btn)
        
        step_layout.addLayout(header_layout)
        
        # Parameters form
        self.params_form = StepParamsFormWidget(self.step)
        self.params_form.params_updated.connect(self.on_params_updated)
        step_layout.addWidget(self.params_form)
        
        # Container for child steps (for loop type)
        self.children_container = QWidget()
        self.children_layout = QVBoxLayout(self.children_container)
        self.children_layout.setContentsMargins(0, 0, 0, 0)
        self.children_layout.setSpacing(10)
        
        step_layout.addWidget(self.children_container)
        self.children_container.setVisible(current_type == "loop" and "steps" in self.step)
        
        # Add to main layout
        main_layout.addWidget(step_frame)
        
        # Refresh child steps if needed
        if current_type == "loop" and "steps" in self.step:
            self.refresh_child_steps()
    
    def on_type_changed(self, index):
        """Handle step type change"""
        new_type = self.type_combo.itemData(index)
        
        # Only update if type actually changed
        if new_type == self.step.get("type"):
            return
        
        # Update step type
        self.step["type"] = new_type
        
        # Reset parameters based on type
        if new_type == "loop":
            # For loop type, add iterations and steps
            self.step["iterations"] = self.step.get("iterations", 1)
            self.step["steps"] = self.step.get("steps", [])
            
            # Remove command_id and params if present
            if "command_id" in self.step:
                del self.step["command_id"]
            if "params" in self.step:
                del self.step["params"]
            
            # Show child steps container and add button
            self.children_container.setVisible(True)
            self.add_child_btn.setVisible(True)
            
            # Refresh child steps
            self.refresh_child_steps()
        else:
            # For transfer/transient/output, add command_id and params
            self.step["command_id"] = 1
            
            if new_type == "transfer":
                self.step["params"] = {
                    "isSweep": 1,
                    "timeStep": 300,
                    "sourceVoltage": 0,
                    "drainVoltage": 100,
                    "gateVoltageStart": -300,
                    "gateVoltageEnd": 400,
                    "gateVoltageStep": 10
                }
            elif new_type == "transient":
                self.step["params"] = {
                    "timeStep": 1,
                    "sourceVoltage": 0,
                    "drainVoltage": 100,
                    "bottomTime": 500,
                    "topTime": 500,
                    "gateVoltageBottom": -300,
                    "gateVoltageTop": 400,
                    "cycles": 5
                }
            elif new_type == "output":  # 新增
                self.step["params"] = {
                    "isSweep": 1,
                    "timeStep": 300,
                    "sourceVoltage": 0,
                    "gateVoltage": 0,
                    "drainVoltageStart": -100,
                    "drainVoltageEnd": 400,
                    "drainVoltageStep": 10
                }
            # Remove iterations and steps if present
            if "iterations" in self.step:
                del self.step["iterations"]
            if "steps" in self.step:
                del self.step["steps"]
            
            # Hide child steps container and add button
            self.children_container.setVisible(False)
            self.add_child_btn.setVisible(False)
        
        # Update params form
        self.params_form.set_step(self.step)
        
        # Emit signal for update
        self.step_updated.emit()
    
    def on_params_updated(self):
        """Handle parameter updates"""
        self.step_updated.emit()
    
    def on_remove(self):
        """Handle step removal"""
        self.step_removed.emit(self.index)
    
    def add_child_step(self):
        """Add a child step to loop"""
        if self.step.get("type") != "loop":
            return
        
        # Ensure steps list exists
        if "steps" not in self.step:
            self.step["steps"] = []
        
        # Create new step
        new_step = {
            "id": str(uuid.uuid4()),
            "type": "transfer",
            "command_id": 1,
            "params": {
                "isSweep": 1,
                "timeStep": 300,
                "sourceVoltage": 0,
                "drainVoltage": 100,
                "gateVoltageStart": -300,
                "gateVoltageEnd": 400,
                "gateVoltageStep": 10
            }
        }
        
        # Add to steps list
        self.step["steps"].append(new_step)
        
        # Refresh UI
        self.refresh_child_steps()
        
        # Emit signal for update
        self.step_updated.emit()
    
    def refresh_child_steps(self):
        """Refresh child step widgets"""
        # Clear existing child widgets
        self.clear_child_widgets()
        
        # Create widgets for child steps
        if self.step.get("type") == "loop" and "steps" in self.step:
            for i, child_step in enumerate(self.step["steps"]):
                child_widget = StepNodeWidget(
                    child_step, 
                    self.step["steps"], 
                    i, 
                    self, 
                    self.depth + 1
                )
                child_widget.step_updated.connect(self.on_params_updated)
                child_widget.step_removed.connect(lambda idx=i: self.remove_child_step(idx))
                
                self.children_layout.addWidget(child_widget)
                self.child_widgets.append(child_widget)
    
    def clear_child_widgets(self):
        """Clear all child widgets"""
        for widget in self.child_widgets:
            widget.setParent(None)
        self.child_widgets = []
    
    def remove_child_step(self, index):
        """Remove a child step"""
        if self.step.get("type") != "loop" or "steps" not in self.step:
            return
        
        if 0 <= index < len(self.step["steps"]):
            # Remove step from list
            del self.step["steps"][index]
            
            # Refresh UI
            self.refresh_child_steps()
            
            # Emit signal for update
            self.step_updated.emit()