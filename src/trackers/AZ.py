# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.AVISTAZ_NETWORK import AZTrackerBase


class AZ(AZTrackerBase):
    def __init__(self, config):
        super().__init__(config, tracker_name='AZ')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'AZ'
        self.source_flag = 'AvistaZ'
        self.banned_groups = ['']
        self.base_url = 'https://avistaz.to'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.requests_url = f'{self.base_url}/requests'

    async def rules(self, meta):
        warnings = []

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
            warnings.append(
                'The only allowed content to be uploaded are Movies and TV Shows.\n'
                'Anything else, like games, music, software and porn is not allowed!'
            )

        if meta.get('anime', False):
            warnings.append("Upload Anime content to our sister site AnimeTorrents.me instead. If it's on AniDB, it's an anime.")

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
            'SI', 'SJ', 'SK', 'SM', 'SU', 'UA', 'VA', 'XC'
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

        if any(code in phd_countries for code in origin_countries_codes):
            warnings.append(
                'DO NOT upload content from major English speaking countries '
                '(USA, UK, Canada, etc). Upload this to our sister site PrivateHD.to instead.'
            )

        elif any(code in cinemaz_countries for code in origin_countries_codes):
            warnings.append(
                'DO NOT upload non-allowed Asian or Western content. '
                'Upload this content to our sister site CinemaZ.to instead.'
            )

        if not is_disc:
            if meta.get('container') not in ['mkv', 'mp4', 'avi']:
                warnings.append('Allowed containers: MKV, MP4, AVI.')

        if not is_disc:
            if video_codec not in ('avc', 'h.264', 'h.265', 'x264', 'x265', 'hevc', 'divx', 'xvid'):
                warnings.append(
                    f'Video codec not allowed in your upload: {video_codec}.\n'
                    'Allowed: H264/x264/AVC, H265/x265/HEVC, DivX/Xvid\n'
                    'Exceptions:\n'
                    '    MPEG2 for Full DVD discs and HDTV recordings\n'
                    "    VC-1/MPEG2 for Bluray only if that's what is on the disc"
                )

        if is_disc:
            pass
        else:
            allowed_keywords = [
                'AC3', 'Audio Layer III', 'MP3', 'Dolby Digital', 'Dolby TrueHD',
                'DTS', 'DTS-HD', 'FLAC', 'AAC', 'Dolby'
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
                warnings.append(
                    f"Unallowed audio codec(s) detected: {', '.join(unique_invalid_codecs)}\n"
                    f'Allowed codecs: AC3 (Dolby Digital), Dolby TrueHD, DTS, DTS-HD (MA), FLAC, AAC, MP3, etc.\n'
                    f'Exceptions: Untouched Opus from source; Uncompressed codecs from Blu-ray discs (PCM, LPCM).'
                )

        if warnings:
            all_warnings = '\n\n'.join(filter(None, warnings))
            return all_warnings

        return
