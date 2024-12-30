# -*- coding: utf-8 -*-
# import discord
import asyncio
import base64
import re
import datetime
import httpx
import aiofiles
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
    def __init__(self, config):
        self.config = config
        self.tracker = 'RTF'
        self.source_flag = 'sunshine'
        self.upload_url = 'https://retroflix.club/api/upload'
        self.search_url = 'https://retroflix.club/api/torrent'
        self.forum_link = 'https://retroflix.club/forums.php?action=viewtopic&topicid=3619'
        self.banned_groups = []
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.forum_link)
        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as file:
                bd_dump = await file.read()
            mi_dump = None
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as file:
                mi_dump = await file.read()
            bd_dump = None

        screenshots = []
        for image in meta['image_list']:
            if image['raw_url'] is not None:
                screenshots.append(image['raw_url'])

        json_data = {
            'name': meta['name'],
            # description does not work for some reason
            # 'description' : meta['overview'] + "\n\n" + desc + "\n\n" + "Uploaded by L4G Upload Assistant",
            'description': "this is a description",
            # editing mediainfo so that instead of 1 080p its 1,080p as site mediainfo parser wont work other wise.
            'mediaInfo': re.sub(r"(\d+)\s+(\d+)", r"\1,\2", mi_dump) if bd_dump is None else f"{bd_dump}",
            "nfo": "",
            "url": "https://www.imdb.com/title/" + (meta['imdb_id'] if str(meta['imdb_id']).startswith("tt") else "tt" + meta['imdb_id']) + "/",
            # auto pulled from IMDB
            "descr": "This is short description",
            "poster": meta["poster"] if meta["poster"] is not None else "",
            "type": "401" if meta['category'] == 'MOVIE'else "402",
            "screenshots": screenshots,
            'isAnonymous': self.config['TRACKERS'][self.tracker]["anon"],
        }

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        base64_message = await self.read_and_encode_file(torrent_path)
        json_data['file'] = base64_message

        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        if meta['debug'] is False:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url=self.upload_url, json=json_data, headers=headers)
                    if response.status_code in [200, 201]:
                        response_data = response.json()
                        console.print(response_data)
                        try:
                            t_id = response.json()['torrent']['id']
                            await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://retroflix.club/browse/t/" + str(t_id))
                        except KeyError:
                            meta['not_uploading'] = True
                            console.print("[red]Error extracting torrent ID from response data.")
                    else:
                        meta['not_uploading'] = True
                        console.print(f"[red]Unexpected status code: {response.status_code}")
                        console.print(f"[red]Response Content: {response.text}")
                except httpx.RequestError as exc:
                    meta['not_uploading'] = True
                    console.print(f"[red]An error occurred during the request: {exc}")
        else:
            console.print("[cyan]Request Data:")
            console.print(json_data)

    async def read_and_encode_file(self, torrent_path):
        with open(torrent_path, 'rb') as binary_file:
            binary_file_data = binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            base64_message = base64_encoded_data.decode('utf-8')
        return base64_message

    async def search_existing(self, meta, disctype):
        disallowed_keywords = {'XXX', 'Erotic'}
        if any(keyword in meta['keywords'] for keyword in disallowed_keywords):
            console.print('[bold red]XXX not allowed.')
            meta['skipping'] = "RTF"
            return []

        if datetime.date.today().year - meta['year'] <= 9:
            console.print("[red]Content must be older than 10 Years to upload at RTF")
            meta['skipping'] = "RTF"
            return []

        dupes = []
        console.print("[yellow]Searching for existing torrents on RTF...")
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }
        params = {'includingDead': '1'}

        if meta['imdb_id'] != "0":
            params['imdbId'] = meta['imdb_id'] if str(meta['imdb_id']).startswith("tt") else "tt" + meta['imdb_id']
        else:
            params['search'] = meta['title'].replace(':', '').replace("'", '').replace(",", '')

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.search_url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    for each in data:
                        result = each['name']
                        dupes.append(result)
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()
            await asyncio.sleep(5)

        return dupes

    # Tests if stored API key is valid. Site API key expires every week so a new one has to be generated.
    async def api_test(self, meta):
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get('https://retroflix.club/api/test', headers=headers)

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

        base_dir = meta.get('base_dir', '.')
        config_path = f"{base_dir}/data/config.py"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post('https://retroflix.club/api/login', headers=headers, json=json_data)

            if response.status_code == 201:
                token = response.json().get("token")
                if token:
                    console.print('[bold green]Saving and using New API key generated for this upload')
                    console.print(f'[bold yellow]{token}')

                    # Update the in-memory config dictionary
                    self.config['TRACKERS'][self.tracker]['api_key'] = token

                    # Now we update the config file on disk using utf-8 encoding
                    with open(config_path, 'r', encoding='utf-8') as file:
                        config_data = file.read()

                    # Find the RTF tracker and replace the api_key value
                    new_config_data = re.sub(
                        r'("RTF":\s*{[^}]*"api_key":\s*\')[^\']*(\'[^\}]*})',  # Match the api_key content only between single quotes
                        rf'\1{token}\2',  # Replace only the content inside the quotes without adding extra backslashes
                        config_data
                    )

                    # Write the updated config back to the file
                    with open(config_path, 'w', encoding='utf-8') as file:
                        file.write(new_config_data)

                    console.print(f'[bold green]API Key successfully saved to {config_path}')
                else:
                    console.print('[bold red]API response does not contain a token.')
            else:
                console.print(f'[bold red]Error getting new API key: {response.status_code}, please check username and password in the config.')

        except httpx.RequestError as e:
            console.print(f'[bold red]An error occurred while requesting the API: {str(e)}')

        except Exception as e:
            console.print(f'[bold red]An unexpected error occurred: {str(e)}')
