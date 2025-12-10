# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import cli_ui
import re
from data.config import config
from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.UNIT3D import UNIT3D


class DP(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='DP')
        self.config = config
        self.tracker = 'DP'
        self.source_flag = 'DarkPeers'
        self.base_url = 'https://darkpeers.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            'ARCADE', 'aXXo', 'BANDOLEROS', 'BONE', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'dAV1nci', 'DNL',
            'FaNGDiNG0', 'FiSTER', 'GalaxyTV', 'HD2DVD', 'HDT', 'HDTime', 'iHYTECH', 'ION10',
            'iPlanet', 'KiNGDOM', 'LAMA', 'MeGusta', 'mHD', 'mSD', 'NaNi', 'NhaNc3', 'nHD',
            'nikt0', 'nSD', 'OFT', 'PiTBULL', 'PRODJi', 'RARBG', 'Rifftrax', 'ROCKETRACCOON',
            'SANTi', 'SasukeducK', 'SEEDSTER', 'ShAaNiG', 'Sicario', 'STUTTERSHIT', 'TAoE',
            'TGALAXY', 'TGx', 'TORRENTGALAXY', 'ToVaR', 'TSP', 'TSPxL', 'ViSION', 'VXT',
            'WAF', 'WKS', 'X0r', 'YIFY', 'YTS',
        ]
        pass

    async def get_additional_checks(self, meta):
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

        if meta['type'] == "ENCODE" and meta.get('tag', "") in ['FGT']:
            if not meta['unattended']:
                console.print(f"[bold red]{self.tracker} does not allow FGT encodes, skipping upload.")
            return False

        if meta['type'] not in ['WEBDL'] and meta.get('tag', "") in ['EVO']:
            if not meta['unattended']:
                console.print(f"[bold red]{self.tracker} does not allow EVO for non-WEBDL types, skipping upload.")
            return False

        return should_continue

    async def get_description(self, meta):
        if meta.get('logo', "") == "":
            from src.tmdb import get_logo
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

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_name(self, meta):
        dp_name = meta.get('name')
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        tag_lower = meta['tag'].lower()
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                dp_name = re.sub(f"-{invalid_tag}", "", dp_name, flags=re.IGNORECASE)
            dp_name = f"{dp_name}-NOGROUP"
        return {'name': dp_name}
