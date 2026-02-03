# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import glob
import os
import platform
import re
from typing import Any, Union, cast

import aiofiles
import httpx
from bs4 import BeautifulSoup

from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.get_desc import DescriptionBuilder

Meta = dict[str, Any]
Config = dict[str, Any]


class IS:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'IS'
        self.source_flag = 'https://immortalseed.me'
        self.banned_groups = ['']
        self.base_url = 'https://immortalseed.me'
        self.torrent_url = 'https://immortalseed.me/details.php?hash='
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
            test_url=f'{self.base_url}/upload.php',
            error_text='Forget your password',
        )

    async def generate_description(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        desc_parts.append(builder.get_custom_header())

        # TV
        title, _, episode_overview = builder.get_tv_info(meta, resize=True)
        if episode_overview:
            desc_parts.append(f'Title: {title}')
            desc_parts.append(f'Overview: {episode_overview}')

        # File information
        mediainfo = builder.get_mediainfo_section(meta)
        if mediainfo:
            desc_parts.append(f'{mediainfo}')

        bdinfo = builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f'{bdinfo}')

        # User description
        desc_parts.append(builder.get_user_description(meta))

        # Screenshots
        images_value = meta.get('image_list', [])
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
            screenshots_block = ''
            for image in images:
                raw_url = str(image.get('raw_url', ''))
                if raw_url:
                    screenshots_block += f"{raw_url}\n"
            desc_parts.append('Screenshots:\n' + screenshots_block)

        # Tonemapped Header
        desc_parts.append(builder.get_tonemapped_header(meta))

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
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

        search_type = ''
        search_query = ''
        category = str(meta.get('category', ''))

        if category == "MOVIE":
            search_type = 't_genre'
            search_query = str(meta.get('imdb_info', {}).get('imdbID', ''))

        elif category == "TV":
            search_type = 't_name'
            search_query = f"{meta.get('title', '')} {meta.get('season', '')}{meta.get('episode', '')}"
        else:
            return dupes

        search_url = f'{self.base_url}/browse.php?do=search&keywords={search_query}&search_type={search_type}'

        try:
            response = await self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            torrent_table = soup.find('table', id='sortabletable')

            if not torrent_table:
                return dupes

            torrent_rows = torrent_table.select('tbody > tr')[1:]

            for row in torrent_rows:
                name_tag = row.select_one('a[href*="details.php?id="]')
                if not name_tag:
                    continue

                name = name_tag.get_text(strip=True)
                href_value = name_tag.get('href')
                torrent_link = href_value if isinstance(href_value, str) else ''

                size_tag = row.select_one('td:nth-of-type(5)')
                size = size_tag.get_text(strip=True) if size_tag else None

                duplicate_entry = {
                    'name': name,
                    'size': size,
                    'link': torrent_link
                }
                dupes.append(duplicate_entry)

        except Exception as e:
            console.print(f'[bold red]Error searching for duplicates on {self.tracker}: {e}[/bold red]')

        return dupes

    def get_category_id(self, meta: Meta) -> int:
        resolution = str(meta.get('resolution', ''))
        category = str(meta.get('category', ''))
        genres = str(meta.get('genres', '')).lower()
        keywords = str(meta.get('keywords', '')).lower()
        is_anime = bool(meta.get('anime'))
        non_eng = False
        sd = bool(meta.get('sd', False))
        if str(meta.get('original_language', '')) != "en":
            non_eng = True

        anime = 32
        childrens_cartoons = 31
        documentary_hd = 54
        documentary_sd = 53

        movies_4k = 59
        movies_4k_non_english = 60

        movies_hd = 16
        movies_hd_non_english = 18

        movies_low_def = 17
        movies_low_def_non_english = 34

        movies_sd = 14
        movies_sd_non_english = 33

        tv_480p = 47
        tv_4k = 64
        tv_hd = 8
        tv_sd_x264 = 48
        tv_sd_xvid = 9

        tv_season_packs_4k = 63
        tv_season_packs_hd = 4
        tv_season_packs_sd = 6

        if category == "MOVIE":
            if "documentary" in genres or "documentary" in keywords:
                if sd:
                    return documentary_sd
                else:
                    return documentary_hd
            elif is_anime:
                return anime
            elif resolution == "2160p":
                if non_eng:
                    return movies_4k_non_english
                else:
                    return movies_4k
            elif not sd:
                if non_eng:
                    return movies_hd_non_english
                else:
                    return movies_hd
            elif sd:
                if non_eng:
                    return movies_sd_non_english
                else:
                    return movies_sd
            else:
                if non_eng:
                    return movies_low_def_non_english
                else:
                    return movies_low_def

        elif category == "TV":
            if "documentary" in genres or "documentary" in keywords:
                if sd:
                    return documentary_sd
                else:
                    return documentary_hd
            elif is_anime:
                return anime
            elif "children" in genres or "cartoons" in genres or "children" in keywords or "cartoons" in keywords:
                return childrens_cartoons
            elif meta.get('tv_pack'):
                if resolution == "2160p":
                    return tv_season_packs_4k
                elif sd:
                    return tv_season_packs_sd
                else:
                    return tv_season_packs_hd
            elif resolution == "2160p":
                return tv_4k
            elif resolution in ["1080p", "1080i", "720p"]:
                return tv_hd
            elif sd:
                if "xvid" in str(meta.get("video_encode", '')).lower():
                    return tv_sd_xvid
                else:
                    return tv_sd_x264
            else:
                return tv_480p

        return 0

    async def get_nfo(self, meta: Meta) -> dict[str, tuple[str, bytes, str]]:
        nfo_dir = os.path.join(str(meta.get('base_dir', '')), "tmp", str(meta.get('uuid', '')))
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo_path = nfo_files[0]
            async with aiofiles.open(nfo_path, "rb") as nfo_file:
                nfo_bytes = await nfo_file.read()
            return {'nfofile': (os.path.basename(nfo_path), nfo_bytes, "application/octet-stream")}
        else:
            nfo_content = await self.generate_description(meta)
            nfo_bytes = nfo_content.encode('utf-8')
            nfo_filename = f"{meta.get('scene_name', meta['uuid'])}.nfo"
            return {'nfofile': (nfo_filename, nfo_bytes, "application/octet-stream")}

    def get_name(self, meta: Meta) -> str:
        scene_name = meta.get('scene_name')
        if scene_name:
            return str(scene_name)
        else:
            name_value = str(meta.get('name', ''))
            aka_value = str(meta.get('aka', ''))
            is_name = name_value.replace(aka_value, '').replace('Dubbed', '').replace('Dual-Audio', '')
            is_name = re.sub(r"\s{2,}", " ", is_name)
            is_name = is_name.replace(' ', '.')
        return is_name

    def get_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'UseNFOasDescr': 'no',
            'message': f"{meta.get('overview', '')}\n\n[youtube]{meta.get('youtube', '')}[/youtube]",
            'category': self.get_category_id(meta),
            'subject': self.get_name(meta),
            'nothingtopost': "1",
            't_image_url': meta.get('poster'),
            'submit': 'Upload Torrent',
        }

        if meta.get('category') == "MOVIE":
            data['t_link'] = str(meta.get('imdb_info', {}).get('imdb_url', ''))

        # Anon
        anon = not (int(meta.get('anon', 0) or 0) == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'yes'
            })
        else:
            data.update({
                'anonymous': 'no'
            })

        return data

    async def upload(self, meta: Meta, _disctype: str, _torrent_bytes: Any = None) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies.clear()
        if cookies is not None:
            self.session.cookies.update(cookies)
        data = self.get_data(meta)
        files = await self.get_nfo(meta)

        is_uploaded = await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            hash_is_id=True,
            torrent_field_name='torrentfile',
            torrent_name=f"{meta.get('clean_name', 'placeholder')}",
            upload_cookies=self.session.cookies,
            upload_url="https://immortalseed.me/upload.php",
            additional_files=files,
            success_text="Thank you",
        )

        return is_uploaded
