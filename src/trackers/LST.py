# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class LST(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='LST')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'LST'
        self.base_url = 'https://lst.gg'
        self.banned_url = f'{self.base_url}/api/bannedReleaseGroups'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.trumping_url = f'{self.base_url}/api/reports/torrents/'
        self.banned_groups = []

    def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True
        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        return should_continue

    def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (reverse, mapping_only)
        release_type = str(type) if type is not None else str(meta.get('type', ''))
        release_type = release_type.upper()
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3'
        }.get(release_type, '0')
        return {'type_id': type_id}

    def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'mod_queue_opt_in': self.get_flag(meta, 'modq'),
            'draft_queue_opt_in': self.get_flag(meta, 'draft'),
        }

        # Only add edition_id if we have a valid edition
        edition_id = self.get_edition(meta)
        if edition_id is not None:
            data['edition_id'] = edition_id

        return data

    def get_edition(self, meta: Meta) -> Optional[int]:
        edition_mapping = {
            'Alternative Cut': 12,
            'Collector\'s Edition': 1,
            'Director\'s Cut': 2,
            'Extended Cut': 3,
            'Extended Uncut': 4,
            'Extended Unrated': 5,
            'Limited Edition': 6,
            'Special Edition': 7,
            'Theatrical Cut': 8,
            'Uncut': 9,
            'Unrated': 10,
            'X Cut': 11,
            'Other': 0  # Default value for "Other"
        }
        edition = meta.get('edition', '')
        if edition in edition_mapping:
            return edition_mapping[edition]
        else:
            return None

    def get_name(self, meta: Meta) -> dict[str, str]:
        lst_name = str(meta.get('name', ''))
        resolution = str(meta.get('resolution', ''))
        video_encode = str(meta.get('video_encode', ''))
        name_type = meta.get('type', "")

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                lst_name = lst_name.replace(f"{meta.get('source', '')}{meta.get('video_encode', '')}", f"{resolution}", 1)
                lst_name = lst_name.replace(str(meta.get('audio', '')), f"{meta.get('audio', '')}{video_encode}", 1)
            else:
                lst_name = lst_name.replace(str(meta.get('source', '')), f"{resolution}", 1)
                lst_name = lst_name.replace(str(meta.get('video_codec', '')), f"{meta.get('audio', '')} {meta.get('video_codec', '')}", 1)

        if meta.get('trump_reason') == 'exact_match':
            lst_name = lst_name + " - TRUMP"

        return {'name': lst_name}
