# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
from typing import Any, Optional

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class NQ(UNIT3D):  # EDIT 'UNIT3D_TEMPLATE' AS ABBREVIATED TRACKER NAME
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='NQ')  # EDIT 'UNIT3D_TEMPLATE' AS ABBREVIATED TRACKER NAME
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'NQ'
        self.base_url = 'https://nordicq.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'  # If the site supports requests via API, otherwise remove this line
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass

    # The section below can be deleted if no changes are needed, as everything else is handled in UNIT3D.py
    # If advanced changes are required, copy the necessary functions from UNIT3D.py here
    # For example, if you need to modify the description, copy and paste the 'get_description' function and adjust it accordingly

    # If default UNIT3D categories, remove this function
    async def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')
        return {'category_id': category_id}

    # If default UNIT3D types, remove this function
    async def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    # If default UNIT3D resolutions, remove this function
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
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '540p': '11',
            '480p': '8',
            '480i': '9',
            'Other': '10',
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    # If there are tracker specific checks to be done before upload, add them here
    # Is it a movie only tracker? Are concerts banned? Etc.
    # If no checks are necessary, remove this function
    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        return await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["danish", "finnish", "norwegian", "swedish"], check_audio=True, check_subtitle=True
        )

    # If the tracker has modq in the api, otherwise remove this function
    # If no additional data is required, remove this function
    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    # If the tracker has specific naming conventions, add them here; otherwise, remove this function
    async def get_name(self, meta: Meta) -> dict[str, str]:
        KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".ts"}
        if bool(meta.get('scene')):
            scene_name = str(meta.get('scene_name', ''))
            name = scene_name if scene_name != "" else str(meta.get('uuid', '')).replace(" ", ".")
        elif bool(meta.get('is_disc')):
            name = str(meta.get('name', '')).replace(" ", ".")
        else:
            base_name = str(meta.get('name', '')).replace(" ", ".")
            uuid_name = str(meta.get('uuid', '')).replace(" ", ".")
            name = base_name if int(meta.get('mal_id', 0) or 0) != 0 else uuid_name
        base, ext = os.path.splitext(name)
        if ext.lower() in KNOWN_EXTENSIONS:
            name = base.replace(" ", ".")
        console.print(f"[cyan]Name: {name}")

        return {'name': name}
