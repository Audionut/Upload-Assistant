# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import re
from typing import Any, Optional, cast
from urllib.parse import urlparse

import aiofiles
import httpx
from bs4 import BeautifulSoup
from unidecode import unidecode

from src.console import console
from src.exceptions import *  # noqa #F405
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class TTG:

    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'TTG'
        self.source_flag = 'TTG'
        self.passkey = str(config['TRACKERS']['TTG'].get('announce_url', '')).strip().split('/')[-1]
        self.signature = None
        self.banned_groups = [""]

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

    async def upload(self, meta: Meta, _disctype: str) -> Optional[bool]:
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

        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt",
            encoding='utf-8',
        ) as desc_file:
            ttg_desc = await desc_file.read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        filelist = cast(list[Any], meta.get('filelist', []))
        async with aiofiles.open(torrent_path, 'rb') as torrent_file:
            torrent_bytes = await torrent_file.read()
        if len(filelist) == 1:
            torrentFileName = unidecode(os.path.basename(str(meta.get('video', ''))).replace(' ', '.'))
        else:
            torrentFileName = unidecode(os.path.basename(str(meta.get('path', ''))).replace(' ', '.'))
        async with aiofiles.open(mi_path, encoding='utf-8') as mi_dump:
            mi_text = await mi_dump.read()
        files = {
            'file': (f"{torrentFileName}.torrent", torrent_bytes, "application/x-bittorent"),
            'nfo': ("torrent.nfo", mi_text)
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
            cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.txt")
            cookies = await common.parseCookieFile(cookiefile)
            async with httpx.AsyncClient(cookies=cookies, follow_redirects=True, timeout=60.0) as client:
                up = await client.post(url=url, data=data, files=files)

            if str(up.url).startswith("https://totheglory.im/details.php?id="):
                tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                tracker_status.setdefault(self.tracker, {})
                tracker_status[self.tracker]['status_message'] = str(up.url)
                id_match = re.search(r"(id=)(\d+)", urlparse(str(up.url)).query)
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

    async def search_existing(self, meta: Meta, _disctype: str) -> list[str]:
        dupes: list[str] = []
        common = COMMON(config=self.config)
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.txt")
        if not os.path.exists(cookiefile):
            console.print("[bold red]Cookie file not found: TTG.txt")
            return []
        cookies = await common.parseCookieFile(cookiefile)

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
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/TTG.txt")
        if not os.path.exists(cookiefile):
            console.print('[red]Cookie file not found for TTG. Please export cookies to data/cookies/TTG.txt')
            return False
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your cookies are valid.')
            return False
        return True

    async def validate_cookies(self, meta: Meta, cookiefile: str) -> bool:
        common = COMMON(config=self.config)
        url = "https://totheglory.im"
        if os.path.exists(cookiefile):
            cookies = await common.parseCookieFile(cookiefile)
            async with httpx.AsyncClient(cookies=cookies, timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url=url)
                if meta.get('debug'):
                    console.print('[cyan]Cookies:')
                    console.print(resp.url)
                return resp.text.find('''<a href="/logout.php">Logout</a>''') != -1
        else:
            return False

    async def edit_desc(self, meta: Meta) -> None:
        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt",
            encoding='utf-8',
        ) as base_file:
            base = await base_file.read()

        from src.bbcode import BBCODE
        from src.trackers.COMMON import COMMON
        common = COMMON(config=self.config)

        parts: list[str] = []
        if int(meta.get('imdb_id', 0) or 0) != 0:
            ptgen = await common.ptgen(meta)
            if ptgen.strip() != '':
                parts.append(ptgen)

        # Add This line for all web-dls
        if meta.get('type') == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description', None) is None:
            parts.append(
                f"[center][b][color=#ff00ff][size=3]{meta['service_longname']}的无损REMUX片源，没有转码/This release is sourced from {meta['service_longname']} and is not transcoded, just remuxed from the direct {meta['service_longname']} stream[/size][/color][/b][/center]"
            )
        bbcode = BBCODE()
        if meta.get('discs', []) != []:
            discs = cast(list[dict[str, Any]], meta.get('discs', []))
            for each in discs:
                if each['type'] == "BDMV":
                    parts.append(f"[quote={each.get('name', 'BDINFO')}]{each['summary']}[/quote]\n")
                    parts.append("\n")
                if each['type'] == "DVD":
                    parts.append(f"{each.get('name', '')}:\n")
                    parts.append(
                        f"[quote={os.path.basename(str(each.get('vob', '')))}][{each.get('vob_mi', '')}[/quote] "
                        f"[quote={os.path.basename(str(each.get('ifo', '')))}][{each.get('ifo_mi', '')}[/quote]\n"
                    )
                    parts.append("\n")
        else:
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt",
                encoding='utf-8',
            ) as mi_file:
                mi = await mi_file.read()
            parts.append(f"[quote=MediaInfo]{mi}[/quote]")
            parts.append("\n")
        desc = base
        desc = bbcode.convert_code_to_quote(desc)
        desc = bbcode.convert_spoiler_to_hide(desc)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)
        desc = desc.replace('[img]', '[img]')
        desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
        parts.append(desc)
        images = cast(list[dict[str, Any]], meta.get('image_list', []))
        if images:
            parts.append("[center]")
            screens = int(meta.get('screens', 0) or 0)
            for each in range(len(images[:screens])):
                web_url = images[each].get('web_url')
                img_url = images[each].get('img_url')
                if not web_url or not img_url:
                    continue
                parts.append(f"[url={web_url}][img]{img_url}[/img][/url]")
            parts.append("[/center]")
        if self.signature is not None:
            parts.append("\n\n")
            parts.append(self.signature)

        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt",
            'w',
            encoding='utf-8',
        ) as descfile:
            await descfile.write("".join(parts))

    async def download_new_torrent(self, id: str, torrent_path: str) -> None:
        download_url = f"https://totheglory.im/dl/{id}/{self.passkey}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url=download_url)
        if r.status_code == 200:
            async with aiofiles.open(torrent_path, "wb") as tor:
                await tor.write(r.content)
        else:
            console.print("[red]There was an issue downloading the new .torrent from TTG")
            console.print(r.text)
