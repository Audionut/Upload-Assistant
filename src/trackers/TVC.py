# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import asyncio
import traceback
import cli_ui
import os
import re
import tmdbsimple as tmdb
from src.bbcode import BBCODE
import json
import httpx
import requests
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts
from datetime import datetime


class TVC():
    """
    Tracker handler for TVChaosUK (TVC).

    Provides methods to prepare metadata, generate description text,
    and upload torrents to TVChaosUK via its API.
    """

    def __init__(self, config):
        """
        Initialize the TVC tracker handler.

        Args:
            config (dict): Global configuration dictionary containing tracker settings.

        Attributes:
            tracker (str): Tracker name ("TVC").
            source_flag (str): Source flag string used in uploads.
            upload_url (str): API endpoint for torrent uploads.
            search_url (str): API endpoint for torrent searches.
            torrent_url (str): Base URL for torrent pages.
            signature (str): Optional signature appended to descriptions.
            banned_groups (list): List of release groups not allowed.
            tv_type_map (dict): Mapping of genre keywords to TVC category IDs.
        """
        self.config = config
        self.tracker = 'TVC'
        self.source_flag = 'TVCHAOS'
        self.upload_url = 'https://tvchaosuk.com/api/torrents/upload'
        self.search_url = 'https://tvchaosuk.com/api/torrents/filter'
        self.torrent_url = 'https://tvchaosuk.com/torrents/'
        self.signature = ""
        self.banned_groups = []
        tmdb.API_KEY = config['DEFAULT']['tmdb_api']

        # TV type mapping as a dict for clarity and maintainability
        self.tv_type_map = {
            "comedy": "29",
            "documentary": "5",
            "drama": "11",
            "entertainment": "14",
            "factual": "19",
            "foreign": "43",
            "kids": "32",
            "movies": "44",
            "news": "45",
            "reality": "52",
            "soaps": "30",
            "sci-fi": "33",
            "sport": "42",
            "holding bin": "53",
            }

    def format_date_ddmmyyyy(self, date_str):
        """
        Convert a date string from 'YYYY-MM-DD' to 'DD-MM-YYYY'.

        Args:
            date_str (str): Input date string.

        Returns:
            str: Reformatted date string, or the original if parsing fails.
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
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
        for g in genres.split(', '):
            g = g.lower().replace(",", "").strip()
            if g and g in self.tv_type_map:
                return self.tv_type_map[g]

        # fallback to holding bin/misc id
        return self.tv_type_map["holding bin"]

    async def get_res_id(self, tv_pack, resolution):
        """
        Map resolution and pack flag to TVC resolution type label.

        Args:
            tv_pack (bool): True if this is a season pack, False otherwise.
            resolution (str): Resolution string (e.g. "1080p", "720p").

        Returns:
            str: Resolution type label used by TVC (e.g. "HD1080p Pack", "SD").
        """
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

    async def append_country_code(self, meta, name):
        """
        Append ISO country code suffix to release name based on origin_country_code.

        Args:
            meta (dict): Metadata containing 'origin_country_code' list.
            name (str): Base release name.

        Returns:
            str: Release name with appended country code (e.g. "Show Title [IRL]").
        """
        if 'origin_country_code' in meta:
            if "IE" in meta['origin_country_code']:
                name += " [IRL]"
            elif "AU" in meta['origin_country_code']:
                name += " [AUS]"
            elif "NZ" in meta['origin_country_code']:
                name += " [NZL]"
            elif "CA" in meta['origin_country_code']:
                name += " [CAN]"
            elif "IT" in meta['origin_country_code']:
                name += " [ITA]"
            elif "FR" in meta['origin_country_code']:
                name += " [FRA]"
            elif "DE" in meta['origin_country_code']:
                name += " [GER]"
            elif "ES" in meta['origin_country_code']:
                name += " [SPA]"
            elif "PT" in meta['origin_country_code']:
                name += " [POR]"
            elif "BE" in meta['origin_country_code']:
                name += " [BEL]"
            elif "DK" in meta['origin_country_code']:
                name += " [DNK]"
            elif "NL" in meta['origin_country_code']:
                name += " [NLD]"
            elif "SE" in meta['origin_country_code']:
                name += " [SWE]"
            elif "NO" in meta['origin_country_code']:
                name += " [NOR]"
            elif "FI" in meta['origin_country_code']:
                name += " [FIN]"
            elif "IS" in meta['origin_country_code']:
                name += " [ISL]"
            elif "PL" in meta['origin_country_code']:
                name += " [POL]"
            elif "RU" in meta['origin_country_code']:
                name += " [RUS]"
            elif "AT" in meta['origin_country_code']:
                name += " [AUT]"
            elif "CZ" in meta['origin_country_code']:
                name += " [CZE]"
            elif "EE" in meta['origin_country_code']:
                name += " [EST]"
            elif "CH" in meta['origin_country_code']:
                name += " [CHE]"
        return name

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """
        Async helper to read a text file safely.
        Uses a with-block to ensure the file handle is closed.
        """
        def _read():
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        return await asyncio.to_thread(_read)

    async def upload(self, meta, disctype):
        """
        Perform upload of torrent metadata to TVC.

        Prepares description, category, resolution, and sends POST request
        to TVC API with torrent file and metadata.

        Args:
            meta (dict): Metadata dictionary for the release.
            disctype (str): Disc type indicator (e.g. "DVD", "BDMV").

        Raises:
            ValueError: If category is unsupported.
            RuntimeError: If upload fails with non-200 HTTP status.
        """
        common = COMMON(config=self.config)
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
            "pixhost.to": "pixhost",
            "imagebam.com": "bam",
            "onlyimage.org": "onlyimage",
        }

        approved_image_hosts = ['imgbb', 'ptpimg', 'imgbox', 'pixhost', 'bam', 'onlyimage']
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping,
                          img_host_index=1, approved_image_hosts=approved_image_hosts)

        image_list = meta.get('TVC_images_key', meta.get('image_list', []))
        if not isinstance(image_list, (list, tuple)):
            image_list = []

        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.get_tmdb_data(meta)

        # load MediaInfo.json
        try:
            content = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/MediaInfo.json")
            mi = json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            console.print(f"[yellow]Warning: Could not load MediaInfo.json: {e}")
            mi = {}

        cat_id = await self.get_cat_id(meta['genres']) if meta['category'] == 'TV' else 44
        meta['language_checked'] = True

        # Parse subtitle languages for metadata only
        subtitle_langs_local = []
        try:
            for t in mi.get('media', {}).get('track', []):
                if t.get('@type') == 'Text' and 'Language' in t and t['Language']:
                    subtitle_langs_local.append(str(t['Language']).strip().title())
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse subtitle languages: {e}")
        subtitle_meta = meta.get('subtitle_languages') or subtitle_langs_local
        if subtitle_meta:
            meta['subtitle_languages'] = subtitle_meta

        # Foreign category check based on TMDB original_language
        original_lang = meta.get("original_language", "")
        if original_lang and not original_lang.startswith("en") and original_lang not in ["ga", "gd", "cy"]:
            cat_id = self.tv_type_map["foreign"]
        elif not original_lang:
            # Fallback: inspect audio languages from MediaInfo if TMDB data is missing
            audio_langs = self.get_audio_languages(mi)
            if audio_langs:
                meta['audio_languages'] = audio_langs
                if "English" not in audio_langs:
                    cat_id = self.tv_type_map["foreign"]

        resolution_id = await self.get_res_id(meta.get('tv_pack', 0), meta['resolution'])
        await self.unit3d_edit_desc(meta, self.tracker, self.signature, image_list)

        anon = 0 if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False) else 1

        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt")
        else:
            mi_dump = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt")
            bd_dump = None

        descfile_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], f"[{self.tracker}]DESCRIPTION.txt")
        try:
            desc = await self.read_file(descfile_path)
        except FileNotFoundError:
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
            year = meta['year'] if meta['search_year'] != "" else ""
            if meta.get('no_year', False):
                year = ''
            year_str = f" ({year})" if year else ""

            if meta['tv_pack']:
                season_first = (meta.get('season_air_first_date') or "")[:4]
                season_year = season_first or meta.get('year', '')
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
        if cat_id == self.tv_type_map["foreign"]:
            if meta.get('original_title') and meta['original_title'] != meta['title']:
                tvc_name = tvc_name.replace(meta['title'], f"{meta['title']} ({meta['original_title']})")

        if not meta['is_disc']:
            # Pass the full MediaInfo dict; get_subs_info handles missing/invalid data internally
            self.get_subs_info(meta, mi)

        if meta['video_codec'] == 'HEVC':
            tvc_name = tvc_name.replace(']', ' HEVC]')
        if meta.get('eng_subs'):
            tvc_name = tvc_name.replace(']', ' SUBS]')
        if meta.get('sdh_subs'):
            if meta.get('eng_subs'):
                tvc_name = tvc_name.replace(' SUBS]', ' (ENG + SDH SUBS)]')
            else:
                tvc_name = tvc_name.replace(']', ' (SDH SUBS)]')

        tvc_name = await self.append_country_code(meta, tvc_name)

        if meta.get('unattended', False) is False:
            upload_to_tvc = cli_ui.ask_yes_no(f"Upload to {self.tracker} with the name {tvc_name}?", default=False)
            if not upload_to_tvc:
                tvc_name = cli_ui.ask_string("Please enter New Name:")
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

        if 'upload_to_tvc' in locals() and upload_to_tvc is False:
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        if meta['debug'] is False:
            response = None
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    with open(torrent_path, "rb") as open_torrent:
                        files = {'torrent': open_torrent}
                        response = await client.post(
                            self.upload_url,
                            files=files,
                            data=data,
                            headers={'User-Agent': 'Mozilla/5.0'},
                            params={'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()}
                        )

                if response.status_code != 200:
                    raise RuntimeError(f"TVC upload failed with HTTP {response.status_code}")
                # TVC returns "application/x-bittorrent\n{json}" so strip the prefix
                json_data = json.loads(response.text.removeprefix('application/x-bittorrent\n'))
                meta['tracker_status'][self.tracker]['status_message'] = json_data

                # Extract torrent ID robustly from returned URL
                data_str = json_data.get('data')
                if not isinstance(data_str, str):
                    raise ValueError(f"Invalid TVC response: 'data' missing or not a string: {data_str}")

                from urllib.parse import urlparse
                parsed = urlparse(data_str)
                segments = [seg for seg in parsed.path.split("/") if seg]
                if not segments:
                    raise ValueError(f"Invalid TVC response format: no path segments in {data_str}")

                # Use last segment as torrent ID
                t_id = segments[-1]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id

                console.print(f"[cyan]Extracted torrent ID {t_id} from {data_str}")

                await common.add_tracker_torrent(
                    meta,
                    self.tracker,
                    self.source_flag,
                    self.config['TRACKERS'][self.tracker].get('announce_url'),
                    f"https://tvchaosuk.com/torrents/{t_id}"
                )

            except Exception:
                console.print(traceback.format_exc())
                console.print("[yellow]It may have uploaded, go check")
                if response is not None:
                    console.print(response.text.removeprefix('application/x-bittorrent\n'))

        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."

    def get_audio_languages(self, mi):
        """
        Parse MediaInfo object and return a list of normalized audio languages.

        Args:
            mi (dict): MediaInfo JSON object.

        Returns:
            list[str]: Sorted list of audio language names (e.g. ["English", "French"]).
        """
        audio_langs = set()
        for track in mi.get("media", {}).get("track", []):
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

    async def get_tmdb_data(self, meta):
        """
        Fetch TMDB metadata for movies or TV shows.

        TMDB’s API is inconsistent: movies expose release dates directly,
        but TV shows require separate calls to TV, TV_Seasons, and TV_Episodes.
        This helper unifies those calls into a single meta dict so the rest
        of the upload logic doesn’t have to care about TMDB’s quirks.
        ...
        """
        if meta['category'] == "MOVIE":
            movie = tmdb.Movies(meta['tmdb'])
            response = movie.info()
            meta['title'] = response.get('title', meta.get('title', ''))
            meta['original_title'] = response.get('original_title', meta['title'])
            meta['original_language'] = response.get('original_language', 'en')
            try:
                meta['release_dates'] = movie.release_dates()
            except (requests.exceptions.RequestException, KeyError) as e:
                console.print(f"[yellow]Warning: Could not fetch movie release dates: {e}")

        elif meta['category'] == "TV":
            tv = tmdb.TV(meta['tmdb'])
            response = tv.info()
            meta['title'] = response.get('name', meta.get('title', ''))
            meta['original_title'] = response.get('original_name', meta['title'])
            meta['original_language'] = response.get('original_language', 'en')

            # TVC-specific extras
            try:
                if hasattr(tv, 'release_dates'):
                    meta['release_dates'] = tv.release_dates()
            except (requests.exceptions.RequestException, KeyError) as e:
                console.print(f"[yellow]Warning: Could not fetch TV release dates: {e}")

            if hasattr(tv, 'networks') and len(tv.networks) != 0 and 'name' in tv.networks[0]:
                meta['networks'] = tv.networks[0]['name']

            try:
                if not meta['tv_pack']:
                    episode_info = tmdb.TV_Episodes(meta['tmdb'], meta['season_int'], meta['episode_int']).info()
                    meta['episode_airdate'] = episode_info.get('air_date', '')
                    meta['episode_name'] = episode_info.get('name', '')
                    meta['episode_overview'] = episode_info.get('overview', '')
                else:
                    season_info = tmdb.TV_Seasons(meta['tmdb'], meta['season_int']).info()
                    air_date = season_info.get('air_date') or ""
                    meta['season_air_first_date'] = air_date
                    meta['season_name'] = season_info.get('name', f"Season {meta['season_int']}")
                    meta['episodes'] = []
                    for ep in season_info.get('episodes', []):
                        code = f"S{str(ep.get('season_number', 0)).zfill(2)}E{str(ep.get('episode_number', 0)).zfill(2)}"
                        meta['episodes'].append({
                            "code": code,
                            "title": (ep.get("name") or "").strip(),
                            "airdate": ep.get("air_date") or "",
                            "overview": (ep.get("overview") or "").strip()
                        })
                    if hasattr(tv, 'first_air_date'):
                        meta['first_air_date'] = tv.first_air_date

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

        # Origin country codes (shared for both movies and TV)
        meta['origin_country_code'] = []
        if 'origin_country' in response:
            if isinstance(response['origin_country'], list):
                meta['origin_country_code'].extend(response['origin_country'])
            else:
                meta['origin_country_code'].append(response['origin_country'])
        elif len(response.get('production_countries', [])):
            for i in response['production_countries']:
                if 'iso_3166_1' in i:
                    meta['origin_country_code'].append(i['iso_3166_1'])
        elif len(response.get('production_companies', [])):
            meta['origin_country_code'].append(response['production_companies'][0].get('origin_country', ''))

    async def search_existing(self, meta, _disctype=None):
        """
        Search TVC for existing torrents to avoid duplicates.

        Args:
            meta (dict): Metadata dictionary for the release.
            _disctype (str, optional): Disc type indicator.

        Returns:
            list[str]: Names of duplicate torrents found. Empty if none or search disabled.
        """
        # Search on TVCUK has been DISABLED due to issues
        # leaving code here for future use when it is re-enabled
        console.print("[red]Cannot search for dupes as search api is not working...")
        console.print("[red]Please make sure you are not uploading duplicates.")
        # https://tvchaosuk.com/api/torrents/filter?api_token=<API_key>&tmdb=138108

        dupes = []

        # UHD, Discs, remux and non-1080p HEVC are not allowed on TVC.
        if meta['resolution'] == '2160p' or (meta['is_disc'] or "REMUX" in meta['type']) or (meta['video_codec'] == 'HEVC' and meta['resolution'] != '1080p'):
            console.print("[bold red]No UHD, Discs, Remuxes or non-1080p HEVC allowed at TVC[/bold red]")
            meta['skipping'] = "TVC"
            return []

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'name': ""
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # 404 catch when their api is down
                    if data['data'] != '404':
                        for each in data['data']:
                            print(each[0]['attributes']['name'])
                            result = each[0]['attributes']['name']
                            dupes.append(result)
                    else:
                        console.print("Search API is down, please check manually")
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes

    async def unit3d_edit_desc(self, meta, tracker, signature, image_list, comparison=False):
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
        base = await self.read_file(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt")

        # Ensure tmp/<uuid> directory exists
        desc_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        os.makedirs(desc_dir, exist_ok=True)
        descfile_path = os.path.join(desc_dir, f"[{tracker}]DESCRIPTION.txt")
        bbcode = BBCODE()
        desc = ""

        # Discs
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

        # Release info for movies
        rd_info = ""
        if meta['category'] == "MOVIE" and 'release_dates' in meta:
            for cc in meta['release_dates']['results']:
                for rd in cc['release_dates']:
                    if rd['type'] == 6:
                        channel = str(rd['note']) if str(rd['note']) != "" else "N/A Channel"
                        rd_info += (
                            f"[color=orange][size=15]{cc['iso_3166_1']} TV Release info [/size][/color]\n"
                            f"{str(rd['release_date'])[:10]} on {channel}\n"
                        )
        if rd_info:
            desc += f"[center]{rd_info}[/center]\n\n"

        # TV pack layout
        if meta['category'] == "TV" and meta.get('tv_pack') == 1 and 'season_air_first_date' in meta:
            channel = meta.get('networks', 'N/A')
            airdate = self.format_date_ddmmyyyy(meta.get('season_air_first_date') or "")

            desc += "[center]\n"
            if meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n\n"

            desc += f"[b]Season Title:[/b] {meta.get('season_name', 'Unknown Season')}\n\n"
            desc += f"[b]This series premiered on:[/b] {channel} on {airdate}\n"

            # Episode list
            if meta.get('episodes'):
                desc += "\n\n[b]Episode List[/b]\n\n"
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
                        desc += f"{ep_overview}\n\n"

            desc += self.get_links(meta)

            screens_count = int(meta.get('screens', 0) or 0)
            if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                desc += "\n\n[b]Screenshots[/b]\n\n"
                for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                    web_url = each['web_url']
                    img_url = each['img_url']
                    desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"

            desc += "[/center]\n\n"

        # Episode layout
        elif meta['category'] == "TV" and meta.get('tv_pack') != 1 and 'episode_overview' in meta:
            desc += "[center]\n"
            if meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n\n"
            episode_name = str(meta.get('episode_name', '')).strip()
            overview = str(meta.get('episode_overview', '')).strip()
            # Note: regex may mis-split on abbreviations (e.g. "Dr. Smith") or ellipses ("...").
            # This is a heuristic; fallback is to treat the whole overview as one block.
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', overview) if s.strip()]
            if not sentences and overview:
                sentences = [overview]

            if episode_name:
                desc += f"[b]Episode Title:[/b] {episode_name}\n\n"
            for s in sentences:
                desc += s.rstrip() + "\n"
            if 'episode_airdate' in meta:
                channel = meta.get('networks', 'N/A')
                formatted_date = self.format_date_ddmmyyyy(meta['episode_airdate'])
                desc += f"\n[b]Broadcast on:[/b] {channel} on {formatted_date}\n"

            desc += self.get_links(meta)

            screens_count = int(meta.get('screens', 0) or 0)
            if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                desc += "\n\n[b]Screenshots[/b]\n\n"
                for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                    web_url = each['web_url']
                    img_url = each['img_url']
                    desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"
            desc += "[/center]\n\n"

        # Movie / fallback overview
        else:
            # Fallback path: for non‑movie categories with only a generic overview available.
            overview = str(meta.get('overview', '')).strip()
            desc += "[center]\n"
            if meta['category'].upper() == "MOVIE" and meta.get("logo"):
                desc += f"[img={self.config['DEFAULT'].get('logo_size', '300')}]"
                desc += f"{meta['logo']}[/img]\n\n"

            if meta['category'].upper() == "MOVIE":
                desc += f"[b]Movie Title:[/b] {meta.get('title', 'Unknown Movie')}\n\n"
                desc += overview + "\n"
                if 'release_date' in meta:
                    formatted_date = self.format_date_ddmmyyyy(meta['release_date'])
                    desc += f"\n[b]Released on:[/b] {formatted_date}\n"
                desc += self.get_links(meta)

                # Screenshots block for movies
                screens_count = int(meta.get('screens', 0) or 0)
                if image_list and screens_count >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                    desc += "\n\n[b]Screenshots[/b]\n\n"
                    for each in image_list[:self.config['TRACKERS'][self.tracker]['image_count']]:
                        web_url = each['web_url']
                        img_url = each['img_url']
                        desc += f"[url={web_url}][img=350]{img_url}[/img][/url]"

                desc += "[/center]\n\n"
            else:
                desc += overview + "\n[/center]\n\n"

        # Notes/Extra Info
        notes_content = base.strip()
        if notes_content and notes_content.lower() != "ptp":
            desc += f"[center][b]Notes / Extra Info[/b]\n\n{notes_content}\n\n[/center]\n\n"

        # BBCode conversions
        desc = bbcode.convert_pre_to_code(desc)
        desc = bbcode.convert_hide_to_spoiler(desc)
        if not comparison:
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)

        # Ensure fallback content if description is empty
        if not desc.strip():
            desc = "[center][i]No description available[/i][/center]\n"

        # Append signature if provided
        if signature:
            desc += f"\n{signature}\n"

        # Write description asynchronously
        def _write():
            with open(descfile_path, "w", encoding="utf-8") as f:
                f.write(desc)

        try:
            await asyncio.to_thread(_write)
            console.print(f"[cyan]Wrote DESCRIPTION file to {descfile_path} ({len(desc)} chars)")
        except Exception as e:
            console.print(f"[bold red]Failed to write DESCRIPTION file: {e}")

        return

    def get_links(self, meta):
        """
        Returns a BBCode string with an 'External Info Sources' heading and icon links.
        No [center] tags are included; callers control layout.
        """
        parts = []

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

    def get_subs_info(self, meta, mi):
        subs = ""
        subs_num = 0
        media = mi.get("media") or {}
        tracks = media.get("track") or []

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

        return subs.strip(", ")
