# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from data.config import config
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language
from src.tmdb import get_logo
from src.trackers.UNIT3D import UNIT3D


class RAS(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='RAS')
        self.config = config
        self.tracker = 'RAS'
        self.source_flag = 'Rastastugan'
        self.base_url = 'https://rastastugan.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['YTS', 'YiFY', 'LAMA', 'MeGUSTA', 'NAHOM', 'GalaxyRG', 'RARBG', 'INFINITY']
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        nordic_languages = ['Danish', 'Swedish', 'Norwegian', 'Icelandic', 'Finnish', 'English']
        if not any(lang in meta.get('audio_languages', []) for lang in nordic_languages) and not any(lang in meta.get('subtitle_languages', []) for lang in nordic_languages):
            console.print(f'[bold red]{self.tracker} requires at least one Nordic/English audio or subtitle track.')
            should_continue = False

        return should_continue

    async def get_description(self, meta):
        if meta.get('logo', "") == "":
            TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id = meta.get('tmdb')
            category = meta.get('category')
            debug = meta.get('debug')
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            logo_path = await get_logo(tmdb_id, category, debug, logo_languages=logo_languages, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)
            if logo_path:
                meta['logo'] = logo_path

        return {'description': await DescriptionBuilder(self.config).unit3d_edit_desc(meta, self.tracker)}
