# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import os
import platform
from typing import Any, cast

import aiofiles
import httpx
from bs4 import BeautifulSoup

from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.get_desc import DescriptionBuilder
from src.tmdb import TmdbManager
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class NEXUSPHP:
    def __init__(self, config: dict[str, Any], tracker_name: str):
        self.common = COMMON(config)
        self.config = config
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.cookie_validator = CookieValidator(config)
        self.tmdb_manager = TmdbManager(config)
        self.tracker = tracker_name
        self.tracker_config: dict[str, Any] = self.config["TRACKERS"].get(self.tracker, {})

        # Normalize announce_url: must be a non-empty string after stripping
        raw_announce = self.tracker_config.get("announce_url")
        self.announce_url = raw_announce.strip() if isinstance(raw_announce, str) else ""

        # Default URLs - should be overridden by subclasses
        self.base_url = ""
        self.search_url = ""
        self.source_flag = ""
        self.torrent_url = ""
        self.upload_url = ""

        self.session = httpx.AsyncClient(headers={"User-Agent": f"Upload Assistant ({platform.system()} {platform.release()})"}, timeout=60.0)

    async def load_localized_data(self, meta: dict[str, Any]) -> None:
        localized_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/tmdb_localized_data.json"
        main_ch_data: dict[str, Any] = {}
        data: dict[str, Any] = {}

        if os.path.isfile(localized_data_file):
            try:
                async with aiofiles.open(localized_data_file, encoding="utf-8") as f:
                    content = await f.read()
                    loaded_data = json.loads(content)
                    data = cast(dict[str, Any], loaded_data) if isinstance(loaded_data, dict) else {}
            except json.JSONDecodeError:
                console.print(f"Warning: Could not decode JSON from {localized_data_file}", markup=False)
                data = {}
            except Exception as e:
                console.print(f"Error reading file {localized_data_file}: {e}", markup=False)
                data = {}

        ch_data = data.get("zh-cn")
        if isinstance(ch_data, dict):
            ch_dict = cast(dict[str, Any], ch_data)
            main_value = ch_dict.get("main")
            main_ch_data = cast(dict[str, Any], main_value) if isinstance(main_value, dict) else {}

        if not main_ch_data:
            localized_main = await self.tmdb_manager.get_tmdb_localized_data(meta, data_type="main", language="zh-cn", append_to_response="credits")
            main_ch_data = localized_main or {}

        self.tmdb_data = main_ch_data

        return

    async def search_existing(self, meta: Meta, _) -> list[dict[str, str]]:
        if not self.announce_url:
            console.print(f"[red]Announce URL is not set for {self.tracker}[/red]", markup=True)
            meta["skipping"] = self.tracker
            return []

        base_url = f"{self.base_url}/torrents.php"
        params = {
            f"cat{self.get_category(meta)}": "1",
            f"medium{self.get_type(meta)}": "1",
            f"standard{self.get_resolution(meta)}": "1",
            "incldead": "0",
        }

        search_name = str(meta.get("title", ""))
        year = str(meta.get("year", ""))
        episode = str(meta.get("episode", ""))
        season = str(meta.get("season", ""))
        season_episode = f"{season}{episode}" if season or episode else ""

        if meta["category"] == "MOVIE":
            params["search"] = f"{search_name} {year}"
        else:
            if meta.get("tv_pack", False):
                params["search"] = f"{search_name} {season}"
            else:
                params["search"] = f"{search_name} {season_episode}"

        try:
            cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
            if cookies:
                self.session.cookies.update(cookies)

            response = await self.session.get(base_url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="torrents")
            if not table:
                return []

            rows = table.find_all("tr")[1:]  # Skip header row
            results = []
            for row in rows:
                name_link = row.find("table", class_="torrentname")
                if not name_link:
                    continue

                a_tag = name_link.find("a", href=lambda x: bool(x and "details.php?id=" in x))
                if a_tag:
                    name_val = a_tag.get("title")
                    name = " ".join(name_val) if isinstance(name_val, list) else name_val or a_tag.get_text(strip=True)

                    href = a_tag.get("href")
                    if isinstance(href, list):
                        href = href[0]

                    if isinstance(href, str):
                        torrent_id = href.split("id=")[1].split("&")[0]
                        link = f"{self.base_url}/details.php?id={torrent_id}"
                        base_entry = {"name": name, "link": link}

                        if meta.get("is_disc") == "BDMV":
                            bdinfo = await self.get_dupe_bdinfo(torrent_id)
                            if bdinfo:
                                base_entry["bd_info"] = bdinfo

                        results.append(base_entry)

            return results
        except Exception as e:
            console.print(f"[red]Error searching {self.tracker}: {e}[/red]", markup=True)
            return []

    async def get_dupe_bdinfo(self, torrent_id: str) -> str:
        try:
            bdinfo_url = f"{self.base_url}/details.php?id={torrent_id}"
            response = await self.session.get(bdinfo_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            bdinfo_div = soup.find("div", class_="nexus-media-info-raw")
            if bdinfo_div:
                pre_tag = bdinfo_div.find("pre")
                if pre_tag:
                    return pre_tag.get_text(strip=True)

            return ""

        except Exception as e:
            console.print(f"Error getting BDInfo for torrent {torrent_id}: {e}", markup=False)
            return ""

    async def validate_credentials(self, meta: Meta) -> bool:
        return await self.cookie_validator.cookie_validation(meta=meta, tracker=self.tracker, test_url=f"{self.base_url}/upload.php", success_text="/announce.php")

    async def standard_desc(self, meta: Meta) -> str:
        data = getattr(self, "tmdb_data", {})
        if not data:
            return ""

        desc_parts: list[str] = []

        # Poster
        poster_path = data.get("poster_path")
        if poster_path:
            desc_parts.append(f"[img]https://image.tmdb.org/t/p/w500{poster_path}[/img]")
            desc_parts.append("")

        name = data.get("name", "")
        original_name = data.get("original_name", "")

        # Season info for TV
        season_num = meta.get("season", 0)
        is_tv = meta.get("category") == "TV"

        if is_tv and season_num:
            season_info = next((s for s in data.get("seasons", []) if s.get("season_number") == season_num), {})
            season_name = season_info.get("name", "")
            if not season_name or season_name == f"第 {season_num} 季":
                if f"第 {season_num} 季" not in name:
                    name = f"{name} 第 {season_num} 季"
            else:
                if season_name not in name:
                    name = f"{name} {season_name}"

        desc_parts.append(f"◎片　　名　{name}")

        aka = []
        if original_name and original_name != name:
            aka.append(original_name)
        if aka:
            desc_parts.append(f"◎译　　名　{' / '.join(aka)}")

        release_date = data.get("first_air_date") or data.get("release_date", "")
        year = release_date[:4] if release_date else str(meta.get("year", ""))
        if year:
            desc_parts.append(f"◎年　　代　{year}")

        countries = [c.get("name") for c in data.get("production_countries", [])]
        if countries:
            desc_parts.append(f"◎产　　地　{' / '.join(countries)}")

        genres = [g.get("name") for g in data.get("genres", [])]
        if genres:
            desc_parts.append(f"◎类　　别　{' / '.join(genres)}")

        languages = [l.get("name") for l in data.get("spoken_languages", [])]
        if languages:
            desc_parts.append(f"◎语　　言　{' / '.join(languages)}")

        if release_date:
            country_name = countries[0] if countries else ""
            date_str = f"{release_date}({country_name})" if country_name else release_date
            desc_parts.append(f"◎上映日期　{date_str}")

        imdb_info = meta.get("imdb_info", {})
        imdb_rating = imdb_info.get("rating")
        imdb_votes = imdb_info.get("votes")
        imdb_url = imdb_info.get("imdb_url")

        if imdb_rating:
            votes_str = f" ({imdb_votes} 人评价)" if imdb_votes else ""
            desc_parts.append(f"◎IMDb评分  {imdb_rating}/10{votes_str}")
        if imdb_url:
            desc_parts.append(f"◎IMDb链接  {imdb_url}/")

        # Douban info from meta if available
        douban_rating = meta.get("douban_rating")
        douban_votes = meta.get("douban_votes")
        douban_id = meta.get("douban_id")
        if douban_rating:
            votes_str = f" ({douban_votes} 人评价)" if douban_votes else ""
            desc_parts.append(f"◎豆瓣评分　{douban_rating}/10{votes_str}")
        if douban_id:
            desc_parts.append(f"◎豆瓣链接　https://movie.douban.com/subject/{douban_id}/")

        if is_tv:
            if season_num:
                season_info = next((s for s in data.get("seasons", []) if s.get("season_number") == season_num), {})
                ep_count = season_info.get("episode_count")
                if ep_count:
                    desc_parts.append(f"◎集　　数　{ep_count}")

            desc_parts.append(f"◎季　　数　{season_num}")

            runtime = data.get("episode_run_time", [])
            if not runtime and data.get("last_episode_to_air"):
                runtime = [data["last_episode_to_air"].get("runtime")]
            if runtime and runtime[0]:
                desc_parts.append(f"◎片　　长　{runtime[0]}分钟")
        else:
            runtime = data.get("runtime") or meta.get("runtime")
            if runtime:
                desc_parts.append(f"◎片　　长　{runtime}分钟")

        credits = data.get("credits", {})
        crew = credits.get("crew", [])

        directors = [f"{c.get('name')} {c.get('original_name')}" for c in crew if c.get("job") == "Director"]
        if directors:
            desc_parts.append(f"◎导　　演　{' / '.join(directors)}")

        writers = [f"{c.get('name')} {c.get('original_name')}" for c in crew if c.get("job") in ("Writer", "Screenplay", "Author")]
        writers = list(dict.fromkeys(writers))
        if writers:
            desc_parts.append(f"◎编　　剧　{' / '.join(writers)}")

        cast = credits.get("cast", [])
        if cast:
            first_actor = cast[0]
            actor_str = f"{first_actor.get('name')} {first_actor.get('original_name')}"
            if first_actor.get("character"):
                actor_str += f" (饰 {first_actor.get('character')})"
            desc_parts.append(f"◎主　　演　{actor_str}")

            for actor in cast[1:25]:
                actor_str = f"{actor.get('name')} {actor.get('original_name')}"
                if actor.get("character"):
                    actor_str += f" (饰 {actor.get('character')})"
                desc_parts.append(f"　　　　　　{actor_str}")

        overview = data.get("overview", "")
        if overview:
            desc_parts.append("")
            desc_parts.append("◎简　　介")
            desc_parts.append("")
            desc_parts.append(f"　　{overview}")

        return "\n".join(desc_parts)

    async def get_description(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        custom_header = await builder.get_custom_header()
        desc_parts.append(custom_header)

        # Standard Description
        desc_parts.append(await self.standard_desc(meta))

        # User description
        user_description = await builder.get_user_description(meta)
        desc_parts.append(user_description)

        # Disc menus screenshots header
        menu_images_value = meta.get("menu_images", [])
        menu_images: list[dict[str, Any]] = []
        if isinstance(menu_images_value, list):
            menu_images_list = list[Any], menu_images_value
            menu_images.extend([cast(dict[str, Any], item) for item in menu_images_list if isinstance(item, dict)])
        if menu_images:
            desc_parts.append(await builder.menu_screenshot_header(meta))

            # Disc menus screenshots
            menu_screenshots_block = ""
            for image in menu_images:
                menu_raw_url = image.get("raw_url")
                if menu_raw_url:
                    menu_screenshots_block += f"[img]{menu_raw_url}[/img]"
            if menu_screenshots_block:
                desc_parts.append(menu_screenshots_block)

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        # Screenshot Header
        images_value = meta.get("image_list", [])
        images: list[dict[str, Any]] = []
        if isinstance(images_value, list):
            images_list = list[Any], images_value
            images.extend([cast(dict[str, Any], item) for item in images_list if isinstance(item, dict)])
        if images:
            desc_parts.append(await builder.screenshot_header())

            # Screenshots
            if images:
                screenshots_block = ""
                for image in images:
                    raw_url = image.get("raw_url")
                    if raw_url:
                        screenshots_block += f"[img]{raw_url}[/img]"
                if screenshots_block:
                    desc_parts.append(screenshots_block)

        # Signature
        desc_parts.append(f"[right][url=https://github.com/Audionut/Upload-Assistant][size=1]{meta['ua_signature']}[/size][/url][/right]")

        description = "\n\n".join(part for part in desc_parts if part.strip())

        from src.bbcode import BBCODE

        bbcode = BBCODE()
        description = description.strip()
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", "w", encoding="utf-8") as description_file:
            await description_file.write(description)

        return description

    def get_category(self, _meta: Meta) -> int:
        raise NotImplementedError

    def get_type(self, _meta: Meta) -> int:
        raise NotImplementedError

    def get_codec(self, _meta: Meta) -> int:
        raise NotImplementedError

    def get_resolution(self, _meta: Meta) -> int:
        raise NotImplementedError

    def get_group_tag(self, _meta: Meta) -> int:
        return 0

    def get_checkboxes(self, _meta: Meta) -> list[str]:
        return []

    def get_anonymous(self, _meta: Meta) -> bool:
        return False

    def get_audio_codec(self, _meta: Meta) -> int:
        return 0

    def get_douban_url(self, meta: Meta) -> str:
        if meta.get("douban_id", 0):
            return f"https://movie.douban.com/subject/{meta['douban_id']}/"
        return ""

    def get_imdb_url(self, meta: Meta) -> str:
        if meta.get("imdb_id", 0):
            return f"{meta.get('imdb_info', {}).get('imdb_url', '')}"
        return ""

    def get_region(self, _meta: Meta) -> int:
        return 0

    def get_container(self, _meta: Meta) -> int:
        return 0

    async def get_data(self, meta: Meta):
        await self.load_localized_data(meta)
        builder = DescriptionBuilder(self.tracker, self.config)
        data = {
            "codec_sel[4]": self.get_codec(meta),
            "color": 0,
            "descr": await self.get_description(meta),
            "font": 0,
            "medium_sel[4]": self.get_type(meta),
            "name": meta.get("name"),
            "size": 0,
            "small_descr": self.common.get_small_description(meta),
            "standard_sel[4]": self.get_resolution(meta),
            "technical_info": await builder.get_mediainfo_section(meta) if meta.get("is_disc", "") != "BDMV" else await builder.get_bdinfo_section(meta),
            "type": self.get_category(meta),
        }

        group_tag = self.get_group_tag(meta)
        if group_tag:
            data["team_sel[4]"] = group_tag

        checkboxes = self.get_checkboxes(meta)
        if checkboxes:
            data["tags[4][]"] = checkboxes

        anonymous = self.get_anonymous(meta)
        if anonymous:
            data["uplver"] = "yes"

        imdb_url = self.get_imdb_url(meta)
        if imdb_url:
            data["url"] = imdb_url

        douban_url = self.get_douban_url(meta)
        if douban_url:
            data["pt_gen"] = douban_url

        audio = self.get_audio_codec(meta)
        if audio:
            data["audiocodec_sel[4]"] = audio

        region = self.get_region(meta)
        if region:
            data["source_sel[4]"] = region

        container = self.get_container(meta)
        if container:
            data["processing_sel[4]"] = container

        return data

    async def upload(self, meta: Meta, _) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies.clear()
        if cookies is not None:
            self.session.cookies.update(cookies)
        data = await self.get_data(meta)

        is_uploaded = await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            id_pattern=r"download\.php\?id=(\d+)",
            data=data,
            torrent_field_name="file",
            upload_cookies=self.session.cookies,
            upload_url=f"{self.base_url}/takeupload.php",
            success_text="download.php?id=",
        )

        return is_uploaded
