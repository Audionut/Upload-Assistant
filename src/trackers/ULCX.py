# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import os
import glob
import httpx
import cli_ui
from src.trackers.COMMON import COMMON
from src.console import console
from src.languages import process_desc_language, has_english_language


class ULCX():

    def __init__(self, config):
        self.config = config
        self.tracker = 'ULCX'
        self.source_flag = 'ULCX'
        self.upload_url = 'https://upload.cx/api/torrents/upload'
        self.search_url = 'https://upload.cx/api/torrents/filter'
        self.torrent_url = 'https://upload.cx/torrents/'
        self.id_url = 'https://upload.cx/api/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [
            '4K4U', 'AROMA', 'd3g', ['EDGE2020', 'Encodes'], 'EMBER', 'FGT', 'FnP', 'FRDS', 'Grym', 'Hi10', 'iAHD', 'INFINITY',
            'ION10', 'iVy', 'Judas', 'LAMA', 'MeGusta', 'NAHOM', 'Niblets', 'nikt0', ['NuBz', 'Encodes'], 'OFT', 'QxR',
            ['Ralphy', 'Encodes'], 'RARBG', 'Sicario', 'SM737', 'SPDVD', 'SWTYBLZ', 'TAoE', 'TGx', 'Tigole', 'TSP',
            'TSPxL', 'VXT', 'Vyndros', 'Will1869', 'x0r', 'YIFY', 'Alcaide_Kira'
        ]
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

    async def get_res_id(self, resolution, type):
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

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        modq = await self.get_flag(meta, 'modq')
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'], meta['type'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, comparison=True)
        should_skip = meta['tracker_status'][self.tracker].get('skip_upload', False)
        if should_skip:
            meta['tracker_status'][self.tracker]['status_message'] = "data error: ulcx_no_language"
            return
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        name, region_id, distributor_id = await self.edit_name(meta, region_id, distributor_id)
        if region_id == "SKIPPED" or distributor_id == "SKIPPED":
            console.print("Region or Distributor ID not found; skipping ULCX upload.")
            return
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
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        open_torrent = open(torrent_file_path, 'rb')
        files = {'torrent': open_torrent}
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)
        nfo_file = None
        if nfo_files:
            nfo_file = open(nfo_files[0], 'rb')
        if nfo_file:
            files['nfo'] = ("nfo_file.nfo", nfo_file, "text/plain")
        data = {
            'name': name,
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
            'mod_queue_opt_in': modq,
            'sticky': 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
        if meta.get('freeleech', 0) != 0:
            data['free'] = meta.get('freeleech', 0)
        if meta['is_disc'] == "BDMV":
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

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://upload.cx/torrents/" + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def edit_name(self, meta, region_id, distributor_id):
        common = COMMON(config=self.config)
        ulcx_name = meta['name']
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        year = str(meta.get('year', ""))
        ulcx_name = ulcx_name.replace(f"{meta['title']}", imdb_name, 1)
        if not meta.get('category') == "TV":
            ulcx_name = ulcx_name.replace(f"{year}", imdb_year, 1)
        if meta.get('mal_id', 0) != 0 and meta.get('aka', "") != "":
            ulcx_name = ulcx_name.replace(f"{meta['aka']}", "", 1)
        if meta.get('is_disc') == "BDMV":
            if not region_id:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    region_name = cli_ui.ask_string("ULCX: Region code not found for disc. Please enter it manually (UPPERCASE): ")
                    region_id = await common.unit3d_region_ids(region_name)
                    if not meta.get('edition', ""):
                        ulcx_name = ulcx_name.replace(f"{meta['resolution']}", f"{meta['resolution']} {region_name}", 1)
                    else:
                        ulcx_name = ulcx_name.replace(f"{meta['resolution']} {meta['edition']}", f"{meta['resolution']} {meta['edition']} {region_name}", 1)
                else:
                    region_id = "SKIPPED"
            if not distributor_id:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    distributor_name = cli_ui.ask_string("ULCX: Distributor code not found for disc. Please enter it manually (UPPERCASE): ")
                    distributor_id = await common.unit3d_distributor_ids(distributor_name)
                else:
                    distributor_id = "SKIPPED"

        return ulcx_name, region_id, distributor_id

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def search_existing(self, meta, disctype):
        if 'concert' in meta['keywords']:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                console.print('[bold red]Concerts not allowed at ULCX.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = "ULCX"
                    return
            else:
                meta['skipping'] = "ULCX"
                return
        if meta['video_codec'] == "HEVC" and meta['resolution'] != "2160p" and 'animation' not in meta['keywords'] and meta.get('anime', False) is not True:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                console.print('[bold red]This content might not fit HEVC rules for ULCX.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = "ULCX"
                    return
            else:
                meta['skipping'] = "ULCX"
                return
        if meta['type'] == "ENCODE" and meta['resolution'] not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
            if not meta['unattended']:
                console.print('[bold red]Encodes must be at least 720p resolution for ULCX.')
            meta['skipping'] = "ULCX"
            return
        if meta['bloated'] is True:
            console.print("[bold red]Non-English dub not allowed at ULCX[/bold red]")
            meta['skipping'] = "ULCX"
            return []

        if not meta['is_disc'] == "BDMV":
            if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            if not await has_english_language(meta.get('audio_languages')) and not await has_english_language(meta.get('subtitle_languages')):
                if not meta['unattended']:
                    console.print('[bold red]ULCX requires at least one English audio or subtitle track.')
                meta['skipping'] = "ULCX"
                return

        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution'], meta['type']),
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
                        attributes = each['attributes']
                        result = {
                            'name': attributes['name'],
                            'size': attributes['size']
                        }
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
