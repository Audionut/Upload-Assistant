# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from datetime import datetime
from src.trackers.COMMON import COMMON
from src.trackers.AVISTAZ_NETWORK import AZTrackerBase


class PHD(AZTrackerBase):
    def __init__(self, config):
        super().__init__(config, tracker_name='PHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'PHD'
        self.source_flag = 'PrivateHD'
        self.banned_groups = [
            "RARBG", "STUTTERSHIT", "LiGaS", "DDR", "Zeus", "TBS", "SWTYBLZ", "EASports", "C4K", "d3g",
            "MeGusta", "YTS", "YIFY", "Tigole", "x0r", "nikt0", "NhaNc3", "PRoDJi", "RDN", "SANTi",
            "FaNGDiNG0", "FRDS", "HD2DVD", "HDTime", "iPlanet", "KiNGDOM", "Leffe", "4K4U", "Xiaomi",
            "VisionXpert", "WKS"
        ]
        self.base_url = 'https://privatehd.to'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.requests_url = f'{self.base_url}/requests'

    async def rules(self, meta):
        warnings = []

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
            warnings.append(
                'The only allowed content to be uploaded are Movies and TV Shows.\n'
                'Anything else, like games, music, software and porn is not allowed!'
            )

        if meta.get('anime', False):
            warnings.append("Upload Anime content to our sister site AnimeTorrents.me instead. If it's on AniDB, it's an anime.")

        year = meta.get('year')
        current_year = datetime.now().year
        is_older_than_50_years = (current_year - year) >= 50
        if is_older_than_50_years:
            warnings.append('Upload movies/series 50+ years old to our sister site CinemaZ.to instead.')

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

        phd_allowed_countries = [
            'AG', 'AI', 'AU', 'BB', 'BM', 'BS', 'BZ', 'CA', 'CW', 'DM', 'GB', 'GD', 'IE',
            'JM', 'KN', 'KY', 'LC', 'MS', 'NZ', 'PR', 'TC', 'TT', 'US', 'VC', 'VG', 'VI',
        ]

        all_countries = africa + america + europe + oceania
        cinemaz_countries = list(set(all_countries) - set(phd_allowed_countries))

        origin_countries_codes = meta.get('origin_country', [])

        if any(code in phd_allowed_countries for code in origin_countries_codes):
            pass

        # CinemaZ
        elif any(code in cinemaz_countries for code in origin_countries_codes):
            warnings.append('Upload European (EXCLUDING United Kingdom and Ireland), South American and African content to our sister site CinemaZ.to instead.')

        # AvistaZ
        elif any(code in asia for code in origin_countries_codes):
            origin_country_str = ', '.join(origin_countries_codes)
            warnings.append(
                'DO NOT upload content originating from countries shown in this map (https://imgur.com/nIB9PM1).\n'
                'In case of doubt, message the staff first. Upload Asian content to our sister site Avistaz.to instead.\n'
                f'Origin country for your upload: {origin_country_str}'
            )

        elif not any(code in phd_allowed_countries for code in origin_countries_codes):
            warnings.append(
                'Only upload content to PrivateHD from all major English speaking countries.\n'
                'Including United States, Canada, UK, Ireland, Australia, and New Zealand.'
            )

        # Tags
        tag = meta.get('tag', '')
        if tag:
            tag = tag.strip().lower()
            if tag in ('rarbg', 'fgt', 'grym', 'tbs'):
                warnings.append('Do not upload RARBG, FGT, Grym or TBS. Existing uploads by these groups can be trumped at any time.')

            if tag == 'evo' and source != 'web':
                warnings.append('Do not upload non-web EVO releases. Existing uploads by this group can be trumped at any time.')

        if meta.get('sd', '') == 1:
            warnings.append('SD (Standard Definition) content is forbidden.')

        if not is_bd_disc:
            if meta.get('container') not in ['mkv', 'mp4']:
                warnings.append('Allowed containers: MKV, MP4.')

        # Video codec
        # 1
        if type == 'remux':
            if video_codec not in ('mpeg-2', 'vc-1', 'h.264', 'h.265', 'avc'):
                warnings.append('Allowed Video Codecs for BluRay (Untouched + REMUX): MPEG-2, VC-1, H.264, H.265')

        # 2
        if type == 'encode' and source == 'bluray':
            if video_encode not in ('h.264', 'h.265', 'x264', 'x265'):
                warnings.append('Allowed Video Codecs for BluRay (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)')

        # 3
        if type in ('webdl', 'web-dl') and source == 'web':
            if video_encode not in ('h.264', 'h.265', 'vp9'):
                warnings.append('Allowed Video Codecs for WEB (Untouched): H.264, H.265, VP9')

        # 4
        if type == 'encode' and source == 'web':
            if video_encode not in ('h.264', 'h.265', 'x264', 'x265'):
                warnings.append('Allowed Video Codecs for WEB (Encoded): H.264, H.265 (x264 and x265 respectively are the only permitted encoders)')

        # 5
        if type == 'encode':
            if video_encode == 'x265':
                if meta.get('bit_depth', '') != '10':
                    warnings.append('Allowed Video Codecs for x265 encodes must be 10-bit')

        # 6
        resolution = int(meta.get('resolution').lower().replace('p', '').replace('i', ''))
        if resolution > 1080:
            if video_encode in ('h.264', 'x264'):
                warnings.append('H.264/x264 only allowed for 1080p and below.')

        # 7
        if video_codec not in ('avc', 'mpeg-2', 'vc-1', 'avc', 'h.264', 'vp9', 'h.265', 'x264', 'x265', 'hevc'):
            warnings.append(f'Video codec not allowed in your upload: {video_codec}.')

        # Audio codec
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
            language_track = track.get('language', '')
            if original_language and language_track:
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
                        warnings.append(
                            f'A TrueHD Atmos track was detected in the original language ({original_language}), '
                            f'but no AC-3 (Dolby Digital) compatibility track was found for that same language.\n'
                            'Rule: TrueHD/Atmos audio must have a compatibility track due to poor compatibility with most players.'
                        )

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
                warnings.append(
                    f"Unallowed audio codec(s) detected: {', '.join(unique_invalid_codecs)}\n"
                    f'Allowed codecs: AC3 (Dolby Digital), Dolby TrueHD, DTS, DTS-HD (MA), FLAC, AAC, all other Dolby codecs.\n'
                    f'Dolby Exceptions: Any uncompressed audio codec that comes on a BluRay disc like; PCM, LPCM, etc.'
                )

        # Quality check
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
                        warnings.append(quality_rule_text + rule)

        if resolution < 720:
            rule = 'Video must be at least 720p.'
            warnings.append(rule)

        # Hybrid
        if type in ('remux', 'encode'):
            if 'hybrid' in meta.get('name', '').lower():
                warnings.append(
                    'Hybrid Remuxes and Encodes are subject to the following condition:\n\n'
                    'Hybrid user releases are permitted, but are treated similarly to regular '
                    'user releases and must be approved by staff before you upload them '
                    '(please see the torrent approvals forum for details).'
                )

        # Log
        if type == 'remux':
            warnings.append(
                'Remuxes must have a demux/eac3to log under spoilers in description.\n'
                'Do you have these logs and will you add them to the description after upload?'
            )

        # Bloated
        if meta.get('bloated', False):
            warnings.append(
                'Audio dubs are never preferred and can always be trumped by original audio only rip (Exception for BD50/BD25).\n'
                'Do NOT upload a multi audio release when there is already a original audio only release on site.\n'
            )

        if warnings:
            all_warnings = '\n\n'.join(filter(None, warnings))
            return all_warnings

        return

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
