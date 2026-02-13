# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import asyncio
import base64
import datetime
import re
from typing import Any, Optional, cast

import aiofiles
import httpx

from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON


class RTF:
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the RTF tracker handler.

        Args:
            config: Configuration dictionary containing tracker settings and API credentials.
        """
        self.config = config
        self.tracker = 'RTF'
        self.source_flag = 'sunshine'
        self.upload_url = 'https://retroflix.club/api/upload'
        self.search_url = 'https://retroflix.club/api/torrent'
        self.torrent_url = 'https://retroflix.club/browse/t/'
        self.forum_link = 'https://retroflix.club/forums.php?action=viewtopic&topicid=3619'
        self.banned_groups: list[str] = []
        pass

    async def upload(self, meta: dict[str, Any], _disctype: str) -> bool:
        """Upload a torrent to RetroFlix tracker.

        Args:
            meta: Metadata dictionary containing torrent information (name, mediainfo, screenshots, etc.).
            disctype: Type of disc (e.g., 'BD', 'DVD').

        Returns:
            True if upload was successful, False otherwise.
        """
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta, signature=self.forum_link)
        if meta['bdinfo'] is not None:
            mi_dump = None
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", encoding='utf-8') as f:
                bd_dump = await f.read()
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", encoding='utf-8') as f:
                mi_dump = await f.read()
            bd_dump = None

        screenshots = [
            image['raw_url'] for image in meta['image_list'] if image['raw_url'] is not None
        ]

        imdb_url_value = meta.get('imdb_info', {}).get('imdb_url', '')
        imdb_url = str(imdb_url_value) if imdb_url_value else ''
        json_data = {
            'name': meta['name'],
            # description does not work for some reason
            # 'description' : meta['overview'] + "\n\n" + desc + "\n\n" + "Uploaded by L4G Upload Assistant",
            'description': "",
            # editing mediainfo so that instead of 1 080p its 1,080p as site mediainfo parser wont work other wise.
            'mediaInfo': re.sub(r"(\d+)\s+(\d+)", r"\1,\2", mi_dump or "") if bd_dump is None else f"{bd_dump}",
            "nfo": "",
            "url": f"{imdb_url}/" if imdb_url else "",
            # auto pulled from IMDB
            "descr": "",
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
                async with httpx.AsyncClient(timeout=40.0) as client:
                    response = await client.post(url=self.upload_url, json=json_data, headers=headers)

                    # Handle successful upload (201)
                    if response.status_code == 201:
                        try:
                            response_json = response.json()

                            # Check if there's an error in the response despite 201 status
                            if response_json.get('error', False):
                                error_msg = response_json.get('message', 'Unknown error occurred')
                                meta['tracker_status'][self.tracker]['status_message'] = f"Upload error: {error_msg}"
                                return False

                            meta['tracker_status'][self.tracker]['status_message'] = response_json
                            t_id = response_json['torrent']['id']
                            meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                            await common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag,
                                                                      self.config['TRACKERS'][self.tracker].get('announce_url'),
                                                                      "https://retroflix.club/browse/t/" + str(t_id))
                            return True
                        except KeyError as e:
                            meta['tracker_status'][self.tracker]['status_message'] = f"Error parsing response: {response.text}: missing key {e}"
                            return False

                    # Handle error responses
                    elif response.status_code == 400:
                        response_json = response.json()
                        error_msg = response_json.get('message', 'Bad request or torrent file')
                        meta['tracker_status'][self.tracker]['status_message'] = f"Bad request: {error_msg}"
                        return False

                    elif response.status_code == 403:
                        response_json = response.json()
                        error_msg = response_json.get('message', 'You are not allowed to upload')
                        meta['tracker_status'][self.tracker]['status_message'] = f"Permission denied: {error_msg}"
                        return False

                    elif response.status_code == 409:
                        response_json = response.json()
                        error_msg = response_json.get('message', 'Torrent already exists')
                        meta['tracker_status'][self.tracker]['status_message'] = f"Duplicate: {error_msg}"
                        return False

                    elif response.status_code == 413:
                        response_json = response.json()
                        error_msg = response_json.get('message', 'Torrent file is too big or has too many files')
                        meta['tracker_status'][self.tracker]['status_message'] = f"File size error: {error_msg}"
                        return False

                    elif response.status_code == 422:
                        response_json = response.json()
                        error_msg = response_json.get('message', 'Upload rejected based on rules')
                        meta['tracker_status'][self.tracker]['status_message'] = f"Upload rejected: {error_msg}"
                        return False

                    else:
                        # Handle any other status codes
                        try:
                            response_json = response.json()
                            error_msg = response_json.get('message', f'HTTP {response.status_code}')
                        except Exception:
                            error_msg = f'HTTP {response.status_code}: {response.text[:200]}'

                        console.print(f"[bold red]Unexpected response: {error_msg}")
                        meta['tracker_status'][self.tracker]['status_message'] = f"Unexpected response: {error_msg}"
                        return False

            except httpx.TimeoutException:
                meta['tracker_status'][self.tracker]['status_message'] = "data error: RTF request timed out while uploading."
                return False
            except httpx.RequestError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f"data error: An error occurred while making the request: {e}"
                return False
            except Exception as e:
                meta['tracker_status'][self.tracker]['status_message'] = f"data error - Unexpected error: {e}"
                return False

        else:
            console.print("[cyan]RTF Request Data:")
            debug_data = json_data.copy()
            if 'file' in debug_data and debug_data['file']:
                debug_data['file'] = f"{str(debug_data['file'])[:10]}..."
            console.print(debug_data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[dict[str, Any]]:
        """Search for existing torrents on RetroFlix tracker.

        Validates content eligibility (age requirements, no adult content) and searches
        for duplicate torrents using IMDB ID or title.

        Args:
            meta: Metadata dictionary containing torrent information.
            disctype: Type of disc (e.g., 'BD', 'DVD').

        Returns:
            List of dictionaries containing information about existing torrents (dupes).
            Returns empty list if content is ineligible or search fails.
        """
        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            console.print('[bold red]Erotic not allowed at RTF.')
            meta['skipping'] = "RTF"
            return []

        year_value = meta.get('year')
        year = int(year_value) if year_value and str(year_value).isdigit() else None
        # Collect all possible years from different sources
        years: list[int] = []

        # IMDB end year
        imdb_end_year = meta.get('imdb_info', {}).get('end_year')
        if imdb_end_year and str(imdb_end_year).isdigit():
            years.append(int(imdb_end_year))

        # TVDB episode year
        tvdb_episode_year = meta.get('tvdb_episode_year')
        if tvdb_episode_year and str(tvdb_episode_year).isdigit():
            years.append(int(tvdb_episode_year))

        # Get most recent aired date from all TVDB episodes
        most_recent_aired_date = None
        tvdb_episodes_value = meta.get('tvdb_episode_data', {}).get('episodes', [])
        tvdb_episodes = cast(list[dict[str, Any]], tvdb_episodes_value) if isinstance(tvdb_episodes_value, list) else []
        if tvdb_episodes:
            for episode in tvdb_episodes:
                aired_date = str(episode.get('aired', ''))
                if aired_date and '-' in aired_date:
                    try:
                        episode_date = datetime.datetime.strptime(aired_date, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).date()
                        if most_recent_aired_date is None or episode_date > most_recent_aired_date:
                            most_recent_aired_date = episode_date
                    except (ValueError, AttributeError):
                        try:
                            episode_year_value = aired_date.split('-')[0]
                            if episode_year_value.isdigit():
                                years.append(int(episode_year_value))
                        except (ValueError, AttributeError):
                            continue

        # Add the year from most recent aired date if found
        if most_recent_aired_date:
            years.append(most_recent_aired_date.year)

        # Use the most recent year found, fallback to meta year
        most_recent_year = max(years) if years else year

        # Update year with the most recent year for TV shows
        if meta.get('category') == "TV":
            year = most_recent_year

        # Check if content is at least 10 years old using actual date comparison
        if meta.get('category') == "MOVIE" and meta.get('release_date'):
            try:
                release_date = datetime.datetime.strptime(meta['release_date'], '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).date()
                year = release_date.year
                # Calculate date exactly 10 years ago from today
                ten_years_ago = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=365*10 + 3)  # add leeway
                if release_date > ten_years_ago:
                    if not meta.get('unattended', False):
                        console.print("[red]Content must be older than 10 Years to upload at RTF")
                    meta['skipping'] = "RTF"
                    return []
            except (ValueError, AttributeError):
                # If date parsing fails, fall back to year comparison
                release_year = meta['release_date'].split('-')[0]
                if release_year.isdigit():
                    year = int(release_year)
                    if datetime.datetime.now(datetime.timezone.utc).date().year - year <= 9:
                        if not meta.get('unattended', False):
                            console.print("[red]Content must be older than 10 Years to upload at RTF")
                        meta['skipping'] = "RTF"
                        return []

        elif meta.get('category') == "TV" and most_recent_aired_date:
            # For TV shows, use the most recent aired date for comparison if available
            ten_years_ago = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=365*10 + 3)  # add leeway
            if most_recent_aired_date > ten_years_ago:
                if not meta.get('unattended', False):
                    console.print("[red]Content must be older than 10 Years to upload at RTF")
                meta['skipping'] = "RTF"
                return []

        else:
            if year is not None and datetime.datetime.now(datetime.timezone.utc).date().year - int(year) <= 9:
                if not meta.get('unattended', False):
                    console.print("[red]Content must be older than 10 Years to upload at RTF")
                meta['skipping'] = "RTF"
                return []

        dupes: list[dict[str, Any]] = []
        headers = {
            'accept': 'application/json',
            'Authorization': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }
        params = {'includingDead': '1'}

        imdb_id_value = int(meta.get('imdb_id', 0) or 0)
        if imdb_id_value != 0:
            imdb_id_str = str(meta.get('imdb_id'))
            params['imdbId'] = imdb_id_str if imdb_id_str.startswith("tt") else "tt" + imdb_id_str
        else:
            params['search'] = meta['title'].replace(':', '').replace("'", '').replace(",", '')

        def build_download_url(entry: dict[str, Any]) -> str:
            torrent_id = entry.get('id')
            torrent_url = str(entry.get('url', ''))
            if not torrent_id:
                match = re.search(r"/browse/t/(\d+)", torrent_url)
                if match:
                    torrent_id = match.group(1)

            if torrent_id:
                return f"https://retroflix.club/api/torrent/{torrent_id}/download"

            return torrent_url

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.search_url, params=params, headers=headers)
                if response.status_code == 200:
                    data = cast(list[dict[str, Any]], response.json())
                    for each in data:
                        download_url = build_download_url(each)
                        result = {
                            'name': str(each.get('name', '')),
                            'size': each.get('size', 0),
                            'files': str(each.get('name', '')),
                            'link': str(each.get('url', '')),
                            'download': download_url,
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

    async def api_test(self, meta: dict[str, Any]) -> Optional[bool]:
        """Test if the stored API key is valid.

        RetroFlix API keys expire weekly, so this method validates the current key
        and generates a new one if needed.

        Args:
            meta: Metadata dictionary containing base directory path.

        Returns:
            True if API key is valid, None if key generation was attempted.
        """
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
                    return None
                else:
                    return True
        except httpx.RequestError as e:
            console.print(f'[bold red]Error testing API: {str(e)}')
            await self.generate_new_api(meta)
            return None
        except Exception as e:
            console.print(f'[bold red]Unexpected error testing API: {str(e)}')
            await self.generate_new_api(meta)
            return None

    async def generate_new_api(self, meta: dict[str, Any]) -> Optional[bool]:
        """Generate a new API key for RetroFlix tracker.

        Authenticates using username/password and retrieves a new API token,
        then updates both the in-memory config and the config file on disk.

        Args:
            meta: Metadata dictionary containing base directory path for config file location.

        Returns:
            True if new API key was successfully generated and saved, None otherwise.
        """
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
                    try:
                        # Update the in-memory config dictionary
                        self.config['TRACKERS'][self.tracker]['api_key'] = token

                        # Now we update the config file on disk using utf-8 encoding
                        async with aiofiles.open(config_path, encoding='utf-8') as file:
                            config_data = await file.read()

                        # Find the RTF tracker and replace the api_key value (supports single/double quotes and multiline blocks)
                        pattern = r"(['\"]RTF['\"]\s*:\s*{.*?['\"]api_key['\"]\s*:\s*)(['\"])[^'\"]*(['\"])"
                        new_config_data, replacements = re.subn(
                            pattern,
                            rf"\1\2{token}\3",
                            config_data,
                            count=1,
                            flags=re.DOTALL,
                        )
                        if replacements == 0:
                            console.print("[bold red]Failed to update RTF api_key in config file.")
                            return None

                        # Write the updated config back to the file
                        async with aiofiles.open(config_path, 'w', encoding='utf-8') as file:
                            await file.write(new_config_data)

                        console.print(f'[bold green]API Key successfully saved to {config_path}')
                        return True
                    except Exception as e:
                        console.print(f'[bold red]Failed to update config file: {str(e)}')
                        return None
                else:
                    console.print('[bold red]API response does not contain a token.')
                    return None
            else:
                console.print(f'[bold red]Error getting new API key: {response.status_code}, please check username and password in the config.')
                return None

        except httpx.RequestError as e:
            console.print(f'[bold red]An error occurred while requesting the API: {str(e)}')
            return None

        except Exception as e:
            console.print(f'[bold red]An unexpected error occurred: {str(e)}')
            return None
