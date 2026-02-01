# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import os
import platform
import re
from typing import Any, Optional, cast

import aiofiles
import httpx

from cogs.redaction import Redaction
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class TL:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'TL'
        self.source_flag = 'TorrentLeech.org'
        self.base_url = 'https://www.torrentleech.org'
        self.http_upload_url = f'{self.base_url}/torrents/upload/'
        self.api_upload_url = f'{self.base_url}/torrents/upload/apiupload'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.banned_groups = []
        self.session = httpx.AsyncClient(timeout=60.0)
        self.tracker_config: dict[str, Any] = self.config['TRACKERS'][self.tracker]
        self.api_upload: bool = bool(self.tracker_config.get('api_upload', False))
        self.passkey: str = str(self.tracker_config.get('passkey', ''))
        self.announce_list = [
            f'https://tracker.torrentleech.org/a/{self.passkey}/announce',
            f'https://tracker.tleechreload.org/a/{self.passkey}/announce'
        ]
        self.session.headers.update({
            'User-Agent': f'Upload Assistant ({platform.system()} {platform.release()})'
        })

    async def login(self, meta: Meta, force: bool = False) -> bool:
        if self.api_upload and not force:
            return True

        cookies_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/TL.txt")

        cookie_path = os.path.abspath(cookies_file)
        if not os.path.exists(cookie_path):
            console.print(f"[bold red]'{self.tracker}' Cookies not found at: {cookie_path}[/bold red]")
            return False

        self.session.cookies.update(await self.common.parseCookieFile(cookies_file))

        try:
            if force:
                response = await self.session.get('https://www.torrentleech.org/torrents/browse/index', timeout=10)
                if response.status_code == 301 and 'torrents/browse' in str(response.url):
                    if meta.get('debug'):
                        console.print(f"[bold green]Logged in to '{self.tracker}' with cookies.[/bold green]")
                    return True
            elif not force:
                response = await self.session.get(self.http_upload_url, timeout=10)
                if response.status_code == 200 and 'torrents/upload' in str(response.url):
                    if meta.get('debug'):
                        console.print(f"[bold green]Logged in to '{self.tracker}' with cookies.[/bold green]")
                    return True
            else:
                console.print(f"[bold red]Login to '{self.tracker}' with cookies failed. Please check your cookies.[/bold red]")
                return False

        except httpx.RequestError as e:
            console.print(f"[bold red]Error while validating credentials for '{self.tracker}': {e}[/bold red]")
            return False

        return False

    async def generate_description(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []
        process_screenshot = not self.tracker_config.get("img_rehost", True) or self.tracker_config.get("api_upload", True)

        # Custom Header
        desc_parts.append(builder.get_custom_header())

        # Logo
        logo, logo_size = builder.get_logo_section(meta)
        if logo and logo_size:
            desc_parts.append(f"""<center><img src="{logo}" style="max-width: {logo_size}px;"></center>""")

        # TV
        title, episode_image, episode_overview = builder.get_tv_info(meta)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')

            if episode_image:
                desc_parts.append(f"[center]<img src='{episode_image}' style='max-width: 350px;'></a>[/center]")

            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        desc_parts.append(await builder.get_mediainfo_section(meta))
        desc_parts.append(builder.get_bdinfo_section(meta))

        # NFO
        if meta.get('description_nfo_content', ''):
            desc_parts.append(f"<div style='display: flex; justify-content: center;'><div style='background-color: #000000; color: #ffffff;'>{meta.get('description_nfo_content')}</div></div>")

        # User description
        desc_parts.append(builder.get_user_description(meta))

        # Menus Screenshots
        if process_screenshot:
            # Disc menus screenshots header
            menu_images = cast(list[dict[str, Any]], meta.get("menu_images", []))
            if menu_images:
                desc_parts.append(builder.menu_screenshot_header(meta))

                # Disc menus screenshots
                menu_screenshots_block = ""
                for i, image in enumerate(menu_images):
                    menu_img_url = image.get("img_url")
                    menu_web_url = image.get("web_url")
                    if menu_img_url and menu_web_url:
                        menu_screenshots_block += f"""<a href="{menu_web_url}"><img src="{menu_img_url}" style="max-width: 350px;"></a>  """
                    if (i + 1) % 2 == 0:
                        menu_screenshots_block += "<br><br>"
                if menu_screenshots_block:
                    desc_parts.append("<center>" + menu_screenshots_block + "</center>")

        # Tonemapped Header
        desc_parts.append(builder.get_tonemapped_header(meta))

        # Screenshots Section
        if process_screenshot:
            images = cast(list[dict[str, Any]], meta.get("image_list", []))
            if images:
                # Screenshot Header
                desc_parts.append(builder.screenshot_header())
                # Screenshots
                screenshots_block = ""
                for i, image in enumerate(images):
                    img_url = image.get("img_url")
                    web_url = image.get("web_url")
                    if img_url and web_url:
                        screenshots_block += (
                            f"""<a href="{web_url}"><img src="{img_url}" style="max-width: 350px;"></a>  """
                        )
                    if (i + 1) % 2 == 0:
                        screenshots_block += "<br><br>"
                if screenshots_block:
                    desc_parts.append("<center>" + screenshots_block + "</center>")

        # Signature
        desc_parts.append(
            f"""<div style="text-align: right; font-size: 11px;"><a href="https://github.com/Audionut/Upload-Assistant">{meta.get('ua_signature', '')}</a></div>"""
        )

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = description.replace("[center]", "<center>").replace("[/center]", "</center>")
        description = re.sub(r'\[\*\]', '\n[*]', description, flags=re.IGNORECASE)
        description = re.sub(r'\[c\](.*?)\[/c\]', r'[code]\1[/code]', description, flags=re.IGNORECASE | re.DOTALL)
        description = re.sub(r'\[hr\]', '---', description, flags=re.IGNORECASE)
        description = re.sub(r'\[img=[\d"x]+\]', '[img]', description, flags=re.IGNORECASE)
        description = description.replace('[*] ', '• ').replace('[*]', '• ')
        description = bbcode.remove_list(description)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = bbcode.remove_spoiler(description)
        description = re.sub(r'\n{3,}', '\n\n', description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    def get_category(self, meta: Meta) -> int:
        categories = {
            'Anime': 34,
            'Movie4K': 47,
            'MovieBluray': 13,
            'MovieBlurayRip': 14,
            'MovieCam': 8,
            'MovieTS': 9,
            'MovieDocumentary': 29,
            'MovieDvd': 12,
            'MovieDvdRip': 11,
            'MovieForeign': 36,
            'MovieHdRip': 43,
            'MovieWebrip': 37,
            'TvBoxsets': 27,
            'TvEpisodes': 26,
            'TvEpisodesHd': 32,
            'TvForeign': 44
        }

        if meta.get('anime', 0):
            return categories['Anime']

        category = str(meta.get('category', ''))
        if category == 'MOVIE':
            if str(meta.get('original_language', '')) != 'en':
                return categories['MovieForeign']
            elif 'Documentary' in str(meta.get('genres', '')):
                return categories['MovieDocumentary']
            elif str(meta.get('resolution', '')) == '2160p':
                return categories['Movie4K']
            elif str(meta.get('is_disc', '')) in ('BDMV', 'HDDVD') or (
                str(meta.get('type', '')) == 'REMUX' and str(meta.get('source', '')) in ('BluRay', 'HDDVD')
            ):
                return categories['MovieBluray']
            elif str(meta.get('type', '')) == 'ENCODE' and str(meta.get('source', '')) in ('BluRay', 'HDDVD'):
                return categories['MovieBlurayRip']
            elif str(meta.get('is_disc', '')) == 'DVD' or (
                str(meta.get('type', '')) == 'REMUX' and 'DVD' in str(meta.get('source', ''))
            ):
                return categories['MovieDvd']
            elif (str(meta.get('type', '')) == 'ENCODE' and 'DVD' in str(meta.get('source', ''))) or str(meta.get('type', '')) == 'DVDRIP':
                return categories['MovieDvdRip']
            elif 'WEB' in str(meta.get('type', '')):
                return categories['MovieWebrip']
            elif str(meta.get('type', '')) == 'HDTV':
                return categories['MovieHdRip']
        elif category == 'TV':
            if str(meta.get('original_language', '')) != 'en':
                return categories['TvForeign']
            elif meta.get('tv_pack', 0):
                return categories['TvBoxsets']
            elif meta.get('sd'):
                return categories['TvEpisodes']
            else:
                return categories['TvEpisodesHd']

        raise NotImplementedError('Failed to determine TL category!')

    def get_screens(self, meta: Meta) -> list[str]:
        images = cast(list[dict[str, Any]], meta.get('menu_images', [])) + cast(
            list[dict[str, Any]], meta.get('image_list', [])
        )
        return [image['raw_url'] for image in images if image.get('raw_url')]

    def get_name(self, meta: Meta) -> str:
        is_scene = bool(meta.get('scene_name'))
        name = str(meta.get('scene_name', '')) if is_scene else str(meta.get('name', '')).replace(str(meta.get('aka', '')), '')

        return name

    async def search_existing(self, meta: Meta, _disctype: str) -> list[dict[str, Any]]:
        login = await self.login(meta, force=True)
        if not login:
            meta['skipping'] = "TL"
            if meta.get('debug'):
                console.print(f"[bold red]Skipping upload to '{self.tracker}' as login failed.[/bold red]")
            return []
        cat_id = self.get_category(meta)

        results: list[dict[str, Any]] = []

        search_name = str(meta.get("title", ""))
        resolution = str(meta.get("resolution", ""))
        year = str(meta.get('year', ''))
        episode = str(meta.get('episode', ''))
        season = str(meta.get('season', ''))
        season_episode = f"{season}{episode}" if season or episode else ''

        forbidden_keywords: list[str] = []

        is_disc = str(meta.get("is_disc", "") or "").strip().lower()
        _type = str(meta.get("type", "") or "").strip().lower()

        if is_disc == 'bdmv':
            forbidden_keywords.extend(['remux', 'x264', 'x265'])

        if _type == 'webdl':
            forbidden_keywords.extend(['webrip', 'bluray', 'blu-ray'])

        search_urls: list[str] = []

        if meta['category'] == 'TV':
            if meta.get('tv_pack', False):
                param = f"{cat_id}/query/{search_name} {season} {resolution}"
                search_urls.append(f"{self.base_url}/torrents/browse/list/categories/{param}")
            else:
                episode_param = f"{cat_id}/query/{search_name} {season_episode} {resolution}"
                search_urls.append(f"{self.base_url}/torrents/browse/list/categories/{episode_param}")

                # Also check for season packs
                pack_cat_id = 44 if cat_id == 44 else 27  # Foreign TV shows do not have a separate cat_id for season/episodes
                pack_param = f"{pack_cat_id}/query/{search_name} {season} {resolution}"
                search_urls.append(f"{self.base_url}/torrents/browse/list/categories/{pack_param}")

        elif meta['category'] == 'MOVIE':
            param = f"{cat_id}/query/{search_name} {year} {resolution}"
            search_urls.append(f"{self.base_url}/torrents/browse/list/categories/{param}")

        for url in search_urls:
            results.extend(await self._search_url(url, forbidden_keywords))

        return results

    async def _search_url(self, url: str, forbidden_keywords: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            response = await self.session.get(url, timeout=20)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            torrents = cast(list[dict[str, Any]], data.get("torrentList", []))

            for torrent in torrents:
                name = str(torrent.get('name', ''))
                link = f"{self.torrent_url}{torrent.get('fid')}"
                size = torrent.get('size')
                if not any(keyword in name.lower() for keyword in forbidden_keywords):
                    results.append({
                        'name': name,
                        'size': size,
                        'link': link
                    })

        except Exception as e:
            console.print(f"[bold red]Error searching for duplicates on {self.tracker} ({url}): {e}[/bold red]")

        return results

    async def get_anilist_id(self, meta: Meta) -> Optional[int]:
        url = 'https://graphql.anilist.co'
        query = '''
        query ($idMal: Int) {
        Media(idMal: $idMal, type: ANIME) {
            id
        }
        }
        '''
        variables = {'idMal': meta.get('mal_id')}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={'query': query, 'variables': variables})
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())

            media = cast(dict[str, Any], data.get('data', {})).get('Media')
            return media['id'] if media else None

    async def upload(self, meta: Meta, _disctype: str) -> Optional[bool]:
        await self.common.create_torrent_for_upload(meta, self.tracker, self.source_flag)

        if self.api_upload:
            is_uploaded = await self.upload_api(meta)
            return is_uploaded
        else:
            is_uploaded = await self.cookie_upload(meta)
            return is_uploaded

    async def upload_api(self, meta: Meta) -> bool:
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        async with aiofiles.open(torrent_path, 'rb') as open_torrent:
            torrent_bytes = await open_torrent.read()
        files: dict[str, tuple[Any, Any, str]] = {
            'torrent': (self.get_name(meta) + '.torrent', torrent_bytes, 'application/x-bittorrent')
        }

        data: dict[str, Any] = {
            'announcekey': self.passkey,
            'category': self.get_category(meta),
            'description': await self.generate_description(meta),
            'name': self.get_name(meta),
            'nonscene': 'on' if not meta.get('scene') else 'off',
        }

        if meta.get('anime', False):
            anilist_id = await self.get_anilist_id(meta)
            if anilist_id:
                data.update({'animeid': f"https://anilist.co/anime/{anilist_id}"})

        else:
            if meta.get('category') == 'MOVIE':
                imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
                data.update({'imdb': imdb_info.get('imdbID', '')})

            if meta.get('category') == 'TV':
                data.update({
                    'tvmazeid': meta.get('tvmaze_id', ''),
                    'tvmazetype': meta.get('tv_pack', ''),
                })

        anon = not (meta.get('anon') == 0 and not self.tracker_config.get('anon', False))
        if anon:
            data.update({'is_anonymous_upload': 'on'})

        if not meta.get('debug'):
            response = await self.session.post(
                url=self.api_upload_url,
                files=files,
                data=data
            )

            if not response.text.isnumeric():
                tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                tracker_status.setdefault(self.tracker, {})
                tracker_status[self.tracker]['status_message'] = 'data error: ' + response.text

            if response.text.isnumeric():
                torrent_id = str(response.text)
                tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                tracker_status.setdefault(self.tracker, {})
                tracker_status[self.tracker]['status_message'] = 'Torrent uploaded successfully.'
                tracker_status[self.tracker]['torrent_id'] = torrent_id
                await self.common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag, self.announce_list, self.torrent_url + torrent_id)
                return True

        else:
            console.print("[cyan]TL Request Data:")
            console.print(Redaction.redact_private_info(data))
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success
        return False

    def get_cookie_upload_data(self, meta: Meta) -> dict[str, Any]:
        tvMazeURL = ''
        if meta.get('category') == 'TV' and meta.get("tvmaze_id"):
            tvMazeURL = f"https://www.tvmaze.com/shows/{meta.get('tvmaze_id')}"

        data: dict[str, Any] = {
            'name': self.get_name(meta),
            'category': self.get_category(meta),
            'nonscene': 'on' if not meta.get("scene") else 'off',
            'imdbURL': str(cast(dict[str, Any], meta.get('imdb_info', {})).get('imdb_url', '')),
            'tvMazeURL': tvMazeURL,
            'igdbURL': '',
            'torrentNFO': '0',
            'torrentDesc': '1',
            'nfotextbox': '',
            'torrentComment': '0',
            'uploaderComments': '',
            'is_anonymous_upload': 'off',
            'screenshots[]': self.get_screens(meta) if self.tracker_config.get('img_rehost', True) else '',
        }

        anon = not (meta.get('anon') == 0 and not self.tracker_config.get('anon', False))
        if anon:
            data.update({'is_anonymous_upload': 'on'})

        return data

    async def cookie_upload(self, meta: Meta) -> Optional[bool]:
        await self.generate_description(meta)
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", encoding='utf-8') as f:
            description_content = await f.read()
        login = await self.login(meta)
        if not login:
            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
            tracker_status.setdefault(self.tracker, {})
            tracker_status[self.tracker]['status_message'] = "data error: Login with cookies failed."
            return None

        data = self.get_cookie_upload_data(meta)

        if meta.get('debug'):
            console.print("[cyan]TL Request Data:")
            console.print(Redaction.redact_private_info(data))
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success
        else:
            try:
                async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb') as f:
                    torrent_bytes = await f.read()
                files = {
                    'torrent': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent'),
                    'nfo': ('description.txt', description_content, 'text/plain'),
                }

                response = await self.session.post(url=self.http_upload_url, files=files, data=data)

                if response.status_code == 302 and 'location' in response.headers:
                    torrent_id = response.headers['location'].replace('/successfulupload?torrentID=', '')
                    torrent_url = f"{self.base_url}/torrent/{torrent_id}"
                    meta['tracker_status'][self.tracker]['status_message'] = 'Torrent uploaded successfully.'
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                    await self.common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag, self.announce_list, torrent_url)
                    return True

                else:
                    meta['tracker_status'][self.tracker]['status_message'] = 'data error - Upload failed: No success redirect found.'
                    failure_path = await self.common.save_html_file(meta, self.tracker, response.text, "Failed_Upload")
                    console.print(f"{self.tracker}: Failed upload. The HTML response saved to {failure_path}")
                    return False

            except httpx.RequestError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error - {str(e)}'
                return False
