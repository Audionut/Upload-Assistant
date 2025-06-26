# -*- coding: utf-8 -*-
import os
import re
import requests
import cli_ui
from src.exceptions import UploadException
from bs4 import BeautifulSoup
from src.console import console
from .COMMON import COMMON
from pymediainfo import MediaInfo


class DC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'DC'
        self.source_flag = 'DigitalCore.club'
        self.banned_groups = [""]
        self.base_url = "https://digitalcore.club"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    async def generate_description(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        description_parts = []

        # MediaInfo/BDInfo
        tech_info = ""
        if meta.get('is_disc') != 'BDMV':
            video_file = meta['filelist'][0]
            mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(mi_template):
                try:
                    media_info = MediaInfo.parse(video_file, output="STRING", full=False, mediainfo_options={"inform": f"file://{mi_template}"})
                    tech_info = str(media_info)
                except Exception:
                    console.print("[bold red]Couldn't find the MediaInfo template[/bold red]")
                    mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                    if os.path.exists(mi_file_path):
                        with open(mi_file_path, 'r', encoding='utf-8') as f:
                            tech_info = f.read()
            else:
                console.print("[bold yellow]Using normal MediaInfo for the description.[/bold yellow]")
                mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                if os.path.exists(mi_file_path):
                    with open(mi_file_path, 'r', encoding='utf-8') as f:
                        tech_info = f.read()
        else:
            bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary_file):
                with open(bd_summary_file, 'r', encoding='utf-8') as f:
                    tech_info = f.read()

        if tech_info:
            description_parts.append(tech_info)

        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            description_parts.append(manual_desc)

        # Screenshots
        images = meta.get('image_list', [])
        if images:
            screenshots_block = "[center][b]Screenshots[/b]\n"
            for i in range(min(4, len(images))):
                img_url = images[i]['img_url']
                web_url = images[i]['web_url']
                screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url] "
            screenshots_block += "[/center]"
            description_parts.append(screenshots_block)

        if self.signature:
            description_parts.append(self.signature)

        final_description = "\n\n".join(filter(None, description_parts))

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(final_description)

    async def search_existing(self, meta, disctype):
        return []

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]")
            return False

        common = COMMON(config=self.config)
        self.session.cookies.update(await common.parseCookieFile(cookie_file))

        try:
            test_url = f"{self.base_url}/upload"

            response = self.session.get(test_url, timeout=10, allow_redirects=False)

            if response.status_code == 200 and '/upload' in response.url:
                return True
            else:
                console.print(f"[bold red]Failed to validate {self.tracker} credentials. The cookie may be expired.[/bold red]")
                return False
        except Exception as e:
            console.print(f"[bold red]Error validating {self.tracker} credentials: {e}[/bold red]")
            return False

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        is_disc = meta.get('is_disc')
        tv_pack = meta.get('tv_pack')
        sd = meta.get('sd')

        if is_disc == 'BDMV':
            if resolution == '1080p' and category == 'MOVIE':
                return 3  # Movies/BluRay
            elif resolution == '2160p' and category == 'MOVIE':
                return 38  # Movies/Bluray/UHD
            elif category == 'TV':
                return 14  # Tv/BluRay

        if is_disc == 'DVD':
            if category == 'MOVIE':
                return 1  # Movies/DVDR
            elif category == 'TV':
                return 11  # Tv/DVDR

        if category == 'TV' and tv_pack == 1:
            return 12  # Tv/PACKS

        if sd == 1:
            if category == 'MOVIE':
                return 2
            elif category == 'TV':  # Movies/SD
                return 10  # Tv/SD

        category_map = {
            'MOVIE': {
                '2160p': 4,  # Movies/2160p
                '1080p': 6, '1080i': 6,  # Movies/1080p
                '720p': 5  # Movies/720p
            },
            'TV': {
                '2160p': 13,  # Tv/2160p
                '1080p': 9, '1080i': 9,  # Tv/1080p
                '720p': 8  # Tv/720p
            },
        }

        if category in category_map:
            return category_map[category].get(resolution)

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)

        if not await self.validate_credentials(meta):
            cli_ui.fatal(f"Failed to validate {self.tracker} credentials, aborting.")
            return

        cat_id = await self.get_category_id(meta)

        # Prepara e lê a descrição do arquivo
        await self.generate_description(meta)
        description_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(description_path, 'r', encoding='utf-8') as f:
            description = f.read()


        tracker_anon_setting = self.config['TRACKERS'][self.tracker].get('anon', False)
        is_anonymous = meta['anon'] != 0 or tracker_anon_setting is True

        if meta['bdinfo'] is not None:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()

        data = {
            'reqid': 0,
            'section': "new",
            'category': cat_id,
            'anonymousUpload': 1 if is_anonymous else 0,
            'imdbId': meta.get('imdb_info', {}).get('imdbID'),  # tem que fazer payload
            'p2p': 1,
            'unrar': 1,
            'frileech': 0,
            'mediainfo': mi_dump,
            'nfo': description,
            'submit': 'Send',
        }

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        with open(torrent_path, 'rb') as torrent_file:
            files = {'file': (f"{meta['name']}.torrent", torrent_file, "application/x-bittorrent")}
            self.session.headers.update({'Referer': f'{self.base_url}/api/v1/torrents/upload'})

            if meta['debug'] is False:
                upload_url = f"{self.base_url}/api/v1/torrents/upload"
                response = self.session.post(upload_url, data=data, files=files, timeout=60)

                if "This torrent may already exist in our database." in response.text:
                    console.print(f"[bold red]Upload to {self.tracker} failed: The torrent already exists on the site.[/bold red]")
                    raise UploadException(f"Upload to {self.tracker} failed: Duplicate detected.", "red")

                elif "Upload successful" in response.text:
                    details_url = 'DigitalCore.club'  # Add torrent link in the future?
                    announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                    await common.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)

                else:
                    console.print(f"[bold red]Upload to {self.tracker} failed.[/bold red]")
                    console.print(f"Status: {response.status_code}")
                    console.print(f"Response: {response.text[:800]}")
                    raise UploadException(f"Upload to {self.tracker} failed, check the response.", "red")
            else:
                console.print(f"[bold blue]Debug Mode: Upload to {self.tracker} was not sent.[/bold blue]")
                console.print("Headers:", self.session.headers)
                console.print("Payload (data):", data)
