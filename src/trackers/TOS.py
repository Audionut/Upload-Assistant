import asyncio
import requests
import distutils.util
import os
import platform

from src.trackers.COMMON import COMMON
from src.console import console


class TOS():

    def __init__(self, config):
        self.config = config
        self.tracker = 'TOS'
        self.source_flag = 'TheOldSchool'
        self.upload_url = 'https://theoldschool.cc/api/torrents/upload'
        self.search_url = 'https://theoldschool.cc/api/torrents/filter'
        self.signature = ' '
        self.banned_groups = [""]
        pass

    async def get_cat_id(self, meta, category_name):
        if ".vostfr." in meta['uuid'].lower() or ".subfrench." in meta['uuid'].lower():
            if category_name == "TV" and meta['tv_pack']:
                category_id = '9'
            else:
                category_id = {
                    'MOVIE': '6',
                    'TV': '7'
                    }.get(category_name, '0')
        else:
            if category_name == "TV" and meta['tv_pack']:
                category_id = '8'
            else:
                category_id = {
                    'MOVIE': '1',
                    'TV': '2'
                    }.get(category_name, '0')
        return category_id

    async def get_type_id(self, meta, type):
        if meta['is_disc'] == "DVD":
            type_id = '7'
        elif meta['3D'] == "3D":
            type_id = '8'
        else:
            type_id = {
                'DISC': '1',
                'REMUX': '2',
                'ENCODE': '3',
                'WEBDL': '4',
                'WEBRIP': '4',
                'HDTV': '6'
                }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            'other':'10', 
            '4320p': '1', 
            '2160p': '2', 
            '1440p' : '3',
            '1080p': '3',
            '1080i':'4', 
            '720p': '5',  
            '576p': '6', 
            '576i': '7',
            '480p': '8', 
            '480i': '9'
            }.get(resolution, '10')
        return resolution_id

    async def get_nfo(self, path):
        nfo = None
        if os.path.isdir(path):
            files = list()
            for item in os.scandir(path):
                if item.is_dir():
                    files += [f.path for f in os.scandir(item.path) if f.name.lower().endswith(".nfo")]
                elif item.name.lower().endswith(".nfo"):
                    files.append(item.path)
            if len(files) > 0:
                for item in files:
                    if ".final." in item.lower():
                        nfo = item
                        break
                if not nfo:
                    if len(files) == 1:
                        nfo = files[0]
                    else:
                        nfo = files.sort()[-1]
        return nfo

    ###############################################################
    ######   STOP HERE UNLESS EXTRA MODIFICATION IS NEEDED   ######
    ###############################################################

    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta, meta['category'])
        type_id = await self.get_type_id(meta, meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        meta['nfoFile'] = await self.get_nfo(meta['path'])
        if meta['anon'] == 0 and bool(distutils.util.strtobool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) == False:
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] != None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')
        if meta['nfoFile']:
            open_nfo = open(meta['nfoFile'], 'rb')
            files = {'torrent': open_torrent, 'nfo': open_nfo}
        else:
            files = {'torrent': open_torrent}
        name = meta['uuid']
        # retire l'extension de fichier du nom si upload fichier seul
        if not meta['isdir'] and '.' in name.split('-')[-1]:
            name = '.'.join(name.split('.')[:-1])
        data = {
            'name' : name,
            'description' : desc,
            'mediainfo' : mi_dump,
            'bdinfo' : bd_dump, 
            'category_id' : cat_id,
            'type_id' : type_id,
            'resolution_id' : resolution_id,
            'tmdb' : meta['tmdb'],
            'imdb' : meta['imdb_id'].replace('tt', ''),
            'tvdb' : meta['tvdb_id'],
            'mal' : meta['mal_id'],
            'igdb' : 0,
            'anonymous' : anon,
            'stream' : meta['stream'],
            'sd' : meta['sd'],
            'keywords' : meta['keywords'],
            'personal_release' : int(meta.get('personalrelease', False)),
            'internal' : 0,
            'featured' : 0,
            'free' : 0,
            'doubleup' : 0,
            'sticky' : 0,
        }
        # Internal
        if meta['exclusive'] == True or self.config['TRACKERS'][self.tracker].get('exclusive', False) == True:
                data['internal'] = 1

        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0'
        }
        params = {
            'api_token' : self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] == False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                console.print(response.json())
            except:
                console.print("It may have uploaded, go check")
                return 
        else:
            console.print(f"[cyan]Request Data:")
            console.print(data)
        if meta['nfoFile']:
            open_nfo.close()
        open_torrent.close()

    async def search_existing(self, meta):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        params = {
            'api_token' : self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId' : meta['tmdb'],
            'categories[]' : await self.get_cat_id(meta, meta['category']),
            'types[]' : await self.get_type_id(meta, meta['type']),
            'resolutions[]' : await self.get_res_id(meta['resolution']),
            'name' : ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}{meta.get('episode', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            response = requests.get(url=self.search_url, params=params)
            response = response.json()
            for each in response['data']:
                result = [each][0]['attributes']['name']
                # difference = SequenceMatcher(None, meta['clean_name'], result).ratio()
                # if difference >= 0.05:
                dupes.append(result)
        except:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes
