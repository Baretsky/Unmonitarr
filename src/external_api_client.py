import httpx
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio

logger = logging.getLogger(__name__)


class ExternalAPIClient:
    """Client for external metadata APIs (IMDB via OMDb, TVDB)."""
    
    def __init__(self, omdb_api_key: Optional[str] = None):
        self.omdb_api_key = omdb_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def _make_request(self, url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request with retry logic."""
        try:
            response = await self.client.get(url, headers=headers or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"External API request failed for {url}: {e}")
            raise
    
    async def search_series_by_title(self, title: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for series using OMDb API (IMDB data)."""
        try:
            if not self.omdb_api_key:
                logger.warning("OMDb API key not configured - falling back to title matching")
                return []
            
            # Search OMDb for TV series
            params = {
                "apikey": self.omdb_api_key,
                "s": title,  # Search by title
                "type": "series"
            }
            
            if year:
                params["y"] = str(year)
            
            url_with_params = f"https://www.omdbapi.com/?" + "&".join([f"{k}={v}" for k, v in params.items()])
            response = await self._make_request(url_with_params)
            
            if not response or response.get("Response") == "False":
                logger.info(f"No OMDb results found for series: {title}")
                return []
            
            search_results = response.get("Search", [])
            results = []
            
            # Get detailed info for each result
            for show in search_results[:5]:  # Top 5 matches
                imdb_id = show.get("imdbID")
                if imdb_id:
                    detailed_info = await self.get_detailed_info_by_imdb_id(imdb_id)
                    if detailed_info:
                        result = {
                            "title": detailed_info.get("Title"),
                            "year": int(detailed_info.get("Year", "0")) if detailed_info.get("Year", "").isdigit() else None,
                            "imdb_id": imdb_id,
                            "tvdb_id": None,  # OMDb doesn't provide TVDB ID directly
                            "tmdb_id": None,  # OMDb doesn't provide TMDB ID directly
                            "overview": detailed_info.get("Plot"),
                            "poster_path": detailed_info.get("Poster"),
                            "imdb_rating": detailed_info.get("imdbRating"),
                            "genre": detailed_info.get("Genre"),
                            "actors": detailed_info.get("Actors"),
                            "source": "omdb"
                        }
                        results.append(result)
                        logger.info(f"📺 Found series: {result['title']} ({result['year']}) - IMDB:{result['imdb_id']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search series '{title}': {e}")
            return []
    
    async def search_movie_by_title(self, title: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for movie using OMDb API (IMDB data)."""
        try:
            if not self.omdb_api_key:
                logger.warning("OMDb API key not configured - falling back to title matching")
                return []
            
            # Search OMDb for movies
            params = {
                "apikey": self.omdb_api_key,
                "s": title,  # Search by title
                "type": "movie"
            }
            
            if year:
                params["y"] = str(year)
            
            url_with_params = f"https://www.omdbapi.com/?" + "&".join([f"{k}={v}" for k, v in params.items()])
            response = await self._make_request(url_with_params)
            
            if not response or response.get("Response") == "False":
                logger.info(f"No OMDb results found for movie: {title}")
                return []
            
            search_results = response.get("Search", [])
            results = []
            
            # Get detailed info for each result
            for movie in search_results[:5]:  # Top 5 matches
                imdb_id = movie.get("imdbID")
                if imdb_id:
                    detailed_info = await self.get_detailed_info_by_imdb_id(imdb_id)
                    if detailed_info:
                        result = {
                            "title": detailed_info.get("Title"),
                            "year": int(detailed_info.get("Year", "0")) if detailed_info.get("Year", "").isdigit() else None,
                            "imdb_id": imdb_id,
                            "tvdb_id": None,  # OMDb doesn't provide TVDB ID
                            "tmdb_id": None,  # OMDb doesn't provide TMDB ID
                            "overview": detailed_info.get("Plot"),
                            "poster_path": detailed_info.get("Poster"),
                            "imdb_rating": detailed_info.get("imdbRating"),
                            "genre": detailed_info.get("Genre"),
                            "actors": detailed_info.get("Actors"),
                            "source": "omdb"
                        }
                        results.append(result)
                        logger.info(f"🎬 Found movie: {result['title']} ({result['year']}) - IMDB:{result['imdb_id']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search movie '{title}': {e}")
            return []
    
    async def get_detailed_info_by_imdb_id(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information from OMDb using IMDB ID."""
        try:
            params = {
                "apikey": self.omdb_api_key,
                "i": imdb_id,  # Search by IMDB ID
                "plot": "full"  # Get full plot
            }
            
            url_with_params = f"https://www.omdbapi.com/?" + "&".join([f"{k}={v}" for k, v in params.items()])
            response = await self._make_request(url_with_params)
            
            if response and response.get("Response") == "True":
                return response
            
            logger.warning(f"No detailed info found for IMDB ID: {imdb_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get detailed info for IMDB ID {imdb_id}: {e}")
            return None
    
    async def search_by_imdb_id(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Direct search using IMDB ID - most reliable method."""
        logger.info(f"🎯 Direct IMDB search for ID: {imdb_id}")
        
        detailed_info = await self.get_detailed_info_by_imdb_id(imdb_id)
        if not detailed_info:
            return None
        
        media_type = detailed_info.get("Type", "").lower()
        
        result = {
            "title": detailed_info.get("Title"),
            "year": int(detailed_info.get("Year", "0")) if detailed_info.get("Year", "").isdigit() else None,
            "imdb_id": imdb_id,
            "tvdb_id": None,  # We'd need additional lookup for TVDB
            "tmdb_id": None,  # We'd need additional lookup for TMDB
            "overview": detailed_info.get("Plot"),
            "poster_path": detailed_info.get("Poster"),
            "imdb_rating": detailed_info.get("imdbRating"),
            "genre": detailed_info.get("Genre"),
            "actors": detailed_info.get("Actors"),
            "media_type": media_type,
            "source": "omdb_direct"
        }
        
        logger.info(f"✅ Direct IMDB match: {result['title']} ({result['year']}) - Type: {media_type}")
        return result
    
    async def find_best_match(
        self, 
        title: str, 
        media_type: str, 
        year: Optional[int] = None,
        existing_ids: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find best matching media using external APIs with IMDB as primary source.
        
        Args:
            title: Media title from Jellyfin
            media_type: 'series' or 'movie'
            year: Release year if available
            existing_ids: Any known external IDs from Jellyfin
        
        Returns:
            Best match with external IDs, or None if not found
        """
        logger.info(f"🔍 External API Search: '{title}' ({media_type}) year:{year}")
        
        # PRIORITY 1: Direct IMDB ID lookup (most reliable)
        if existing_ids and existing_ids.get("imdb_id"):
            logger.info(f"🎯 PRIORITY 1: Direct IMDB ID lookup: {existing_ids['imdb_id']}")
            direct_result = await self.search_by_imdb_id(existing_ids["imdb_id"])
            if direct_result:
                return direct_result
        
        # PRIORITY 2: Use other existing IDs if available
        if existing_ids and (existing_ids.get("tvdb_id") or existing_ids.get("tmdb_id")):
            logger.info("🎯 PRIORITY 2: Using existing external IDs from Jellyfin webhook")
            return {
                "title": title,
                "year": year,
                "tvdb_id": existing_ids.get("tvdb_id"),
                "imdb_id": existing_ids.get("imdb_id"), 
                "tmdb_id": existing_ids.get("tmdb_id"),
                "source": "jellyfin_webhook"
            }
        
        # PRIORITY 3: Search by title using OMDb
        logger.info("🎯 PRIORITY 3: Searching by title using OMDb API")
        if media_type.lower() in ["series", "episode", "season"]:
            results = await self.search_series_by_title(title, year)
        elif media_type.lower() == "movie":
            results = await self.search_movie_by_title(title, year)
        else:
            logger.warning(f"Unknown media type: {media_type}")
            return None
        
        if not results:
            logger.warning(f"❌ No external API results for '{title}'")
            return None
        
        # Find best match (prioritize exact title and year matches)
        best_match = results[0]  # Start with first result
        
        for result in results:
            # Prefer exact title matches
            if result["title"].lower() == title.lower():
                best_match = result
                break
            
            # Prefer year matches if available
            if year and result.get("year") == year:
                best_match = result
                # Don't break here in case we find an exact title match later
        
        logger.info(f"✅ Best external match: '{best_match['title']}' ({best_match.get('year')})")
        logger.info(f"   🎯 IMDB ID: {best_match.get('imdb_id')} (will be used for Sonarr/Radarr matching)")
        
        best_match["source"] = "external_api_search"
        return best_match


# Utility functions for matching scores
def calculate_title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity score between two titles (0.0 to 1.0)."""
    if not title1 or not title2:
        return 0.0
    
    title1_clean = title1.lower().strip()
    title2_clean = title2.lower().strip()
    
    # Exact match
    if title1_clean == title2_clean:
        return 1.0
    
    # Contains match (shorter in longer)
    if title1_clean in title2_clean or title2_clean in title1_clean:
        return 0.8
    
    # Word-based similarity (simple approach)
    words1 = set(title1_clean.split())
    words2 = set(title2_clean.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0