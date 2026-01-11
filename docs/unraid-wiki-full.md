# Install and tips for Unraid

CREDITS: To the author/s at Aither.

---

## Supported Architectures

Upload-Assistant Docker images now support multiple architectures:

| Architecture | Unraid Compatibility |
|-------------|---------------------|
| `linux/amd64` | ✅ Standard Unraid servers (Intel/AMD) |
| `linux/arm64` | ✅ ARM-based systems |

Docker will automatically pull the correct image for your system.

---

## How to install L4G natively on Unraid

**Disclaimer:** This guide comes as is, and I do not claim to be someone who knows how to fix things if you break it.

As unraid is completely focused on docker, I was having issues installing L4g to work on unraid, I also didn't find using the docker image to be easy.

So here are the steps you will need to take to get l4g to work directly on unraid.

### Step 1: Install Nerd Tools

You will need the nerd tools package, this can be installed from CA app. After that enable these packages:

*Not sure which ones are absolutely essential but I got it working with the ones shown in screenshot, you can probably check by uninstalling some and see if it still works.*

### Step 2: Clone the Repository

Open a terminal on unraid, cd to the directory you want to install L4g or make a directory.

```bash
git clone https://github.com/Audionut/Upload-Assistant.git
```

The other stuff is standard steps you have to follow as per audionut's guide that can be found here: https://github.com/Audionut/Upload-Assistant

### Step 3: Install Missing Packages

You will need some missing packages that are not included with nerdtools.

First is grabbing libffi and the steps you have to follow are here:
https://forums.unraid.net/topic/129200-plug-in-nerdtools/page/7/#comment-1192737

### Step 4: Install FFmpeg

The final thing you need is ffmpeg. Make a directory you want to download ffmpeg to then:

```bash
wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz
```

This will download the tar.xz file to the location you are in currently.

Next, unpack this with:

```bash
tar -xf ffmpeg-git-amd64-static.tar.xz
```

This unpacks ffmpeg folder for you. Now cd to the newly unpacked folder, and run:

```bash
cp -r ffmpeg /usr/bin
cp -r ffprobe /usr/bin
```

This adds ffmpeg and ffprobe to be called anywhere.

You now are done, and l4g should work natively.

*Thank you to noraa for all your help, shoutout to deeznuts and ringbear*

---

## Since people were asking how to do it in Unraid when still wanting CLI options, here goes:

1. Create `/mnt/user/appdata/l4g-upload-assistant`
2. cd into folder, `nano run-cli.sh`, paste contents
3. Adjust contents to match your setup
4. Ctrl+X to save
5. Do `chmod +x run-cli.sh`
6. Place config.py in here

### run-cli.sh

```bash
#!/bin/sh
docker rm l4g-upload-assistant-cli

docker run \
  -d \
  --name='l4g-upload-assistant-cli' \
  --network=htpc \
  # Optional: Uncomment next line for non-root execution
  # --user 99:100 \
  --entrypoint tail \
  -v '/mnt/user/share_media':'/data':'rw' \
  -v '/mnt/user/appdata/l4g-upload-assistant/config.py':'/Upload-Assistant/data/config.py':'rw' \
  -v '/mnt/user/appdata/qbittorrent/qBittorrent/BT_backup/':'/BT_backup':'rw' \
  -v '/mnt/user/appdata/l4g-upload-assistant/tmp':'/Upload-Assistant/tmp':'rw' \
  'ghcr.io/audionut/upload-assistant:latest' \
  -f /dev/null

docker exec -it l4g-upload-assistant-cli /bin/sh
## After this, you can python3 upload.py --help
## To stop, type exit
## The container will continue to run
```

### Usage

```bash
./run-cli.sh
```

---

## How to use L4G-Audionut's fork with docker-compose on unraid

This would work on any OS where you can use docker compose but I will focus on unraid here.

For this I had used Dockge. You can read more about it here: [https://github.com/louislam/dockge](https://github.com/louislam/dockge), but you can use any way you'd like to do docker-compose. There are plugins for it on the CA appstore or you can use cli. In this guide I will only cover Dockge.

### Installation

The installation is quite simple, just pull the Dockge container from CA and login to the WebUI.

On the homepage, you'll see a massive + button to add a compose file.

You want to name this container "l4g-upload-assistant-cli" (without the quotes) and remove the sample text that exists.

### Docker Compose Configuration

```yaml
services:
  l4g-upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: l4g-upload-assistant-cli
    restart: unless-stopped
    # Optional: Run as non-root for improved security
    # user: "99:100"  # Unraid's nobody:users - uncomment if desired
    networks:
      - changeme                ######enter a custom network here that your qbittorrent uses
    entrypoint: tail
    command: -f /dev/null
    volumes:
      - /mnt/user/Data/torrents/:/data/torrents/:rw #map this to qbit download location, map exactly as qbittorent template on both sides.
      - /mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw #map this to config.py exactly
      - /mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir:rw #map this to your qbittorrent bt_backup
      - /mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw #map this to your /tmp folder.
networks:
  "changemetowhatyouputinnetworksabove":
    external: true
```

### Path Mapping Explanation

Here you will need to customize your paths as to how your qbittorrent and L4G-uploadassistant is located. You also want to change networks on 2 values to how your custom network is configured. It has to be on the same network as your qbittorrent.

I will explain what each path mapping needs to be:

- **`/mnt/user/Data/torrents/:/data/torrents/:rw`** - Needs to be mapped exactly how your qbittorrent is mapped. Both on the Host and container side. Left side is how your host side is and right would be how qbit container side is. You can copy paste those values here. You also want to remove any local or remote locations you have mapped in config.py as the container will now be using this instead.

- **`/mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw`** - This is the location of your Upload-Assistant's config.py. Please note, this has to be mapped to config.py and not config the folder.

- **`/mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir`** - This is an important part, so please map this correctly if you don't want to rehash every time you upload. Left side is the location where your BT_backup is, right side is what you want to map in your config.py. For example: `"torrent_storage_dir" : "/torrent_storage_dir"`. This is how mine is mapped in config.py. So use the value on the right side in your config.py exactly.

- **`/mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw`** - This is the location of your /tmp in upload-assistant folder.

### Deploy and Use

Once done click deploy and it will create the container for you.

**Example usage:** You can use bash to run commands directly with dockge or unraid terminal, whichever you prefer.

Left-click on your newly created upload-assistant container and go to console.

Here you can type the same exact commands you used for native install but with one change. You'll want to start with how your container side of qbit is mounted. For example, since my container side is "/data/torrents/" my example command would be:

```bash
python3 upload.py "/data/torrents/movies/nicemovieiupload.mkv"
```

This will run exactly how a native install runs where you can supply with extra arguments.

---

## For anyone not wanting to run dockge, the compose plugin or Portainer

You can achieve this by adding:

**Extra Parameters:** `--entrypoint tail`  
**Post Arguments:** `-f /dev/null`

Set your docker network and do your mappings as per usual in the Unraid GUI.

**Optional - Run as non-root:**  
Add to Extra Parameters: `--user 99:100`  
(Ensure your mapped directories are owned by nobody:users first)

Then you can just enter the container and do the CLI.

---

## Running as Non-Root on Unraid (Optional)

By default, the container runs as root. For improved security, you can run as a non-root user. On Unraid, the standard approach is to use `nobody:users` (UID 99, GID 100) or a custom PUID/PGID.

### Option 1: Using Unraid's nobody:users (99:100)

**Step 1: Set directory permissions**

Open Unraid terminal and run:

```bash
# Set ownership to nobody:users
chown -R 99:100 /mnt/user/appdata/Upload-Assistant

# Ensure tmp directory has correct permissions
chmod 700 /mnt/user/appdata/Upload-Assistant/tmp
```

**Step 2: Update docker-compose or container settings**

For docker-compose, add the `user` directive:

```yaml
services:
  l4g-upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:latest
    user: "99:100"
    # ... rest of config
```

For Unraid GUI template, add to Extra Parameters:

```
--user 99:100
```

### Option 2: Using UID 1000 (matches container default)

If you prefer to use UID 1000 (which is what the container's mkbrr binary is owned by):

```bash
# Create a user with UID 1000 if needed, or just set ownership
chown -R 1000:1000 /mnt/user/appdata/Upload-Assistant
chmod 700 /mnt/user/appdata/Upload-Assistant/tmp
```

Then use `--user 1000:1000` or `user: "1000:1000"` in your container config.

### Important Notes for Non-Root on Unraid

1. **Download directory access**: Your download directories (e.g., `/mnt/user/Data/torrents/`) must be readable by the container user. On Unraid, directories on the array are typically owned by `nobody:users`, so using `99:100` often works well.

2. **BT_backup access**: The qBittorrent BT_backup folder must also be accessible. Check permissions:
   ```bash
   ls -la /mnt/user/appdata/qBittorrent/data/BT_backup/
   ```

3. **Network considerations**: Non-root containers can still use custom Docker networks as shown in the examples.

4. **When to stay with root**: If you encounter persistent permission issues or your setup uses mixed ownerships, running as root (the default) is still a valid and simpler approach.

---

## Troubleshooting Common Issues

### Permission Denied Errors (Non-Root Mode)

If you see "Permission denied" errors when running as non-root:

1. **Check directory ownership:**
   ```bash
   ls -la /mnt/user/appdata/Upload-Assistant/
   ls -la /mnt/user/appdata/Upload-Assistant/tmp/
   ```

2. **Fix ownership (for nobody:users):**
   ```bash
   chown -R 99:100 /mnt/user/appdata/Upload-Assistant
   ```

3. **Fix ownership (for UID 1000):**
   ```bash
   chown -R 1000:1000 /mnt/user/appdata/Upload-Assistant
   ```

4. **Verify tmp permissions:**
   ```bash
   chmod 700 /mnt/user/appdata/Upload-Assistant/tmp
   ```

### mkbrr Binary Not Executable

If you encounter errors with the mkbrr torrent creator:
- When running as root: Should work automatically
- When running as non-root (UID 1000): Should work automatically (binary owned by 1000:1000)
- When running as non-root (other UID): May need to verify binary permissions

### Container Won't Start After Upgrade

After upgrading to images with ARM64/non-root support:
1. Pull the latest image: `docker pull ghcr.io/audionut/upload-assistant:latest`
2. Remove the old container and recreate it
3. Verify your volume mounts are correct
