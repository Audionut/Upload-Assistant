# -*- coding: utf-8 -*-
# import discord
import asyncio
from torf import Torrent
import requests
from src.console import console
from str2bool import str2bool
from pprint import pprint
import base64
import shutil
import os
import traceback

from src.trackers.COMMON import COMMON


# from pprint import pprint

class SPD():

    def __init__(self, config):
        self.url = "https://speedapp.io"
        self.config = config
        self.tracker = 'SPD'
        self.source_flag = 'speedapp.io'
        self.search_url = 'https://speedapp.io/api/torrent'
        self.upload_url = 'https://speedapp.io/api/upload'
        self.forum_link = 'https://speedapp.io/support/wiki/rules'
        self.banned_groups = ['']
        pass


    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        type_id = ""
        if meta['anime']:
            type_id = '3'
        elif meta['category'] == 'TV':
            if meta['tv_pack']:
                type_id = '41'
            elif meta['sd'] and not meta['tv_pack']:
                type_id = '45'
            # must be hd
            else:
                type_id = '43'
        else:
            if meta['type'] != "DISC" and meta['resolution'] == "2160p":
                type_id = '61'
            else:
                type_id = {
                    'DISC': '17',
                    'REMUX': '8',
                    'WEBDL': '8',
                    'WEBRIP': '8',
                    'HDTV': '8',
                    'SD': '10',
                    'ENCODE': '8'
                }.get(type, '0')

        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) is False:
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] != None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        screenshots = []
        if len(meta['image_list']) != 0:
            for image in meta['image_list']:
                screenshots.append(image['raw_url'])
        data = {
            'name': meta['name'].replace("'", '').replace(': ', '.').replace(':', '.').replace('  ', '.').replace(' ', '.').replace('DD+', 'DDP'),
            'screenshots': screenshots,
            'release_info': f"[center][url={self.forum_link}]Please seed[/url][/center]",
            'media_info': mi_dump,
            'bd_info': bd_dump,
            'type': type_id,
            'url': f"https://www.imdb.com/title/tt{meta['imdb_id']}",
            'shortDescription': meta['genres'],
            'keywords': meta['keywords'],
            'releaseInfo': self.forum_link
        }
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb') as binary_file:
            binary_file_data = binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            base64_message = base64_encoded_data.decode('utf-8')
            data['file'] = base64_message

        headers = {'Authorization': 'Bearer ' + self.config['TRACKERS'][self.tracker]['api_key'].strip() }

        if meta['debug'] == False:
            response = requests.request("POST", url=self.upload_url, json=data, headers=headers)
            try:
                print(response.json())
                # response = {'status': True, 'error': False, 'downloadUrl': '/api/torrent/383435/download', 'torrent': {'id': 383435, 'name': 'name-with-full-stops', 'slug': 'name-with-dashs', 'category_id': 3}}
                #downloading the torrent from site as it adds a tonne of different trackers and the source is different all the time.
                try:
                    # torrent may not dl and may not provide error if machine is under load or network connection usage high.
                    with requests.get(url=self.url + response.json()['downloadUrl'], stream=True, headers=headers) as r:
                        # replacing L4g/torf created torrent so it will be added to the client.
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent",
                                  'wb') as f:
                            shutil.copyfileobj(r.raw, f)
                    # adding as comment link to torrent
                    if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"):
                        new_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent")
                        new_torrent.metainfo['comment'] = f"{self.url}/browse/{response.json()['torrent']['id']}"
                        Torrent.copy(new_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", overwrite=True)
                except:
                    console.print(traceback.print_exc())
                    console.print(f"[red]Unable to Download torrent, try manually")
            except:
                console.print(traceback.print_exc())
                console.print(f"[yellow]Unable to Download torrent, try manually")
                return
        else:
            console.print(f"[cyan]Request Data:")
            pprint(data)


    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '3'
        }.get(category_name, '0')
        return category_id


    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        params = {
            'includingDead': '1'
        }

        if meta['imdb_id'] != "0":
            params['imdbId'] = meta['imdb_id'] if str(meta['imdb_id']).startswith("tt") else "tt" + meta['imdb_id']
        else:
            params['search'] = meta['title'].replace(':', '').replace("'", '').replace(",", '')

        try:
            response = requests.get(url=self.search_url, params=params, headers=headers)
            response = response.json()
            for each in response:
                result = [each][0]['name']
                dupes.append(result)
        except Exception:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes
