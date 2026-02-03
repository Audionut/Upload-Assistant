# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import glob
import io
import json
import os
import platform
import re
from pathlib import Path
from typing import Any, Optional, Union, cast
from urllib.parse import urlparse

import aiofiles
import cli_ui
import click
import httpx
from pymediainfo import MediaInfo

from cogs.redaction import Redaction
from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieValidator
from src.exceptions import *  # noqa F403
from src.rehostimages import RehostImagesManager
from src.takescreens import TakeScreensManager
from src.torrentcreate import TorrentCreator
from src.trackers.COMMON import COMMON
from src.uploadscreens import UploadScreensManager


class PTP:

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.rehost_images_manager = RehostImagesManager(config)
        self.takescreens_manager = TakeScreensManager(config)
        self.uploadscreens_manager = UploadScreensManager(config)
        self.tracker = 'PTP'
        self.source_flag = 'PTP'
        self.api_user = config['TRACKERS']['PTP'].get('ApiUser', '').strip()
        self.api_key = config['TRACKERS']['PTP'].get('ApiKey', '').strip()
        announce_url = config['TRACKERS']['PTP'].get('announce_url', '').strip()
        if announce_url and announce_url.startswith('http://'):
            console.print("[red]PTP announce URL is using plaintext HTTP.\n")
            console.print("[red]PTP is turning off their plaintext HTTP tracker soon. You must update your announce URLS. See PTP/forums.php?page=1&action=viewthread&threadid=46663")
            console.print("[yellow]Modifying the url to use HTTPS. Update your config file to avoid this message in the future.")
            self.announce_url = announce_url.replace('http://', 'https://').replace(':2710', '')
        else:
            self.announce_url = announce_url
        self.username = config['TRACKERS']['PTP'].get('username', '').strip()
        self.password = config['TRACKERS']['PTP'].get('password', '').strip()
        self.web_source = self._is_true(config['TRACKERS']['PTP'].get('add_web_source_to_desc', True))
        self.user_agent = f'Upload Assistant/2.3 ({platform.system()} {platform.release()})'
        self.banned_groups = ['aXXo', 'BMDru', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'd3g', 'DNL', 'FaNGDiNG0', 'HD2DVD', 'HDT', 'HDTime', 'ION10', 'iPlanet',
                              'KiNGDOM', 'mHD', 'mSD', 'nHD', 'nikt0', 'nSD', 'NhaNc3', 'OFT', 'PRODJi', 'SANTi', 'SPiRiT', 'STUTTERSHIT', 'ViSION', 'VXT',
                              'WAF', 'x0r', 'YIFY', 'LAMA', 'WORLD']
        self.approved_image_hosts = ['ptpimg', 'pixhost']

        self.sub_lang_map = {
            ("Arabic", "ara", "ar"): 22,
            ("Brazilian Portuguese", "Brazilian", "Portuguese-BR", 'pt-br', 'pt-BR'): 49,
            ("Bulgarian", "bul", "bg"): 29,
            ("Chinese", "chi", "zh", "Chinese (Simplified)", "Chinese (Traditional)", 'cmn-Hant', 'cmn-Hans', 'yue-Hant', 'yue-Hans'): 14,
            ("Croatian", "hrv", "hr", "scr"): 23,
            ("Czech", "cze", "cz", "cs"): 30,
            ("Danish", "dan", "da"): 10,
            ("Dutch", "dut", "nl"): 9,
            ("English", "eng", "en", "en-US", "en-GB", "English (CC)", "English - SDH"): 3,
            ("English - Forced", "English (Forced)", "en (Forced)", "en-US (Forced)"): 50,
            ("English Intertitles", "English (Intertitles)", "English - Intertitles", "en (Intertitles)", "en-US (Intertitles)"): 51,
            ("Estonian", "est", "et"): 38,
            ("Finnish", "fin", "fi"): 15,
            ("French", "fre", "fr", "fr-FR", "fr-CA"): 5,
            ("German", "ger", "de"): 6,
            ("Greek", "gre", "el"): 26,
            ("Hebrew", "heb", "he"): 40,
            ("Hindi", "hin", "hi"): 41,
            ("Hungarian", "hun", "hu"): 24,
            ("Icelandic", "ice", "is"): 28,
            ("Indonesian", "ind", "id"): 47,
            ("Italian", "ita", "it"): 16,
            ("Japanese", "jpn", "ja"): 8,
            ("Korean", "kor", "ko"): 19,
            ("Latvian", "lav", "lv"): 37,
            ("Lithuanian", "lit", "lt"): 39,
            ("Norwegian", "nor", "no"): 12,
            ("Polish", "pol", "pl"): 17,
            ("Portuguese", "por", "pt", "pt-PT"): 21,
            ("Romanian", "rum", "ro"): 13,
            ("Russian", "rus", "ru"): 7,
            ("Serbian", "srp", "sr", "scc"): 31,
            ("Slovak", "slo", "sk"): 42,
            ("Slovenian", "slv", "sl"): 43,
            ("Spanish", "spa", "es", "es-ES", "es-419"): 4,
            ("Swedish", "swe", "sv"): 11,
            ("Thai", "tha", "th"): 20,
            ("Turkish", "tur", "tr"): 18,
            ("Ukrainian", "ukr", "uk"): 34,
            ("Vietnamese", "vie", "vi"): 25,
        }

        self.cookie_validator = CookieValidator(config)

    def _is_true(self, value: Any) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes"}

    async def get_ptp_id_imdb(
        self,
        search_term: str,
        _search_file_folder: str,
        _meta: dict[str, Any],
    ) -> tuple[Optional[int], Optional[Union[int, str]], Optional[str]]:
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            "User-Agent": self.user_agent,
        }
        url = 'https://passthepopcorn.me/torrents.php'
        search_value = search_term or _search_file_folder
        params = {
            'searchstr': search_value,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url=url, headers=headers, params=params)
            await asyncio.sleep(1)

            if response.status_code == 200:
                data = response.json()
                movies = cast(list[dict[str, Any]], data.get('Movies', []))
                for movie in movies:
                    imdb_value = movie.get('ImdbId')
                    torrents = cast(list[dict[str, Any]], movie.get('Torrents', []) or [])
                    ptp_torrent_id: Optional[Union[int, str]] = None
                    ptp_torrent_hash: Optional[str] = None

                    normalized_search = str(search_value or '').lower()
                    if normalized_search:
                        for torrent in torrents:
                            release_name = str(torrent.get('ReleaseName', '')).lower()
                            if normalized_search in release_name:
                                ptp_torrent_id = torrent.get('Id')
                                ptp_torrent_hash = torrent.get('InfoHash')
                                break

                    if ptp_torrent_id is None and torrents:
                        first = torrents[0]
                        ptp_torrent_id = first.get('Id')
                        ptp_torrent_hash = first.get('InfoHash')

                    if imdb_value:
                        return int(imdb_value or 0), ptp_torrent_id, ptp_torrent_hash

                console.print(f'[yellow]Could not find any release matching [bold yellow]{search_value}[/bold yellow] on PTP')
                return None, None, None

            elif response.status_code in [400, 401, 403]:
                console.print("[bold red]PTP Error: 400/401/403 - Invalid request or authentication failed[/bold red]")
                return None, None, None
            elif response.status_code == 503:
                console.print("[bold yellow]PTP Unavailable (503)")
                return None, None, None
            else:
                return None, None, None
        except Exception as e:
            console.print(f'[red]An error occurred: {str(e)}[/red]')
            return None, None, None

    async def get_imdb_from_torrent_id(self, ptp_torrent_id: Union[int, str]) -> tuple[Optional[int], Optional[str]]:
        params = {
            'torrentid': ptp_torrent_id
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
        await asyncio.sleep(1)
        try:
            if response.status_code == 200:
                response = response.json()
                imdb_id = int(response.get('ImdbId', 0) or 0)
                ptp_infohash = None
                for torrent in response['Torrents']:
                    if torrent.get('Id', 0) == str(ptp_torrent_id):
                        ptp_infohash = torrent.get('InfoHash', None)
                return imdb_id, ptp_infohash
            elif int(response.status_code) in [400, 401, 403]:
                console.print(response.text)
                return None, None
            elif int(response.status_code) == 503:
                console.print("[bold yellow]PTP Unavailable (503)")
                return None, None
            else:
                return None, None
        except Exception:
            return None, None

    async def get_ptp_description(self, ptp_torrent_id: Union[int, str], meta: dict[str, Any], is_disc: str) -> list[Any]:
        params = {
            'id': ptp_torrent_id,
            'action': 'get_description'
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        console.print(f"[yellow]Requesting description from {url} with ID {ptp_torrent_id}")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
        await asyncio.sleep(1)

        ptp_desc = response.text
        # console.print(f"[yellow]Raw description received:\n{ptp_desc}...")  # Show first 500 characters for brevity
        desc = None
        imagelist: list[Any] = []
        bbcode = BBCODE()
        desc, imagelist = bbcode.clean_ptp_description(ptp_desc, is_disc)

        if not meta.get('only_id'):
            console.print("[bold green]Successfully grabbed description from PTP")
            console.print(f"Description after cleaning:\n{desc[:1000]}...", markup=False)  # Show first 1000 characters for brevity

            if not meta.get('skipit') and not meta['unattended']:
                # Allow user to edit or discard the description
                console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                edit_choice = cli_ui.ask_string("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")

                if (edit_choice or "").lower() == 'e':
                    edited_description = click.edit(desc)
                    if edited_description:
                        desc = edited_description.strip()
                        meta['description'] = desc
                        meta['saved_description'] = True
                    console.print(f"[green]Final description after editing:[/green] {desc}")
                elif (edit_choice or "").lower() == 'd':
                    desc = None
                    console.print("[yellow]Description discarded.[/yellow]")
                else:
                    console.print("[green]Keeping the original description.[/green]")
                    meta['description'] = desc
                    meta['saved_description'] = True
            else:
                meta['description'] = desc
                meta['saved_description'] = True
        imagelist = imagelist if meta.get('keep_images') else []

        return imagelist

    async def get_group_by_imdb(self, imdb: Union[int, str]) -> Optional[str]:
        params = {
            'imdb': imdb,
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url=url, headers=headers, params=params)
        await asyncio.sleep(1)
        try:
            if response.status_code != 200:
                console.print(f"[red]PTP group lookup failed with HTTP {response.status_code}[/red]")
                if response.text:
                    console.print(f"[red]Response body (truncated): {response.text[:200]}[/red]")
                return None

            try:
                response_data = response.json()
            except json.JSONDecodeError:
                content_type = response.headers.get("content-type", "unknown")
                console.print(f"[red]PTP group lookup returned non-JSON content (content-type: {content_type})[/red]")
                if response.text:
                    console.print(f"[red]Response body (truncated): {response.text[:200]}[/red]")
                return None

            if response_data.get('TotalResults'):  # Search results page
                total_results = int(response_data.get('TotalResults', 0))
                if total_results == 0:
                    console.print(f"[yellow]No results found for IMDb: tt{imdb}[/yellow]")
                    return None
                elif total_results == 1:
                    # Single result - use it
                    movie = response_data.get('Movies', [{}])[0]
                    groupID: Optional[str] = str(movie.get('GroupId')) if movie.get('GroupId') is not None else None
                    title = movie.get('Title', 'Unknown')
                    year = movie.get('Year', 'Unknown')
                    console.print(f"[green]Found single match for IMDb: [yellow]tt{imdb}[/yellow] -> Group ID: [yellow]{groupID}[/yellow][/green]")
                    console.print(f"[green]Title: [yellow]{title}[/yellow] ([yellow]{year}[/yellow])")
                    return groupID
                else:
                    # Multiple results - let user choose
                    console.print(f"[yellow]Found {total_results} matches for IMDb: tt{imdb}[/yellow]")
                    movies = cast(list[dict[str, Any]], response_data.get('Movies', []))
                    choices: list[str] = []
                    for _i, movie in enumerate(movies):
                        title = movie.get('Title', 'Unknown')
                        year = movie.get('Year', 'Unknown')
                        group_id = movie.get('GroupId', 'Unknown')
                        choice_text = f"{title} ({year}) - Group ID: {group_id}"
                        choices.append(choice_text)

                    choices.append("Skip - Don't use any of these matches")

                    try:
                        selected = cli_ui.ask_choice("Select the correct movie:", choices=choices)
                        if selected == "Skip - Don't use any of these matches":
                            console.print("[yellow]User chose to skip all matches[/yellow]")
                            return None

                        # Match selection directly to movie data to avoid index issues from cli_ui sorting
                        groupID = None
                        for movie in movies:
                            title = movie.get('Title', 'Unknown')
                            year = movie.get('Year', 'Unknown')
                            group_id = movie.get('GroupId', 'Unknown')
                            if f"{title} ({year}) - Group ID: {group_id}" == selected:
                                groupID = str(group_id)
                                break

                        console.print(f"[green]User selected: Group ID [yellow]{groupID}[/yellow][/green]")
                        return groupID

                    except KeyboardInterrupt:
                        console.print("[yellow]Selection cancelled by user[/yellow]")
                        return None
            elif response_data.get("Page") == "Browse":  # No Releases on Site with ID
                return None
            elif response_data.get('Page') == "Details":  # Group Found
                groupID = response_data.get('GroupId')
                console.print(f"[green]Matched IMDb: [yellow]tt{imdb}[/yellow] to Group ID: [yellow]{groupID}[/yellow][/green]")
                console.print(f"[green]Title: [yellow]{response_data.get('Name')}[/yellow] ([yellow]{response_data.get('Year')}[/yellow])")
                return str(groupID) if groupID is not None else None
        except Exception:
            console.print("[red]An error has occurred trying to find a group ID")
            console.print("[red]Please check that the site is online and your ApiUser/ApiKey values are correct")
            return None

        return None

    async def get_torrent_info(self, imdb: Union[int, str], meta: dict[str, Any]) -> dict[str, Any]:
        params = {
            'imdb': imdb,
            'action': 'torrent_info',
            'fast': 1
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = "https://passthepopcorn.me/ajax.php"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url=url, params=params, headers=headers)
        await asyncio.sleep(1)
        tinfo = {}
        try:
            response = response.json()
            # console.print(f"[blue]Raw info API Response: {response}[/blue]")
            # title, plot, art, year, tags, Countries, Languages
            tinfo = {key: value for key, value in response[0].items() if value not in (None, "")}
            if tinfo['tags'] == "":
                tags = self.get_tags([meta.get("genres", ""), meta.get("keywords", ""), meta['imdb_info']['genres']])
                tinfo['tags'] = ", ".join(tags)
        except Exception:
            pass
        return tinfo

    def get_torrent_info_tmdb(self, meta: dict[str, Any]) -> dict[str, Any]:
        tinfo = {
            "title": meta.get("title", ""),
            "year": meta.get("year", ""),
            "album_desc": meta.get("overview", ""),
        }
        tags = self.get_tags([meta.get("genres", ""), meta.get("keywords", "")])
        tinfo['tags'] = ", ".join(tags)
        return tinfo

    def get_tags(self, check_against: Any) -> list[str]:
        tags: list[str] = []
        ptp_tags = [
            "action", "adventure", "animation", "arthouse", "asian", "biography", "camp", "comedy",
            "crime", "cult", "documentary", "drama", "experimental", "exploitation", "family", "fantasy", "film.noir",
            "history", "horror", "martial.arts", "musical", "mystery", "performance", "philosophy", "politics", "romance",
            "sci.fi", "short", "silent", "sport", "thriller", "video.art", "war", "western"
        ]

        check_against_list = cast(list[Any], check_against) if isinstance(check_against, list) else [check_against]
        normalized_check_against: list[str] = [
            x.lower().replace(' ', '').replace('-', '') for x in check_against_list if isinstance(x, str)
        ]
        for each in ptp_tags:
            clean_tag = each.replace('.', '')
            if any(clean_tag in item for item in normalized_check_against):
                tags.append(each)

        return tags

    async def search_existing(self, groupID: Union[int, str], meta: dict[str, Any], _disctype: str) -> list[str]:
        # Map resolutions to SD / HD / UHD
        quality = None
        if meta.get('sd', 0) == 1:  # 1 is SD
            quality = "Standard Definition"
        elif meta['resolution'] in ["1440p", "1080p", "1080i", "720p"]:
            quality = "High Definition"
        elif meta['resolution'] in ["2160p", "4320p", "8640p"]:
            quality = "Ultra High Definition"

        # Prepare request parameters and headers
        params = {
            'id': groupID,
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers, params=params)
                await asyncio.sleep(1)  # Mimic server-friendly delay
                if response.status_code == 200:
                    existing: list[str] = []
                    try:
                        data = response.json()
                        torrents = cast(list[dict[str, Any]], data.get('Torrents', []))
                        existing.extend(
                            f"[{torrent.get('Resolution')}] {torrent.get('ReleaseName', 'RELEASE NAME NOT FOUND')}"
                            for torrent in torrents
                            if torrent.get('Quality') == quality and quality is not None
                        )
                    except ValueError:
                        console.print("[red]Failed to parse JSON response from API.")
                    return existing
                else:
                    console.print(f"[bold red]HTTP request failed with status code {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while trying to find existing releases.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return []

    async def ptpimg_url_rehost(self, image_url: str) -> str:
        payload = {
            'format': 'json',
            'api_key': self.config["DEFAULT"]["ptpimg_api"],
            'link-upload': image_url
        }
        headers = {'referer': 'https://ptpimg.me/index.php'}
        url = "https://ptpimg.me/upload.php"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.post(url, headers=headers, data=payload)
        try:
            response = response.json()
            ptpimg_code = response[0]['code']
            ptpimg_ext = response[0]['ext']
            img_url = f"https://ptpimg.me/{ptpimg_code}.{ptpimg_ext}"
        except Exception:
            console.print("[red]PTPIMG image rehost failed")
            img_url = image_url
            # img_url = ptpimg_upload(image_url, ptpimg_api)
        return img_url

    def get_type(self, imdb_info: dict[str, Any], meta: dict[str, Any]) -> Optional[str]:
        ptpType = None
        if imdb_info['type'] is not None:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie'):
                ptpType = "Feature Film" if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0 else "Short Film"
            if imdbType == "short":
                ptpType = "Short Film"
            elif imdbType == "tv mini series":
                ptpType = "Miniseries"
            elif imdbType == "comedy":
                ptpType = "Stand-up Comedy"
            elif imdbType == "concert":
                ptpType = "Live Performance"
        else:
            keywords = meta.get("keywords", "").lower()
            tmdb_type = meta.get("tmdb_type", "movie").lower()
            if tmdb_type == "movie":
                ptpType = "Feature Film" if int(meta.get('runtime', 60)) >= 45 or int(meta.get('runtime', 60)) == 0 else "Short Film"
            if tmdb_type == "miniseries" or "miniseries" in keywords:
                ptpType = "Miniseries"
            if "short" in keywords or "short film" in keywords:
                ptpType = "Short Film"
            elif "stand-up comedy" in keywords:
                ptpType = "Stand-up Comedy"
            elif "concert" in keywords:
                ptpType = "Live Performance"
        if ptpType is None and meta.get('mode', 'discord') == 'cli':
            ptpTypeList = ["Feature Film", "Short Film", "Miniseries", "Stand-up Comedy", "Concert", "Movie Collection"]
            ptpType = cli_ui.ask_choice("Select the proper type", choices=ptpTypeList)
            if ptpType == "Concert":
                ptpType = "Live Performance"
        return ptpType

    def get_codec(self, meta: dict[str, Any]) -> str:
        codec = ""
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
            for each in bd_sizes:
                if bdinfo['size'] < each:
                    codec = f"BD{each}"
                    break
            if not codec:
                codec = f"BD{bd_sizes[-1]}"
        elif meta['is_disc'] == "DVD":
            if "DVD5" in meta['dvd_size']:
                codec = "DVD5"
            elif "DVD9" in meta['dvd_size']:
                codec = "DVD9"
        else:
            codecmap = {
                "AVC": "H.264",
                "H.264": "H.264",
                "HEVC": "H.265",
                "H.265": "H.265",
            }
            searchcodec_value = meta.get('video_codec', meta.get('video_encode'))
            searchcodec = searchcodec_value if isinstance(searchcodec_value, str) else ''
            codec = codecmap.get(searchcodec, searchcodec)
            if meta.get('has_encode_settings') is True:
                codec = codec.replace("H.", "x")
        return codec

    def get_resolution(self, meta: dict[str, Any]) -> tuple[str, Optional[str]]:
        other_res = None
        res = meta.get('resolution', "OTHER")
        if (res == "OTHER" and meta['is_disc'] != "BDMV") or (meta['sd'] == 1 and meta['type'] == "WEBDL") or (meta['sd'] == 1 and meta['type'] == "DVDRIP"):
            video_mi = meta['mediainfo']['media']['track'][1]
            other_res = f"{video_mi['Width']}x{video_mi['Height']}"
            res = "Other"
        if meta["is_disc"] == "DVD":
            res = meta["source"].replace(" DVD", "")
        return res, other_res

    def get_container(self, meta: dict[str, Any]) -> Optional[str]:
        container = None
        if meta["is_disc"] == "BDMV":
            container = "m2ts"
        elif meta['is_disc'] == "DVD":
            container = "VOB IFO"
        else:
            ext = os.path.splitext(meta['filelist'][0])[1]
            containermap = {
                '.mkv': "MKV",
                '.mp4': 'MP4'
            }
            container = containermap.get(ext, 'Other')
        return container

    def get_source(self, source: str) -> str:
        sources = {
            "Blu-ray": "Blu-ray",
            "BluRay": "Blu-ray",
            "HD DVD": "HD-DVD",
            "HDDVD": "HD-DVD",
            "Web": "WEB",
            "HDTV": "HDTV",
            'UHDTV': 'HDTV',
            "NTSC": "DVD",
            "PAL": "DVD"
        }
        source_id = sources.get(source, "OtherR")
        return source_id

    def get_subtitles(self, meta: dict[str, Any]) -> list[int]:
        sub_lang_map = self.sub_lang_map

        sub_langs: list[int] = []
        if meta.get('is_disc', '') != 'BDMV':
            mi = meta['mediainfo']
            if meta.get('is_disc', '') == "DVD":
                mi_result = MediaInfo.parse(meta['discs'][0]['ifo'], output='JSON')
                mi_json = mi_result.to_json() if isinstance(mi_result, MediaInfo) else str(mi_result)
                mi = json.loads(mi_json)
            for track in mi['media']['track']:
                if track['@type'] == "Text":
                    language = track.get('Language_String2', track.get('Language'))
                    if language == "en":
                        if track.get('Forced', "") == "Yes":
                            language = "en (Forced)"
                        title = track.get('Title', "")
                        if isinstance(title, str) and "intertitles" in title.lower():
                            language = "en (Intertitles)"
                    for lang, subID in sub_lang_map.items():
                        if language in lang and subID not in sub_langs:
                            sub_langs.append(subID)
        else:
            for language in meta['bdinfo']['subtitles']:
                for lang, subID in sub_lang_map.items():
                    if language in lang and subID not in sub_langs:
                        sub_langs.append(subID)

        if sub_langs == []:
            sub_langs = [44]  # No Subtitle
        return sub_langs

    def get_trumpable(self, sub_langs: list[int]) -> tuple[Optional[list[int]], list[int]]:
        trumpable_values = {
            "English Hardcoded Subs (Full)": 4,
            "English Hardcoded Subs (Forced)": 50,
            "No English Subs": 14,
            "English Softsubs Exist (Mislabeled)": None,
            "Hardcoded Subs (Non-English)": "OTHER"
        }
        opts = cli_ui.select_choices("Please select any/all applicable options:", choices=list(trumpable_values.keys()))
        trumpable_list: list[int] = []
        for opt in opts:
            v = trumpable_values.get(opt)
            if v is None:
                continue
            elif v == 4:
                trumpable_list.append(4)
                if 3 not in sub_langs:
                    sub_langs.append(3)
                if 44 in sub_langs:
                    sub_langs.remove(44)
            elif v == 50:
                trumpable_list.append(50)
                if 50 not in sub_langs:
                    sub_langs.append(50)
                if 44 in sub_langs:
                    sub_langs.remove(44)
            elif v == 14:
                trumpable_list.append(14)
            elif v == "OTHER":
                trumpable_list.append(15)
                hc_sub_langs = (cli_ui.ask_string("Enter language code for HC Subtitle languages") or "").strip()
                if hc_sub_langs:
                    for lang, subID in self.sub_lang_map.items():
                        if any(hc_sub_langs == x for x in lang) and subID not in sub_langs:
                            sub_langs.append(subID)
        sub_langs_result = [*{*sub_langs}]
        trumpable_unique = [*{*trumpable_list}]
        trumpable_result: Union[list[int], None] = trumpable_unique if trumpable_unique else None
        return trumpable_result, sub_langs_result

    def get_remaster_title(self, meta: dict[str, Any]) -> str:
        remaster_title: list[str] = []
        # Collections
        # Masters of Cinema, The Criterion Collection, Warner Archive Collection
        if meta.get('distributor') in ('WARNER ARCHIVE', 'WARNER ARCHIVE COLLECTION', 'WAC'):
            remaster_title.append('Warner Archive Collection')
        elif meta.get('distributor') in ('CRITERION', 'CRITERION COLLECTION', 'CC'):
            remaster_title.append('The Criterion Collection')
        elif meta.get('distributor') in ('MASTERS OF CINEMA', 'MOC'):
            remaster_title.append('Masters of Cinema')

        # Editions
        # Director's Cut, Extended Edition, Rifftrax, Theatrical Cut, Uncut, Unrated
        if "director's cut" in meta.get('edition', '').lower():
            remaster_title.append("Director's Cut")
        elif "extended" in meta.get('edition', '').lower():
            remaster_title.append("Extended Edition")
        elif "theatrical" in meta.get('edition', '').lower() or "rifftrax" in meta.get('edition', '').lower():
            remaster_title.append("Theatrical Cut")
        elif "uncut" in meta.get('edition', '').lower():
            remaster_title.append("Uncut")
        elif "unrated" in meta.get('edition', '').lower():
            remaster_title.append("Unrated")
        else:
            if meta.get('edition') not in ('', None):
                remaster_title.append(meta['edition'])

        # Features
        # 2-Disc Set, 2in1, 2D/3D Edition, 3D Anaglyph, 3D Full SBS, 3D Half OU, 3D Half SBS,
        # 4K Restoration, 4K Remaster,
        # Extras, Remux,
        if meta.get('type') == "REMUX":
            remaster_title.append("Remux")

        # DTS:X, Dolby Atmos, Dual Audio, English Dub, With Commentary,
        if "DTS:X" in meta['audio']:
            remaster_title.append('DTS:X')
        if "Atmos" in meta['audio']:
            remaster_title.append('Dolby Atmos')
        if "Dual" in meta['audio']:
            remaster_title.append('Dual Audio')
        if "Dubbed" in meta['audio']:
            remaster_title.append('English Dub')

        # HDR10, HDR10+, Dolby Vision, 10-bit,
        # if "Hi10P" in meta.get('video_encode', ''):
        #     remaster_title.append('10-bit')
        if meta.get('hdr', '').strip() == '' and meta.get('bit_depth') == '10':
            remaster_title.append('10-bit')
        if "DV" in meta.get('hdr', ''):
            remaster_title.append('Dolby Vision')
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                remaster_title.append('HDR10+')
            else:
                remaster_title.append('HDR10')
        if "HLG" in meta.get('hdr', ''):
            remaster_title.append('HLG')

        # with commentary always last
        if meta.get('has_commentary', False) is True:
            remaster_title.append('With Commentary')

        output = " / ".join(remaster_title) if remaster_title != [] else ""
        return output

    def convert_bbcode(self, desc: str) -> str:
        desc = desc.replace("[spoiler", "[hide").replace("[/spoiler]", "[/hide]")
        desc = desc.replace("[center]", "[align=center]").replace("[/center]", "[/align]")
        desc = desc.replace("[left]", "[align=left]").replace("[/left]", "[/align]")
        desc = desc.replace("[right]", "[align=right]").replace("[/right]", "[/align]")
        desc = desc.replace("[sup]", "").replace("[/sup]", "")
        desc = desc.replace("[sub]", "").replace("[/sub]", "")
        desc = desc.replace("[alert]", "").replace("[/alert]", "")
        desc = desc.replace("[note]", "").replace("[/note]", "")
        desc = desc.replace("[h1]", "[u][b]").replace("[/h1]", "[/b][/u]")
        desc = desc.replace("[h2]", "[u][b]").replace("[/h2]", "[/b][/u]")
        desc = desc.replace("[h3]", "[u][b]").replace("[/h3]", "[/b][/u]")
        desc = desc.replace("[list]", "").replace("[/list]", "")
        desc = desc.replace("[ul]", "").replace("[/ul]", "")
        desc = desc.replace("[ol]", "").replace("[/ol]", "")
        desc = re.sub(r"\[img=[^\]]+\]", "[img]", desc)
        return desc

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        url_host_mapping = {
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
        }

        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts,
        )

    async def edit_desc(self, meta: dict[str, Any]) -> None:
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", encoding="utf-8") as base_file:
            base = await base_file.read()
        if meta.get('scene_nfo_file'):
            # Remove NFO from description
            meta_description = re.sub(
                r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]",
                "",
                base,
                flags=re.DOTALL,
            )
            base = meta_description
        multi_screens = int(self.config['DEFAULT'].get('multiScreens', 2))
        if multi_screens < 2:
            multi_screens = 2
            console.print("[yellow]PTP requires at least 2 screenshots for multi disc/file content, overriding config")

        image_list_value: Any = (meta['PTP_images_key'] if 'PTP_images_key' in meta else meta.get('image_list', [])) if not meta.get('skip_imghost_upload', False) else []
        image_list = cast(list[dict[str, Any]], image_list_value) if isinstance(image_list_value, list) else []
        images: list[dict[str, Any]] = image_list

        # Check for saved pack_image_links.json file
        pack_images_file = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "pack_image_links.json")
        pack_images_data: dict[str, Any] = {}
        if os.path.exists(pack_images_file):
            try:
                async with aiofiles.open(pack_images_file, encoding='utf-8') as f:
                    content = await f.read()
                    pack_images_data = cast(dict[str, Any], json.loads(content)) if content.strip() else {}

                    # Filter out keys with non-approved image hosts
                    keys = cast(dict[str, Any], pack_images_data.get('keys', {}))
                    keys_to_remove: list[str] = []
                    for key_name, key_data in keys.items():
                        key_data_dict = cast(dict[str, Any], key_data)
                        images_to_keep: list[dict[str, Any]] = []
                        for img in cast(list[dict[str, Any]], key_data_dict.get('images', [])):
                            raw_url = str(img.get('raw_url', ''))
                            # Extract hostname from URL (e.g., ptpimg.me -> ptpimg)
                            try:
                                parsed_url = urlparse(raw_url)
                                hostname = parsed_url.netloc
                                # Get the main domain name (first part before the dot)
                                host_key = hostname.split('.')[0] if hostname else ''

                                if host_key in self.approved_image_hosts:
                                    images_to_keep.append(img)
                                elif meta['debug']:
                                    console.print(f"[yellow]Filtering out image from non-approved host: {hostname}[/yellow]")
                            except Exception:
                                # If URL parsing fails, skip this image
                                if meta['debug']:
                                    console.print(f"[yellow]Could not parse URL: {raw_url}[/yellow]")
                                continue

                        if images_to_keep:
                            # Update the key with only approved images
                            pack_images_data['keys'][key_name]['images'] = images_to_keep
                            pack_images_data['keys'][key_name]['count'] = len(images_to_keep)
                        else:
                            # Mark key for removal if no approved images
                            keys_to_remove.append(key_name)

                    # Remove keys with no approved images
                    for key_name in keys_to_remove:
                        del pack_images_data['keys'][key_name]
                        if meta['debug']:
                            console.print(f"[yellow]Removed key '{key_name}' - no approved image hosts[/yellow]")

                    # Recalculate total count
                    keys = cast(dict[str, Any], pack_images_data.get('keys', {}))
                    pack_images_data['total_count'] = sum(cast(dict[str, Any], key_data).get('count', 0) for key_data in keys.values())

                    if pack_images_data.get('total_count', 0) < 3:
                        pack_images_data = {}  # Invalidate if less than 3 images total
                        if meta['debug']:
                            console.print("[yellow]Invalidating pack images - less than 3 approved images total[/yellow]")
                    else:
                        if meta['debug']:
                            console.print(f"[green]Loaded previously uploaded images from {pack_images_file}")
                            console.print(f"[blue]Found {pack_images_data.get('total_count', 0)} approved images across {len(pack_images_data.get('keys', {}))} keys[/blue]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load pack image data: {str(e)}[/yellow]")

        desc = io.StringIO()
        discs = cast(list[dict[str, Any]], meta.get('discs', []))
        filelist = cast(list[str], meta.get('filelist', []))

        # Handle single disc case
        if len(discs) == 1:
            each = discs[0]
            new_screens: list[str] = []
            bdinfo_keys: list[str] = []
            if each['type'] == "BDMV":
                bdinfo_keys = [key for key in each if key.startswith("bdinfo")]
                bdinfo = cast(dict[str, Any], meta.get('bdinfo', {}))
                if len(bdinfo_keys) > 1:
                    edition = str(bdinfo.get("edition", "Unknown Edition"))
                    desc.write(f"[b]{edition}[/b]\n\n")
                desc.write(f"[mediainfo]{each['summary']}[/mediainfo]\n\n")
                base2ptp = self.convert_bbcode(base)
                if base2ptp.strip() != "":
                    desc.write(base2ptp)
                    desc.write("\n\n")
                try:
                    if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                        tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                        tonemapped_header = self.convert_bbcode(tonemapped_header)
                        desc.write(tonemapped_header)
                        desc.write("\n\n")
                except Exception as e:
                    console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
                for img_index in range(len(images[:int(meta['screens'])])):
                    raw_url = str(image_list[img_index].get('raw_url', ''))
                    desc.write(f"[img]{raw_url}[/img]\n")
                desc.write("\n")
            elif each['type'] == "DVD":
                desc.write(f"[b][size=3]{each['name']}:[/size][/b]\n")
                desc.write(f"[mediainfo]{each['ifo_mi_full']}[/mediainfo]\n")
                desc.write(f"[mediainfo]{each['vob_mi_full']}[/mediainfo]\n\n")
                base2ptp = self.convert_bbcode(base)
                if base2ptp.strip() != "":
                    desc.write(base2ptp)
                    desc.write("\n\n")
                for img_index in range(len(images[:int(meta['screens'])])):
                    raw_url = image_list[img_index]['raw_url']
                    desc.write(f"[img]{raw_url}[/img]\n")
                desc.write("\n")
            if len(bdinfo_keys) > 1:
                meta['retry_count'] = meta.get('retry_count', 0)

                for i, key in enumerate(bdinfo_keys[1:], start=1):  # Skip the first bdinfo
                    new_images_key = f'new_images_playlist_{i}'
                    bdinfo = each[key]
                    edition = bdinfo.get("edition", "Unknown Edition")

                    # Find the corresponding summary for this bdinfo
                    summary_key = f"summary_{i}" if i > 0 else "summary"
                    summary = each.get(summary_key, "No summary available")

                    # Check for saved images first
                    if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                        saved_images = cast(list[dict[str, Any]], pack_images_data['keys'][new_images_key]['images'])
                        if saved_images:
                            if meta['debug']:
                                console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                            meta[new_images_key] = []
                            for img in saved_images:
                                meta[new_images_key].append({
                                    'img_url': str(img.get('img_url', '')),
                                    'raw_url': str(img.get('raw_url', '')),
                                    'web_url': str(img.get('web_url', ''))
                                })

                    if new_images_key in meta and meta[new_images_key]:
                        desc.write(f"\n[b]{edition}[/b]\n\n")
                        # Use the summary corresponding to the current bdinfo
                        desc.write(f"[mediainfo]{summary}[/mediainfo]\n\n")
                        if meta['debug']:
                            console.print("[yellow]Using original uploaded images for first disc")
                        for img in meta[new_images_key]:
                            raw_url = str(img.get('raw_url', ''))
                            desc.write(f"[img]{raw_url}[/img]\n")
                    else:
                        desc.write(f"\n[b]{edition}[/b]\n")
                        # Use the summary corresponding to the current bdinfo
                        desc.write(f"[mediainfo]{summary}[/mediainfo]\n\n")
                        meta['retry_count'] += 1
                        meta[new_images_key] = []
                        new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png"))]
                        if not new_screens:
                            use_vs = meta.get('vapoursynth', False)
                            try:
                                await self.takescreens_manager.disc_screenshots(meta, f"PLAYLIST_{i}", bdinfo, meta['uuid'], meta['base_dir'], use_vs, [], meta.get('ffdebug', False), multi_screens, True)
                            except Exception as e:
                                console.print(f"Error during BDMV screenshot capture: {e}", markup=False)
                            new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png"))]
                        uploaded_images: list[dict[str, Any]] = []
                        if new_screens and not meta.get('skip_imghost_upload', False):
                            uploaded_images, _ = await self.uploadscreens_manager.upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]}, allowed_hosts=self.approved_image_hosts)
                            if uploaded_images and not meta.get('skip_imghost_upload', False):
                                await self.save_image_links(meta, new_images_key, uploaded_images)
                            for img in uploaded_images:
                                meta[new_images_key].append({
                                    'img_url': str(img.get('img_url', '')),
                                    'raw_url': str(img.get('raw_url', '')),
                                    'web_url': str(img.get('web_url', ''))
                                })

                            for img in uploaded_images:
                                raw_url = str(img.get('raw_url', ''))
                                desc.write(f"[img]{raw_url}[/img]\n")

                        meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                        async with aiofiles.open(meta_filename, 'w', encoding='utf-8') as f:
                            await f.write(json.dumps(meta, indent=4))

        # Handle multiple discs case
        elif len(discs) > 1:
            if 'retry_count' not in meta:
                meta['retry_count'] = 0
            for i, each in enumerate(discs):
                new_images_key = f'new_images_disc_{i}'
                if each['type'] == "BDMV":
                    if i == 0:
                        desc.write(f"[mediainfo]{each['summary']}[/mediainfo]\n\n")
                        base2ptp = self.convert_bbcode(base)
                        if base2ptp.strip() != "":
                            desc.write(base2ptp)
                            desc.write("\n\n")
                        try:
                            if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                                tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                                tonemapped_header = self.convert_bbcode(tonemapped_header)
                                desc.write(tonemapped_header)
                                desc.write("\n\n")
                        except Exception as e:
                            console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
                        for img_index in range(min(multi_screens, len(image_list))):
                            raw_url = str(image_list[img_index].get('raw_url', ''))
                            desc.write(f"[img]{raw_url}[/img]\n")
                        desc.write("\n")
                    else:
                        desc.write(f"[mediainfo]{each['summary']}[/mediainfo]\n\n")
                        base2ptp = self.convert_bbcode(base)
                        if base2ptp.strip() != "":
                            desc.write(base2ptp)
                            desc.write("\n\n")
                        # Check for saved images first
                        if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                            saved_images = cast(list[dict[str, Any]], pack_images_data['keys'][new_images_key]['images'])
                            if saved_images:
                                if meta['debug']:
                                    console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                                meta[new_images_key] = []
                                for img in saved_images:
                                    meta[new_images_key].append({
                                        'img_url': str(img.get('img_url', '')),
                                        'raw_url': str(img.get('raw_url', '')),
                                        'web_url': str(img.get('web_url', ''))
                                    })
                        if new_images_key in meta and meta[new_images_key]:
                            for img in meta[new_images_key]:
                                raw_url = str(img.get('raw_url', ''))
                                desc.write(f"[img]{raw_url}[/img]\n")
                            desc.write("\n")
                        else:
                            meta['retry_count'] += 1
                            meta[new_images_key] = []
                            new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"))]
                            if not new_screens:
                                try:
                                    await self.takescreens_manager.disc_screenshots(meta, f"FILE_{i}", each['bdinfo'], meta['uuid'], meta['base_dir'], meta.get('vapoursynth', False), [], meta.get('ffdebug', False), multi_screens, True)
                                except Exception as e:
                                    console.print(f"Error during BDMV screenshot capture: {e}", markup=False)
                            new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"))]
                            uploaded_images: list[dict[str, Any]] = []
                            if new_screens and not meta.get('skip_imghost_upload', False):
                                uploaded_images, _ = await self.uploadscreens_manager.upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]}, allowed_hosts=self.approved_image_hosts)
                            if uploaded_images and not meta.get('skip_imghost_upload', False):
                                await self.save_image_links(meta, new_images_key, uploaded_images)
                                for img in uploaded_images:
                                    meta[new_images_key].append({
                                        'img_url': str(img.get('img_url', '')),
                                        'raw_url': str(img.get('raw_url', '')),
                                        'web_url': str(img.get('web_url', ''))
                                    })
                                    raw_url = str(img.get('raw_url', ''))
                                    desc.write(f"[img]{raw_url}[/img]\n")
                                desc.write("\n")

                            meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                            async with aiofiles.open(meta_filename, 'w', encoding='utf-8') as f:
                                await f.write(json.dumps(meta, indent=4))

                elif each['type'] == "DVD":
                    if i == 0:
                        desc.write(f"[b][size=3]{each['name']}:[/size][/b]\n")
                        desc.write(f"[mediainfo]{each['ifo_mi_full']}[/mediainfo]\n")
                        desc.write(f"[mediainfo]{each['vob_mi_full']}[/mediainfo]\n\n")
                        base2ptp = self.convert_bbcode(base)
                        if base2ptp.strip() != "":
                            desc.write(base2ptp)
                            desc.write("\n\n")
                        for img_index in range(min(multi_screens, len(image_list))):
                            raw_url = image_list[img_index]['raw_url']
                            desc.write(f"[img]{raw_url}[/img]\n")
                        desc.write("\n")
                    else:
                        desc.write(f"[b][size=3]{each['name']}:[/size][/b]\n")
                        desc.write(f"[mediainfo]{each['ifo_mi_full']}[/mediainfo]\n")
                        desc.write(f"[mediainfo]{each['vob_mi_full']}[/mediainfo]\n\n")
                        base2ptp = self.convert_bbcode(base)
                        if base2ptp.strip() != "":
                            desc.write(base2ptp)
                            desc.write("\n\n")
                        # Check for saved images first
                        if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                            saved_images = pack_images_data['keys'][new_images_key]['images']
                            if saved_images:
                                if meta['debug']:
                                    console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                                meta[new_images_key] = []
                                for img in saved_images:
                                    meta[new_images_key].append({
                                        'img_url': img.get('img_url', ''),
                                        'raw_url': img.get('raw_url', ''),
                                        'web_url': img.get('web_url', '')
                                    })
                        if new_images_key in meta and meta[new_images_key]:
                            for img in meta[new_images_key]:
                                raw_url = img['raw_url']
                                desc.write(f"[img]{raw_url}[/img]\n")
                            desc.write("\n")
                        else:
                            meta['retry_count'] += 1
                            meta[new_images_key] = []
                            new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png"))]
                            if not new_screens:
                                try:
                                    await self.takescreens_manager.dvd_screenshots(meta, i, multi_screens, True)
                                except Exception as e:
                                    console.print(f"Error during DVD screenshot capture: {e}", markup=False)
                            new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png"))]
                            uploaded_images: list[dict[str, Any]] = []
                            if new_screens and not meta.get('skip_imghost_upload', False):
                                uploaded_images, _ = await self.uploadscreens_manager.upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]}, allowed_hosts=self.approved_image_hosts)
                            if uploaded_images and not meta.get('skip_imghost_upload', False):
                                await self.save_image_links(meta, new_images_key, uploaded_images)
                                for img in uploaded_images:
                                    meta[new_images_key].append({
                                        'img_url': img['img_url'],
                                        'raw_url': img['raw_url'],
                                        'web_url': img['web_url']
                                    })
                                    raw_url = img['raw_url']
                                    desc.write(f"[img]{raw_url}[/img]\n")
                                desc.write("\n")

                        meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                        async with aiofiles.open(meta_filename, 'w', encoding='utf-8') as f:
                            await f.write(json.dumps(meta, indent=4))

        # Handle single file case
        elif len(filelist) == 1:
            if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description') is None and self.web_source is True:
                desc.write(f"[quote][align=center]This release is sourced from {meta['service_longname']}[/align][/quote]")
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", encoding='utf-8') as mi_file:
                mi_dump = await mi_file.read()
            desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
            base2ptp = self.convert_bbcode(base)
            if base2ptp.strip() != "":
                desc.write(base2ptp)
                desc.write("\n\n")
            if meta.get('comparison') and 'comparison_groups' in meta and meta['comparison_groups']:
                desc.write("\n")

                comparison_groups = meta['comparison_groups']
                group_keys = sorted(comparison_groups.keys(), key=lambda x: int(x))
                comparison_names = [comparison_groups[key].get('name', f'Group {key}') for key in group_keys]
                comparison_header = ', '.join(comparison_names)
                desc.write(f"[comparison={comparison_header}]\n")

                num_images = min([len(comparison_groups[key]['urls']) for key in group_keys])

                for img_index in range(num_images):
                    for key in group_keys:
                        group = comparison_groups[key]
                        if img_index < len(group['urls']):
                            img_data = group['urls'][img_index]
                            raw_url = img_data.get('raw_url', '')
                            if raw_url:
                                desc.write(f"[img]{raw_url}[/img] ")
                    desc.write("\n")

                desc.write("[/comparison]\n\n")

            try:
                if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                    tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                    tonemapped_header = self.convert_bbcode(tonemapped_header)
                    desc.write(tonemapped_header)
                    desc.write("\n\n")
            except Exception as e:
                console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")

            for img_index in range(len(images[:int(meta['screens'])])):
                raw_url = image_list[img_index]['raw_url']
                desc.write(f"[img]{raw_url}[/img]\n")
            desc.write("\n")

        # Handle multiple files case
        elif len(filelist) > 1:
            for i, file in enumerate(filelist):
                if i == 0:
                    if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description') is None and self.web_source is True:
                        desc.write(f"[quote][align=center]This release is sourced from {meta['service_longname']}[/align][/quote]")
                    base2ptp = self.convert_bbcode(base)
                    if base2ptp.strip() != "":
                        desc.write(base2ptp)
                        desc.write("\n\n")
                    async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", encoding='utf-8') as mi_file:
                        mi_dump = await mi_file.read()
                    desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                    try:
                        if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                            tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                            tonemapped_header = self.convert_bbcode(tonemapped_header)
                            desc.write(tonemapped_header)
                            desc.write("\n\n")
                    except Exception as e:
                        console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
                    for img_index in range(min(multi_screens, len(image_list))):
                        raw_url = image_list[img_index]['raw_url']
                        desc.write(f"[img]{raw_url}[/img]\n")
                    desc.write("\n")
                else:
                    mi_dump_result = MediaInfo.parse(file, output="STRING", full=False)
                    mi_dump = mi_dump_result if isinstance(mi_dump_result, str) else str(mi_dump_result)
                    temp_mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/TEMP_PTP_MEDIAINFO.txt"
                    async with aiofiles.open(temp_mi_path, "w", newline="", encoding="utf-8") as f:
                        await f.write(mi_dump.replace(file, os.path.basename(file)))
                    async with aiofiles.open(temp_mi_path, encoding="utf-8") as mi_file:
                        mi_dump = await mi_file.read()
                    desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                    new_images_key = f'new_images_file_{i}'
                    # Check for saved images first
                    if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                        saved_images = pack_images_data['keys'][new_images_key]['images']
                        if saved_images:
                            if meta['debug']:
                                console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                            meta[new_images_key] = []
                            for img in saved_images:
                                meta[new_images_key].append({
                                    'img_url': img.get('img_url', ''),
                                    'raw_url': img.get('raw_url', ''),
                                    'web_url': img.get('web_url', '')
                                })
                    if new_images_key in meta and meta[new_images_key]:
                        for img in meta[new_images_key]:
                            raw_url = img['raw_url']
                            desc.write(f"[img]{raw_url}[/img]\n")
                        desc.write("\n")
                    else:
                        meta['retry_count'] = meta.get('retry_count', 0) + 1
                        meta[new_images_key] = []
                        new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"))]
                        if not new_screens:
                            try:
                                await self.takescreens_manager.screenshots(
                                    file, f"FILE_{i}", meta['uuid'], meta['base_dir'], meta, multi_screens, True, "")
                            except Exception as e:
                                console.print(f"Error during generic screenshot capture: {e}", markup=False)
                        new_screens = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"))]
                        if new_screens and not meta.get('skip_imghost_upload', False):
                            uploaded_images, _ = await self.uploadscreens_manager.upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]}, allowed_hosts=self.approved_image_hosts)
                            if uploaded_images and not meta.get('skip_imghost_upload', False):
                                await self.save_image_links(meta, new_images_key, uploaded_images)
                            for img in uploaded_images:
                                meta[new_images_key].append({
                                    'img_url': img['img_url'],
                                    'raw_url': img['raw_url'],
                                    'web_url': img['web_url']
                                })
                                raw_url = img['raw_url']
                                desc.write(f"[img]{raw_url}[/img]\n")
                            desc.write("\n")

                    meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                    async with aiofiles.open(meta_filename, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(meta, indent=4))

        async with aiofiles.open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt",
            'w',
            encoding="utf-8",
        ) as desc_file:
            await desc_file.write(desc.getvalue())

    async def save_image_links(
        self,
        meta: dict[str, Any],
        image_key: str,
        image_list: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[str]:
        if image_list is None:
            console.print("[yellow]No image links to save.[/yellow]")
            return None

        output_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "pack_image_links.json")

        # Load existing data if the file exists
        existing_data: dict[str, Any] = {}
        if os.path.exists(output_file):
            try:
                async with aiofiles.open(output_file, encoding='utf-8') as f:
                    content = await f.read()
                    existing_data = cast(dict[str, Any], json.loads(content)) if content.strip() else {}
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load existing image data: {str(e)}[/yellow]")

        # Create data structure if it doesn't exist yet
        if not existing_data:
            existing_data = {
                "keys": {},
                "total_count": 0
            }

        # Update the data with the new images under the specific key
        keys = cast(dict[str, Any], existing_data.get("keys", {}))
        if image_key not in keys:
            keys[image_key] = {
                "count": 0,
                "images": []
            }
            existing_data["keys"] = keys

        # Add new images to the specific key
        for idx, img in enumerate(image_list):
            image_entry = {
                "index": cast(dict[str, Any], keys[image_key]).get("count", 0) + idx,
                "raw_url": str(img.get("raw_url", "")),
                "web_url": str(img.get("web_url", "")),
                "img_url": str(img.get("img_url", "")),
            }
            cast(list[dict[str, Any]], cast(dict[str, Any], keys[image_key]).get("images", [])).append(image_entry)

        # Update counts
        key_images = cast(list[dict[str, Any]], cast(dict[str, Any], keys[image_key]).get("images", []))
        cast(dict[str, Any], keys[image_key])["count"] = len(key_images)
        existing_data["total_count"] = sum(cast(dict[str, Any], key_data).get("count", 0) for key_data in keys.values())

        try:
            async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_data, indent=2))

            if meta['debug']:
                console.print(f"[green]Saved {len(image_list)} new images for key '{image_key}' (total: {existing_data['total_count']}):[/green]")
                console.print(f"[blue]  - JSON: {output_file}[/blue]")

            return output_file
        except Exception as e:
            console.print(f"[bold red]Error saving image links: {e}[/bold red]")
            return None

    async def get_AntiCsrfToken(self, meta: dict[str, Any]) -> str:
        if not os.path.exists(f"{meta['base_dir']}/data/cookies"):
            Path(f"{meta['base_dir']}/data/cookies").mkdir(parents=True, exist_ok=True)
        cookiefile = f"{meta['base_dir']}/data/cookies/PTP.json"
        loggedIn = False
        uploadresponse: Optional[httpx.Response] = None
        cookies: dict[str, str] = {}
        if os.path.exists(cookiefile):
            raw_cookies = self.cookie_validator._load_cookies_dict_secure(cookiefile)  # pyright: ignore[reportPrivateUsage]
            cookies = {name: str(data.get('value', '')) for name, data in raw_cookies.items()}
            async with httpx.AsyncClient(cookies=cookies, timeout=30.0, follow_redirects=True) as client:
                uploadresponse = await client.get("https://passthepopcorn.me/upload.php")
                loggedIn = self.validate_login(uploadresponse)
                if loggedIn is True:
                    token_match = re.search(r'data-AntiCsrfToken="(.*)"', uploadresponse.text)
                    if not token_match:
                        raise LoginException("Failed to find AntiCsrfToken on upload page.")  # noqa F405
                    AntiCsrfToken = token_match.group(1)
                    return AntiCsrfToken
        else:
            console.print("[yellow]PTP Cookies not found. Creating new session.")

        passkey_match = re.match(r"https?://please\.passthepopcorn\.me:?\d*/(.+)/announce", self.announce_url)
        if not passkey_match:
            raise LoginException("Failed to extract passkey from PTP announce URL.")  # noqa F405
        passKey = passkey_match.group(1)
        data = {
            "username": self.username,
            "password": self.password,
            "passkey": passKey,
            "keeplogged": "1",
        }
        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(cookies=cookies, timeout=30.0, follow_redirects=True) as client:
            loginresponse = await client.post("https://passthepopcorn.me/ajax.php?action=login", data=data, headers=headers)
            await asyncio.sleep(2)
            try:
                resp = loginresponse.json()
                if resp['Result'] == "TfaRequired":
                    data['TfaType'] = "normal"
                    data['TfaCode'] = cli_ui.ask_string("2FA Required: Please enter PTP 2FA code")
                    loginresponse = await client.post("https://passthepopcorn.me/ajax.php?action=login", data=data, headers=headers)
                    await asyncio.sleep(2)
                    resp = loginresponse.json()
                try:
                    if resp["Result"] != "Ok":
                        raise LoginException("Failed to login to PTP. Probably due to the bad user name, password, announce url, or 2FA code.")  # noqa F405
                    AntiCsrfToken = resp["AntiCsrfToken"]
                    self.cookie_validator._save_cookies_secure(client.cookies.jar, cookiefile)  # pyright: ignore[reportPrivateUsage]
                except Exception:
                    try:
                        parsed = json.loads(loginresponse.text)
                        redacted = Redaction.redact_private_info(parsed)
                        redacted_text = json.dumps(redacted)
                    except json.JSONDecodeError:
                        redacted_text = Redaction.redact_private_info(loginresponse.text)
                    raise LoginException(f"Got exception while loading JSON login response from PTP. Response: {redacted_text}")  # noqa F405
            except Exception:
                try:
                    parsed = json.loads(loginresponse.text)
                    redacted = Redaction.redact_private_info(parsed)
                    redacted_text = json.dumps(redacted)
                except json.JSONDecodeError:
                    redacted_text = Redaction.redact_private_info(loginresponse.text)
                raise LoginException(f"Got exception while loading JSON login response from PTP. Response: {redacted_text}")  # noqa F405
        return AntiCsrfToken

    def validate_login(self, response: httpx.Response) -> bool:
        loggedIn = False
        if response.text.find("""<a href="login.php?act=recover">""") != -1:
            console.print("Looks like you are not logged in to PTP. Probably due to the bad user name, password, or expired session.")
        elif "Your popcorn quota has been reached, come back later!" in response.text:
            raise LoginException("Your PTP request/popcorn quota has been reached, try again later")  # noqa F405
        else:
            loggedIn = True
        return loggedIn

    async def fill_upload_form(self, groupID: Optional[Union[int, str]], meta: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        resolution, other_resolution = self.get_resolution(meta)
        await self.edit_desc(meta)
        file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        desc = ""
        try:
            os.stat(file_path)  # Ensures the file is accessible
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                desc = await f.read()
        except OSError as e:
            console.print(f"File error: {e}", markup=False)
        ptp_subtitles = self.get_subtitles(meta)
        no_audio_found = False
        english_audio = False
        if meta['is_disc'] == 'BDMV':
            bdinfo = meta.get('bdinfo', {})
            audio_tracks = bdinfo.get("audio", [])
            if audio_tracks:
                first_language = str(audio_tracks[0].get("Language", "")).lower()
                if not first_language:
                    no_audio_found = True
                elif first_language.startswith("en"):
                    english_audio = True
                else:
                    english_audio = False
        else:
            mediainfo = meta.get('mediainfo', {})
            audio_tracks = [track for track in mediainfo.get("media", {}).get("track", []) if track.get("@type") == "Audio"]
            if meta['debug']:
                console.print(f"[Debug] Found {len(audio_tracks)} audio tracks")

            if not audio_tracks:
                no_audio_found = True
                console.print("[yellow]No audio tracks found in mediainfo")
            else:
                first_language = str(audio_tracks[0].get("Language", "")).lower()
                if meta['debug']:
                    console.print(f"[Debug] First audio track language: {first_language}")

                if not first_language:
                    no_audio_found = True
                elif first_language.startswith("en"):
                    english_audio = True
                else:
                    english_audio = False

        ptp_trumpable = None
        if meta.get('hardcoded_subs'):
            ptp_trumpable, ptp_subtitles = self.get_trumpable(ptp_subtitles)
            if ptp_trumpable and 50 in ptp_trumpable:
                ptp_trumpable.remove(50)
                ptp_trumpable.append(4)
            if ptp_trumpable and 14 in ptp_trumpable and 44 in ptp_subtitles:
                ptp_subtitles.remove(44)
            if ptp_trumpable and 15 in ptp_trumpable:
                ptp_trumpable.remove(15)
                ptp_trumpable.append(4)
                if 44 in ptp_subtitles:
                    ptp_subtitles.remove(44)
                if not english_audio and (not any(x in [3, 50] for x in ptp_subtitles)):
                    ptp_trumpable.append(14)

        elif no_audio_found and (not any(x in [3, 50] for x in ptp_subtitles)):
            cli_ui.info("No English subs and no audio tracks found should this be trumpable?")
            if cli_ui.ask_yes_no("Mark trumpable?", default=True):
                ptp_trumpable, ptp_subtitles = self.get_trumpable(ptp_subtitles)
        elif not english_audio and (not any(x in [3, 50] for x in ptp_subtitles)):
            cli_ui.info("No English subs and English audio is not the first audio track, should this be trumpable?")
            if cli_ui.ask_yes_no("Mark trumpable?", default=True):
                ptp_trumpable, ptp_subtitles = self.get_trumpable(ptp_subtitles)

        if meta['debug']:
            console.print("ptp_trumpable", ptp_trumpable)
            console.print("ptp_subtitles", ptp_subtitles)
        data: dict[str, Any] = {
            "submit": "true",
            "remaster_year": "",
            "remaster_title": self.get_remaster_title(meta),  # Eg.: Hardcoded English
            "type": self.get_type(meta['imdb_info'], meta),
            "codec": "Other",  # Sending the codec as custom.
            "other_codec": self.get_codec(meta),
            "container": "Other",
            "other_container": self.get_container(meta),
            "resolution": resolution,
            "source": "Other",  # Sending the source as custom.
            "other_source": self.get_source(meta['source']),
            "release_desc": desc,
            "nfo_text": "",
            "subtitles[]": ptp_subtitles,
            "trumpable[]": ptp_trumpable,
            "AntiCsrfToken": await self.get_AntiCsrfToken(meta)
        }
        if data["remaster_year"] != "" or data["remaster_title"] != "":
            data["remaster"] = "on"
        if meta.get('scene', False) is True:
            data["scene"] = "on"
        if resolution == "Other":
            data["other_resolution"] = other_resolution
        if meta.get('personalrelease', False) is True:
            data["internalrip"] = "on"
        # IF SPECIAL (idk how to check for this automatically)
            # data["special"] = "on"
        imdb_id_value = meta.get("imdb_id")
        imdb_id_int = int(imdb_id_value) if isinstance(imdb_id_value, (int, str)) else 0
        if imdb_id_int == 0:
            data["imdb"] = "0"
        else:
            data["imdb"] = str(imdb_id_int).zfill(7)
        if groupID is None:  # If need to make new group
            url = "https://passthepopcorn.me/upload.php"
            if data["imdb"] == '0':
                tinfo = self.get_torrent_info_tmdb(meta)
            else:
                imdb_value = meta.get("imdb") or "0"
                tinfo = await self.get_torrent_info(imdb_value, meta)
            if meta.get('youtube') is None or "youtube" not in str(meta.get('youtube', '')):
                youtube = "" if meta['unattended'] else cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)", default="")
                meta['youtube'] = youtube
            cover = meta["imdb_info"].get("cover")
            if cover is None:
                cover = meta.get('poster')
            if isinstance(cover, str) and "ptpimg" not in cover:
                cover = await self.ptpimg_url_rehost(cover)
            while cover is None:
                cover = cli_ui.ask_string("No Poster was found. Please input a link to a poster: \n", default="")
                if "ptpimg" not in str(cover) and str(cover).endswith(('.jpg', '.png')):
                    cover = await self.ptpimg_url_rehost(str(cover))
            new_data = {
                "title": tinfo.get("title", meta["imdb_info"].get("title", meta["title"])),
                "year": tinfo.get("year", meta["imdb_info"].get("year", meta["year"])),
                "image": cover,
                "tags": tinfo.get("tags", ""),
                "album_desc": tinfo.get("plot", meta.get("overview", "")),
                "trailer": meta.get("youtube", ""),
            }
            if new_data['year'] in ['', '0', 0, None] and meta.get('manual_year') not in [0, '', None]:
                new_data['year'] = meta['manual_year']
            while new_data["tags"] == "":
                if meta.get('mode', 'discord') == 'cli':
                    console.print('[yellow]Unable to match any tags')
                    console.print("Valid tags can be found on the PTP upload form")
                    new_data["tags"] = console.input("Please enter at least one tag. Comma separated (action, animation, short):")
            data.update(new_data)
            imdb_info = cast(dict[str, Any], meta.get("imdb_info", {}))
            directors: Union[list[str], tuple[str, ...], None] = None
            directors_value = imdb_info.get('directors')
            if isinstance(directors_value, (list, tuple)):
                director_names = [
                    str(director) for director in cast(list[Any], directors_value) if isinstance(director, str)
                ]
                directors = tuple(director_names)
            if directors:
                data["artist[]"] = directors
                data["importance[]"] = "1"
        else:  # Upload on existing group
            url = f"https://passthepopcorn.me/upload.php?groupid={groupID}"
            data["groupid"] = groupID

        return url, data

    async def upload(self, meta: dict[str, Any], url: str, data: dict[str, Any], _disctype: str, _torrent_bytes: Any = None) -> bool:
        common = COMMON(config=self.config)
        base_piece_mb = int(meta.get('base_torrent_piece_mb', 0) or 0)
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        # Check if the piece size exceeds 16 MiB and regenerate the torrent if needed
        if base_piece_mb > 16 and not meta.get('nohash', False):
            console.print("[red]Piece size is OVER 16M and does not work on PTP. Generating a new .torrent")
            tracker_url = self.announce_url.strip() if self.announce_url else "https://fake.tracker"
            piece_size = 16
            torrent_create = f"[{self.tracker}]"
            try:
                cooldown = int(self.config.get('DEFAULT', {}).get('rehash_cooldown', 0) or 0)
            except (ValueError, TypeError):
                cooldown = 0
            if cooldown > 0:
                await asyncio.sleep(cooldown)  # Small cooldown before rehashing

            await TorrentCreator.create_torrent(meta, str(meta['path']), torrent_create, tracker_url=tracker_url, piece_size=piece_size)
            await common.create_torrent_for_upload(
                meta,
                self.tracker,
                self.source_flag,
                torrent_filename=torrent_create,
                torrent_bytes=_torrent_bytes,
            )
        else:
            await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_bytes=_torrent_bytes)

        # Proceed with the upload process
        async with aiofiles.open(torrent_file_path, 'rb') as torrentFile:
            torrent_bytes = await torrentFile.read()
        files = {
            "file_input": ("placeholder.torrent", torrent_bytes, "application/x-bittorent")
        }
        headers = {
            # 'ApiUser' : self.api_user,
            # 'ApiKey' : self.api_key,
            "User-Agent": self.user_agent
        }
        if meta['debug']:
            debug_data = data.copy()
            # Redact the AntiCsrfToken
            if 'AntiCsrfToken' in debug_data:
                debug_data['AntiCsrfToken'] = '[REDACTED]'
            console.log(url)
            console.log(Redaction.redact_private_info(debug_data))
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(
                meta,
                f"{self.tracker}" + "_DEBUG",
                f"{self.tracker}" + "_DEBUG",
                announce_url="https://fake.tracker",
                torrent_bytes=_torrent_bytes,
            )
            return True  # Debug mode - simulated success
        else:
            failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]PTP_upload_failure.html"
            cookiefile = f"{meta['base_dir']}/data/cookies/PTP.json"
            raw_cookies = self.cookie_validator._load_cookies_dict_secure(cookiefile)  # pyright: ignore[reportPrivateUsage]
            cookies = {name: str(data.get('value', '')) for name, data in raw_cookies.items()}
            async with httpx.AsyncClient(cookies=cookies, timeout=60.0, follow_redirects=True) as client:
                response = await client.post(url=url, data=data, headers=headers, files=files)
            console.print(f"[cyan]{response.url}")
            responsetext = response.text
            # If the response contains our announce URL, then we are on the upload page and the upload wasn't successful.
            if responsetext.find(self.announce_url) != -1:
                # Get the error message.
                errorMessage = ""
                match = re.search(r"""<div class="alert alert--error.*?>(.+?)</div>""", responsetext)
                if match is not None:
                    errorMessage = match.group(1)

                async with aiofiles.open(failure_path, 'w', encoding='utf-8') as f:
                    await f.write(responsetext)
                meta['tracker_status'][self.tracker]['status_message'] = f"data error: see {failure_path} | {errorMessage}"

            # URL format in case of successful upload: https://passthepopcorn.me/torrents.php?id=9329&torrentid=91868
            match = re.match(r".*?passthepopcorn\.me/torrents\.php\?id=(\d+)&torrentid=(\d+)", str(response.url))
            if match is None:
                async with aiofiles.open(failure_path, 'w', encoding='utf-8') as f:
                    await f.write(responsetext)
                meta['tracker_status'][self.tracker]['status_message'] = f"data error: see {failure_path}"
                return False

            # having UA add the torrent link as a comment.
            if match:
                meta['tracker_status'][self.tracker]['status_message'] = str(response.url)
                await common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag, self.announce_url, str(response.url))
                return True
        return False
