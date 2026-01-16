# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
from typing import Any, cast

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class PTT(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='PTT')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'PTT'
        self.base_url = 'https://polishtorrent.top'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['ViP', 'BiRD', 'M@RTiNU$', 'inTGrity', 'CiNEMAET', 'MusicET', 'TeamET', 'R2D2']
        pass

    async def get_name(self, meta: Meta) -> dict[str, str]:
        ptt_name = str(meta.get('name', ''))
        imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
        if meta.get('original_language', '') == 'pl' and imdb_info:
            ptt_name = ptt_name.replace(str(meta.get('aka', '')), '')
            ptt_name = ptt_name.replace(str(meta.get('title', '')), str(imdb_info.get('aka', '')))
        return {'name': ptt_name.strip()}
