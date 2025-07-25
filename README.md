# Unmonitarr

**Sync Jellyfin watched status with Sonarr/Radarr monitoring**

Unmonitarr automatically synchronizes your Jellyfin watched/unwatched status with Sonarr and Radarr monitoring to prevent unnecessary upgrade downloads after you've watched content. Especially useful for users who used [TRaSH Guides](https://trash-guides.info/) to setup their media servers.

**Why Unmonitarr?**

I made this because I didn't find any existing solution specifically for Jellyfin. If you are using Plex, you can check out [Unmonitorr](https://github.com/Shraymonks/unmonitorr).

## Features

- 🔄 **Bidirectional Sync**: Watched → Unmonitor, Unwatched → Monitor
- 📅 **Automatic Sync**: Automatically sync when changes are made within Jellyfin
- 📊 **Dashboard**: Web interface for configuration and monitoring

## How It Works

1. **Jellyfin Webhook**: Jellyfin sends webhook when media is marked as watched/unwatched
2. **Intelligent Processing**: Unmonitarr filters and processes status changes
3. **Service Sync**: Updates monitoring status in Sonarr (TV shows) or Radarr (movies)
4. **Database Tracking**: Maintains sync history and mappings

## Quick Start

### Docker Compose (Recommended)

1. **Clone the repository**:
```bash
git clone https://github.com/Baretsky/unmonitarr.git
cd unmonitarr
```

2. **Edit `docker-compose.yml`**:
   Open the `docker-compose.yml` file and update the placeholder values with your actual Jellyfin, Sonarr, and Radarr URLs and API keys. You can also set the timezone and other environment variables as needed.

3. **Deploy**:
```bash
docker-compose up -d
```

4. **Configure Jellyfin Webhook**:
   Access the Unmonitarr web UI at `http://localhost:8088` (or your configured address). Navigate to the **Configuration** page and follow the instructions in the "Webhook Setup" section to configure your Jellyfin Webhook plugin.

### Standalone Docker

```bash
docker run -d \
  --name unmonitarr \
  -p 8088:8088 \
  -v ./data:/app/data \
  -v ./config:/app/config \
  -e JELLYFIN_URL=http://your-jellyfin-ip:8096 \
  -e JELLYFIN_API_KEY=your_jellyfin_api_key \
  -e SONARR_URL=http://your-sonarr-ip:8989 \
  -e SONARR_API_KEY=your_sonarr_api_key \
  -e RADARR_URL=http://your-radarr-ip:7878 \
  -e RADARR_API_KEY=your_radarr_api_key \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=your_secure_admin_password \
  -e OMDB_API_KEY=your_omdb_api_key \
  -e USE_EXTERNAL_API=true \
  -e AUTO_SYNC_ENABLED=true \
  -e SYNC_DELAY_SECONDS=5 \
  -e MAX_REQUESTS_PER_MINUTE=60 \
  -e RETRY_ATTEMPTS=3 \
  -e RETRY_DELAY=2 \
  -e IGNORE_SPECIAL_EPISODES=true \
  -e TZ=Europe/Paris \
  --restart unless-stopped \
  baretsky24/unmonitarr:latest
```

### Docker Compose Example
```yaml
version: '3.8'

services:
  unmonitarr:
    image: baretsky24/unmonitarr:latest
    container_name: unmonitarr
    restart: unless-stopped
    ports:
      - "8088:8088"
    volumes:
      - path/to/data:/app/data
      - path/to/config:/app/config
    environment:
      # -- General Settings --
      - TZ=Europe/London
      - LOG_LEVEL=INFO

      # -- Jellyfin Configuration --
      - JELLYFIN_URL=http://your-jellyfin-ip:8096
      - JELLYFIN_API_KEY=your_jellyfin_api_key

      # -- Sonarr Configuration --
      - SONARR_URL=http://your-sonarr-ip:8989
      - SONARR_API_KEY=your_sonarr_api_key

      # -- Radarr Configuration --
      - RADARR_URL=http://your-radarr-ip:7878
      - RADARR_API_KEY=your_radarr_api_key

      # -- Security & External APIs --
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_admin_password
      - OMDB_API_KEY=your_omdb_api_key # Optional: For better metadata matching
      - USE_EXTERNAL_API=true # Set to false to disable external API lookups

      # -- Sync & Performance --
      - AUTO_SYNC_ENABLED=true
      - SYNC_DELAY_SECONDS=5
      - MAX_REQUESTS_PER_MINUTE=60
      - RETRY_ATTEMPTS=3
      - RETRY_DELAY=2

      # -- Special Episodes Configuration --
      - IGNORE_SPECIAL_EPISODES=true

      # -- Database (Do not change unless you know what you are doing) --
      - DATABASE_URL=sqlite:///app/data/unmonitarr.db
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JELLYFIN_URL` | URL of your Jellyfin server. | `http://localhost:8096` | Yes |
| `JELLYFIN_API_KEY` | API key for your Jellyfin server. | - | Yes |
| `SONARR_URL` | URL of your Sonarr server. | `http://localhost:8989` | Yes |
| `SONARR_API_KEY` | API key for your Sonarr server. | - | Yes |
| `RADARR_URL` | URL of your Radarr server. | `http://localhost:7878` | Yes |
| `RADARR_API_KEY` | API key for your Radarr server. | - | Yes |
| `ADMIN_USERNAME` | Username for accessing the Unmonitarr web UI. | `admin` | No |
| `ADMIN_PASSWORD` | Password for accessing the Unmonitarr web UI. **Change this from default!** | `your_secure_admin_password` | No |
| `OMDB_API_KEY` | Optional: OMDb API key for enhanced metadata matching. Get one from [OMDb API](http://www.omdbapi.com/apikey.aspx). | - | No |
| `USE_EXTERNAL_API` | Enable/disable external API lookups (e.g., OMDb). | `true` | No |
| `AUTO_SYNC_ENABLED` | Enable automatic synchronization of watched status. | `true` | No |
| `SYNC_DELAY_SECONDS` | Delay in seconds before processing a sync request. | `5` | No |
| `MAX_REQUESTS_PER_MINUTE` | Maximum number of API requests per minute to external services. | `60` | No |
| `RETRY_ATTEMPTS` | Number of times to retry failed API requests. | `3` | No |
| `RETRY_DELAY` | Delay in seconds between retry attempts. | `2` | No |
| `TZ` | Timezone for the container (e.g., `Europe/Paris`, `America/New_York`). | `UTC` | No |
| `LOG_LEVEL` | Logging level (e.g., `INFO`, `DEBUG`, `WARNING`, `ERROR`). | `INFO` | No |
| `IGNORE_SPECIAL_EPISODES` | Ignore season 0 (special episodes) when syncing with Sonarr. | `true` | No |
| `DATABASE_URL` | Database connection string. **Do not change unless you know what you are doing.** | `sqlite:///app/data/unmonitarr.db` | No |

### Webhook Setup

Webhook configuration is now managed directly from the Unmonitarr web interface.

1.  Access the Unmonitarr web UI at `http://localhost:8088` (or your configured address).
2.  Navigate to the **Configuration** page.
3.  Follow the instructions in the "Webhook Setup" section to configure your Jellyfin Webhook plugin. This includes copying the generated Webhook URL and Authorization Header Value.
4.  You can also regenerate the webhook token from this page if needed.

## Troubleshooting

### Common Issues

**Webhook not working**:
- Check Jellyfin webhook plugin configuration
- Verify webhook URL is accessible from Jellyfin
- Check Unmonitarr logs for incoming webhook events

**Sync not working**:
- Verify API keys for Sonarr/Radarr
- Check network connectivity between services
- Review sync logs in web interface

**Media not found**:
- Ensure media exists in both Jellyfin and Sonarr/Radarr
- Check title matching (case-sensitive)
- Use manual sync with force flag

### Logs

View application logs:
```bash
docker logs unmonitarr
```

### Health Checks

Monitor service health:
```bash
curl http://localhost:8088/health
```

## Development

### GitHub Actions Setup

This project uses GitHub Actions to automatically build and push Docker images to Docker Hub. To set this up for your fork:

1. **Fork the repository** to your GitHub account

2. **Create a GitHub Environment** (recommended for better security):
   - Go to your GitHub repository → Settings → Environments
   - Create a new environment named `dockerhub`
   - Add the following environment secrets:
     - `DOCKERHUB_USERNAME`: Your Docker Hub username
     - `DOCKERHUB_TOKEN`: Your Docker Hub access token (create one at https://hub.docker.com/settings/security)
   
   *Alternative: You can also add these as repository secrets under Settings → Secrets and variables → Actions, but using environments provides better isolation and control.*

3. **Update the image name** in `.github/workflows/docker-build.yml`:
   - Change `IMAGE_NAME: baretsky24/unmonitarr` to `IMAGE_NAME: yourusername/unmonitarr`
   - Update the environment URL: `url: https://hub.docker.com/r/yourusername/unmonitarr`

4. **Workflow triggers**:
   - **Push to main/develop**: Builds and pushes with branch name as tag (only if code changes in `src/`, `static/`, `templates/`, `Dockerfile`, `requirements.txt`, or `docker-compose.yml`)
   - **Create tag (v*)**: Builds and pushes with semantic versioning tags
   - **Pull requests**: Builds only (no push to registry, same path filters apply)
   - **Manual trigger**: Use workflow_dispatch for manual builds

### Manual Build

To build the Docker image locally:

```bash
# Build for current architecture
docker build -t unmonitarr .

# Build for multiple architectures (requires buildx)
docker buildx build --platform linux/amd64,linux/arm64 -t unmonitarr .
```

## Contributing

Contributions are welcome.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/Baretsky/unmonitarr/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Baretsky/unmonitarr/discussions)

## Related Projects

- [Jellyfin](https://jellyfin.org/) - Media server
- [Sonarr](https://sonarr.tv/) - TV series management
- [Radarr](https://radarr.video/) - Movie management
- [Jellyfin Webhook Plugin](https://github.com/jellyfin/jellyfin-plugin-webhook) - Required for webhooks (available in Jellyfin Plugin Catalog)
