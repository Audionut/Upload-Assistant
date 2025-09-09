# -*- coding: utf-8 -*-
import asyncio
import httpx
import json
import langcodes
import os
import platform
import re
import unicodedata
from bs4 import BeautifulSoup
from langcodes.tag_parser import LanguageTagError
from src.console import console
from src.languages import process_desc_language
from src.tmdb import get_tmdb_localized_data
from src.trackers.COMMON import COMMON


class GPW():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'GPW'
        self.banned_groups = ['']
        self.source_flag = 'GreatPosterWall'
        self.base_url = 'https://greatposterwall.com'
        self.torrent_url = 'https://greatposterwall.com/torrents.php?torrentid='
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Upload realizado via Audionut's Upload Assistant[/url][/center]"

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f'[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            upload_page_url = f'{self.base_url}/upload.php'
            response = await self.session.get(upload_page_url, timeout=30.0)
            response.raise_for_status()

            if 'login.php' in str(response.url):
                console.print(f'[bold red]Falha na validação do {self.tracker}. O cookie parece estar expirado (redirecionado para login).[/bold red]')
                return False

            auth_match = re.search(r'name="auth" value="([^"]+)"', response.text)

            user_link = re.search(r'user\.php\?id=(\d+)', response.text)
            if user_link:
                self.user_id = user_link.group(1)
            else:
                self.user_id = ''

            if not auth_match:
                console.print(f'[bold red]Falha na validação do {self.tracker}. Token auth não encontrado.[/bold red]')
                console.print('[yellow]A estrutura do site pode ter mudado ou o login falhou silenciosamente.[/yellow]')

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print(f'[yellow]A resposta do servidor foi salva em {failure_path} para análise.[/yellow]')
                return False

            self.auth_token = auth_match.group(1)
            return True

        except httpx.TimeoutException:
            console.print(f'[bold red]Erro no {self.tracker}: Timeout ao tentar validar credenciais.[/bold red]')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'[bold red]Erro HTTP ao validar credenciais do {self.tracker}: Status {e.response.status_code}.[/bold red]')
            return False
        except httpx.RequestError as e:
            console.print(f'[bold red]Erro de rede ao validar credenciais do {self.tracker}: {e.__class__.__name__}.[/bold red]')
            return False

    def load_localized_data(self, meta):
        localized_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/tmdb_localized_data.json"

        if os.path.isfile(localized_data_file):
            with open(localized_data_file, "r", encoding="utf-8") as f:
                self.tmdb_data = json.load(f)
        else:
            self.tmdb_data = {}

    async def ch_tmdb_data(self, meta):
        brazil_data_in_meta = self.tmdb_data.get('zh-cn', {}).get('main')
        if brazil_data_in_meta:
            return brazil_data_in_meta

        data = await get_tmdb_localized_data(meta, data_type='main', language='zh-cn', append_to_response='credits')
        self.load_localized_data(meta)

        return data

    async def get_container(self, meta):
        '''
        AVI
        MPG
        MP4
        MKV
        VOB IFO
        ISO
        m2ts
        Other
        '''
        container = None
        if meta['is_disc'] == 'BDMV':
            container = 'm2ts'
        elif meta['is_disc'] == 'DVD':
            container = 'VOB IFO'
        else:
            ext = os.path.splitext(meta['filelist'][0])[1]
            containermap = {
                '.mkv': 'MKV',
                '.mp4': 'MP4'
            }
            container = containermap.get(ext, 'Outro')
        return container

    async def get_subtitle(self, meta):
        if not meta.get('subtitle_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('subtitle_languages', [])

        if found_language_strings:
            return [lang.lower() for lang in found_language_strings]
        else:
            return 3

    async def codec(self, meta):
        '''
        * DivX
        * XviD
        * x264
        * H.264
        * x265
        * H.265
        * Other
        '''
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
        tmdb_data = await self.ch_tmdb_data(meta)

        title = tmdb_data.get('name') or tmdb_data.get('title') or ''

        return title if title and title != meta.get('title') else ''

    async def build_description(self, meta):
        description = []

        base_desc = ''
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()
                if base_desc:
                    description.append(base_desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description.append(custom_description_header + '\n')

        if self.signature:
            description.append(self.signature)

        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = '\n'.join(filter(None, description))
            descfile.write(final_description)

        return final_description

    async def get_trailer(self, meta):
        tmdb_data = await self.ch_tmdb_data(meta)
        video_results = tmdb_data.get('videos', {}).get('results', [])

        youtube = ''

        if video_results:
            youtube = video_results[-1].get('key', '')

        if not youtube:
            meta_trailer = meta.get('youtube', '')
            if meta_trailer:
                youtube = meta_trailer.replace('https://www.youtube.com/watch?v=', '').replace('/', '')

        return youtube

    async def get_tags(self, meta):
        tmdb_data = await self.ch_tmdb_data(meta)
        tags = ''

        if tmdb_data and isinstance(tmdb_data.get('genres'), list):
            genre_names = [
                g.get('name', '') for g in tmdb_data['genres']
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
            tags = await asyncio.to_thread(input, f'Digite os gêneros (no formato do {self.tracker}): ')

        return tags

    async def search_existing(self, meta, disctype):
        is_tv_pack = bool(meta.get('tv_pack'))

        search_url = f"{self.base_url}/torrents.php?searchstr={meta['imdb_info']['imdbID']}"

        found_items = []
        try:
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

    async def media_info(self, meta):
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

    async def processing_other(self, meta):
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

    async def get_remaster_title(self, meta):
        '''
        Collections
        - Masters of Cinema → 'masters_of_cinema'
        - The Criterion Collection → 'the_criterion_collection'
        - Warner Archive Collection → 'warner_archive_collection'

        Editions
        - Director's Cut → 'director_s_cut'
        - Extended Edition → 'extended_edition'
        - Rifftrax → 'rifftrax'
        - Theatrical Cut → 'theatrical_cut'
        - Uncut → 'uncut'
        - Unrated → 'unrated'

        Features
        - 2D/3D Edition → '2d_3d_edition'
        - 3D Anaglyph → '3d_anaglyph'
        - 3D Full SBS → '3d_full_sbs'
        - 3D Half OU → '3d_half_ou'
        - 3D Half SBS → '3d_half_sbs'
        - 2-Disc Set → '2_disc_set'
        - 2in1 → '2_in_1'
        - 4K Restoration → '4k_restoration'
        - 4K Remaster → '4k_remaster'
        - Remaster → 'remaster'
        - Dual Audio → 'dual_audio'
        - English Dub → 'english_dub'
        - Extras → 'extras'
        - With Commentary → 'with_commentary'
        '''

    async def get_groupid(self, meta):
        ''''''

    async def source(self, meta):
        '''
        * VHS
        * DVD
        * HD-DVD
        * TV
        * HDTV
        * WEB
        * Blu-ray
        * Other
        '''

    async def processing(self, meta):
        '''
        * Encode
        * Remux
        * DIY
        * Untouched
        '''

    async def codec_other(self, meta):
        '''
        Se não tiver nos codecs abaixo, tem que retornar nessa função o codec manualmente, senão retornar ''
        * DivX
        * XviD
        * x264
        * H.264
        * x265
        * H.265
        * Other
        '''

    async def fetch_data(self, meta, disctype):
        self.load_localized_data(meta)
        await self.validate_credentials(meta)
        remaster_title = await self.get_remaster_title(meta)

        data = {
            'audio_51': 'on' if meta.get('channels', '') == '5.1' else 'off',
            'audio_71': 'on' if meta.get('channels', '') == '7.1' else 'off',
            'auth': self.auth_token,
            'codec_other': await self.codec_other(meta),
            'codec': await self.codec(meta),
            'container': await self.get_container(meta),
            'dolby_atmos': 'on' if 'atmos' in meta.get('audio', '').lower() else 'off',
            'groupid': await self.get_groupid(meta),
            'mediainfo[]': await self.media_info(meta),
            'movie_edition_information': 'on' if remaster_title else 'off',
            'processing_other': await self.processing_other(meta) if meta.get('type') == 'DISC' else '',
            'processing': await self.processing(meta),
            'release_desc': await self.build_description(meta),
            'remaster_custom_title': '',
            'remaster_title_show': remaster_title.get('remaster_title_show'),
            'remaster_title': remaster_title.get('remaster_title'),
            'remaster_year': '',
            'resolution_height': '',
            'resolution_width': '',
            'resolution': meta.get('resolution'),
            'source_other': '',
            'source': await self.source(meta),
            'submit': 'true',
            'subtitle_type': '1' if meta.get('subtitle_languages', []) else '3',  # 1. Softcoded subtitles / 2.  Hardcoded subtitles / 3. No Subtitles
        }

        return data

    async def upload(self, meta, disctype):
        await self.load_cookies(meta)
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta, disctype)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            upload_url = f'{self.base_url}/upload.php'
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file_input': (f'{self.tracker}.placeholder.torrent', torrent_file, 'application/x-bittorrent')}

                response = await self.session.post(upload_url, data=data, files=files, timeout=120)

                if response.status_code in (302, 303):
                    status_message = 'Enviado com sucesso.'

                else:
                    status_message = 'O upload pode ter falhado, verifique. '
                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    console.print(f'Falha no upload, a resposta HTML foi salva em: {response_save_path}')
                    meta['skipping'] = f'{self.tracker}'
                    return

            await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
