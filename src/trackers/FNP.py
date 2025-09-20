# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class FNP(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='FNP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'FNP'
        self.source_flag = 'FnP'
        self.base_url = 'https://fearnopeer.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            "4K4U", "BiTOR", "d3g", "FGT", "FRDS", "FTUApps", "GalaxyRG", "LAMA",
            "MeGusta", "NeoNoir", "PSA", "RARBG", "YAWNiX", "YTS", "YIFY", "x0r"
        ]
        pass

    async def get_resolution_id(self, resolution):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return {'resolution_id': resolution_id}

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data
