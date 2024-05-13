# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from difflib import SequenceMatcher
from str2bool import str2bool
import json
import os
import platform

from src.trackers.COMMON import COMMON
from src.console import console

class STT():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'STT'
        self.source_flag = 'STT'
        self.search_url = 'https://skipthetrailers.xyz/api/torrents/filter'
        self.upload_url = 'https://skipthetrailers.xyz/api/torrents/upload'
        self.signature = '\n[center][url=https://skipthetrailers.xyz/pages/1]Please Seed[/url][/center]'
        self.banned_groups = [""]
        pass
    
    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        stt_name = await self.edit_name(meta)
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) == False:
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
        files = {'torrent': open_torrent}
        data = {
            'name' : stt_name,
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
        headers = {
            'User-Agent': f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) == True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
                
        if meta.get('category') == "TV":
            console.print('[bold red]This site only ALLOWS Movies.')
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
        open_torrent.close()



    async def edit_name(self, meta):
        stt_name = meta['name']
        return stt_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type):
        type_id = {
            'DISC': '1', 
            'REMUX': '2',
            'WEBDL': '4', 
            'WEBRIP': '5', 
            'FANRES': '6',
            'ENCODE': '3'
            }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            # '8640p':'10', 
            '4320p': '1', 
            '2160p': '2', 
            # '1440p' : '3',
            '1080p': '3',
            '1080i': '4',
             '720p': '5',
             '576p': '6',
             '576i': '7',
             '480p': '8',
             '480i': '9'
            }.get(resolution, '11')
        return resolution_id


    async def search_existing(self, meta):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        params = {
            'api_token' : self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId' : meta['tmdb'],
            'categories[]' : await self.get_cat_id(meta['category']),
            'types[]' : await self.get_type_id(meta['type']),
            'resolutions[]' : await self.get_res_id(meta['resolution']),
            'name' : ""
        }
        if meta['category'] == 'TV':
            console.print('[bold red]Unable to search site for TV as this site only ALLOWS Movies.')
        #     params['name'] = f"{meta.get('season', '')}{meta.get('episode', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + meta['edition']
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