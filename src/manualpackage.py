# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import glob
import json
import os
import re
import shutil
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Union, cast

import aiofiles
import httpx
from torf import Torrent

from src.console import console
from src.uploadscreens import UploadScreensManager


class ManualPackageManager:
    def __init__(self, config: Mapping[str, Any]) -> None:
        default_config = cast(Mapping[str, Any], config.get('DEFAULT', {}))
        if not isinstance(default_config, dict):
            raise ValueError("'DEFAULT' config section must be a dict")
        tracker_config = cast(Mapping[str, Any], config.get('TRACKERS', {}))
        if not isinstance(tracker_config, dict):
            raise ValueError("'TRACKERS' config section must be a dict")
        self.default_config = default_config
        self.tracker_config = tracker_config
        self.uploadscreens_manager = UploadScreensManager(cast(dict[str, Any], config))

    async def package(self, meta: dict[str, Any]) -> Union[str, bool]:
        tag = "" if meta['tag'] == "" else f" / {meta['tag'][1:]}"
        res = meta['source'] if meta['is_disc'] == "DVD" else meta['resolution']

        generic_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/GENERIC_INFO.txt"
        async with aiofiles.open(generic_path, 'w', encoding="utf-8") as generic:
            await generic.write(f"Name: {meta['name']}\n\n")
            await generic.write(f"Overview: {meta['overview']}\n\n")
            await generic.write(f"{res} / {meta['type']}{tag}\n\n")
            await generic.write(f"Category: {meta['category']}\n")
            await generic.write(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}\n")
            if meta['imdb_id'] != 0:
                await generic.write(f"IMDb: https://www.imdb.com/title/tt{meta['imdb_id']}\n")
            if meta['tvdb_id'] != 0:
                await generic.write(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series\n")
            if "tvmaze_id" in meta and meta['tvmaze_id'] != 0:
                await generic.write(f"TVMaze: https://www.tvmaze.com/shows/{meta['tvmaze_id']}\n")
            poster_img = f"{meta['base_dir']}/tmp/{meta['uuid']}/POSTER.png"
            if meta.get('poster') not in ['', None] and not os.path.exists(poster_img):
                if meta.get('rehosted_poster') is None:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(meta['poster'])
                    if response.status_code == 200:
                        console.print("[bold yellow]Rehosting Poster")
                        await asyncio.to_thread(Path(poster_img).write_bytes, response.content)
                        if not meta.get('skip_imghost_upload', False):
                            poster, _ = await self.uploadscreens_manager.upload_screens(meta, 1, 1, 0, 1, [poster_img], {})
                            poster = poster[0]
                            await generic.write(f"TMDB Poster: {poster.get('raw_url', poster.get('img_url'))}\n")
                            meta['rehosted_poster'] = poster.get('raw_url', poster.get('img_url'))
                    else:
                        console.print("[bold yellow]Poster could not be retrieved")
            elif os.path.exists(poster_img) and meta.get('rehosted_poster') is not None:
                await generic.write(f"TMDB Poster: {meta.get('rehosted_poster')}\n")
            if len(meta['image_list']) > 0:
                await generic.write("\nImage Webpage:\n")
                for each in meta['image_list']:
                    await generic.write(f"{each['web_url']}\n")
                await generic.write("\nThumbnail Image:\n")
                for each in meta['image_list']:
                    await generic.write(f"{each['img_url']}\n")
        title = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", meta['title'])
        archive = f"{meta['base_dir']}/tmp/{meta['uuid']}/{title}"
        torrent_files = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", "*.torrent"))]
        if len(torrent_files) > 1:
            for each in torrent_files:
                if not each.startswith(('BASE', '[RAND')):
                    os.remove(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{each}"))
        try:
            if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"):
                base_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
                manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(meta['path']))
                Torrent.copy(base_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{manual_name}.torrent", overwrite=True)
                # shutil.copy(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"), os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['name'].replace(' ', '.')}.torrent").replace(' ', '.'))
            manual_tracker_raw = self.tracker_config.get('MANUAL')
            manual_tracker_cfg: dict[str, Any] = cast(dict[str, Any], manual_tracker_raw) if isinstance(manual_tracker_raw, dict) else {}
            manual_filebrowser = manual_tracker_cfg.get('filebrowser')
            filebrowser = manual_filebrowser if isinstance(manual_filebrowser, str) else None
            shutil.make_archive(archive, 'tar', f"{meta['base_dir']}/tmp/{meta['uuid']}")
            if filebrowser is not None:
                base_url = filebrowser.rstrip('/')
                path = f"/tmp/{meta['uuid']}"
                url = base_url + urllib.parse.quote(path, safe="/")
            else:
                tar_bytes = await asyncio.to_thread(Path(f"{archive}.tar").read_bytes)
                files = {
                    "files[]": (f"{meta['title']}.tar", tar_bytes)
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = (await client.post("https://uguu.se/upload.php", files=files)).json()
                if meta['debug']:
                    console.print(f"[cyan]{response}")
                url = response['files'][0]['url']
            return url
        except Exception:
            return False
