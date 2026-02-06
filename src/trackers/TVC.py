# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import re
import traceback
from datetime import datetime, timezone
from typing import Any, Optional, cast
from urllib.parse import urlparse

import aiofiles
import cli_ui
import httpx
import requests
import tmdbsimple as tmdb

from src.bbcode import BBCODE
from src.console import console
from src.rehostimages import RehostImagesManager
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class TVC:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.rehost_images_manager = RehostImagesManager(config)
        self.tracker = 'TVC'
        self.source_flag = 'TVCHAOS'
        self.upload_url = 'https://tvchaosuk.com/api/torrents/upload'
        self.search_url = 'https://tvchaosuk.com/api/torrents/filter'
        self.torrent_url = 'https://tvchaosuk.com/torrents/'
        self.signature = ""
        self.banned_groups = []
        self.approved_image_hosts = ['imgbb', 'ptpimg', 'imgbox', 'pixhost', 'bam', 'onlyimage']
        tmdb.API_KEY = config['DEFAULT']['tmdb_api']

        # TV type mapping as a dict for clarity and maintainability
        self.tv_type_map = {
            "comedy": "29",
            "current affairs": "45",
            "documentary": "5",
            "drama": "11",
            "entertainment": "14",
            "factual": "19",
            "foreign": "43",
            "kids": "32",
            "movies": "44",
            "news": "54",
            "reality": "52",
            "soaps": "30",
            "sci-fi": "33",
            "sport": "42",
            "holding bin": "53",
        }

    def format_date_ddmmyyyy(self, date_str: str) -> str:
        """
        Convert a date string from 'YYYY-MM-DD' to 'DD-MM-YYYY'.

        Args:
            date_str (str): Input date string.

        Returns:
            str: Reformatted date string, or the original if parsing fails.
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).strftime("%d-%m-%Y")
        except (ValueError, TypeError):
            return date_str

    async def get_cat_id(self, genres: str) -> str:
        """
        Determine TVC category ID based on genre list.

        Args:
            genres (str): Comma-separated genre names (e.g. "Drama, Comedy").

        Returns:
            str: Category ID string from tv_type_map. Defaults to "holding bin" if no match.
        """
        # Note sections are based on Genre not type, source, resolution etc..
        # Uses tv_type_map dict for genre → category ID mapping
        if not genres:
            return self.tv_type_map["holding bin"]
        for g in genres.split(', '):
            g = g.lower().replace(",", "").strip()
            if g and g in self.tv_type_map:
                return self.tv_type_map[g]

        # fallback to holding bin/misc id
        return self.tv_type_map["holding bin"]

    async def get_res_id(self, tv_pack: bool, resolution: str) -> str:
        if tv_pack:
            resolution_id = {
                '1080p': 'HD1080p Pack',
                '1080i': 'HD1080p Pack',
                '720p': 'HD720p Pack',
                '576p': 'SD Pack',
                '576i': 'SD Pack',
                '540p': 'SD Pack',
                '540i': 'SD Pack',
                '480p': 'SD Pack',
                '480i': 'SD Pack'
            }.get(resolution, 'SD')
        else:
            resolution_id = {
                '1080p': 'HD1080p',
                '1080i': 'HD1080p',
                '720p': 'HD720p',
                '576p': 'SD',
                '576i': 'SD',
                '540p': 'SD',
                '540': 'SD',
                '480p': 'SD',
                '480i': 'SD'
            }.get(resolution, 'SD')
        return resolution_id

    async def append_country_code(self, meta: Meta, name: str) -> str:
        """
        Append ISO country code suffix to release name based on origin_country_code.

        Args:
            meta (dict): Metadata containing 'origin_country_code' list.
            name (str): Base release name.

        Returns:
            str: Release name with appended country code (e.g. "Show Title [IRL]").
        """
        country_map = {
            "AT": "AUT",
            "AU": "AUS",
            "BE": "BEL",
            "CA": "CAN",
            "CH": "CHE",
            "CZ": "CZE",
            "DE": "GER",
            "DK": "DNK",
            "EE": "EST",
            "ES": "SPA",
            "FI": "FIN",
            "FR": "FRA",
            "IE": "IRL",
            "IS": "ISL",
            "IT": "ITA",
            "NL": "NLD",
            "NO": "NOR",
            "NZ": "NZL",
            "PL": "POL",
            "PT": "POR",
            "RU": "RUS",
            "SE": "SWE",
        }

        if 'origin_country_code' in meta:
            for code in meta['origin_country_code']:
                if code in country_map:
                    name += f" [{country_map[code]}]"
                    break  # append only the first match

        return name

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """
        Async helper to read a text file safely.
        Uses a with-block to ensure the file handle is closed.
        """
        def _read():
            with open(path, encoding=encoding) as f:
                return f.read()
        return await asyncio.to_thread(_read)

    async def check_image_hosts(self, meta: Meta) -> None:
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
            "pixhost.to": "pixhost",
            "imagebam.com": "bam",
            "onlyimage.org": "onlyimage",
        }

        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts
        )
        return

    async def upload(self, meta: Meta, _disctype: str) -> Optional[bool]:
        common = COMMON(config=self.config)

        raw_images = meta.get('TVC_images_key', meta.get('image_list', []))
        image_list_seq: list[Any]
        if isinstance(raw_images, list):
            image_list_seq = cast(list[Any], raw_images)
        elif isinstance(raw_images, tuple):
            image_list_seq = list(cast(tuple[Any, ...], raw_images))
        else:
            image_list_seq = []
        image_list = [cast(dict[str, Any], img) for img in image_list_seq]

        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        await self.get_tmdb_data(meta)

        # load MediaInfo.json
        try:
            content = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/MediaInfo.json")
            mi = cast(dict[str, Any], json.loads(content))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            console.print(f"[yellow]Warning: Could not load MediaInfo.json: {e}")
            mi = {}

        cat_id = await self.get_cat_id(meta.get('genres', '')) if meta.get('category', '') == 'TV' else '44'
        meta['language_checked'] = True

        # Foreign category check based on TMDB original_language only
        original_lang = str(meta.get("original_language", ""))
        if original_lang and not original_lang.startswith("en") and original_lang not in ["ga", "gd", "cy"]:
            cat_id = self.tv_type_map["foreign"]
        elif not original_lang:
            # Fallback: inspect audio languages from MediaInfo if TMDB data is missing
            audio_langs = self.get_audio_languages(mi)
            if audio_langs and "English" not in audio_langs:
                cat_id = self.tv_type_map["foreign"]
        resolution_id = await self.get_res_id(bool(meta.get('tv_pack', 0)), str(meta.get('resolution', '')))

        anon = 0 if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False) else 1

        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt")
        else:
            mi_dump = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt")
            bd_dump = None

        # build description and capture return instead of reopening file
        descfile_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], f"[{self.tracker}]DESCRIPTION.txt")
        desc = await self.unit3d_edit_desc(meta, self.tracker, self.signature, image_list)
        if not desc:
            console.print(f"[yellow]Warning: DESCRIPTION file not found at {descfile_path}")
            desc = ""

        # Naming logic
        if meta['type'] == "ENCODE" and ("bluray" in str(meta['path']).lower() or
                                         "brrip" in str(meta['path']).lower() or
                                         "bdrip" in str(meta['path']).lower()):
            type = "BRRip"
        else:
            type = meta['type'].replace('WEBDL', 'WEB-DL')

        if meta['category'] == "MOVIE":
            tvc_name = f"{meta['title']} ({meta['year']}) [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]"
        elif meta['category'] == "TV":
            # Use safe lookups to avoid KeyError if 'search_year' is missing
            search_year = meta.get('search_year', '')
            # If search_year is empty, fall back to year
            year = search_year if search_year else meta.get('year', '')
            if meta.get('no_year', False):
                year = ''
            year_str = f" ({year})" if year else ""

            if meta['tv_pack']:
                season_first = (meta.get('season_air_first_date') or "")[:4]
                season_year = season_first or year
                tvc_name = (
                    f"{meta['title']} - Series {meta['season_int']} ({season_year}) "
                    f"[{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]"
                )
            else:
                if 'episode_airdate' in meta:
                    formatted_date = self.format_date_ddmmyyyy(meta['episode_airdate'])
                    tvc_name = (
                        f"{meta['title']}{year_str} {meta['season']}{meta['episode']} "
                        f"({formatted_date}) [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]"
                    )
                else:
                    tvc_name = (
                        f"{meta['title']}{year_str} {meta['season']}{meta['episode']} "
                        f"[{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]"
                    )
        else:
            # Defensive guard for unsupported categories
            raise ValueError(f"Unsupported category for TVC: {meta.get('category')}")

        # Add original language title if foreign
        if cat_id == self.tv_type_map["foreign"] and meta.get('original_title') and meta['original_title'] != meta['title']:
            tvc_name = tvc_name.replace(meta['title'], f"{meta['title']} ({meta['original_title']})")

        if not meta['is_disc']:
            # Pass the full MediaInfo dict; get_subs_info handles missing/invalid data internally
            self.get_subs_info(meta, mi)

        if meta['video_codec'] == 'HEVC':
            tvc_name = tvc_name.replace(']', ' HEVC]')
        if meta.get('eng_subs'):
            tvc_name = tvc_name.replace(']', ' SUBS]')
        if meta.get('sdh_subs'):
            tvc_name = tvc_name.replace(' SUBS]', ' (ENG + SDH SUBS)]') if meta.get('eng_subs') else tvc_name.replace(']', ' (SDH SUBS)]')

        tvc_name = await self.append_country_code(meta, tvc_name)

        upload_to_tvc = True
        if meta.get('unattended', False) is False:
            upload_to_tvc = cli_ui.ask_yes_no(f"Upload to {self.tracker} with the name {tvc_name}?", default=False)
            if not upload_to_tvc:
                tvc_name = cli_ui.ask_string("Please enter New Name:") or tvc_name
                upload_to_tvc = cli_ui.ask_yes_no(f"Upload to {self.tracker} with the name {tvc_name}?", default=False)

        data = {
            'name': tvc_name,
            'description': desc.replace('\n', '<br>').replace('\r', '<br>'),
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
        }
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')

        if upload_to_tvc is False:
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        if meta['debug'] is False:
            response = None
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with aiofiles.open(torrent_path, "rb") as open_torrent:
                        torrent_bytes = await open_torrent.read()
                    files = {'torrent': (os.path.basename(torrent_path), torrent_bytes)}
                    response = await client.post(
                        self.upload_url,
                        files=files,
                        data=data,
                        headers={'User-Agent': 'Mozilla/5.0'},
                        params={'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()}
                    )

                if response.status_code != 200:
                    if response.status_code == 403:
                        meta['tracker_status'][self.tracker]['status_message'] = (
                            "data error: Forbidden (403). This may indicate that you do not have upload permission."
                        )
                    elif response.status_code in (301, 302, 303, 307, 308):
                        meta['tracker_status'][self.tracker]['status_message'] = (
                            f"data error: Redirect ({response.status_code}). Please verify that your API key is valid."
                        )
                    else:
                        meta['tracker_status'][self.tracker]['status_message'] = (
                            f"data error: HTTP {response.status_code} - {response.text}"
                        )
                    return
                # TVC returns "application/x-bittorrent\n{json}" so strip the prefix
                json_data = json.loads(response.text.split('\n', 1)[-1])
                meta['tracker_status'][self.tracker]['status_message'] = json_data

                # Extract torrent ID robustly from returned URL
                data_str = json_data.get('data')
                if not isinstance(data_str, str):
                    raise ValueError(f"Invalid TVC response: 'data' missing or not a string: {data_str}")

                parsed = urlparse(data_str)
                segments = [seg for seg in parsed.path.split("/") if seg]
                if not segments:
                    raise ValueError(f"Invalid TVC response format: no path segments in {data_str}")

                # Use last segment as torrent ID
                t_id = segments[-1]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id

                await common.create_torrent_ready_to_seed(
                    meta,
                    self.tracker,
                    self.source_flag,
                    self.config['TRACKERS'][self.tracker].get('announce_url'),
                    f"https://tvchaosuk.com/torrents/{t_id}"
                )
                return True

            except httpx.TimeoutException:
                meta['tracker_status'][self.tracker]['status_message'] = 'data error: Request timed out after 30 seconds'
                return False
            except httpx.RequestError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e}.\nResponse: {(response.text) if response else "No response"}'
                return False
            except Exception as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {(response.text) if response else "No response"}'
                return False

        else:
            console.print("[cyan]TVC Request Data:")
            console.print(data)
            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
            tracker_status.setdefault(self.tracker, {})
            tracker_status[self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success

    def get_audio_languages(self, mi: dict[str, Any]) -> list[str]:
        """
        Parse MediaInfo object and return a list of normalized audio languages.

        Args:
            mi (dict): MediaInfo JSON object.

        Returns:
            list[str]: Sorted list of audio language names (e.g. ["English", "French"]).
        """
        audio_langs: set[str] = set()
        tracks = cast(list[dict[str, Any]], mi.get("media", {}).get("track", []))
        for track in tracks:
            if track.get("@type") != "Audio":
                continue
            lang_val = (
                track.get("Language/String")
                or track.get("Language/String1")
                or track.get("Language/String2")
                or track.get("Language")
            )
            lang = str(lang_val).strip() if lang_val else ""
            if not lang:
                continue
            lowered = lang.lower()
            if lowered in {"en", "eng", "en-us", "en-gb", "en-ie", "en-au"}:
                audio_langs.add("English")
            else:
                audio_langs.add(lang.title())
        return sorted(audio_langs) if audio_langs else []

    async def get_tmdb_data(self, meta: Meta) -> dict[str, Any]:
        # Origin country codes (shared for both movies and TV)
        origin_country_code: list[str] = []
        origin_country = meta.get('origin_country')
        if origin_country:
            if isinstance(origin_country, list):
                origin_country_list = cast(list[Any], origin_country)
                origin_country_code.extend([str(code) for code in origin_country_list])
            else:
                origin_country_code.append(str(origin_country))
        elif len(meta.get('production_countries', [])):
            production_countries = cast(list[dict[str, Any]], meta.get('production_countries', []))
            origin_country_code.extend(
                [
                    str(country['iso_3166_1'])
                    for country in production_countries
                    if 'iso_3166_1' in country
                ]
            )
        elif len(meta.get('production_companies', [])):
            production_companies = cast(list[dict[str, Any]], meta.get('production_companies', []))
            origin_country_code.append(str(production_companies[0].get('origin_country', '')))
        meta['origin_country_code'] = origin_country_code

        if meta['category'] == "MOVIE":
            # Everything movie-specific is already handled
            if meta['debug']:
                console.print("[yellow]Fetching TMDb movie details[/yellow]")
                movie = tmdb.Movies(meta['tmdb'])
                response = cast(Any, movie).info()
                console.print(f"[cyan]DEBUG: Movie data: {response}[/cyan]")
            return {}

        elif meta['category'] == "TV":
            # TVC-specific extras
            if meta.get('networks') and len(meta['networks']) != 0 and 'name' in meta['networks'][0]:
                meta['networks'] = meta['networks'][0]['name']

            try:
                if not meta['tv_pack']:
                    if 'tmdb_episode_data' not in meta or not meta['tmdb_episode_data']:
                        episode_info = cast(
                            dict[str, Any],
                            cast(Any, tmdb.TV_Episodes(meta['tmdb'], meta['season_int'], meta['episode_int'])).info(),
                        )
                        meta['episode_airdate'] = episode_info.get('air_date', '')
                        meta['episode_name'] = episode_info.get('name', '')
                        meta['episode_overview'] = episode_info.get('overview', '')
                    else:
                        episode_info = cast(dict[str, Any], meta['tmdb_episode_data'])
                        meta['episode_airdate'] = episode_info.get('air_date', '')
                        meta['episode_name'] = episode_info.get('name', '')
                        meta['episode_overview'] = episode_info.get('overview', '')
                else:
                    if 'tmdb_season_data' not in meta or not meta['tmdb_season_data']:
                        season_info = cast(
                            dict[str, Any],
                            cast(Any, tmdb.TV_Seasons(meta['tmdb'], meta['season_int'])).info(),
                        )
                        air_date = season_info.get('air_date') or ""
                        meta['season_air_first_date'] = air_date
                        meta['season_name'] = season_info.get('name', f"Season {meta['season_int']}")
                        episodes: list[dict[str, str]] = []
                        for ep in cast(list[dict[str, Any]], season_info.get('episodes', [])):
                            season_num = str(ep.get('season_number', 0))
                            episode_num = str(ep.get('episode_number', 0))
                            code = f"S{season_num.zfill(2)}E{episode_num.zfill(2)}"
                            episodes.append({
                                "code": code,
                                "title": (ep.get("name") or "").strip(),
                                "airdate": ep.get("air_date") or "",
                                "overview": (ep.get("overview") or "").strip()
                            })
                        meta['episodes'] = episodes
                    else:
                        season_info = cast(dict[str, Any], meta['tmdb_season_data'])
                        air_date = season_info.get('air_date') or ""
                        meta['season_air_first_date'] = air_date
                        meta['season_name'] = season_info.get('name', f"Season {meta['season_int']}")
                        episodes = []
                        for ep in cast(list[dict[str, Any]], season_info.get('episodes', [])):
                            season_num = str(ep.get('season_number', 0))
                            episode_num = str(ep.get('episode_number', 0))
                            code = f"S{season_num.zfill(2)}E{episode_num.zfill(2)}"
                            episodes.append({
                                "code": code,
                                "title": (ep.get("name") or "").strip(),
                                "airdate": ep.get("air_date") or "",
                                "overview": (ep.get("overview") or "").strip()
                            })
                        meta['episodes'] = episodes

            except (requests.exceptions.RequestException, KeyError, TypeError) as e:
                console.print(f"[yellow]Expected error while fetching TV episode/season info: {e}")
                console.print(traceback.format_exc())

                console.print(
                    f"Unable to get episode information, Make sure episode {meta['season']}{meta['episode']} exists in TMDB.\n"
                    f"https://www.themoviedb.org/tv/{meta['tmdb']}/season/{meta['season_int']}"
                )
                meta.setdefault('season_air_first_date', f"{meta['year']}-N/A-N/A")
                meta.setdefault('first_air_date', f"{meta['year']}-N/A-N/A")

        else:
            raise ValueError(f"Unsupported category for TVC: {meta.get('category')}")

        return {}

    async def search_existing(self, meta: Meta, _disctype: Optional[str] = None) -> list[dict[str, Any]]:
        # Search on TVCUK has been DISABLED due to issues, but we can still skip uploads based on criteria
        dupes: list[dict[str, Any]] = []

        # UHD, Discs, remux and non-1080p HEVC are not allowed on TVC.
        if meta['resolution'] == '2160p' or (meta['is_disc'] or "REMUX" in meta['type']) or (meta['video_codec'] == 'HEVC' and meta['resolution'] != '1080p'):
            console.print("[bold red]No UHD, Discs, Remuxes or non-1080p HEVC allowed at TVC[/bold red]")
            meta['skipping'] = "TVC"
            return []

        console.print("[red]Cannot search for dupes on TVC at this time.[/red]")
        console.print("[red]Please make sure you are not uploading duplicates.")
        await asyncio.sleep(2)

        return dupes

    async def unit3d_edit_desc(
        self,
        meta: Meta,
        tracker: str,
        signature: str,
        image_list: list[dict[str, Any]],
        comparison: bool = False,
    ) -> str:
        """
        Build and write the tracker-specific DESCRIPTION.txt file.

        Constructs BBCode-formatted description text for discs, TV packs,
        episodes, or movies, including screenshots and notes. Always writes
        a non-empty description file to tmp/<uuid>/[TVC]DESCRIPTION.txt.

        Args:
            meta (dict): Metadata dictionary for the release.
            tracker (str): Tracker name (e.g. "TVC").
            signature (str): Optional signature string to append.
            image_list (list): List of screenshot image dicts.
            comparison (bool): Whether to include comparison collapse blocks.

        Returns:
            str: The final BBCode description string (also written to file).
        """
        try:
            base = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt")
        except FileNotFoundError:
            base = ""

        # Ensure tmp/<uuid> directory exists
        desc_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        os.makedirs(desc_dir, exist_ok=True)
        descfile_path = os.path.join(desc_dir, f"[{tracker}]DESCRIPTION.txt")

        bbcode = BBCODE()
        desc = ""

        # DISCS
        if meta.get('discs', []):
            discs = meta['discs']
            if discs[0]['type'] == "DVD":
                desc += f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n\n"
            for each in discs[1:]:
                if each['type'] == "BDMV":
                    desc += f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n"
                if each['type'] == "DVD":
                    desc += f"{each['name']}:\n"
                    desc += (
                        f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler] "
                        f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n"
                    )

        # MOVIE RELEASE INFO
        rd_info = ""
        if meta['category'] == "MOVIE":
            if 'release_dates' in meta:
                for cc in meta['release_dates']['results']:
                    for rd in cc['release_dates']:
                        if rd['type'] == 6:
                            channel = str(rd['note']) if str(rd['note']) != "" else "N/A Channel"
                            rd_info += (
                                f"[color=orange][size=15]{cc['iso_3166_1']} TV Release info [/size][/color]\n"
                                f"{str(rd['release_date'])[:10]} on {channel}\n"
                            )
            else:
                rd_info = meta.get('release_date', '')

            if rd_info:
                desc += f"[center]{rd_info}[/center]\n\n"

        # TV PACK LAYOUT
        if meta['category'] == "TV" and meta.get('tv_pack') == 1 and 'season_air_first_date' in meta:

            channel = meta.get('networks', 'N/A')
            airdate = self.format_date_ddmmyyyy(meta.get('season_air_first_date') or "")

            desc += "[center]"
            if meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n"

            desc += f"[b]Series Title:[/b] {meta.get('season_name', 'Unknown Series')}\n"
            desc += f"[b]This series premiered on:[/b] {channel} on {airdate}\n"

            if meta.get('episodes'):
                desc += "\n[b]Episode List[/b]\n"
                for ep in meta['episodes']:
                    ep_num = ep.get('code', '')
                    ep_title = ep.get('title', '').strip()
                    ep_date = ep.get('airdate', '')
                    ep_overview = ep.get('overview', '').strip()

                    desc += f"[b]{ep_num}[/b]"
                    if ep_title:
                        desc += f" - {ep_title}"
                    if ep_date:
                        formatted_date = self.format_date_ddmmyyyy(ep_date)
                        desc += f" ({formatted_date})"
                    desc += "\n"

                    if ep_overview:
                        desc += f"{ep_overview}\n"

            desc += self.get_links(meta)

            screens_count = int(meta.get('screens', 0) or 0)
            if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                desc += "\n[b]Screenshots[/b]\n"
                for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                    web_url = each['web_url']
                    img_url = each['img_url']
                    desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"

            desc += "\n[/center]\n\n"

        # EPISODE LAYOUT
        elif meta['category'] == "TV" and meta.get('tv_pack') != 1 and 'episode_overview' in meta:

            desc += "[center]"
            if meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n"

            episode_name = str(meta.get('episode_name', '')).strip()
            overview = str(meta.get('episode_overview', '')).strip()

            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', overview) if s.strip()]
            if not sentences and overview:
                sentences = [overview]

            if episode_name:
                desc += f"[b]Episode Title:[/b] {episode_name}\n"

            for s in sentences:
                desc += s.rstrip() + "\n"

            if 'episode_airdate' in meta:
                channel = meta.get('networks', 'N/A')
                formatted_date = self.format_date_ddmmyyyy(meta['episode_airdate'])
                desc += f"[b]Broadcast on:[/b] {channel} on {formatted_date}\n"

            desc += self.get_links(meta)

            screens_count = int(meta.get('screens', 0) or 0)
            if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                desc += "\n[b]Screenshots[/b]\n"
                for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                    web_url = each['web_url']
                    img_url = each['img_url']
                    desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"

            desc += "\n[/center]\n\n"

        # MOVIE / FALLBACK
        else:
            overview = str(meta.get('overview', '')).strip()
            desc += "[center]"
            if meta['category'].upper() == "MOVIE" and meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n"

            if meta['category'].upper() == "MOVIE":
                desc += f"[b]Movie Title:[/b] {meta.get('title', 'Unknown Movie')}\n"
                desc += overview + "\n"
                if 'release_date' in meta:
                    formatted_date = self.format_date_ddmmyyyy(meta['release_date'])
                    desc += f"[b]Released on:[/b] {formatted_date}\n"

                desc += self.get_links(meta)

                screens_count = int(meta.get('screens', 0) or 0)
                if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                    desc += "\n[b]Screenshots[/b]\n"
                    for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                        web_url = each['web_url']
                        img_url = each['img_url']
                        desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"

                desc += "\n[/center]\n\n"
            else:
                desc += overview + "\n[/center]\n\n"

        # NOTES
        notes_content = base.strip()
        if notes_content and notes_content.lower() != "ptp":
            desc += f"[center][b]Notes / Extra Info[/b]\n{notes_content}\n[/center]\n\n"

        # BBCode conversions
        desc = bbcode.convert_pre_to_code(desc)
        desc = bbcode.convert_hide_to_spoiler(desc)
        if not comparison:
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)

        # MINIMAL TVC FIX
        desc = desc.replace("[center]\n", "[center]")
        desc = desc.replace("\n\n", "\n")

        # Fallback
        if not desc.strip():
            desc = "[center][i]No description available[/i][/center]\n"

        if signature:
            desc += f"\n{signature}\n"

        # Write description asynchronously
        def _write():
            with open(descfile_path, "w", encoding="utf-8") as f:
                f.write(desc)

        await asyncio.to_thread(_write)
        return desc


    def get_links(self, meta: Meta) -> str:
        """
        Returns a BBCode string with an 'External Info Sources' heading and icon links.
        No [center] tags are included; callers control layout.
        """
        parts: list[str] = []

        parts.append("\n[b]External Info Sources:[/b]\n\n")

        if meta.get('imdb_id', 0):
            parts.append(f"[URL={meta.get('imdb_info', {}).get('imdb_url', '')}][img]{self.config['IMAGES']['imdb_75']}[/img][/URL]")

        if meta.get('tmdb_id', 0):
            parts.append(f"[URL=https://www.themoviedb.org/{meta.get('category', '').lower()}/{meta['tmdb_id']}][img]{self.config['IMAGES']['tmdb_75']}[/img][/URL]")

        if meta.get('tvdb_id', 0):
            parts.append(f"[URL=https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series][img]{self.config['IMAGES']['tvdb_75']}[/img][/URL]")

        if meta.get('tvmaze_id', 0):
            parts.append(f"[URL=https://www.tvmaze.com/shows/{meta['tvmaze_id']}][img]{self.config['IMAGES']['tvmaze_75']}[/img][/URL]")

        if meta.get('mal_id', 0):
            parts.append(f"[URL=https://myanimelist.net/anime/{meta['mal_id']}][img]{self.config['IMAGES']['mal_75']}[/img][/URL]")

        return " ".join(parts)

    # get subs function
    # used in naming conventions

    def get_subs_info(self, meta: Meta, mi: dict[str, Any]) -> None:
        subs = ""
        subs_num = 0
        media = cast(dict[str, Any], mi.get("media") or {})
        tracks_raw: list[Any] = []
        raw_tracks = media.get("track")
        if isinstance(raw_tracks, list):
            tracks_raw = cast(list[Any], raw_tracks)
        tracks = cast(list[dict[str, Any]], tracks_raw)

        # Count subtitle tracks
        for s in tracks:
            if s.get("@type") == "Text":
                subs_num += 1

        meta['has_subs'] = 1 if subs_num > 0 else 0
        # Reset flags to avoid stale values
        meta.pop('eng_subs', None)
        meta.pop('sdh_subs', None)

        # Collect languages and flags
        for s in tracks:
            if s.get("@type") == "Text":
                lang = s.get("Language")
                if lang and subs_num > 0:
                    lang_str = str(lang).strip()
                    if lang_str:
                        subs += lang_str + ", "
                        lowered = lang_str.lower()
                        if lowered in {"en", "eng", "en-us", "en-gb", "en-ie", "en-au", "english"}:
                            meta['eng_subs'] = 1
                # crude SDH detection
                if "sdh" in str(s).lower():
                    meta['sdh_subs'] = 1
