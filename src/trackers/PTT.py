# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class PTT(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='PTT')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'PTT'
        self.source_flag = 'PTT'
        self.base_url = 'https://polishtorrent.top'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['ViP', 'BiRD', 'M@RTiNU$', 'inTGrity', 'CiNEMAET', 'MusicET', 'TeamET', 'R2D2']
        pass

    async def get_name(self, meta):
        ptt_name = meta['name']
        if meta.get('original_language', '') == 'pl' and meta.get('imdb_info'):
            ptt_name = ptt_name.replace(meta.get('aka', ''), '')
            ptt_name = ptt_name.replace(meta['title'], meta['imdb_info']['aka'])
        return {'name': ptt_name.strip()}
