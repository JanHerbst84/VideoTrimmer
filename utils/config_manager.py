"""
Configuration manager for saving and loading application settings
"""
import os
import json
from typing import Any, Dict, List, Optional

# Default configuration values
DEFAULT_CONFIG = {
    "recent_files": [],
    "max_recent_files": 5,
    "output_directory": "",
    "default_fade_in": 0.5,
    "default_fade_out": 0.5,
    "preset_fades": [
        {"name": "None", "in": 0.0, "out": 0.0},
        {"name": "Gentle", "in": 0.5, "out": 0.5},
        {"name": "Smooth", "in": 1.0, "out": 1.0},
        {"name": "Dramatic", "in": 0.0, "out": 2.0},
        {"name": "Intro", "in": 2.0, "out": 0.0}
    ]
}


class ConfigManager:
    """Manages application configuration and persistence"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager
        
        Args:
            config_path: Path to the configuration file,
                         defaults to ~/.youtube_trimmer.json
        """
        if config_path is None:
            self.config_path = os.path.expanduser("~/.youtube_trimmer.json")
        else:
            self.config_path = config_path
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create default
        
        Returns:
            dict: Configuration dictionary
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                # Ensure all default keys exist
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                
                return config
            except (json.JSONDecodeError, IOError):
                # If loading fails, use defaults
                return DEFAULT_CONFIG.copy()
        else:
            return DEFAULT_CONFIG.copy()
    
    def save_config(self) -> bool:
        """
        Save configuration to file
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            The configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
        self.save_config()
    
    def add_recent_file(self, file_path: str) -> None:
        """
        Add a file to the recent files list
        
        Args:
            file_path: Path to the file
        """
        recent_files = self.get("recent_files", [])
        
        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to the beginning
        recent_files.insert(0, file_path)
        
        # Trim to max length
        max_recent = self.get("max_recent_files", 5)
        if len(recent_files) > max_recent:
            recent_files = recent_files[:max_recent]
        
        self.set("recent_files", recent_files)
    
    def get_preset_fades(self) -> List[Dict[str, Any]]:
        """
        Get the list of preset fades
        
        Returns:
            list: List of fade presets
        """
        return self.get("preset_fades", DEFAULT_CONFIG["preset_fades"])
    
    def add_preset_fade(self, name: str, fade_in: float, fade_out: float) -> None:
        """
        Add a new preset fade
        
        Args:
            name: Name of the preset
            fade_in: Fade in duration in seconds
            fade_out: Fade out duration in seconds
        """
        presets = self.get_preset_fades()
        
        # Check if name already exists
        for preset in presets:
            if preset["name"] == name:
                preset["in"] = fade_in
                preset["out"] = fade_out
                self.set("preset_fades", presets)
                return
        
        # Add new preset
        presets.append({
            "name": name,
            "in": fade_in,
            "out": fade_out
        })
        
        self.set("preset_fades", presets)
