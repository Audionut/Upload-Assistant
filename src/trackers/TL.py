# -*- coding: utf-8 -*-
# import discord
import httpx
import os
import re
import platform
from src.trackers.COMMON import COMMON
from src.console import console


class TL:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'TL'
        self.source_flag = 'TorrentLeech.org'
        self.base_url = 'https://www.torrentleech.org'
        self.http_upload_url = f'{self.base_url}/torrents/upload/'
        self.api_upload_url = f'{self.base_url}/torrents/upload/apiupload'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.signature = """<center><a href="https://github.com/Audionut/Upload-Assistant">Created by Upload Assistant</a></center>"""
        self.banned_groups = [""]
        self.session = httpx.AsyncClient(timeout=60.0)
        self.tracker_config = self.config['TRACKERS'][self.tracker]
        self.api_upload = self.tracker_config.get('api_upload', False)
        self.passkey = self.tracker_config.get('passkey')
        self.announce_list = [
            f'https://tracker.torrentleech.org/a/{self.passkey}/announce',
            f'https://tracker.tleechreload.org/a/{self.passkey}/announce'
        ]
        self.session.headers.update({
            'User-Agent': f'Upload Assistant/2.3 ({platform.system()} {platform.release()})'
        })

    async def login(self, meta, force=False):
        if self.api_upload and not force:
            return True

        self.cookies_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/TL.txt")

        cookie_path = os.path.abspath(self.cookies_file)
        if not os.path.exists(cookie_path):
            console.print(f"[bold red]'{self.tracker}' Cookies not found at: {cookie_path}[/bold red]")
            return False

        self.session.cookies.update(await self.common.parseCookieFile(self.cookies_file))

        try:
            if force:
                response = await self.session.get('https://www.torrentleech.org/torrents/browse/index', timeout=10)
                if response.status_code == 301 and 'torrents/browse' in str(response.url):
                    if meta['debug']:
                        console.print(f"[bold green]Logged in to '{self.tracker}' with cookies.[/bold green]")
                    return True
            elif not force:
                response = await self.session.get(self.http_upload_url, timeout=10)
                if response.status_code == 200 and 'torrents/upload' in str(response.url):
                    if meta['debug']:
                        console.print(f"[bold green]Logged in to '{self.tracker}' with cookies.[/bold green]")
                    return True
            else:
                console.print(f"[bold red]Login to '{self.tracker}' with cookies failed. Please check your cookies.[/bold red]")
                return False

        except httpx.RequestError as e:
            console.print(f"[bold red]Error while validating credentials for '{self.tracker}': {e}[/bold red]")
            return False

    async def generate_description(self, meta):
        description_parts = []

        file_info = ''
        file_info = await self.common.mediainfo_template(self.tracker, meta)

        if meta.get('is_disc') == 'BDMV':
            discs = meta['discs']
            if isinstance(discs, list):
                file_info = discs[0].get('summary', '') if discs else ''

        if file_info:
            description_parts.append(file_info)

        meta['mediainfo_or_bdinfo'] = file_info
        meta['img_rehost'] = self.tracker_config.get('img_rehost', True)

        template_name = self.tracker_config.get('description_template', 'TL_default.txt.j2') or 'TL_default.txt.j2'
        description = await self.common.description_template(self.tracker, meta, template_name)

        from src.bbcode import BBCODE
        bbcode = BBCODE()
        description = description.replace("[center]", "<center>").replace("[/center]", "</center>")
        description = re.sub(r'\[\*\]', '\n[*]', description, flags=re.IGNORECASE)
        description = re.sub(r'\[list=.*?\]', '[list]', description, flags=re.IGNORECASE)
        description = re.sub(r'\[c\](.*?)\[/c\]', r'[code]\1[/code]', description, flags=re.IGNORECASE | re.DOTALL)
        description = re.sub(r'\[hr\]', '---', description, flags=re.IGNORECASE)
        description = re.sub(r'\[img=[\d"x]+\]', '[img]', description, flags=re.IGNORECASE)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = bbcode.remove_spoiler(description)
        description = re.sub(r'\n{3,}', '\n\n', description)

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as f:
            f.write(description)

        return description

    def get_cat_id(self, meta):
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

        if meta['category'] == 'MOVIE':
            if meta['original_language'] != 'en':
                return categories['MovieForeign']
            elif 'Documentary' in meta['genres']:
                return categories['MovieDocumentary']
            elif meta['resolution'] == '2160p':
                return categories['Movie4K']
            elif meta['is_disc'] in ('BDMV', 'HDDVD') or (meta['type'] == 'REMUX' and meta['source'] in ('BluRay', 'HDDVD')):
                return categories['MovieBluray']
            elif meta['type'] == 'ENCODE' and meta['source'] in ('BluRay', 'HDDVD'):
                return categories['MovieBlurayRip']
            elif meta['is_disc'] == 'DVD' or (meta['type'] == 'REMUX' and 'DVD' in meta['source']):
                return categories['MovieDvd']
            elif meta['type'] == 'ENCODE' and 'DVD' in meta['source']:
                return categories['MovieDvdRip']
            elif 'WEB' in meta['type']:
                return categories['MovieWebrip']
            elif meta['type'] == 'HDTV':
                return categories['MovieHdRip']
        elif meta['category'] == 'TV':
            if meta['original_language'] != 'en':
                return categories['TvForeign']
            elif meta.get('tv_pack', 0):
                return categories['TvBoxsets']
            elif meta['sd']:
                return categories['TvEpisodes']
            else:
                return categories['TvEpisodesHd']

        raise NotImplementedError('Failed to determine TL category!')

    def get_screens(self, meta):
        screenshot_urls = [
            image.get('raw_url')
            for image in meta.get('image_list', [])
            if image.get('raw_url')
        ]

        return screenshot_urls

    def get_name(self, meta):
        is_scene = bool(meta.get('scene_name'))
        if is_scene:
            name = meta['scene_name']
        else:
            name = meta['name'].replace(meta['aka'], '')

        return name

    async def search_existing(self, meta, disctype):
        login = await self.login(meta, force=True)
        if not login:
            meta['skipping'] = "TL"
            if meta['debug']:
                console.print(f"[bold red]Skipping upload to '{self.tracker}' as login failed.[/bold red]")
            return
        cat_id = self.get_cat_id(meta)

        dupes = []

        search_name = meta["title"]
        resolution = meta["resolution"]
        year = meta['year']
        episode = meta.get('episode', '')
        season = meta.get('season', '')
        season_episode = f"{season}{episode}" if season or episode else ''

        search_urls = []

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
            try:
                response = await self.session.get(url, timeout=20)
                response.raise_for_status()

                data = response.json()
                torrents = data.get("torrentList", [])

                for torrent in torrents:
                    name = torrent.get("name")
                    size = torrent.get("size")
                    if name or size:
                        dupes.append({'name': name, 'size': size})

            except Exception as e:
                console.print(f"[bold red]Error searching for duplicates on {self.tracker} ({url}): {e}[/bold red]")

        return dupes

    async def get_anilist_id(self, meta):
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
            data = response.json()

            media = data.get('data', {}).get('Media')
            return media['id'] if media else None

    async def upload(self, meta, disctype):
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)

        if self.api_upload:
            await self.upload_api(meta)
        else:
            await self.upload_http(meta)

    async def upload_api(self, meta):
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        with open(torrent_path, 'rb') as open_torrent:
            files = {
                'torrent': (self.get_name(meta) + '.torrent', open_torrent, 'application/x-bittorrent')
            }

            data = {
                'announcekey': self.passkey,
                'category': self.get_cat_id(meta),
                'description': await self.generate_description(meta),
                'name': self.get_name(meta),
                'nonscene': 'on' if not meta.get('scene') else 'off',
            }

            if meta.get('anime', False):
                anilist_id = await self.get_anilist_id(meta)
                if anilist_id:
                    data.update({'animeid': f"https://anilist.co/anime/{anilist_id}"})

            else:
                if meta['category'] == 'MOVIE':
                    data.update({'imdb': meta.get('imdb_info', {}).get('imdbID', '')})

                if meta['category'] == 'TV':
                    data.update({
                        'tvmazeid': meta.get('tvmaze_id'),
                        'tvmazetype': meta.get('tv_pack'),
                    })

            anon = not (meta['anon'] == 0 and not self.tracker_config.get('anon', False))
            if anon:
                data.update({'is_anonymous_upload': 'on'})

            if meta['debug'] is False:
                response = await self.session.post(
                    url=self.api_upload_url,
                    files=files,
                    data=data
                )

                if not response.text.isnumeric():
                    meta['tracker_status'][self.tracker]['status_message'] = 'data error: ' + response.text

                if response.text.isnumeric():
                    torrent_id = str(response.text)
                    meta['tracker_status'][self.tracker]['status_message'] = 'Torrent uploaded successfully.'
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce_list, self.torrent_url + torrent_id)

            else:
                console.print(data)

    async def upload_http(self, meta):
        login = await self.login(meta)
        if not login:
            meta['tracker_status'][self.tracker]['status_message'] = "data error: Login with cookies failed."
            return

        await self.generate_description(meta)

        imdbURL = ''
        if meta.get('category') == 'MOVIE' and meta.get('imdb_info', {}).get('imdbID', ''):
            imdbURL = f"https://www.imdb.com/title/{meta.get('imdb_info', {}).get('imdbID', '')}"

        tvMazeURL = ''
        if meta.get('category') == 'TV' and meta.get("tvmaze_id"):
            tvMazeURL = f"https://www.tvmaze.com/shows/{meta.get('tvmaze_id')}"

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        torrent_file = f"[{self.tracker}].torrent"
        description_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        with open(torrent_path, 'rb') as torrent_fh, open(description_path, 'rb') as nfo:

            files = {
                'torrent': (torrent_file, torrent_fh, 'application/x-bittorrent'),
                'nfo': (f"[{self.tracker}]DESCRIPTION.txt", nfo, 'text/plain')
            }

            data = {
                'name': self.get_name(meta),
                'category': self.get_cat_id(meta),
                'nonscene': 'on' if not meta.get("scene") else 'off',
                'imdbURL': imdbURL,
                'tvMazeURL': tvMazeURL,
                'igdbURL': '',
                'torrentNFO': '0',
                'torrentDesc': '1',
                'nfotextbox': '',
                'torrentComment': '0',
                'uploaderComments': '',
                'is_anonymous_upload': 'off',
                'screenshots[]': '' if meta.get('anon', False) else self.get_screens(meta),  # It is not possible to upload screenshots anonymously
            }

            anon = not (meta['anon'] == 0 and not self.tracker_config.get('anon', False))
            if anon:
                data.update({'is_anonymous_upload': 'on'})

            if meta['debug'] is False:
                try:
                    response = await self.session.post(
                        url=self.http_upload_url,
                        files=files,
                        data=data
                    )

                    if response.status_code == 302 and 'location' in response.headers:
                        torrent_id = response.headers['location'].replace('/successfulupload?torrentID=', '')
                        torrent_url = f"{self.base_url}/torrent/{torrent_id}"
                        meta['tracker_status'][self.tracker]['status_message'] = torrent_url
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                    else:
                        meta['tracker_status'][self.tracker]['status_message'] = 'data error - Upload failed: No success redirect found.'
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                        with open(failure_path, "w", encoding="utf-8") as f:
                            f.write(f"Status Code: {response.status_code}\n")
                            f.write(f"Headers: {response.headers}\n")
                            f.write(response.text)
                        console.print(f"[yellow]The response was saved at: '{failure_path}'[/yellow]")

                    await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce_list, torrent_url)

                except httpx.RequestError as e:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error - {str(e)}'
            else:
                console.print(data)
