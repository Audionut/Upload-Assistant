# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class UTP(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='UTP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'UTP'
        self.base_url = 'https://utp.to'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        category_name = meta['category']
        edition = meta.get('edition', '')
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '3'
        }.get(category_name, '0')
        if category_name == 'MOVIE' and 'FANRES' in edition:
            category_id = '3'
        return {'category_id': category_id}

    async def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (resolution, reverse, mapping_only)
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4'
        }.get(meta['resolution'], '1')
        return {'resolution_id': resolution_id}
