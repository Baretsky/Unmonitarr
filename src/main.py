from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
# BackgroundTask is created inline, not imported
from contextlib import asynccontextmanager
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import settings, save_setting_to_env
from .app_config import app_config
import secrets

# Diagnostic temporairement désactivé pour éviter les conflits
# from .debug_database import debug_database_issue
# print("🔍 EXÉCUTION DU DIAGNOSTIC DE DÉMARRAGE...")
# debug_database_issue()

from .database import init_database, close_database, get_db, check_database_health
from .models import (
    MediaItemResponse, WebhookPayload, 
    HealthCheck, MediaItemCreate, MediaItemUpdate
)
from .webhook_handler import WebhookHandler
from .jellyfin_client import JellyfinClient
from .sonarr_client import SonarrClient
from .radarr_client import RadarrClient
from .external_api_client import ExternalAPIClient

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Global bulk sync status tracking
bulk_sync_status = {
    "is_running": False,
    "start_time": None,
    "processed_count": 0,
    "total_count": 0,
    "synced_count": 0,
    "errors": [],
    "current_item": None,
    "completed": False,
    "success": False,
    "sync_type": "all" # Added sync_type
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Unmonitarr application...")
    
    # Add volume mount diagnostics
    import os
    logger.info("🔍 Volume mount diagnostics:")
    logger.info(f"📁 Current working directory: {os.getcwd()}")
    logger.info(f"📂 /app exists: {os.path.exists('/app')}")
    logger.info(f"📂 /app/data exists: {os.path.exists('/app/data')}")
    logger.info(f"📂 /app/config exists: {os.path.exists('/app/config')}")
    
    if os.path.exists('/app/data'):
        logger.info(f"📊 /app/data permissions: {oct(os.stat('/app/data').st_mode)[-3:]}")
        logger.info(f"👤 /app/data owner: {os.stat('/app/data').st_uid}:{os.stat('/app/data').st_gid}")
        # List contents of /app/data
        try:
            data_contents = os.listdir('/app/data')
            logger.info(f"📋 /app/data contents: {data_contents}")
        except Exception as e:
            logger.error(f"❌ Cannot list /app/data contents: {e}")
    
    # Initialize database
    await init_database()
    
    # Initialize persistent configuration
    await app_config.initialize()
    
    # Initialize clients
    app.state.jellyfin_client = JellyfinClient(settings.jellyfin_url, settings.jellyfin_api_key)
    app.state.sonarr_client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
    app.state.radarr_client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
    app.state.external_api_client = ExternalAPIClient(settings.omdb_api_key)
    app.state.webhook_handler = WebhookHandler(
        app.state.jellyfin_client,
        app.state.sonarr_client,
        app.state.radarr_client,
        app.state.external_api_client
    )
    
    logger.info("Application startup complete")
    
    yield
    
    # Cleanup
    logger.info("Shutting down application...")
    await close_database()
    await app.state.jellyfin_client.close()
    await app.state.sonarr_client.close()
    await app.state.radarr_client.close()
    await app.state.external_api_client.close()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Unmonitarr",
    description="Sync Jellyfin watched status with Sonarr/Radarr monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
# Get the directory containing the main.py file
src_dir = Path(__file__).parent
unmonitarr_dir = src_dir.parent

app.mount("/static", StaticFiles(directory=str(unmonitarr_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(unmonitarr_dir / "templates"))


@app.get("/api/config/webhook-details")
async def get_webhook_details(request: Request):
    """Get the webhook URL and authorization header."""
    base_url = str(request.base_url)
    webhook_path = app.url_path_for("jellyfin_webhook")
    return {
        "url": f"{base_url.rstrip('/')}{webhook_path}",
        "authorization_header": f"Bearer {app_config.webhook_token}"
    }

@app.post("/api/config/webhook-token/regenerate")
async def regenerate_webhook_token():
    """Generate a new webhook token and save it."""
    new_token = await app_config.regenerate_webhook_token()
    return {
        "message": "Webhook token regenerated successfully.",
        "token": new_token
    }


@app.get("/api/config/status")
async def get_config_status():
    """Get configuration status including persistence information."""
    return {
        "webhook_token_configured": app_config.webhook_token is not None,
        "secret_key_configured": app_config.secret_key is not None,
        "configuration_initialized": app_config.is_initialized(),
        "storage_type": "database",
        "persistent": True
    }


@app.get("/api/debug/database")
async def get_database_debug_info():
    """Get database diagnostic information."""
    import os
    from .config import get_database_path
    
    try:
        db_path = get_database_path()
        db_dir = os.path.dirname(db_path)
        
        # Collect diagnostic information
        debug_info = {
            "database_config": {
                "database_url": settings.database_url,
                "database_path": db_path,
                "database_directory": db_dir
            },
            "file_system": {
                "current_working_directory": os.getcwd(),
                "database_file_exists": os.path.exists(db_path),
                "database_directory_exists": os.path.exists(db_dir),
                "database_directory_writable": os.access(db_dir, os.W_OK) if os.path.exists(db_dir) else False
            },
            "volume_mounts": {
                "app_exists": os.path.exists("/app"),
                "app_data_exists": os.path.exists("/app/data"),
                "app_config_exists": os.path.exists("/app/config")
            }
        }
        
        # Add file system details if available
        if os.path.exists(db_path):
            debug_info["database_file"] = {
                "size_bytes": os.path.getsize(db_path),
                "last_modified": os.path.getmtime(db_path)
            }
        
        if os.path.exists(db_dir):
            import stat
            dir_stat = os.stat(db_dir)
            debug_info["database_directory_info"] = {
                "permissions": oct(dir_stat.st_mode)[-3:],
                "owner_uid": dir_stat.st_uid,
                "owner_gid": dir_stat.st_gid,
                "permissions_readable": stat.filemode(dir_stat.st_mode)
            }
        
        if os.path.exists("/app/data"):
            try:
                debug_info["app_data_contents"] = os.listdir("/app/data")
            except Exception as e:
                debug_info["app_data_contents"] = f"Error listing contents: {str(e)}"
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to collect database debug information"
        }


# Health check endpoint
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    db_healthy = await check_database_health()
    
    # Check external services
    jellyfin_healthy = await app.state.jellyfin_client.check_health()
    sonarr_healthy = await app.state.sonarr_client.check_health()
    radarr_healthy = await app.state.radarr_client.check_health()
    
    services = {
        "database": "healthy" if db_healthy else "unhealthy",
        "jellyfin": "healthy" if jellyfin_healthy else "unhealthy",
        "sonarr": "healthy" if sonarr_healthy else "unhealthy",
        "radarr": "healthy" if radarr_healthy else "unhealthy"
    }
    
    overall_status = "healthy" if all([db_healthy, jellyfin_healthy, sonarr_healthy, radarr_healthy]) else "unhealthy"
    
    return HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services
    )


# Test webhook endpoint to see raw Jellyfin data
@app.post("/webhook/jellyfin/test")
async def jellyfin_webhook_test(request: Request):
    """Test endpoint to capture raw webhook data from Jellyfin."""
    try:
        # Log everything about this request
        logger.info("=== JELLYFIN WEBHOOK TEST ENDPOINT ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Get raw body
        raw_body = await request.body()
        logger.info(f"Raw body ({len(raw_body)} bytes): {raw_body}")
        
        # Try to parse as JSON
        if raw_body:
            try:
                body_text = raw_body.decode('utf-8')
                logger.info(f"Body as text: {body_text}")
                
                import json
                payload = json.loads(body_text)
                logger.info(f"Parsed JSON: {json.dumps(payload, indent=2)}")
                
                # Log each field individually
                for key, value in payload.items():
                    logger.info(f"Field '{key}': {repr(value)}")
                    
            except Exception as e:
                logger.error(f"Failed to parse body: {e}")
        
        logger.info("=== END WEBHOOK TEST ===")
        return {"status": "test_received", "message": "Check logs for details"}
        
    except Exception as e:
        logger.error(f"Error in test webhook: {e}")
        return {"status": "error", "message": str(e)}

# Webhook endpoint for Jellyfin
@app.post("/webhook/jellyfin")
async def jellyfin_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Receive webhooks from Jellyfin."""
    try:
        # Validate webhook token first
        if app_config.webhook_token:
            auth_header = request.headers.get("Authorization")
            if not auth_header or auth_header != f"Bearer {app_config.webhook_token}":
                logger.warning(f"Invalid webhook token. Expected: Bearer {app_config.webhook_token}, Got: {auth_header}")
                raise HTTPException(status_code=401, detail="Invalid webhook token")
        
        # Handle different content types and empty bodies
        content_type = request.headers.get("content-type", "").lower()
        raw_body = await request.body()
        
        logger.info(f"Webhook received - Content-Type: {content_type}, Body length: {len(raw_body)}")
        
        # Handle empty body (common with "Send All" disabled or misconfigured template)
        if not raw_body:
            logger.warning("Received webhook with empty body. Check Jellyfin webhook configuration.")
            logger.info("Try enabling 'Send All' or 'Ignore Template' in Jellyfin webhook settings.")
            return {"status": "accepted", "message": "Empty webhook body received - check Jellyfin configuration"}
        
        # Try to parse JSON payload
        try:
            if "application/json" in content_type:
                payload = await request.json()
            else:
                # Try to parse as JSON even if content-type is wrong
                body_text = raw_body.decode('utf-8')
                import json
                payload = json.loads(body_text)
                
            logger.info(f"Parsed webhook payload: {payload}")
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse webhook body as JSON: {e}")
            logger.error(f"Raw body: {raw_body}")
            raise HTTPException(status_code=422, detail="Invalid JSON payload")
        
        # Handle empty or malformed template responses
        if isinstance(payload, dict) and all(v == "" for v in payload.values() if isinstance(v, str)):
            logger.warning("Received webhook with all empty string values - template substitution failed")
            logger.info("Please check your Jellyfin webhook template configuration or enable 'Send All'")
            return {"status": "accepted", "message": "Empty template data - check Jellyfin webhook configuration"}
        
        # Process webhook in background
        background_tasks.add_task(
            app.state.webhook_handler.process_webhook,
            payload
        )
        
        return {"status": "accepted", "message": "Webhook received and queued for processing"}
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail="Internal server error")




# API endpoints for media management
@app.get("/api/media", response_model=List[MediaItemResponse])
async def get_media_items(
    skip: int = 0,
    limit: int = 100,
    media_type: Optional[str] = None,
    db=Depends(get_db)
):
    """Get list of media items."""
    # This will be implemented once we have the database operations
    return []


@app.get("/api/media/{jellyfin_id}", response_model=MediaItemResponse)
async def get_media_item(jellyfin_id: str, db=Depends(get_db)):
    """Get specific media item."""
    # This will be implemented once we have the database operations
    raise HTTPException(status_code=404, detail="Media item not found")


# Web UI routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def configuration(request: Request):
    """Configuration page."""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    """Logs page."""
    return templates.TemplateResponse("logs.html", {"request": request})


# Debug endpoint to test logic
@app.get("/debug/logic/test")
async def debug_logic_test(watched: bool = True):
    """Test the sync logic for a given watched status."""
    should_monitor = not watched
    action_text = "monitor" if should_monitor else "unmonitor"
    
    return {
        "input": {
            "jellyfin_watched": watched
        },
        "output": {
            "sonarr_radarr_monitor": should_monitor,
            "action": action_text
        },
        "explanation": f"Jellyfin watched={watched} → Sonarr/Radarr monitor={should_monitor} (will {action_text})"
    }

# Debug endpoint for Sonarr series
@app.get("/debug/sonarr/series")
async def debug_sonarr_series():
    """Debug endpoint to see all Sonarr series."""
    try:
        series_list = await app.state.sonarr_client.get_all_series()
        return {
            "total_series": len(series_list),
            "series": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "year": s.get("year"),
                    "tvdbId": s.get("tvdbId"),
                    "imdbId": s.get("imdbId"),
                    "alternateTitles": s.get("alternateTitles", [])
                }
                for s in series_list[:20]  # First 20 series
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get Sonarr series: {e}")
        return {"error": str(e)}

# Debug endpoint for Radarr movies  
@app.get("/debug/radarr/movies")
async def debug_radarr_movies():
    """Debug endpoint to see all Radarr movies."""
    try:
        movies_list = await app.state.radarr_client.get_all_movies()
        return {
            "total_movies": len(movies_list),
            "movies": [
                {
                    "id": m.get("id"),
                    "title": m.get("title"), 
                    "year": m.get("year"),
                    "tmdbId": m.get("tmdbId"),
                    "imdbId": m.get("imdbId")
                }
                for m in movies_list[:20]  # First 20 movies
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get Radarr movies: {e}")
        return {"error": str(e)}

# Debug endpoint for manual matching test
@app.get("/debug/match/{title}")
async def debug_match_series(title: str):
    """Debug endpoint to test series matching."""
    try:
        # Test Sonarr matching
        sonarr_matches = await app.state.sonarr_client.search_series_by_title(title)
        
        return {
            "search_title": title,
            "sonarr_matches": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "year": s.get("year"),
                    "tvdbId": s.get("tvdbId")
                }
                for s in sonarr_matches
            ]
        }
    except Exception as e:
        logger.error(f"Failed to test matching for '{title}': {e}")
        return {"error": str(e)}

# Debug endpoint to show webhook extraction capabilities
@app.post("/debug/webhook/extract")
async def debug_webhook_extract(payload: dict):
    """Debug endpoint to test webhook data extraction."""
    try:
        # Extract external IDs using the same logic as the webhook handler
        extracted_data = {
            "original_payload": payload,
            "extracted_ids": {
                "tvdb_id": (
                    payload.get("Provider_tvdb") or 
                    payload.get("ProviderIds", {}).get("Tvdb") or
                    payload.get("ProviderIds", {}).get("tvdb") or
                    payload.get("TvdbId") or
                    payload.get("tvdbId")
                ),
                "imdb_id": (
                    payload.get("Provider_imdb") or 
                    payload.get("ProviderIds", {}).get("Imdb") or
                    payload.get("ProviderIds", {}).get("imdb") or
                    payload.get("ImdbId") or
                    payload.get("imdbId")
                ),
                "tmdb_id": (
                    payload.get("Provider_tmdb") or 
                    payload.get("ProviderIds", {}).get("Tmdb") or
                    payload.get("ProviderIds", {}).get("tmdb") or
                    payload.get("TmdbId") or
                    payload.get("tmdbId")
                )
            },
            "all_provider_fields": {
                key: value for key, value in payload.items() 
                if any(provider in key.lower() for provider in ["provider", "tvdb", "imdb", "tmdb"])
            }
        }
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"Failed to extract webhook data: {e}")
        return {"error": str(e)}

# Debug endpoint to test external ID matching
@app.get("/debug/match/external")
async def debug_external_id_matching(
    title: str,
    tvdb_id: Optional[str] = None,
    imdb_id: Optional[str] = None,
    tmdb_id: Optional[str] = None,
    year: Optional[int] = None,
    media_type: str = "series"  # series or movie
):
    """Debug endpoint to test external ID matching."""
    try:
        if media_type.lower() == "movie":
            result = await app.state.radarr_client.find_movie_by_jellyfin_metadata(
                title=title,
                year=year,
                tmdb_id=tmdb_id,
                imdb_id=imdb_id
            )
            service = "radarr"
        else:
            result = await app.state.sonarr_client.find_series_by_jellyfin_metadata(
                title=title,
                year=year,
                tvdb_id=tvdb_id,
                imdb_id=imdb_id
            )
            service = "sonarr"
        
        return {
            "input": {
                "title": title,
                "year": year,
                "tvdb_id": tvdb_id,
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "service": service
            },
            "match_found": result is not None,
            "result": result if result else "No match found"
        }
        
    except Exception as e:
        logger.error(f"Failed to test external ID matching: {e}")
        return {"error": str(e)}

# Debug endpoint to test external API search
@app.get("/debug/external/search")
async def debug_external_api_search(
    title: str,
    media_type: str = "series",
    year: Optional[int] = None,
    imdb_id: Optional[str] = None
):
    """Debug endpoint to test external API search."""
    try:
        external_client = app.state.external_api_client
        
        existing_ids = {}
        if imdb_id:
            existing_ids["imdb_id"] = imdb_id
        
        result = await external_client.find_best_match(
            title=title,
            media_type=media_type,
            year=year,
            existing_ids=existing_ids if existing_ids else None
        )
        
        return {
            "input": {
                "title": title,
                "media_type": media_type,
                "year": year,
                "existing_imdb_id": imdb_id
            },
            "external_api_configured": external_client.omdb_api_key is not None,
            "match_found": result is not None,
            "result": result if result else "No match found"
        }
        
    except Exception as e:
        logger.error(f"Failed to test external API search: {e}")
        return {"error": str(e)}

# Background task function
async def perform_bulk_sync(sync_type: str = "all"):
    """Perform bulk sync of all Jellyfin media to Sonarr/Radarr."""
    global bulk_sync_status
    
    try:
        # Initialize the status
        bulk_sync_status.update({
            "is_running": True,
            "start_time": datetime.utcnow().isoformat(),
            "processed_count": 0,
            "total_count": 0,
            "synced_count": 0,
            "errors": [],
            "current_item": None,
            "completed": False,
            "success": False,
            "sync_type": sync_type # Set the sync type
        })
        
        logger.info(f"🔄 Starting bulk sync process for type: {sync_type}...")
        logger.info("🔧 Bulk sync uses force_sync=True to process all items regardless of status changes")
        
        if not app.state.jellyfin_client:
            logger.error("❌ Jellyfin client not initialized")
            bulk_sync_status.update({
                "completed": True,
                "success": False,
                "is_running": False,
                "errors": [{"general": "Jellyfin client not initialized", "timestamp": datetime.utcnow().isoformat()}]
            })
            return
        
        # Get all users from Jellyfin  
        users = await app.state.jellyfin_client.get_users()
        if not users:
            logger.warning("⚠️ No users found in Jellyfin")
            bulk_sync_status.update({
                "completed": True,
                "success": False,
                "is_running": False,
                "errors": [{"general": "No users found in Jellyfin", "timestamp": datetime.utcnow().isoformat()}]
            })
            return
        
        # For now, use the first user (could be extended to support multiple users)
        user = users[0]
        user_id = user.get("Id")
        username = user.get("Name", "Unknown")
        
        logger.info(f"👤 Syncing for user: {username} ({user_id})")
        
        # Get all media items for the user, filtered by sync_type
        if sync_type == "movies":
            all_items = await app.state.jellyfin_client.get_all_movies_for_user(user_id)
        elif sync_type == "series":
            all_items = await app.state.jellyfin_client.get_all_series_for_user(user_id)
        else: # "all" or any other value
            all_items = await app.state.jellyfin_client.get_all_media_for_user(user_id)
        
        if not all_items:
            logger.warning(f"⚠️ No {sync_type} media items found for user")
            bulk_sync_status.update({
                "completed": True,
                "success": False,
                "is_running": False,
                "errors": [{"general": f"No {sync_type} media items found for user", "timestamp": datetime.utcnow().isoformat()}]
            })
            return
        
        # Update total count
        bulk_sync_status["total_count"] = len(all_items)
        logger.info(f"📊 Found {len(all_items)} media items to process")
        
        # Process each media item
        for item in all_items:
            try:
                # Extract media info
                media_info = app.state.jellyfin_client.extract_media_info(item)
                if not media_info:
                    continue
                    
                # Update current item being processed
                bulk_sync_status["current_item"] = media_info.get("title", "Unknown")
                bulk_sync_status["processed_count"] += 1
                
                # Create webhook-like data for processing
                webhook_data = {
                    "event_type": "UserDataSaved",
                    "jellyfin_id": media_info["jellyfin_id"],
                    "user_id": user_id,
                    "is_watched": media_info.get("is_watched", False),
                    "item_name": media_info.get("title", ""),
                    "item_type": media_info.get("media_type", "unknown"),
                    "username": username,
                    "timestamp": datetime.utcnow(),
                    # Add series info for episodes
                    "series_name": item.get("SeriesName"),
                    "series_id": item.get("SeriesId"),
                    "season_number": item.get("ParentIndexNumber"),
                    "episode_number": item.get("IndexNumber"),
                    # Provider IDs
                    "Provider_tvdb": item.get("ProviderIds", {}).get("Tvdb"),
                    "Provider_imdb": item.get("ProviderIds", {}).get("Imdb"),
                    "Provider_tmdb": item.get("ProviderIds", {}).get("Tmdb"),
                    "year": item.get("ProductionYear")
                }
                
                # Process through webhook handler with force_sync=True for bulk operations
                await app.state.webhook_handler.process_webhook(webhook_data, force_sync=True)
                bulk_sync_status["synced_count"] += 1
                
                # Add small delay to prevent overwhelming the system
                if bulk_sync_status["processed_count"] % 10 == 0:
                    await asyncio.sleep(1)
                    logger.info(f"📈 Progress: {bulk_sync_status['processed_count']}/{len(all_items)} items processed, {bulk_sync_status['synced_count']} synced")
                    
            except Exception as item_error:
                error_entry = {
                    "item": item.get("Name", "Unknown"),
                    "error": str(item_error),
                    "timestamp": datetime.utcnow().isoformat()
                }
                bulk_sync_status["errors"].append(error_entry)
                logger.error(f"❌ Error processing item {item.get('Name', 'Unknown')}: {item_error}")
                continue
        
        # Mark as completed with success
        bulk_sync_status.update({
            "completed": True,
            "success": True,
            "is_running": False
        })
        
        logger.info(f"✅ Bulk sync completed: {bulk_sync_status['processed_count']} items processed, {bulk_sync_status['synced_count']} synced")
        
    except Exception as e:
        # Mark as completed with error
        bulk_sync_status.update({
            "completed": True,
            "success": False,
            "is_running": False,
            "errors": [{"general": str(e), "timestamp": datetime.utcnow().isoformat()}]
        })
        
        logger.error(f"❌ Bulk sync failed: {e}")
        logger.exception("Full bulk sync error traceback:")


# API Info endpoint
@app.get("/api/info")
async def api_info():
    """Get API information."""
    return {
        "name": "Unmonitarr",
        "version": "1.0.0",
        "description": "Sync Jellyfin watched status with Sonarr/Radarr monitoring",
        "settings": {
            "auto_sync_enabled": settings.auto_sync_enabled,
            "sync_delay_seconds": settings.sync_delay_seconds,
            "log_level": settings.log_level,
            "use_external_api": settings.use_external_api,
            "omdb_api_configured": bool(settings.omdb_api_key)
        }
    }


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    from .database import get_db_session
    from .models import MediaItem, SyncLog, SonarrMapping, RadarrMapping
    from sqlalchemy import select, func, and_
    from datetime import datetime, timedelta
    
    async with get_db_session() as db:
        # Total media items
        total_media_result = await db.execute(select(func.count(MediaItem.id)))
        total_media = total_media_result.scalar()
        
        # Watched items
        watched_result = await db.execute(select(func.count(MediaItem.id)).where(MediaItem.is_watched == True))
        watched_items = watched_result.scalar()
        
        # Total sync actions (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sync_actions_result = await db.execute(
            select(func.count(SyncLog.id)).where(SyncLog.created_at >= thirty_days_ago)
        )
        sync_actions = sync_actions_result.scalar()
        
        # Success rate (last 30 days)
        successful_syncs_result = await db.execute(
            select(func.count(SyncLog.id)).where(
                and_(SyncLog.created_at >= thirty_days_ago, SyncLog.status == "completed")
            )
        )
        successful_syncs = successful_syncs_result.scalar()
        success_rate = (successful_syncs / sync_actions * 100) if sync_actions > 0 else 0
        
        # Media breakdown by type
        media_types_result = await db.execute(
            select(MediaItem.media_type, func.count(MediaItem.id))
            .group_by(MediaItem.media_type)
        )
        media_types = {row[0]: row[1] for row in media_types_result.fetchall()}
        
        # Mappings count
        sonarr_mappings_result = await db.execute(select(func.count(SonarrMapping.id)))
        sonarr_mappings = sonarr_mappings_result.scalar()
        
        radarr_mappings_result = await db.execute(select(func.count(RadarrMapping.id)))
        radarr_mappings = radarr_mappings_result.scalar()
        
        return {
            "total_media": total_media,
            "watched_items": watched_items,
            "unwatched_items": total_media - watched_items,
            "sync_actions": sync_actions,
            "success_rate": round(success_rate, 1),
            "media_types": media_types,
            "sonarr_mappings": sonarr_mappings,
            "radarr_mappings": radarr_mappings,
            "watch_percentage": round((watched_items / total_media * 100) if total_media > 0 else 0, 1)
        }


@app.get("/api/logs/recent")
async def get_recent_logs(limit: int = 10):
    """Get recent sync logs."""
    from .database import get_db_session
    from .models import SyncLog, MediaItem
    from sqlalchemy import select, desc
    from sqlalchemy.orm import aliased
    
    async with get_db_session() as db:
        # Get recent logs with media item info (series_name is now stored directly)
        stmt = (
            select(SyncLog, MediaItem)
            .join(MediaItem, SyncLog.media_item_id == MediaItem.id, isouter=True)
            .order_by(desc(SyncLog.created_at))
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        logs = []
        
        for row in result.fetchall():
            log = row[0]  # SyncLog object
            media_item = row[1]  # MediaItem object
            
            logs.append({
                "id": log.id,
                "action": log.action,
                "status": log.status,
                "service": log.service,
                "title": media_item.title if media_item else log.series_name,
                "media_type": media_item.media_type if media_item else "unknown",
                "season_number": media_item.season_number if media_item else None,
                "episode_number": media_item.episode_number if media_item else None,
                "series_name": media_item.series_name if media_item else log.series_name,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
                "updated_at": log.updated_at.isoformat()
            })
        
        return logs


@app.get("/api/logs")
async def get_logs(
    limit: int = 50,
    skip: int = 0,
    status: Optional[str] = None,
    service: Optional[str] = None,
    action: Optional[str] = None,
    date_range: Optional[str] = None
):
    """Get sync logs with filtering and pagination."""
    from .database import get_db_session
    from .models import SyncLog, MediaItem
    from sqlalchemy import select, desc, and_
    from sqlalchemy.orm import aliased
    from datetime import datetime, timedelta
    
    async with get_db_session() as db:
        # Build base query (series_name is now stored directly)
        stmt = (
            select(SyncLog, MediaItem)
            .join(MediaItem, SyncLog.media_item_id == MediaItem.id, isouter=True)
            .order_by(desc(SyncLog.created_at))
        )
        
        # Apply filters
        conditions = []
        
        if status:
            conditions.append(SyncLog.status == status)
        
        if service:
            conditions.append(SyncLog.service == service)
            
        if action:
            conditions.append(SyncLog.action == action)
            
        if date_range:
            now = datetime.utcnow()
            if date_range == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                conditions.append(SyncLog.created_at >= start_date)
            elif date_range == "week":
                start_date = now - timedelta(days=7)
                conditions.append(SyncLog.created_at >= start_date)
            elif date_range == "month":
                start_date = now - timedelta(days=30)
                conditions.append(SyncLog.created_at >= start_date)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        logs = []
        
        for row in result.fetchall():
            log = row[0]  # SyncLog object
            media_item = row[1]  # MediaItem object
            
            logs.append({
                "id": log.id,
                "action": log.action,
                "status": log.status,
                "service": log.service,
                "title": media_item.title if media_item else log.series_name,
                "media_type": media_item.media_type if media_item else "unknown",
                "season_number": media_item.season_number if media_item else None,
                "episode_number": media_item.episode_number if media_item else None,
                "series_name": media_item.series_name if media_item else log.series_name,
                "jellyfin_id": media_item.jellyfin_id if media_item else "unknown",
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
                "updated_at": log.updated_at.isoformat()
            })
        
        return logs


@app.get("/api/logs/{log_id}")
async def get_log_detail(log_id: int):
    """Get detailed information for a specific log entry."""
    from .database import get_db_session
    from .models import SyncLog, MediaItem
    from sqlalchemy import select
    from sqlalchemy.orm import aliased
    
    async with get_db_session() as db:
        # Get specific log with media item info (series_name is now stored directly)
        stmt = (
            select(SyncLog, MediaItem)
            .join(MediaItem, SyncLog.media_item_id == MediaItem.id, isouter=True)
            .where(SyncLog.id == log_id)
        )
        
        result = await db.execute(stmt)
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Log entry not found")
        
        log = row[0]  # SyncLog object
        media_item = row[1]  # MediaItem object
        
        return {
            "id": log.id,
            "action": log.action,
            "status": log.status,
            "service": log.service,
            "title": media_item.title if media_item else log.series_name,
            "media_type": media_item.media_type if media_item else "unknown",
            "season_number": media_item.season_number if media_item else None,
            "episode_number": media_item.episode_number if media_item else None,
            "series_name": media_item.series_name if media_item else log.series_name,
            "jellyfin_id": media_item.jellyfin_id if media_item else "unknown",
            "external_id": log.external_id,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat(),
            "updated_at": log.updated_at.isoformat()
        }


@app.post("/api/logs/{log_id}/retry")
async def retry_sync_action(
    log_id: int,
    background_tasks: BackgroundTasks,
    force: bool = False
):
    """Retry a failed sync action from the logs."""
    from .database import get_db_session
    from .models import SyncLog, MediaItem
    from sqlalchemy import select
    
    async with get_db_session() as db:
        # Get the log entry
        stmt = (
            select(SyncLog, MediaItem)
            .join(MediaItem, SyncLog.media_item_id == MediaItem.id, isouter=True)
            .where(SyncLog.id == log_id)
        )
        
        result = await db.execute(stmt)
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Log entry not found")
        
        log = row[0]  # SyncLog object
        media_item = row[1]  # MediaItem object
        
        # Check if retry is allowed
        if log.status == "completed" and not force:
            raise HTTPException(
                status_code=400, 
                detail="Cannot retry completed sync. Use force=true to override."
            )
        
        if log.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="Sync is currently processing. Please wait for completion."
            )
        
        try:
            # Get media item details for retry
            if not media_item:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot retry sync: Media item not found in database"
                )
            
            # Create webhook-like data for reprocessing
            webhook_data = {
                "event_type": "UserDataSaved",
                "jellyfin_id": media_item.jellyfin_id,
                "user_id": "retry_user",  # Special user ID for retry operations
                "is_watched": media_item.is_watched,
                "item_name": media_item.title,
                "item_type": media_item.media_type,
                "username": "retry",
                "timestamp": datetime.utcnow(),
                "series_name": media_item.series_name,
                "season_number": media_item.season_number,
                "episode_number": media_item.episode_number,
                # Add provider IDs if available
                "retry_mode": True,
                "original_log_id": log_id
            }
            
            # Mark log as processing
            log.status = "processing"
            log.error_message = None
            log.updated_at = datetime.utcnow()
            await db.commit()
            
            # Process through webhook handler in background
            background_tasks.add_task(
                app.state.webhook_handler.process_webhook,
                webhook_data,
                force_sync=True
            )
            
            logger.info(f"🔄 Retry initiated for log ID {log_id}: {media_item.title}")
            
            return {
                "status": "retry_started",
                "message": f"Retry initiated for {media_item.title}",
                "log_id": log_id,
                "media_title": media_item.title
            }
            
        except Exception as e:
            # Revert log status on error
            log.status = "failed"
            log.error_message = f"Retry failed: {str(e)}"
            log.updated_at = datetime.utcnow()
            await db.commit()
            
            logger.error(f"❌ Failed to retry sync for log ID {log_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initiate retry: {str(e)}"
            )


@app.post("/api/logs/retry/bulk")
async def retry_failed_syncs(
    background_tasks: BackgroundTasks,
    limit: int = 10,
    hours_back: int = 24
):
    """Retry multiple failed sync actions in bulk."""
    from .database import get_db_session
    from .models import SyncLog, MediaItem
    from sqlalchemy import select, and_
    from datetime import timedelta
    
    async with get_db_session() as db:
        # Get failed logs from the last X hours
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        stmt = (
            select(SyncLog, MediaItem)
            .join(MediaItem, SyncLog.media_item_id == MediaItem.id, isouter=True)
            .where(and_(
                SyncLog.status == "failed",
                SyncLog.created_at >= cutoff_time
            ))
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        failed_logs = result.fetchall()
        
        if not failed_logs:
            return {
                "status": "no_failed_logs",
                "message": f"No failed logs found in the last {hours_back} hours",
                "retried_count": 0
            }
        
        retried_count = 0
        errors = []
        
        for row in failed_logs:
            log = row[0]
            media_item = row[1]
            
            if not media_item:
                continue
                
            try:
                # Create webhook data for retry
                webhook_data = {
                    "event_type": "UserDataSaved",
                    "jellyfin_id": media_item.jellyfin_id,
                    "user_id": "bulk_retry_user",
                    "is_watched": media_item.is_watched,
                    "item_name": media_item.title,
                    "item_type": media_item.media_type,
                    "username": "bulk_retry",
                    "timestamp": datetime.utcnow(),
                    "series_name": media_item.series_name,
                    "season_number": media_item.season_number,
                    "episode_number": media_item.episode_number,
                    "retry_mode": True,
                    "original_log_id": log.id
                }
                
                # Mark as processing
                log.status = "processing"
                log.error_message = None
                log.updated_at = datetime.utcnow()
                
                # Queue for background processing
                background_tasks.add_task(
                    app.state.webhook_handler.process_webhook,
                    webhook_data,
                    force_sync=True
                )
                
                retried_count += 1
                
            except Exception as e:
                errors.append({
                    "log_id": log.id,
                    "media_title": media_item.title if media_item else "Unknown",
                    "error": str(e)
                })
        
        await db.commit()
        
        logger.info(f"🔄 Bulk retry initiated for {retried_count} failed syncs")
        
        return {
            "status": "bulk_retry_started",
            "message": f"Initiated retry for {retried_count} failed syncs",
            "retried_count": retried_count,
            "errors": errors[:5]  # Only return first 5 errors
        }


@app.get("/api/sync/bulk/status")
async def get_bulk_sync_status():
    """Get current bulk sync status."""
    return {
        "is_running": bulk_sync_status["is_running"],
        "progress": {
            "processed": bulk_sync_status["processed_count"],
            "total": bulk_sync_status["total_count"],
            "synced": bulk_sync_status["synced_count"],
            "percentage": (bulk_sync_status["processed_count"] / max(bulk_sync_status["total_count"], 1)) * 100
        },
        "current_item": bulk_sync_status["current_item"],
        "start_time": bulk_sync_status["start_time"],
        "errors": bulk_sync_status["errors"][-5:],  # Last 5 errors
        "completed": bulk_sync_status["completed"],
        "success": bulk_sync_status["success"],
        "sync_type": bulk_sync_status["sync_type"] # Include sync_type
    }


@app.post("/api/sync/bulk")
async def bulk_sync_jellyfin(background_tasks: BackgroundTasks):
    """Sync all Jellyfin watched status to Sonarr/Radarr monitoring."""
    try:
        # Check if a sync is already running
        if bulk_sync_status["is_running"]:
            return JSONResponse(
                content={"error": "A bulk sync is already in progress"},
                status_code=409
            )
        
        # This endpoint will fetch all media from Jellyfin and sync their watched status
        logger.info("🚀 Starting bulk sync of all Jellyfin media...")
        
        # Add background task for bulk sync
        background_tasks.add_task(perform_bulk_sync, "all")
        
        return {
            "message": "Bulk sync started in background", 
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Failed to start bulk sync: {e}")
        return JSONResponse(
            content={"error": f"Failed to start bulk sync: {str(e)}"},
            status_code=500
        )

@app.post("/api/sync/bulk/movies")
async def bulk_sync_movies(background_tasks: BackgroundTasks):
    """Sync all Jellyfin movies watched status to Radarr monitoring."""
    try:
        if bulk_sync_status["is_running"]:
            return JSONResponse(
                content={"error": "A bulk sync is already in progress"},
                status_code=409
            )
        
        logger.info("🚀 Starting bulk sync of Jellyfin movies...")
        background_tasks.add_task(perform_bulk_sync, "movies")
        
        return {
            "message": "Bulk movie sync started in background", 
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Failed to start bulk movie sync: {e}")
        return JSONResponse(
            content={"error": f"Failed to start bulk movie sync: {str(e)}"},
            status_code=500
        )

@app.post("/api/sync/bulk/series")
async def bulk_sync_series(background_tasks: BackgroundTasks):
    """Sync all Jellyfin series (episodes) watched status to Sonarr monitoring."""
    try:
        if bulk_sync_status["is_running"]:
            return JSONResponse(
                content={"error": "A bulk sync is already in progress"},
                status_code=409
            )
        
        logger.info("🚀 Starting bulk sync of Jellyfin series...")
        background_tasks.add_task(perform_bulk_sync, "series")
        
        return {
            "message": "Bulk series sync started in background", 
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Failed to start bulk series sync: {e}")
        return JSONResponse(
            content={"error": f"Failed to start bulk series sync: {str(e)}"},
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8088, reload=True)