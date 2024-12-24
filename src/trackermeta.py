from src.console import console
from src.trackers.COMMON import COMMON
from data.config import config
import aiohttp
import asyncio
import sys
from PIL import Image
import io
from io import BytesIO


async def prompt_user_for_confirmation(message: str) -> bool:
    try:
        response = input(f"{message} (Y/n): ").strip().lower()
        if response in ["y", "yes", ""]:
            return True
        return False
    except EOFError:
        sys.exit(1)


async def check_images_concurrently(imagelist, meta):
    approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb']
    invalid_host_found = False  # Track if any image is on a non-approved host

    # Ensure meta['image_sizes'] exists
    if 'image_sizes' not in meta:
        meta['image_sizes'] = {}

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
    async def check_and_collect(image_dict):
        img_url = image_dict.get('raw_url')
        if not img_url:
            return None

        if "ptpimg.me" in img_url and img_url.startswith("http://"):
            img_url = img_url.replace("http://", "https://")
            image_dict['raw_url'] = img_url
            image_dict['web_url'] = img_url

        # Verify the image link
        if await check_image_link(img_url):
            # Check if the image is hosted on an approved image host
            if not any(host in img_url for host in approved_image_hosts):
                nonlocal invalid_host_found
                invalid_host_found = True  # Mark that we found an invalid host

            async with aiohttp.ClientSession() as session:
                async with session.get(img_url) as response:
                    if response.status == 200:
                        image_content = await response.read()

                        try:
                            image = Image.open(BytesIO(image_content))
                            vertical_resolution = image.height
                            lower_bound = expected_vertical_resolution * 0.70  # 30% below
                            if meta['is_disc'] == "DVD":
                                upper_bound = expected_vertical_resolution * 1.30
                            else:
                                upper_bound = expected_vertical_resolution * 1.00

                            if not (lower_bound <= vertical_resolution <= upper_bound):
                                console.print(
                                    f"[red]Image {img_url} resolution ({vertical_resolution}p) "
                                    f"is outside the allowed range ({int(lower_bound)}-{int(upper_bound)}p). Skipping.[/red]"
                                )
                                return None

                            meta['image_sizes'][img_url] = len(image_content)
                            console.print(
                                f"Valid image {img_url} with resolution {image.width}x{image.height} "
                                f"and size {len(image_content) / 1024:.2f} KiB"
                            )
                        except Exception as e:
                            console.print(f"[red]Failed to process image {img_url}: {e}")
                            return None
                    else:
                        console.print(f"[red]Failed to fetch image {img_url}. Skipping.")

            return image_dict
        else:
            return None

    # Run image verification concurrently
    tasks = [check_and_collect(image_dict) for image_dict in imagelist]
    results = await asyncio.gather(*tasks)

    # Collect valid images
    valid_images = [image for image in results if image is not None]

    # Convert default_trackers string into a list
    default_trackers = config['TRACKERS'].get('default_trackers', '')
    trackers_list = [tracker.strip() for tracker in default_trackers.split(',')]

    # Ensure meta['trackers'] is a list
    if meta.get('trackers') is not None:
        if isinstance(meta.get('trackers', ''), str):
            meta['trackers'] = [tracker.strip() for tracker in meta['trackers'].split(',')]
        if 'MTV' in meta.get('trackers', []):
            if invalid_host_found:
                console.print(
                    "[red]Warning: Some images are not hosted on an MTV-approved image host. MTV will need new images later.[/red]"
                )
    # Issue warning if any valid image is on an unapproved host and MTV is in the trackers list
    elif 'MTV' in trackers_list:
        if invalid_host_found:
            console.print("[red]Warning: Some images are not hosted on an MTV-approved image host. MTV will need new images later.[/red]")

    return valid_images


async def check_image_link(url):
    async with aiohttp.ClientSession() as session:
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
                            console.print(f"[green]Image verified successfully: {url}[/green]")
                            return True
                        except (IOError, SyntaxError) as e:  # noqa #F841
                            console.print(f"[red]Image verification failed (corrupt image): {url}[/red]")
                            return False
                    else:
                        console.print(f"[red]Content type is not an image: {url}[/red]")
                        return False
                else:
                    console.print(f"[red]Failed to retrieve image: {url} (status code: {response.status})[/red]")
                    return False
        except Exception as e:
            console.print(f"[red]Exception occurred while checking image: {url} - {str(e)}[/red]")
            return False


async def update_meta_with_unit3d_data(meta, tracker_data, tracker_name):
    # Unpack the expected 9 elements, ignoring any additional ones
    tmdb, imdb, tvdb, mal, desc, category, infohash, imagelist, filename, *rest = tracker_data

    if tmdb not in [None, '0']:
        meta['tmdb_manual'] = tmdb
    if imdb not in [None, '0']:
        meta['imdb'] = str(imdb).zfill(7)
    if tvdb not in [None, '0']:
        meta['tvdb_id'] = tvdb
    if mal not in [None, '0']:
        meta['mal'] = mal
    if desc not in [None, '0', '']:
        meta['description'] = desc
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            description.write((desc or "") + "\n")
    if category.upper() in ['MOVIE', 'TV SHOW', 'FANRES']:
        meta['category'] = 'TV' if category.upper() == 'TV SHOW' else category.upper()

    if not meta.get('image_list'):  # Only handle images if image_list is not already populated
        if imagelist:  # Ensure imagelist is not empty before setting
            valid_images = await check_images_concurrently(imagelist, meta)
            if valid_images:
                meta['image_list'] = valid_images
                if meta.get('image_list'):  # Double-check if image_list is set before handling it
                    if not (meta.get('blu') or meta.get('aither') or meta.get('lst') or meta.get('oe') or meta.get('tik')) or meta['unattended']:
                        await handle_image_list(meta, tracker_name)

    if filename:
        meta[f'{tracker_name.lower()}_filename'] = filename

    console.print(f"[green]{tracker_name} data successfully updated in meta[/green]")


async def update_metadata_from_tracker(tracker_name, tracker_instance, meta, search_term, search_file_folder):
    tracker_key = tracker_name.lower()
    manual_key = f"{tracker_key}_manual"
    found_match = False

    if tracker_name in ["BLU", "AITHER", "LST", "OE", "TIK"]:
        if meta.get(tracker_key) is not None:
            console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")
            tracker_data = await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.torrent_url,
                tracker_instance.search_url,
                meta,
                id=meta[tracker_key]
            )
        else:
            console.print(f"[yellow]No ID found in meta for {tracker_name}, searching by file name[/yellow]")
            tracker_data = await COMMON(config).unit3d_torrent_info(
                tracker_name,
                tracker_instance.torrent_url,
                tracker_instance.search_url,
                meta,
                file_name=search_term
            )

        if any(item not in [None, '0'] for item in tracker_data[:3]):  # Check for valid tmdb, imdb, or tvdb
            console.print(f"[green]Valid data found on {tracker_name}, setting meta values[/green]")
            await update_meta_with_unit3d_data(meta, tracker_data, tracker_name)
            found_match = True
        else:
            console.print(f"[yellow]No valid data found on {tracker_name}[/yellow]")
            found_match = False

    elif tracker_name == "PTP":
        imdb_id = None
        if meta.get('ptp') is None:
            imdb_id, ptp_torrent_id, ptp_torrent_hash = await tracker_instance.get_ptp_id_imdb(search_term, search_file_folder, meta)
            if ptp_torrent_id:
                meta['imdb'] = str(imdb_id).zfill(7) if imdb_id else None
                console.print(f"[green]{tracker_name} IMDb ID found: tt{meta['imdb']}[/green]")

                if not meta['unattended']:
                    if await prompt_user_for_confirmation("Do you want to use this ID data from PTP?"):
                        found_match = True
                        meta['ptp'] = ptp_torrent_id
                        ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
                        meta['description'] = ptp_desc
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
                            description.write((ptp_desc or "") + "\n")

                        if not meta.get('image_list'):
                            valid_images = await check_images_concurrently(ptp_imagelist, meta)
                            if valid_images:
                                meta['image_list'] = valid_images
                                await handle_image_list(meta, tracker_name)

                    else:
                        found_match = False
                        meta['imdb'] = None

                else:
                    found_match = True
                    ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
                    meta['description'] = ptp_desc
                    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
                        description.write((ptp_desc or "") + "\n")
                    meta['saved_description'] = True

                    if not meta.get('image_list'):
                        valid_images = await check_images_concurrently(ptp_imagelist, meta)
                        if valid_images:
                            meta['image_list'] = valid_images
            else:
                console.print("[yellow]Skipping PTP as no match found[/yellow]")
                found_match = False

        else:
            ptp_torrent_id = meta['ptp']
            console.print("[cyan]Using specified PTP ID to get IMDb ID[/cyan]")
            imdb_id, _, meta['ext_torrenthash'] = await tracker_instance.get_imdb_from_torrent_id(ptp_torrent_id)
            if imdb_id:
                meta['imdb'] = str(imdb_id).zfill(7)
                console.print(f"[green]IMDb ID found: tt{meta['imdb']}[/green]")
                found_match = True
                meta['skipit'] = True
                ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(meta['ptp'], meta, meta.get('is_disc', False))
                meta['description'] = ptp_desc
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
                    description.write(ptp_desc + "\n")
                meta['saved_description'] = True
                if not meta.get('image_list'):  # Only handle images if image_list is not already populated
                    valid_images = await check_images_concurrently(ptp_imagelist, meta)
                    if valid_images:
                        meta['image_list'] = valid_images
                        console.print("[green]PTP images added to metadata.[/green]")
            else:
                console.print(f"[yellow]Could not find IMDb ID using PTP ID: {ptp_torrent_id}[/yellow]")
                found_match = False

    elif tracker_name == "HDB":
        if meta.get('hdb') is not None:
            meta[manual_key] = meta[tracker_key]
            console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")

            # Use get_info_from_torrent_id function if ID is found in meta
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'] = await tracker_instance.get_info_from_torrent_id(meta[tracker_key])

            meta['tvdb_id'] = str(tvdb_id) if tvdb_id else meta.get('tvdb_id')
            meta['hdb_name'] = hdb_name
            found_match = True

            # Skip user confirmation if searching by ID
            console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
        else:
            console.print("[yellow]No ID found in meta for HDB, searching by file name[/yellow]")

            # Use search_filename function if ID is not found in meta
            imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], tracker_id = await tracker_instance.search_filename(search_term, search_file_folder, meta)

            meta['tvdb_id'] = str(tvdb_id) if tvdb_id else meta.get('tvdb_id')
            meta['hdb_name'] = hdb_name
            if tracker_id:
                meta[tracker_key] = tracker_id
            found_match = True

            if found_match:
                if imdb or tvdb_id or hdb_name:
                    console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
                    if await prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                        console.print(f"[green]{tracker_name} data retained.[/green]")
                    else:
                        console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                        meta[tracker_key] = None
                        meta['tvdb_id'] = None
                        meta['hdb_name'] = None
                        found_match = False
                else:
                    found_match = False

    return meta, found_match


async def handle_image_list(meta, tracker_name):
    if meta.get('image_list'):
        console.print(f"[cyan]Found the following images from {tracker_name}:")
        for img in meta['image_list']:
            console.print(f"[blue]{img}[/blue]")

        if meta['unattended']:
            keep_images = True
        else:
            keep_images = await prompt_user_for_confirmation(f"Do you want to keep the images found on {tracker_name}?")
            if not keep_images:
                meta['image_list'] = []
                meta['image_sizes'] = {}
                console.print(f"[yellow]Images discarded from {tracker_name}.")
            else:
                console.print(f"[green]Images retained from {tracker_name}.")
