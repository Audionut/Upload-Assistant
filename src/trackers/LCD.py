# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import re
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class LCD(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='LCD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'LCD'
        self.source_flag = 'LOCADORA'
        self.base_url = 'https://locadora.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_name(self, meta):
        if meta.get('is_disc', '') == 'BDMV':
            name = meta.get('name')

        else:
            name = meta['uuid']

        replacements = {
            '.mkv': '',
            '.mp4': '',
            '.': ' ',
            'DDP2 0': 'DDP2.0',
            'DDP5 1': 'DDP5.1',
            'H 264': 'H.264',
            'H 265': 'H.265',
            'DD+7 1': 'DDP7.1',
            'AAC2 0': 'AAC2.0',
            'DD5 1': 'DD5.1',
            'DD2 0': 'DD2.0',
            'TrueHD 7 1': 'TrueHD 7.1',
            'TrueHD 5 1': 'TrueHD 5.1',
            'DTS-HD MA 7 1': 'DTS-HD MA 7.1',
            'DTS-HD MA 5 1': 'DTS-HD MA 5.1',
            'DTS-X 7 1': 'DTS-X 7.1',
            'DTS-X 5 1': 'DTS-X 5.1',
            'FLAC 2 0': 'FLAC 2.0',
            'FLAC 5 1': 'FLAC 5.1',
            'DD1 0': 'DD1.0',
            'DTS ES 5 1': 'DTS ES 5.1',
            'DTS5 1': 'DTS 5.1',
            'AAC1 0': 'AAC1.0',
            'DD+5 1': 'DDP5.1',
            'DD+2 0': 'DDP2.0',
            'DD+1 0': 'DDP1.0',
        }

        for old, new in replacements.items():
            name = name.replace(old, new)

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                name = re.sub(f"-{invalid_tag}", "", name, flags=re.IGNORECASE)
            name = f'{name}-NoGroup'

        return {'name': name}

    async def get_region_id(self, meta):
        if meta.get('region') == 'EUR':
            return {}

        region_id = await self.common.unit3d_region_ids(meta.get('region'))
        if region_id != 0:
            return {'region_id': region_id}

        return {}

    async def get_mediainfo(self, meta):
        if meta['bdinfo'] is not None:
            mediainfo = await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'])
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as f:
                mediainfo = await f.read()

        return {'mediainfo': mediainfo}

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIMES': '6'
        }.get(meta['category'], '0')
        if meta['anime'] is True and category_id == '2':
            category_id = '6'
        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution_id = {
            # '8640p':'10',
            '4320p': '1',
            '2160p': '2',
            # '1440p' : '2',
            '1080p': '3',
            '1080i': '34',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
            'Other': '10',
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}
