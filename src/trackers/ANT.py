# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import cli_ui
import httpx
import json
import os
import platform
import re
from pathlib import Path
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.torrentcreate import create_torrent
from src.trackers.COMMON import COMMON


class ANT:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ANT'
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

    async def get_flags(self, meta):
        flags = []
        for each in ['Directors', 'Extended', 'Uncut', 'Unrated', '4KRemaster']:
            if each in meta['edition'].replace("'", ""):
                flags.append(each)
        for each in ['Dual-Audio', 'Atmos']:
            if each in meta['audio']:
                flags.append(each.replace('-', ''))
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

    async def get_type(self, meta):
        antType = None
        imdb_info = meta.get('imdb_info', {})
        if imdb_info['type'] is not None:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie'):
                if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0:
                    antType = 0
                else:
                    antType = 1
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
                if int(meta.get('runtime', 60)) >= 45 or int(meta.get('runtime', 60)) == 0:
                    antType = 0
                else:
                    antType = 1
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
                antType = type_map.get(choice)
            else:
                if meta['debug']:
                    console.print(f"[bold red]{self.tracker} type could not be determined automatically in unattended mode.")
                antType = 0  # Default to Feature Film in unattended mode

        return antType

    async def upload(self, meta, disctype):
        torrent_filename = "BASE"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        torrent_file_size_kib = os.path.getsize(torrent_path) / 1024
        if meta.get('mkbrr', False):
            tracker_url = self.config['TRACKERS']['ANT'].get('announce_url', "https://fake.tracker").strip()
        else:
            tracker_url = ''

        # Trigger regeneration automatically if size constraints aren't met
        if torrent_file_size_kib > 250:  # 250 KiB
            console.print("[yellow]Existing .torrent exceeds 250 KiB and will be regenerated to fit constraints.")
            meta['max_piece_size'] = '128'  # 128 MiB
            create_torrent(meta, Path(meta['path']), "ANT", tracker_url=tracker_url)
            torrent_filename = "ANT"

        await self.common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
        flags = await self.get_flags(meta)

        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files = {'file_input': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')}
        data = {
            'type': await self.get_type(meta),
            'audioformat': await self.get_audio(meta),
            'api_key': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'action': 'upload',
            'tmdbid': meta['tmdb'],
            'mediainfo': await self.mediainfo(meta),
            'flags[]': flags,
            'release_desc': await self.edit_desc(meta),
        }
        if meta['bdinfo'] is not None:
            data.update({
                'media': 'Blu-ray',
                'releasegroup': str(meta['tag'])[1:]
            })
        if meta['scene']:
            # ID of "Scene?" checkbox on upload form is actually "censored"
            data['censored'] = 1

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print('[bold red]Adult content detected[/bold red]')
                if cli_ui.ask_yes_no("Are the screenshots safe?", default=False):
                    data.update({'screenshots': '\n'.join([x['raw_url'] for x in meta['image_list']][:4])})
                    if meta.get('is_disc') == 'BDMV':
                        data.update({'flagchangereason': "(Adult with screens) BDMV Uploaded with Upload Assistant"})
                    else:
                        data.update({'flagchangereason': "Adult with screens uploaded with Upload Assistant"})
                else:
                    data.update({'screenshots': ''})  # No screenshots for adult content
            else:
                data.update({'screenshots': ''})
        else:
            data.update({'screenshots': '\n'.join([x['raw_url'] for x in meta['image_list']][:4])})

        if meta.get('is_disc') == 'BDMV' and data.get('flagchangereason') is None:
            data.update({'flagchangereason': "BDMV Uploaded with Upload Assistant"})

        headers = {
            'User-Agent': f'Upload Assistant/2.4 ({platform.system()} {platform.release()})'
        }

        try:
            if not meta['debug']:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(url=self.upload_url, files=files, data=data, headers=headers)
                    if response.status_code in [200, 201]:
                        try:
                            response_data = response.json()
                        except json.JSONDecodeError:
                            meta['tracker_status'][self.tracker]['status_message'] = "data error: ANT json decode error, the API is probably down"
                            return
                        if "Success" not in response_data:
                            meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                        if meta.get('tag', '') and 'HONE' in meta.get('tag', ''):
                            meta['tracker_status'][self.tracker]['status_message'] = f"{response_data} - HONE release, fix tag at ANT"
                        else:
                            meta['tracker_status'][self.tracker]['status_message'] = response_data
                    elif response.status_code == 502:
                        response_data = {
                            "error": "Bad Gateway",
                            "site seems down": "https://ant.trackerstatus.info/"
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                    else:
                        response_data = {
                            "error": f"Unexpected status code: {response.status_code}",
                            "response_content": response.text
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
            else:
                console.print("[cyan]ANT Request Data:")
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        except Exception as e:
            meta['tracker_status'][self.tracker]['status_message'] = f"data error: ANT upload failed: {e}"

    async def get_audio(self, meta):
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
        return None

    async def mediainfo(self, meta):
        if meta.get('is_disc') == 'BDMV':
            mediainfo = await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'])
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            async with aiofiles.open(mi_path, 'r', encoding='utf-8') as f:
                mediainfo = await f.read()

        return mediainfo

    async def edit_desc(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Avoid unnecessary descriptions, adding only the logo if there is a user description
        user_desc = await builder.get_user_description(meta)
        if user_desc:
            # Custom Header
            desc_parts.append(await builder.get_custom_header(self.tracker))

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

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

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

    async def search_existing(self, meta, disctype):
        if meta.get('category') == "TV":
            if not meta['unattended']:
                console.print('[bold red]ANT only ALLOWS Movies.')
            meta['skipping'] = "ANT"
            return []

        if meta.get('bloated', False):
            if not meta['unattended']:
                console.print('[bold red]ANT does not allow bloated releases.')
            meta['skipping'] = "ANT"
            return []

        dupes = []
        params = {
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            't': 'search',
            'o': 'json'
        }
        if str(meta['tmdb']) != 0:
            params['tmdb'] = meta['tmdb']
        elif int(meta['imdb_id']) != 0:
            params['imdb'] = meta['imdb']

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url='https://anthelion.me/api', params=params)
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

                            result = {
                                'name': largest_file or each.get('fileName', ''),
                                'files': [file.get('name', '') for file in each.get('files', [])],
                                'size': int(each.get('size', 0)),
                                'link': each.get('guid', ''),
                                'flags': each.get('flags', []),
                                'file_count': each.get('fileCount', 0)
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

    async def get_data_from_files(self, meta):
        if meta.get('is_disc', False):
            return []
        filelist = meta.get('filelist', [])
        filename = [os.path.basename(f) for f in filelist][0]
        params = {
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            't': 'search',
            'filename': filename,
            'o': 'json'
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url='https://anthelion.me/api', params=params)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        imdb_tmdb_list = []
                        items = data.get('item', [])
                        if len(items) == 1:
                            each = items[0]
                            imdb_id = each.get('imdb')
                            tmdb_id = each.get('tmdb')
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
