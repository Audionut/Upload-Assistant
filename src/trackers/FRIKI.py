# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class FRIKI(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='FRIKI')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'FRIKI'
        self.source_flag = 'frikibar.com'
        self.base_url = 'https://frikibar.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass
