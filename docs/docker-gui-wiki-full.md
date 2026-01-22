# Docker GUI (WebUI)

The Upload-Assistant WebUI provides a browser-based interface for selecting content and running uploads without needing command-line access.

---

## Supported Architectures

The WebUI Docker images are built for multiple architectures:

| Architecture | Platform | Examples |
|-------------|----------|----------|
| `linux/amd64` | Intel/AMD 64-bit | Most desktop PCs, Intel Macs, cloud VMs |
| `linux/arm64` | ARM 64-bit | Apple Silicon Macs, Raspberry Pi 4/5, AWS Graviton, Oracle Ampere |

Docker will automatically pull the correct image for your system architecture.

---

## Available WebUI Image Tags

| Tag | Description |
|-----|-------------|
| `<version>-webui` | Specific release version with WebUI (e.g., `v6.3.1-webui`) |
| `<branch>-webui` | Specific branch build with WebUI | Not recommended unless you know what you are doing.

**Note:** The standard `latest` tag does NOT include WebUI. You must use a `-webui` suffixed tag appended to a version.

---

## Prerequisites

Before installing, please review:

1. [Docker Wiki](https://github.com/Audionut/Upload-Assistant/wiki/Docker) - General Docker instructions
2. [Web UI Documentation](https://github.com/Audionut/Upload-Assistant/blob/master/docs/web-ui.md) - Detailed WebUI configuration options

---

## Standard Installation

### Step 1: Create Directory Structure

Create your Upload-Assistant folder with a data subfolder:

```bash
mkdir -p /path/to/Upload-Assistant/data
mkdir -p /path/to/Upload-Assistant/tmp
```

### Step 2: Add Configuration

**Option 1: Use existing config.py**
Copy your `config.py` into the data folder:

```bash
cp config.py /path/to/Upload-Assistant/data/
```

**Option 2: Let WebUI create config automatically**
If you don't have a `config.py` file yet, the WebUI will create one automatically from the example config when you first access it. The volume mount will ensure the created config persists on your host.

### Step 3: Download docker-compose.yml

Download the [docker-compose.yml](https://github.com/Audionut/Upload-Assistant/blob/master/docker-compose.yml) from GitHub and place it in your Upload-Assistant folder.

### Step 4: Configure docker-compose.yml

Edit the file to configure:
- **Ports**: Default is localhost-only (`127.0.0.1:5000:5000`). Use `0.0.0.0:5000:5000` (or `5000:5000`) to allow access from other devices.
  Note: this is typically LAN access, but it can become WAN exposure if you port-forward, enable UPnP, or reverse-proxy it.
- **Volume mounts**: Update paths to match your system
- **Network**: Set to your torrent client's network

Example docker-compose.yml:

```yaml
services:
  upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:master-webui
    container_name: UA
    restart: unless-stopped
    # Optional: Run as non-root for improved security
    # user: "1000:1000"
    networks:
      - yournetwork  # Change to the network with your torrent instance
    ports: 
      # Localhost-only on the Docker host (recommended default).
      # Change to "0.0.0.0:5000:5000" (or "5000:5000") to allow access from other devices.
      # Note: this is typically LAN access, but it can become WAN exposure if you port-forward, enable UPnP,
      # run a reverse proxy, or otherwise expose the host publicly.
      - "127.0.0.1:5000:5000"
    environment:
      - ENABLE_WEB_UI=true
      # Bind inside the container so the host port mapping works
      - UA_WEBUI_HOST=0.0.0.0
      - UA_WEBUI_PORT=5000
      # Required: allowlisted roots the Web UI is allowed to browse/execute within
      # Using a specific subfolder is not working correctly, use the top folder as needed. for instance, /data, not /data/torrents
      - UA_BROWSE_ROOTS=/data,/Upload-Assistant/tmp
      # Optional: enable HTTP Basic Auth for the Web UI/API (recommended if exposed beyond localhost)
      # - UA_WEBUI_USERNAME=admin
      # - UA_WEBUI_PASSWORD=change-me
      # Optional: only needed if you serve the UI from a different origin/domain
      # - UA_WEBUI_CORS_ORIGINS=https://your-ui-host
    entrypoint: /bin/bash
    command: -c "source /venv/bin/activate && python /Upload-Assistant/upload.py --webui 0.0.0.0:5000 & tail -f /dev/null"
    volumes:
      - /path/to/torrents/:/data/torrents/:rw #map this to qbit download location, map exactly as qbittorent template on both sides.
      - /mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw # Optional: will be created automatically if missing
      - /mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir:rw #map this to your qbittorrent bt_backup
      - /mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw #map this to your /tmp folder.
      # - /mnt/user/appdata/Upload-Assistant/webui-auth:/root/.config/UploadAssistant:rw # Optional: persist web UI session auth config
networks:
  "yournetwork":
    external: true
```

### Step 5: Start the Container

Navigate to your Upload-Assistant directory and run:

```bash
cd /path/to/Upload-Assistant/
docker compose up -d
```

### Step 6: Access the WebUI

Open your browser and navigate to:
- Localhost-only default: `http://localhost:5000` (on the Docker host)
- Access from other devices: change the compose `ports` line to `0.0.0.0:5000:5000` (or `5000:5000`), then use `http://[your-server-ip]:5000`

Security note: if you enable access from other devices, set `UA_WEBUI_USERNAME` and `UA_WEBUI_PASSWORD` and do not port-forward this service to the internet.

**Enjoy!**

---

## Unraid Installation

### Prerequisites

Make sure you have the Compose plugin installed from Community Applications:
https://forums.unraid.net/topic/38582-plug-in-community-applications

### Step 1: Create New Stack

1. Go to the Compose plugin
2. Click **Add New Stack**
3. Name it: `Upload-Assistant`

### Step 2: Set Appdata Path

1. Click **Advanced**
2. Set the appdata path to:

```
/mnt/user/appdata/Upload-Assistant/
```

3. Click **OK**

### Step 3: Configure Compose File

1. Click the **Gear Icon** next to the stack name
2. Select **Edit Stack** → **Compose File**
3. Copy the [docker-compose.yml](https://github.com/Audionut/Upload-Assistant/blob/master/docker-compose.yml) from GitHub into the compose editor
4. Update the file:
   - Set desired ports
   - Update volume paths for your Unraid setup
   - Set network to match your torrent client

Example Unraid docker-compose.yml:

```yaml
services:
  upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:master-webui
    container_name: UA
    restart: unless-stopped
    # Optional: Run as non-root (use Unraid's nobody:users)
    # user: "99:100"
    networks:
      - br0  # Or your custom network
    ports: 
      # Unraid users typically access the UI from another machine on the LAN.
      # Use localhost-only ("127.0.0.1:5000:5000") if you intentionally want host-only access.
      - "0.0.0.0:5000:5000"
    environment:
      - ENABLE_WEB_UI=true
      - UA_WEBUI_HOST=0.0.0.0
      - UA_WEBUI_PORT=5000
      - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
      # RECOMMENDED: Set web UI authentication credentials via environment variables, else OS keyring will be used if available.
      # - UA_WEBUI_USERNAME=admin
      # - UA_WEBUI_PASSWORD=change-me
    entrypoint: /bin/bash
    command: -c "source /venv/bin/activate && python /Upload-Assistant/upload.py --webui 0.0.0.0:5000 & tail -f /dev/null"
    volumes:
      - /mnt/user/Data/torrents/:/data/torrents/:rw
      - /mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw # Optional: will be created automatically if missing
      - /mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir:rw
      - /mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw
networks:
  "br0":
    external: true
```

5. Click **Save Changes**

### Step 4: Set Stack UI Label (Optional)

If you want an icon-accessible web link in Unraid:

1. Edit the stack UI labels
2. Point it to (requires access from other devices / published port on the host):

```
http://[IP]:5000
```

### Step 5: Start the Stack

Click **Compose Up** and wait for the container to build.

Once built — enjoy!

---

## Running as Non-Root (Optional)

By default, the WebUI container runs as root. For improved security, you can run as a non-root user.

### Standard Systems (UID 1000)

**Step 1: Set directory permissions**

```bash
sudo chown -R 1000:1000 /path/to/Upload-Assistant/data
sudo chown -R 1000:1000 /path/to/Upload-Assistant/tmp
sudo chmod 700 /path/to/Upload-Assistant/tmp
```

**Step 2: Add user directive to docker-compose.yml**

```yaml
services:
  upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:master-webui
    user: "1000:1000"
    # ... rest of config
```

### Unraid (UID 99:100)

**Step 1: Set directory permissions**

```bash
chown -R 99:100 /mnt/user/appdata/Upload-Assistant
chmod 700 /mnt/user/appdata/Upload-Assistant/tmp
```

**Step 2: Add user directive**

```yaml
services:
  upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:master-webui
    user: "99:100"
    # ... rest of config
```

### Important Notes

- Download directories must be readable by the container user
- When running as non-root, all volume-mounted directories must have correct ownership
- If you encounter permission issues, running as root (the default) is still valid

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_WEB_UI` | Yes | `false` | Set to `true` to enable the WebUI |
| `UA_WEBUI_HOST` | No | `127.0.0.1` | IP to bind to (`0.0.0.0` for all interfaces) |
| `UA_WEBUI_PORT` | No | `5000` | Port for the WebUI |
| `UA_BROWSE_ROOTS` | Yes | - | Comma-separated list of allowed browse directories |
| `UA_WEBUI_USERNAME` | No | - | Username for HTTP Basic Auth |
| `UA_WEBUI_PASSWORD` | No | - | Password for HTTP Basic Auth |
| `UA_WEBUI_TOTP_SECRET` | No | - | Base32-encoded TOTP secret for 2FA (takes priority over other storage methods) |
| `UA_WEBUI_CORS_ORIGINS` | No | - | Allowed CORS origins (comma-separated) |

---

## How to Use the WebUI

### Accessing the Interface

After starting the container, access the WebUI at:
- Default: `http://localhost:5000`
- Unraid (with Stack UI Label): Click the container icon and select **WebUI**

### File Browser

Once you load up the GUI front end, you will see your files on the left side of the screen. This is your file browser.

- Files are pathed under `/data/*` (based on your volume mounts)
- Navigate directly to your files and videos
- Select either single files or folders

### Theme Toggle

If you prefer a light theme, use the toggle at the top right corner.

### Running an Upload

1. **Select Content**: Browse and select your file or folder in the left panel
2. **Add Arguments**: In the arguments field, add any additional options (e.g., `-tmdb 12345`)
3. **Execute**: Click **"Execute Upload"**
4. **Monitor**: Watch the terminal output in the interface

**Note:** If text cuts off at any time, zoom out your browser window.

### Canceling an Upload

To cancel a running upload:
- Click the **"Kill & Clear"** button (red) beside the grey executing bar
- This will kill the process and clear the terminal screen

---

## Security Recommendations

### Enable Authentication

If the WebUI is accessible beyond localhost, enable HTTP Basic Auth:

```yaml
environment:
  - UA_WEBUI_USERNAME=admin
  - UA_WEBUI_PASSWORD=your-secure-password
```

### Network Isolation

Keep the WebUI on an internal network when possible. If you must expose it:

1. Use a reverse proxy (nginx, Traefik, Caddy) with HTTPS
2. Enable authentication
3. Consider IP allowlisting

### Browse Roots

Only include directories in `UA_BROWSE_ROOTS` that you actually need to access. This limits what the WebUI can browse and execute against.

---

## Troubleshooting

### WebUI Not Accessible

1. **Check container is running:**
   ```bash
   docker ps | grep UA
   ```

2. **Check logs:**
   ```bash
   docker logs UA
   ```

3. **Verify port mapping:**
   - Ensure the port isn't already in use
   - Check firewall rules

4. **Verify ENABLE_WEB_UI:**
   - Must be set to `true`

### "Browse roots not configured" Error

The `UA_BROWSE_ROOTS` environment variable must be set. Ensure:
- It's defined in your docker-compose.yml
- The paths match your volume mounts (container-side paths)

### Permission Denied Errors (Non-Root Mode)

1. Check directory ownership matches the user running the container
2. Fix ownership:
   ```bash
   # For UID 1000
   sudo chown -R 1000:1000 /path/to/Upload-Assistant
   
   # For Unraid (99:100)
   chown -R 99:100 /mnt/user/appdata/Upload-Assistant
   ```

### Files Not Showing in Browser

1. Verify volume mounts are correct
2. Check `UA_BROWSE_ROOTS` includes the mounted paths
3. Ensure the container user has read access to the directories

### Container Won't Start After Update

After updating to newer images:

1. Pull the latest image:
   ```bash
   docker pull ghcr.io/audionut/upload-assistant:master-webui
   ```

2. Recreate the container:
   ```bash
   docker compose down
   docker compose up -d
   ```
