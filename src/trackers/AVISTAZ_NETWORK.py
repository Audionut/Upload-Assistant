# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import importlib
import json
import os
import platform
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, cast
from urllib.parse import urlparse

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup

import bbcode
from cogs.redaction import Redaction
from src.console import console
from src.cookie_auth import CookieValidator
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]

class AZTrackerBase:
    def __init__(self, config: Config, tracker_name: str):
        self.config = config
        self.tracker = tracker_name
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.az_class = getattr(importlib.import_module(f"src.trackers.{self.tracker}"), self.tracker)

        tracker_config = self.config['TRACKERS'][self.tracker]
        self.base_url: str = tracker_config.get('base_url') or ''
        self.requests_url: str = tracker_config.get('requests_url') or ''
        self.announce_url: str = tracker_config.get('announce_url') or ''
        self.source_flag: str = tracker_config.get('source_flag') or ''
        self.torrent_url: str = f'{self.base_url}/torrent/' if self.base_url else ''

        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Upload Assistant/2.3 ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.media_code = ''
        self.upload_url_step2 = ''

    def rules(self, _meta: Meta) -> str:
        return ''

    def get_resolution(self, meta: Meta) -> str:
        resolution = ''
        width, height = None, None

        try:
            if meta.get('is_disc') == 'BDMV':
                resolution_str = meta.get('resolution', '')
                height_num = int(resolution_str.lower().replace('p', '').replace('i', ''))
                height = str(height_num)
                width = str(round((16 / 9) * height_num))
            else:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                if len(tracks) > 1:
                    video_mi = tracks[1]
                    width = video_mi.get('Width')
                    height = video_mi.get('Height')
        except (ValueError, TypeError, KeyError, IndexError):
            return ''

        if width and height:
            resolution = f'{width}x{height}'

        return resolution

    def get_video_quality(self, meta: Meta) -> str:
        resolution: str = meta.get('resolution', '')

        if self.tracker != 'PHD':
            resolution_int = int(resolution.lower().replace('p', '').replace('i', ''))
            if resolution_int < 720 or meta.get('sd', False):
                return '1'

        keyword_map = {
            '1080i': '7',
            '1080p': '3',
            '2160p': '6',
            '4320p': '8',
            '720p': '2',
        }

        return keyword_map.get(resolution.lower(), "0")

    async def get_media_code(self, meta: Meta) -> bool:
        self.media_code = ''

        if meta['category'] == 'MOVIE':
            category = '1'
        elif meta['category'] == 'TV':
            category = '2'
        else:
            return False

        imdb_info = meta.get('imdb_info', {})
        imdb_id: str = str(imdb_info.get('imdbID', ''))
        tmdb_id: str = str(meta.get('tmdb', ''))
        title = meta['title']

        headers = {
            'Referer': f"{self.base_url}/upload/{meta['category'].lower()}",
            'X-Requested-With': 'XMLHttpRequest'
        }

        for attempt in range(2):
            try:
                if attempt == 1:
                    console.print(f'{self.tracker}: Trying to search again by ID after adding to media to database...\n')
                    await asyncio.sleep(5)  # Small delay to ensure the DB has been updated

                data: dict[str, Any] = {}

                if imdb_id:
                    response = await self.session.get(f'{self.base_url}/ajax/movies/{category}?term={imdb_id}', headers=headers)
                    response.raise_for_status()
                    data = response.json()

                if not data.get('data', ''):
                    response = await self.session.get(f'{self.base_url}/ajax/movies/{category}?term={title}', headers=headers)
                    response.raise_for_status()
                    data = response.json()

                match = None
                for item in data.get('data', []):
                    if imdb_id and item.get('imdb') == imdb_id or item.get('tmdb') == tmdb_id:
                        match = item
                        break

                if match:
                    self.media_code = str(match['id'])
                    if attempt == 1:
                        console.print(f"{self.tracker}: [green]Found new ID at:[/green] {self.base_url}/{meta['category'].lower()}/{self.media_code}")
                    return True

            except Exception as e:
                console.print(f'{self.tracker}: Error while trying to fetch media code in attempt {attempt + 1}: {e}')
                break

            if attempt == 0 and not self.media_code:
                console.print(f"\n{self.tracker}: The media [[yellow]IMDB:{imdb_id}[/yellow]] [[blue]TMDB:{tmdb_id}[/blue]] appears to be missing from the site's database.")
                if cli_ui.ask_yes_no(f"{self.tracker}: Do you want to add it to the site database?\n"):
                    added_successfully = await self.add_media_to_db(meta, title, category, imdb_id, tmdb_id)
                    if not added_successfully:
                        console.print(f'{self.tracker}: Failed to add media. Aborting.')
                        break
                else:
                    console.print(f'{self.tracker}: User chose not to add media. Aborting.')
                    break

        if not self.media_code:
            console.print(f'{self.tracker}: Unable to get media code.')

        return bool(self.media_code)

    async def add_media_to_db(self, meta: Meta, title: str, category: str, imdb_id: str, tmdb_id: str) -> bool:
        data: dict[str, Any] = {
            '_token': self.az_class.secret_token,
            'type_id': category,
            'title': title,
            'imdb_id': imdb_id if imdb_id else '',
            'tmdb_id': tmdb_id if tmdb_id else '',
        }

        if meta['category'] == 'TV':
            tvdb_id = meta.get('tvdb')
            if tvdb_id:
                data['tvdb_id'] = str(tvdb_id)

        url = f"{self.base_url}/add/{meta['category'].lower()}"

        headers = {
            'Referer': f'{self.base_url}/upload',
        }

        try:
            console.print(f'{self.tracker}: Trying to add to database...')
            response = await self.session.post(url, data=data, headers=headers)
            if response.status_code == 302:
                console.print(f'{self.tracker}: The attempt to add the media to the database appears to have been successful..')
                return True
            else:
                console.print(f'{self.tracker}: Error adding media to the database. Status: {response.status_code}')
                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]Failed_DB_attempt.html"
                os.makedirs(os.path.dirname(failure_path), exist_ok=True)
                async with aiofiles.open(failure_path, 'w', encoding='utf-8') as f:
                    await f.write(response.text)
                console.print(f'The server response was saved to {failure_path} for analysis.')
                return False

        except Exception as e:
            console.print(f'{self.tracker}: Exception when trying to add media to the database: {e}')
            return False

    async def validate_credentials(self, meta: Meta):
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if cookie_jar:
            self.session.cookies = cookie_jar
            return await self.cookie_validator.cookie_validation(
                meta=meta,
                tracker=self.tracker,
                test_url=f'{self.base_url}/torrents',
                error_text='Page not found',
                token_pattern=r'name="_token" content="([^"]+)"'  # nosec B106
            )
        return False

    async def search_existing(self, meta: Meta, _) -> list[dict[str, str]]:
        duplicates: list[dict[str, str]] = []

        if self.config['TRACKERS'][self.tracker].get('check_for_rules', True):
            warnings = self.rules(meta)
            if warnings:
                console.print(f"{self.tracker}: [red]Rule check returned the following warning(s):[/red]\n\n{warnings}")
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    if not cli_ui.ask_yes_no('Do you want to continue anyway?', default=False):
                        meta['skipping'] = f'{self.tracker}'
                        return duplicates
                else:
                    meta['skipping'] = f'{self.tracker}'
                    return duplicates

        if meta['type'] not in ['WEBDL'] and self.tracker == "PHD" and meta.get('tag', "") in ['FGT', 'EVO']:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]Group {meta["tag"]} is only allowed for web-dl[/bold red]')
                if not cli_ui.ask_yes_no('Do you want to upload anyway?', default=False):
                    meta['skipping'] = f'{self.tracker}'
                    return duplicates
            else:
                meta['skipping'] = f'{self.tracker}'
                return duplicates

        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if cookie_jar:
            self.session.cookies = cookie_jar

        if not await self.get_media_code(meta):
            console.print(f"{self.tracker}: This media is not registered, please add it to the database by following this link: {self.base_url}/add/{meta['category'].lower()}")
            meta['skipping'] = f'{self.tracker}'
            return duplicates

        if meta.get('resolution') == '2160p':
            resolution = 'UHD'
        elif meta.get('resolution') in ('720p', '1080p'):
            resolution = meta.get('resolution') or 'all'
        else:
            resolution = 'all'

        rip_type = self.get_rip_type(meta, display_name=True)

        page_url: str = f'{self.base_url}/movies/torrents/{self.media_code}?quality={resolution}'

        visited_urls: set[str] = set()

        while page_url and page_url not in visited_urls:
            visited_urls.add(page_url)

            try:
                response = await self.session.get(page_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                torrent_table = soup.find('table', class_='table-bordered')
                if not torrent_table:
                    page_url = ""
                    continue

                tbody = torrent_table.find('tbody')
                if not tbody:
                    page_url = ""
                    continue

                torrent_rows = tbody.find_all('tr', recursive=False)

                for row in torrent_rows:
                    badges = [b.get_text(strip=True) for b in row.find_all('span', class_='badge-extra')]

                    if rip_type and rip_type not in badges:
                        continue

                    name_tag = row.find('a', class_='torrent-filename')
                    name = name_tag.get_text(strip=True) if name_tag else ''

                    href_value = name_tag.get('href') if name_tag else None
                    torrent_link = href_value if isinstance(href_value, str) else ''
                    if torrent_link:
                        match = re.search(r'/(\d+)', torrent_link)
                        if match:
                            torrent_link = f'{self.torrent_url}{match.group(1)}'

                    cells = row.find_all('td')
                    size = ''
                    if len(cells) > 4:
                        size_span = cells[4].find('span')
                        size = size_span.get_text(strip=True) if size_span else cells[4].get_text(strip=True)

                    dupe_entry = {
                        'name': name,
                        'size': size,
                        'link': torrent_link
                    }

                    if meta.get('is_disc') == "BDMV":
                        bd_info = await self.get_dupe_bdinfo(torrent_link)
                        if bd_info:
                            dupe_entry.update({
                                'bd_info': bd_info
                            })

                    duplicates.append(dupe_entry)

                next_page_tag = soup.select_one("a[rel='next']")
                if next_page_tag and 'href' in next_page_tag.attrs:
                    next_href = next_page_tag.get('href', '')
                    page_url = next_href if isinstance(next_href, str) else ""
                else:
                    page_url = ""

            except httpx.RequestError as e:
                console.print(f'{self.tracker}: Failed to search for duplicates. {e.request.url}: {e}')
                return duplicates

        return duplicates

    async def get_dupe_bdinfo(self, torrent_link: str) -> str:
        """
        Fetch the BDInfo/MediaInfo content from the torrent page.
        """
        try:
            response = await self.session.get(torrent_link, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            mediainfo_container = soup.find('div', id='collapseMediaInfo')

            if mediainfo_container:
                pre_tag = mediainfo_container.find('pre')
                if pre_tag:
                    return pre_tag.get_text("\n", strip=True)

            console.print(f'[yellow]{self.tracker}: MediaInfo/BDInfo block not found at {torrent_link}[/yellow]')
            return ''

        except httpx.HTTPStatusError as e:
            console.print(f'[red]{self.tracker}: HTTP error {e.response.status_code} from {torrent_link}[/red]')
        except httpx.RequestError as e:
            console.print(f'[red]{self.tracker}: Request failed to {torrent_link}. {e}[/red]')
        except Exception as e:
            console.print(f'[red]{self.tracker}: Unexpected error parsing {torrent_link}. {e}[/red]')

        return ''

    def get_cat_id(self, category_name: str) -> str:
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, "0")
        return category_id

    async def get_file_info(self, meta: Meta) -> str:
        info_file_path = ''
        file_info = ''
        if meta.get('is_disc') == 'BDMV':
            summary_file = 'BD_SUMMARY_EXT_00' if self.tracker == 'CZ' else 'BD_SUMMARY_00'
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/{summary_file}.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            async with aiofiles.open(info_file_path, encoding='utf-8') as f:
                file_info = await f.read()

        return file_info

    async def get_lang(self, meta: Meta) -> dict[str, list[str]]:
        self.language_map()
        audio_ids: set[str] = set()
        subtitle_ids: set[str] = set()

        if meta.get('is_disc', False):
            if not meta.get('language_checked', False):
                await languages_manager.process_desc_language(meta, tracker=self.tracker)

            found_subs_strings = meta.get('subtitle_languages', [])
            for lang_str in found_subs_strings:
                target_id = self.lang_map.get(lang_str.lower())
                if target_id:
                    subtitle_ids.add(target_id)

            found_audio_strings = meta.get('audio_languages', [])
            for lang_str in found_audio_strings:
                target_id = self.lang_map.get(lang_str.lower())
                if target_id:
                    audio_ids.add(target_id)
        else:
            try:
                media_info_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json"
                async with aiofiles.open(media_info_path, encoding='utf-8') as f:
                    data = json.loads(await f.read())

                tracks = data.get('media', {}).get('track', [])

                missing_audio_languages: list[dict[str, Any]] = []

                for track in tracks:
                    track_type = track.get('@type')
                    language_code = track.get('Language')

                    if not language_code:
                        if track_type == 'Audio':
                            missing_audio_languages.append(track)
                        continue

                    target_id = self.lang_map.get(language_code.lower())

                    if not target_id and '-' in language_code:
                        primary_code = language_code.split('-')[0]
                        target_id = self.lang_map.get(primary_code.lower())

                    if target_id:
                        if track_type == 'Audio':
                            audio_ids.add(target_id)
                        elif track_type == 'Text':
                            subtitle_ids.add(target_id)
                    else:
                        if track_type == 'Audio':
                            missing_audio_languages.append(track)

                if missing_audio_languages:
                    console.print('No audio language/s found.')
                    console.print('You must enter (comma-separated) languages for all audio tracks, eg: English, Spanish: ')
                    user_input_raw = cli_ui.ask_string('[bold yellow]Enter languages: [/bold yellow]')
                    user_input = (user_input_raw or "").strip()
                    langs = [lang.strip() for lang in user_input.split(',')]
                    for lang in langs:
                        target_id = self.lang_map.get(lang.lower())
                        if target_id:
                            audio_ids.add(target_id)

            except FileNotFoundError:
                console.print(f'Warning: MediaInfo.json not found for uuid {meta.get("uuid")}. No languages will be processed.', markup=False)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                console.print(f'Error processing MediaInfo.json for uuid {meta.get("uuid")}: {e}', markup=False)

        final_subtitle_ids = sorted(subtitle_ids)
        final_audio_ids = sorted(audio_ids)

        return {
            'subtitles[]': final_subtitle_ids,
            'languages[]': final_audio_ids
        }

    async def img_host(self, _meta: Meta, referer: str, image_bytes: bytes, filename: str) -> Optional[str]:
        upload_url = f'{self.base_url}/ajax/image/upload'

        headers = {
            'Referer': referer,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
            'Origin': self.base_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'
        }

        data: dict[str, Any] = {
            '_token': self.az_class.secret_token,
            'qquuid': str(uuid.uuid4()),
            'qqfilename': filename,
            'qqtotalfilesize': str(len(image_bytes))
        }

        files = {'qqfile': (filename, image_bytes, 'image/png')}

        try:
            response = await self.session.post(upload_url, headers=headers, data=data, files=files)

            if response.is_success:
                json_data = response.json()
                if json_data.get('success'):
                    image_id = json_data.get('imageId')
                    return str(image_id)
                else:
                    error_message = json_data.get('error', 'Unknown image host error.')
                    console.print(f'{self.tracker}: Error uploading {filename}: {error_message}', markup=False)
                    return None
            else:
                console.print(f'{self.tracker}: Error uploading {filename}: Status {response.status_code} - {response.text}', markup=False)
                return None
        except Exception as e:
            console.print(f'{self.tracker}: Exception when uploading {filename}: {e}', markup=False)
            return None

    async def get_screenshots(self, meta: Meta) -> Optional[list[str]]:
        screenshot_dir = Path(meta['base_dir']) / 'tmp' / meta['uuid']
        local_files = sorted(screenshot_dir.glob('*.png'))
        results: list[str] = []

        limit = 3 if meta.get('tv_pack', '') == 0 else 15

        disc_menu_links = [
            img.get('raw_url')
            for img in meta.get('menu_images', [])
            if img.get('raw_url')
        ][:12]  # minimum number of screenshots is 3, so we can allow up to 12 menu images

        async def upload_local_file(path: Path):
            async with aiofiles.open(path, 'rb') as f:
                image_bytes = await f.read()
            return await self.img_host(meta, self.tracker, image_bytes, path.name)

        async def upload_remote_file(url: str):
            try:
                response = await self.session.get(url)
                response.raise_for_status()
                image_bytes = response.content
                filename = os.path.basename(urlparse(url).path) or 'screenshot.png'
                return await self.img_host(meta, self.tracker, image_bytes, filename)
            except Exception as e:
                console.print(f'Failed to process screenshot from URL {url}: {e}', markup=False)
                return None

        # Upload menu images
        for url in disc_menu_links:
            if not url.lower().endswith('.png'):
                console.print(f"{self.tracker}: Skipping non-PNG menu image: {url}")
            else:
                result = await upload_remote_file(url)
                if result:
                    results.append(result)

        remaining_slots = max(0, limit - len(results))

        if local_files and remaining_slots > 0:
            paths = local_files[:remaining_slots]

            for path in paths:
                result = await upload_local_file(path)
                if result:
                    results.append(result)

        else:
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')]
            remaining_slots = max(0, limit - len(results))
            links = image_links[:remaining_slots]

            for url in links:
                result = await upload_remote_file(url)
                if result:
                    results.append(result)

        return results

    async def get_requests(self, meta: Meta) -> Optional[list[dict[str, Any]]]:
        results: list[dict[str, Any]] = []
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return results
        else:
            try:
                cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
                if not cookie_jar:
                    return results
                self.session.cookies = cookie_jar
                category = meta.get('category', '').lower()
                query = meta['title'] + f" {meta.get('season', '')}{meta.get('episode', '')}" if category == 'tv' else meta['title']

                search_url = f'{self.requests_url}?type={category}&search={query}&condition=new'

                response = await self.session.get(search_url)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')

                request_rows = soup.select('.table-responsive table tbody tr')

                for row in request_rows:
                    link_element = row.select_one('a.torrent-filename')

                    if not link_element:
                        continue

                    name = link_element.text.strip()
                    link = link_element.get('href')

                    all_tds = row.find_all('td')

                    reward = all_tds[5].text.strip() if len(all_tds) > 5 else 'N/A'

                    results.append({
                        'Name': name,
                        'Link': link,
                        'Reward': reward
                    })

                if results:
                    message = f'\n{self.tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n'
                    for r in results:
                        message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Reward:[/bold green] {r['Reward']}\n"
                        message += f"[bold green]Link:[/bold green] {r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                console.print(f'{self.tracker}: An error occurred while fetching requests: {e}')
                return results

    async def fetch_tag_id(self, word: str) -> int:
        tags_url = f'{self.base_url}/ajax/tags'
        params = {'term': word}

        headers = {
            'Referer': f'{self.base_url}/upload',
            'X-Requested-With': 'XMLHttpRequest'
        }
        try:
            response = await self.session.get(tags_url, headers=headers, params=params)
            response.raise_for_status()

            json_data = response.json()

            for tag_info in json_data.get('data', []):
                if tag_info.get('tag') == word:
                    try:
                        tag = int(tag_info.get('id', 0))
                        return tag
                    except ValueError:
                        return 0

        except Exception as e:
            console.print(f"An unexpected error occurred while processing the tag '{word}': {e}", markup=False)

        return 0

    async def get_tags(self, meta: Meta) -> list[str]:
        tags: list[str] = []

        genres = meta.get('keywords', '')
        if not genres:
            return tags

        # divides by commas, cleans spaces and normalizes to lowercase
        phrases = [re.sub(r'\s+', ' ', x.strip().lower()) for x in re.split(r',+', genres) if x.strip()]

        words_to_search = set(phrases)

        tasks = [self.fetch_tag_id(word) for word in words_to_search]

        tag_ids_results = await asyncio.gather(*tasks)

        tags = [str(tag_id) for tag_id in tag_ids_results if tag_id]

        if meta.get('personalrelease', False):
            if self.tracker == 'AZ':
                tags.insert(0, '3773')
            elif self.tracker == 'CZ':
                tags.insert(0, '1594')
            elif self.tracker == 'PHD':
                tags.insert(0, '1448')

        if self.config['TRACKERS'][self.tracker].get('internal', False):
            if self.tracker == 'AZ':
                tags.insert(0, '943')
            elif self.tracker == 'CZ':
                tags.insert(0, '938')
            elif self.tracker == 'PHD':
                tags.insert(0, '415')

        return tags

    async def edit_desc(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # TV stuff
        title, _, episode_overview = await builder.get_tv_info(meta)
        if episode_overview:
            desc_parts.append(f'[b]Episode:[/b] {title}')
            desc_parts.append(f'[b]Overview:[/b] {episode_overview}')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        if not description:
            return ''

        processed_desc, amount = re.subn(
            r'\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]',
            '',
            description,
            flags=re.DOTALL
        )
        if amount > 0:
            console.print(f'{self.tracker}: Deleted from description: {amount} NFO section.')

        processed_desc, amount = re.subn(r'http[s]?://\S+|www\.\S+', '', processed_desc)
        if amount > 0:
            console.print(f'{self.tracker}: Deleted from description: {amount} link(s).')

        bbcode_tags_pattern = r'\[/?(size|align|left|center|right|img|table|tr|td|spoiler|url)[^\]]*\]'
        processed_desc, amount = re.subn(
            bbcode_tags_pattern,
            '',
            processed_desc,
            flags=re.IGNORECASE
        )
        if amount > 0:
            console.print(f'{self.tracker}: Deleted from description: {amount} BBCode tag(s).')

        render_html = getattr(bbcode, 'render_html', None)
        final_html_desc = cast(Callable[[str], str], render_html)(processed_desc) if callable(render_html) else cast(Any, bbcode).Parser().format(processed_desc)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(final_html_desc)

        return final_html_desc

    async def create_task_id(self, meta: Meta) -> dict[str, Any]:
        await self.get_media_code(meta)
        data: dict[str, Any] = {
            "_token": self.az_class.secret_token,
            "type_id": self.get_cat_id(meta["category"]),
            "movie_id": self.media_code,
            "media_info": await self.get_file_info(meta),
        }

        default_announce = ""
        if self.tracker == 'AZ':
            default_announce = 'https://tracker.avistaz.to/announce'
        elif self.tracker == 'CZ':
            default_announce = 'https://tracker.cinemaz.to/announce'
        elif self.tracker == 'PHD':
            default_announce = 'https://tracker.privatehd.to/announce'

        if not meta.get('debug', False):
            try:
                await self.common.create_torrent_for_upload(meta, self.tracker, self.source_flag, announce_url=default_announce)
                upload_url_step1 = f"{self.base_url}/upload/{meta['category'].lower()}"
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

                async with aiofiles.open(torrent_path, 'rb') as torrent_file:
                    torrent_bytes = await torrent_file.read()
                files = {'torrent_file': (os.path.basename(torrent_path), torrent_bytes, 'application/x-bittorrent')}
                task_response = await self.session.post(upload_url_step1, data=data, files=files)

                if task_response.status_code == 302 and 'Location' in task_response.headers:
                    redirect_url = task_response.headers['Location']

                    match = re.search(r'/(\d+)$', redirect_url)
                    if not match:
                        console.print(f"{self.tracker}: Could not extract 'task_id' from redirect URL: {redirect_url}")
                        console.print(f'{self.tracker}: The cookie appears to be expired or invalid.')
                        meta['skipping'] = f'{self.tracker}'
                        return {}

                    task_id = match.group(1)

                    task: dict[str, Any] = {
                        'task_id': task_id,
                        'info_hash': await self.common.get_torrent_hash(meta, self.tracker),
                        'redirect_url': redirect_url,
                    }

                    return task

                else:
                    failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step1.html"
                    async with aiofiles.open(failure_path, 'w', encoding='utf-8') as f:
                        await f.write(task_response.text)
                    status_message = f'''[red]Step 1 of upload failed to {self.tracker}. Status: {task_response.status_code}, URL: {task_response.url}[/red].
                                            [yellow]The HTML response was saved to '{failure_path}' for analysis.[/yellow]'''

            except Exception as e:
                status_message = f'[red]An unexpected error occurred while uploading to {self.tracker}: {e}[/red]'
                meta['skipping'] = f'{self.tracker}'
                return {}

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
        return {}

    def edit_name(self, meta: Meta) -> str:
        # https://avistaz.to/guides/how-to-properly-titlename-a-torrent
        # https://cinemaz.to/guides/how-to-properly-titlename-a-torrent
        # https://privatehd.to/rules/upload-rules
        aka_name = meta.get("aka") or ""
        manual_episode_title = meta.get("manual_episode_title") or ""
        daily_episode_title = meta.get("daily_episode_title") or ""
        upload_name: str = (
            str(meta.get("name", "")).replace(aka_name, "").replace("Dubbed", "").replace("Dual-Audio", "").replace(manual_episode_title, "").replace(daily_episode_title, "")
        )

        if self.tracker == 'PHD':
            forbidden_terms = [
                r'\bLIMITED\b',
                r'\bCriterion Collection\b',
                r'\b\d{1,3}(?:st|nd|rd|th)\s+Anniversary Edition\b'
            ]
            for term in forbidden_terms:
                upload_name = re.sub(term, '', upload_name, flags=re.IGNORECASE).strip()

            upload_name = re.sub(r'\bDirector[’\'`]s\s+Cut\b', 'DC', upload_name, flags=re.IGNORECASE)
            upload_name = re.sub(r'\bExtended\s+Cut\b', 'Extended', upload_name, flags=re.IGNORECASE)
            upload_name = re.sub(r'\bTheatrical\s+Cut\b', 'Theatrical', upload_name, flags=re.IGNORECASE)
            upload_name = re.sub(r'\s{2,}', ' ', upload_name).strip()

        if meta.get('has_encode_settings', False):
            upload_name = upload_name.replace('H.264', 'x264').replace('H.265', 'x265')

        tag_lower = meta['tag'].lower()
        invalid_tags = ['nogrp', 'nogroup', 'unknown', '-unk-']

        if meta['tag'] == '' or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                upload_name = re.sub(f'-{invalid_tag}', '', upload_name, flags=re.IGNORECASE)

            if self.tracker == 'CZ':
                upload_name = f'{upload_name}-NoGroup'
            if self.tracker == 'PHD':
                upload_name = f'{upload_name}-NOGROUP'

        if meta['category'] == 'TV':
            year_to_use = meta.get('year')
            if not meta.get('no_year', False) and not meta.get('search_year', ''):
                season_int = meta.get('season_int', 0)
                season_info = meta.get('imdb_info', {}).get('seasons_summary', [])

                # Find the correct year for this specific season
                season_year = None
                if season_int and season_info:
                    for season_data in season_info:
                        if season_data.get('season') == season_int:
                            season_year = season_data.get('year')
                            break

                # Use the season-specific year if found, otherwise fall back to meta year
                if season_year:
                    year_to_use = season_year
                upload_name = upload_name.replace(
                    meta['title'],
                    f"{meta['title']} {year_to_use}",
                    1
                )

            if self.tracker == 'PHD':
                upload_name = upload_name.replace(
                    str(year_to_use),
                    ''
                )

            if self.tracker == 'AZ' and meta.get('tv_pack', False):
                upload_name = upload_name.replace(
                    f"{meta['title']} {year_to_use} {meta.get('season')}",
                    f"{meta['title']} {meta.get('season')} {year_to_use}"
                )

        if meta.get('type', '') == 'DVDRIP' and meta.get('source', ''):
            upload_name = upload_name.replace(meta['source'], '')

        return re.sub(r'\s{2,}', ' ', upload_name)

    def get_rip_type(self, meta: Meta, display_name: bool = False) -> str:
        # Translation from meta keywords to site display labels
        translation = {
            "bdrip": "BDRip",
            "brrip": "BRRip",
            "encode": "BluRay",
            "dvdrip": "DVDRip",
            "hdrip": "HDRip",
            "hdtv": "HDTV",
            "sdtv": "SDTV",
            "vcd": "VCD",
            "vcdrip": "VCDRip",
            "vhsrip": "VHSRip",
            "vodrip": "VODRip",
            "webdl": "WEB-DL",
            "webrip": "WEBRip",
        }

        # Available rip types from HTML
        available_rip_types = {
            "BDRip": "1",
            "BluRay": "2",
            "BRRip": "3",
            "DVD": "4",
            "DVDRip": "5",
            "HDRip": "6",
            "HDTV": "7",
            "VCD": "8",
            "VCDRip": "9",
            "VHSRip": "10",
            "VODRip": "11",
            "WEB-DL": "12",
            "WEBRip": "13",
            "BluRay REMUX": "14",
            "BluRay Raw": "15",
            "SDTV": "16",
            "DVD Remux": "17",
        }

        source_type = str(meta.get("type", "") or "").strip().lower()
        source = str(meta.get("source", "") or "").strip().lower()
        is_disc = str(meta.get("is_disc", "") or "").strip().lower()

        html_label = ""

        if source_type == 'disc':
            if is_disc == "bdmv":
                html_label = "BluRay Raw"
            elif is_disc in ("dvd", "hddvd"):
                html_label = "DVD"

        elif source_type == "remux":
            if "dvd" in source:
                html_label = "DVD Remux"
            elif source in ("bluray", "blu-ray"):
                html_label = "BluRay REMUX"
            else:
                return "0"
        else:
            html_label = translation.get(source_type) or ''

        if display_name:
            return html_label

        return available_rip_types.get(html_label, "0")

    async def fetch_data(self, meta: Meta) -> dict[str, Any]:
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if cookie_jar:
            self.session.cookies = cookie_jar
        task_info = await self.create_task_id(meta)
        lang_info = await self.get_lang(meta) or {}

        data: dict[str, Any] = {
            "_token": self.az_class.secret_token,
            "torrent_id": "",
            "type_id": self.get_cat_id(meta["category"]),
            "file_name": self.edit_name(meta),
            "anon_upload": "",
            "description": await self.edit_desc(meta),
            "qqfile": "",
            "rip_type_id": self.get_rip_type(meta),
            "video_quality_id": self.get_video_quality(meta),
            "video_resolution": self.get_resolution(meta),
            "movie_id": self.media_code,
            "languages[]": lang_info.get("languages[]"),
            "subtitles[]": lang_info.get("subtitles[]"),
            "media_info": await self.get_file_info(meta),
            "tags[]": await self.get_tags(meta),
            "screenshots[]": [""],
        }

        # TV
        if meta.get('category') == 'TV':
            data.update({
                'tv_collection': '1' if meta.get('tv_pack') == 0 else '2',
                'tv_season': meta.get('season_int', ''),
                'tv_episode': meta.get('episode_int', ''),
            })

        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anon_upload': '1'
            })

        if not meta.get('debug', False):
            try:
                self.upload_url_step2 = task_info.get('redirect_url', '')
                screenshots = await self.get_screenshots(meta) or []
                # task_id and screenshot cannot be called until Step 1 is completed
                data.update({
                    'info_hash': task_info.get('info_hash'),
                    'task_id': task_info.get('task_id'),
                    'screenshots[]': screenshots
                })

            except Exception as e:
                console.print(f'{self.tracker}: An unexpected error occurred while uploading: {e}')

        return data

    def check_data(self, meta: Meta, data: dict[str, Any]):
        if not meta.get('debug', False):
            if len(data['screenshots[]']) < 3:
                return f'UPLOAD FAILED: The {self.tracker} image host did not return the minimum number of screenshots.'

            if not self.upload_url_step2 or not data.get("task_id") or not data.get("info_hash"):
                return "UPLOAD FAILED: Step 1 did not complete (missing redirect/task_id/info_hash)."

        if data["rip_type_id"] == "0":
            return "UPLOAD FAILED: Unable to determine rip type for this upload."

        if data["type_id"] == "0":
            return "UPLOAD FAILED: Unable to determine category for this upload."

        if data["video_quality_id"] == "0":
            return "UPLOAD FAILED: Unable to determine the resolution for this upload."

        return False

    async def upload(self, meta: Meta, _) -> bool:
        data = await self.fetch_data(meta)
        status_message = ''

        issue = self.check_data(meta, data)
        if issue:
            meta['tracker_status'][self.tracker] = f'data error - {issue}'
            return False
        else:
            if not meta.get('debug', False):
                response = await self.session.post(self.upload_url_step2, data=data)
                if response.status_code == 302:
                    torrent_url = response.headers['Location']

                    # Even if you are uploading, you still need to download the .torrent from the website
                    # because it needs to be registered as a download before you can start seeding
                    download_url = torrent_url.replace('/torrent/', '/download/torrent/')
                    register_download = await self.session.get(download_url)
                    if register_download.status_code != 200:
                        meta['tracker_status'][self.tracker]['status_message'] = (
                            f'data error - Unable to register your upload in your download history, please go to the URL and download the torrent file before you can start seeding: {torrent_url}\n'
                            f'Error: {register_download.status_code}'
                        )
                        return False

                    await self.common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag, self.announce_url, torrent_url)

                    meta['tracker_status'][self.tracker]['status_message'] = f'{self.tracker} torrent uploaded successfully.'

                    match = re.search(r'/torrent/(\d+)', torrent_url)
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                    return True

                else:
                    failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step2.html"
                    async with aiofiles.open(failure_path, 'w', encoding='utf-8') as f:
                        await f.write(response.text)

                    status_message = (
                        f"data error - It may have uploaded, go check\n"
                        f'Step 2 of upload to {self.tracker} failed.\n'
                        f'Status code: {response.status_code}\n'
                        f'URL: {response.url}\n'
                        f"The HTML response has been saved to '{failure_path}' for analysis."
                    )
                    meta['tracker_status'][self.tracker]['status_message'] = status_message
                    return False

            else:
                console.print(f"[cyan]{self.tracker} Request Data:")
                console.print(Redaction.redact_private_info(data))
                meta['tracker_status'][self.tracker]['status_message'] = 'Debug mode enabled, not uploading.'
                await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
                return True

    def language_map(self) -> None:
        all_lang_map = {
            ('Abkhazian', 'abk', 'ab'): '1',
            ('Afar', 'aar', 'aa'): '2',
            ('Afrikaans', 'afr', 'af'): '3',
            ('Akan', 'aka', 'ak'): '4',
            ('Albanian', 'sqi', 'sq'): '5',
            ('Amharic', 'amh', 'am'): '6',
            ('Arabic', 'ara', 'ar'): '7',
            ('Aragonese', 'arg', 'an'): '8',
            ('Armenian', 'hye', 'hy'): '9',
            ('Assamese', 'asm', 'as'): '10',
            ('Avaric', 'ava', 'av'): '11',
            ('Avestan', 'ave', 'ae'): '12',
            ('Aymara', 'aym', 'ay'): '13',
            ('Azerbaijani', 'aze', 'az'): '14',
            ('Bambara', 'bam', 'bm'): '15',
            ('Bashkir', 'bak', 'ba'): '16',
            ('Basque', 'eus', 'eu'): '17',
            ('Belarusian', 'bel', 'be'): '18',
            ('Bengali', 'ben', 'bn'): '19',
            ('Bihari languages', 'bih', 'bh'): '20',
            ('Bislama', 'bis', 'bi'): '21',
            ('Bokmål, Norwegian', 'nob', 'nb'): '22',
            ('Bosnian', 'bos', 'bs'): '23',
            ('Breton', 'bre', 'br'): '24',
            ('Bulgarian', 'bul', 'bg'): '25',
            ('Burmese', 'mya', 'my'): '26',
            ('Cantonese', 'yue', 'zh'): '27',
            ('Catalan', 'cat', 'ca'): '28',
            ('Central Khmer', 'khm', 'km'): '29',
            ('Chamorro', 'cha', 'ch'): '30',
            ('Chechen', 'che', 'ce'): '31',
            ('Chichewa', 'nya', 'ny'): '32',
            ('Chinese', 'zho', 'zh'): '33',
            ('Church Slavic', 'chu', 'cu'): '34',
            ('Chuvash', 'chv', 'cv'): '35',
            ('Cornish', 'cor', 'kw'): '36',
            ('Corsican', 'cos', 'co'): '37',
            ('Cree', 'cre', 'cr'): '38',
            ('Croatian', 'hrv', 'hr'): '39',
            ('Czech', 'ces', 'cs'): '40',
            ('Danish', 'dan', 'da'): '41',
            ('Dhivehi', 'div', 'dv'): '42',
            ('Dutch', 'nld', 'nl'): '43',
            ('Dzongkha', 'dzo', 'dz'): '44',
            ('English', 'eng', 'en'): '45',
            ('Esperanto', 'epo', 'eo'): '46',
            ('Estonian', 'est', 'et'): '47',
            ('Ewe', 'ewe', 'ee'): '48',
            ('Faroese', 'fao', 'fo'): '49',
            ('Fijian', 'fij', 'fj'): '50',
            ('Finnish', 'fin', 'fi'): '51',
            ('French', 'fra', 'fr'): '52',
            ('Fulah', 'ful', 'ff'): '53',
            ('Gaelic', 'gla', 'gd'): '54',
            ('Galician', 'glg', 'gl'): '55',
            ('Ganda', 'lug', 'lg'): '56',
            ('Georgian', 'kat', 'ka'): '57',
            ('German', 'deu', 'de'): '58',
            ('Greek', 'ell', 'el'): '59',
            ('Guarani', 'grn', 'gn'): '60',
            ('Gujarati', 'guj', 'gu'): '61',
            ('Haitian', 'hat', 'ht'): '62',
            ('Hausa', 'hau', 'ha'): '63',
            ('Hebrew', 'heb', 'he'): '64',
            ('Herero', 'her', 'hz'): '65',
            ('Hindi', 'hin', 'hi'): '66',
            ('Hiri Motu', 'hmo', 'ho'): '67',
            ('Hungarian', 'hun', 'hu'): '68',
            ('Icelandic', 'isl', 'is'): '69',
            ('Ido', 'ido', 'io'): '70',
            ('Igbo', 'ibo', 'ig'): '71',
            ('Indonesian', 'ind', 'id'): '72',
            ('Interlingua', 'ina', 'ia'): '73',
            ('Interlingue', 'ile', 'ie'): '74',
            ('Inuktitut', 'iku', 'iu'): '75',
            ('Inupiaq', 'ipk', 'ik'): '76',
            ('Irish', 'gle', 'ga'): '77',
            ('Italian', 'ita', 'it'): '78',
            ('Japanese', 'jpn', 'ja'): '79',
            ('Javanese', 'jav', 'jv'): '80',
            ('Kalaallisut', 'kal', 'kl'): '81',
            ('Kannada', 'kan', 'kn'): '82',
            ('Kanuri', 'kau', 'kr'): '83',
            ('Kashmiri', 'kas', 'ks'): '84',
            ('Kazakh', 'kaz', 'kk'): '85',
            ('Kikuyu', 'kik', 'ki'): '86',
            ('Kinyarwanda', 'kin', 'rw'): '87',
            ('Kirghiz', 'kir', 'ky'): '88',
            ('Komi', 'kom', 'kv'): '89',
            ('Kongo', 'kon', 'kg'): '90',
            ('Korean', 'kor', 'ko'): '91',
            ('Kuanyama', 'kua', 'kj'): '92',
            ('Kurdish', 'kur', 'ku'): '93',
            ('Lao', 'lao', 'lo'): '94',
            ('Latin', 'lat', 'la'): '95',
            ('Latvian', 'lav', 'lv'): '96',
            ('Limburgan', 'lim', 'li'): '97',
            ('Lingala', 'lin', 'ln'): '98',
            ('Lithuanian', 'lit', 'lt'): '99',
            ('Luba-Katanga', 'lub', 'lu'): '100',
            ('Luxembourgish', 'ltz', 'lb'): '101',
            ('Macedonian', 'mkd', 'mk'): '102',
            ('Malagasy', 'mlg', 'mg'): '103',
            ('Malay', 'msa', 'ms'): '104',
            ('Malayalam', 'mal', 'ml'): '105',
            ('Maltese', 'mlt', 'mt'): '106',
            ('Mandarin', 'cmn', 'cmn'): '107',
            ('Manx', 'glv', 'gv'): '108',
            ('Maori', 'mri', 'mi'): '109',
            ('Marathi', 'mar', 'mr'): '110',
            ('Marshallese', 'mah', 'mh'): '111',
            ('Mongolian', 'mon', 'mn'): '112',
            ('Nauru', 'nau', 'na'): '113',
            ('Navajo', 'nav', 'nv'): '114',
            ('Ndebele, North', 'nde', 'nd'): '115',
            ('Ndebele, South', 'nbl', 'nr'): '116',
            ('Ndonga', 'ndo', 'ng'): '117',
            ('Nepali', 'nep', 'ne'): '118',
            ('Northern Sami', 'sme', 'se'): '119',
            ('Norwegian', 'nor', 'no'): '120',
            ('Norwegian Nynorsk', 'nno', 'nn'): '121',
            ('Occitan (post 1500)', 'oci', 'oc'): '122',
            ('Ojibwa', 'oji', 'oj'): '123',
            ('Oriya', 'ori', 'or'): '124',
            ('Oromo', 'orm', 'om'): '125',
            ('Ossetian', 'oss', 'os'): '126',
            ('Pali', 'pli', 'pi'): '127',
            ('Panjabi', 'pan', 'pa'): '128',
            ('Persian', 'fas', 'fa'): '129',
            ('Polish', 'pol', 'pl'): '130',
            ('Portuguese', 'por', 'pt'): '131',
            ('Pushto', 'pus', 'ps'): '132',
            ('Quechua', 'que', 'qu'): '133',
            ('Romanian', 'ron', 'ro'): '134',
            ('Romansh', 'roh', 'rm'): '135',
            ('Rundi', 'run', 'rn'): '136',
            ('Russian', 'rus', 'ru'): '137',
            ('Samoan', 'smo', 'sm'): '138',
            ('Sango', 'sag', 'sg'): '139',
            ('Sanskrit', 'san', 'sa'): '140',
            ('Sardinian', 'srd', 'sc'): '141',
            ('Serbian', 'srp', 'sr'): '142',
            ('Shona', 'sna', 'sn'): '143',
            ('Sichuan Yi', 'iii', 'ii'): '144',
            ('Sindhi', 'snd', 'sd'): '145',
            ('Sinhala', 'sin', 'si'): '146',
            ('Slovak', 'slk', 'sk'): '147',
            ('Slovenian', 'slv', 'sl'): '148',
            ('Somali', 'som', 'so'): '149',
            ('Sotho, Southern', 'sot', 'st'): '150',
            ('Spanish', 'spa', 'es'): '151',
            ('Sundanese', 'sun', 'su'): '152',
            ('Swahili', 'swa', 'sw'): '153',
            ('Swati', 'ssw', 'ss'): '154',
            ('Swedish', 'swe', 'sv'): '155',
            ('Tagalog', 'tgl', 'tl'): '156',
            ('Tahitian', 'tah', 'ty'): '157',
            ('Tajik', 'tgk', 'tg'): '158',
            ('Tamil', 'tam', 'ta'): '159',
            ('Tatar', 'tat', 'tt'): '160',
            ('Telugu', 'tel', 'te'): '161',
            ('Thai', 'tha', 'th'): '162',
            ('Tibetan', 'bod', 'bo'): '163',
            ('Tigrinya', 'tir', 'ti'): '164',
            ('Tongan', 'ton', 'to'): '165',
            ('Tsonga', 'tso', 'ts'): '166',
            ('Tswana', 'tsn', 'tn'): '167',
            ('Turkish', 'tur', 'tr'): '168',
            ('Turkmen', 'tuk', 'tk'): '169',
            ('Twi', 'twi', 'tw'): '170',
            ('Uighur', 'uig', 'ug'): '171',
            ('Ukrainian', 'ukr', 'uk'): '172',
            ('Urdu', 'urd', 'ur'): '173',
            ('Uzbek', 'uzb', 'uz'): '174',
            ('Venda', 'ven', 've'): '175',
            ('Vietnamese', 'vie', 'vi'): '176',
            ('Volapük', 'vol', 'vo'): '177',
            ('Walloon', 'wln', 'wa'): '178',
            ('Welsh', 'cym', 'cy'): '179',
            ('Western Frisian', 'fry', 'fy'): '180',
            ('Wolof', 'wol', 'wo'): '181',
            ('Xhosa', 'xho', 'xh'): '182',
            ('Yiddish', 'yid', 'yi'): '183',
            ('Yoruba', 'yor', 'yo'): '184',
            ('Zhuang', 'zha', 'za'): '185',
            ('Zulu', 'zul', 'zu'): '186',
        }

        if self.tracker == 'PHD':
            all_lang_map.update({
                ('Portuguese (BR)', 'por', 'pt-br'): '187',
                ('Filipino', 'fil', 'fil'): '189',
                ('Mooré', 'mos', 'mos'): '188',
            })

        if self.tracker == 'AZ':
            all_lang_map.update({
                ('Portuguese (BR)', 'por', 'pt-br'): '189',
                ('Filipino', 'fil', 'fil'): '188',
                ('Mooré', 'mos', 'mos'): '187',
            })

        if self.tracker == 'CZ':
            all_lang_map.update({
                ('Portuguese (BR)', 'por', 'pt-br'): '187',
                ('Mooré', 'mos', 'mos'): '188',
                ('Filipino', 'fil', 'fil'): '189',
                ('Bissa', 'bib', 'bib'): '190',
                ('Romani', 'rom', 'rom'): '191',
            })

        self.lang_map: dict[str, str] = {}
        for key_tuple, lang_id in all_lang_map.items():
            for alias in key_tuple:
                if alias:
                    self.lang_map[alias.lower()] = lang_id
