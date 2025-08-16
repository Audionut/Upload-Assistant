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


class HDS(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'HDS'
        self.source_flag = 'HD-Space'
        self.banned_groups = [""]
        self.base_url = "https://hd-space.org"
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
        if not images or len(images) < 3:
            raise UploadException("[red]HDS requires at least 3 screenshots.[/red]")

        screenshots_block = "[center][b]Screenshots[/b]\n\n"
        for image in images:
            img_url = image['img_url']
            web_url = image['web_url']
            screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url] "
        screenshots_block += "[/center]"

        description_parts.append(screenshots_block)

        if self.signature:
            description_parts.append(self.signature)

        final_description = "\n\n".join(filter(None, description_parts))
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
        desc = desc.replace("[hide]", "").replace("[/hide]", "")
        desc = re.sub(r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]", r"NFO:[code][pre]\1[/pre][/code]", desc, flags=re.DOTALL)
        desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)
        desc = bbcode.remove_spoiler(desc)

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

    async def search_existing(self, meta, disctype):
        dupes = []
        if not await self.validate_credentials(meta):
            cli_ui.fatal(f"Failed to validate {self.tracker} credentials, skipping duplicate check.")
            return dupes

        imdb_id = meta.get('imdb', '')
        if imdb_id == '0':
            cli_ui.info(f"IMDb ID not found, cannot search for duplicates on {self.tracker}.")
            return dupes

        search_url = f"{self.base_url}/index.php?page=torrents&search={imdb_id}&active=0&options=2"

        try:
            response = self.session.get(search_url, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            torrent_links = soup.find_all('a', href=lambda href: href and 'page=torrent-details&id=' in href)

            if torrent_links:
                for link in torrent_links:
                    dupes.append(link.get_text(strip=True))

        except Exception as e:
            console.print(f"[bold red]Error searching for duplicates on {self.tracker}: {e}[/bold red]")

        return dupes

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/HDS.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]")
            return False

        common = COMMON(config=self.config)
        self.session.cookies.update(await common.parseCookieFile(cookie_file))

        try:
            test_url = f"{self.base_url}/index.php?page=upload"

            response = self.session.get(test_url, timeout=10, allow_redirects=False)

            if response.status_code == 200 and 'index.php?page=upload' in response.url:
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
        type_ = meta.get('type')
        is_disc = meta.get('is_disc')
        genres = meta.get("genres", "").lower()
        keywords = meta.get("keywords", "").lower()
        is_anime = meta.get('anime')

        if is_disc == 'BDMV':
            return 15  # Blu-Ray
        if type_ == 'REMUX':
            return 40  # Remux

        category_map = {
            'MOVIE': {
                '2160p': 46,
                '1080p': 19, '1080i': 19,
                '720p': 18
            },
            'TV': {
                '2160p': 45,
                '1080p': 22, '1080i': 22,
                '720p': 21
            },
            'DOCUMENTARY': {
                '2160p': 47,
                '1080p': 25, '1080i': 25,
                '720p': 24
            },
            'ANIME': {
                '2160p': 48,
                '1080p': 28, '1080i': 28,
                '720p': 27
            }
        }

        if 'documentary' in genres or 'documentary' in keywords:
            return category_map['DOCUMENTARY'].get(resolution, 38)
        if is_anime:
            return category_map['ANIME'].get(resolution, 38)

        if category in category_map:
            return category_map[category].get(resolution, 38)

        return 38

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)

        if not await self.validate_credentials(meta):
            cli_ui.fatal(f"Failed to validate {self.tracker} credentials, aborting.")
            return

        cat_id = await self.get_category_id(meta)

        await self.generate_description(meta)
        description_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(description_path, 'r', encoding='utf-8') as f:
            description = f.read()

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        tracker_anon_setting = self.config['TRACKERS'][self.tracker].get('anon', False)
        is_anonymous = meta['anon'] != 0 or tracker_anon_setting is True

        data = {
            'user_id': '',
            'category': cat_id,
            'filename': meta['name'],
            'imdb': meta.get('imdb', ''),
            'youtube_video': meta.get('youtube', ''),
            'info': description,
            'anonymous': 'true' if is_anonymous else 'false',
            't3d': 'true' if '3D' in meta.get('3d', '') else 'false',
            'req': 'false',
            'nuk': 'false',
            'nuk_rea': '',
            'submit': 'Send',
        }

        if meta.get('genre'):
            data['genre'] = meta.get('genre')

        with open(torrent_path, 'rb') as torrent_file:
            files = {'torrent': (os.path.basename(torrent_path), torrent_file, 'application/x-bittorrent')}
            self.session.headers.update({'Referer': f'{self.base_url}/index.php?page=upload'})

            if meta['debug'] is False:
                upload_url = f"{self.base_url}/index.php?page=upload"
                response = self.session.post(upload_url, data=data, files=files, timeout=60)

                if "This torrent may already exist in our database." in response.text:
                    console.print(f"[bold red]Upload to {self.tracker} failed: The torrent already exists on the site.[/bold red]")
                    raise UploadException(f"Upload to {self.tracker} failed: Duplicate detected.", "red")

                elif "Upload successful!" in response.text and "download.php?id=" in response.text:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    download_link_tag = soup.find('a', href=lambda href: href and "download.php?id=" in href)

                    if download_link_tag:
                        href = download_link_tag['href']
                        id_match = re.search(r'id=([a-f0-9]+)', href)

                        if id_match:
                            torrent_id = id_match.group(1)
                            details_url = f"{self.base_url}/index.php?page=torrent-details&id={torrent_id}"
                            meta['tracker_status'][self.tracker]['status_message'] = details_url

                            announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                            await common.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                        else:
                            console.print("[bold red]Critical Error: Could not extract torrent ID from the download link.[/bold red]")
                    else:
                        console.print("[bold yellow]Warning: Upload was successful, but the torrent link could not be found on the response page.[/bold yellow]")

                else:
                    console.print(f"[bold red]Upload to {self.tracker} failed.[/bold red]")
                    console.print(f"Status: {response.status_code}")
                    console.print(f"Response: {response.text[:800]}")
                    raise UploadException(f"Upload to {self.tracker} failed, check the response.", "red")
            else:
                console.print(f"[bold blue]Debug Mode: Upload to {self.tracker} was not sent.[/bold blue]")
                console.print("Headers:", self.session.headers)
                console.print("Payload (data):", data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
