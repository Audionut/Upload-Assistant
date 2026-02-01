# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import asyncio
from typing import Any, Optional, cast

import httpx

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class R4E(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='R4E')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'R4E'
        self.base_url = 'https://racing4everyone.eu'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []

    def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        category_id = '24'
        # Use stored genre IDs if available
        if meta and meta.get('genre_ids'):
            genre_ids = [g.strip() for g in meta['genre_ids'].split(',')]
            is_docu = '99' in genre_ids

            if meta['category'] == 'MOVIE':
                category_id = '70'  # Motorsports Movie
                if is_docu:
                    category_id = '66'  # Documentary
            elif meta['category'] == 'TV':
                category_id = '79'  # TV Series
                if is_docu:
                    category_id = '2'  # TV Documentary
            else:
                category_id = '24'

        return {'category_id': category_id}

    def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        type_id = {
            '8640p': '2160p',
            '4320p': '2160p',
            '2160p': '2160p',
            '1440p': '1080p',
            '1080p': '1080p',
            '1080i': '1080i',
            '720p': '720p',
            '576p': 'SD',
            '576i': 'SD',
            '480p': 'SD',
            '480i': 'SD'
        }.get(str(meta.get('type', '')), '10')
        return {'type_id': type_id}

    def get_personal_release(self, meta: Meta) -> dict[str, str]:
        _ = meta
        return {}

    def get_internal(self, meta: Meta) -> dict[str, str]:
        _ = meta
        return {}

    def get_featured(self, _meta: Meta) -> dict[str, str]:
        return {}

    def get_free(self, meta: Meta) -> dict[str, str]:
        _ = meta
        return {}

    def get_doubleup(self, _meta: Meta) -> dict[str, str]:
        return {}

    def get_sticky(self, _meta: Meta) -> dict[str, str]:
        return {}

    def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (meta, resolution, reverse, mapping_only)
        return {}

    async def search_existing(self, meta: Meta, _: str) -> list[dict[str, Any]]:
        dupes: list[dict[str, Any]] = []
        url = "https://racing4everyone.eu/api/torrents/filter"
        params: dict[str, Any] = {
            'api_token': str(self.config['TRACKERS']['R4E']['api_key']).strip(),
            'tmdb': meta.get('tmdb'),
            'categories[]': (self.get_category_id(meta))['category_id'],
            'types[]': (self.get_type_id(meta))['type_id'],
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = str(params['name']) + str(meta['edition'])
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=url, params=params)
                if response.status_code == 200:
                    data = cast(dict[str, Any], response.json())
                    items = cast(list[dict[str, Any]], data.get('data', []))
                    for each in items:
                        attributes = cast(dict[str, Any], each.get('attributes', {}))
                        result_name = str(attributes.get('name', ''))
                        dupes.append({
                            'name': result_name,
                            'files': result_name,
                            'size': 0,
                            'link': '',
                            'file_count': 0,
                            'download': ''
                        })
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes
