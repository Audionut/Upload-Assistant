# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

from src.get_desc import DescriptionBuilder
from src.tmdb import TmdbManager
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class RAS(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='RAS')
        self.config: Config = config
        self.tmdb_manager = TmdbManager(config)
        self.tracker = 'RAS'
        self.base_url = 'https://rastastugan.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ['YTS', 'YiFY', 'LAMA', 'MeGUSTA', 'NAHOM', 'GalaxyRG', 'RARBG', 'INFINITY']

    def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        nordic_languages = ['danish', 'swedish', 'norwegian', 'icelandic', 'finnish', 'english']
        if not self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=nordic_languages, check_audio=True, check_subtitle=True
        ):
            return False

        return should_continue

    async def get_description(self, meta: Meta, cached_description: Optional[str] = None) -> dict[str, str]:  # noqa: ARG002
        if meta.get('logo', "") == "":
            TMDB_API_KEY = str(self.config['DEFAULT'].get('tmdb_api', ''))
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id = int(meta.get('tmdb', 0) or 0)
            category = str(meta.get('category', ''))
            debug = bool(meta.get('debug', False))
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            logo_path = await self.tmdb_manager.get_logo(
                tmdb_id,
                category,
                debug,
                logo_languages=logo_languages,
                TMDB_API_KEY=TMDB_API_KEY,
                TMDB_BASE_URL=TMDB_BASE_URL,
            )
            if logo_path:
                meta['logo'] = logo_path

        return {'description': await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta)}
