# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import asyncio
import json
import os
import platform
import re
import time
from contextlib import ExitStack
from typing import Any, Optional, Union, cast

import aiofiles
import httpx
from typing_extensions import TypeAlias

from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON, get_upload_process_executor

QueryValue: TypeAlias = Union[str, int, float, bool, None]
ParamsList: TypeAlias = list[tuple[str, QueryValue]]


def _unit3d_upload_worker(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url", ""))
    data = payload.get("data")
    file_specs = cast(list[dict[str, str]], payload.get("file_specs") or [])
    headers = payload.get("headers")
    timeout = float(payload.get("timeout", 40.0))
    max_keepalive_raw = int(payload.get("max_keepalive", 10))
    max_connections_raw = int(payload.get("max_connections", 20))
    max_keepalive = max_keepalive_raw if max_keepalive_raw > 0 else None
    max_connections = max_connections_raw if max_connections_raw > 0 else None

    if not url:
        return {"error": "request", "message": "Missing upload URL."}

    try:
        limits = httpx.Limits(
            max_keepalive_connections=max_keepalive,
            max_connections=max_connections,
        )
        with httpx.Client(timeout=timeout, follow_redirects=True, limits=limits) as client, ExitStack() as stack:
            files: dict[str, tuple[str, Any, str]] = {}
            for spec in file_specs:
                field = spec.get("field", "")
                path = spec.get("path", "")
                filename = spec.get("filename", "")
                content_type = spec.get("content_type", "application/octet-stream")
                if not field or not path or not filename:
                    return {"error": "request", "message": "Invalid file spec for upload."}
                if not os.path.exists(path):
                    return {"error": "request", "message": f"Missing upload file: {path}"}
                file_handle = stack.enter_context(open(path, "rb"))
                files[field] = (filename, file_handle, content_type)
            response = client.post(url=url, files=files, data=data, headers=headers)
        return {
            "status_code": response.status_code,
            "content": response.content,
            "text": response.text,
        }
    except httpx.TimeoutException as exc:
        return {"error": "timeout", "message": str(exc)}
    except httpx.RequestError as exc:
        return {"error": "request", "message": str(exc)}
    except Exception as exc:
        return {"error": "unexpected", "message": str(exc)}


class UNIT3D:
    def __init__(self, config: dict[str, Any], tracker_name: str, http_client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self.tracker = tracker_name
        self.common = COMMON(config, http_client=http_client)
        self.tracker_config: dict[str, Any] = self.config["TRACKERS"].get(self.tracker, {})
        self.http_client = http_client

        # Normalize announce_url: must be a non-empty string after stripping
        raw_announce = self.tracker_config.get("announce_url")
        self.announce_url = raw_announce.strip() if isinstance(raw_announce, str) else ""

        # Normalize api_key: must be a non-empty string after stripping
        raw_api_key = self.tracker_config.get("api_key")
        self.api_key = raw_api_key.strip() if isinstance(raw_api_key, str) else ""

        # Default URLs - should be overridden by subclasses
        self.search_url = ""
        self.upload_url = ""

    def get_additional_checks(self, _meta: dict[str, Any]) -> bool:
        should_continue = True
        return should_continue

    async def search_existing(self, meta: dict[str, Any], _: Any) -> list[dict[str, Any]]:
        dupes: list[dict[str, Any]] = []

        # Ensure tracker_status keys exist before any potential writes
        meta.setdefault("tracker_status", {})
        meta["tracker_status"].setdefault(self.tracker, {})

        if not self.api_key:
            if not meta["debug"]:
                await asyncio.to_thread(
                    console.print,
                    f"[bold red]{self.tracker}: Missing API key in config file. Skipping upload...[/bold red]"
                )
            meta["skipping"] = f"{self.tracker}"
            return dupes

        should_continue = self.get_additional_checks(meta)
        if not should_continue:
            meta["skipping"] = f"{self.tracker}"
            return dupes

        headers = {
            "authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
        }

        category_id = str((self.get_category_id(meta))['category_id'])
        params_dict: dict[str, str] = {
            "tmdbId": str(meta['tmdb']),
            "categories[]": category_id,
            "name": "",
            "perPage": "100",
        }
        params_list: Optional[ParamsList] = None
        resolutions = self.get_resolution_id(meta)
        resolution_id = str(resolutions["resolution_id"])
        if resolution_id in ["3", "4"]:
            # Convert params to list of tuples to support duplicate keys
            params_list = list(params_dict.items())
            params_list.append(("resolutions[]", "3"))
            params_list.append(("resolutions[]", "4"))
        else:
            params_dict["resolutions[]"] = resolution_id

        if self.tracker not in ["SP", "STC"]:
            type_id = str((self.get_type_id(meta))["type_id"])
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
        request_params = params_list if params_list is not None else list(params_dict.items())

        try:
            # Use shared client if available, otherwise create temporary one
            if self.http_client:
                response = await self.http_client.get(url=self.search_url, headers=headers, params=request_params)
                response.raise_for_status()
                if response.status_code == 200:
                    response_body = await response.aread()
                    data = await asyncio.to_thread(json.loads, response_body)
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
                                "bd_info": attributes.get("bd_info", ""),
                                "description": attributes.get("description", ""),
                            }
                        dupes.append(result)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
            else:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url=self.search_url, headers=headers, params=request_params)
                    response.raise_for_status()
                    if response.status_code == 200:
                        response_body = await response.aread()
                        data = await asyncio.to_thread(json.loads, response_body)
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
                                    "bd_info": attributes.get("bd_info", ""),
                                    "description": attributes.get("description", ""),
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

    def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"name": meta["name"]}

    async def get_description(self, meta: dict[str, Any], cached_description: Optional[str] = None) -> dict[str, str]:
        tracker_cached = meta.get(f"{self.tracker}_cached_description")
        cached_desc = cached_description or tracker_cached or meta.get("cached_description")
        if cached_desc is not None:
            meta[f"{self.tracker}_description_cache_hit"] = True
            console.print(f"[yellow]{self.tracker} - using cached description[/yellow]")
            return {"description": cast(str, cached_desc)}
        console.print(f"[yellow]{self.tracker} - building fresh description[/yellow]")
        description = await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(
            meta, comparison=True
        )
        meta[f"{self.tracker}_description_cache_hit"] = False
        meta[f"{self.tracker}_cached_description"] = description
        meta[f"{self.tracker}_cached_description_has_logo"] = bool(meta.get("logo"))
        return {"description": description}

    async def get_mediainfo(self, meta: dict[str, Any], mediainfo_text: Optional[str] = None) -> dict[str, str]:
        if meta.get("bdinfo") is not None:
            mediainfo = ""
        else:
            cached_text = mediainfo_text or cast(Optional[str], meta.get("cached_mediainfo_text"))
            if cached_text is not None:
                mediainfo = cached_text
            else:
                cached_bytes = cast(Optional[bytes], meta.get("cached_mediainfo_bytes"))
                if cached_bytes is not None:
                    mediainfo = cached_bytes.decode("utf-8")
                elif meta.get("cached_mediainfo_missing") is True:
                    mediainfo = ""
                else:
                    async with aiofiles.open(
                        f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", encoding="utf-8"
                    ) as f:
                        mediainfo = await f.read()
        return {"mediainfo": mediainfo}

    async def get_bdinfo(self, meta: dict[str, Any], bdinfo_text: Optional[str] = None) -> dict[str, str]:
        if meta.get("bdinfo") is not None:
            cached_text = bdinfo_text or cast(Optional[str], meta.get("cached_bdinfo_text"))
            if cached_text is not None:
                bdinfo = cached_text
            else:
                cached_bytes = cast(Optional[bytes], meta.get("cached_bdinfo_bytes"))
                if cached_bytes is not None:
                    bdinfo = cached_bytes.decode("utf-8")
                elif meta.get("cached_bdinfo_missing") is True:
                    bdinfo = ""
                else:
                    async with aiofiles.open(
                        f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", encoding="utf-8"
                    ) as f:
                        bdinfo = await f.read()
        else:
            bdinfo = ""
        return {"bdinfo": bdinfo}

    def get_category_id(
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

    def get_type_id(
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

    def get_resolution_id(
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

    def get_anonymous(self, meta: dict[str, Any]) -> dict[str, str]:
        anonymous = "0" if meta["anon"] == 0 and not self.tracker_config.get("anon", False) else "1"
        return {"anonymous": anonymous}

    def get_additional_data(self, _meta: dict[str, Any]) -> dict[str, str]:
        # Used to add additional data if needed
        """
        data = {
            'modq': self.get_flag(meta, 'modq'),
            'draft': self.get_flag(meta, 'draft'),
        }
        """
        data: dict[str, str] = {}

        return data

    def get_flag(self, meta: dict[str, Any], flag_name: str) -> str:
        config_flag = self.tracker_config.get(flag_name)
        if meta.get(flag_name, False):
            return "1"
        else:
            if config_flag is not None:
                return "1" if config_flag else "0"
            else:
                return "0"

    def get_distributor_id(self, meta: dict[str, Any]) -> dict[str, str]:
        distributor_id = self.common.unit3d_distributor_ids(meta.get("distributor", ""))
        if distributor_id:
            return {"distributor_id": distributor_id}

        return {}

    def get_region_id(self, meta: dict[str, Any]) -> dict[str, str]:
        region_id = self.common.unit3d_region_ids(meta.get("region", ""))
        if region_id:
            return {"region_id": region_id}

        return {}

    def get_tmdb(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"tmdb": f"{meta['tmdb']}"}

    def get_imdb(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"imdb": f"{meta['imdb']}"}

    def get_tvdb(self, meta: dict[str, Any]) -> dict[str, str]:
        tvdb = meta.get("tvdb_id", 0) if meta["category"] == "TV" else 0
        return {"tvdb": f"{tvdb}"}

    def get_mal(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"mal": f"{meta['mal_id']}"}

    def get_igdb(self, _meta: dict[str, Any]) -> dict[str, str]:
        return {"igdb": "0"}

    def get_stream(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"stream": f"{meta['stream']}"}

    def get_sd(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"sd": f"{meta['sd']}"}

    def get_keywords(self, meta: dict[str, Any]) -> dict[str, str]:
        return {"keywords": meta.get("keywords", "")}

    def get_personal_release(self, meta: dict[str, Any]) -> dict[str, str]:
        personal_release = "1" if meta.get("personalrelease", False) else "0"
        return {"personal_release": personal_release}

    def get_internal(self, meta: dict[str, Any]) -> dict[str, str]:
        internal = "0"
        if self.tracker_config.get("internal", False) is True and meta["tag"] != "" and (
            meta["tag"][1:] in self.tracker_config.get("internal_groups", [])
        ):
            internal = "1"

        return {"internal": internal}

    def get_season_number(self, meta: dict[str, Any]) -> dict[str, str]:
        data = {}
        if meta.get("category") == "TV":
            data = {"season_number": f"{meta.get('season_int', '0')}"}

        return data

    def get_episode_number(self, meta: dict[str, Any]) -> dict[str, str]:
        data = {}
        if meta.get("category") == "TV":
            data = {"episode_number": f"{meta.get('episode_int', '0')}"}

        return data

    def get_featured(self, _meta: dict[str, Any]) -> dict[str, str]:
        return {"featured": "0"}

    def get_free(self, meta: dict[str, Any]) -> dict[str, str]:
        free = "0"
        if meta.get("freeleech", 0) != 0:
            free = f"{meta.get('freeleech', '0')}"

        return {"free": free}

    def get_doubleup(self, _meta: dict[str, Any]) -> dict[str, str]:
        return {"doubleup": "0"}

    def get_sticky(self, _meta: dict[str, Any]) -> dict[str, str]:
        return {"sticky": "0"}

    async def get_data(self, meta: dict[str, Any]) -> dict[str, str]:
        def log_step(label: str, start_time: float) -> None:
            elapsed = time.perf_counter() - start_time
            message = (
                f"[cyan]{self.tracker} timing: {label} {elapsed:.2f}s[/cyan]"
                if elapsed is not None
                else f"[cyan]{self.tracker} timing: {label}[/cyan]"
            )
            if self.config.get("DEFAULT", {}).get("async_timing_logs", True):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    console.print(message)
                else:
                    loop.create_task(asyncio.to_thread(console.print, message))
            else:
                console.print(message)

        async def run_timed_task(label: str, coro: Any, created_at: float) -> Any:
            if meta.get("debug"):
                start_delay = time.perf_counter() - created_at
                console.print(f"[cyan]{self.tracker} timing: {label} start_delay {start_delay:.2f}s[/cyan]")
            result = await coro
            if meta.get("debug"):
                total_elapsed = time.perf_counter() - created_at
                console.print(f"[cyan]{self.tracker} timing: {label} total {total_elapsed:.2f}s[/cyan]")
            return result

        cached_description = cast(Optional[str], meta.get("cached_description"))
        mediainfo_text = cast(Optional[str], meta.get("cached_mediainfo_text"))
        bdinfo_text = cast(Optional[str], meta.get("cached_bdinfo_text"))

        gather_start = time.perf_counter()

        # Create tasks to track when each completes
        task_created = time.perf_counter()
        desc_task = asyncio.create_task(
            run_timed_task("get_description(task)", self.get_description(meta, cached_description=cached_description), task_created)
        )
        mediainfo_task = asyncio.create_task(
            run_timed_task("get_mediainfo(task)", self.get_mediainfo(meta, mediainfo_text=mediainfo_text), task_created)
        )
        bdinfo_task = asyncio.create_task(
            run_timed_task("get_bdinfo(task)", self.get_bdinfo(meta, bdinfo_text=bdinfo_text), task_created)
        )

        description = await desc_task
        desc_time = time.perf_counter() - gather_start
        console.print(f"[cyan]{self.tracker} timing: get_description (completed) {desc_time:.2f}s[/cyan]")

        mediainfo = await mediainfo_task
        mediainfo_time = time.perf_counter() - gather_start
        console.print(f"[cyan]{self.tracker} timing: get_mediainfo (completed) {mediainfo_time:.2f}s[/cyan]")

        bdinfo = await bdinfo_task
        bdinfo_time = time.perf_counter() - gather_start
        console.print(f"[cyan]{self.tracker} timing: get_bdinfo (completed) {bdinfo_time:.2f}s[/cyan]")

        log_step("get_description/mediainfo/bdinfo (all completed)", gather_start)

        merged: dict[str, str] = {}
        step_start = time.perf_counter()
        merged.update(self.get_name(meta))
        log_step("get_name()", step_start)
        merged.update(description)
        merged.update(mediainfo)
        merged.update(bdinfo)
        step_start = time.perf_counter()
        merged.update(self.get_category_id(meta))
        log_step("get_category_id()", step_start)
        step_start = time.perf_counter()
        merged.update(self.get_type_id(meta))
        log_step("get_type_id()", step_start)
        step_start = time.perf_counter()
        merged.update(self.get_resolution_id(meta))
        log_step("get_resolution_id()", step_start)

        step_start = time.perf_counter()
        merged.update(self.get_tmdb(meta))
        merged.update(self.get_imdb(meta))
        merged.update(self.get_tvdb(meta))
        merged.update(self.get_mal(meta))
        merged.update(self.get_igdb(meta))
        log_step("get_ids()", step_start)

        step_start = time.perf_counter()
        merged.update(self.get_anonymous(meta))
        merged.update(self.get_stream(meta))
        merged.update(self.get_sd(meta))
        merged.update(self.get_keywords(meta))
        merged.update(self.get_personal_release(meta))
        merged.update(self.get_internal(meta))
        log_step("get_flags()", step_start)

        step_start = time.perf_counter()
        merged.update(self.get_season_number(meta))
        merged.update(self.get_episode_number(meta))
        merged.update(self.get_featured(meta))
        merged.update(self.get_free(meta))
        merged.update(self.get_doubleup(meta))
        merged.update(self.get_sticky(meta))
        log_step("get_episode_flags()", step_start)

        additional_start = time.perf_counter()
        merged.update(self.get_additional_data(meta))
        log_step("get_additional_data()", additional_start)

        step_start = time.perf_counter()
        merged.update(self.get_region_id(meta))
        merged.update(self.get_distributor_id(meta))
        log_step("get_region_distributor()", step_start)

        # Handle exclusive flag centrally for all UNIT3D trackers
        # Priority: meta['exclusive'] > tracker config > default (not set)
        exclusive_flag = None
        if meta.get("exclusive", False) or self.tracker_config.get("exclusive", False):
            exclusive_flag = "1"
        if exclusive_flag:
            merged["exclusive"] = exclusive_flag

        return merged

    async def get_additional_files(
        self,
        meta: dict[str, Any],
        nfo_bytes: Optional[bytes] = None,
        nfo_name: Optional[str] = None,
    ) -> dict[str, tuple[str, bytes, str]]:
        files: dict[str, tuple[str, bytes, str]] = {}
        if meta.get("cached_nfo_missing") is True and nfo_bytes is None:
            return files
        cached_bytes = nfo_bytes if nfo_bytes is not None else meta.get("cached_nfo_bytes")
        cached_name = nfo_name if nfo_name is not None else meta.get("cached_nfo_name")
        if isinstance(cached_bytes, (bytes, bytearray)):
            nfo_name = str(cached_name) if cached_name else "nfo_file.nfo"
            files["nfo"] = (nfo_name, bytes(cached_bytes), "text/plain")
            return files
        base_dir = meta["base_dir"]
        uuid = meta["uuid"]
        tmp_dir = os.path.join(base_dir, "tmp", uuid)
        nfo_files = await asyncio.to_thread(self._list_nfo_files, tmp_dir)

        if (
            not nfo_files
            and meta.get("keep_nfo", False)
            and (meta.get("keep_folder", False) or meta.get("isdir", False))
        ):
            search_dir = os.path.dirname(meta["path"])
            nfo_files = await asyncio.to_thread(self._list_nfo_files, search_dir)

        if nfo_files:
            async with aiofiles.open(nfo_files[0], "rb") as f:
                nfo_bytes = await f.read()
            files["nfo"] = ("nfo_file.nfo", nfo_bytes, "text/plain")

        return files

    async def upload(self, meta: dict[str, Any], _: Any, torrent_bytes: Optional[bytes] = None) -> bool:
        timing_enabled = True

        def log_timing(label: str, start_time: Optional[float] = None) -> None:
            if not timing_enabled:
                return
            elapsed = None
            if start_time is not None:
                elapsed = time.perf_counter() - start_time
            message = (
                f"[cyan]{self.tracker} timing: {label} {elapsed:.2f}s[/cyan]"
                if elapsed is not None
                else f"[cyan]{self.tracker} timing: {label}[/cyan]"
            )

            if self.config.get("DEFAULT", {}).get("async_timing_logs", True):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    console.print(message)
                else:
                    loop.create_task(asyncio.to_thread(console.print, message))
            else:
                console.print(message)

        async def loop_lag_probe(
            stop_event: asyncio.Event,
            get_phase: Any,
            interval: float = 0.2,
            warn_threshold: float = 0.5,
        ) -> None:
            last_tick = time.perf_counter()
            while not stop_event.is_set():
                await asyncio.sleep(interval)
                now = time.perf_counter()
                lag = now - last_tick - interval
                if lag > warn_threshold:
                    phase = get_phase() or "unknown"
                    console.print(
                        f"[yellow]{self.tracker} timing: upload_loop lag {lag:.2f}s (phase: {phase})[/yellow]"
                    )
                last_tick = now

        data_start = time.perf_counter()
        data = await self.get_data(meta)
        log_timing("get_data()", data_start)
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        if meta.get("debug") is True:
            if torrent_bytes is None:
                torrent_read_start = time.perf_counter()
                async with aiofiles.open(torrent_file_path, "rb") as f:
                    torrent_bytes = await f.read()
                log_timing("read BASE.torrent", torrent_read_start)
            else:
                log_timing("read BASE.torrent (preloaded)")
        else:
            log_timing("read BASE.torrent (path)")

        additional_files_start = time.perf_counter()
        nfo_source = "none"
        nfo_spec: Optional[dict[str, str]] = None
        cached_nfo_bytes = cast(Optional[bytes], meta.get("cached_nfo_bytes"))
        cached_nfo_name = cast(Optional[str], meta.get("cached_nfo_name"))
        base_dir = meta["base_dir"]
        uuid = meta["uuid"]
        tmp_dir = os.path.join(base_dir, "tmp", uuid)

        if cached_nfo_bytes is not None:
            nfo_filename = os.path.basename(cached_nfo_name or "nfo_file.nfo")
            cached_nfo_path = os.path.join(tmp_dir, f"CACHED_{nfo_filename}")
            async with aiofiles.open(cached_nfo_path, "wb") as f:
                await f.write(cached_nfo_bytes)
            nfo_source = "cached"
            nfo_spec = {
                "field": "nfo",
                "path": cached_nfo_path,
                "filename": nfo_filename,
                "content_type": "text/plain",
            }
        elif meta.get("cached_nfo_missing") is not True:
            nfo_files = await asyncio.to_thread(self._list_nfo_files, tmp_dir)
            if (
                not nfo_files
                and meta.get("keep_nfo", False)
                and (meta.get("keep_folder", False) or meta.get("isdir", False))
            ):
                search_dir = os.path.dirname(meta["path"])
                nfo_files = await asyncio.to_thread(self._list_nfo_files, search_dir)

            if nfo_files:
                nfo_path = nfo_files[0]
                nfo_source = "disk"
                nfo_spec = {
                    "field": "nfo",
                    "path": nfo_path,
                    "filename": os.path.basename(nfo_path),
                    "content_type": "text/plain",
                }

        log_timing(f"get_additional_files() [{nfo_source}]", additional_files_start)

        file_specs: list[dict[str, str]] = [
            {
                "field": "torrent",
                "path": torrent_file_path,
                "filename": "torrent.torrent",
                "content_type": "application/x-bittorrent",
            }
        ]
        if nfo_spec:
            file_specs.append(nfo_spec)

        request_prep_start = time.perf_counter()
        headers = {
            "User-Agent": f'{meta["ua_name"]} {meta.get("current_version", "")} ({platform.system()} {platform.release()})',
            "authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
        }
        log_timing("prepare_request_headers", request_prep_start)

        probe_task: Optional[asyncio.Task[None]] = None
        probe_stop: Optional[asyncio.Event] = None
        phase_state = {"value": "idle"}
        if meta.get("debug") is False and self.config.get("DEFAULT", {}).get("async_timing_logs", True):
            probe_stop = asyncio.Event()
            probe_task = asyncio.create_task(loop_lag_probe(probe_stop, lambda: phase_state["value"]))

        try:
            if meta["debug"] is False:
                max_retries = 2
                retry_delay = 5
                timeout = 40.0

                # Use higher limits for concurrent uploads
                limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)

                async def perform_upload() -> tuple[bool, dict[str, Any]]:
                    """Perform the upload with retry logic."""
                    nonlocal timeout
                    response_data: dict[str, Any] = {}
                    for attempt in range(max_retries):
                        attempt_start = time.perf_counter()
                        try:  # noqa: PERF203
                            phase_state["value"] = "post"
                            payload = {
                                "url": self.upload_url,
                                "data": data,
                                "file_specs": file_specs,
                                "headers": headers,
                                "timeout": timeout,
                                "max_keepalive": limits.max_keepalive_connections or 0,
                                "max_connections": limits.max_connections or 0,
                            }
                            upload_workers_raw = self.config.get("DEFAULT", {}).get("max_concurrent_uploads")
                            upload_workers: Optional[int]
                            if upload_workers_raw in (None, ""):
                                upload_workers = os.cpu_count() or 4
                            else:
                                try:
                                    upload_workers = int(upload_workers_raw)
                                except (TypeError, ValueError):
                                    upload_workers = os.cpu_count() or 4
                            loop = asyncio.get_running_loop()
                            result = await loop.run_in_executor(
                                get_upload_process_executor(upload_workers),
                                _unit3d_upload_worker,
                                payload,
                            )
                            if result.get("error") == "timeout":
                                raise httpx.TimeoutException(result.get("message", "timeout"))
                            if result.get("error"):
                                raise httpx.RequestError(result.get("message", "request error"))
                            status_code = int(result.get("status_code", 0) or 0)
                            response_text = str(result.get("text", ""))
                            response_body = cast(bytes, result.get("content") or b"")
                            if status_code < 200 or status_code >= 300:
                                request = httpx.Request("POST", self.upload_url)
                                response = httpx.Response(status_code, text=response_text, request=request)
                                raise httpx.HTTPStatusError("HTTP error", request=request, response=response)
                            log_timing(f"upload attempt {attempt + 1} response", attempt_start)
                            response_read_start = time.perf_counter()
                            phase_state["value"] = "read_body"
                            log_timing(f"upload attempt {attempt + 1} read body", response_read_start)

                            response_parse_start = time.perf_counter()
                            phase_state["value"] = "parse_json"
                            response_data = await asyncio.to_thread(json.loads, response_body)
                            log_timing(f"upload attempt {attempt + 1} parse", response_parse_start)

                            # Verify API success before proceeding
                            if not response_data.get("success"):
                                error_msg = response_data.get("message", "Unknown error")
                                meta["tracker_status"][self.tracker]["status_message"] = f"API error: {error_msg}"
                                console.print(f"[yellow]Upload to {self.tracker} failed: {error_msg}[/yellow]")
                                return False, response_data

                            meta["tracker_status"][self.tracker]["status_message"] = (
                                self.process_response_data(response_data)
                            )
                            torrent_id = self.get_torrent_id(response_data)

                            meta["tracker_status"][self.tracker]["torrent_id"] = torrent_id
                            download_start = time.perf_counter()
                            phase_state["value"] = "download_torrent"
                            await self.common.download_tracker_torrent_process(
                                meta, self.tracker, headers=headers, downurl=response_data["data"]
                            )
                            log_timing("download_tracker_torrent()", download_start)
                            phase_state["value"] = "upload_complete"
                            return True, response_data  # Success

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
                                return False, response_data  # Auth/permission error
                            elif e.response.status_code in [401, 404, 422]:
                                meta["tracker_status"][self.tracker][
                                    "status_message"
                                ] = f"data error: HTTP {e.response.status_code} - {e.response.text}"
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
                                    return False, response_data  # HTTP error after all retries
                        except httpx.TimeoutException:
                            if attempt < max_retries - 1:
                                timeout = timeout * 1.5  # Increase timeout by 50% for next retry
                                console.print(
                                    f"[yellow]{self.tracker}: Request timed out, retrying in {retry_delay} seconds with {timeout}s timeout... (attempt {attempt + 1}/{max_retries})[/yellow]"
                                )
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                meta["tracker_status"][self.tracker]["status_message"] = "data error: Request timed out after multiple attempts"
                                return False, response_data
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
                                return False, response_data
                        except json.JSONDecodeError as e:
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = f"data error: Invalid JSON response from {self.tracker}. Error: {e}"
                            return False, response_data

                    # All retries exhausted
                    return False, response_data

                phase_state["value"] = "perform_upload"
                success, _ = await perform_upload()
                return success
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
                    torrent_bytes=torrent_bytes,
                )
                return True  # Debug mode - simulated success
        finally:
            if probe_task is not None and probe_stop is not None:
                probe_stop.set()
                await probe_task

        return False

    def get_torrent_id(self, response_data: dict[str, Any]) -> str:
        """Matches /12345.abcde and returns 12345"""
        torrent_id = ""
        try:
            match = re.search(r"/(\d+)\.", response_data["data"])
            if match:
                torrent_id = match.group(1)
        except (IndexError, KeyError):
            console.print("Could not parse torrent_id from response data.")
        return torrent_id

    def process_response_data(self, response_data: dict[str, Any]) -> str:
        """Returns the success message from the response data as a string."""
        if response_data.get("success") is True:
            return str(response_data.get("message", "Upload successful"))

        # For non-success responses, format as string
        error_msg = response_data.get("message", "")
        if error_msg:
            return f"API response: {error_msg}"
        return f"API response: {response_data}"

    def _list_nfo_files(self, directory: str) -> list[str]:
        files: list[str] = []
        try:
            entries = os.listdir(directory)
        except OSError:
            return files

        for entry in entries:
            if not entry.lower().endswith(".nfo"):
                continue
            absolute_path = os.path.join(directory, entry)
            if os.path.isfile(absolute_path):
                files.append(absolute_path)
        return files
