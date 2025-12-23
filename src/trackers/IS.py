# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import glob
import httpx
import os
import platform
import re
from bs4 import BeautifulSoup
from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.get_desc import DescriptionBuilder


class IS:
    def __init__(self, config):
        self.config = config
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

    async def validate_credentials(self, meta):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/upload.php',
            error_text='Forget your password',
        )

    async def generate_description(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # TV
        title, episode_image, episode_overview = await builder.get_tv_info(meta, self.tracker, resize=True)
        if episode_overview:
            desc_parts.append(f'Title: {title}')
            desc_parts.append(f'Overview: {episode_overview}')

        # File information
        mediainfo = await builder.get_mediainfo_section(meta, self.tracker)
        if mediainfo:
            desc_parts.append(f'{mediainfo}')

        bdinfo = await builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f'{bdinfo}')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Screenshots
        images = meta.get('image_list', [])
        if images:
            screenshots_block = ''
            for image in images:
                screenshots_block += f"{image['raw_url']}\n"
            desc_parts.append('Screenshots:\n' + screenshots_block)

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def search_existing(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        dupes = []

        if meta['category'] == "MOVIE":
            search_type = 't_genre'
            search_query = meta.get('imdb_info', {}).get('imdbID', '')

        elif meta['category'] == "TV":
            search_type = 't_name'
            search_query = meta.get('title') + f" {meta.get('season', '')}{meta.get('episode', '')}"

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
                torrent_link = name_tag.get('href')

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

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        genres = meta.get('genres', '').lower()
        keywords = meta.get('keywords', '').lower()
        is_anime = meta.get('anime')
        non_eng = False
        sd = meta.get('sd', False)
        if meta.get('original_language') != "en":
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
                if "xvid" in meta.get("video_encode", '').lower():
                    return tv_sd_xvid
                else:
                    return tv_sd_x264
            else:
                return tv_480p

    async def get_nfo(self, meta):
        nfo_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo_path = nfo_files[0]
            return {'nfofile': (os.path.basename(nfo_path), open(nfo_path, "rb"), "application/octet-stream")}
        else:
            nfo_content = await self.generate_description(meta)
            nfo_bytes = nfo_content.encode('utf-8')
            nfo_filename = f"{meta.get('scene_name', meta['uuid'])}.nfo"
            return {'nfofile': (nfo_filename, nfo_bytes, "application/octet-stream")}

    def get_name(self, meta):
        if meta.get('scene_name'):
            return meta.get('scene_name')
        else:
            is_name = meta.get('name').replace(meta['aka'], '').replace('Dubbed', '').replace('Dual-Audio', '')
            is_name = re.sub(r"\s{2,}", " ", is_name)
            is_name = is_name.replace(' ', '.')
        return is_name

    async def get_data(self, meta):
        data = {
            'UseNFOasDescr': 'no',
            'message': f"{meta.get('overview', '')}\n\n[youtube]{meta.get('youtube', '')}[/youtube]",
            'category': await self.get_category_id(meta),
            'subject': self.get_name(meta),
            'nothingtopost': "1",
            't_image_url': meta.get('poster'),
            'submit': 'Upload Torrent',
        }

        if meta['category'] == "MOVIE":
            data['t_link'] = meta['imdb_info']['imdb_url']

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'yes'
            })
        else:
            data.update({
                'anonymous': 'no'
            })

        return data

    async def upload(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        data = await self.get_data(meta)
        files = await self.get_nfo(meta)

        await self.cookie_auth_uploader.handle_upload(
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

        return
