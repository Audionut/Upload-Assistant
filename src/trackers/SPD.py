# -*- coding: utf-8 -*-
# import discord
import asyncio
import base64
import bencodepy
import hashlib
import httpx
import os
import unicodedata
import re
from pprint import pprint
from src.console import console
from src.trackers.COMMON import COMMON


class SPD(COMMON):

    def __init__(self, config):
        self.url = "https://speedapp.io"
        self.config = config
        self.tracker = 'SPD'
        self.passkey = self.config['TRACKERS'][self.tracker]['passkey']
        self.upload_url = 'https://speedapp.io/api/upload'
        self.torrent_url = 'https://speedapp.io/browse/'
        self.announce_list = [
            f"http://ramjet.speedapp.io/{self.passkey}/announce",
            f"http://ramjet.speedapp.to/{self.passkey}/announce",
            f"http://ramjet.speedappio.org/{self.passkey}/announce",
            f"https://ramjet.speedapp.io/{self.passkey}/announce",
            f"https://ramjet.speedapp.to/{self.passkey}/announce",
            f"https://ramjet.speedappio.org/{self.passkey}/announce"
        ]
        self.banned_groups = ['']
        self.signature = "Created by Audionut's Upload Assistant"
        self.session = httpx.AsyncClient(headers={
            'User-Agent': "Audionut's Upload Assistant",
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'],
        }, timeout=30.0)

    async def get_cat_id(self, meta):
        category_id = None

        if meta.get('anime'):
            category_id = '3'

        elif meta.get('category') == 'TV':
            if meta.get('tv_pack'):
                category_id = '41'
            elif meta.get('sd'):
                category_id = '45'
            else:
                category_id = '43'

        elif meta.get('category') == 'MOVIE':
            if meta.get('resolution') == '2160p' and meta.get('type') != 'DISC':
                category_id = '61'

            else:
                movie_type_to_id = {
                    'DISC': '17',
                    'REMUX': '8',
                    'WEBDL': '8',
                    'WEBRIP': '8',
                    'HDTV': '8',
                    'ENCODE': '8',
                    'SD': '10',
                }
                category_id = movie_type_to_id.get(meta.get('type'))

        return category_id

    async def get_file_info(self, meta):
        base_path = f"{meta['base_dir']}/tmp/{meta['uuid']}"

        if meta.get('bdinfo'):
            bd_info = open(f"{base_path}/BD_SUMMARY_00.txt", encoding='utf-8').read()
            return None, bd_info
        else:
            media_info = open(f"{base_path}/MEDIAINFO_CLEANPATH.txt", encoding='utf-8').read()
            return media_info, None

    async def get_screenshots(self, meta):
        screenshots = []
        if len(meta['image_list']) != 0:
            for image in meta['image_list']:
                screenshots.append(image['raw_url'])

        return screenshots

    async def search_existing(self, meta, disctype):
        dupes = []

        search_url = 'https://speedapp.io/api/torrent'

        params = {
            'includingDead': '1'
        }

        if meta['imdb_id'] != 0:
            params['imdbId'] = f"{meta.get('imdb_info', {}).get('imdbID', '')}"
        else:
            params['search'] = meta['title'].replace(':', '').replace("'", '').replace(",", '')
        try:
            response = await self.session.get(url=search_url, params=params, headers=self.session.headers)
            if response.status_code == 200:
                data = response.json()
                for each in data:
                    result = each['name']
                    dupes.append(result)
                    return dupes
            else:
                console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes

    async def search_channel(self, meta):
        spd_channel = meta.get('spd_channel', '') or self.config['TRACKERS'][self.tracker].get('channel', '')

        if not spd_channel:
            return 1

        params = {
            'search': spd_channel
        }

        try:
            response = await self.session.get(url=self.url + '/api/channel', params=params, headers=self.session.headers)
            console.print(response)

            if response.status_code == 200:
                data = response.json()
                console.print(data)
                for entry in data:
                    id = entry['id']
                    tag = entry['tag']

                    if id and tag:
                        if tag != spd_channel:
                            console.print(f'[{self.tracker}]: Unable to find a matching channel based on your input. Please check if you entered it correctly.')
                            return
                        else:
                            return id
                    else:
                        console.print(f'[{self.tracker}]: Could not find the channel ID. Please check if you entered it correctly.')

                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        description_parts = []

        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            description_parts.append(manual_desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header)

        if self.signature:
            description_parts.append(self.signature)

        final_description = "\n\n".join(filter(None, description_parts))
        desc = final_description
        desc = re.sub(r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]", r"", desc, flags=re.DOTALL)
        desc = re.sub(r'\[/?.*?\]', '', desc)
        desc = re.sub(r'\n{3,}', '\n\n', desc)

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def edit_name(self, meta):
        is_scene = bool(meta.get('scene_name'))
        torrent_name = meta['scene_name'] if is_scene else meta['name']

        name = torrent_name.replace(':', '-')
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = re.sub(r'[\\/*?"<>|]', '', name)

        return name

    async def get_source_flag(self, meta):
        torrent = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"

        with open(torrent, "rb") as f:
            torrent_data = bencodepy.decode(f.read())
            info = bencodepy.encode(torrent_data[b'info'])
            source_flag = hashlib.sha1(info).hexdigest()
            self.source_flag = f"speedapp.io-{source_flag}"
            await self.edit_torrent(meta, self.tracker, self.source_flag)

        return

    async def fetch_data(self, meta):
        await self.get_source_flag(meta)
        media_info, bd_info = await self.get_file_info(meta)

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent", 'rb') as binary_file:
            binary_file_data = binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            base64_message = base64_encoded_data.decode('utf-8')

        data = {
            'bdInfo': bd_info,
            'coverPhotoUrl': meta.get('backdrop', ''),
            'description': meta.get('genres', ''),
            'media_info': media_info,
            'name': await self.edit_name(meta),
            'poster': meta.get('poster', ''),
            'releaseInfo': await self.edit_desc(meta),
            'screenshots': await self.get_screenshots(meta),
            'type': await self.get_cat_id(meta),
            'url': f"https://www.imdb.com/title/{meta.get('imdb_info', {}).get('imdbID', '')}",
        }

        if not meta.get('debug', False):
            data['file'] = base64_message

        return data

    async def upload(self, meta, disctype):
        data = await self.fetch_data(meta)

        channel = await self.search_channel(meta)
        if channel is None:
            meta['skipping'] = f"{self.tracker}"
            return
        data['channel'] = "1" if channel == 1 else str(channel)

        status_message = ''
        torrent_id = ''

        if meta['debug'] is False:
            response = await self.session.post(url=self.upload_url, json=data, headers=self.session.headers)

            if response.status_code == 201:

                response = response.json()
                status_message = response

                if 'downloadUrl' in response:
                    torrent_id = str(response.get('torrent', {}).get('id', ''))
                    if torrent_id:
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        # torrent hash changes depending on the channel id
                        # await self.download_torrent(meta, torrent_id)

                else:
                    console.print("[bold red]No downloadUrl in response.")
                    console.print("[bold red]Confirm it uploaded correctly and try to download manually")
                    console.print({response.json()})

            else:
                console.print(f"[bold red]Failed to upload got status code: {response.status_code}")

            await self.add_tracker_torrent(meta, self.tracker, self.source_flag + f"-{channel}", self.announce_list, self.torrent_url + torrent_id)

        else:
            console.print("[cyan]Request Data:")
            pprint(data)
            status_message = "Debug mode enabled, not uploading."

        meta['tracker_status'][self.tracker]['status_message'] = status_message

    async def download_torrent(self, meta, torrent_id):
        url = f"{self.url}/api/torrent/{torrent_id}/download"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        async with httpx.AsyncClient(headers=self.session.headers, timeout=None) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(torrent_path, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
