# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import base64
import datetime
import httpx
import re
from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON


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
        self.torrent_url = 'https://retroflix.club/browse/t/'
        self.forum_link = 'https://retroflix.club/forums.php?action=viewtopic&topicid=3619'
        self.banned_groups = []
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await DescriptionBuilder(self.config).unit3d_edit_desc(meta, self.tracker, self.forum_link)
        if meta['bdinfo'] is not None:
            mi_dump = None
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as f:
                bd_dump = await f.read()
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as f:
                mi_dump = await f.read()
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
            "url": str(meta.get('imdb_info', {}).get('imdb_url', '') + '/'),
            # auto pulled from IMDB
            "descr": "This is short description",
            "poster": meta["poster"] if meta["poster"] is not None else "",
            "type": "401" if meta['category'] == 'MOVIE'else "402",
            "screenshots": screenshots,
            'isAnonymous': self.config['TRACKERS'][self.tracker]["anon"],
        }

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb') as binary_file:
            binary_file_data = await binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            base64_message = base64_encoded_data.decode('utf-8')
            json_data['file'] = base64_message

        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        if meta['debug'] is False:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url=self.upload_url, json=json_data, headers=headers)
                    try:
                        response_json = response.json()
                        meta['tracker_status'][self.tracker]['status_message'] = response.json()

                        t_id = response_json['torrent']['id']
                        meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                        await common.add_tracker_torrent(meta, self.tracker, self.source_flag,
                                                         self.config['TRACKERS'][self.tracker].get('announce_url'),
                                                         "https://retroflix.club/browse/t/" + str(t_id))

                    except Exception:
                        console.print("It may have uploaded, go check")
                        return
            except httpx.TimeoutException:
                meta['tracker_status'][self.tracker]['status_message'] = "data error: RTF request timed out while uploading."
            except httpx.RequestError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f"data error: An error occurred while making the request: {e}"
            except Exception:
                meta['tracker_status'][self.tracker]['status_message'] = "data error - It may have uploaded, go check"
                return

        else:
            console.print("[cyan]RTF Request Data:")
            debug_data = json_data.copy()
            if 'file' in debug_data and debug_data['file']:
                debug_data['file'] = debug_data['file'][:10] + '...'
            console.print(debug_data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."

    async def search_existing(self, meta, disctype):
        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            console.print('[bold red]Erotic not allowed at RTF.')
            meta['skipping'] = "RTF"
            return []

        year = meta.get('year')
        # Collect all possible years from different sources
        years = []

        # IMDB end year
        imdb_end_year = meta.get('imdb_info', {}).get('end_year')
        if imdb_end_year:
            years.append(int(imdb_end_year))

        # TVDB episode year
        tvdb_episode_year = meta.get('tvdb_episode_year')
        if tvdb_episode_year:
            years.append(int(tvdb_episode_year))

        # Get most recent aired date from all TVDB episodes
        tvdb_episodes = meta.get('tvdb_episode_data', {}).get('episodes', [])
        if tvdb_episodes:
            for episode in tvdb_episodes:
                aired_date = episode.get('aired', '')
                if aired_date and '-' in aired_date:
                    try:
                        episode_year = int(aired_date.split('-')[0])
                        years.append(episode_year)
                    except (ValueError, IndexError):
                        continue

        # Use the most recent year found, fallback to meta year
        most_recent_year = max(years) if years else year

        # Update year with the most recent year for TV shows
        if meta.get('category') == "TV":
            year = most_recent_year
        if datetime.date.today().year - year <= 9:
            console.print("[red]Content must be older than 10 Years to upload at RTF")
            meta['skipping'] = "RTF"
            return []

        dupes = []
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }
        params = {'includingDead': '1'}

        if meta['imdb_id'] != 0:
            params['imdbId'] = str(meta['imdb_id']) if str(meta['imdb_id']).startswith("tt") else "tt" + str(meta['imdb_id'])
        else:
            params['search'] = meta['title'].replace(':', '').replace("'", '').replace(",", '')

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.search_url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    for each in data:
                        result = {
                            'name': each['name'],
                            'size': each['size'],
                            'files': each['name'],
                            'link': each['url'],
                        }
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

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get('https://retroflix.club/api/test', headers=headers)

                if response.status_code != 200:
                    console.print('[bold red]Your API key is incorrect SO generating a new one')
                    await self.generate_new_api(meta)
                else:
                    return True
        except httpx.RequestError as e:
            console.print(f'[bold red]Error testing API: {str(e)}')
            await self.generate_new_api(meta)
        except Exception as e:
            console.print(f'[bold red]Unexpected error testing API: {str(e)}')
            await self.generate_new_api(meta)

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
                    console.print(f'[bold yellow]{token[:10]}...[/bold yellow]')

                    # Update the in-memory config dictionary
                    self.config['TRACKERS'][self.tracker]['api_key'] = token

                    # Now we update the config file on disk using utf-8 encoding
                    with open(config_path, 'r', encoding='utf-8') as file:
                        config_data = file.read()

                    # Find the RTF tracker and replace the api_key value
                    new_config_data = re.sub(
                        r'("RTF":\s*{[^}]*"api_key":\s*)([\'"])[^\'"]*([\'"])([^\}]*})',
                        rf'\1\2{token}\3\4',
                        config_data
                    )

                    # Write the updated config back to the file
                    with open(config_path, 'w', encoding='utf-8') as file:
                        file.write(new_config_data)

                    console.print(f'[bold green]API Key successfully saved to {config_path}')
                    return True
                else:
                    console.print('[bold red]API response does not contain a token.')
            else:
                console.print(f'[bold red]Error getting new API key: {response.status_code}, please check username and password in the config.')

        except httpx.RequestError as e:
            console.print(f'[bold red]An error occurred while requesting the API: {str(e)}')

        except Exception as e:
            console.print(f'[bold red]An unexpected error occurred: {str(e)}')
