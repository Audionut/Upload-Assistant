# -*- coding: utf-8 -*-
import httpx
import os
import platform
import re
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.AVISTAZ_NETWORK import AZ_COMMON


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
            base_url=self.base_url,
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
            base_url=self.base_url,
            session=self.session,
            auth_token=self.auth_token
        ):
            console.print((f"[{self.tracker}] This media is not registered, please add it to the database by following this link: {self.base_url}/add/{meta['category'].lower()}"))
            meta['skipping'] = f"{self.tracker}"
            return

        return await self.az_common.search_existing(
            meta,
            tracker=self.tracker,
            base_url=self.base_url,
            media_code=self.az_common.media_code,
            session=self.session
        )

    async def upload(self, meta, disctype):
        await self.validate_credentials(meta)

        await self.az_common.upload(
            meta,
            name=self.edit_name(meta),
            rip_type=self.get_rip_type(meta),
            tracker=self.tracker,
            base_url=self.base_url,
            session=self.session,
            auth_token=self.auth_token,
            source_flag=self.source_flag,
            default_announce='https://tracker.avistaz.to/announce'
        )
