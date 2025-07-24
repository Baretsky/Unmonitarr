import httpx
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Client for interacting with Jellyfin API."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "X-MediaBrowser-Token": api_key,
                "Content-Type": "application/json"
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10)
    )
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Jellyfin API with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            raise
    
    async def check_health(self) -> bool:
        """Check if Jellyfin is accessible."""
        try:
            response = await self._make_request("GET", "/System/Info/Public")
            return response is not None
        except Exception as e:
            logger.error(f"Jellyfin health check failed: {e}")
            return False
    
    async def get_system_info(self) -> Optional[Dict[str, Any]]:
        """Get Jellyfin system information."""
        return await self._make_request("GET", "/System/Info")
    
    async def get_users(self) -> List[Dict[str, Any]]:
        """Get all users."""
        result = await self._make_request("GET", "/Users")
        return result if result else []
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        return await self._make_request("GET", f"/Users/{user_id}")
    
    async def get_item_by_id(self, item_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get media item by ID."""
        endpoint = f"/Items/{item_id}"
        params = {}
        if user_id:
            params["userId"] = user_id
        
        return await self._make_request("GET", endpoint, params=params)
    
    async def get_user_data(self, user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get user-specific data for an item (including watched status)."""
        endpoint = f"/Users/{user_id}/Items/{item_id}/UserData"
        return await self._make_request("GET", endpoint)
    
    async def mark_as_played(self, user_id: str, item_id: str) -> bool:
        """Mark an item as played/watched."""
        endpoint = f"/Users/{user_id}/PlayedItems/{item_id}"
        try:
            await self._make_request("POST", endpoint)
            logger.info(f"Marked item {item_id} as played for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark item {item_id} as played: {e}")
            return False
    
    async def mark_as_unplayed(self, user_id: str, item_id: str) -> bool:
        """Mark an item as unplayed/unwatched."""
        endpoint = f"/Users/{user_id}/PlayedItems/{item_id}"
        try:
            await self._make_request("DELETE", endpoint)
            logger.info(f"Marked item {item_id} as unplayed for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark item {item_id} as unplayed: {e}")
            return False
    
    async def get_episodes_for_series(self, series_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all episodes for a series."""
        params = {
            "ParentId": series_id,
            "IncludeItemTypes": "Episode",
            "Recursive": True,
            "Fields": "UserData,ParentId,SeasonUserData"
        }
        if user_id:
            params["UserId"] = user_id
        
        result = await self._make_request("GET", "/Items", params=params)
        return result.get("Items", []) if result else []
    
    async def get_movies(self, user_id: Optional[str] = None, start_index: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get movies from Jellyfin."""
        params = {
            "IncludeItemTypes": "Movie",
            "Fields": "UserData,Genres,Overview",
            "StartIndex": start_index,
            "Limit": limit,
            "Recursive": True
        }
        if user_id:
            params["UserId"] = user_id
        
        result = await self._make_request("GET", "/Items", params=params)
        return result.get("Items", []) if result else []
    
    async def get_series(self, user_id: Optional[str] = None, start_index: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get TV series from Jellyfin."""
        params = {
            "IncludeItemTypes": "Series",
            "Fields": "UserData,Genres,Overview",
            "StartIndex": start_index,
            "Limit": limit,
            "Recursive": True
        }
        if user_id:
            params["UserId"] = user_id
        
        result = await self._make_request("GET", "/Items", params=params)
        return result.get("Items", []) if result else []
    
    async def search_media(self, query: str, media_types: List[str] = None) -> List[Dict[str, Any]]:
        """Search for media items."""
        if media_types is None:
            media_types = ["Movie", "Series", "Episode"]
        
        params = {
            "SearchTerm": query,
            "IncludeItemTypes": ",".join(media_types),
            "Recursive": True,
            "Limit": 50
        }
        
        result = await self._make_request("GET", "/Items", params=params)
        return result.get("Items", []) if result else []
    
    def extract_media_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant media information from Jellyfin item."""
        media_info = {
            "jellyfin_id": item.get("Id"),
            "title": item.get("Name"),
            "media_type": item.get("Type", "").lower(),
            "parent_id": item.get("ParentId"),
            "series_id": item.get("SeriesId"),
            "series_name": item.get("SeriesName"),  # Get series name directly from Jellyfin
            "season_number": item.get("ParentIndexNumber"),
            "episode_number": item.get("IndexNumber"),
            "year": item.get("ProductionYear"),
            "overview": item.get("Overview"),
            "genres": item.get("Genres", []),
            "runtime_ticks": item.get("RunTimeTicks"),
            "path": item.get("Path")
        }
        
        # Extract user data if available
        user_data = item.get("UserData", {})
        if user_data:
            media_info.update({
                "is_watched": user_data.get("Played", False),
                "play_count": user_data.get("PlayCount", 0),
                "last_played_date": user_data.get("LastPlayedDate"),
                "playback_position_ticks": user_data.get("PlaybackPositionTicks", 0)
            })
        
        return media_info
    
    def is_watched_status_change(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """Check if the watched status actually changed between two items."""
        old_played = old_data.get("UserData", {}).get("Played", False)
        new_played = new_data.get("UserData", {}).get("Played", False)
        
        return old_played != new_played
    
    async def get_all_media_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all media items for a specific user (movies, episodes)."""
        all_media = []
        
        try:
            # Get all movies
            logger.info("📽️ Fetching all movies...")
            movies = await self.get_all_items(
                user_id=user_id,
                include_item_types="Movie",
                recursive=True,
                fields="ProviderIds,UserData,MediaInfo"
            )
            all_media.extend(movies)
            logger.info(f"Found {len(movies)} movies")
            
            # Get all episodes  
            logger.info("📺 Fetching all episodes...")
            episodes = await self.get_all_items(
                user_id=user_id,
                include_item_types="Episode", 
                recursive=True,
                fields="ProviderIds,UserData,MediaInfo,SeriesInfo"
            )
            all_media.extend(episodes)
            logger.info(f"Found {len(episodes)} episodes")
            
            logger.info(f"📊 Total media items: {len(all_media)}")
            return all_media
            
        except Exception as e:
            logger.error(f"Failed to get all media for user {user_id}: {e}")
            return []

    async def get_all_movies_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all movie items for a specific user."""
        try:
            logger.info("📽️ Fetching all movies for bulk sync...")
            movies = await self.get_all_items(
                user_id=user_id,
                include_item_types="Movie",
                recursive=True,
                fields="ProviderIds,UserData,MediaInfo"
            )
            logger.info(f"Found {len(movies)} movies for bulk sync")
            return movies
        except Exception as e:
            logger.error(f"Failed to get all movies for user {user_id}: {e}")
            return []

    async def get_all_series_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all episode items for a specific user (part of series)."""
        try:
            logger.info("📺 Fetching all episodes for bulk sync...")
            episodes = await self.get_all_items(
                user_id=user_id,
                include_item_types="Episode", 
                recursive=True,
                fields="ProviderIds,UserData,MediaInfo,SeriesInfo"
            )
            logger.info(f"Found {len(episodes)} episodes for bulk sync")
            return episodes
        except Exception as e:
            logger.error(f"Failed to get all episodes for user {user_id}: {e}")
            return []
    
    async def get_all_items(
        self,
        user_id: Optional[str] = None,
        include_item_types: Optional[str] = None,
        recursive: bool = True,
        fields: Optional[str] = None,
        start_index: int = 0,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get items with pagination support to handle large libraries."""
        all_items = []
        current_start = start_index
        
        while True:
            try:
                params = {
                    "StartIndex": current_start,
                    "Limit": limit,
                    "Recursive": recursive
                }
                
                if include_item_types:
                    params["IncludeItemTypes"] = include_item_types
                if fields:
                    params["Fields"] = fields
                    
                endpoint = f"/Users/{user_id}/Items" if user_id else "/Items"
                
                response = await self._make_request("GET", endpoint, params=params)
                if not response:
                    break
                    
                items = response.get("Items", [])
                if not items:
                    break
                    
                all_items.extend(items)
                
                # Check if we got all items
                total_record_count = response.get("TotalRecordCount", 0)
                if len(all_items) >= total_record_count:
                    break
                    
                current_start += limit
                
            except Exception as e:
                logger.error(f"Error fetching items at index {current_start}: {e}")
                break
                
        return all_items