# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import glob
import httpx
import os
import platform
from bs4 import BeautifulSoup
from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.get_desc import DescriptionBuilder


class HDS:
    def __init__(self, config):
        self.config = config
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

    async def validate_credentials(self, meta):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/index.php?page=upload',
            error_text='Recover password',
        )

    async def generate_description(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # Logo
        logo_resize_url = meta.get('tmdb_logo', '')
        if logo_resize_url:
            desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

        # TV
        title, episode_image, episode_overview = await builder.get_tv_info(meta, self.tracker, resize=True)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')

            if episode_image:
                desc_parts.append(f"[center][img]{episode_image}[/img][/center]")

            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        mediainfo = await builder.get_mediainfo_section(meta, self.tracker)
        if mediainfo:
            desc_parts.append(f'[pre]{mediainfo}[/pre]')

        bdinfo = await builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f'[pre]{bdinfo}[/pre]')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Disc menus screenshots header
        menu_images = meta.get("menu_images", [])
        if menu_images:
            desc_parts.append(await builder.menu_screenshot_header(meta, self.tracker))

            # Disc menus screenshots
            menu_screenshots_block = ""
            for image in menu_images:
                menu_web_url = image.get("web_url")
                menu_img_url = image.get("img_url")
                if menu_web_url and menu_img_url:
                    menu_screenshots_block += f"[url={menu_web_url}][img]{menu_img_url}[/img][/url]"
                    # HDS cannot resize images. If the image host does not provide small thumbnails(<400px), place only one image per line
                    if "imgbox" not in menu_web_url:
                        menu_screenshots_block += "\n"
            if menu_screenshots_block:
                desc_parts.append(f"[center]\n{menu_screenshots_block}\n[/center]")

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        # Screenshot Header
        images = meta.get("image_list", [])
        if images:
            desc_parts.append(await builder.screenshot_header(self.tracker))

            # Screenshots
            if images:
                screenshots_block = ""
                for image in images:
                    web_url = image.get("web_url")
                    img_url = image.get("img_url")
                    if web_url and img_url:
                        screenshots_block += f"[url={web_url}][img]{img_url}[/img][/url]"
                        # HDS cannot resize images. If the image host does not provide small thumbnails(<400px), place only one image per line
                        if "imgbox" not in web_url:
                            screenshots_block += "\n"
                if screenshots_block:
                    desc_parts.append(f"[center]\n{screenshots_block}\n[/center]")

        # Signature
        desc_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant][size=2]{meta['ua_signature']}[/size][/url][/center]")

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

    async def search_existing(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)

        dupes = []
        imdb_id = meta.get('imdb', '')
        if imdb_id == '0':
            console.print(f'IMDb ID not found, cannot search for duplicates on {self.tracker}.')
            return dupes

        search_url = f'{self.base_url}/index.php?'

        params = {
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

            torrent_rows = []

            for table in all_tables:
                recommend_header = table.find('td', class_='block', string='Our Team Recommend')
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

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        type_ = meta.get('type')
        is_disc = meta.get('is_disc')
        genres = meta.get('genres', '').lower()
        keywords = meta.get('keywords', '').lower()
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

    async def get_requests(self, meta):
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False
        else:
            try:
                self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
                query = meta['title']
                search_url = f'{self.base_url}/index.php?'

                params = {
                    'page': 'viewrequests',
                    'search': query,
                    'filter': 'true'
                }

                response = await self.session.get(search_url, params=params, cookies=self.session.cookies)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')
                request_rows = soup.select('form[action="index.php?page=takedelreq"] table.lista tr')

                results = []
                for row in request_rows:
                    if row.find('td', class_='header'):
                        continue

                    name_element = row.select_one('td.lista a b')
                    if not name_element:
                        continue

                    name = name_element.text.strip()
                    link_element = name_element.find_parent('a')
                    link = link_element['href'] if link_element else None

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

    async def get_data(self, meta):
        data = {
            'category': await self.get_category_id(meta),
            'filename': meta['name'],
            'genre': meta.get('genres', ''),
            'imdb': meta.get('imdb', ''),
            'info': await self.generate_description(meta),
            'nuk_rea': '',
            'nuk': 'false',
            'req': 'false',
            'submit': 'Send',
            't3d': 'true' if '3D' in meta.get('3d', '') else 'false',
            'user_id': '',
            'youtube_video': meta.get('youtube', ''),
        }

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'true'
            })
        else:
            data.update({
                'anonymous': 'false'
            })

        return data

    async def get_nfo(self, meta):
        nfo_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo_path = nfo_files[0]
            return {'nfo': (os.path.basename(nfo_path), open(nfo_path, "rb"), "application/octet-stream")}
        return {}

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
            torrent_field_name='torrent',
            upload_cookies=self.session.cookies,
            upload_url="https://hd-space.org/index.php?page=upload",
            hash_is_id=True,
            success_text="download.php?id=",
            additional_files=files,
        )

        return
