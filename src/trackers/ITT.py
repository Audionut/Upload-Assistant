# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class ITT(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='ITT')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ITT'
        self.source_flag = 'ItaTorrents'
        self.base_url = 'https://itatorrents.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DLMux': '27',
            'BDMux': '29',
            'WEBMux': '26',
            'DVDMux': '39',
            'BDRip': '25',
            'DVDRip': '24',
            'Cinema-MD': '14',
            }.get(meta['type'], '0')
        return type_id
