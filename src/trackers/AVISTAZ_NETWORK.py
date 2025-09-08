import asyncio
import bencodepy
import hashlib
import httpx
import json
import os
import re
import uuid
from bs4 import BeautifulSoup
from pathlib import Path
from src.console import console
from src.exceptions import UploadException
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from tqdm.asyncio import tqdm
from typing import Optional
from urllib.parse import urlparse


class AZ_COMMON():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)

    def get_resolution(self, meta):
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

    def get_video_quality(self, meta):
        resolution = meta.get('resolution')

        keyword_map = {
            '1080i': '7',
            '1080p': '3',
            '2160p': '6',
            '4320p': '8',
            '720p': '2',
        }

        return keyword_map.get(resolution.lower())

    async def get_media_code(self, meta, tracker, base_url, session, auth_token):
        self.media_code = ''

        if meta['category'] == 'MOVIE':
            category = '1'
        elif meta['category'] == 'TV':
            category = '2'
        else:
            return False

        search_term = ''
        imdb_info = meta.get('imdb_info', {})
        imdb_id = imdb_info.get('imdbID') if isinstance(imdb_info, dict) else None
        tmdb_id = meta.get('tmdb')
        title = meta['title']

        if imdb_id:
            search_term = imdb_id
        else:
            search_term = title

        ajax_url = f'{base_url}/ajax/movies/{category}?term={search_term}'

        headers = {
            'Referer': f"{base_url}/upload/{meta['category'].lower()}",
            'X-Requested-With': 'XMLHttpRequest'
        }

        for attempt in range(2):
            try:
                if attempt == 1:
                    console.print(f'{tracker}: Trying to search again by ID after adding to media to database...\n')
                    await asyncio.sleep(5)  # Small delay to ensure the DB has been updated

                response = await session.get(ajax_url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data.get('data'):
                    match = None
                    for item in data['data']:
                        if imdb_id and item.get('imdb') == imdb_id:
                            match = item
                            break
                        elif not imdb_id and item.get('tmdb') == str(tmdb_id):
                            match = item
                            break

                    if match:
                        self.media_code = str(match['id'])
                        if attempt == 1:
                            console.print(f"{tracker}: [green]Found new ID at:[/green] {base_url}/{meta['category'].lower()}/{self.media_code}")
                        return True

            except Exception as e:
                console.print(f'{tracker}: Error while trying to fetch media code in attempt {attempt + 1}: {e}')
                break

            if attempt == 0 and not self.media_code:
                console.print(f"\n[{tracker}] The media ([yellow]IMDB:{imdb_id}[/yellow] [blue]TMDB:{tmdb_id}[/blue]) appears to be missing from the site's database.")

                user_choice = input(f"{tracker}: Do you want to add '{title}' to the site database? (y/n): \n").lower()

                if user_choice in ['y', 'yes']:
                    console.print(f'{tracker}: Trying to add to database...')
                    added_successfully = await self.add_media_to_db(meta, title, category, imdb_id, tmdb_id, tracker, base_url, session, auth_token)
                    if not added_successfully:
                        console.print(f'{tracker}: Failed to add media. Aborting.')
                        break
                else:
                    console.print(f'{tracker}: User chose not to add media. Aborting.')
                    break

        if not self.media_code:
            console.print(f'{tracker}: Unable to get media code.')

        return bool(self.media_code)

    async def add_media_to_db(self, meta, title, category, imdb_id, tmdb_id, tracker, base_url, session, auth_token):
        data = {
            '_token': auth_token,
            'type_id': category,
            'title': title,
            'imdb_id': imdb_id if imdb_id else '',
            'tmdb_id': tmdb_id if tmdb_id else '',
        }

        if meta['category'] == 'TV':
            tvdb_id = meta.get('tvdb')
            if tvdb_id:
                data['tvdb_id'] = str(tvdb_id)

        url = f"{base_url}/add/{meta['category'].lower()}"

        headers = {
            'Referer': f'{base_url}/upload',
        }

        try:
            response = await session.post(url, data=data, headers=headers)
            if response.status_code == 302:
                console.print(f'{tracker}: The attempt to add the media to the database appears to have been successful..')
                return True
            else:
                console.print(f'{tracker}: Error adding media to the database. Status: {response.status}')
                return False
        except Exception as e:
            console.print(f'{tracker}: Exception when trying to add media to the database: {e}')
            return False

    async def search_existing(self, meta, tracker, base_url, media_code, session):
        if meta.get('resolution') == '2160p':
            resolution = 'UHD'
        elif meta.get('resolution') in ('720p', '1080p'):
            resolution = meta.get('resolution')
        else:
            resolution = 'all'

        page_url = f'{base_url}/movies/torrents/{media_code}?quality={resolution}'

        dupes = []

        visited_urls = set()

        while page_url and page_url not in visited_urls:

            visited_urls.add(page_url)

            try:
                response = await session.get(page_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                torrent_links = soup.find_all('a', class_='torrent-filename')

                for link in torrent_links:
                    dupes.append(link.get_text(strip=True))

                # Finds the next page
                next_page_tag = soup.select_one('a[rel="next"]')
                if next_page_tag and 'href' in next_page_tag.attrs:
                    page_url = next_page_tag['href']
                else:
                    # if no rel="next", we are at the last page
                    page_url = None

            except httpx.RequestError as e:
                console.log(f'{tracker}: Failed to search for duplicates. {e.request.url}: {e}')
                return dupes

        return dupes

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def validate_credentials(self, meta, tracker, base_url, session):
        try:
            upload_page_url = f'{base_url}/upload'
            response = await session.get(upload_page_url)
            response.raise_for_status()

            if 'login' in str(response.url):
                console.print(f'[{tracker}] Validation failed. The cookie appears to be expired or invalid.')
                return False

            auth_match = re.search(r'name="_token" content="([^"]+)"', response.text)

            if not auth_match:
                console.print(f"{tracker} Validation failed. Could not find 'auth' token on upload page.")
                console.print('This can happen if the site HTML has changed or if the login failed silently..')

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]FailedUpload.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print(f'The server response was saved to {failure_path} for analysis.')
                return False

            self.auth_token = auth_match.group(1)
            return True

        except httpx.TimeoutException:
            console.print(f'[{tracker}] Error in {tracker}: Timeout while trying to validate credentials.')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'[{tracker}] HTTP error validating credentials for {tracker}: Status {e.response.status_code}.')
            return False
        except httpx.RequestError as e:
            console.print(f'[{tracker}] Network error while validating credentials for {tracker}: {e.__class__.__name__}.')
            return False

    async def get_file_info(self, meta):
        info_file_path = ''
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            with open(info_file_path, 'r', encoding='utf-8') as f:
                return f.read()

    async def get_lang(self, meta, tracker):
        self.language_map(tracker)
        if not meta.get('subtitle_languages') or meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=tracker)

        found_subs_strings = meta.get('subtitle_languages', [])
        subtitle_ids = set()
        for lang_str in found_subs_strings:
            target_id = self.lang_map.get(lang_str.lower())
            if target_id:
                subtitle_ids.add(target_id)
        final_subtitle_ids = sorted(list(subtitle_ids))

        found_audio_strings = meta.get('audio_languages', [])
        audio_ids = set()
        for lang_str in found_audio_strings:
            target_id = self.lang_map.get(lang_str.lower())
            if target_id:
                audio_ids.add(target_id)
        final_audio_ids = sorted(list(audio_ids))

        return {
            'subtitles[]': final_subtitle_ids,
            'languages[]': final_audio_ids
        }

    async def img_host(self, meta, tracker, base_url, session, referer, image_bytes: bytes, filename: str) -> Optional[str]:
        upload_url = f'{base_url}/ajax/image/upload'

        headers = {
            'Referer': referer,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
            'Origin': base_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'
        }

        data = {
            '_token': self.auth_token,
            'qquuid': str(uuid.uuid4()),
            'qqfilename': filename,
            'qqtotalfilesize': str(len(image_bytes))
        }

        files = {'qqfile': (filename, image_bytes, 'image/png')}

        try:
            response = await session.post(upload_url, headers=headers, data=data, files=files)

            if response.is_success:
                json_data = response.json()
                if json_data.get('success'):
                    image_id = json_data.get('imageId')
                    return str(image_id)
                else:
                    error_message = json_data.get('error', 'Unknown image host error.')
                    print(f'{tracker}: Error uploading {filename}: {error_message}')
                    return None
            else:
                print(f'{tracker}: Error uploading {filename}: Status {response.status_code} - {response.text}')
                return None
        except Exception as e:
            print(f'{tracker}: Exception when uploading {filename}: {e}')
            return None

    async def get_screenshots(self, meta, tracker, base_url, session, referer):
        screenshot_dir = Path(meta['base_dir']) / 'tmp' / meta['uuid']
        local_files = sorted(screenshot_dir.glob('*.png'))
        results = []

        limit = 3 if meta.get('tv_pack', '') == 0 else 15

        if local_files:
            async def upload_local_file(path):
                with open(path, 'rb') as f:
                    image_bytes = f.read()
                return await self.img_host(meta, tracker, base_url, session, referer, image_bytes, path.name)

            paths = local_files[:limit] if limit else local_files

            for path in tqdm(
                paths,
                total=len(paths),
                desc=f'{tracker}: Uploading screenshots'
            ):
                result = await upload_local_file(path)
                if result:
                    results.append(result)

        else:
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')]
            if len(image_links) < 3:
                raise UploadException(f'UPLOAD FAILED: At least 3 screenshots are required for {tracker}.')

            async def upload_remote_file(url):
                try:
                    response = await session.get(url)
                    response.raise_for_status()
                    image_bytes = response.content
                    filename = os.path.basename(urlparse(url).path) or 'screenshot.png'
                    return await self.img_host(meta, tracker, base_url, session, referer, image_bytes, filename)
                except Exception as e:
                    print(f'Failed to process screenshot from URL {url}: {e}')
                    return None

            links = image_links[:limit] if limit else image_links

            for url in tqdm(
                links,
                total=len(links),
                desc=f'{tracker}: Uploading screenshots'
            ):
                result = await upload_remote_file(url)
                if result:
                    results.append(result)

        if len(results) < 3:
            raise UploadException('UPLOAD FAILED: The image host did not return the minimum number of screenshots.')

        return results

    async def get_requests(self, meta, tracker, base_url, session):
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False

        else:
            try:
                category = meta.get('category').lower()

                if category == 'tv':
                    query = meta['title'] + f" {meta.get('season', '')}{meta.get('episode', '')}"
                else:
                    query = meta['title']

                search_url = f'{base_url}/requests?type={category}&search={query}&condition=new'

                response = await session.get(search_url)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')

                request_rows = soup.select('.table-responsive table tbody tr')

                results = []
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
                    message = f'\n{tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n'
                    for r in results:
                        message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Reward:[/bold green] {r['Reward']}\n"
                        message += f"[bold green]Link:[/bold green] {r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                console.print(f'[{tracker}] An error occurred while fetching requests: {e}')
                return []

    async def fetch_tag_id(self, base_url, session, word):
        tags_url = f'{base_url}/ajax/tags'
        params = {'term': word}

        headers = {
            'Referer': f'{base_url}/upload',
            'X-Requested-With': 'XMLHttpRequest'
        }
        try:
            response = await session.get(tags_url, headers=headers, params=params)
            response.raise_for_status()

            json_data = response.json()

            for tag_info in json_data.get('data', []):
                if tag_info.get('tag') == word:
                    return tag_info.get('id')

        except Exception as e:
            print(f"An unexpected error occurred while processing the tag '{word}': {e}")

        return None

    async def get_tags(self, meta, base_url, session):
        genres = meta.get('keywords', '')
        if not genres:
            return []

        # divides by commas, cleans spaces and normalizes to lowercase
        phrases = [re.sub(r'\s+', ' ', x.strip().lower()) for x in re.split(r',+', genres) if x.strip()]

        words_to_search = set(phrases)

        tasks = [self.fetch_tag_id(base_url, session, word) for word in words_to_search]

        tag_ids_results = await asyncio.gather(*tasks)

        tags = [str(tag_id) for tag_id in tag_ids_results if tag_id is not None]

        if meta.get('personalrelease', False):
            tags.insert(0, '3773')

        return tags

    async def edit_desc(self, meta, tracker):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt"

        description_parts = []

        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            description_parts.append(manual_desc)

        final_description = '\n\n'.join(filter(None, description_parts))
        desc = final_description
        cleanup_patterns = [
            (r'\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]', re.DOTALL, 'NFO'),
            (r'\[/?.*?\]', 0, 'BBCode tag(s)'),
            (r'http[s]?://\S+|www\.\S+', 0, 'Link(s)'),
            (r'\n{3,}', 0, 'Line break(s)')
        ]

        for pattern, flag, removed_type in cleanup_patterns:
            desc, amount = re.subn(pattern, '', desc, flags=flag)
            if amount > 0:
                console.print(f'{tracker}: Deleted {amount} {removed_type} from description.')

        desc = desc.strip()
        desc = desc.replace('\r\n', '\n').replace('\r', '\n')

        paragraphs = re.split(r'\n\s*\n', desc)

        html_parts = []
        for p in paragraphs:
            if not p.strip():
                continue

            p_with_br = p.replace('\n', '<br>')
            html_parts.append(f'<p>{p_with_br}</p>')

        final_html_desc = '\r\n'.join(html_parts)

        meta['z_images'] = False
        rehost_images = self.config['TRACKERS'][tracker].get('img_rehost', True)
        if not rehost_images:
            limit = 3 if meta.get('tv_pack', '') == 0 else 15
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')]
            thumb_links = [img.get('img_url') for img in meta.get('image_list', []) if img.get('img_url')]

            raw_links = []
            thumb_links_limited = []

            if len(image_links) >= 3 and 'imgbox.com' in image_links[0]:
                raw_links = image_links[:limit]
                thumb_links_limited = thumb_links[:limit]
            else:
                image_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/reuploaded_images.json"
                if os.path.exists(image_data_file):
                    try:
                        with open(image_data_file, 'r') as img_file:
                            image_data = json.load(img_file)

                            if 'image_list' in image_data and image_data.get('image_list') and 'imgbox.com' in image_data.get('image_list', [{}])[0].get('raw_url', ''):
                                if len(image_data.get('image_list', [])) >= 3:
                                    json_raw_links = [img.get('raw_url') for img in image_data.get('image_list', []) if img.get('raw_url')]
                                    json_thumb_links = [img.get('img_url') for img in image_data.get('image_list', []) if img.get('img_url')]

                                    raw_links = json_raw_links[:limit]
                                    thumb_links_limited = json_thumb_links[:limit]

                    except Exception as e:
                        console.print(f"[yellow]Could not load saved image data: {str(e)}")

            if len(raw_links) >= 3:
                image_html = '<br><br>'
                for i, (raw_url, thumb_url) in enumerate(zip(raw_links, thumb_links_limited)):
                    image_html += f'<a href="{raw_url}"><img src="{thumb_url}" alt="Screenshot {i+1}"></a> '
                final_html_desc += image_html
                meta['z_images'] = True

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(final_html_desc)

        return final_html_desc

    async def create_task_id(self, meta, tracker, base_url, session, auth_token, source_flag, default_announce):
        await self.get_media_code(meta, tracker, base_url, session, auth_token)
        data = {
            '_token': self.auth_token,
            'type_id': await self.get_cat_id(meta['category']),
            'movie_id': self.media_code,
            'media_info': await self.get_file_info(meta),
        }

        if not meta.get('debug', False):
            try:
                await self.common.edit_torrent(meta, tracker, source_flag, announce_url=default_announce)
                upload_url_step1 = f"{base_url}/upload/{meta['category'].lower()}"
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent"

                with open(torrent_path, 'rb') as torrent_file:
                    files = {'torrent_file': (os.path.basename(torrent_path), torrent_file, 'application/x-bittorrent')}
                    torrent_data = bencodepy.decode(torrent_file.read())
                    info = bencodepy.encode(torrent_data[b'info'])
                    info_hash = hashlib.sha1(info).hexdigest()

                    task_response = await session.post(upload_url_step1, data=data, files=files)

                    if task_response.status_code == 302 and 'Location' in task_response.headers:
                        redirect_url = task_response.headers['Location']

                        match = re.search(r'/(\d+)$', redirect_url)
                        if not match:
                            console.print(f"{tracker}: Could not extract 'task_id' from redirect URL: {redirect_url}")
                            meta['skipping'] = f'{tracker}'
                            return

                        task_id = match.group(1)

                        return {
                            'task_id': task_id,
                            'info_hash': info_hash,
                            'redirect_url': redirect_url,
                        }

                    else:
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]FailedUpload_Step1.html"
                        with open(failure_path, 'w', encoding='utf-8') as f:
                            f.write(task_response.text)
                        status_message = f'''[red]Step 1 of upload failed to {tracker}. Status: {task_response.status_code}, URL: {task_response.url}[/red].
                                            [yellow]The HTML response was saved to '{failure_path}' for analysis.[/yellow]'''

            except Exception as e:
                status_message = f'[red]An unexpected error occurred while uploading to {tracker}: {e}[/red]'
                meta['skipping'] = f'{tracker}'
                return

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][tracker]['status_message'] = status_message

    async def fetch_data(self, meta, name, rip_type, tracker, base_url, session, auth_token, source_flag, default_announce):
        task_info = await self.create_task_id(
            meta,
            tracker,
            base_url,
            session,
            auth_token,
            source_flag,
            default_announce
        )
        lang_info = await self.get_lang(meta, tracker) or {}

        data = {
            '_token': self.auth_token,
            'torrent_id': '',
            'type_id': await self.get_cat_id(meta['category']),
            'file_name': name,
            'anon_upload': '',
            'description': await self.edit_desc(meta, tracker),
            'qqfile': '',
            'rip_type_id': rip_type,
            'video_quality_id': self.get_video_quality(meta),
            'video_resolution': self.get_resolution(meta),
            'movie_id': self.media_code,
            'languages[]': lang_info.get('languages[]'),
            'subtitles[]': lang_info.get('subtitles[]'),
            'media_info': await self.get_file_info(meta),
            'tags[]': await self.get_tags(meta, base_url, session),
            }

        # TV
        if meta.get('category') == 'TV':
            data.update({
                'tv_collection': '1' if meta.get('tv_pack') == 0 else '2',
                'tv_season': meta.get('season_int', ''),
                'tv_episode': meta.get('episode_int', ''),
                })

        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][tracker].get('anon', False))
        if anon:
            data.update({
                'anon_upload': '1'
            })

        if not meta.get('debug', False):
            try:
                self.upload_url_step2 = task_info.get('redirect_url')

                # task_id and screenshot cannot be called until Step 1 is completed
                data.update({
                    'info_hash': task_info.get('info_hash'),
                    'task_id': task_info.get('task_id'),
                })
                if not meta['z_images']:
                    data.update({
                        'screenshots[]': await self.get_screenshots(meta, tracker, base_url, session, referer=self.upload_url_step2)
                    })

            except Exception as e:
                console.print(f'{tracker}: An unexpected error occurred while uploading: {e}')

        return data

    async def upload(self, meta, name, rip_type, tracker, base_url, session, auth_token, source_flag, default_announce):
        data = await self.fetch_data(meta, name, rip_type, tracker, base_url, session, auth_token, source_flag, default_announce)
        requests = await self.get_requests(meta, tracker, base_url, session)
        status_message = ''

        if not meta.get('debug', False):
            response = await session.post(self.upload_url_step2, data=data)

            if response.status_code == 302:
                torrent_url = response.headers['Location']

                torrent_id = ''
                match = re.search(r'/torrent/(\d+)', torrent_url)
                if match:
                    torrent_id = match.group(1)
                    meta['tracker_status'][tracker]['torrent_id'] = torrent_id

                # Even if you are uploading, you still need to download the .torrent from the website
                # because it needs to be registered as a download before you can start seeding
                download_url = torrent_url.replace('/torrent/', '/download/torrent/')
                register_download = await session.get(download_url)
                if register_download.status_code != 200:
                    print(f"Unable to register your upload in your download history, please go to the URL and download the torrent file before you can start seeding: {torrent_url}"
                          f"Error: {register_download.status_code}")

                announce_url = self.config['TRACKERS'][tracker]['announce_url']
                await self.common.add_tracker_torrent(meta, tracker, source_flag, announce_url, torrent_url)

                status_message = 'Torrent uploaded successfully.'

                if requests:
                    status_message += ' Your upload may fulfill existing requests, check prior console logs.'

            else:
                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]FailedUpload_Step2.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                status_message = (
                    f'Step 2 of upload to {tracker} failed.\n'
                    f'Status code: {response.status_code}\n'
                    f'URL: {response.url}\n'
                    f"The HTML response has been saved to '{failure_path}' for analysis."
                )
                meta['skipping'] = f'{tracker}'
                return

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][tracker]['status_message'] = status_message

    def language_map(self, tracker):
        self.all_lang_map = {
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
            ('Mandarin', 'cmn', 'zh'): '107',
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

        if tracker == 'PHD':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '187',
                ('Filipino', 'fil', 'fil'): '189',
                ('Mooré', 'mos', 'mos'): '188',
            })

        if tracker == 'AZ':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '189',
                ('Filipino', 'fil', 'fil'): '188',
                ('Mooré', 'mos', 'mos'): '187',
            })

        if tracker == 'CZ':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '187',
                ('Mooré', 'mos', 'mos'): '188',
                ('Filipino', 'fil', 'fil'): '189',
                ('Bissa', 'bib', 'bib'): '190',
                ('Romani', 'rom', 'rom'): '191',
            })

        self.lang_map = {}
        for key_tuple, lang_id in self.all_lang_map.items():
            lang_name, code3, code2 = key_tuple

            self.lang_map[lang_name.lower()] = lang_id

            if code3:
                self.lang_map[code3.lower()] = lang_id

            if code2:
                self.lang_map[code2.lower()] = lang_id
