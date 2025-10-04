# -*- coding: utf-8 -*-
# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class RHD(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='RHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'RHD'
        self.source_flag = 'RocketHD'
        self.base_url = 'https://rocket-hd.cc/'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['1XBET', 'MEGA', 'MTZ', 'Whistler', 'WOTT', 'Taylor.D', 'HELD', 'FSX', 'FuN', 'MagicX', 'w00t', 'PaTroL', 'BB', '266ers', 'GTF', 'JellyfinPlex', '2BA']
        pass

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')
        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution_id = {
            '4320p': '0',
            '2160p': '1',
            '1080p': '2',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '480p': '8'
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    # If the tracker has modq in the api, otherwise remove this function
    # If no additional data is required, remove this function
    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data
