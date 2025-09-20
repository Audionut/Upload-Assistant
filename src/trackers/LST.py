# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class LST(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='LST')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'LST'
        self.source_flag = 'LST.GG'
        self.base_url = 'https://lst.gg'
        self.banned_url = f'{self.base_url}/api/bannedReleaseGroups'
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
            'DVDRIP': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
            'draft': await self.get_flag(meta, 'draft'),
        }

        return data

    async def get_name(self, meta):
        lst_name = meta['name']
        resolution = meta.get('resolution')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                lst_name = lst_name.replace(f"{meta['source']}{meta['video_encode']}", f"{resolution}", 1)
                lst_name = lst_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)
            else:
                lst_name = lst_name.replace(f"{meta['source']}", f"{resolution}", 1)
                lst_name = lst_name.replace(f"{meta['video_codec']}", f"{meta['audio']} {meta['video_codec']}", 1)

        return {'name': lst_name}
