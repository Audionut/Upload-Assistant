# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import aiofiles
import asyncio
import glob
import json
import os
import re
import requests
import urllib.parse
from jinja2 import Template

from pymediainfo import MediaInfo
from src.bbcode import BBCODE
from src.console import console
from src.languages import process_desc_language
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.trackers.COMMON import COMMON
from src.uploadscreens import upload_screens


async def gen_desc(meta):
    def clean_text(text):
        return text.replace("\r\n", "\n").strip()

    description_link = meta.get("description_link")
    description_file = meta.get("description_file")
    scene_nfo = False
    bhd_nfo = False

    with open(
        f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", "w", newline="", encoding="utf8"
    ) as description:
        description.seek(0)
        content_written = False

        if meta.get("description_template"):
            try:
                with open(f"{meta['base_dir']}/data/templates/{meta['description_template']}.txt", "r") as f:
                    template = Template(f.read())
                    template_desc = template.render(meta)
                    cleaned_content = clean_text(template_desc)
                    if cleaned_content:
                        if not content_written:
                            description.write
                        if len(template_desc) > 0:
                            description.write(cleaned_content + "\n")
                            meta["description_template_content"] = cleaned_content
                        content_written = True
            except FileNotFoundError:
                console.print(f"[ERROR] Template '{meta['description_template']}' not found.")

        base_dir = meta["base_dir"]
        uuid = meta["uuid"]
        path = meta["path"]
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        source_dir_path = os.path.join(path, "*.nfo")
        if meta.get("nfo"):
            if meta["debug"]:
                console.print(f"specified_dir_path: {specified_dir_path}")
                console.print(f"sourcedir_path: {source_dir_path}")
            if "auto_nfo" in meta and meta["auto_nfo"] is True:
                nfo_files = glob.glob(specified_dir_path)
                scene_nfo = True
            elif "bhd_nfo" in meta and meta["bhd_nfo"] is True:
                nfo_files = glob.glob(specified_dir_path)
                bhd_nfo = True
            else:
                nfo_files = glob.glob(source_dir_path)
            if not nfo_files:
                console.print("NFO was set but no nfo file was found")
                if not content_written:
                    description.write("\n")
                return meta

            if nfo_files:
                nfo = nfo_files[0]
                try:
                    with open(nfo, "r", encoding="utf-8") as nfo_file:
                        nfo_content = nfo_file.read()
                    if meta["debug"]:
                        console.print("NFO content read with utf-8 encoding.")
                except UnicodeDecodeError:
                    if meta["debug"]:
                        console.print("utf-8 decoding failed, trying latin1.")
                    with open(nfo, "r", encoding="latin1") as nfo_file:
                        nfo_content = nfo_file.read()

                if not content_written:
                    if scene_nfo is True:
                        description.write(
                            f"[center][spoiler=Scene NFO:][code]{nfo_content}[/code][/spoiler][/center]\n"
                        )
                    elif bhd_nfo is True:
                        description.write(
                            f"[center][spoiler=FraMeSToR NFO:][code]{nfo_content}[/code][/spoiler][/center]\n"
                        )
                    else:
                        description.write(f"[code]{nfo_content}[/code]\n")

                    content_written = True

                nfo_content_utf8 = nfo_content.encode("utf-8", "ignore").decode("utf-8")
                meta["description_nfo_content"] = nfo_content_utf8

        if description_link:
            try:
                parsed = urllib.parse.urlparse(description_link.replace("/raw/", "/"))
                split = os.path.split(parsed.path)
                raw = parsed._replace(
                    path=f"{split[0]}/raw/{split[1]}" if split[0] != "/" else f"/raw{parsed.path}"
                )
                raw_url = urllib.parse.urlunparse(raw)
                description_link_content = requests.get(raw_url, timeout=20).text
                cleaned_content = clean_text(description_link_content)
                if cleaned_content:
                    if not content_written:
                        description.write(cleaned_content + "\n")
                    meta["description_link_content"] = cleaned_content
                    content_written = True
            except Exception as e:
                console.print(f"[ERROR] Failed to fetch description from link: {e}")

        if description_file and os.path.isfile(description_file):
            with open(description_file, "r", encoding="utf-8") as f:
                file_content = f.read()
                cleaned_content = clean_text(file_content)
                if cleaned_content:
                    if not content_written:
                        description.write(file_content)
                meta["description_file_content"] = cleaned_content
                content_written = True

        if not content_written:
            if meta.get("description"):
                description_text = meta.get("description", "").strip()
            else:
                description_text = ""
            if description_text:
                description.write(description_text + "\n")

        if description.tell() != 0:
            description.write("\n")

    # Fallback if no description is provided
    if not meta.get("skip_gen_desc", False) and not content_written:
        description_text = meta["description"] if meta.get("description", "") else ""
        with open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", "w", newline="", encoding="utf8"
        ) as description:
            if len(description_text) > 0:
                description.write(description_text + "\n")

    if meta.get("description") in ("None", "", " "):
        meta["description"] = None

    return meta


class DescriptionBuilder:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.parser = self.common.parser

    async def get_custom_header(self, tracker):
        """Returns a custom header if configured."""
        try:
            custom_description_header = self.config["TRACKERS"][tracker].get(
                "custom_description_header", self.config["DEFAULT"].get("custom_description_header", False)
            )
            if custom_description_header:
                return custom_description_header
        except Exception as e:
            console.print(f"[yellow]Warning: Error setting custom description header: {str(e)}[/yellow]")

        return ""

    async def get_tonemapped_header(self, meta, tracker):
        try:
            tonemapped_description_header = self.config["TRACKERS"][tracker].get(
                "tonemapped_header", self.config["DEFAULT"].get("tonemapped_header", "")
            )
            if tonemapped_description_header and meta.get("tonemapped", False):
                return tonemapped_description_header
        except Exception as e:
            console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
        return ""

    async def get_logo_section(self, meta, tracker):
        """Returns the logo URL and size if applicable."""
        logo, logo_size = "", ""
        try:
            if not self.config["TRACKERS"][tracker].get(
                "add_logo", self.config["DEFAULT"].get("add_logo", False)
            ):
                return logo, logo_size

            logo = meta.get("logo", "")
            logo_size = self.config["DEFAULT"].get("logo_size", "300")

            if logo:
                return logo, logo_size
        except Exception as e:
            console.print(f"[yellow]Warning: Error getting logo section: {str(e)}[/yellow]")

        return logo, logo_size

    async def get_tv_info(self, meta, tracker, resize=False):
        title, image, overview = "", "", ""
        try:
            if (
                not self.config["TRACKERS"][tracker].get(
                    "episode_overview", self.config["DEFAULT"].get("episode_overview", False)
                )
                or meta["category"] != "TV"
            ):
                return title, image, overview

            tvmaze_episode_data = meta.get("tvmaze_episode_data", {})

            season_name = tvmaze_episode_data.get("season_name", "") or meta.get("tvdb_season_name", "")
            season_number = meta.get("season", "")
            episode_number = meta.get("episode", "")
            overview = tvmaze_episode_data.get("overview", "") or meta.get("overview_meta", "")
            episode_title = meta.get("auto_episode_title") or tvmaze_episode_data.get("episode_name", "")

            image = ""
            if meta.get("tv_pack", False):
                image = tvmaze_episode_data.get("series_image", "")
                if resize:
                    image = tvmaze_episode_data.get("series_image_medium", "")
            else:
                image = tvmaze_episode_data.get("image", "")
                if resize:
                    image = tvmaze_episode_data.get("image_medium", "")

            title = ""
            if season_name:
                title = f"{season_name}"
                if season_number:
                    title += f" - {season_number}{episode_number}"

            if episode_title:
                if title:
                    title += ": "
                title += f"{episode_title}"

        except Exception as e:
            console.print(f"[yellow]Warning: Error getting TV info: {str(e)}[/yellow]")

        return title, image, overview

    async def get_mediainfo_section(self, meta, tracker):
        """Returns the mediainfo/bdinfo section, using a cache file if available."""
        if meta.get("is_disc") == "BDMV":
            return ""

        if self.config["TRACKERS"][tracker].get(
            "full_mediainfo", self.config["DEFAULT"].get("full_mediainfo", False)
        ):
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            if await self.common.path_exists(mi_path):
                async with aiofiles.open(mi_path, "r", encoding="utf-8") as mi:
                    return await mi.read()

        cache_file_dir = os.path.join(meta["base_dir"], "tmp", meta["uuid"])
        cache_file_path = os.path.join(cache_file_dir, "MEDIAINFO_SHORT.txt")

        file_exists = os.path.exists(cache_file_path)
        file_size = os.path.getsize(cache_file_path) if file_exists else 0

        if file_exists and file_size > 0:
            try:
                async with aiofiles.open(cache_file_path, mode="r", encoding="utf-8") as f:
                    media_info_content = await f.read()
                return media_info_content
            except Exception:
                pass

        video_file = meta["filelist"][0]
        mi_template = os.path.join(meta["base_dir"], "data", "templates", "MEDIAINFO.txt")
        mi_file_path = os.path.join(cache_file_dir, "MEDIAINFO_CLEANPATH.txt")

        template_exists = await self.common.path_exists(mi_template)

        if template_exists:
            try:
                media_info_result = MediaInfo.parse(
                    video_file,
                    output="STRING",
                    full=False,
                    mediainfo_options={"inform": f"file://{mi_template}"},
                )
                media_info_content = str(media_info_result)

                if media_info_content:
                    media_info_content = media_info_content.replace("\r\n", "\n")
                    try:
                        await self.common.makedirs(cache_file_dir)
                        async with aiofiles.open(cache_file_path, mode="w", encoding="utf-8") as f:
                            await f.write(media_info_content)
                    except Exception:
                        pass

                    return media_info_content

            except Exception:
                cleanpath_exists = await self.common.path_exists(mi_file_path)
                if cleanpath_exists:
                    async with aiofiles.open(mi_file_path, "r", encoding="utf-8") as f:
                        return await f.read()

        else:
            cleanpath_exists = await self.common.path_exists(mi_file_path)
            if cleanpath_exists:
                async with aiofiles.open(mi_file_path, "r", encoding="utf-8") as f:
                    tech_info = await f.read()
                    return tech_info

        return ""

    async def get_bdinfo_section(self, meta):
        """Returns the bdinfo section if applicable."""
        try:
            if meta.get("is_disc") == "BDMV":
                bdinfo_sections = []
                if meta.get("discs"):
                    for disc in meta["discs"]:
                        file_info = disc.get("summary", "")
                        if file_info:
                            bdinfo_sections.append(file_info)
                return "\n\n".join(bdinfo_sections)
        except Exception as e:
            console.print(f"[yellow]Warning: Error getting bdinfo section: {str(e)}[/yellow]")

        return ""

    async def screenshot_header(self, tracker):
        """Returns the screenshot header if applicable."""
        try:
            screenheader = self.config["TRACKERS"][tracker].get(
                "custom_screenshot_header", self.config["DEFAULT"].get("screenshot_header", None)
            )
            if screenheader:
                return screenheader
        except Exception as e:
            console.print(f"[yellow]Warning: Error getting screenshot header: {str(e)}[/yellow]")

        return ""

    async def get_user_description(self, meta):
        """Returns the user-provided description (file or link)"""
        try:
            description_file_content = meta.get("description_file_content", "").strip()
            description_link_content = meta.get("description_link_content", "").strip()

            if description_file_content or description_link_content:
                if description_file_content:
                    return description_file_content
                elif description_link_content:
                    return description_link_content
        except Exception as e:
            console.print(f"[yellow]Warning: Error getting user description: {str(e)}[/yellow]")

        return ""

    async def get_custom_signature(self, tracker):
        custom_signature = ""
        try:
            custom_signature = self.config["TRACKERS"][tracker].get(
                "custom_signature", self.config["DEFAULT"].get("custom_signature", None)
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Error setting custom signature: {str(e)}[/yellow]")
        return custom_signature

    async def get_bluray_section(self, meta, tracker):
        release_url = ""
        cover_list = []
        cover_images = ""

        try:
            cover_size = int(self.config["DEFAULT"].get("bluray_image_size", "250"))
            bluray_link = self.config["DEFAULT"].get("add_bluray_link", False)

            if meta.get("is_disc") in ["BDMV", "DVD"] and bluray_link and meta.get("release_url", ""):
                release_url = meta["release_url"]

            covers = False
            if await self.common.path_exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/covers.json"):
                covers = True

            if (
                meta.get("is_disc") in ["BDMV", "DVD"]
                and self.config["DEFAULT"].get("use_bluray_images", False)
                and covers
            ):
                async with aiofiles.open(
                    f"{meta['base_dir']}/tmp/{meta['uuid']}/covers.json", "r", encoding="utf-8"
                ) as f:
                    cover_data = json.loads(await f.read())

                if isinstance(cover_data, list):
                    for img_data in cover_data:
                        if "raw_url" in img_data and "web_url" in img_data:
                            web_url = img_data["web_url"]
                            raw_url = img_data["raw_url"]

                            if tracker == "TL":
                                cover_list.append(
                                    f"""<a href="{web_url}"><img src="{raw_url}" style="max-width: {cover_size}px;"></a>  """
                                )
                            elif tracker == "HDT":
                                cover_list.append(
                                    f"<a href='{raw_url}'><img src='{web_url}' height=137></a> "
                                )
                            else:
                                cover_list.append(
                                    f"[url={web_url}][img={cover_size}]{raw_url}[/img][/url]"
                                )

            if cover_list:
                cover_images = "".join(cover_list)

        except Exception as e:
            console.print(f"[yellow]Warning: Error getting bluray section: {str(e)}[/yellow]")

        return release_url, cover_images

    async def unit3d_edit_desc(
        self,
        meta,
        tracker,
        signature="",
        comparison=False,
        desc_header="",
        image_list=None,
        approved_image_hosts=None,
    ):
        if image_list is not None:
            images = image_list
            multi_screens = 0
        else:
            images = meta["image_list"]
            multi_screens = int(self.config["DEFAULT"].get("multiScreens", 2))
        if meta.get("sorted_filelist"):
            multi_screens = 0

        desc_parts = []

        # Custom Header
        if not desc_header:
            desc_header = await self.get_custom_header(tracker)
        if desc_header:
            desc_parts.append(desc_header + "\n")

        # Language
        try:
            if not meta.get("language_checked", False):
                await process_desc_language(meta, desc_parts, tracker)
            if meta.get("audio_languages") and meta.get("write_audio_languages"):
                desc_parts.append(f"[code]Audio Language/s: {', '.join(meta['audio_languages'])}[/code]")

            if meta["subtitle_languages"] and meta["write_subtitle_languages"]:
                desc_parts.append(
                    f"[code]Subtitle Language/s: {', '.join(meta['subtitle_languages'])}[/code]"
                )
            if meta["subtitle_languages"] and meta["write_hc_languages"]:
                desc_parts.append(
                    f"[code]Hardcoded Subtitle Language/s: {', '.join(meta['subtitle_languages'])}[/code]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: Error processing language: {str(e)}[/yellow]")

        # Logo
        logo, logo_size = await self.get_logo_section(meta, tracker)
        if logo and logo_size:
            desc_parts.append(f"[center][img={logo_size}]{logo}[/img][/center]\n")

        # Blu-ray
        release_url, cover_images = await self.get_bluray_section(meta, tracker)
        if release_url:
            desc_parts.append(f"[center]{release_url}[/center]")
        if cover_images:
            desc_parts.append(f"[center]{cover_images}[/center]\n")

        # TV
        title, episode_image, episode_overview = await self.get_tv_info(meta, tracker)
        if episode_overview:
            if tracker == "HUNO":
                desc_parts.append(f"[center]{title}[/center]\n")
            else:
                desc_parts.append(f"[center][pre]{title}[/pre][/center]\n")

            if tracker == "HUNO":
                desc_parts.append(f"[center]{episode_overview}[/center]\n")
            else:
                desc_parts.append(f"[center][pre]{episode_overview}[/pre][/center]\n")

        # Description that may come from API requests
        meta_description = meta.get("description", "")
        # Add FraMeSToR NFO to Aither
        if tracker == "AITHER" and "framestor" in meta and meta["framestor"]:
            nfo_content = meta.get("description_nfo_content", "")
            if nfo_content:
                aither_framestor_nfo = f"[code]{nfo_content}[/code]"
                aither_framestor_nfo = aither_framestor_nfo.replace(
                    "https://i.imgur.com/e9o0zpQ.png",
                    "https://beyondhd.co/images/2017/11/30/c5802892418ee2046efba17166f0cad9.png",
                )
                images = []
                desc_parts.append(aither_framestor_nfo)
            else:
                # Remove NFO from description
                meta_description = re.sub(
                    r"\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]",
                    "",
                    meta_description,
                    flags=re.DOTALL,
                )
                if meta_description:
                    desc_parts.append(meta_description)
        elif meta_description:
            desc_parts.append(meta_description)

        # Description from file/pastebin link
        desc_parts.append(await self.get_user_description(meta))

        # Tonemapped Header
        desc_parts.append(await self.get_tonemapped_header(meta, tracker))

        # Discs and Screenshots
        discs_and_screenshots = await self._handle_discs_and_screenshots(
            meta, tracker, approved_image_hosts, images, multi_screens
        )
        desc_parts.append(discs_and_screenshots)

        # Custom Signature
        desc_parts.append(await self.get_custom_signature(tracker))

        # UA Signature
        if not signature:
            signature = f"[right][url=https://github.com/Audionut/Upload-Assistant][size=4]{meta['ua_signature']}[/size][/url][/right]"
            if tracker == "HUNO":
                signature = signature.replace("[size=4]", "[size=8]")
        desc_parts.append(signature)

        description = "\n".join(
            part for part in desc_parts
            if part is not None and str(part).strip()
        )

        # Formatting
        bbcode = BBCODE()
        description = bbcode.convert_pre_to_code(description)
        description = bbcode.convert_hide_to_spoiler(description)
        description = description.replace("[user]", "").replace("[/user]", "")
        description = description.replace("[hr]", "").replace("[/hr]", "")
        description = description.replace("[ul]", "").replace("[/ul]", "")
        description = description.replace("[ol]", "").replace("[/ol]", "")
        description = bbcode.remove_extra_lines(description)
        if comparison is False:
            description = bbcode.convert_comparison_to_collapse(description, 1000)

        if meta['debug']:
            desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt"
            console.print(f"DEBUG: Saving final description to [yellow]{desc_file}[/yellow]")
            async with aiofiles.open(desc_file, "w", encoding="utf-8") as description_file:
                await description_file.write(description)

        return description

    async def _check_saved_pack_image_links(self, meta, approved_image_hosts):
        pack_images_file = os.path.join(meta["base_dir"], "tmp", meta["uuid"], "pack_image_links.json")
        pack_images_data = {}
        approved_hosts = set(approved_image_hosts or [])
        if await self.common.path_exists(pack_images_file):
            try:
                async with aiofiles.open(pack_images_file, "r", encoding="utf-8") as f:
                    pack_images_data = json.loads(await f.read())

                    # Filter out keys with non-approved image hosts
                    keys_to_remove = []
                    for key_name, key_data in pack_images_data.get("keys", {}).items():
                        images_to_keep = []
                        for img in key_data.get("images", []):
                            raw_url = img.get("raw_url", "")
                            # Extract hostname from URL (e.g., ptpimg.me -> ptpimg)
                            try:
                                parsed_url = urllib.parse.urlparse(raw_url)
                                hostname = parsed_url.netloc
                                # Get the main domain name (first part before the dot)
                                host_key = hostname.split(".")[0] if hostname else ""

                                if not approved_hosts or host_key in approved_hosts:
                                    images_to_keep.append(img)
                                elif meta["debug"]:
                                    console.print(
                                        f"[yellow]Filtering out image from non-approved host: {hostname}[/yellow]"
                                    )
                            except Exception:
                                # If URL parsing fails, skip this image
                                if meta["debug"]:
                                    console.print(f"[yellow]Could not parse URL: {raw_url}[/yellow]")
                                continue

                        if images_to_keep:
                            # Update the key with only approved images
                            pack_images_data["keys"][key_name]["images"] = images_to_keep
                            pack_images_data["keys"][key_name]["count"] = len(images_to_keep)
                        else:
                            # Mark key for removal if no approved images
                            keys_to_remove.append(key_name)

                    # Remove keys with no approved images
                    for key_name in keys_to_remove:
                        del pack_images_data["keys"][key_name]
                        if meta["debug"]:
                            console.print(
                                f"[yellow]Removed key '{key_name}' - no approved image hosts[/yellow]"
                            )

                    # Recalculate total count
                    pack_images_data["total_count"] = sum(
                        key_data["count"] for key_data in pack_images_data.get("keys", {}).values()
                    )

                    if pack_images_data.get("total_count", 0) < 3:
                        pack_images_data = {}  # Invalidate if less than 3 images total
                        if meta["debug"]:
                            console.print(
                                "[yellow]Invalidating pack images - less than 3 approved images total[/yellow]"
                            )
                    else:
                        if meta["debug"]:
                            console.print(f"[green]Loaded previously uploaded images from {pack_images_file}")
                            console.print(
                                f"[blue]Found {pack_images_data.get('total_count', 0)} approved images across {len(pack_images_data.get('keys', {}))} keys[/blue]"
                            )
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load pack image data: {str(e)}[/yellow]")
        return pack_images_data

    async def _handle_discs_and_screenshots(self, meta, tracker, approved_image_hosts, images, multi_screens):
        try:
            screenheader = await self.screenshot_header(tracker)
        except Exception:
            screenheader = None

        # Check for saved pack_image_links.json file
        pack_images_data = await self._check_saved_pack_image_links(meta, approved_image_hosts)

        char_limit = int(self.config["DEFAULT"].get("charLimit", 14000))
        file_limit = int(self.config["DEFAULT"].get("fileLimit", 5))
        thumb_size = int(self.config["DEFAULT"].get("pack_thumb_size", "300"))
        process_limit = int(self.config["DEFAULT"].get("processLimit", 10))

        try:
            # If screensPerRow is set, use that to determine how many screenshots should be on each row. Otherwise, use 2 as default
            screensPerRow = int(self.config["DEFAULT"].get("screens_per_row", 2))
            if tracker == "HUNO":
                width = int(self.config["DEFAULT"].get("thumbnail_size", "350"))
                # Adjust screensPerRow to keep total width below 1100
                while screensPerRow * width > 1100 and screensPerRow > 1:
                    screensPerRow -= 1
        except Exception:
            screensPerRow = 2

        desc_parts = []

        discs = meta.get("discs", [])
        if len(discs) == 1:
            each = discs[0]
            if each["type"] == "DVD":
                desc_parts.append("[center]")
                desc_parts.append(
                    f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler]\n\n"
                )
                desc_parts.append("[/center]")
            if screenheader is not None:
                desc_parts.append(screenheader + "\n")
            desc_parts.append("[center]")
            for img_index in range(len(images[: int(meta["screens"])])):
                web_url = images[img_index]["web_url"]
                raw_url = images[img_index]["raw_url"]
                desc_parts.append(
                    f"[url={web_url}][img={self.config['DEFAULT'].get('thumbnail_size', '350')}]{raw_url}[/img][/url] "
                )
                if screensPerRow and (img_index + 1) % screensPerRow == 0:
                    desc_parts.append("\n")
            desc_parts.append("[/center]")
            if each["type"] == "BDMV":
                bdinfo_keys = [key for key in each if key.startswith("bdinfo")]
                if len(bdinfo_keys) > 1:
                    if "retry_count" not in meta:
                        meta["retry_count"] = 0

                    for i, key in enumerate(bdinfo_keys[1:], start=1):  # Skip the first bdinfo
                        new_images_key = f"new_images_playlist_{i}"
                        bdinfo = each[key]
                        edition = bdinfo.get("edition", "Unknown Edition")

                        # Find the corresponding summary for this bdinfo
                        summary_key = f"summary_{i}" if i > 0 else "summary"
                        summary = each.get(summary_key, "No summary available")

                        # Check for saved images first
                        if (
                            pack_images_data
                            and "keys" in pack_images_data
                            and new_images_key in pack_images_data["keys"]
                        ):
                            saved_images = pack_images_data["keys"][new_images_key]["images"]
                            if saved_images:
                                if meta["debug"]:
                                    console.print(
                                        f"[yellow]Using saved images from pack_image_links.json for {new_images_key}"
                                    )

                                meta[new_images_key] = []
                                for img in saved_images:
                                    meta[new_images_key].append(
                                        {
                                            "img_url": img.get("img_url", ""),
                                            "raw_url": img.get("raw_url", ""),
                                            "web_url": img.get("web_url", ""),
                                        }
                                    )

                        if new_images_key in meta and meta[new_images_key]:
                            desc_parts.append("[center]\n\n")
                            # Use the summary corresponding to the current bdinfo
                            desc_parts.append(
                                f"[spoiler={edition}][code]{summary}[/code][/spoiler]\n\n"
                            )
                            if meta["debug"]:
                                console.print("[yellow]Using original uploaded images for first disc")
                            desc_parts.append("[center]")
                            for img in meta[new_images_key]:
                                web_url = img["web_url"]
                                raw_url = img["raw_url"]
                                image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                desc_parts.append(image_str)
                            desc_parts.append("[/center]\n\n")
                        else:
                            desc_parts.append("[center]\n\n")
                            # Use the summary corresponding to the current bdinfo
                            desc_parts.append(
                                f"[spoiler={edition}][code]{summary}[/code][/spoiler]\n\n"
                            )
                            desc_parts.append("[/center]\n\n")
                            meta["retry_count"] += 1
                            meta[new_images_key] = []
                            new_screens = glob.glob1(
                                f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png"
                            )
                            if not new_screens:
                                use_vs = meta.get("vapoursynth", False)
                                try:
                                    await disc_screenshots(
                                        meta,
                                        f"PLAYLIST_{i}",
                                        bdinfo,
                                        meta["uuid"],
                                        meta["base_dir"],
                                        use_vs,
                                        [],
                                        meta.get("ffdebug", False),
                                        multi_screens,
                                        True,
                                    )
                                except Exception as e:
                                    print(f"Error during BDMV screenshot capture: {e}")
                                new_screens = glob.glob1(
                                    f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png"
                                )
                            if new_screens and not meta.get("skip_imghost_upload", False):
                                uploaded_images, _ = await upload_screens(
                                    meta,
                                    multi_screens,
                                    1,
                                    0,
                                    multi_screens,
                                    new_screens,
                                    {new_images_key: meta[new_images_key]},
                                    allowed_hosts=approved_image_hosts,
                                )
                                if uploaded_images and not meta.get("skip_imghost_upload", False):
                                    await self.common.save_image_links(meta, new_images_key, uploaded_images)
                                for img in uploaded_images:
                                    meta[new_images_key].append(
                                        {
                                            "img_url": img["img_url"],
                                            "raw_url": img["raw_url"],
                                            "web_url": img["web_url"],
                                        }
                                    )

                                desc_parts.append("[center]")
                                for img in uploaded_images:
                                    web_url = img["web_url"]
                                    raw_url = img["raw_url"]
                                    image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                    desc_parts.append(image_str)
                                desc_parts.append("[/center]\n\n")

                            meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                            async with aiofiles.open(meta_filename, "w") as f:
                                await f.write(json.dumps(meta, indent=4))

        # Handle multiple discs case
        elif len(discs) > 1:
            # Initialize retry_count if not already set
            if "retry_count" not in meta:
                meta["retry_count"] = 0

            total_discs_to_process = min(len(discs), process_limit)
            processed_count = 0
            if multi_screens != 0:
                console.print("[cyan]Processing screenshots for packed content (multiScreens)[/cyan]")
                console.print(f"[cyan]{total_discs_to_process} files (processLimit)[/cyan]")

            for i, each in enumerate(discs):
                # Set a unique key per disc for managing images
                new_images_key = f"new_images_disc_{i}"

                if i == 0:
                    desc_parts.append("[center]")
                    if each["type"] == "BDMV":
                        desc_parts.append(f"{each.get('name', 'BDINFO')}\n\n")
                    elif each["type"] == "DVD":
                        desc_parts.append(f"{each['name']}:\n")
                        desc_parts.append(
                            f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler]"
                        )
                        desc_parts.append(
                            f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n"
                        )
                    # For the first disc, use images from `meta['image_list']` and add screenheader if applicable
                    if meta["debug"]:
                        console.print("[yellow]Using original uploaded images for first disc")
                    if screenheader is not None:
                        desc_parts.append("[/center]\n\n")
                        desc_parts.append(screenheader + "\n")
                        desc_parts.append("[center]")
                    for img_index in range(len(images[: int(meta["screens"])])):
                        web_url = images[img_index]["web_url"]
                        raw_url = images[img_index]["raw_url"]
                        image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url]"
                        desc_parts.append(image_str)
                        if screensPerRow and (img_index + 1) % screensPerRow == 0:
                            desc_parts.append("\n")
                    desc_parts.append("[/center]\n\n")
                else:
                    if multi_screens != 0:
                        processed_count += 1
                        disc_name = each.get("name", f"Disc {i}")
                        print(
                            f"\rProcessing disc {processed_count}/{total_discs_to_process}: {disc_name[:40]}{'...' if len(disc_name) > 40 else ''}",
                            end="",
                            flush=True,
                        )
                        # Check if screenshots exist for the current disc key
                        # Check for saved images first
                        if (
                            pack_images_data
                            and "keys" in pack_images_data
                            and new_images_key in pack_images_data["keys"]
                        ):
                            saved_images = pack_images_data["keys"][new_images_key]["images"]
                            if saved_images:
                                if meta["debug"]:
                                    console.print(
                                        f"[yellow]Using saved images from pack_image_links.json for {new_images_key}"
                                    )

                                meta[new_images_key] = []
                                for img in saved_images:
                                    meta[new_images_key].append(
                                        {
                                            "img_url": img.get("img_url", ""),
                                            "raw_url": img.get("raw_url", ""),
                                            "web_url": img.get("web_url", ""),
                                        }
                                    )
                        if new_images_key in meta and meta[new_images_key]:
                            if meta["debug"]:
                                console.print(f"[yellow]Found needed image URLs for {new_images_key}")
                            desc_parts.append("[center]")
                            if each["type"] == "BDMV":
                                desc_parts.append(
                                    f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n"
                                )
                            elif each["type"] == "DVD":
                                desc_parts.append(f"{each['name']}:\n")
                                desc_parts.append(
                                    f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler] "
                                )
                                desc_parts.append(
                                    f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n"
                                )
                            desc_parts.append("[/center]\n\n")
                            # Use existing URLs from meta to write to descfile
                            desc_parts.append("[center]")
                            for img in meta[new_images_key]:
                                web_url = img["web_url"]
                                raw_url = img["raw_url"]
                                image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url]"
                                desc_parts.append(image_str)
                            desc_parts.append("[/center]\n\n")
                        else:
                            # Increment retry_count for tracking but use unique disc keys for each disc
                            meta["retry_count"] += 1
                            meta[new_images_key] = []
                            desc_parts.append("[center]")
                            if each["type"] == "BDMV":
                                desc_parts.append(
                                    f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n"
                                )
                            elif each["type"] == "DVD":
                                desc_parts.append(f"{each['name']}:\n")
                                desc_parts.append(
                                    f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler] "
                                )
                                desc_parts.append(
                                    f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n"
                                )
                            desc_parts.append("[/center]\n\n")
                            # Check if new screenshots already exist before running prep.screenshots
                            if each["type"] == "BDMV":
                                new_screens = glob.glob1(
                                    f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"
                                )
                            elif each["type"] == "DVD":
                                new_screens = glob.glob1(
                                    f"{meta['base_dir']}/tmp/{meta['uuid']}",
                                    f"{meta['discs'][i]['name']}-*.png",
                                )
                            if not new_screens:
                                if meta["debug"]:
                                    console.print(
                                        f"[yellow]No new screens for {new_images_key}; creating new screenshots"
                                    )
                                # Run prep.screenshots if no screenshots are present
                                if each["type"] == "BDMV":
                                    use_vs = meta.get("vapoursynth", False)
                                    try:
                                        await disc_screenshots(
                                            meta,
                                            f"FILE_{i}",
                                            each["bdinfo"],
                                            meta["uuid"],
                                            meta["base_dir"],
                                            use_vs,
                                            [],
                                            meta.get("ffdebug", False),
                                            multi_screens,
                                            True,
                                        )
                                    except Exception as e:
                                        print(f"Error during BDMV screenshot capture: {e}")
                                    new_screens = glob.glob1(
                                        f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png"
                                    )
                                if each["type"] == "DVD":
                                    try:
                                        await dvd_screenshots(meta, i, multi_screens, True)
                                    except Exception as e:
                                        print(f"Error during DVD screenshot capture: {e}")
                                    new_screens = glob.glob1(
                                        f"{meta['base_dir']}/tmp/{meta['uuid']}",
                                        f"{meta['discs'][i]['name']}-*.png",
                                    )

                            if new_screens and not meta.get("skip_imghost_upload", False):
                                uploaded_images, _ = await upload_screens(
                                    meta,
                                    multi_screens,
                                    1,
                                    0,
                                    multi_screens,
                                    new_screens,
                                    {new_images_key: meta[new_images_key]},
                                    allowed_hosts=approved_image_hosts,
                                )
                                if uploaded_images and not meta.get("skip_imghost_upload", False):
                                    await self.common.save_image_links(meta, new_images_key, uploaded_images)
                                # Append each uploaded image's data to `meta[new_images_key]`
                                for img in uploaded_images:
                                    meta[new_images_key].append(
                                        {
                                            "img_url": img["img_url"],
                                            "raw_url": img["raw_url"],
                                            "web_url": img["web_url"],
                                        }
                                    )

                                # Write new URLs to descfile
                                desc_parts.append("[center]")
                                for img in uploaded_images:
                                    web_url = img["web_url"]
                                    raw_url = img["raw_url"]
                                    image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url]"
                                    desc_parts.append(image_str)
                                desc_parts.append("[/center]\n\n")

                            # Save the updated meta to `meta.json` after upload
                            meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                            async with aiofiles.open(meta_filename, "w") as f:
                                await f.write(json.dumps(meta, indent=4))
                        console.print()

        # Handle single file case
        filelist = meta.get("filelist", [])
        if len(filelist) == 1:
            if meta.get("comparison") and meta.get("comparison_groups"):
                desc_parts.append("[center]")
                comparison_groups = meta.get("comparison_groups", {})
                sorted_group_indices = sorted(comparison_groups.keys(), key=lambda x: int(x))

                comp_sources = []
                for group_idx in sorted_group_indices:
                    group_data = comparison_groups[group_idx]
                    group_name = group_data.get("name", f"Group {group_idx}")
                    comp_sources.append(group_name)

                sources_string = ", ".join(comp_sources)
                desc_parts.append(f"[comparison={sources_string}]\n")

                images_per_group = min(
                    [len(comparison_groups[idx].get("urls", [])) for idx in sorted_group_indices]
                )

                for img_idx in range(images_per_group):
                    for group_idx in sorted_group_indices:
                        group_data = comparison_groups[group_idx]
                        urls = group_data.get("urls", [])
                        if img_idx < len(urls):
                            img_url = urls[img_idx].get("raw_url", "")
                            if img_url:
                                desc_parts.append(f"{img_url}\n")

                desc_parts.append("[/comparison][/center]\n\n")

            if screenheader is not None:
                desc_parts.append(screenheader + "\n")
            desc_parts.append("[center]")
            for img_index in range(len(images[: int(meta["screens"])])):
                web_url = images[img_index]["web_url"]
                raw_url = images[img_index]["raw_url"]
                desc_parts.append(
                    f"[url={web_url}][img={self.config['DEFAULT'].get('thumbnail_size', '350')}]{raw_url}[/img][/url] "
                )
                if screensPerRow and (img_index + 1) % screensPerRow == 0:
                    desc_parts.append("\n")
            desc_parts.append("[/center]")

        # Handle multiple files case
        # Initialize character counter
        char_count = 0
        max_char_limit = char_limit  # Character limit
        other_files_spoiler_open = False  # Track if "Other files" spoiler has been opened
        total_files_to_process = min(len(filelist), process_limit)
        processed_count = 0
        if multi_screens != 0 and total_files_to_process > 1:
            console.print("[cyan]Processing screenshots for packed content (multiScreens)[/cyan]")
            console.print(f"[cyan]{total_files_to_process} files (processLimit)[/cyan]")

        # First Pass: Create and Upload Images for Each File
        for i, file in enumerate(filelist):
            if i >= process_limit:
                # console.print("[yellow]Skipping processing more files as they exceed the process limit.")
                continue
            if multi_screens != 0:
                if total_files_to_process > 1:
                    processed_count += 1
                    filename = os.path.basename(file)
                    print(
                        f"\rProcessing file {processed_count}/{total_files_to_process}: {filename[:40]}{'...' if len(filename) > 40 else ''}",
                        end="",
                        flush=True,
                    )
                if i > 0:
                    new_images_key = f"new_images_file_{i}"
                    # Check for saved images first
                    if (
                        pack_images_data
                        and "keys" in pack_images_data
                        and new_images_key in pack_images_data["keys"]
                    ):
                        saved_images = pack_images_data["keys"][new_images_key]["images"]
                        if saved_images:
                            if meta["debug"]:
                                console.print(
                                    f"[yellow]Using saved images from pack_image_links.json for {new_images_key}"
                                )

                            meta[new_images_key] = []
                            for img in saved_images:
                                meta[new_images_key].append(
                                    {
                                        "img_url": img.get("img_url", ""),
                                        "raw_url": img.get("raw_url", ""),
                                        "web_url": img.get("web_url", ""),
                                    }
                                )
                    if new_images_key not in meta or not meta[new_images_key]:
                        meta[new_images_key] = []
                        # Proceed with image generation if not already present
                        new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")

                        # If no screenshots exist, create them
                        if not new_screens:
                            if meta["debug"]:
                                console.print(
                                    f"[yellow]No existing screenshots for {new_images_key}; generating new ones."
                                )
                        try:
                            await screenshots(
                                file,
                                f"FILE_{i}",
                                meta["uuid"],
                                meta["base_dir"],
                                meta,
                                multi_screens,
                                True,
                                None,
                            )
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            print(f"Error during generic screenshot capture: {e}")

                        new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")

                        # Upload generated screenshots
                        if new_screens and not meta.get("skip_imghost_upload", False):
                            uploaded_images, _ = await upload_screens(
                                meta,
                                multi_screens,
                                1,
                                0,
                                multi_screens,
                                new_screens,
                                {new_images_key: meta[new_images_key]},
                                allowed_hosts=approved_image_hosts,
                            )
                            if uploaded_images and not meta.get("skip_imghost_upload", False):
                                await self.common.save_image_links(meta, new_images_key, uploaded_images)
                            for img in uploaded_images:
                                meta[new_images_key].append(
                                    {
                                        "img_url": img["img_url"],
                                        "raw_url": img["raw_url"],
                                        "web_url": img["web_url"],
                                    }
                                )

                            await asyncio.sleep(0.1)

                await asyncio.sleep(0.05)

        # Save updated meta
        meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
        async with aiofiles.open(meta_filename, "w") as f:
            await f.write(json.dumps(meta, indent=4))
        await asyncio.sleep(0.1)

        # Second Pass: Process MediaInfo and Write Descriptions
        if len(filelist) > 1:
            for i, file in enumerate(filelist):
                if i >= process_limit:
                    continue
                # Extract filename directly from the file path
                filename = (
                    os.path.splitext(os.path.basename(file.strip()))[0].replace("[", "").replace("]", "")
                )

                # If we are beyond the file limit, add all further files in a spoiler
                if multi_screens != 0:
                    if i >= file_limit:
                        if not other_files_spoiler_open:
                            desc_parts.append("[center][spoiler=Other files]\n")
                            char_count += len("[center][spoiler=Other files]\n")
                            other_files_spoiler_open = True

                # Write filename in BBCode format with MediaInfo in spoiler if not the first file
                if multi_screens != 0:
                    if i > 0 and char_count < max_char_limit:
                        mi_dump = MediaInfo.parse(
                            file, output="STRING", full=False, mediainfo_options={"inform_version": "1"}
                        )
                        parsed_mediainfo = self.parser.parse_mediainfo(mi_dump)
                        formatted_bbcode = self.parser.format_bbcode(parsed_mediainfo)
                        desc_parts.append(
                            f"[center][spoiler={filename}]{formatted_bbcode}[/spoiler][/center]\n"
                        )
                        char_count += len(
                            f"[center][spoiler={filename}]{formatted_bbcode}[/spoiler][/center]\n"
                        )
                    else:
                        if i == 0 and images and screenheader is not None:
                            desc_parts.append(screenheader + "\n")
                            char_count += len(screenheader + "\n")
                        desc_parts.append(f"[center]{filename}\n[/center]\n")
                        char_count += len(f"[center]{filename}\n[/center]\n")

                # Write images if they exist
                new_images_key = f"new_images_file_{i}"
                if i == 0:  # For the first file, use 'image_list' key and add screenheader if applicable
                    if images:
                        if screenheader is not None:
                            desc_parts.append(screenheader + "\n")
                            char_count += len(screenheader + "\n")
                        desc_parts.append("[center]")
                        char_count += len("[center]")
                        for img_index in range(len(images)):
                            web_url = images[img_index]["web_url"]
                            raw_url = images[img_index]["raw_url"]
                            image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                            desc_parts.append(image_str)
                            char_count += len(image_str)
                            if screensPerRow and (img_index + 1) % screensPerRow == 0:
                                desc_parts.append("\n")
                        desc_parts.append("[/center]\n\n")
                        char_count += len("[/center]\n\n")
                elif multi_screens != 0:
                    if new_images_key in meta and meta[new_images_key]:
                        desc_parts.append("[center]")
                        char_count += len("[center]")
                        for img in meta[new_images_key]:
                            web_url = img["web_url"]
                            raw_url = img["raw_url"]
                            image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                            desc_parts.append(image_str)
                            char_count += len(image_str)
                        desc_parts.append("[/center]\n\n")
                        char_count += len("[/center]\n\n")

            if other_files_spoiler_open:
                desc_parts.append("[/spoiler][/center]\n")
                char_count += len("[/spoiler][/center]\n")

        if char_count >= 1 and meta["debug"]:
            console.print(f"[yellow]Total characters written to description: {char_count}")
        if total_files_to_process > 1:
            console.print()

        description = "".join(part for part in desc_parts if part.strip())

        return description
