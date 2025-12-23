# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
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
        self.base_url = 'https://reelflix.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended']:
                console.print('[bold red]Erotic not allowed at RF.')
            should_continue = False
        if meta.get('category') == "TV":
            if not meta['unattended']:
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

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type_id = {
            'DISC': '43',
            'REMUX': '40',
            'WEBDL': '42',
            'WEBRIP': '45',
            # 'FANRES': '6',
            'ENCODE': '41',
            'HDTV': '35',
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type is not None:
            return {'type_id': type_id.get(type, '0')}
        else:
            meta_type = meta.get('type', '')
            resolved_id = type_id.get(meta_type, '0')
            return {'type_id': resolved_id}

    async def get_resolution_id(self, meta, resolution=None, reverse=False, mapping_only=False):
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
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution is not None:
            return {'resolution_id': resolution_id.get(resolution, '10')}
        else:
            meta_resolution = meta.get('resolution', '')
            resolved_id = resolution_id.get(meta_resolution, '10')
            return {'resolution_id': resolved_id}
