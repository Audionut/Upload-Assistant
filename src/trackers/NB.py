# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from typing import Any, cast
from typing import Optional

import cli_ui

from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.tmdb import TmdbManager
from src.trackers.UNIT3D import UNIT3D
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class NB(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='NB')
        self.config = config
        self.common = COMMON(config)
        self.tmdb_manager = TmdbManager(config)
        self.tracker = 'NordicBytes'
        self.base_url = 'https://nordicbytes.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'  # If the site supports requests via API, otherwise remove this line
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass
    
    
    def _can_prompt(self, meta: dict[str, Any]) -> bool:
        return not meta.get('unattended', False) or (meta.get('unattended', False) and meta.get('unattended_confirm', False))

    def _reject_or_confirm(self, meta: dict[str, Any], reason: str, allow_override: bool = False) -> bool:
        console.print(f'[bold red]{reason}[/bold red]')
        if not allow_override:
            return False
        if self._can_prompt(meta):
            return cli_ui.ask_yes_no("Do you want to upload anyway?", default=False)
        return False

    @staticmethod
    def _normalize_lang_set(values: Any) -> set[str]:
        if not isinstance(values, list):
            return set()
        return {str(lang).strip().lower() for lang in values if str(lang).strip()}

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

    # If there are tracker specific checks to be done before upload, add them here
    # Is it a movie only tracker? Are concerts banned? Etc.
    # If no checks are necessary, remove this function
    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True
        
        # NordicBytes does not allow for PAD files, so we check for that here and reject if found.
        filelist = meta.get('filelist', [])
        if isinstance(filelist, list):
            has_pad = any(os.path.basename(str(path)).lower().endswith('.pad') for path in filelist)
            if has_pad:
                return self._reject_or_confirm(meta, f'{self.tracker} does not allow uploads with .PAD files.')
        
        # NordicBytes has strict naming requirements, we check for unsupported characters here and reject if found.
        upload_name = str(meta.get('name', '')).strip()
        normalized_title = upload_name.replace(' ', '.')
        if re.search(r'[^A-Za-z0-9.\-]', normalized_title):
            return self._reject_or_confirm(
                meta,
                f'{self.tracker} title contains unsupported characters. Use only letters, numbers, dots, and hyphens.',
            )
        
        tag_value = str(meta.get('tag', '')).strip()
        if tag_value and '-' not in upload_name:
            return self._reject_or_confirm(
                meta,
                f'{self.tracker} title appears to be missing the group separator before tag (-GROUP).',
                allow_override=True,
            )
        
        if meta.get('hardcoded_subs', False):
            return self._reject_or_confirm(meta, f'{self.tracker} does not allow hardcoded subtitles.')
        
        subtitle_languages = self._normalize_lang_set(meta.get('subtitle_languages', []))
        subtitle_language_text = ' '.join(subtitle_languages)
        if any(token in subtitle_language_text for token in ('google translated', 'machine translated', 'auto translated')):
            return self._reject_or_confirm(meta, f'{self.tracker} does not allow machine translated subtitles.')

        name_edition = f"{meta.get('name', '')} {meta.get('edition', '')}".lower()
        if any(token in name_edition for token in ('upscale', 'upscaled', 'ai-upscale', 'ai upscale')):
            return self._reject_or_confirm(meta, f'{self.tracker} does not allow upscaled releases.')
        
        return should_continue
    
    
    async def get_description(self, meta: dict[str, Any]) -> dict[str, str]:
        if meta.get('logo', "") == "":
            TMDB_API_KEY = self.config['DEFAULT'].get('tmdb_api')
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id_raw = meta.get('tmdb')
            tmdb_id = int(tmdb_id_raw) if isinstance(tmdb_id_raw, (int, str)) and str(tmdb_id_raw).isdigit() else 0
            category = str(meta.get('category', ''))
            debug = bool(meta.get('debug'))
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            tmdb_api_key = str(TMDB_API_KEY) if TMDB_API_KEY else ''
            if tmdb_id and category:
                logo_path = await self.tmdb_manager.get_logo(
                    tmdb_id,
                    category,
                    debug,
                    logo_languages=logo_languages,
                    TMDB_API_KEY=tmdb_api_key,
                    TMDB_BASE_URL=TMDB_BASE_URL,
                )
                if logo_path:
                    meta['logo'] = logo_path

        return {'description': await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta)}

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    # If the tracker has specific naming conventions, add them here; otherwise, remove this function
    async def get_name(self, meta: Meta) -> dict[str, str]:
        nb_name = meta['name']
        nb_name = nb_name.replace(' ', '.')
        return {'name': nb_name}
