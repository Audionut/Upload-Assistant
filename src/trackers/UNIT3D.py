# -*- coding: utf-8 -*-
# import discord
import asyncio
import httpx
import platform
import re
from pathlib import Path
from src.trackers.COMMON import COMMON
from src.console import console


class UNIT3D():
    def __init__(self, config, tracker_name):
        self.config = config
        self.tracker = tracker_name
        self.common = COMMON(config)

        tracker_config = self.config['TRACKERS'][self.tracker]
        self.base_url = tracker_config.get('base_url')
        self.announce_url = tracker_config.get('announce_url')
        self.source_flag = tracker_config.get('source_flag')

        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.api_key = self.config['TRACKERS'][self.tracker]['api_key'].strip()
        version = get_local_version()
        self.ua_name = f"Audionut's Upload Assistant{f' {version}' if version else ''}"
        self.signature = f'\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by {self.ua_name}[/url][/center]'
        pass

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.api_key,
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_category_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_resolution_id(meta['resolution']),
            'name': ''
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}"
        if meta.get('edition', '') != '':
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        result = [each][0]['attributes']['name']
                        dupes.append(result)
                else:
                    console.print(f'[bold red]Failed to search torrents. HTTP Status: {response.status_code}')
        except httpx.TimeoutException:
            console.print('[bold red]Request timed out after 10 seconds')
        except httpx.RequestError as e:
            console.print(f'[bold red]Unable to search for existing torrents: {e}')
        except Exception as e:
            console.print(f'[bold red]Unexpected error: {e}')
            await asyncio.sleep(5)

        return dupes

    async def get_name(self, meta):
        return meta['name']

    async def get_description(self, meta):
        await self.common.unit3d_edit_desc(meta, self.tracker, self.signature)
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        return desc

    async def get_mediainfo(self, meta):
        if meta['bdinfo'] is not None:
            mediainfo = None
        else:
            mediainfo = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()

        return mediainfo

    async def get_bdinfo(self, meta):
        if meta['bdinfo'] is not None:
            bdinfo = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            bdinfo = None

        return bdinfo

    async def get_category_id(self, category_name):
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

    async def get_resolution_id(self, resolution):
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

    async def get_anonymous(self, meta):
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1
        return anon

    async def get_additional_data(self, meta):
        data = {}
        # Used to add additional data if needed
        '''
        data = {
            'modq': await self.get_flag(meta, 'modq'),
            'draft': await self.get_flag(meta, 'draft'),
        }
        '''

        return data

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def get_distributor_ids(self, meta):
        distributor = await self.common.unit3d_distributor_ids(meta.get('distributor'))
        return distributor

    async def get_region_id(self, meta):
        region = await self.common.unit3d_region_ids(meta.get('region'))
        return region

    async def get_data(self, meta):
        region_id = await self.get_region_id(meta)
        distributor_id = await self.get_distributor_ids(meta)

        data = {
            'name': await self.get_name(meta),
            'description': await self.get_description(meta),
            'mediainfo': await self.get_mediainfo(meta),
            'bdinfo': await self.get_bdinfo(meta),
            'category_id': await self.get_category_id(meta['category']),
            'type_id': await self.get_type_id(meta['type']),
            'resolution_id': await self.get_resolution_id(meta['resolution']),
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta.get('tvdb_id', 0) if meta['category'] == 'TV' else 0,
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': await self.get_anonymous(meta),
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
            if meta['tag'] != '' and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
        if meta.get('freeleech', 0) != 0:
            data['free'] = meta.get('freeleech', 0)
        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == 'TV':
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')

        data.update(await self.get_additional_data(meta))

        return data

    async def get_additional_files(self, meta):
        # Used to add nfo or other files if needed
        files = {}

        return files

    async def upload(self, meta, disctype):
        data = await self.get_data(meta)
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb') as torrent_file:
            files = {'torrent': torrent_file}
            files.update(await self.get_additional_files(meta))
            headers = {'User-Agent': f'{self.ua_name} ({platform.system()} {platform.release()})'}
            params = {'api_token': self.api_key}

            if meta['debug'] is False:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
                    try:
                        meta['tracker_status'][self.tracker]['status_message'] = response.json()
                        # adding torrent link to comment of torrent file
                        t_id = response.json()['data'].split('.')[1].split('/')[3]
                        meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                        await self.common.add_tracker_torrent(
                            meta,
                            self.tracker,
                            self.source_flag,
                            self.announce_url,
                            self.torrent_url + t_id,
                            headers=headers,
                            params=params,
                            downurl=response.json()['data']
                        )
                    except httpx.TimeoutException:
                        console.print('[bold red]Request timed out after 10 seconds')
                    except httpx.RequestError as e:
                        console.print(f'[bold red]Unable to upload to tracker: {e}')
                    except Exception:
                        console.print('It may have uploaded, go check')
                        return
            else:
                console.print('[cyan]Request Data:')
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = 'Debug mode enabled, not uploading.'


def get_local_version():
    project_root = Path(__file__).resolve().parent.parent.parent
    version_file_path = project_root / 'data' / 'version.py'

    if not version_file_path.is_file():
        return None
    try:
        with open(version_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
            if match:
                return match.group(1)
    except OSError:
        return None

    return None
