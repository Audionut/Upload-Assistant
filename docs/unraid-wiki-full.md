CREDITS: To the author/s at Aither.

## How to install Upload Assistant natively on Unraid

 Disclaimer: This guide comes as is, and i do not claim to be someone who knows how to fix things if you break it

As unraid is completely focused on docker, i was having issues installing Upload Assistant to work on unraid, i also didn't find using the docker image to be easy.

So here are the steps you will need to take to get Upload Assistant to work directly on unraid.
```
1. You will need the nerd tools package, this can be installed from CA app. 
After that enable this packages
```
![](https://images2.imgbox.com/3f/d2/vPw50sqv_o.png?)

*Not sure which ones are absolutely essential but i got it working with the ones shown in screenshot, you can probably check by uninstalling some and see if it still works.
```
2. open a terminal on unraid, cd to the directory you want to install Upload Assistant or make a directory.
"git clone https://github.com/Audionut/Upload-Assistant.git" run the command,
the other stuff is standard steps you have to follow as per audionuts guide that can be found
here https://github.com/Audionut/Upload-Assistant
```
```
3. you will need some missing packages that are not included with nerdtools.
First is grabbing libffi and the steps you have to follow are here
https://forums.unraid.net/topic/129200-plug-in-nerdtools/page/7/#comment-1192737
```
```
4. Youre almost there, the final thing you need is ffmpeg and the steps to install are
as follows make a directory you want to download ffmpeg to then 
"wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz" this
will download the tar.xz file to the location you are in currently.
```

Next, unpack this, with "tar -xf ffmpeg-git-amd64-static.tar.xz"

this unpackes ffmpeg folder for you. Now cd to the newly unpacked folder, and run "cp -r ffmpeg /usr/bin" and "cp -r ffprobe /usr/bin" this add ffmpeg and ffprobe to be called anywhere.

you now are done, and Upload Assistant should work natively.

Thank you to noraa for all your help, shoutout to deeznuts and ringbear 

## Since people were asking how to do it in Unraid when still wanting CLI options, here goes:
    * create /mnt/user/appdata/upload-assistant
    * cd into folder, nano run-cli.sh, paste contents
    * adjust contents to match your setup
    * Ctrl+X to save
    * do chmod +x run-cli.sh
    * place config.py in here

```
#!/bin/sh
docker rm upload-assistant-cli
docker run \
  -d \
  --name='upload-assistant-cli' \
  --network=htpc \
  --entrypoint tail \
  -v '/mnt/user/share_media':'/data':'rw' \
  -v '/mnt/user/appdata/upload-assistant/config.py':'/Upload-Assistant/data/config.py':'rw' \
  -v '/mnt/user/appdata/qbittorrent/qBittorrent/BT_backup/':'/BT_backup':'rw' \
  -v '/mnt/user/appdata/upload-assistant/tmp':'/Upload-Assistant/tmp':'rw' 'ghcr.io/audionut/upload-assistant:latest' \
  -f /dev/null
docker exec -it upload-assistant-cli /bin/sh
## After this, you can python3 upload.py --help
## To stop, type exit
## The container will continue to run
```

DO:
```
./run-cli.sh
```

## How to use Upload Assistant with docker-compose on unraid

This would work on any os where you can use docker compose but i will focus on unraid here.

For this i had used Dockge. You can read more about it here https://github.com/louislam/dockge, but you can use any way you'd like to do docker-compose. There are plugins for it on the CA appstore or you can use cli. In this guide i will only cover Dockge.

The installation is quite simple, just pull the Dockge container from CA. and login to the WebUI.

On the homepage, you'll see a massive + button to add a compose file.

You will see a screen like this https://ibb.co/r0g07Zs

You want to name this container "upload-assistant-cli" without the "" and remove the sample text that exists here  https://ibb.co/dfMWq7n

Next replace it with
```
services:
  upload-assistant-cli:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant-cli
    restart: unless-stopped
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

Here you will need to customize your paths as to how your qbittorent and Upload Assistant is located. You also want to change networks on 2 values to how your custom network is configured. It has to be on the same network as your qbittorent.

I will explain what each path mapping needs to be.

- /mnt/user/Data/torrents/:/data/torrents/:rw Needs to be mapped exactly how your qbittorrent is mapped. Both on the Host and container side. Left side is how your host side is and right would be how qbit container side is. You can copy paste those values here. You also want to remove any local or remote locations you have mapped in config.py as the container will now be using this instead.

- /mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw This is the location of your Upload-Assistants config.py. Please note, this has to be mapped to config.py and not config the folder

- /mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir This is a important part, so please map this correctly if you dont want to rehash every time you upload. Left side is the location where you Bt_backup is, right side is what you want to map in your config.py. For example: "torrent_storage_dir" : "/torrent_storage_dir", This is how mine is mapped in config.py. So use the value on the right side in your config.py exactly.

- /mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw This is the location of your /tmp in upload-assistant folder.

Once done click deploy and it will create the container for you.

Example usage: You can use bash to run commands directly with dockge or unraid terminal. whichever you prefer.

Leftclick on your newly created upload-assistant container and go to console.

Here you can type the same exact commands you used for native install but with one change. You'll want to start with how your container side of qbit is mounted.
For example. Since my container side is "/data/torrents/"
My example command would be: python3 upload.py "/data/torrents/movies/nicemovieiupload.mkv".
This will run exactly how a native install runs where you can supply with extra arguments. 

## For anyone not wanting to run dockge, the compose plugin or Portainer.

You can achieve this by adding

Extra Parameters: --entrypoint tail
Post Arguments: -f /dev/null
Set your docker network

Do your mappings as per usual in the Unraid GUI

Then you can just enter the container and do the CLI