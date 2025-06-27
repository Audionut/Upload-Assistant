# -*- coding: utf-8 -*-
import os
import requests
from src.exceptions import UploadException
from src.console import console
from .COMMON import COMMON


class DC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'DC'
        self.source_flag = 'DigitalCore.club'
        self.base_url = "https://digitalcore.club"
        self.api_base_url = f"{self.base_url}/api/v1"
        self.banned_groups = [""]

        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.api_key = self.config['TRACKERS'][self.tracker].get('announce_url').replace('https://digitalcore.club/tracker.php/', '').replace('/announce', '')
        self.username = self.config['TRACKERS'][self.tracker].get('username')
        self.password = self.config['TRACKERS'][self.tracker].get('password')
        self.auth_cookies = None
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    async def generate_description(self, meta):
        base_desc = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        dc_desc = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        desc_parts = []

        # BDInfo
        tech_info = ""
        if meta.get('is_disc') == 'BDMV':
            bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary_file):
                with open(bd_summary_file, 'r', encoding='utf-8') as f:
                    tech_info = f.read()

        if tech_info:
            desc_parts.append(tech_info)

        if os.path.exists(base_desc):
            with open(base_desc, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            desc_parts.append(manual_desc)

        # Screenshots
        images = meta.get('image_list', [])
        if images:
            screenshots_block = "[center][b]Screenshots[/b]\n\n"
            for image in images:
                img_url = image['img_url']
                web_url = image['web_url']
                screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url] "
            screenshots_block += "[/center]"
            desc_parts.append(screenshots_block)

        if self.signature:
            desc_parts.append(self.signature)

        final_description = "\n\n".join(filter(None, desc_parts))

        with open(dc_desc, 'w', encoding='utf-8') as f:
            f.write(final_description)

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        is_disc = meta.get('is_disc')
        tv_pack = meta.get('tv_pack')
        sd = meta.get('sd')

        if is_disc == 'BDMV':
            if resolution == '1080p' and category == 'MOVIE':
                return 3
            elif resolution == '2160p' and category == 'MOVIE':
                return 38
            elif category == 'TV':
                return 14
        if is_disc == 'DVD':
            if category == 'MOVIE':
                return 1
            elif category == 'TV':
                return 11
        if category == 'TV' and tv_pack == 1:
            return 12
        if sd == 1:
            if category == 'MOVIE':
                return 2
            elif category == 'TV':
                return 10
        category_map = {
            'MOVIE': {'2160p': 4, '1080p': 6, '1080i': 6, '720p': 5},
            'TV': {'2160p': 13, '1080p': 9, '1080i': 9, '720p': 8},
        }
        if category in category_map:
            return category_map[category].get(resolution)
        return None

    async def login(self):
        if self.auth_cookies:
            return True
        if not all([self.username, self.password, self.api_key]):
            console.print(f"[bold red]Username, password, or api_key for {self.tracker} is not configured.[/bold red]")
            return False

        login_url = f"{self.api_base_url}/auth"
        auth_params = {'username': self.username, 'password': self.password, 'captcha': self.api_key}

        try:
            response = self.session.get(login_url, params=auth_params, timeout=10)

            if response.status_code == 200 and response.cookies:
                self.auth_cookies = response.cookies
                return True
            else:
                console.print(f"[bold red]Failed to authenticate or no cookies received. Status: {response.status_code}[/bold red]")
                self.auth_cookies = None
                return False
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error during {self.tracker} authentication: {e}[/bold red]")
            self.auth_cookies = None
            return False

    async def search_existing(self, meta, disctype):
        dupes = []
        if not self.auth_cookies:
            if not await self.login():
                console.print(f"[bold red]Search failed on {self.tracker} because login failed.[/bold red]")
                return dupes

        search_url = f"{self.api_base_url}/torrents_exact_search"
        search_params = {'searchText': meta['uuid']}

        try:
            response = self.session.get(search_url, params=search_params, cookies=self.auth_cookies, timeout=15)
            response.raise_for_status()

            if not response.text or response.text == '[]':
                return dupes

            results = response.json()
            if results and isinstance(results, list):
                for torrent in results:
                    dupes.append(torrent.get('name', ''))
            return dupes
        except Exception as e:
            console.print(f"[bold red]Error searching on {self.tracker}: {e}[/bold red]")
            return dupes

    async def upload(self, meta, disctype):
        await self.edit_torrent(meta, self.tracker, self.source_flag)

        if await self.search_existing(meta, disctype):
            raise UploadException(f"Upload to {self.tracker} failed: Duplicate torrent detected on site.", "red")

        cat_id = await self.get_category_id(meta)

        await self.generate_description(meta)

        description_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(description_path, 'r', encoding='utf-8') as f:
            description = f.read()

        imdb = meta.get('imdb_info', {}).get('imdbID', '')

        mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{'BD_SUMMARY_00.txt' if meta.get('is_disc') == 'BDMV' else 'MEDIAINFO.txt'}"
        with open(mi_path, 'r', encoding='utf-8') as f:
            mediainfo_dump = f.read()

        is_anonymous = "1" if meta['anon'] != 0 or self.config['TRACKERS'][self.tracker].get('anon', False) else "0"

        data = {
            'category': cat_id,
            'imdbId': imdb,
            'nfo': description,
            'mediainfo': mediainfo_dump,
            'reqid': "0",
            'section': "new",
            'frileech': "1",
            'anonymousUpload': is_anonymous,
            'p2p': "0"
        }

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        try:
            with open(torrent_path, 'rb') as torrent_file:
                files = {'file': (f"{meta['uuid']}.torrent", torrent_file, "application/x-bittorrent")}

                upload_url = f"{self.api_base_url}/torrents/upload"

                if meta['debug'] is False:
                    response = self.session.post(upload_url, data=data, files=files, cookies=self.auth_cookies, timeout=90)
                    response.raise_for_status()

                    json_response = response.json()
                    if response.status_code == 200 and json_response.get('id'):
                        torrent_id = json_response.get('id')
                        details_url = f"{self.base_url}/torrent/{torrent_id}/" if torrent_id else self.base_url
                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await self.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                    else:
                        raise UploadException(f"Upload to {self.tracker} failed: {json_response.get('message', 'Unknown API error.')}", "red")
                else:
                    console.print(f"[bold blue]Debug Mode: Upload to {self.tracker} was not sent.[/bold blue]")
                    console.print("Headers:", self.session.headers)
                    console.print("Payload (data):", data)

        except Exception as e:
            raise UploadException(f"An unexpected error occurred during upload to {self.tracker}: {e}", "red")
