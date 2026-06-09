# Upload Assistant (local custom tracker)
import re
from typing import Any

import cli_ui

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class ZNTH(UNIT3D):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config, tracker_name='ZNTH')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ZNTH'
        self.base_url = 'https://znth.cx'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_url = f'{self.base_url}/api/bannedReleaseGroups'
        self.banned_groups: list[str] = []

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        znth_name = meta['name']
        if meta['category'] == 'TV' and meta.get('episode_title', "") != "":
            znth_name = znth_name.replace(f"{meta['episode_title']} {meta['resolution']}", f"{meta['resolution']}", 1)
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        year = str(meta.get('year', ""))
        if meta.get('category') != "TV" and imdb_year and imdb_year.strip() and year and year.strip() and imdb_year != year:
            znth_name = znth_name.replace(f"{year}", imdb_year, 1)
        return {'name': znth_name}

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True

        genres = ", ".join(part for part in (meta.get('keywords', ''), meta.get('combined_genres', '')) if part)
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy', 'hentai']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))):
                console.print(f'[bold red]Porn/xxx is not allowed at {self.tracker}.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        return should_continue

    async def get_type_id(
        self, meta: dict[str, Any], type: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'DVDRIP': '11',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type:
            return {'type_id': type_id.get(type, '0')}
        else:
            meta_type = meta.get('type', '')
            resolved_id = type_id.get(meta_type, '0')
            return {'type_id': resolved_id}

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, str]:
        return {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }
