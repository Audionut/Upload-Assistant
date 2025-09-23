# -*- coding: utf-8 -*-
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class YUS(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='YUS')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'YUS'
        self.source_flag = 'YuScene'
        self.base_url = 'https://yu-scene.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        disallowed_keywords = {'XXX', 'Erotic', 'Porn', 'Hentai', 'softcore'}
        if any(keyword.lower() in disallowed_keywords for keyword in map(str.lower, meta['keywords'])):
            console.print('[bold red]Adult animation not allowed at YUS.')
            should_continue = False

        return should_continue

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '17',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}
