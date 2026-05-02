# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any

from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

class MB(UNIT3D):
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, tracker_name='MB')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'MB'
        self.base_url = 'https://malayabits.cc'
        self.banned_url = f'{self.base_url}/api/bannedReleaseGroups'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.trumping_url = f'{self.base_url}/api/reports/torrents/'
        self.banned_groups = []
        pass

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def edit_name(self, meta):
        malayabits_name = meta['name']
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")

        if not meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        elif meta.get('audio_languages'):
            audio_languages = meta['audio_languages'][0].upper()
            if audio_languages and not await has_english_language(audio_languages):
                if (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
                    malayabits_name = malayabits_name.replace(str(meta['year']), f"{meta['year']} {audio_languages}", 1)
                elif not meta.get('is_disc') == "BDMV":
                    malayabits_name = malayabits_name.replace(meta['resolution'], f"{audio_languages} {meta['resolution']}", 1)

        if name_type == "DVDRIP":
            source = "DVDRip"
            malayabits_name = malayabits_name.replace(f"{meta['source']} ", "", 1)
            malayabits_name = malayabits_name.replace(f"{meta['video_encode']}", "", 1)
            malayabits_name = malayabits_name.replace(f"{source}", f"{resolution} {source}", 1)
            malayabits_name = malayabits_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)

        elif meta['is_disc'] == "DVD" or (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            malayabits_name = malayabits_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            malayabits_name = malayabits_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)

        return malayabits_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'Musik': '3',
        }.get(category_name, '0')
        return category_id

    async def get_res_id(self, resolution=None, reverse=False):
        resolution_mapping = {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
        }

        if reverse:
            # Return reverse mapping of IDs to resolutions
            return {v: k for k, v in resolution_mapping.items()}
        elif resolution is not None:
            # Return the ID for the given resolution
            return resolution_mapping.get(resolution, '10')  # Default to '10' for unknown resolutions
        else:
            # Return the full mapping
            return resolution_mapping
