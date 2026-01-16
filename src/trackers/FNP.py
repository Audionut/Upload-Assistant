# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class FNP(UNIT3D):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, tracker_name='FNP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'FNP'
        self.base_url = 'https://fearnopeer.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            "4K4U", "BiTOR", "d3g", "FGT", "FRDS", "FTUApps", "GalaxyRG", "LAMA",
            "MeGusta", "NeoNoir", "PSA", "RARBG", "YAWNiX", "YTS", "YIFY", "x0r"
        ]
        pass

    async def get_resolution_id(
        self,
        meta: dict[str, Any],
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '11',
            '720p': '5',
            '576p': '6',
            '576i': '15',
            '480p': '8',
            '480i': '14'
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution is not None:
            return {'resolution_id': resolution_id.get(resolution, '10')}
        else:
            meta_resolution = meta.get('resolution', '')
            resolved_id = resolution_id.get(meta_resolution, '10')
            return {'resolution_id': resolved_id}

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data
