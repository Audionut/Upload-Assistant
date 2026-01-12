# Docker

There is a docker image available for Upload-Assistant that is automatically built within a few minutes of each release.

See this video which covers many aspects of docker itself, and setting up for UA:
[https://videos.badkitty.zone/ua](https://videos.badkitty.zone/ua) NOTE: The video might be slightly out of date, particularly with regards to permission handling, read below.

---

## Supported Architectures

The Docker images are built for multiple architectures:

| Architecture | Platform | Examples |
|-------------|----------|----------|
| `linux/amd64` | Intel/AMD 64-bit | Most desktop PCs, Intel Macs, cloud VMs |
| `linux/arm64` | ARM 64-bit | Apple Silicon Macs, Raspberry Pi 4/5, AWS Graviton, Oracle Ampere |

Docker will automatically pull the correct image for your system architecture.

---

## Usage

```bash
docker run --rm -it --network=host \
  -v /full/path/to/config.py:/Upload-Assistant/data/config.py \
  -v /full/path/to/downloads:/downloads \
  ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

The paths in your config file need to refer to paths inside the docker image, same with path provided for file. May need to utilize remote path mapping for your client.

**Recommended usage (mounting entire data directory for persistence):**

```bash
docker run --rm -it --network=host \
  -v /full/path/to/ua-data:/Upload-Assistant/data \
  -v /full/path/to/downloads:/downloads \
  ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

Mounting the entire data directory allows:
- Cookies and session data to persist
- Templates to be customized
- Logs and cache to be preserved between runs

---

## Config-generator

```bash
docker run --rm -it --network=host \
  -v /full/path/to/config.py:/Upload-Assistant/data/config.py \
  -v /full/path/to/downloads:/downloads \
  --entrypoint python \
  ghcr.io/audionut/upload-assistant:master /Upload-Assistant/config-generator.py
```

---

## What if I want to utilize re-using torrents and I use qbit?

Add another -v line to your command to expose your BT_Backup folder, and set the path in your config to /BT_Backup

```bash
docker run --rm -it --network=host \
  -v /full/path/to/config.py:/Upload-Assistant/data/config.py \
  -v /full/path/to/downloads:/downloads \
  -v /full/path/to/BT_backup:/BT_backup \
  ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

---

## What if I want to utilize re-using torrents and I use rtorrent/rutorrent?

Add another -v line to your command to expose your session folder, and set the path in your config to /session

```bash
docker run --rm -it --network=host \
  -v /full/path/to/config.py:/Upload-Assistant/data/config.py \
  -v /full/path/to/downloads:/downloads \
  -v /full/path/to/session/folder:/session \
  ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

---

## Available Image Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable release (Standard image, no WebUI) |
| `master` | Latest build from master branch |
| `<version>` | Specific release version (e.g., `v1.2.3`) |
| `<branch>` | Specific branch build |
| `<version>-webui` | Specific version with WebUI included |
| `<branch>-webui` | Branch build with WebUI included |
| `<commit-hash>` | Specific commit (first 6-7 characters) |

**Examples:**
```bash
# Latest stable
ghcr.io/audionut/upload-assistant:latest

# Master branch with WebUI
ghcr.io/audionut/upload-assistant:master-webui

# Specific version
ghcr.io/audionut/upload-assistant:v2.0.0
```

---

## Web UI (Docker / Compose)

Upload Assistant has an optional Web UI (Flask) which is included in the `*-webui` images.

- Use an image tag that includes the Web UI, e.g. `ghcr.io/audionut/upload-assistant:master-webui` or `<version>-webui`.
- Set `ENABLE_WEB_UI=true`.
- Set `UA_BROWSE_ROOTS` (required): a comma-separated list of directories inside the container that the UI is allowed to browse/execute within.

Recommended compose pattern (localhost-only on the Docker host by default):

```yaml
services:
  upload-assistant-webui:
    image: ghcr.io/audionut/upload-assistant:master-webui
    ports:
      # Localhost-only on the Docker host (recommended default).
      # Change to "0.0.0.0:5000:5000" (or "5000:5000") to allow access from other devices.
      # Note: "other devices" typically means LAN, but it can become WAN exposure if you port-forward, enable UPnP,
      # run a reverse proxy, or otherwise expose the host publicly.
      - "127.0.0.1:5000:5000"
    environment:
      - ENABLE_WEB_UI=true
      # Bind inside the container so the host port mapping works.
      - UA_WEBUI_HOST=0.0.0.0
      - UA_WEBUI_PORT=5000
      - UA_BROWSE_ROOTS=/data,/Upload-Assistant/tmp
      # Strongly recommended if you allow access from other devices:
      # - UA_WEBUI_USERNAME=admin
      # - UA_WEBUI_PASSWORD=change-me
    volumes:
      - /path/to/torrents:/data:rw
      - /path/to/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw
      - /path/to/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw

```

For more details (auth, CORS, troubleshooting), see [docs/web-ui.md](web-ui.md).

---

## How do I update the docker image?

```bash
docker pull ghcr.io/audionut/upload-assistant:latest
```

---

## How do I use an image of a specific commit?

```bash
docker run --rm -it --network=host \
  -v /full/path/to/config.py:/Upload-Assistant/data/config.py \
  -v /full/path/to/downloads:/downloads \
  ghcr.io/audionut/upload-assistant:abc123 /downloads/path/to/content --help
```

Where `abc123` is the first 6 digits of the hash of the commit.

---

## Running as Non-Root (Optional)

By default, the container runs as root for maximum compatibility. For improved security or environments that require non-root containers (e.g., Kubernetes with restricted policies), you can run as a non-root user.

### Prerequisites

Before running as non-root, ensure your mounted directories have the correct ownership. The container expects UID:GID `1000:1000`:

```bash
# Set ownership on your data and tmp directories
sudo chown -R 1000:1000 /full/path/to/ua-data
sudo chown -R 1000:1000 /full/path/to/ua-tmp  # Only if mounting tmp

# Ensure tmp has appropriate permissions
sudo chmod 700 /full/path/to/ua-tmp
```

### Docker Run with Non-Root User

```bash
docker run --rm -it --user 1000:1000 --network=host \
  -v /full/path/to/ua-data:/Upload-Assistant/data \
  -v /full/path/to/downloads:/downloads \
  ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

### Docker Compose with Non-Root User

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    user: "1000:1000"
    network_mode: host
    volumes:
      - /full/path/to/ua-data:/Upload-Assistant/data
      - /full/path/to/ua-tmp:/Upload-Assistant/tmp
      - /full/path/to/downloads:/downloads
```

### Troubleshooting Permission Issues

If you encounter "Permission denied" errors when running as non-root:

1. **Check directory ownership:**
   ```bash
   ls -la /full/path/to/ua-data
   ls -la /full/path/to/ua-tmp
   ```
   All files should be owned by `1000:1000`.

2. **Fix ownership recursively:**
   ```bash
   sudo chown -R 1000:1000 /full/path/to/ua-data /full/path/to/ua-tmp
   ```

3. **For download directories:** The user running the container must have read access to your download files. If your downloads are owned by a different user, you may need to:
   - Run as root (default), or
   - Add the container user to a group with read access, or
   - Adjust download directory permissions

> **Note:** Most users can continue running as root (the default). Non-root execution is optional and primarily benefits security-conscious deployments or restricted environments.

---

## What is docker?

Google is your friend.

---

## Can I use this with Docker on Windows?

Yes but this is a linux container so make sure you are running in that mode. Forewarning Docker on Windows is funky and certain features aren't implemented like mounting singular files as a volume, using paths that contain spaces in a volume, and lots more so you are on your own. You will not receive help trying to get it to work.

---

## The command for running is really long and I dont want to type it.

Make an alias or a function or something. Will depend on OS. I use:

```bash
function upload(){
    # save args as array and expand each element inside of ""
    args=("$@")
    args="${args[@]@Q}"
    echo $args
    docker pull ghcr.io/audionut/upload-assistant:latest
    eval "docker run --rm -it --network=host -v /full/path/to/config.py:/Upload-Assistant/data/config.py -v /full/path/to/downloads:/downloads -v /full/path/to/BT_backup:/BT_backup ghcr.io/audionut/upload-assistant:latest ${args}"
}
```

This prints out the parameters passed as well so you can see for sure what is happening.

---

## Can I utilize the -vs/--vapoursynth parameter?

No. The base docker image of alpine does not include vapoursynth in its package manager and building it or downloading portable version into python directory and configuring was decided to not be worth the extra complexity for something that probably gets very little usage and would probably break regularly. If this is important to you let us know.

---

## Can you make the docker image smaller? It takes forever to download

No. FFmpeg and mono are thiccc and are required for functionality (taking screenshots and utilizing bdinfo). This cannot be avoided.
