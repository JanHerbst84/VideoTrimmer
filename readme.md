# YouTube_Trimmer

A Python application for trimming video files with customizable fade effects.

## Features

- Trim video files using HH:MM:SS timecodes
- Create multiple trim segments from a single video
- Apply customizable fade-in and fade-out effects
- Preview video frames at specific timecodes
- Save presets for commonly used fade durations
- User-friendly PyQt5-based GUI

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/YouTube_Trimmer.git
   cd YouTube_Trimmer
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the application:
```
python main.py
```

### Basic Workflow

1. Click "Open Video" to select a local video file
2. Use the "Add Segment" button to create trim segments
3. For each segment:
   - Set the start and end times in HH:MM:SS format
   - Choose a fade preset or customize fade durations
   - Optionally name your segment
4.