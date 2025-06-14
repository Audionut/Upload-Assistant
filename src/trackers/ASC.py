# -*- coding: utf-8 -*-
import os
import requests
import cli_ui
from datetime import datetime
from src.exceptions import UploadException
from bs4 import BeautifulSoup
from src.console import console
from .COMMON import COMMON
from pymediainfo import MediaInfo


class ASC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'ASC'
        self.source_flag = 'ASC'
        self.banned_groups = [""]
        self.base_url = "https://cliente.amigos-share.club"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Upload automatizado via Audionut's Upload Assistant[/url][/center]"

    def _get_torrent_name(self, meta):
        nome_original = meta.get('title')
        nome_em_portugues = None
        try:
            for aka in meta.get('imdb_info', {}).get('akas', []):
                if aka.get('country') == 'Brazil':
                    nome_em_portugues = aka.get('title')
                    break
        except (TypeError, AttributeError):
            nome_em_portugues = None

        nome_base = nome_original
        if nome_em_portugues and nome_em_portugues.lower() != nome_original.lower():
            nome_base = f"{nome_em_portugues} ({nome_original})"

        if meta.get('category') == 'TV':
            season_episode_str = ""
            if meta.get('tv_pack') == 1 and meta.get('season'):
                season_episode_str = f" - {meta.get('season')}"
            elif meta.get('tv_pack') == 0 and meta.get('season') and meta.get('episode'):
                season_episode_str = f" - {meta.get('season')}{meta.get('episode')}"
            return f"{nome_base}{season_episode_str}"
        return nome_base

    def _get_category_type(self, meta):
        if meta.get('anime'):
            if meta.get('category') == 'MOVIE':
                return '116'  # Categoria Anime (Filme)
            elif meta.get('category') == 'TV':
                return '118'  # Categoria Anime (Série)
        return None  # Retorna None se não for uma categoria de anime específica

    def _determine_subtitle_option(self, meta):
        subtitle_languages = []
        pt_variants = ["pt", "portuguese", "português", "pt-br"]

        if meta.get('is_disc') == 'BDMV':
            try:
                bdinfo_subs = meta.get('bdinfo', {}).get('subtitles', [])
                for sub in bdinfo_subs:
                    lang = sub.get('language', '') if isinstance(sub, dict) else sub
                    subtitle_languages.append(lang.lower())
            except Exception:
                console.print("[bold yellow]Aviso: Falha ao ler dados de legenda do BDInfo.[/bold yellow]")
        else:
            try:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                for track in tracks:
                    if track.get('@type') == 'Text':
                        subtitle_languages.append(track.get('Language', '').lower())
            except (AttributeError, TypeError):
                console.print("[bold yellow]Aviso: Falha ao ler dados de legenda do MediaInfo.[/bold yellow]")

        if any(any(variant in lang for variant in pt_variants) for lang in subtitle_languages):
            return '1'  # Legenda Embutida

        console.print("[cyan]Nenhuma legenda embutida em Português foi detectada.[/cyan]")
        if cli_ui.ask_yes_no("Este upload inclui um arquivo de legenda SEPARADO (.srt, .sub) em Português?", default=False):
            console.print("[green]Opção 'Legenda Separada' selecionada pelo usuário.[/green]")
            return '2'  # Legenda Separada

        console.print("[green]Opção 'Sem Legenda' selecionada.[/green]")
        return '0'  # Sem Legenda

    def _get_resolution(self, meta):
        if meta.get('is_disc') == 'BDMV':
            res_map = {'2160p': ('3840', '2160'), '1080p': ('1920', '1080'), '1080i': ('1920', '1080'), '720p': ('1280', '720')}
            return res_map.get(meta.get('resolution'))

        video_track = next((t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'Video'), None)
        if video_track:
            return video_track.get('Width'), video_track.get('Height')
        return None, None

    def _determine_quality(self, meta):
        qualidade_map_disc = {"BD25": "40", "BD50": "41", "BD66": "42", "BD100": "43"}
        qualidade_map_files = {"ENCODE": "9", "REMUX": "39", "WEBDL": "23", "WEBRIP": "38", "BDRIP": "8", "DVDR": "10"}

        if meta.get('type') == 'DISC':
            disctype = meta.get('disctype')
            if disctype in qualidade_map_disc:
                return qualidade_map_disc[disctype]

            console.print("[bold yellow]Aviso: Não foi encontrado o tipo de disco.[/bold yellow]")
            if cli_ui.ask_yes_no("Deseja definir o tipo de disco pelo tamanho do arquivo?", default=True):
                size = meta.get('torrent_comments', [{}])[0].get('size', 0)
                if size > 66_000_000_000:
                    return "43"  # BD100
                elif size > 50_000_000_000:
                    return "42"  # BD66
                elif size > 25_000_000_000:
                    return "41"  # BD50
                return "40"  # BD25
            else:
                raise UploadException(f"Upload para o '{self.tracker}' cancelado pelo usuário.", 'yellow')
        else:
            return qualidade_map_files.get(meta.get('type'), "0")

    def _determine_audio_type(self, meta):
        audio_tracks_raw = []
        pt_variants = ["pt", "portuguese", "português", "pt-br"]

        if meta.get('is_disc') == 'BDMV' and meta.get('bdinfo', {}).get('audio'):
            audio_tracks_raw = meta['bdinfo']['audio']
        elif meta.get('mediainfo'):
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            audio_tracks_raw = [{'language': t.get('Language')} for t in tracks if t.get('@type') == 'Audio']

        has_pt = any(any(v in track.get('language', '').lower() for v in pt_variants) for track in audio_tracks_raw)
        other_langs_count = sum(1 for t in audio_tracks_raw if not any(v in t.get('language', '').lower() for v in pt_variants))
        is_original_pt = any(v in meta.get('original_language', '').lower() for v in pt_variants)

        if has_pt:
            if is_original_pt:
                return "4"  # Nacional
            elif other_langs_count > 0:
                return "2"  # Dual-Audio
            return "3"  # Dublado
        return "1"  # Legendado

    def _get_file_extension(self, meta):
        if meta.get('is_disc') == "BDMV":
            return "5"

        try:
            general_track = next(t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'General')
            file_extension = general_track.get('FileExtension', '').lower()
            if file_extension == 'mkv':
                return '6'
            elif file_extension == 'mp4':
                return '8'
        except (StopIteration, AttributeError, TypeError):
            return None
        return None

    def _get_audio_codec(self, meta):
        cn = meta.get('clean_name', '').upper()
        if "ATMOS" in cn:
            return "43"
        elif "DTS:X" in cn:
            return "25"
        elif "DTS-HD MA" in cn:
            return "24"
        elif "DTS-HD" in cn:
            return "23"
        elif "TRUEHD" in cn:
            return "29"
        elif "DD+" in cn:
            return "26"
        elif "AC-3" in cn or ("DD" in cn and "+" not in cn):
            return "11"
        elif "DTS" in cn:
            return "12"
        elif "FLAC" in cn:
            return "13"
        elif "LPCM" in cn:
            return "21"
        elif "PCM" in cn:
            return "28"
        elif "AAC" in cn:
            return "10"
        elif "OPUS" in cn:
            return "27"
        elif "MPEG" in cn:
            return "17"
        return None

    def _get_video_codec(self, meta):
        codec_video_map = {
            "MPEG-4": "31", "AV1": "29", "AVC": "30", "DivX": "9",
            "H264": "17", "H265": "18", "HEVC": "27", "M4V": "20",
            "MPEG-1": "10", "MPEG-2": "11", "RMVB": "12", "VC-1": "21",
            "VP6": "22", "VP9": "23", "WMV": "13", "XviD": "15"
        }

        codec_video = None
        video_encode_raw = meta.get('video_encode')

        if video_encode_raw and isinstance(video_encode_raw, str):
            video_encode_clean = video_encode_raw.strip().lower()
            if '264' in video_encode_clean:
                codec_video = 'H264'
            elif '265' in video_encode_clean:
                codec_video = 'HEVC'

        if not codec_video:
            codec_video = meta.get('video_codec')

        codec_id = codec_video_map.get(codec_video, "16")

        is_hdr = bool(meta.get('hdr'))

        if is_hdr:
            if codec_video in ("HEVC", "H265"):
                return "28"
            if codec_video in ("AVC", "H264"):
                return "32"

        return codec_id

    async def _generate_description(self, meta):
        if not meta.get('imdb_id'):
            return await self._generate_description_manual(meta)

        url_gerador_desc = f"{self.base_url}/search.php"
        payload = {
            'imdb': f"tt{str(meta.get('imdb_id')).zfill(7)}",
            'layout': '2'
        }

        try:
            cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
            if os.path.exists(cookie_file):
                self.session.cookies.update(await self.parseCookieFile(cookie_file))

            response = self.session.post(url_gerador_desc, data=payload, timeout=20)
            response.raise_for_status()

            json_data = response.json()

            auto_description = self._build_description_from_json(json_data)

            if not auto_description:
                raise ValueError("Não foi possível construir a descrição automática.")

            final_description = f"{auto_description}\n\n{self.signature}"
            return final_description.strip()

        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro no processo de descrição automática: {e}[/bold red]")
            console.print("[yellow]Usando o método de descrição manual como fallback.[/yellow]")
            return await self._generate_description_manual(meta)

    def _build_description_from_json(self, json_data):
        asc_data = json_data.get('ASC')
        if not asc_data:
            return None

        barrinhas = {key: value for key, value in asc_data.items() if key.startswith('BARRINHA_')}

        titulo = asc_data.get('Title', 'Título não disponível')
        poster_path = asc_data.get('poster_path', '')
        sinopse = asc_data.get('overview', 'Sinopse não disponível.')

        duracao = asc_data.get('Runtime', 'N/A')
        produtora = asc_data.get('Production', 'N/A')
        pais = asc_data.get('Country', 'N/A')
        generos = asc_data.get('Genre', 'N/A')
        data_lancamento_str = asc_data.get('Released', '')

        try:
            data_lancamento_formatada = datetime.strptime(data_lancamento_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            data_lancamento_formatada = 'N/A'

        elenco_lista = asc_data.get('cast', [])

        imdb_id = asc_data.get('imdbID', '')
        ratings_lista = asc_data.get('Ratings', [])
        ratings = {rating.get('Source'): rating.get('Value') for rating in ratings_lista}

        imdb_rating = ratings.get('Internet Movie Database', 'N/A')
        rotten_rating = ratings.get('Rotten Tomatoes', 'N/A')
        metacritic_rating = ratings.get('Metacritic', 'N/A')

        description = "[center]\n"

        if barrinhas.get('BARRINHA_APRESENTA'):
            description += f"[img]{barrinhas['BARRINHA_APRESENTA']}[/img]\n"
            description += f"[size=3]{titulo}[/size]\n\n"

        if barrinhas.get('BARRINHA_CAPA') and poster_path:
            description += f"[img]{barrinhas['BARRINHA_CAPA']}[/img]\n"
            description += f"[img]{poster_path}[/img]\n\n"

        if barrinhas.get('BARRINHA_SINOPSE') and sinopse:
            description += f"[img]{barrinhas['BARRINHA_SINOPSE']}[/img]\n"
            description += f"{sinopse}\n\n"

        if barrinhas.get('BARRINHA_FICHA_TECNICA'):
            description += f"[img]{barrinhas['BARRINHA_FICHA_TECNICA']}[/img]\n"
            description += f"Tempo: {duracao}\n"
            description += f"Produtora: {produtora}\n"
            description += f"País de Origem: {pais}\n"
            description += f"Gêneros: {generos}\n"
            description += f"Data de Lançamento: {data_lancamento_formatada}\n\n"

        if barrinhas.get('BARRINHA_ELENCO') and elenco_lista:
            description += f"[img]{barrinhas['BARRINHA_ELENCO']}[/img]\n"
            for ator in elenco_lista[:5]:
                ator_id = ator.get('id')
                profile_path = ator.get('profile_path')
                nome = ator.get('name')
                personagem = ator.get('character')

                if all([ator_id, profile_path, nome, personagem]):
                    tmdb_url = f"https://www.themoviedb.org/person/{ator_id}?language=pt-BR"
                    foto_url = f"https://image.tmdb.org/t/p/w45{profile_path}"

                    description += f"[url={tmdb_url}][img]{foto_url}[/img][/url]\n"
                    description += f"[size=2][b]({nome}) como {personagem}[/b][/size]\n\n"

        if barrinhas.get('BARRINHA_INFORMACOES'):
            description += f"[img]{barrinhas['BARRINHA_INFORMACOES']}[/img]\n"
            imdb_icon = "https://i.postimg.cc/Pr8Gv4RQ/IMDB.png"
            rotten_icon = "https://i.postimg.cc/rppL76qC/rotten.png"
            metacritic_icon = "https://i.postimg.cc/SKkH5pNg/Metacritic45x45.png"

            if imdb_id and imdb_rating != 'N/A':
                imdb_page_url = f"https://www.imdb.com/title/{imdb_id}"
                description += f"[img]{imdb_icon}[/img]\n[url={imdb_page_url}][b]{imdb_rating}[/b][/url]\n"

            if rotten_rating != 'N/A':
                description += f"[img]{rotten_icon}[/img]\n[b]{rotten_rating}[/b]\n"

            if metacritic_rating != 'N/A':
                description += f"[img]{metacritic_icon}[/img]\n[b]{metacritic_rating}[/b]\n"

        description += "[/center]"

        return description

    async def _generate_description_manual(self, meta):
        description = ""
        mi_path = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
        mi_clean_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"

        if meta.get('is_disc') != 'BDMV':
            media_info_text = ""
            if os.path.exists(mi_path):
                try:
                    media_info_text = MediaInfo.parse(meta['filelist'][0], output="STRING", full=False, mediainfo_options={"inform": f"file://{mi_path}"})
                except Exception as e:
                    console.print(f"[bold red]Ocorreu um erro ao processar o template do MediaInfo: {e}[/bold red]")

            if not media_info_text and os.path.exists(mi_clean_path):
                with open(mi_clean_path, 'r', encoding='utf-8') as f:
                    media_info_text = f.read()

            if media_info_text:
                description += f"[left][font=consolas]\n{media_info_text}\n[/font][/left]\n\n"
        else:
            bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary_file):
                with open(bd_summary_file, 'r', encoding='utf-8') as f:
                    bd_summary = f.read()
                description += f"[left][font=consolas]\n{bd_summary}\n[/font][/left]\n\n"

        description += self.signature
        return description.strip()

    async def _prepare_form_data(self, meta):
        try:
            data = {'takeupload': 'yes', 'tresd': 2, 'layout': 2}

            asc_data = None
            if meta.get('imdb_id'):
                url_gerador_desc = f"{self.base_url}/search.php"
                payload = {'imdb': f"tt{str(meta.get('imdb_id')).zfill(7)}", 'layout': '2'}
                try:
                    cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
                    self.session.cookies.update(await self.parseCookieFile(cookie_file))
                    response = self.session.post(url_gerador_desc, data=payload, timeout=20)
                    response.raise_for_status()
                    asc_data = response.json().get('ASC')
                except Exception:
                    asc_data = None

            if asc_data:
                description = self._build_description_from_json({'ASC': asc_data})
                data['descr'] = f"{description}\n\n{self.signature}".strip()

                if asc_data.get('poster_path'):
                    data['capa'] = asc_data.get('poster_path')

            else:
                data['descr'] = await self._generate_description_manual(meta)
                if meta.get('poster'):
                    data['capa'] = meta.get('poster')

            data['name'] = self._get_torrent_name(meta)
            data['descr'] = await self._generate_description(meta)
            data['type'] = self._get_category_type(meta)
            data['legenda'] = self._determine_subtitle_option(meta)
            data['qualidade'] = self._determine_quality(meta)
            data['audio'] = self._determine_audio_type(meta)
            data['extencao'] = self._get_file_extension(meta)
            data['codecaudio'] = self._get_audio_codec(meta)
            data['codecvideo'] = self._get_video_codec(meta)

            if meta.get('imdb_id'):
                data['imdb'] = f"tt{str(meta.get('imdb_id')).zfill(7)}"
            if meta.get('genres'):
                data['genre'] = meta.get('genres')
            if meta.get('year'):
                data['ano'] = meta.get('year')
            if meta.get('youtube'):
                data['tube'] = meta.get('youtube')

            largura, altura = self._get_resolution(meta)
            if largura:
                data['largura'] = largura
            if altura:
                data['altura'] = altura

            lang_map = {"en": "1", "fr": "2", "de": "3", "it": "4", "ja": "5", "es": "6", "ru": "7", "pt": "8", "zh": "10", "da": "12", "sv": "13", "fi": "14", "bg": "15", "no": "16", "nl": "17", "pl": "19", "ko": "20", "th": "21", "hi": "23", "tr": "25"}
            data['lang'] = lang_map.get(meta.get('original_language', '').lower(), "11")

            if meta.get('anime'):
                idioma_map = {"de": "3", "zh": "9", "ko": "11", "es": "1", "en": "4", "ja": "8", "pt": "5", "ru": "2"}
                data['idioma'] = idioma_map.get(meta.get('original_language', '').lower(), "6")

            for i, img in enumerate(meta.get('image_list', [])[:4]):
                data[f'screens{i+1}'] = img.get('raw_url')

            return data
        except Exception as e:
            console.print(f"[bold red]A preparação dos dados para o upload falhou: {e}[/bold red]")
            raise

    async def upload(self, meta, disctype):
        if not await self._check_and_handle_anonymous_upload(meta):
            return

        await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)

        data = await self._prepare_form_data(meta)
        if data is None:
            raise UploadException("Falha ao preparar os dados do formulário.", 'red')

        if meta.get('debug', False):
            console.print("[yellow]MODO DEBUG ATIVADO. Upload não será realizado.[/yellow]")
            console.print("[cyan]Dados do formulário:[/cyan]", data)
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not os.path.exists(torrent_path):
            console.print(f"[bold red]CRÍTICO: Arquivo torrent não encontrado: {torrent_path}[/bold red]")
            return

        upload_url = self._get_upload_url(meta)
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
        self.session.cookies.update(await self.parseCookieFile(cookie_file))

        with open(torrent_path, 'rb') as torrent_file:
            files = {'torrent': (f"{data['name']}.torrent", torrent_file, "application/x-bittorrent")}
            response = self.session.post(upload_url, data=data, files=files, timeout=60)

        if "foi enviado com sucesso" in response.text:
            await self._handle_successful_upload(response.text, meta)
        else:
            self._handle_failed_upload(response, meta)

    async def _check_and_handle_anonymous_upload(self, meta):
        if meta.get('anon'):
            console.print(f"[bold yellow]Aviso: Você solicitou um upload anônimo, mas o tracker '{self.tracker}' não suporta esta opção.[/bold yellow]")

            should_continue = cli_ui.ask_yes_no(
                "Deseja continuar com o upload de forma pública (não-anônima)?",
                default=False
            )

            if not should_continue:
                console.print(f"[red]Upload para o tracker '{self.tracker}' cancelado pelo usuário.[/red]")
                return False

        return True

    def _get_upload_url(self, meta):
        if meta.get('anime'):
            return f"{self.base_url}/enviar-anime.php"
        elif meta.get('category') == 'MOVIE':
            return f"{self.base_url}/enviar-filme.php"
        else:
            return f"{self.base_url}/enviar-series.php"

    async def _handle_successful_upload(self, response_text, meta):
        console.print("[bold green]Upload para o ASC realizado com sucesso![/bold green]")
        try:
            soup = BeautifulSoup(response_text, 'html.parser')
            details_link_tag = soup.find('a', href=lambda href: href and "torrents-details.php?id=" in href)
            if not details_link_tag:
                console.print("[bold yellow]Aviso: Não foi possível encontrar o link do torrent na página de sucesso.[/bold yellow]")
                return

            relative_url = details_link_tag['href']
            torrent_url = f"{self.base_url}/{relative_url}"
            announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')

            await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, torrent_url)

            should_approve, reason = await self._should_auto_approve(meta)
            if should_approve:
                await self._attempt_auto_approval(relative_url)
            else:
                console.print(f"[yellow]{reason}. A aprovação automática será ignorada.[/yellow]")

        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro no pós-processamento do upload: {e}[/bold red]")

    async def _attempt_auto_approval(self, relative_url):
        try:
            torrent_id = relative_url.split('id=')[-1]
            console.print(f"[cyan]Tentando realizar a aprovação automática para o torrent ID {torrent_id}...[/cyan]")
            approval_url = f"{self.base_url}/uploader_app.php?id={torrent_id}"
            approval_response = self.session.get(approval_url, timeout=30)
            approval_response.raise_for_status()
        except Exception as e:
            console.print(f"[bold red]Erro durante a tentativa de aprovação automática: {e}[/bold red]")

    def _handle_failed_upload(self, response, meta):
        response_save_path = f"{meta['base_dir']}/tmp/asc_upload_fail_{meta['uuid']}.html"
        with open(response_save_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        console.print("[bold red]Falha no upload para o ASC. A resposta do servidor não indicou sucesso.[/bold red]")
        console.print(f"[yellow]A resposta foi salva em: {response_save_path}[/yellow]")
        raise UploadException("Falha no upload para o ASC: resposta inesperada do servidor.", 'red')

    async def _perform_search_and_parse(self, search_url, meta):
        dupes = []
        console.print(f"[cyan]Buscando duplicados em:[/cyan] {search_url}")

        try:
            cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
            self.session.cookies.update(await self.parseCookieFile(cookie_file))
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            releases = soup.find_all('li', class_='list-group-item dark-gray')
        except Exception as e:
            console.print(f"[bold red]Falha ao acessar a página de busca do ASC: {e}[/bold red]")
            return dupes

        if not releases:
            return dupes

        console.print(f"[cyan]Encontrados {len(releases)} releases. Analisando...[/cyan]")

        for release in releases:
            try:
                badges = release.find_all('span', class_='badge')
                disc_types = ['BD25', 'BD50', 'BD66', 'BD100', 'ISO']
                is_disc = any(badge.text.strip().upper() in disc_types for badge in badges)

                if is_disc:
                    name, year, resolution, disk_type, video_codec, audio_codec = meta.get('title'), "N/A", "N/A", "Blu-ray", "N/A", "N/A"
                    video_codec_terms = ['H264', 'H265', 'HEVC', 'AVC', 'XVID', 'VC-1']
                    audio_codec_terms = ['DTS', 'AC3', 'DDP', 'E-AC-3', 'TRUEHD', 'ATMOS', 'LPCM', 'AAC', 'FLAC']

                    for badge in badges:
                        badge_text = badge.text.strip()
                        badge_text_upper = badge_text.upper()

                        if badge_text.isdigit() and len(badge_text) == 4:
                            year = badge_text
                        elif badge_text_upper in ['4K', '2160P', '1080P', '720P', 'BDRIP']:
                            resolution = "2160p" if badge_text_upper == '4K' else badge_text
                        elif any(term in badge_text_upper for term in video_codec_terms):
                            video_codec = badge_text
                        elif any(term in badge_text_upper for term in audio_codec_terms):
                            audio_codec = badge_text

                    dupe_string = f"{name} {year} {resolution} {disk_type} {video_codec} {audio_codec}"
                    dupes.append(dupe_string)
                else:
                    details_link_tag = release.find('a', href=lambda href: href and "torrents-details.php?id=" in href)
                    if not details_link_tag:
                        continue

                    torrent_id = details_link_tag['href'].split('id=')[-1]
                    file_page_url = f"https://cliente.amigos-share.club/torrents-arquivos.php?id={torrent_id}"
                    file_page_response = self.session.get(file_page_url, timeout=15)
                    file_page_response.raise_for_status()
                    file_page_soup = BeautifulSoup(file_page_response.text, 'html.parser')

                    file_li_tag = file_page_soup.find('li', class_='list-group-item')
                    if file_li_tag and file_li_tag.contents:
                        filename = file_li_tag.contents[0].strip()
                        dupes.append(filename)

            except Exception as e:
                console.print(f"[bold red]Falha ao processar um release da lista: {e}[/bold red]")
                continue
        return dupes

    async def search_existing(self, meta, disctype):
        search_url = None
        # Animes não possuem IMDb, a busca tem que ser feita por nome
        if meta.get('anime'):
            nome_base = meta.get('title')
            search_name = nome_base
            if meta.get('category') == 'TV':
                season_episode_str = ""
                if meta.get('tv_pack') == 1 and meta.get('season'):
                    season_episode_str = f" - {meta.get('season')}"
                elif meta.get('tv_pack') == 0 and meta.get('season') and meta.get('episode'):
                    season_episode_str = f" - {meta.get('season')}{meta.get('episode')}"
                search_name = f"{nome_base}{season_episode_str}"

            search_query = search_name.replace(' ', '+')
            search_url = f"https://cliente.amigos-share.club/torrents-search.php?search={search_query}&cat=0&free=2&sort=id&tipo=contenha&order=desc"

        # Lógica para Filmes/Séries (pelo IMDb)
        else:
            if not meta.get('imdb_id'):
                console.print("[yellow]IMDb ID não encontrado, não é possível buscar por duplicados no ASC.[/yellow]")
                return []
            imdb_id = f"tt{str(meta['imdb_id']).zfill(7)}"
            search_url = f"https://cliente.amigos-share.club/busca-filmes.php?search=&imdb={imdb_id}&sort=size&order=desc"

        return await self._perform_search_and_parse(search_url, meta)

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False

        common = COMMON(config=self.config)
        self.session.cookies.update(await common.parseCookieFile(cookie_file))

        try:
            test_url = f"{self.base_url}/gerador.php"

            response = self.session.get(test_url, timeout=10, allow_redirects=False)

            if response.status_code == 200 and 'gerador.php' in response.url:
                return True
            else:
                console.print(f"[bold red]Falha na validação das credenciais do {self.tracker}. O cookie pode estar expirado.[/bold red]")
                return False
        except Exception as e:
            console.print(f"[bold red]Erro ao validar credenciais do {self.tracker}: {e}[/bold red]")
            return False

    async def _should_auto_approve(self, meta):
        uploader_enabled = self.config['TRACKERS'][self.tracker].get('uploader_status', False)
        if not uploader_enabled:
            return False, f"A aprovação automática está desativada para o uploader no tracker {self.tracker}."

        send_to_mod_queue = meta.get('modq', False) or meta.get('mq', False)
        if send_to_mod_queue:
            return False, "A flag --modq ou --mq foi usada, enviando para a fila de moderação."

        return True, "Critérios de aprovação automática atendidos."
