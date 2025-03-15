"""
Panel for managing video trim segments
"""
import re
from typing import Dict, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QComboBox, QScrollArea,
    QGroupBox, QFormLayout, QMessageBox, QFrame, QDialog,
    QDialogButtonBox, QInputDialog, QListWidget, QStyle
)
from PyQt5.QtCore import Qt, pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator

from models.video_segment import VideoSegment
from utils.config_manager import ConfigManager
from services.timecode_utils import validate_timecode


class SegmentWidget(QGroupBox):
    """Widget for a single video segment"""
    
    # Signals
    remove_clicked = pyqtSignal(object)  # Signal when remove button clicked
    seek_start_clicked = pyqtSignal(str)  # Signal when seek to start clicked
    seek_end_clicked = pyqtSignal(str)  # Signal when seek to end clicked
    
    def __init__(self, segment: VideoSegment, presets: List[Dict], parent=None):
        """
        Initialize a segment widget
        
        Args:
            segment: VideoSegment to represent
            presets: List of fade presets
            parent: Parent widget
        """
        # Ensure segment has a valid name
        title = segment.name if segment.name else "Segment"
        super().__init__(title, parent)
        
        # Validate segment attributes
        if not isinstance(segment.start_time, str):
            segment.start_time = "00:00:00"
        if not isinstance(segment.end_time, str):
            segment.end_time = "00:00:10"
        
        self.segment = segment
        self.presets = presets if isinstance(presets, list) else []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components"""
        layout = QFormLayout(self)
        
        # Segment name
        name_str = self.segment.name if hasattr(self.segment, 'name') and self.segment.name else ""
        self.name_edit = QLineEdit(name_str)
        self.name_edit.setPlaceholderText("Segment name (optional)")
        self.name_edit.textChanged.connect(self._update_segment_name)
        layout.addRow("Name:", self.name_edit)
        
        # Time range
        time_layout = QHBoxLayout()
        
        # Start time
        start_time_str = str(self.segment.start_time) if hasattr(self.segment, 'start_time') else "00:00:00"
        self.start_time = QLineEdit(start_time_str)
        self.start_time.setValidator(QRegExpValidator(QRegExp(r'\d{2}:\d{2}:\d{2}(?:[:.]\d{1,3})?')))
        self.start_time.setPlaceholderText("HH:MM:SS")
        self.start_time.textChanged.connect(self._update_segment)
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time)
        
        # Seek to start button
        seek_start_btn = QPushButton("⏺")
        seek_start_btn.setToolTip("Seek to start time")
        seek_start_btn.setMaximumWidth(30)
        seek_start_btn.clicked.connect(lambda: self.seek_start_clicked.emit(self.start_time.text()))
        time_layout.addWidget(seek_start_btn)
        
        layout.addRow("", time_layout)
        
        # End time - on a new row for clearer UI
        end_layout = QHBoxLayout()
        
        end_time_str = str(self.segment.end_time) if hasattr(self.segment, 'end_time') else "00:00:10"
        self.end_time = QLineEdit(end_time_str)
        self.end_time.setValidator(QRegExpValidator(QRegExp(r'\d{2}:\d{2}:\d{2}(?:[:.]\d{1,3})?')))
        self.end_time.setPlaceholderText("HH:MM:SS")
        self.end_time.textChanged.connect(self._update_segment)
        end_layout.addWidget(QLabel("End:"))
        end_layout.addWidget(self.end_time)
        
        # Seek to end button
        seek_end_btn = QPushButton("⏺")
        seek_end_btn.setToolTip("Seek to end time")
        seek_end_btn.setMaximumWidth(30)
        seek_end_btn.clicked.connect(lambda: self.seek_end_clicked.emit(self.end_time.text()))
        end_layout.addWidget(seek_end_btn)
        
        layout.addRow("", end_layout)
        
        # Duration display (calculated)
        self.duration_label = QLabel("0.0 seconds")
        layout.addRow("Duration:", self.duration_label)
        self._update_duration_display()
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addRow(separator)
        
        # Fade presets
        self.preset_combo = QComboBox()
        self._populate_presets()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        layout.addRow("Fade Preset:", self.preset_combo)
        
        # Fade durations
        fade_layout = QHBoxLayout()
        
        # Fade in
        self.fade_in = QDoubleSpinBox()
        self.fade_in.setRange(0, 10)
        self.fade_in.setSingleStep(0.1)
        try:
            fade_in_value = float(self.segment.fade_in_duration) if hasattr(self.segment, 'fade_in_duration') else 0.5
            self.fade_in.setValue(fade_in_value)
        except (ValueError, TypeError):
            self.fade_in.setValue(0.5)
        self.fade_in.setSuffix(" sec")
        self.fade_in.valueChanged.connect(self._update_segment)
        fade_layout.addWidget(QLabel("In:"))
        fade_layout.addWidget(self.fade_in)
        
        # Fade out
        self.fade_out = QDoubleSpinBox()
        self.fade_out.setRange(0, 10)
        self.fade_out.setSingleStep(0.1)
        try:
            fade_out_value = float(self.segment.fade_out_duration) if hasattr(self.segment, 'fade_out_duration') else 0.5
            self.fade_out.setValue(fade_out_value)
        except (ValueError, TypeError):
            self.fade_out.setValue(0.5)
        self.fade_out.setSuffix(" sec")
        self.fade_out.valueChanged.connect(self._update_segment)
        fade_layout.addWidget(QLabel("Out:"))
        fade_layout.addWidget(self.fade_out)
        
        layout.addRow("Fade Durations:", fade_layout)
        
        # Add a separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addRow(separator2)
        
        # Bottom buttons
        buttons_layout = QHBoxLayout()
        
        # Remove button
        remove_button = QPushButton("Remove Segment")
        remove_button.clicked.connect(lambda: self.remove_clicked.emit(self))
        buttons_layout.addWidget(remove_button)
        
        # Preview button
        preview_button = QPushButton("Preview Segment")
        preview_button.clicked.connect(self._preview_segment)
        buttons_layout.addWidget(preview_button)
        
        layout.addRow("", buttons_layout)
    
    def _populate_presets(self):
        """Populate the presets combo box"""
        self.preset_combo.clear()
        self.preset_combo.addItem("Custom")
        
        for preset in self.presets:
            name = preset.get("name", "Unknown")
            fade_in = preset.get("in", 0.0)
            fade_out = preset.get("out", 0.0)
            self.preset_combo.addItem(f"{name} (In: {fade_in}s, Out: {fade_out}s)")
            
            # Select if matches current fade settings
            if (preset.get("in") == self.segment.fade_in_duration and 
                preset.get("out") == self.segment.fade_out_duration):
                self.preset_combo.setCurrentText(f"{name} (In: {fade_in}s, Out: {fade_out}s)")
    
    def _on_preset_changed(self, index):
        """Handle preset selection change"""
        if index == 0:  # Custom
            return
        
        preset = self.presets[index - 1]  # -1 because "Custom" is at index 0
        
        self.fade_in.setValue(preset.get("in", 0.0))
        self.fade_out.setValue(preset.get("out", 0.0))
        
        self._update_segment()
    
    def _update_segment(self):
        """Update the segment with current values"""
        # Validate timecodes
        start_time = self.start_time.text()
        end_time = self.end_time.text()
        
        if validate_timecode(start_time) and validate_timecode(end_time):
            self.segment.start_time = start_time
            self.segment.end_time = end_time
        
        # Update fade durations
        self.segment.fade_in_duration = self.fade_in.value()
        self.segment.fade_out_duration = self.fade_out.value()
        
        # Update duration display
        self._update_duration_display()
    
    def _update_duration_display(self):
        """Update the duration display label"""
        try:
            duration = self.segment.duration
            self.duration_label.setText(f"{duration:.1f} seconds")
        except Exception:
            self.duration_label.setText("Invalid duration")
    
    def _update_segment_name(self):
        """Update the segment name"""
        name = self.name_edit.text()
        self.segment.name = name if name else None
        
        # Update the group box title
        title = name if name else "Segment"
        self.setTitle(title)
    
    def _preview_segment(self):
        """Preview this segment by setting the preview to the start time"""
        self.seek_start_clicked.emit(self.start_time.text())
    
    def get_segment(self) -> VideoSegment:
        """
        Get the current segment
        
        Returns:
            VideoSegment: The current segment
        """
        return self.segment


class TrimPanel(QWidget):
    """Panel for managing video trim segments"""
    
    # Signals
    segment_added = pyqtSignal(VideoSegment)
    segment_removed = pyqtSignal(int)
    segment_seek_requested = pyqtSignal(str)
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the trim panel
        
        Args:
            config_manager: Configuration manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.segment_widgets: List[SegmentWidget] = []
        self.enabled = True
        
        # Load fade presets
        self.fade_presets = self.config_manager.get_preset_fades()
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components"""
        layout = QVBoxLayout(self)
        
        # Panel title
        title_label = QLabel("Trim Segments")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # Top controls
        top_controls = QHBoxLayout()
        
        # Add Segment button
        self.add_button = QPushButton("Add Segment")
        self.add_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.add_button.clicked.connect(self.add_segment)
        top_controls.addWidget(self.add_button)
        
        # Fade presets management
        preset_button = QPushButton("Manage Fade Presets")
        preset_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        preset_button.clicked.connect(self._manage_presets)
        top_controls.addWidget(preset_button)
        
        layout.addLayout(top_controls)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Instructions
        instructions = QLabel("Add trim segments by clicking 'Add Segment'. Set start and end times, and add fade effects as needed.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Scroll area for segments
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.segments_container = QWidget()
        self.segments_layout = QVBoxLayout(self.segments_container)
        self.segments_layout.setAlignment(Qt.AlignTop)
        self.segments_layout.setSpacing(10)
        
        scroll_area.setWidget(self.segments_container)
        layout.addWidget(scroll_area, 1)  # Give the scroll area all available space
    
    def set_enabled(self, enabled: bool):
        """
        Enable or disable the panel
        
        Args:
            enabled: True to enable, False to disable
        """
        self.enabled = enabled
        self.add_button.setEnabled(enabled)
        
        for widget in self.segment_widgets:
            widget.setEnabled(enabled)
    
    def add_segment(self, start_time="00:00:00", end_time="00:00:10"):
        """
        Add a new segment
        
        Args:
            start_time: Initial start time
            end_time: Initial end time
        """
        if not self.enabled:
            return
        
        # Ensure start_time and end_time are strings
        if not isinstance(start_time, str):
            start_time = "00:00:00"
        if not isinstance(end_time, str):
            end_time = "00:00:10"
            
        # Get fade durations with default values
        try:
            fade_in = float(self.config_manager.get("default_fade_in", 0.5))
        except (ValueError, TypeError):
            fade_in = 0.5
            
        try:
            fade_out = float(self.config_manager.get("default_fade_out", 0.5))
        except (ValueError, TypeError):
            fade_out = 0.5
        
        # Create a new segment
        segment_count = len(self.segment_widgets) + 1
        segment = VideoSegment(
            start_time=start_time,
            end_time=end_time,
            fade_in_duration=fade_in,
            fade_out_duration=fade_out,
            name=f"Segment {segment_count}"
        )
        
        # Create and add the widget
        widget = SegmentWidget(segment, self.fade_presets)
        widget.remove_clicked.connect(self._remove_segment)
        widget.seek_start_clicked.connect(self.segment_seek_requested)
        widget.seek_end_clicked.connect(self.segment_seek_requested)
        
        self.segments_layout.addWidget(widget)
        self.segment_widgets.append(widget)
        
        # Emit the signal
        self.segment_added.emit(segment)
    
    def clear_segments(self):
        """Remove all segments"""
        # Remove all widgets
        for widget in self.segment_widgets:
            self.segments_layout.removeWidget(widget)
            widget.deleteLater()
        
        self.segment_widgets.clear()
    
    def _remove_segment(self, widget: SegmentWidget):
        """
        Remove a segment
        
        Args:
            widget: The widget to remove
        """
        # Find the index
        index = self.segment_widgets.index(widget)
        
        # Remove the widget
        self.segments_layout.removeWidget(widget)
        self.segment_widgets.remove(widget)
        widget.deleteLater()
        
        # Emit the signal
        self.segment_removed.emit(index)
    
    def _manage_presets(self):
        """Open dialog to manage fade presets"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Fade Presets")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel("Manage fade presets to quickly apply common fade effects to your segments.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # List of presets
        preset_list = QListWidget()
        for preset in self.fade_presets:
            preset_list.addItem(f"{preset.get('name')} (In: {preset.get('in', 0)}s, Out: {preset.get('out', 0)}s)")
        
        layout.addWidget(preset_list)
        
        # Buttons for managing presets
        buttons_layout = QHBoxLayout()
        
        add_button = QPushButton("Add")
        add_button.clicked.connect(lambda: self._add_preset(preset_list))
        buttons_layout.addWidget(add_button)
        
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(lambda: self._edit_preset(preset_list))
        buttons_layout.addWidget(edit_button)
        
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self._remove_preset(preset_list))
        buttons_layout.addWidget(remove_button)
        
        layout.addLayout(buttons_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        # Show dialog
        dialog.exec_()
        
        # Update all segment widgets with new presets
        for widget in self.segment_widgets:
            widget.presets = self.fade_presets
            widget._populate_presets()
    
    def _add_preset(self, preset_list):
        """Add a new fade preset"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Fade Preset")
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        # Name input
        name_edit = QLineEdit()
        form_layout.addRow("Name:", name_edit)
        
        # Fade in duration
        fade_in_edit = QDoubleSpinBox()
        fade_in_edit.setRange(0, 10)
        fade_in_edit.setSingleStep(0.1)
        fade_in_edit.setValue(0.5)
        fade_in_edit.setSuffix(" sec")
        form_layout.addRow("Fade In:", fade_in_edit)
        
        # Fade out duration
        fade_out_edit = QDoubleSpinBox()
        fade_out_edit.setRange(0, 10)
        fade_out_edit.setSingleStep(0.1)
        fade_out_edit.setValue(0.5)
        fade_out_edit.setSuffix(" sec")
        form_layout.addRow("Fade Out:", fade_out_edit)
        
        layout.addLayout(form_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog
        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text()
            fade_in = fade_in_edit.value()
            fade_out = fade_out_edit.value()
            
            if name:
                # Add preset
                new_preset = {
                    "name": name,
                    "in": fade_in,
                    "out": fade_out
                }
                
                self.fade_presets.append(new_preset)
                preset_list.addItem(f"{name} (In: {fade_in}s, Out: {fade_out}s)")
                
                # Save to config
                self.config_manager.set("preset_fades", self.fade_presets)
    
    def _edit_preset(self, preset_list):
        """Edit a fade preset"""
        selected_index = preset_list.currentRow()
        
        if selected_index == -1 or selected_index >= len(self.fade_presets):
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Fade Preset")
        
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        # Get current preset
        preset = self.fade_presets[selected_index]
        
        # Name input
        name_edit = QLineEdit(preset.get("name", ""))
        form_layout.addRow("Name:", name_edit)
        
        # Fade in duration
        fade_in_edit = QDoubleSpinBox()
        fade_in_edit.setRange(0, 10)
        fade_in_edit.setSingleStep(0.1)
        fade_in_edit.setValue(preset.get("in", 0.5))
        fade_in_edit.setSuffix(" sec")
        form_layout.addRow("Fade In:", fade_in_edit)
        
        # Fade out duration
        fade_out_edit = QDoubleSpinBox()
        fade_out_edit.setRange(0, 10)
        fade_out_edit.setSingleStep(0.1)
        fade_out_edit.setValue(preset.get("out", 0.5))
        fade_out_edit.setSuffix(" sec")
        form_layout.addRow("Fade Out:", fade_out_edit)
        
        layout.addLayout(form_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog
        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text()
            fade_in = fade_in_edit.value()
            fade_out = fade_out_edit.value()
            
            if name:
                # Update preset
                self.fade_presets[selected_index] = {
                    "name": name,
                    "in": fade_in,
                    "out": fade_out
                }
                
                # Update list item
                preset_list.item(selected_index).setText(f"{name} (In: {fade_in}s, Out: {fade_out}s)")
                
                # Save to config
                self.config_manager.set("preset_fades", self.fade_presets)
    
    def _remove_preset(self, preset_list):
        """Remove a fade preset"""
        selected_index = preset_list.currentRow()
        
        if selected_index == -1 or selected_index >= len(self.fade_presets):
            return
        
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the preset '{self.fade_presets[selected_index].get('name')}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # Remove preset
            del self.fade_presets[selected_index]
            preset_list.takeItem(selected_index)
            
            # Save to config
            self.config_manager.set("preset_fades", self.fade_presets)
    
    def get_all_segments(self) -> List[VideoSegment]:
        """
        Get all segments
        
        Returns:
            List[VideoSegment]: List of all segments
        """
        return [widget.get_segment() for widget in self.segment_widgets]
