from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum


Base = declarative_base()


class MediaType(str, Enum):
    MOVIE = "movie"
    EPISODE = "episode"
    SERIES = "series"
    SEASON = "season"


class SyncAction(str, Enum):
    MONITOR = "monitor"
    UNMONITOR = "unmonitor"


class SyncStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Database Models
class MediaItem(Base):
    __tablename__ = "media_items"
    
    id = Column(Integer, primary_key=True, index=True)
    jellyfin_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    media_type = Column(String, nullable=False)  # movie, episode, series, season
    is_watched = Column(Boolean, default=False)
    parent_id = Column(String, nullable=True)  # For episodes (series id) or seasons (series id)
    series_name = Column(String, nullable=True)  # Store series name directly for episodes
    season_number = Column(Integer, nullable=True)  # For episodes and seasons
    episode_number = Column(Integer, nullable=True)  # For episodes
    
    # Relationships
    sonarr_mapping = relationship("SonarrMapping", back_populates="media_item", uselist=False)
    radarr_mapping = relationship("RadarrMapping", back_populates="media_item", uselist=False)
    sync_logs = relationship("SyncLog", back_populates="media_item")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SonarrMapping(Base):
    __tablename__ = "sonarr_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), unique=True)
    sonarr_series_id = Column(Integer, nullable=False)
    sonarr_episode_id = Column(Integer, nullable=True)  # For episodes
    sonarr_season_number = Column(Integer, nullable=True)  # For seasons
    is_monitored = Column(Boolean, default=True)
    
    # Relationships
    media_item = relationship("MediaItem", back_populates="sonarr_mapping")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RadarrMapping(Base):
    __tablename__ = "radarr_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"), unique=True)
    radarr_movie_id = Column(Integer, nullable=False)
    is_monitored = Column(Boolean, default=True)
    
    # Relationships
    media_item = relationship("MediaItem", back_populates="radarr_mapping")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    media_item_id = Column(Integer, ForeignKey("media_items.id"))
    series_name = Column(String, nullable=True)
    action = Column(String, nullable=False)  # monitor, unmonitor
    status = Column(String, nullable=False)  # pending, processing, completed, failed
    service = Column(String, nullable=False)  # sonarr, radarr
    external_id = Column(String, nullable=True)  # sonarr_id, radarr_id for tracking
    error_message = Column(Text, nullable=True)
    
    # Relationships
    media_item = relationship("MediaItem", back_populates="sync_logs")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Configuration(Base):
    __tablename__ = "configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Models for API
class MediaItemBase(BaseModel):
    jellyfin_id: str
    title: str
    media_type: MediaType
    is_watched: bool = False
    parent_id: Optional[str] = None
    series_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None


class MediaItemCreate(MediaItemBase):
    pass


class MediaItemUpdate(BaseModel):
    title: Optional[str] = None
    is_watched: Optional[bool] = None
    parent_id: Optional[str] = None
    series_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None


class MediaItemResponse(MediaItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WebhookPayload(BaseModel):
    event_type: str
    jellyfin_id: str
    user_id: str
    is_watched: bool
    media_type: MediaType
    title: str
    parent_id: Optional[str] = None
    series_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None




class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    services: dict