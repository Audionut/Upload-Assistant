# -*- coding: utf-8 -*-
import asyncio
import requests
import json
import glob
import cli_ui
import os
import re
import platform
import httpx
from bs4 import BeautifulSoup
from unidecode import unidecode
from src.console import console
from src.trackers.COMMON import COMMON


class THR():
    def __init__(self, config):
        self.config = config
        self.tracker = 'THR'
        self.source_flag = '[https://www.torrenthr.org] TorrentHR.org'
        self.username = config['TRACKERS']['THR'].get('username')
        self.password = config['TRACKERS']['THR'].get('password')
        self.banned_groups = [""]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta)
        subs = self.get_subtitles(meta)
        pronfo = await self.edit_desc(meta)  # noqa #F841
        thr_name = unidecode(meta['name'].replace('DD+', 'DDP'))

        # Confirm the correct naming order for THR
        cli_ui.info(f"THR name: {thr_name}")
        if meta.get('unattended', False) is False:
            thr_confirm = cli_ui.ask_yes_no("Correct?", default=False)
            if thr_confirm is not True:
                thr_name_manually = cli_ui.ask_string("Please enter a proper name", default="")
                if thr_name_manually == "":
                    console.print('No proper name given')
                    console.print("Aborting...")
                    return
                else:
                    thr_name = thr_name_manually
        torrent_name = re.sub(r"[^0-9a-zA-Z. '\-\[\]]+", " ", thr_name)

        if meta.get('is_disc', '') == 'BDMV':
            mi_file = None
            # bd_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8'
        else:
            mi_file = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt")
            with open(mi_file, 'r') as f:
                mi_file = f.read()
                f.close()
            # bd_file = None

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt", 'r', encoding='utf-8') as f:
            desc = f.read()
            f.close()

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR].torrent")
        with open(torrent_path, 'rb') as f:
            tfile = f.read()
            f.close()

        # Upload Form
        url = 'https://www.torrenthr.org/takeupload.php'
        files = {
            'tfile': (f'{torrent_name}.torrent', tfile)
        }
        payload = {
            'name': thr_name,
            'descr': desc,
            'type': cat_id,
            'url': f"https://www.imdb.com/title/tt{meta.get('imdb')}/",
            'tube': meta.get('youtube', '')
        }
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        # If pronfo fails, put mediainfo into THR parser
        if meta.get('is_disc', '') != 'BDMV':
            files['nfo'] = ("MEDIAINFO.txt", mi_file)
        if subs != []:
            payload['subs[]'] = tuple(subs)

        if meta['debug'] is False:
            thr_upload_prompt = True
        else:
            thr_upload_prompt = cli_ui.ask_yes_no("send to takeupload.php?", default=False)

        if thr_upload_prompt is True:
            await asyncio.sleep(0.5)
            try:
                cookies = await self.login()

                if cookies:
                    console.print("[green]Using authenticated session for upload")

                    async with httpx.AsyncClient(cookies=cookies, follow_redirects=True) as session:
                        response = await session.post(url=url, files=files, data=payload, headers=headers)

                        if meta['debug']:
                            console.print(f"[dim]Response status: {response.status_code}")
                            console.print(f"[dim]Response URL: {response.url}")
                            console.print(response.text[:500] + "...")

                        if "uploaded=1" in str(response.url):
                            meta['tracker_status'][self.tracker]['status_message'] = response.url
                            return True
                        else:
                            console.print(f"[yellow]Upload response didn't contain 'uploaded=1'. URL: {response.url}")
                            soup = BeautifulSoup(response.text, 'html.parser')
                            error_text = soup.find('h2', string=lambda text: text and 'Error' in text)

                            if error_text:
                                error_message = error_text.find_next('p')
                                if error_message:
                                    console.print(f"[red]Upload error: {error_message.text}")

                            return False
                else:
                    console.print("[red]Failed to log in to THR for upload")
                    return False

            except Exception as e:
                console.print(f"[red]Error during upload: {str(e)}")
                console.print_exception()
                if meta['debug']:
                    try:
                        console.print(f"[red]Response: {response.text[:500]}...")
                    except Exception:
                        pass
                console.print("[yellow]It may have uploaded, please check THR manually")
                return False
        else:
            console.print("[cyan]Request Data:")
            console.print(payload)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            return False

    async def get_cat_id(self, meta):
        if meta['category'] == "MOVIE":
            if meta.get('is_disc') == "BMDV":
                cat = '40'
            elif meta.get('is_disc') == "DVD" or meta.get('is_disc') == "HDDVD":
                cat = '14'
            else:
                if meta.get('sd') == 1:
                    cat = '4'
                else:
                    cat = '17'
        elif meta['category'] == "TV":
            if meta.get('sd') == 1:
                cat = '7'
            else:
                cat = '34'
        elif meta.get('anime') is not False:
            cat = '31'
        return cat

    def get_subtitles(self, meta):
        subs = []
        sub_langs = []
        if meta.get('is_disc', '') != 'BDMV':
            with open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json", 'r', encoding='utf-8') as f:
                mi = json.load(f)
            for track in mi['media']['track']:
                if track['@type'] == "Text":
                    language = track.get('Language')
                    if language in ['hr', 'en', 'bs', 'sr', 'sl']:
                        if language not in sub_langs:
                            sub_langs.append(language)
        else:
            for sub in meta['bdinfo']['subtitles']:
                if sub not in sub_langs:
                    sub_langs.append(sub)
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

    async def edit_desc(self, meta):
        pronfo = False
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            if meta['tag'] == "":
                tag = ""
            else:
                tag = f" / {meta['tag'][1:]}"
            if meta['is_disc'] == "DVD":
                res = meta['source']
            else:
                res = meta['resolution']
            desc.write("[quote=Info]")
            name_aka = f"{meta['title']} {meta['aka']} {meta['year']}"
            name_aka = unidecode(name_aka)
            # name_aka = re.sub("[^0-9a-zA-Z. '\-\[\]]+", " ", name_aka)
            desc.write(f"Name: {' '.join(name_aka.split())}\n\n")
            desc.write(f"Overview: {meta['overview']}\n\n")
            desc.write(f"{res} / {meta['type']}{tag}\n\n")
            desc.write(f"Category: {meta['category']}\n")
            desc.write(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}\n")
            if meta['imdb_id'] != 0:
                desc.write(f"IMDb: https://www.imdb.com/title/tt{meta['imdb']}\n")
            if meta['tvdb_id'] != 0:
                desc.write(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series\n")
            desc.write("[/quote]")
            desc.write(base)
            # REHOST IMAGES
            os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
            image_patterns = ["*.png", ".[!.]*.png"]
            image_glob = []
            for pattern in image_patterns:
                image_glob.extend(glob.glob(pattern))

            unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
            unwanted_files = set()
            for pattern in unwanted_patterns:
                unwanted_files.update(glob.glob(pattern))
                if pattern.startswith("FILE") or pattern.startswith("PLAYLIST") or pattern.startswith("POSTER"):
                    hidden_pattern = "." + pattern
                    unwanted_files.update(glob.glob(hidden_pattern))

            image_glob = [file for file in image_glob if file not in unwanted_files]
            image_glob = list(set(image_glob))
            image_list = []
            for image in image_glob:
                url = "https://img2.torrenthr.org/api/1/upload"
                data = {
                    'key': self.config['TRACKERS']['THR'].get('img_api'),
                    # 'source' : base64.b64encode(open(image, "rb").read()).decode('utf8')
                }
                files = {'source': open(image, 'rb')}
                response = requests.post(url, data=data, files=files)
                try:
                    response = response.json()
                    # med_url = response['image']['medium']['url']
                    img_url = response['image']['url']
                    image_list.append(img_url)
                except json.decoder.JSONDecodeError:
                    console.print("[yellow]Failed to upload image")
                    console.print(response.text)
                except KeyError:
                    console.print("[yellow]Failed to upload image")
                    console.print(response)
                await asyncio.sleep(1)
            desc.write("[align=center]")
            if meta.get('is_disc', '') == 'BDMV':
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt") as bd_file:
                    desc.write(f"[nfo]{bd_file.read()}[/nfo]")
                    bd_file.close()
            else:
                # ProNFO
                pronfo_url = f"https://www.pronfo.com/api/v1/access/upload/{self.config['TRACKERS']['THR'].get('pronfo_api_key', '')}"
                data = {
                    'content': open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r').read(),
                    'theme': self.config['TRACKERS']['THR'].get('pronfo_theme', 'gray'),
                    'rapi': self.config['TRACKERS']['THR'].get('pronfo_rapi_id')
                }
                response = requests.post(pronfo_url, data=data)
                try:
                    response = response.json()
                    if response.get('error', True) is False:
                        mi_img = response.get('url')
                        desc.write(f"\n[img]{mi_img}[/img]\n")
                        pronfo = True
                except Exception:
                    console.print('[bold red]Error parsing pronfo response, using THR parser instead')
                    if meta['debug']:
                        console.print(f"[red]{response}")
                        console.print(response.text)

            for each in image_list[:int(meta['screens'])]:
                desc.write(f"\n[img]{each}[/img]\n")
            # if pronfo:
            #     with open(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"), 'r') as mi_file:
            #         full_mi = mi_file.read()
            #         desc.write(f"[/align]\n[hide=FULL MEDIAINFO]{full_mi}[/hide][align=center]")
            #         mi_file.close()
            desc.write("\n\n[size=2][url=https://www.torrenthr.org/forums.php?action=viewtopic&topicid=8977]Created by L4G's Upload Assistant[/url][/size][/align]")
            desc.close()
        return pronfo

    async def search_existing(self, meta, disctype):
        imdb_id = meta.get('imdb', '')
        base_search_url = f"https://www.torrenthr.org/browse.php?search={imdb_id}&blah=2&incldead=1"
        dupes = []

        if not imdb_id:
            console.print("[red]No IMDb ID available for search", style="bold red")
            return dupes

        try:
            cookies = await self.login()

            client_args = {'timeout': 10.0, 'follow_redirects': True}
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
                all_titles_seen = set()

                while more_pages:
                    page_url = base_search_url
                    if current_page > 0:
                        page_url += f"&page={current_page}"

                    page_count += 1
                    if meta.get('debug', False):
                        console.print(f"[dim]Searching page {page_count}...")
                    response = await client.get(page_url)

                    page_dupes, has_next_page, next_page_number = await self._process_search_response(
                        response, meta, all_titles_seen, current_page)

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

    async def _process_search_response(self, response, meta, existing_dupes, current_page):
        page_dupes = []
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
                if link['href'].startswith('details.php'):
                    link_count += 1
                    if link.get('onmousemove', False):
                        onmousemove_count += 1
                        try:
                            dupe = link['onmousemove'].split("','/images")[0]
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
                        href = link.get('href', '')

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

    async def login(self):
        console.print("[yellow]Logging in to THR...")
        url = 'https://www.torrenthr.org/takelogin.php'

        if not self.username or not self.password:
            console.print('[red]Missing THR credentials in config.py')
            return None

        payload = {
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
                    if input_tag.get('name') and input_tag.get('value'):
                        payload[input_tag['name']] = input_tag['value']

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
