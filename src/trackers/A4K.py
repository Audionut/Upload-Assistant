# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
from typing import Any, Optional

import cli_ui

from src.console import console
from src.languages import languages_manager
from src.rehostimages import RehostImagesManager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class A4K(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='A4K')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'A4K'
        self.base_url = 'https://aura4k.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.rehost_images_manager = RehostImagesManager(config)
        self.approved_image_hosts = ['ptpimg', 'onlyimage','imgbox', 'ptscreens', 'imgbb', 'imgur', 'postimg']
        self.banned_groups = ["BiTOR", "DepraveD", "Flights", "SasukeducK", "SPDVD", "TEKNO3D"]
        pass

    async def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'ENCODE': '3'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (resolution, reverse, mapping_only)
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True
        if meta.get('resolution') not in ['2160p', '4320p']:
            if not meta.get('unattended'):
                console.print(f"[red]{self.tracker} only accepts 4K uploads.")
            return False

        if meta.get('type') not in ['DISC', 'REMUX', 'WEBDL', 'ENCODE']:
            if not meta.get('unattended'):
                console.print(f"[red]{self.tracker} only accepts DISC, REMUX, WEBDL, and ENCODE uploads.")
            return False

        if 'AV1' in meta.get('video_codec', ''):
            # AV1 has no bitrate requirements, so skip the bitrate check for AV1 uploads
            return should_continue

        # check bitrate requirements for A4K uploads, but only if it's not a disc upload since discs can have variable bitrates and A4K doesn't specify bitrate requirements for disc uploads
        if not meta['is_disc'] and meta['type'] in ['ENCODE', 'WEBDL']:
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            for track in tracks:
                if track.get('@type') == "Video":
                    encoding_settings = track.get('Encoded_Library_Settings', {})

                    if encoding_settings:
                        bit_rate = track.get('BitRate')
                        if bit_rate:
                            try:
                                bit_rate_num = int(bit_rate)
                            except (ValueError, TypeError):
                                bit_rate_num = None

                            if bit_rate_num is not None:
                                bit_rate_kbps = bit_rate_num / 1000
                                if meta.get('category') == "MOVIE" and bit_rate_kbps < 15000:
                                    if not meta.get('unattended', False):
                                        console.print(f"Video bitrate too low: {bit_rate_kbps:.0f} kbps for A4K movie uploads.")
                                    return False
                                elif meta.get('category') == "TV" and bit_rate_kbps < 10000:
                                    if not meta.get('unattended', False):
                                        console.print(f"Video bitrate too low: {bit_rate_kbps:.0f} kbps for A4K TV uploads.")
                                    return False
                            else:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                    console.print(f"[bold red]Could not determine video bitrate from mediainfo for {self.tracker} upload.[/bold red]")
                                    console.print("[yellow]Bitrate must be above 15000 kbps for movies and 10000 kbps for TV shows.[/yellow]")
                                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                                        pass
                                    else:
                                        return False
                        else:
                            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                console.print(f"[bold red]Could not determine video bitrate from mediainfo for {self.tracker} upload.[/bold red]")
                                console.print("[yellow]Bitrate must be above 15000 kbps for movies and 10000 kbps for TV shows.[/yellow]")
                                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                                    pass
                                else:
                                    return False
                    else:
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                            console.print(f"[bold red]Could not determine video bitrate from mediainfo for {self.tracker} upload.[/bold red]")
                            console.print("[yellow]Bitrate must be above 15000 kbps for movies and 10000 kbps for TV shows.[/yellow]")
                            if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                                pass
                            else:
                                return False

        return should_continue

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        url_host_mapping = {
            'ibb.co': 'imgbb',
            'imgbox.com': 'imgbox',
            'imgur.com': 'imgur',
            'postimg.cc': 'postimg',
            'ptscreens.com': 'ptscreens',
            'onlyimage.org': 'onlyimage',
            'ptpimg.me': 'ptpimg',
        }
        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts,
        )
        return

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        a4k_name: str = meta["name"]
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
        audio_languages: list[str] = meta['audio_languages']
        if audio_languages and not await languages_manager.has_english_language(audio_languages):
            foreign_lang = audio_languages[0].upper()
            if meta.get('is_disc') != "BDMV":
                a4k_name = a4k_name.replace(meta['resolution'], f"{foreign_lang} {meta['resolution']}", 1)
        console.print(f"[yellow]Generated name for {self.tracker}: [bold]{a4k_name}[/bold][/yellow]")
        return {'name': a4k_name}
