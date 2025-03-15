"""
Test script to check if OpenCV can properly read video frames
"""
import os
import sys
import cv2
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer

class VideoTester(QMainWindow):
    """Simple application to test video preview"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Video Frame Tester")
        self.setGeometry(100, 100, 800, 600)
        
        self.video_path = ""
        self.cap = None
        self.current_frame = 0
        self.total_frames = 0
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Preview area
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("No video loaded")
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        layout.addWidget(self.preview_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open Video")
        self.open_button.clicked.connect(self._open_video)
        controls_layout.addWidget(self.open_button)
        
        self.prev_button = QPushButton("Previous Frame")
        self.prev_button.clicked.connect(self._prev_frame)
        self.prev_button.setEnabled(False)
        controls_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("Next Frame")
        self.next_button.clicked.connect(self._next_frame)
        self.next_button.setEnabled(False)
        controls_layout.addWidget(self.next_button)
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._toggle_play)
        self.play_button.setEnabled(False)
        controls_layout.addWidget(self.play_button)
        
        layout.addLayout(controls_layout)
        
        # Status
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        # Timer for playback
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.timer.setInterval(33)  # ~30fps
        
    def _open_video(self):
        """Open a video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        
        if not file_path:
            return
        
        self.video_path = file_path
        self._load_video()
        
    def _load_video(self):
        """Load the selected video"""
        if not os.path.exists(self.video_path):
            self.status_label.setText("Error: File does not exist")
            return
        
        # Close any existing video
        if self.cap:
            self.cap.release()
            self.cap = None
        
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            
            if not self.cap.isOpened():
                self.status_label.setText("Error: Could not open video")
                return
            
            # Get video properties
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.status_label.setText(
                f"Video loaded: {os.path.basename(self.video_path)} | "
                f"Frames: {self.total_frames} | "
                f"FPS: {fps:.2f} | "
                f"Resolution: {width}x{height}"
            )
            
            # Reset frame counter
            self.current_frame = 0
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            
            # Enable controls
            self.prev_button.setEnabled(True)
            self.next_button.setEnabled(True)
            self.play_button.setEnabled(True)
            
            # Show first frame
            self._show_current_frame()
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            if self.cap:
                self.cap.release()
                self.cap = None
    
    def _show_current_frame(self):
        """Display the current frame"""
        if not self.cap:
            return
        
        # Seek to frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        
        # Read frame
        ret, frame = self.cap.read()
        
        if not ret:
            self.status_label.setText(f"Error: Could not read frame {self.current_frame}")
            return
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Create and set pixmap
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        
        # Update status
        self.status_label.setText(
            f"Frame: {self.current_frame}/{self.total_frames} | "
            f"File: {os.path.basename(self.video_path)}"
        )
    
    def _next_frame(self):
        """Go to next frame"""
        if not self.cap:
            return
        
        self.current_frame = min(self.current_frame + 1, self.total_frames - 1)
        self._show_current_frame()
        
        # Stop playback if we've reached the end
        if self.current_frame >= self.total_frames - 1:
            self.timer.stop()
            self.play_button.setText("Play")
    
    def _prev_frame(self):
        """Go to previous frame"""
        if not self.cap:
            return
        
        self.current_frame = max(self.current_frame - 1, 0)
        self._show_current_frame()
    
    def _toggle_play(self):
        """Toggle playback"""
        if not self.cap:
            return
        
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("Play")
        else:
            if self.current_frame >= self.total_frames - 1:
                self.current_frame = 0
            self.timer.start()
            self.play_button.setText("Pause")
            
    def closeEvent(self, event):
        """Handle window close event"""
        if self.cap:
            self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoTester()
    window.show()
    sys.exit(app.exec_())
