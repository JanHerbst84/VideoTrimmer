"""
Main window for the YouTube_Trimmer application
"""
import os
from typing import List, Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QLabel, QAction, QMenu,
    QMessageBox, QSplitter, QStatusBar
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

from ui.trim_panel import TrimPanel
from ui.preview_panel import PreviewPanel
from utils.config_manager import ConfigManager
from services.video_processor import VideoProcessor
from models.video_segment import VideoSegment


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize state
        self.config_manager = ConfigManager()
        self.video_processor: Optional[VideoProcessor] = None
        self.current_file_path: Optional[str] = None
        self.segments: List[VideoSegment] = []
        
        # Set up UI
        self.setWindowTitle("YouTube Trimmer")
        self.resize(1000, 700)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        
        # Update UI state
        self._update_ui_state()
    
    def _setup_ui(self):
        """Set up the main UI components"""
        # Create main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Create top bar with file controls
        top_bar = QHBoxLayout()
        
        self.open_button = QPushButton("Open Video")
        self.open_button.clicked.connect(self._open_video)
        top_bar.addWidget(self.open_button)
        
        top_bar.addStretch()
        
        self.process_button = QPushButton("Process Video")
        self.process_button.clicked.connect(self._process_video)
        self.process_button.setEnabled(False)
        top_bar.addWidget(self.process_button)
        
        main_layout.addLayout(top_bar)
        
        # Create splitter for preview and trim panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Create preview panel
        self.preview_panel = PreviewPanel()
        splitter.addWidget(self.preview_panel)
        
        # Create trim panel
        self.trim_panel = TrimPanel(self.config_manager)
        self.trim_panel.segment_added.connect(self._on_segment_added)
        self.trim_panel.segment_removed.connect(self._on_segment_removed)
        self.trim_panel.segment_seek_requested.connect(self._on_segment_seek)
        splitter.addWidget(self.trim_panel)
        
        # Set initial sizes
        splitter.setSizes([500, 500])
        
        main_layout.addWidget(splitter, 1)  # Give the splitter all available space
    
    def _setup_menu(self):
        """Set up the application menu"""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        open_action = QAction("&Open Video...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_video)
        file_menu.addAction(open_action)
        
        # Recent files submenu
        self.recent_menu = QMenu("Recent Files", self)
        file_menu.addMenu(self.recent_menu)
        self._update_recent_files_menu()
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")
        
        add_segment_action = QAction("&Add Segment", self)
        add_segment_action.setShortcut("Ctrl+N")
        add_segment_action.triggered.connect(self.trim_panel.add_segment)
        edit_menu.addAction(add_segment_action)
        
        edit_menu.addSeparator()
        
        preferences_action = QAction("&Preferences...", self)
        preferences_action.triggered.connect(self._show_preferences)
        edit_menu.addAction(preferences_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_statusbar(self):
        """Set up the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.file_info_label = QLabel("")
        self.status_bar.addPermanentWidget(self.file_info_label)
    
    def _update_recent_files_menu(self):
        """Update the recent files menu"""
        self.recent_menu.clear()
        
        recent_files = self.config_manager.get("recent_files", [])
        
        if not recent_files:
            no_recent_action = QAction("No Recent Files", self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
            return
        
        for path in recent_files:
            action = QAction(os.path.basename(path), self)
            action.setData(path)
            action.triggered.connect(self._open_recent_file)
            self.recent_menu.addAction(action)
        
        self.recent_menu.addSeparator()
        
        clear_action = QAction("Clear Recent Files", self)
        clear_action.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(clear_action)
    
    def _update_ui_state(self):
        """Update UI elements based on current state"""
        has_video = self.video_processor is not None
        has_segments = len(self.segments) > 0
        
        self.process_button.setEnabled(has_video and has_segments)
        self.trim_panel.set_enabled(has_video)
        
        # Update file info in status bar
        if has_video:
            filename = os.path.basename(self.current_file_path)
            duration = self.video_processor.duration
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            
            self.file_info_label.setText(
                f"{filename} ({hours:02d}:{minutes:02d}:{seconds:02d})"
            )
        else:
            self.file_info_label.setText("")
    
    def _open_video(self):
        """Open a video file"""
        initial_dir = self.config_manager.get("output_directory", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            initial_dir,
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        
        if not file_path:
            return
        
        self._load_video(file_path)
    
    def _load_video(self, file_path: str):
        """Load a video file"""
        try:
            self.status_label.setText(f"Loading {os.path.basename(file_path)}...")
            
            # Clean up existing processor
            if self.video_processor:
                self.video_processor.close()
            
            # Create new processor
            self.video_processor = VideoProcessor(file_path)
            self.current_file_path = file_path
            
            # Update config
            self.config_manager.add_recent_file(file_path)
            self._update_recent_files_menu()
            
            # Clear existing segments
            self.segments.clear()
            self.trim_panel.clear_segments()
            
            # Update preview panel
            self.preview_panel.set_video(file_path, self.video_processor)
            
            self.status_label.setText(f"Loaded {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {str(e)}")
            self.status_label.setText("Error loading video")
            return
        
        # Update UI state
        self._update_ui_state()
    
    def _open_recent_file(self):
        """Handle opening a file from the recent files menu"""
        action = self.sender()
        if action:
            file_path = action.data()
            if os.path.exists(file_path):
                self._load_video(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"The file {file_path} no longer exists."
                )
                
                # Remove from recent files
                recent_files = self.config_manager.get("recent_files", [])
                if file_path in recent_files:
                    recent_files.remove(file_path)
                    self.config_manager.set("recent_files", recent_files)
                    self._update_recent_files_menu()
    
    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.config_manager.set("recent_files", [])
        self._update_recent_files_menu()
    
    def _process_video(self):
        """Process the video with the current segments"""
        if not self.video_processor or not self.segments:
            return
        
        # Get output file path
        initial_dir = self.config_manager.get("output_directory", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.path.dirname(self.current_file_path)
        
        input_filename = os.path.basename(self.current_file_path)
        base_name, ext = os.path.splitext(input_filename)
        default_output = f"{base_name}_trimmed{ext}"
        
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Trimmed Video",
            os.path.join(initial_dir, default_output),
            "Video Files (*.mp4);;All Files (*)"
        )
        
        if not output_path:
            return
        
        # Remember the output directory
        self.config_manager.set("output_directory", os.path.dirname(output_path))
        
        try:
            self.status_label.setText("Processing video...")
            self.process_button.setEnabled(False)
            
            # Process the video
            self.video_processor.process_segments(self.segments, output_path)
            
            self.status_label.setText("Video processing complete")
            QMessageBox.information(
                self,
                "Success",
                f"Video processed successfully and saved to:\n{output_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process video: {str(e)}")
            self.status_label.setText("Error processing video")
        finally:
            self.process_button.setEnabled(True)
    
    def _on_segment_added(self, segment: VideoSegment):
        """Handle a new segment being added"""
        self.segments.append(segment)
        self._update_ui_state()
    
    def _on_segment_removed(self, segment_index: int):
        """Handle a segment being removed"""
        if 0 <= segment_index < len(self.segments):
            del self.segments[segment_index]
            self._update_ui_state()
    
    def _on_segment_seek(self, timecode: str):
        """Handle a request to seek to a specific timecode"""
        if self.video_processor:
            self.preview_panel.seek_to_timecode(timecode)
    
    def _show_preferences(self):
        """Show the preferences dialog"""
        # TODO: Implement preferences dialog
        QMessageBox.information(
            self,
            "Preferences",
            "Preferences dialog not yet implemented."
        )
    
    def _show_about(self):
        """Show the about dialog"""
        QMessageBox.about(
            self,
            "About YouTube Trimmer",
            "YouTube Trimmer\n\n"
            "A video trimming application with fade effects.\n\n"
            "Version 1.0.0"
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clean up resources
        if self.video_processor:
            self.video_processor.close()
        
        # Accept the event
        event.accept()