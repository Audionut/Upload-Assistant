# Upload Assistant — MidnightScene (UNIT3D based)
from typing import Any

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class MNS(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='MNS')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'MNS'
        self.base_url = 'https://midnightscene.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]

    async def get_additional_data(self, meta: Meta) -> dict[str, str]:
        return {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

    async def get_category_id(
        self,
        meta: Meta,
        category: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = reverse
        category_map = {
            'MOVIE': '1',
            'TV': '2',
        }
        if mapping_only:
            return category_map
        selected = category or meta['category']
        return {'category_id': category_map.get(selected, '0')}

    async def get_type_id(
        self,
        meta: Meta,
        type: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = reverse
        type_map = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
        }
        if mapping_only:
            return type_map
        selected = type or meta['type']
        return {'type_id': type_map.get(selected, '0')}

    async def get_resolution_id(
        self,
        meta: Meta,
        resolution: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = reverse
        resolution_map = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
        }
        if mapping_only:
            return resolution_map
        selected = resolution or meta['resolution']
        return {'resolution_id': resolution_map.get(selected, '10')}
