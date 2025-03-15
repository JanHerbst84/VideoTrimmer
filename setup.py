"""
Setup script for YouTube_Trimmer
"""
import os
import sys
import subprocess

def create_directory_structure():
    """Create the required directory structure"""
    directories = [
        'models',
        'services',
        'ui',
        'utils'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def install_dependencies():
    """Install the required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_opencv.txt"])
    print("Dependencies installed successfully.")

def update_import_in_file(file_path):
    """Update moviepy import to opencv import"""
    if not os.path.exists(file_path):
        return
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace moviepy import with opencv import
    content = content.replace(
        "from moviepy.editor import VideoFileClip, concatenate_videoclips",
        "# Using OpenCV implementation"
    )
    
    with open(file_path, 'w') as f:
        f.write(content)

def main():
    """Main function"""
    print("Setting up YouTube_Trimmer...")
    
    # Create directory structure
    create_directory_structure()
    
    # Install dependencies
    install_dependencies()
    
    # Update video_processor.py to use OpenCV
    update_import_in_file("services/video_processor.py")
    
    # Rename opencv implementation to standard name
    if os.path.exists("services/video_processor_opencv.py"):
        if os.path.exists("services/video_processor.py"):
            os.remove("services/video_processor.py")
        os.rename("services/video_processor_opencv.py", "services/video_processor.py")
    
    print("\nSetup completed successfully!")
    print("To run the application, use: python main.py")

if __name__ == "__main__":
    main()
