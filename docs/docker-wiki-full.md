There is a docker image available for Upload-Assistant that is automatically built within a few minutes of each release. 

See this video which covers many aspects of docker itself, and setting up for UA. Note that the video will be slightly out of date in a few minor aspects, particularly the webui if using that.
The video should be viewed in conjunction with the documentation here.

https://videos.badkitty.zone/ua

## Supported Architectures

The Docker images are built for multiple architectures:

| Architecture | Platform | Examples |
|-------------|----------|----------|
| `linux/amd64` | Intel/AMD 64-bit | Most desktop PCs, Intel Macs, cloud VMs |
| `linux/arm64` | ARM 64-bit | Apple Silicon Macs, Raspberry Pi 4/5, AWS Graviton, Oracle Ampere |

Docker will automatically pull the correct image for your system architecture.

## Usage?
```
docker run --rm -it --network=host \
-v /full/path/to/config.py:/Upload-Assistant/data/config.py \
-v /full/path/to/downloads:/downloads \
ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```
The paths in your config file need to refer to paths inside the docker image, same with path provided for file.  May need to utilize remote path mapping for your client.

## Config-generator
```
docker run --rm -it --network=host \
-v /full/path/to/config.py:/Upload-Assistant/data/config.py \
-v /full/path/to/downloads:/downloads \
--entrypoint python \
ghcr.io/audionut/upload-assistant:latest /Upload-Assistant/config-generator.py
```

## What if I want to utilize re-using torrents and I use qbit?
Add another -v line to your command to expose your BT_Backup folder, and set the path in your config to /BT_Backup

```
docker run --rm -it --network=host \
-v /full/path/to/config.py:/Upload-Assistant/data/config.py \
-v /full/path/to/downloads:/downloads \
-v /full/path/to/BT_backup:/BT_backup \
ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

## What if I want to utilize re-using torrents and I use rtorrent/rutorrent?
Add another -v line to your command to expose your session folder, and set the path in your config to /session
```
docker run --rm -it --network=host \
-v /full/path/to/config.py:/Upload-Assistant/data/config.py \
-v /full/path/to/downloads:/downloads \
-v /full/path/to/session/folder:/session \
ghcr.io/audionut/upload-assistant:latest /downloads/path/to/content --help
```

## What is docker?
Google is your friend

## How do I update the docker image? 
`docker pull ghcr.io/audionut/upload-assistant:latest`

## How do I use an image of a specific commit?
```
docker run --rm -it --network=host \
-v /full/path/to/config.py:/Upload-Assistant/data/config.py \
-v /full/path/to/downloads:/downloads \
ghcr.io/audionut/upload-assistant:abc123 /downloads/path/to/content --help
```
Where abc123 is the first 6 digits of the hash of the commit

## Can I use this with Docker on Windows?
Yes but this is a linux container so make sure you are running in that mode.  Forewarning Docker on Windows is funky and certain features aren't implemented like mounting singular files as a volume, using paths that contain spaces in a volume, and lots more so you are on your own.  You will not receive help trying to get it to work.

## The command for running is really long and I dont want to type it.
Make an alias or a function or something.  Will depend on OS.  I use
```
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

## Can I utilize the -vs/--vapoursynth parameter?
No.  The base docker image of alpine does not include vapoursynth in its package manager and building it or downloading portable version into python directory and configuring was decided to not be worth the extra complexity for something that probably gets very little usage and would probably break regularly.  If this is important to you let us know.
