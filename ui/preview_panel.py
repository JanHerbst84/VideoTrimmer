"""
Panel for video preview with playback controls
"""
import os
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QLineEdit, QFormLayout, QStyle,
    QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QRegExp, QSize
from PyQt5.QtGui import QPixmap, QImage, QRegExpValidator

from services.video_processor import VideoProcessor
from services.timecode_utils import timecode_to_seconds, seconds_to_timecode


class VideoPreviewWidget(QLabel):
    """Widget for displaying video frames"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: black;")
        
        # Set placeholder image
        self.clear()
    
    def set_frame(self, width: int, height: int, frame_data: bytes):
        """
        Set a video frame
        
        Args:
            width: Frame width
            height: Frame height
            frame_data: RGB frame data
        """
        try:
            # Calculate the correct bytes per line (stride)
            bytes_per_line = width * 3
            
            image = QImage(frame_data, width, height, bytes_per_line, QImage.Format_RGB888)
            if image.isNull():
                print("Failed to create QImage from frame data")
                self.setText("Failed to display frame")
                return
            
            # Scale down the image for better performance
            scaled_width = 640
            scaled_height = int(height * (scaled_width / width))
            
            scaled_image = image.scaled(
                scaled_width, 
                scaled_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
                
            pixmap = QPixmap.fromImage(scaled_image)
            if pixmap.isNull():
                print("Failed to create QPixmap from QImage")
                self.setText("Failed to display frame")
                return
            
            # Scale pixmap to fit the widget while preserving aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error displaying frame: {str(e)}")
            self.setText(f"Error displaying frame: {str(e)}")
            return
    
    def clear(self):
        """Clear the display"""
        self.setText("No video loaded")
    
    def resizeEvent(self, event):
        """Handle resize events to scale the pixmap"""
        if self.pixmap() and not self.pixmap().isNull():
            self.setPixmap(self.pixmap().scaled(
                event.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        super().resizeEvent(event)


class PreviewPanel(QWidget):
    """Panel for video preview with playback controls"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.video_processor: Optional[VideoProcessor] = None
        self.current_time = 0.0
        self.video_path = ""
        self.is_playing = False
        
        # For static frame display
        self.update_interval = 33  # ~30 fps in milliseconds
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(self.update_interval)
        self.update_timer.timeout.connect(self._update_frame)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components"""
        layout = QVBoxLayout(self)
        
        # Video preview widget
        self.preview_widget = VideoPreviewWidget()
        layout.addWidget(self.preview_widget, 1)  # Give it all available space
        
        # Timecode display and seek
        time_layout = QHBoxLayout()
        
        self.current_timecode = QLineEdit("00:00:00")
        self.current_timecode.setValidator(QRegExpValidator(QRegExp(r'\d{2}:\d{2}:\d{2}(?:[:.]\d{1,3})?')))
        self.current_timecode.returnPressed.connect(self._seek_to_current_timecode)
        time_layout.addWidget(self.current_timecode)
        
        seek_button = QPushButton("Seek")
        seek_button.clicked.connect(self._seek_to_current_timecode)
        time_layout.addWidget(seek_button)
        
        # Add Open in External Player button
        external_player_button = QPushButton("Open in External Player")
        external_player_button.clicked.connect(self._open_in_external_player)
        time_layout.addWidget(external_player_button)
        
        layout.addLayout(time_layout)
        
        # Timeline slider
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)  # Use 1000 steps for precision
        self.timeline_slider.setValue(0)
        self.timeline_slider.sliderPressed.connect(self._slider_pressed)
        self.timeline_slider.sliderReleased.connect(self._slider_released)
        self.timeline_slider.sliderMoved.connect(self._slider_moved)
        layout.addWidget(self.timeline_slider)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        
        # Previous frame button
        self.prev_frame_button = QPushButton()
        self.prev_frame_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_frame_button.clicked.connect(self._prev_frame)
        controls_layout.addWidget(self.prev_frame_button)
        
        # Play/pause button
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setToolTip("Open in system media player")
        self.play_button.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self.play_button)
        
        # Next frame button
        self.next_frame_button = QPushButton()
        self.next_frame_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_frame_button.clicked.connect(self._next_frame)
        controls_layout.addWidget(self.next_frame_button)
        
        controls_layout.addStretch()
        
        # Add to main layout
        layout.addLayout(controls_layout)
        
        # Disable controls initially
        self._update_controls_state(False)
    
    def set_video(self, video_path: str, processor: VideoProcessor):
        """
        Set the video to preview
        
        Args:
            video_path: Path to the video file
            processor: VideoProcessor instance
        """
        self.video_path = video_path
        self.video_processor = processor
        self.current_time = 0.0
        
        # Enable controls
        self._update_controls_state(True)
        
        # Update the UI
        self._update_timecode_display()
        self._seek_to_time(0.0)
    
    def _update_controls_state(self, enabled: bool):
        """
        Update the state of the controls
        
        Args:
            enabled: True to enable, False to disable
        """
        self.current_timecode.setEnabled(enabled)
        self.timeline_slider.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        self.prev_frame_button.setEnabled(enabled)
        self.next_frame_button.setEnabled(enabled)
        
        # Reset play/pause button icon
        self.is_playing = False
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.update_timer.stop()
    
    def _toggle_play(self):
        """Toggle play/pause state by opening the system's media player"""
        if not self.video_processor or not self.video_path:
            return
        
        try:
            # Use Windows media player to play the file
            import os
            import subprocess
            
            # Get current time position in milliseconds
            position_ms = int(self.current_time * 1000)
            
            # Open the video in default player
            # Note: Most media players don't support starting at a specific time via command line
            # So we'll just open the video at the beginning
            os.startfile(self.video_path)
            
            # Update UI state
            self.is_playing = False  # We're not controlling playback internally
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.update_timer.stop()
            
            # Inform the user
            print(f"Opened video in system player: {self.video_path}")
            
        except Exception as e:
            print(f"Error opening system player: {str(e)}")
            
            # Show error message to user
            QMessageBox.warning(
                self, 
                "Player Error",
                f"Could not open the video in the system player. Error: {str(e)}"
            )
    
    def _open_in_external_player(self):
        """Open the video in the system's default media player"""
        if not self.video_path:
            return
        
        try:
            import os
            os.startfile(self.video_path)
            print(f"Opened video in system player: {self.video_path}")
        except Exception as e:
            print(f"Error opening external player: {str(e)}")
            
            # Show error message to user
            QMessageBox.warning(
                self, 
                "Player Error",
                f"Could not open the video in an external player. Error: {str(e)}"
            )
    
    def _update_frame(self):
        """Update the current frame during playback"""
        if not self.video_processor or not self.is_playing:
            return
        
        try:
            # Advance time
            self.current_time += self.update_interval / 1000.0
            
            # Check if we've reached the end
            if self.current_time >= self.video_processor.duration:
                self.current_time = 0.0
                self._toggle_play()  # Stop playback
                return
            
            # Update display
            self._update_timecode_display()
            self._update_timeline_slider()
            self._show_frame_at_current_time()
        except Exception as e:
            print(f"Error updating frame: {str(e)}")
            self._toggle_play()  # Stop playback on error
    
    def _seek_to_current_timecode(self):
        """Seek to the timecode in the input field"""
        if not self.video_processor:
            return
        
        timecode = self.current_timecode.text()
        self.seek_to_timecode(timecode)
    
    def seek_to_timecode(self, timecode: str):
        """
        Seek to a specific timecode
        
        Args:
            timecode: Timecode in HH:MM:SS format
        """
        if not self.video_processor:
            return
        
        try:
            seconds = timecode_to_seconds(timecode)
            self._seek_to_time(seconds)
        except ValueError:
            # Invalid timecode, reset display
            self._update_timecode_display()
    
    def _seek_to_time(self, seconds: float):
        """
        Seek to a specific time in seconds
        
        Args:
            seconds: Time in seconds
        """
        if not self.video_processor:
            return
        
        # Clamp to valid range
        seconds = max(0.0, min(seconds, self.video_processor.duration))
        
        self.current_time = seconds
        self._update_timecode_display()
        self._update_timeline_slider()
        self._show_frame_at_current_time()
    
    def _show_frame_at_current_time(self):
        """Show the frame at the current time"""
        if not self.video_processor:
            return
        
        # Convert to timecode
        timecode = seconds_to_timecode(self.current_time)
        
        # Get the frame
        frame_data = self.video_processor.get_frame_at_time(timecode)
        if frame_data:
            width, height, data = frame_data
            self.preview_widget.set_frame(width, height, data)
        else:
            self.preview_widget.setText(f"Could not get frame at {timecode}")
            print(f"Failed to get frame at time {timecode}")
    
    def _update_timecode_display(self):
        """Update the timecode display"""
        if not self.video_processor:
            return
        
        timecode = seconds_to_timecode(self.current_time)
        self.current_timecode.setText(timecode)
    
    def _update_timeline_slider(self):
        """Update the timeline slider position"""
        if not self.video_processor:
            return
        
        # Calculate position (0-1000)
        position = int((self.current_time / self.video_processor.duration) * 1000)
        self.timeline_slider.setValue(position)
    
    def _slider_pressed(self):
        """Handle slider press event"""
        # Pause playback while seeking
        was_playing = self.is_playing
        if was_playing:
            self._toggle_play()
        
        # Store the state to resume after release if needed
        self.timeline_slider.setProperty("was_playing", was_playing)
    
    def _slider_released(self):
        """Handle slider release event"""
        # Get the time from the slider position
        position = self.timeline_slider.value()
        if self.video_processor:
            self.current_time = (position / 1000.0) * self.video_processor.duration
            self._update_timecode_display()
            self._show_frame_at_current_time()
        
        # Resume playback if it was playing before
        was_playing = self.timeline_slider.property("was_playing")
        if was_playing:
            self._toggle_play()
    
    def _slider_moved(self, position):
        """
        Handle slider movement
        
        Args:
            position: New slider position (0-1000)
        """
        # Update time display during dragging
        if self.video_processor:
            time = (position / 1000.0) * self.video_processor.duration
            self.current_timecode.setText(seconds_to_timecode(time))
    
    def _prev_frame(self):
        """Go to previous frame"""
        # Move back by 1/30th of a second
        self._seek_to_time(self.current_time - 1/30.0)
    
    def _next_frame(self):
        """Go to next frame"""
        # Move forward by 1/30th of a second
        self._seek_to_time(self.current_time + 1/30.0)
