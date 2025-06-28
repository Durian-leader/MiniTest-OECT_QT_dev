import os
import json
import csv
import shutil  # Added for file/directory operations
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                           QLabel, QPushButton, QListWidget, QListWidgetItem,
                           QTreeWidget, QTreeWidgetItem, QFrame, QGroupBox,
                           QTabWidget, QSizePolicy, QHeaderView, 
                           QFormLayout, QMessageBox, QStyledItemDelegate, QStyle,
                           QFileDialog, QToolBar, QAction, QAbstractItemView)  # Added QAbstractItemView
from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import QIcon, QColor, QFont, QPalette, QBrush

import pyqtgraph as pg
########################### 日志设置 ###################################
from logger_config import get_module_logger
logger = get_module_logger() 
#####################################################################
class CustomTestItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering test list items with more information"""
    
    def sizeHint(self, option, index):
        """Return the size needed to display the item"""
        return QSize(option.rect.width(), 70)  # Altura aumentada para mostrar más información
        
    def paint(self, painter, option, index):
        """Custom painting for test items"""
        # Obtener los datos del test
        test = index.data(Qt.UserRole)
        if not test:
            super().paint(painter, option, index)
            return
            
        # Preparar el rectángulo de dibujo
        rect = option.rect
        
        # Verificar si el elemento está seleccionado - Corregido el uso de QStyle.State_Selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
            sec_color = QColor(text_color)
            sec_color.setAlpha(180)
        else:
            painter.fillRect(rect, option.palette.base())
            text_color = option.palette.text().color()
            sec_color = QColor(150, 150, 150)
            
        # Dibujar el nombre con fuente grande en negrita
        painter.setPen(text_color)
        name_font = QFont(option.font)
        name_font.setPointSize(name_font.pointSize() + 1)
        name_font.setBold(True)
        painter.setFont(name_font)
        
        test_name = test.get("name", "Sin nombre")
        name_rect = QRect(rect.left() + 10, rect.top() + 5, rect.width() - 20, 20)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, test_name)
        
        # Dibujar la descripción con fuente normal
        desc_font = QFont(option.font)
        painter.setFont(desc_font)
        painter.setPen(sec_color)
        
        # Obtener descripción - Primera prueba con campos que podrían contener la descripción
        desc = ""
        if "description" in test:
            desc = test["description"]
        elif "desc" in test:
            desc = test["desc"]
        
        # Si no hay descripción, intentar obtenerla de test_info si existe
        if not desc and "test_info" in test:
            test_info = test.get("test_info", {})
            if isinstance(test_info, dict):
                desc = test_info.get("description", "")
        
        if len(desc) > 60:  # Truncar descripciones largas
            desc = desc[:57] + "..."
            
        desc_rect = QRect(rect.left() + 10, rect.top() + 25, rect.width() - 20, 20)
        painter.drawText(desc_rect, Qt.AlignLeft | Qt.AlignVCenter, desc)
        
        # Dibujar la fecha en la parte inferior derecha
        date_font = QFont(option.font)
        date_font.setPointSize(date_font.pointSize() - 1)
        painter.setFont(date_font)
        
        created_at = test.get("created_at", "")
        timestamp = ""
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
                timestamp = dt.strftime("%Y-%m-%d %H:%M")
            except:
                timestamp = created_at
                
        date_rect = QRect(rect.left() + 10, rect.top() + 45, rect.width() - 20, 20)
        painter.drawText(date_rect, Qt.AlignRight | Qt.AlignVCenter, timestamp)
        
        # Dibujar ícono de dispositivo
        device_id = test.get("device_id", "")
        device_text = f"🔬 {device_id}" if device_id else "🔬 Sin dispositivo"
        device_rect = QRect(rect.left() + 10, rect.top() + 45, rect.width() - 20, 20)
        painter.drawText(device_rect, Qt.AlignLeft | Qt.AlignVCenter, device_text)

class TestHistoryWidget(QWidget):
    """
    Widget for viewing and analyzing historical test data - 支持output多曲线显示
    """
    
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        
        # Current selections
        self.selected_device = None
        self.selected_test = None
        self.selected_step_index = -1
        
        # Current data
        self.devices = []
        self.tests = []
        self.test_info = {}
        self.step_data = []
        self.step_data_dict = {}  # 新增：支持多曲线数据存储
        
        # Plot lines for multiple curves
        self.plot_lines = {}
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)  # Reduce los márgenes
        main_layout.setSpacing(5)  # Reduce el espaciado
        
        # Device selection section - OPTIMIZADO
        device_frame = QFrame()
        device_frame.setFrameShape(QFrame.StyledPanel)
        device_frame.setMaximumHeight(40)  # Reducido de 50 a 40
        device_layout = QHBoxLayout(device_frame)
        device_layout.setContentsMargins(5, 2, 5, 2)  # Márgenes muy pequeños
        
        device_label = QLabel("设备:")
        device_label.setFont(QFont("Arial", 10, QFont.Bold))  # Reducido tamaño de fuente
        device_layout.addWidget(device_label)
        
        self.device_list = QListWidget()
        self.device_list.setFlow(QListWidget.LeftToRight)
        self.device_list.setMaximumHeight(100)  # Reducido de 50 a 30
        self.device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.device_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.device_list.setSpacing(5)
        self.device_list.currentItemChanged.connect(self.on_device_selected)
        device_layout.addWidget(self.device_list)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.setMaximumWidth(60)  # Ancho limitado
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(refresh_btn)
        
        main_layout.addWidget(device_frame)
        
        # Main content splitter
        self.content_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.content_splitter)
        
        # Left panel - Test list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes para maximizar espacio
        
        test_list_group = QGroupBox("测试列表")
        test_list_layout = QVBoxLayout(test_list_group)
        test_list_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        
        # Add toolbar for batch operations
        test_toolbar = QToolBar()
        test_toolbar.setIconSize(QSize(16, 16))
        
        # Export selected action
        export_action = QAction(QIcon.fromTheme("document-save"), "导出所选", self)
        export_action.triggered.connect(self.export_selected_tests)
        test_toolbar.addAction(export_action)
        
        # Delete selected action
        delete_action = QAction(QIcon.fromTheme("edit-delete"), "删除所选", self)
        delete_action.triggered.connect(self.delete_selected_tests)
        test_toolbar.addAction(delete_action)
        
        test_list_layout.addWidget(test_toolbar)
        
        # Selected count label
        self.selection_label = QLabel("提示: 按住Ctrl多选或Shift连选")
        self.selection_label.setAlignment(Qt.AlignCenter)
        self.selection_label.setStyleSheet("color: #666; font-size: 11px;")
        test_list_layout.addWidget(self.selection_label)
        
        # Test list with multi-selection
        self.test_list = QListWidget()
        self.test_list.setItemDelegate(CustomTestItemDelegate())  # Use custom delegate
        self.test_list.setSpacing(4)  # Add spacing between items
        # Set selection mode to allow multiple selection with Ctrl/Shift
        self.test_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.test_list.currentItemChanged.connect(self.on_test_selected)
        self.test_list.itemSelectionChanged.connect(self.on_selection_changed)
        test_list_layout.addWidget(self.test_list)
        
        left_layout.addWidget(test_list_group)
        
        # Middle panel - Step list
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes para maximizar espacio
        
        step_list_group = QGroupBox("步骤列表")
        step_list_layout = QVBoxLayout(step_list_group)
        step_list_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        
        self.step_list = QTreeWidget()
        self.step_list.setHeaderLabels(["步骤", "类型", "参数"])
        self.step_list.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.step_list.currentItemChanged.connect(self.on_step_selected)
        step_list_layout.addWidget(self.step_list)
        
        middle_layout.addWidget(step_list_group)
        
        # Right panel - Data visualization & details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes para maximizar espacio
        
        data_viz_group = QGroupBox("数据分析")
        data_viz_layout = QVBoxLayout(data_viz_group)
        data_viz_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        
        # Tab widget for plot and details
        self.data_tabs = QTabWidget()
        
        # Plot tab
        plot_tab = QWidget()
        plot_layout = QVBoxLayout(plot_tab)
        plot_layout.setContentsMargins(2, 2, 2, 2)  # Márgenes muy pequeños
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        
        # 添加图例
        self.legend = self.plot_widget.addLegend()

        # 添加文本显示项
        self.coord_label = pg.TextItem(text="", anchor=(0, 1), color=(50, 50, 50), fill=(200, 200, 200, 150))
        self.plot_widget.addItem(self.coord_label)
        self.coord_label.hide()  # 初始隐藏

        # 添加垂直和水平线用于标记位置
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('g', width=1))
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=1))
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)
        self.plot_widget.addItem(self.hLine, ignoreBounds=True)
        self.vLine.hide()
        self.hLine.hide()

        # 创建散点图用于标记最近点
        self.highlight_point = pg.ScatterPlotItem(
            size=10, brush=pg.mkBrush(255, 0, 0, 200), pen=None, symbol='o'
        )
        self.plot_widget.addItem(self.highlight_point)

        # 添加鼠标移动事件处理
        self.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)

        plot_layout.addWidget(self.plot_widget)
        
        self.data_tabs.addTab(plot_tab, "图表")
        
        # Details tab
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)
        details_layout.setContentsMargins(2, 2, 2, 2)  # Márgenes muy pequeños
        
        # Test info
        self.test_info_group = QGroupBox("测试信息")
        test_info_layout = QFormLayout(self.test_info_group)
        test_info_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        test_info_layout.setVerticalSpacing(4)  # Reduce espaciado vertical
        
        self.test_id_label = QLabel()
        test_info_layout.addRow("测试ID:", self.test_id_label)
        
        self.test_name_label = QLabel()
        test_info_layout.addRow("名称:", self.test_name_label)
        
        self.test_desc_label = QLabel()  # Added description label
        self.test_desc_label.setWordWrap(True)  # Allow wrapping for long descriptions
        test_info_layout.addRow("描述:", self.test_desc_label)
        
        self.test_device_label = QLabel()
        test_info_layout.addRow("设备:", self.test_device_label)
        
        self.test_created_label = QLabel()
        test_info_layout.addRow("创建时间:", self.test_created_label)
        
        details_layout.addWidget(self.test_info_group)
        
        # Step params
        self.step_params_group = QGroupBox("步骤参数")
        self.step_params_layout = QFormLayout(self.step_params_group)
        self.step_params_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        self.step_params_layout.setVerticalSpacing(4)  # Reduce espaciado vertical
        details_layout.addWidget(self.step_params_group)
        
        # Data stats
        self.data_stats_group = QGroupBox("数据统计")
        self.data_stats_layout = QFormLayout(self.data_stats_group)
        self.data_stats_layout.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        self.data_stats_layout.setVerticalSpacing(4)  # Reduce espaciado vertical
        
        self.data_points_label = QLabel()
        self.data_stats_layout.addRow("数据点数:", self.data_points_label)
        
        self.data_file_label = QLabel()
        self.data_stats_layout.addRow("文件名:", self.data_file_label)
        
        details_layout.addWidget(self.data_stats_group)
        
        self.data_tabs.addTab(details_tab, "详情")
        
        data_viz_layout.addWidget(self.data_tabs)
        right_layout.addWidget(data_viz_group)
        
        # Add panels to splitter
        self.content_splitter.addWidget(left_panel)
        self.content_splitter.addWidget(middle_panel)
        self.content_splitter.addWidget(right_panel)
        
        # Set default sizes
        self.content_splitter.setSizes([250, 250, 500])
    
    def on_selection_changed(self):
        """Handle changes in the test list selection"""
        selected_items = self.test_list.selectedItems()
        count = len(selected_items)
        
        # Update selection label
        if count > 1:
            self.selection_label.setText(f"已选择: {count} 项")
            self.selection_label.setStyleSheet("color: #1890ff; font-weight: bold; font-size: 11px;")
        else:
            self.selection_label.setText("提示: 按住Ctrl多选或Shift连选")
            self.selection_label.setStyleSheet("color: #666; font-size: 11px;")
    
    def refresh_devices(self):
        """Refresh the device list"""
        try:
            # Get all saved tests
            all_tests = self.backend.list_saved_tests()
            
            # Extract unique device IDs
            device_ids = set()
            for test in all_tests:
                device_ids.add(test.get("device_id", ""))
            
            # Update devices list
            self.devices = sorted(list(device_ids))
            
            # Remember current selection
            current_device = self.selected_device
            
            # Update device list widget
            self.device_list.clear()
            for device_id in self.devices:
                if device_id:  # Skip empty device IDs
                    item = QListWidgetItem(device_id)
                    item.setData(Qt.UserRole, device_id)
                    self.device_list.addItem(item)
            
            # Restore selection if possible
            if current_device in self.devices:
                for i in range(self.device_list.count()):
                    if self.device_list.item(i).data(Qt.UserRole) == current_device:
                        self.device_list.setCurrentRow(i)
                        break
            elif self.device_list.count() > 0:
                self.device_list.setCurrentRow(0)
            else:
                # Clear other lists
                self.tests = []
                self.test_list.clear()
                self.step_list.clear()
                self.clear_plot()
                self.clear_details()
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"获取设备列表失败: {str(e)}")
    
    def refresh_tests(self):
        """Refresh the test list for selected device"""
        if not self.selected_device:
            return
        
        try:
            # Get tests for selected device
            self.tests = self.backend.list_saved_tests(self.selected_device)
            
            # Remember current selection
            current_test_id = None
            if self.selected_test:
                current_test_id = self.selected_test.get("test_id")
            
            # Update test list widget
            self.test_list.clear()
            for test in self.tests:
                # 预先加载test_info数据
                test_dir = test.get("dir_path")
                if test_dir and os.path.exists(test_dir):
                    test_data = self.backend.get_saved_test_data(test_dir)
                    if test_data and test_data.get("status") == "ok":
                        test_info = test_data.get("test_info", {})
                        # 更新test对象的description
                        if "description" in test_info:
                            test["description"] = test_info["description"]
                        test["test_info"] = test_info
                
                # Create list item with test info
                item = QListWidgetItem()
                item.setData(Qt.UserRole, test)
                item.setText(test.get("name", "未命名"))
                self.test_list.addItem(item)
            
            # Restore selection if possible
            if current_test_id:
                for i in range(self.test_list.count()):
                    test = self.test_list.item(i).data(Qt.UserRole)
                    if test.get("test_id") == current_test_id:
                        self.test_list.setCurrentRow(i)
                        break
            elif self.test_list.count() > 0:
                self.test_list.setCurrentRow(0)
            else:
                # Clear other widgets
                self.step_list.clear()
                self.clear_plot()
                self.clear_details()
            
            # Update selection label
            self.on_selection_changed()
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"获取测试列表失败: {str(e)}")
    
    def get_selected_tests(self):
        """Get all currently selected tests"""
        selected_items = self.test_list.selectedItems()
        selected_tests = []
        
        for item in selected_items:
            test = item.data(Qt.UserRole)
            if test:
                selected_tests.append(test)
                
        return selected_tests
    
    def export_selected_tests(self):
        """Export selected tests to a user-specified directory"""
        selected_tests = self.get_selected_tests()
        
        if not selected_tests:
            QMessageBox.information(self, "导出", "请先选择要导出的测试")
            return
        
        # Ask for destination directory
        dest_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", "", QFileDialog.ShowDirsOnly)
        if not dest_dir:
            return  # User canceled
            
        try:
            exported_count = 0
            skipped_count = 0
            
            for test in selected_tests:
                # Get test info
                test_name = test.get("name", "").replace(" ", "_")
                test_desc = test.get("description", "").replace(" ", "_")
                source_dir = test.get("dir_path", "")
                
                if not source_dir or not os.path.exists(source_dir):
                    skipped_count += 1
                    continue
                
                # Create new directory name with test name and description prefix
                prefix = ""
                if test_name:
                    prefix += test_name + "_"
                if test_desc:
                    prefix += test_desc + "_"
                    
                # If no prefix was created, use a default
                if not prefix:
                    prefix = "Test_"
                    
                # Make sure prefix is not too long and has valid characters
                prefix = ''.join(c for c in prefix if c.isalnum() or c in '_-')
                if len(prefix) > 50:  # Truncate if too long
                    prefix = prefix[:50]
                    
                new_dir_name = prefix + os.path.basename(source_dir)
                target_dir = os.path.join(dest_dir, new_dir_name)
                
                # Copy directory
                if os.path.exists(target_dir):
                    # Directory already exists, add timestamp to make it unique
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    target_dir = os.path.join(dest_dir, f"{prefix}{timestamp}_{os.path.basename(source_dir)}")
                
                # Copy the directory
                shutil.copytree(source_dir, target_dir)
                exported_count += 1
            
            # Show results
            result_message = f"成功导出 {exported_count} 个测试"
            if skipped_count > 0:
                result_message += f"，跳过 {skipped_count} 个测试（源目录不存在）"
                
            QMessageBox.information(self, "导出完成", result_message)
            
        except Exception as e:
            QMessageBox.warning(self, "导出错误", f"导出过程中发生错误: {str(e)}")
    
    def delete_selected_tests(self):
        """Delete selected tests"""
        selected_tests = self.get_selected_tests()
        
        if not selected_tests:
            QMessageBox.information(self, "删除", "请先选择要删除的测试")
            return
            
        # Confirm deletion
        count = len(selected_tests)
        if count == 1:
            confirm_msg = "确定要删除选中的测试吗？此操作不可撤销。"
        else:
            confirm_msg = f"确定要删除选中的 {count} 个测试吗？此操作不可撤销。"
            
        reply = QMessageBox.question(self, "确认删除", confirm_msg, 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply != QMessageBox.Yes:
            return
            
        try:
            deleted_count = 0
            failed_count = 0
            
            for test in selected_tests:
                test_id = test.get("test_id", "")
                source_dir = test.get("dir_path", "")
                
                if source_dir and os.path.exists(source_dir):
                    try:
                        # Delete the directory
                        shutil.rmtree(source_dir)
                        deleted_count += 1
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Error deleting test {test_id}: {str(e)}")
                else:
                    failed_count += 1
            
            # Refresh the tests list
            self.refresh_tests()
            
            # Show results
            result_message = f"成功删除 {deleted_count} 个测试"
            if failed_count > 0:
                result_message += f"，失败 {failed_count} 个测试"
                
            QMessageBox.information(self, "删除完成", result_message)
            
        except Exception as e:
            QMessageBox.warning(self, "删除错误", f"删除过程中发生错误: {str(e)}")
    
    def load_test_info(self):
        """Load test information for selected test"""
        if not self.selected_test:
            return
        
        try:
            # Get test directory
            test_dir = self.selected_test.get("dir_path")
            if not test_dir or not os.path.exists(test_dir):
                QMessageBox.warning(self, "Error", f"测试目录不存在: {test_dir}")
                return
            
            # Load test info
            self.test_info = self.backend.get_saved_test_data(test_dir)
            
            # Update test object with additional information - IMPORTANTE!
            # Esto asegura que la información completa esté disponible para el delegado
            if self.test_info and self.test_info.get("status") == "ok":
                test_info_data = self.test_info.get("test_info", {})
                
                # Añadir datos al objeto test actual
                self.selected_test["test_info"] = test_info_data
                
                # Asegurarse de que la descripción esté disponible
                if "description" in test_info_data:
                    self.selected_test["description"] = test_info_data["description"]
                
                # Actualizar el item en la lista para reflejar los cambios
                for i in range(self.test_list.count()):
                    item = self.test_list.item(i)
                    test = item.data(Qt.UserRole)
                    if test.get("test_id") == self.selected_test.get("test_id"):
                        item.setData(Qt.UserRole, self.selected_test)
                        # Forzar actualización visual
                        self.test_list.update()
                        break
            
            # Update step list
            self.refresh_step_list()
            
            # Update test details
            self.update_test_details()
            
            # Clear plot until a step is selected
            self.clear_plot()
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"加载测试信息失败: {str(e)}")
    
    def refresh_step_list(self):
        """Refresh the step list for selected test"""
        self.step_list.clear()
        
        if not self.test_info or self.test_info.get("status") != "ok":
            return
        
        test_info_data = self.test_info.get("test_info", {})
        steps = test_info_data.get("steps", [])
        
        for i, step in enumerate(steps):
            # Create tree item
            item = QTreeWidgetItem()
            
            # Set step number
            item.setText(0, f"步骤 {i+1}")
            
            # Set step type
            step_type = step.get("type", "unknown")
            item.setText(1, step_type)
            
            # Set step data
            item.setData(0, Qt.UserRole, {"index": i, "step": step})
            
            # Set params summary
            params = step.get("params", {})
            params_text = ""
            
            if step_type == "transfer":
                gate_start = params.get("gateVoltageStart", 0) / 1000.0
                gate_end = params.get("gateVoltageEnd", 0) / 1000.0
                drain = params.get("drainVoltage", 0) / 1000.0
                source = params.get("sourceVoltage", 0) / 1000.0
                params_text = f"Vg: {gate_start} → {gate_end}V, Vd: {drain}V, Vs: {source}V"
            
            elif step_type == "transient":
                gate_bottom = params.get("gateVoltageBottom", 0) / 1000.0
                gate_top = params.get("gateVoltageTop", 0) / 1000.0
                drain = params.get("drainVoltage", 0) / 1000.0
                source = params.get("sourceVoltage", 0) / 1000.0
                cycles = params.get("cycles", 0)
                params_text = f"Vg: {gate_bottom} → {gate_top}V, Vd: {drain}V, Vs: {source}V, 循环: {cycles}"
                
            elif step_type == "output":  # 修改：正确显示output参数
                gate_voltages = params.get("gateVoltageList", [0])
                if isinstance(gate_voltages, list):
                    gate_text = f"{min(gate_voltages)/1000.0:.3f}-{max(gate_voltages)/1000.0:.3f}V ({len(gate_voltages)}条)"
                else:
                    gate_text = f"{gate_voltages/1000.0:.3f}V"
                
                drain_start = params.get("drainVoltageStart", 0) / 1000.0
                drain_end = params.get("drainVoltageEnd", 0) / 1000.0
                source = params.get("sourceVoltage", 0) / 1000.0
                params_text = f"Vd: {drain_start:.3f} → {drain_end:.3f}V, Vg: {gate_text}, Vs: {source:.3f}V"

            item.setText(2, params_text)
            
            # Add to tree widget
            self.step_list.addTopLevelItem(item)
        
        # Auto-expand all items
        self.step_list.expandAll()
    
    def update_test_details(self):
        """Update test details in the details tab"""
        if not self.test_info or self.test_info.get("status") != "ok":
            self.clear_details()
            return
        
        test_info_data = self.test_info.get("test_info", {})
        
        # Update test info labels
        self.test_id_label.setText(test_info_data.get("test_id", ""))
        self.test_name_label.setText(test_info_data.get("name", ""))
        self.test_desc_label.setText(test_info_data.get("description", ""))  # Show description
        self.test_device_label.setText(test_info_data.get("device_id", ""))
        
        # Format created date
        created_at = test_info_data.get("created_at", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
                self.test_created_label.setText(dt.strftime("%Y-%m-%d %H:%M:%S"))
            except:
                self.test_created_label.setText(created_at)
        else:
            self.test_created_label.setText("")
    
    def update_step_params(self, step):
        """Update step parameters in the details tab"""
        # Clear existing form
        self.clear_step_params()
        
        # Get step type and params
        step_type = step.get("type", "unknown")
        params = step.get("params", {})
        
        # Add params to form
        if step_type == "transfer":
            self.add_param_label("是否回扫", "是" if params.get("isSweep") == 1 else "否")
            self.add_param_label("时间步长", f"{params.get('timeStep', 0)} ms")
            
            # Add voltages with consistent formatting and highlighting
            self.add_voltage_param("源电压 (Vs)", params.get('sourceVoltage', 0))
            self.add_voltage_param("漏电压 (Vd)", params.get('drainVoltage', 0))
            self.add_voltage_param("栅压起点 (Vg start)", params.get('gateVoltageStart', 0))
            self.add_voltage_param("栅压终点 (Vg end)", params.get('gateVoltageEnd', 0))
            self.add_voltage_param("栅压步长 (Vg step)", params.get('gateVoltageStep', 0))
            
            # Add calculated values for convenience
            gate_span = abs(params.get('gateVoltageEnd', 0) - params.get('gateVoltageStart', 0))
            step_size = params.get('gateVoltageStep', 0)
            if step_size > 0:
                num_points = gate_span / step_size + 1
                self.add_param_label("理论数据点数", f"{int(num_points)}")
        
        elif step_type == "transient":
            self.add_param_label("时间步长", f"{params.get('timeStep', 0)} ms")
            
            # Add voltages with consistent formatting and highlighting
            self.add_voltage_param("源电压 (Vs)", params.get('sourceVoltage', 0))
            self.add_voltage_param("漏电压 (Vd)", params.get('drainVoltage', 0))
            self.add_voltage_param("底部栅压 (Vg low)", params.get('gateVoltageBottom', 0))
            self.add_voltage_param("顶部栅压 (Vg high)", params.get('gateVoltageTop', 0))
            
            # Add timing parameters
            self.add_param_label("底部时间", f"{params.get('bottomTime', 0)} ms")
            self.add_param_label("顶部时间", f"{params.get('topTime', 0)} ms")
            self.add_param_label("循环次数", f"{params.get('cycles', 0)}")
            
            # Add calculated values for convenience
            cycle_time = params.get('bottomTime', 0) + params.get('topTime', 0)
            total_time = cycle_time * params.get('cycles', 0)
            self.add_param_label("总测试时间", f"{total_time} ms ({total_time/1000:.1f} s)")
            
        elif step_type == "output":  # 修改：正确显示output参数
            self.add_param_label("是否回扫", "是" if params.get("isSweep") == 1 else "否")
            self.add_param_label("时间步长", f"{params.get('timeStep', 0)} ms")
            
            # Add voltages with consistent formatting and highlighting
            self.add_voltage_param("源电压 (Vs)", params.get('sourceVoltage', 0))
            
            # 显示栅极电压列表
            gate_voltages = params.get("gateVoltageList", [0])
            if isinstance(gate_voltages, list):
                gate_voltage_text = ", ".join([f"{v} mV" for v in gate_voltages])
                self.add_param_label("栅极电压列表", gate_voltage_text)
                self.add_param_label("输出特性曲线数", f"{len(gate_voltages)} 条")
            else:
                self.add_voltage_param("栅极电压", gate_voltages)
            
            self.add_voltage_param("漏压起点 (Vd start)", params.get('drainVoltageStart', 0))
            self.add_voltage_param("漏压终点 (Vd end)", params.get('drainVoltageEnd', 0))
            self.add_voltage_param("漏压步长 (Vd step)", params.get('drainVoltageStep', 0))
            
            # Add calculated values for convenience
            drain_span = abs(params.get('drainVoltageEnd', 0) - params.get('drainVoltageStart', 0))
            step_size = params.get('drainVoltageStep', 0)
            if step_size > 0:
                num_points = drain_span / step_size + 1
                self.add_param_label("每条曲线数据点数", f"{int(num_points)}")
    
    def add_param_label(self, name, value):
        """Add a parameter label to the form"""
        label = QLabel(str(value))
        self.step_params_layout.addRow(name + ":", label)
    
    def add_voltage_param(self, name, value_mv):
        """Add a voltage parameter with mV and V display"""
        value_v = value_mv / 1000.0
        label = QLabel(f"{value_mv} mV ({value_v:.3f} V)")
        # Style for voltage parameters - blue text
        label.setStyleSheet("color: #0066cc; font-weight: bold;")
        self.step_params_layout.addRow(name + ":", label)
    
    def update_data_stats(self, file_name, data_count, curve_count=1):
        """Update data statistics in the details tab"""
        if curve_count > 1:
            self.data_points_label.setText(f"{data_count} 点/曲线 × {curve_count} 曲线")
        else:
            self.data_points_label.setText(str(data_count))
        self.data_file_label.setText(file_name)
    
    def clear_details(self):
        """Clear all details"""
        self.test_id_label.setText("")
        self.test_name_label.setText("")
        self.test_desc_label.setText("")  # Clear description
        self.test_device_label.setText("")
        self.test_created_label.setText("")
        self.clear_step_params()
        self.data_points_label.setText("")
        self.data_file_label.setText("")
    
    def clear_step_params(self):
        """Clear step parameters form"""
        # Remove all form rows except for the first two (which are data stats)
        while self.step_params_layout.rowCount() > 0:
            # Get the first field item
            item = self.step_params_layout.itemAt(0, QFormLayout.FieldRole)
            if item:
                # Remove the widget
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            # Remove the row
            self.step_params_layout.removeRow(0)
    
    def load_step_data(self, step_index):
        """Load data for selected step - 支持output多曲线"""
        if not self.test_info or self.test_info.get("status") != "ok":
            return
        
        test_info_data = self.test_info.get("test_info", {})
        steps = test_info_data.get("steps", [])
        
        if step_index < 0 or step_index >= len(steps):
            return
        
        try:
            # Get step info
            step = steps[step_index]
            step_type = step.get("type", "unknown")
            data_file = step.get("data_file")
            
            if not data_file:
                self.step_data = []
                self.step_data_dict = {}
                self.clear_plot()
                return
            
            # Get test directory
            test_dir = self.selected_test.get("dir_path")
            file_path = os.path.join(test_dir, data_file)
            
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "Error", f"数据文件不存在: {file_path}")
                return
            
            # Load CSV data
            with open(file_path, "r") as f:
                reader = csv.reader(f)
                # Get header
                header = next(reader)
                
                # Parse data based on step type
                if step_type == "output":
                    # Output type: multiple columns for different gate voltages
                    self.load_output_data(reader, header)
                else:
                    # Transfer/Transient type: traditional two-column data
                    self.load_traditional_data(reader, header)
            
            # Update plot
            self.update_plot(step_type)
            
            # Update data stats
            if step_type == "output":
                curve_count = len(self.step_data_dict)
                point_count = len(next(iter(self.step_data_dict.values()))) if self.step_data_dict else 0
                self.update_data_stats(data_file, point_count, curve_count)
            else:
                self.update_data_stats(data_file, len(self.step_data))
            
            # Update step params
            self.update_step_params(step)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"加载步骤数据失败: {str(e)}")
    
    def load_output_data(self, reader, header):
        """加载output类型的多曲线数据"""
        # 第一列是x轴数据（通常是Vd）
        x_label = header[0]
        curve_labels = header[1:]  # 后续列是各条曲线
        
        # 初始化数据结构
        x_values = []
        curves_data = {label: [] for label in curve_labels}
        
        # 读取数据
        for row in reader:
            if len(row) == len(header):
                try:
                    x_val = float(row[0])
                    x_values.append(x_val)
                    
                    for i, label in enumerate(curve_labels):
                        y_val = float(row[i + 1])
                        curves_data[label].append(y_val)
                except ValueError:
                    continue
        
        # 存储数据
        self.step_data = [[x, curves_data[curve_labels[0]][i]] for i, x in enumerate(x_values)]  # 保持兼容性
        self.step_data_dict = {
            'x_values': x_values,
            'curves': curves_data,
            'x_label': x_label
        }
    
    def load_traditional_data(self, reader, header):
        """加载传统的两列数据"""
        data = []
        for row in reader:
            try:
                x = float(row[0])
                y = float(row[1])
                data.append([x, y])
            except:
                pass
        
        self.step_data = data
        self.step_data_dict = {}
    
    def update_plot(self, step_type):
        """Update plot with loaded data - 支持多曲线"""
        # 清除现有图例和曲线
        self.legend.clear()
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        if step_type == "output" and self.step_data_dict:
            # 绘制output多曲线
            self.plot_output_curves()
        elif self.step_data:
            # 绘制单曲线
            self.plot_single_curve(step_type)
        else:
            self.clear_plot()
    
    def plot_output_curves(self):
        """绘制output类型的多条曲线"""
        x_values = self.step_data_dict['x_values']
        curves = self.step_data_dict['curves']
        x_label = self.step_data_dict['x_label']
        
        # 设置坐标轴标签
        self.plot_widget.setLabel('bottom', f'{x_label} (V)')
        self.plot_widget.setLabel('left', 'Current (A)')
        self.plot_widget.setTitle('输出特性曲线')
        
        # 绘制每条曲线
        colors = ['b', 'r', 'g', 'c', 'm', 'y', 'k', 'orange', 'purple', 'brown']
        
        for i, (curve_name, y_values) in enumerate(curves.items()):
            if len(y_values) == len(x_values):
                color = colors[i % len(colors)]
                line = self.plot_widget.plot(x_values, y_values, 
                                           pen=pg.mkPen(color=color, width=2),
                                           name=curve_name)
                self.plot_lines[curve_name] = line
        
        # 隐藏鼠标追踪相关的辅助线
        self.vLine.hide()
        self.hLine.hide()
        self.coord_label.hide()
        self.highlight_point.clear()
    
    def plot_single_curve(self, step_type):
        """绘制单条曲线（transfer或transient）"""
        # Extract x and y values
        x = [point[0] for point in self.step_data]
        y = [point[1] for point in self.step_data]
        
        # Set plot labels based on step type
        if step_type == "transfer":
            self.plot_widget.setLabel('bottom', 'Gate Voltage (V)')
            self.plot_widget.setLabel('left', 'Current (A)')
            self.plot_widget.setTitle('转移特性曲线')
        else:  # transient
            self.plot_widget.setLabel('bottom', 'Time (s)')
            self.plot_widget.setLabel('left', 'Current (A)')
            self.plot_widget.setTitle('瞬态响应曲线')
        
        # 创建并绘制曲线
        line = self.plot_widget.plot(x, y, 
                                   pen=pg.mkPen(color='b', width=2),
                                   name="Current")
        self.plot_lines["Current"] = line
        
        # 隐藏辅助线和标签
        self.vLine.hide()
        self.hLine.hide()
        self.coord_label.hide()
        self.highlight_point.clear()
    
    def clear_plot(self):
        """Clear the plot"""
        # 清除图例和曲线
        self.legend.clear()
        for line in self.plot_lines.values():
            self.plot_widget.removeItem(line)
        self.plot_lines = {}
        
        self.plot_widget.setTitle('')
        # 隐藏辅助线和标签
        self.vLine.hide()
        self.hLine.hide()
        self.coord_label.hide()
        self.highlight_point.clear()
    
    def on_device_selected(self, current, previous):
        """Handle device selection"""
        if not current:
            self.selected_device = None
            return
        
        # Get device ID
        device_id = current.data(Qt.UserRole)
        
        # Update selection
        self.selected_device = device_id
        
        # Refresh tests for this device
        self.refresh_tests()
    
    def on_test_selected(self, current, previous):
        """Handle test selection"""
        if not current:
            self.selected_test = None
            return
        
        # Get test data
        test = current.data(Qt.UserRole)
        
        # Update selection
        self.selected_test = test
        
        # Load test info
        self.load_test_info()

        # 自动选择第一个步骤
        if self.step_list.topLevelItemCount() > 0:
            first_item = self.step_list.topLevelItem(0)
            self.step_list.setCurrentItem(first_item)
        
    def on_step_selected(self, current, previous):
        """Handle step selection"""
        if not current:
            self.selected_step_index = -1
            return
        
        # Get step data
        step_data = current.data(0, Qt.UserRole)
        if not step_data:
            return
        
        # Get step index
        step_index = step_data.get("index", -1)
        
        # Update selection
        self.selected_step_index = step_index
        
        # Load step data
        self.load_step_data(step_index)

    def on_mouse_moved(self, pos):
        """处理鼠标在图表上移动的事件 - 仅对单曲线有效"""
        # 仅对单曲线图表启用鼠标追踪
        if len(self.plot_lines) != 1 or not self.step_data:
            self.vLine.hide()
            self.hLine.hide()
            self.coord_label.hide()
            self.highlight_point.clear()
            return
            
        # 获取鼠标在绘图项中的位置
        view_box = self.plot_widget.getPlotItem().getViewBox()
        if not view_box.sceneBoundingRect().contains(pos):
            self.vLine.hide()
            self.hLine.hide()
            self.coord_label.hide()
            self.highlight_point.clear()
            return
            
        # 将鼠标位置转换为图表坐标
        mouse_point = view_box.mapSceneToView(pos)
        x, y = mouse_point.x(), mouse_point.y()
        
        # 设置十字线位置
        self.vLine.setPos(x)
        self.hLine.setPos(y)
        self.vLine.show()
        self.hLine.show()
        
        # 找到最近的数据点
        x_data = [point[0] for point in self.step_data]
        y_data = [point[1] for point in self.step_data]
        
        # 计算鼠标到所有点的距离
        distances = []
        for i in range(len(x_data)):
            dx = x - x_data[i]
            dy = y - y_data[i]
            # 使用距离的平方（避免开平方运算）
            distances.append(dx*dx + dy*dy)
        
        # 找到最近点的索引
        if not distances:
            return
        nearest_idx = distances.index(min(distances))
        nearest_x = x_data[nearest_idx]
        nearest_y = y_data[nearest_idx]
        
        # 计算距离阈值，仅在足够近时显示
        view_range = view_box.viewRange()
        x_range = view_range[0][1] - view_range[0][0]
        y_range = view_range[1][1] - view_range[1][0]
        distance_threshold = ((x_range/20)**2 + (y_range/20)**2)
        
        if distances[nearest_idx] > distance_threshold:
            self.coord_label.hide()
            self.highlight_point.clear()
            return
        
        text = f"x: {nearest_x:.3f}\ny: {nearest_y:.3e}"
        
        # 设置文本位置和内容
        self.coord_label.setText(text)
        self.coord_label.setPos(nearest_x, nearest_y)
        self.coord_label.show()
        
        # 高亮显示最近的点
        self.highlight_point.setData([nearest_x], [nearest_y])