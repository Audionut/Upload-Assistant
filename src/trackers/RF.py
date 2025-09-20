# -*- coding: utf-8 -*-
import re
from src.trackers.COMMON import COMMON
from src.console import console
from src.trackers.UNIT3D import UNIT3D


class RF(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='RF')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'RF'
        self.source_flag = 'ReelFliX'
        self.base_url = 'https://reelflix.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        disallowed_keywords = {'XXX', 'Erotic', 'softcore'}
        if any(keyword.lower() in disallowed_keywords for keyword in map(str.lower, meta['keywords'])):
            console.print('[bold red]Erotic not allowed at RF.')
            should_continue = False
        if meta.get('category') == "TV":
            console.print('[bold red]RF only ALLOWS Movies.')
            should_continue = False

        return should_continue

    async def get_name(self, meta):
        rf_name = meta['name']
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                rf_name = re.sub(f"-{invalid_tag}", "", rf_name, flags=re.IGNORECASE)
            rf_name = f"{rf_name}-NoGroup"

        return {'name': rf_name}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '43',
            'REMUX': '40',
            'WEBDL': '42',
            'WEBRIP': '45',
            # 'FANRES': '6',
            'ENCODE': '41',
            'HDTV': '35',
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution_id = {
            # '8640p':'10',
            '4320p': '1',
            '2160p': '2',
            # '1440p' : '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}
