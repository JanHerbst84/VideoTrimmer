"""
Utility functions for handling timecodes
"""
import re
from typing import Union, Tuple


def validate_timecode(timecode: str) -> bool:
    """
    Validates if the provided string is in HH:MM:SS format
    
    Args:
        timecode: String in the format HH:MM:SS, HH:MM:SS.mmm, or HH:MM:SS:mmm
        
    Returns:
        bool: True if format is valid, False otherwise
    """
    # Match multiple formats: HH:MM:SS, HH:MM:SS.mmm, and HH:MM:SS:mmm
    pattern = r'^\d{2}:\d{2}:\d{2}(?:[:.]\d{1,3})?$'
    return bool(re.match(pattern, timecode))


def timecode_to_seconds(timecode: str) -> float:
    """
    Converts HH:MM:SS format to seconds
    
    Args:
        timecode: String in the format HH:MM:SS, HH:MM:SS.mmm, or HH:MM:SS:mmm
        
    Returns:
        float: Total seconds
    """
    if not validate_timecode(timecode):
        raise ValueError(f"Invalid timecode format: {timecode}. Expected HH:MM:SS")
    
    # Handle different formats
    if timecode.count(':') == 3:  # Format with milliseconds using colon: HH:MM:SS:mmm
        parts = timecode.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
    else:  # Standard format: HH:MM:SS or HH:MM:SS.mmm
        parts = timecode.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        
        # Handle decimal seconds if present
        if '.' in parts[2]:
            seconds = float(parts[2])
        else:
            seconds = int(parts[2])
        
        return hours * 3600 + minutes * 60 + seconds


def seconds_to_timecode(seconds: Union[int, float]) -> str:
    """
    Converts seconds to HH:MM:SS format
    
    Args:
        seconds: Number of seconds
        
    Returns:
        str: Formatted timecode in HH:MM:SS format
    """
    if seconds < 0:
        raise ValueError("Seconds cannot be negative")
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    # Format with leading zeros
    if isinstance(secs, int) or secs.is_integer():
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"
    else:
        # Handle decimal seconds with a dot, not a colon
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def parse_timecode_range(range_str: str) -> Tuple[float, float]:
    """
    Parse a range of timecodes in the format "HH:MM:SS-HH:MM:SS"
    
    Args:
        range_str: String in the format "HH:MM:SS-HH:MM:SS"
        
    Returns:
        tuple: (start_seconds, end_seconds)
    """
    parts = range_str.split('-')
    if len(parts) != 2:
        raise ValueError(f"Invalid timecode range: {range_str}. Expected format HH:MM:SS-HH:MM:SS")
    
    start_timecode = parts[0].strip()
    end_timecode = parts[1].strip()
    
    start_seconds = timecode_to_seconds(start_timecode)
    end_seconds = timecode_to_seconds(end_timecode)
    
    if end_seconds <= start_seconds:
        raise ValueError(f"End time must be after start time. Got {start_timecode} to {end_timecode}")
    
    return (start_seconds, end_seconds)
