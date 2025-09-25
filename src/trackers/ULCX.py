# -*- coding: utf-8 -*-
# import discord
import cli_ui
from difflib import SequenceMatcher
from src.console import console
from src.languages import process_desc_language, has_english_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class ULCX(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='ULCX')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ULCX'
        self.source_flag = 'ULCX'
        self.base_url = 'https://upload.cx'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '4K4U', 'AROMA', 'd3g', ['EDGE2020', 'Encodes'], 'EMBER', 'FGT', 'FnP', 'FRDS', 'Grym', 'Hi10', 'iAHD', 'INFINITY',
            'ION10', 'iVy', 'Judas', 'LAMA', 'MeGusta', 'NAHOM', 'Niblets', 'nikt0', ['NuBz', 'Encodes'], 'OFT', 'QxR',
            ['Ralphy', 'Encodes'], 'RARBG', 'Sicario', 'SM737', 'SPDVD', 'SWTYBLZ', 'TAoE', 'TGx', 'Tigole', 'TSP',
            'TSPxL', 'VXT', 'Vyndros', 'Will1869', 'x0r', 'YIFY', 'Alcaide_Kira', 'PHOCiS'
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if 'concert' in meta['keywords']:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]Concerts not allowed at {self.tracker}.[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = {self.tracker}
                    return False
            else:
                meta['skipping'] = {self.tracker}
                return False
        if meta['video_codec'] == "HEVC" and meta['resolution'] != "2160p" and 'animation' not in meta['keywords'] and meta.get('anime', False) is not True:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]This content might not fit HEVC rules for {self.tracker}.[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = {self.tracker}
                    return False
            else:
                meta['skipping'] = {self.tracker}
                return False
        if meta['type'] == "ENCODE" and meta['resolution'] not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
            if not meta['unattended']:
                console.print(f'[bold red]Encodes must be at least 720p resolution for {self.tracker}.[/bold red]')
            meta['skipping'] = {self.tracker}
            return False
        if meta['bloated'] is True:
            console.print(f"[bold red]Non-English dub not allowed at {self.tracker}[/bold red]")
            meta['skipping'] = {self.tracker}
            return False

        if not meta['is_disc'] == "BDMV":
            if not meta.get('language_checked', False):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            if not await has_english_language(meta.get('audio_languages')) and not await has_english_language(meta.get('subtitle_languages')):
                if not meta['unattended']:
                    console.print(f'[bold red]{self.tracker} requires at least one English audio or subtitle track.')
                meta['skipping'] = {self.tracker}
                return False

        return should_continue

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_name(self, meta):
        ulcx_name = meta['name']
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        year = str(meta.get('year', ""))
        aka = meta.get('aka', "")
        if imdb_name and imdb_name != "":
            difference = SequenceMatcher(None, imdb_name, aka).ratio()
            if difference >= 0.7 or not aka or aka in imdb_name:
                if meta['aka'] != "":
                    ulcx_name = ulcx_name.replace(f"{meta['aka']} ", "", 1)
            ulcx_name = ulcx_name.replace(f"{meta['title']}", imdb_name, 1)
        if "Hybrid" in ulcx_name:
            ulcx_name = ulcx_name.replace("Hybrid ", "", 1)
        if not meta.get('category') == "TV" and imdb_year and imdb_year != "" and year and year != "" and imdb_year != year:
            ulcx_name = ulcx_name.replace(f"{year}", imdb_year, 1)
        if meta.get('mal_id', 0) != 0 and meta.get('aka', "") != "":
            ulcx_name = ulcx_name.replace(f"{meta['aka']} ", "", 1)

        return {'name': ulcx_name}
