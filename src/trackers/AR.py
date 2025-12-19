# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import httpx
import json
import os
import platform
import re
import asyncio
from rich.prompt import Prompt
import urllib.parse
from src.exceptions import *  # noqa F403
from bs4 import BeautifulSoup
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.trackers.COMMON import COMMON
from pymediainfo import MediaInfo


class AR():
    def __init__(self, config):
        self.config = config
        self.cookie_validator = CookieValidator(config)
        self.cookie_uploader = CookieAuthUploader(config)
        self.tracker = 'AR'
        self.source_flag = 'AlphaRatio'
        self.username = config['TRACKERS']['AR'].get('username', '').strip()
        self.password = config['TRACKERS']['AR'].get('password', '').strip()
        self.base_url = 'https://alpharatio.cc'
        self.login_url = f'{self.base_url}/login.php'
        self.upload_url = f'{self.base_url}/upload.php'
        self.search_url = f'{self.base_url}/torrents.php'
        self.test_url = f'{self.base_url}/torrents.php'
        self.torrent_url = f'{self.base_url}/torrents.php?id='
        self.user_agent = f'Upload Assistant/2.3 ({platform.system()} {platform.release()})'
        self.banned_groups = []

    async def get_type(self, meta):
        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if (meta['type'] == 'DISC' or meta['type'] == 'REMUX') and meta['source'] == 'Blu-ray':
            return "14"

        if meta.get('anime'):
            if meta['sd']:
                return '15'
            else:
                return {
                    '8640p': '16',
                    '4320p': '16',
                    '2160p': '16',
                    '1440p': '16',
                    '1080p': '16',
                    '1080i': '16',
                    '720p': '16',
                }.get(meta['resolution'], '15')

        elif meta['category'] == "TV":
            if meta['tv_pack']:
                if meta['sd']:
                    return '4'
                else:
                    return {
                        '8640p': '6',
                        '4320p': '6',
                        '2160p': '6',
                        '1440p': '5',
                        '1080p': '5',
                        '1080i': '5',
                        '720p': '5',
                    }.get(meta['resolution'], '4')
            elif meta['sd']:
                return '0'
            else:
                return {
                    '8640p': '2',
                    '4320p': '2',
                    '2160p': '2',
                    '1440p': '1',
                    '1080p': '1',
                    '1080i': '1',
                    '720p': '1',
                }.get(meta['resolution'], '0')

        if meta['category'] == "MOVIE":
            if meta['sd']:
                return '7'
            elif any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
                return '13'
            else:
                return {
                    '8640p': '9',
                    '4320p': '9',
                    '2160p': '9',
                    '1440p': '8',
                    '1080p': '8',
                    '1080i': '8',
                    '720p': '8',
                }.get(meta['resolution'], '7')

    async def validate_credentials(self, meta):
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=self.test_url,
            error_text="login.php?act=recover",
        )

    def get_links(self, movie, subheading, heading_end):
        description = ""
        description += "\n" + subheading + "Links" + heading_end + "\n"
        if 'IMAGES' in self.config:
            if movie['imdb_id'] != 0:
                description += f"[url={movie.get('imdb_info', {}).get('imdb_url', '')}][img]{self.config['IMAGES']['imdb_75']}[/img][/url]"
            if movie['tmdb'] != 0:
                description += f" [url=https://www.themoviedb.org/{str(movie['category'].lower())}/{str(movie['tmdb'])}][img]{self.config['IMAGES']['tmdb_75']}[/img][/url]"
            if movie['tvdb_id'] != 0:
                description += f" [url=https://www.thetvdb.com/?id={str(movie['tvdb_id'])}&tab=series][img]{self.config['IMAGES']['tvdb_75']}[/img][/url]"
            if movie['tvmaze_id'] != 0:
                description += f" [url=https://www.tvmaze.com/shows/{str(movie['tvmaze_id'])}][img]{self.config['IMAGES']['tvmaze_75']}[/img][/url]"
            if movie['mal_id'] != 0:
                description += f" [url=https://myanimelist.net/anime/{str(movie['mal_id'])}][img]{self.config['IMAGES']['mal_75']}[/img][/url]"
        else:
            if movie['imdb_id'] != 0:
                description += f"{movie.get('imdb_info', {}).get('imdb_url', '')}"
            if movie['tmdb'] != 0:
                description += f"\nhttps://www.themoviedb.org/{str(movie['category'].lower())}/{str(movie['tmdb'])}"
            if movie['tvdb_id'] != 0:
                description += f"\nhttps://www.thetvdb.com/?id={str(movie['tvdb_id'])}&tab=series"
            if movie['tvmaze_id'] != 0:
                description += f"\nhttps://www.tvmaze.com/shows/{str(movie['tvmaze_id'])}"
            if movie['mal_id'] != 0:
                description += f"\nhttps://myanimelist.net/anime/{str(movie['mal_id'])}"
        return description

    async def edit_desc(self, meta):
        heading = "[color=green][size=6]"
        subheading = "[color=red][size=4]"
        heading_end = "[/size][/color]"
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf8') as f:
            base = await f.read()
        base = re.sub(r'\[center\]\[spoiler=Scene NFO:\].*?\[/center\]', '', base, flags=re.DOTALL)
        base = re.sub(r'\[center\]\[spoiler=FraMeSToR NFO:\].*?\[/center\]', '', base, flags=re.DOTALL)
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            description = ""
            if meta['is_disc'] == "BDMV":
                description += heading + str(meta['name']) + heading_end + "\n" + self.get_links(meta, subheading, heading_end) + "\n\n" + subheading + "BDINFO" + heading_end + "\n"
            else:
                description += heading + str(meta['name']) + heading_end + "\n" + self.get_links(meta, subheading, heading_end) + "\n\n" + subheading + "MEDIAINFO" + heading_end + "\n"
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            description += f"[hide={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/hide]\n\n"
                        if each['type'] == "DVD":
                            description += f"{each['name']}:\n"
                            description += f"[hide={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/hide] [hide={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/hide]\n\n"
            # description += common.get_links(movie, "[COLOR=red][size=4]", "[/size][/color]")
                elif discs[0]['type'] == "DVD":
                    description += f"[hide][code]{discs[0]['vob_mi']}[/code][/hide]\n\n"
                elif meta['is_disc'] == "BDMV":
                    description += f"[hide][code]{discs[0]['summary']}[/code][/hide]\n\n"
            else:
                # Beautify MediaInfo for AR using custom template
                video = meta['filelist'][0]
                # using custom mediainfo template.
                # can not use full media info as sometimes its more than max chars per post.
                mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/summary-mediainfo.csv")
                if os.path.exists(mi_template):
                    media_info = await self.parse_mediainfo_async(video, mi_template)
                    description += (f"""[code]\n{media_info}\n[/code]\n""")
                    # adding full mediainfo as spoiler
                    async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as MI:
                        full_mediainfo = await MI.read()
                    description += f"[hide=FULL MEDIAINFO][code]{full_mediainfo}[/code][/hide]\n"
                else:
                    console.print("[bold red]Couldn't find the MediaInfo template")
                    console.print("[green]Using normal MediaInfo for the description.")

                    async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as MI:
                        cleaned_mediainfo = await MI.read()
                        description += (f"""[code]\n{cleaned_mediainfo}\n[/code]\n\n""")

            description += "\n\n" + subheading + "PLOT" + heading_end + "\n" + str(meta['overview'])
            if meta['genres']:
                description += "\n\n" + subheading + "Genres" + heading_end + "\n" + str(meta['genres'])

            if meta['image_list'] is not None and len(meta['image_list']) > 0:
                description += "\n\n" + subheading + "Screenshots" + heading_end + "\n"
                description += "[align=center]"
                for image in meta['image_list']:
                    if image['raw_url'] is not None:
                        description += "[url=" + image['raw_url'] + "][img]" + image['img_url'] + "[/img][/url]"
                description += "[/align]"
            if 'youtube' in meta:
                description += "\n\n" + subheading + "Youtube" + heading_end + "\n" + str(meta['youtube'])

            # adding extra description if passed
            if len(base) > 2:
                description += "\n\n" + subheading + "Notes" + heading_end + "\n" + str(base)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            await descfile.write(description)
        return

    async def get_language_tag(self, meta):
        lang_tag = ""
        has_eng_audio = False
        audio_lang = ""
        if meta['is_disc'] != "BDMV":
            try:
                async with aiofiles.open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json", 'r', encoding='utf-8') as f:
                    mi_content = await f.read()
                    mi = json.loads(mi_content)
                for track in mi['media']['track']:
                    if track['@type'] == "Audio":
                        if track.get('Language', 'None').startswith('en'):
                            has_eng_audio = True
                        if not has_eng_audio:
                            audio_lang = mi['media']['track'][2].get('Language_String', "").upper()
            except Exception as e:
                console.print(f"[red]Error: {e}")
        else:
            for audio in meta['bdinfo']['audio']:
                if audio['language'] == 'English':
                    has_eng_audio = True
                if not has_eng_audio:
                    audio_lang = meta['bdinfo']['audio'][0]['language'].upper()
        if audio_lang != "":
            lang_tag = audio_lang
        return lang_tag

    async def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def search_existing(self, meta, DISCTYPE):
        dupes = []
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if not cookie_jar:
            console.print(f"{self.tracker}: Cannot search without valid cookies.")
            return dupes

        # Combine title and year
        title = str(meta.get('title', '')).strip()
        year = str(meta.get('year', '')).strip()
        if not title:
            console.print("[red]Title is missing.")
            return dupes

        search_query = f"{title} {year}".strip()
        search_query_encoded = urllib.parse.quote(search_query)
        search_url = f'{self.base_url}/ajax.php?action=browse&searchstr={search_query_encoded}'

        if meta.get('debug', False):
            console.print(f"[blue]{search_url}")

        headers = {
            "User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=30.0, cookies=cookie_jar) as client:
                response = await client.get(search_url)

                if response.status_code != 200:
                    console.print("[bold red]Request failed. Site May be down")
                    return dupes

                json_response = response.json()
                if json_response.get('status') != 'success':
                    console.print("[red]Invalid response status.")
                    return dupes

                results = json_response.get('response', {}).get('results', [])
                if not results:
                    return dupes

                for res in results:
                    if 'groupName' in res:
                        dupe = {
                            'name': res['groupName'],
                            'size': res['size'],
                            'files': res['groupName'],
                            'file_count': res['fileCount'],
                            'link': f'{self.search_url}?id={res["groupId"]}&torrentid={res["torrentId"]}',
                        }
                        dupes.append(dupe)

                return dupes

        except Exception as e:
            console.print(f"[red]Error occurred: {e}")
            return dupes

    async def get_auth_key(self, meta):
        """Retrieve the saved auth key from cookie_auth.py."""
        auth_key = await self.cookie_validator.get_ar_auth_key(meta, self.tracker)
        if auth_key:
            return auth_key

        console.print(f"{self.tracker}: [yellow]Auth key not found. This may happen if you're using manually exported cookies.[/yellow]")
        console.print(f"{self.tracker}: [yellow]Attempting to extract auth key from torrents page...[/yellow]")

        # Fallback: extract from torrents page if not saved
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if not cookie_jar:
            return None

        headers = {
            "User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=30.0, cookies=cookie_jar) as client:
                response = await client.get(self.test_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                logout_link = soup.find('a', href=True, text='Logout')

                if logout_link:
                    href = logout_link['href']
                    match = re.search(r'auth=([^&]+)', href)
                    if match:
                        auth_key = match.group(1)
                        # Save it for next time
                        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
                        auth_file = cookie_file.replace('.txt', '_auth.txt')
                        try:
                            async with aiofiles.open(auth_file, 'w', encoding='utf-8') as f:
                                await f.write(auth_key)
                            console.print(f"{self.tracker}: [green]Auth key saved for future use[/green]")
                        except Exception:
                            pass
                        return auth_key
        except Exception as e:
            console.print(f"[red]Error extracting auth key: {e}")

        return None

    async def upload(self, meta, disctype):
        """Upload torrent to AR using centralized cookie_upload."""
        # Prepare the data for the upload
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        type_id = await self.get_type(meta)

        # Read the description
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        try:
            async with aiofiles.open(desc_path, 'r', encoding='utf-8') as desc_file:
                desc = await desc_file.read()
        except FileNotFoundError:
            meta['tracker_status'][self.tracker]['status_message'] = f"data error: Description file not found at {desc_path}"
            return

        # Handle cover image input
        cover = meta.get('poster', None) or meta["imdb_info"].get("cover", None)
        while cover is None and not meta.get("unattended", False):
            cover = Prompt.ask("No Poster was found. Please input a link to a poster:", default="")
            if not re.match(r'https?://.*\.(jpg|png|gif)$', cover):
                console.print("[red]Invalid image link. Please enter a link that ends with .jpg, .png, or .gif.")
                cover = None

        # Tag Compilation
        genres = meta.get('genres')
        if genres:
            tags = []
            for item in genres.split(','):
                for subitem in item.split('&'):
                    tags.append(subitem.strip())
            genres = ', '.join(tags)

            genres = re.sub(r'\.{2,}', '.', genres)

        # adding tags
        tags = ""
        if meta['imdb_id'] != 0:
            tags += f"tt{meta.get('imdb', '')}, "
        tags += f"{genres}, "

        # Get auth key
        auth_key = await self.get_auth_key(meta)
        if not auth_key:
            meta['tracker_status'][self.tracker]['status_message'] = "data error: Failed to extract auth key"
            return

        # must use scene name if scene release
        KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".ts"}
        if meta['scene']:
            ar_name = meta.get('scene_name')
        else:
            ar_name = meta['uuid']
            base, ext = os.path.splitext(ar_name)
            if ext.lower() in KNOWN_EXTENSIONS:
                ar_name = base
            ar_name = ar_name.replace(' ', ".").replace("'", '').replace(':', '').replace("(", '.').replace(")", '.').replace("[", '.').replace("]", '.').replace("{", '.').replace("}", '.')
            ar_name = re.sub(r'\.{2,}', '.', ar_name)

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                ar_name = re.sub(f"-{invalid_tag}", "", ar_name, flags=re.IGNORECASE)
            ar_name = f"{ar_name}-NoGRP"

        # Prepare upload data
        data = {
            "submit": "true",
            "auth": auth_key,
            "type": type_id,
            "title": ar_name,
            "tags": tags,
            "image": cover,
            "desc": desc,
        }

        # Load cookies for upload
        upload_cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if not upload_cookies:
            meta['tracker_status'][self.tracker]['status_message'] = "data error:Failed to load cookies for upload"
            return

        # Use centralized handle_upload from CookieAuthUploader
        await self.cookie_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            data=data,
            upload_cookies=upload_cookies,
            upload_url=self.upload_url,
            torrent_field_name="file_input",
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            id_pattern=r'torrents\.php\?id=(\d+)',
            success_status_code="200",
        )

    async def parse_mediainfo_async(self, video_path, template_path):
        """Parse MediaInfo asynchronously using thread executor"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: MediaInfo.parse(
                video_path,
                output="STRING",
                full=False,
                mediainfo_options={"inform": f"file://{template_path}"}
            )
        )
