import uuid
import json
import copy
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                           QPushButton, QLabel, QFrame, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from qt_app.widgets.step_node import StepNodeWidget
from qt_app.i18n.translator import tr

class WorkflowEditorWidget(QWidget):
    """
    Widget for editing workflow steps with support for nested loops
    """
    
    # Signal when workflow is updated
    workflow_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.steps = []
        self.collapse_states = {}  # Store collapse states by step id
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        
        # Top controls
        controls_layout = QHBoxLayout()

        self.add_btn = QPushButton(tr("workflow.add_step_button"))
        self.add_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_btn.clicked.connect(self.add_step)
        controls_layout.addWidget(self.add_btn)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Scroll area for steps
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(10)
        self.steps_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(self.steps_container)
        main_layout.addWidget(scroll_area)

        # Empty state
        self.empty_label = QLabel(tr("workflow.empty_state_message"))
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 20px;")
        self.steps_layout.addWidget(self.empty_label)
    
    def add_step(self):
        """Add a new step to the workflow"""
        # Create default step
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
        self.steps.append(new_step)
        
        # Update UI
        self.refresh_steps()
        self.workflow_updated.emit()
    
    def save_collapse_states(self):
        """Save current collapse states of all step widgets"""
        for i in range(self.steps_layout.count()):
            item = self.steps_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget and hasattr(widget, 'step') and hasattr(widget, 'is_collapsed'):
                step_id = widget.step.get('id')
                if step_id:
                    self.collapse_states[step_id] = widget.is_collapsed
                    # Also save child states for loop steps
                    if hasattr(widget, 'child_widgets'):
                        for child_widget in widget.child_widgets:
                            if hasattr(child_widget, 'step') and hasattr(child_widget, 'is_collapsed'):
                                child_step_id = child_widget.step.get('id')
                                if child_step_id:
                                    self.collapse_states[child_step_id] = child_widget.is_collapsed
    
    def restore_collapse_states(self):
        """Restore collapse states to step widgets"""
        for i in range(self.steps_layout.count()):
            item = self.steps_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget and hasattr(widget, 'step') and hasattr(widget, 'is_collapsed'):
                step_id = widget.step.get('id')
                if step_id and step_id in self.collapse_states:
                    if self.collapse_states[step_id]:
                        widget.toggle_collapse()
                    # Also restore child states for loop steps
                    if hasattr(widget, 'child_widgets'):
                        for child_widget in widget.child_widgets:
                            if hasattr(child_widget, 'step') and hasattr(child_widget, 'is_collapsed'):
                                child_step_id = child_widget.step.get('id')
                                if child_step_id and child_step_id in self.collapse_states:
                                    if self.collapse_states[child_step_id]:
                                        child_widget.toggle_collapse()
    
    def refresh_steps(self):
        """Refresh the step editor UI"""
        # Save current collapse states
        self.save_collapse_states()
        
        # Hide empty label if there are steps
        self.empty_label.setVisible(len(self.steps) == 0)
        
        # Clear all existing step widgets
        self.clear_step_widgets()
        
        # Create widgets for steps
        for i, step in enumerate(self.steps):
            step_widget = StepNodeWidget(step, self.steps, i, parent_widget=self)
            step_widget.step_updated.connect(self.on_step_updated)
            step_widget.step_removed.connect(lambda idx=i: self.remove_step(idx))
            step_widget.step_move_requested.connect(self.move_step)
            self.steps_layout.addWidget(step_widget)
        
        # Restore collapse states
        self.restore_collapse_states()
    
    def clear_step_widgets(self):
        """Clear all step widgets from the layout"""
        # Remove all widgets except for the empty label
        for i in reversed(range(self.steps_layout.count())):
            item = self.steps_layout.itemAt(i)
            widget = item.widget()
            if widget and widget != self.empty_label:
                widget.setParent(None)
    
    def on_step_updated(self):
        """Handle step updates"""
        self.workflow_updated.emit()
    
    def remove_step(self, index):
        """Remove a step at the given index"""
        if 0 <= index < len(self.steps):
            del self.steps[index]
            self.refresh_steps()
            self.workflow_updated.emit()
    
    def move_step(self, from_index, to_index):
        """Move a step from one position to another"""
        if (0 <= from_index < len(self.steps) and 
            0 <= to_index < len(self.steps) and 
            from_index != to_index):
            
            # Remove step from original position
            step = self.steps.pop(from_index)
            
            # Adjust target index if necessary
            if from_index < to_index:
                to_index -= 1
            
            # Insert at new position
            self.steps.insert(to_index, step)
            
            # Refresh UI
            self.refresh_steps()
            self.workflow_updated.emit()
    
    def clear(self):
        """Clear all steps"""
        self.steps = []
        self.refresh_steps()
    
    def set_steps(self, steps):
        """Set the workflow steps"""
        self.steps = copy.deepcopy(steps) if steps else []
        self.refresh_steps()
    
    def get_steps(self):
        """Get the current workflow steps"""
        return copy.deepcopy(self.steps)

    def update_translations(self):
        """Update all UI text when language changes"""
        self.add_btn.setText(tr("workflow.add_step_button"))
        self.empty_label.setText(tr("workflow.empty_state_message"))

        # Update all step nodes
        for i in range(self.steps_layout.count()):
            widget = self.steps_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'update_translations'):
                widget.update_translations()
