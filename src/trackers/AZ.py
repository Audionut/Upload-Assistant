# -*- coding: utf-8 -*-
import asyncio
import bencodepy
import hashlib
import httpx
import json
import os
import platform
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


class AZ():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'AZ'
        self.source_flag = 'AvistaZ'
        self.banned_groups = ['']
        self.base_url = 'https://avistaz.to'
        self.torrent_url = 'https://avistaz.to/torrent/'
        self.announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
        self.rehost_images = config['TRACKERS']['AZ'].get('img_rehost', True)
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.signature = ''

    async def rules(self, meta):
        meta['az_rule'] = ''
        warning = f'{self.tracker} RULE WARNING: '

        is_disc = False
        if meta.get('is_disc', ''):
            is_disc = True

        video_codec = meta.get('video_codec', '')
        if video_codec:
            video_codec = video_codec.strip().lower()

        video_encode = meta.get('video_encode', '')
        if video_encode:
            video_encode = video_encode.strip().lower()

        type = meta.get('type', '')
        if type:
            type = type.strip().lower()

        source = meta.get('source', '')
        if source:
            source = source.strip().lower()

        # This also checks the rule 'FANRES content is not allowed'
        if meta['category'] not in ('MOVIE', 'TV'):
            meta['az_rule'] = (
                warning + 'The only allowed content to be uploaded are Movies and TV Shows.\n'
                'Anything else, like games, music, software and porn is not allowed!'
            )
            return False

        if meta.get('anime', False):
            meta['az_rule'] = warning + "Upload Anime content to our sister site AnimeTorrents.me instead. If it's on AniDB, it's an anime."
            return False

        # https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes

        africa = [
            'AO', 'BF', 'BI', 'BJ', 'BW', 'CD', 'CF', 'CG', 'CI', 'CM', 'CV', 'DJ', 'DZ', 'EG', 'EH',
            'ER', 'ET', 'GA', 'GH', 'GM', 'GN', 'GQ', 'GW', 'IO', 'KE', 'KM', 'LR', 'LS', 'LY', 'MA',
            'MG', 'ML', 'MR', 'MU', 'MW', 'MZ', 'NA', 'NE', 'NG', 'RE', 'RW', 'SC', 'SD', 'SH', 'SL',
            'SN', 'SO', 'SS', 'ST', 'SZ', 'TD', 'TF', 'TG', 'TN', 'TZ', 'UG', 'YT', 'ZA', 'ZM', 'ZW'
        ]
        america = [
            'AG', 'AI', 'AR', 'AW', 'BB', 'BL', 'BM', 'BO', 'BQ', 'BR', 'BS', 'BV', 'BZ', 'CA', 'CL',
            'CO', 'CR', 'CU', 'CW', 'DM', 'DO', 'EC', 'FK', 'GD', 'GF', 'GL', 'GP', 'GS', 'GT', 'GY',
            'HN', 'HT', 'JM', 'KN', 'KY', 'LC', 'MF', 'MQ', 'MS', 'MX', 'NI', 'PA', 'PE', 'PM', 'PR',
            'PY', 'SR', 'SV', 'SX', 'TC', 'TT', 'US', 'UY', 'VC', 'VE', 'VG', 'VI'
        ]
        asia = [
            'AE', 'AF', 'AM', 'AZ', 'BD', 'BH', 'BN', 'BT', 'CN', 'CY', 'GE', 'HK', 'ID', 'IL', 'IN',
            'IQ', 'IR', 'JO', 'JP', 'KG', 'KH', 'KP', 'KR', 'KW', 'KZ', 'LA', 'LB', 'LK', 'MM', 'MN',
            'MO', 'MV', 'MY', 'NP', 'OM', 'PH', 'PK', 'PS', 'QA', 'SA', 'SG', 'SY', 'TH', 'TJ', 'TL',
            'TM', 'TR', 'TW', 'UZ', 'VN', 'YE'
        ]
        europe = [
            'AD', 'AL', 'AT', 'AX', 'BA', 'BE', 'BG', 'BY', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FO', 'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT',
            'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE',
            'SI', 'SJ', 'SK', 'SM', 'UA', 'VA'
        ]
        oceania = [
            'AS', 'AU', 'CC', 'CK', 'CX', 'FJ', 'FM', 'GU', 'HM', 'KI', 'MH', 'MP', 'NC', 'NF', 'NR',
            'NU', 'NZ', 'PF', 'PG', 'PN', 'PW', 'SB', 'TK', 'TO', 'TV', 'UM', 'VU', 'WF', 'WS'
        ]

        az_allowed_countries = [
            'BD', 'BN', 'BT', 'CN', 'HK', 'ID', 'IN', 'JP', 'KH', 'KP', 'KR', 'LA', 'LK',
            'MM', 'MN', 'MO', 'MY', 'NP', 'PH', 'PK', 'SG', 'TH', 'TL', 'TW', 'VN'
        ]

        phd_countries = [
            'AG', 'AI', 'AU', 'BB', 'BM', 'BS', 'BZ', 'CA', 'CW', 'DM', 'GB', 'GD', 'IE',
            'JM', 'KN', 'KY', 'LC', 'MS', 'NZ', 'PR', 'TC', 'TT', 'US', 'VC', 'VG', 'VI',
        ]

        all_countries = africa + america + asia + europe + oceania
        cinemaz_countries = list(set(all_countries) - set(phd_countries) - set(az_allowed_countries))

        origin_countries_codes = meta.get('origin_country', [])

        if any(code in az_allowed_countries for code in origin_countries_codes):
            return True

        elif any(code in phd_countries for code in origin_countries_codes):
            meta['az_rule'] = (
                warning + 'DO NOT upload content from major English speaking countries '
                '(USA, UK, Canada, etc). Upload this to our sister site PrivateHD.to instead.'
            )
            return False

        elif any(code in cinemaz_countries for code in origin_countries_codes):
            meta['az_rule'] = (
                warning + 'DO NOT upload non-allowed Asian or Western content. '
                'Upload this content to our sister site CinemaZ.to instead.'
            )
            return False

        if not is_disc:
            ext = os.path.splitext(meta['filelist'][0])[1].lower()
            allowed_extensions = {'.mkv': 'MKV', '.mp4': 'MP4', '.avi': 'AVI'}
            container = allowed_extensions.get(ext)
            if container is None:
                meta['az_rule'] = warning + 'Allowed containers: MKV, MP4, AVI.'
                return False

        '''
        Video Codecs:
            Allowed: H264/x264/AVC, H265/x265/HEVC, DivX/Xvid
            Exceptions:
                MPEG2 for Full DVD discs and HDTV recordings
                VC-1/MPEG2 for Bluray only if that's what is on the disc
            Not Allowed: Any codec not mentioned above is not allowed!
        '''
        if not is_disc:
            if video_codec not in ('avc', 'h.264', 'h.265', 'x264', 'x265', 'hevc', 'divx', 'xvid'):
                meta['az_rule'] = (
                                warning +
                                f'Video codec not allowed in your upload: {video_codec}.\n'
                                'Allowed: H264/x264/AVC, H265/x265/HEVC, DivX/Xvid\n'
                                'Exceptions:\n'
                                '    MPEG2 for Full DVD discs and HDTV recordings\n'
                                "    VC-1/MPEG2 for Bluray only if that's what is on the disc"
                                )
                return False

        resolution = int(meta.get('resolution').lower().replace('p', '').replace('i', ''))
        if resolution > 600:
            meta['az_rule'] = warning + 'Video: A minimum resolution of 600 pixel width.'
            return False

        '''
        Audio Codecs:
            Allowed: MP3, AAC, HE-AAC, AC3 (Dolby Digital), E-AC3, Dolby TrueHD, DTS, DTS-HD (MA), FLAC
            Not Allowed: Any codec not mentioned above is not allowed!
            Exceptions: Source is OPUS and upload is untouched from the source
                Note: AC3(DD) / E-AC3 (DDP) will not trump existing AAC uploads with same audio bitrate and channels.
                (Considering all else is equal and only audio codecs are different)
        '''
        if is_disc:
            pass
        else:
            allowed_keywords = [
                'AC3', 'Audio Layer III', 'MP3', 'Dolby Digital', 'Dolby TrueHD',
                'DTS', 'DTS-HD', 'FLAC', 'AAC', 'Dolby', 'PCM', 'LPCM'
            ]

            is_untouched_opus = False
            audio_field = meta.get('audio', '')
            if isinstance(audio_field, str) and 'opus' in audio_field.lower() and bool(meta.get('untouched', False)):
                is_untouched_opus = True

            audio_tracks = []
            media_tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            for track in media_tracks:
                if track.get('@type') == 'Audio':
                    codec_info = track.get('Format_Commercial_IfAny') or track.get('Format')
                    codec = codec_info if isinstance(codec_info, str) else ''
                    audio_tracks.append({
                        'codec': codec,
                        'language': track.get('Language', '')
                    })

            invalid_codecs = []
            for track in audio_tracks:
                codec = track['codec']
                if not codec:
                    continue

                if 'opus' in codec.lower():
                    if is_untouched_opus:
                        continue
                    else:
                        invalid_codecs.append(codec)
                        continue

                is_allowed = any(kw.lower() in codec.lower() for kw in allowed_keywords)
                if not is_allowed:
                    invalid_codecs.append(codec)

            if invalid_codecs:
                unique_invalid_codecs = sorted(list(set(invalid_codecs)))
                meta['az_rule'] = (
                    warning + f"Unallowed audio codec(s) detected: {', '.join(unique_invalid_codecs)}\n"
                    f'Allowed codecs: AC3 (Dolby Digital), Dolby TrueHD, DTS, DTS-HD (MA), FLAC, AAC, MP3, etc.\n'
                    f'Exceptions: Untouched Opus from source; Uncompressed codecs from Blu-ray discs (PCM, LPCM).'
                )
                return False

        return True

    def edit_name(self, meta):
        upload_name = meta.get('name').replace(meta['aka'], '')

        tag_lower = meta['tag'].lower()
        invalid_tags = ['nogrp', 'nogroup', 'unknown', '-unk-']

        if meta['tag'] == '' or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                upload_name = re.sub(f'-{invalid_tag}', '', upload_name, flags=re.IGNORECASE)
            upload_name = f'{upload_name}-NoGroup'

        return upload_name

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

        if meta.get('sd', False):
            return '1'

        keyword_map = {
            '1080i': '7',
            '1080p': '3',
            '2160p': '6',
            '4320p': '8',
            '720p': '2',
        }

        return keyword_map.get(resolution.lower())

    def get_rip_type(self, meta):
        source_type = str(meta.get('type', '') or '').strip().lower()
        source = str(meta.get('source', '') or '').strip().lower()
        is_disc = str(meta.get('is_disc', '') or '').strip().upper()

        if is_disc == 'BDMV':
            return '15'
        if is_disc == 'HDDVD':
            return '4'
        if is_disc == 'DVD':
            return '4'

        if source == 'dvd' and source_type == 'remux':
            return '17'

        if source_type == 'remux':
            if source == 'dvd':
                return '17'
            if source in ('bluray', 'blu-ray'):
                return '14'

        keyword_map = {
            'bdrip': '1',
            'brrip': '3',
            'encode': '2',
            'dvdrip': '5',
            'hdrip': '6',
            'hdtv': '7',
            'sdtv': '16',
            'vcd': '8',
            'vcdrip': '8',
            'vhsrip': '10',
            'vodrip': '11',
            'webdl': '12',
            'webrip': '13',
        }

        return keyword_map.get(source_type.lower())

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f'{self.tracker}: Cookie file for {self.tracker} not found: {cookie_file}')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            upload_page_url = f'{self.base_url}/upload'
            response = await self.session.get(upload_page_url)
            response.raise_for_status()

            if 'login' in str(response.url):
                console.print(f'{self.tracker}: Validation failed. The cookie appears to be expired or invalid.')
                return False

            auth_match = re.search(r'name="_token" content="([^"]+)"', response.text)

            if not auth_match:
                console.print(f"{self.tracker} Validation failed. Could not find 'auth' token on upload page.")
                console.print('This can happen if the site HTML has changed or if the login failed silently..')

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print(f'The server response was saved to {failure_path} for analysis.')
                return False

            self.auth_token = auth_match.group(1)
            return True

        except httpx.TimeoutException:
            console.print(f'{self.tracker}: Error in {self.tracker}: Timeout while trying to validate credentials.')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'{self.tracker}: HTTP error validating credentials for {self.tracker}: Status {e.response.status_code}.')
            return False
        except httpx.RequestError as e:
            console.print(f'{self.tracker}: Network error while validating credentials for {self.tracker}: {e.__class__.__name__}.')
            return False

    async def search_existing(self, meta, disctype):
        if not await self.rules(meta):
            console.print(f"[red]{meta['az_rule']}[/red]")
            meta['skipping'] = f'{self.tracker}'
            return

        if not await self.get_media_code(meta):
            console.print((f"{self.tracker}: This media is not registered, please add it to the database by following this link: {self.base_url}/add/{meta['category'].lower()}"))
            meta['skipping'] = f'{self.tracker}'
            return

        if meta.get('resolution') == '2160p':
            resolution = 'UHD'
        elif meta.get('resolution') in ('720p', '1080p'):
            resolution = meta.get('resolution')
        else:
            resolution = 'all'

        page_url = f'{self.base_url}/movies/torrents/{self.media_code}?quality={resolution}'

        dupes = []

        visited_urls = set()

        while page_url and page_url not in visited_urls:

            visited_urls.add(page_url)

            try:
                response = await self.session.get(page_url)
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
                console.log(f'{self.tracker}: Failed to search for duplicates. {e.request.url}: {e}')
                return dupes

        return dupes

    async def get_media_code(self, meta):
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

        ajax_url = f'{self.base_url}/ajax/movies/{category}?term={search_term}'

        headers = {
            'Referer': f"{self.base_url}/upload/{meta['category'].lower()}",
            'X-Requested-With': 'XMLHttpRequest'
        }

        for attempt in range(2):
            try:
                if attempt == 1:
                    console.print(f'{self.tracker}: Trying to search again by ID after adding to media to database...\n')
                    await asyncio.sleep(5)  # Small delay to ensure the DB has been updated

                response = await self.session.get(ajax_url, headers=headers)
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
                            console.print(f"{self.tracker}: [green]Found new ID at:[/green] {self.base_url}/{meta['category'].lower()}/{self.media_code}")
                        return True

            except Exception as e:
                console.print(f'{self.tracker}: Error while trying to fetch media code in attempt {attempt + 1}: {e}')
                break

            if attempt == 0 and not self.media_code:
                console.print(f"\n[{self.tracker}] The media ([yellow]IMDB:{imdb_id}[/yellow] [blue]TMDB:{tmdb_id}[/blue]) appears to be missing from the site's database.")

                user_choice = input(f"{self.tracker}: Do you want to add '{title}' to the site database? (y/n): \n").lower()

                if user_choice in ['y', 'yes']:
                    console.print(f'{self.tracker}: Trying to add to database...')
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

    async def add_media_to_db(self, meta, title, category, imdb_id, tmdb_id):
        data = {
            '_token': self.auth_token,
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
            response = await self.session.post(url, data=data, headers=headers)
            if response.status_code == 302:
                console.print(f'{self.tracker}: The attempt to add the media to the database appears to have been successful..')
                return True
            else:
                console.print(f'{self.tracker}: Error adding media to the database. Status: {response.status}')
                return False
        except Exception as e:
            console.print(f'{self.tracker}: Exception when trying to add media to the database: {e}')
            return False

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_file_info(self, meta):
        info_file_path = ''
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            with open(info_file_path, 'r', encoding='utf-8') as f:
                return f.read()

    async def get_lang(self, meta):
        self.common.z_language_map()
        if not meta.get('subtitle_languages') or meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

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

    async def img_host(self, meta, image_bytes: bytes, filename: str) -> Optional[str]:
        upload_url = f'{self.base_url}/ajax/image/upload'

        headers = {
            'Referer': self.upload_url_step2,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
            'Origin': self.base_url,
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
            response = await self.session.post(upload_url, headers=headers, data=data, files=files)

            if response.is_success:
                json_data = response.json()
                if json_data.get('success'):
                    image_id = json_data.get('imageId')
                    return str(image_id)
                else:
                    error_message = json_data.get('error', 'Unknown image host error.')
                    print(f'Error uploading {filename}: {error_message}')
                    return None
            else:
                print(f'Error uploading {filename}: Status {response.status_code} - {response.text}')
                return None
        except Exception as e:
            print(f'Exception when uploading {filename}: {e}')
            return None

    async def get_screenshots(self, meta):
        screenshot_dir = Path(meta['base_dir']) / 'tmp' / meta['uuid']
        local_files = sorted(screenshot_dir.glob('*.png'))
        results = []

        limit = 3 if meta.get('tv_pack', '') == 0 else 15

        if local_files:
            async def upload_local_file(path):
                with open(path, 'rb') as f:
                    image_bytes = f.read()
                return await self.img_host(meta, image_bytes, path.name)

            paths = local_files[:limit] if limit else local_files

            for path in tqdm(
                paths,
                total=len(paths),
                desc=f'{self.tracker}: Uploading screenshots'
            ):
                result = await upload_local_file(path)
                if result:
                    results.append(result)

        else:
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')]
            if len(image_links) < 3:
                raise UploadException(f'UPLOAD FAILED: At least 3 screenshots are required for {self.tracker}.')

            async def upload_remote_file(url):
                try:
                    response = await self.session.get(url)
                    response.raise_for_status()
                    image_bytes = response.content
                    filename = os.path.basename(urlparse(url).path) or 'screenshot.png'
                    return await self.img_host(meta, image_bytes, filename)
                except Exception as e:
                    print(f'Failed to process screenshot from URL {url}: {e}')
                    return None

            links = image_links[:limit] if limit else image_links

            for url in tqdm(
                links,
                total=len(links),
                desc=f'{self.tracker}: Uploading screenshots'
            ):
                result = await upload_remote_file(url)
                if result:
                    results.append(result)

        if len(results) < 3:
            raise UploadException('UPLOAD FAILED: The image host did not return the minimum number of screenshots.')

        return results

    async def get_requests(self, meta):
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False

        else:
            try:
                category = meta.get('category').lower()

                if category == 'tv':
                    query = meta['title'] + f" {meta.get('season', '')}{meta.get('episode', '')}"
                else:
                    query = meta['title']

                search_url = f'{self.base_url}/requests?type={category}&search={query}&condition=new'

                response = await self.session.get(search_url)
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
                    message = f'\n{self.tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n'
                    for r in results:
                        message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Reward:[/bold green] {r['Reward']}\n"
                        message += f"[bold green]Link:[/bold green] {r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                console.print(f'{self.tracker}: An error occurred while fetching requests: {e}')
                return []

    async def fetch_tag_id(self, meta, word):
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
                    return tag_info.get('id')

        except Exception as e:
            print(f"An unexpected error occurred while processing the tag '{word}': {e}")

        return None

    async def get_tags(self, meta):
        genres = meta.get('keywords', '')
        if not genres:
            return []

        # divides by commas, cleans spaces and normalizes to lowercase
        phrases = [re.sub(r'\s+', ' ', x.strip().lower()) for x in re.split(r',+', genres) if x.strip()]

        words_to_search = set(phrases)

        tasks = [self.fetch_tag_id(self.session, word) for word in words_to_search]

        tag_ids_results = await asyncio.gather(*tasks)

        tags = [str(tag_id) for tag_id in tag_ids_results if tag_id is not None]

        if meta.get('personalrelease', False):
            tags.insert(0, '3773')

        return tags

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

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
                console.print(f'{self.tracker}: Deleted {amount} {removed_type} from description.')

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
        if not self.rehost_images:
            limit = 3 if meta.get('tv_pack', '') == 0 else 15
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')]
            thumb_links = [img.get('img_url') for img in meta.get('image_list', []) if img.get('img_url')]

            raw_links = []
            thumb_links_limited = []

            if len(image_links) >= 3:
                if 'imgbox.com' in image_links[0]:
                    raw_links = image_links[:limit]
                    thumb_links_limited = thumb_links[:limit]
            else:
                image_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/image_data.json"
                if os.path.exists(image_data_file) and not meta.get('image_list'):
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

    async def create_task_id(self, meta):
        await self.get_media_code(meta)

        data = {
            '_token': self.auth_token,
            'type_id': await self.get_cat_id(meta['category']),
            'movie_id': self.media_code,
            'media_info': await self.get_file_info(meta),
        }

        if not meta.get('debug', False):
            try:
                await self.common.edit_torrent(meta, self.tracker, self.source_flag, announce_url='https://tracker.avistaz.to/announce')
                upload_url_step1 = f"{self.base_url}/upload/{meta['category'].lower()}"
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

                with open(torrent_path, 'rb') as torrent_file:
                    files = {'torrent_file': (os.path.basename(torrent_path), torrent_file, 'application/x-bittorrent')}
                    torrent_data = bencodepy.decode(torrent_file.read())
                    info = bencodepy.encode(torrent_data[b'info'])
                    info_hash = hashlib.sha1(info).hexdigest()

                    task_response = await self.session.post(upload_url_step1, data=data, files=files)

                    if task_response.status_code == 302 and 'Location' in task_response.headers:
                        redirect_url = task_response.headers['Location']

                        match = re.search(r'/(\d+)$', redirect_url)
                        if not match:
                            console.print(f"{self.tracker}: Could not extract 'task_id' from redirect URL: {redirect_url}")
                            meta['skipping'] = f'{self.tracker}'
                            return

                        task_id = match.group(1)

                        return {
                            'task_id': task_id,
                            'info_hash': info_hash,
                            'redirect_url': redirect_url,
                        }

                    else:
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step1.html"
                        with open(failure_path, 'w', encoding='utf-8') as f:
                            f.write(task_response.text)
                        status_message = f'''[red]Step 1 of upload failed to {self.tracker}. Status: {task_response.status_code}, URL: {task_response.url}[/red].
                                            [yellow]The HTML response was saved to '{failure_path}' for analysis.[/yellow]'''

            except Exception as e:
                status_message = f'[red]An unexpected error occurred while uploading to {self.tracker}: {e}[/red]'
                meta['skipping'] = f'{self.tracker}'
                return

        else:
            console.print(data)
            status_message = f'{self.tracker}: Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message

    async def fetch_data(self, meta):
        await self.validate_credentials(meta)
        task_info = await self.create_task_id(meta)
        lang_info = await self.get_lang(meta) or {}

        data = {
            '_token': self.auth_token,
            'torrent_id': '',
            'type_id': await self.get_cat_id(meta['category']),
            'file_name': self.edit_name(meta),
            'anon_upload': '',
            'description': await self.edit_desc(meta),
            'qqfile': '',
            'rip_type_id': self.get_rip_type(meta),
            'video_quality_id': self.get_video_quality(meta),
            'video_resolution': self.get_resolution(meta),
            'movie_id': self.media_code,
            'languages[]': lang_info.get('languages[]'),
            'subtitles[]': lang_info.get('subtitles[]'),
            'media_info': await self.get_file_info(meta),
            'tags[]': await self.get_tags(meta),
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
                self.upload_url_step2 = task_info.get('redirect_url')

                # task_id and screenshot cannot be called until Step 1 is completed
                data.update({
                    'info_hash': task_info.get('info_hash'),
                    'task_id': task_info.get('task_id'),
                })
                if not meta['z_images']:
                    data.update({
                        'screenshots[]': await self.get_screenshots(meta),
                    })

            except Exception as e:
                console.print(f'{self.tracker}: An unexpected error occurred while uploading: {e}')

        return data

    async def upload(self, meta, disctype):
        data = await self.fetch_data(meta)
        requests = await self.get_requests(meta)
        status_message = ''

        if not meta.get('debug', False):
            response = await self.session.post(self.upload_url_step2, data=data)

            if response.status_code == 302:
                torrent_url = response.headers['Location']

                torrent_id = ''
                match = re.search(r'/torrent/(\d+)', torrent_url)
                if match:
                    torrent_id = match.group(1)
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                # Even if you are uploading, you still need to download the .torrent from the website
                # because it needs to be registered as a download before you can start seeding
                download_url = torrent_url.replace('/torrent/', '/download/torrent/')
                register_download = await self.session.get(download_url)
                if register_download.status_code != 200:
                    print(f'Unable to register your upload in your download history, please go to the URL and download the torrent file before you can start seeding: {torrent_url}'
                          f'Error: {register_download.status_code}')

                await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce_url, torrent_url)

                status_message = 'Torrent uploaded successfully.'

                if requests:
                    status_message += ' Your upload may fulfill existing requests, check prior console logs.'

            else:
                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step2.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                status_message = (
                    f'Step 2 of upload to {self.tracker} failed.\n'
                    f'Status code: {response.status_code}\n'
                    f'URL: {response.url}\n'
                    f"The HTML response has been saved to '{failure_path}' for analysis."
                )
                meta['skipping'] = f'{self.tracker}'
                return

        else:
            console.print(data)
            status_message = f'{self.tracker}: Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
