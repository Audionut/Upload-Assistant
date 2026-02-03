# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import contextlib
import glob
import json
import os
import platform
import re
from typing import Any, Optional, cast

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup
from bs4.element import AttributeValueList
from unidecode import unidecode

from src.bbcode import BBCODE
from src.console import console
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class THR:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'THR'
        self.source_flag = '[https://www.torrenthr.org] TorrentHR.org'
        self.username = str(config['TRACKERS']['THR'].get('username', ''))
        self.password = str(config['TRACKERS']['THR'].get('password', ''))
        self.banned_groups = [""]

    async def upload(self, meta: Meta, _disctype: str, _torrent_bytes: Any = None) -> Optional[bool]:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_bytes=_torrent_bytes)
        cat_id = self.get_cat_id(meta)
        subs = self.get_subtitles(meta)
        await self.edit_desc(meta)
        thr_name = unidecode(str(meta.get('name', '')).replace('DD+', 'DDP'))

        # Confirm the correct naming order for THR
        cli_ui.info(f"THR name: {thr_name}")
        if not bool(meta.get('unattended', False)):
            thr_confirm = cli_ui.ask_yes_no("Correct?", default=False)
            if thr_confirm is not True:
                thr_name_manually = cli_ui.ask_string("Please enter a proper name", default="") or ""
                if thr_name_manually == "":
                    console.print('No proper name given')
                    console.print("Aborting...")
                    return
                else:
                    thr_name = thr_name_manually
        torrent_name = re.sub(r"[^0-9a-zA-Z. '\-\[\]]+", " ", thr_name)

        mi_file: bytes = b""

        if str(meta.get('is_disc', '')) == 'BDMV':
            mi_file = b""
            # bd_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8'
        else:
            mi_file_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt")
            async with aiofiles.open(mi_file_path, 'rb') as f:
                mi_file = await f.read()
            # bd_file = None

        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt",
            encoding='utf-8',
        ) as f:
            desc = await f.read()

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR].torrent")
        async with aiofiles.open(torrent_path, 'rb') as f:
            tfile = await f.read()

        # Upload Form
        url = 'https://www.torrenthr.org/takeupload.php'
        files: dict[str, tuple[str, Any]] = {
            'tfile': (f'{torrent_name}.torrent', tfile)
        }
        imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
        payload: dict[str, Any] = {
            'name': thr_name,
            'descr': desc,
            'type': cat_id,
            'url': f"{imdb_info.get('imdb_url', '')}/",
            'tube': str(meta.get('youtube', '')),
        }
        headers = {
            'User-Agent': f'Upload Assistant/2.3 ({platform.system()} {platform.release()})'
        }
        # If pronfo fails, put mediainfo into THR parser
        if str(meta.get('is_disc', '')) != 'BDMV':
            files['nfo'] = ("MEDIAINFO.txt", mi_file)
        if subs:
            payload['subs[]'] = tuple(subs)

        thr_upload_prompt = True if not bool(meta.get('debug')) else cli_ui.ask_yes_no("send to takeupload.php?", default=False)

        if thr_upload_prompt is True:
            await asyncio.sleep(0.5)
            response: Optional[httpx.Response] = None
            try:
                cookies = await self.login()

                if cookies:
                    console.print("[green]Using authenticated session for upload")

                    async with httpx.AsyncClient(cookies=cookies, follow_redirects=True) as session:
                        response = await session.post(url=url, files=files, data=payload, headers=headers)

                        if meta.get('debug'):
                            console.print(f"[dim]Response status: {response.status_code}")
                            console.print(f"[dim]Response URL: {response.url}")
                            console.print(response.text[:500] + "...")

                        if "uploaded=1" in str(response.url):
                            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                            tracker_status.setdefault(self.tracker, {})
                            tracker_status[self.tracker]['status_message'] = response.url
                            return True
                        else:
                            console.print(f"[yellow]Upload response didn't contain 'uploaded=1'. URL: {response.url}")
                            soup = BeautifulSoup(response.text, 'html.parser')
                            error_text = soup.find('h2', string=re.compile(r'Error'))  # type: ignore

                            if error_text:
                                error_message = cast(Any, error_text).find_next('p')
                                if error_message:
                                    console.print(
                                        f"[red]Upload error: {error_message.text}"
                                    )

                            return False
                else:
                    console.print("[red]Failed to log in to THR for upload")
                    return False

            except Exception as e:
                console.print(f"[red]Error during upload: {str(e)}")
                console.print_exception()
                if meta.get('debug') and response is not None:
                    with contextlib.suppress(Exception):
                        console.print(f"[red]Response: {response.text[:500]}...")
                console.print("[yellow]It may have uploaded, please check THR manually")
                return False
        else:
            console.print("[cyan]THR Request Data:")
            console.print(payload)
            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
            tracker_status.setdefault(self.tracker, {})
            tracker_status[self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(
                meta,
                f"{self.tracker}" + "_DEBUG",
                f"{self.tracker}" + "_DEBUG",
                announce_url="https://fake.tracker",
                torrent_bytes=_torrent_bytes,
            )
            return False

    def get_cat_id(self, meta: Meta) -> str:
        genres = str(meta.get('genres', '')).lower()
        keywords = str(meta.get('keywords', '')).lower()
        category = str(meta.get('category', ''))
        is_disc = str(meta.get('is_disc', ''))
        sd = int(meta.get('sd', 0) or 0)
        cat = '17'

        if 'documentary' in genres or 'documentary' in keywords:
            cat = '12'
        elif category == "MOVIE":
            if is_disc == "BDMV":
                cat = '40'
            elif is_disc in {"DVD", "HDDVD"}:
                cat = '14'
            else:
                cat = '4' if sd == 1 else '17'
        elif category == "TV":
            cat = '7' if sd == 1 else '34'
        elif bool(meta.get('anime')):
            cat = '31'
        return cat

    def get_subtitles(self, meta: Meta) -> list[int]:
        subs: list[int] = []
        sub_langs: list[str] = []
        if str(meta.get('is_disc', '')) != 'BDMV':
            with open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json", encoding='utf-8') as f:
                mi = cast(dict[str, Any], json.load(f))
            tracks = cast(list[dict[str, Any]], cast(dict[str, Any], mi.get('media', {})).get('track', []))
            for track in tracks:
                if track['@type'] == "Text":
                    language = track.get('Language')
                    language = language.split('-')[0] if language else language
                    if language in ['hr', 'en', 'bs', 'sr', 'sl'] and language not in sub_langs:
                        sub_langs.append(str(language))
        else:
            bdinfo = cast(dict[str, Any], meta.get('bdinfo', {}))
            for sub in cast(list[Any], bdinfo.get('subtitles', [])):
                if sub not in sub_langs:
                    sub_langs.append(str(sub))
        if sub_langs != []:
            subs = []
            sub_lang_map = {
                'hr': 1, 'en': 2, 'bs': 3, 'sr': 4, 'sl': 5,
                'Croatian': 1, 'English': 2, 'Bosnian': 3, 'Serbian': 4, 'Slovenian': 5
            }
            for sub in sub_langs:
                language = sub_lang_map.get(sub)
                if language is not None:
                    subs.append(language)
        return subs

    async def edit_desc(self, meta: Meta) -> bool:
        pronfo = False
        bbcode = BBCODE()
        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt",
            encoding='utf-8',
        ) as base_file:
            base = await base_file.read()

        desc_parts: list[str] = []
        tag_value = str(meta.get('tag', ''))
        tag = "" if tag_value == "" else f" / {tag_value[1:]}"
        res = str(meta.get('source', '')) if str(meta.get('is_disc', '')) == "DVD" else str(meta.get('resolution', ''))
        desc_parts.append("[quote=Info]")
        name_aka = f"{meta.get('title', '')} {meta.get('aka', '')} {meta.get('year', '')}"
        name_aka = unidecode(name_aka)
        # name_aka = re.sub("[^0-9a-zA-Z. '\-\[\]]+", " ", name_aka)
        desc_parts.append(f"Name: {' '.join(name_aka.split())}\n\n")
        desc_parts.append(f"Overview: {meta.get('overview', '')}\n\n")
        desc_parts.append(f"{res} / {meta.get('type', '')}{tag}\n\n")
        category = str(meta.get('category', ''))
        desc_parts.append(f"Category: {category}\n")
        desc_parts.append(f"TMDB: https://www.themoviedb.org/{category.lower()}/{meta.get('tmdb', '')}\n")
        if int(meta.get('imdb_id', 0) or 0) != 0:
            imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
            desc_parts.append(f"IMDb: {str(imdb_info.get('imdb_url', ''))}\n")
        if int(meta.get('tvdb_id', 0) or 0) != 0:
            desc_parts.append(f"TVDB: https://www.thetvdb.com/?id={meta.get('tvdb_id', '')}&tab=series\n")
        if int(meta.get('tvmaze_id', 0) or 0) != 0:
            desc_parts.append(f"TVMaze: https://www.tvmaze.com/shows/{meta.get('tvmaze_id', '')}\n")
        if int(meta.get('mal_id', 0) or 0) != 0:
            desc_parts.append(f"MAL: https://myanimelist.net/anime/{meta.get('mal_id', '')}\n")
        desc_parts.append("[/quote]")

        image_glob: list[str] = []

        if base:
            # replace unsupported bbcode tags
            base = bbcode.convert_named_spoiler_to_named_hide(base)
            base = bbcode.convert_spoiler_to_hide(base)
            base = bbcode.convert_code_to_pre(base)
            # fix alignment for NFO content inherited from centering the spoiler
            base = re.sub(r'(?P<open>\[hide=(Scene|FraMeSToR) NFO:\]\[pre\])(?P<content>.*?)(?P<close>\[/pre\]\[/hide\])',
                          r'\g<open>[align=left]\g<content>[/align]\g<close>',
                          base,
                          flags=re.DOTALL)
            desc_parts.append("\n\n" + base)

            # REHOST IMAGES
            os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
            image_patterns: list[str] = ["*.png", ".[!.]*.png"]
            for pattern in image_patterns:
                image_glob.extend(glob.glob(pattern))

            unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
            unwanted_files: set[str] = set()
            for pattern in unwanted_patterns:
                unwanted_files.update(glob.glob(pattern))
                if pattern.startswith("FILE") or pattern.startswith("PLAYLIST") or pattern.startswith("POSTER"):
                    hidden_pattern = "." + pattern
                    unwanted_files.update(glob.glob(hidden_pattern))

            image_glob = [file for file in image_glob if file not in unwanted_files]
            image_glob = list(set(image_glob))
        image_list: list[str] = []
        async with httpx.AsyncClient(timeout=30.0) as image_client:
            for image in image_glob:
                url = "https://img2.torrenthr.org/api/1/upload"
                data: dict[str, Any] = {
                    'key': str(self.config['TRACKERS']['THR'].get('img_api', '')),
                    # 'source' : base64.b64encode(open(image, "rb").read()).decode('utf8')
                }
                async with aiofiles.open(image, 'rb') as image_file:
                    file_bytes = await image_file.read()
                response: Optional[httpx.Response] = None
                response_data: dict[str, Any] = {}
                try:
                    response = await image_client.post(
                        url,
                        data=data,
                        files={'source': (os.path.basename(image), file_bytes)},
                    )
                    response_data = response.json()
                    img_url = response_data['image']['url']
                    image_list.append(img_url)
                except json.decoder.JSONDecodeError:
                    console.print("[yellow]Failed to upload image")
                    if response is not None:
                        console.print(response.text)
                except KeyError:
                    console.print("[yellow]Failed to upload image")
                    console.print(response_data)
                await asyncio.sleep(1)

        desc_parts.append("[align=center]")
        if str(meta.get('is_disc', '')) == 'BDMV':
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt") as bd_file:
                desc_parts.append(f"[nfo]{await bd_file.read()}[/nfo]")
        elif self.config['TRACKERS']['THR'].get('pronfo_api_key'):
            # ProNFO
            pronfo_url = f"https://www.pronfo.com/api/v1/access/upload/{self.config['TRACKERS']['THR'].get('pronfo_api_key', '')}"
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
            ) as mi_file:
                data = {
                    'content': await mi_file.read(),
                    'theme': self.config['TRACKERS']['THR'].get('pronfo_theme', 'gray'),
                    'rapi': self.config['TRACKERS']['THR'].get('pronfo_rapi_id')
                }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(pronfo_url, data=data)
            try:
                response_data = response.json()
                if response_data.get('error', True) is False:
                    mi_img = response_data.get('url')
                    desc_parts.append(f"\n[img]{mi_img}[/img]\n")
                    pronfo = True
            except Exception:
                console.print('[bold red]Error parsing pronfo response, using THR parser instead')
                if meta['debug']:
                    console.print(f"[red]{response}")
                    console.print(response.text)

        screens = int(meta.get('screens', 0) or 0)
        desc_parts.extend([f"\n[img]{each}[/img]\n" for each in image_list[:screens]])
            # if pronfo:
            #     with open(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"), 'r') as mi_file:
            #         full_mi = mi_file.read()
            #         desc.write(f"[/align]\n[hide=FULL MEDIAINFO]{full_mi}[/hide][align=center]")
            #         mi_file.close()
        desc_parts.append(
            f"\n\n[size=2][url=https://www.torrenthr.org/forums.php?action=viewtopic&topicid=8977]{meta.get('ua_signature', '')}[/url][/size][/align]"
        )
        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt",
            'w',
            encoding='utf-8',
        ) as desc:
            await desc.write("".join(desc_parts))
        return pronfo

    async def search_existing(self, meta: Meta, _disctype: str) -> list[str]:
        imdb_id = str(meta.get('imdb', ''))
        base_search_url = f"https://www.torrenthr.org/browse.php?search={imdb_id}&blah=2&incldead=1"
        dupes: list[str] = []

        if not imdb_id:
            console.print("[red]No IMDb ID available for search", style="bold red")
            return dupes

        try:
            cookies = await self.login()

            client_args: dict[str, Any] = {'timeout': 10.0, 'follow_redirects': True}
            if cookies:
                client_args['cookies'] = cookies
            else:
                console.print("[red]Failed to log in to THR for search")
                return dupes

            async with httpx.AsyncClient(**client_args) as client:
                # Start with first page (page 0 in THR's system)
                current_page = 0
                more_pages = True
                page_count = 0
                all_titles_seen: set[str] = set()

                while more_pages:
                    page_url = base_search_url
                    if current_page > 0:
                        page_url += f"&page={current_page}"

                    page_count += 1
                    if meta.get('debug', False):
                        console.print(f"[dim]Searching page {page_count}...")
                    response = await client.get(page_url)

                    page_dupes, has_next_page, next_page_number = self._process_search_response(
                        response, meta, current_page)

                    for dupe in page_dupes:
                        if dupe not in dupes:
                            dupes.append(dupe)
                            all_titles_seen.add(dupe)

                    if meta.get('debug', False) and has_next_page:
                        console.print(f"[dim]Next page available: page {next_page_number}")

                    if has_next_page:
                        current_page = next_page_number

                        await asyncio.sleep(1)
                    else:
                        more_pages = False

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes

    def _process_search_response(
        self,
        response: httpx.Response,
        meta: Meta,
        current_page: int,
    ) -> tuple[list[str], bool, int]:
        page_dupes: list[str] = []
        has_next_page = False
        next_page_number = current_page

        if response.status_code == 200 or response.status_code == 302:
            html_length = len(response.text)
            if meta.get('debug', False):
                console.print(f"[dim]Response HTML length: {html_length} bytes")

            if html_length < 1000:
                console.print(f"[yellow]Response seems too small ({html_length} bytes), might be an error page")
                if meta.get('debug', False):
                    console.print(f"[yellow]Response content: {response.text[:500]}")
                return page_dupes, False, current_page

            soup = BeautifulSoup(response.text, 'html.parser')

            result_table = soup.find('table', {'class': 'torrentlist'}) or soup.find('table', {'align': 'center'})
            if not result_table:
                console.print("[yellow]No results table found in HTML - either no results or page structure changed")

            link_count = 0
            onmousemove_count = 0

            for link in soup.find_all('a', href=True):
                href_raw = link.get('href')
                if not href_raw:
                    continue
                href = ' '.join(href_raw) if isinstance(href_raw, AttributeValueList) else str(href_raw)

                if href.startswith('details.php'):
                    link_count += 1
                    onmousemove_raw = link.get('onmousemove')
                    if onmousemove_raw:
                        onmousemove_count += 1
                        try:
                            onmousemove = ' '.join(onmousemove_raw) if isinstance(onmousemove_raw, AttributeValueList) else str(onmousemove_raw)
                            dupe = onmousemove.split("','/images")[0]
                            dupe = dupe.replace("return overlibImage('", "")
                            page_dupes.append(dupe)
                        except Exception as parsing_error:
                            if meta.get('debug', False):
                                console.print(f"[yellow]Error parsing link: {parsing_error}")

            page_number_display = current_page + 1
            if meta.get('debug', False):
                console.print(f"[dim]Page {page_number_display}: Found {link_count} detail links, {onmousemove_count} parsed successfully")

            pagination_text = None
            for p_tag in soup.find_all('p', align="center"):
                if p_tag.text and ('Prev' in p_tag.text or 'Next' in p_tag.text):
                    pagination_text = p_tag
                    if meta.get('debug', False):
                        console.print(f"[dim]Found pagination: {pagination_text.text.strip()}")
                    break

            if pagination_text:
                next_links = pagination_text.find_all('a')
                for link in next_links:
                    if 'Next' in link.text:
                        has_next_page = True
                        href_raw = link.get('href')
                        href = ''
                        if href_raw:
                            href = ' '.join(href_raw) if isinstance(href_raw, AttributeValueList) else str(href_raw)

                        if meta.get('debug', False):
                            console.print(f"[dim]Next page URL: {href}")

                        page_match = re.search(r'page=(\d+)', href)
                        if page_match:
                            next_page_number = int(page_match.group(1))
                            if meta.get('debug', False):
                                console.print(f"[dim]Found next page link: page={next_page_number} (will be displayed as page {next_page_number + 1})")
                            break
        else:
            console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")
            if meta.get('debug', False):
                console.print(f"[red]Response: {response.text[:500]}...")

        return page_dupes, has_next_page, next_page_number

    async def login(self) -> Optional[dict[str, Any]]:
        console.print("[yellow]Logging in to THR...")
        url = 'https://www.torrenthr.org/takelogin.php'

        if not self.username or not self.password:
            console.print('[red]Missing THR credentials in config.py')
            return None

        payload: dict[str, Any] = {
            'username': self.username,
            'password': self.password,
            'ssl': 'yes'
        }
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})',
            'Referer': 'https://www.torrenthr.org/login.php'
        }

        async with httpx.AsyncClient(follow_redirects=True) as session:
            try:
                login_page = await session.get('https://www.torrenthr.org/login.php')
                login_soup = BeautifulSoup(login_page.text, 'html.parser')

                for input_tag in login_soup.find_all('input', type='hidden'):
                    name_raw = input_tag.get('name')
                    value_raw = input_tag.get('value')
                    if name_raw and value_raw:
                        name = ' '.join(name_raw) if isinstance(name_raw, AttributeValueList) else str(name_raw)
                        value = ' '.join(value_raw) if isinstance(value_raw, AttributeValueList) else str(value_raw)
                        payload[name] = value

                resp = await session.post(url, headers=headers, data=payload)

                if "index.php" in str(resp.url) or "logout.php" in resp.text:
                    console.print('[green]Successfully logged in to THR')
                    return dict(session.cookies)
                else:
                    console.print('[red]Failed to log in to THR')
                    console.print(f'[red]Login response URL: {resp.url}')
                    console.print(f'[red]Login status code: {resp.status_code}')
                    return None

            except Exception as e:
                console.print(f"[red]Error during THR login: {str(e)}")
                console.print_exception()
                return None
