# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class TLZ(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='TLZ')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'TLZ'
        self.base_url = 'https://tlzdigital.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]

    def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        type_id = {
            'FILM': '1',
            'EPISODE': '3',
            'PACK': '4',
        }
        if mapping_only:
            return type_id
        if reverse:
            return {v: k for k, v in type_id.items()}
        if type is not None:
            return {'type_id': type_id.get(type, '0')}
        type_value = str(meta.get('type', ''))
        type_id_value = type_id.get(type_value, '0')

        if meta.get('tv_pack'):
            type_id_value = '4'
        elif type_id_value != '4':
            type_id_value = '3'

        if str(meta.get('category', '')) == 'MOVIE':
            type_id_value = '1'

        return {'type_id': type_id_value}
