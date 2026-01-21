# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, Optional, cast

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class LT(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='LT')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'LT'
        self.base_url = 'https://lat-team.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ["EVO"]
        pass

    async def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')

        keywords = str(meta.get('keywords', '')).lower()
        overview = str(meta.get('overview', '')).lower()
        genres = str(meta.get('genres', '')).lower()
        soap_keywords = ['telenovela', 'novela', 'soap', 'culebrón', 'culebron']
        origin_countries_value = meta.get('origin_country', [])
        origin_countries = cast(list[str], origin_countries_value) if isinstance(origin_countries_value, list) else []

        if meta['category'] == 'TV':
            # Anime
            if meta.get('anime', False):
                category_id = '5'
            # Telenovela / Soap
            elif any(kw in keywords for kw in soap_keywords) or any(kw in overview for kw in soap_keywords):
                category_id = '8'
            # Turkish & Asian
            elif 'drama' in genres and any(c in [
                'AE', 'AF', 'AM', 'AZ', 'BD', 'BH', 'BN', 'BT', 'CN', 'CY', 'GE', 'HK', 'ID', 'IL', 'IN',
                'IQ', 'IR', 'JO', 'JP', 'KG', 'KH', 'KP', 'KR', 'KW', 'KZ', 'LA', 'LB', 'LK', 'MM', 'MN',
                'MO', 'MV', 'MY', 'NP', 'OM', 'PH', 'PK', 'PS', 'QA', 'SA', 'SG', 'SY', 'TH', 'TJ', 'TL',
                'TM', 'TR', 'TW', 'UZ', 'VN', 'YE'
            ] for c in origin_countries):
                category_id = '20'

        return {'category_id': category_id}

    async def get_name(self, meta: Meta) -> dict[str, str]:
        aka_value = str(meta.get('aka', ''))
        lt_name = (
            str(meta.get('name', ''))
            .replace('Dual-Audio', '')
            .replace('Dubbed', '')
            .replace(aka_value, '')
        )

        if meta['type'] != 'DISC':  # DISC don't have mediainfo
            # Check if original language is "es" if true replace title for AKA if available
            title_value = str(meta.get('title', ''))
            if meta.get('original_language') == 'es' and aka_value:
                lt_name = lt_name.replace(title_value, aka_value.replace('AKA', '')).strip()
            # Check if audio Spanish exists

            audio_latino_check = {
                "es-419", "es-mx", "es-ar", "es-cl", "es-ve",
                "es-bo",  "es-co", "es-cr", "es-do", "es-ec",
                "es-sv",  "es-gt", "es-hn", "es-ni", "es-pa",
                "es-py",  "es-pe", "es-pr", "es-uy"}

            audio_castilian_check = ["es", "es-es"]
            # Use keywords instead of massive exact-match lists
            # "latino" matches: "latino", "latinoamérica", "latinoamericano", etc.
            latino_keywords = ["latino", "latin america"]
            # "castellano" matches any title explicitly labeled as such.
            castilian_keywords = ["castellano"]

            audios: list[dict[str, Any]] = []
            has_latino = False
            has_castilian = False

            tracks_value = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            tracks_list = cast(list[Any], tracks_value) if isinstance(tracks_value, list) else []
            for audio in tracks_list[2:]:
                if not isinstance(audio, dict):
                    continue
                audio_map = cast(dict[str, Any], audio)
                if audio_map.get("@type") != "Audio":
                    continue
                lang = str(audio_map.get("Language", "")).lower()
                title = str(audio_map.get("Title", "")).lower()

                if "commentary" in title:
                    continue

                # Check if title contains keywords
                is_latino_title = any(kw in title for kw in latino_keywords)
                is_castilian_title = any(kw in title for kw in castilian_keywords)

                # 1. Check strict Latino language codes or Edge Case: Language is 'es' but Title contains Latino keywords
                if lang in audio_latino_check or (lang == 'es' and is_latino_title):
                    has_latino = True
                    audios.append(audio_map)

                # 2. Edge Case: Language is 'es' and Title contains Castilian keywords or Fallback: Check strict Castilian codes (includes 'es' as default)
                elif (lang == 'es' and is_castilian_title) or lang in audio_castilian_check:
                    has_castilian = True
                    audios.append(audio_map)

            if len(audios) > 0:  # If there is at least 1 audio spanish
                if not has_latino and has_castilian:
                    tag_value = str(meta.get('tag', ''))
                    lt_name = lt_name.replace(tag_value, f" [CAST]{tag_value}") if tag_value else f"{lt_name} [CAST]"
                # else: no special tag needed for Latino-only or mixed audio
            # if not audio Spanish exists, add "[SUBS]"
            elif not meta.get('tag'):
                lt_name = lt_name + " [SUBS]"
            else:
                tag_value = str(meta.get('tag', ''))
                lt_name = lt_name.replace(tag_value, f" [SUBS]{tag_value}")

        return {"name": re.sub(r"\s{2,}", " ", lt_name)}

    async def get_additional_checks(self, meta: Meta) -> bool:
        spanish_languages = ["spanish", "spanish (latin america)"]
        return await self.common.check_language_requirements(meta, self.tracker, languages_to_check=spanish_languages, check_audio=True, check_subtitle=True)

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_distributor_ids(self, _meta: Meta) -> dict[str, str]:
        return {}

    async def get_region_id(self, meta: Meta) -> dict[str, str]:
        _ = meta
        return {}
