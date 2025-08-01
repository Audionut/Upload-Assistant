# -*- coding: utf-8 -*-
# import discord
import httpx
import os
import re
import platform
from src.trackers.COMMON import COMMON
from src.console import console
from pymediainfo import MediaInfo


class TL():
    CATEGORIES = {
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

    def __init__(self, config):
        self.config = config
        self.tracker = 'TL'
        self.source_flag = 'TorrentLeech.org'
        self.base_url = 'https://www.torrentleech.org'
        self.http_upload_url = f'{self.base_url}/torrents/upload/'
        self.api_upload_url = f'{self.base_url}/torrents/upload/apiupload'
        self.signature = """<center><a href="https://github.com/Audionut/Upload-Assistant">Created by Audionut's Upload Assistant</a></center>"""
        self.banned_groups = [""]
        self.session = httpx.AsyncClient(timeout=60.0)
        self.api_upload = self.config['TRACKERS'][self.tracker].get('api_upload')
        self.announce_key = self.config['TRACKERS'][self.tracker]['announce_key']
        self.config['TRACKERS'][self.tracker]['announce_url'] = f"https://tracker.torrentleech.org/a/{self.announce_key}/announce"
        self.session.headers.update({
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        })

    async def login(self, meta):
        if self.api_upload:
            return True

        self.cookies_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/TL.txt")

        cookie_path = os.path.abspath(self.cookies_file)
        if not os.path.exists(cookie_path):
            console.print(f"[bold red]'{self.tracker}' Cookies not found at: {cookie_path}[/bold red]")
            return False

        common = COMMON(config=self.config)
        self.session.cookies.update(await common.parseCookieFile(self.cookies_file))

        try:
            response = await self.session.get(self.http_upload_url, timeout=10)
            if response.status_code == 200 and 'torrents/upload' in str(response.url):
                return True

        except httpx.RequestError as e:
            console.print(f"[bold red]Error while validating credentials for '{self.tracker}': {e}[/bold red]")
            return False

    async def generate_description(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        self.final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

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

        # Add screenshots to description only if it is an anonymous upload as TL does not support anonymous upload in the screenshots section
        if meta.get('anon', False) or self.api_upload:
            images = meta.get('image_list', [])

            screenshots_block = "<center>Screenshots\n\n"
            for image in images:
                img_url = image['img_url']
                web_url = image['web_url']
                screenshots_block += f"""<a href="{web_url}"><img src="{img_url}"></a> """
            screenshots_block += "\n</center>"

            description_parts.append(screenshots_block)

        if self.signature:
            description_parts.append(self.signature)

        final_description = "\n\n".join(filter(None, description_parts))
        from src.bbcode import BBCODE
        bbcode = BBCODE()
        desc = final_description
        desc = desc.replace("[center]", "<center>").replace("[/center]", "</center>")
        desc = re.sub(r'\[spoiler=.*?\]', '[spoiler]', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\[\*\]', '\n[*]', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\[list=.*?\]', '[list]', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\[c\](.*?)\[/c\]', r'[code]\1[/code]', desc, flags=re.IGNORECASE | re.DOTALL)
        desc = re.sub(r'\[hr\]', '---', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\[img=[\d"x]+\]', '[img]', desc, flags=re.IGNORECASE)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)

        with open(self.final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def get_cat_id(self, common, meta):
        if meta.get('anime', 0):
            return self.CATEGORIES['Anime']

        if meta['category'] == 'MOVIE':
            if meta['original_language'] != 'en':
                return self.CATEGORIES['MovieForeign']
            elif 'Documentary' in meta['genres']:
                return self.CATEGORIES['MovieDocumentary']
            elif meta['resolution'] == '2160p':
                return self.CATEGORIES['Movie4K']
            elif meta['is_disc'] in ('BDMV', 'HDDVD') or (meta['type'] == 'REMUX' and meta['source'] in ('BluRay', 'HDDVD')):
                return self.CATEGORIES['MovieBluray']
            elif meta['type'] == 'ENCODE' and meta['source'] in ('BluRay', 'HDDVD'):
                return self.CATEGORIES['MovieBlurayRip']
            elif meta['is_disc'] == 'DVD' or (meta['type'] == 'REMUX' and 'DVD' in meta['source']):
                return self.CATEGORIES['MovieDvd']
            elif meta['type'] == 'ENCODE' and 'DVD' in meta['source']:
                return self.CATEGORIES['MovieDvdRip']
            elif 'WEB' in meta['type']:
                return self.CATEGORIES['MovieWebrip']
            elif meta['type'] == 'HDTV':
                return self.CATEGORIES['MovieHdRip']
        elif meta['category'] == 'TV':
            if meta['original_language'] != 'en':
                return self.CATEGORIES['TvForeign']
            elif meta.get('tv_pack', 0):
                return self.CATEGORIES['TvBoxsets']
            elif meta['sd']:
                return self.CATEGORIES['TvEpisodes']
            else:
                return self.CATEGORIES['TvEpisodesHd']

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
            name = meta['name']

        return name

    async def search_existing(self, meta, disctype):
        await self.login(meta)
        cat_id = await self.get_cat_id(self, meta)

        dupes = []

        if self.api_upload:
            console.print(f"[bold yellow]Cannot search for duplicates on {self.tracker} when using API upload.[/bold yellow]")
            return dupes

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

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(common, meta)

        if self.api_upload:
            await self.upload_api(meta, cat_id)
        else:
            await self.upload_http(meta, cat_id)

    async def upload_api(self, meta, cat_id):
        desc_content = await self.generate_description(meta)
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        with open(torrent_path, 'rb') as open_torrent:
            files = {
                'torrent': (self.get_name(meta) + '.torrent', open_torrent, 'application/x-bittorrent')
            }
            data = {
                'announcekey': self.announce_key,
                'category': cat_id,
                'nfo': desc_content
            }

            if meta['debug'] is False:
                response = await self.session.post(
                    url=self.api_upload_url,
                    files=files,
                    data=data
                )
                if not response.text.isnumeric():
                    meta['tracker_status'][self.tracker]['status_message'] = response.text
            else:
                console.print("[cyan]Request Data:")
                console.print(data)

    async def upload_http(self, meta, cat_id):
        if not await self.login(meta):
            meta['tracker_status'][self.tracker]['status_message'] = "Login with cookies failed."
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
                'category': cat_id,
                'nonscene': 'on' if not meta.get("scene") else 'off',
                'imdbURL': imdbURL,
                'tvMazeURL': tvMazeURL,
                'igdbURL': '',
                'torrentNFO': '0',
                'torrentDesc': '1',
                'nfotextbox': '',
                'torrentComment': '0',
                'uploaderComments': '',
                'is_anonymous_upload': 'on' if meta.get('anon', False) else 'off',
                'screenshots[]': '' if meta.get('anon', False) else self.get_screens(meta),  # It is not possible to upload screenshots anonymously
            }

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

                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        common = COMMON(config=self.config)
                        await common.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, torrent_url)

                    else:
                        console.print("[bold red]Upload failed: No success redirect found.[/bold red]")
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                        with open(failure_path, "w", encoding="utf-8") as f:
                            f.write(f"Status Code: {response.status_code}\n")
                            f.write(f"Headers: {response.headers}\n")
                            f.write(response.text)
                        console.print(f"[yellow]The response was saved at: '{failure_path}'[/yellow]")

                except httpx.RequestError as e:
                    console.print(f"[bold red]Error during upload to '{self.tracker}': {e}[/bold red]")
                    meta['tracker_status'][self.tracker]['status_message'] = str(e)
            else:
                console.print(data)
