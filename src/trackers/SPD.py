# -*- coding: utf-8 -*-
# import discord
import base64
import bencodepy
import glob
import hashlib
import httpx
import os
import re
import unicodedata
from src.languages import process_desc_language
from src.console import console
from .COMMON import COMMON


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
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.session = httpx.AsyncClient(headers={
            'User-Agent': "Audionut's Upload Assistant",
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'],
        }, timeout=30.0)

    async def get_cat_id(self, meta):
        languages = (meta.get('subtitle_languages') or []) + (meta.get('audio_languages') or [])

        if not languages:
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        langs = [lang.lower() for lang in languages]
        romanian = 'romanian' in langs

        if 'RO' in meta.get('origin_country', []):
            if meta.get('category') == 'TV':
                return '60'
            elif meta.get('category') == 'MOVIE':
                return '59'

        # documentary
        if 'documentary' in meta.get("genres", "").lower() or 'documentary' in meta.get("keywords", "").lower():
            return '63' if romanian else '9'

        # anime
        if meta.get('anime'):
            return '3'

        # TV
        if meta.get('category') == 'TV':
            if meta.get('tv_pack'):
                return '66' if romanian else '41'
            elif meta.get('sd'):
                return '46' if romanian else '45'
            return '44' if romanian else '43'

        # MOVIE
        if meta.get('category') == 'MOVIE':
            if meta.get('resolution') == '2160p' and meta.get('type') != 'DISC':
                return '57' if romanian else '61'
            if meta.get('type') in ('REMUX', 'WEBDL', 'WEBRIP', 'HDTV', 'ENCODE'):
                return '29' if romanian else '8'
            if meta.get('type') == 'DISC':
                return '24' if romanian else '17'
            if meta.get('type') == 'SD':
                return '35' if romanian else '10'

        return None

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

        params = {}

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

        # if no channel is specified, use the default
        if not spd_channel:
            return 1

        # return the channel as int if it's already an integer
        if isinstance(spd_channel, int):
            return spd_channel

        # if user enters id as a string number
        if isinstance(spd_channel, str):
            if spd_channel.isdigit():
                return int(spd_channel)
            # if user enter tag then it will use API to search
            else:
                pass

        params = {
            'search': spd_channel
        }

        try:
            response = await self.session.get(url=self.url + '/api/channel', params=params, headers=self.session.headers)

            if response.status_code == 200:
                data = response.json()
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
        desc = re.sub(r"(\[spoiler=[^]]+])", "[spoiler]", desc, flags=re.IGNORECASE)
        desc = re.sub(r'\[img(?:[^\]]*)\]', '[img]', desc, flags=re.IGNORECASE)
        desc = re.sub(r'\n{3,}', '\n\n', desc)

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def edit_name(self, meta):
        torrent_name = meta['name']

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
            self.source_flag = f"speedapp.io-{source_flag}-"
            await self.edit_torrent(meta, self.tracker, self.source_flag)

        return

    async def encode_to_base64(self, file_path):
        with open(file_path, 'rb') as binary_file:
            binary_file_data = binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            return base64_encoded_data.decode('utf-8')

    async def get_nfo(self, meta):
        nfo_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo = await self.encode_to_base64(nfo_files[0])
            return nfo

        return None

    async def fetch_data(self, meta):
        await self.get_source_flag(meta)
        media_info, bd_info = await self.get_file_info(meta)

        data = {
            'bdInfo': bd_info,
            'coverPhotoUrl': meta.get('backdrop', ''),
            'description': meta.get('genres', ''),
            'media_info': media_info,
            'name': await self.edit_name(meta),
            'nfo': await self.get_nfo(meta),
            'plot': meta.get('overview_meta', '') or meta.get('overview', ''),
            'poster': meta.get('poster', ''),
            'technicalDetails': await self.edit_desc(meta),
            'screenshots': await self.get_screenshots(meta),
            'type': await self.get_cat_id(meta),
            'url': f"https://www.imdb.com/title/{meta.get('imdb_info', {}).get('imdbID', '')}",
        }

        if not meta.get('debug', False):
            data['file'] = await self.encode_to_base64(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")

        return data

    async def upload(self, meta, disctype):
        data = await self.fetch_data(meta)

        channel = await self.search_channel(meta)
        if channel is None:
            meta['skipping'] = f"{self.tracker}"
            return
        channel = str(channel)
        data['channel'] = channel

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

                else:
                    console.print("[bold red]No downloadUrl in response.")
                    console.print("[bold red]Confirm it uploaded correctly and try to download manually")
                    console.print(response)

            else:
                console.print(f"[bold red]Failed to upload got status code: {response.status_code}")

        else:
            console.print(data)
            status_message = "Debug mode enabled, not uploading."

        await self.add_tracker_torrent(meta, self.tracker, self.source_flag + channel, self.announce_list, self.torrent_url + torrent_id)

        meta['tracker_status'][self.tracker]['status_message'] = status_message
