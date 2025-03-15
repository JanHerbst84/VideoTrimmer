"""
Data model for video segment with timecodes and fade information
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoSegment:
    """Represents a segment of video to be trimmed with optional fade effects"""
    
    # Timecodes in HH:MM:SS format
    start_time: str
    end_time: str
    
    # Fade durations in seconds
    fade_in_duration: float = 0.0
    fade_out_duration: float = 0.0
    
    # Optional segment name for identifying multiple segments
    name: Optional[str] = None
    
    def __post_init__(self):
        """Validate the data types after initialization"""
        # Ensure start_time and end_time are strings
        if not isinstance(self.start_time, str):
            self.start_time = "00:00:00"
        
        if not isinstance(self.end_time, str):
            self.end_time = "00:00:10"
        
        # Ensure fade durations are floats
        if not isinstance(self.fade_in_duration, float):
            self.fade_in_duration = float(self.fade_in_duration)
        
        if not isinstance(self.fade_out_duration, float):
            self.fade_out_duration = float(self.fade_out_duration)
    
    @property
    def duration(self) -> float:
        """Calculate segment duration in seconds"""
        return self.time_to_seconds(self.end_time) - self.time_to_seconds(self.start_time)
    
    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        """Convert HH:MM:SS format to seconds"""
        try:
            # Handle both formats: HH:MM:SS and HH:MM:SS:mmm or HH:MM:SS.mmm
            if time_str.count(':') == 3:  # Format with milliseconds using colon: HH:MM:SS:mmm
                h, m, s, ms = time_str.split(':')
                return float(h) * 3600 + float(m) * 60 + float(s) + float(ms) / 1000
            elif '.' in time_str:  # Format with milliseconds using dot: HH:MM:SS.mmm
                parts = time_str.split(':')
                h, m = float(parts[0]), float(parts[1])
                s = float(parts[2])
                return h * 3600 + m * 60 + s
            else:  # Basic format: HH:MM:SS
                h, m, s = map(float, time_str.split(':'))
                return h * 3600 + m * 60 + s
        except (ValueError, AttributeError):
            # Return 0 if conversion fails
            return 0.0
    
    @staticmethod
    def seconds_to_time(seconds: float) -> str:
        """Convert seconds to HH:MM:SS format"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        
        # Format with leading zeros
        if s.is_integer():
            return f"{h:02d}:{m:02d}:{int(s):02d}"
        else:
            # Format with decimal seconds
            return f"{h:02d}:{m:02d}:{s:06.3f}"
