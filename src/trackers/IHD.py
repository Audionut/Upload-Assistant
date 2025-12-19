# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui
import pycountry
import re

from src.console import console
from src.languages import process_desc_language, has_english_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class IHD(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='IHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'IHD'
        self.source_flag = 'InfinityHD'
        self.base_url = 'https://infinityhd.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_category_id(self, meta, category=None, reverse=False, mapping_only=False):
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

    async def get_resolution_id(self, meta, resolution=None, reverse=False, mapping_only=False):
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

    def _get_language_code(self, track_or_string):
        """Extract and normalize language to ISO alpha-2 code"""
        if isinstance(track_or_string, dict):
            lang = track_or_string.get("Language", "")
            if isinstance(lang, dict):
                lang = lang.get("String", "")
        else:
            lang = track_or_string
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
        except (AttributeError, KeyError, LookupError):
            return lang_str

    def original_language_check(self, meta):
        if "mediainfo" not in meta:
            return False

        original_languages = {
            lang.lower()
            for lang in meta.get("original_language", [])
            if isinstance(lang, str) and lang.strip()
        }
        if not original_languages:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        for track in tracks:
            if track.get("@type") != "Audio":
                continue
            if "commentary" in str(track.get("Title", "")).lower():
                continue
            lang_code = self._get_language_code(track)
            if lang_code and lang_code.lower() in original_languages:
                return True
        return False

    async def get_name(self, meta):
        ihd_name = meta['name']
        resolution = meta.get('resolution')

        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        audio_languages = meta['audio_languages']
        if audio_languages and not await has_english_language(audio_languages):
            foreign_lang = meta['audio_languages'][0].upper()
            ihd_name = ihd_name.replace(resolution, f"{foreign_lang} {resolution}", 1)

        return {'name': ihd_name}

    async def get_additional_checks(self, meta):
        should_continue = True

        if meta['resolution'] not in ['4320p', '2160p', '1440p', '1080p', '1080i']:
            if not meta['unattended'] or meta['debug']:
                console.print(f'[bold red]Uploads must be at least 1080 resolution for {self.tracker}.[/bold red]')
            should_continue = False

        if not meta['valid_mi_settings']:
            if not meta['unattended'] or meta['debug']:
                console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            should_continue = False

        if not meta['is_disc'] == "BDMV":
            if not meta.get('language_checked', False):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            original_language = self.original_language_check(meta)
            has_eng_audio = await has_english_language(meta.get('audio_languages'))
            has_eng_subs = await has_english_language(meta.get('subtitle_languages'))
            # Require at least one English audio/subtitle track or an original language audio track
            if not (original_language or has_eng_audio or has_eng_subs):
                if not meta['unattended'] or meta['debug']:
                    console.print(f'[bold red]{self.tracker} requires at least one English audio or subtitle track or an original language audio track.')
                should_continue = False

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))):
                console.print(f'[bold red]Pornographic content is not allowed at {self.tracker}, unless it follows strict rules.')
                yes = cli_ui.ask_yes_no(f'Do you have permission to upload this torrent to {self.tracker}?', default=False)
                if yes:
                    should_continue = True
                else:
                    should_continue = False
            else:
                if not meta['unattended'] or meta['debug']:
                    console.print('[bold red]Pornographic content is not allowed at IHD, unless it follows strict rules.')
                should_continue = False

        return should_continue
