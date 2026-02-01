# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from typing import Any, Optional

import cli_ui

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class SP(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='SP')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'SP'
        self.base_url = 'https://seedpool.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []

    def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        category_name = str(meta.get('category', '')).upper()
        release_title = str(meta.get('name', ''))
        mal_id = int(meta.get('mal_id', 0) or 0)

        # Custom SEEDPOOL category logic
        # Anime TV go in the Anime category
        if mal_id != 0 and category_name == 'TV':
            return {'category_id': '6'}

        # Sports
        if self.contains_sports_patterns(release_title):
            return {'category_id': '8'}

        # Default category logic
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return {'category_id': category_id}

    # New function to check for sports releases in a title
    def contains_sports_patterns(self, release_title: str) -> bool:
        patterns = [
            r'EFL.*', r'.*mlb.*', r'.*formula1.*', r'.*nascar.*', r'.*nfl.*', r'.*wrc.*', r'.*wwe.*',
            r'.*fifa.*', r'.*boxing.*', r'.*rally.*', r'.*ufc.*', r'.*ppv.*', r'.*uefa.*', r'.*nhl.*',
            r'.*nba.*', r'.*motogp.*', r'.*moto2.*', r'.*moto3.*', r'.*gamenight.*', r'.*darksport.*',
            r'.*overtake.*'
        ]

        return any(re.search(pattern, release_title, re.IGNORECASE) for pattern in patterns)

    def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        type_value = str(meta.get('type', ''))
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3'
        }.get(type_value, '0')
        return {'type_id': type_id}

    def get_name(self, meta: Meta) -> dict[str, str]:
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

    def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True
        resolution = str(meta.get('resolution', ''))
        if resolution not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i']:
            console.print(f'[bold red]Only 1080 or higher resolutions allowed at {self.tracker}.[/bold red]')
            if not bool(meta.get('unattended')) or (
                bool(meta.get('unattended')) and meta.get('unattended_confirm', False)
            ):
                if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    return False
            else:
                return False

        if not self.common.prompt_adult_content(
            meta,
            tracker_name=self.tracker,
            block_message=f'[bold red]Porn/xxx is not allowed at {self.tracker}.',
            prompt_text="Do you want to upload anyway?",
            default=False,
        ):
            return False

        return should_continue
