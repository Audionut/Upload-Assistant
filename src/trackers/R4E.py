# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import asyncio
import httpx
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class R4E(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='R4E')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'R4E'
        self.source_flag = 'R4E'
        self.base_url = 'https://racing4everyone.eu'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_category_id(self, meta):
        # Use stored genre IDs if available
        if meta and meta.get('genre_ids'):
            genre_ids = meta['genre_ids'].split(',')
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

    async def get_type_id(self, meta):
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
        }.get(meta['type'], '10')
        return {'type_id': type_id}

    async def get_personal_release(self, meta):
        return {}

    async def get_internal(self, meta):
        return {}

    async def get_featured(self, meta):
        return {}

    async def get_free(self, meta):
        return {}

    async def get_doubleup(self, meta):
        return {}

    async def get_sticky(self, meta):
        return {}

    async def get_resolution_id(self, meta):
        return {}

    async def search_existing(self, meta, disctype):
        dupes = []
        url = "https://racing4everyone.eu/api/torrents/filter"
        params = {
            'api_token': self.config['TRACKERS']['R4E']['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'categories[]': (await self.get_category_id(meta))['category_id'],
            'types[]': await self.get_type_id(meta),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + meta['edition']
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        result = [each][0]['attributes']['name']
                        dupes.append(result)
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
