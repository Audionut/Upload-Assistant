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
from datetime import datetime
from pathlib import Path
from src.console import console
from src.exceptions import UploadException
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.AZ_COMMON import AZ_COMMON
from tqdm.asyncio import tqdm
from typing import Optional
from urllib.parse import urlparse


class PHD():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.az_common = AZ_COMMON(config)
        self.tracker = 'PHD'
        self.source_flag = 'PrivateHD'
        self.banned_groups = ['']
        self.base_url = 'https://privatehd.to'
        self.torrent_url = 'https://privatehd.to/torrent/'
        self.announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
        self.rehost_images = config['TRACKERS']['PHD'].get('img_rehost', True)
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.signature = ''

    async def rules(self, meta):
        meta['phd_rule'] = ''
        warning = f'{self.tracker} RULE WARNING: '
        rule = ''

        is_bd_disc = False
        if meta.get('is_disc', '') == 'BDMV':
            is_bd_disc = True

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
            meta['phd_rule'] = (
                warning + 'The only allowed content to be uploaded are Movies and TV Shows.\n'
                'Anything else, like games, music, software and porn is not allowed!'
            )
            return False

        if meta.get('anime', False):
            meta['phd_rule'] = warning + "Upload Anime content to our sister site AnimeTorrents.me instead. If it's on AniDB, it's an anime."
            return False

        year = meta.get('year')
        current_year = datetime.now().year
        is_older_than_50_years = (current_year - year) >= 50
        if is_older_than_50_years:
            meta['phd_rule'] = warning + 'Upload movies/series 50+ years old to our sister site CinemaZ.to instead.'
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

        phd_allowed_countries = [
            'AG', 'AI', 'AU', 'BB', 'BM', 'BS', 'BZ', 'CA', 'CW', 'DM', 'GB', 'GD', 'IE',
            'JM', 'KN', 'KY', 'LC', 'MS', 'NZ', 'PR', 'TC', 'TT', 'US', 'VC', 'VG', 'VI',
        ]

        all_countries = africa + america + europe + oceania
        cinemaz_countries = list(set(all_countries) - set(phd_allowed_countries))

        origin_countries_codes = meta.get('origin_country', [])

        if any(code in phd_allowed_countries for code in origin_countries_codes):
            return True

        # CinemaZ
        elif any(code in cinemaz_countries for code in origin_countries_codes):
            meta['phd_rule'] = warning + 'Upload European (EXCLUDING United Kingdom and Ireland), South American and African content to our sister site CinemaZ.to instead.'
            return False

        # AvistaZ
        elif any(code in asia for code in origin_countries_codes):
            origin_country_str = ', '.join(origin_countries_codes)
            meta['phd_rule'] = (
                warning + 'DO NOT upload content originating from countries shown in this map (https://imgur.com/nIB9PM1).\n'
                'In case of doubt, message the staff first. Upload Asian content to our sister site Avistaz.to instead.\n'
                f'Origin country for your upload: {origin_country_str}'
            )
            return False

        elif not any(code in phd_allowed_countries for code in origin_countries_codes):
            meta['phd_rule'] = (
                warning + 'Only upload content to PrivateHD from all major English speaking countries.\n'
                'Including United States, Canada, UK, Ireland, Australia, and New Zealand.'
            )
            return False

        # Tags
        tag = meta.get('tag', '')
        if tag:
            tag = tag.strip().lower()
            if tag in ('rarbg', 'fgt', 'grym', 'tbs'):
                meta['phd_rule'] = warning + 'Do not upload RARBG, FGT, Grym or TBS. Existing uploads by these groups can be trumped at any time.'
                return False

            if tag == 'evo' and source != 'web':
                meta['phd_rule'] = warning + 'Do not upload non-web EVO releases. Existing uploads by this group can be trumped at any time.'
                return False

        if meta.get('sd', '') == 1:
            meta['phd_rule'] = warning + 'SD (Standard Definition) content is forbidden.'
            return False

        if not is_bd_disc:
            ext = os.path.splitext(meta['filelist'][0])[1].lower()
            allowed_extensions = {'.mkv': 'MKV', '.mp4': 'MP4'}
            container = allowed_extensions.get(ext)
            if container is None:
                meta['phd_rule'] = warning + 'Allowed containers: MKV, MP4.'
                return False

        # Video codec
        '''
        Video Codecs:
            Allowed:
                1 - BluRay (Untouched + REMUX): MPEG-2, VC-1, H.264, H.265
                2 - BluRay (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)
                3 - WEB (Untouched): H.264, H.265, VP9
                4 - WEB (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)
                5 - x265 encodes must be 10-bit
                6 - H.264/x264 only allowed for 1080p and below.
                7 - Not Allowed: Any codec not mentioned above is not allowed.
        '''
        # 1
        if type == 'remux':
            if video_codec not in ('mpeg-2', 'vc-1', 'h.264', 'h.265', 'avc'):
                meta['phd_rule'] = warning + 'Allowed Video Codecs for BluRay (Untouched + REMUX): MPEG-2, VC-1, H.264, H.265'
                return False

        # 2
        if type == 'encode' and source == 'bluray':
            if video_encode not in ('h.264', 'h.265', 'x264', 'x265'):
                meta['phd_rule'] = warning + 'Allowed Video Codecs for BluRay (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)'
                return False

        # 3
        if type in ('webdl', 'web-dl') and source == 'web':
            if video_encode not in ('h.264', 'h.265', 'vp9'):
                meta['phd_rule'] = warning + 'Allowed Video Codecs for WEB (Untouched): H.264, H.265, VP9'
                return False

        # 4
        if type == 'encode' and source == 'web':
            if video_encode not in ('h.264', 'h.265', 'x264', 'x265'):
                meta['phd_rule'] = warning + 'Allowed Video Codecs for WEB (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)'
                return False

        # 5
        if type == 'encode':
            if video_encode == 'x265':
                if meta.get('bit_depth', '') != '10':
                    meta['phd_rule'] = warning + 'Allowed Video Codecs for x265 encodes must be 10-bit'
                    return False

        # 6
        resolution = int(meta.get('resolution').lower().replace('p', '').replace('i', ''))
        if resolution > 1080:
            if video_encode in ('h.264', 'x264'):
                meta['phd_rule'] = warning + 'H.264/x264 only allowed for 1080p and below.'
                return False

        # 7
        if video_codec not in ('avc', 'mpeg-2', 'vc-1', 'avc', 'h.264', 'vp9', 'h.265', 'x264', 'x265', 'hevc'):
            meta['phd_rule'] = warning + f'Video codec not allowed in your upload: {video_codec}.'
            return False

        # Audio codec
        '''
        Audio Codecs:
            1 - Allowed: AC3 (Dolby Digital), Dolby TrueHD, DTS, DTS-HD (MA), FLAC, AAC, all other Dolby codecs.
            2 - Exceptions: Any uncompressed audio codec that comes on a BluRay disc like; PCM, LPCM, etc.
            3 - TrueHD/Atmos audio must have a compatibility track due to poor compatibility with most players.
            4 - Not Allowed: Any codec not mentioned above is not allowed.
        '''
        if is_bd_disc:
            pass
        else:
            # 1
            allowed_keywords = ['AC3', 'Dolby Digital', 'Dolby TrueHD', 'DTS', 'DTS-HD', 'FLAC', 'AAC', 'Dolby']

            # 2
            forbidden_keywords = ['LPCM', 'PCM', 'Linear PCM']

            audio_tracks = []
            media_tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            for track in media_tracks:
                if track.get('@type') == 'Audio':
                    codec_info = track.get('Format_Commercial_IfAny')
                    codec = codec_info if isinstance(codec_info, str) else ''
                    audio_tracks.append({
                        'codec': codec,
                        'language': track.get('Language', '')
                    })

            # 3
            original_language = meta.get('original_language', '')

            if original_language:
                # Filter to only have audio tracks that are in the original language
                original_language_tracks = [
                    track for track in audio_tracks if track.get('language', '').lower() == original_language.lower()
                ]

                # Now checks are only done on the original language track list
                if original_language_tracks:
                    has_truehd_atmos = any(
                        'truehd' in track['codec'].lower() and 'atmos' in track['codec'].lower()
                        for track in original_language_tracks
                    )

                    # Check if there is an AC-3 compatibility track in the same language
                    has_ac3_compat_track = any(
                        'ac-3' in track['codec'].lower() or 'dolby digital' in track['codec'].lower()
                        for track in original_language_tracks
                    )

                    if has_truehd_atmos and not has_ac3_compat_track:
                        meta['phd_rule'] = (
                            warning + f'A TrueHD Atmos track was detected in the original language ({original_language}), '
                            f'but no AC-3 (Dolby Digital) compatibility track was found for that same language.\n'
                            'Rule: TrueHD/Atmos audio must have a compatibility track due to poor compatibility with most players.'
                        )
                        return False

            # 4
            invalid_codecs = []
            for track in audio_tracks:
                codec = track['codec']
                if not codec:
                    continue

                is_forbidden = any(kw.lower() in codec.lower() for kw in forbidden_keywords)
                if is_forbidden:
                    invalid_codecs.append(codec)
                    continue

                is_allowed = any(kw.lower() in codec.lower() for kw in allowed_keywords)
                if not is_allowed:
                    invalid_codecs.append(codec)

            if invalid_codecs:
                unique_invalid_codecs = sorted(list(set(invalid_codecs)))
                meta['phd_rule'] = (
                    warning + f"Unallowed audio codec(s) detected: {', '.join(unique_invalid_codecs)}\n"
                    f'Allowed codecs: AC3 (Dolby Digital), Dolby TrueHD, DTS, DTS-HD (MA), FLAC, AAC, all other Dolby codecs.\n'
                    f'Dolby Exceptions: Any uncompressed audio codec that comes on a BluRay disc like; PCM, LPCM, etc.'
                )
                return False

        def ask_yes_no(prompt_text):
            while True:
                answer = input(f'{prompt_text} (y/n): ').lower()
                if answer in ['y', 'n']:
                    return answer
                else:
                    print("Invalid input. Please enter 'y' or 'n'.")

        # Quality check
        '''
        Minimum quality:
            Only upload proper encodes. Any encodes where the size and/or the bitrate imply a bad quality of the encode will be deleted. Indication of a proper encode:
                Or a minimum x265 video bitrate  of:
                    720p HDTV/WEB-DL/WEBRip/HDRip: 1500 Kbps
                    720p BluRay encode: 2000 Kbps
                    1080p HDTV/WEB-DL/WEBRip/HDRip: 2500 Kbps
                    1080p BluRay encode: 3500 Kbps
                Depending on the content, for example an animation movie or series, a lower bitrate (x264) can be allowed.
            Video must at least be 720p
            The above bitrates are subject to staff discretion and uploads may be nuked even if they fulfill the above criteria.
        '''
        BITRATE_RULES = {
            ('x265', 'web', 720): 1500000,
            ('x265', 'web', 1080): 2500000,
            ('x265', 'bluray', 720): 2000000,
            ('x265', 'bluray', 1080): 3500000,

            ('x264', 'web', 720): 2500000,
            ('x264', 'web', 1080): 4500000,
            ('x264', 'bluray', 720): 3500000,
            ('x264', 'bluray', 1080): 6000000,
        }

        WEB_SOURCES = ('hdtv', 'web', 'hdrip')

        if type == 'encode':
            bitrate = 0
            for track in media_tracks:
                if track.get('@type') == 'Video':
                    bitrate = int(track.get('BitRate'))
                    break

            source_type = None
            if source in WEB_SOURCES:
                source_type = 'web'
            elif source == 'bluray':
                source_type = 'bluray'

            if source_type:
                rule_key = (video_encode, source_type, resolution)

                if rule_key in BITRATE_RULES:
                    min_bitrate = BITRATE_RULES[rule_key]

                    if bitrate < min_bitrate:
                        quality_rule_text = (
                            'Only upload proper encodes.\n'
                            'Any encodes where the size and/or the bitrate imply a bad quality will be deleted.'
                        )
                        rule = (
                            f'Your upload was rejected due to low quality.\n'
                            f'Minimum bitrate for {resolution}p {source.upper()} {video_encode.upper()} is {min_bitrate / 1000} Kbps.'
                        )
                        meta['phd_rule'] = (warning + quality_rule_text + rule)

        if resolution < 720:
            rule = 'Video must be at least 720p.'
            meta['phd_rule'] = (warning + rule)

        # Hybrid
        if type in ('remux', 'encode'):
            if 'hybrid' in meta.get('name', '').lower():

                is_hybrid_confirm = ask_yes_no(
                    "This release appears to be a 'Hybrid'. Is this correct?"
                )

                if is_hybrid_confirm == 'y':
                    hybrid_rule_text = (
                        'Hybrid Remuxes and Encodes are subject to the following condition:\n\n'
                        'Hybrid user releases are permitted, but are treated similarly to regular '
                        'user releases and must be approved by staff before you upload them '
                        '(please see the torrent approvals forum for details).'
                    )

                    print('\n' + '-'*60)
                    print('Important Rule for Hybrid Releases')
                    print('-' * 60)
                    print(warning + hybrid_rule_text)
                    print('-' * 60 + '\n')

                    continue_upload = ask_yes_no(
                        'Have you already received staff approval for this upload?'
                        'Do you wish to continue?'
                    )

                    if continue_upload == 'n':
                        error_message = 'Upload aborted by user. Hybrid releases require prior staff approval.'
                        print(f'{error_message}')
                        meta['phd_rule'] = error_message

                else:
                    error_message = "Upload aborted. The term 'Hybrid' in the release name is reserved for approved hybrid releases. Please correct the name if it is not a hybrid."
                    print(f'{error_message}')
                    meta['phd_rule'] = error_message

        # Log
        if type == 'remux':
            remux_log = ask_yes_no(
                warning + 'Remuxes must have a demux/eac3to log under spoilers in description.\n'
                'Do you have these logs and will you add them to the description after upload?'
            )
            if remux_log == 'y':
                pass
            else:
                meta['phd_rule'] = (warning + 'Remuxes must have a demux/eac3to log under spoilers in description.')
                return False

        # Bloated
        if meta.get('bloated', False):
            ask_bloated = ask_yes_no(
                warning + 'Audio dubs are never preferred and can always be trumped by original audio only rip (Exception for BD50/BD25).\n'
                'Do NOT upload a multi audio release when there is already a original audio only release on site.\n'
                'Do you want to upload anyway?'
            )
            if ask_bloated == 'y':
                pass
            else:
                meta['phd_rule'] = 'Canceled by user. Reason: Bloated'
                return False

        return True

    def edit_name(self, meta):
        upload_name = meta.get('name').replace(meta["aka"], '')
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

        tag_lower = meta['tag'].lower()
        invalid_tags = ['nogrp', 'nogroup', 'unknown', '-unk-']

        if meta['tag'] == '' or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                upload_name = re.sub(f'-{invalid_tag}', '', upload_name, flags=re.IGNORECASE)
            upload_name = f'{upload_name}-NOGROUP'

        return upload_name

    def get_rip_type(self, meta):
        source_type = meta.get('type')

        keyword_map = {
            'bdrip': '1',
            'encode': '2',
            'disc': '3',
            'hdrip': '6',
            'hdtv': '7',
            'webdl': '12',
            'webrip': '13',
            'remux': '14',
        }

        return keyword_map.get(source_type.lower())

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f'[{self.tracker}] Cookie file for {self.tracker} not found: {cookie_file}')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            upload_page_url = f'{self.base_url}/upload'
            response = await self.session.get(upload_page_url)
            response.raise_for_status()

            if 'login' in str(response.url):
                console.print(f'[{self.tracker}] Validation failed. The cookie appears to be expired or invalid.')
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
            console.print(f'[{self.tracker}] Error in {self.tracker}: Timeout while trying to validate credentials.')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'[{self.tracker}] HTTP error validating credentials for {self.tracker}: Status {e.response.status_code}.')
            return False
        except httpx.RequestError as e:
            console.print(f'[{self.tracker}] Network error while validating credentials for {self.tracker}: {e.__class__.__name__}.')
            return False

    async def search_existing(self, meta, disctype):
        if not await self.rules(meta):
            console.print(f"[red]{meta['phd_rule']}[/red]")
            meta['skipping'] = f"{self.tracker}"
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
        self.az_common.language_map(self.tracker)
        if not meta.get('subtitle_languages') or meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_subs_strings = meta.get('subtitle_languages', [])
        subtitle_ids = set()
        for lang_str in found_subs_strings:
            target_id = self.az_common.lang_map.get(lang_str.lower())
            if target_id:
                subtitle_ids.add(target_id)
        final_subtitle_ids = sorted(list(subtitle_ids))

        found_audio_strings = meta.get('audio_languages', [])
        audio_ids = set()
        for lang_str in found_audio_strings:
            target_id = self.az_common.lang_map.get(lang_str.lower())
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
                desc=f'[{self.tracker}] Uploading screenshots'
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
                desc=f'[{self.tracker}] Uploading screenshots'
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
                console.print(f'[{self.tracker}] An error occurred while fetching requests: {e}')
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
            tags.insert(0, '1448')

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
                console.print(f'[{self.tracker}] Deleted {amount} {removed_type} from description.')

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
            'media_info': await self.get_file_info(meta),
        }

        if not meta.get('debug', False):
            try:
                await self.common.edit_torrent(meta, self.tracker, self.source_flag)
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
                            console.print(f"[{self.tracker}] Could not extract 'task_id' from redirect URL: {redirect_url}")
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
            'video_quality_id': self.az_common.get_video_quality(meta),
            'video_resolution': self.az_common.get_resolution(meta),
            'movie_id': self.az_common.media_code,
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
                    print(f"Unable to register your upload in your download history, please go to the URL and download the torrent file before you can start seeding: {torrent_url}"
                          f"Error: {register_download.status_code}")

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
