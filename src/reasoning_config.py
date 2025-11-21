import json
import os
from typing import Optional
from src.log import logger

# Path to the reasoning level configuration file
CONFIG_FILE = "reasoning_levels.json"

# Valid reasoning levels for GPT-5.1
VALID_LEVELS = ["none", "minimal", "low", "medium", "high"]


def _load_config() -> dict:
    """Load reasoning level configuration from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading reasoning config: {e}")
        return {}


def _save_config(config: dict) -> bool:
    """Save reasoning level configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving reasoning config: {e}")
        return False


def get_reasoning_level(channel_id: str) -> Optional[str]:
    """
    Get the reasoning level for a specific channel.
    
    Args:
        channel_id: Discord channel ID
        
    Returns:
        Reasoning level string if set, None if not set (OpenAI will use default)
    """
    config = _load_config()
    return config.get(str(channel_id))


def set_reasoning_level(channel_id: str, level: str) -> bool:
    """
    Set the reasoning level for a specific channel.
    
    Args:
        channel_id: Discord channel ID
        level: Reasoning level (none, minimal, low, medium, high)
        
    Returns:
        True if successful, False otherwise
    """
    if level not in VALID_LEVELS:
        logger.warning(f"Invalid reasoning level: {level}")
        return False
    
    config = _load_config()
    config[str(channel_id)] = level
    success = _save_config(config)
    
    if success:
        logger.info(f"Set reasoning level for channel {channel_id} to {level}")
    
    return success


def remove_reasoning_level(channel_id: str) -> bool:
    """
    Remove the reasoning level setting for a specific channel.
    This will let OpenAI use its default reasoning level.
    
    Args:
        channel_id: Discord channel ID
        
    Returns:
        True if successful, False otherwise
    """
    config = _load_config()
    
    if str(channel_id) in config:
        del config[str(channel_id)]
        success = _save_config(config)
        
        if success:
            logger.info(f"Removed reasoning level for channel {channel_id}")
        
        return success
    
    return True  # Already not set, consider it success


def get_all_reasoning_levels() -> dict:
    """
    Get all reasoning level configurations.
    
    Returns:
        Dictionary mapping channel IDs to reasoning levels
    """
    return _load_config()

