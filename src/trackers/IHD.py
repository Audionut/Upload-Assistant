# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui
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
            if not await has_english_language(meta.get('audio_languages')) and not await has_english_language(meta.get('subtitle_languages')):
                if not meta['unattended'] or meta['debug']:
                    console.print(f'[bold red]{self.tracker} requires at least one English audio or subtitle track.')
                should_continue = False

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))):
                console.print(f'[bold red]Pornographic content is not allowed at {self.tracker}, unless it follows strict rules.')
                yes = cli_ui.ask_yes_no(f'Do you have persmission to upload this torrent to {self.tracker}?', default=False)
                if yes:
                    should_continue = True
                else:
                    should_continue = False
            else:
                if not meta['unattended'] or meta['debug']:
                    console.print('[bold red]Pornographic content is not allowed at IHD, unless it follows strict rules.')
                should_continue = False

        return should_continue
