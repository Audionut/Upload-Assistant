# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import glob
import json
import os
import re
import shutil
import urllib.parse
from collections.abc import Mapping
from typing import Any, Union, cast

import requests
from torf import Torrent

from data.config import config
from src.console import console
from src.uploadscreens import upload_screens

DEFAULT_CONFIG: Mapping[str, Any] = cast(Mapping[str, Any], config.get('DEFAULT', {}))
if not isinstance(DEFAULT_CONFIG, dict):
    raise ValueError("'DEFAULT' config section must be a dict")

TRACKER_CONFIG: Mapping[str, Any] = cast(Mapping[str, Any], config.get('TRACKERS', {}))
if not isinstance(TRACKER_CONFIG, dict):
    raise ValueError("'TRACKERS' config section must be a dict")


async def package(meta: dict[str, Any]) -> Union[str, bool]:
    tag = "" if meta['tag'] == "" else f" / {meta['tag'][1:]}"
    res = meta['source'] if meta['is_disc'] == "DVD" else meta['resolution']

    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/GENERIC_INFO.txt", 'w', encoding="utf-8") as generic:
        generic.write(f"Name: {meta['name']}\n\n")
        generic.write(f"Overview: {meta['overview']}\n\n")
        generic.write(f"{res} / {meta['type']}{tag}\n\n")
        generic.write(f"Category: {meta['category']}\n")
        generic.write(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}\n")
        if meta['imdb_id'] != 0:
            generic.write(f"IMDb: https://www.imdb.com/title/tt{meta['imdb_id']}\n")
        if meta['tvdb_id'] != 0:
            generic.write(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series\n")
        if "tvmaze_id" in meta and meta['tvmaze_id'] != 0:
            generic.write(f"TVMaze: https://www.tvmaze.com/shows/{meta['tvmaze_id']}\n")
        poster_img = f"{meta['base_dir']}/tmp/{meta['uuid']}/POSTER.png"
        if meta.get('poster') not in ['', None] and not os.path.exists(poster_img):
            if meta.get('rehosted_poster') is None:
                r = requests.get(meta['poster'], stream=True, timeout=30)
                if r.status_code == 200:
                    console.print("[bold yellow]Rehosting Poster")
                    r.raw.decode_content = True
                    with open(poster_img, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                    if not meta.get('skip_imghost_upload', False):
                        poster, dummy = await upload_screens(meta, 1, 1, 0, 1, [poster_img], {})
                        poster = poster[0]
                        generic.write(f"TMDB Poster: {poster.get('raw_url', poster.get('img_url'))}\n")
                        meta['rehosted_poster'] = poster.get('raw_url', poster.get('img_url'))
                    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as metafile:
                        json.dump(meta, metafile, indent=4)
                        metafile.close()
                else:
                    console.print("[bold yellow]Poster could not be retrieved")
        elif os.path.exists(poster_img) and meta.get('rehosted_poster') is not None:
            generic.write(f"TMDB Poster: {meta.get('rehosted_poster')}\n")
        if len(meta['image_list']) > 0:
            generic.write("\nImage Webpage:\n")
            for each in meta['image_list']:
                generic.write(f"{each['web_url']}\n")
            generic.write("\nThumbnail Image:\n")
            for each in meta['image_list']:
                generic.write(f"{each['img_url']}\n")
    title = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", meta['title'])
    archive = f"{meta['base_dir']}/tmp/{meta['uuid']}/{title}"
    torrent_files = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", "*.torrent"))]
    if isinstance(torrent_files, list) and len(torrent_files) > 1:
        for each in torrent_files:
            if not each.startswith(('BASE', '[RAND')):
                os.remove(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{each}"))
    try:
        if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"):
            base_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
            manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(meta['path']))
            Torrent.copy(base_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{manual_name}.torrent", overwrite=True)
            # shutil.copy(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"), os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['name'].replace(' ', '.')}.torrent").replace(' ', '.'))
        manual_tracker_raw = TRACKER_CONFIG.get('MANUAL')
        manual_tracker_cfg = manual_tracker_raw if isinstance(manual_tracker_raw, dict) else {}
        manual_filebrowser = manual_tracker_cfg.get('filebrowser')
        filebrowser = manual_filebrowser if isinstance(manual_filebrowser, str) else None
        shutil.make_archive(archive, 'tar', f"{meta['base_dir']}/tmp/{meta['uuid']}")
        if filebrowser is not None:
            url = '/'.join(s.strip('/') for s in (filebrowser, f"/tmp/{meta['uuid']}"))
            url = urllib.parse.quote(url, safe="https://")
        else:
            files = {
                "files[]": (f"{meta['title']}.tar", open(f"{archive}.tar", 'rb'))
            }
            response = requests.post("https://uguu.se/upload.php", files=files, timeout=30).json()
            if meta['debug']:
                console.print(f"[cyan]{response}")
            url = response['files'][0]['url']
        return url
    except Exception:
        return False
