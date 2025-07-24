"""
Persistent configuration management using database storage.
"""
import secrets
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db_session
from .models import Configuration

logger = logging.getLogger(__name__)


class PersistentConfig:
    """Manage persistent configuration values in the database."""
    
    @staticmethod
    async def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a configuration value from the database."""
        try:
            async with get_db_session() as db:
                stmt = select(Configuration).where(Configuration.key == key)
                result = await db.execute(stmt)
                config = result.scalar_one_or_none()
                
                if config:
                    logger.debug(f"Retrieved config {key} from database")
                    return config.value
                else:
                    logger.debug(f"Config {key} not found in database, returning default")
                    return default
                    
        except Exception as e:
            logger.error(f"Failed to get config value for {key}: {e}")
            return default
    
    @staticmethod
    async def set_config_value(
        key: str, 
        value: str, 
        description: Optional[str] = None
    ) -> bool:
        """Set a configuration value in the database."""
        try:
            async with get_db_session() as db:
                # Check if config already exists
                stmt = select(Configuration).where(Configuration.key == key)
                result = await db.execute(stmt)
                config = result.scalar_one_or_none()
                
                if config:
                    # Update existing
                    config.value = value
                    if description:
                        config.description = description
                    logger.info(f"Updated config {key} in database")
                else:
                    # Create new
                    config = Configuration(
                        key=key,
                        value=value,
                        description=description or f"Auto-generated config for {key}"
                    )
                    db.add(config)
                    logger.info(f"Created new config {key} in database")
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to set config value for {key}: {e}")
            return False
    
    @staticmethod
    async def get_or_create_webhook_token() -> str:
        """Get existing webhook token or create a new one."""
        try:
            # Try to get existing token from database
            token = await PersistentConfig.get_config_value("webhook_token")
            
            if token:
                logger.info("🔑 Using existing webhook token from database")
                return token
            
            # Migration: Check if token exists in environment/settings
            from .config import settings
            if settings.webhook_token:
                logger.info("📦 Migrating existing webhook token from environment to database")
                success = await PersistentConfig.set_config_value(
                    "webhook_token",
                    settings.webhook_token,
                    "Webhook authentication token for Jellyfin webhooks (migrated from env)"
                )
                if success:
                    logger.info("✅ Successfully migrated webhook token to database")
                    return settings.webhook_token
                else:
                    logger.warning("⚠️ Failed to migrate webhook token to database, using existing env token")
                    return settings.webhook_token
            
            # Generate new token
            new_token = f"unmonitarr-{secrets.token_hex(16)}"
            
            # Save to database
            success = await PersistentConfig.set_config_value(
                "webhook_token",
                new_token,
                "Webhook authentication token for Jellyfin webhooks"
            )
            
            if success:
                logger.info("🆕 Generated and saved new webhook token to database")
                return new_token
            else:
                logger.error("Failed to save webhook token to database")
                return new_token  # Return it anyway, but it won't persist
                
        except Exception as e:
            logger.error(f"Failed to get or create webhook token: {e}")
            # Fallback to generating a non-persistent token
            return f"unmonitarr-{secrets.token_hex(16)}"
    
    @staticmethod
    async def regenerate_webhook_token() -> str:
        """Generate a new webhook token and save it."""
        try:
            new_token = f"unmonitarr-{secrets.token_hex(16)}"
            
            success = await PersistentConfig.set_config_value(
                "webhook_token",
                new_token,
                "Webhook authentication token for Jellyfin webhooks (regenerated)"
            )
            
            if success:
                logger.info("🔄 Generated and saved new webhook token to database")
                return new_token
            else:
                logger.error("Failed to save regenerated webhook token to database")
                return new_token
                
        except Exception as e:
            logger.error(f"Failed to regenerate webhook token: {e}")
            return f"unmonitarr-{secrets.token_hex(16)}"
    
    @staticmethod
    async def get_or_create_secret_key() -> str:
        """Get existing secret key or create a new one."""
        try:
            # Try to get existing key from database
            key = await PersistentConfig.get_config_value("secret_key")
            
            if key:
                logger.info("🔑 Using existing secret key from database")
                return key
            
            # Migration: Check if key exists in environment/settings
            from .config import settings
            if settings.secret_key:
                logger.info("📦 Migrating existing secret key from environment to database")
                success = await PersistentConfig.set_config_value(
                    "secret_key",
                    settings.secret_key,
                    "Secret key for web session encryption (migrated from env)"
                )
                if success:
                    logger.info("✅ Successfully migrated secret key to database")
                    return settings.secret_key
                else:
                    logger.warning("⚠️ Failed to migrate secret key to database, using existing env key")
                    return settings.secret_key
            
            # Generate new key
            new_key = secrets.token_urlsafe(32)
            
            # Save to database
            success = await PersistentConfig.set_config_value(
                "secret_key",
                new_key,
                "Secret key for web session encryption"
            )
            
            if success:
                logger.info("🆕 Generated and saved new secret key to database")
                return new_key
            else:
                logger.error("Failed to save secret key to database")
                return new_key
                
        except Exception as e:
            logger.error(f"Failed to get or create secret key: {e}")
            return secrets.token_urlsafe(32)
    
    @staticmethod
    async def initialize_persistent_config():
        """Initialize persistent configuration on application startup."""
        try:
            logger.info("🔧 Initializing persistent configuration...")
            
            # Initialize webhook token
            webhook_token = await PersistentConfig.get_or_create_webhook_token()
            
            # Initialize secret key
            secret_key = await PersistentConfig.get_or_create_secret_key()
            
            logger.info("✅ Persistent configuration initialized successfully")
            
            return {
                "webhook_token": webhook_token,
                "secret_key": secret_key
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize persistent configuration: {e}")
            return {
                "webhook_token": f"unmonitarr-{secrets.token_hex(16)}",
                "secret_key": secrets.token_urlsafe(32)
            }