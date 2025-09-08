# -*- coding: utf-8 -*-
import asyncio
import bencodepy
import hashlib
import httpx
import json
import os
import platform
import re
from bs4 import BeautifulSoup
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.AZ_COMMON import AZ_COMMON


class AZ():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.az_common = AZ_COMMON(config)
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
        upload_name = meta.get('name').replace(meta['aka'], '').replace('Dubbed', '').replace('Dual-Audio', '')

        tag_lower = meta['tag'].lower()
        invalid_tags = ['nogrp', 'nogroup', 'unknown', '-unk-']

        if meta['tag'] == '' or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                upload_name = re.sub(f'-{invalid_tag}', '', upload_name, flags=re.IGNORECASE)
            upload_name = f'{upload_name}-NoGroup'

        return upload_name

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f'[{self.tracker}] Cookie file for {self.tracker} not found: {cookie_file}')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        await self.az_common.validate_credentials(
            meta,
            tracker=self.tracker,
            tracker_url=self.base_url,
            session=self.session
        )
        self.auth_token = self.az_common.auth_token

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

    async def search_existing(self, meta, disctype):
        if not await self.rules(meta):
            console.print(f"[red]{meta['az_rule']}[/red]")
            meta['skipping'] = f'{self.tracker}'
            return

        if not await self.az_common.get_media_code(
            meta,
            tracker=self.tracker,
            tracker_url=self.base_url,
            session=self.session,
            auth_token=self.auth_token
        ):
            console.print((f"[{self.tracker}] This media is not registered, please add it to the database by following this link: {self.base_url}/add/{meta['category'].lower()}"))
            meta['skipping'] = f"{self.tracker}"
            return

        return await self.az_common.search_existing(
            meta,
            tracker=self.tracker,
            tracker_url=self.base_url,
            media_code=self.az_common.media_code,
            session=self.session
        )

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

    async def create_task_id(self, meta):
        await self.az_common.get_media_code(meta, tracker=self.tracker, tracker_url=self.base_url, session=self.session, auth_token=self.auth_token)

        data = {
            '_token': self.auth_token,
            'type_id': await self.az_common.get_cat_id(meta['category']),
            'movie_id': self.az_common.media_code,
            'media_info': await self.az_common.get_file_info(meta),
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
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message

    async def fetch_data(self, meta):
        await self.validate_credentials(meta)
        task_info = await self.create_task_id(meta)
        lang_info = await self.get_lang(meta) or {}

        data = {
            '_token': self.auth_token,
            'torrent_id': '',
            'type_id': await self.az_common.get_cat_id(meta['category']),
            'file_name': self.edit_name(meta),
            'anon_upload': '',
            'description': await self.edit_desc(meta),
            'qqfile': '',
            'rip_type_id': self.get_rip_type(meta),
            'video_quality_id': '1' if meta.get('sd', False) else self.az_common.get_video_quality(meta),
            'video_resolution': self.az_common.get_resolution(meta),
            'movie_id': self.az_common.media_code,
            'languages[]': lang_info.get('languages[]'),
            'subtitles[]': lang_info.get('subtitles[]'),
            'media_info': await self.az_common.get_file_info(meta),
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
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
