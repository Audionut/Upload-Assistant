# -*- coding: utf-8 -*-
import asyncio
import httpx
import langcodes
import os
import pycountry
import re
import requests
import unicodedata
from .COMMON import COMMON
from bs4 import BeautifulSoup
from datetime import datetime
from http.cookiejar import MozillaCookieJar
from langcodes.tag_parser import LanguageTagError
from pathlib import Path
from src.console import console
from src.exceptions import UploadException
from src.languages import process_desc_language
from urllib.parse import urlparse


class BJS(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "BJS"
        self.banned_groups = [""]
        self.source_flag = "BJ"
        self.base_url = "https://bj-share.info"
        self.auth_token = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    def assign_media_properties(self, meta):
        self.imdb_id = meta['imdb_info']['imdbID']
        self.tmdb_id = meta['tmdb']
        self.category = meta['category']
        self.season = meta.get('season_int', '')
        self.episode = meta.get('episode_int', '')
        self.is_tv_pack = meta.get('tv_pack', '') == 1

    async def ptbr_tmdb_data(self, meta):
        self.assign_media_properties(meta)
        tmdb_api = self.config['DEFAULT']['tmdb_api']
        tmdb_data = None

        base_url = "https://api.themoviedb.org/3"
        url = f"{base_url}/{self.category.lower()}/{self.tmdb_id}?api_key={tmdb_api}&language=pt-BR&append_to_response=credits,videos,content_ratings"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        except httpx.RequestError:
            return None

        if not tmdb_data:
            return None

    async def required_data(self, meta):
        data = await self.ptbr_tmdb_data(meta)
        required_fields = {}
        required_fields.update({
            'Data de Lançamento ou Primeira Exibição': data.get('first_air_date') or data.get('release_date'),
            'Elenco': [a.get("name") for a in data.get('credits', {}).get('cast', []) if a.get("name")],
            'Gêneros': [g.get("name") for g in data.get('genres', []) if g.get("name")],
            'Idioma Original': data.get('original_language'),
            'Sinopse (Português)': data.get('overview'),
        })

        if self.category == 'TV':
            required_fields.update({
                'Criado(a) por': [p.get("name") for p in data.get('created_by', []) if p.get("name")],
            })
        if self.category == 'MOVIE':
            required_fields.update({
                'Diretor': meta.get('tmdb_directors') if meta.get('tmdb_directors') and any(meta.get('tmdb_directors')) else None
            })

        missing_items = [name for name, value in required_fields.items() if not value]

        if missing_items:
            missing_fields_str = ', '.join(missing_items)
            error_message = (
                f"""Upload bloqueado. Campos obrigatórios faltando no TMDB: {missing_fields_str}
                Por favor, adicione as informações em: https://www.themoviedb.org/{self.category.lower()}/{self.tmdb_id}/edit?language=pt-BR"""
            )
            meta['tracker_status'][self.tracker]['status_message'] = f"{error_message}"
            raise UploadException(error_message)

    async def get_rating(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)
        ratings = tmdb_data.get('content_ratings', {}).get('results', [])

        if not ratings:
            return ''

        VALID_BR_RATINGS = {'L', '10', '12', '14', '16', '18'}

        br_rating = ''
        us_rating = ''

        for item in ratings:
            if item.get('iso_3166_1') == 'BR' and item.get('rating') in VALID_BR_RATINGS:
                br_rating = item['rating']
                if br_rating == 'L':
                    br_rating = 'Livre para todos os públicos'
                else:
                    br_rating = f"Não recomendado para menores de {br_rating} anos"
                break

            # Use US rating as fallback
            if item.get('iso_3166_1') == 'US' and not us_rating:
                us_rating = item.get('rating', '')

        return br_rating or us_rating or ''

    async def get_original_language(self, meta):
        possible_languages = {
            "Alemão", "Árabe", "Argelino", "Búlgaro", "Cantonês", "Chinês",
            "Coreano", "Croata", "Dinamarquês", "Egípcio", "Espanhol", "Estoniano",
            "Filipino", "Finlandês", "Francês", "Grego", "Hebraico", "Hindi",
            "Holandês", "Húngaro", "Indonésio", "Inglês", "Islandês", "Italiano",
            "Japonês", "Macedônio", "Malaio", "Marati", "Nigeriano", "Norueguês",
            "Persa", "Polaco", "Polonês", "Português", "Português (pt)", "Romeno",
            "Russo", "Sueco", "Tailandês", "Tamil", "Tcheco", "Telugo", "Turco",
            "Ucraniano", "Urdu", "Vietnamita", "Zulu", "Outro"
        }
        tmdb_data = await self.ptbr_tmdb_data(meta)
        lang_code = tmdb_data.get("original_language")
        origin_countries = tmdb_data.get("origin_country", [])

        if not lang_code:
            return "Outro"

        language_name = None

        if lang_code == 'pt':
            if 'PT' in origin_countries:
                language_name = "Português (pt)"
            else:
                language_name = "Português"
        else:
            try:
                language_name = langcodes.Language.make(lang_code).display_name('pt').capitalize()
            except LanguageTagError:
                language_name = lang_code

        if language_name in possible_languages:
            return language_name
        else:
            return "Outro"

    async def search_existing(self, meta, disctype):
        if meta.get('debug'):
            return []

        self.assign_media_properties(meta)
        upload_season_num = None
        upload_episode_num = None
        upload_resolution = meta.get('resolution')
        process_folder_name = False

        if self.category == 'TV':
            season_match = meta.get('season', '').replace('S', '')
            if season_match:
                upload_season_num = season_match

            if not self.is_tv_pack:
                episode_match = meta.get('episode', '').replace('E', '')
                if episode_match:
                    upload_episode_num = episode_match

        search_url = f"{self.base_url}/torrents.php?searchstr={self.imdb_id}"

        found_items = []
        try:
            response = self.session.get(search_url, allow_redirects=False)
            if response.status_code in [301, 302, 307] and 'Location' in response.headers:
                redirect_url = f"{self.base_url}/{response.headers['Location']}"
                response = self.session.get(redirect_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            torrent_details_table = soup.find('div', class_='main_column')

            episode_found_on_page = False
            if self.category == 'TV' and not self.is_tv_pack and upload_season_num and upload_episode_num:
                temp_season_on_page = None
                upload_episode_str = f"E{upload_episode_num}"
                for r in torrent_details_table.find_all('tr'):
                    if 'season_header' in r.get('class', []):
                        s_match = re.search(r'Temporada (\d+)', r.get_text(strip=True))
                        if s_match:
                            temp_season_on_page = s_match.group(1)
                        continue
                    if temp_season_on_page == upload_season_num and r.get('id', '').startswith('torrent'):
                        link = r.find('a', onclick=re.compile(r"loadIfNeeded\("))
                        if link and re.search(r'\b' + re.escape(upload_episode_str) + r'\b', link.get_text(strip=True)):
                            episode_found_on_page = True
                            break

            # Get the cover while searching for dupes
            cover_div = soup.find('div', id='cover_div_0')
            image_url = None

            if cover_div:
                link_tag = cover_div.find('a')
                if link_tag and link_tag.get('href'):
                    image_url = link_tag['href']

            if image_url:
                self.cover = image_url

            if not torrent_details_table:
                return []

            current_season_on_page = None
            current_resolution_on_page = None
            for row in torrent_details_table.find_all('tr'):
                if 'resolution_header' in row.get('class', []):
                    header_text = row.get_text(strip=True)
                    resolution_match = re.search(r'(\d{3,4}p)', header_text)
                    if resolution_match:
                        current_resolution_on_page = resolution_match.group(1)
                    continue
                if 'season_header' in row.get('class', []):
                    season_header_text = row.get_text(strip=True)
                    season_match = re.search(r'Temporada (\d+)', season_header_text)
                    if season_match:
                        current_season_on_page = season_match.group(1)
                    continue

                if not row.get('id', '').startswith('torrent'):
                    continue

                torrent_row = row
                id_link = torrent_row.find('a', onclick=re.compile(r"loadIfNeeded\("))
                if not id_link:
                    continue

                description_text = " ".join(id_link.get_text(strip=True).split())

                should_make_ajax_call = False

                # TV
                if self.category == 'TV':
                    if current_season_on_page == upload_season_num:
                        existing_episode_match = re.search(r'E(\d+)', description_text)
                        is_current_row_a_pack = not existing_episode_match

                        # Case 1: We are uploading a SEASON PACK
                        if self.is_tv_pack:
                            if is_current_row_a_pack:
                                should_make_ajax_call = True

                        # Case 2: We are uploading a SINGLE EPISODE
                        else:
                            # Subcase 2a: Exact episode was found on the page. Only process that match.
                            if episode_found_on_page:
                                if existing_episode_match:
                                    existing_episode_num = existing_episode_match.group(1)
                                    if existing_episode_num == upload_episode_num:
                                        should_make_ajax_call = True
                            # Subcase 2b: Exact episode not found. Process season packs instead.
                            else:
                                if is_current_row_a_pack:
                                    process_folder_name = True
                                    should_make_ajax_call = True

                # MOVIE
                if self.category == 'MOVIE':
                    # Only process matching resolution
                    if upload_resolution and current_resolution_on_page == upload_resolution:
                        should_make_ajax_call = True

                if should_make_ajax_call:
                    onclick_attr = id_link['onclick']
                    id_match = re.search(r"loadIfNeeded\('(\d+)',\s*'(\d+)'", onclick_attr)
                    if not id_match:
                        continue

                    torrent_id = id_match.group(1)
                    group_id = id_match.group(2)
                    ajax_url = f"{self.base_url}/ajax.php?action=torrent_content&torrentid={torrent_id}&groupid={group_id}"

                    try:
                        ajax_response = self.session.get(ajax_url)
                        ajax_response.raise_for_status()
                        ajax_soup = BeautifulSoup(ajax_response.text, 'html.parser')
                    except requests.exceptions.RequestException as e:
                        console.print(f"[yellow]Não foi possível buscar a lista de arquivos para o torrent {torrent_id}: {e}[/yellow]")
                        continue

                    item_name = None
                    is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                    if is_existing_torrent_a_disc or self.is_tv_pack or process_folder_name:
                        path_div = ajax_soup.find('div', class_='filelist_path')
                        if path_div and path_div.get_text(strip=True):
                            item_name = path_div.get_text(strip=True).strip('/')
                        else:
                            file_table = ajax_soup.find('table', class_='filelist_table')
                            if file_table:
                                first_file_row = file_table.find('tr', class_=lambda x: x != 'colhead_dark')
                                if first_file_row and first_file_row.find('td'):
                                    item_name = first_file_row.find('td').get_text(strip=True)
                    else:
                        file_table = ajax_soup.find('table', class_='filelist_table')
                        if file_table:
                            first_row = file_table.find('tr', class_=lambda x: x != 'colhead_dark')
                            if first_row and first_row.find('td'):
                                item_name = first_row.find('td').get_text(strip=True)

                    if item_name:
                        found_items.append(item_name)

        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Ocorreu um erro de rede ao buscar por duplicatas: {e}[/bold red]")
            return []
        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            return []

        return found_items

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False

        try:
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies = jar
        except Exception as e:
            console.print(f"[bold red]Erro ao carregar o arquivo de cookie. Verifique se o formato está correto. Erro: {e}[/bold red]")
            return False

        try:
            upload_page_url = f"{self.base_url}/upload.php"
            response = self.session.get(upload_page_url, timeout=10, allow_redirects=True)

            if 'login.php' in str(response.url):
                console.print(f"[bold red]Falha na validação do {self.tracker}. O cookie parece estar expirado ou é inválido.[/bold red]")
                return False

            auth_match = re.search(r'name="auth" value="([^"]+)"', response.text)

            if auth_match:
                self.auth_token = auth_match.group(1)
                return True
            else:
                console.print(f"[bold red]Falha na validação do {self.tracker}. Não foi possível encontrar o token 'auth' na página de upload.[/bold red]")
                console.print("[yellow]Isso pode acontecer se a estrutura do site mudou ou se o login falhou silenciosamente.[/yellow]")
                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                with open(failure_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                console.print(f"[yellow]A resposta do servidor foi salva em {failure_path} para análise.[/yellow]")
                return False

        except Exception as e:
            console.print(f"[bold red]Erro ao validar credenciais do {self.tracker}: {e}[/bold red]")
            return False

    def get_type(self, meta):
        self.assign_media_properties(meta)

        if meta.get('anime'):
            return '13'

        category_map = {
            'TV': '1',
            'MOVIE': '0'
        }

        return category_map.get(self.category)

    def get_container(self, meta):
        container = None
        if meta["is_disc"] == "BDMV":
            container = "M2TS"
        elif meta['is_disc'] == "DVD":
            container = "VOB"
        else:
            ext = os.path.splitext(meta['filelist'][0])[1]
            containermap = {
                '.mkv': "MKV",
                '.mp4': 'MP4'
            }
            container = containermap.get(ext, 'Outro')
        return container

    async def get_subtitles(self, meta):
        await process_desc_language(meta, desc=None, tracker=self.tracker)
        found_language_strings = meta.get('subtitle_languages', [])

        tipolegenda = 'Nenhuma'

        if 'Portuguese' in found_language_strings:
            tipolegenda = 'Embutida'

        else:
            video_path = meta.get('path')
            directory = video_path if os.path.isdir(video_path) else os.path.dirname(video_path)
            subtitle_extensions = ('.srt', '.sub', '.ass', '.ssa', '.idx', '.smi', '.psb')

            if any(f.lower().endswith(subtitle_extensions) for f in os.listdir(directory)):
                if meta['keep_folder']:
                    tipolegenda = 'Arquivos Separados'
                else:
                    meta['tracker_status'][self.tracker]['status_message'] = (
                        "ERRO: Seu upload contém legendas em arquivos separados."
                        "Use [yellow]-kf[/yellow] ou [yellow]--keep-folder[/yellow] para incluir todos os arquivos da pasta."
                    )
                    raise UploadException("Legendas externas detectadas sem o uso de -kf/--keep-folder")

        return tipolegenda

    async def get_audio(self, meta):
        await process_desc_language(meta, desc=None, tracker=self.tracker)

        audio_languages = set(meta.get('audio_languages', []))

        portuguese_languages = ['Portuguese', 'Português']

        has_pt_audio = any(lang in portuguese_languages for lang in audio_languages)

        original_lang = meta.get('original_language', '').lower()
        is_original_pt = original_lang in portuguese_languages

        if has_pt_audio:
            if is_original_pt:
                return "Nacional"
            elif len(audio_languages) > 1:
                return "Dual Áudio"
            else:
                return "Dublado"

        return "Legendado"

    def get_video_codec(self, meta):
        CODEC_MAP = {
            'x265': 'x265',
            'h.265': 'H.265',
            'x264': 'x264',
            'h.264': 'H.264',
            'av1': 'AV1',
            'divx': 'DivX',
            'h.263': 'H.263',
            'kvcd': 'KVCD',
            'mpeg-1': 'MPEG-1',
            'mpeg-2': 'MPEG-2',
            'realvideo': 'RealVideo',
            'vc-1': 'VC-1',
            'vp6': 'VP6',
            'vp8': 'VP8',
            'vp9': 'VP9',
            'windows media video': 'Windows Media Video',
            'xvid': 'XviD',
            'hevc': 'H.265',
            'avc': 'H.264',
        }

        video_encode = meta.get('video_encode', '').lower()
        video_codec = meta.get('video_codec', '')

        search_text = f"{video_encode} {video_codec.lower()}"

        for key, value in CODEC_MAP.items():
            if key in search_text:
                return value

        return video_codec if video_codec else "Outro"

    def get_audio_codec(self, meta):
        priority_order = [
            "DTS-X", "E-AC-3 JOC", "TrueHD", "DTS-HD", "LPCM", "PCM", "FLAC",
            "DTS-ES", "DTS", "E-AC-3", "AC3", "AAC", "Opus", "Vorbis", "MP3", "MP2"
        ]

        codec_map = {
            "DTS-X": ["DTS:X", "DTS-X"],
            "E-AC-3 JOC": ["E-AC-3 JOC", "DD+ JOC"],
            "TrueHD": ["TRUEHD"],
            "DTS-HD": ["DTS-HD", "DTSHD"],
            "LPCM": ["LPCM"],
            "PCM": ["PCM"],
            "FLAC": ["FLAC"],
            "DTS-ES": ["DTS-ES"],
            "DTS": ["DTS"],
            "E-AC-3": ["E-AC-3", "DD+"],
            "AC3": ["AC3", "DD"],
            "AAC": ["AAC"],
            "Opus": ["OPUS"],
            "Vorbis": ["VORBIS"],
            "MP2": ["MP2"],
            "MP3": ["MP3"]
        }

        audio_description = meta.get('audio')

        if not audio_description or not isinstance(audio_description, str):
            return "Outro"

        audio_upper = audio_description.upper()

        for codec_name in priority_order:
            search_terms = codec_map.get(codec_name, [])

            for term in search_terms:
                if term.upper() in audio_upper:
                    return codec_name

        return "Outro"

    def get_edition(self, meta):
        edition_str = meta.get('edition', '').lower()
        if not edition_str:
            return ""

        edition_map = {
            "director's cut": "Director's Cut",
            "extended": "Extended Edition",
            "imax": "IMAX",
            "open matte": "Open Matte",
            "noir": "Noir Edition",
            "theatrical": "Theatrical Cut",
            "uncut": "Uncut",
            "unrated": "Unrated",
            "uncensored": "Uncensored",
        }

        for keyword, label in edition_map.items():
            if keyword in edition_str:
                return label

        return ""

    def get_bitrate(self, meta):
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = meta.get('disctype')
                if disctype in ["BD100", "BD66", "BD50", "BD25"]:
                    return disctype

                try:
                    size_in_gb = meta['bdinfo']['size']
                except (KeyError, IndexError, TypeError):
                    size_in_gb = 0

                if size_in_gb > 66:
                    return "BD100"
                elif size_in_gb > 50:
                    return "BD66"
                elif size_in_gb > 25:
                    return "BD50"
                else:
                    return "BD25"

            elif is_disc_type == 'DVD':
                dvd_size = meta.get('dvd_size')
                if dvd_size in ["DVD9", "DVD5"]:
                    return dvd_size
                return "DVD9"

        source_type = meta.get('type')

        if not source_type or not isinstance(source_type, str):
            return "Outro"

        keyword_map = {
            'webdl': 'WEB-DL',
            'webrip': 'WEBRip',
            'web': 'WEB',
            'encode': 'Blu-ray',
            'bdrip': 'BDRip',
            'brrip': 'BRRip',
            'hdtv': 'HDTV',
            'sdtv': 'SDTV',
            'dvdrip': 'DVDRip',
            'hd-dvd': 'HD DVD',
            'dvdscr': 'DVDScr',
            'hdrip': 'HDRip',
            'hdtc': 'HDTC',
            'hdtv': 'HDTV',
            'pdtv': 'PDTV',
            'sdtv': 'SDTV',
            'tc': 'TC',
            'uhdtv': 'UHDTV',
            'vhsrip': 'VHSRip',
            'tvrip': 'TVRip',
        }

        return keyword_map.get(source_type.lower(), "Outro")

    async def img_host(self, image_bytes: bytes, filename: str) -> str | None:
        upload_url = f"{self.base_url}/ajax.php?action=screen_up"
        headers = {
            'Referer': f"{self.base_url}/upload.php",
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        }
        files = {'file': (filename, image_bytes, 'image/png')}

        try:
            response = await asyncio.to_thread(
                self.session.post, upload_url, headers=headers, files=files, timeout=60
            )
            if response.ok:
                data = response.json()
                return data.get('url', '').replace('\\/', '/')
            else:
                print(f"Erro no upload de {filename}: Status {response.status_code}")
                return None
        except Exception as e:
            print(f"Exceção no upload de {filename}: {e}")
            return None

    async def get_cover(self, meta, disctype):
        await self.search_existing(meta, disctype)
        # Use an existing cover instead of uploading a new one
        if self.cover:
            return self.cover
        else:
            tmdb_data = await self.ptbr_tmdb_data(meta)
            cover_path = tmdb_data.get('poster_path') or meta.get('tmdb_poster')
            if not cover_path:
                print("Nenhum poster_path encontrado nos dados do TMDB.")
                return None

            cover_tmdb_url = f"https://image.tmdb.org/t/p/w500{cover_path}"
            try:
                response = await self.session.get(cover_tmdb_url, timeout=60)
                response.raise_for_status()
                image_bytes = response.content
                filename = os.path.basename(cover_path)

                return await self.img_host(image_bytes, filename)
            except Exception as e:
                print(f"Falha ao processar pôster da URL {cover_tmdb_url}: {e}")
                return None

    async def get_screenshots(self, meta):
        screenshot_dir = Path(meta['base_dir']) / 'tmp' / meta['uuid']
        local_files = sorted(screenshot_dir.glob('*.png'))

        tasks = []
        # Use existing files
        if local_files:
            print(f"Enviando {len(local_files)} screenshots para o {self.tracker}.")

            async def upload_local_file(path):
                with open(path, 'rb') as f:
                    image_bytes = f.read()
                return await self.img_host(image_bytes, os.path.basename(path))

            tasks = [upload_local_file(path) for path in local_files[:6]]

        # If no files are found, get them from meta links
        else:
            image_links = [img.get('raw_url') for img in meta.get('image_list', []) if img.get('raw_url')][:6]
            if len(image_links) < 2:
                raise UploadException(f"[bold red]FALHA NO UPLOAD:[/bold red] É necessário pelo menos 2 screenshots para fazer upload para o {self.tracker}.")

            async def upload_remote_file(url):
                try:
                    response = await asyncio.to_thread(self.session.get, url, timeout=60)
                    response.raise_for_status()
                    image_bytes = response.content
                    filename = os.path.basename(urlparse(url).path) or "screenshot.png"
                    return await self.img_host(image_bytes, filename)
                except Exception as e:
                    print(f"Falha ao processar screenshot da URL {url}: {e}")
                    return None

            tasks = [upload_remote_file(link) for link in image_links]

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)
        final_urls = [url for url in results if url]

        if len(final_urls) < 2:
            raise UploadException(f"[bold red]FALHA NO UPLOAD:[/bold red] O host de imagem do {self.tracker} não retornou o número mínimo de screenshots.")

        return final_urls

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        base_desc = ""
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()

        description_parts = []

        description_parts.append(base_desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header + "\n")

        if self.signature:
            description_parts.append(self.signature)

        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = "\n".join(filter(None, description_parts))
            descfile.write(final_description)

    def get_resolution(self, meta):
        width, height = "", ""

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

        return {
            'resolucaow': width,
            'resolucaoh': height
        }

    async def get_cast(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)
        cast_data = (tmdb_data.get('credits') or {}).get('cast', [])
        if cast_data:
            return ", ".join(
                cast_member['name']
                for cast_member in cast_data[:4]
                if cast_member.get('name')
            )
        else:
            meta['tracker_status'][self.tracker]['status_message'] = "Não foi encontrado o elenco no TMDB. O upload não pode continuar."
            raise UploadException("Não foi encontrado o elenco no TMDB. O upload não pode continuar.")

    def get_runtime(self, meta):
        try:
            minutes_in_total = int(meta.get('runtime'))
            if minutes_in_total < 0:
                return 0, 0
        except (ValueError, TypeError):
            return 0, 0

        hours, minutes = divmod(minutes_in_total, 60)
        return {
            'hours': hours,
            'minutes': minutes
        }

    def get_release_date(self, tmdb_data):
        raw_date_string = tmdb_data.get('first_air_date') or tmdb_data.get('release_date')

        if not raw_date_string:
            return ""

        try:
            date_object = datetime.strptime(raw_date_string, "%Y-%m-%d")
            formatted_date = date_object.strftime("%d %b %Y")

            return formatted_date

        except ValueError:
            return ""

    async def get_trailer(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)
        video_results = tmdb_data.get('videos', {}).get('results', [])
        youtube_code = video_results[-1].get('key', '') if video_results else ''
        if youtube_code:
            youtube = f"http://www.youtube.com/watch?v={youtube_code}"
        else:
            youtube = meta.get('youtube') or ''

        return youtube

    def find_remaster_tags(self, meta):
        found_tags = set()

        edition = self.get_edition(meta)
        if edition:
            found_tags.add(edition)

        audio_string = meta.get('audio', '')
        if 'Atmos' in audio_string:
            found_tags.add('Dolby Atmos')

        is_10_bit = False
        if meta.get('is_disc') == 'BDMV':
            try:
                bit_depth_str = meta['discs'][0]['bdinfo']['video'][0]['bit_depth']
                if '10' in bit_depth_str:
                    is_10_bit = True
            except (KeyError, IndexError, TypeError):
                pass
        else:
            if str(meta.get('bit_depth')) == '10':
                is_10_bit = True

        if is_10_bit:
            found_tags.add('10-bit')

        hdr_string = meta.get('hdr', '').upper()
        if 'DV' in hdr_string:
            found_tags.add('Dolby Vision')
        if 'HDR10+' in hdr_string:
            found_tags.add('HDR10+')
        if 'HDR' in hdr_string and 'HDR10+' not in hdr_string:
            found_tags.add('HDR10')

        if meta.get('type') == 'REMUX':
            found_tags.add('Remux')
        if meta.get('extras'):
            found_tags.add('Com extras')
        if meta.get('has_commentary') or meta.get('manual_commentary'):
            found_tags.add('Com comentários')

        return found_tags

    def build_remaster_title(self, meta):
        tag_priority = [
            'Dolby Atmos',
            'Remux',
            "Director's Cut",
            'Extended Edition',
            'IMAX',
            'Open Matte',
            'Noir Edition',
            'Theatrical Cut',
            'Uncut',
            'Unrated',
            'Uncensored',
            '10-bit',
            'Dolby Vision',
            'HDR10+',
            'HDR10',
            'Com extras',
            'Com comentários'
        ]
        available_tags = self.find_remaster_tags(meta)

        ordered_tags = []
        for tag in tag_priority:
            if tag in available_tags:
                ordered_tags.append(tag)

        return " / ".join(ordered_tags)

    async def data_prep(self, meta, disctype):
        await self.validate_credentials(meta)
        await self.edit_desc(meta)
        await self.required_data(meta)
        tmdb_data = await self.ptbr_tmdb_data(meta)

        data = {}

        # These fields are common across all upload types
        data.update({
            'submit': 'true',
            'auth': self.auth_token,
            'type': self.get_type(meta),
            'imdblink': meta['imdb_info']['imdbID'],
            'title': meta['title'],
            'titulobrasileiro': (tmdb_data.get('name') or tmdb_data.get('title')) if (tmdb_data.get('name') or tmdb_data.get('title')) != meta.get('title') else '',
            'tags': ', '.join(unicodedata.normalize('NFKD', g['name']).encode('ASCII', 'ignore').decode('utf-8').replace(' ', '.').lower() for g in tmdb_data.get('genres', [])),
            'year': str(meta['year']),
            'duracaotipo': 'selectbox',
            'duracaoHR': self.get_runtime(meta).get('hours'),
            'duracaoMIN': self.get_runtime(meta).get('minutes'),
            'traileryoutube': await self.get_trailer(meta),
            'formato': self.get_container(meta),
            'qualidade': self.get_bitrate(meta),
            'release': meta.get('service_longname', ''),
            'audio': await self.get_audio(meta),
            'tipolegenda': await self.get_subtitles(meta),
            'codecvideo': self.get_video_codec(meta),
            'codecaudio': self.get_audio_codec(meta),
            'idioma': await self.get_original_language(meta),
            'remaster_title': self.build_remaster_title(meta),
            'resolucaow': self.get_resolution(meta).get('resolucaow'),
            'resolucaoh': self.get_resolution(meta).get('resolucaoh'),
            'sinopse': tmdb_data.get('overview'),
            'fichatecnica': f"{open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', newline='', encoding='utf-8').read()}",
            })

        # These fields are common in movies and TV shows, even if it's anime
        if self.category == 'MOVIE':
            data.update({
                'adulto': '2',
                'diretor': ", ".join(set(meta.get('tmdb_directors', [])[:5])),
            })

        if self.category == 'TV':
            data.update({
                'diretor': ", ".join([p["name"] for p in tmdb_data.get("created_by", [])[:3] if "name" in p]),
                'tipo': 'episode' if meta.get('tv_pack') == 0 else 'season',
                'season': self.season,
                'episode': self.episode if not self.is_tv_pack else '',
            })

        # These fields are common in movies and TV shows, if not Anime
        if not meta.get('anime'):
            if self.category == 'MOVIE':
                data.update({
                    'validimdb': 'yes',
                    'imdbrating': str(meta.get('imdb_info', {}).get('rating', '')),
                    'elenco': await self.get_cast(meta),
                    'datalancamento': self.get_release_date(tmdb_data),
                })

            if self.category == 'TV':
                # Convert country code to name
                country_list = [
                    country.name
                    for code in tmdb_data.get('origin_country', [])
                    if (country := pycountry.countries.get(alpha_2=code))
                ]
                data.update({
                    'validimdb': 'yes',
                    'imdbrating': str(meta.get('imdb_info', {}).get('rating', '')),
                    'network': ", ".join([p.get("name", "Desconhecido") for p in tmdb_data.get("networks", [])]) or "",  # Optional
                    'numtemporadas': tmdb_data.get("number_of_seasons", ''),  # Optional
                    'datalancamento': self.get_release_date(tmdb_data),
                    'pais': ", ".join(country_list),  # Optional
                    'elenco': await self.get_cast(meta),
                    'diretorserie': ", ".join(set(meta.get('tmdb_directors', [])[:5])),  # Optional
                    'avaliacao': await self.get_rating(meta),  # Optional
                })

        # Anime-specific data
        if meta.get('anime'):
            if self.category == 'MOVIE':
                data.update({
                    'tipo': 'movie',
                })
            if self.category == 'TV':
                data.update({
                    'adulto': '2',
                })

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'on'
            })
            if self.config['TRACKERS'][self.tracker].get('show_group_if_anon', False):
                data.update({
                    'anonymousshowgroup': 'on'
                })

        # Only upload images if not debugging
        if not meta.get('debug', False):
            data.update({
                'image': await self.get_cover(meta, disctype),
                'screenshots[]': await self.get_screenshots(meta),
            })

        return data

    async def upload(self, meta, disctype):
        data = await self.data_prep(meta, disctype)
        if not meta.get('debug', False):
            await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
            upload_url = f"{self.base_url}/upload.php"
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            with open(torrent_path, 'rb') as torrent_file:
                files = {'file_input': (f"{self.tracker}.placeholder.torrent", torrent_file, "application/x-bittorrent")}

                try:
                    response = self.session.post(upload_url, data=data, files=files, timeout=60)

                    if response.status_code == 200 and 'Clique em baixar para entrar de' in response.text:
                        id_match = re.search(r'action=download&id=(\d+)', response.text)

                        if id_match:
                            torrent_id = id_match.group(1)
                            details_url = f"{self.base_url}/torrents.php?torrentid={torrent_id}"
                            announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                            await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                            final_message = details_url

                        else:
                            final_message = "[bold yellow]Upload parece ter sido bem-sucedido, mas não foi possível extrair o ID do torrent da página.[/bold yellow]"

                    else:
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                        with open(failure_path, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        final_message = f"""[bold red]Falha no upload para {self.tracker}. Status: {response.status_code}, URL: {response.url}[/bold red].
                                            [yellow]A resposta HTML foi salva em '{failure_path}' para análise.[/yellow]"""

                except requests.exceptions.RequestException as e:
                    final_message = f"[bold red]Erro de conexão ao fazer upload para {self.tracker}: {e}[/bold red]"

        else:
            console.print(data)
            final_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = final_message
