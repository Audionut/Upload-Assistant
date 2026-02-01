# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import platform
import re
from typing import Any, Optional, cast

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup
from pymediainfo import MediaInfo

from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class PTS:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = "PTS"
        self.banned_groups = []
        self.source_flag = "[www.ptskit.org] PTSKIT"
        self.base_url = "https://www.ptskit.org"
        self.torrent_url = "https://www.ptskit.org/details.php?id="
        self.announce = str(self.config['TRACKERS'][self.tracker]['announce_url'])
        self.auth_token: Optional[str] = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Upload Assistant/2.3 ({platform.system()} {platform.release()})"
        }, timeout=60.0)

    async def validate_credentials(self, meta: Meta) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies = cast(Any, cookies)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/upload.php',
            success_text='forums.php',
        )

    def get_type(self, meta: Meta) -> Optional[str]:
        if meta.get('anime'):
            return '407'

        category_map = {
            'TV': '405',
            'MOVIE': '404'
        }

        return category_map.get(meta['category'])

    async def generate_description(self, meta: Meta) -> str:
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        description_parts: list[str] = []

        # MediaInfo/BDInfo
        tech_info = ""
        if meta.get('is_disc') != 'BDMV':
            filelist = cast(list[str], meta.get('filelist', []))
            video_file = filelist[0] if filelist else ''
            mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(mi_template):
                try:
                    media_info = MediaInfo.parse(video_file, output="STRING", full=False, mediainfo_options={"inform": f"file://{mi_template}"})
                    tech_info = str(media_info)
                except Exception:
                    console.print("[bold red]Couldn't find the MediaInfo template[/bold red]")
                    mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                    if os.path.exists(mi_file_path):
                        async with aiofiles.open(mi_file_path, encoding='utf-8') as f:
                            tech_info = await f.read()
            else:
                console.print("[bold yellow]Using normal MediaInfo for the description.[/bold yellow]")
                mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                if os.path.exists(mi_file_path):
                    async with aiofiles.open(mi_file_path, encoding='utf-8') as f:
                        tech_info = await f.read()
        else:
            bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary_file):
                async with aiofiles.open(bd_summary_file, encoding='utf-8') as f:
                    tech_info = await f.read()

        if tech_info:
            description_parts.append(tech_info)

        if os.path.exists(base_desc_path):
            async with aiofiles.open(base_desc_path, encoding='utf-8') as f:
                manual_desc = await f.read()
            description_parts.append(manual_desc)

        # Screenshots
        images_value = meta.get(f'{self.tracker}_images_key', meta.get('image_list', []))
        images = cast(list[dict[str, Any]], images_value) if isinstance(images_value, list) else []
        if images:
            screenshots_block = "[center][b]Screenshots[/b]\n\n"
            for image in images:
                img_url = str(image.get('img_url', ''))
                web_url = str(image.get('web_url', ''))
                screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url] "
            screenshots_block += "[/center]"
            description_parts.append(screenshots_block)

        custom_description_header = str(self.config['DEFAULT'].get('custom_description_header', ''))
        if custom_description_header:
            description_parts.append(custom_description_header)

        description_parts.append(f"[right][url=https://github.com/Audionut/Upload-Assistant][size=1]{meta['ua_signature']}[/size][/url][/right]")

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

        async with aiofiles.open(final_desc_path, 'w', encoding='utf-8') as f:
            await f.write(desc)

        return desc

    async def search_existing(self, meta: Meta, _disctype: str) -> Optional[list[str]]:
        mandarin = self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=['mandarin', 'chinese'], check_audio=True, check_subtitle=True
        )

        if not mandarin:
            user_input_raw = cli_ui.ask_string("Warning: Mandarin subtitle or audio not found. Do you want to continue with the upload anyway?", default="n")
            if (user_input_raw or "").lower() not in ['y', 'yes']:
                console.print("Upload cancelled by user.", markup=False)
                meta['skipping'] = f"{self.tracker}"
                return

        search_url = f"{self.base_url}/torrents.php"
        params: dict[str, Any] = {
            'incldead': 1,
            'search': str(meta.get('imdb_info', {}).get('imdbID', '')),
            'search_area': 4
        }
        found_items: list[str] = []

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
            console.print(f"An error occurred while searching: {e}", markup=False)

        return found_items

    async def get_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'name': meta['name'],
            'url': str(meta.get('imdb_info', {}).get('imdb_url', '')),
            'descr': await self.generate_description(meta),
            'type': self.get_type(meta),
        }

        return data

    async def upload(self, meta: Meta, _disctype: str) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies = cast(Any, cookies)
        data = await self.get_data(meta)

        is_uploaded = await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='file',
            upload_cookies=self.session.cookies,
            upload_url=f"{self.base_url}/takeupload.php",
            id_pattern=r'download\.php\?id=([^&]+)',
            success_status_code="302, 303",
        )

        return is_uploaded
