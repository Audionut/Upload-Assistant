# -*- coding: utf-8 -*-
from datetime import datetime
import httpx
import langcodes
import os
import re
import requests
import unicodedata
from .COMMON import COMMON
from bs4 import BeautifulSoup
from http.cookiejar import MozillaCookieJar
from langcodes.tag_parser import LanguageTagError
from src.console import console
from src.languages import process_desc_language


class BJ(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "BJ"
        self.banned_groups = [""]
        self.source_flag = "BJ"
        self.base_url = "https://bj-share.info"
        self.auth_token = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

        self.payload_fields_map = {
            # Movies
            '0': [
                "submit", "auth", "type", "adulto", "imdblink", "validimdb",
                "title", "titulobrasileiro", "imdbrating", "tags", "year", "elenco", "diretor",
                "duracaotipo", "duracaoHR", "duracaoMIN", "datalancamento", "traileryoutube",
                "formato", "qualidade", "release", "audio", "tipolegenda", "codecvideo",
                "codecaudio", "idioma", "remaster_title", "resolucaow", "resolucaoh",
                "sinopse", "fichatecnica", "image", "screenshots",
            ],
            # TV
            '1': [
                "submit", "auth", "type", "validimdb", "imdbrating", "tipo", "season", "episode",
                "imdblink", "network", "title", "titulobrasileiro", "numtemporadas", "year",
                "datalancamento", "tags", "pais", "elenco", "diretorserie", "diretor", "duracaotipo",
                "duracaoHR", "duracaoMIN", "avaliacao", "traileryoutube", "formato", "qualidade",
                "release", "audio", "tipolegenda", "codecvideo", "codecaudio", "idioma", "remaster_title",
                "resolucaow", "resolucaoh", "sinopse", "fichatecnica", "image", "screenshots"
            ],
            # Animes
            '13': [
                "submit", "auth", "type", "imdblink", "adulto", "title", "titulobrasileiro",
                "tags", "tipo", "season", "episode", "release", "year", "diretor", "duracaotipo",
                "duracaoHR", "duracaoMIN", "traileryoutube", "formato", "qualidade", "audio",
                "tipolegenda", "codecvideo", "codecaudio", "idioma", "remaster_title", "resolucaow",
                "resolucaoh", "sinopse", "fichatecnica", "image", "screenshots",
            ]
        }



    def assign_media_properties(self, meta):
        self.imdb_id = meta['imdb_info']['imdbID']
        self.tmdb_id = meta['tmdb']
        self.category = meta['category']
        self.season = meta.get('season', '')
        self.episode = meta.get('episode', '')

    async def tmdb_data(self, meta):
        tmdb_api = self.config['DEFAULT']['tmdb_api']
        self.assign_media_properties(meta)

        url = f"https://api.themoviedb.org/3/{self.category.lower()}/{self.tmdb_id}?api_key={tmdb_api}&language=pt-BR&append_to_response=videos"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        except httpx.RequestError:
            return None

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
        tmdb_data = await self.tmdb_data(meta)
        lang_code = tmdb_data.get("original_language")

        # Pega a lista de países, garantindo que seja sempre uma lista
        origin_countries = tmdb_data.get("origin_country", [])

        # Se não houver código de idioma, não há o que fazer.
        if not lang_code:
            return "Outro"

        language_name = None

        # --- Lógica principal ---

        # 1. Tratamento especial para o código 'pt'
        if lang_code == 'pt':
            # Verifica se 'PT' (código de Portugal) está na lista de países
            if 'PT' in origin_countries:
                language_name = "Português (pt)"
            else:
                language_name = "Português"
        else:
            # 2. Caso geral para todos os outros idiomas
            try:
                # Tenta traduzir o código (ex: 'en') para o nome em português ('Inglês')
                language_name = langcodes.Language.make(lang_code).display_name('pt').capitalize()
            except LanguageTagError:
                # Se o código for inválido (ex: "xx"), não podemos traduzir.
                # A validação final irá transformar isso em "Outro".
                language_name = lang_code

        # 3. Validação final contra a lista de idiomas permitidos
        if language_name in possible_languages:
            return language_name
        else:
            return "Outro"

    async def search_existing(self, meta, disctype):
        """
        Busca por torrents existentes em uma página de detalhes.
        O código foi adaptado para a nova estrutura HTML.
        """
        self.assign_media_properties(meta)
        is_current_upload_a_tv_pack = meta.get('tv_pack') == 1

        # Assumimos que a URL de busca já leva para a página de detalhes do grupo
        search_url = f"{self.base_url}/torrents.php?searchstr={self.imdb_id}"

        found_items = []
        try:
            response = await self.session.get(search_url)  # Use 'await' se a sessão for aiohttp/httpx
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. MUDANÇA: Encontra a tabela principal pelo novo ID 'torrent_details'
            # O nome anterior era 'torrent_table'
            torrent_details_table = soup.find('table', id='torrent_details')
            if not torrent_details_table:
                return []

            # 2. MUDANÇA: A lógica de 'group_links' foi removida.
            # Iteramos diretamente sobre as linhas de torrent na página atual.

            # Encontra todas as linhas de torrent que correspondem ao padrão de ID
            for torrent_row in torrent_details_table.find_all('tr', id=re.compile(r'^torrent\d+$')):

                # MUDANÇA: O link da descrição agora usa 'loadIfNeeded' no onclick
                desc_link = torrent_row.find('a', onclick=re.compile(r"loadIfNeeded"))
                if not desc_link:
                    continue
                description_text = " ".join(desc_link.get_text(strip=True).split())

                # A extração do ID do torrent continua a mesma
                torrent_id = torrent_row.get('id', '').replace('torrent', '')
                if not torrent_id:
                    continue

                # 3. MUDANÇA CRÍTICA: A lista de arquivos está na PRÓXIMA tag <tr>
                # Usamos find_next_sibling() para encontrar a linha de detalhes correspondente
                details_row = torrent_row.find_next_sibling('tr', class_=re.compile(r'torrentdetails'))
                if not details_row:
                    continue

                # Agora procuramos a div de arquivos dentro desta nova linha encontrada
                file_div = details_row.find('div', id=f'files_{torrent_id}')
                if not file_div:
                    # Se a div não for encontrada (pode não ter sido carregada), pulamos para o próximo
                    continue

                # A lógica para identificar se é um disco permanece a mesma
                is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                # A lógica para extrair o nome do arquivo ou pasta permanece a mesma,
                # mas agora opera sobre o 'file_div' corretamente encontrado.
                if is_existing_torrent_a_disc or is_current_upload_a_tv_pack:
                    path_div = file_div.find('div', class_='filelist_path')
                    # Verifica se o path_div existe e tem texto
                    if path_div and path_div.get_text(strip=True):
                        folder_name = path_div.get_text(strip=True).strip('/')
                        if folder_name:
                            found_items.append(folder_name)
                    else:
                        # Fallback para discos: se não houver um path, pega o primeiro item da lista,
                        # que geralmente é a pasta principal do disco.
                        file_table = file_div.find('table', class_='filelist_table')
                        if file_table:
                            # Encontra a primeira linha que não seja o cabeçalho
                            first_file_row = file_table.find('tr', class_=lambda x: x != 'colhead_dark')
                            if first_file_row:
                                cell = first_file_row.find('td')
                                if cell:
                                    item_name = cell.get_text(strip=True)
                                    if item_name:
                                        found_items.append(item_name)
                else:  # Caso de ser um arquivo único (encode)
                    file_table = file_div.find('table', class_='filelist_table')
                    if file_table:
                        # Itera nas linhas para encontrar a primeira que não é cabeçalho
                        for row in file_table.find_all('tr'):
                            if 'colhead_dark' not in row.get('class', []):
                                cell = row.find('td')
                                if cell:
                                    filename = cell.get_text(strip=True)
                                    if filename:
                                        found_items.append(filename)
                                        break  # Encontrou o arquivo, pode parar e ir para o próximo torrent

        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Ocorreu um erro de rede ao buscar por duplicatas: {e}[/bold red]")
            return []
        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]")
            # Para depuração, é útil imprimir o rastreamento do erro
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
                with open(f"{self.tracker}_auth_failure_{meta['uuid']}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                console.print(f"[yellow]A resposta do servidor foi salva em '{self.tracker}_auth_failure_{meta['uuid']}.html' para análise.[/yellow]")
                return False

        except Exception as e:
            console.print(f"[bold red]Erro ao validar credenciais do {self.tracker}: {e}[/bold red]")
            return False

    def get_type(self, meta):
        self.assign_media_properties(meta)

        if meta.get('anime', False):
            return '13'

        if self.category == 'TV' or meta.get('season') is not None:
            return '1'

        if self.category == 'MOVIE':
            return '0'

        return '0'

    def get_file_info(self, meta):
        info_file_path = ""
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            try:
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                console.print(f"[bold red]Erro ao ler o arquivo de info em '{info_file_path}': {e}[/bold red]")
                return ""
        else:
            console.print(f"[bold red]Arquivo de info não encontrado: {info_file_path}[/bold red]")
            return ""

    def get_format(self, meta):
        if meta.get('is_disc') == "BDMV":
            return "M2TS"
        elif meta.get('is_disc') == "DVD":
            return "VOB"

        try:
            general_track = next(t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'General')
            file_extension = general_track.get('FileExtension', '').lower()
            if file_extension == 'mkv':
                return 'MKV'
            elif file_extension == 'mp4':
                return 'MP4'
            else:
                return "Outro"
        except (StopIteration, AttributeError, TypeError):
            return None

    # desnecessário?
    async def get_subtitles(self, meta):
        if not meta.get('subtitle_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('subtitle_languages', [])

        subtitle_ids = set()
        for lang_str in found_language_strings:
            target_id = self.ultimate_lang_map.get(lang_str.lower())
            if target_id:
                subtitle_ids.add(target_id)

        legenda_value = "Sim" if '49' in subtitle_ids else "Nao"

        final_subtitle_ids = sorted(list(subtitle_ids))
        if not final_subtitle_ids:
            final_subtitle_ids.append('44')

        return {
            'legenda': legenda_value,
            'subtitles[]': final_subtitle_ids
        }

    async def get_audio(self, meta):
        if not meta.get('audio_languages'):
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
                return "Dual Audio"
            else:
                return "Dublado"

        return "Legendado"

    def get_video_codec(self, meta):
        # 'meta': 'site'
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
                    size_in_gb = meta['torrent_comments'][0]['size'] / (10**9)
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

    def get_screens(self, meta):
        screenshot_urls = [
            image.get('raw_url')
            for image in meta.get('image_list', [])
            if image.get('raw_url')
        ]

        return screenshot_urls

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        base_desc = ""
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()

        description_parts = []

        description_parts.append(base_desc)

        if self.signature:
            description_parts.append(self.signature)

        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = "\n\n".join(filter(None, description_parts))
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
            try:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                video_track = next((t for t in tracks if t.get('@type') == 'Video'), None)
                if video_track:
                    width = video_track.get('Width', '')
                    height = video_track.get('Height', '')
            except (AttributeError, TypeError):
                pass

        return {
            'resolucaow': width,
            'resolucaoh': height
        }

    async def get_cast(self, meta):
        tmdb_data = await self.tmdb_data(meta)
        cast_data = (tmdb_data.get('credits') or {}).get('cast', [])

        return ", ".join(
            cast_member['name']
            for cast_member in cast_data
            if cast_member.get('name')
        )

    def get_runtime(self, runtime):
        try:
            minutes_in_total = int(runtime)
            if minutes_in_total < 0:
                return 0, 0
        except (ValueError, TypeError):
            return 0, 0

        hours, minutes = divmod(minutes_in_total, 60)
        return hours, minutes

    def get_formatted_date(self, tmdb_data):
        """
        Busca a data de lançamento ou primeira exibição e a formata.
        Formato de entrada: "YYYY-MM-DD"
        Formato de saída: "DD Mon YYYY" (ex: "08 Feb 2015")
        """
        raw_date_string = None

        # 1. Seleciona a chave correta baseada na categoria
        if self.category == 'TV':
            raw_date_string = tmdb_data.get('first_air_date')
        elif self.category == 'MOVIE':
            raw_date_string = tmdb_data.get('release_date')

        # 2. Valida se a data foi encontrada antes de continuar
        if not raw_date_string:
            return ""  # Retorna string vazia se a data for nula ou vazia

        try:
            # 3. Converte a string da API em um objeto de data do Python
            # "%Y" = Ano com 4 dígitos (2015)
            # "%m" = Mês em número (02)
            # "%d" = Dia (08)
            date_object = datetime.strptime(raw_date_string, "%Y-%m-%d")

            # 4. Formata o objeto de data para a string no formato desejado
            # "%d" = Dia (08)
            # "%b" = Mês abreviado em inglês (Feb)
            # "%Y" = Ano com 4 dígitos (2015)
            formatted_date = date_object.strftime("%d %b %Y")

            return formatted_date

        except ValueError:
            # 5. Se a data na API estiver em um formato inesperado, retorna vazio
            return ""

    async def get_trailer(self, meta):
        tmdb_data = await self.tmdb_data(meta)
        video_results = tmdb_data.get('videos', {}).get('results', [])
        youtube_code = video_results[-1].get('key', '') if video_results else ''
        if youtube_code:
            youtube = f"http://www.youtube.com/watch?v={youtube_code}"

        return youtube if youtube else meta.get('youtube', '')

    def _find_remaster_tags(self, meta):
        """
        Função auxiliar para encontrar todas as tags aplicáveis no metadado.
        Retorna um conjunto ('set') de tags encontradas.
        """
        found_tags = set()

        # 1. Edições (usando sua função existente)
        edition = self.get_edition(meta)
        if edition:
            found_tags.add(edition)

        # 2. Recursos de Áudio (Dolby Atmos)
        audio_string = meta.get('audio', '')
        if 'Atmos' in audio_string:
            found_tags.add('Dolby Atmos')

        # 3. Recursos 4K (10-bit, Dolby Vision, HDR)
        # 10-bit
        is_10_bit = False
        if meta.get('is_disc') == 'BDMV':
            try:
                # Acessa o dicionário de forma segura
                bit_depth_str = meta['discs'][0]['bdinfo']['video'][0]['bit_depth']
                if '10' in bit_depth_str:
                    is_10_bit = True
            except (KeyError, IndexError, TypeError):
                pass  # Ignora se a estrutura de dados não existir
        else:
            if str(meta.get('bit_depth')) == '10':
                is_10_bit = True

        if is_10_bit:
            found_tags.add('10-bit')

        # HDR (Dolby Vision, HDR10, HDR10+)
        hdr_string = meta.get('hdr', '').upper()  # Usa upper() para ser mais robusto
        if 'DV' in hdr_string:
            found_tags.add('Dolby Vision')
        if 'HDR10+' in hdr_string:
            found_tags.add('HDR10+')
        if 'HDR' in hdr_string and 'HDR10+' not in hdr_string:
            found_tags.add('HDR10')

        # 4. Demais Recursos (Remux, Comentários)
        if meta.get('type') == 'REMUX':
            found_tags.add('Remux')
        if meta.get('has_commentary') is True:
            found_tags.add('Com comentários')

        return found_tags

    def build_remaster_title(self, meta):
        """
        Constrói a string do remaster_title com base nas tags encontradas,
        respeitando a ordem de prioridade definida na classe.
        """
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
            'Com comentários'
        ]
        # Passo 1: Encontra todas as tags disponíveis no metadado.
        available_tags = self._find_remaster_tags(meta)

        # Passo 2: Filtra e ordena as tags encontradas de acordo com a lista de prioridade.
        ordered_tags = []
        for tag in tag_priority:
            if tag in available_tags:
                ordered_tags.append(tag)

        # Passo 3: Junta as tags ordenadas com " / " como separador.
        return " / ".join(ordered_tags)

    async def upload(self, meta, disctype):
        tmdb_data = await self.tmdb_data(meta)

        runtime_value = meta.get('runtime')
        hours, minutes = self.get_runtime(runtime_value)

        if not await self.validate_credentials(meta):
            console.print(f"[bold red]Upload para {self.tracker} abortado.[/bold red]")
            return

        await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)

        category_type = self.get_type(meta)

        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        if meta.get('type') == 'WEBDL' and meta.get('service_longname', ''):
            release = meta.get('service_longname', '')

        all_possible_data = {}

        all_possible_data.update({
            'submit': 'true',
            'auth': self.auth_token,
            'type': category_type,
            'imdblink': meta.get('imdb_info', {}).get('imdbID', ''),
            'validimdb': 'yes' if meta.get('imdb_info', {}).get('imdbID') else 'no',
            'adulto': '0'
        })

        all_possible_data.update({
            'title': meta['title'],
            'titulobrasileiro': tmdb_data.get('name') or tmdb_data.get('title') or '',
            'imdbrating': str(meta.get('imdb_info', {}).get('rating', '')),
            'tags': ', '.join(unicodedata.normalize('NFKD', g['name']).encode('ASCII', 'ignore').decode('utf-8').replace(' ', '.').lower() for g in tmdb_data.get('genres', [])),
            'year': str(meta['year']),
            'elenco': await self.get_cast(meta),
            'diretor': ", ".join(set(meta.get('tmdb_directors', []))),
            'duracaotipo': 'selectbox',
            'duracaoHR': hours,
            'duracaoMIN': minutes,
            'datalancamento': self.get_formatted_date(tmdb_data),
            'traileryoutube': await self.get_trailer(meta),
            'formato': self.get_format(meta),
            'qualidade': self.get_bitrate(meta),
            'release': release,
            'audio': await self.get_audio(meta),
            # 'tipolegenda': ,
            'codecvideo': self.get_video_codec(meta),
            'codecaudio': self.get_audio_codec(meta),
            'idioma': await self.get_original_language(meta),
            'remaster_title': self.build_remaster_title(meta),
            'resolucaow': self.get_resolution(meta).get('resolucaow', ''),
            'resolucaoh': self.get_resolution(meta).get('resolucaoh', ''),
            'sinopse': tmdb_data.get('overview', 'Nenhuma sinopse disponível.'),
            'fichatecnica': self.get_file_info(meta),


            'image': f"https://image.tmdb.org/t/p/w500{tmdb_data.get('poster_path', '')}",
        })

        bt_desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', newline='', encoding='utf-8').read()
        subtitles_info = await self.get_subtitles(meta)

        all_possible_data.update({
            'mediainfo': self.get_file_info(meta),
            'format': self.get_format(meta),
            'audio': await self.get_audio(meta),
            'video_c': self.get_video_codec(meta),
            'audio_c': self.get_audio_codec(meta),
            'legenda': subtitles_info.get('legenda', 'Nao'),
            'subtitles[]': subtitles_info.get('subtitles[]'),
            '3d': 'Sim' if meta.get('3d') else 'Nao',
            'resolucao_1': resolution['resolucao_1'],
            'resolucao_2': resolution['resolucao_2'],
            'bitrate': self.get_bitrate(meta),
            'screen[]': self.get_screens(meta),
            'desc': '',
            'especificas': bt_desc
        })

        # Movies
        all_possible_data['versao'] = self.get_edition(meta)

        # TV/Anime
        all_possible_data.update({
            'ntorrent': f"{self.season}{self.episode}",
            'tipo': 'ep_individual' if meta.get('tv_pack') == 0 else 'completa',
            'temporada': self.season if meta.get('tv_pack') == 1 else '',
            'temporada_e': self.season if meta.get('tv_pack') == 0 else '',
            'episodio': self.episode
        })

        # Anime specific data
        duracao_min = 0
        try:
            duracao_apenas_numeros = re.search(r'\d+', all_possible_data.get('duracao', '0'))
            if duracao_apenas_numeros:
                duracao_min = int(duracao_apenas_numeros.group(0))
        except (ValueError, TypeError):
            pass

        all_possible_data.update({
            'releasedate': str(all_possible_data.get('year', '')),
            'rating': str(all_possible_data.get('nota_imdb', '')),
            'horas': str(duracao_min // 60),
            'minutos': str(duracao_min % 60),
            'fundo_torrent': meta.get('backdrop'),
        })

        required_fields = self.payload_fields_map.get(category_type)
        if not required_fields:
            console.print(f"[bold red]Erro: Modelo de payload não encontrado para a categoria '{category_type}'. Upload abortado.[/bold red]")
            return

        final_data = {}
        for field in required_fields:
            if field in all_possible_data:
                final_data[field] = all_possible_data[field]

        if anon == 1:
            final_data['anonymous'] = '1'

        if meta.get('debug', False):
            console.print(final_data)
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not os.path.exists(torrent_path):
            return

        upload_url = f"{self.base_url}/upload.php"
        with open(torrent_path, 'rb') as torrent_file:
            files = {'file_input': (f"{self.tracker}.placeholder.torrent", torrent_file, "application/x-bittorrent")}

            try:
                response = self.session.post(upload_url, data=final_data, files=files, timeout=60)

                if response.status_code == 200 and 'torrents.php?id=' in str(response.url):
                    final_url = str(response.url)
                    meta['tracker_status'][self.tracker]['status_message'] = final_url
                    id_match = re.search(r'id=(\d+)', final_url)
                    if id_match:
                        torrent_id = id_match.group(1)
                        details_url = f"{self.base_url}/torrents.php?id={torrent_id}"
                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                    else:
                        console.print(f"[bold yellow]Redirecionamento para a página do torrent ocorreu, mas não foi possível extrair o ID da URL: {final_url}[/bold yellow]")
                else:
                    console.print(f"[bold red]Falha no upload para {self.tracker}. Status: {response.status_code}, URL: {response.url}[/bold red]")
                    failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(failure_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    console.print(f"[yellow]A resposta HTML foi salva em '{failure_path}' para análise.[/yellow]")

            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Erro de conexão ao fazer upload para {self.tracker}: {e}[/bold red]")
