import cli_ui
import requests
import asyncio
import re
import os
from pathlib import Path
import json
import glob
import platform
import pickle
import click
import httpx
from pymediainfo import MediaInfo
from src.trackers.COMMON import COMMON
from src.bbcode import BBCODE
from src.exceptions import *  # noqa F403
from src.console import console
from torf import Torrent
from datetime import datetime
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.uploadscreens import upload_screens
from src.torrentcreate import CustomTorrent, torf_cb, create_torrent


class PTP():

    def __init__(self, config):
        self.config = config
        self.tracker = 'PTP'
        self.source_flag = 'PTP'
        self.api_user = config['TRACKERS']['PTP'].get('ApiUser', '').strip()
        self.api_key = config['TRACKERS']['PTP'].get('ApiKey', '').strip()
        self.announce_url = config['TRACKERS']['PTP'].get('announce_url', '').strip()
        self.username = config['TRACKERS']['PTP'].get('username', '').strip()
        self.password = config['TRACKERS']['PTP'].get('password', '').strip()
        self.web_source = self._is_true(config['TRACKERS']['PTP'].get('add_web_source_to_desc', True))
        self.user_agent = f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        self.banned_groups = ['aXXo', 'BMDru', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'd3g', 'DNL', 'FaNGDiNG0', 'HD2DVD', 'HDTime', 'ION10', 'iPlanet',
                              'KiNGDOM', 'mHD', 'mSD', 'nHD', 'nikt0', 'nSD', 'NhaNc3', 'OFT', 'PRODJi', 'SANTi', 'SPiRiT', 'STUTTERSHIT', 'ViSION', 'VXT',
                              'WAF', 'x0r', 'YIFY', 'LAMA', 'WORLD']

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
            ("Hindi" "hin", "hi"): 41,
            ("Hungarian", "hun", "hu"): 24,
            ("Icelandic", "ice", "is"): 28,
            ("Indonesian", "ind", "id"): 47,
            ("Italian", "ita", "it"): 16,
            ("Japanese", "jpn", "ja"): 8,
            ("Korean", "kor", "ko"): 19,
            ("Latvian", "lav", "lv"): 37,
            ("Lithuanian", "lit", "lt"): 39,
            ("Norwegian", "nor", "no"): 12,
            ("Persian", "fa", "far"): 52,
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

    def _is_true(self, value):
        return str(value).strip().lower() in {"true", "1", "yes"}

    async def get_ptp_id_imdb(self, search_term, search_file_folder, meta):
        imdb_id = ptp_torrent_id = None
        filename = str(os.path.basename(search_term))
        params = {
            'filelist': filename
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        response = requests.get(url, params=params, headers=headers)
        await asyncio.sleep(1)
        console.print(f"[green]Searching PTP for: [bold yellow]{filename}[/bold yellow]")

        try:
            if response.status_code == 200:
                response = response.json()
                # console.print(f"[blue]Raw API Response: {response}[/blue]")

                if int(response['TotalResults']) >= 1:
                    for movie in response['Movies']:
                        if len(movie['Torrents']) >= 1:
                            for torrent in movie['Torrents']:
                                # First, try matching in filelist > path
                                for file in torrent['FileList']:
                                    if file.get('Path') == filename:
                                        imdb_id = int(movie.get('ImdbId', 0) or 0)
                                        imdb = f"tt{str(imdb_id).zfill(7)}"
                                        ptp_torrent_id = torrent['Id']
                                        dummy, ptp_torrent_hash, *_ = await self.get_imdb_from_torrent_id(ptp_torrent_id)
                                        console.print(f'[bold green]Matched release with PTP ID: [yellow]{ptp_torrent_id}[/yellow][/bold green]')

                                        # Call get_torrent_info and print the results
                                        tinfo = await self.get_torrent_info(imdb, meta)
                                        console.print(f"[cyan]Torrent Info: {tinfo}[/cyan]")

                                        return imdb_id, ptp_torrent_id, ptp_torrent_hash

                                # If no match in filelist > path, check directly in filepath
                                if torrent.get('FilePath') == filename:
                                    imdb_id = int(movie.get('ImdbId', 0) or 0)
                                    ptp_torrent_id = torrent['Id']
                                    dummy, ptp_torrent_hash, *_ = await self.get_imdb_from_torrent_id(ptp_torrent_id)
                                    console.print(f'[bold green]Matched release with PTP ID: [yellow]{ptp_torrent_id}[/yellow][/bold green]')

                                    # Call get_torrent_info and print the results
                                    tinfo = await self.get_torrent_info(imdb_id, meta)
                                    console.print(f"[cyan]Torrent Info: {tinfo}[/cyan]")

                                    return imdb_id, ptp_torrent_id, ptp_torrent_hash

                console.print(f'[yellow]Could not find any release matching [bold yellow]{filename}[/bold yellow] on PTP')
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

        console.print(f'[yellow]Could not find any release matching [bold yellow]{filename}[/bold yellow] on PTP')
        return None, None, None

    async def get_imdb_from_torrent_id(self, ptp_torrent_id):
        params = {
            'torrentid': ptp_torrent_id
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        response = requests.get(url, params=params, headers=headers)
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

    async def get_ptp_description(self, ptp_torrent_id, meta, is_disc):
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
        response = requests.get(url, params=params, headers=headers)
        await asyncio.sleep(1)

        ptp_desc = response.text
        # console.print(f"[yellow]Raw description received:\n{ptp_desc}...")  # Show first 500 characters for brevity
        desc = None
        imagelist = []
        bbcode = BBCODE()
        desc, imagelist = bbcode.clean_ptp_description(ptp_desc, is_disc)

        if not meta.get('only_id'):
            console.print("[bold green]Successfully grabbed description from PTP")
            console.print(f"Description after cleaning:\n{desc[:1000]}...", markup=False)  # Show first 1000 characters for brevity

            if not meta.get('skipit') and not meta['unattended']:
                # Allow user to edit or discard the description
                console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                edit_choice = input("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")

                if edit_choice.lower() == 'e':
                    edited_description = click.edit(desc)
                    if edited_description:
                        desc = edited_description.strip()
                        meta['description'] = desc
                        meta['saved_description'] = True
                    console.print(f"[green]Final description after editing:[/green] {desc}")
                elif edit_choice.lower() == 'd':
                    desc = None
                    console.print("[yellow]Description discarded.[/yellow]")
                else:
                    console.print("[green]Keeping the original description.[/green]")
                    meta['description'] = desc
                    meta['saved_description'] = True
            else:
                meta['description'] = desc
                meta['saved_description'] = True
        if meta.get('keep_images'):
            imagelist = imagelist
        else:
            imagelist = []

        return imagelist

    async def get_group_by_imdb(self, imdb):
        params = {
            'imdb': imdb,
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        response = requests.get(url=url, headers=headers, params=params)
        await asyncio.sleep(1)
        try:
            response = response.json()
            if response.get("Page") == "Browse":  # No Releases on Site with ID
                return None
            elif response.get('Page') == "Details":  # Group Found
                groupID = response.get('GroupId')
                console.print(f"[green]Matched IMDb: [yellow]tt{imdb}[/yellow] to Group ID: [yellow]{groupID}[/yellow][/green]")
                console.print(f"[green]Title: [yellow]{response.get('Name')}[/yellow] ([yellow]{response.get('Year')}[/yellow])")
                return groupID
        except Exception:
            console.print("[red]An error has occured trying to find a group ID")
            console.print("[red]Please check that the site is online and your ApiUser/ApiKey values are correct")
            return None

    async def get_torrent_info(self, imdb, meta):
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
        response = requests.get(url=url, params=params, headers=headers)
        await asyncio.sleep(1)
        tinfo = {}
        try:
            response = response.json()
            # console.print(f"[blue]Raw info API Response: {response}[/blue]")
            # title, plot, art, year, tags, Countries, Languages
            for key, value in response[0].items():
                if value not in (None, ""):
                    tinfo[key] = value
            if tinfo['tags'] == "":
                tags = self.get_tags([meta.get("genres", ""), meta.get("keywords", ""), meta['imdb_info']['genres']])
                tinfo['tags'] = ", ".join(tags)
        except Exception:
            pass
        return tinfo

    async def get_torrent_info_tmdb(self, meta):
        tinfo = {
            "title": meta.get("title", ""),
            "year": meta.get("year", ""),
            "album_desc": meta.get("overview", ""),
        }
        tags = await self.get_tags([meta.get("genres", ""), meta.get("keywords", "")])
        tinfo['tags'] = ", ".join(tags)
        return tinfo

    async def get_tags(self, check_against):
        tags = []
        ptp_tags = [
            "action", "adventure", "animation", "arthouse", "asian", "biography", "camp", "comedy",
            "crime", "cult", "documentary", "drama", "experimental", "exploitation", "family", "fantasy", "film.noir",
            "history", "horror", "martial.arts", "musical", "mystery", "performance", "philosophy", "politics", "romance",
            "sci.fi", "short", "silent", "sport", "thriller", "video.art", "war", "western"
        ]

        if not isinstance(check_against, list):
            check_against = [check_against]
        normalized_check_against = [
            x.lower().replace(' ', '').replace('-', '') for x in check_against if isinstance(x, str)
        ]
        for each in ptp_tags:
            clean_tag = each.replace('.', '')
            if any(clean_tag in item for item in normalized_check_against):
                tags.append(each)

        return tags

    async def search_existing(self, groupID, meta, disctype):
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                await asyncio.sleep(1)  # Mimic server-friendly delay
                if response.status_code == 200:
                    existing = []
                    try:
                        data = response.json()
                        torrents = data.get('Torrents', [])
                        for torrent in torrents:
                            if torrent.get('Quality') == quality and quality is not None:
                                existing.append(f"[{torrent.get('Resolution')}] {torrent.get('ReleaseName', 'RELEASE NAME NOT FOUND')}")
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

    async def ptpimg_url_rehost(self, image_url):
        payload = {
            'format': 'json',
            'api_key': self.config["DEFAULT"]["ptpimg_api"],
            'link-upload': image_url
        }
        headers = {'referer': 'https://ptpimg.me/index.php'}
        url = "https://ptpimg.me/upload.php"

        response = requests.post(url, headers=headers, data=payload)
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

    def get_type(self, imdb_info, meta):
        ptpType = None
        if imdb_info['type'] is not None:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie'):
                if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0:
                    ptpType = "Feature Film"
                else:
                    ptpType = "Short Film"
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
                if int(meta.get('runtime', 60)) >= 45 or int(meta.get('runtime', 60)) == 0:
                    ptpType = "Feature Film"
                else:
                    ptpType = "Short Film"
            if tmdb_type == "miniseries" or "miniseries" in keywords:
                ptpType = "Miniseries"
            if "short" in keywords or "short film" in keywords:
                ptpType = "Short Film"
            elif "stand-up comedy" in keywords:
                ptpType = "Stand-up Comedy"
            elif "concert" in keywords:
                ptpType = "Live Performance"
        if ptpType is None:
            if meta.get('mode', 'discord') == 'cli':
                ptpTypeList = ["Feature Film", "Short Film", "Miniseries", "Stand-up Comedy", "Concert", "Movie Collection"]
                ptpType = cli_ui.ask_choice("Select the proper type", choices=ptpTypeList)
                if ptpType == "Concert":
                    ptpType = "Live Performance"
        return ptpType

    def get_codec(self, meta):
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
            for each in bd_sizes:
                if bdinfo['size'] < each:
                    codec = f"BD{each}"
                    break
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
            searchcodec = meta.get('video_codec', meta.get('video_encode'))
            codec = codecmap.get(searchcodec, searchcodec)
            if meta.get('has_encode_settings') is True:
                codec = codec.replace("H.", "x")
        return codec

    def get_resolution(self, meta):
        other_res = None
        res = meta.get('resolution', "OTHER")
        if (res == "OTHER" and meta['is_disc'] != "BDMV") or (meta['sd'] == 1 and meta['type'] == "WEBDL"):
            video_mi = meta['mediainfo']['media']['track'][1]
            other_res = f"{video_mi['Width']}x{video_mi['Height']}"
            res = "Other"
        if meta["is_disc"] == "DVD":
            res = meta["source"].replace(" DVD", "")
        return res, other_res

    def get_container(self, meta):
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

    def get_source(self, source):
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

    def get_subtitles(self, meta):
        sub_lang_map = self.sub_lang_map

        sub_langs = []
        if meta.get('is_disc', '') != 'BDMV':
            mi = meta['mediainfo']
            if meta.get('is_disc', '') == "DVD":
                mi = json.loads(MediaInfo.parse(meta['discs'][0]['ifo'], output='JSON'))
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

    def get_trumpable(self, sub_langs):
        trumpable_values = {
            "English Hardcoded Subs (Full)": 4,
            "English Hardcoded Subs (Forced)": 50,
            "No English Subs": 14,
            "English Softsubs Exist (Mislabeled)": None,
            "Hardcoded Subs (Non-English)": "OTHER"
        }
        opts = cli_ui.select_choices("Please select any/all applicable options:", choices=list(trumpable_values.keys()))
        trumpable = []
        for opt in opts:
            v = trumpable_values.get(opt)
            if v is None:
                continue
            elif v == 4:
                trumpable.append(4)
                if 3 not in sub_langs:
                    sub_langs.append(3)
                if 44 in sub_langs:
                    sub_langs.remove(44)
            elif v == 50:
                trumpable.append(50)
                if 50 not in sub_langs:
                    sub_langs.append(50)
                if 44 in sub_langs:
                    sub_langs.remove(44)
            elif v == 14:
                trumpable.append(14)
            elif v == "OTHER":
                trumpable.append(15)
                hc_sub_langs = cli_ui.ask_string("Enter language code for HC Subtitle languages")
                for lang, subID in self.sub_lang_map.items():
                    if any(hc_sub_langs.strip() == x for x in list(lang)):
                        if subID not in sub_langs:
                            sub_langs.append(subID)
        sub_langs = list(set(sub_langs))
        trumpable = list(set(trumpable))
        if not trumpable:
            trumpable = None
        return trumpable, sub_langs

    def get_remaster_title(self, meta):
        remaster_title = []
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
        elif "theatrical" in meta.get('edition', '').lower():
            remaster_title.append("Theatrical Cut")
        elif "rifftrax" in meta.get('edition', '').lower():
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

        if remaster_title != []:
            output = " / ".join(remaster_title)
        else:
            output = ""
        return output

    def convert_bbcode(self, desc):
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

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding="utf-8").read()
        multi_screens = int(self.config['DEFAULT'].get('multiScreens', 2))

        # Check for saved pack_image_links.json file
        pack_images_file = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "pack_image_links.json")
        pack_images_data = {}
        if os.path.exists(pack_images_file):
            try:
                with open(pack_images_file, 'r', encoding='utf-8') as f:
                    pack_images_data = json.load(f)
                    if meta['debug']:
                        console.print(f"[green]Loaded previously uploaded images from {pack_images_file}")
                        console.print(f"[blue]Found {pack_images_data.get('total_count', 0)} previously uploaded images")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load pack image data: {str(e)}[/yellow]")

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding="utf-8") as desc:
            images = meta['image_list']
            discs = meta.get('discs', [])
            filelist = meta.get('filelist', [])

            # Handle single disc case
            if len(discs) == 1:
                each = discs[0]
                new_screens = []
                bdinfo_keys = []
                if each['type'] == "BDMV":
                    bdinfo_keys = [key for key in each if key.startswith("bdinfo")]
                    bdinfo = meta.get('bdinfo')
                    if len(bdinfo_keys) > 1:
                        edition = bdinfo.get("edition", "Unknown Edition")
                        desc.write(f"[b]{edition}[/b]\n\n")
                    desc.write(f"[mediainfo]{each['summary']}[/mediainfo]\n\n")
                    base2ptp = self.convert_bbcode(base)
                    if base2ptp.strip() != "":
                        desc.write(base2ptp)
                        desc.write("\n\n")
                    for img_index in range(len(images[:int(meta['screens'])])):
                        raw_url = meta['image_list'][img_index]['raw_url']
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
                        raw_url = meta['image_list'][img_index]['raw_url']
                        desc.write(f"[img]{raw_url}[/img]\n")
                    desc.write("\n")
                if len(bdinfo_keys) > 1:
                    if 'retry_count' not in meta:
                        meta['retry_count'] = 0

                    for i, key in enumerate(bdinfo_keys[1:], start=1):  # Skip the first bdinfo
                        new_images_key = f'new_images_playlist_{i}'
                        bdinfo = each[key]
                        edition = bdinfo.get("edition", "Unknown Edition")

                        # Find the corresponding summary for this bdinfo
                        summary_key = f"summary_{i}" if i > 0 else "summary"
                        summary = each.get(summary_key, "No summary available")

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
                            desc.write(f"\n[b]{edition}[/b]\n\n")
                            # Use the summary corresponding to the current bdinfo
                            desc.write(f"[mediainfo]{summary}[/mediainfo]\n\n")
                            if meta['debug']:
                                console.print("[yellow]Using original uploaded images for first disc")
                            for img in meta[new_images_key]:
                                raw_url = img['raw_url']
                                desc.write(f"[img]{raw_url}[/img]\n")
                        else:
                            desc.write(f"\n[b]{edition}[/b]\n")
                            # Use the summary corresponding to the current bdinfo
                            desc.write(f"[mediainfo]{summary}[/mediainfo]\n\n")
                            meta['retry_count'] += 1
                            meta[new_images_key] = []
                            new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png")
                            if not new_screens:
                                use_vs = meta.get('vapoursynth', False)
                                try:
                                    await disc_screenshots(meta, f"PLAYLIST_{i}", bdinfo, meta['uuid'], meta['base_dir'], use_vs, [], meta.get('ffdebug', False), multi_screens, True)
                                except Exception as e:
                                    print(f"Error during BDMV screenshot capture: {e}")
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png")
                            if new_screens and not meta.get('skip_imghost_upload', False):
                                uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
                                if uploaded_images and not meta.get('skip_imghost_upload', False):
                                    await self.save_image_links(meta, new_images_key, uploaded_images)
                                for img in uploaded_images:
                                    meta[new_images_key].append({
                                        'img_url': img['img_url'],
                                        'raw_url': img['raw_url'],
                                        'web_url': img['web_url']
                                    })

                                for img in uploaded_images:
                                    raw_url = img['raw_url']
                                    desc.write(f"[img]{raw_url}[/img]\n")

                            meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                            with open(meta_filename, 'w') as f:
                                json.dump(meta, f, indent=4)

            # Handle multiple discs case
            elif len(discs) > 1:
                if 'retry_count' not in meta:
                    meta['retry_count'] = 0
                if multi_screens < 2:
                    multi_screens = 2
                    console.print("[yellow]PTP requires at least 2 screenshots for multi disc content, overriding config")
                for i, each in enumerate(discs):
                    new_images_key = f'new_images_disc_{i}'
                    if each['type'] == "BDMV":
                        if i == 0:
                            desc.write(f"[mediainfo]{each['summary']}[/mediainfo]\n\n")
                            base2ptp = self.convert_bbcode(base)
                            if base2ptp.strip() != "":
                                desc.write(base2ptp)
                                desc.write("\n\n")
                            for img_index in range(min(multi_screens, len(meta['image_list']))):
                                raw_url = meta['image_list'][img_index]['raw_url']
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
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                                if not new_screens:
                                    try:
                                        await disc_screenshots(meta, f"FILE_{i}", each['bdinfo'], meta['uuid'], meta['base_dir'], meta.get('vapoursynth', False), [], meta.get('ffdebug', False), multi_screens, True)
                                    except Exception as e:
                                        print(f"Error during BDMV screenshot capture: {e}")
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                                if new_screens and not meta.get('skip_imghost_upload', False):
                                    uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
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
                                with open(meta_filename, 'w') as f:
                                    json.dump(meta, f, indent=4)

                    elif each['type'] == "DVD":
                        if i == 0:
                            desc.write(f"[b][size=3]{each['name']}:[/size][/b]\n")
                            desc.write(f"[mediainfo]{each['ifo_mi_full']}[/mediainfo]\n")
                            desc.write(f"[mediainfo]{each['vob_mi_full']}[/mediainfo]\n\n")
                            base2ptp = self.convert_bbcode(base)
                            if base2ptp.strip() != "":
                                desc.write(base2ptp)
                                desc.write("\n\n")
                            for img_index in range(min(multi_screens, len(meta['image_list']))):
                                raw_url = meta['image_list'][img_index]['raw_url']
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
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png")
                                if not new_screens:
                                    try:
                                        await dvd_screenshots(
                                            meta, i, multi_screens, True
                                        )
                                    except Exception as e:
                                        print(f"Error during DVD screenshot capture: {e}")
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png")
                                if new_screens and not meta.get('skip_imghost_upload', False):
                                    uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
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
                            with open(meta_filename, 'w') as f:
                                json.dump(meta, f, indent=4)

            # Handle single file case
            elif len(filelist) == 1:
                file = filelist[0]
                if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description', None) is None and self.web_source is True:
                    desc.write(f"[quote][align=center]This release is sourced from {meta['service_longname']}[/align][/quote]")
                mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
                desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                base2ptp = self.convert_bbcode(base)
                if base2ptp.strip() != "":
                    desc.write(base2ptp)
                    desc.write("\n\n")
                if meta.get('comparison', None):
                    if 'comparison_groups' in meta and meta['comparison_groups']:
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

                for img_index in range(len(images[:int(meta['screens'])])):
                    raw_url = meta['image_list'][img_index]['raw_url']
                    desc.write(f"[img]{raw_url}[/img]\n")
                desc.write("\n")

            # Handle multiple files case
            elif len(filelist) > 1:
                if multi_screens < 2:
                    multi_screens = 2
                    console.print("[yellow]PTP requires at least 2 screenshots for multi disc/file content, overriding config")
                for i in range(len(filelist)):
                    file = filelist[i]
                    if i == 0:
                        if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description', None) is None and self.web_source is True:
                            desc.write(f"[quote][align=center]This release is sourced from {meta['service_longname']}[/align][/quote]")
                        base2ptp = self.convert_bbcode(base)
                        if base2ptp.strip() != "":
                            desc.write(base2ptp)
                            desc.write("\n\n")
                        mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
                        desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                        for img_index in range(min(multi_screens, len(meta['image_list']))):
                            raw_url = meta['image_list'][img_index]['raw_url']
                            desc.write(f"[img]{raw_url}[/img]\n")
                        desc.write("\n")
                    else:
                        mi_dump = MediaInfo.parse(file, output="STRING", full=False)
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/TEMP_PTP_MEDIAINFO.txt", "w", newline="", encoding="utf-8") as f:
                            f.write(mi_dump.replace(file, os.path.basename(file)))
                        mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/TEMP_PTP_MEDIAINFO.txt", "r", encoding="utf-8").read()
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
                            new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                            if not new_screens:
                                try:
                                    await screenshots(
                                        file, f"FILE_{i}", meta['uuid'], meta['base_dir'], meta, multi_screens, True, None)
                                except Exception as e:
                                    print(f"Error during generic screenshot capture: {e}")
                            new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                            if new_screens and not meta.get('skip_imghost_upload', False):
                                uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
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
                        with open(meta_filename, 'w') as f:
                            json.dump(meta, f, indent=4)

    async def save_image_links(self, meta, image_key, image_list=None):
        if image_list is None:
            console.print("[yellow]No image links to save.[/yellow]")
            return None

        output_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "pack_image_links.json")

        # Load existing data if the file exists
        existing_data = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load existing image data: {str(e)}[/yellow]")

        # Create data structure if it doesn't exist yet
        if not existing_data:
            existing_data = {
                "keys": {},
                "total_count": 0
            }

        # Update the data with the new images under the specific key
        if image_key not in existing_data["keys"]:
            existing_data["keys"][image_key] = {
                "count": 0,
                "images": []
            }

        # Add new images to the specific key
        for idx, img in enumerate(image_list):
            image_entry = {
                "index": existing_data["keys"][image_key]["count"] + idx,
                "raw_url": img.get("raw_url", ""),
                "web_url": img.get("web_url", ""),
                "img_url": img.get("img_url", ""),
            }
            existing_data["keys"][image_key]["images"].append(image_entry)

        # Update counts
        existing_data["keys"][image_key]["count"] = len(existing_data["keys"][image_key]["images"])
        existing_data["total_count"] = sum(key_data["count"] for key_data in existing_data["keys"].values())

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)

            if meta['debug']:
                console.print(f"[green]Saved {len(image_list)} new images for key '{image_key}' (total: {existing_data['total_count']}):[/green]")
                console.print(f"[blue]  - JSON: {output_file}[/blue]")

            return output_file
        except Exception as e:
            console.print(f"[bold red]Error saving image links: {e}[/bold red]")
            return None

    async def get_AntiCsrfToken(self, meta):
        if not os.path.exists(f"{meta['base_dir']}/data/cookies"):
            Path(f"{meta['base_dir']}/data/cookies").mkdir(parents=True, exist_ok=True)
        cookiefile = f"{meta['base_dir']}/data/cookies/PTP.pickle"
        with requests.Session() as session:
            loggedIn = False
            if os.path.exists(cookiefile):
                with open(cookiefile, 'rb') as cf:
                    session.cookies.update(pickle.load(cf))
                uploadresponse = session.get("https://passthepopcorn.me/upload.php")
                loggedIn = await self.validate_login(uploadresponse)
            else:
                console.print("[yellow]PTP Cookies not found. Creating new session.")
            if loggedIn is True:
                AntiCsrfToken = re.search(r'data-AntiCsrfToken="(.*)"', uploadresponse.text).group(1)
            else:
                passKey = re.match(r"https?://please\.passthepopcorn\.me:?\d*/(.+)/announce", self.announce_url).group(1)
                data = {
                    "username": self.username,
                    "password": self.password,
                    "passkey": passKey,
                    "keeplogged": "1",
                }
                headers = {"User-Agent": self.user_agent}
                loginresponse = session.post("https://passthepopcorn.me/ajax.php?action=login", data=data, headers=headers)
                await asyncio.sleep(2)
                try:
                    resp = loginresponse.json()
                    if resp['Result'] == "TfaRequired":
                        data['TfaType'] = "normal"
                        data['TfaCode'] = cli_ui.ask_string("2FA Required: Please enter 2FA code")
                        loginresponse = session.post("https://passthepopcorn.me/ajax.php?action=login", data=data, headers=headers)
                        await asyncio.sleep(2)
                        resp = loginresponse.json()
                    try:
                        if resp["Result"] != "Ok":
                            raise LoginException("Failed to login to PTP. Probably due to the bad user name, password, announce url, or 2FA code.")  # noqa F405
                        AntiCsrfToken = resp["AntiCsrfToken"]
                        with open(cookiefile, 'wb') as cf:
                            pickle.dump(session.cookies, cf)
                    except Exception:
                        raise LoginException(f"Got exception while loading JSON login response from PTP. Response: {loginresponse.text}")  # noqa F405
                except Exception:
                    raise LoginException(f"Got exception while loading JSON login response from PTP. Response: {loginresponse.text}")  # noqa F405
        return AntiCsrfToken

    async def validate_login(self, response):
        loggedIn = False
        if response.text.find("""<a href="login.php?act=recover">""") != -1:
            console.print("Looks like you are not logged in to PTP. Probably due to the bad user name, password, or expired session.")
        elif "Your popcorn quota has been reached, come back later!" in response.text:
            raise LoginException("Your PTP request/popcorn quota has been reached, try again later")  # noqa F405
        else:
            loggedIn = True
        return loggedIn

    async def fill_upload_form(self, groupID, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        resolution, other_resolution = self.get_resolution(meta)
        await self.edit_desc(meta)
        file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        try:
            os.stat(file_path)  # Ensures the file is accessible
            with open(file_path, "r", encoding="utf-8") as f:
                desc = f.read()
        except OSError as e:
            print(f"File error: {e}")
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
        if meta['hardcoded-subs']:
            ptp_trumpable, ptp_subtitles = self.get_trumpable(ptp_subtitles)
            if ptp_trumpable and 50 in ptp_trumpable:
                ptp_trumpable.remove(50)
                ptp_trumpable.append(4)
            if ptp_trumpable and 14 in ptp_trumpable:
                if 44 in ptp_subtitles:
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
        data = {
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
        if resolution == "Other":
            data["other_resolution"] = other_resolution
        if meta.get('personalrelease', False) is True:
            data["internalrip"] = "on"
        # IF SPECIAL (idk how to check for this automatically)
            # data["special"] = "on"
        if int(meta.get("imdb_id")) == 0:
            data["imdb"] = "0"
        else:
            data["imdb"] = str(meta["imdb_id"]).zfill(7)

        if groupID is None:  # If need to make new group
            url = "https://passthepopcorn.me/upload.php"
            if data["imdb"] == '0':
                tinfo = await self.get_torrent_info_tmdb(meta)
            else:
                tinfo = await self.get_torrent_info(meta.get("imdb"), meta)
            if meta.get('youtube', None) is None or "youtube" not in str(meta.get('youtube', '')):
                youtube = "" if meta['unattended'] else cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)", default="")
                meta['youtube'] = youtube
            cover = meta["imdb_info"].get("cover")
            if cover is None:
                cover = meta.get('poster')
            if cover is not None and "ptpimg" not in cover:
                cover = await self.ptpimg_url_rehost(cover)
            while cover is None:
                cover = cli_ui.ask_string("No Poster was found. Please input a link to a poster: \n", default="")
                if "ptpimg" not in str(cover) and str(cover).endswith(('.jpg', '.png')):
                    cover = await self.ptpimg_url_rehost(cover)
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
                    new_data["tags"] = console.input("Please enter at least one tag. Comma seperated (action, animation, short):")
            data.update(new_data)
            if meta["imdb_info"].get("directors", None) is not None:
                data["artist[]"] = tuple(meta['imdb_info'].get('directors'))
                data["importance[]"] = "1"
        else:  # Upload on existing group
            url = f"https://passthepopcorn.me/upload.php?groupid={groupID}"
            data["groupid"] = groupID

        return url, data

    async def upload(self, meta, url, data, disctype):
        torrent_filename = f"[{self.tracker}].torrent"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{torrent_filename}"
        torrent = Torrent.read(torrent_path)

        # Check if the piece size exceeds 16 MiB and regenerate the torrent if needed
        if torrent.piece_size > 16777216:  # 16 MiB in bytes
            console.print("[red]Piece size is OVER 16M and does not work on PTP. Generating a new .torrent")
            if meta.get('mkbrr', False):
                from data.config import config
                common = COMMON(config=self.config)
                tracker_url = config['TRACKERS']['PTP'].get('announce_url', "https://fake.tracker").strip()

                # Create the torrent with the tracker URL
                torrent_create = f"[{self.tracker}]"
                create_torrent(meta, meta['path'], torrent_create, tracker_url=tracker_url)
                torrent_filename = "[PTP]"

                await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
            else:
                if meta['is_disc']:
                    include = []
                    exclude = []
                else:
                    include = ["*.mkv", "*.mp4", "*.ts"]
                    exclude = ["*.*", "*sample.mkv", "!sample*.*"]

                new_torrent = CustomTorrent(
                    meta=meta,
                    path=Path(meta['path']),
                    trackers=[self.announce_url],
                    source="Audionut",
                    private=True,
                    exclude_globs=exclude,  # Ensure this is always a list
                    include_globs=include,  # Ensure this is always a list
                    creation_date=datetime.now(),
                    comment="Created by Audionut's Upload Assistant",
                    created_by="Audionut's Upload Assistant"
                )

                # Explicitly set the piece size and update metainfo
                new_torrent.piece_size = 16777216  # 16 MiB in bytes
                new_torrent.metainfo['info']['piece length'] = 16777216  # Ensure 'piece length' is set

                # Validate and write the new torrent
                new_torrent.validate_piece_size()
                new_torrent.generate(callback=torf_cb, interval=5)
                new_torrent.write(torrent_path, overwrite=True)

        # Proceed with the upload process
        with open(torrent_path, 'rb') as torrentFile:
            files = {
                "file_input": ("placeholder.torrent", torrentFile, "application/x-bittorent")
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
                console.log(debug_data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            else:
                with requests.Session() as session:
                    cookiefile = f"{meta['base_dir']}/data/cookies/PTP.pickle"
                    with open(cookiefile, 'rb') as cf:
                        session.cookies.update(pickle.load(cf))
                    response = session.post(url=url, data=data, headers=headers, files=files)
                console.print(f"[cyan]{response.url}")
                responsetext = response.text
                # If the response contains our announce URL, then we are on the upload page and the upload wasn't successful.
                if responsetext.find(self.announce_url) != -1:
                    # Get the error message.
                    errorMessage = ""
                    match = re.search(r"""<div class="alert alert--error.*?>(.+?)</div>""", responsetext)
                    if match is not None:
                        errorMessage = match.group(1)

                    raise UploadException(f"Upload to PTP failed: {errorMessage} ({response.status_code}). (We are still on the upload page.)")  # noqa F405

                # URL format in case of successful upload: https://passthepopcorn.me/torrents.php?id=9329&torrentid=91868
                match = re.match(r".*?passthepopcorn\.me/torrents\.php\?id=(\d+)&torrentid=(\d+)", response.url)
                if match is None:
                    console.print(url)
                    console.print(data)
                    raise UploadException(f"Upload to PTP failed: result URL {response.url} ({response.status_code}) is not the expected one.")  # noqa F405

                # having UA add the torrent link as a comment.
                if match:
                    meta['tracker_status'][self.tracker]['status_message'] = response.url
                    common = COMMON(config=self.config)
                    await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), response.url)
