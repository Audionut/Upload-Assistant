# -*- coding: utf-8 -*-
import httpx
import os
import platform
import re
from pymediainfo import MediaInfo
from .COMMON import COMMON
from bs4 import BeautifulSoup
from src.console import console
from src.languages import process_desc_language


class PTS(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "PTS"
        self.banned_groups = [""]
        self.source_flag = "[www.ptskit.org] PTSKIT"
        self.base_url = "https://www.ptskit.org"
        self.torrent_url = "https://www.ptskit.org/details.php?id="
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.signature = "[center]Created by Audionut's Upload Assistant[/center]"

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]")
            return False

        self.session.cookies = await self.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)

        upload_page_url = f"{self.base_url}/upload.php"
        response = await self.session.get(upload_page_url, timeout=30.0)
        response.raise_for_status()

        if 'login.php' in str(response.url):
            console.print(f"[bold red]{self.tracker} validation failed. Cookie appears to be expired (redirected to login).[/bold red]")
            return False

        return True

    async def get_type(self, meta):
        if meta.get('anime'):
            return '407'

        category_map = {
            'TV': '405',
            'MOVIE': '404'
        }

        return category_map.get(meta['category'])

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
            description_parts.append(screenshots_block)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header)

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
        desc = re.sub(r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]", r"", desc, flags=re.DOTALL)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)
        desc = bbcode.remove_spoiler(desc)
        desc = re.sub(r'\n{3,}', '\n\n', desc)

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def search_existing(self, meta, disctype):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        langs = [lang.lower() for lang in meta.get('subtitle_languages', []) + meta.get('audio_languages', [])]
        mandarin = 'mandarin' in langs or 'chinese' in langs

        if not mandarin:
            response = input("Warning: Mandarin subtitle or audio not found. Do you want to continue with the upload anyway? (y/n): ")
            if response.lower() not in ['y', 'yes']:
                print("Upload cancelled by user.")
                meta['skipping'] = f"{self.tracker}"
                return

        search_url = f"{self.base_url}/torrents.php"
        params = {
            'incldead': 1,
            'search': meta['imdb_info']['imdbID'],
            'search_area': 4
        }
        found_items = []

        try:
            response = await self.session.get(search_url, params=params, cookies=self.session.cookies)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            torrents_table = soup.find('table', class_='torrents')

            if torrents_table:
                torrent_name_tables = torrents_table.find_all('table', class_='torrentname')

                for torrent_table in torrent_name_tables:
                    name_tag = torrent_table.find('b')
                    if name_tag:
                        torrent_name = name_tag.get_text(strip=True)
                        found_items.append(torrent_name)

        except Exception as e:
            print(f"An error occurred while searching: {e}")

        return found_items

    async def gather_data(self, meta, disctype):
        data = {
            'name': meta['name'],
            'url': f"https://www.imdb.com/title/{meta.get('imdb_info', {}).get('imdbID', '')}",
            'descr': await self.generate_description(meta),
            'type': await self.get_type(meta),
        }

        return data

    async def upload(self, meta, disctype):
        await self.load_cookies(meta)
        await self.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.gather_data(meta, disctype)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            upload_url = f"{self.base_url}/takeupload.php"
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file': (f"{self.tracker}.placeholder.torrent", torrent_file, "application/x-bittorrent")}

                response = await self.session.post(upload_url, data=data, files=files, timeout=120)

                if response.status_code in (302, 303):
                    status_message = "Uploaded successfully."

                    redirect_url = response.headers['Location']
                    match = re.search(r'id=(\d+)', redirect_url)
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                else:
                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    console.print(f"Upload failed, HTML response was saved to: {response_save_path}")
                    meta['skipping'] = f"{self.tracker}"
                    return

            await self.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
