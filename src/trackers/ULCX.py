# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

import aiofiles
import cli_ui

from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class ULCX(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='ULCX')
        self.config = config
        self.tracker = 'ULCX'
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

    async def get_additional_checks(self, meta: Meta) -> bool:
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
        if meta['type'] in ["ENCODE", "HDTV"] and meta['resolution'] not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
            if not meta['unattended']:
                console.print(f'[bold red]Encodes must be at least 720p resolution for {self.tracker}.[/bold red]')
            return False

        if meta['type'] in ["DVDRIP"]:
            if not meta['unattended']:
                console.print(f'[bold red]DVDRIPs are not allowed for {self.tracker}.[/bold red]')
            return False

        if meta['is_disc'] != "BDMV" and not await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["english"], check_audio=True, check_subtitle=True
        ):
            return False

        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        if meta.get('personalrelease', False):
            if meta.get('has_multiple_default_audio_tracks', False):
                console.print(
                    f"[bold red]Multiple default audio tracks detected, skipping {self.tracker} upload.[/bold red]")
                return False

            if meta.get('has_multiple_default_subtitle_tracks', False):
                console.print(
                    f"[bold red]Multiple default subtitle tracks detected, skipping {self.tracker} upload.[/bold red]")
                return False

        if meta.get('non_disc_has_pcm_audio_tracks', False):
            console.print(
                f"[bold red]Non-disc source with PCM audio tracks detected, skipping {self.tracker} upload.[/bold red]")
            return False

        if meta.get('discs_missing_certificate', []):
            console.print(
                f"[bold red]Disc source(s) missing BD certificate, skipping {self.tracker} upload.[/bold red]")
            return False

        return should_continue

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_description(self, meta: Meta) -> dict[str, str]:
        desc = await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta, comparison=True)

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            pattern = r'(\[center\](?:(?!\[/center\]).)*\[/center\])'

            def wrap_in_spoiler(match: re.Match[str]) -> str:
                center_block = match.group(1)
                if '[img' not in center_block.lower():
                    return center_block
                return f'[center][spoiler=Screenshots]{center_block}[/spoiler][/center]'

            desc = re.sub(pattern, wrap_in_spoiler, desc, flags=re.DOTALL)
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as f:
                await f.write(desc)

        return {'description': desc}

    async def get_name(self, meta: Meta) -> dict[str, str]:
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
        if "Hybrid" in ulcx_name and meta.get('type') == "WEBDL":
            ulcx_name = ulcx_name.replace("Hybrid ", "", 1)
        if meta.get('category') != "TV" and imdb_year and imdb_year.strip() and year and year.strip() and imdb_year != year:
            ulcx_name = ulcx_name.replace(f"{year}", imdb_year, 1)

        return {'name': ulcx_name}
