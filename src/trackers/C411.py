# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# https://github.com/Audionut/Upload-Assistant/tree/master

import aiofiles
import asyncio
import json
import httpx
import src.trackers.FRENCH as fr
from typing import Any
from src.trackers.COMMON import COMMON
from src.console import console
from lxml import etree
import unidecode

Meta = dict[str, Any]
Config = dict[str, Any]


class C411:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'C411'
        self.base_url = 'https://c411.org'
        self.id_url = f'{self.base_url}/api/torrents'
        self.upload_url = f'{self.base_url}/api/torrents'
        # self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/'
        self.torrent_url = f'{self.base_url}/api/'
        self.banned_groups: list[str] = []
        pass

    # async def get_cat_id(self, meta: Meta) -> str:
        # mediatype video
    #    return '1'

    async def get_subcat_id(self, meta: Meta) -> str:
        sub_cat_id = "0"
        genres = meta.get("genres","").lower().replace(' ', '').replace('-', '')
        if meta['category'] == 'MOVIE':
            sub_cat_id = '1' if meta.get('mal_id') else '6'
            if 'animation' in genres:
                sub_cat_id = '6'
        elif meta['category'] == 'TV':
            sub_cat_id = '2' if meta.get('mal_id') else '7'

        return sub_cat_id

    async def get_option_tag(self, meta: Meta):
        obj1 = []
        obj2 = 0
        vff = None
        vfq = None
        eng = None
        audio_track = await fr.get_audio_tracks(meta, True)
        source = meta.get('source', "")
        type = meta.get('type', "").upper()

        for item in audio_track:
            lang = str(item.get('Language', '')).lower()
            if lang == "fr-ca":
                vfq = True
            if lang == "fr-fr":
                vff = True
            if lang in ("en", "en-us", "en-gb"):
                eng = True

        if vff and vfq:
            obj1.append(4)
        if vfq:
            obj1.append(5)
        if vff:
            obj1.append(2)
        if eng and not vff and not vfq:  # vo
            obj1.append(1)


        if meta['is_disc'] == 'BDMV':
            if meta['resolution'] == '2160p':
                obj2 = 10  # blu 4k full
            else:
                obj2 = 11  # blu full
        elif meta['is_disc'] == 'DVD':
            obj2 = 14  # DVD r5 r9  13 - 14

        elif type == "REMUX" and source in ("BluRay", "HDDVD"):
            if meta['resolution'] == '2160p':
                obj2 = 10  # blu 4k remux
            else:
                obj2 = 12  # blu remux

        elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
            obj2 = 15

        elif type == "ENCODE" and source in ("BluRay", "HDDVD"):
            if meta['resolution'] == '2160p':
                obj2 = 17
            elif meta['resolution'] == '1080p':
                obj2 = 16
            elif meta['resolution'] == '720p':
                obj2 = 18
            # else:
            #    obj2 = 25)

        elif type == "WEBDL":
            if meta['resolution'] == '2160p':
                obj2 = 26
            elif meta['resolution'] == '1080p':
                obj2 = 25
            elif meta['resolution'] == '720p':
                obj2 = 27
            else:
                obj2 = 24

        elif type == "WEBRIP":
            if meta['resolution'] == '2160p':
                obj2 = 30
            elif meta['resolution'] == '1080p':
                obj2 = 29
            elif meta['resolution'] == '720p':
                obj2 = 31
            else:
                obj2 = 28
        elif type == "HDTV":
            if meta['resolution'] == '2160p':
                obj2 = 21
            elif meta['resolution'] == '1080p':
                obj2 = 20
            elif meta['resolution'] == '720p':
                obj2 = 22
            else:
                obj2 = 19

        elif type == "DVDRIP":
            obj2 = 15  # DVDRIP

        uuid = meta.get('uuid', "").lower()

        if "4klight" in uuid: # and type == "ENCODE"
            obj2 = 415
        elif "hdlight" in uuid: # and type == "ENCODE"
            if meta['resolution'] == '1080p':
                obj2 = 413
            else:
                obj2 = 414

        # vcd/vhs ID= 23

        options_dict = {}
        options_dict[1] = obj1
        # None check is missing, check for correct data structure.
        options_dict[2] = [obj2]

        if meta['category'] == 'TV':
            if meta.get('no_season', False) is False:
                season = str(meta.get('season_int', ''))
                if season:
                    options_dict[7] = 120 + int(season)
            # Episode
            episode = str(meta.get('episode_int', ''))
            if episode:  # Episode 0 check is missing
                options_dict[6] = 96 + int(episode)
            else:
                # pas d'épisode, on suppose que c'est une saison complete
                options_dict[6] = 96
        return json.dumps(options_dict)

    # https://c411.org/wiki/nommage
    async def get_name(self, meta: Meta) -> dict[str, str]:

        type = str(meta.get('type', "")).upper()
        title, _ = await fr.get_translation_fr(meta)
        year = str(meta.get('year', ""))
        manual_year_value = meta.get('manual_year')
        if manual_year_value is not None and int(manual_year_value) > 0:
            year = str(manual_year_value)
        resolution = str(meta.get('resolution', ""))
        if resolution == "OTHER":
            resolution = ""
        audio = await fr.get_audio_name(meta)
        language = await fr.build_audio_string(meta)
        extra_audio = await fr.get_extra_french_tag(meta, True)
        if extra_audio:
            language = language.replace("FRENCH", "") + " " + extra_audio
        service = ""
        season = str(meta.get('season', ""))
        episode = str(meta.get('episode', ""))
        part = str(meta.get('part', ""))
        repack = str(meta.get('repack', ""))
        three_d = str(meta.get('3D', ""))
        tag = str(meta.get('tag', ""))
        source = str(meta.get('source', ""))
        uhd = str(meta.get('uhd', ""))
        hdr = str(meta.get('hdr', "")).replace('HDR10+', 'HDR10PLUS')
        hybrid = 'Hybrid' if meta.get('webdv', "") else ""
        video_codec = ""
        video_encode = ""
        region = ""
        dvd_size = ""
        if meta.get('is_disc', "") == "BDMV":
            video_codec = str(meta.get('video_codec', ""))
            region = str(meta.get('region', "") or "")
        elif meta.get('is_disc', "") == "DVD":
            region = str(meta.get('region', "") or "")
            dvd_size = str(meta.get('dvd_size', ""))
        else:
            video_codec = str(meta.get('video_codec', "")).replace('H.264', 'H264').replace('H.265', 'H265')
            video_encode = str(meta.get('video_encode', "")).replace('H.264', 'H264').replace('H.265', 'H265')
        edition = str(meta.get('edition', ""))
        if 'hybrid' in edition.upper():
            edition = edition.replace('Hybrid', '').strip()

        if meta['category'] == "TV":
            year = meta['year'] if meta['search_year'] != "" else ""
            if meta.get('manual_date'):
                # Ignore season and year for --daily flagged shows, just use manual date stored in episode_name
                season = ''
                episode = ''
        if meta.get('no_season', False) is True:
            season = ''
        if meta.get('no_year', False) is True:
            year = ''
        #if meta.get('no_aka', False) is True:
        #    alt_title = ''

        # YAY NAMING FUN
        name = ""
        if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
            if type == "DISC":
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} {year} {three_d} {edition} {hybrid} {repack} {language} {resolution} {uhd} {region} {source} {hdr} {audio} {video_codec}"
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} {year} {repack} {edition} {region} {source} {dvd_size} {audio}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} {year} {edition} {repack} {language} {resolution} {source} {video_codec} {audio}"
            elif type == "REMUX" and source in ("BluRay", "HDDVD"):
                name = f"{title} {year} {three_d} {edition} {hybrid} {repack} {language} {resolution} {uhd} {source} REMUX {hdr} {audio} {video_codec}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
                name = f"{title} {year} {edition} {repack} {source} REMUX  {audio}"
            elif type == "ENCODE":
                name = f"{title} {year} {edition} {hybrid} {repack} {language} {resolution} {uhd} {source} {hdr} {audio} {video_encode}"
            elif type == "WEBDL":
                name = f"{title} {year} {edition} {hybrid} {repack} {language} {resolution} {uhd} {service} WEB {hdr} {audio} {video_encode}"
            elif type == "WEBRIP":
                name = f"{title} {year} {edition} {hybrid} {repack} {language} {resolution} {uhd} {service} WEBRip {hdr} {audio} {video_encode}"
            elif type == "HDTV":
                name = f"{title} {year} {edition} {repack} {language} {resolution} {source} {audio} {video_encode}"
            elif type == "DVDRIP":
                name = f"{title} {year} {source} {video_encode} DVDRip {audio}"

        elif meta['category'] == "TV":  # TV SPECIFIC
            if type == "DISC":
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} {year} {season}{episode} {three_d} {edition} {hybrid} {repack} {language} {resolution} {uhd} {region} {source} {hdr} {audio} {video_codec}"
                if meta['is_disc'] == 'DVD':
                    name = f"{title} {year} {season}{episode}{three_d} {repack} {edition} {region} {source} {dvd_size} {audio}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} {year} {edition} {repack} {language} {resolution} {source} {video_codec} {audio}"
            elif type == "REMUX" and source in ("BluRay", "HDDVD"):
                name = f"{title} {year} {season}{episode} {part} {three_d} {edition} {hybrid} {repack} {language} {resolution} {uhd} {source} REMUX {hdr} {audio} {video_codec}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
                name = f"{title} {year} {season}{episode} {part} {edition} {repack} {source} REMUX {audio}"
            elif type == "ENCODE":
                name = f"{title} {year} {season}{episode} {part} {edition} {hybrid} {repack} {language} {resolution} {uhd} {source} {hdr} {audio} {video_encode}"
            elif type == "WEBDL":
                name = f"{title} {year} {season}{episode} {part} {edition} {hybrid} {repack} {language} {resolution} {uhd} {service} WEB {hdr} {audio} {video_encode}"
            elif type == "WEBRIP":
                name = f"{title} {year} {season}{episode} {part} {edition} {hybrid} {repack} {language} {resolution} {uhd} {service} WEBRip {hdr} {audio}  {video_encode}"
            elif type == "HDTV":
                name = f"{title} {year} {season}{episode} {part} {edition} {repack} {language} {resolution} {source} {audio} {video_encode}"
            elif type == "DVDRIP":
                name = f"{title} {year} {season} {source} DVDRip {audio} {video_encode}"

        try:
            name = ' '.join(name.split())
        except Exception:
            console.print(
                "[bold red]Unable to generate name. Please re-run and correct any of the following args if needed.")
            console.print(f"--category [yellow]{meta['category']}")
            console.print(f"--type [yellow]{meta['type']}")
            console.print(f"--source [yellow]{meta['source']}")
            console.print(
                "[bold green]If you specified type, try also specifying source")
            raise

        name_notag = name
        name = name_notag + tag
        name = await fr.clean_name(name)

        if meta['debug']:
            console.log("[cyan]get_name cat/type")
            console.log(f"CATEGORY: {meta['category']}")
            console.log(f"TYPE: {meta['type']}")
            console.log("[cyan]get_name meta:")
            console.print(f"source : {source}")
            console.print(f"type : {type}")
            console.print(f"video_codec : {video_codec}")
            console.print(f"video_encode : {video_encode}")
            console.print(f"NAME : {name}")

        return {'name': name}

    async def get_additional_checks(self, meta: Meta) -> bool:
        # Check language requirements: must be French audio OR original audio with French subtitles
        french_languages = ["french", "fre", "fra", "fr",
                            "français", "francais", 'fr-fr', 'fr-ca']
        # check or ignore audio req config
        # self.config['TRACKERS'][self.tracker].get('check_for_rules', True):
        if not await self.common.check_language_requirements(
            meta,
            self.tracker,
            languages_to_check=french_languages,
            check_audio=True,
            check_subtitle=True,
            require_both=False,
            original_language=True,
        ):
            console.print(
                f"[bold red]Language requirements not met for {self.tracker}.[/bold red]")
            return False

        return True

    async def search_existing(self, meta: dict[str, Any], _) -> list[str]:
        dupes: list[str] = []

        # Nothing came with the name, we'll look using tmdb_id
        tmdb_id = meta.get('tmdb_id','')
        title, descr = await fr.get_translation_fr(meta)
        params: dict[str, Any] = {
            't': 'search',
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbid': tmdb_id
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    response_text = response.text.encode('utf-8')
                    root = etree.fromstring(response_text)
                    channel = root[0]
                    for result in channel:
                        if result.tag == 'item':
                            dupe = result[0]
                            dupes.append(dupe.text)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)
        if not dupes:
            # Nothing came with tmdn id, we'll check using names just in case
            title, descr = await fr.get_translation_fr(meta)
            params: dict[str, Any] = {
                't': 'search',
                'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
                'q': unidecode.unidecode(title.replace(" ", "."))
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url=self.search_url, params=params)
                    if response.status_code == 200:
                        response_text = response.text.encode('utf-8')
                        root = etree.fromstring(response_text)
                        channel = root[0]
                        for result in channel:
                            if result.tag == 'item':
                                dupe = result[0]
                                dupes.append(dupe.text)
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



    async def upload(self, meta: Meta, _disctype: str) -> bool:
        description = await fr.get_desc_full(meta, self.tracker)
         # Tmdb infos
        tmdb_info = {}
        tmdb_info['id'] = meta.get("tmdb_id","")
        tmdb_info['title'] = meta.get("title","")
        tmdb_info['originalTitle'] = meta.get("original_title","")
        tmdb_info['overview'] = meta.get("overview","")
        tmdb_info['release_date'] = meta.get("release_date","")
        tmdb_info['runtime'] = meta.get("runtime","")
        tmdb_info['voteAverage'] = meta.get("vote_average","")
        if not meta["debug"]:
            await self.common.create_torrent_for_upload(meta, self.tracker, 'C411')
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        mediainfo_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"

        headers = {
            "Authorization": f"Bearer {self.config['TRACKERS'][self.tracker]['api_key'].strip()}"}
        c411_name = await self.get_name(meta)
        dot_name = c411_name["name"].replace(" ", ".")
        response = None

        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        async with aiofiles.open(mediainfo_file_path, 'rb') as f:
            mediainfo_bytes = await f.read()
        data = {
            "title": str(dot_name),
            "description": await fr.get_desc_full(meta, self.tracker),
            "categoryId": "1",
            "subcategoryId": str(await self.get_subcat_id(meta)),
            # 1 langue , 2 qualite
            "options": await self.get_option_tag(meta),
            # "isExclusive": "Test Upload-Assistant",
            "uploaderNote": "Upload-Assistant",
            "tmdbData": str(tmdb_info),
            # "rawgData": "Test Upload-Assistant",
        }
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/c411_payload.json", 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4))

        # Place holder for potential improvement
        # files={"torrent": ("torrent.torrent", torrent_bytes, "application/x-bittorrent"),"nfo": ("MEDIAINFO.txt", mediainfo_bytes, "text/plain"),}
        files = {"torrent": torrent_bytes, "nfo": mediainfo_bytes, }

        if meta["debug"] is False:
            response_data = {}
            max_retries = 2
            retry_delay = 5
            timeout = 40.0

            for attempt in range(max_retries):
                try:  # noqa: PERF203
                    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                        response = await client.post(
                            url=self.upload_url, files=files, data=data, headers=headers
                        )
                        response.raise_for_status()

                        response_data = response.json()

                        # Verify API success before proceeding
                        if not response_data.get("success"):
                            error_msg = response_data.get(
                                "message", "Unknown error")
                            meta["tracker_status"][self.tracker][
                                "status_message"] = f"API error: {error_msg}"
                            console.print(
                                f"[yellow]Upload to {self.tracker} failed: {error_msg}[/yellow]")
                            return False

                        meta["tracker_status"][self.tracker]["status_message"] = (
                            await self.process_response_data(response_data)
                        )

                        torrent_hash = response_data["data"]["infoHash"]
                        meta["tracker_status"][self.tracker]["torrent_id"] = torrent_hash
                        await self.download_torrent(meta, torrent_hash)
                        return True  # Success

                except httpx.HTTPStatusError as e:  # noqa: PERF203
                    if e.response.status_code in [403, 302]:
                        # Don't retry auth/permission errors
                        if e.response.status_code == 403:
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = f"data error: Forbidden (403). This may indicate that you do not have upload permission. {e.response.text}"
                        else:
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = f"data error: Redirect (302). This may indicate a problem with authentication. {e.response.text}"
                        return False  # Auth/permission error
                    elif e.response.status_code in [401, 404, 422]:
                        meta["tracker_status"][self.tracker][
                            "status_message"
                        ] = f"data error: HTTP {e.response.status_code} - {e.response.text}"
                        return False
                    else:
                        # Retry other HTTP errors
                        if attempt < max_retries - 1:
                            console.print(
                                f"[yellow]{self.tracker}: HTTP {e.response.status_code} error, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})[/yellow]"
                            )
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            # Final attempt failed
                            if e.response.status_code == 520:
                                meta["tracker_status"][self.tracker][
                                    "status_message"
                                ] = "data error: Error (520). This is probably a cloudflare issue on the tracker side."
                            else:
                                meta["tracker_status"][self.tracker][
                                    "status_message"
                                ] = f"data error: HTTP {e.response.status_code} - {e.response.text}"
                            return False  # HTTP error after all retries
                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        timeout = timeout * 1.5  # Increase timeout by 50% for next retry
                        console.print(
                            f"[yellow]{self.tracker}: Request timed out, retrying in {retry_delay} seconds with {timeout}s timeout... (attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        meta["tracker_status"][self.tracker][
                            "status_message"
                        ] = "data error: Request timed out after multiple attempts"
                        return False  # Timeout after all retries
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        console.print(
                            f"[yellow]{self.tracker}: Request error, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        meta["tracker_status"][self.tracker][
                            "status_message"
                        ] = f"data error: Unable to upload. Error: {e}.\nResponse: {response_data}"
                        return False  # Request error after all retries
                except json.JSONDecodeError as e:
                    meta["tracker_status"][self.tracker][
                        "status_message"
                    ] = f"data error: Invalid JSON response from {self.tracker}. Error: {e}"
                    return False  # JSON parsing error
        else:
            console.print(f"[cyan]{self.tracker} Request Data:")
            console.print(data)
            meta["tracker_status"][self.tracker][
                "status_message"
            ] = f"Debug mode enabled, not uploading: {self.tracker}."
            await self.common.create_torrent_for_upload(
                meta,
                f"{self.tracker}" + "_DEBUG",
                f"{self.tracker}" + "_DEBUG",
                announce_url="https://fake.tracker",
            )
            return True  # Debug mode - simulated success

        return False

    async def download_torrent(self, meta: dict[str, Any], torrent_hash: str, ) -> None:
        path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DL.torrent"
        params: dict[str, Any] = {
            "t": "get",
            "id": torrent_hash,
            "apikey": self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }

        # https://c411.org/api/?t=get&id={{infoHash}}&apikey={{config.API_KEY}}
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(self.torrent_url, params=params)

                r.raise_for_status()
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        await f.write(chunk)

            return None

        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not download torrent file: {str(e)}[/yellow]")
            console.print(
                "[yellow]Download manually from the tracker.[/yellow]")
            return None

    async def process_response_data(self, response_data: dict[str, Any]) -> str:
        """Returns the success message from the response data as a string."""
        if response_data.get("success") is True:
            return str(response_data.get("message", "Upload successful"))

        # For non-success responses, format as string
        error_msg = response_data.get("message", "")
        if error_msg:
            return f"API response: {error_msg}"
        return f"API response: {response_data}"