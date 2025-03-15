"""
Video processing service for trimming videos with fades using OpenCV
"""
import os
import numpy as np
import cv2
import subprocess
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
            # Open the video
            self._video_capture = cv2.VideoCapture(self.video_path)
            
            # Get video properties
            self.fps = self._video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self._video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.width = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            self.duration = self.total_frames / self.fps if self.fps > 0 else 0
            
        except Exception as e:
            raise RuntimeError(f"Failed to load video: {str(e)}")
    
    def _get_frame_number(self, time_seconds: float) -> int:
        """
        Convert time in seconds to frame number
        
        Args:
            time_seconds: Time in seconds
            
        Returns:
            int: Frame number
        """
        return int(time_seconds * self.fps)
    
    def _apply_fade(self, frame, alpha: float) -> np.ndarray:
        """
        Apply fade effect to a frame
        
        Args:
            frame: The frame to apply fade to
            alpha: Fade factor (0.0 to 1.0)
            
        Returns:
            np.ndarray: The frame with fade applied
        """
        return cv2.convertScaleAbs(frame, alpha=alpha, beta=0)
    
    def trim_segment(self, segment: VideoSegment, output_path: str) -> str:
        """
        Trim a segment from the video with optional fade effects
        
        Args:
            segment: VideoSegment object containing trim and fade information
            output_path: Path to save the output video
            
        Returns:
            str: Path to the saved file
        """
        if self._video_capture is None:
            raise RuntimeError("No video loaded")
        
        start_time = timecode_to_seconds(segment.start_time)
        end_time = timecode_to_seconds(segment.end_time)
        
        # Ensure times are within video bounds
        if start_time < 0 or end_time > self.duration:
            raise ValueError(f"Trim times out of range. Video duration is {self.duration} seconds")
        
        # Calculate frame numbers
        start_frame = self._get_frame_number(start_time)
        end_frame = self._get_frame_number(end_time)
        total_segment_frames = end_frame - start_frame
        
        # Calculate fade frames
        fade_in_frames = int(segment.fade_in_duration * self.fps)
        fade_out_frames = int(segment.fade_out_duration * self.fps)
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            self.fps,
            (self.width, self.height)
        )
        
        # Seek to start frame
        self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        # Process frames
        for i in range(total_segment_frames):
            ret, frame = self._video_capture.read()
            
            if not ret:
                break
            
            # Apply fade in
            if i < fade_in_frames and fade_in_frames > 0:
                alpha = i / fade_in_frames
                frame = self._apply_fade(frame, alpha)
            
            # Apply fade out
            elif i >= total_segment_frames - fade_out_frames and fade_out_frames > 0:
                alpha = (total_segment_frames - i) / fade_out_frames
                frame = self._apply_fade(frame, alpha)
            
            # Write the frame
            writer.write(frame)
        
        # Release the writer
        writer.release()
        
        return output_path
    
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
                
                # Use FFmpeg directly for trimming with audio
                self._trim_segment_with_ffmpeg(segment, temp_output)
                segment_files.append(temp_output)
            
            # If only one segment, just rename the file
            if len(segment_files) == 1:
                os.replace(segment_files[0], output_path)
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

    def _trim_segment_with_ffmpeg(self, segment: VideoSegment, output_path: str) -> str:
        """
        Trim a segment using FFmpeg to preserve audio
        
        Args:
            segment: VideoSegment object containing trim and fade information
            output_path: Path to save the output video
            
        Returns:
            str: Path to the output file
        """
        try:
            # Convert timecodes to seconds
            start_seconds = segment.time_to_seconds(segment.start_time)
            end_seconds = segment.time_to_seconds(segment.end_time)
            duration = end_seconds - start_seconds
            
            # Build basic FFmpeg command for trimming
            cmd = [
                "ffmpeg", "-y",  # Overwrite output files without asking
                "-i", self.video_path,
                "-ss", str(start_seconds),
                "-t", str(duration)
            ]
            
            # Initialize filter_complex list for both video and audio filters
            video_filters = []
            audio_filters = []
            
            # Add fade effects if needed
            if segment.fade_in_duration > 0:
                # Video fade in
                video_filters.append(f"fade=t=in:st=0:d={segment.fade_in_duration}")
                # Audio fade in
                audio_filters.append(f"afade=t=in:st=0:d={segment.fade_in_duration}")
            
            if segment.fade_out_duration > 0:
                # Calculate fade out start time
                fade_out_start = duration - segment.fade_out_duration
                if fade_out_start < 0:
                    fade_out_start = 0
                
                # Video fade out
                video_filters.append(f"fade=t=out:st={fade_out_start}:d={segment.fade_out_duration}")
                # Audio fade out
                audio_filters.append(f"afade=t=out:st={fade_out_start}:d={segment.fade_out_duration}")
            
            # Apply video filters if any
            if video_filters:
                cmd.extend(["-vf", ",".join(video_filters)])
            
            # Apply audio filters if any
            if audio_filters:
                cmd.extend(["-af", ",".join(audio_filters)])
            
            # Set output codecs
            cmd.extend([
                "-c:v", "libx264",  # Use H.264 codec for video
                "-c:a", "aac",      # Use AAC codec for audio
                "-b:a", "192k"      # Set audio bitrate for better quality
            ])
            
            # Add output path
            cmd.append(output_path)
            
            # Execute FFmpeg command
            print(f"Running FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  check=False)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                # Fall back to OpenCV method if FFmpeg fails
                return self.trim_segment(segment, output_path)
            
            return output_path
            
        except Exception as e:
            print(f"Error using FFmpeg, falling back to OpenCV: {str(e)}")
            # Fall back to OpenCV method
            return self.trim_segment(segment, output_path)
    
    def _concatenate_videos(self, input_files: List[str], output_file: str):
        """
        Concatenate multiple video files
        
        Args:
            input_files: List of input video files
            output_file: Output video file
        """
        # Create text file with list of files for concatenation
        list_file = os.path.join(os.path.dirname(output_file), "filelist.txt")
        
        with open(list_file, 'w') as f:
            for file in input_files:
                f.write(f"file '{file}'\n")
        
        try:
            # Check if FFmpeg is available
            try:
                result = subprocess.run(['ffmpeg', '-version'], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True,
                                       check=False)
                ffmpeg_available = result.returncode == 0
            except (FileNotFoundError, subprocess.SubprocessError):
                ffmpeg_available = False
            
            if ffmpeg_available:
                # Use ffmpeg to concatenate videos
                cmd = f'ffmpeg -f concat -safe 0 -i "{list_file}" -c copy "{output_file}"'
                print(f"Running command: {cmd}")
                result = subprocess.run(cmd, 
                                       shell=True,
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True,
                                       check=False)
                
                if result.returncode != 0:
                    print(f"FFmpeg error: {result.stderr}")
                    raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            else:
                # Fallback: manual concatenation
                print("FFmpeg not available, using manual concatenation")
                self._manual_concatenate_videos(input_files, output_file)
        
        finally:
            # Remove the temporary list file
            if os.path.exists(list_file):
                os.remove(list_file)
    
    def _manual_concatenate_videos(self, input_files: List[str], output_file: str):
        """
        Manually concatenate videos when FFmpeg is not available
        
        Args:
            input_files: List of input video files
            output_file: Output video file
        """
        # Use OpenCV to concatenate the files
        output_cap = None
        
        try:
            # Get properties from first video
            first_cap = cv2.VideoCapture(input_files[0])
            fps = first_cap.get(cv2.CAP_PROP_FPS)
            width = int(first_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(first_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            first_cap.release()
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            output_cap = cv2.VideoWriter(
                output_file,
                fourcc,
                fps,
                (width, height)
            )
            
            # Process each input file
            for input_file in input_files:
                cap = cv2.VideoCapture(input_file)
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    output_cap.write(frame)
                cap.release()
                
        except Exception as e:
            raise RuntimeError(f"Manual concatenation failed: {str(e)}")
        finally:
            if output_cap:
                output_cap.release()
    
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
            frame_number = self._get_frame_number(seconds)
            if frame_number in self._frame_cache:
                return self._frame_cache[frame_number]
            
            # Only reopen for significant jumps to reduce overhead
            current_pos = self._video_capture.get(cv2.CAP_PROP_POS_MSEC)
            time_diff_ms = abs(seconds * 1000 - current_pos)
            
            if time_diff_ms > 1000:  # If jump is more than 1 second
                try:
                    self._video_capture.release()
                    self._video_capture = cv2.VideoCapture(self.video_path)
                except Exception:
                    # If reopening fails, try to continue with the existing capture
                    pass
            
            # Seek by milliseconds for more accuracy
            position_ms = int(seconds * 1000)
            self._video_capture.set(cv2.CAP_PROP_POS_MSEC, position_ms)
            
            # Read the frame
            ret, frame = self._video_capture.read()
            
            if not ret:
                # Fallback: try seeking by frame number
                frame_number = self._get_frame_number(seconds)
                self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = self._video_capture.read()
                
                if not ret:
                    return None
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to bytes
            frame_bytes = rgb_frame.tobytes()
            
            # Cache the frame
            result = (self.width, self.height, frame_bytes)
            self._add_to_cache(frame_number, result)
            
            return result
            
        except Exception as e:
            print(f"Error getting frame: {str(e)}")
            return None
    
    def _add_to_cache(self, frame_number: int, frame_data: Tuple[int, int, bytes]):
        """Add a frame to the cache, removing oldest if necessary"""
        # Remove oldest frame if cache is full
        if len(self._frame_cache) >= self._cache_size_limit:
            oldest_key = min(self._frame_cache.keys())
            del self._frame_cache[oldest_key]
        
        # Add new frame to cache
        self._frame_cache[frame_number] = frame_data
    
    def close(self):
        """Release video resources"""
        if self._video_capture is not None:
            self._video_capture.release()
            self._video_capture = None
