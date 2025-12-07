# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import httpx
import json
import langcodes
import os
import platform
import re
import unicodedata
from bs4 import BeautifulSoup
from langcodes.tag_parser import LanguageTagError
from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language
from src.tmdb import get_tmdb_localized_data
from src.trackers.COMMON import COMMON


class BT:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'BT'
        self.banned_groups = []
        self.source_flag = 'BT'
        self.base_url = 'https://brasiltracker.org'
        self.torrent_url = f'{self.base_url}/torrents.php?id='
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f'Upload Assistant ({platform.system()} {platform.release()})'
        }, timeout=60.0)

        target_site_ids = {
            'arabic': '22', 'bulgarian': '29', 'chinese': '14', 'croatian': '23',
            'czech': '30', 'danish': '10', 'dutch': '9', 'english - forçada': '50',
            'english': '3', 'estonian': '38', 'finnish': '15', 'french': '5',
            'german': '6', 'greek': '26', 'hebrew': '40', 'hindi': '41',
            'hungarian': '24', 'icelandic': '28', 'indonesian': '47', 'italian': '16',
            'japanese': '8', 'korean': '19', 'latvian': '37', 'lithuanian': '39',
            'norwegian': '12', 'persian': '52', 'polish': '17', 'português': '49',
            'romanian': '13', 'russian': '7', 'serbian': '31', 'slovak': '42',
            'slovenian': '43', 'spanish': '4', 'swedish': '11', 'thai': '20',
            'turkish': '18', 'ukrainian': '34', 'vietnamese': '25',
        }

        source_alias_map = {
            ('Arabic', 'ara', 'ar'): 'arabic',
            ('Brazilian Portuguese', 'Brazilian', 'Portuguese-BR', 'pt-br', 'pt-BR', 'Portuguese', 'por', 'pt', 'pt-PT', 'Português Brasileiro', 'Português'): 'português',
            ('Bulgarian', 'bul', 'bg'): 'bulgarian',
            ('Chinese', 'chi', 'zh', 'Chinese (Simplified)', 'Chinese (Traditional)', 'cmn-Hant', 'cmn-Hans', 'yue-Hant', 'yue-Hans'): 'chinese',
            ('Croatian', 'hrv', 'hr', 'scr'): 'croatian',
            ('Czech', 'cze', 'cz', 'cs'): 'czech',
            ('Danish', 'dan', 'da'): 'danish',
            ('Dutch', 'dut', 'nl'): 'dutch',
            ('English - Forced', 'English (Forced)', 'en (Forced)', 'en-US (Forced)'): 'english - forçada',
            ('English', 'eng', 'en', 'en-US', 'en-GB', 'English (CC)', 'English - SDH'): 'english',
            ('Estonian', 'est', 'et'): 'estonian',
            ('Finnish', 'fin', 'fi'): 'finnish',
            ('French', 'fre', 'fr', 'fr-FR', 'fr-CA'): 'french',
            ('German', 'ger', 'de'): 'german',
            ('Greek', 'gre', 'el'): 'greek',
            ('Hebrew', 'heb', 'he'): 'hebrew',
            ('Hindi', 'hin', 'hi'): 'hindi',
            ('Hungarian', 'hun', 'hu'): 'hungarian',
            ('Icelandic', 'ice', 'is'): 'icelandic',
            ('Indonesian', 'ind', 'id'): 'indonesian',
            ('Italian', 'ita', 'it'): 'italian',
            ('Japanese', 'jpn', 'ja'): 'japanese',
            ('Korean', 'kor', 'ko'): 'korean',
            ('Latvian', 'lav', 'lv'): 'latvian',
            ('Lithuanian', 'lit', 'lt'): 'lithuanian',
            ('Norwegian', 'nor', 'no'): 'norwegian',
            ('Persian', 'fa', 'far'): 'persian',
            ('Polish', 'pol', 'pl'): 'polish',
            ('Romanian', 'rum', 'ro'): 'romanian',
            ('Russian', 'rus', 'ru'): 'russian',
            ('Serbian', 'srp', 'sr', 'scc'): 'serbian',
            ('Slovak', 'slo', 'sk'): 'slovak',
            ('Slovenian', 'slv', 'sl'): 'slovenian',
            ('Spanish', 'spa', 'es', 'es-ES', 'es-419'): 'spanish',
            ('Swedish', 'swe', 'sv'): 'swedish',
            ('Thai', 'tha', 'th'): 'thai',
            ('Turkish', 'tur', 'tr'): 'turkish',
            ('Ukrainian', 'ukr', 'uk'): 'ukrainian',
            ('Vietnamese', 'vie', 'vi'): 'vietnamese',
        }

        self.ultimate_lang_map = {}
        for aliases_tuple, canonical_name in source_alias_map.items():
            if canonical_name in target_site_ids:
                correct_id = target_site_ids[canonical_name]
                for alias in aliases_tuple:
                    self.ultimate_lang_map[alias.lower()] = correct_id

    async def validate_credentials(self, meta):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/upload.php',
            error_text='login.php',
            token_pattern=r'name="auth" value="([^"]+)"'
        )

    async def load_localized_data(self, meta):
        localized_data_file = f'{meta["base_dir"]}/tmp/{meta["uuid"]}/tmdb_localized_data.json'
        main_ptbr_data = {}
        episode_ptbr_data = {}
        data = {}

        if os.path.isfile(localized_data_file):
            try:
                async with aiofiles.open(localized_data_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
            except json.JSONDecodeError:
                print(f'Warning: Could not decode JSON from {localized_data_file}')
                data = {}
            except Exception as e:
                print(f'Error reading file {localized_data_file}: {e}')
                data = {}

        main_ptbr_data = data.get('pt-BR', {}).get('main')

        if not main_ptbr_data:
            main_ptbr_data = await get_tmdb_localized_data(
                meta,
                data_type='main',
                language='pt-BR',
                append_to_response='credits,videos,content_ratings'
            )

        if self.config['DEFAULT']['episode_overview']:
            if meta['category'] == 'TV' and not meta.get('tv_pack'):
                episode_ptbr_data = data.get('pt-BR', {}).get('episode')
                if not episode_ptbr_data:
                    episode_ptbr_data = await get_tmdb_localized_data(
                        meta,
                        data_type='episode',
                        language='pt-BR',
                        append_to_response=''
                    )

        self.main_tmdb_data = main_ptbr_data or {}
        self.episode_tmdb_data = episode_ptbr_data or {}

        return

    async def get_container(self, meta):
        container = meta.get('container', '')
        if container in ['avi', 'm2ts', 'm4v', 'mkv', 'mp4', 'ts', 'vob', 'wmv', 'mkv']:
            return container.upper()

        return 'Outro'

    async def get_type(self, meta):
        if meta.get('anime'):
            return '5'

        category_map = {
            'TV': '1',
            'MOVIE': '0'
        }

        return category_map.get(meta['category'])

    async def get_languages(self, meta):
        lang_code = self.main_tmdb_data.get('original_language')

        if not lang_code:
            return None

        try:
            return langcodes.Language.make(lang_code).display_name('pt').capitalize()

        except LanguageTagError:
            return lang_code

    async def get_audio(self, meta):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        audio_languages = set(meta.get('audio_languages', []))

        portuguese_languages = ['Portuguese', 'Português', 'pt']

        has_pt_audio = any(lang in portuguese_languages for lang in audio_languages)

        original_lang = meta.get('original_language', '').lower()
        is_original_pt = original_lang in portuguese_languages

        if has_pt_audio:
            if is_original_pt:
                return 'Nacional'
            elif len(audio_languages) > 1:
                return 'Dual Audio'
            else:
                return 'Dublado'

        return 'Legendado'

    async def get_subtitle(self, meta):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('subtitle_languages', [])

        subtitle_ids = set()
        for lang_str in found_language_strings:
            target_id = self.ultimate_lang_map.get(lang_str.lower())
            if target_id:
                subtitle_ids.add(target_id)

        has_pt_subtitles = 'Sim' if '49' in subtitle_ids else 'Nao'

        subtitle_ids = sorted(list(subtitle_ids))

        if not subtitle_ids:
            subtitle_ids.append('44')

        return has_pt_subtitles, subtitle_ids

    async def get_resolution(self, meta):
        if meta.get('is_disc') == 'BDMV':
            resolution_str = meta.get('resolution', '')
            try:
                height_num = int(resolution_str.lower().replace('p', '').replace('i', ''))
                height = str(height_num)

                width_num = round((16 / 9) * height_num)
                width = str(width_num)
            except (ValueError, TypeError):
                pass

        else:
            video_mi = meta['mediainfo']['media']['track'][1]
            width = video_mi['Width']
            height = video_mi['Height']

        return width, height

    async def get_video_codec(self, meta):
        video_encode = meta.get('video_encode', '').strip().lower()
        codec_final = meta.get('video_codec', '')
        is_hdr = bool(meta.get('hdr'))

        encode_map = {
            'x265': 'x265',
            'h.265': 'H.265',
            'x264': 'x264',
            'h.264': 'H.264',
            'vp9': 'VP9',
            'xvid': 'XviD',
        }

        for key, value in encode_map.items():
            if key in video_encode:
                if value in ['x265', 'H.265'] and is_hdr:
                    return f'{value} HDR'
                return value

        codec_lower = codec_final.lower()

        codec_map = {
            'hevc': 'x265',
            'avc': 'x264',
            'mpeg-2': 'MPEG-2',
            'vc-1': 'VC-1',
        }

        for key, value in codec_map.items():
            if key in codec_lower:
                return f"{value} HDR" if value == "x265" and is_hdr else value

        return codec_final if codec_final else "Outro"

    async def get_audio_codec(self, meta):
        priority_order = [
            'DTS-X', 'E-AC-3 JOC', 'TrueHD', 'DTS-HD', 'PCM', 'FLAC', 'DTS-ES',
            'DTS', 'E-AC-3', 'AC3', 'AAC', 'Opus', 'Vorbis', 'MP3', 'MP2'
        ]

        codec_map = {
            'DTS-X': ['DTS:X'],
            'E-AC-3 JOC': ['DD+ 5.1 Atmos', 'DD+ 7.1 Atmos'],
            'TrueHD': ['TrueHD'],
            'DTS-HD': ['DTS-HD'],
            'PCM': ['LPCM'],
            'FLAC': ['FLAC'],
            'DTS-ES': ['DTS-ES'],
            'DTS': ['DTS'],
            'E-AC-3': ['DD+'],
            'AC3': ['DD'],
            'AAC': ['AAC'],
            'Opus': ['Opus'],
            'Vorbis': ['VORBIS'],
            'MP2': ['MP2'],
            'MP3': ['MP3']
        }

        audio_description = meta.get('audio')

        if not audio_description or not isinstance(audio_description, str):
            return 'Outro'

        for codec_name in priority_order:
            search_terms = codec_map.get(codec_name, [])

            for term in search_terms:
                if term in audio_description:
                    return codec_name

        return 'Outro'

    async def get_title(self, meta):
        title = self.main_tmdb_data.get('name') or self.main_tmdb_data.get('title') or ''

        return title if title and title != meta.get('title') else ''

    async def get_description(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # Logo
        logo_resize_url = meta.get('tmdb_logo', '')
        if logo_resize_url:
            desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

        # TV
        title = self.episode_tmdb_data.get('name', '')
        episode_image = self.episode_tmdb_data.get('still_path', '')
        episode_overview = self.episode_tmdb_data.get('overview', '')

        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')

            if episode_image:
                desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300{episode_image}[/img][/center]")

            desc_parts.append(f'[center]{episode_overview}[/center]')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        # Signature
        desc_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant]Upload realizado via {meta['ua_name']} {meta['current_version']}[/url][/center]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_img_resize(description)
        description = bbcode.remove_list(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def get_trailer(self, meta):
        video_results = self.main_tmdb_data.get('videos', {}).get('results', [])

        youtube = ''

        if video_results:
            youtube = video_results[-1].get('key', '')

        if not youtube:
            meta_trailer = meta.get('youtube', '')
            if meta_trailer:
                youtube = meta_trailer.replace('https://www.youtube.com/watch?v=', '').replace('/', '')

        return youtube

    async def get_tags(self, meta):
        tags = ''

        if self.main_tmdb_data and isinstance(self.main_tmdb_data.get('genres'), list):
            genre_names = [
                g.get('name', '') for g in self.main_tmdb_data['genres']
                if isinstance(g.get('name'), str) and g.get('name').strip()
            ]

            if genre_names:
                tags = ', '.join(
                    unicodedata.normalize('NFKD', name)
                    .encode('ASCII', 'ignore')
                    .decode('utf-8')
                    .replace(' ', '.')
                    .lower()
                    for name in genre_names
                )

        if not tags:
            tags = await self.common.async_input(prompt=f'Digite os gêneros (no formato do {self.tracker}): ')

        return tags

    async def search_existing(self, meta, disctype):
        is_tv_pack = bool(meta.get('tv_pack'))

        search_url = f"{self.base_url}/torrents.php?searchstr={meta['imdb_info']['imdbID']}"

        found_items = []
        try:
            self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)

            response = await self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            torrent_table = soup.find('table', id='torrent_table')
            if not torrent_table:
                return []

            group_links = set()
            for group_row in torrent_table.find_all('tr'):
                link = group_row.find('a', href=re.compile(r'torrents\.php\?id=\d+'))
                if link and 'torrentid' not in link.get('href', ''):
                    group_links.add(link['href'])

            if not group_links:
                return []

            for group_link in group_links:
                group_url = f'{self.base_url}/{group_link}'
                group_response = await self.session.get(group_url)
                group_response.raise_for_status()
                group_soup = BeautifulSoup(group_response.text, 'html.parser')

                for torrent_row in group_soup.find_all('tr', id=re.compile(r'^torrent\d+$')):
                    desc_link = torrent_row.find('a', onclick=re.compile(r'gtoggle'))
                    if not desc_link:
                        continue
                    description_text = ' '.join(desc_link.get_text(strip=True).split())

                    torrent_id = torrent_row.get('id', '').replace('torrent', '')
                    file_div = group_soup.find('div', id=f'files_{torrent_id}')
                    if not file_div:
                        continue

                    is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                    if is_existing_torrent_a_disc or is_tv_pack:
                        path_div = file_div.find('div', class_='filelist_path')
                        if path_div:
                            folder_name = path_div.get_text(strip=True).strip('/')
                            if folder_name:
                                found_items.append(folder_name)
                    else:
                        file_table = file_div.find('table', class_='filelist_table')
                        if file_table:
                            for row in file_table.find_all('tr'):
                                if 'colhead_dark' not in row.get('class', []):
                                    cell = row.find('td')
                                    if cell:
                                        filename = cell.get_text(strip=True)
                                        if filename:
                                            found_items.append(filename)
                                            break

        except Exception as e:
            console.print(f'[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]')
            return []

        return found_items

    async def get_media_info(self, meta):
        info_file_path = ''
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            try:
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                console.print(f'[bold red]Erro ao ler o arquivo de info em {info_file_path}: {e}[/bold red]')
                return ''
        else:
            console.print(f'[bold red]Arquivo de info não encontrado: {info_file_path}[/bold red]')
            return ''

    async def get_edition(self, meta):
        edition_str = meta.get('edition', '').lower()
        if not edition_str:
            return ''

        edition_map = {
            "director's cut": "Director's Cut",
            'theatrical': 'Theatrical Cut',
            'extended': 'Extended',
            'uncut': 'Uncut',
            'unrated': 'Unrated',
            'imax': 'IMAX',
            'noir': 'Noir',
            'remastered': 'Remastered',
        }

        for keyword, label in edition_map.items():
            if keyword in edition_str:
                return label

        return ''

    async def get_bitrate(self, meta):
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = meta.get('disctype')
                if disctype in ['BD100', 'BD66', 'BD50', 'BD25']:
                    return disctype

                try:
                    size_in_gb = meta['bdinfo']['size']
                except (KeyError, IndexError, TypeError):
                    size_in_gb = 0

                if size_in_gb > 66:
                    return 'BD100'
                elif size_in_gb > 50:
                    return 'BD66'
                elif size_in_gb > 25:
                    return 'BD50'
                else:
                    return 'BD25'

            elif is_disc_type == 'DVD':
                dvd_size = meta.get('dvd_size')
                if dvd_size in ['DVD9', 'DVD5']:
                    return dvd_size
                return 'DVD9'

        source_type = meta.get('type')

        if not source_type or not isinstance(source_type, str):
            return 'Outro'

        keyword_map = {
            'remux': 'Remux',
            'webdl': 'WEB-DL',
            'webrip': 'WEBRip',
            'web': 'WEB',
            'encode': 'Blu-ray',
            'bdrip': 'BDRip',
            'brrip': 'BRRip',
            'hdtv': 'HDTV',
            'sdtv': 'SDTV',
            'dvdrip': 'DVDRip',
            'hd-dvd': 'HD-DVD',
            'tvrip': 'TVRip',
        }

        return keyword_map.get(source_type.lower(), 'Outro')

    async def get_screens(self, meta):
        screenshot_urls = [
            image.get('raw_url')
            for image in meta.get('image_list', [])
            if image.get('raw_url')
        ]

        return screenshot_urls

    async def get_credits(self, meta):
        director = (meta.get('imdb_info', {}).get('directors') or []) + (meta.get('tmdb_directors') or [])
        if director:
            unique_names = list(dict.fromkeys(director))[:5]
            return ', '.join(unique_names)
        else:
            return 'N/A'

    async def get_data(self, meta):
        await self.load_localized_data(meta)
        has_pt_subtitles, subtitle_ids = await self.get_subtitle(meta)
        resolution_width, resolution_height = await self.get_resolution(meta)

        data = {
            'audio_c': await self.get_audio_codec(meta),
            'audio': await self.get_audio(meta),
            'auth': BT.secret_token,
            'bitrate': await self.get_bitrate(meta),
            'desc': '',
            'diretor': await self.get_credits(meta),
            'duracao': f"{str(meta.get('runtime', ''))} min",
            'especificas': await self.get_description(meta),
            'format': await self.get_container(meta),
            'idioma_ori': await self.get_languages(meta) or meta.get('original_language', ''),
            'image': f"https://image.tmdb.org/t/p/w500{self.main_tmdb_data.get('poster_path', '') or meta.get('tmdb_poster', '')}",
            'legenda': has_pt_subtitles,
            'mediainfo': await self.get_media_info(meta),
            'resolucao_1': resolution_width,
            'resolucao_2': resolution_height,
            'screen[]': await self.get_screens(meta),
            'sinopse': self.main_tmdb_data.get('overview', 'Nenhuma sinopse disponível.'),
            'submit': 'true',
            'subtitles[]': subtitle_ids,
            'tags': await self.get_tags(meta),
            'title': meta['title'],
            'type': await self.get_type(meta),
            'video_c': await self.get_video_codec(meta),
            'year': str(meta['year']),
            'youtube': await self.get_trailer(meta),
        }

        # Common data MOVIE/TV
        if not meta.get('anime'):
            if meta['category'] in ('MOVIE', 'TV'):
                data.update({
                    '3d': 'Sim' if meta.get('3d') else 'Nao',
                    'adulto': '0',
                    'imdb_input': meta.get('imdb_info', {}).get('imdbID', ''),
                    'nota_imdb': str(meta.get('imdb_info', {}).get('rating', '')),
                    'title_br': await self.get_title(meta),
                })
            if meta.get('scene', False):
                data['scene'] = 'on'

        # Common data TV/Anime
        tv_pack = bool(meta.get('tv_pack'))
        if meta['category'] == 'TV' or meta.get('anime'):
            data.update({
                'episodio': meta.get('episode', ''),
                'ntorrent': f"{meta.get('season', '')}{meta.get('episode', '')}",
                'temporada_e': meta.get('season', '') if not tv_pack else '',
                'temporada': meta.get('season', '') if tv_pack else '',
                'tipo': 'ep_individual' if not tv_pack else 'completa',
            })

        # Specific
        if meta['category'] == 'MOVIE':
            data['versao'] = await self.get_edition(meta)
        elif meta.get('anime'):
            data.update({
                'fundo_torrent': meta.get('backdrop'),
                'horas': '',
                'minutos': '',
                'rating': str(meta.get('imdb_info', {}).get('rating', '')),
                'releasedate': str(meta['year']),
                'vote': '',
            })

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data['anonymous'] = '1'

        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != '' and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data.update({
                    'internal': 1,
                })

        return data

    async def upload(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        data = await self.get_data(meta)

        await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='file_input',
            upload_cookies=self.session.cookies,
            upload_url=f"{self.base_url}/upload.php",
            id_pattern=r'groupid=(\d+)',
            success_status_code="200, 302, 303",
        )

        return
