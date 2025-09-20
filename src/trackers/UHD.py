# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class UHD(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='UHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'UHD'
        self.source_flag = 'UHD'
        self.base_url = 'https://uhdshare.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass
