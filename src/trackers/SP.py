# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import re
import os
from src.trackers.COMMON import COMMON
from src.console import console
from src.trackers.UNIT3D import UNIT3D


class SP(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='SP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'SP'
        self.source_flag = 'seedpool.org'
        self.base_url = 'https://seedpool.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_category_id(self, meta):
        if not isinstance(meta, dict):
            raise TypeError('meta must be a dict when passed to Seedpool get_cat_id')

        category_name = meta.get('category', '').upper()
        release_title = meta.get('name', '')
        mal_id = meta.get('mal_id', 0)

        # Custom SEEDPOOL category logic
        # Anime TV go in the Anime category
        if mal_id != 0 and category_name == 'TV':
            return {'category_id': '6'}

        # Sports
        if self.contains_sports_patterns(release_title):
            return {'category_id': '8'}

        # Default category logic
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return {'category_id': category_id}

    # New function to check for sports releases in a title
    def contains_sports_patterns(self, release_title):
        patterns = [
            r'EFL.*', r'.*mlb.*', r'.*formula1.*', r'.*nascar.*', r'.*nfl.*', r'.*wrc.*', r'.*wwe.*',
            r'.*fifa.*', r'.*boxing.*', r'.*rally.*', r'.*ufc.*', r'.*ppv.*', r'.*uefa.*', r'.*nhl.*',
            r'.*nba.*', r'.*motogp.*', r'.*moto2.*', r'.*moto3.*', r'.*gamenight.*', r'.*darksport.*',
            r'.*overtake.*'
        ]

        for pattern in patterns:
            if re.search(pattern, release_title, re.IGNORECASE):
                return True
        return False

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_name(self, meta):
        KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".ts"}
        if meta['scene'] is True:
            if meta.get('scene_name') != "":
                name = meta.get('scene_name')
            else:
                name = meta['uuid'].replace(" ", ".")
        elif meta.get('is_disc') is True:
            name = meta['name'].replace(" ", ".")
        else:
            if meta.get('mal_id', 0) != 0:
                name = meta['name'].replace(" ", ".")
            else:
                name = meta['uuid'].replace(" ", ".")
        base, ext = os.path.splitext(name)
        if ext.lower() in KNOWN_EXTENSIONS:
            name = base.replace(" ", ".")
        console.print(f"[cyan]Name: {name}")

        return {'name': name}
