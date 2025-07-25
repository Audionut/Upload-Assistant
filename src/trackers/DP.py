# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import glob
import os
from src.trackers.COMMON import COMMON
from src.console import console
from data.config import config
from src.languages import process_desc_language


class DP():
    def __init__(self, config):
        self.config = config
        self.tracker = 'DP'
        self.source_flag = 'DarkPeers'
        self.upload_url = 'https://darkpeers.org/api/torrents/upload'
        self.search_url = 'https://darkpeers.org/api/torrents/filter'
        self.torrent_url = 'https://darkpeers.org/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [
            'aXXo', 'BONE', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'dAV1nci', 'DNL', 'FaNGDiNG0', 'GalaxyTV', 'HD2DVD', 'HDT', 'HDTime',
            'iHYTECH', 'ION10', 'iPlanet', 'KiNGDOM', 'LAMA', 'MeGusta', 'mHD', 'mSD', 'NaNi', 'NhaNc3', 'nHD', 'nikt0', 'nSD',
            'OFT', 'PRODJi', 'RARBG', 'Rifftrax', 'SANTi', 'SasukeducK', 'SEEDSTER', 'ShAaNiG', 'Sicario', 'STUTTERSHIT', 'TAoE',
            'TGALAXY', 'TGx', 'TORRENTGALAXY', 'ToVaR', 'TSP', 'TSPxL', 'ViSION', 'VXT', 'WAF', 'WKS', 'X0r', 'YIFY', 'YTS',
            ['EVO', 'web-dl Only']
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

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        modq = await self.get_flag(meta, 'modq')
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        if meta.get('logo', "") == "":
            from src.tmdb import get_logo
            TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id = meta.get('tmdb')
            category = meta.get('category')
            debug = meta.get('debug')
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            logo_path = await get_logo(tmdb_id, category, debug, logo_languages=logo_languages, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)
            if logo_path:
                meta['logo'] = logo_path
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        region_id = await common.unit3d_region_ids(meta.get('region'))
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
            'name': meta['name'],
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
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), self.torrent_url + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def search_existing(self, meta, disctype):
        if not meta['is_disc'] == "BDMV":
            if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            nordic_languages = ['Danish', 'Swedish', 'Norwegian', 'Icelandic', 'Finnish', 'English']
            if not any(lang in meta.get('audio_languages', []) for lang in nordic_languages) and not any(lang in meta.get('subtitle_languages', []) for lang in nordic_languages):
                if not meta['unattended']:
                    console.print('[bold red]DP requires at least one Nordic/English audio or subtitle track.')
                meta['skipping'] = "DP"
                return

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

        if meta['type'] == "ENCODE" and meta.get('tag', "") and 'fgt' in meta['tag'].lower() and len(dupes) > 0:
            if not meta['unattended']:
                console.print("[bold red]DP does not allow FGT encodes, skipping upload.")
            meta['skipping'] = "DP"
            return []

        return dupes
