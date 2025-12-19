# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import base64
import glob
import httpx
import os
import re
import unicodedata
from .COMMON import COMMON
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language


class SPD:
    def __init__(self, config):
        self.url = "https://speedapp.io"
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'SPD'
        self.source_flag = "speedapp.io"
        self.upload_url = 'https://speedapp.io/api/upload'
        self.torrent_url = 'https://speedapp.io/browse/'
        self.banned_groups = []
        self.banned_url = 'https://speedapp.io/api/torrent/release-group/blacklist'
        self.session = httpx.AsyncClient(headers={
            'User-Agent': "Upload Assistant",
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'],
        }, timeout=30.0)

    async def get_cat_id(self, meta):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        langs = [lang.lower() for lang in meta.get('subtitle_languages', []) + meta.get('audio_languages', [])]
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
        results = []
        search_url = 'https://speedapp.io/api/torrent'

        params = {}
        if meta.get('imdb_id', 0) != 0:
            params['imdbId'] = f"{meta.get('imdb_info', {}).get('imdbID', '')}"
        else:
            search_title = meta['title'].replace(':', '').replace("'", '').replace(',', '')
            params['search'] = search_title

        try:
            response = await self.session.get(url=search_url, params=params, headers=self.session.headers)

            if response.status_code == 200:
                data = response.json()
                for each in data:
                    name = each.get('name')
                    size = each.get('size')
                    link = f'{self.torrent_url}{each.get("id")}/'

                    if name:
                        results.append({
                            'name': name,
                            'size': size,
                            'link': link
                        })
                return results
            else:
                console.print(f'[bold red]HTTP request failed. Status: {response.status_code}')

        except Exception as e:
            console.print(f'[bold red]Unexpected error: {e}')
            console.print_exception()

        return results

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
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        user_description = await builder.get_user_description(meta)
        title, episode_image, episode_overview = await builder.get_tv_info(meta, self.tracker, resize=True)
        if user_description or episode_overview:  # Avoid unnecessary descriptions
            # Custom Header
            desc_parts.append(await builder.get_custom_header(self.tracker))

            # Logo
            logo_resize_url = meta.get('tmdb_logo', '')
            if logo_resize_url:
                desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

            # TV
            if episode_overview:
                desc_parts.append(f'[center]{title}[/center]')

                if episode_image:
                    desc_parts.append(f"[center][img]{episode_image}[/img][/center]")

                desc_parts.append(f'[center]{episode_overview}[/center]')

            # User description
            desc_parts.append(user_description)

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        # Signature
        desc_parts.append(f"[url=https://github.com/Audionut/Upload-Assistant]{meta['ua_signature']}[/url]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_img_resize(description)
        description = bbcode.convert_named_spoiler_to_normal_spoiler(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def edit_name(self, meta):
        torrent_name = meta['name']

        name = torrent_name.replace(':', ' -')
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = re.sub(r'[\\/*?"<>|]', '', name)

        return re.sub(r"\s{2,}", " ", name)

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
            'url': str(meta.get('imdb_info', {}).get('imdb_url', '')),
        }

        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        data['file'] = await self.encode_to_base64(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent")
        if meta['debug'] is True:
            data['file'] = data['file'][:50] + '...[DEBUG MODE]'
            data['nfo'] = data['nfo'][:50] + '...[DEBUG MODE]'

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
            try:
                response = await self.session.post(url=self.upload_url, json=data, headers=self.session.headers)
                response.raise_for_status()
                response = response.json()
                if response.get('status') is True and response.get('error') is False:
                    status_message = "Torrent uploaded successfully."

                    if 'downloadUrl' in response:
                        torrent_id = str(response.get('torrent', {}).get('id', ''))
                        if torrent_id:
                            meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                        download_url = f"{self.url}/api/torrent/{torrent_id}/download"
                        await self.common.add_tracker_torrent(
                            meta,
                            tracker=self.tracker,
                            source_flag=None,
                            new_tracker=None,
                            comment=None,
                            headers={'Authorization': self.config['TRACKERS'][self.tracker]['api_key']},
                            downurl=download_url
                        )

                    else:
                        console.print("[bold red]No downloadUrl in response.")
                        console.print("[bold red]Confirm it uploaded correctly and try to download manually")
                        console.print(response)

                else:
                    status_message = f'data error: {response}'

            except httpx.HTTPStatusError as e:
                status_message = f'data error: HTTP {e.response.status_code} - {e.response.text}'
            except httpx.TimeoutException:
                status_message = f'data error: Request timed out after {self.session.timeout.write} seconds'
            except httpx.RequestError as e:
                status_message = f'data error: Unable to upload. Error: {e}.\nResponse: {response}'
            except Exception as e:
                status_message = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {response}'
                return

        else:
            console.print(data)
            status_message = "Debug mode enabled, not uploading."

        meta['tracker_status'][self.tracker]['status_message'] = status_message
