# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import glob
import os
import json
import aiofiles
import asyncio
import re
from src.console import console
from urllib.parse import urlparse
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.uploadscreens import upload_screens
from data.config import config
from aiofiles import os as aio_os


async def match_host(hostname, approved_hosts):
    for approved_host in approved_hosts:
        if hostname == approved_host or hostname.endswith(f".{approved_host}"):
            return approved_host
    return hostname


async def sanitize_filename(filename):
    # Replace invalid characters like colons with an underscore
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def check_hosts(meta, tracker, url_host_mapping, img_host_index=1, approved_image_hosts=None):
    if meta.get('skip_imghost_upload', False):
        if meta['debug']:
            console.print(f"[yellow]Skipping image host upload for {tracker} as per meta['skip_imghost_upload'] setting.")
        return
    new_images_key = f'{tracker}_images_key'
    if new_images_key not in meta:
        meta[new_images_key] = []

    # Check if we have main image_list but no tracker-specific images yet
    if meta.get('image_list') and not meta.get(new_images_key):
        if meta['debug']:
            console.print(f"[yellow]Checking if existing images in meta['image_list'] can be used for {tracker}...")
        # Check if the URLs in image_list are from approved hosts
        approved_images = []
        need_reupload = False

        for image in meta.get('image_list', []):
            raw_url = image.get('raw_url')
            if not raw_url:
                continue

            parsed_url = urlparse(raw_url)
            hostname = parsed_url.netloc
            mapped_host = await match_host(hostname, url_host_mapping.keys())

            if mapped_host:
                mapped_host = url_host_mapping.get(mapped_host, mapped_host)
                if mapped_host in approved_image_hosts:
                    approved_images.append(image)
                    if meta['debug']:
                        console.print(f"[green]URL '{raw_url}' is from approved host '{mapped_host}'.")
                else:
                    need_reupload = True
                    if meta['debug']:
                        console.print(f"[yellow]URL '{raw_url}' is not from an approved host for {tracker}.")
            else:
                need_reupload = True

        # If all images are approved, use them directly
        if approved_images and len(approved_images) == len(meta.get('image_list', [])) and not need_reupload:
            meta[new_images_key] = approved_images.copy()
            if meta['debug']:
                console.print(f"[green]All existing images are from approved hosts for {tracker}.")
            return meta[new_images_key], False, False

    if tracker == "covers":
        reuploaded_images_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "covers.json")
    else:
        reuploaded_images_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "reuploaded_images.json")
    reuploaded_images = []

    if os.path.exists(reuploaded_images_path):
        try:
            async with aiofiles.open(reuploaded_images_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                reuploaded_images = json.loads(content)
        except Exception as e:
            console.print(f"[red]Failed to load reuploaded images: {e}")

    valid_reuploaded_images = []
    for image in reuploaded_images:
        raw_url = image.get('raw_url')
        if not raw_url:
            continue

        # For covers, verify the release_url matches
        if tracker == "covers" and "release_url" in meta:
            if "release_url" not in image or image["release_url"] != meta["release_url"]:
                if meta.get('debug'):
                    if "release_url" not in image:
                        console.print(f"[yellow]Skipping image without release_url: {raw_url}")
                    else:
                        console.print(f"[yellow]Skipping image with mismatched release_url: {image['release_url']} != {meta['release_url']}")
                continue

        parsed_url = urlparse(raw_url)
        hostname = parsed_url.netloc
        mapped_host = await match_host(hostname, url_host_mapping.keys())

        if mapped_host:
            mapped_host = url_host_mapping.get(mapped_host, mapped_host)
            if mapped_host in approved_image_hosts:
                valid_reuploaded_images.append(image)
            elif meta['debug']:
                console.print(f"[red]URL '{raw_url}' from reuploaded_images.json is not recognized as an approved host.")

    if valid_reuploaded_images:
        meta[new_images_key] = valid_reuploaded_images
        if tracker == "covers":
            console.print("[green]Using valid images from covers.json.")
        else:
            console.print("[green]Using valid images from reuploaded_images.json.")
        return meta[new_images_key], False, False

    # Check if the tracker-specific key has valid images
    has_valid_images = False
    if meta.get(new_images_key):
        valid_hosts = []
        for image in meta[new_images_key]:
            netloc = urlparse(image.get('raw_url', '')).netloc
            matched_host = await match_host(netloc, url_host_mapping.keys())
            mapped_host = url_host_mapping.get(matched_host, None)
            valid_hosts.append(mapped_host in approved_image_hosts)

        # Then check if all are valid
        if all(valid_hosts) and meta[new_images_key]:
            has_valid_images = True

    if has_valid_images:
        console.print(f"[green]Using valid images from {new_images_key}.")
        return meta[new_images_key], False, False

    if meta['debug']:
        console.print(f"[yellow]No valid images found for {tracker}, will attempt to reupload...")

    images_reuploaded = False
    max_retries = len(approved_image_hosts)

    while img_host_index <= max_retries:
        image_list, retry_mode, images_reuploaded = await handle_image_upload(
            meta, tracker, url_host_mapping, approved_image_hosts, img_host_index=img_host_index
        )

        if image_list:
            meta[new_images_key] = image_list

        if retry_mode:
            console.print(f"[yellow]Switching to the next image host. Current index: {img_host_index}")
            img_host_index += 1
            continue  # Retry with next host

        break

    if not meta.get(new_images_key):
        console.print("[red]All image hosts failed. Please check your configuration.")

    return meta.get(new_images_key, []), False, images_reuploaded


async def handle_image_upload(meta, tracker, url_host_mapping, approved_image_hosts=None, img_host_index=1, file=None):
    original_imghost = meta.get('imghost')
    retry_mode = False
    images_reuploaded = False
    new_images_key = f'{tracker}_images_key'
    discs = meta.get('discs', [])  # noqa F841
    filelist = meta.get('video', [])
    filename = meta['title']
    if meta.get('is_disc') == "HDDVD":
        path = meta['discs'][0]['largest_evo']
    else:
        path = meta.get('filelist', [None])
        path = path[0] if path else None

    if isinstance(filelist, str):
        filelist = [filelist]

    multi_screens = meta.get('screens') if meta.get('screens') else int(config['DEFAULT'].get('screens', 6))
    base_dir = meta['base_dir']
    folder_id = meta['uuid']
    meta[new_images_key] = []

    screenshots_dir = os.path.join(base_dir, 'tmp', folder_id)
    if meta['debug']:
        console.print(f"[yellow]Searching for screenshots in {screenshots_dir}...")
    all_screenshots = []

    # First check if there are any saved screenshots matching those in the image_list
    if meta.get('image_list') and isinstance(meta['image_list'], list):
        # Get all PNG files in the screenshots directory
        all_png_files = [file for file in await aio_os.listdir(screenshots_dir) if file.endswith('.png')]
        if all_png_files and meta.get('debug'):
            console.print(f"[cyan]Found {len(all_png_files)} PNG files in screenshots directory")

        # Extract filenames from the image_list
        image_filenames = []
        for image in meta['image_list']:
            for url_key in ['raw_url', 'img_url', 'web_url']:
                if url_key in image and image[url_key]:
                    parsed_url = urlparse(image[url_key])
                    filename_from_url = os.path.basename(parsed_url.path)
                    if filename_from_url and filename_from_url.lower().endswith('.png'):
                        image_filenames.append(filename_from_url)
                        break

        if image_filenames and meta.get('debug'):
            console.print(f"[cyan]Extracted {len(image_filenames)} filenames from image_list URLs: {image_filenames}")

        # Check if any of the extracted filenames match the actual files in the directory
        if all_png_files and image_filenames:
            for png_file in all_png_files:
                basename = os.path.basename(png_file)
                if basename in image_filenames:
                    # Found a match for this filename
                    all_screenshots.append(png_file)
                    if meta.get('debug'):
                        console.print(f"[green]Found existing screenshot matching URL: {basename}")

        # Also check for any screenshots that match the title pattern as a fallback
        if filename and len(all_screenshots) < multi_screens:
            sanitized_title = await sanitize_filename(filename)
            title_pattern_files = [f for f in all_png_files if os.path.basename(f).startswith(sanitized_title)]
            if meta['debug']:
                console.print(f"[yellow]Searching for screenshots with pattern: {sanitized_title}*.png")
            if title_pattern_files:
                # Only add title pattern files that aren't already in all_screenshots
                for file in title_pattern_files:
                    if file not in all_screenshots:
                        all_screenshots.append(file)

                if meta.get('debug'):
                    console.print(f"[green]Found {len(title_pattern_files)} screenshots matching title pattern")

    # If we haven't found enough screenshots yet, search for files in the normal way
    if len(all_screenshots) < multi_screens:
        for i, file in enumerate(filelist):
            sanitized_title = await sanitize_filename(filename)
            filename_pattern = f"{sanitized_title}*.png"
            if meta['debug']:
                console.print(f"[yellow]Searching for screenshots with pattern: {filename_pattern}")

            if meta['is_disc'] == "DVD":
                existing_screens = await asyncio.to_thread(glob.glob, f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][0]['name']}-*.png")
            else:
                existing_screens = await asyncio.to_thread(glob.glob, os.path.join(screenshots_dir, filename_pattern))

            # Add any new screenshots to our list
            for screen in existing_screens:
                if screen not in all_screenshots:
                    all_screenshots.append(screen)

    # Fallback: glob for indexed screenshots if still not enough
    if len(all_screenshots) < multi_screens:
        os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
        image_patterns = ["*.png", ".[!.]*.png"]
        image_glob = []
        for pattern in image_patterns:
            glob_results = await asyncio.to_thread(glob.glob, pattern)
            image_glob.extend(glob_results)
            if meta['debug']:
                console.print(f"[cyan]Found {len(image_glob)} files matching pattern: {pattern}")

        unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
        unwanted_files = set()
        for pattern in unwanted_patterns:
            glob_results = await asyncio.to_thread(glob.glob, pattern)
            unwanted_files.update(glob_results)
            if pattern.startswith("FILE") or pattern.startswith("PLAYLIST") or pattern.startswith("POSTER"):
                hidden_pattern = "." + pattern
                hidden_glob_results = await asyncio.to_thread(glob.glob, hidden_pattern)
                unwanted_files.update(hidden_glob_results)

        # Remove unwanted files
        image_glob = [file for file in image_glob if file not in unwanted_files]
        image_glob = list(set(image_glob))
        if meta['debug']:
            console.print(f"[cyan]Filtered out {len(unwanted_files)} unwanted files, remaining: {len(image_glob)}")

        # Only keep files that match the indexed pattern: xxx-0.png, xxx-1.png, etc.
        indexed_pattern = re.compile(r".*-\d+\.png$")
        indexed_files = [file for file in image_glob if indexed_pattern.match(os.path.basename(file))]
        if meta['debug']:
            console.print(f"[cyan]Found {len(indexed_files)} indexed files matching pattern")

        # Add any new indexed screenshots to our list
        for screen in indexed_files:
            if screen not in all_screenshots:
                all_screenshots.append(screen)
                if meta.get('debug'):
                    console.print(f"[green]Found indexed screenshot: {os.path.basename(screen)}")

    if tracker == "covers":
        all_screenshots = []
        existing_screens = await asyncio.to_thread(glob.glob, f"{meta['base_dir']}/tmp/{meta['uuid']}/cover_*.jpg")
        for screen in existing_screens:
            if screen not in all_screenshots:
                all_screenshots.append(screen)

    # Ensure we have unique screenshots
    all_screenshots = list(set(all_screenshots))

    if tracker == "covers":
        multi_screens = len(all_screenshots)

    # If we still don't have enough screenshots, generate new ones
    if len(all_screenshots) < multi_screens:
        # Calculate how many more screenshots we need
        needed_screenshots = multi_screens - len(all_screenshots)

        if meta.get('debug'):
            console.print(f"[yellow]Found {len(all_screenshots)} screenshots, need {needed_screenshots} more to reach {multi_screens} total.")

        try:
            if meta['is_disc'] == "BDMV":
                await disc_screenshots(meta, filename, meta['bdinfo'], folder_id, base_dir,
                                       meta.get('vapoursynth', False), [], meta.get('ffdebug', False),
                                       needed_screenshots, True)
            elif meta['is_disc'] == "DVD":
                await dvd_screenshots(meta, 0, None, True)
            else:
                await screenshots(path, filename, meta['uuid'], base_dir, meta,
                                  needed_screenshots, True, None)

            if meta['is_disc'] == "DVD":
                new_screens = await asyncio.to_thread(glob.glob, f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][0]['name']}-*.png")
            else:
                # Use a more generic pattern to find any PNG files that aren't already in all_screenshots
                new_screens = await asyncio.to_thread(glob.glob, os.path.join(screenshots_dir, "*.png"))
                indexed_pattern = re.compile(r".*-\d+\.png$")
                new_screens = [s for s in new_screens if indexed_pattern.match(os.path.basename(s))]

                # Filter out files we already have
                new_screens = [screen for screen in new_screens if screen not in all_screenshots]

            # Add any new screenshots to our list (only those not already in all_screenshots)
            if new_screens and meta.get('debug'):
                console.print(f"[green]Found {len(new_screens)} new screenshots after generation")

            for screen in new_screens:
                if screen not in all_screenshots:
                    all_screenshots.append(screen)
                    if meta.get('debug'):
                        console.print(f"[green]Added new screenshot: {os.path.basename(screen)}")

        except Exception as e:
            console.print(f"[red]Error during screenshot capture: {e}")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    if not all_screenshots:
        console.print("[red]No screenshots were generated or found. Please check the screenshot generation process.")
        return [], True, images_reuploaded

    all_screenshots.sort()
    existing_from_image_list = []
    other_screenshots = []

    # First separate the screenshots into two categories
    for screenshot in all_screenshots:
        basename = os.path.basename(screenshot)
        # Check if this is from the image_list we extracted earlier
        if meta.get('image_list') and any(os.path.basename(urlparse(img.get('raw_url', '')).path) == basename
                                          for img in meta['image_list']):
            existing_from_image_list.append(screenshot)
        else:
            other_screenshots.append(screenshot)

    # First take all existing screenshots from image_list
    final_screenshots = existing_from_image_list.copy()

    # Then fill up to multi_screens with other screenshots
    remaining_needed = multi_screens - len(final_screenshots)
    if remaining_needed > 0 and other_screenshots:
        final_screenshots.extend(other_screenshots[:remaining_needed])

    # If we still don't have enough, just use whatever we have
    if len(final_screenshots) < multi_screens and len(all_screenshots) >= multi_screens:
        # Fill with any remaining screenshots not yet included
        remaining = [s for s in all_screenshots if s not in final_screenshots]
        final_screenshots.extend(remaining[:multi_screens - len(final_screenshots)])

    if tracker == "covers":
        all_screenshots = all_screenshots
    else:
        all_screenshots = final_screenshots[:multi_screens]

    if meta.get('debug'):
        console.print(f"[green]Using {len(all_screenshots)} screenshots:")
        for i, screenshot in enumerate(all_screenshots):
            console.print(f"  {i+1}. {os.path.basename(screenshot)}")

    if not meta.get('skip_imghost_upload', False):
        uploaded_images = []

        # Add a max retry limit to prevent infinite loop
        max_retries = len(approved_image_hosts)
        while img_host_index <= max_retries:
            current_img_host_key = f'img_host_{img_host_index}'
            current_img_host = config.get('DEFAULT', {}).get(current_img_host_key)

            if not current_img_host:
                console.print("[red]No more image hosts left to try.")
                return [], True, images_reuploaded

            if current_img_host not in approved_image_hosts:
                console.print(f"[red]Your preferred image host '{current_img_host}' is not supported at {tracker}, trying next host.")
                retry_mode = True
                images_reuploaded = True
                img_host_index += 1
                continue
            else:
                meta['imghost'] = current_img_host
                if meta['debug']:
                    console.print(f"[green]Uploading to approved host '{current_img_host}'.")
                break

        uploaded_images, _ = await upload_screens(
            meta, multi_screens, img_host_index, 0, multi_screens,
            all_screenshots, {new_images_key: meta[new_images_key]}, retry_mode
        )
        if uploaded_images:
            meta[new_images_key] = uploaded_images

        if meta['debug']:
            console.print(f"[debug] Updated {new_images_key} with {len(uploaded_images)} images.")
            for image in uploaded_images:
                console.print(f"[debug] Response in upload_image_task: {image['img_url']}, {image['raw_url']}, {image['web_url']}")

        for image in meta.get(new_images_key, []):
            raw_url = image['raw_url']
            parsed_url = urlparse(raw_url)
            hostname = parsed_url.netloc
            mapped_host = await match_host(hostname, url_host_mapping.keys())
            mapped_host = url_host_mapping.get(mapped_host, mapped_host)

            if mapped_host not in approved_image_hosts:
                console.print(f"[red]Unsupported image host detected in URL '{raw_url}'. Please use one of the approved image hosts.")
                if original_imghost:
                    meta['imghost'] = original_imghost
                return meta[new_images_key], True, images_reuploaded  # Trigger retry_mode if switching hosts

        # Ensure all uploaded images are valid
        valid_hosts = []
        for image in meta[new_images_key]:
            netloc = urlparse(image['raw_url']).netloc
            matched_host = await match_host(netloc, url_host_mapping.keys())
            mapped_host = url_host_mapping.get(matched_host, matched_host)
            valid_hosts.append(mapped_host in approved_image_hosts)
        if all(valid_hosts) and new_images_key in meta and isinstance(meta[new_images_key], list):
            if tracker == "covers":
                output_file = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], "covers.json")
            else:
                output_file = os.path.join(screenshots_dir, "reuploaded_images.json")

            try:
                async with aiofiles.open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = await f.read()
                    existing_data = json.loads(existing_data) if existing_data else []
                    if not isinstance(existing_data, list):
                        console.print(f"[red]Existing data in {output_file} is not a list. Resetting to an empty list.")
                        existing_data = []
            except Exception:
                existing_data = []

            updated_data = existing_data + meta[new_images_key]
            updated_data = [dict(s) for s in {tuple(d.items()) for d in updated_data}]

            if tracker == "covers" and "release_url" in meta:
                for image in updated_data:
                    if "release_url" not in image:
                        image["release_url"] = meta["release_url"]
                console.print(f"[green]Added release URL to {len(updated_data)} cover images: {meta['release_url']}")

            try:
                async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(updated_data, indent=4))
                if meta['debug']:
                    console.print(f"[green]Successfully updated reuploaded images in {output_file}.")

                if tracker == "covers":
                    deleted_count = 0
                    for screenshot in all_screenshots:
                        try:
                            if os.path.exists(screenshot):
                                os.remove(screenshot)
                                deleted_count += 1
                                if meta.get('debug'):
                                    console.print(f"[dim]Deleted cover image file: {screenshot}[/dim]")
                        except Exception as e:
                            console.print(f"[yellow]Failed to delete cover image file {screenshot}: {str(e)}[/yellow]")

                    if deleted_count > 0:
                        if meta['debug']:
                            console.print(f"[green]Cleaned up {deleted_count} cover image files after successful upload[/green]")

            except Exception as e:
                console.print(f"[red]Failed to save reuploaded images: {e}")
        else:
            console.print("[red]new_images_key is not a valid key in meta or is not a list.")

        if original_imghost:
            meta['imghost'] = original_imghost
        return meta[new_images_key], False, images_reuploaded
    else:
        if original_imghost:
            meta['imghost'] = original_imghost
        return meta[new_images_key], False, images_reuploaded
