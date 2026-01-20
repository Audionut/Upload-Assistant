# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import asyncio
import json
import os
import platform
import re
from pathlib import Path
from typing import Any, Union

import aiofiles
import cli_ui
import httpx

from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.torrentcreate import TorrentCreator
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class ANT:
    def __init__(self, config: Config):
        self.tracker = 'ANT'
        self.config = config
        self.common = COMMON(config)
        self.tracker_config = self.config["TRACKERS"].get(self.tracker, {})
        self.source_flag = 'ANT'
        self.search_url = 'https://anthelion.me/api.php'
        self.upload_url = 'https://anthelion.me/api.php'
        self.banned_groups = [
            '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AROMA', 'aXXo', 'Brrip', 'CHD', 'CM8',
            'CrEwSaDe', 'd3g', 'DDR', 'DNL', 'DeadFish', 'ELiTE', 'eSc', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS',
            'FUM', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'Leffe',
            'LiGaS', 'LOAD', 'MeGusta', 'MkvCage', 'mHD', 'mSD', 'NhaNc3', 'nHD', 'NOIVTC', 'nSD', 'Oj', 'Ozlem',
            'PiRaTeS', 'PRoDJi', 'RAPiDCOWS', 'RARBG', 'RetroPeeps', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi',
            'SicFoI', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'TBS', 'Telly', 'TM', 'UPiNSMOKE', 'URANiME', 'WAF', 'xRed',
            'XS', 'YIFY', 'YTS', 'Zeus', 'ZKBL', 'ZmN', 'ZMNT'
        ]
        pass

    async def get_flags(self, meta: Meta) -> list[str]:
        flags: list[str] = []
        flags.extend(
            [
                each
                for each in ['Directors', 'Extended', 'Uncut', 'Unrated', '4KRemaster']
                if each in str(meta.get('edition', '')).replace("'", "")
            ]
        )
        flags.extend(
            [
                each.replace('-', '')
                for each in ['Dual-Audio', 'Atmos']
                if each in meta['audio']
            ]
        )
        if meta.get('has_commentary', False) or meta.get('manual_commentary', False):
            flags.append('Commentary')
        if meta['3D'] == "3D":
            flags.append('3D')
        if "HDR" in meta['hdr']:
            flags.append('HDR10')
        if "DV" in meta['hdr']:
            flags.append('DV')
        if "Criterion" in meta.get('distributor', ''):
            flags.append('Criterion')
        if "REMUX" in meta['type']:
            flags.append('Remux')
        return flags

    async def get_release_group(self, meta: Meta) -> str:
        if meta.get('tag', ''):
            tag = str(meta['tag'])

            return tag[1:]  # Remove leading character

        return ""

    async def get_tags(self, meta: Meta) -> Union[list[str], str]:
        no_tags = False
        tags: list[str] = []
        if meta.get('genres', []):
            genres = meta['genres']
            # Handle both string and list formats
            if isinstance(genres, str):
                tags.append(genres.replace(' ', '.').lower())
            else:
                tags.extend(genre.replace(' ', '.').lower() for genre in genres)
        else:
            no_tags = True
        if no_tags and meta.get('imdb_info', {}):
            imdb_genres = meta['imdb_info'].get('genres', [])
            # Handle both string and list formats
            if isinstance(imdb_genres, str):
                tags.append(imdb_genres.replace(' ', '.').lower())
            else:
                tags.extend(genre.replace(' ', '.').lower() for genre in imdb_genres)
            allowed_tags = {
                'action', 'adventure', 'animation', 'comedy', 'crime', 'documentary', 'drama',
                'family', 'fantasy', 'history', 'horror', 'music', 'mystery', 'romance', 'sci.fi',
                'thriller', 'war', 'western'
            }
            tags = [tag for tag in tags if tag.lower() in allowed_tags]

            if tags:
                console.print(f"[green]{self.tracker}: Using IMDb genres for tagging: {', '.join(tags)}")
                console.print("[yellow]ANT api will accept this upload, but no tag will be added.\n"
                              "You must manually add at least one tag from the approved list when uploaded.")
                await asyncio.sleep(3)

        if not tags:
            console.print(f"[yellow]{self.tracker}: No genres found for tagging. Tag required.")
            console.print("[yellow]Only use a tag in the approved list found in the site search box.")
            console.print("[yellow]ANT api will accept this upload, but no tag will be added.\n"
                            "You must manually add at least one tag from the approved list when uploaded.")
            await asyncio.sleep(3)
            user_tag = cli_ui.ask_string("Please enter at least one tag (genre) to use for the upload", default="")
            if user_tag:
                tags.append(user_tag.replace(' ', '.').lower())

        return tags if not no_tags else ""

    async def get_type(self, meta: Meta) -> int:
        antType = None
        imdb_info = meta.get('imdb_info', {})
        if imdb_info.get('type') is not None:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie'):
                antType = 0 if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0 else 1
            if imdbType == "short":
                antType = 1
            elif imdbType == "tv mini series":
                antType = 2
            elif imdbType == "comedy":
                antType = 3
        else:
            keywords = meta.get("keywords", "").lower()
            tmdb_type = meta.get("tmdb_type", "movie").lower()
            if tmdb_type == "movie":
                antType = 0 if int(meta.get('runtime', 60)) >= 45 or int(meta.get('runtime', 60)) == 0 else 1
            if tmdb_type == "miniseries" or "miniseries" in keywords:
                antType = 2
            if "short" in keywords or "short film" in keywords:
                antType = 1
            elif "stand-up comedy" in keywords:
                antType = 3

        if antType is None:
            if not meta['unattended']:
                antTypeList = ["Feature Film", "Short Film", "Miniseries", "Other"]
                choice = cli_ui.ask_choice("Select the proper type for ANT", choices=antTypeList)
                # Map the choice back to the integer
                type_map = {
                    "Feature Film": 0,
                    "Short Film": 1,
                    "Miniseries": 2,
                    "Other": 3
                }
                antType = type_map.get(choice, 0)
            else:
                if meta['debug']:
                    console.print(f"[bold red]{self.tracker} type could not be determined automatically in unattended mode.")
                antType = 0  # Default to Feature Film in unattended mode

        return antType

    async def upload(self, meta: Meta, _) -> bool:
        torrent_filename = "BASE"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        torrent_file_size_kib = os.path.getsize(torrent_path) / 1024
        tracker_url: str = ''
        if meta.get('mkbrr', False):
            tracker_url = self.tracker_config.get('announce_url', "https://fake.tracker").strip()

        # Trigger regeneration automatically if size constraints aren't met
        if torrent_file_size_kib > 250:  # 250 KiB
            console.print("[yellow]Existing .torrent exceeds 250 KiB and will be regenerated to fit constraints.")
            meta['max_piece_size'] = '128'  # 128 MiB
            await TorrentCreator.create_torrent(meta, str(Path(meta['path'])), "ANT", tracker_url=tracker_url)
            torrent_filename = "ANT"

        await self.common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
        flags = await self.get_flags(meta)
        audioformat = await self.get_audio(meta)
        if not audioformat:
            console.print(f"[bold red]{self.tracker} upload aborted due to unsupported audio format.")
            meta['tracker_status'][self.tracker]['status_message'] = "data error: upload aborted: unsupported audio format"
            return False

        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files = {'file_input': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')}
        data: dict[str, Any] = {
            'type': await self.get_type(meta),
            'audioformat': audioformat,
            'api_key': str(self.tracker_config.get('api_key', '')).strip(),
            'action': 'upload',
            'tmdbid': meta['tmdb'],
            'mediainfo': await self.mediainfo(meta),
            'flags[]': flags,
            'release_desc': await self.edit_desc(meta),
        }
        if meta['bdinfo'] is not None:
            data.update({"media": "BluRay"})
        if meta['scene']:
            # ID of "Scene?" checkbox on upload form is actually "censored"
            data['censored'] = 1

        tags = await self.get_tags(meta)
        if tags:
            data.update({'tags': ','.join(tags)})

        release_group = await self.get_release_group(meta)
        if release_group and release_group not in self.banned_groups:
            data.update({'releasegroup': release_group})
        else:
            data.update({'noreleasegroup': 1})

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print('[bold red]Adult content detected[/bold red]')
                if cli_ui.ask_yes_no("Are the screenshots safe?", default=False):
                    data.update({'screenshots': '\n'.join([x['raw_url'] for x in meta['image_list']][:4])})
                    if not tags:
                        data.update({'flagchangereason': "Adult with screens uploaded with Upload Assistant"})
                    else:
                        data.update({'flagchangereason': "Adult with screens uploaded with Upload Assistant. User to add tags manually."})
                else:
                    data.update({'screenshots': ''})  # No screenshots for adult content
            else:
                data.update({'screenshots': ''})
        else:
            data.update({'screenshots': '\n'.join([x['raw_url'] for x in meta['image_list']][:4])})
            if tags:
                data.update({'flagchangereason': "User prompted to add tags manually"})

        headers = {
            'User-Agent': f'Upload Assistant/2.4 ({platform.system()} {platform.release()})'
        }

        try:
            if not meta['debug']:
                async with httpx.AsyncClient(timeout=40) as client:
                    response = await client.post(url=self.upload_url, files=files, data=data, headers=headers)
                    try:
                        response_data: dict[str, Any] = response.json()
                    except json.JSONDecodeError:
                        meta['tracker_status'][self.tracker]['status_message'] = "data error: ANT json decode error, the API is probably down"
                        return False

                    if response.status_code in [200, 201]:
                        is_success = (
                            ('success' in response_data)
                            or (str(response_data.get('status', '')).lower() == 'success')
                        )
                        if not is_success:
                            meta['tracker_status'][self.tracker]['status_message'] = f"data error: {response_data}"
                            return False
                        else:
                            meta['tracker_status'][self.tracker]['status_message'] = response_data
                            return True

                    elif response.status_code == 400:
                        response_text_lc = str(response_data).lower()
                        is_exact = (
                            ('exact same' in response_text_lc)
                            or (str(response_data.get('status', '')).lower() == 'exact same')
                            or ('exact same' in str(response_data.get('error', '')).lower())
                        )
                        is_same_infohash = (
                            ('same infohash' in response_text_lc)
                            or (str(response_data.get('status', '')).lower() == 'same infohash')
                            or ('same infohash' in str(response_data.get('error', '')).lower())
                        )

                        if is_same_infohash:
                            folder = f"{meta['base_dir']}/tmp/{meta['uuid']}"
                            view_link = response_data.get('view', '')
                            status_msg = "data error: A torrent with the same infohash already exists on ANT.\n"
                            if view_link:
                                status_msg += f"View existing torrent: {view_link}\n"
                            meta['tracker_status'][self.tracker]['status_message'] = status_msg
                            return False

                        if is_exact:
                            folder = f"{meta['base_dir']}/tmp/{meta['uuid']}"
                            meta['tracker_status'][self.tracker]['status_message'] = (
                                "data error: The exact same media file already exists on ANT. You must use the website to upload a new version if you wish to trump.\n"
                                f"Use the files from {folder} to assist with manual upload.\n"
                                "raw_url image links from the image_data.json file"
                            )
                            return False

                        else:
                            response_data = {
                                "error": f"Unexpected status code: {response.status_code}",
                                "response_content": response.text
                            }
                            meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                            return False

                    elif response.status_code == 403:
                        response_data = {
                            "error": "Wrong API key or insufficient permissions",
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                        return False

                    elif response.status_code == 500:
                        response_data = {
                            "error": "Internal Server Error, report to ANT staff",
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                        return False

                    elif response.status_code == 502:
                        response_data = {
                            "error": "Bad Gateway",
                            "site seems down": "https://ant.trackerstatus.info/"
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                        return False
                    else:
                        response_data = {
                            "error": f"Unexpected status code: {response.status_code}",
                            "response_content": response.text
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                        return False
            else:
                console.print("[cyan]ANT Request Data:")
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
                await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
                return True
        except httpx.TimeoutException:
            meta['tracker_status'][self.tracker]['status_message'] = "data error: ANT request timed out while uploading."
            return False
        except httpx.RequestError as e:
            meta['tracker_status'][self.tracker]['status_message'] = f"data error: An error occurred while making the request: {e}"
            return False
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "No error message"
            traceback_str = traceback.format_exc()
            console.print(f"[bold red]ANT upload exception ({error_type}): {error_msg}[/bold red]")
            console.print(f"[red]Traceback:\n{traceback_str}[/red]")
            meta['tracker_status'][self.tracker]['status_message'] = "data error: double check if it uploaded"
            return False

    async def get_audio(self, meta: Meta) -> str:
        '''
        Possible values:
        MP2, MP3, AAC, AC3, DTS, FLAC, PCM, True-HD, Opus
        '''
        audio = meta.get('audio', '').upper()
        audio_map = {
            'MP2': 'MP2',
            'MP3': 'MP3',
            'AAC': 'AAC',
            'DD': 'AC3',
            'DTS': 'DTS',
            'FLAC': 'FLAC',
            'PCM': 'PCM',
            'TRUEHD': 'True-HD',
            'OPUS': 'Opus'
        }
        for key, value in audio_map.items():
            if key in audio:
                return value
        console.print(f'{self.tracker}: Unexpected audio format: {audio}. The format must be one of the following: MP2, MP3, AAC, AC3, DTS, FLAC, PCM, True-HD, Opus')
        return ""

    async def mediainfo(self, meta: Meta) -> str:
        if meta.get('is_disc') == 'BDMV':
            mediainfo = str(await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'], char_limit=100000))
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            async with aiofiles.open(mi_path, encoding='utf-8') as f:
                mediainfo = str(await f.read())

        return mediainfo

    async def edit_desc(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Avoid unnecessary descriptions, adding only the logo if there is a user description
        user_desc: str = await builder.get_user_description(meta)
        if user_desc:
            # Custom Header
            desc_parts.append(await builder.get_custom_header())

            # Logo
            logo_resize_url = meta.get('tmdb_logo', '')
            if logo_resize_url:
                desc_parts.append(f"[align=center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/align]")

        # BDinfo
        bdinfo = await builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f"[spoiler=BDInfo][pre]{bdinfo}[/pre][/spoiler]")

        if user_desc:
            # User description
            desc_parts.append(user_desc)

        # Disc menus screenshots
        menu_images = meta.get("menu_images", [])
        if menu_images:
            desc_parts.append(await builder.menu_screenshot_header(meta))

            # Disc menus screenshots
            menu_screenshots_block = ""
            for image in menu_images:
                menu_raw_url = image.get("raw_url")
                if menu_raw_url:
                    menu_screenshots_block += f"[img]{menu_raw_url}[/img] "
            if menu_screenshots_block:
                desc_parts.append(f"[align=center]{menu_screenshots_block}[/align]")

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.convert_to_align(description)
        description = bbcode.remove_img_resize(description)
        description = bbcode.remove_sup(description)
        description = bbcode.remove_sub(description)
        description = description.replace('•', '-').replace('’', "'").replace('–', '-')
        description = bbcode.remove_extra_lines(description)
        description = description.strip()

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def search_existing(self, meta: Meta, _) -> list[dict[str, Any]]:
        dupes: list[dict[str, Any]] = []
        if meta.get('category') == "TV":
            if not meta['unattended']:
                console.print('[bold red]ANT only ALLOWS Movies.')
            meta['skipping'] = "ANT"
            return dupes

        if meta['valid_mi'] is False:
            if not meta['unattended']:
                console.print(f"[bold red]No unique ID in mediainfo, skipping {self.tracker} upload.")
            meta['skipping'] = "ANT"
            return dupes

        api_key = self.tracker_config.get('api_key')
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            console.print(f"[bold red]{self.tracker} API key not configured or invalid.")
            meta['skipping'] = "ANT"
            return dupes

        params = {
            'apikey': api_key.strip(),
            't': 'search',
            'o': 'json'
        }
        if meta['tmdb'] != 0:
            params['tmdb'] = meta['tmdb']
        elif int(meta['imdb_id']) != 0:
            params['imdb'] = meta['imdb']

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        target_resolution = meta.get('resolution', '').lower()

                        for each in data.get('item', []):
                            if target_resolution and each.get('resolution', '').lower() != target_resolution.lower():
                                if meta.get('debug'):
                                    console.print(f"[yellow]Skipping {each.get('fileName')} - resolution mismatch: {each.get('resolution')} vs {target_resolution}")
                                continue

                            largest_file = None
                            if 'files' in each and len(each['files']) > 0:
                                largest = each['files'][0]
                                for file in each['files']:
                                    current_size = int(file.get('size', 0))
                                    largest_size = int(largest.get('size', 0))
                                    if current_size > largest_size:
                                        largest = file
                                largest_file = largest.get('name', '')

                            result: dict[str, Any] = {
                                'name': largest_file or each.get('fileName', ''),
                                'files': [file.get('name', '') for file in each.get('files', [])],
                                'size': int(each.get('size', 0)),
                                'link': each.get('guid', ''),
                                'flags': each.get('flags', []),
                                'file_count': each.get('fileCount', 0),
                                'download': each.get('link', '').replace('&amp;', '&'),
                            }
                            dupes.append(result)

                            if meta.get('debug'):
                                console.print(f"[green]Found potential dupe: {result['name']} ({result['size']} bytes)")

                    except json.JSONDecodeError:
                        console.print("[bold yellow]ANT response content is not valid JSON. Skipping this API call.")
                        meta['skipping'] = "ANT"
                else:
                    console.print(f"[bold red]ANT failed to search torrents. HTTP Status: {response.status_code}")
                    meta['skipping'] = "ANT"
        except httpx.TimeoutException:
            console.print("[bold red]ANT Request timed out after 5 seconds")
            meta['skipping'] = "ANT"
        except httpx.RequestError as e:
            console.print(f"[bold red]ANT unable to search for existing torrents: {e}")
            meta['skipping'] = "ANT"
        except Exception as e:
            console.print(f"[bold red]ANT unexpected error: {e}")
            meta['skipping'] = "ANT"
            await asyncio.sleep(5)

        return dupes

    async def get_data_from_files(self, meta: Meta) -> list[dict[str, Any]]:
        imdb_tmdb_list: list[dict[str, Any]] = []
        if meta.get('is_disc', False):
            return imdb_tmdb_list

        filelist: list[str] = meta.get('filelist', [])
        if not filelist:
            if meta.get('debug'):
                console.print(f"[yellow]{self.tracker}: No files in filelist, skipping file-based search.")
            return imdb_tmdb_list

        filename: str = os.path.basename(filelist[0])

        api_key = self.tracker_config.get('api_key')
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            if meta.get('debug'):
                console.print(f"[yellow]{self.tracker}: API key not configured, skipping file-based search.")
            return imdb_tmdb_list

        params: dict[str, Any] = {
            'apikey': api_key.strip(),
            't': 'search',
            'filename': filename,
            'o': 'json'
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        items = data.get('item', [])

                        matched_item = None
                        if len(items) == 1:
                            matched_item = items[0]
                        elif len(items) > 1:
                            # Try to match filename from the files in each result
                            for item in items:
                                files = item.get('files', [])
                                for file in files:
                                    file_name = file.get('name', '')

                                    # Try exact match first (with extension)
                                    if filename.lower() == file_name.lower():
                                        matched_item = item
                                        break

                                    # Try base filename match (without extension)
                                    base_filename = os.path.splitext(filename)[0]
                                    base_file_name = os.path.splitext(file_name)[0]
                                    if base_filename.lower() == base_file_name.lower():
                                        matched_item = item
                                        break
                                if matched_item:
                                    break

                            if not matched_item:
                                if meta['debug']:
                                    console.print("[yellow]Could not match filename, returning empty list")
                                imdb_tmdb_list = []

                        if matched_item:
                            imdb_id = matched_item.get('imdb')
                            tmdb_id = matched_item.get('tmdb')
                            if imdb_id and imdb_id.startswith('tt'):
                                imdb_num = int(imdb_id[2:])
                                imdb_tmdb_list.append({'imdb_id': imdb_num})
                            if tmdb_id and str(tmdb_id).isdigit() and int(tmdb_id) != 0:
                                imdb_tmdb_list.append({'tmdb_id': int(tmdb_id)})
                    except json.JSONDecodeError:
                        console.print("[bold yellow]Error parsing JSON response from ANT")
                        imdb_tmdb_list = []
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
                    imdb_tmdb_list = []
        except httpx.TimeoutException:
            console.print("[bold red]ANT Request timed out after 5 seconds")
            imdb_tmdb_list = []
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
            imdb_tmdb_list = []
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            imdb_tmdb_list = []

        return imdb_tmdb_list
