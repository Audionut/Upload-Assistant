# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import re
from typing import Any, Optional, cast

import cloudscraper

from src.console import console
from src.languages import languages_manager
from src.tmdb import TmdbManager
from src.trackers.UNIT3D import UNIT3D


class EMUW(UNIT3D):
    """
    EMUW tracker handler with Spanish naming conventions
    Handles torrents with Spanish titles, audio, and subtitle requirements
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config, tracker_name='EMUW')
        self.tmdb_manager = TmdbManager(config)
        self.base_url = 'https://emuwarez.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        """
        Generate EMUW-compliant torrent name format
        Format: [Spanish Title] [Season] [Year] [Resolution] [Format] [Codec] [Audio] [SUBS] - [Group]

        Examples:
        - Hora punta 1998 1080p BluRay x264 ESP DD 5.1 ING DTS 5.1 SUBS-EMUWAREZ
        - Sound! Euphonium S03 2025 1080p WEB-DL AVC JAP AAC 2.0 SUBS-Fool
        """
        # Get Spanish title if available and configured
        title = await self._get_title(meta)

        # Get season using season_int
        season = ""
        if meta['category'] == 'TV' and meta.get('season_int'):
            season = f"S{meta['season_int']:02d}"

        year = meta.get('year', '')
        resolution = self._map_resolution(str(meta.get('resolution', '')))
        video_format = self._map_format(meta)
        video_codec = self._map_codec(meta)

        # Process language information
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        # Build audio string
        audio_str = await self._build_audio_string(meta)

        # Check for Spanish subtitles
        subs_tag = " SUBS" if self._has_spanish_subs(meta) else ""

        # Get tag from meta['tag']
        tag = meta.get('tag', '').strip()

        # Remove leading dash if present
        if tag.startswith('-'):
            tag = tag[1:]

        # Filter out invalid tags and use default if needed
        if not tag or tag.lower() in ['nogrp', 'nogroup', 'unknown', 'unk', 'hd.ma.5.1', 'untouched']:
            tag = 'EMUWAREZ'

        # Build final name
        name_parts = [
            part
            for part in [title, season, str(year), resolution, video_format, video_codec, audio_str]
            if part
        ]
        base_name = ' '.join(name_parts)

        # Clean up spaces and build final name
        base_name = re.sub(r'\s{2,}', ' ', base_name).strip()
        emuwarez_name = f"{base_name}{subs_tag}-{tag}"

        return {'name': emuwarez_name}

    async def _get_title(self, meta: dict[str, Any]) -> str:
        """Get Spanish title if available and configured"""
        spanish_title = None

        # Try to get from IMDb with priority: country match, then language match
        imdb_info_raw = meta.get('imdb_info')
        imdb_info: dict[str, Any] = cast(dict[str, Any], imdb_info_raw) if isinstance(imdb_info_raw, dict) else {}
        akas_raw = imdb_info.get('akas', [])
        akas: list[Any] = cast(list[Any], akas_raw) if isinstance(akas_raw, list) else []

        country_match = None
        language_match = None

        for aka in akas:
            if isinstance(aka, dict):
                aka_dict = cast(dict[str, Any], aka)
                if aka_dict.get("country") in ["Spain", "ES"]:
                    country_match = aka_dict.get("title")
                    break  # Country match takes priority
                elif aka_dict.get("language") in ["Spain", "Spanish", "ES"] and not language_match:
                    language_match = aka_dict.get("title")

        spanish_title = country_match or language_match

        # Try TMDb if not found
        tmdb_id_raw = meta.get('tmdb')
        tmdb_id = int(tmdb_id_raw) if isinstance(tmdb_id_raw, (int, str)) and str(tmdb_id_raw).isdigit() else 0
        if not spanish_title and tmdb_id:
            spanish_title = await self.tmdb_manager.get_tmdb_translations(
                tmdb_id=tmdb_id,
                category=str(meta.get('category', 'MOVIE')),
                target_language='es',
                debug=bool(meta.get('debug', False))
            )

        # Use Spanish title if configured
        use_spanish_title = self.config['TRACKERS'][self.tracker].get('use_spanish_title', False)
        if isinstance(spanish_title, str) and spanish_title and use_spanish_title:
            return spanish_title

        return meta.get('title', '')

    def _map_resolution(self, resolution: str) -> str:
        """Map resolution to EMUW nomenclature"""
        resolution_map = {
            '4320p': '4320p FUHD',
            '2160p': '2160p UHD',
            '1080p': '1080p',
            '720p': '720p',
            '576p': '576p SD',
            '540p': '540p SD',
            '480p': '480p SD',
        }
        return resolution_map.get(resolution, resolution)

    def _map_format(self, meta: dict[str, Any]) -> str:
        """Map source format to EMUW nomenclature"""
        source = str(meta.get('source', ''))
        type_name = str(meta.get('type', ''))

        format_map = {
            'BDMV': 'FBD',
            'DVD': 'FDVD',
            'REMUX': 'BDRemux',
        }

        is_disc = meta.get('is_disc')
        if isinstance(is_disc, str) and is_disc in format_map:
            return format_map[is_disc]
        if type_name in format_map:
            return format_map[type_name]

        if 'BluRay' in source or 'Blu-ray' in source:
            return 'BluRay'
        if 'WEB' in source:
            return 'WEB-DL' if 'WEB-DL' in source else 'WEBRIP'
        if 'HDTV' in source:
            return 'HDTV'
        if 'DVD' in source:
            return 'SD'

        return ''

    def _map_codec(self, meta: dict[str, Any]) -> str:
        """Map video codec to EMUW nomenclature with HDR/DV prefix"""
        codec_map = {
            'H.264': 'AVC', 'H.265': 'HEVC', 'HEVC': 'HEVC', 'AVC': 'AVC',
            'x264': 'x264', 'x265': 'x265', 'AV1': 'AV1', 'VP9': 'VP9',
            'VP8': 'VP8', 'VC-1': 'VC-1', 'MPEG-4': 'MPEG',
        }

        hdr_prefix = ''
        if meta.get('hdr'):
            hdr = str(meta.get('hdr', ''))
            if 'DV' in hdr:
                hdr_prefix = 'DV '
            if 'HDR' in hdr:
                hdr_prefix += 'HDR '

        video_codec = str(meta.get('video_codec', ''))
        video_encode = str(meta.get('video_encode', ''))
        codec = codec_map.get(video_codec) or codec_map.get(video_encode, video_codec)

        return f"{hdr_prefix}{codec}".strip()

    async def _get_original_language(self, meta: dict[str, Any]) -> Optional[str]:
        """Get the original language from existing metadata"""
        original_lang = None

        if meta.get('original_language'):
            original_lang = str(meta['original_language'])

        if not original_lang:
            imdb_info_raw = meta.get('imdb_info')
            imdb_info: dict[str, Any] = cast(dict[str, Any], imdb_info_raw) if isinstance(imdb_info_raw, dict) else {}
            imdb_lang: Any = imdb_info.get('language')

            if isinstance(imdb_lang, list):
                imdb_lang_list = cast(list[Any], imdb_lang)
                imdb_lang = imdb_lang_list[0] if imdb_lang_list else ''

            if imdb_lang:
                if isinstance(imdb_lang, dict):
                    imdb_lang_dict = cast(dict[str, Any], imdb_lang)
                    imdb_lang_text = imdb_lang_dict.get('text', '')
                    original_lang = str(imdb_lang_text).strip()
                elif isinstance(imdb_lang, str):
                    original_lang = imdb_lang.strip()
                else:
                    original_lang = str(imdb_lang).strip()

        if original_lang:
            return self._map_language(str(original_lang))

        return None

    async def _build_audio_string(self, meta: dict[str, Any]) -> str:
        """
        Build audio string in EMUW format with proper priority order

        Priority Order:
        1. DUAL: Exactly 2 audio tracks, same codec
        2. MULTI: 4+ audio tracks, same codec
        3. VOSE: Single audio (original lang) + Spanish subs + NO Spanish audio
        4. V.O.: Single audio (original lang) + NO Spanish subs + NO Spanish audio
        5. Normal: List all audio tracks
        """
        audio_tracks = self._get_audio_tracks(meta)
        if not audio_tracks:
            return ''

        audio_langs = self._extract_audio_languages(audio_tracks, meta)
        if not audio_langs:
            return ''

        original_lang = await self._get_original_language(meta)
        has_spanish_audio = 'ESP' in audio_langs or 'LAT' in audio_langs
        has_spanish_subs = self._has_spanish_subs(meta)
        num_audio_tracks = len(audio_tracks)

        # DUAL - Exactly 2 audios, same codec
        if num_audio_tracks == 2:
            codec1 = self._map_audio_codec(audio_tracks[0])
            codec2 = self._map_audio_codec(audio_tracks[1])

            if codec1 == codec2:
                channels = self._get_audio_channels(audio_tracks[0])
                return f"DUAL {codec1} {channels}"

        # MULTI - 4+ audios, same codec
        if num_audio_tracks >= 4:
            codecs = [self._map_audio_codec(t) for t in audio_tracks]
            if all(c == codecs[0] for c in codecs):
                channels = self._get_audio_channels(audio_tracks[0])
                return f"MULTI {codecs[0]} {channels}"

        # VOSE - Single audio (original) + Spanish subs + NO Spanish audio
        if num_audio_tracks == 1 and original_lang and not has_spanish_audio and has_spanish_subs and audio_langs[0] == original_lang:
            codec = self._map_audio_codec(audio_tracks[0])
            channels = self._get_audio_channels(audio_tracks[0])
            return f"VOSE {original_lang} {codec} {channels}"

        # V.O. - Single audio (original) + NO Spanish subs + NO Spanish audio
        if num_audio_tracks == 1 and original_lang and not has_spanish_audio and not has_spanish_subs and audio_langs[0] == original_lang:
            codec = self._map_audio_codec(audio_tracks[0])
            channels = self._get_audio_channels(audio_tracks[0])
            return f"V.O. {original_lang} {codec} {channels}"

        # Normal listing
        audio_parts: list[str] = []
        for i, track in enumerate(audio_tracks):
            if i < len(audio_langs):
                lang = audio_langs[i]
                codec = self._map_audio_codec(track)
                channels = self._get_audio_channels(track)
                audio_parts.append(f"{lang} {codec} {channels}")

        return ' '.join(audio_parts)

    def _get_audio_tracks(self, meta: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract audio tracks from mediainfo"""
        if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
            return []

        media_info = meta['mediainfo']
        if not isinstance(media_info, dict):
            return []
        media_info_dict = cast(dict[str, Any], media_info)
        media = media_info_dict.get('media')
        if not isinstance(media, dict):
            return []

        media_dict = cast(dict[str, Any], media)
        tracks = media_dict.get('track', [])
        if not isinstance(tracks, list):
            return []

        audio_tracks: list[dict[str, Any]] = []
        tracks_list = cast(list[Any], tracks)
        for track in tracks_list:
            if isinstance(track, dict):
                track_dict = cast(dict[str, Any], track)
                if track_dict.get('@type') == 'Audio':
                    audio_tracks.append(track_dict)

        return audio_tracks

    def _extract_audio_languages(self, audio_tracks: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:
        """Extract and normalize audio languages"""
        audio_langs: list[str] = []

        for track in audio_tracks:
            lang = track.get('Language', '')
            if lang:
                lang_code = self._map_language(str(lang))
                if lang_code and lang_code not in audio_langs:
                    audio_langs.append(lang_code)

        if not audio_langs and meta.get('audio_languages'):
            audio_languages = meta.get('audio_languages')
            audio_languages_list: list[Any] = cast(list[Any], audio_languages) if isinstance(audio_languages, list) else []
            for lang in audio_languages_list:
                lang_code = self._map_language(str(lang))
                if lang_code and lang_code not in audio_langs:
                    audio_langs.append(lang_code)

        return audio_langs

    def _map_language(self, lang: str) -> str:
        """Map language codes and names to EMUW nomenclature"""
        if not lang:
            return ''

        lang_map = {
            'spa': 'ESP', 'es': 'ESP', 'spanish': 'ESP', 'español': 'ESP', 'castellano': 'ESP', 'es-es': 'ESP',
            'eng': 'ING', 'en': 'ING', 'english': 'ING', 'en-us': 'ING', 'en-gb': 'ING',
            'lat': 'LAT', 'latino': 'LAT', 'latin american spanish': 'LAT', 'es-mx': 'LAT', 'es-419': 'LAT',
            'fre': 'FRA', 'fra': 'FRA', 'fr': 'FRA', 'french': 'FRA', 'français': 'FRA',
            'ger': 'ALE', 'deu': 'ALE', 'de': 'ALE', 'german': 'ALE', 'deutsch': 'ALE',
            'jpn': 'JAP', 'ja': 'JAP', 'japanese': 'JAP', '日本語': 'JAP',
            'kor': 'COR', 'ko': 'COR', 'korean': 'COR', '한국어': 'COR',
            'ita': 'ITA', 'it': 'ITA', 'italian': 'ITA', 'italiano': 'ITA',
            'por': 'POR', 'pt': 'POR', 'portuguese': 'POR', 'português': 'POR', 'pt-br': 'POR', 'pt-pt': 'POR',
            'chi': 'CHI', 'zho': 'CHI', 'zh': 'CHI', 'chinese': 'CHI', 'mandarin': 'CHI', '中文': 'CHI', 'zh-cn': 'CHI',
            'rus': 'RUS', 'ru': 'RUS', 'russian': 'RUS', 'русский': 'RUS',
            'ara': 'ARA', 'ar': 'ARA', 'arabic': 'ARA',
            'hin': 'HIN', 'hi': 'HIN', 'hindi': 'HIN',
            'tha': 'THA', 'th': 'THA', 'thai': 'THA',
            'vie': 'VIE', 'vi': 'VIE', 'vietnamese': 'VIE',
        }

        lang_lower = str(lang).lower().strip()
        mapped = lang_map.get(lang_lower)

        if mapped:
            return mapped

        return lang.upper()[:3] if len(lang) >= 3 else lang.upper()

    def _map_audio_codec(self, audio_track: dict[str, Any]) -> str:
        """Map audio codec to EMUW nomenclature"""
        codec = str(audio_track.get('Format', '')).upper()

        if 'atmos' in str(audio_track.get('Format_AdditionalFeatures', '')).lower():
            return 'Atmos'

        codec_map = {
            'AAC LC': 'AAC LC', 'AAC': 'AAC', 'AC-3': 'DD', 'AC3': 'DD',
            'E-AC-3': 'DD+', 'EAC3': 'DD+', 'DTS': 'DTS',
            'DTS-HD MA': 'DTS-HD MA', 'DTS-HD HRA': 'DTS-HD HRA',
            'TRUEHD': 'TrueHD', 'MLP FBA': 'MLP', 'PCM': 'PCM',
            'FLAC': 'FLAC', 'OPUS': 'OPUS', 'MP3': 'MP3',
        }

        return codec_map.get(codec, codec)

    def _get_audio_channels(self, audio_track: dict[str, Any]) -> str:
        """Get audio channel configuration"""
        channels = audio_track.get('Channels', '')
        channel_map = {
            '1': 'Mono', '2': '2.0', '3': '3.0',
            '4': '3.1', '5': '5.0', '6': '5.1', '8': '7.1',
        }
        return channel_map.get(str(channels), '5.1')

    def _has_spanish_subs(self, meta: dict[str, Any]) -> bool:
        """Check if torrent has Spanish subtitles"""
        if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
            return False
        media_info = meta['mediainfo']
        if not isinstance(media_info, dict):
            return False
        media_info_dict = cast(dict[str, Any], media_info)
        media = media_info_dict.get('media')
        if not isinstance(media, dict):
            return False
        media_dict = cast(dict[str, Any], media)
        tracks = media_dict.get('track', [])
        if not isinstance(tracks, list):
            return False

        tracks_list = cast(list[Any], tracks)
        for track in tracks_list:
            if not isinstance(track, dict):
                continue
            track_dict = cast(dict[str, Any], track)
            if track_dict.get('@type') == 'Text':
                lang = track_dict.get('Language', '')
                lang = lang.lower() if isinstance(lang, str) else ''

                title = track_dict.get('Title', '')
                title = title.lower() if isinstance(title, str) else ''

                if lang in ['es', 'spa', 'spanish', 'es-es', 'español']:
                    return True
                if 'spanish' in title or 'español' in title or 'castellano' in title:
                    return True

        return False

    async def get_cat_id(self, category_name: str) -> str:
        """Categories: Movies(1), Series(2), Documentales(4), Musica(5), Juegos(6), Software(7)"""
        category_map = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '1'
        }
        return category_map.get(category_name, '1')

    async def get_type_id(
        self,
        meta: dict[str, Any],
        type: Any = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        """Types: Full Disc(1), Remux(2), Encode(3), WEB-DL(4), WEBRIP(5), HDTV(6), SD(7)"""
        type_map = {
            'DISC': '1', 'REMUX': '2', 'ENCODE': '3',
            'WEBDL': '4', 'WEBRIP': '5', 'HDTV': '6', 'SD': '7'
        }
        meta_type = meta.get('type', '')
        type_id = type_map.get(str(meta_type), '3')
        return {'type_id': type_id}

    async def get_res_id(self, resolution: str) -> str:
        """Resolutions: 4320p(1), 2160p(2), 1080p(3), 1080i(4), 720p(5), 576p(6), 540p(7), 480p(8), Otras(10)"""
        resolution_map = {
            '4320p': '1', '2160p': '2', '1080p': '3', '1080i': '4',
            '720p': '5', '576p': '6', '540p': '7', '480p': '8',
            'SD': '10', 'OTHER': '10'
        }
        return resolution_map.get(resolution, '10')

    async def search_existing(self, meta: dict[str, Any], _) -> list[dict[str, Any]]:
        """Search for duplicate torrents using cloudscraper for Cloudflare bypass"""
        dupes: list[dict[str, Any]] = []

        # Build search name using meta['name'] like UNIT3D
        search_name = str(meta.get('name', ''))

        # Add season for TV shows
        if meta['category'] == 'TV' and meta.get('season'):
            search_name = f"{search_name} {meta['season']}"

        # Add edition if present
        if meta.get('edition'):
            search_name = f"{search_name} {meta['edition']}"

        params: dict[str, Any] = {
            'tmdbId': meta.get('tmdb', ''),
            'categories[]': await self.get_cat_id(str(meta['category'])),
            'name': search_name
        }

        api_key = str(self.config['TRACKERS'][self.tracker]['api_key']).strip()
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Origin': self.base_url
        }

        cloudscraper_module = cast(Any, cloudscraper)
        create_scraper = cloudscraper_module.create_scraper
        scraper = create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True
            },
            delay=10
        )

        try:
            # Establish session
            scraper.get(self.base_url, timeout=15.0)

            # Make API request
            response = scraper.get(url=self.search_url, params=params, headers=headers, timeout=15.0)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        data_dict = cast(dict[str, Any], data)
                        data_items_raw = data_dict.get('data')
                        if not isinstance(data_items_raw, list):
                            return dupes
                        data_items = cast(list[Any], data_items_raw)
                        for torrent in data_items:
                            if not isinstance(torrent, dict):
                                continue
                            torrent_dict = cast(dict[str, Any], torrent)
                            attributes = torrent_dict.get('attributes')
                            if not isinstance(attributes, dict):
                                continue
                            attributes_dict = cast(dict[str, Any], attributes)
                            if 'name' not in attributes_dict:
                                continue

                            files_value = attributes_dict.get('files', [])
                            files_list: list[Any] = cast(list[Any], files_value) if isinstance(files_value, list) else []
                            file_names: list[str] = []
                            for file in files_list:
                                if not isinstance(file, dict):
                                    continue
                                file_dict = cast(dict[str, Any], file)
                                name = file_dict.get('name')
                                if isinstance(name, str):
                                    file_names.append(name)

                            if not meta['is_disc']:
                                result = {
                                    'name': attributes_dict['name'],
                                    'size': attributes_dict.get('size'),
                                    'files': file_names,
                                    'file_count': len(files_list),
                                    'trumpable': attributes_dict.get('trumpable', False),
                                    'link': attributes_dict.get('details_link', None)
                                }
                            else:
                                result = {
                                    'name': attributes_dict['name'],
                                    'size': attributes_dict.get('size'),
                                    'trumpable': attributes_dict.get('trumpable', False),
                                    'link': attributes_dict.get('details_link', None)
                                }
                            dupes.append(result)
                except Exception as json_error:
                    console.print(f"[red]Failed to parse JSON: {json_error}")

            elif response.status_code == 403:
                console.print(f"[red]Cloudflare protection blocked API access to {self.tracker}")
            elif response.status_code == 429:
                console.print(f"[yellow]Rate limited by {self.tracker}, waiting 60s...")
                await asyncio.sleep(60)
            else:
                console.print(f"[yellow]Unexpected status code: {response.status_code}")

        except Exception as e:
            console.print(f"[red]Search error for {self.tracker}: {type(e).__name__}: {str(e)}")

        return dupes

    async def get_upload_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Get upload data with EMUW-specific options"""
        upload_data = await super().get_data(meta)

        if meta.get('anon', False):
            upload_data['anonymous'] = "1"
        if meta.get('stream', False):
            upload_data['stream'] = "1"
        if meta.get('resolution', '') in ['576p', '540p', '480p']:
            upload_data['sd'] = "1"
        if meta.get('personalrelease', False):
            upload_data['personal_release'] = "1"

        return upload_data
