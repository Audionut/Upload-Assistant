# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class STC(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='STC')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'STC'
        self.source_flag = 'STC'
        self.base_url = 'https://skipthecommericals.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass

    async def get_type_id(self, type, tv_pack, sd, category):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        if tv_pack == 1:
            if sd == 1:
                # Season SD
                type_id = '14'
                if type == "ENCODE":
                    type_id = '18'
            if sd == 0:
                # Season HD
                type_id = '13'
                if type == "ENCODE":
                    type_id = '18'
        if type == "DISC" and category == "TV":
            if sd == 1:
                # SD-RETAIL
                type_id = '17'
            if sd == 0:
                # HD-RETAIL
                type_id = '18'
        return type_id
