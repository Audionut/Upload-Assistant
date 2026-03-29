# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from typing import Any, Optional, cast
from urllib.parse import urlparse, urlunparse

import aiofiles
import httpx
from bs4 import BeautifulSoup

from cogs.redaction import Redaction
from src.console import console
from src.get_desc import DescriptionBuilder
from src.tmdb import TmdbManager
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class MTEAM:
    """
    API Docs: https://test2.m-team.cc/api/swagger-ui/index.html
    API Limits: https://wiki.m-team.cc/zh-tw/api
    Upload Rules: https://wiki.m-team.cc/zh-tw/upload-rules
    """

    def __init__(self, config: Config):
        self.config = config
        self.common = COMMON(config)
        self.tmdb_manager = TmdbManager(config)

        self.tracker = "MTEAM"

        raw_url = self.config["TRACKERS"][self.tracker].get("base_url", "kp.m-team.cc").strip()
        parsed_raw = urlparse(raw_url)
        clean_netloc = parsed_raw.netloc if parsed_raw.netloc else parsed_raw.path
        self.base_url = urlunparse(("https", clean_netloc, "", "", "", ""))

        self.api_base_url = "https://api.m-team.cc/api"
        self.torrent_url = f"{self.base_url}/detail/"
        self.requests_url = f"{self.api_base_url}/seek/search"
        self.api_key = self.config["TRACKERS"][self.tracker].get("api_key")

        self.banned_groups = ["FGT"]

        self.session = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "Accept": "*/*",
            },
            timeout=30.0,
        )

        self.douban_id: int = 0

    async def get_requests(self, meta: dict[str, Any]) -> list[dict[str, str]]:
        requests: list[dict[str, str]] = []

        category = self.get_category_id(meta)

        payload = {
            "pageNumber": 1,
            "pageSize": 10,
            "keyword": meta["title"],
            "take": False,
        }

        try:
            response = await self.session.post(self.requests_url, json=payload, timeout=15)
            response.raise_for_status()
            res_json = response.json()

            data_list = res_json.get("data", {}).get("data", [])

            for item in data_list:
                if item.get("category") != category:
                    continue

                name = item.get("title", "N/A")
                reward = item.get("rewardCurrent", "0")
                link = f"{self.base_url}/seekDetail?id={item.get('id')}"

                requests.append(
                    {
                        "Name": name,
                        "Reward": reward,
                        "Link": link,
                    }
                )

            if requests:
                message = f"\n{self.tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n"
                for r in requests:
                    message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                    message += f"[bold green]Reward:[/bold green] {r['Reward']}\n"
                    message += f"[bold green]Link:[/bold green] {r['Link']}\n\n"
                console.print(message)

            return requests

        except Exception as e:
            console.print(f"{self.tracker}: [bold red]Error searching for requests with title {meta['title']}: {e}[/bold red]")
            return requests

    async def mediainfo(self, meta: Meta) -> str:
        mi_path: str = ""
        mediainfo: str = ""

        if meta.get("is_disc") == "BDMV":
            disc_folder = os.path.join(meta["base_dir"], "tmp", meta["uuid"])
            for filename in os.listdir(disc_folder):
                if filename.endswith("_FULL.txt"):
                    mi_path = os.path.join(disc_folder, filename)
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"

        if mi_path:
            async with aiofiles.open(mi_path, encoding="utf-8") as f:
                mediainfo = await f.read()

        return mediainfo

    def bbcode_to_markdown(self, text):
        specific_img_pattern = r"\[url=[^\]]*\]\[img(?:=[^\]]*)?\](.*?)\[/img\]\[/url\]"
        text = re.sub(specific_img_pattern, r"![](\1)", text, flags=re.IGNORECASE)

        patterns = [
            (r"\[b\](.*?)\[/b\]", r"**\1**"),
            (r"\[i\](.*?)\[/i\]", r"*\1*"),
            (r"\[u\](.*?)\[/u\]", r"<u>\1</u>"),
            (r"\[s\](.*?)\[/s\]", r"~~\1~~"),
            (r"\[img(?:=[^\]]*)?\](.*?)\[/img\]", r"![](\1)"),
            (r"\[url=(.*?)\](.*?)\[/url\]", r"[\2](\1)"),
            (r"\[url\](.*?)\[/url\]", r"<\1>"),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)

        return text

    async def get_douban_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {}
        if not self.douban_id:
            return info

        api_url = f"{self.api_base_url}/media/douban/infoV2"

        params = {
            "code": self.douban_id,
            "refresh": False,
        }

        headers = {
            "x-api-key": self.api_key,
            "Accept": "*/*",
        }

        try:
            response = await self.session.post(api_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            info = response.json()
            return info

        except Exception as e:
            console.print(f"Error fetching Douban info: {e}")
            return info

    async def mteam_standard_desc(self, meta: Meta):
        db_info = await self.get_douban_info()

        if db_info and db_info.get("code") == "0":
            d = db_info.get("data", {})
            title = d.get("title", "")
            aka = d.get("aka", [])
            translated_names = " / ".join([title] + aka) if title else " / ".join(aka)

            countries = " / ".join(d.get("countries", []))
            genres = " / ".join(d.get("genres", []))
            languages = " / ".join(d.get("languages", []))
            pubdates = " / ".join(d.get("pubdate", []))
            durations = " / ".join(d.get("durations", []))

            directors = " / ".join([person.get("name", "") for person in d.get("directors", [])])
            actors = " / ".join([person.get("name", "") for person in d.get("actors", [])])

            rating_val = d.get("score", "0")
            rating_count = d.get("rating", {}).get("count", "0")
            subject_id = d.get("subjectId", "")

            desc = [
                f"![]({d.get('coverUrl', '')})",
                "",
                f"**◎译　　名** {translated_names}",
                f"**◎片　　名** {title}",
                f"**◎年　　代** {d.get('year', 'N/A')}",
                f"**◎产　　地** {countries}",
                f"**◎类　　别** {genres}",
                f"**◎语　　言** {languages}",
                f"**◎上映日期** {pubdates}",
                f"**◎豆瓣评分** {rating_val}/10 from {rating_count} users",
                f"**◎豆瓣链接** https://www.douban.com/subject/{subject_id}/",
                f"**◎片　　长** {durations}",
                f"**◎导　　演** {directors}",
                f"**◎主　　演** {actors}",
                "",
                "**◎简　　介**",
                "",
                f"　　{d.get('intro', '')}",
            ]
            return "\n".join(desc)

        # Fallback
        console.print(f"{self.tracker}: Douban information is unavailable, using an alternative English version for the description.")
        imdb = meta.get("imdb_info", {})

        tmdb_poster_path = str(meta.get("tmdb_poster") or "").strip()
        tmdb_poster = f"https://image.tmdb.org/t/p/w200{tmdb_poster_path}" if tmdb_poster_path else ""
        poster_url = tmdb_poster or str(imdb.get("cover") or "")
        title = meta.get("title", "N/A")
        year = meta.get("year", "N/A")
        rating = imdb.get("rating", "N/A")

        writers = imdb.get("writers", [])
        creators_str = " / ".join(writers)

        cast = meta.get("tmdb_cast", [])
        actors_str = " / ".join(cast)

        plot = imdb.get("plot", meta.get("overview", ""))

        desc = [
            f"![]({poster_url})",
            "",
            f"**Title**: {title}",
            f"**Year**: {year}",
            f"**IMDb Rating**: {rating}/10",
            f"**Creators**: {creators_str}",
            f"**Actors**: {actors_str}",
            "",
            "### Introduction",
            "",
            f"  {plot}",
        ]

        return "\n".join(desc)

    async def generate_description(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        custom_header = await builder.get_custom_header()
        desc_parts.append(custom_header)

        # M-Team Standard Description
        desc_parts.append(await self.mteam_standard_desc(meta))

        # User description
        user_description = await builder.get_user_description(meta)
        desc_parts.append(user_description)

        # Disc menus screenshots header
        menu_images_value = meta.get("menu_images", [])
        menu_images: list[dict[str, Any]] = []
        if isinstance(menu_images_value, list):
            menu_images_list = cast(list[Any], menu_images_value)
            menu_images.extend([cast(dict[str, Any], item) for item in menu_images_list if isinstance(item, dict)])
        if menu_images:
            desc_parts.append(await builder.menu_screenshot_header(meta))

            # Disc menus screenshots
            menu_screenshots_block = ""
            for image in menu_images:
                menu_raw_url = image.get("raw_url")
                if menu_raw_url:
                    menu_screenshots_block += f"![]({menu_raw_url})"
            if menu_screenshots_block:
                desc_parts.append(menu_screenshots_block)

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        # Screenshot Header
        images_value = meta.get("image_list", [])
        images: list[dict[str, Any]] = []
        if isinstance(images_value, list):
            images_list = cast(list[Any], images_value)
            images.extend([cast(dict[str, Any], item) for item in images_list if isinstance(item, dict)])
        if images:
            desc_parts.append(await builder.screenshot_header())

            # Screenshots
            if images:
                screenshots_block = ""
                for image in images:
                    raw_url = image.get("raw_url")
                    if raw_url:
                        screenshots_block += f"![]({raw_url})"
                if screenshots_block:
                    desc_parts.append(screenshots_block)

        # Signature
        desc_parts.append(f"[{meta['ua_signature']}](https://github.com/Audionut/Upload-Assistant)")

        description = "\n\n".join(part for part in desc_parts if part.strip())

        from src.bbcode import BBCODE

        bbcode = BBCODE()
        description = description.strip()
        description = description.replace("[*] ", "• ").replace("[*]", "• ")
        description = self.bbcode_to_markdown(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", "w", encoding="utf-8") as description_file:
            await description_file.write(description)

        return description

    def get_category_id(self, meta: Meta) -> Optional[int]:
        movie_sd = 401  # Movie/SD
        movie_hd = 419  # Movie/HD
        movie_dvdiso = 420  # Movie/DVDiSo
        movie_blu_ray = 421  # Movie/Blu-Ray
        movie_remux = 439  # Movie/Remux
        tv_series_sd = 403  # TV Series/SD
        tv_series_hd = 402  # TV Series/HD
        tv_series_bd = 438  # TV Series/BD
        tv_series_dvdiso = 435  # TV Series/DVDiSo
        anime = 405  # Anime

        is_sd = meta.get("sd", False)
        is_dvd = meta.get("is_disc") == "DVD"
        is_bd = meta.get("is_disc") == "BDMV"
        is_remux = meta.get("type", "") == "REMUX"
        is_anime = meta.get("anime", False)

        if is_anime:
            return anime

        if is_bd:
            return tv_series_bd if meta["category"] == "TV" else movie_blu_ray

        if is_remux and meta["category"] == "MOVIE":
            return movie_remux

        if is_dvd:
            return tv_series_dvdiso if meta["category"] == "TV" else movie_dvdiso

        if is_sd:
            return tv_series_sd if meta["category"] == "TV" else movie_sd

        # Default to HD
        return tv_series_hd if meta["category"] == "TV" else movie_hd

    def get_small_description(self, meta: Meta) -> str:
        resolution = meta.get("resolution", "")
        audio = meta.get("audio", "")
        video_bitrate, audio_bitrate = self.get_bitrates(meta)

        return f"{resolution} @ {video_bitrate} kbps - {audio} @ {audio_bitrate} kbps"

    def get_bitrates(self, meta) -> tuple[int, int]:
        v_raw = None
        a_raw = None
        is_bdmv = meta.get("is_disc") == "BDMV"
        is_dvd = meta.get("is_disc") == "DVD"

        if is_bdmv:
            discs = meta.get("discs", [])
            if discs:
                bdinfo = discs[0].get("bdinfo", {})
                v_tracks = bdinfo.get("video", [])
                a_tracks = bdinfo.get("audio", [])
                if v_tracks:
                    v_raw = v_tracks[0].get("bitrate")
                if a_tracks:
                    a_raw = a_tracks[0].get("bitrate")
        elif is_dvd:
            pass
        else:
            tracks = meta.get("mediainfo", {}).get("media", {}).get("track", [])
            for track in tracks:
                t_type = track.get("@type")
                if t_type == "Video" and v_raw is None:
                    v_raw = track.get("BitRate")
                elif t_type == "Audio" and a_raw is None:
                    a_raw = track.get("BitRate")

        def clean_to_int(val, bdmv_mode):
            if not val or isinstance(val, dict):
                return 0

            try:
                if bdmv_mode:
                    numeric_match = re.search(r"\d+", str(val).replace(".", "").replace(",", ""))
                    return int(numeric_match.group()) if numeric_match else 0
                else:
                    return int(val) // 1000
            except (ValueError, TypeError, AttributeError):
                return 0

        return (clean_to_int(v_raw, is_bdmv), clean_to_int(a_raw, is_bdmv))

    async def get_additional_checks(self, meta: dict[str, Any]):
        should_continue = True

        imdb_id = meta.get("imdb_info", {}).get("imdbID")
        if not imdb_id:
            console.print(f"{self.tracker}: [bold yellow]IMDb ID not found in metadata, skipping upload.[/bold yellow]")
            return False

        # Upscaled Content
        uuid: str = meta["uuid"]
        if "upscale" in uuid.lower() and "upscale" not in meta["title"]:
            console.print(f"{self.tracker}: Uploading upscaled files created by converting low-bitrate videos to high-bitrate versions might be prohibited.")
            if not meta["unattended"] or (meta["unattended"] and meta.get("unattended_confirm", False)):
                user_input = self.common.prompt_user_for_confirmation(f"{self.tracker}: Do you want to continue with the upload? (y/n): ")
                if not user_input:
                    return False
            else:
                return False

        # Screenshots
        if meta.get("screens", 0) < 3:
            console.print(f"{self.tracker}: [bold yellow]At least 3 screenshots are required for video uploads. Skipping upload.[/bold yellow]")
            return False

        # LGBT Content
        keywords: str = meta.get("keywords", "")
        combined_genres: str = meta.get("combined_genres", "")
        combined_text = f"{keywords}, {combined_genres}".lower()
        combined_list = [item.strip() for item in combined_text.split(",") if item.strip()]
        lgbt_keywords = ["lgbt", "queer", "lgbtq", "lgbtqia", "transgender", "trans", "gay", "lesbian", "bisexual", "pansexual", "non-binary", "homoerotic"]
        if any(kw in combined_list for kw in lgbt_keywords):
            console.print(
                f"{self.tracker}: [bold yellow]LGBT content detected. Please ensure the cover photo does not contain depictions of genitalia per tracker rules.[/bold yellow]"
            )
            if not meta["unattended"] or (meta["unattended"] and meta.get("unattended_confirm", False)):
                user_input = self.common.prompt_user_for_confirmation(f"{self.tracker}: Do you want to continue with the upload? (y/n): ")
                if not user_input:
                    return False
            else:
                return False

        return should_continue

    async def get_douban_id(self, meta: Meta) -> int:
        douban_id: int = 0
        try:
            douban_manual = int(meta.get("douban_manual") or 0)
        except (ValueError, TypeError):
            console.print(f"{self.tracker}: [bold yellow]Invalid douban_manual value, ignoring.[/bold yellow]")
            douban_manual = 0

        if douban_manual:
            console.print(f"{self.tracker}: Using manual Douban ID: {douban_manual}")
            self.douban_id = douban_manual
            return douban_manual

        imdb_id = meta.get("imdb_info", {}).get("imdbID")
        if not imdb_id:
            return douban_id

        search_url = f"https://m.douban.com/search/?query={imdb_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                response = await client.get(search_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            result = soup.find("ul", class_="search_results_subjects")

            if result:
                link_tag = result.find("a")
                if link_tag and "href" in link_tag.attrs:
                    link_mobile = str(link_tag["href"])
                    match = re.search(r"subject/(\d+)", link_mobile)
                    if match:
                        douban_id = int(match.group(1))
                        self.douban_id = douban_id
                        return douban_id

            console.print(f"{self.tracker}: [bold yellow]No Douban ID found for IMDb ID {imdb_id}.[/bold yellow]")
            return douban_id

        except Exception as e:
            console.print(f"{self.tracker}: [bold yellow]Failed to fetch Douban ID for IMDb ID {imdb_id}: {e}[/bold yellow]")
            return douban_id

    async def search_existing(self, meta: dict[str, Any], _) -> list[dict[str, Any]]:
        dupes: list[dict[str, Any]] = []

        should_continue = await self.get_additional_checks(meta)
        if not should_continue:
            meta["skipping"] = f"{self.tracker}"
            return dupes

        imdb_id = meta.get("imdb_info", {}).get("imdbID")
        category = self.get_category_id(meta)
        standard = self.get_standard(meta)

        if not imdb_id:
            console.print(f"{self.tracker}: [bold yellow]Cannot perform search on {self.tracker}: IMDb ID not found in metadata.[/bold yellow]")
            return dupes

        api_url = f"{self.api_base_url}/torrent/search"

        payload = {
            "mode": "normal",
            "imdb": imdb_id,
            "categories": [category],
            "standards": [standard],
        }

        try:
            response = await self.session.post(api_url, json=payload, timeout=15)
            res_json = response.json()

            if res_json.get("code") != "0":
                console.print(f"[bold red]API Error: {res_json.get('message')}[/bold red]")
                return dupes

            torrents = res_json.get("data", {}).get("data", [])

            for torrent in torrents:
                t_id = torrent.get("id")
                if not t_id:
                    continue

                dupe_entry = {
                    "name": torrent.get("name"),
                    "size": int(torrent.get("size", 0)),
                    "link": f"{self.base_url}/detail/{t_id}",
                    "file_count": torrent.get("file_count", 0),
                    "download": f"{self.api_base_url}/torrent/genDlToken?id={t_id}",
                    "id": t_id,
                }
                if meta.get("is_disc") == "BDMV":
                    bdinfo = await self.get_dupe_bdinfo(t_id)
                    if bdinfo:
                        dupe_entry["bd_info"] = bdinfo

                dupes.append(dupe_entry)

            return dupes

        except Exception as e:
            console.print(f"[bold red]Error searching for IMDb ID {imdb_id} on {self.tracker}: {e}[/bold red]")
            if not meta["unattended"] or (meta["unattended"] and meta.get("unattended_confirm", False)):
                pass
            else:
                meta["skipping"] = f"{self.tracker}"

        return dupes

    async def get_dupe_bdinfo(self, torrent_id: int) -> str:
        api_url = f"{self.api_base_url}/torrent/detail?id={torrent_id}"

        try:
            response = await self.session.post(api_url, timeout=15)
            response.raise_for_status()

            response_data = response.json()
            bdinfo = response_data.get("data", {}).get("mediainfo")
            if not bdinfo:
                bdinfo = response_data.get("data", {}).get("descr")
            return bdinfo

        except Exception as e:
            console.print(f"{self.tracker}: Error fetching BDinfo: {e}")
            return ""

    def get_standard(self, meta: Meta) -> int:
        _1080p = 1
        _1080i = 2
        _720p = 3
        sd = 5
        _4k = 6
        _8k = 7

        resolution = meta.get("resolution", "").lower()
        if resolution == "1080p":
            return _1080p
        elif resolution == "1080i":
            return _1080i
        elif resolution == "720p":
            return _720p
        elif resolution == "2160p":
            return _4k
        elif resolution == "4320p":
            return _8k
        elif meta.get("sd", False):
            return sd
        else:
            console.print(f"{self.tracker}: Unknown or unsupported resolution '{resolution}', defaulting to 1080p.")
            return _1080p

    def get_videocodec(self, meta: Meta) -> int:
        x264 = 1  # H.264(x264/AVC)
        x265 = 16  # H.265(x265/HEVC)
        vc1 = 2  # VC-1
        mpeg2 = 4  # MPEG-2
        xvid = 3  # Xvid
        av1 = 19  # AV1
        vp8_9 = 21  # VP8/9

        codec = meta.get("video_codec", "").lower()
        if codec in ("h264", "x264", "avc", "h.264"):
            return x264
        elif codec in ("h265", "h.265", "hevc", "x265"):
            return x265
        elif codec in ("vc1", "vc-1"):
            return vc1
        elif codec in ("mpeg2", "mpeg-2"):
            return mpeg2
        elif codec == "xvid":
            return xvid
        elif codec == "av1":
            return av1
        elif codec in ("vp8", "vp9"):
            return vp8_9
        else:
            console.print(f"{self.tracker}: Unknown or unsupported video codec '{codec}', defaulting to x264.")
            return x264

    def get_audiocodec(self, meta: Meta) -> int:
        aac = 6  # AAC
        ac3 = 8  # AC3(DD)
        dts = 3  # DTS
        dts_hd_ma = 11  # DTS-HD MA
        eac3 = 12  # E-AC3(DDP)
        atmos_eac3 = 13  # E-AC3 Atoms(DDP Atoms)
        true_hd = 9  # TrueHD

        codec = meta.get("audio", "").lower()

        if "atmos" in codec and "dd+" in codec:
            return atmos_eac3
        elif "aac" in codec:
            return aac
        elif "dd+" in codec:
            return eac3
        elif "dd " in codec:
            return ac3
        elif "dts-hd" in codec:
            return dts_hd_ma
        elif "dts" in codec:
            return dts
        elif "truehd" in codec:
            return true_hd
        else:
            console.print(f"{self.tracker}: Unknown or unsupported audio codec '{codec}', defaulting to AC3.")
            return ac3

    async def fetch_data(self, meta: Meta) -> dict[str, Any]:
        """
        https://test2.m-team.cc/api/swagger-ui/index.html#/種子/createOredit
        """
        douban_id = await self.get_douban_id(meta)

        data = {
            # "torrent": 0,
            # "offer": 0,
            "name": meta["name"],
            "smallDescr": self.get_small_description(meta),
            "descr": await self.generate_description(meta),
            "category": self.get_category_id(meta),
            # "source": 0,
            # "medium": 0,
            "standard": self.get_standard(meta),
            "videoCodec": self.get_videocodec(meta),
            "audioCodec": self.get_audiocodec(meta),
            # "team": 0,
            # "processing": 0,
            # "countries": "",
            "imdb": meta.get("imdb_info", {}).get("imdbID", ""),
            "douban": douban_id,
            # "dmmCode": "",
            # "cids": "",
            # "aids": "",
            "anonymous": bool(meta.get("anon", False) or self.config["TRACKERS"][self.tracker].get("anon", False)),
            # "labels": 0,
            # "tags": "",
            # "file": "",
            # "nfo": "",
            "mediainfo": await self.mediainfo(meta),
            "mediaInfoAnalysisResult": True,
            # "labelsNew": ""
        }

        return data

    async def upload(self, meta: Meta, _) -> bool:
        data = await self.fetch_data(meta)
        response = None

        if not meta.get("debug", False):
            try:
                upload_url = f"{self.api_base_url}/torrent/createOredit"
                await self.common.create_torrent_for_upload(meta, self.tracker, "[kp.m-team.cc] M-Team - TP")
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

                async with aiofiles.open(torrent_path, "rb") as torrent_file:
                    torrent_bytes = await torrent_file.read()
                files = {"file": ("upload.torrent", torrent_bytes, "application/x-bittorrent")}

                response = await self.session.post(upload_url, data=data, files=files, headers=dict(self.session.headers), timeout=90)
                response.raise_for_status()
                response_json = response.json()
                response_data: dict[str, Any] = cast(dict[str, Any], response_json) if isinstance(response_json, dict) else {}

                if response_data.get("message") == "SUCCESS":
                    torrent_id = str(response_data["data"]["id"])
                    meta["tracker_status"][self.tracker]["torrent_id"] = torrent_id
                    meta["tracker_status"][self.tracker]["status_message"] = response_data.get("message")

                    download_api_url = f"{self.api_base_url}/torrent/genDlToken?id={torrent_id}"
                    response = await self.session.post(download_api_url)
                    data = response.json()
                    final_download_url = data.get("data")
                    if final_download_url:
                        await self.common.download_tracker_torrent(
                            meta,
                            self.tracker,
                            headers=dict(self.session.headers),
                            downurl=final_download_url,
                        )
                        return True
                    console.print(f"{self.tracker}: Failed to get download URL from API response.")
                    meta["tracker_status"][self.tracker]["status_message"] = "Failed to get download URL from API response"
                    return False
                else:
                    meta["tracker_status"][self.tracker]["status_message"] = f"data error: {response_data.get('message', 'Unknown API error.')}"
                    return False

            except httpx.HTTPStatusError as e:
                meta["tracker_status"][self.tracker]["status_message"] = f"data error: HTTP {e.response.status_code} - {e.response.text}"
                return False
            except httpx.TimeoutException:
                meta["tracker_status"][self.tracker]["status_message"] = f"data error: Request timed out after {self.session.timeout.write} seconds"
                return False
            except httpx.RequestError as e:
                resp_text = getattr(getattr(e, "response", None), "text", "No response received")
                meta["tracker_status"][self.tracker]["status_message"] = f"data error: Unable to upload. Error: {e}.\nResponse: {resp_text}"
                return False
            except Exception as e:
                resp_text = response.text if response is not None else "No response received"
                meta["tracker_status"][self.tracker]["status_message"] = f"data error: It may have uploaded, go check. Error: {e}.\nResponse: {resp_text}"
                return False

        else:
            console.print("[cyan]M-Team Request Data:")
            console.print(Redaction.redact_private_info(data))
            meta["tracker_status"][self.tracker]["status_message"] = "Debug mode enabled, not uploading"
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success
