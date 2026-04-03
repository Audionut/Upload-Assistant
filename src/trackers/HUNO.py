# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

import aiofiles
import httpx

from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.rehostimages import RehostImagesManager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class HUNO(UNIT3D):
    """
    https://hawke.uno/api-docs
    """
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, "HUNO")
        self.config = config
        self.common = COMMON(config)
        self.rehost_images_manager = RehostImagesManager(config)
        self.tracker = "HUNO"
        self.source_flag = "HUNO"
        self.base_url = "https://hawke.uno"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.announce_url = str(self.config.get("TRACKERS", {}).get(self.tracker, {}).get("announce_url", "")).strip()
        self.banned_groups = [
            '4K4U', 'Bearfish', 'BiTOR', 'BONE', 'D3FiL3R', 'd3g', 'DTR', 'ELiTE',
            'EVO', 'eztv', 'EzzRips', 'FGT', 'HashMiner', 'HETeam', 'HEVCBay', 'HiQVE',
            'HR-DR', 'iFT', 'ION265', 'iVy', 'JATT', 'Joy', 'LAMA', 'm3th', 'MeGusta',
            'MRN', 'Musafirboy', 'OEPlus', 'Pahe.in', 'PHOCiS', 'PSA', 'RARBG', 'RMTeam',
            'ShieldBearer', 'SiQ', 'TBD', 'Telly', 'TSP', 'VXT', 'WKS', 'YAWNiX', 'YIFY', 'YTS'
        ]  # fmt: off
        self.approved_image_hosts = [
            "ptpimg",
            "imgbox",
            "imgbb",
            "pixhost",
            "bam",
            "onlyimage",
            "ptscreens",
            "passtheimage",
            "hawke.pics",
        ]
        pass

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True

        # No WEBRIPs allowed
        if meta["type"] == "WEBRIP":
            console.print(f"{self.tracker}: [bold red]WEB-RIP is not allowed, skipping upload.[/bold red]")
            return False

        # Check language requirements
        if not meta.get("language_checked", False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
        audio_languages = meta.get("audio_languages")
        if not audio_languages:
            console.print(f"{self.tracker}: [bold red]No audio languages found, skipping upload.[/bold red]")
            return False

        # Check if mediainfo is valid
        if not meta["valid_mi_settings"]:
            console.print(f"{self.tracker}: [bold red]No encoding settings in mediainfo, skipping upload.[/bold red]")
            return False

        # Check if announce URL is configured
        if not self.announce_url:
            console.print(f"{self.tracker}: [bold red]Missing announce URL in config.[/bold red]")
            return False

        # Check if x265 or HEVC is used
        if not meta["is_disc"] and meta["type"] in ["ENCODE", "DVDRIP", "HDTV"] and ("x265" in meta.get("video_encode", "") or "HEVC" in meta.get("video_codec", "")):
            tracks = meta.get("mediainfo", {}).get("media", {}).get("track", [])
            for track in tracks:
                if track.get("@type") == "Video":
                    encoding_settings = track.get("Encoded_Library_Settings", {})

                    if encoding_settings:
                        crf_match = re.search(r"crf[ =:]+([\d.]+)", encoding_settings, re.IGNORECASE)
                        if crf_match:
                            if meta.get("debug", False):
                                console.print(f"Found CRF value: {crf_match.group(1)}")
                            crf_value = float(crf_match.group(1))
                            if crf_value > 22:
                                if not meta["unattended"]:
                                    console.print(f"CRF value too high: {crf_value} for HUNO")
                                return False
                        else:
                            if meta.get("debug", False):
                                console.print("No CRF value found in encoding settings.")
                            bit_rate = track.get("BitRate")
                            if bit_rate and "Animation" not in meta.get("genre", ""):
                                try:
                                    bit_rate_num = int(bit_rate)
                                except (ValueError, TypeError):
                                    bit_rate_num = None

                                if bit_rate_num is not None:
                                    bit_rate_kbps = bit_rate_num / 1000

                                    if bit_rate_kbps < 3000:
                                        if not meta.get("unattended", False):
                                            console.print(f"Video bitrate too low: {bit_rate_kbps:.0f} kbps for HUNO")
                                        return False

        return should_continue

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "imagebam.com": "bam",
            "hawke.pics": "hawke.pics",
            "onlyimage.org": "onlyimage",
            "ptscreens.com": "ptscreens",
            "passtheimage.me": "passtheimage",
        }
        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts,
        )

    async def get_description(self, meta: dict[str, Any]) -> None:
        image_list = meta["HUNO_images_key"] if "HUNO_images_key" in meta else meta["image_list"]

        desc = await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta, image_list=image_list, approved_image_hosts=self.approved_image_hosts)
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", "w", encoding="utf-8") as f:
            await f.write(desc)

    async def get_internal(self, meta: dict[str, Any]) -> int:
        internal = 0
        if (
            self.config["TRACKERS"][self.tracker].get("internal", False) is True
            and meta["tag"] != ""
            and (meta["tag"][1:] in self.config["TRACKERS"][self.tracker].get("internal_groups", []))
        ):
            internal = 1

        return internal

    async def get_resolution_id(self, meta: dict[str, Any], resolution: str = "", reverse: bool = False, mapping_only: bool = False) -> dict[str, str]:
        resolution_id = {
            "Other": "10",
            "4320p": "1",
            "2160p": "2",
            "1080p": "3",
            "1080i": "4",
            "720p": "5",
            "576p": "6",
            "576i": "7",
            "540p": "11",
            # no mapping for 540i
            "540i": "11",
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

    async def get_type_id(self, meta: dict[str, Any], type: str = "", reverse: bool = False, mapping_only: bool = False) -> dict[str, str]:
        type_id = {
            "DISC": "1",
            "REMUX": "2",
            "WEBDL": "3",
            "WEBRIP": "15",
            "HDTV": "15",
            "ENCODE": "15",
            "DVDRIP": "15",
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

    async def get_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        await self.get_description(meta)

        data: dict[str, Any] = {
            "category_id": 1 if meta.get("category") == "MOVIE" else 2,
            "type_id": (await self.get_type_id(meta))["type_id"],
            "tmdb": meta.get("tmdb"),
            "anonymous": 1 if meta.get("anon", False) else 0,
        }

        internal = await self.get_internal(meta)
        if internal == 1:
            data["internal"] = 1

        if meta.get("is_disc"):
            region = meta.get("region")
            distributor = meta.get("distributor")
            if region:
                data["region"] = region
            if distributor:
                data["distributor"] = distributor

        if meta["category"] == "TV":
            season_int = meta.get("season_int")
            episode_int = meta.get("episode_int")
            if season_int:
                data["season_number"] = int(season_int)
            if episode_int:
                data["episode_number"] = int(episode_int)

        return data

    async def get_files(self, meta: dict[str, Any]) -> dict[str, tuple[str, bytes, str]]:
        files: dict[str, tuple[str, bytes, str]] = {}
        await self.common.create_torrent_for_upload(meta, self.tracker, self.source_flag, announce_url=self.announce_url)
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_path, "rb") as f:
            files["torrent"] = (f"{meta['clean_name']}.torrent", await f.read(), "application/x-bittorrent")

        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        async with aiofiles.open(desc_path, "rb") as f:
            files["description"] = ("description.txt", await f.read(), "text/plain")

        if meta.get("is_disc", "") == "BDMV":
            bdinfo_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            async with aiofiles.open(bdinfo_path, "rb") as f:
                files["bdinfo"] = ("bdinfo.txt", await f.read(), "text/plain")
        else:
            mediainfo_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            async with aiofiles.open(mediainfo_path, "rb") as f:
                files["mediainfo"] = ("mediainfo.txt", await f.read(), "text/plain")

        return files

    async def upload(self, meta: dict[str, Any], _: str = "") -> bool:
        data = await self.get_data(meta)

        # Initialize tracker status
        meta.setdefault("tracker_status", {})
        meta["tracker_status"].setdefault(self.tracker, {})

        api_token = str(self.config["TRACKERS"][self.tracker].get("api_key", ""))
        if not api_token:
            console.print(f"[bold red]{self.tracker}: Missing API key in config.[/bold red]")
            meta["skipping"] = self.tracker
            return False

        url = f"{self.upload_url}?api_token={api_token}"

        if meta.get("debug", False):
            console.print(f"[cyan]{self.tracker} Request Data:")
            console.print(data)
            meta["tracker_status"][self.tracker]["status_message"] = "Debug mode enabled, not uploading."
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}_DEBUG", f"{self.tracker}_DEBUG", announce_url="https://fake.tracker")
            return True

        try:
            files = await self.get_files(meta)

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.post(url=url, data=data, files=files)
                response.raise_for_status()
                response_json = response.json()

                if response_json.get("success") is True:
                    response_data = response_json.get("data", {})
                    moderation_status = response_data.get("moderation_status", "")
                    warnings = response_data.get("warnings", [])
                    name_issues = response_data.get("name_issues", [])
                    status_message = f"{response_json.get('message')}\nModeration Status: {moderation_status}\nWarnings: {warnings}\nName Issues: {name_issues}"
                    meta["tracker_status"][self.tracker]["status_message"] = status_message
                    return True
                else:
                    error_msg = response_json.get("message", "Unknown error")
                    meta["tracker_status"][self.tracker]["status_message"] = f"data error: API error: {error_msg}"
                    console.print(f"[yellow]Upload to {self.tracker} failed: {error_msg}[/yellow]")
                    return False

        except httpx.HTTPStatusError as e:
            msg = f"HTTP {e.response.status_code} - {e.response.text}"
            meta["tracker_status"][self.tracker]["status_message"] = f"data error: {msg}"
            console.print(f"[bold red]{self.tracker} Upload error: {msg}[/bold red]")
            return False
        except Exception as e:
            meta["tracker_status"][self.tracker]["status_message"] = f"data error: {e}"
            console.print(f"[bold red]{self.tracker} Upload unexpected error: {e}[/bold red]")
            return False
