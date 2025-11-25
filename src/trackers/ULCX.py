# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import cli_ui
import re
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language, has_english_language
from src.trackers.UNIT3D import UNIT3D


class ULCX(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='ULCX')
        self.config = config
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
            'TSPxL', 'VXT', 'Vyndros', 'Will1869', 'x0r', 'YIFY', 'Alcaide_Kira', 'PHOCiS', 'HDT', 'SPx', 'seedpool'
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
                    return False
            else:
                return False
        if meta['video_codec'] == "HEVC" and meta['resolution'] != "2160p" and 'animation' not in meta['keywords'] and meta.get('anime', False) is not True:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]This content might not fit HEVC rules for {self.tracker}.[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False
        if meta['type'] == "ENCODE" and meta['resolution'] not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
            if not meta['unattended']:
                console.print(f'[bold red]Encodes must be at least 720p resolution for {self.tracker}.[/bold red]')
            return False
        if meta['bloated'] is True:
            console.print(f"[bold red]Non-English dub not allowed at {self.tracker}[/bold red]")
            return False

        if not meta['is_disc'] == "BDMV":
            if not meta.get('language_checked', False):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            if not await has_english_language(meta.get('audio_languages')) and not await has_english_language(meta.get('subtitle_languages')):
                if not meta['unattended']:
                    console.print(f'[bold red]{self.tracker} requires at least one English audio or subtitle track.')
                return False

        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        return should_continue

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_description(self, meta):
        desc = await DescriptionBuilder(self.config).unit3d_edit_desc(meta, self.tracker, comparison=True)

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            pattern = r'(\[center\](?:\s*\[url=[^\]]+\]\[img(?:=[0-9]+)?\][^\]]+\[/img\]\[/url\]\s*)+\[/center\])'

            def wrap_in_spoiler(match):
                center_block = match.group(1)
                return f'[center][spoiler=Screenshots]{center_block}[/spoiler][/center]'

            desc = re.sub(pattern, wrap_in_spoiler, desc, flags=re.DOTALL)
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as f:
                await f.write(desc)

        return {'description': desc}

    async def get_name(self, meta):
        ulcx_name = meta['name']
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        imdb_aka = meta.get('imdb_info', {}).get('aka', "")
        year = str(meta.get('year', ""))
        aka = meta.get('aka', "")
        if imdb_name and imdb_name.strip():
            if aka:
                ulcx_name = ulcx_name.replace(f"{aka} ", "", 1)
            ulcx_name = ulcx_name.replace(f"{meta['title']}", imdb_name, 1)
            if imdb_aka and imdb_aka.strip() and imdb_aka != imdb_name and not meta.get('no_aka', False) and not meta.get('anime', False):
                ulcx_name = ulcx_name.replace(f"{imdb_name}", f"{imdb_name} AKA {imdb_aka}", 1)
        if "Hybrid" in ulcx_name:
            ulcx_name = ulcx_name.replace("Hybrid ", "", 1)
        if not meta.get('category') == "TV" and imdb_year and imdb_year.strip() and year and year.strip() and imdb_year != year:
            ulcx_name = ulcx_name.replace(f"{year}", imdb_year, 1)

        return {'name': ulcx_name}
