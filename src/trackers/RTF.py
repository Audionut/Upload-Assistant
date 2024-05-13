# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import base64
import re
import datetime
import json

from src.trackers.COMMON import COMMON
from src.console import console

class RTF():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    ###############################################################
    ########                    EDIT ME                    ########
    ###############################################################
    def __init__(self, config):
        self.config = config
        self.tracker = 'RTF'
        self.source_flag = 'sunshine'
        self.upload_url = 'https://retroflix.club/api/upload'
        self.search_url = 'https://retroflix.club/api/torrent'
        self.forum_link = 'https://retroflix.club/forums.php?action=viewtopic&topicid=3619'
        self.banned_groups = []
        pass

    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.forum_link)
        if meta['bdinfo'] != None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None

        screenshots = []
        for image in meta['image_list']:
            if image['raw_url'] != None:
                screenshots.append(image['raw_url'])

        json_data = {
            'name' : meta['name'],
            # description does not work for some reason
            # 'description' : meta['overview'] + "\n\n" + desc + "\n\n" + "Uploaded by L4G Upload Assistant",
            'description': "this is a description",
            # editing mediainfo so that instead of 1 080p its 1,080p as site mediainfo parser wont work other wise.
            'mediaInfo': re.sub(r"(\d+)\s+(\d+)", r"\1,\2", mi_dump) if bd_dump == None else f"{bd_dump}",
            "nfo": "",
            "url": "https://www.imdb.com/title/" + (meta['imdb_id'] if str(meta['imdb_id']).startswith("tt") else "tt" + meta['imdb_id']) + "/",
            # auto pulled from IMDB
            "descr": "This is short description",
            "poster": meta["poster"] if meta["poster"] != None else "",
            "type": "401" if meta['category'] == 'MOVIE'else "402",
            "screenshots": screenshots,
            'isAnonymous': self.config['TRACKERS'][self.tracker]["anon"],
        }

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb') as binary_file:
            binary_file_data = binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            base64_message = base64_encoded_data.decode('utf-8')
            json_data['file'] = base64_message

        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }


        if datetime.date.today().year - meta['year'] <= 9:
            console.print(f"[red]ERROR: Not uploading!\nMust be older than 10 Years as per rules")
            return


        if meta['debug'] == False:
            response = requests.post(url=self.upload_url, json=json_data, headers=headers)
            try:
                console.print(response.json())

                t_id = response.json()['torrent']['id']
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://retroflix.club/browse/t/" + str(t_id))

            except:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print(f"[cyan]Request Data:")
            console.print(json_data)


    async def search_existing(self, meta):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        params = {
            'includingDead' : '1'
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
        except:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes

    # tests if API key valid site API key expires every week so a new one has to be generated.
    async def api_test(self, meta):
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        response = requests.get('https://retroflix.club/api/test', headers=headers)

        if response.status_code != 200:
            console.print('[bold red]Your API key is incorrect SO generating a new one')
            await self.generate_new_api(meta)
        else:
            return

    async def generate_new_api(self, meta):
        headers = {
            'accept': 'application/json',
        }

        json_data = {
            'username': self.config['TRACKERS'][self.tracker]['username'],
            'password': self.config['TRACKERS'][self.tracker]['password'],
        }

        response = requests.post('https://retroflix.club/api/login', headers=headers, json=json_data)

        if response.status_code == 201:
            console.print('[bold green]Using New API key generated for this upload')
            console.print(f'[bold green]Please update your L4G config with the below RTF API Key for future uploads')
            console.print(f'[bold yellow]{response.json()["token"]}')
            self.config['TRACKERS'][self.tracker]['api_key'] = response.json()["token"]
        else:
            console.print(f'[bold red]Error getting new API key got error code {response.status_code}, Please check username and password in config')
