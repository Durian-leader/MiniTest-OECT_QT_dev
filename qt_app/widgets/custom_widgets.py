from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit
from PyQt5.QtCore import Qt

class NoWheelSpinBox(QSpinBox):
    """禁用鼠标滚轮的整数SpinBox"""
    
    def wheelEvent(self, event):
        """覆盖滚轮事件，使其不执行任何操作"""
        event.ignore()

class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """禁用鼠标滚轮的浮点数SpinBox"""
    
    def wheelEvent(self, event):
        """覆盖滚轮事件，使其不执行任何操作"""
        event.ignore()

class NoWheelLineEdit(QLineEdit):
    """禁用鼠标滚轮的LineEdit"""
    
    def wheelEvent(self, event):
        """覆盖滚轮事件，使其不执行任何操作"""
        event.ignore()