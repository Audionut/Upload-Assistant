import cli_ui
import requests
import asyncio
import re
import os
from pathlib import Path
from str2bool import str2bool
import json
import glob
import multiprocessing
import platform
import pickle
import click
from pymediainfo import MediaInfo
from src.trackers.COMMON import COMMON
from src.bbcode import BBCODE
from src.exceptions import *  # noqa F403
from src.console import console
from torf import Torrent
from datetime import datetime
from tempfile import NamedTemporaryFile


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
        self.web_source = str2bool(str(config['TRACKERS']['PTP'].get('add_web_source_to_desc', True)))
        self.user_agent = f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        self.banned_groups = ['aXXo', 'BMDru', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'd3g', 'DNL', 'FaNGDiNG0', 'HD2DVD', 'HDTime', 'ION10', 'iPlanet',
                              'KiNGDOM', 'mHD', 'mSD', 'nHD', 'nikt0', 'nSD', 'NhaNc3', 'OFT', 'PRODJi', 'SANTi', 'SPiRiT', 'STUTTERSHIT', 'ViSION', 'VXT',
                              'WAF', 'x0r', 'YIFY', 'LAMA', 'WORLD']

        self.sub_lang_map = {
            ("Arabic", "ara", "ar"): 22,
            ("Brazilian Portuguese", "Brazilian", "Portuguese-BR", 'pt-br'): 49,
            ("Bulgarian", "bul", "bg"): 29,
            ("Chinese", "chi", "zh", "Chinese (Simplified)", "Chinese (Traditional)"): 14,
            ("Croatian", "hrv", "hr", "scr"): 23,
            ("Czech", "cze", "cz", "cs"): 30,
            ("Danish", "dan", "da"): 10,
            ("Dutch", "dut", "nl"): 9,
            ("English", "eng", "en", "en-US", "English (CC)", "English - SDH"): 3,
            ("English - Forced", "English (Forced)", "en (Forced)", "en-US (Forced)"): 50,
            ("English Intertitles", "English (Intertitles)", "English - Intertitles", "en (Intertitles)", "en-US (Intertitles)"): 51,
            ("Estonian", "est", "et"): 38,
            ("Finnish", "fin", "fi"): 15,
            ("French", "fre", "fr"): 5,
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
            ("Portuguese", "por", "pt"): 21,
            ("Romanian", "rum", "ro"): 13,
            ("Russian", "rus", "ru"): 7,
            ("Serbian", "srp", "sr", "scc"): 31,
            ("Slovak", "slo", "sk"): 42,
            ("Slovenian", "slv", "sl"): 43,
            ("Spanish", "spa", "es"): 4,
            ("Swedish", "swe", "sv"): 11,
            ("Thai", "tha", "th"): 20,
            ("Turkish", "tur", "tr"): 18,
            ("Ukrainian", "ukr", "uk"): 34,
            ("Vietnamese", "vie", "vi"): 25,
        }

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
                                        imdb_id = movie['ImdbId']
                                        ptp_torrent_id = torrent['Id']
                                        dummy, ptp_torrent_hash, *_ = await self.get_imdb_from_torrent_id(ptp_torrent_id)
                                        console.print(f'[bold green]Matched release with PTP ID: [yellow]{ptp_torrent_id}[/yellow][/bold green]')

                                        # Call get_torrent_info and print the results
                                        tinfo = await self.get_torrent_info(imdb_id, meta)
                                        console.print(f"[cyan]Torrent Info: {tinfo}[/cyan]")

                                        return imdb_id, ptp_torrent_id, ptp_torrent_hash

                                # If no match in filelist > path, check directly in filepath
                                if torrent.get('FilePath') == filename:
                                    imdb_id = movie['ImdbId']
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
                console.print(f"[bold red]PTP: {response.text}")
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
                imdb_id = response['ImdbId']
                ptp_infohash = None
                for torrent in response['Torrents']:
                    if torrent.get('Id', 0) == str(ptp_torrent_id):
                        ptp_infohash = torrent.get('InfoHash', None)
                return imdb_id, ptp_infohash, None
            elif int(response.status_code) in [400, 401, 403]:
                console.print(response.text)
                return None, None, None
            elif int(response.status_code) == 503:
                console.print("[bold yellow]PTP Unavailable (503)")
                return None, None, None
            else:
                return None, None, None
        except Exception:
            return None, None, None

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
        # console.print(f"[yellow]Raw description received:\n{ptp_desc[:6800]}...")  # Show first 500 characters for brevity

        bbcode = BBCODE()
        desc, imagelist = bbcode.clean_ptp_description(ptp_desc, is_disc)

        console.print("[bold green]Successfully grabbed description from PTP")
        console.print(f"[cyan]Description after cleaning:[yellow]\n{desc[:1000]}...", markup=False)  # Show first 1000 characters for brevity

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
                meta['description'] = ptp_desc
                meta['saved_description'] = True
        else:
            meta['description'] = ptp_desc
            meta['saved_description'] = True

        return desc, imagelist

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
        for each in ptp_tags:
            if any(each.replace('.', '') in x for x in check_against.lower().replace(' ', '').replace('-', '')):
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

        params = {
            'id': groupID,
        }
        headers = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'User-Agent': self.user_agent
        }
        url = 'https://passthepopcorn.me/torrents.php'
        response = requests.get(url=url, headers=headers, params=params)
        await asyncio.sleep(1)
        existing = []
        try:
            response = response.json()
            torrents = response.get('Torrents', [])
            if len(torrents) != 0:
                for torrent in torrents:
                    if torrent.get('Quality') == quality and quality is not None:
                        existing.append(f"[{torrent.get('Resolution')}] {torrent.get('ReleaseName', 'RELEASE NAME NOT FOUND')}")
        except Exception:
            console.print("[red]An error has occured trying to find existing releases")
        return existing

    async def pixhost_url_rehost(self, image_url):
        url = "https://api.pixhost.to/images"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "application/json",
        }
        data = {
            'content_type': '0',
            'max_th_size': 350
        }
        try:
            with NamedTemporaryFile(delete=False) as temp_file:
                response = requests.get(image_url, stream=True)
                if response.status_code != 200:
                    console.print(f"[red]Failed to download image from URL: {image_url}")
                    return image_url

                for chunk in response.iter_content(1024):
                    temp_file.write(chunk)

                temp_file_path = temp_file.name

            with open(temp_file_path, 'rb') as image_file:
                files = {
                    'img': ('file-upload[0]', image_file)
                }
                response = requests.post(url, headers=headers, data=data, files=files, timeout=30)

                if response.status_code == 200:
                    response_data = response.json()
                    raw_url = response_data['th_url'].replace('https://t', 'https://img').replace('/thumbs/', '/images/')
                    img_url = raw_url
                    console.print(f"[green]Image successfully uploaded to Pixhost: {img_url}")
                else:
                    console.print(f"[red]Pixhost API returned an error: {response.status_code}")
                    img_url = image_url

        except Exception as e:
            console.print(f"[red]Pixhost image rehost failed: {str(e)}")
            img_url = image_url

        finally:
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        return img_url

    def get_type(self, imdb_info, meta):
        ptpType = None
        if imdb_info['type'] is not None:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie"):
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
                ptpType = "Concert"
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
                ptpType = "Concert"
        if ptpType is None:
            if meta.get('mode', 'discord') == 'cli':
                ptpTypeList = ["Feature Film", "Short Film", "Miniseries", "Stand-up Comedy", "Concert", "Movie Collection"]
                ptpType = cli_ui.ask_choice("Select the proper type", choices=ptpTypeList)
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
        opts = cli_ui.select_choices("English subtitles not found. Please select any/all applicable options:", choices=list(trumpable_values.keys()))
        trumpable = []
        if opts:
            for t, v in trumpable_values.items():
                if t in ''.join(opts):
                    if v is None:
                        break
                    elif v != 50:  # Hardcoded, Forced
                        trumpable.append(v)
                    elif v == "OTHER":  # Hardcoded, Non-English
                        trumpable.append(14)
                        hc_sub_langs = cli_ui.ask_string("Enter language code for HC Subtitle languages")
                        for lang, subID in self.sub_lang_map.items():
                            if any(hc_sub_langs.strip() == x for x in list(lang)):
                                sub_langs.append(subID)
                    else:
                        sub_langs.append(v)
                        trumpable.append(4)

        sub_langs = list(set(sub_langs))
        trumpable = list(set(trumpable))
        if trumpable == []:
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
        if meta.get('has_commentary', False) is True:
            remaster_title.append('With Commentary')

        # HDR10, HDR10+, Dolby Vision, 10-bit,
        # if "Hi10P" in meta.get('video_encode', ''):
        #     remaster_title.append('10-bit')
        if meta.get('hdr', '').strip() == '' and meta.get('bit_depth') == '10':
            remaster_title.append('10-bit')
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                remaster_title.append('HDR10+')
            else:
                remaster_title.append('HDR10')
        if "DV" in meta.get('hdr', ''):
            remaster_title.append('Dolby Vision')
        if "HLG" in meta.get('hdr', ''):
            remaster_title.append('HLG')

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
        desc = desc.replace("[code]", "[quote]").replace("[/code]", "[/quote]")
        return desc

    async def edit_desc(self, meta):
        from src.prep import Prep
        prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=self.config)
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding="utf-8").read()
        multi_screens = int(self.config['DEFAULT'].get('multiScreens', 2))

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding="utf-8") as desc:
            images = meta['image_list']
            discs = meta.get('discs', [])
            filelist = meta.get('filelist', [])

            # Handle single disc case
            if len(discs) == 1:
                each = discs[0]
                new_screens = []
                if each['type'] == "BDMV":
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
                                    use_vs = meta.get('vapoursynth', False)
                                    ds = multiprocessing.Process(target=prep.disc_screenshots, args=(meta, f"FILE_{i}", each['bdinfo'], meta['uuid'], meta['base_dir'], use_vs, [], meta.get('ffdebug', False), multi_screens, True))
                                    ds.start()
                                    while ds.is_alive() is True:
                                        await asyncio.sleep(1)
                                    new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                                if new_screens:
                                    uploaded_images, _ = prep.upload_screens(meta, multi_screens, 1, 0, 2, new_screens, {new_images_key: meta[new_images_key]})
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
                                    ds = multiprocessing.Process(target=prep.dvd_screenshots, args=(meta, i, multi_screens, True))
                                    ds.start()
                                    while ds.is_alive() is True:
                                        await asyncio.sleep(1)
                                    new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png")
                                if new_screens:
                                    uploaded_images, _ = prep.upload_screens(meta, multi_screens, 1, 0, 2, new_screens, {new_images_key: meta[new_images_key]})
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
                        mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
                        desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                        for img_index in range(min(multi_screens, len(meta['image_list']))):
                            raw_url = meta['image_list'][img_index]['raw_url']
                            desc.write(f"[img]{raw_url}[/img]\n")
                        desc.write("\n")
                    else:
                        mi_dump = MediaInfo.parse(file, output="STRING", full=False, mediainfo_options={'inform_version': '1'})
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/TEMP_PTP_MEDIAINFO.txt", "w", newline="", encoding="utf-8") as f:
                            f.write(mi_dump)
                        mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/TEMP_PTP_MEDIAINFO.txt", "r", encoding="utf-8").read()
                        desc.write(f"[mediainfo]{mi_dump}[/mediainfo]\n")
                        new_images_key = f'new_images_file_{i}'
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
                                s = multiprocessing.Process(target=prep.screenshots, args=(file, f"FILE_{i}", meta['uuid'], meta['base_dir'], meta, multi_screens, True, None))
                                s.start()
                                while s.is_alive() is True:
                                    await asyncio.sleep(3)
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                            if new_screens:
                                uploaded_images, _ = prep.upload_screens(meta, multi_screens, 1, 0, 2, new_screens, {new_images_key: meta[new_images_key]})
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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", "r", encoding='utf-8').read()
        ptp_subtitles = self.get_subtitles(meta)
        ptp_trumpable = None
        if not any(x in [3, 50] for x in ptp_subtitles) or meta['hardcoded-subs']:
            ptp_trumpable, ptp_subtitles = self.get_trumpable(ptp_subtitles)
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
        if int(str(meta.get("imdb_id", "0")).replace('tt', '')) == 0:
            data["imdb"] = "0"
        else:
            data["imdb"] = meta["imdb_id"]

        if groupID is None:  # If need to make new group
            url = "https://passthepopcorn.me/upload.php"
            if data["imdb"] == "0":
                tinfo = await self.get_torrent_info_tmdb(meta)
            else:
                tinfo = await self.get_torrent_info(meta.get("imdb_id", "0"), meta)
            cover = meta["imdb_info"].get("cover")
            if cover is None:
                cover = meta.get('poster')
            if cover is not None and "ptpimg" not in cover:
                cover = await self.pixhost_url_rehost(cover)
            while cover is None:
                cover = cli_ui.ask_string("No Poster was found. Please input a link to a poster: \n", default="")
                if "ptpimg" not in str(cover) and str(cover).endswith(('.jpg', '.png')):
                    cover = await self.pixhost_url_rehost(cover)
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
        torrent_filename = f"[{self.tracker}]{meta['clean_name']}.torrent"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{torrent_filename}"
        torrent = Torrent.read(torrent_path)

        # Check if the piece size exceeds 16 MiB and regenerate the torrent if needed
        if torrent.piece_size > 16777216:  # 16 MiB in bytes
            console.print("[red]Piece size is OVER 16M and does not work on PTP. Generating a new .torrent")

            # Import Prep and regenerate the torrent with 16 MiB piece size limit
            from src.prep import Prep
            prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=self.config)

            if meta['is_disc']:
                include = []
                exclude = []
            else:
                include = ["*.mkv", "*.mp4", "*.ts"]
                exclude = ["*.*", "*sample.mkv", "!sample*.*"]

            # Create a new torrent with piece size explicitly set to 8 MiB
            from src.prep import Prep
            prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=self.config)
            new_torrent = prep.CustomTorrent(
                meta=meta,
                path=Path(meta['path']),
                trackers=[self.announce_url],
                source="L4G",
                private=True,
                exclude_globs=exclude,  # Ensure this is always a list
                include_globs=include,  # Ensure this is always a list
                creation_date=datetime.now(),
                comment="Created by L4G's Upload Assistant",
                created_by="L4G's Upload Assistant"
            )

            # Explicitly set the piece size and update metainfo
            new_torrent.piece_size = 16777216  # 16 MiB in bytes
            new_torrent.metainfo['info']['piece length'] = 16777216  # Ensure 'piece length' is set

            # Validate and write the new torrent
            new_torrent.validate_piece_size()
            new_torrent.generate(callback=prep.torf_cb, interval=5)
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
                console.log(url)
                console.log(data)
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
