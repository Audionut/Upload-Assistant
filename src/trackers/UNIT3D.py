# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import glob
import httpx
import json
import os
import platform
import re
from typing import Any, Union, Optional
from typing_extensions import TypeAlias

from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON

QueryValue: TypeAlias = Union[str, int, float, bool, None]
ParamsList: TypeAlias = list[tuple[str, QueryValue]]


class UNIT3D:
    def __init__(self, config: dict[str, Any], tracker_name: str):
        self.config = config
        self.tracker = tracker_name
        self.common = COMMON(config)
        self.tracker_config: dict[str, Any] = self.config["TRACKERS"].get(self.tracker, {})
        self.announce_url = self.tracker_config.get("announce_url", "")
        self.api_key = self.tracker_config.get("api_key", "")
        # Default URLs - should be overridden by subclasses
        self.search_url = ""
        self.upload_url = ""
        pass

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True
        return should_continue

    async def search_existing(self, meta: dict[str, Any], _) -> list[dict[str, Any]]:
        dupes: list[dict[str, Any]] = []

        # Ensure tracker_status keys exist before any potential writes
        meta.setdefault("tracker_status", {})
        meta["tracker_status"].setdefault(self.tracker, {})

        if not self.api_key:
            if not meta["debug"]:
                console.print(
                    f"[bold red]{self.tracker}: Missing API key in config file. Skipping upload...[/bold red]"
                )
            meta["skipping"] = f"{self.tracker}"
            return dupes

        should_continue = await self.get_additional_checks(meta)
        if not should_continue:
            meta["skipping"] = f"{self.tracker}"
            return dupes

        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
        }

        category_id = str((await self.get_category_id(meta))['category_id'])
        params_dict: dict[str, str] = {
            "tmdbId": str(meta['tmdb']),
            "categories[]": category_id,
            "name": "",
            "perPage": "100",
        }
        params_list: Optional[ParamsList] = None
        resolutions = await self.get_resolution_id(meta)
        resolution_id = str(resolutions["resolution_id"])
        if resolution_id in ["3", "4"]:
            # Convert params to list of tuples to support duplicate keys
            params_list = [(k, v) for k, v in params_dict.items()]
            params_list.append(("resolutions[]", "3"))
            params_list.append(("resolutions[]", "4"))
        else:
            params_dict["resolutions[]"] = resolution_id

        if self.tracker not in ["SP", "STC"]:
            type_id = str((await self.get_type_id(meta))["type_id"])
            if params_list is not None:
                params_list.append(("types[]", type_id))
            else:
                params_dict["types[]"] = type_id

        if meta["category"] == "TV":
            season_value = f" {meta.get('season', '')}"
            if params_list is not None:
                # Update the 'name' parameter in the list
                params_list = [
                    (k, (v + season_value if k == "name" and isinstance(v, str) else v))
                    for k, v in params_list
                ]
            else:
                params_dict["name"] = params_dict["name"] + season_value

        request_params: ParamsList
        if params_list is not None:
            request_params = params_list
        else:
            request_params = [(k, v) for k, v in params_dict.items()]

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url=self.search_url, headers=headers, params=request_params)
                response.raise_for_status()
                if response.status_code == 200:
                    data = response.json()
                    for each in data["data"]:
                        torrent_id = each.get("id", None)
                        attributes = each.get("attributes", {})
                        name = attributes.get("name", "")
                        size = attributes.get("size", 0)
                        result: dict[str, Any]
                        if not meta["is_disc"]:
                            result = {
                                "name": name,
                                "size": size,
                                "files": [
                                    file["name"]
                                    for file in attributes.get("files", [])
                                    if isinstance(file, dict) and "name" in file
                                ],
                                "file_count": (
                                    len(attributes.get("files", []))
                                    if isinstance(attributes.get("files"), list)
                                    else 0
                                ),
                                "trumpable": attributes.get("trumpable", False),
                                "link": attributes.get("details_link", None),
                                "download": attributes.get("download_link", None),
                                "id": torrent_id,
                                "type": attributes.get("type", None),
                                "res": attributes.get("resolution", None),
                                "internal": attributes.get("internal", False),
                            }
                        else:
                            result = {
                                "name": name,
                                "size": size,
                                "files": [],
                                "file_count": (
                                    len(attributes.get("files", []))
                                    if isinstance(attributes.get("files"), list)
                                    else 0
                                ),
                                "trumpable": attributes.get("trumpable", False),
                                "link": attributes.get("details_link", None),
                                "download": attributes.get("download_link", None),
                                "id": torrent_id,
                                "type": attributes.get("type", None),
                                "res": attributes.get("resolution", None),
                                "internal": attributes.get("internal", False),
                            }
                        dupes.append(result)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                meta["tracker_status"][self.tracker][
                    "status_message"
                ] = "data error: Redirect (302). This may indicate a problem with authentication. Please verify that your API key is valid."
            else:
                meta["tracker_status"][self.tracker][
                    "status_message"
                ] = f"data error: HTTP {e.response.status_code} - {e.response.text}"
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 10 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"name": meta["name"]}

    async def get_description(self, meta: dict[str, Any]) -> dict[str, str]:
        return {
            "description": await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(
                meta, comparison=True
            )
        }

    async def get_mediainfo(self, meta: dict[str, Any]) -> dict[str, str]:
        if meta["bdinfo"] is not None:
            mediainfo = ""
        else:
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", "r", encoding="utf-8"
            ) as f:
                mediainfo = await f.read()
        return {"mediainfo": mediainfo}

    async def get_bdinfo(self, meta: dict[str, Any]) -> dict[str, str]:
        if meta["bdinfo"] is not None:
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", "r", encoding="utf-8"
            ) as f:
                bdinfo = await f.read()
        else:
            bdinfo = ""
        return {"bdinfo": bdinfo}

    async def get_category_id(
        self, meta: dict[str, Any], category: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        category_id = {
            "MOVIE": "1",
            "TV": "2",
        }
        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}
        elif category:
            return {"category_id": category_id.get(category, "0")}
        else:
            meta_category = meta.get("category", "")
            resolved_id = category_id.get(meta_category, "0")
            return {"category_id": resolved_id}

    async def get_type_id(
        self, meta: dict[str, Any], type: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        type_id = {
            "DISC": "1",
            "REMUX": "2",
            "WEBDL": "4",
            "WEBRIP": "5",
            "HDTV": "6",
            "ENCODE": "3",
            "DVDRIP": "3",
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type:
            return {"type_id": type_id.get(type, "0")}
        else:
            meta_type = meta.get("type", "")
            resolved_id = type_id.get(meta_type, "0")
            return {"type_id": resolved_id}

    async def get_resolution_id(
        self, meta: dict[str, Any], resolution: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        resolution_id = {
            "8640p": "10",
            "4320p": "1",
            "2160p": "2",
            "1440p": "3",
            "1080p": "3",
            "1080i": "4",
            "720p": "5",
            "576p": "6",
            "576i": "7",
            "480p": "8",
            "480i": "9",
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution:
            return {"resolution_id": resolution_id.get(resolution, "10")}
        else:
            meta_resolution = meta.get("resolution", "")
            resolved_id = resolution_id.get(meta_resolution, "10")
            return {"resolution_id": resolved_id}

    async def get_anonymous(self, meta: dict[str, Any]) -> dict[str, str]:
        if meta["anon"] == 0 and not self.tracker_config.get("anon", False):
            anonymous = "0"
        else:
            anonymous = "1"
        return {"anonymous": anonymous}

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, str]:
        # Used to add additional data if needed
        """
        data = {
            'modq': await self.get_flag(meta, 'modq'),
            'draft': await self.get_flag(meta, 'draft'),
        }
        """
        data: dict[str, str] = {}

        return data

    async def get_flag(self, meta: dict[str, Any], flag_name: str) -> str:
        config_flag = self.tracker_config.get(flag_name)
        if meta.get(flag_name, False):
            return "1"
        else:
            if config_flag is not None:
                return "1" if config_flag else "0"
            else:
                return "0"

    async def get_distributor_id(self, meta: dict[str, Any]) -> dict[str, str]:
        distributor_id = await self.common.unit3d_distributor_ids(meta.get("distributor", ""))
        if distributor_id:
            return {"distributor_id": distributor_id}

        return {}

    async def get_region_id(self, meta: dict[str, Any]) -> dict[str, str]:
        region_id = await self.common.unit3d_region_ids(meta.get("region", ""))
        if region_id:
            return {"region_id": region_id}

        return {}

    async def get_tmdb(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"tmdb": f"{meta['tmdb']}"}

    async def get_imdb(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"imdb": f"{meta['imdb']}"}

    async def get_tvdb(self, meta: dict[str, Any]) -> dict[str, str]:
        tvdb = meta.get("tvdb_id", 0) if meta["category"] == "TV" else 0
        return {"tvdb": f"{tvdb}"}

    async def get_mal(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"mal": f"{meta['mal_id']}"}

    async def get_igdb(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"igdb": "0"}

    async def get_stream(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"stream": f"{meta['stream']}"}

    async def get_sd(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"sd": f"{meta['sd']}"}

    async def get_keywords(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"keywords": meta.get("keywords", "")}

    async def get_personal_release(self, meta: dict[str, Any]) -> dict[str, str]:
        personal_release = "1" if meta.get("personalrelease", False) else "0"
        return {"personal_release": personal_release}

    async def get_internal(self, meta: dict[str, Any]) -> dict[str, str]:
        internal = "0"
        if self.tracker_config.get("internal", False) is True:
            if meta["tag"] != "" and (
                meta["tag"][1:] in self.tracker_config.get("internal_groups", [])
            ):
                internal = "1"

        return {"internal": internal}

    async def get_season_number(self, meta: dict[str, Any]) -> dict[str, str]:
        data = {}
        if meta.get("category") == "TV":
            data = {"season_number": f"{meta.get('season_int', '0')}"}

        return data

    async def get_episode_number(self, meta: dict[str, Any]) -> dict[str, str]:
        data = {}
        if meta.get("category") == "TV":
            data = {"episode_number": f"{meta.get('episode_int', '0')}"}

        return data

    async def get_featured(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"featured": "0"}

    async def get_free(self, meta: dict[str, Any]) -> dict[str, str]:
        free = "0"
        if meta.get("freeleech", 0) != 0:
            free = f"{meta.get('freeleech', '0')}"

        return {"free": free}

    async def get_doubleup(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"doubleup": "0"}

    async def get_sticky(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"sticky": "0"}

    async def get_data(self, meta: dict[str, Any]) -> dict[str, str]:
        results = await asyncio.gather(
            self.get_name(meta),
            self.get_description(meta),
            self.get_mediainfo(meta),
            self.get_bdinfo(meta),
            self.get_category_id(meta),
            self.get_type_id(meta),
            self.get_resolution_id(meta),
            self.get_tmdb(meta),
            self.get_imdb(meta),
            self.get_tvdb(meta),
            self.get_mal(meta),
            self.get_igdb(meta),
            self.get_anonymous(meta),
            self.get_stream(meta),
            self.get_sd(meta),
            self.get_keywords(meta),
            self.get_personal_release(meta),
            self.get_internal(meta),
            self.get_season_number(meta),
            self.get_episode_number(meta),
            self.get_featured(meta),
            self.get_free(meta),
            self.get_doubleup(meta),
            self.get_sticky(meta),
            self.get_additional_data(meta),
            self.get_region_id(meta),
            self.get_distributor_id(meta),
        )

        merged: dict[str, str] = {}
        for r in results:
            merged.update(r)

        return merged

    async def get_additional_files(self, meta: dict[str, Any]) -> dict[str, tuple[str, bytes, str]]:
        files: dict[str, tuple[str, bytes, str]] = {}
        base_dir = meta["base_dir"]
        uuid = meta["uuid"]
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)

        if nfo_files:
            async with aiofiles.open(nfo_files[0], "rb") as f:
                nfo_bytes = await f.read()
            files["nfo"] = ("nfo_file.nfo", nfo_bytes, "text/plain")

        return files

    async def upload(self, meta: dict[str, Any], _):
        data = await self.get_data(meta)
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        async with aiofiles.open(torrent_file_path, "rb") as f:
            torrent_bytes = await f.read()
        files = {"torrent": ("torrent.torrent", torrent_bytes, "application/x-bittorrent")}
        files.update(await self.get_additional_files(meta))
        headers = {
            "User-Agent": f'{meta["ua_name"]} {meta.get("current_version", "")} ({platform.system()} {platform.release()})',
            "authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
        }

        if meta["debug"] is False:
            response_data = {}
            max_retries = 1
            retry_delay = 5
            timeout = 40.0

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                        response = await client.post(
                            url=self.upload_url, files=files, data=data, headers=headers
                        )
                        response.raise_for_status()

                        response_data = response.json()

                        # Verify API success before proceeding
                        if not response_data.get("success"):
                            error_msg = response_data.get("message", "Unknown error")
                            meta["tracker_status"][self.tracker]["status_message"] = f"API error: {error_msg}"
                            console.print(f"[yellow]Upload to {self.tracker} failed: {error_msg}[/yellow]")
                            return False

                        meta["tracker_status"][self.tracker]["status_message"] = (
                            await self.process_response_data(response_data)
                        )
                        torrent_id = await self.get_torrent_id(response_data)

                        meta["tracker_status"][self.tracker]["torrent_id"] = torrent_id
                        await self.common.download_tracker_torrent(
                            meta, self.tracker, headers=headers, downurl=response_data["data"]
                        )
                        return True  # Success

                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [403, 302]:
                        # Don't retry auth/permission errors
                        if e.response.status_code == 403:
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = "data error: Forbidden (403). This may indicate that you do not have upload permission."
                        else:
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = "data error: Redirect (302). This may indicate a problem with authentication. Please verify that your API key is valid."
                        return False  # Auth/permission error
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

    async def get_torrent_id(self, response_data: dict[str, Any]):
        """Matches /12345.abcde and returns 12345"""
        torrent_id = ""
        try:
            match = re.search(r"/(\d+)\.", response_data["data"])
            if match:
                torrent_id = match.group(1)
        except (IndexError, KeyError):
            print("Could not parse torrent_id from response data.")
        return torrent_id

    async def process_response_data(self, response_data: dict[str, Any]) -> str:
        """Returns the success message from the response data as a string."""
        if response_data.get("success") is True:
            return str(response_data.get("message", "Upload successful"))

        # For non-success responses, format as string
        error_msg = response_data.get("message", "")
        if error_msg:
            return f"API response: {error_msg}"
        return f"API response: {response_data}"
