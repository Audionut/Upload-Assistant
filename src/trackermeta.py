from src.console import console
from src.trackers.COMMON import COMMON
from data.config import config
import aiohttp
import asyncio
import sys
from PIL import Image
import io
from io import BytesIO
import os
import click
from src.btnid import get_bhd_torrents

# Define expected amount of screenshots from the config
expected_images = int(config['DEFAULT']['screens'])
valid_images = []


async def prompt_user_for_confirmation(message: str) -> bool:
    try:
        response = input(f"{message} (Y/n): ").strip().lower()
        if response in ["y", "yes", ""]:
            return True
        return False
    except EOFError:
        sys.exit(1)


async def check_images_concurrently(imagelist, meta):
    # Ensure meta['image_sizes'] exists
    if 'image_sizes' not in meta:
        meta['image_sizes'] = {}

    seen_urls = set()
    unique_images = []

    for img in imagelist:
        img_url = img.get('raw_url')
        if img_url and img_url not in seen_urls:
            seen_urls.add(img_url)
            unique_images.append(img)
        elif img_url:
            if meta.get('debug'):
                console.print(f"[yellow]Removing duplicate image URL: {img_url}[/yellow]")

    if len(unique_images) < len(imagelist) and meta['debug']:
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
    expected_resolution_name = meta.get('resolution', None)
    expected_vertical_resolution = resolution_map.get(expected_resolution_name, None)

    # If no valid resolution is found, skip processing
    if expected_vertical_resolution is None:
        console.print("[red]Meta resolution is invalid or missing. Skipping all images.[/red]")
        return []

    # Function to check each image's URL, host, and log resolution
    save_directory = f"{meta['base_dir']}/tmp/{meta['uuid']}"

    timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_connect=10, sock_read=10)

    async def check_and_collect(image_dict):
        img_url = image_dict.get('raw_url')
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
                                        upper_bound = expected_vertical_resolution * (1.30 if meta['is_disc'] == "DVD" else 1.00)

                                        if not (lower_bound <= vertical_resolution <= upper_bound):
                                            console.print(
                                                f"[red]Image {img_url} resolution ({vertical_resolution}p) "
                                                f"is outside the allowed range ({int(lower_bound)}-{int(upper_bound)}p). Skipping.[/red]"
                                            )
                                            return None

                                        # Save image
                                        os.makedirs(save_directory, exist_ok=True)
                                        image_filename = os.path.join(save_directory, os.path.basename(img_url))
                                        with open(image_filename, "wb") as f:
                                            f.write(image_content)

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

    async def bounded_check(image_dict):
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


async def check_image_link(url, timeout=None):
    # Handle when pixhost url points to web_url and convert to raw_url
    if url.startswith("https://pixhost.to/show/"):
        url = url.replace("https://pixhost.to/show/", "https://img1.pixhost.to/images/", 1)

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
                            except (IOError, SyntaxError) as e:
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


async def update_meta_with_unit3d_data(meta, tracker_data, tracker_name, only_id=False):
    # Unpack the expected 9 elements, ignoring any additional ones
    tmdb, imdb, tvdb, mal, desc, category, infohash, imagelist, filename, *rest = tracker_data

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
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            if len(desc) > 0:
                description.write((desc or "") + "\n")
    if category and not meta.get('category'):
        cat_upper = category.upper()
        if "MOVIE" in cat_upper:
            meta['category'] = "MOVIE"
        elif "TV" in cat_upper:
            meta['category'] = "TV"
        if meta['debug']:
            console.print("set Category:", meta['category'])

    if not meta.get('image_list'):  # Only handle images if image_list is not already populated
        if imagelist:  # Ensure imagelist is not empty before setting
            valid_images = await check_images_concurrently(imagelist, meta)
            if valid_images:
                meta['image_list'] = valid_images
                if meta.get('image_list'):  # Double-check if image_list is set before handling it
                    if not (meta.get('blu') or meta.get('aither') or meta.get('lst') or meta.get('oe') or meta.get('huno') or meta.get('ulcx')) or meta['unattended']:
                        await handle_image_list(meta, tracker_name, valid_images)

    if filename:
        meta[f'{tracker_name.lower()}_filename'] = filename

    if meta['debug']:
        console.print(f"[green]{tracker_name} data successfully updated in meta[/green]")


async def update_metadata_from_tracker(tracker_name, tracker_instance, meta, search_term, search_file_folder, only_id=False):
    tracker_key = tracker_name.lower()
    manual_key = f"{tracker_key}_manual"
    found_match = False

    if tracker_name == "PTP":
        imdb_id = 0
        ptp_imagelist = []
        if meta.get('ptp') is None:
            imdb_id, ptp_torrent_id, meta['ext_torrenthash'] = await tracker_instance.get_ptp_id_imdb(search_term, search_file_folder, meta)
            if ptp_torrent_id:
                if imdb_id:
                    console.print(f"[green]{tracker_name} IMDb ID found: tt{str(imdb_id).zfill(7)}[/green]")

                if not meta['unattended']:
                    if await prompt_user_for_confirmation("Do you want to use this ID data from PTP?"):
                        meta['imdb_id'] = imdb_id
                        found_match = True
                        meta['ptp'] = ptp_torrent_id

                        if not only_id or meta.get('keep_images'):
                            ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
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
                        ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
                    if ptp_imagelist:
                        valid_images = await check_images_concurrently(ptp_imagelist, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
            else:
                console.print("[yellow]Skipping PTP as no match found[/yellow]")
                found_match = False

        else:
            ptp_torrent_id = meta['ptp']
            imdb_id, meta['ext_torrenthash'] = await tracker_instance.get_imdb_from_torrent_id(ptp_torrent_id)
            if imdb_id:
                meta['imdb_id'] = imdb_id
                if meta['debug']:
                    console.print(f"[green]IMDb ID found: tt{str(meta['imdb_id']).zfill(7)}[/green]")
                found_match = True
                meta['skipit'] = True
                if not only_id or meta.get('keep_images'):
                    ptp_imagelist = await tracker_instance.get_ptp_description(meta['ptp'], meta, meta.get('is_disc', False))
                if ptp_imagelist:
                    valid_images = await check_images_concurrently(ptp_imagelist, meta)
                    if valid_images:
                        meta['image_list'] = valid_images
                        console.print("[green]PTP images added to metadata.[/green]")
            else:
                console.print(f"[yellow]Could not find IMDb ID using PTP ID: {ptp_torrent_id}[/yellow]")
                found_match = False

    elif tracker_name == "BHD":
        bhd_main_api = config['TRACKERS']['BHD'].get('api_key')
        bhd_other_api = config['DEFAULT'].get('bhd_api')
        if bhd_main_api and len(bhd_main_api) < 25:
            bhd_main_api = None
        if bhd_other_api and len(bhd_other_api) < 25:
            bhd_other_api = None
        elif bhd_other_api and len(bhd_other_api) > 25:
            console.print("[red]BHD API key is being retired from the DEFAULT config section. Only using api from the BHD tracker section instead.[/red]")
            await asyncio.sleep(2)
        bhd_api = bhd_main_api if bhd_main_api else bhd_other_api
        bhd_main_rss = config['TRACKERS']['BHD'].get('bhd_rss_key')
        bhd_other_rss = config['DEFAULT'].get('bhd_rss_key')
        if bhd_main_rss and len(bhd_main_rss) < 25:
            bhd_main_rss = None
        if bhd_other_rss and len(bhd_other_rss) < 25:
            bhd_other_rss = None
        elif bhd_other_rss and len(bhd_other_rss) > 25:
            console.print("[red]BHD RSS key is being retired from the DEFAULT config section. Only using rss key from the BHD tracker section instead.[/red]")
            await asyncio.sleep(2)
        bhd_rss_key = bhd_main_rss if bhd_main_rss else bhd_other_rss
        if not bhd_api or not bhd_rss_key:
            console.print("[red]BHD API or RSS key not found. Please check your configuration.[/red]")
            return meta, False
        use_foldername = (meta.get('is_disc') is not None or
                          meta.get('keep_folder') is True or
                          meta.get('isdir') is True)

        if meta.get('bhd'):
            await get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, torrent_id=meta['bhd'])
        elif use_foldername:
            # Use folder name from path if available, fall back to UUID
            folder_path = meta.get('path', '')
            foldername = os.path.basename(folder_path) if folder_path else meta.get('uuid', '')
            await get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, foldername=foldername)
        else:
            # Only use filename if none of the folder conditions are met
            filename = os.path.basename(meta['filelist'][0]) if meta.get('filelist') else None
            await get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, filename=filename)

        if meta.get('imdb_id') or meta.get('tmdb_id'):
            if not meta['unattended']:
                console.print(f"[green]{tracker_name} data found: IMDb ID: {meta.get('imdb_id')}, TMDb ID: {meta.get('tmdb_id')}[/green]")
                if await prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                    if meta.get('description') and meta.get('description') != "":
                        description = meta.get('description')
                        console.print("[bold green]Successfully grabbed description from BHD")
                        console.print(f"Description after cleaning:\n{description[:1000]}...", markup=False)

                        if not meta.get('skipit'):
                            console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                            edit_choice = input("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")

                            if edit_choice.lower() == 'e':
                                edited_description = click.edit(description)
                                if edited_description:
                                    desc = edited_description.strip()
                                    meta['description'] = desc
                                    meta['saved_description'] = True
                                console.print(f"[green]Final description after editing:[/green] {meta['description']}", markup=False)
                            elif edit_choice.lower() == 'd':
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
                                with open(nfo_file_path, 'r', encoding='utf-8') as nfo_file:
                                    nfo_content = nfo_file.read()
                                    console.print("[bold green]Successfully grabbed FraMeSToR description")
                                    console.print(f"Description content:\n{nfo_content[:1000]}...", markup=False)
                                    console.print("[cyan]Do you want to discard or keep the description?[/cyan]")
                                    edit_choice = input("Enter 'd' to discard, or press Enter to keep it as is: ")

                                    if edit_choice.lower() == 'd':
                                        meta['description'] = ""
                                        meta['image_list'] = []
                                        nfo_file_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], "bhd.nfo")
                                        nfo_file.close()

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
                                                        import time
                                                        time.sleep(1)
                                                    else:
                                                        console.print(f"[red]Failed to delete BHD NFO file after 3 attempts: {e}[/red]")
                                        except Exception as e:
                                            console.print(f"[red]Error during file cleanup: {e}[/red]")
                                        meta['nfo'] = False
                                        meta['bhd_nfo'] = False
                                        console.print("[yellow]Description discarded.[/yellow]")
                                    else:
                                        console.print("[green]Keeping the original description.[/green]")

                    if meta.get('image_list'):
                        valid_images = await check_images_concurrently(meta.get('image_list'), meta)
                        if valid_images:
                            meta['image_list'] = valid_images
                            await handle_image_list(meta, tracker_name, valid_images)
                            found_match = True
                            console.print(f"[green]{tracker_name} data retained.[/green]")
                        else:
                            meta['image_list'] = []
                else:
                    console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                    meta[tracker_key] = None
                    meta['imdb_id'] = 0
                    meta['tmdb_id'] = 0
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
                console.print(f"[green]{tracker_name} data found: IMDb ID: {meta.get('imdb_id')}, TMDb ID: {meta.get('tmdb_id')}[/green]")
                if meta.get('image_list'):
                    valid_images = await check_images_concurrently(meta.get('image_list'), meta)
                    if valid_images:
                        meta['image_list'] = valid_images
                        found_match = True
                    else:
                        meta['image_list'] = []
        else:
            found_match = False

    elif tracker_name in ["HUNO", "BLU", "AITHER", "LST", "OE", "ULCX"]:
        if meta.get(tracker_key) is not None:
            if meta['debug']:
                console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")
            tracker_data = await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.id_url,
                tracker_instance.search_url,
                meta,
                id=meta[tracker_key],
                only_id=only_id
            )
        else:
            if meta['debug']:
                console.print(f"[yellow]No ID found in meta for {tracker_name}, searching by file name[/yellow]")
            tracker_data = await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.id_url,
                tracker_instance.search_url,
                meta,
                file_name=search_term,
                only_id=only_id
            )

        if any(item not in [None, 0] for item in tracker_data[:3]):  # Check for valid tmdb, imdb, or tvdb
            if meta['debug']:
                console.print(f"[green]Valid data found on {tracker_name}, setting meta values[/green]")
            await update_meta_with_unit3d_data(meta, tracker_data, tracker_name, only_id)
            found_match = True
        else:
            if meta['debug']:
                console.print(f"[yellow]No valid data found on {tracker_name}[/yellow]")
            found_match = False

    elif tracker_name == "HDB":
        from src.bbcode import BBCODE
        bbcode = BBCODE()
        if meta.get('hdb') is not None:
            meta[manual_key] = meta[tracker_key]
            console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")

            # Use get_info_from_torrent_id function if ID is found in meta
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], meta['hdb_description'] = await tracker_instance.get_info_from_torrent_id(meta[tracker_key])

            if imdb or tvdb_id:
                meta['imdb_id'] = imdb if imdb else meta.get('imdb_id', 0)
                meta['tvdb_id'] = tvdb_id if tvdb_id else meta.get('tvdb_id', 0)
                meta['hdb_name'] = hdb_name
                found_match = True
                result = bbcode.clean_hdb_description(meta['hdb_description'])
                if meta['hdb_description'] and len(meta['hdb_description']) > 0 and not only_id:
                    if result is None:
                        console.print("[yellow]Failed to clean HDB description, it might be empty or malformed[/yellow]")
                        meta['description'] = ""
                        meta['image_list'] = []
                    else:
                        meta['description'], meta['image_list'] = result
                        meta['saved_description'] = True

                if meta.get('image_list') and meta.get('keep_images'):
                    valid_images = await check_images_concurrently(meta.get('image_list'), meta)
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
            console.print("[yellow]No ID found in meta for HDB, searching by file name[/yellow]")

            # Use search_filename function if ID is not found in meta
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], meta['hdb_description'], tracker_id = await tracker_instance.search_filename(search_term, search_file_folder, meta)
            meta['hdb_name'] = hdb_name
            if tracker_id:
                meta[tracker_key] = tracker_id

            if imdb or tvdb_id:
                if not meta['unattended']:
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
                    if await prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                        console.print(f"[green]{tracker_name} data retained.[/green]")
                        meta['imdb_id'] = imdb if imdb else meta.get('imdb_id')
                        meta['tvdb_id'] = tvdb_id if tvdb_id else meta.get('tvdb_id')
                        found_match = True
                        if meta['hdb_description'] and len(meta['hdb_description']) > 0 and not only_id:
                            result = bbcode.clean_hdb_description(meta['hdb_description'])
                            if result is None:
                                console.print("[yellow]Failed to clean HDB description, it might be empty or malformed[/yellow]")
                                meta['description'] = ""
                                meta['image_list'] = []
                            else:
                                desc, meta['image_list'] = result
                                console.print("[bold green]Successfully grabbed description from HDB")
                                console.print(f"Description content:\n{desc[:1000]}...", markup=False)
                                console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                                edit_choice = input("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")

                                if edit_choice.lower() == 'e':
                                    edited_description = click.edit(desc)
                                    if edited_description:
                                        desc = edited_description.strip()
                                        meta['description'] = desc
                                        meta['saved_description'] = True
                                    console.print(f"[green]Final description after editing:[/green] {desc}", markup=False)
                                elif edit_choice.lower() == 'd':
                                    meta['description'] = ""
                                    meta['hdb_description'] = ""
                                    console.print("[yellow]Description discarded.[/yellow]")
                                else:
                                    console.print("[green]Keeping the original description.[/green]")
                                    meta['description'] = desc
                                    meta['saved_description'] = True
                                if meta.get('image_list') and meta.get('keep_images'):
                                    valid_images = await check_images_concurrently(meta.get('image_list'), meta)
                                    if valid_images:
                                        meta['image_list'] = valid_images
                                        await handle_image_list(meta, tracker_name, valid_images)
                    else:
                        console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                        meta[tracker_key] = None
                        meta['tvdb_id'] = meta.get('tvdb_id') if meta.get('tvdb_id') else 0
                        meta['imdb_id'] = meta.get('imdb_id') if meta.get('imdb_id') else 0
                        meta['hdb_name'] = None
                        found_match = False
                else:
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {hdb_name}[/green]")
                    found_match = True
            else:
                found_match = False

    return meta, found_match


async def handle_image_list(meta, tracker_name, valid_images=None):
    if meta.get('image_list'):
        console.print(f"[cyan]Selected the following {len(valid_images)} valid images from {tracker_name}:")
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
