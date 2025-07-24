"""
Global application configuration with persistent storage.
"""
import logging
import secrets
from typing import Optional
from .config import settings
from .persistent_config import PersistentConfig

logger = logging.getLogger(__name__)


class AppConfig:
    """Global application configuration manager."""
    
    def __init__(self):
        self._webhook_token: Optional[str] = None
        self._secret_key: Optional[str] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize persistent configuration from database."""
        if self._initialized:
            return
            
        try:
            logger.info("🔧 Initializing application configuration...")
            
            # Get or create persistent tokens
            config = await PersistentConfig.initialize_persistent_config()
            
            self._webhook_token = config["webhook_token"]
            self._secret_key = config["secret_key"]
            
            # Update the global settings object
            settings.webhook_token = self._webhook_token
            settings.secret_key = self._secret_key
            
            self._initialized = True
            logger.info("✅ Application configuration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application configuration: {e}")
            # Fallback to default behavior
            self._webhook_token = settings.webhook_token or f"unmonitarr-{secrets.token_hex(16)}"
            self._secret_key = settings.secret_key or secrets.token_urlsafe(32)
            settings.webhook_token = self._webhook_token
            settings.secret_key = self._secret_key
            self._initialized = True
    
    @property
    def webhook_token(self) -> Optional[str]:
        """Get the current webhook token."""
        return self._webhook_token
    
    @property
    def secret_key(self) -> Optional[str]:
        """Get the current secret key."""
        return self._secret_key
    
    async def regenerate_webhook_token(self) -> str:
        """Regenerate the webhook token."""
        new_token = await PersistentConfig.regenerate_webhook_token()
        self._webhook_token = new_token
        settings.webhook_token = new_token
        return new_token
    
    def is_initialized(self) -> bool:
        """Check if configuration has been initialized."""
        return self._initialized


# Global app configuration instance
app_config = AppConfig()