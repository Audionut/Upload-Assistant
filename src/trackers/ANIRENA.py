# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import base64
import os
import re
import platform
from typing import Any, Optional, cast

import httpx
import langcodes
from src.console import console
from src.trackers.COMMON import COMMON


class ANIRENA:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tracker = 'ANIRENA'
        self.source_flag = 'AniRena'
        self.base_url = 'https://www.anirena.com'
        self.api_url = f'{self.base_url}/api/v1'
        
        trackers_cfg = cast(dict[str, Any], self.config.get('TRACKERS', {}))
        anirena_cfg = cast(dict[str, Any], trackers_cfg.get('ANIRENA', {}))
        self.api_key = str(anirena_cfg.get('api_key', '')).strip()
        self.token: Optional[str] = None
        self.banned_groups: list[str] = []

    async def get_token(self) -> Optional[str]:
        if not self.api_key:
            console.print(f"[{self.tracker}] API Key is missing in config.")
            return None
        
        url = f"{self.api_url}/auth/token"
        headers = {
            "Authorization": f"ApiKey {self.api_key}",
            "User-Agent": f"Upload Assistant/7.1.7 ({platform.system()} {platform.release()})",
            "Accept": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                self.token = data.get("token")
                return self.token
        except Exception as e:
            console.print(f"[{self.tracker}] Error getting auth token: {e}")
            return None

    async def upload(self, meta: dict[str, Any], _disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        
        if not self.token:
            await self.get_token()
        
        if not self.token:
            meta['tracker_status'][self.tracker]['status_message'] = "Authentication failed: No token obtained"
            return False

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        if not os.path.exists(torrent_path):
            console.print(f"[{self.tracker}] Torrent file not found: {torrent_path}")
            meta['tracker_status'][self.tracker]['status_message'] = f"Torrent file not found: {torrent_path}"
            return False

        with open(torrent_path, 'rb') as f:
            torrent_b64 = base64.b64encode(f.read()).decode()

        # Category mapping
        category = self.get_category(meta)
        sub_category = self.get_sub_category(meta)
        
        # Languages (AniRena uses BCP 47)
        languages = self.get_languages(meta)
        
        # Description
        description = await self.get_description(meta)

        data = {
            "torrent": torrent_b64,
            "category": category,
            "sub_category": sub_category,
            "languages": languages,
            "description": description,
            "name": meta['name'],
            "is_private": False,
        }

        # Add anime_id if available (AniRena specific)
        # We could potentially search for the anime UUID using AniList/MAL ID
        # but let's stick to the basics first.

        url = f"{self.api_url}/torrents"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": f"Upload Assistant/7.1.7 ({platform.system()} {platform.release()})",
            "Accept": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=data, headers=headers)
                
                # Handle token rotation
                new_token = response.headers.get("X-New-Token")
                if new_token:
                    self.token = new_token
                
                if response.status_code == 200:
                    res_data = response.json()
                    if res_data.get('ok'):
                        console.print(f"[{self.tracker}] Uploaded successfully: {res_data.get('id')}")
                        return True
                    else:
                        console.print(f"[{self.tracker}] Upload failed: {res_data}")
                        meta['tracker_status'][self.tracker]['status_message'] = f"Upload failed: {res_data.get('message', res_data)}"
                        return False
                elif response.status_code == 401:
                    # Token might have expired or rotated unexpectedly
                    console.print(f"[{self.tracker}] Unauthorized (401). Retrying with new token...")
                    self.token = None
                    return await self.upload(meta, _disctype)
                else:
                    console.print(f"[{self.tracker}] Upload failed with status {response.status_code}: {response.text}")
                    meta['tracker_status'][self.tracker]['status_message'] = f"Upload failed with status {response.status_code}"
                    return False
        except Exception as e:
            console.print(f"[{self.tracker}] Exception during upload: {e}")
            meta['tracker_status'][self.tracker]['status_message'] = f"Exception: {e}"
            return False

    def get_category(self, meta: dict[str, Any]) -> str:
        if meta.get('hentai') or 'Hentai' in str(meta.get('genres', '')):
            return 'hentai'
        if meta.get('anime'):
            return 'anime'
        if meta.get('category') == 'MUSIC':
            return 'audio'
        return 'other'

    def get_sub_category(self, meta: dict[str, Any]) -> str:
        if meta.get('anime'):
            audio_langs = [l.lower() for l in meta.get('audio_languages', [])]
            if 'japanese' in audio_langs and len(audio_langs) == 1:
                # If it's only Japanese audio, check subs
                sub_langs = [l.lower() for l in meta.get('subtitle_languages', [])]
                if not sub_langs:
                    return 'raw'
            return 'sub-audio'
        return ''

    def get_languages(self, meta: dict[str, Any]) -> list[str]:
        langs = set()
        # Collect languages from audio and subtitles
        all_langs = meta.get('audio_languages', []) + meta.get('subtitle_languages', [])
        for lang_name in all_langs:
            try:
                # Use langcodes to find the best BCP 47 match
                lang = langcodes.find(lang_name)
                if lang and lang.is_valid():
                    langs.add(lang.to_tag())
            except Exception:
                pass
        return list(langs)

    async def get_description(self, meta: dict[str, Any]) -> str:
        # Build a Markdown description
        desc = f"# {meta['name']}\n\n"
        
        # Add links
        links = []
        if meta.get('imdb_id'):
            links.append(f"[IMDb](https://www.imdb.com/title/tt{meta['imdb_id']})")
        if meta.get('tmdb'):
            cat = meta.get('category', 'movie').lower()
            links.append(f"[TMDb](https://www.themoviedb.org/{cat}/{meta['tmdb']})")
        if meta.get('mal_id'):
            links.append(f"[MAL](https://myanimelist.net/anime/{meta['mal_id']})")
        if meta.get('anilist_id'):
            links.append(f"[AniList](https://anilist.co/anime/{meta['anilist_id']})")
        
        if links:
            desc += " | ".join(links) + "\n\n"

        # Add Overview
        if meta.get('overview'):
            desc += f"## Overview\n{meta['overview']}\n\n"

        # Add Mediainfo / BDInfo summary
        desc += "## Technical Information\n"
        if meta.get('is_disc') == "BDMV":
            # For discs, we usually have a summary in meta['discs']
            for disc in meta.get('discs', []):
                summary = disc.get('summary', '')
                if summary:
                    desc += f"### {disc.get('name', 'Disc')}\n```\n{summary}\n```\n\n"
        else:
            # For files, use the short mediainfo if available
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            if os.path.exists(mi_path):
                with open(mi_path, 'r', encoding='utf-8') as f:
                    desc += f"```\n{f.read()}\n```\n\n"

        # Add Screenshots
        image_list = meta.get('image_list', [])
        if image_list:
            desc += "## Screenshots\n"
            for img in image_list:
                web_url = img.get('web_url')
                img_url = img.get('img_url') or img.get('raw_url')
                if web_url and img_url:
                    desc += f"[![Screenshot]({img_url})]({web_url}) "
                elif img_url:
                    desc += f"![Screenshot]({img_url}) "
            desc += "\n\n"

        # Add Signature
        desc += "---\n"
        desc += f"*Generated by [Upload Assistant](https://github.com/Audionut/Upload-Assistant)*"

        return desc

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[dict[str, str]]:
        # AniRena search API can be used to check for duplicates
        # POST /api/v1/torrents/search
        if not self.token:
            await self.get_token()
        
        if not self.token:
            return []

        url = f"{self.api_url}/torrents/search"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": f"Upload Assistant/7.1.7 ({platform.system()} {platform.release()})",
            "Accept": "application/json",
        }
        
        # Search by title or part of it
        search_query = meta['title']
        # Clean up the title a bit for better search
        search_query = re.sub(r'\[.*?\]', '', search_query).strip()
        
        data = {
            "q": search_query,
            "per_page": 25
        }
        
        dupes = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    res_data = response.json()
                    torrents = res_data.get('torrents', [])
                    for t in torrents:
                        # Simple name matching or info_hash matching if we had it
                        # Since we don't have the info_hash yet (torrent not created or hash not in meta),
                        # we rely on name matching.
                        dupes.append({
                            'name': t.get('title'),
                            'size': t.get('size_fmt'),
                            'link': f"{self.base_url}/torrent/{t.get('id')}"
                        })
        except Exception as e:
            console.print(f"[{self.tracker}] Error searching for duplicates: {e}")
            
        return dupes
