# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional, cast

import pycountry

from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class IHD(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='IHD')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'IHD'
        self.base_url = 'https://infinityhd.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []

    def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        category_name = meta['category']
        anime = meta.get('anime', False)
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIME': '3',
            'ANIME MOVIE': '4',
        }

        is_anime_movie = False
        is_anime = False

        if category_name == 'MOVIE' and anime is True:
            is_anime_movie = True

        if category_name == 'TV' and anime is True:
            is_anime = True

        if is_anime:
            return {'category_id': '3'}
        if is_anime_movie:
            return {'category_id': '4'}

        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}
        elif category is not None:
            return {'category_id': category_id.get(category, '0')}
        else:
            meta_category = meta.get('category', '')
            resolved_id = category_id.get(meta_category, '0')
            return {'category_id': resolved_id}

    def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4'
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

    def _get_language_code(self, track_or_string: Any) -> str:
        """Extract and normalize language to ISO alpha-2 code"""
        if isinstance(track_or_string, dict):
            track_map = cast(dict[str, Any], track_or_string)
            lang_value = track_map.get("Language", "")
            if isinstance(lang_value, dict):
                lang_map = cast(dict[str, Any], lang_value)
                lang = str(lang_map.get("String", ""))
            else:
                lang = str(lang_value)
        else:
            lang = str(track_or_string)
        if not lang:
            return ""
        lang_str = str(lang).lower()

        # Strip country code if present (e.g., "en-US" → "en")
        if "-" in lang_str:
            lang_str = lang_str.split("-")[0]

        if len(lang_str) == 2:
            return lang_str
        try:
            lang_obj = (
                pycountry.languages.get(name=lang_str.title())
                or pycountry.languages.get(alpha_2=lang_str)
                or pycountry.languages.get(alpha_3=lang_str)
            )
            return lang_obj.alpha_2.lower() if lang_obj else lang_str
        except (AttributeError, LookupError):
            return lang_str

    def original_language_check(self, meta: Meta) -> bool:
        if "mediainfo" not in meta:
            return False

        original_languages = {
            lang.lower()
            for lang in meta.get("original_language", [])
            if isinstance(lang, str) and lang.strip()
        }
        if not original_languages:
            return False

        tracks_value = meta["mediainfo"].get("media", {}).get("track", [])
        tracks_list = cast(list[Any], tracks_value) if isinstance(tracks_value, list) else []
        for track in tracks_list:
            if not isinstance(track, dict):
                continue
            track_map = cast(dict[str, Any], track)
            if track_map.get("@type") != "Audio":
                continue
            if "commentary" in str(track_map.get("Title", "")).lower():
                continue
            lang_code = self._get_language_code(track_map)
            if lang_code and lang_code.lower() in original_languages:
                return True
        return False

    def get_name(self, meta: Meta) -> dict[str, str]:
        ihd_name = str(meta.get('name', ''))
        resolution = str(meta.get('resolution', ''))

        audio_languages_value = meta.get('audio_languages', [])
        audio_languages: list[str] = []
        if isinstance(audio_languages_value, list):
            audio_languages_list = cast(list[Any], audio_languages_value)
            audio_languages = [str(item) for item in audio_languages_list]
        if audio_languages and not languages_manager.has_english_language(audio_languages):
            foreign_lang = str(audio_languages[0]).upper()
            ihd_name = ihd_name.replace(resolution, f"{foreign_lang} {resolution}", 1)

        return {'name': ihd_name}

    def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        if meta['resolution'] not in ['4320p', '2160p', '1440p', '1080p', '1080i']:
            if not meta['unattended'] or meta['debug']:
                console.print(f'[bold red]Uploads must be at least 1080 resolution for {self.tracker}.[/bold red]')
            should_continue = False

        if not meta['valid_mi_settings']:
            if not meta['unattended'] or meta['debug']:
                console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            should_continue = False

        if meta['is_disc'] != "BDMV":
            original_language = self.original_language_check(meta)
            audio_languages_value = meta.get('audio_languages', [])
            subtitle_languages_value = meta.get('subtitle_languages', [])
            audio_languages: list[str] = []
            subtitle_languages: list[str] = []
            if isinstance(audio_languages_value, list):
                audio_languages_list = cast(list[Any], audio_languages_value)
                audio_languages = [str(item) for item in audio_languages_list]
            else:
                audio_languages = []
            if isinstance(subtitle_languages_value, list):
                subtitle_languages_list = cast(list[Any], subtitle_languages_value)
                subtitle_languages = [str(item) for item in subtitle_languages_list]
            else:
                subtitle_languages = []
            has_eng_audio = languages_manager.has_english_language(audio_languages if audio_languages else '')
            has_eng_subs = languages_manager.has_english_language(subtitle_languages if subtitle_languages else '')
            # Require at least one English audio/subtitle track or an original language audio track
            if not (original_language or has_eng_audio or has_eng_subs):
                if not meta['unattended'] or meta['debug']:
                    console.print(f'[bold red]{self.tracker} requires at least one English audio or subtitle track or an original language audio track.')
                should_continue = False

        unattended_message = (
            '[bold red]Pornographic content is not allowed at IHD, unless it follows strict rules.'
            if meta.get('debug')
            else None
        )
        should_continue = self.common.prompt_adult_content(
            meta,
            tracker_name=self.tracker,
            block_message=f'[bold red]Pornographic content is not allowed at {self.tracker}, unless it follows strict rules.',
            prompt_text=f'Do you have permission to upload this torrent to {self.tracker}?',
            unattended_message=unattended_message,
            default=False,
        )

        return should_continue
