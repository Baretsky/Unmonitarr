from pydantic_settings import BaseSettings
from typing import Optional
import os
import secrets


def get_or_create_env_file():
    """Get the path to the .env file, creating it if it doesn't exist."""
    # Use /app/config directory for .env file to avoid permission issues
    config_dir = "/app/config"
    env_path = os.path.join(config_dir, ".env")
    
    # Ensure config directory exists
    os.makedirs(config_dir, exist_ok=True)
    
    if not os.path.exists(env_path):
        try:
            with open(env_path, "w") as f:
                pass
        except PermissionError:
            # If we can't create in config, try in app directory
            env_path = "/app/.env"
            if not os.path.exists(env_path):
                with open(env_path, "w") as f:
                    pass
    return env_path


def get_setting_from_env(key: str) -> Optional[str]:
    """Read a specific setting from the .env file."""
    env_path = get_or_create_env_file()
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.strip().split('=', 1)[1]
    return None


def save_setting_to_env(key: str, value: str):
    """Save a specific setting to the .env file."""
    env_path = get_or_create_env_file()
    with open(env_path, "r") as f:
        lines = f.readlines()

    with open(env_path, "w") as f:
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{key}={value}\n")


class Settings(BaseSettings):
    # Jellyfin Configuration
    jellyfin_url: str = "http://localhost:8096"
    jellyfin_api_key: str = ""
    
    # Sonarr Configuration
    sonarr_url: str = "http://localhost:8989"
    sonarr_api_key: str = ""
    
    # Radarr Configuration
    radarr_url: str = "http://localhost:7878"
    radarr_api_key: str = ""
    
    # Database Configuration
    database_url: str = "sqlite:////app/data/unmonitarr.db"
    
    # Application Configuration
    log_level: str = "INFO"
    webhook_token: Optional[str] = None
    auto_sync_enabled: bool = True
    sync_delay_seconds: int = 5
    
    # Web UI Configuration
    secret_key: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin"
    
    # API Rate Limiting
    max_requests_per_minute: int = 60
    retry_attempts: int = 3
    retry_delay: int = 1
    
    # External API Configuration
    omdb_api_key: Optional[str] = None  # OMDb API key for IMDB metadata matching (free at omdbapi.com)
    use_external_api: bool = True  # Enable external API matching
    
    # Special Episodes Configuration
    ignore_special_episodes: bool = True  # Ignore season 0 (special episodes) when syncing with Sonarr
    
    class Config:
        env_file = get_or_create_env_file()
        case_sensitive = False


# Global settings instance
settings = Settings()

# Note: Webhook token and secret key are now managed via persistent_config.py
# They will be initialized at application startup from the database


def get_database_path() -> str:
    """Get the database file path, creating directory if needed."""
    # Handle both relative and absolute paths
    if settings.database_url.startswith("sqlite:////"):
        # Absolute path with 4 slashes
        db_path = settings.database_url.replace("sqlite:////", "/")
    elif settings.database_url.startswith("sqlite:///"):
        # Relative path with 3 slashes - make it absolute from /app
        relative_path = settings.database_url.replace("sqlite:///", "")
        if relative_path.startswith("/"):
            db_path = relative_path
        else:
            db_path = f"/{relative_path}"
    else:
        raise ValueError(f"Unsupported database URL format: {settings.database_url}")
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path
