# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, cast

import cli_ui

from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.tmdb import TmdbManager
from src.trackers.UNIT3D import UNIT3D


class DP(UNIT3D):
    """Tracker class for DarkPeers (DP), a UNIT3D-based Nordic tracker."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the DarkPeers tracker with API endpoints and banned groups."""
        super().__init__(config, tracker_name='DP')
        self.config = config
        self.tmdb_manager = TmdbManager(config)
        self.tracker = 'DP'
        self.base_url = 'https://darkpeers.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            'ARCADE', 'aXXo', 'BANDOLEROS', 'BONE', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'dAV1nci', 'DNL',
            'eranger2', 'FaNGDiNG0', 'FGT', 'FiSTER', 'flower', 'GalaxyTV', 'HD2DVD', 'HDTime', 'HorribleSubs',
            'iHYTECH', 'ION10', 'iPlanet', 'KiNGDOM', 'LAMA', 'MeGusta', 'mHD', 'mSD', 'NaNi', 'NhaNc3', 'nHD',
            'nikt0', 'nSD', 'OFT', 'PiTBULL', 'PRODJi', 'PSA', 'RARBG', 'Rifftrax', 'ROCKETRACCOON',
            'SANTi', 'SasukeducK', 'SEEDSTER', 'ShAaNiG', 'Sicario', 'STUTTERSHIT', 'Subsplease', 'SyncUp',
            'TAoE', 'TGALAXY', 'TGx', 'TORRENTGALAXY', 'ToVaR', 'Trix', 'TSP', 'TSPxL', 'ViSION', 'VXT',
            'WAF', 'WKS', 'X0r', 'YIFY', 'YTS',
        ]
        pass

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        """Validate DP-specific upload rules: folder structure, Nordic languages, EVO, and hardcoded subs."""
        should_continue = True
        if meta.get('keep_folder'):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]{self.tracker} does not allow single files in a folder.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        nordic_languages = ['danish', 'swedish', 'norwegian', 'icelandic', 'finnish', 'english']
        if not await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=nordic_languages, check_audio=True, check_subtitle=True
        ):
            return False

        if meta['type'] not in ['WEBDL'] and meta.get('tag', "") in ['EVO']:
            if not meta['unattended']:
                console.print(f"[bold red]{self.tracker} does not allow EVO for non-WEBDL types, skipping upload.")
            return False

        if meta.get('hardcoded_subs', False) and not meta['unattended']:
            console.print(f"[bold red]{self.tracker} does not allow hardcoded subtitles.")
            return False

        return should_continue

    async def get_description(self, meta: dict[str, Any]) -> dict[str, str]:
        """Build the upload description, fetching a Nordic-language logo from TMDB if needed."""
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
        """Return additional upload fields including mod queue opt-in."""
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_audio(self, meta: dict[str, Any]) -> str:
        """Determine the audio language tag: single language, Dual-Audio, or MULTi."""
        languages_result = "SKIPPED"

        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        audio_languages = meta.get('audio_languages')
        if isinstance(audio_languages, list):
            audio_languages_list = cast(list[Any], audio_languages)
            normalized_languages = {str(lang).strip() for lang in audio_languages_list if str(lang).strip()}

            if len(normalized_languages) > 2:
                languages_result = "MULTi"
            elif len(normalized_languages) > 1:
                languages_result = "Dual-Audio"
            else:
                languages_result = str(next(iter(normalized_languages), "SKIPPED"))

        return f'{languages_result}'

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        """Build the release name with audio language normalization and Hybrid tag handling."""
        dp_name = str(meta.get('name', ''))

        audio = await self.get_audio(meta)
        if audio and audio != "SKIPPED" and "Dual-Audio" in dp_name:
            dp_name = dp_name.replace("Dual-Audio", audio)

        title = str(meta.get('title', ''))
        year = str(meta.get('year', ''))
        technical_suffix = dp_name
        if title:
            title_idx = dp_name.find(title)
            if title_idx != -1:
                technical_suffix = dp_name[title_idx + len(title):]
        if year and year in technical_suffix:
            year_idx = technical_suffix.find(year)
            technical_suffix = technical_suffix[year_idx + len(year):]

        has_hybrid_tag = bool(re.search(r'\bHybrid\b', technical_suffix, re.IGNORECASE))

        if has_hybrid_tag:
            prefix = dp_name[:len(dp_name) - len(technical_suffix)]
            technical_suffix = re.sub(r'\bHybrid\b', 'Hybrid', technical_suffix, flags=re.IGNORECASE)
            dp_name = prefix + technical_suffix
        elif not meta.get('unattended') or meta.get('unattended_confirm', False):
            console.print(
                f'[bold yellow][{self.tracker}] DarkPeers requires "Hybrid" in the name '
                'when audio and video come from different sources.'
            )
            if cli_ui.ask_yes_no('Does this release require "Hybrid" in the name?', default=False):
                resolution = str(meta.get('resolution', ''))
                if resolution and f' {resolution} ' in dp_name:
                    dp_name = dp_name.replace(f' {resolution} ', f' Hybrid {resolution} ', 1)
                elif resolution and dp_name.endswith(f' {resolution}'):
                    dp_name = dp_name[: -len(resolution)] + f'Hybrid {resolution}'
                else:
                    dp_name = f'{dp_name} Hybrid'

        return {'name': dp_name}
