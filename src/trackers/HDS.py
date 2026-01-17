# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import glob
import os
import platform
import re
from typing import Any, Optional, Union, cast

import aiofiles
import httpx
from bs4 import BeautifulSoup, Tag

from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.get_desc import DescriptionBuilder

Meta = dict[str, Any]
Config = dict[str, Any]


class HDS:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'HDS'
        self.source_flag = 'HD-Space'
        self.banned_groups = ['']
        self.base_url = 'https://hd-space.org'
        self.torrent_url = f'{self.base_url}/index.php?page=torrent-details&id='
        self.requests_url = f'{self.base_url}/index.php?page=viewrequests'
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Upload Assistant/2.3 ({platform.system()} {platform.release()})"
        }, timeout=30)

    async def validate_credentials(self, meta: Meta) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies.clear()
        if cookies is not None:
            self.session.cookies.update(cookies)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/index.php?page=upload',
            error_text='Recover password',
        )

    async def generate_description(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header())

        # Logo
        logo_resize_url = str(meta.get('tmdb_logo', ''))
        if logo_resize_url:
            desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

        # TV
        title, episode_image, episode_overview = await builder.get_tv_info(meta, resize=True)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')

            if episode_image:
                desc_parts.append(f"[center][img]{episode_image}[/img][/center]")

            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        mediainfo = await builder.get_mediainfo_section(meta)
        if mediainfo:
            desc_parts.append(f'[pre]{mediainfo}[/pre]')

        bdinfo = await builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f'[pre]{bdinfo}[/pre]')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Disc menus screenshots header
        menu_images_value = meta.get("menu_images", [])
        menu_images: list[dict[str, Any]] = []
        if isinstance(menu_images_value, list):
            menu_images_list = cast(list[Any], menu_images_value)
            menu_images.extend(
                [
                    cast(dict[str, Any], item)
                    for item in menu_images_list
                    if isinstance(item, dict)
                ]
            )
        if menu_images:
            desc_parts.append(await builder.menu_screenshot_header(meta))

            # Disc menus screenshots
            menu_screenshots_block = ""
            for image in menu_images:
                menu_web_url = str(image.get("web_url", ""))
                menu_img_url = str(image.get("img_url", ""))
                if menu_web_url and menu_img_url:
                    menu_screenshots_block += f"[url={menu_web_url}][img]{menu_img_url}[/img][/url]"
                    # HDS cannot resize images. If the image host does not provide small thumbnails(<400px), place only one image per line
                    if "imgbox" not in menu_web_url:
                        menu_screenshots_block += "\n"
            if menu_screenshots_block:
                desc_parts.append(f"[center]\n{menu_screenshots_block}\n[/center]")

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        # Screenshot Header
        images_value = meta.get("image_list", [])
        images: list[dict[str, Any]] = []
        if isinstance(images_value, list):
            images_list = cast(list[Any], images_value)
            images.extend(
                [
                    cast(dict[str, Any], item)
                    for item in images_list
                    if isinstance(item, dict)
                ]
            )
        if images:
            desc_parts.append(await builder.screenshot_header())

            # Screenshots
            if images:
                screenshots_block = ""
                for image in images:
                    web_url = str(image.get("web_url", ""))
                    img_url = str(image.get("img_url", ""))
                    if web_url and img_url:
                        screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url]"
                        # HDS cannot resize images. If the image host does not provide small thumbnails(<400px), place only one image per line
                        if "imgbox" not in web_url:
                            screenshots_block += "\n"
                if screenshots_block:
                    desc_parts.append(f"[center]\n{screenshots_block}\n[/center]")

        # Signature
        desc_parts.append(
            f"[center][url=https://github.com/Audionut/Upload-Assistant][size=2]{meta.get('ua_signature', '')}[/size][/url][/center]"
        )

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = description.replace('[user]', '').replace('[/user]', '')
        description = description.replace('[align=left]', '').replace('[/align]', '')
        description = description.replace('[right]', '').replace('[/right]', '')
        description = description.replace('[align=right]', '').replace('[/align]', '')
        description = bbcode.remove_sub(description)
        description = bbcode.remove_sup(description)
        description = description.replace('[alert]', '').replace('[/alert]', '')
        description = description.replace('[note]', '').replace('[/note]', '')
        description = description.replace('[hr]', '').replace('[/hr]', '')
        description = description.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
        description = description.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
        description = description.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
        description = description.replace('[ul]', '').replace('[/ul]', '')
        description = description.replace('[ol]', '').replace('[/ol]', '')
        description = bbcode.remove_hide(description)
        description = bbcode.remove_img_resize(description)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = bbcode.remove_spoiler(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def search_existing(self, meta: Meta, _disctype: str) -> list[dict[str, Union[str, None]]]:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies.clear()
        if cookies is not None:
            self.session.cookies.update(cookies)

        dupes: list[dict[str, Union[str, None]]] = []
        imdb_id = str(meta.get('imdb', ''))
        if imdb_id == '0':
            console.print(f'IMDb ID not found, cannot search for duplicates on {self.tracker}.')
            return dupes

        search_url = f'{self.base_url}/index.php?'

        params: dict[str, str] = {
            'page': 'torrents',
            'search': imdb_id,
            'active': '0',
            'options': '2'
        }

        try:
            response = await self.session.get(search_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            all_tables = soup.find_all('table', class_='lista')

            torrent_rows: list[Tag] = []

            for table in all_tables:
                recommend_header = table.find('td', attrs={'class': 'block'}, string=re.compile(r'Our Team Recommend'))  # type: ignore
                if recommend_header:
                    continue

                rows_in_table = table.select('tr:has(td.lista)')
                torrent_rows.extend(rows_in_table)

            for row in torrent_rows:
                name_tag = row.select_one('td:nth-child(2) > a[href*="page=torrent-details&id="]')
                name = name_tag.get_text(strip=True) if name_tag else 'Unknown Name'

                link_tag = name_tag
                torrent_link = None
                if link_tag and 'href' in link_tag.attrs:
                    torrent_link = f'{self.base_url}/{link_tag["href"]}'

                duplicate_entry = {
                    'name': name,
                    'size': None,
                    'link': torrent_link
                }
                dupes.append(duplicate_entry)

        except Exception as e:
            console.print(f'[bold red]Error searching for duplicates on {self.tracker}: {e}[/bold red]')

        return dupes

    async def get_category_id(self, meta: Meta) -> int:
        resolution = str(meta.get('resolution', ''))
        category = str(meta.get('category', ''))
        type_ = str(meta.get('type', ''))
        is_disc = str(meta.get('is_disc', ''))
        genres = str(meta.get('genres', '')).lower()
        keywords = str(meta.get('keywords', '')).lower()
        is_anime = bool(meta.get('anime'))

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

    async def get_requests(self, meta: Meta) -> Union[list[dict[str, Optional[str]]], bool]:
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False
        else:
            try:
                cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
                self.session.cookies.clear()
                if cookies is not None:
                    self.session.cookies.update(cookies)
                query = str(meta.get('title', ''))
                search_url = f'{self.base_url}/index.php?'

                params: dict[str, str] = {
                    'page': 'viewrequests',
                    'search': query,
                    'filter': 'true'
                }

                response = await self.session.get(search_url, params=params, cookies=self.session.cookies)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')
                request_rows = soup.select('form[action="index.php?page=takedelreq"] table.lista tr')

                results: list[dict[str, Optional[str]]] = []
                for row in request_rows:
                    if row.find('td', class_='header'):
                        continue

                    name_element = row.select_one('td.lista a b')
                    if not name_element:
                        continue

                    name = name_element.text.strip()
                    link_element = name_element.find_parent('a')
                    raw_link = link_element.get('href') if link_element else None
                    link = str(raw_link) if raw_link else None

                    results.append({
                        'Name': name,
                        'Link': link,
                    })

                if results:
                    message = f"\n{self.tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n"
                    for r in results:
                        message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Link:[/bold green] {self.base_url}/{r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                print(f'An error occurred while fetching requests: {e}')
                return []

    async def get_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'category': await self.get_category_id(meta),
            'filename': str(meta.get('name', '')),
            'genre': str(meta.get('genres', '')),
            'imdb': str(meta.get('imdb', '')),
            'info': await self.generate_description(meta),
            'nuk_rea': '',
            'nuk': 'false',
            'req': 'false',
            'submit': 'Send',
            't3d': 'true' if '3D' in str(meta.get('3d', '')) else 'false',
            'user_id': '',
            'youtube_video': str(meta.get('youtube', '')),
        }

        # Anon
        anon = not (int(meta.get('anon', 0) or 0) == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'true'
            })
        else:
            data.update({
                'anonymous': 'false'
            })

        return data

    async def get_nfo(self, meta: Meta) -> dict[str, tuple[str, bytes, str]]:
        nfo_dir = os.path.join(str(meta.get('base_dir', '')), "tmp", str(meta.get('uuid', '')))
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo_path = nfo_files[0]
            async with aiofiles.open(nfo_path, "rb") as nfo_file:
                nfo_bytes = await nfo_file.read()
            return {'nfo': (os.path.basename(nfo_path), nfo_bytes, "application/octet-stream")}
        return {}

    async def upload(self, meta: Meta, _disctype: str) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies.clear()
        if cookies is not None:
            self.session.cookies.update(cookies)
        data = await self.get_data(meta)
        files = await self.get_nfo(meta)

        is_uploaded = await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='torrent',
            upload_cookies=self.session.cookies,
            upload_url="https://hd-space.org/index.php?page=upload",
            hash_is_id=True,
            success_text="download.php?id=",
            additional_files=files,
        )

        return is_uploaded
