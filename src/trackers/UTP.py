# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
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
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '1')  # Default to MOVIE
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
            '1080i': '4',
        }.get(meta['resolution'], '11')  # Default to Other (11)
        return {'resolution_id': resolution_id}

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
            'ENCODE': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
        }.get(str(meta.get('type', '')).upper(), '3')  # Default to ENCODE
        return {'type_id': type_id}

    async def get_name(self, meta: Meta) -> dict[str, str]:
        """
        Build UTOPIA-compliant torrent name from meta components.
        Follows naming.json templates from UTOPIA fork.
        """
        category = str(meta.get('category', ''))
        release_type = str(meta.get('type', '')).upper()
        source = str(meta.get('source', ''))
        is_disc = meta.get('is_disc', '')

        # Common components
        title = str(meta.get('title', ''))
        aka = str(meta.get('aka', '')).strip()
        year = str(meta.get('year', ''))
        three_d = str(meta.get('3D', ''))
        edition = str(meta.get('edition', ''))
        repack = str(meta.get('repack', ''))
        resolution = str(meta.get('resolution', ''))
        hdr = str(meta.get('hdr', ''))
        service = str(meta.get('service', ''))
        audio = str(meta.get('audio', ''))
        video_codec = str(meta.get('video_codec', ''))
        video_encode = str(meta.get('video_encode', ''))
        tag = str(meta.get('tag', ''))

        # TV-specific
        season = str(meta.get('season', ''))
        episode = str(meta.get('episode', ''))

        name = ""

        if category == "MOVIE":
            if release_type == "DISC":
                if is_disc == 'BDMV':
                    name = f"{title} {aka} {year} {three_d} {edition} {repack} BluRay {resolution} {hdr} {video_codec} {audio}"
                elif is_disc == 'DVD':
                    name = f"{title} {aka} {year} {edition} {repack} {source} {audio}"
                elif is_disc == 'HDDVD':
                    name = f"{title} {aka} {year} {edition} {repack} HD-DVD {resolution} {video_codec} {audio}"
            elif release_type == "REMUX":
                if source in ("BluRay", "Blu-ray", "HDDVD"):
                    name = f"{title} {aka} {year} {three_d} {edition} {repack} BDRemux {resolution} {hdr}"
                else:  # DVD variants
                    name = f"{title} {aka} {year} {edition} {repack} DVDRemux {audio}"
            elif release_type == "ENCODE":
                name = f"{title} {aka} {year} {edition} {repack} BDRip {resolution} {hdr}"
            elif release_type == "WEBDL":
                name = f"{title} {aka} {year} {edition} {repack} {service} WEB-DL {resolution} {hdr}"
            elif release_type == "WEBRIP":
                name = f"{title} {aka} {year} {edition} {repack} {service} WEBRip {resolution} {hdr}"
            elif release_type == "HDTV":
                name = f"{title} {aka} {year} {edition} {repack} HDTV {resolution} {video_encode}"

        elif category == "TV":
            if release_type == "DISC":
                if is_disc == 'BDMV':
                    name = f"{title} {aka} {year} {season}{episode} {three_d} {edition} {repack} BluRay {resolution} {hdr} {video_codec} {audio}"
                elif is_disc == 'DVD':
                    name = f"{title} {aka} {year} {season}{episode} {edition} {repack} {source} {audio}"
                elif is_disc == 'HDDVD':
                    name = f"{title} {aka} {year} {season}{episode} {edition} {repack} HD-DVD {resolution} {video_codec} {audio}"
            elif release_type == "REMUX":
                if source in ("BluRay", "Blu-ray", "HDDVD"):
                    name = f"{title} {aka} {year} {season}{episode} {three_d} {edition} {repack} BDRemux {resolution} {hdr}"
                else:  # DVD variants
                    name = f"{title} {aka} {year} {season}{episode} {edition} {repack} DVDRemux {audio}"
            elif release_type == "ENCODE":
                name = f"{title} {aka} {year} {season}{episode} {edition} {repack} BDRip {resolution} {hdr}"
            elif release_type == "WEBDL":
                name = f"{title} {aka} {year} {season}{episode} {edition} {repack} {service} WEB-DL {resolution} {hdr}"
            elif release_type == "WEBRIP":
                name = f"{title} {aka} {year} {season}{episode} {edition} {repack} {service} WEBRip {resolution} {hdr}"
            elif release_type == "HDTV":
                name = f"{title} {aka} {year} {season}{episode} {edition} {repack} HDTV {resolution} {video_encode}"

        # Fallback if no pattern matched
        if not name:
            name = str(meta.get('name', ''))

        # Clean up multiple spaces and add tag
        name = ' '.join(name.split())
        if tag:
            name = f"{name}{tag}"

        # Final cleanup
        name = re.sub(r'\s{2,}', ' ', name).strip()

        return {'name': name}