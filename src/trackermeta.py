# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import io
import os
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, cast

import aiohttp
import cli_ui
import click
from PIL import Image
from typing_extensions import TypeAlias

from src.bbcode import BBCODE
from src.btnid import BtnIdManager
from src.console import console
from src.trackers.COMMON import COMMON
from src.type_utils import to_int

config: dict[str, Any] = {}
default_config: Mapping[str, Any] = {}
trackers_config: Mapping[str, Any] = {}

Meta: TypeAlias = MutableMapping[str, Any]
ImageDict: TypeAlias = dict[str, Any]


expected_images = 0


def _apply_config(next_config: dict[str, Any]) -> None:
    global config, default_config, trackers_config, expected_images
    config = next_config
    default_config = cast(Mapping[str, Any], next_config.get('DEFAULT', {}))
    trackers_config = cast(Mapping[str, Any], next_config.get('TRACKERS', {}))
    expected_images = to_int(default_config.get('screens', 0))


class TrackerMetaManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        _apply_config(config)

    async def prompt_user_for_confirmation(self, message: str) -> bool:
        return await prompt_user_for_confirmation(message)

    async def check_images_concurrently(self, imagelist: Sequence[ImageDict], meta: Meta) -> list[ImageDict]:
        return await check_images_concurrently(imagelist, meta)

    async def check_image_link(self, url: str, timeout: Optional[aiohttp.ClientTimeout] = None) -> bool:
        return await check_image_link(url, timeout)

    async def update_meta_with_unit3d_data(
        self, meta: Meta, tracker_data: Sequence[Any], tracker_name: str, only_id: bool = False
    ) -> bool:
        return await update_meta_with_unit3d_data(meta, tracker_data, tracker_name, only_id)

    async def update_metadata_from_tracker(
        self,
        tracker_name: str,
        tracker_instance: Any,
        meta: Meta,
        search_term: str,
        search_file_folder: str,
        only_id: bool = False,
    ) -> tuple[Meta, bool]:
        return await update_metadata_from_tracker(
            tracker_name,
            tracker_instance,
            meta,
            search_term,
            search_file_folder,
            only_id,
        )

    async def handle_image_list(
        self, meta: Meta, tracker_name: str, valid_images: Optional[Sequence[ImageDict]] = None
    ) -> None:
        await handle_image_list(meta, tracker_name, valid_images)


async def prompt_user_for_confirmation(message: str) -> bool:
    try:
        response_raw = cli_ui.ask_string(f"{message} (Y/n): ")
        response = (response_raw or "").strip().lower()
        return response in ["y", "yes", ""]
    except EOFError:
        sys.exit(1)


async def check_images_concurrently(imagelist: Sequence[ImageDict], meta: Meta) -> list[ImageDict]:
    # Ensure meta['image_sizes'] exists
    if 'image_sizes' not in meta:
        meta['image_sizes'] = {}

    seen_urls: set[str] = set()
    unique_images: list[ImageDict] = []

    for img in imagelist:
        img_url = cast(Optional[str], img.get('raw_url'))
        if img_url and img_url not in seen_urls:
            seen_urls.add(img_url)
            unique_images.append(img)
        elif img_url:
            if meta.get('debug'):
                console.print(f"[yellow]Removing duplicate image URL: {img_url}[/yellow]")

    if len(unique_images) < len(imagelist) and meta.get('debug'):
        console.print(f"[yellow]Removed {len(imagelist) - len(unique_images)} duplicate images from the list.[/yellow]")

    # Map fixed resolution names to vertical resolutions
    resolution_map = {
        '8640p': 8640,
        '4320p': 4320,
        '2160p': 2160,
        '1440p': 1440,
        '1080p': 1080,
        '1080i': 1080,
        '720p': 720,
        '576p': 576,
        '576i': 576,
        '480p': 480,
        '480i': 480,
    }

    # Get expected vertical resolution
    expected_resolution_name = cast(Optional[str], meta.get('resolution', None))
    expected_vertical_resolution = resolution_map.get(expected_resolution_name or "")

    # If no valid resolution is found, skip processing
    if expected_vertical_resolution is None:
        console.print("[red]Meta resolution is invalid or missing. Skipping all images.[/red]")
        return []

    # Function to check each image's URL, host, and log resolution
    save_directory = os.path.join(str(meta.get('base_dir', '')), 'tmp', str(meta.get('uuid', '')))

    timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=5)

    async def check_and_collect(image_dict: ImageDict) -> Optional[ImageDict]:
        img_url = cast(Optional[str], image_dict.get('raw_url'))
        if not img_url:
            return None

        if "ptpimg.me" in img_url and img_url.startswith("http://"):
            img_url = img_url.replace("http://", "https://")
            image_dict['raw_url'] = img_url
            image_dict['web_url'] = img_url

        # Handle when pixhost url points to web_url and convert to raw_url
        if img_url.startswith("https://pixhost.to/show/"):
            img_url = img_url.replace("https://pixhost.to/show/", "https://img1.pixhost.to/images/", 1)

        # Verify the image link
        try:
            if await check_image_link(img_url, timeout):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        try:
                            async with session.get(img_url) as response:
                                if response.status == 200:
                                    image_content = await response.read()

                                    try:
                                        image = Image.open(BytesIO(image_content))
                                        vertical_resolution = image.height
                                        lower_bound = expected_vertical_resolution * 0.70
                                        upper_bound = expected_vertical_resolution * (1.30 if meta.get('is_disc') == "DVD" else 1.00)

                                        if not (lower_bound <= vertical_resolution <= upper_bound):
                                            console.print(
                                                f"[red]Image {img_url} resolution ({vertical_resolution}p) "
                                                f"is outside the allowed range ({int(lower_bound)}-{int(upper_bound)}p). Skipping.[/red]"
                                            )
                                            return None

                                        # Save image
                                        os.makedirs(save_directory, exist_ok=True)
                                        image_filename = os.path.join(save_directory, os.path.basename(img_url))
                                        await asyncio.to_thread(Path(image_filename).write_bytes, image_content)

                                        console.print(f"Saved {img_url} as {image_filename}")

                                        meta['image_sizes'][img_url] = len(image_content)

                                        if meta['debug']:
                                            console.print(
                                                f"Valid image {img_url} with resolution {image.width}x{image.height} "
                                                f"and size {len(image_content) / 1024:.2f} KiB"
                                            )
                                        return image_dict
                                    except Exception as e:
                                        console.print(f"[red]Failed to process image {img_url}: {e}")
                                        return None
                                else:
                                    console.print(f"[red]Failed to fetch image {img_url}. Status: {response.status}. Skipping.")
                                    return None
                        except asyncio.TimeoutError:
                            console.print(f"[red]Timeout downloading image: {img_url}")
                            return None
                        except aiohttp.ClientError as e:
                            console.print(f"[red]Client error downloading image: {img_url} - {e}")
                            return None
                except Exception as e:
                    console.print(f"[red]Session error for image: {img_url} - {e}")
                    return None
            else:
                return None
        except Exception as e:
            console.print(f"[red]Error checking image: {img_url} - {e}")
            return None

    # Run image verification concurrently but with a limit to prevent too many simultaneous connections
    semaphore = asyncio.Semaphore(2)  # Limit concurrent requests to 2

    async def bounded_check(image_dict: ImageDict) -> Optional[ImageDict]:
        async with semaphore:
            return await check_and_collect(image_dict)

    tasks = [bounded_check(image_dict) for image_dict in unique_images]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as e:
        console.print(f"[red]Error during image processing: {e}")
        results = []

    # Collect valid images and limit to amount set in config
    valid_images = [image for image in results if image is not None]
    if expected_images < len(valid_images):
        valid_images = valid_images[:expected_images]

    return valid_images


async def check_image_link(url: str, timeout: Optional[aiohttp.ClientTimeout] = None) -> bool:
    # Handle when pixhost url points to web_url and convert to raw_url
    if url.startswith("https://pixhost.to/show/"):
        url = url.replace("https://pixhost.to/show/", "https://img1.pixhost.to/images/", 1)
    if timeout is None:
        timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_connect=10)

    connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification for testing

    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '').lower()
                        if 'image' in content_type:
                            # Attempt to load the image
                            image_data = await response.read()
                            try:
                                image = Image.open(io.BytesIO(image_data))
                                image.verify()  # This will check if the image is broken
                                return True
                            except (OSError, SyntaxError) as e:
                                console.print(f"[red]Image verification failed (corrupt image): {url} {e}[/red]")
                                return False
                        else:
                            console.print(f"[red]Content type is not an image: {url}[/red]")
                            return False
                    else:
                        console.print(f"[red]Failed to retrieve image: {url} (status code: {response.status})[/red]")
                        return False
            except asyncio.TimeoutError:
                console.print(f"[red]Timeout checking image link: {url}[/red]")
                return False
            except Exception as e:
                console.print(f"[red]Exception occurred while checking image: {url} - {str(e)}[/red]")
                return False
    except Exception as e:
        console.print(f"[red]Session creation failed for: {url} - {str(e)}[/red]")
        return False


async def update_meta_with_unit3d_data(meta: Meta, tracker_data: Sequence[Any], tracker_name: str, only_id: bool = False) -> bool:
    # Unpack the expected 9 elements, ignoring any additional ones
    tmdb, imdb, tvdb, mal, desc, category, _infohash, imagelist, filename, *_rest = tracker_data
    if tmdb:
        meta['tmdb_id'] = tmdb
        if meta['debug']:
            console.print("set TMDB ID:", meta['tmdb_id'])
    if imdb:
        meta['imdb_id'] = int(imdb)
        if meta['debug']:
            console.print("set IMDB ID:", meta['imdb_id'])
    if tvdb:
        meta['tvdb_id'] = tvdb
        if meta['debug']:
            console.print("set TVDB ID:", meta['tvdb_id'])
    if mal:
        meta['mal_id'] = mal
        if meta['debug']:
            console.print("set MAL ID:", meta['mal_id'])
    if desc and not only_id:
        meta['description'] = desc
        meta['saved_description'] = True
        description_path = Path(meta['base_dir']) / "tmp" / meta['uuid'] / "DESCRIPTION.txt"
        if len(desc) > 0:
            await asyncio.to_thread(description_path.write_text, (desc or "") + "\n", encoding="utf8")
    if category and not meta.get('manual_category', None):
        cat_upper = category.upper()
        if "MOVIE" in cat_upper:
            meta['category'] = "MOVIE"
        elif "TV" in cat_upper:
            meta['category'] = "TV"
        if meta['debug']:
            console.print("set Category:", meta['category'])

    imagelist_typed = cast(Optional[list[ImageDict]], imagelist)
    if imagelist_typed:  # Ensure imagelist is not empty before setting
        valid_images = await check_images_concurrently(imagelist_typed, meta)
        if valid_images:
            meta['image_list'] = valid_images
            if (
                meta.get('image_list')
                and (
                    not (meta.get('blu') or meta.get('aither') or meta.get('lst') or meta.get('oe') or meta.get('huno') or meta.get('ulcx'))
                    or meta['unattended']
                )
            ):
                await handle_image_list(meta, tracker_name, valid_images)

    if filename:
        meta[f'{tracker_name.lower()}_filename'] = filename

    if meta['debug']:
        console.print(f"[green]{tracker_name} data successfully updated in meta[/green]")
    return True


async def update_metadata_from_tracker(
    tracker_name: str,
    tracker_instance: Any,
    meta: Meta,
    search_term: str,
    search_file_folder: str,
    only_id: bool = False,
) -> tuple[Meta, bool]:
    tracker_key = tracker_name.lower()
    manual_key = f"{tracker_key}_manual"
    found_match = False

    if tracker_name == "PTP":
        imdb_id: int = 0
        ptp_imagelist: list[ImageDict] = []
        if meta.get('ptp') is None:
            ptp_result = await tracker_instance.get_ptp_id_imdb(search_term, search_file_folder, meta)
            imdb_id, ptp_torrent_id, meta['ext_torrenthash'] = cast(tuple[int, Optional[int], Optional[str]], ptp_result)
            if ptp_torrent_id:
                if imdb_id:
                    console.print(f"[green]{tracker_name} IMDb ID found: tt{str(imdb_id).zfill(7)}[/green]")

                if not meta['unattended']:
                    if await prompt_user_for_confirmation("Do you want to use this ID data from PTP?"):
                        meta['imdb_id'] = imdb_id
                        found_match = True
                        meta['ptp'] = ptp_torrent_id

                        if not only_id or meta.get('keep_images'):
                            ptp_imagelist = cast(
                                list[ImageDict],
                                await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False)),
                            )
                        if ptp_imagelist:
                            valid_images = await check_images_concurrently(ptp_imagelist, meta)
                            if valid_images:
                                meta['image_list'] = valid_images
                                await handle_image_list(meta, tracker_name, valid_images)

                    else:
                        found_match = False
                        meta['imdb_id'] = meta.get('imdb_id') if meta.get('imdb_id') else 0
                        meta['ptp'] = None
                        meta['description'] = ""
                        meta['image_list'] = []

                else:
                    found_match = True
                    meta['imdb_id'] = imdb_id
                    if not only_id or meta.get('keep_images'):
                        ptp_imagelist = cast(
                            list[ImageDict],
                            await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False)),
                        )
                    if ptp_imagelist:
                        valid_images = await check_images_concurrently(ptp_imagelist, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
            else:
                if meta['debug']:
                    console.print("[yellow]Skipping PTP as no match found[/yellow]")
                found_match = False

        else:
            ptp_torrent_id = cast(int, meta['ptp'])
            ptp_imdb_result = await tracker_instance.get_imdb_from_torrent_id(ptp_torrent_id)
            imdb_id, meta['ext_torrenthash'] = cast(tuple[int, Optional[str]], ptp_imdb_result)
            if imdb_id:
                meta['imdb_id'] = imdb_id
                if meta['debug']:
                    console.print(f"[green]IMDb ID found: tt{str(meta['imdb_id']).zfill(7)}[/green]")
                found_match = True
                meta['skipit'] = True
                if not only_id or meta.get('keep_images'):
                    ptp_imagelist = cast(
                        list[ImageDict],
                        await tracker_instance.get_ptp_description(meta['ptp'], meta, meta.get('is_disc', False)),
                    )
                if ptp_imagelist:
                    valid_images = await check_images_concurrently(ptp_imagelist, meta)
                    if valid_images:
                        meta['image_list'] = valid_images
                        console.print("[green]PTP images added to metadata.[/green]")
            else:
                console.print(f"[yellow]Could not find IMDb ID using PTP ID: {ptp_torrent_id}[/yellow]")
                found_match = False

    elif tracker_name == "BHD":
        trackers_cfg = cast(Mapping[str, Any], config.get('TRACKERS', {}))
        tracker_cfg = cast(dict[str, Any], trackers_cfg.get('BHD', {}))
        bhd_api = tracker_cfg.get('api_key')
        bhd_api = bhd_api if isinstance(bhd_api, str) else None
        if bhd_api and len(bhd_api) < 25:
            bhd_api = None

        bhd_rss_key = tracker_cfg.get('bhd_rss_key')
        bhd_rss_key = bhd_rss_key if isinstance(bhd_rss_key, str) else None
        if bhd_rss_key and len(bhd_rss_key) < 25:
            bhd_rss_key = None

        if not bhd_api or not bhd_rss_key:
            console.print("[red]BHD API or RSS key not found. Please check your configuration.[/red]")
            return meta, False
        use_foldername = (meta.get('is_disc') is not None or
                          meta.get('keep_folder') is True or
                          meta.get('isdir') is True)

        if meta.get('bhd'):
            imdb, tmdb = cast(
                tuple[Optional[int], Optional[int]],
                await BtnIdManager.get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, torrent_id=meta['bhd']),
            )
        elif use_foldername:
            # Use folder name from path if available, fall back to UUID
            folder_path = meta.get('path', '')
            foldername = os.path.basename(folder_path) if folder_path else meta.get('uuid', '')
            imdb, tmdb = cast(
                tuple[Optional[int], Optional[int]],
                await BtnIdManager.get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, foldername=foldername),
            )
        else:
            # Only use filename if none of the folder conditions are met
            filelist = cast(list[str], meta.get('filelist') or [])
            filename = os.path.basename(filelist[0]) if filelist else None
            imdb, tmdb = cast(
                tuple[Optional[int], Optional[int]],
                await BtnIdManager.get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, filename=filename),
            )

        if to_int(imdb) != 0 or to_int(tmdb) != 0:
            if not meta['unattended']:
                console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TMDb ID: {tmdb}[/green]")
                if await prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                    found_match = True
                    meta['imdb_id'] = to_int(imdb, to_int(meta.get('imdb_id')))
                    meta['tmdb_id'] = to_int(tmdb, to_int(meta.get('tmdb_id')))
                    description_value = meta.get('description')
                    if isinstance(description_value, str) and description_value:
                        description = description_value
                        console.print("[bold green]Successfully grabbed description from BHD")
                        console.print(f"Description after cleaning:\n{description[:1000]}...", markup=False)

                        if not meta.get('skipit'):
                            console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                            edit_choice = cli_ui.ask_string("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")

                            if (edit_choice or "").lower() == 'e':
                                edited_description = click.edit(description)
                                if edited_description:
                                    desc = edited_description.strip()
                                    meta['description'] = desc
                                    meta['saved_description'] = True
                                console.print(f"[green]Final description after editing:[/green] {meta['description']}", markup=False)
                            elif (edit_choice or "").lower() == 'd':
                                meta['description'] = ""
                                meta['image_list'] = []
                                console.print("[yellow]Description discarded.[/yellow]")
                            else:
                                console.print("[green]Keeping the original description.[/green]")
                                meta['description'] = description
                                meta['saved_description'] = True
                        else:
                            meta['description'] = description
                            meta['saved_description'] = True
                    elif meta.get('bhd_nfo'):
                        if not meta.get('skipit'):
                            nfo_file_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], "bhd.nfo")
                            if os.path.exists(nfo_file_path):
                                nfo_content = await asyncio.to_thread(Path(nfo_file_path).read_text, encoding="utf-8")
                                console.print("[bold green]Successfully grabbed FraMeSToR description")
                                console.print(f"Description content:\n{nfo_content[:1000]}...", markup=False)
                                console.print("[cyan]Do you want to discard or keep the description?[/cyan]")
                                edit_choice = cli_ui.ask_string("Enter 'd' to discard, or press Enter to keep it as is: ")

                                if (edit_choice or "").lower() == 'd':
                                    meta['description'] = ""
                                    meta['image_list'] = []
                                    nfo_file_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], "bhd.nfo")

                                    try:
                                        import gc
                                        gc.collect()  # Force garbage collection to close any lingering handles
                                        for attempt in range(3):
                                            try:
                                                os.remove(nfo_file_path)
                                                console.print("[yellow]NFO file successfully deleted.[/yellow]")
                                                break
                                            except Exception as e:
                                                if attempt < 2:
                                                    console.print(f"[yellow]Attempt {attempt+1}: Could not delete file, retrying in 1 second...[/yellow]")
                                                    await asyncio.sleep(1)
                                                else:
                                                    console.print(f"[red]Failed to delete BHD NFO file after 3 attempts: {e}[/red]")
                                    except Exception as e:
                                        console.print(f"[red]Error during file cleanup: {e}[/red]")
                                    meta['nfo'] = False
                                    meta['bhd_nfo'] = False
                                    console.print("[yellow]Description discarded.[/yellow]")
                                else:
                                    console.print("[green]Keeping the original description.[/green]")

                    image_list = cast(Optional[Sequence[ImageDict]], meta.get('image_list'))
                    if image_list:
                        valid_images = await check_images_concurrently(image_list, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
                            await handle_image_list(meta, tracker_name, valid_images)
                        else:
                            meta['image_list'] = []

                else:
                    console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                    meta[tracker_key] = None
                    meta['imdb_id'] = meta.get('imdb_id') if meta.get('imdb_id') else 0
                    meta['tmdb_id'] = meta.get('tmdb_id') if meta.get('tmdb_id') else 0
                    meta["framestor"] = False
                    meta["flux"] = False
                    meta["description"] = ""
                    meta["image_list"] = []
                    meta['nfo'] = False
                    meta['bhd_nfo'] = False
                    save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                    nfo_file_path = os.path.join(save_path, "bhd.nfo")
                    if os.path.exists(nfo_file_path):
                        try:
                            os.remove(nfo_file_path)
                        except Exception as e:
                            console.print(f"[red]Failed to delete BHD NFO file: {e}[/red]")
                    found_match = False
            else:
                # Only treat as match if we actually got valid IDs
                meta['imdb_id'] = to_int(imdb, to_int(meta.get('imdb_id')))
                meta['tmdb_id'] = to_int(tmdb, to_int(meta.get('tmdb_id')))
                if to_int(meta.get('imdb_id')) != 0 or to_int(meta.get('tmdb_id')) != 0:
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {meta.get('imdb_id')}, TMDb ID: {meta.get('tmdb_id')}[/green]")
                    found_match = True
                    image_list = cast(Optional[Sequence[ImageDict]], meta.get('image_list'))
                    if image_list:
                        valid_images = await check_images_concurrently(image_list, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
                        else:
                            meta['image_list'] = []
                else:
                    if meta['debug']:
                        console.print(f"[yellow]{tracker_name} returned invalid IDs (both 0), not using as match[/yellow]")
                    found_match = False
        else:
            if meta['debug']:
                console.print(f"[yellow]{tracker_name} returned invalid IDs (both 0)[/yellow]")
            found_match = False

    elif tracker_name in ["HUNO", "BLU", "AITHER", "LST", "OE", "ULCX", "RF", "OTW", "YUS", "DP", "SP"]:
        if meta.get(tracker_key) is not None:
            if meta['debug']:
                console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")
            tracker_data = cast(
                Sequence[Any],
                await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.id_url,
                tracker_instance.search_url,
                cast(dict[str, Any], meta),
                id=meta[tracker_key],
                only_id=only_id
                ),
            )
        else:
            if meta['debug']:
                console.print(f"[yellow]No ID found in meta for {tracker_name}, searching by file name[/yellow]")
            tracker_data = cast(
                Sequence[Any],
                await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.id_url,
                tracker_instance.search_url,
                cast(dict[str, Any], meta),
                file_name=search_term,
                only_id=only_id
                ),
            )

        if any(item not in [None, 0] for item in tracker_data[:3]):  # Check for valid tmdb, imdb, or tvdb
            if meta['debug']:
                console.print(f"[green]Valid data found on {tracker_name}[/green]")
            selected = await update_meta_with_unit3d_data(meta, tracker_data, tracker_name, only_id)
            found_match = bool(selected)
        else:
            if meta['debug']:
                console.print(f"[yellow]No valid data found on {tracker_name}[/yellow]")
            found_match = False

    elif tracker_name == "HDB":
        bbcode = BBCODE()
        if meta.get('hdb') is not None:
            meta[manual_key] = meta[tracker_key]
            console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")

            # Use get_info_from_torrent_id function if ID is found in meta
            hdb_info = await tracker_instance.get_info_from_torrent_id(meta[tracker_key])
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], meta['hdb_description'] = cast(
                tuple[Optional[int], Optional[int], Optional[str], Optional[str], Optional[str]],
                hdb_info,
            )

            if imdb or tvdb_id or meta['hdb_description']:
                meta['imdb_id'] = imdb if imdb else meta.get('imdb_id', 0)
                meta['tvdb_id'] = tvdb_id if tvdb_id else meta.get('tvdb_id', 0)
                meta['hdb_name'] = hdb_name
                found_match = True
                description_source = cast(str, meta.get('hdb_description') or "")
                description, image_list = cast(
                    tuple[Optional[str], list[ImageDict]],
                    bbcode.clean_hdb_description(description_source),
                )
                if description and len(description) > 0 and not only_id:
                    console.print(f"Description content:\n{description[:500]}...", markup=False)
                    meta['description'] = description
                    meta['saved_description'] = True
                else:
                    console.print("[yellow]HDB description empty[/yellow]")
                if image_list and meta.get('keep_images'):
                    valid_images = await check_images_concurrently(image_list, meta)
                    if valid_images:
                        meta['image_list'] = valid_images
                        await handle_image_list(meta, tracker_name, valid_images)
                else:
                    meta['image_list'] = []

                console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
            else:
                console.print(f"[yellow]{tracker_name} data not found for ID: {meta[tracker_key]}[/yellow]")
                found_match = False
        else:
            if meta['debug']:
                console.print("[yellow]No ID found in meta for HDB, searching by file name[/yellow]")

            # Use search_filename function if ID is not found in meta
            hdb_search = await tracker_instance.search_filename(search_term, search_file_folder, meta)
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], meta['hdb_description'], tracker_id = cast(
                tuple[Optional[int], Optional[int], Optional[str], Optional[str], Optional[str], Optional[int]],
                hdb_search,
            )
            meta['hdb_name'] = hdb_name
            if tracker_id:
                meta[tracker_key] = tracker_id

            if imdb or tvdb_id or meta['hdb_description']:
                if not meta['unattended']:
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
                    if await prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                        console.print(f"[green]{tracker_name} data retained.[/green]")
                        meta['imdb_id'] = imdb if imdb else meta.get('imdb_id')
                        meta['tvdb_id'] = tvdb_id if tvdb_id else meta.get('tvdb_id')
                        found_match = True
                        description_source = cast(str, meta.get('hdb_description') or "")
                        description, image_list = cast(
                            tuple[Optional[str], list[ImageDict]],
                            bbcode.clean_hdb_description(description_source),
                        )
                        if description and len(description) > 0 and not only_id:
                            console.print("[bold green]Successfully grabbed description from HDB")
                            console.print(f"HDB Description content:\n{description[:1000]}.....", markup=False)
                            console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                            edit_choice_raw = cli_ui.ask_string("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")
                            edit_choice = (edit_choice_raw or "").strip().lower()

                            if edit_choice.lower() == 'e':
                                edited_description = click.edit(description)
                                if edited_description:
                                    description = edited_description.strip()
                                    meta['description'] = description
                                    meta['saved_description'] = True
                                console.print(f"[green]Final description after editing:[/green] {description}", markup=False)
                            elif edit_choice.lower() == 'd':
                                meta['hdb_description'] = ""
                                console.print("[yellow]Description discarded.[/yellow]")
                            else:
                                console.print("[green]Keeping the original description.[/green]")
                                meta['description'] = description
                                meta['saved_description'] = True
                        else:
                            console.print("[yellow]HDB description empty[/yellow]")
                        if image_list and meta.get('keep_images'):
                            valid_images = await check_images_concurrently(image_list, meta)
                            if valid_images:
                                meta['image_list'] = valid_images
                                await handle_image_list(meta, tracker_name, valid_images)
                    else:
                        console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                        meta[tracker_key] = None
                        meta['tvdb_id'] = meta.get('tvdb_id') if meta.get('tvdb_id') else 0
                        meta['imdb_id'] = meta.get('imdb_id') if meta.get('imdb_id') else 0
                        meta['hdb_name'] = None
                        meta['hdb_description'] = ""
                        found_match = False
                else:
                    meta['imdb_id'] = imdb if imdb else meta.get('imdb_id')
                    meta['tvdb_id'] = tvdb_id if tvdb_id else meta.get('tvdb_id')
                    description_source = cast(str, meta.get('hdb_description') or "")
                    description, image_list = cast(
                        tuple[Optional[str], list[ImageDict]],
                        bbcode.clean_hdb_description(description_source),
                    )
                    if description and len(description) > 0 and not only_id:
                        console.print(f"HDB Description content:\n{description[:500]}.....", markup=False)
                        meta['description'] = description
                        meta['saved_description'] = True
                    if image_list and meta.get('keep_images'):
                        valid_images = await check_images_concurrently(image_list, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
                            await handle_image_list(meta, tracker_name, valid_images)
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {hdb_name}[/green]")
                    found_match = True
            else:
                meta['hdb_name'] = None
                meta['hdb_description'] = ""
                meta[tracker_key] = None
                found_match = False

    return meta, found_match


async def handle_image_list(meta: Meta, tracker_name: str, valid_images: Optional[Sequence[ImageDict]] = None) -> None:
    if meta.get('image_list'):
        valid_count = len(valid_images) if valid_images is not None else 0
        console.print(f"[cyan]Selected the following {valid_count} valid images from {tracker_name}:")
        for img in meta['image_list']:
            console.print(f"Image:[green]'{img.get('img_url')}'[/green]")

        if meta['unattended']:
            keep_images = True
        else:
            keep_images = await prompt_user_for_confirmation(f"Do you want to keep the images found on {tracker_name}?")
            if not keep_images:
                meta['image_list'] = []
                meta['image_sizes'] = {}
                save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                try:
                    import glob
                    png_files = glob.glob(os.path.join(save_path, "*.png"))
                    for png_file in png_files:
                        os.remove(png_file)

                    if png_files:
                        console.print(f"[yellow]Successfully deleted {len(png_files)} image files.[/yellow]")
                    else:
                        console.print("[yellow]No image files found to delete.[/yellow]")
                except Exception as e:
                    console.print(f"[red]Failed to delete image files: {e}[/red]")
                console.print(f"[yellow]Images discarded from {tracker_name}.")
            else:
                console.print(f"[green]Images retained from {tracker_name}.")
