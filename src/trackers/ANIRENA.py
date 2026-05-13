# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import base64
import os
import re
import platform
from typing import Any, Optional, cast

import httpx
import langcodes
from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON


class ANIRENA:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tracker = 'ANIRENA'
        self.source_flag = 'AniRena'
        self.base_url = 'https://www.anirena.com'
        self.api_url = f'{self.base_url}/api/v1'
        self.torrent_url = f'{self.base_url}/torrent/'
        
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

    async def upload(self, meta: dict[str, Any], _disctype: str, tries: int = 0) -> bool:
        common = COMMON(config=self.config)
        # AniRena requires its own trackers to be present in the torrent file
        announce_urls = [
            "udp://tracker-udp.anirena.com:80/announce",
            "https://tracker.anirena.com/announce"
        ]
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, announce_url=announce_urls, is_private=False)
        
        if not self.token:
            await self.get_token()
        
        if not self.token:
            meta['tracker_status'][self.tracker]['status_message'] = "Authentication failed: No token obtained"
            return False

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not os.path.exists(torrent_path):
            console.print(f"[{self.tracker}] Torrent file not found: {torrent_path}")
            meta['tracker_status'][self.tracker]['status_message'] = f"Torrent file not found: {torrent_path}"
            return False

        with open(torrent_path, 'rb') as f:
            torrent_b64 = base64.b64encode(f.read()).decode()

        # Category mapping
        category = self.get_category(meta)
        
        # Languages (AniRena uses BCP 47) - call this before sub_category
        # because it might prompt for hardsubs which changes the sub_category
        languages = await self.get_languages(meta)
        
        sub_category = self.get_sub_category(meta)
        
        # Description
        description = await self.get_description(meta)

        # Anime linking (AniRena specific)
        anime_id = await self.get_anime_id(meta)

        data = {
            "torrent": torrent_b64,
            "category": category,
            "sub_category": sub_category,
            "languages": languages,
            "description": description,
            "name": meta['name'],
            "is_private": False,
        }
        if anime_id:
            data['anime_id'] = anime_id

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
                
                if response.status_code in (200, 201):
                    res_data = response.json()
                    if res_data.get('ok'):
                        torrent_id = res_data.get('id')
                        console.print(f"[{self.tracker}] Uploaded successfully: {torrent_id}")
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        meta['tracker_status'][self.tracker]['status_message'] = f"Uploaded successfully to {self.tracker}"
                        return True
                    else:
                        console.print(f"[{self.tracker}] Upload failed: {res_data}")
                        meta['tracker_status'][self.tracker]['status_message'] = f"Upload failed: {res_data.get('message', res_data)}"
                        return False
                elif response.status_code == 401:
                    # Token might have expired or rotated unexpectedly
                    if tries < 2:
                        console.print(f"[{self.tracker}] Unauthorized (401). Retrying with new token (attempt {tries + 1})...")
                        self.token = None
                        return await self.upload(meta, _disctype, tries=tries + 1)
                    else:
                        console.print(f"[{self.tracker}] Unauthorized (401). Maximum retries reached.")
                        meta['tracker_status'][self.tracker]['status_message'] = "Authentication failed: 401 Unauthorized after retries"
                        return False
                else:
                    console.print(f"[{self.tracker}] Upload failed with status {response.status_code}: {response.text}")
                    meta['tracker_status'][self.tracker]['status_message'] = f"Upload failed with status {response.status_code}"
                    return False
        except Exception as e:
            console.print(f"[{self.tracker}] Exception during upload: {e}")
            meta['tracker_status'][self.tracker]['status_message'] = f"Exception: {e}"
            return False

    def _canonicalize_languages(self, val: Any) -> list[str]:
        if val is None:
            return []
        if isinstance(val, str):
            if not val.strip():
                return []
            raw_list = [val]
        elif isinstance(val, list):
            raw_list = val
        else:
            return []
            
        canonical = []
        for l in raw_list:
            if not l or not isinstance(l, str):
                continue
            l_strip = l.strip()
            if not l_strip:
                continue
            try:
                # Use langcodes to get a standardized name
                lang = langcodes.find(l_strip)
                if lang and lang.is_valid():
                    canonical.append(lang.language_name().lower())
                else:
                    canonical.append(l_strip.lower())
            except Exception:
                canonical.append(l_strip.lower())
        
        # Deduplicate while preserving order
        seen = set()
        return [x for x in canonical if not (x in seen or seen.add(x))]

    async def get_anime_id(self, meta: dict[str, Any]) -> Optional[str]:
        # If user provided anime_id in config or args (hypothetically)
        if meta.get('anirena_anime_id'):
            return str(meta['anirena_anime_id'])
            
        if not meta.get('anime'):
            return None
            
        # Search by title
        search_query = meta.get('title') or meta.get('name')
        if not search_query:
            return None
            
        # Clean title for better search
        search_query = re.sub(r'\[.*?\]', '', search_query).strip()
        # Remove season/episode info if present to find the series
        search_query = re.sub(r'S\d+E\d+.*|S\d+.*|E\d+.*', '', search_query, flags=re.IGNORECASE).strip()
        
        url = f"{self.api_url}/anime/search"
        params = {"q": search_query, "limit": 10}
        
        if meta.get('debug'):
            console.print(f"[{self.tracker}] Searching for anime series with query: [bold cyan]{search_query}[/bold cyan]")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    results = response.json()
                    if not results:
                        return None
                        
                    if meta.get('unattended') and meta.get('anime'):
                        # In unattended mode, we only link if there's an exact title match or only one result
                        if len(results) == 1:
                            return results[0]['id']
                        for res in results:
                            if res['title'].lower() == search_query.lower():
                                return res['id']
                        return None
                    
                    # Prompt user to select
                    console.print(f"[{self.tracker}] [cyan]Select the anime series to link this upload to:[/cyan]")
                    console.print(f" 0) Skip linking")
                    for i, res in enumerate(results, 1):
                        console.print(f" {i}) {res['title']} ({res['season_year']} {res['season']})")
                    
                    from rich.prompt import IntPrompt
                    choice = IntPrompt.ask(f"[{self.tracker}] Enter selection", default=0, show_default=True)
                    if 0 < choice <= len(results):
                        return results[choice-1]['id']
                else:
                    console.print(f"[{self.tracker}] Anime search failed with status {response.status_code}: {response.text}")
        except Exception as e:
            console.print(f"[{self.tracker}] Error searching for anime series: {e}")
            
        return None

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
            audio_langs = self._canonicalize_languages(meta.get('audio_languages'))
            
            if 'japanese' in audio_langs and len(audio_langs) == 1:
                # If it's only Japanese audio, check subs
                sub_langs = self._canonicalize_languages(meta.get('subtitle_languages'))
                
                if not sub_langs:
                    # Check for hardsubs if no soft subs.
                    # Only classify as 'raw' if we explicitly know there are no hardsubs.
                    if 'hardsub_languages' in meta:
                        hardsub_langs = self._canonicalize_languages(meta.get('hardsub_languages'))
                        if not hardsub_langs:
                            return 'raw'
                    # If hardsub_languages is missing (unattended or skipped),
                    # we default to 'sub-audio' to be safe.
                
            return 'sub-audio'
        return ''

    async def get_languages(self, meta: dict[str, Any]) -> list[str]:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
            
        langs = set()
        # Collect languages from audio and subtitles
        audio_langs = self._canonicalize_languages(meta.get('audio_languages'))
        sub_langs = self._canonicalize_languages(meta.get('subtitle_languages'))
            
        all_langs = audio_langs + sub_langs
        for lang_name in all_langs:
            try:
                # Use langcodes to find the best BCP 47 match
                lang = langcodes.find(lang_name)
                if lang and lang.is_valid():
                    langs.add(lang.to_tag())
            except Exception:
                pass
        
        # If no soft subtitles detected, ask about hardsubs
        if not sub_langs and not meta.get('unattended'):
            from rich.prompt import Confirm, Prompt
            if Confirm.ask(f"[{self.tracker}] [yellow]No soft subtitles detected.[/yellow] Does this release include Hardsubs?"):
                hardsub_lang = Prompt.ask(f"[{self.tracker}] Please enter the Hardsub language code (e.g., 'en', 'es')")
                if hardsub_lang:
                    langs.add(hardsub_lang.strip())
                    # Store it in meta so get_sub_category can see it
                    if 'hardsub_languages' not in meta:
                        meta['hardsub_languages'] = []
                    meta['hardsub_languages'].append(hardsub_lang.strip())
            else:
                # Explicitly indicate no hardsubs for get_sub_category
                meta['hardsub_languages'] = []

        # If no languages detected at all, prompt user (if not unattended)
        if not langs and not meta.get('unattended'):
            console.print(f"[{self.tracker}] [yellow]No languages detected from media file.[/yellow]")
            from rich.prompt import Prompt
            lang_input = Prompt.ask(f"[{self.tracker}] Please enter languages (BCP 47 codes, comma separated, e.g., 'en, ja')")
            if lang_input:
                for l in lang_input.split(','):
                    l = l.strip()
                    if l:
                        langs.add(l)

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
        desc += "-----"
        desc += f"\n*Generated by [Upload Assistant](https://github.com/Audionut/Upload-Assistant)*"

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
                
                # Handle token rotation
                new_token = response.headers.get("X-New-Token")
                if new_token:
                    self.token = new_token
                
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
                elif response.status_code == 401:
                    self.token = None
                    if await self.get_token():
                        headers["Authorization"] = f"Bearer {self.token}"
                        response = await client.post(url, json=data, headers=headers)
                        if response.status_code == 200:
                            res_data = response.json()
                            torrents = res_data.get('torrents', [])
                            for t in torrents:
                                dupes.append({
                                    'name': t.get('title'),
                                    'size': t.get('size_fmt'),
                                    'link': f"{self.base_url}/torrent/{t.get('id')}"
                                })
                        else:
                            console.print(f"[{self.tracker}] Duplicate search failed after retry: HTTP {response.status_code}")
                else:
                    console.print(f"[{self.tracker}] Duplicate search failed: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            console.print(f"[{self.tracker}] Exception searching for duplicates: {e}")
            
        return dupes
