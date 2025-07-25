# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import re
import os
from src.trackers.COMMON import COMMON
from src.console import console


class PT():
    def __init__(self, config):
        self.config = config
        self.tracker = 'PT'
        self.source_flag = 'Portugas'
        self.upload_url = 'https://portugas.org/api/torrents/upload'
        self.search_url = 'https://portugas.org/api/torrents/filter'
        self.torrent_url = 'https://portugas.org/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [""]
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
            'WEBRIP': '39',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1440p': '13',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '540p': '11',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def edit_name(self, meta):
        name = meta['name'].replace(' ', '.')

        pt_name = name
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                pt_name = re.sub(f"-{invalid_tag}", "", pt_name, flags=re.IGNORECASE)
            pt_name = f"{pt_name}-NOGROUP"

        return pt_name

    def get_audio(self, meta):
        found_portuguese_audio = False

        if meta.get('is_disc') == "BDMV":
            bdinfo = meta.get('bdinfo', {})
            audio_tracks = bdinfo.get("audio", [])
            if audio_tracks:
                for track in audio_tracks:
                    lang = track.get("language", "")
                    if lang and lang.lower() == "portuguese":
                        found_portuguese_audio = True
                        break

        needs_mediainfo_check = (meta.get('is_disc') != "BDMV") or (meta.get('is_disc') == "BDMV" and not found_portuguese_audio)

        if needs_mediainfo_check:
            base_dir = meta.get('base_dir', '.')
            uuid = meta.get('uuid', 'default_uuid')
            media_info_path = os.path.join(base_dir, 'tmp', uuid, 'MEDIAINFO.txt')

            try:
                if os.path.exists(media_info_path):
                    with open(media_info_path, 'r', encoding='utf-8') as f:
                        media_info_text = f.read()

                    if not found_portuguese_audio:
                        audio_sections = re.findall(r'Audio(?: #\d+)?\s*\n(.*?)(?=\n\n(?:Audio|Video|Text|Menu)|$)', media_info_text, re.DOTALL | re.IGNORECASE)
                        for section in audio_sections:
                            language_match = re.search(r'Language\s*:\s*(.+)', section, re.IGNORECASE)
                            if language_match:
                                lang_raw = language_match.group(1).strip()
                                # Clean "Portuguese (Brazil)" variation.
                                lang_clean = re.sub(r'[/\\].*|\(.*?\)', '', lang_raw).strip()
                                if lang_clean.lower() == "portuguese":
                                    found_portuguese_audio = True
                                    break

            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"ERRO: Falha ao processar MediaInfo para verificar áudio Português: {e}")

        return 1 if found_portuguese_audio else 0

    def get_subtitles(self, meta):
        found_portuguese_subtitle = False

        if meta.get('is_disc') == "BDMV":
            bdinfo = meta.get('bdinfo', {})
            subtitle_tracks = bdinfo.get("subtitles", [])
            if subtitle_tracks:
                found_portuguese_subtitle = False
                for track in subtitle_tracks:
                    if isinstance(track, str) and track.lower() == "portuguese":
                        found_portuguese_subtitle = True
                        break

        needs_mediainfo_check = (meta.get('is_disc') != "BDMV") or (meta.get('is_disc') == "BDMV" and not found_portuguese_subtitle)

        if needs_mediainfo_check:
            base_dir = meta.get('base_dir', '.')
            uuid = meta.get('uuid', 'default_uuid')
            media_info_path = os.path.join(base_dir, 'tmp', uuid, 'MEDIAINFO.txt')

            try:
                if os.path.exists(media_info_path):
                    with open(media_info_path, 'r', encoding='utf-8') as f:
                        media_info_text = f.read()

                    if not found_portuguese_subtitle:
                        text_sections = re.findall(r'Text(?: #\d+)?\s*\n(.*?)(?=\n\n(?:Audio|Video|Text|Menu)|$)', media_info_text, re.DOTALL | re.IGNORECASE)
                        if not text_sections:
                            text_sections = re.findall(r'Subtitle(?: #\d+)?\s*\n(.*?)(?=\n\n(?:Audio|Video|Text|Menu)|$)', media_info_text, re.DOTALL | re.IGNORECASE)

                        for section in text_sections:
                            language_match = re.search(r'Language\s*:\s*(.+)', section, re.IGNORECASE)
                            if language_match:
                                lang_raw = language_match.group(1).strip()
                                # Clean "Portuguese (Brazil)" variation.
                                lang_clean = re.sub(r'[/\\].*|\(.*?\)', '', lang_raw).strip()
                                if lang_clean.lower() == "portuguese":
                                    found_portuguese_subtitle = True
                                    break

            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"ERRO: Falha ao processar MediaInfo para verificar legenda Português: {e}")

        return 1 if found_portuguese_subtitle else 0

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        pt_name = await self.edit_name(meta)
        audio_flag = self.get_audio(meta)
        subtitle_flag = self.get_subtitles(meta)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        # region_id = await common.unit3d_region_ids(meta.get('region'))
        # distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
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
            'name': pt_name,
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
            'audio_pt': audio_flag,
            'legenda_pt': subtitle_flag,
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

        # if region_id != 0:
        #     data['region_id'] = region_id
        # if distributor_id != 0:
        #    data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

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
