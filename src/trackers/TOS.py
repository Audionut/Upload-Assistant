# -*- coding: utf-8 -*-
# import discord
import asyncio
import os
import glob
import aiofiles
import platform
import httpx
from typing import Any
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D
from src.torrentcreate import CustomTorrent, torf_cb, calculate_piece_size
from datetime import datetime
from pathlib import Path


class TOS(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name="TOS")
        self.config = config
        self.common = COMMON(config)
        self.tracker = "TOS"
        self.source_flag = "TheOldSchool"
        self.base_url = "https://theoldschool.cc"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.banned_groups = [
            "FL3ER",
            "SUNS3T",
            "WoLFHD",
            "EXTREME",
            "Slay3R",
            "3T3AM",
            "BARBiE",
        ]
        pass

    async def get_category_id(
        self,
        meta: dict[str, Any],
        category: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        tags_lower = meta["tag"].lower()
        if "vostfr" in tags_lower or "subfrench" in tags_lower:
            if meta["category"] == "TV" and meta.get("tv_pack"):
                category_id = "9"
            else:
                category_id = {
                    "MOVIE": "6",
                    "TV": "7",
                }.get(meta["category"], "0")
        else:
            if meta["category"] == "TV" and meta.get("tv_pack"):
                category_id = "8"
            else:
                category_id = {
                    "MOVIE": "1",
                    "TV": "2",
                }.get(meta["category"], "0")
        return {"category_id": category_id}

    async def get_type_id(
        self,
        meta: dict[str, Any],
        type: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        if meta["is_disc"] == "DVD":
            type_id = "7"
        elif meta.get("3D") == "3D":
            type_id = "8"
        else:
            type_id = {
                "DISC": "1",
                "REMUX": "2",
                "ENCODE": "3",
                "WEBDL": "4",
                "WEBRIP": "5",
                "HDTV": "6",
            }.get(meta["type"], "0")
        return {"type_id": type_id}

    async def get_name(self, meta):
        is_scene = bool(meta.get("scene_name"))
        base_name = meta.get("scene_name") if is_scene else meta.get("uuid")

        if is_scene is False:
            replacements = {
                ".mkv": "",
                ".mp4": "",
                ".torrent": "",
                " ": ".",
            }

            for old, new in replacements.items():
                base_name = base_name.replace(old, new)

        return {"name": base_name}

    async def get_additional_files(
        self, meta: dict[str, Any]
    ) -> dict[str, tuple[str, bytes, str]]:
        files: dict[str, tuple[str, bytes, str]] = {}

        # Determine the directory to search for NFO files
        if os.path.isdir(meta["path"]):
            search_dir = meta["path"]
        else:
            # If path is a file, search in its parent directory
            search_dir = os.path.dirname(meta["path"])

        specified_dir_path = os.path.join(search_dir, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)

        if nfo_files:
            async with aiofiles.open(nfo_files[0], "rb") as f:
                nfo_bytes = await f.read()
            files["nfo"] = ("nfo_file.nfo", nfo_bytes, "text/plain")

        return files

    async def upload(self, meta, disctype):
        # Check language requirements: must be French audio OR original audio with French subtitles
        french_languages = ["french", "fre", "fra", "fr", "français", "francais"]
        if not await self.common.check_language_requirements(
            meta,
            self.tracker,
            languages_to_check=french_languages,
            check_audio=True,
            check_subtitle=True,
        ):
            return

        # Check if it's a Scene release without NFO - TOS requires NFO for Scene releases
        is_scene = bool(meta.get("scene_name"))
        has_nfo = meta.get("nfo", False) or meta.get("auto_nfo", False)

        if is_scene and not has_nfo:
            console.print(
                f"[red]{self.tracker}: Scene release detected but no NFO file found. TOS requires NFO files for Scene releases.[/red]"
            )
            meta["tracker_status"][self.tracker][
                "status_message"
            ] = "Skipped: Scene release requires NFO file"
            return

        data = await self.get_data(meta)

        if meta["isdir"]:
            # As TOS want us to keep directory at upload and upload NFO file, we need to generate a new .torrent
            console.print(
                "[yellow]Uploading a full directory to TOS, generating a new .torrent"
            )
            torrent_file_path = (
                f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            )

            # Use Torf to create torrent as we can change filelist easily
            tracker_url = (
                self.config["TRACKERS"]["TOS"]
                .get("announce_url", "https://fake.tracker")
                .strip()
            )
            if meta["is_disc"]:
                include = []
                exclude = []
            else:
                include = ["*.mkv", "*.mp4", "*.ts", "*.nfo"]
                exclude = ["*.*", "*sample.mkv"]
            initial_size = 0
            path = Path(meta["path"])
            if os.path.isfile(path):
                initial_size = os.path.getsize(path)
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    initial_size += sum(
                        os.path.getsize(os.path.join(root, f))
                        for f in files
                        if os.path.isfile(os.path.join(root, f))
                    )

            piece_size = calculate_piece_size(initial_size, 32768, 134217728, meta)

            new_torrent = CustomTorrent(
                meta=meta,
                path=path,
                trackers=[tracker_url],
                source=self.source_flag,
                private=True,
                exclude_globs=exclude,  # Ensure this is always a list
                include_globs=include,  # Ensure this is always a list
                creation_date=datetime.now(),
                comment="Le seed c'est la vie!",
                created_by="Audionut's Upload Assistant modded by mika23 & CptCherry",
            )

            new_torrent.piece_size = piece_size
            new_torrent.validate_piece_size()
            await asyncio.to_thread(new_torrent.generate, callback=torf_cb, interval=5)
            new_torrent.write(torrent_file_path, overwrite=True)

        else:
            console.print(
                "[green]Uploading a single file to TOS, editing already created .torrent"
            )
            await self.common.create_torrent_for_upload(
                meta, self.tracker, self.source_flag
            )
            # create_torrent_for_upload writes to [TOS].torrent, not BASE.torrent
            torrent_file_path = (
                f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            )

        # normal upload function from UNITED.py
        async with aiofiles.open(torrent_file_path, "rb") as f:
            torrent_bytes = await f.read()
        upload_files: dict[str, tuple[str, bytes, str]] = {
            "torrent": ("torrent.torrent", torrent_bytes, "application/x-bittorrent")
        }
        upload_files.update(await self.get_additional_files(meta))
        headers = {
            "User-Agent": f'{meta["ua_name"]} {meta.get("current_version", "")} ({platform.system()} {platform.release()})'
        }
        params = {"api_token": self.api_key}

        if meta["debug"] is False:
            response_data = {}
            max_retries = 2
            retry_delay = 5
            timeout = 40.0

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=True
                    ) as client:
                        response = await client.post(
                            url=self.upload_url,
                            files=upload_files,
                            data=data,
                            headers=headers,
                            params=params,
                        )
                        response.raise_for_status()

                        response_data = response.json()
                        meta["tracker_status"][self.tracker]["status_message"] = (
                            await self.process_response_data(response_data)
                        )
                        torrent_id = await self.get_torrent_id(response_data)

                        meta["tracker_status"][self.tracker]["torrent_id"] = torrent_id
                        await self.common.download_tracker_torrent(
                            meta,
                            self.tracker,
                            headers=headers,
                            params=params,
                            downurl=response_data["data"],
                        )
                        break  # Success, exit retry loop

                except httpx.HTTPStatusError as e:
                    # Check if upload already exists (can happen after timeout)
                    is_dupe = False
                    if (
                        "The name has already been taken" in e.response.text
                        or "The info hash has already been taken" in e.response.text
                    ):
                        is_dupe = True

                    # Also check for French error message in JSON (404 with info_hash already used)
                    if e.response.status_code == 404:
                        try:
                            error_data = e.response.json()
                            if error_data.get("success") is False:
                                data_errors = error_data.get("data", {})
                                # Check if info_hash error exists (French or English)
                                if "info_hash" in data_errors:
                                    error_msg = str(data_errors["info_hash"])
                                    if (
                                        "déjà utilisée" in error_msg
                                        or "already been taken" in error_msg
                                    ):
                                        is_dupe = True
                        except Exception:
                            pass

                    if is_dupe:
                        try:
                            error_data = e.response.json()
                            existing_torrent = error_data.get("data", {}).get(
                                "existing_torrent", {}
                            )
                            torrent_id = str(existing_torrent.get("existing_id", ""))
                            download_url = existing_torrent.get("download_url", "")

                            if torrent_id and download_url:
                                meta["tracker_status"][self.tracker][
                                    "status_message"
                                ] = "Found the uploaded torrent (it was already uploaded successfully)."
                                meta["tracker_status"][self.tracker][
                                    "torrent_id"
                                ] = torrent_id
                                await self.common.download_tracker_torrent(
                                    meta,
                                    self.tracker,
                                    headers=headers,
                                    params=params,
                                    downurl=download_url,
                                )
                                break  # Success, exit retry loop
                            else:
                                # Dupe detected but no existing torrent info - just skip without error
                                console.print(
                                    f"[yellow]{self.tracker}: Torrent already exists (dupe detected)[/yellow]"
                                )
                                meta["tracker_status"][self.tracker][
                                    "status_message"
                                ] = "Skipped: Torrent already exists on tracker"
                                break  # Don't retry, exit as if successful
                        except Exception:
                            console.print(
                                f"[yellow]{self.tracker}: Torrent already exists (dupe detected)[/yellow]"
                            )
                            meta["tracker_status"][self.tracker][
                                "status_message"
                            ] = "Skipped: Torrent already exists on tracker"
                            break  # Don't retry, exit as if successful

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
                        break  # Don't retry
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
                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        timeout = (
                            timeout * 2.00
                        )  # Increase timeout by 100% for next retry
                        console.print(
                            f"[yellow]{self.tracker}: Request timed out, retrying in {retry_delay} seconds with {timeout}s timeout... (attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        meta["tracker_status"][self.tracker][
                            "status_message"
                        ] = "data error: Request timed out after multiple attempts"
                        return False
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
                        return False
                except Exception as e:
                    meta["tracker_status"][self.tracker][
                        "status_message"
                    ] = f"data error: It may have uploaded, go check. Error: {e}.\nResponse: {response_data}"
                    return False
            return True
        else:
            console.print(f"[cyan]{self.tracker} Request Data:")
            console.print(data)
            meta["tracker_status"][self.tracker][
                "status_message"
            ] = f"Debug mode enabled, not uploading: {self.tracker}."
            return True
