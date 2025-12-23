# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
from src.console import console
from src.languages import process_desc_language, has_english_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class AITHER(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='AITHER')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'AITHER'
        self.source_flag = 'Aither'
        self.base_url = 'https://aither.cc'
        self.banned_url = f'{self.base_url}/api/blacklists/releasegroups'
        self.claims_url = f'{self.base_url}/api/internals/claim'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.banned_groups = []
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if meta['valid_mi'] is False:
            console.print("[bold red]No unique ID in mediainfo, skipping AITHER upload.")
            return False

        return should_continue

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_name(self, meta):
        aither_name = meta['name']
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")

        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        audio_languages = meta['audio_languages']
        if audio_languages and not await has_english_language(audio_languages):
            foreign_lang = meta['audio_languages'][0].upper()
            if (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
                aither_name = aither_name.replace(str(meta['year']), f"{meta['year']} {foreign_lang}", 1)
            elif not meta.get('is_disc') == "BDMV":
                aither_name = aither_name.replace(meta['resolution'], f"{foreign_lang} {meta['resolution']}", 1)

        if name_type == "DVDRIP":
            source = "DVDRip"
            aither_name = aither_name.replace(f"{meta['source']} ", "", 1)
            aither_name = aither_name.replace(f"{meta['video_encode']}", "", 1)
            aither_name = aither_name.replace(f"{source}", f"{resolution} {source}", 1)
            aither_name = aither_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)

        elif meta['is_disc'] == "DVD" or (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            aither_name = aither_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            aither_name = aither_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)

        return {'name': aither_name}
