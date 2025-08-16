# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import os
import glob
import httpx
from src.trackers.COMMON import COMMON
from src.console import console


class R4E():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'R4E'
        self.source_flag = 'R4E'
        # self.signature = f"\n[center][url=https://github.com/L4GSP1KE/Upload-Assistant]Created by L4G's Upload Assistant[/url][/center]"
        self.signature = None
        self.banned_groups = [""]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'], meta['tmdb'], meta)
        type_id = await self.get_type_id(meta['resolution'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        name = await self.edit_name(meta)
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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[R4E]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[R4E].torrent", 'rb')
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
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            # 'personal_release' : int(meta.get('personalrelease', False)), NOT IMPLEMENTED on R4E
            # 'internal' : 0,
            # 'featured' : 0,
            # 'free' : 0,
            # 'double_up' : 0,
            # 'sticky' : 0,
        }
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        url = f"https://racing4everyone.eu/api/torrents/upload?api_token={self.config['TRACKERS']['R4E']['api_key'].strip()}"
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        if meta['debug'] is False:
            response = requests.post(url=url, files=files, data=data, headers=headers)
            try:

                meta['tracker_status'][self.tracker]['status_message'] = response.json()
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def edit_name(self, meta):
        name = meta['name']
        return name

    async def get_cat_id(self, category_name, tmdb_id, meta):
        # Use stored genre IDs if available
        if meta and meta.get('genre_ids'):
            genre_ids = meta['genre_ids'].split(',')
            is_docu = '99' in genre_ids

            if category_name == 'MOVIE':
                category_id = '70'  # Motorsports Movie
                if is_docu:
                    category_id = '66'  # Documentary
            elif category_name == 'TV':
                category_id = '79'  # TV Series
                if is_docu:
                    category_id = '2'  # TV Documentary
            else:
                category_id = '24'

        return category_id

    async def get_type_id(self, type):
        type_id = {
            '8640p': '2160p',
            '4320p': '2160p',
            '2160p': '2160p',
            '1440p': '1080p',
            '1080p': '1080p',
            '1080i': '1080i',
            '720p': '720p',
            '576p': 'SD',
            '576i': 'SD',
            '480p': 'SD',
            '480i': 'SD'
        }.get(type, '10')
        return type_id

    async def is_docu(self, genres):
        is_docu = False
        for each in genres:
            if each['id'] == 99:
                is_docu = True
        return is_docu

    async def search_existing(self, meta, disctype):
        dupes = []
        url = "https://racing4everyone.eu/api/torrents/filter"
        params = {
            'api_token': self.config['TRACKERS']['R4E']['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + meta['edition']
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=url, params=params)
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
