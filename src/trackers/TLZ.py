# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class TLZ(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='TLZ')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'TLZ'
        self.source_flag = 'TLZ'
        self.base_url = 'https://tlzdigital.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')
        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'FILM': '1',
            'EPISODE': '3',
            'PACK': '4',
        }.get(meta.get('type'), '0')

        if meta.get('tv_pack'):
            type_id = '4'
        elif type_id != '4':
            type_id = '3'

        if meta['category'] == 'MOVIE':
            type_id = '1'

        return {'type_id': type_id}
