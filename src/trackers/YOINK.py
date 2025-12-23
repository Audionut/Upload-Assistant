# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class YOINK(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='YOINK')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'YOINK'
        self.source_flag = 'YOiNKED'
        self.base_url = 'https://yoinked.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['YTS', 'YiFY', 'LAMA', 'MeGUSTA', 'NAHOM', 'GalaxyRG', 'RARBG', 'INFINITY']
        pass
