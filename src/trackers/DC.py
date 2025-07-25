# -*- coding: utf-8 -*-
import os
import re
import requests
from src.exceptions import UploadException
from src.console import console
from src.rehostimages import check_hosts
from .COMMON import COMMON


class DC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'DC'
        self.source_flag = 'DigitalCore.club'
        self.base_url = "https://digitalcore.club"
        self.torrent_url = f"{self.base_url}/torrent/"
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
            desc_parts.append(f"{tech_info}\n")

        if os.path.exists(base_desc):
            with open(base_desc, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            desc_parts.append(manual_desc)

        # Screenshots
        if f'{self.tracker}_images_key' in meta:
            images = meta[f'{self.tracker}_images_key']
        else:
            images = meta['image_list']
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

        final_description = "\n".join(filter(None, desc_parts))
        from src.bbcode import BBCODE
        bbcode = BBCODE()
        desc = final_description
        desc = desc.replace("[user]", "").replace("[/user]", "")
        desc = desc.replace("[align=left]", "").replace("[/align]", "")
        desc = desc.replace("[right]", "").replace("[/right]", "")
        desc = desc.replace("[align=right]", "").replace("[/align]", "")
        desc = desc.replace("[sup]", "").replace("[/sup]", "")
        desc = desc.replace("[sub]", "").replace("[/sub]", "")
        desc = desc.replace("[alert]", "").replace("[/alert]", "")
        desc = desc.replace("[note]", "").replace("[/note]", "")
        desc = desc.replace("[hr]", "").replace("[/hr]", "")
        desc = desc.replace("[h1]", "[u][b]").replace("[/h1]", "[/b][/u]")
        desc = desc.replace("[h2]", "[u][b]").replace("[/h2]", "[/b][/u]")
        desc = desc.replace("[h3]", "[u][b]").replace("[/h3]", "[/b][/u]")
        desc = desc.replace("[ul]", "").replace("[/ul]", "")
        desc = desc.replace("[ol]", "").replace("[/ol]", "")
        desc = re.sub(r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]", r"[nfo]\1[/nfo]", desc, flags=re.DOTALL)
        desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
        desc = re.sub(r"(\[spoiler=[^]]+])", "[spoiler]", desc, flags=re.IGNORECASE)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)

        with open(dc_desc, 'w', encoding='utf-8') as f:
            f.write(desc)

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
        if not self.auth_cookies:
            if not await self.login():
                console.print(f"[bold red]Search failed on {self.tracker} because login failed.[/bold red]")
                return []

        imdb_id = meta.get('imdb_info', {}).get('imdbID')
        if not imdb_id:
            console.print(f"[bold yellow]Cannot perform search on {self.tracker}: IMDb ID not found in metadata.[/bold yellow]")
            return []

        search_url = f"{self.api_base_url}/torrents"
        search_params = {'searchText': imdb_id}

        try:
            response = self.session.get(search_url, params=search_params, cookies=self.auth_cookies, timeout=15)
            response.raise_for_status()

            if response.text and response.text != '[]':
                results = response.json()
                if results and isinstance(results, list):
                    return results

        except Exception as e:
            console.print(f"[bold red]Error searching for IMDb ID '{imdb_id}' on {self.tracker}: {e}[/bold red]")

        return []

    async def upload(self, meta, disctype):
        await self.edit_torrent(meta, self.tracker, self.source_flag)
        approved_image_hosts = ['imgbox', 'imgbb', "bhd", "imgur", "postimg", "digitalcore"]
        url_host_mapping = {
            "ibb.co": "imgbb",
            "imgbox.com": "imgbox",
            "beyondhd.co": "bhd",
            "imgur.com": "imgur",
            "postimg.cc": "postimg",
            "digitalcore.club": "digitalcore"
        }

        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)

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
            is_scene = bool(meta.get('scene_name'))
            base_name = meta['scene_name'] if is_scene else meta['uuid']

            existing_torrents = await self.search_existing(meta, disctype)
            needs_unrar_tag = False

            if existing_torrents:
                current_release_identifiers = {meta['uuid']}
                if is_scene:
                    current_release_identifiers.add(meta['scene_name'])

                relevant_torrents = [
                    t for t in existing_torrents
                    if t.get('name') in current_release_identifiers
                ]

                if relevant_torrents:
                    unrar_version_exists = any(t.get('unrar', 0) != 0 for t in relevant_torrents)

                    if unrar_version_exists:
                        raise UploadException("An UNRAR duplicate of this specific release already exists on site.")
                    else:
                        console.print(f"[bold yellow]Found a RAR version of this release on {self.tracker}. Appending [UNRAR] to filename.[/bold yellow]")
                        needs_unrar_tag = True

            if needs_unrar_tag:
                upload_base_name = meta['scene_name'] if is_scene else meta['uuid']
                upload_filename = f"{upload_base_name} [UNRAR].torrent"
            else:
                upload_filename = f"{base_name}.torrent"

            upload_filename = upload_filename.replace('.mkv', '').replace('.mp4', '')

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file': (upload_filename, torrent_file, "application/x-bittorrent")}
                upload_url = f"{self.api_base_url}/torrents/upload"

                if meta['debug'] is False:
                    response = self.session.post(upload_url, data=data, files=files, cookies=self.auth_cookies, timeout=90)
                    response.raise_for_status()
                    json_response = response.json()
                    meta['tracker_status'][self.tracker]['status_message'] = response.json()

                    if response.status_code == 200 and json_response.get('id'):
                        torrent_id = json_response.get('id')
                        details_url = f"{self.base_url}/torrent/{torrent_id}/" if torrent_id else self.base_url
                        if torrent_id:
                            meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await self.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                    else:
                        raise UploadException(f"{json_response.get('message', 'Unknown API error.')}")
                else:
                    console.print(f"[bold blue]Debug Mode: Upload to {self.tracker} was not sent.[/bold blue]")
                    console.print("Headers:", self.session.headers)
                    console.print("Payload (data):", data)
                    meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."

        except UploadException:
            raise
        except Exception as e:
            raise UploadException(f"An unexpected error occurred during upload to {self.tracker}: {e}")
