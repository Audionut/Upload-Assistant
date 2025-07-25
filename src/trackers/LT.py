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


class LT():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'LT'
        self.source_flag = 'Lat-Team "Poder Latino"'
        self.upload_url = 'https://lat-team.com/api/torrents/upload'
        self.search_url = 'https://lat-team.com/api/torrents/filter'
        self.torrent_url = 'https://lat-team.com/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [""]
        pass

    async def get_cat_id(self, category_name, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIME': '5',
            'TELENOVELAS': '8',
            'Asiáticas & Turcas': '20',
        }.get(category_name, '0')
        # if is anime
        if meta['anime'] is True and category_id == '2':
            category_id = '5'
        # elif is telenovela
        elif category_id == '2' and ("telenovela" in meta['keywords'] or "telenovela" in meta['overview']):
            category_id = '8'
        # if is  TURCAS o Asiáticas
        elif meta["original_language"] in ['ja', 'ko', 'tr'] and category_id == '2' and 'Drama' in meta['genres']:
            category_id = '20'
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

    async def edit_name(self, meta):
        lt_name = meta['name'].replace('Dual-Audio', '').replace('Dubbed', '').replace(meta['aka'], '').replace('  ', ' ').strip()
        if meta['type'] != 'DISC':  # DISC don't have mediainfo
            # Check if is HYBRID (Copied from BLU.py)
            if 'hybrid' in meta.get('uuid').lower():
                if "repack" in meta.get('uuid').lower():
                    lt_name = lt_name.replace('REPACK', 'Hybrid REPACK')
                else:
                    lt_name = lt_name.replace(meta['resolution'], f"Hybrid {meta['resolution']}")
            # Check if original language is "es" if true replace title for AKA if available
            if meta.get('original_language') == 'es' and meta.get('aka') != "":
                lt_name = lt_name.replace(meta.get('title'), meta.get('aka').replace('AKA', '')).strip()
            # Check if audio Spanish exists
            audios = [
                audio for audio in meta['mediainfo']['media']['track'][2:]
                if audio.get('@type') == 'Audio'
                and isinstance(audio.get('Language'), str)
                and audio.get('Language').lower() in {'es-419', 'es', 'es-mx', 'es-ar', 'es-cl', 'es-ve', 'es-bo', 'es-co',
                                                      'es-cr', 'es-do', 'es-ec', 'es-sv', 'es-gt', 'es-hn', 'es-ni', 'es-pa',
                                                      'es-py', 'es-pe', 'es-pr', 'es-uy'}
                and "commentary" not in str(audio.get('Title', '')).lower()
                ]
            if len(audios) > 0:  # If there is at least 1 audio spanish
                lt_name = lt_name
            # if not audio Spanish exists, add "[SUBS]"
            elif not meta.get('tag'):
                lt_name = lt_name + " [SUBS]"
            else:
                lt_name = lt_name.replace(meta['tag'], f" [SUBS]{meta['tag']}")

        return lt_name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'], meta)
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        # region_id = await common.unit3d_region_ids(meta.get('region'))
        # distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        lt_name = await self.edit_name(meta)
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
            'name': lt_name,
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

        # if distributor_id != 0:
        #    data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = int(meta.get('season_int', '0'))
            data['episode_number'] = int(meta.get('episode_int', '0'))
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
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://lat-team.com/torrents/" + t_id)
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
            'categories[]': await self.get_cat_id(meta['category'], meta),
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
