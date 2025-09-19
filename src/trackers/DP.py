# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import httpx
import re
from data.config import config
from src.console import console
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class DP(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='DP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'DP'
        self.source_flag = 'DarkPeers'
        self.base_url = 'https://darkpeers.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            'aXXo', 'BANDOLEROS', 'BONE', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'dAV1nci', 'DNL',
            'FaNGDiNG0', 'FiSTER', 'GalaxyTV', 'HD2DVD', 'HDT', 'HDTime', 'iHYTECH', 'ION10',
            'iPlanet', 'KiNGDOM', 'LAMA', 'MeGusta', 'mHD', 'mSD', 'NaNi', 'NhaNc3', 'nHD',
            'nikt0', 'nSD', 'OFT', 'PiTBULL', 'PRODJi', 'RARBG', 'Rifftrax', 'ROCKETRACCOON',
            'SANTi', 'SasukeducK', 'SEEDSTER', 'ShAaNiG', 'Sicario', 'STUTTERSHIT', 'TAoE',
            'TGALAXY', 'TGx', 'TORRENTGALAXY', 'ToVaR', 'TSP', 'TSPxL', 'ViSION', 'VXT',
            'WAF', 'WKS', 'X0r', 'YIFY', 'YTS', ['EVO', 'web-dl Only']
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if not meta['is_disc'] == "BDMV":
            if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            nordic_languages = ['Danish', 'Swedish', 'Norwegian', 'Icelandic', 'Finnish', 'English']
            if not any(lang in meta.get('audio_languages', []) for lang in nordic_languages) and not any(lang in meta.get('subtitle_languages', []) for lang in nordic_languages):
                console.print('[bold red]DP requires at least one Nordic/English audio or subtitle track.')
                should_continue = False

        return should_continue

    async def get_description(self, meta):
        if meta.get('logo', "") == "":
            from src.tmdb import get_logo
            TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id = meta.get('tmdb')
            category = meta.get('category')
            debug = meta.get('debug')
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            logo_path = await get_logo(tmdb_id, category, debug, logo_languages=logo_languages, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)
            if logo_path:
                meta['logo'] = logo_path
        await self.common.unit3d_edit_desc(meta, self.tracker, self.signature)
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8') as f:
            desc = await f.read()
        return {'description': desc}

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_name(self, meta):
        dp_name = meta.get('name')
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        tag_lower = meta['tag'].lower()
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                dp_name = re.sub(f"-{invalid_tag}", "", dp_name, flags=re.IGNORECASE)
            dp_name = f"{dp_name}-NOGROUP"
        return {'name': dp_name}

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_category_id(meta),
            'types[]': await self.get_type_id(meta),
            'resolutions[]': await self.get_resolution_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
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

        if meta['type'] == "ENCODE" and meta.get('tag', "") and 'fgt' in meta['tag'].lower() and len(dupes) > 0:
            if not meta['unattended']:
                console.print("[bold red]DP does not allow FGT encodes, skipping upload.")
            meta['skipping'] = "DP"
            return []

        return dupes
