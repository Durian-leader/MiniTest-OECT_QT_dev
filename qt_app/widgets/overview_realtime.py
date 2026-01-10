import time
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QGroupBox,
    QHBoxLayout,
    QSizePolicy,
    QGridLayout,
    QSpinBox,
    QToolButton,
    QMenu,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from qt_app.i18n import tr
from qt_app.widgets.realtime_plot import RealtimePlotWidget

########################### 日志设置 ###################################
from logger_config import get_module_logger

logger = get_module_logger()
#####################################################################


class OverviewRealtimeWidget(QWidget):
    """Tab for monitoring all devices' real-time plots simultaneously."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_panels: Dict[str, Dict[str, Any]] = {}
        self.columns_count = 2
        self.plot_height = 440
        self.min_column_width = 320
        self._chrome_height = 140  # Approximate non-plot height for uniform cards
        self.filter_actions: Dict[str, Any] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.header_label = QLabel(tr("overview.title"))
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.header_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.header_label)

        self.subtitle_label = QLabel(tr("overview.subtitle"))
        self.subtitle_label.setStyleSheet("color: #666;")
        layout.addWidget(self.subtitle_label)

        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(6)
        self.layout_label = QLabel(tr("overview.columns_label"))
        control_row.addWidget(self.layout_label, 0, Qt.AlignLeft)
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 10)
        self.columns_spin.setValue(self.columns_count)
        self.columns_spin.setSuffix(tr("overview.columns_suffix"))
        self.columns_spin.valueChanged.connect(self._on_columns_changed)
        control_row.addWidget(self.columns_spin, 0, Qt.AlignLeft)

        self.height_label = QLabel(tr("overview.height_label"))
        control_row.addWidget(self.height_label, 0, Qt.AlignLeft)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(200, 800)
        self.height_spin.setSingleStep(20)
        self.height_spin.setValue(self.plot_height)
        self.height_spin.setSuffix(tr("overview.height_suffix"))
        self.height_spin.valueChanged.connect(self._on_height_changed)
        control_row.addWidget(self.height_spin, 0, Qt.AlignLeft)

        self.filter_button = QToolButton()
        self.filter_button.setText(tr("overview.filter_label"))
        self.filter_button.setPopupMode(QToolButton.InstantPopup)
        self.filter_menu = QMenu(self)
        self.filter_button.setMenu(self.filter_menu)
        control_row.addWidget(self.filter_button, 0, Qt.AlignLeft)

        control_row.addStretch()
        layout.addLayout(control_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.devices_layout = QGridLayout(self.scroll_content)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setHorizontalSpacing(10)
        self.devices_layout.setVerticalSpacing(10)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

        self.empty_label = QLabel(tr("overview.empty"))
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 12px;")
        layout.addWidget(self.empty_label)

    def handle_test_started(self, port: str, test_id: str, metadata: Dict[str, Any]):
        """Create or reset a panel when a device test starts."""
        panel = self._get_or_create_panel(port)
        panel["meta"] = metadata or {}
        panel["meta"]["port"] = port
        panel["meta"]["test_id"] = test_id
        panel["completed"] = False
        plot: RealtimePlotWidget = panel["plot"]
        plot.set_test_id(test_id)
        plot.display_max_points = 3000

        # Apply device-specific settings if provided
        if metadata:
            plot.set_transimpedance_ohms(metadata.get("transimpedance_ohms"))
            plot.set_baseline_current(metadata.get("baseline_current"))

        self._update_panel_labels(port)
        panel["status_label"].setText(tr("overview.card_running"))
        panel["container"].setStyleSheet("QGroupBox { border: 1px solid #ddd; border-radius: 6px; }")
        self.empty_label.setVisible(False)
        self._ensure_filter_action(port, panel["meta"])
        self._apply_filter_visibility(port)

    def handle_real_time_data(self, port: str, data: Dict[str, Any]):
        """Forward real-time data to the corresponding plot."""
        panel = self.device_panels.get(port)
        if not panel:
            return
        try:
            panel["plot"].process_message(data)
            panel["last_update"] = time.time()
        except Exception as exc:
            logger.error(f"Forwarding real-time data failed for {port}: {exc}")

    def handle_test_completed(self, port: str, test_id: str):
        """Mark a device panel as completed."""
        panel = self.device_panels.get(port)
        if not panel:
            return
        panel["completed"] = True
        panel["status_label"].setText(tr("overview.card_completed"))
        try:
            panel["plot"].set_test_completed()
        except Exception:
            pass
        self._update_panel_labels(port)
        self._ensure_filter_action(port, panel.get("meta", {}))

    def _get_or_create_panel(self, port: str) -> Dict[str, Any]:
        if port in self.device_panels:
            return self.device_panels[port]

        container = QGroupBox()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        container.setStyleSheet("QGroupBox { border: 1px solid #eee; border-radius: 6px; }")
        panel_layout = QVBoxLayout(container)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        title_label = QLabel()
        title_label.setFont(QFont("Arial", 11, QFont.Bold))
        title_row.addWidget(title_label, 1)

        status_label = QLabel(tr("overview.card_running"))
        status_label.setStyleSheet("color: #888;")
        title_row.addWidget(status_label, 0, Qt.AlignRight)

        panel_layout.addLayout(title_row)

        info_label = QLabel()
        info_label.setStyleSheet("color: #666;")
        panel_layout.addWidget(info_label)

        plot = RealtimePlotWidget(port)
        self._apply_plot_height(plot)
        panel_layout.addWidget(plot)

        panel = {
            "container": container,
            "title_label": title_label,
            "status_label": status_label,
            "info_label": info_label,
            "plot": plot,
            "meta": {},
            "completed": False,
            "last_update": None,
        }
        self.device_panels[port] = panel

        self._rebuild_grid()
        return panel

    def _rebuild_grid(self):
        """Re-apply grid positions based on columns."""
        # Clear existing items
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(self.scroll_content)

        visible_panels = [p for p in self.device_panels.values() if self._is_panel_visible(p)]
        target_width = self._compute_card_width()
        target_height = self._compute_card_height()

        for col in range(self.columns_count):
            self.devices_layout.setColumnStretch(col, 1)
            self.devices_layout.setColumnMinimumWidth(col, self.min_column_width)

        for idx, panel in enumerate(visible_panels):
            row = idx // self.columns_count
            col = idx % self.columns_count
            container = panel["container"]
            container.setMinimumWidth(target_width)
            container.setMaximumWidth(target_width)
            container.setMinimumHeight(target_height)
            container.setMaximumHeight(target_height)
            self.devices_layout.addWidget(container, row, col)

    def _on_columns_changed(self, value: int):
        self.columns_count = max(1, value)
        self._rebuild_grid()

    def _on_height_changed(self, value: int):
        self.plot_height = max(100, value)
        for panel in self.device_panels.values():
            self._apply_plot_height(panel["plot"])
        self._rebuild_grid()

    def _apply_plot_height(self, plot: RealtimePlotWidget):
        plot.setMinimumHeight(self.plot_height)
        plot.setMaximumHeight(self.plot_height)
        self._rebuild_grid()

    def _compute_card_width(self) -> int:
        available = self.scroll_area.viewport().width()
        spacing = self.devices_layout.horizontalSpacing() or 0
        columns = max(1, self.columns_count)
        target = (available - spacing * (columns - 1)) / columns
        return max(int(target), self.min_column_width)

    def _compute_card_height(self) -> int:
        return self.plot_height + self._chrome_height

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_grid()

    def _apply_filter_visibility(self, port: str):
        panel = self.device_panels.get(port)
        if not panel:
            return
        panel["container"].setVisible(self._is_panel_visible(port))

    def _is_panel_visible(self, port_or_panel) -> bool:
        port = port_or_panel
        if isinstance(port_or_panel, dict):
            port = port_or_panel.get("meta", {}).get("port") or ""
        action = self.filter_actions.get(port)
        if action:
            return action.isChecked()
        return True

    def _ensure_filter_action(self, port: str, meta: Dict[str, Any]):
        name = meta.get("device_id") or port
        if port in self.filter_actions:
            action = self.filter_actions[port]
            action.setText(name)
            return

        action = self.filter_menu.addAction(name)
        action.setCheckable(True)
        action.setChecked(True)
        action.setData(port)
        action.toggled.connect(lambda checked, p=port: self._on_filter_toggled(p, checked))
        self.filter_actions[port] = action
        self._refresh_filter_button_text()

    def _on_filter_toggled(self, port: str, checked: bool):
        self._apply_filter_visibility(port)
        self._refresh_filter_button_text()
        self._rebuild_grid()

    def _refresh_filter_button_text(self):
        total = len(self.filter_actions)
        shown = len([a for a in self.filter_actions.values() if a.isChecked()])
        self.filter_button.setText(tr("overview.filter_label") + f" ({shown}/{total})" if total else tr("overview.filter_label"))

    def _update_panel_labels(self, port: str):
        panel = self.device_panels.get(port)
        if not panel:
            return

        meta = panel["meta"]
        device_name = meta.get("device_id") or port
        test_name = meta.get("test_name") or tr("overview.no_name")
        test_id = meta.get("test_id", "")

        panel["title_label"].setText(tr("overview.card_title", device=device_name, port=port))
        if test_id:
            status_text = panel["status_label"].text()
            panel["info_label"].setText(tr("overview.card_test_line", name=test_name, test_id=test_id, status=status_text))
        else:
            panel["info_label"].setText(test_name)

    def update_translations(self):
        """Refresh static text and existing panel labels."""
        self.header_label.setText(tr("overview.title"))
        self.subtitle_label.setText(tr("overview.subtitle"))
        self.empty_label.setText(tr("overview.empty"))
        self.layout_label.setText(tr("overview.columns_label"))
        self.columns_spin.setSuffix(tr("overview.columns_suffix"))
        self.height_label.setText(tr("overview.height_label"))
        self.height_spin.setSuffix(tr("overview.height_suffix"))
        self._refresh_filter_button_text()
        for port in list(self.device_panels.keys()):
            self._update_panel_labels(port)

    def update_device_list(self, devices: list):
        """Synchronize filter list with device control panel."""
        ports_from_devices = set()
        for device in devices or []:
            port = device.get("device")
            if not port:
                continue
            ports_from_devices.add(port)
            meta = {
                "device_id": device.get("device_id"),
                "description": device.get("description"),
                "port": port,
            }
            self._ensure_filter_action(port, meta)

        # Keep actions for active panels even if device temporarily missing
        for panel in self.device_panels.values():
            port = panel.get("meta", {}).get("port")
            if port:
                ports_from_devices.add(port)
                self._ensure_filter_action(port, panel.get("meta", {}))

        # Remove stale actions
        for port in list(self.filter_actions.keys()):
            if port not in ports_from_devices:
                action = self.filter_actions.pop(port)
                self.filter_menu.removeAction(action)

        self._refresh_filter_button_text()
        self._rebuild_grid()
