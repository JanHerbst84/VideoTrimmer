"""
Video processing service for trimming videos with fades using FFmpeg with absolute timestamps
"""
import os
import cv2
import subprocess
import tempfile
import shutil
from typing import List, Optional, Tuple
from models.video_segment import VideoSegment
from services.timecode_utils import timecode_to_seconds


class VideoProcessor:
    """Handles video processing operations including trimming and applying fades"""
    
    def __init__(self, video_path: str):
        """
        Initialize with a video file path
        
        Args:
            video_path: Path to the video file
        """
        self.video_path = video_path
        self._video_capture = None
        self.duration = 0
        self.fps = 0
        self.width = 0
        self.height = 0
        self.total_frames = 0
        self._frame_cache = {}  # Cache for frequently accessed frames
        self._cache_size_limit = 30  # Maximum number of frames to cache
        self._load_video()
    
    def _load_video(self):
        """Load the video file and get its properties"""
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
        
        try:
            # Use OpenCV to get video properties
            self._video_capture = cv2.VideoCapture(self.video_path)
            
            if not self._video_capture.isOpened():
                raise RuntimeError(f"Could not open video file: {self.video_path}")
                
            self.fps = self._video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self._video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.width = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            self.duration = self.total_frames / self.fps if self.fps > 0 else 0
            
        except Exception as e:
            raise RuntimeError(f"Failed to load video: {str(e)}")
    
    def process_segments(self, segments: List[VideoSegment], output_path: str) -> str:
        """
        Process multiple segments and save to file
        
        Args:
            segments: List of VideoSegment objects to process
            output_path: Path to save the output video
            
        Returns:
            str: Path to the saved file
        """
        if not segments:
            raise ValueError("No segments provided")
        
        # Create temporary directory for segment files
        temp_dir = os.path.join(os.path.dirname(output_path), "temp_segments")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            segment_files = []
            
            # Process each segment to its own file
            for i, segment in enumerate(segments):
                temp_output = os.path.join(temp_dir, f"segment_{i}.mp4")
                
                # Try direct approach with absolute timestamps
                self._direct_absolute_trim(segment, temp_output)
                segment_files.append(temp_output)
            
            # If only one segment, just rename the file
            if len(segment_files) == 1:
                shutil.copy2(segment_files[0], output_path)
            else:
                # Concatenate segments if there are multiple
                self._concatenate_videos(segment_files, output_path)
            
            return output_path
            
        finally:
            # Clean up temporary files
            for file in segment_files:
                if os.path.exists(file):
                    try:
                        os.remove(file)
                    except:
                        pass
            
            # Remove temporary directory
            try:
                os.rmdir(temp_dir)
            except:
                pass
    
    def _direct_absolute_trim(self, segment: VideoSegment, output_path: str) -> str:
        """
        Direct FFmpeg trim with absolute timing for fades
        
        Args:
            segment: VideoSegment object
            output_path: Output path
            
        Returns:
            str: Output path
        """
        try:
            # Get exact timecodes
            start_seconds = segment.time_to_seconds(segment.start_time)
            end_seconds = segment.time_to_seconds(segment.end_time)
            duration = end_seconds - start_seconds
            
            print(f"Segment duration: {duration} seconds")
            print(f"Start time: {start_seconds} seconds")
            print(f"End time: {end_seconds} seconds")
            
            # Use a direct approach that keeps the absolute timestamps
            # This method avoids the seek (-ss) changing the timestamps
            
            # Create a temporary file for the exact trim
            temp_dir = tempfile.mkdtemp()
            trimmed_file = os.path.join(temp_dir, "trimmed.mp4")
            
            try:
                # Step 1: Perform an exact trim with copy codecs
                # This preserves the original timestamps
                trim_cmd = [
                    "ffmpeg", "-y",
                    "-i", self.video_path,
                    "-ss", str(start_seconds),
                    "-to", str(end_seconds),
                    "-c", "copy",
                    trimmed_file
                ]
                
                print(f"Trimming command: {' '.join(trim_cmd)}")
                subprocess.run(trim_cmd, check=True, capture_output=True, text=True)
                
                # Step 2: Apply fades using absolute timestamps
                fade_in_sec = segment.fade_in_duration
                fade_out_sec = segment.fade_out_duration
                
                # Skip fades if they're too large
                if fade_in_sec + fade_out_sec > duration * 0.9:
                    print("Fades are too long for clip duration - disabling fades")
                    fade_in_sec = 0
                    fade_out_sec = 0
                
                # Calculate fade timestamps - these are absolute to the original video
                fade_in_end = start_seconds + fade_in_sec if fade_in_sec > 0 else 0
                fade_out_start = end_seconds - fade_out_sec if fade_out_sec > 0 else 0
                
                print(f"Fade in from {start_seconds}s to {fade_in_end}s")
                print(f"Fade out from {fade_out_start}s to {end_seconds}s")
                
                # Build complex filtergraph for absolute timestamps
                vf_parts = []
                af_parts = []
                
                # Add fades
                if fade_in_sec > 0:
                    vf_parts.append(f"fade=type=in:start_time=0:duration={fade_in_sec}")
                    af_parts.append(f"afade=type=in:start_time=0:duration={fade_in_sec}")
                
                if fade_out_sec > 0:
                    # CRITICAL: Use duration-fade_out_sec as the start time
                    fade_out_rel_start = duration - fade_out_sec
                    vf_parts.append(f"fade=type=out:start_time={fade_out_rel_start}:duration={fade_out_sec}")
                    af_parts.append(f"afade=type=out:start_time={fade_out_rel_start}:duration={fade_out_sec}")
                
                # Create FFmpeg command
                final_cmd = [
                    "ffmpeg", "-y",
                    "-i", trimmed_file
                ]
                
                # Add filters if needed
                if vf_parts:
                    final_cmd.extend(["-vf", ",".join(vf_parts)])
                
                if af_parts:
                    final_cmd.extend(["-af", ",".join(af_parts)])
                
                # Add output parameters
                final_cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "18",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    output_path
                ])
                
                print(f"Final processing command: {' '.join(final_cmd)}")
                subprocess.run(final_cmd, check=True, capture_output=True, text=True)
                
                # Verify output file
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise Exception("Output file missing or empty")
                
                return output_path
                
            finally:
                # Clean up temp dir
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            print(f"Error in direct absolute trim: {str(e)}")
            
            # Fall back to simple trim method
            print("Falling back to simple trim method...")
            return self._simple_trim(segment, output_path)
    
    def _simple_trim(self, segment: VideoSegment, output_path: str) -> str:
        """
        Very simple trim without fades as fallback
        
        Args:
            segment: VideoSegment object
            output_path: Output path
            
        Returns:
            str: Output path
        """
        try:
            # Convert timecodes to seconds
            start_seconds = segment.time_to_seconds(segment.start_time)
            end_seconds = segment.time_to_seconds(segment.end_time)
            duration = end_seconds - start_seconds
            
            # Basic FFmpeg command
            cmd = [
                "ffmpeg", "-y",
                "-i", self.video_path,
                "-ss", str(start_seconds),
                "-t", str(duration),
                "-c", "copy",
                output_path
            ]
            
            print(f"Simple fallback command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            return output_path
            
        except Exception as e:
            print(f"Error in simple fallback: {str(e)}")
            raise
    
    def _concatenate_videos(self, input_files: List[str], output_file: str):
        """
        Concatenate multiple video files using FFmpeg
        
        Args:
            input_files: List of input video files
            output_file: Output video file
        """
        # Create a temporary file listing the videos to concatenate
        list_file = os.path.join(os.path.dirname(output_file), "filelist.txt")
        
        try:
            # Write the file list
            with open(list_file, 'w') as f:
                for file_path in input_files:
                    f.write(f"file '{os.path.abspath(file_path)}'\n")
            
            # Run FFmpeg to concatenate the files
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_file
            ]
            
            print(f"Concatenating videos with command: {' '.join(cmd)}")
            
            # Execute the command
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Verify the output
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                raise ValueError("Failed to create output file")
                
        except Exception as e:
            print(f"Error concatenating videos: {str(e)}")
            raise
            
        finally:
            # Clean up the list file
            if os.path.exists(list_file):
                os.remove(list_file)
    
    def get_frame_at_time(self, timecode: str) -> Optional[Tuple[int, int, bytes]]:
        """
        Get a frame from the video at the specified timecode
        
        Args:
            timecode: Timecode in HH:MM:SS format
            
        Returns:
            tuple: (width, height, frame_data) or None if failed
        """
        if self._video_capture is None:
            return None
        
        try:
            seconds = timecode_to_seconds(timecode)
            if seconds < 0 or seconds > self.duration:
                return None
            
            # Check if frame is in cache
            frame_number = int(seconds * self.fps)
            if frame_number in self._frame_cache:
                return self._frame_cache[frame_number]
            
            # Seek to the frame
            self._video_capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            
            # Read the frame
            ret, frame = self._video_capture.read()
            
            if not ret:
                return None
            
            # Convert the frame to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to bytes
            frame_bytes = rgb_frame.tobytes()
            
            # Cache the result
            result = (self.width, self.height, frame_bytes)
            
            # Add to cache
            if len(self._frame_cache) >= self._cache_size_limit:
                oldest = min(self._frame_cache.keys())
                del self._frame_cache[oldest]
            self._frame_cache[frame_number] = result
            
            return result
            
        except Exception as e:
            print(f"Error getting frame: {str(e)}")
            return None
    
    def close(self):
        """Release video resources"""
        if self._video_capture is not None:
            self._video_capture.release()
            self._video_capture = None
