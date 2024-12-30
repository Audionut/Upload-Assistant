# -*- coding: utf-8 -*-
# import discord
import asyncio
import platform
from str2bool import str2bool
import os
import aiofiles
import httpx
from src.trackers.COMMON import COMMON
from src.console import console


class ULCX():

    def __init__(self, config):
        self.config = config
        self.tracker = 'ULCX'
        self.source_flag = 'ULCX'
        self.upload_url = 'https://upload.cx/api/torrents/upload'
        self.search_url = 'https://upload.cx/api/torrents/filter'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = ['Tigole', 'x0r', 'Judas', 'SPDVD', 'MeGusta', 'YIFY', 'SWTYBLZ', 'TAoE', 'TSP', 'TSPxL', 'LAMA', '4K4U',
                              'ION10', 'Will1869', 'TGx', 'Sicario', 'QxR', 'Hi10', 'EMBER', 'FGT', 'AROMA', 'd3g', 'nikt0', 'Grym',
                              'RARBG', 'iVy', 'FnP', 'EDGE2020', 'NuBz', 'NAHOM', 'Ralphy']
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
        if type not in ['DISC']:
            if resolution not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
                return None
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

    async def file_exists_async(self, file_path):
        try:
            async with aiofiles.open(file_path, 'r'):
                return True
        except FileNotFoundError:
            return False

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'], meta['type'])
        if resolution_id is None:
            console.print("[red]Resolutions below 720p are not supported at ULCX.")
            meta['not_uploading'] = True
            return
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, comparison=True)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) is False:
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as file:
                bd_dump = await file.read()
            mi_dump = None
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as file:
                mi_dump = await file.read()
            bd_dump = None

        desc = None
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8') as file:
            desc = await file.read()

        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        file_exists = await self.file_exists_async(torrent_file_path)
        if not file_exists:
            meta['not_uploading'] = True
            return

        async with aiofiles.open(torrent_file_path, 'rb') as open_torrent:
            file_content = await open_torrent.read()
        files = {'torrent': ('torrent_file.torrent', file_content, 'application/x-bittorrent')}

        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid)
        nfo_files = []
        for file_name in os.listdir(specified_dir_path):
            if file_name.endswith(".nfo"):
                file_path = os.path.join(specified_dir_path, file_name)
                if await self.file_exists_async(file_path):
                    nfo_files.append(file_path)

        nfo_file = None
        if nfo_files:
            async with aiofiles.open(nfo_files[0], 'rb') as file:
                nfo_file = await file.read()

        if nfo_file:
            files['nfo'] = ("nfo_file.nfo", nfo_file, "text/plain")
        data = {
            'name': meta['name'],
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb_id'].replace('tt', ''),
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
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
                    if response.status_code in [200, 201]:
                        response_data = response.json()
                        console.print(response_data)
                        try:
                            t_id = response_data['data'].split(".")[1].split("/")[3]
                            await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://upload.cx/torrents/" + t_id)
                        except KeyError:
                            meta['not_uploading'] = True
                            console.print("[red]Error extracting torrent ID from response data.")
                    else:
                        meta['not_uploading'] = True
                        console.print(f"[red]Unexpected status code: {response.status_code}")
                        console.print(f"[red]Response Content: {response.text}")
                except httpx.RequestError as exc:
                    meta['not_uploading'] = True
                    console.print(f"[red]An error occurred during the request: {exc}")
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        await open_torrent.close()

    async def search_existing(self, meta, disctype):
        if 'concert' in meta['keywords']:
            console.print('[bold red]Concerts not allowed at ULCX.')
            meta['skipping'] = "ULCX"
            return
        dupes = []
        console.print("[yellow]Searching for existing torrents on ULCX...")
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution'], meta['type']),
            'name': ""
        }
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
