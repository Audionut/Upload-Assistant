# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, Optional

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class RMC(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='RMC')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'RMC'
        self.base_url = 'https://retro-movies.club'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AROMA', 'aXXo', 'CM8',
            'CrEwSaDe', 'DeadFish', 'DNL', 'ELiTE', 'eSc', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS', 'FUM',
            'GalaxyRG', 'HAiKU', 'HDS', 'HDTime', 'INFINITY', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'LAMA',
            'Leffe', 'LOAD', 'mHD', 'nHD', 'NOIVTC', 'nSD', 'PiRaTeS', 'RARBG', 'RDN', 'REsuRRecTioN',
            'RMTeam', 'SANTi', 'SicFoI', 'SPASM', 'STUTTERSHIT', 'Telly', 'TM', 'UPiNSMOKE', 'WAF', 'xRed',
            'XS', 'YELLO', 'YIFY', 'YTS', 'ZKBL', 'ZmN'
        ]

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
        }.get(meta['category'], '0')
        return {'category_id': category_id}

    async def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        if mapping_only:
            return {
                'BDMV': '1',
                'REMUX_BLURAY': '2',
                'DVD': '3',
                'REMUX_DVD': '4',
                'ENCODE': '5',
                'DVDRIP': '6',
                'WEBDL': '7',
                'WEBRIP': '8',
                'UHDTV': '9',
                'HDTV': '10',
                'TV_SD': '11',
            }
        if reverse:
            return {
                '1': 'BDMV',
                '2': 'REMUX_BLURAY',
                '3': 'DVD',
                '4': 'REMUX_DVD',
                '5': 'ENCODE',
                '6': 'DVDRIP',
                '7': 'WEBDL',
                '8': 'WEBRIP',
                '9': 'UHDTV',
                '10': 'HDTV',
                '11': 'TV_SD',
            }

        source = str(meta.get('source', '')).upper()
        is_disc = str(meta.get('is_disc', '')).upper()
        category = str(meta.get('category', '')).upper()
        sd = int(meta.get('sd') or 0)
        type_value = str(type) if type is not None else str(meta.get('type', ''))
        type_upper = type_value.upper()

        if is_disc == 'BDMV':
            return {'type_id': '1'}
        if type_upper == 'REMUX' and source in {'BLURAY', 'BLU-RAY'}:
            return {'type_id': '2'}
        if is_disc == 'DVD':
            return {'type_id': '3'}
        if type_upper == 'REMUX' and source in {'DVD', 'PAL DVD', 'NTSC DVD'}:
            return {'type_id': '4'}
        if type_upper == 'ENCODE':
            return {'type_id': '5'}
        if type_upper == 'DVDRIP':
            return {'type_id': '6'}
        if type_upper == 'WEBDL':
            return {'type_id': '7'}
        if type_upper == 'WEBRIP' or source == 'WEB':
            return {'type_id': '8'}
        if source == 'UHDTV':
            return {'type_id': '9'}
        if type_upper == 'HDTV':
            return {'type_id': '10'}
        if category == 'TV' and sd == 1:
            return {'type_id': '11'}

        return {'type_id': '0'}

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
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(meta['resolution'], '11')
        return {'resolution_id': resolution_id}

    async def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        if meta.get('category') != "MOVIE":
            if not meta.get('unattended'):
                console.print(f"Only movies are allowed on {self.tracker}.")
            meta['skipping'] = self.tracker
            return False

        if meta.get('year') and int(meta['year']) > 2000:
            if not meta.get('unattended'):
                console.print(f"{self.tracker} only allows movies released in 2000 or earlier.")
            meta['skipping'] = self.tracker
            return False

        return should_continue

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_name(self, meta: Meta) -> dict[str, str]:
        rmc_name = str(meta.get('name', ''))
        aka = str(meta.get('aka', '')).strip()

        if aka:
            rmc_name = rmc_name.replace(f" {aka} ", " ")

        rmc_name = re.sub(r'[^A-Za-z0-9 ._-]+', '', rmc_name)
        rmc_name = re.sub(r'\s+', ' ', rmc_name).strip()

        return {'name': rmc_name}
