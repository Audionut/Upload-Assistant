# -*- coding: utf-8 -*-
# import discord
import asyncio
import json
import re
import time

import cli_ui
import requests
import platform
import httpx
from src.trackers.COMMON import COMMON
from src.console import console


class RHD():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'RHD'
        self.source_flag = 'RocketHD'
        self.upload_url = 'https://rocket-hd.cc/api/torrents/upload/'
        self.search_url = 'https://rocket-hd.cc/api/torrents/filter/'
        self.torrent_url = 'https://rocket-hd.cc/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = ["1XBET", "MEGA", "MTZ", "Whistler", "WOTT", "Taylor.D", "HELD", "FSX", "FuN", "MagicX", "w00t", "PaTroL", "BB", "266ers", "GTF", "JellyfinPlex", "2BA"]
        pass

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    ###############################################################
    ######   STOP HERE UNLESS EXTRA MODIFICATION IS NEEDED   ###### noqa E266
    ###############################################################

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        name = await self.edit_name(meta)
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name':name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
        if meta.get('freeleech', 0) != 0:
            data['free'] = meta.get('freeleech', 0)
        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        # === Minimum Size Check: Enforce MB/min requirement ===
        try:
            bit_per_s = int(meta.get('mediainfo').get('media', {}).get('track', [])[0].get('OverallBitRate'))

            if not bit_per_s:
                raise ValueError("Missing 'OverallBitRate' in mediainfo.")

            mb_per_min = bit_per_s * 60 / (8 * 10**6)

            if meta['debug']:
                print(f"MB/min: {mb_per_min:.2f} MB/min")

            if meta.get('type') == 'WEBDL' and mb_per_min < 12.5:
                console.print(f"[bold red]ERROR:[/bold red] WEB release too small: {mb_per_min:.2f} MB/min (< 12.5 MB/min)")
                return
            elif meta.get('type') == 'ENCODE' and mb_per_min < 20:
                console.print(f"[bold red]ERROR:[/bold red] ENCODE release too small: {mb_per_min:.2f} MB/min (< 20 MB/min)")
                return
        except Exception as e:
            console.print(f"[yellow]MB/min check skipped:[/yellow] {e}")

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), self.torrent_url + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    def get_language_tag(self, meta):
        audio_languages = []
        text_languages = []
        lang_tag = ""
        audio_codec = ""
        ignored_keywords = ["commentary", "music", "director", "cast", "party"]
        german_language_codes = ["de", "deu", "ger"]
        english_language_codes = ["en", "eng"]

        if meta['is_disc'] != "BDMV":
            with open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json", 'r',
                      encoding='utf-8') as f:
                mi = json.load(f)

            german_audio_tracks = []
            for track in mi['media']['track']:
                if track.get('@type') == 'Audio':
                    title = track.get('Title', '').lower()
                    if not any(keyword in title for keyword in ignored_keywords):
                        language = track.get('Language', '').lower()
                        if language:
                            audio_languages.append(language)
                            if language in german_language_codes:
                                channels = track.get('Channels', '0')
                                format_str = track.get('Format', '')
                                if format_str == 'DTS XLL':
                                    format_str = 'DTS HD-MA'
                                elif format_str == 'MLP FBA':
                                    format_str = 'TrueHD'
                                elif format_str == 'E-AC-3':
                                    format_str = 'DDP'
                                elif format_str == 'AC-3':
                                    format_str = 'DD'
                                channel_notation = {'6': '5.1', '8': '7.1'}.get(channels,
                                                                                f"{channels}.0")
                                codec = f"{format_str} {channel_notation}"
                                german_audio_tracks.append(
                                    {'codec': codec, 'channels': int(channels)})
                elif track.get('@type') == 'Text':
                    language = track.get('Language', '').lower()
                    if language:
                        text_languages.append(language)

            # Select German track with most channels
            if german_audio_tracks:
                audio_codec = max(german_audio_tracks, key=lambda x: x['channels'])['codec']

        else:
            with open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00", 'r',
                      encoding='utf-8') as f:
                bd_summary = f.read()

            # Extract audio and subtitle languages
            audio_languages = re.findall(r"Audio:\s*([^/]+)", bd_summary, re.IGNORECASE)
            subtitle_languages = re.findall(r"Subtitle:\s*([^/]+)", bd_summary, re.IGNORECASE)
            audio_languages = [lang.strip().lower() for lang in
                               audio_languages] if audio_languages else []
            text_languages = [lang.strip().lower() for lang in
                              subtitle_languages] if subtitle_languages else []

            # Extract German audio codec
            german_audio_tracks = []
            for line in bd_summary.split('\n'):
                if 'Audio:' in line and 'German' in line:
                    match = re.search(r"Audio:.*?/ ([^/]+) / (\d\.\d)", line, re.IGNORECASE)
                    if match:
                        format_str, channel_notation = match.groups()
                        format_str = format_str.strip()
                        if format_str == 'DTS-HD Master Audio':
                            format_str = 'DTS HD-MA'
                        elif format_str == 'Dolby Digital Plus':
                            format_str = 'DDP'
                        elif format_str == 'Dolby Digital':
                            format_str = 'DD'
                        channels = 6 if channel_notation == '5.1' else 8 if channel_notation == '7.1' else 2 if channel_notation == '2.0' else '1.0'
                        codec = f"{format_str} {channel_notation}"
                        german_audio_tracks.append({'codec': codec, 'channels': channels})

            # Select German track with most channels
            if german_audio_tracks:
                audio_codec = max(german_audio_tracks, key=lambda x: x['channels'])['codec']

        has_german_audio = any(code in german_language_codes for code in audio_languages)
        has_english_audio = any(code in english_language_codes for code in audio_languages)
        has_german_subtitles = any(code in german_language_codes for code in text_languages)
        distinct_audio_languages = set(audio_languages)  # Remove duplicates

        if not has_german_audio:
            console.print("[yellow]WARN: No german track found. This is only allowed for requested media.", default=False)

        if has_german_audio and len(distinct_audio_languages) == 1:
            lang_tag = "GERMAN"
        elif has_german_audio and len(distinct_audio_languages) == 2:
            lang_tag = "GERMAN DL"
        elif has_german_audio and len(distinct_audio_languages) > 2:
            lang_tag = "GERMAN ML"
        elif not has_german_audio and has_german_subtitles:
            lang_tag = "GERMAN SUBBED"
        elif not has_german_audio and not has_german_subtitles and has_english_audio:
            lang_tag = "ENGLISH"

        return lang_tag, audio_codec

    async def edit_name(self, meta):
        rhd_name = meta.get('name', '')

        lang_tag, audio_codec = self.get_language_tag(meta)

        # Replace audio with German audio_codec
        if meta.get('audio') and audio_codec:
            rhd_name = rhd_name.replace(meta['audio'], audio_codec)

        _known = {
            part.upper()
            for part in [meta.get('cut'),
                         meta.get('edition'),
                         meta.get('ratio'),
                         meta.get('repack'),
                         meta.get('resolution') if meta.get('resolution') != "OTHER" else "",
                         meta.get('source'),
                         meta.get('uhd')
                         ]
            if part
        }

        if lang_tag:
            name_parts = rhd_name.split()
            existing_lang_tags = {"GERMAN", "GERMAN DL", "GERMAN ML", "GERMAN SUBBED"}
            name_parts = [part for part in name_parts if part.upper() not in existing_lang_tags]

            insert_index = next(
                (i for i, part in enumerate(name_parts) if part.upper() in _known),
                len(name_parts)
            )
            name_parts.insert(insert_index, lang_tag)
            rhd_name = ' '.join(name_parts)

        if lang_tag == "GERMAN DL":
            rhd_name = rhd_name.replace("Dual-Audio ", "")

        if not meta.get('tag') and not (
                rhd_name.endswith("-NOGRP") or rhd_name.endswith("-NOGROUP")):
            rhd_name += " -NOGRP"

        return ' '.join(rhd_name.split())

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        result = [each][0]['attributes']['name']
                        dupes.append(result)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes
