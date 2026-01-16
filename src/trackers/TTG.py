# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import re
from typing import Any, Optional, cast
from urllib.parse import urlparse

import cli_ui
import httpx
import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

from src.console import console
from src.cookie_auth import CookieValidator
from src.exceptions import *  # noqa #F405
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class TTG:

    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'TTG'
        self.source_flag = 'TTG'
        self.username = str(config['TRACKERS']['TTG'].get('username', '')).strip()
        self.password = str(config['TRACKERS']['TTG'].get('password', '')).strip()
        self.passid = str(config['TRACKERS']['TTG'].get('login_question', '0')).strip()
        self.passan = str(config['TRACKERS']['TTG'].get('login_answer', '')).strip()
        self.uid = str(config['TRACKERS']['TTG'].get('user_id', '')).strip()
        self.passkey = str(config['TRACKERS']['TTG'].get('announce_url', '')).strip().split('/')[-1]
        self.signature = None
        self.banned_groups = [""]

        self.cookie_validator = CookieValidator(config)

    async def edit_name(self, meta: Meta) -> str:
        ttg_name = str(meta.get('name', ''))

        remove_list = ['Dubbed', 'Dual-Audio']
        for each in remove_list:
            ttg_name = ttg_name.replace(each, '')
        ttg_name = ttg_name.replace('PQ10', 'HDR')
        ttg_name = ttg_name.replace('.', '{@}')
        return ttg_name

    async def get_type_id(self, meta: Meta) -> int:
        type_id = 0
        lang = str(meta.get('original_language', 'UNKNOWN')).upper()
        category = str(meta.get('category', ''))
        resolution = str(meta.get('resolution', ''))
        if meta['category'] == "MOVIE":
            # 51 = DVDRip
            if resolution.startswith("720"):
                type_id = 52  # 720p
            if resolution.startswith("1080"):
                type_id = 53  # 1080p/i
            if meta.get('is_disc') == "BDMV":
                type_id = 54  # Blu-ray disc

        elif category == "TV":
            if meta.get('tv_pack', 0) != 1:
                # TV Singles
                if resolution.startswith("720"):
                    type_id = 69  # 720p TV EU/US
                    if lang in ('ZH', 'CN', 'CMN'):
                        type_id = 76  # Chinese
                if resolution.startswith("1080"):
                    type_id = 70  # 1080 TV EU/US
                    if lang in ('ZH', 'CN', 'CMN'):
                        type_id = 75  # Chinese
                if lang in ('KR', 'KO'):
                    type_id = 75  # Korean
                if lang in ('JA', 'JP'):
                    type_id = 73  # Japanese
            else:
                # TV Packs
                type_id = 87  # EN/US
                if lang in ('KR', 'KO'):
                    type_id = 99  # Korean
                if lang in ('JA', 'JP'):
                    type_id = 88  # Japanese
                if lang in ('ZH', 'CN', 'CMN'):
                    type_id = 90  # Chinese

        genres_value = str(meta.get("genres", "")).lower().replace(' ', '').replace('-', '')
        keywords_value = str(meta.get("keywords", "")).lower().replace(' ', '').replace('-', '')
        if "documentary" in genres_value or 'documentary' in keywords_value:
            if resolution.startswith("720"):
                type_id = 62  # 720p
            if resolution.startswith("1080"):
                type_id = 63  # 1080
            if meta.get('is_disc', '') == 'BDMV':
                type_id = 64  # BDMV

        if (
            "animation" in genres_value
            or 'animation' in keywords_value
        ) and meta.get('sd', 1) == 0:
            type_id = 58

        if resolution in ("2160p"):
            type_id = 108
            if meta.get('is_disc', '') == 'BDMV':
                type_id = 109

        # I guess complete packs?:
            # 103 = TV Shows KR
            # 101 = TV Shows JP
            # 60 = TV Shows
        return type_id

    async def upload(self, meta: Meta, disctype: str) -> Optional[bool]:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        ttg_name = await self.edit_name(meta)

        # FORM
        # type = category dropdown
        # name = name
        # descr = description
        # anonymity = "yes" / "no"
        # nodistr = "yes" / "no" (exclusive?) not required
        # imdb_c = tt123456
        #
        # POST > upload/upload

        anon = (
            'no'
            if meta.get('anon') == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False)
            else 'yes'
        )

        mi_path = (
            f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if meta['bdinfo'] is not None
            else f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
        )

        with open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt",
            encoding='utf-8',
        ) as desc_file:
            ttg_desc = desc_file.read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        filelist = cast(list[Any], meta.get('filelist', []))
        with open(torrent_path, 'rb') as torrentFile:
            if len(filelist) == 1:
                torrentFileName = unidecode(os.path.basename(str(meta.get('video', ''))).replace(' ', '.'))
            else:
                torrentFileName = unidecode(os.path.basename(str(meta.get('path', ''))).replace(' ', '.'))
            with open(mi_path, encoding='utf-8') as mi_dump:
                files = {
                    'file': (f"{torrentFileName}.torrent", torrentFile, "application/x-bittorent"),
                    'nfo': ("torrent.nfo", mi_dump)
                }
                data: dict[str, Any] = {
                    'MAX_FILE_SIZE': '4000000',
                    'team': '',
                    'hr': 'no',
                    'name': ttg_name,
                    'type': await self.get_type_id(meta),
                    'descr': ttg_desc.rstrip(),

                    'anonymity': anon,
                    'nodistr': 'no',

                }
                url = "https://totheglory.im/takeupload.php"
                if int(meta.get('imdb_id', 0) or 0) != 0:
                    data['imdb_c'] = f"tt{meta.get('imdb')}"

                # Submit
                if meta.get('debug'):
                    console.print(url)
                    console.print(data)
                    tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                    tracker_status.setdefault(self.tracker, {})
                    tracker_status[self.tracker]['status_message'] = "Debug mode enabled, not uploading."
                    await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
                    return True  # Debug mode - simulated success
                else:
                    with requests.Session() as session:
                        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.json")
                        self.cookie_validator._load_cookies_secure(session, cookiefile, self.tracker)  # type: ignore[reportPrivateUsage]
                        up = session.post(url=url, data=data, files=files, timeout=60)

                        if up.url.startswith("https://totheglory.im/details.php?id="):
                            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                            tracker_status.setdefault(self.tracker, {})
                            tracker_status[self.tracker]['status_message'] = up.url
                            id_match = re.search(r"(id=)(\d+)", urlparse(up.url).query)
                            if not id_match:
                                raise UploadException(  # noqa #F405
                                    f"Upload to TTG succeeded but torrent id missing from URL {up.url}",
                                    'red',
                                )
                            torrent_id = id_match.group(2)
                            await self.download_new_torrent(torrent_id, torrent_path)
                            return True
                        else:
                            console.print(data)
                            console.print("\n\n")
                            raise UploadException(f"Upload to TTG Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa #F405

    async def search_existing(self, meta: Meta, disctype: str) -> list[str]:
        dupes: list[str] = []
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.json")
        if not os.path.exists(cookiefile):
            console.print("[bold red]Cookie file not found: TTG.json")
            return []
        cookies = self.cookie_validator._load_cookies_dict_secure(cookiefile)  # type: ignore[reportPrivateUsage]

        imdb = f"imdb{meta.get('imdb')}" if int(meta.get('imdb_id', 0) or 0) != 0 else ""
        if meta.get('is_disc', '') == "BDMV":
            res_type = f"{meta.get('resolution', '')} Blu-ray"
        elif meta.get('is_disc', '') == "DVD":
            res_type = "DVD"
        else:
            res_type = str(meta.get('resolution', ''))

        search_url = f"https://totheglory.im/browse.php?search_field= {imdb} {res_type}"

        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
                response = await client.get(search_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    find = soup.find_all('a', href=True)
                    for each in find:
                        href_value = each.get('href')
                        if isinstance(href_value, str) and href_value.startswith('/t/'):
                            release = re.search(r"(<b>)(<font.*>)?(.*)<br", str(each))
                            if release:
                                dupes.append(release.group(3))
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

                await asyncio.sleep(0.5)

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes

    async def validate_credentials(self, meta: Meta) -> bool:
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.pkl")
        if not os.path.exists(cookiefile):
            await self.login(cookiefile)
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your passkey is valid.')
            recreate = cli_ui.ask_yes_no("Log in again and create new session?")
            if recreate is True:
                if os.path.exists(cookiefile):
                    os.remove(cookiefile)
                await self.login(cookiefile)
                vcookie = await self.validate_cookies(meta, cookiefile)
                return vcookie
            else:
                return False
        return True

    async def validate_cookies(self, meta: Meta, cookiefile: str) -> bool:
        url = "https://totheglory.im"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                self.cookie_validator._load_cookies_secure(session, cookiefile, self.tracker)  # type: ignore[reportPrivateUsage]
                resp = session.get(url=url, timeout=30)
                if meta.get('debug'):
                    console.print('[cyan]Cookies:')
                    console.print(resp.url)
                return resp.text.find('''<a href="/logout.php">Logout</a>''') != -1
        else:
            return False

    async def login(self, cookiefile: str) -> None:
        url = "https://totheglory.im/takelogin.php"
        data: dict[str, Any] = {
            'username': self.username,
            'password': self.password,
            'passid': self.passid,
            'passan': self.passan
        }
        with requests.Session() as session:
            response = session.post(url, data=data, timeout=30)
            await asyncio.sleep(0.5)
            if response.url.endswith('2fa.php'):
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'name': 'authenticity_token'})
                auth_token = token_input.get('value') if token_input else None
                if not auth_token:
                    raise UploadException('Missing authenticity token during TTG login', 'red')  # noqa #F405
                two_factor_data = {
                    'otp': console.input('[yellow]TTG 2FA Code: '),
                    'authenticity_token': auth_token,
                    'uid': self.uid
                }
                two_factor_url = "https://totheglory.im/take2fa.php"
                response = session.post(two_factor_url, data=two_factor_data)
                await asyncio.sleep(0.5)
            if response.url.endswith('my.php'):
                console.print('[green]Successfully logged into TTG')
                self.cookie_validator._save_cookies_secure(session.cookies, cookiefile)  # type: ignore[reportPrivateUsage]
            else:
                console.print('[bold red]Something went wrong')
                await asyncio.sleep(1)
                console.print(response.text)
                console.print(response.url)
        return

    async def edit_desc(self, meta: Meta) -> None:
        with open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt",
            encoding='utf-8',
        ) as base_file:
            base = base_file.read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            from src.trackers.COMMON import COMMON
            common = COMMON(config=self.config)
            if int(meta.get('imdb_id', 0) or 0) != 0:
                ptgen = await common.ptgen(meta)
                if ptgen.strip() != '':
                    descfile.write(ptgen)

            # Add This line for all web-dls
            if meta.get('type') == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description', None) is None:
                descfile.write(f"[center][b][color=#ff00ff][size=3]{meta['service_longname']}的无损REMUX片源，没有转码/This release is sourced from {meta['service_longname']} and is not transcoded, just remuxed from the direct {meta['service_longname']} stream[/size][/color][/b][/center]")
            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = cast(list[dict[str, Any]], meta.get('discs', []))
                for each in discs:
                    if each['type'] == "BDMV":
                        descfile.write(f"[quote={each.get('name', 'BDINFO')}]{each['summary']}[/quote]\n")
                        descfile.write("\n")
                        pass
                    if each['type'] == "DVD":
                        descfile.write(f"{each.get('name', '')}:\n")
                        descfile.write(
                            f"[quote={os.path.basename(str(each.get('vob', '')))}][{each.get('vob_mi', '')}[/quote] "
                            f"[quote={os.path.basename(str(each.get('ifo', '')))}][{each.get('ifo_mi', '')}[/quote]\n"
                        )
                        descfile.write("\n")
            else:
                with open(
                    f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt",
                    encoding='utf-8',
                ) as mi_file:
                    mi = mi_file.read()
                descfile.write(f"[quote=MediaInfo]{mi}[/quote]")
                descfile.write("\n")
            desc = base
            desc = bbcode.convert_code_to_quote(desc)
            desc = bbcode.convert_spoiler_to_hide(desc)
            desc = bbcode.convert_comparison_to_centered(desc, 1000)
            desc = desc.replace('[img]', '[img]')
            desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
            descfile.write(desc)
            images = cast(list[dict[str, Any]], meta.get('image_list', []))
            if images:
                descfile.write("[center]")
                screens = int(meta.get('screens', 0) or 0)
                for each in range(len(images[:screens])):
                    web_url = images[each].get('web_url')
                    img_url = images[each].get('img_url')
                    if not web_url or not img_url:
                        continue
                    descfile.write(f"[url={web_url}][img]{img_url}[/img][/url]")
                descfile.write("[/center]")
            if self.signature is not None:
                descfile.write("\n\n")
                descfile.write(self.signature)
            descfile.close()

    async def download_new_torrent(self, id: str, torrent_path: str) -> None:
        download_url = f"https://totheglory.im/dl/{id}/{self.passkey}"
        r = requests.get(url=download_url, timeout=30)
        if r.status_code == 200:
            with open(torrent_path, "wb") as tor:
                tor.write(r.content)
        else:
            console.print("[red]There was an issue downloading the new .torrent from TTG")
            console.print(r.text)
