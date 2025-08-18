# -*- coding: utf-8 -*-
import aiofiles
import asyncio
import httpx
import langcodes
import os
import platform
import pycountry
import re
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
from tqdm import tqdm
from typing import Optional
from urllib.parse import urlparse


class BJS(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "BJS"
        self.banned_groups = [""]
        self.source_flag = "BJ"
        self.base_url = "https://bj-share.info"
        self.torrent_url = "https://bj-share.info/torrents.php?torrentid="
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.cover = ''
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Upload realizado via Audionut's Upload Assistant[/url][/center]"

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False

        try:
            jar = MozillaCookieJar()
            loop = asyncio.get_running_loop()

            await loop.run_in_executor(
                None,
                lambda: jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
            )
            self.session.cookies = jar

        except FileNotFoundError:
            console.print(f"[bold red]Arquivo de cookie não encontrado ao tentar carregar: {cookie_file}[/bold red]")
            return False
        except Exception as e:
            console.print(f"[bold red]Erro ao carregar o arquivo de cookie. Formato inválido? Erro: {e}[/bold red]")
            return False

        try:
            upload_page_url = f"{self.base_url}/upload.php"
            response = await self.session.get(upload_page_url, timeout=30.0)
            response.raise_for_status()

            if 'login.php' in str(response.url):
                console.print(f"[bold red]Falha na validação do {self.tracker}. O cookie parece estar expirado (redirecionado para login).[/bold red]")
                return False

            auth_match = re.search(r'name="auth" value="([^"]+)"', response.text)

            if not auth_match:
                console.print(f"[bold red]Falha na validação do {self.tracker}. Token 'auth' não encontrado.[/bold red]")
                console.print("[yellow]A estrutura do site pode ter mudado ou o login falhou silenciosamente.[/yellow]")

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                async with aiofiles.open(failure_path, "w", encoding="utf-8") as f:
                    await f.write(response.text)
                console.print(f"[yellow]A resposta do servidor foi salva em {failure_path} para análise.[/yellow]")
                return False

            self.auth_token = auth_match.group(1)
            return True

        except httpx.TimeoutException:
            console.print(f"[bold red]Erro no {self.tracker}: Timeout ao tentar validar credenciais.[/bold red]")
            return False
        except httpx.HTTPStatusError as e:
            console.print(f"[bold red]Erro HTTP ao validar credenciais do {self.tracker}: Status {e.response.status_code}.[/bold red]")
            return False
        except httpx.RequestError as e:
            console.print(f"[bold red]Erro de rede ao validar credenciais do {self.tracker}: {e.__class__.__name__}.[/bold red]")
            return False

    async def ptbr_tmdb_data(self, meta):
        tmdb_api = self.config['DEFAULT']['tmdb_api']
        tmdb_data = None

        base_url = "https://api.themoviedb.org/3"
        url = f"{base_url}/{meta['category'].lower()}/{meta['tmdb']}?api_key={tmdb_api}&language=pt-BR&append_to_response=credits,videos,content_ratings"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        except httpx.RequestError:
            return None

        if not tmdb_data:
            return None

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

    def get_type(self, meta):
        if meta.get('anime'):
            return '13'

        category_map = {
            'TV': '1',
            'MOVIE': '0'
        }

        return category_map.get(meta['category'])

    async def get_languages(self, meta):
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

    async def get_audio(self, meta):
        await process_desc_language(meta, desc=None, tracker=self.tracker)

        audio_languages = set(meta.get('audio_languages', []))

        portuguese_languages = ['Portuguese', 'Português', 'pt']

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

    async def get_subtitle(self, meta):
        # Stops uploading when an external subtitle is detected
        video_path = meta.get('path')
        directory = video_path if os.path.isdir(video_path) else os.path.dirname(video_path)
        subtitle_extensions = ('.srt', '.sub', '.ass', '.ssa', '.idx', '.smi', '.psb')

        if any(f.lower().endswith(subtitle_extensions) for f in os.listdir(directory)):
            raise UploadException("[bold red]ERRO: Esta ferramenta não suporta o upload de legendas em arquivos separados.[/bold red]")

        await process_desc_language(meta, desc=None, tracker=self.tracker)
        found_language_strings = meta.get('subtitle_languages', [])

        subtitle_type = 'Nenhuma'

        if 'Portuguese' in found_language_strings:
            subtitle_type = 'Embutida'

        return subtitle_type

    def get_resolution(self, meta):
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
            'width': width,
            'height': height
        }

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

    async def get_title(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)

        title = tmdb_data.get('name') or tmdb_data.get('title') or ''

        return title if title and title != meta.get('title') else ''

    async def build_description(self, meta):
        description = []

        # The site does not auto-generate BDInfo like it does with MediaInfo, so it must be provided manually
        bd_info = ""
        if meta.get('is_disc') == 'BDMV':
            bd_summary = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary):
                with open(bd_summary, 'r', encoding='utf-8') as f:
                    bd_info = f.read()
                    if bd_info:
                        description.append(f"[quote]{bd_info}[/quote]")

        base_desc = ""
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()
                if base_desc:
                    description.append(base_desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description.append(custom_description_header + "\n")

        if self.signature:
            description.append(self.signature)

        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = "\n".join(filter(None, description))
            descfile.write(final_description)

        return final_description

    async def get_trailer(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)
        video_results = tmdb_data.get('videos', {}).get('results', [])
        youtube_code = video_results[-1].get('key', '') if video_results else ''
        if youtube_code:
            youtube = f"http://www.youtube.com/watch?v={youtube_code}"
        else:
            youtube = meta.get('youtube') or ''

        return youtube

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
                    br_rating = 'Livre'
                else:
                    br_rating = f"{br_rating} anos"
                break

            # Use US rating as fallback
            if item.get('iso_3166_1') == 'US' and not us_rating:
                us_rating = item.get('rating', '')

        return br_rating or us_rating or ''

    async def get_tags(self, meta):
        tmdb_data = await self.ptbr_tmdb_data(meta)
        tags = ""

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
            tags = await asyncio.to_thread(input, f"Digite os gêneros (no formato do {self.tracker}): ")

        return tags

    async def search_existing(self, meta, disctype):
        is_tv_pack = bool(meta.get('tv_pack'))
        upload_season_num = None
        upload_episode_num = None
        upload_resolution = meta.get('resolution')
        process_folder_name = False

        if meta['category'] == 'TV':
            season_match = meta.get('season', '').replace('S', '')
            if season_match:
                upload_season_num = season_match

            if not is_tv_pack:
                episode_match = meta.get('episode', '').replace('E', '')
                if episode_match:
                    upload_episode_num = episode_match

        search_url = f"{self.base_url}/torrents.php?searchstr={meta['imdb_info']['imdbID']}"

        found_items = []
        try:
            response = await self.session.get(search_url)
            if response.status_code in [301, 302, 307] and 'Location' in response.headers:
                redirect_url = f"{self.base_url}/{response.headers['Location']}"
                response = await self.session.get(redirect_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            torrent_details_table = soup.find('div', class_='main_column')

            episode_found_on_page = False
            if meta['category'] == 'TV' and not is_tv_pack and upload_season_num and upload_episode_num:
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
                if meta['category'] == 'TV':
                    if current_season_on_page == upload_season_num:
                        existing_episode_match = re.search(r'E(\d+)', description_text)
                        is_current_row_a_pack = not existing_episode_match

                        # Case 1: We are uploading a SEASON PACK
                        if is_tv_pack:
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
                if meta['category'] == 'MOVIE':
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
                        ajax_response = await self.session.get(ajax_url)
                        ajax_response.raise_for_status()
                        ajax_soup = BeautifulSoup(ajax_response.text, 'html.parser')
                    except Exception as e:
                        console.print(f"[yellow]Não foi possível buscar a lista de arquivos para o torrent {torrent_id}: {e}[/yellow]")
                        continue

                    item_name = None
                    is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                    if is_existing_torrent_a_disc or is_tv_pack or process_folder_name:
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

        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            return []

        return found_items

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

    async def img_host(self, image_bytes: bytes, filename: str) -> Optional[str]:
        upload_url = f"{self.base_url}/ajax.php?action=screen_up"
        headers = {
            "Referer": f"{self.base_url}/upload.php",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }
        files = {"file": (filename, image_bytes, "image/png")}

        try:
            response = await self.session.post(
                upload_url, headers=headers, files=files, timeout=120
            )
            response.raise_for_status()
            data = response.json()
            return data.get("url", "").replace("\\/", "/")
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
                response = await self.session.get(cover_tmdb_url, timeout=120)
                response.raise_for_status()
                image_bytes = response.content
                filename = os.path.basename(cover_path)

                return await self.img_host(image_bytes, filename)
            except Exception as e:
                print(f"Falha ao processar pôster da URL {cover_tmdb_url}: {e}")
                return None

    async def get_screenshots(self, meta):
        screenshot_dir = Path(meta["base_dir"]) / "tmp" / meta["uuid"]
        local_files = sorted(screenshot_dir.glob("*.png"))
        results = []

        # Use existing files
        if local_files:
            async def upload_local_file(path):
                with open(path, "rb") as f:
                    image_bytes = f.read()
                return await self.img_host(image_bytes, os.path.basename(path))

            paths = local_files[:6]

            for coro in tqdm(
                asyncio.as_completed([upload_local_file(p) for p in paths]),
                total=len(paths),
                desc=f"Enviando {len(local_files)} screenshots para o host do {self.tracker}",
            ):
                result = await coro
                if result:
                    results.append(result)

        else:
            image_links = [
                img.get("raw_url")
                for img in meta.get("image_list", [])
                if img.get("raw_url")
            ][:6]

            if len(image_links) < 2:
                raise UploadException(
                    f"[bold red]FALHA NO UPLOAD:[/bold red] É necessário pelo menos 2 screenshots para fazer upload para o {self.tracker}."
                )

            async def upload_remote_file(url):
                try:
                    response = await self.session.get(url, timeout=120)
                    response.raise_for_status()
                    image_bytes = response.content
                    filename = os.path.basename(urlparse(url).path) or "screenshot.png"
                    return await self.img_host(image_bytes, filename)
                except Exception as e:
                    print(f"Falha ao processar screenshot da URL {url}: {e}")
                    return None

            for coro in tqdm(
                asyncio.as_completed([upload_remote_file(url) for url in image_links]),
                total=len(image_links),
                desc=f"Enviando {len(image_links)} screenshots para o host do {self.tracker}",
            ):
                result = await coro
                if result:
                    results.append(result)

        if len(results) < 2:
            raise UploadException(
                f"[bold red]FALHA NO UPLOAD:[/bold red] O host de imagem do {self.tracker} não retornou o número mínimo de screenshots."
            )

        return results

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

        if meta['is_disc'] != "BDMV":
            for track in meta['mediainfo']['media']['track']:
                if track['@type'] == "Video":
                    dar_str = track.get('DisplayAspectRatio', '')
                    if dar_str:
                        try:
                            dar = float(dar_str)
                            if dar > 2.0:
                                found_tags.add('Ultrawide')
                        except ValueError:
                            pass

        return found_tags

    def build_remaster_title(self, meta):
        tag_priority = [
            'Ultrawide',
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

    def get_credits(self, meta, role):
        role_map = {
            'director': ('directors', 'tmdb_directors'),
            'creator': ('creators', 'tmdb_creators'),
            'cast': ('stars', 'tmdb_cast'),
        }

        prompt_name_map = {
            'director': 'Diretor(es)',
            'creator': 'Criador(es)',
            'cast': 'Elenco',
        }

        if role in role_map:
            imdb_key, tmdb_key = role_map[role]

            names = (meta.get('imdb_info', {}).get(imdb_key) or []) + (meta.get(tmdb_key) or [])

            unique_names = list(dict.fromkeys(names))[:5]
            if unique_names:
                return ", ".join(unique_names)

            else:
                if not self.cover:  # Only ask for input if there's no info in the site already
                    role_display_name = prompt_name_map.get(role, role.capitalize())
                    prompt_message = (f"{role_display_name} não encontrado(s).\nPor favor, insira manualmente (separados por vírgula): ")
                    user_input = input(prompt_message)

                    if user_input.strip():
                        return user_input.strip()
                    else:
                        raise UploadException(f"Dados obrigatórios não fornecidos: {role_display_name}")
                else:
                    return "N/A"

    async def gather_data(self, meta, disctype):
        await self.validate_credentials(meta)
        tmdb_data = await self.ptbr_tmdb_data(meta)
        category = meta['category']

        data = {}

        # These fields are common across all upload types
        data.update({
            'audio': await self.get_audio(meta),
            'auth': self.auth_token,
            'codecaudio': self.get_audio_codec(meta),
            'codecvideo': self.get_video_codec(meta),
            'duracaoHR': self.get_runtime(meta).get('hours'),
            'duracaoMIN': self.get_runtime(meta).get('minutes'),
            'duracaotipo': 'selectbox',
            'fichatecnica': await self.build_description(meta),
            'formato': self.get_container(meta),
            'idioma': await self.get_languages(meta),
            'imdblink': meta['imdb_info']['imdbID'],
            'qualidade': self.get_bitrate(meta),
            'release': meta.get('service_longname', ''),
            'remaster_title': self.build_remaster_title(meta),
            'resolucaoh': self.get_resolution(meta).get('height'),
            'resolucaow': self.get_resolution(meta).get('width'),
            'sinopse': tmdb_data.get('overview') or await asyncio.to_thread(input, "Digite a sinopse: "),
            'submit': 'true',
            'tags': await self.get_tags(meta),
            'tipolegenda': await self.get_subtitle(meta),
            'title': meta['title'],
            'titulobrasileiro': await self.get_title(meta),
            'traileryoutube': await self.get_trailer(meta),
            'type': self.get_type(meta),
            'year': f"{meta['year']}-{meta['imdb_info']['end_year']}" if meta.get('imdb_info').get('end_year') else meta['year'],
            })

        # These fields are common in movies and TV shows, even if it's anime
        if category == 'MOVIE':
            data.update({
                'adulto': '2',
                'diretor': self.get_credits(meta, 'director'),
            })

        if category == 'TV':
            data.update({
                'diretor': self.get_credits(meta, 'creator'),
                'tipo': 'episode' if meta.get('tv_pack') == 0 else 'season',
                'season': meta.get('season_int', ''),
                'episode': meta.get('episode_int', ''),
            })

        # These fields are common in movies and TV shows, if not Anime
        if not meta.get('anime'):
            data.update({
                'validimdb': 'yes',
                'imdbrating': str(meta.get('imdb_info', {}).get('rating', '')),
                'elenco': self.get_credits(meta, 'cast'),
            })
            if category == 'MOVIE':
                data.update({
                    'datalancamento': self.get_release_date(tmdb_data),
                })

            if category == 'TV':
                # Convert country code to name
                country_list = [
                    country.name
                    for code in tmdb_data.get('origin_country', [])
                    if (country := pycountry.countries.get(alpha_2=code))
                ]
                data.update({
                    'network': ", ".join([p.get('name', '') for p in tmdb_data.get("networks", [])]) or "",  # Optional
                    'numtemporadas': tmdb_data.get("number_of_seasons", ''),  # Optional
                    'datalancamento': self.get_release_date(tmdb_data),
                    'pais': ", ".join(country_list),  # Optional
                    'diretorserie': ", ".join(set(meta.get('tmdb_directors', []) or meta.get('imdb_info', {}).get('directors', [])[:5])),  # Optional
                    'avaliacao': await self.get_rating(meta),  # Optional
                })

        # Anime-specific data
        if meta.get('anime'):
            if category == 'MOVIE':
                data.update({
                    'tipo': 'movie',
                })
            if category == 'TV':
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

        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            data.update({
                'internalrel': 1,
            })

        # Only upload images if not debugging
        if not meta.get('debug', False):
            data.update({
                'image': await self.get_cover(meta, disctype),
                'screenshots[]': await self.get_screenshots(meta),
            })

        return data

    async def upload(self, meta, disctype):
        data = await self.gather_data(meta, disctype)
        await self.edit_torrent(meta, self.tracker, self.source_flag)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            upload_url = f"{self.base_url}/upload.php"
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file_input': (f"{self.tracker}.placeholder.torrent", torrent_file, "application/x-bittorrent")}

                response = await self.session.post(upload_url, data=data, files=files, timeout=120)
                soup = BeautifulSoup(response.text, 'html.parser')

                if 'Clique em baixar para entrar de' in response.text:
                    page_element = soup.select_one('div#wrapper div#content p font')

                    # Find the torrent id
                    match = re.search(r'action=download&id=(\d+)', response.text)
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                else:
                    page_element = soup.select_one("div.thin p[style*='color: red']")

                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    console.print(f"Falha no upload, a resposta HTML foi salva em: {response_save_path}")
                    meta['tracker_status'][self.tracker]['skipped'] = True
                    meta['tracker_status'][self.tracker]['upload'] = False

                # Find the response text
                page_message = ""
                if page_element:
                    page_message = page_element.get_text(strip=True)
                    status_message = page_message

            await self.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message