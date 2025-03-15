"""
Panel for video preview with internal playback using OpenCV
"""
import os
import cv2
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QLineEdit, QFormLayout, QStyle,
    QSizePolicy, QMessageBox, QFrame
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
        self.setText("No video loaded")
    
    def display_frame(self, frame):
        """
        Display a video frame (OpenCV format)
        
        Args:
            frame: OpenCV frame (numpy array)
        """
        if frame is None:
            self.setText("No frame available")
            return
            
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Create QImage from frame
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Scale pixmap to fit widget while preserving aspect ratio
            pixmap = QPixmap.fromImage(img)
            scaled_pixmap = pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Set pixmap and clear text
            self.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.setText(f"Error displaying frame: {str(e)}")
    
    def clear(self):
        """Clear the display"""
        self.clear()
        self.setText("No video loaded")
    
    def resizeEvent(self, event):
        """Handle resize events"""
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
        self.duration = 0.0
        
        # OpenCV video capture
        self.video_capture = None
        self.fps = 0.0
        self.total_frames = 0
        
        # Timer for video playback
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self._update_frame)
        
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
        time_layout.addWidget(QLabel("Current Position:"))
        time_layout.addWidget(self.current_timecode)
        
        # Add duration display
        self.duration_label = QLabel("/ 00:00:00")
        time_layout.addWidget(self.duration_label)
        
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
        self.play_button.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self.play_button)
        
        # Next frame button
        self.next_frame_button = QPushButton()
        self.next_frame_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_frame_button.clicked.connect(self._next_frame)
        controls_layout.addWidget(self.next_frame_button)
        
        # Playback speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(25, 200)  # 25% to 200% speed
        self.speed_slider.setValue(100)  # Default 100% speed
        self.speed_slider.valueChanged.connect(self._set_playback_speed)
        speed_layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("100%")
        speed_layout.addWidget(self.speed_label)
        
        # Add speed control to main controls
        controls_layout.addStretch()
        controls_layout.addLayout(speed_layout)
        
        # Add to main layout
        layout.addLayout(controls_layout)
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Status display
        self.status_label = QLabel("No video loaded")
        layout.addWidget(self.status_label)
        
        # Disable controls initially
        self._update_controls_state(False)
    
    def set_video(self, video_path: str, processor: VideoProcessor):
        """
        Set the video to preview
        
        Args:
            video_path: Path to the video file
            processor: VideoProcessor instance
        """
        # Close any existing video
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        
        # Store references
        self.video_path = video_path
        self.video_processor = processor
        
        try:
            # Open the video with OpenCV
            self.video_capture = cv2.VideoCapture(video_path)
            
            if not self.video_capture.isOpened():
                raise RuntimeError(f"Could not open video: {video_path}")
            
            # Get video properties
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = self.total_frames / self.fps if self.fps > 0 else 0
            
            # Set timer interval based on FPS
            self._set_playback_speed(self.speed_slider.value())
            
            # Update duration display
            self.duration_label.setText(f"/ {seconds_to_timecode(self.duration)}")
            
            # Reset current time
            self.current_time = 0.0
            
            # Update UI
            self.status_label.setText(f"Loaded: {os.path.basename(video_path)} ({self.fps:.2f} FPS)")
            self._update_controls_state(True)
            
            # Seek to beginning and show first frame
            self._seek_to_time(0.0)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {str(e)}")
            self.status_label.setText("Error loading video")
            return
    
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
        self.speed_slider.setEnabled(enabled)
        
        # Reset play/pause button icon
        self.is_playing = False
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playback_timer.stop()
    
    def _toggle_play(self):
        """Toggle play/pause state"""
        if not self.video_capture:
            return
        
        if self.is_playing:
            # Pause playback
            self.playback_timer.stop()
            self.is_playing = False
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            # Start playback
            if self.current_time >= self.duration:
                # If at the end, loop back to beginning
                self._seek_to_time(0.0)
            
            self.playback_timer.start()
            self.is_playing = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
    
    def _set_playback_speed(self, speed_percent):
        """
        Set the playback speed
        
        Args:
            speed_percent: Speed as a percentage (25-200)
        """
        if self.fps > 0:
            # Calculate frame interval in milliseconds
            base_interval = 1000.0 / self.fps  # ms per frame at 100% speed
            interval = base_interval * (100.0 / speed_percent)
            self.playback_timer.setInterval(int(interval))
            
            # Update speed label
            self.speed_label.setText(f"{speed_percent}%")
    
    def _update_frame(self):
        """Update the current frame during playback"""
        if not self.video_capture or not self.is_playing:
            return
        
        # Get current position
        current_frame = int(self.current_time * self.fps)
        next_frame = current_frame + 1
        
        if next_frame >= self.total_frames:
            # End of video reached
            self._toggle_play()  # Stop playback
            return
        
        # Seek to next frame
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
        ret, frame = self.video_capture.read()
        
        if not ret:
            # Error reading frame
            self._toggle_play()  # Stop playback
            return
        
        # Update current time
        self.current_time = next_frame / self.fps
        
        # Update UI
        self._update_ui_for_time(self.current_time)
        
        # Display the frame
        self.preview_widget.display_frame(frame)
    
    def _update_ui_for_time(self, seconds):
        """
        Update UI elements for a given time
        
        Args:
            seconds: Time in seconds
        """
        # Update timecode display
        if not self.current_timecode.hasFocus():
            self.current_timecode.setText(seconds_to_timecode(seconds))
        
        # Update slider position
        if self.duration > 0:
            slider_position = int((seconds / self.duration) * 1000)
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(slider_position)
            self.timeline_slider.blockSignals(False)
    
    def _open_in_external_player(self):
        """Open the video in the system's default media player"""
        if not self.video_path:
            return
        
        try:
            import os
            os.startfile(self.video_path)
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Player Error",
                f"Could not open the video in an external player. Error: {str(e)}"
            )
    
    def _seek_to_current_timecode(self):
        """Seek to the timecode in the input field"""
        timecode = self.current_timecode.text()
        self.seek_to_timecode(timecode)
    
    def seek_to_timecode(self, timecode: str):
        """
        Seek to a specific timecode
        
        Args:
            timecode: Timecode in HH:MM:SS format
        """
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
        if not self.video_capture:
            return
        
        # Clamp to valid range
        seconds = max(0.0, min(seconds, self.duration))
        
        # Calculate frame number
        frame_number = int(seconds * self.fps)
        
        # Seek to frame
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_capture.read()
        
        if not ret:
            self.status_label.setText(f"Error seeking to frame {frame_number}")
            return
        
        # Update current time
        self.current_time = seconds
        
        # Update UI
        self._update_ui_for_time(seconds)
        
        # Display the frame
        self.preview_widget.display_frame(frame)
    
    def _update_timecode_display(self):
        """Update the timecode display"""
        timecode = seconds_to_timecode(self.current_time)
        self.current_timecode.setText(timecode)
    
    def _slider_pressed(self):
        """Handle slider press event"""
        # Pause playback while seeking
        was_playing = self.is_playing
        if was_playing:
            self.playback_timer.stop()
        
        # Store the state to resume after release if needed
        self.timeline_slider.setProperty("was_playing", was_playing)
    
    def _slider_released(self):
        """Handle slider release event"""
        # Get the time from the slider position
        position = self.timeline_slider.value()
        if self.duration > 0:
            seconds = (position / 1000.0) * self.duration
            self._seek_to_time(seconds)
        
        # Resume playback if it was playing before
        was_playing = self.timeline_slider.property("was_playing")
        if was_playing:
            self.playback_timer.start()
            self.is_playing = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
    
    def _slider_moved(self, position):
        """
        Handle slider movement
        
        Args:
            position: New slider position (0-1000)
        """
        # Preview the frame at the slider position
        if self.duration > 0 and self.video_capture:
            seconds = (position / 1000.0) * self.duration
            frame_number = int(seconds * self.fps)
            
            # Seek to frame for preview
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.video_capture.read()
            
            if ret:
                # Display the frame
                self.preview_widget.display_frame(frame)
                
                # Update timecode display (without changing current_time)
                if not self.current_timecode.hasFocus():
                    self.current_timecode.setText(seconds_to_timecode(seconds))
    
    def _prev_frame(self):
        """Go to previous frame"""
        if not self.video_capture:
            return
        
        # Calculate current frame and previous frame
        current_frame = int(self.current_time * self.fps)
        prev_frame = max(0, current_frame - 1)
        
        if prev_frame != current_frame:
            # Seek to previous frame
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, prev_frame)
            ret, frame = self.video_capture.read()
            
            if ret:
                # Update current time
                self.current_time = prev_frame / self.fps
                
                # Update UI
                self._update_ui_for_time(self.current_time)
                
                # Display the frame
                self.preview_widget.display_frame(frame)
    
    def _next_frame(self):
        """Go to next frame"""
        if not self.video_capture:
            return
        
        # Calculate current frame and next frame
        current_frame = int(self.current_time * self.fps)
        next_frame = min(current_frame + 1, self.total_frames - 1)
        
        if next_frame != current_frame:
            # Seek to next frame
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
            ret, frame = self.video_capture.read()
            
            if ret:
                # Update current time
                self.current_time = next_frame / self.fps
                
                # Update UI
                self._update_ui_for_time(self.current_time)
                
                # Display the frame
                self.preview_widget.display_frame(frame)
