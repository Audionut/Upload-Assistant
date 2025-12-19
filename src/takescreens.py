# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
import glob
import time
import ffmpeg
import random
import json
import platform
import asyncio
import psutil
import sys
import gc
import traceback
from pymediainfo import MediaInfo
from src.console import console
from data.config import config
from src.cleanup import cleanup, reset_terminal

task_limit = int(config['DEFAULT'].get('process_limit', 1))
threads = str(config['DEFAULT'].get('threads', '1'))
cutoff = int(config['DEFAULT'].get('cutoff_screens', 1))
ffmpeg_limit = config['DEFAULT'].get('ffmpeg_limit', False)
ffmpeg_is_good = config['DEFAULT'].get('ffmpeg_is_good', False)
use_libplacebo = config['DEFAULT'].get('use_libplacebo', True)

try:
    task_limit = int(task_limit)  # Convert to integer
except ValueError:
    task_limit = 1
tone_map = config['DEFAULT'].get('tone_map', False)
ffmpeg_compression = str(config['DEFAULT'].get('ffmpeg_compression', '6'))
algorithm = config['DEFAULT'].get('algorithm', 'mobius').strip()
desat = float(config['DEFAULT'].get('desat', 10.0))


async def run_ffmpeg(command):
    if platform.system() == 'Linux':
        ffmpeg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bin', 'ffmpeg', 'ffmpeg')
        if os.path.exists(ffmpeg_path):
            cmd_list = command.compile()
            cmd_list[0] = ffmpeg_path

            process = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout, stderr

    process = await asyncio.create_subprocess_exec(
        *command.compile(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout, stderr


async def sanitize_filename(filename):
    # Replace invalid characters like colons with an underscore
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def disc_screenshots(meta, filename, bdinfo, folder_id, base_dir, use_vs, image_list, ffdebug, num_screens=None, force_screenshots=False):
    img_host = await get_image_host(meta)
    screens = meta['screens']
    if meta['debug']:
        start_time = time.time()
    if 'image_list' not in meta:
        meta['image_list'] = []
    existing_images = [img for img in meta['image_list'] if isinstance(img, dict) and img.get('img_url', '').startswith('http')]

    if len(existing_images) >= cutoff and not force_screenshots:
        console.print(f"[yellow]There are already at least {cutoff} images in the image list. Skipping additional screenshots.")
        return

    if num_screens is None:
        num_screens = screens
    if num_screens == 0 or len(image_list) >= num_screens:
        return

    sanitized_filename = await sanitize_filename(filename)
    length = 0
    file = None
    frame_rate = None
    for each in bdinfo['files']:
        # Calculate total length in seconds, including fractional part
        int_length = sum(float(x) * 60 ** i for i, x in enumerate(reversed(each['length'].split(':'))))

        if int_length > length:
            length = int_length
            for root, dirs, files in os.walk(bdinfo['path']):
                for name in files:
                    if name.lower() == each['file'].lower():
                        file = os.path.join(root, name)
                        break  # Stop searching once the file is found

    if 'video' in bdinfo and bdinfo['video']:
        fps_string = bdinfo['video'][0].get('fps', None)
        if fps_string:
            try:
                frame_rate = float(fps_string.split(' ')[0])  # Extract and convert to float
            except ValueError:
                console.print("[red]Error: Unable to parse frame rate from bdinfo['video'][0]['fps']")

    keyframe = 'nokey' if "VC-1" in bdinfo['video'][0]['codec'] or bdinfo['video'][0]['hdr_dv'] != "" else 'none'
    if meta['debug']:
        print(f"File: {file}, Length: {length}, Frame Rate: {frame_rate}")
    os.chdir(f"{base_dir}/tmp/{folder_id}")
    existing_screens = glob.glob(f"{sanitized_filename}-*.png")
    total_existing = len(existing_screens) + len(existing_images)
    if not force_screenshots:
        num_screens = max(0, screens - total_existing)
    else:
        num_screens = num_screens

    if num_screens == 0 and not force_screenshots:
        console.print('[bold green]Reusing existing screenshots. No additional screenshots needed.')
        return

    if meta['debug'] and not force_screenshots:
        console.print(f"[bold yellow]Saving Screens... Total needed: {screens}, Existing: {total_existing}, To capture: {num_screens}")

    if tone_map and "HDR" in meta['hdr']:
        hdr_tonemap = True
        meta['tonemapped'] = True
    else:
        hdr_tonemap = False

    ss_times = await valid_ss_time([], num_screens, length, frame_rate, meta, retake=force_screenshots)

    if meta.get('frame_overlay', False):
        console.print("[yellow]Getting frame information for overlays...")
        frame_info_tasks = [
            get_frame_info(file, ss_times[i], meta)
            for i in range(num_screens + 1)
            if not os.path.exists(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png")
            or meta.get('retake', False)
        ]
        frame_info_results = await asyncio.gather(*frame_info_tasks)
        meta['frame_info_map'] = {}

        # Create a mapping from time to frame info
        for i, info in enumerate(frame_info_results):
            meta['frame_info_map'][ss_times[i]] = info

        if meta['debug']:
            console.print(f"[cyan]Collected frame information for {len(frame_info_results)} frames")

    num_workers = min(num_screens, task_limit)

    if meta['debug']:
        console.print(f"Using {num_workers} worker(s) for {num_screens} image(s)")

    capture_tasks = []
    capture_results = []
    if use_vs:
        from src.vs import vs_screengn
        vs_screengn(source=file, encode=None, filter_b_frames=False, num=num_screens, dir=f"{base_dir}/tmp/{folder_id}/")
    else:
        if meta.get('ffdebug', False):
            loglevel = 'verbose'
        else:
            loglevel = 'quiet'

        existing_indices = {int(p.split('-')[-1].split('.')[0]) for p in existing_screens}

        # Create semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(task_limit)

        async def capture_disc_with_semaphore(*args):
            async with semaphore:
                return await capture_disc_task(*args)

        capture_tasks = [
            capture_disc_with_semaphore(
                i,
                file,
                ss_times[i],
                os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{len(existing_indices) + i}.png"),
                keyframe,
                loglevel,
                hdr_tonemap,
                meta
            )
            for i in range(num_screens + 1)
        ]

        results = await asyncio.gather(*capture_tasks)
        filtered_results = [r for r in results if isinstance(r, tuple) and len(r) == 2]

        if len(filtered_results) != len(results):
            console.print(f"[yellow]Warning: {len(results) - len(filtered_results)} capture tasks returned invalid results.")

        filtered_results.sort(key=lambda x: x[0])  # Ensure order is preserved
        capture_results = [r[1] for r in filtered_results if r[1] is not None]

        if capture_results and len(capture_results) > num_screens:
            try:
                smallest = min(capture_results, key=os.path.getsize)
                if meta['debug']:
                    console.print(f"[yellow]Removing smallest image: {smallest} ({os.path.getsize(smallest)} bytes)")
                os.remove(smallest)
                capture_results.remove(smallest)
            except Exception as e:
                console.print(f"[red]Error removing smallest image: {str(e)}")

        if not force_screenshots and meta['debug']:
            console.print(f"[green]Successfully captured {len(capture_results)} screenshots.")

        valid_results = []
        remaining_retakes = []
        for image_path in capture_results:
            if "Error" in image_path:
                console.print(f"[red]{image_path}")
                continue

            retake = False
            image_size = os.path.getsize(image_path)
            if meta['debug']:
                console.print(f"[yellow]Checking image {image_path} (size: {image_size} bytes) for image host: {img_host}[/yellow]")
            if image_size <= 75000:
                console.print(f"[yellow]Image {image_path} is incredibly small, retaking.")
                retake = True
            else:
                if "imgbb" in img_host:
                    if image_size <= 31000000:
                        if meta['debug']:
                            console.print(f"[green]Image {image_path} meets size requirements for imgbb.[/green]")
                    else:
                        console.print(f"[red]Image {image_path} with size {image_size} bytes: does not meet size requirements for imgbb, retaking.")
                        retake = True
                elif img_host in ["imgbox", "pixhost"]:
                    if 75000 < image_size <= 10000000:
                        if meta['debug']:
                            console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
                    else:
                        console.print(f"[red]Image {image_path} with size {image_size} bytes: does not meet size requirements for {img_host}, retaking.")
                        retake = True
                elif img_host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"]:
                    if meta['debug']:
                        console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
                else:
                    console.print(f"[red]Unknown image host or image doesn't meet requirements for host: {img_host}, retaking.")
                    retake = True

            if retake:
                retry_attempts = 3
                for attempt in range(1, retry_attempts + 1):
                    console.print(f"[yellow]Retaking screenshot for: {image_path} (Attempt {attempt}/{retry_attempts})[/yellow]")
                    try:
                        index = int(image_path.rsplit('-', 1)[-1].split('.')[0])
                        if os.path.exists(image_path):
                            os.remove(image_path)

                        random_time = random.uniform(0, length)
                        screenshot_response = await capture_disc_task(
                            index, file, random_time, image_path, keyframe, loglevel, hdr_tonemap, meta
                        )
                        new_size = os.path.getsize(screenshot_response)
                        valid_image = False

                        if "imgbb" in img_host:
                            if new_size > 75000 and new_size <= 31000000:
                                console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                valid_image = True
                        elif img_host in ["imgbox", "pixhost"]:
                            if new_size > 75000 and new_size <= 10000000:
                                console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                valid_image = True
                        elif img_host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"]:
                            if new_size > 75000:
                                console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                valid_image = True

                        if valid_image:
                            valid_results.append(screenshot_response)
                            break
                        else:
                            console.print(f"[red]Retaken image {screenshot_response} does not meet the size requirements for {img_host}. Retrying...[/red]")
                    except Exception as e:
                        console.print(f"[red]Error retaking screenshot for {image_path}: {e}[/red]")
                else:
                    console.print(f"[red]All retry attempts failed for {image_path}. Skipping.[/red]")
                    remaining_retakes.append(image_path)
            else:
                valid_results.append(image_path)

        if remaining_retakes:
            console.print(f"[red]The following images could not be retaken successfully: {remaining_retakes}[/red]")

    if not force_screenshots and meta['debug']:
        console.print(f"[green]Successfully captured {len(valid_results)} screenshots.")

    if meta['debug']:
        finish_time = time.time()
        console.print(f"Screenshots processed in {finish_time - start_time:.4f} seconds")

    multi_screens = int(config['DEFAULT'].get('multiScreens', 2))
    discs = meta.get('discs', [])
    one_disc = True
    if discs and len(discs) == 1:
        one_disc = True
    elif discs and len(discs) > 1:
        one_disc = False

    if (not meta.get('tv_pack') and one_disc) or multi_screens == 0:
        await cleanup()


async def capture_disc_task(index, file, ss_time, image_path, keyframe, loglevel, hdr_tonemap, meta):
    try:
        # Build filter chain
        vf_filters = []

        if hdr_tonemap:
            vf_filters.extend([
                "zscale=transfer=linear",
                f"tonemap=tonemap={algorithm}:desat={desat}",
                "zscale=transfer=bt709",
                "format=rgb24"
            ])

        if meta.get('frame_overlay', False):
            # Get frame info from pre-collected data if available
            frame_info = meta.get('frame_info_map', {}).get(ss_time, {})

            frame_rate = meta.get('frame_rate', 24.0)
            frame_number = int(ss_time * frame_rate)

            # If we have PTS time from frame info, use it to calculate a more accurate frame number
            if 'pts_time' in frame_info:
                # Only use PTS time for frame number calculation if it makes sense
                # (sometimes seeking can give us a frame from the beginning instead of where we want)
                pts_time = frame_info.get('pts_time', 0)
                if pts_time > 1.0 and abs(pts_time - ss_time) < 10:
                    frame_number = int(pts_time * frame_rate)

            frame_type = frame_info.get('frame_type', 'Unknown')

            text_size = int(config['DEFAULT'].get('overlay_text_size', 18))
            # Get the resolution and convert it to integer
            resol = int(''.join(filter(str.isdigit, meta.get('resolution', '1080p'))))
            font_size = round(text_size*resol/1080)
            x_all = round(10*resol/1080)

            # Scale vertical spacing based on font size
            line_spacing = round(font_size * 1.1)
            y_number = x_all
            y_type = y_number + line_spacing
            y_hdr = y_type + line_spacing

            # Frame number
            vf_filters.append(
                f"drawtext=text='Frame Number\\: {frame_number}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_number}:box=1:boxcolor=black@0.5"
            )

            # Frame type
            vf_filters.append(
                f"drawtext=text='Frame Type\\: {frame_type}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_type}:box=1:boxcolor=black@0.5"
            )

            # HDR status
            if hdr_tonemap:
                vf_filters.append(
                    f"drawtext=text='Tonemapped HDR':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_hdr}:box=1:boxcolor=black@0.5"
                )

        # Build command
        # Always ensure at least format filter is present for PNG compression to work
        if not vf_filters:
            vf_filters.append("format=rgb24")
        vf_chain = ",".join(vf_filters)

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", loglevel,
            "-hide_banner",
            "-ss", str(ss_time),
            "-skip_frame", keyframe,
            "-i", file,
            "-vframes", "1",
            "-vf", vf_chain,
            "-compression_level", ffmpeg_compression,
            "-pred", "mixed",
            image_path
        ]

        # Print the command for debugging
        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            console.print(f"[cyan]FFmpeg command: {' '.join(cmd)}[/cyan]")

        # Run command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode

        # Print stdout and stderr if in verbose mode
        if loglevel == 'verbose':
            if stdout:
                console.print(f"[blue]FFmpeg stdout:[/blue]\n{stdout.decode('utf-8', errors='replace')}")
            if stderr:
                console.print(f"[yellow]FFmpeg stderr:[/yellow]\n{stderr.decode('utf-8', errors='replace')}")

        if returncode == 0:
            return (index, image_path)
        else:
            console.print(f"[red]FFmpeg error capturing screenshot: {stderr.decode()}")
            return (index, None)  # Ensure tuple format
    except Exception as e:
        console.print(f"[red]Error capturing screenshot: {e}")
        return None


async def dvd_screenshots(meta, disc_num, num_screens=None, retry_cap=None):
    screens = meta['screens']
    if 'image_list' not in meta:
        meta['image_list'] = []
    existing_images = [img for img in meta['image_list'] if isinstance(img, dict) and img.get('img_url', '').startswith('http')]

    if len(existing_images) >= cutoff and not retry_cap:
        console.print(f"[yellow]There are already at least {cutoff} images in the image list. Skipping additional screenshots.")
        return
    screens = meta.get('screens', 6)
    if num_screens is None:
        num_screens = screens - len(existing_images)
    if num_screens == 0 or (len(meta.get('image_list', [])) >= screens and disc_num == 0):
        return

    if len(glob.glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][disc_num]['name']}-*.png")) >= num_screens:
        i = num_screens
        console.print('[bold green]Reusing screenshots')
        return

    ifo_mi = MediaInfo.parse(f"{meta['discs'][disc_num]['path']}/VTS_{meta['discs'][disc_num]['main_set'][0][:2]}_0.IFO", mediainfo_options={'inform_version': '1'})
    sar = 1
    for track in ifo_mi.tracks:
        if track.track_type == "Video":
            if isinstance(track.duration, str):
                durations = [float(d) for d in track.duration.split(' / ')]
                length = max(durations) / 1000  # Use the longest duration
            else:
                length = float(track.duration) / 1000  # noqa #F841 # Convert to seconds

            par = float(track.pixel_aspect_ratio)
            dar = float(track.display_aspect_ratio)
            width = float(track.width)
            height = float(track.height)
            frame_rate = float(track.frame_rate)
    if par < 1:
        new_height = dar * height
        sar = width / new_height
        w_sar = 1
        h_sar = sar
    else:
        sar = par
        w_sar = sar
        h_sar = 1

    async def _is_vob_good(n, loops, num_screens):
        max_loops = 6
        fallback_duration = 300
        valid_tracks = []

        while loops < max_loops:
            try:
                vob_mi = MediaInfo.parse(
                    f"{meta['discs'][disc_num]['path']}/VTS_{main_set[n]}",
                    output='JSON'
                )
                vob_mi = json.loads(vob_mi)

                for track in vob_mi.get('media', {}).get('track', []):
                    duration = float(track.get('Duration', 0))
                    width = track.get('Width')
                    height = track.get('Height')

                    if duration > 1 and width and height:  # Minimum 1-second track
                        valid_tracks.append({
                            'duration': duration,
                            'track_index': n
                        })

                if valid_tracks:
                    # Sort by duration, take longest track
                    longest_track = max(valid_tracks, key=lambda x: x['duration'])
                    return longest_track['duration'], longest_track['track_index']

            except Exception as e:
                console.print(f"[red]Error parsing VOB {n}: {e}")

            n = (n + 1) % len(main_set)
            loops += 1

        return fallback_duration, 0

    main_set = meta['discs'][disc_num]['main_set'][1:] if len(meta['discs'][disc_num]['main_set']) > 1 else meta['discs'][disc_num]['main_set']
    os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
    voblength, n = await _is_vob_good(0, 0, num_screens)
    ss_times = await valid_ss_time([], num_screens, voblength, frame_rate, meta, retake=retry_cap)
    capture_tasks = []
    existing_images = 0
    existing_image_paths = []

    for i in range(num_screens + 1):
        image = f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][disc_num]['name']}-{i}.png"
        input_file = f"{meta['discs'][disc_num]['path']}/VTS_{main_set[i % len(main_set)]}"
        if os.path.exists(image) and not meta.get('retake', False):
            existing_images += 1
            existing_image_paths.append(image)

    if existing_images == num_screens and not meta.get('retake', False):
        console.print("[yellow]The correct number of screenshots already exists. Skipping capture process.")
        capture_results = existing_image_paths
        return
    else:
        capture_tasks = []
        image_paths = []
        input_files = []

        for i in range(num_screens + 1):
            sanitized_disc_name = await sanitize_filename(meta['discs'][disc_num]['name'])
            image = f"{meta['base_dir']}/tmp/{meta['uuid']}/{sanitized_disc_name}-{i}.png"
            input_file = f"{meta['discs'][disc_num]['path']}/VTS_{main_set[i % len(main_set)]}"
            image_paths.append(image)
            input_files.append(input_file)

        if meta.get('frame_overlay', False):
            if meta['debug']:
                console.print("[yellow]Getting frame information for overlays...")
            frame_info_tasks = [
                get_frame_info(input_files[i], ss_times[i], meta)
                for i in range(num_screens + 1)
                if not os.path.exists(image_paths[i]) or meta.get('retake', False)
            ]

            frame_info_results = await asyncio.gather(*frame_info_tasks)
            meta['frame_info_map'] = {}

            for i, info in enumerate(frame_info_results):
                meta['frame_info_map'][ss_times[i]] = info

            if meta['debug']:
                console.print(f"[cyan]Collected frame information for {len(frame_info_results)} frames")

        num_workers = min(num_screens + 1, task_limit)

        if meta['debug']:
            console.print(f"Using {num_workers} worker(s) for {num_screens} image(s)")

        # Create semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(task_limit)

        async def capture_dvd_with_semaphore(args):
            async with semaphore:
                return await capture_dvd_screenshot(args)

        for i in range(num_screens + 1):
            if not os.path.exists(image_paths[i]) or meta.get('retake', False):
                capture_tasks.append(
                    capture_dvd_with_semaphore(
                        (i, input_files[i], image_paths[i], ss_times[i], meta, width, height, w_sar, h_sar)
                    )
                )

        capture_results = []
        results = await asyncio.gather(*capture_tasks)
        filtered_results = [r for r in results if isinstance(r, tuple) and len(r) == 2]

        if len(filtered_results) != len(results):
            console.print(f"[yellow]Warning: {len(results) - len(filtered_results)} capture tasks returned invalid results.")

        filtered_results.sort(key=lambda x: x[0])  # Ensure order is preserved
        capture_results = [r[1] for r in filtered_results if r[1] is not None]

        if capture_results and len(capture_results) > num_screens:
            smallest = None
            smallest_size = float('inf')
            for screens in glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}/", f"{meta['discs'][disc_num]['name']}-*"):
                screen_path = os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}/", screens)
                try:
                    screen_size = os.path.getsize(screen_path)
                    if screen_size < smallest_size:
                        smallest_size = screen_size
                        smallest = screen_path
                except FileNotFoundError:
                    console.print(f"[red]File not found: {screen_path}[/red]")  # Handle potential edge cases
                    continue

            if smallest:
                if meta['debug']:
                    console.print(f"[yellow]Removing smallest image: {smallest} ({smallest_size} bytes)[/yellow]")
                os.remove(smallest)
                capture_results.remove(smallest)

        valid_results = []
        remaining_retakes = []

        for image in capture_results:
            if "Error" in image:
                console.print(f"[red]{image}")
                continue

            retake = False
            image_size = os.path.getsize(image)
            if image_size <= 120000:
                console.print(f"[yellow]Image {image} is incredibly small, retaking.")
                retake = True

            if retake:
                retry_attempts = 3
                for attempt in range(1, retry_attempts + 1):
                    console.print(f"[yellow]Retaking screenshot for: {image} (Attempt {attempt}/{retry_attempts})[/yellow]")

                    index = int(image.rsplit('-', 1)[-1].split('.')[0])
                    input_file = f"{meta['discs'][disc_num]['path']}/VTS_{main_set[index % len(main_set)]}"
                    adjusted_time = random.uniform(0, voblength)

                    if os.path.exists(image):  # Prevent unnecessary deletion error
                        try:
                            os.remove(image)
                        except Exception as e:
                            console.print(f"[red]Failed to delete {image}: {e}[/red]")
                            break

                    try:
                        # Ensure `capture_dvd_screenshot()` always returns a tuple
                        screenshot_response = await capture_dvd_screenshot(
                            (index, input_file, image, adjusted_time, meta, width, height, w_sar, h_sar)
                        )

                        # Ensure it is a tuple before unpacking
                        if not isinstance(screenshot_response, tuple) or len(screenshot_response) != 2:
                            console.print(f"[red]Failed to capture screenshot for {image}. Retrying...[/red]")
                            continue

                        index, screenshot_result = screenshot_response  # Safe unpacking

                        if screenshot_result is None:
                            console.print(f"[red]Failed to capture screenshot for {image}. Retrying...[/red]")
                            continue

                        retaken_size = os.path.getsize(screenshot_result)
                        if retaken_size > 75000:
                            console.print(f"[green]Successfully retaken screenshot for: {screenshot_result} ({retaken_size} bytes)[/green]")
                            valid_results.append(screenshot_result)
                            break
                        else:
                            console.print(f"[red]Retaken image {screenshot_result} is still too small. Retrying...[/red]")
                    except Exception as e:
                        console.print(f"[red]Error capturing screenshot for {input_file} at {adjusted_time}: {e}[/red]")

                else:
                    console.print(f"[red]All retry attempts failed for {image}. Skipping.[/red]")
                    remaining_retakes.append(image)
            else:
                valid_results.append(image)
        if remaining_retakes:
            console.print(f"[red]The following images could not be retaken successfully: {remaining_retakes}[/red]")

    if not retry_cap and meta['debug']:
        console.print(f"[green]Successfully captured {len(valid_results)} screenshots.")

    multi_screens = int(config['DEFAULT'].get('multiScreens', 2))
    discs = meta.get('discs', [])
    one_disc = True
    if discs and len(discs) == 1:
        one_disc = True
    elif discs and len(discs) > 1:
        one_disc = False

    if (not meta.get('tv_pack') and one_disc) or multi_screens == 0:
        await cleanup()


async def capture_dvd_screenshot(task):
    index, input_file, image, seek_time, meta, width, height, w_sar, h_sar = task

    try:
        loglevel = 'verbose' if meta.get('ffdebug', False) else 'quiet'
        media_info = MediaInfo.parse(input_file)
        video_duration = next((track.duration for track in media_info.tracks if track.track_type == "Video"), None)

        if video_duration and seek_time > video_duration:
            seek_time = max(0, video_duration - 1)

        # Build filter chain
        vf_filters = []
        if w_sar != 1 or h_sar != 1:
            scaled_w = int(round(width * w_sar))
            scaled_h = int(round(height * h_sar))
            vf_filters.append(f"scale={scaled_w}:{scaled_h}")

        if meta.get('frame_overlay', False):
            # Get frame info from pre-collected data if available
            frame_info = meta.get('frame_info_map', {}).get(seek_time, {})

            frame_rate = meta.get('frame_rate', 24.0)
            frame_number = int(seek_time * frame_rate)

            # If we have PTS time from frame info, use it to calculate a more accurate frame number
            if 'pts_time' in frame_info:
                # Only use PTS time for frame number calculation if it makes sense
                # (sometimes seeking can give us a frame from the beginning instead of where we want)
                pts_time = frame_info.get('pts_time', 0)
                if pts_time > 1.0 and abs(pts_time - seek_time) < 10:
                    frame_number = int(pts_time * frame_rate)

            frame_type = frame_info.get('frame_type', 'Unknown')

            text_size = int(config['DEFAULT'].get('overlay_text_size', 18))
            # Get the resolution and convert it to integer
            resol = int(''.join(filter(str.isdigit, meta.get('resolution', '576p'))))
            font_size = round(text_size*resol/576)
            x_all = round(10*resol/576)

            # Scale vertical spacing based on font size
            line_spacing = round(font_size * 1.1)
            y_number = x_all
            y_type = y_number + line_spacing

            # Frame number
            vf_filters.append(
                f"drawtext=text='Frame Number\\: {frame_number}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_number}:box=1:boxcolor=black@0.5"
            )

            # Frame type
            vf_filters.append(
                f"drawtext=text='Frame Type\\: {frame_type}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_type}:box=1:boxcolor=black@0.5"
            )

        # Build command
        # Always ensure at least format filter is present for PNG compression to work
        if not vf_filters:
            vf_filters.append("format=rgb24")
        vf_chain = ",".join(vf_filters)

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", loglevel,
            "-hide_banner",
            "-ss", str(seek_time),
            "-accurate_seek",
            "-i", input_file,
            "-vframes", "1",
            "-vf", vf_chain,
            "-compression_level", ffmpeg_compression,
            "-pred", "mixed",
            image
        ]

        # Print the command for debugging
        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            console.print(f"[cyan]FFmpeg command: {' '.join(cmd)}[/cyan]", emoji=False)

        # Run command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode

        if returncode != 0:
            console.print(f"[red]Error capturing screenshot for {input_file} at {seek_time}s:[/red]\n{stderr.decode()}")
            return (index, None)

        if os.path.exists(image):
            return (index, image)
        else:
            console.print(f"[red]Screenshot creation failed for {image}[/red]")
            return (index, None)

    except Exception as e:
        console.print(f"[red]Error capturing screenshot for {input_file} at {seek_time}s: {e}[/red]")
        return (index, None)


async def screenshots(path, filename, folder_id, base_dir, meta, num_screens=None, force_screenshots=False, manual_frames=None):
    img_host = await get_image_host(meta)
    screens = meta['screens']
    if meta['debug']:
        start_time = time.time()
        console.print("Image Host:", img_host)
    if 'image_list' not in meta:
        meta['image_list'] = []

    existing_images = [img for img in meta['image_list'] if isinstance(img, dict) and img.get('img_url', '').startswith('http')]

    if len(existing_images) >= cutoff and not force_screenshots:
        console.print(f"[yellow]There are already at least {cutoff} images in the image list. Skipping additional screenshots.")
        return

    try:
        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", encoding='utf-8') as f:
            mi = json.load(f)
            video_track = mi['media']['track'][1]

            def safe_float(value, default=0.0, field_name=""):
                if isinstance(value, (int, float)):
                    return float(value)
                elif isinstance(value, str):
                    try:
                        return float(value)
                    except ValueError:
                        console.print(f"[yellow]Warning: Could not convert string '{value}' to float for {field_name}, using default {default}[/yellow]")
                        return default
                elif isinstance(value, dict):
                    for key in ['#value', 'value', 'duration', 'Duration']:
                        if key in value:
                            return safe_float(value[key], default, field_name)
                    console.print(f"[yellow]Warning: {field_name} is a dict but no usable value found: {value}, using default {default}[/yellow]")
                    return default
                else:
                    console.print(f"[yellow]Warning: Unable to convert to float: {type(value)} {value} for {field_name}, using default {default}[/yellow]")
                    return default

            length = safe_float(
                video_track.get('Duration'),
                safe_float(mi['media']['track'][0].get('Duration'), 3600.0, "General Duration"),
                "Video Duration"
            )

            width = safe_float(video_track.get('Width'), 1920.0, "Width")
            height = safe_float(video_track.get('Height'), 1080.0, "Height")
            par = safe_float(video_track.get('PixelAspectRatio'), 1.0, "PixelAspectRatio")
            dar = safe_float(video_track.get('DisplayAspectRatio'), 16.0/9.0, "DisplayAspectRatio")
            frame_rate = safe_float(video_track.get('FrameRate'), 24.0, "FrameRate")

            if par == 1:
                sar = w_sar = h_sar = 1
            elif par < 1:
                new_height = dar * height
                sar = width / new_height
                w_sar = 1
                h_sar = sar
            else:
                sar = w_sar = par
                h_sar = 1
    except Exception as e:
        console.print(f"[red]Error processing MediaInfo.json: {e}")
        if meta.get('debug', False):
            import traceback
            console.print(traceback.format_exc())
        return
    meta['frame_rate'] = frame_rate
    loglevel = 'verbose' if meta.get('ffdebug', False) else 'quiet'
    os.chdir(f"{base_dir}/tmp/{folder_id}")

    if manual_frames and meta['debug']:
        console.print(f"[yellow]Using manual frames: {manual_frames}")
    ss_times = []
    if manual_frames and not force_screenshots:
        try:
            if isinstance(manual_frames, str):
                manual_frames_list = [int(frame.strip()) for frame in manual_frames.split(',') if frame.strip()]
            elif isinstance(manual_frames, list):
                manual_frames_list = [int(frame) if isinstance(frame, str) else frame for frame in manual_frames]
            else:
                manual_frames_list = []
            num_screens = len(manual_frames_list)
            if num_screens > 0:
                ss_times = [frame / frame_rate for frame in manual_frames_list]
        except (TypeError, ValueError) as e:
            if meta['debug'] and manual_frames:
                console.print(f"[red]Error processing manual frames: {e}[/red]")
                sys.exit(1)

    if num_screens is None or num_screens <= 0:
        num_screens = screens - len(existing_images)
    if num_screens <= 0:
        return

    sanitized_filename = await sanitize_filename(filename)

    existing_images_count = 0
    existing_image_paths = []
    for i in range(num_screens):
        image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png")
        if os.path.exists(image_path) and not meta.get('retake', False):
            existing_images_count += 1
            existing_image_paths.append(image_path)

    if existing_images_count == num_screens and not meta.get('retake', False):
        console.print("[yellow]The correct number of screenshots already exists. Skipping capture process.")
        return existing_image_paths

    num_capture = num_screens - existing_images_count

    if not ss_times:
        ss_times = await valid_ss_time([], num_capture, length, frame_rate, meta, retake=force_screenshots)

    if meta.get('frame_overlay', False):
        if meta['debug']:
            console.print("[yellow]Getting frame information for overlays...")
        frame_info_tasks = [
            get_frame_info(path, ss_times[i], meta)
            for i in range(num_capture)
            if not os.path.exists(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png")
            or meta.get('retake', False)
        ]
        frame_info_results = await asyncio.gather(*frame_info_tasks)
        meta['frame_info_map'] = {}

        # Create a mapping from time to frame info
        for i, info in enumerate(frame_info_results):
            meta['frame_info_map'][ss_times[i]] = info

        if meta['debug']:
            console.print(f"[cyan]Collected frame information for {len(frame_info_results)} frames")

    num_tasks = num_capture
    num_workers = min(num_tasks, task_limit)

    meta['libplacebo'] = False
    if tone_map and ("HDR" in meta['hdr'] or "DV" in meta['hdr'] or "HLG" in meta['hdr']):
        if use_libplacebo and not meta.get('frame_overlay', False):
            if not ffmpeg_is_good:
                test_time = ss_times[0] if ss_times else 0
                test_image = image_path if isinstance(image_path, str) else (
                    image_path[0] if isinstance(image_path, list) and image_path else None
                )
                libplacebo, compatible = await check_libplacebo_compatibility(
                    w_sar, h_sar, width, height, path, test_time, test_image, loglevel, meta
                )
                if compatible:
                    hdr_tonemap = True
                    meta['tonemapped'] = True
                if libplacebo:
                    hdr_tonemap = True
                    meta['tonemapped'] = True
                    meta['libplacebo'] = True
                if not compatible and not libplacebo:
                    hdr_tonemap = False
                    console.print("[yellow]FFMPEG failed tonemap checking.[/yellow]")
                    await asyncio.sleep(2)
                if not libplacebo and "HDR" not in meta.get('hdr'):
                    hdr_tonemap = False
            else:
                hdr_tonemap = True
                meta['tonemapped'] = True
                meta['libplacebo'] = True
        else:
            if "HDR" not in meta.get('hdr'):
                hdr_tonemap = False
            else:
                hdr_tonemap = True
                meta['tonemapped'] = True
    else:
        hdr_tonemap = False

    if meta['debug']:
        console.print(f"Using {num_workers} worker(s) for {num_capture} image(s)")

    # Create semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(num_workers)

    async def capture_with_semaphore(args):
        async with semaphore:
            return await capture_screenshot(args)

    capture_tasks = []
    for i in range(num_capture):
        image_index = existing_images_count + i
        image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{image_index}.png")
        if not os.path.exists(image_path) or meta.get('retake', False):
            capture_tasks.append(
                capture_with_semaphore(
                    (i, path, ss_times[i], image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta)
                )
            )

    try:
        results = await asyncio.gather(*capture_tasks, return_exceptions=True)
        capture_results = [r for r in results if isinstance(r, tuple) and len(r) == 2]
        capture_results.sort(key=lambda x: x[0])
        capture_results = [r[1] for r in capture_results if r[1] is not None]

    except KeyboardInterrupt:
        console.print("\n[red]CTRL+C detected. Cancelling capture tasks...[/red]")
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        console.print("[red]All tasks cancelled. Exiting.[/red]")
        gc.collect()
        reset_terminal()
        sys.exit(1)
    except asyncio.CancelledError:
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        gc.collect()
        reset_terminal()
        sys.exit(1)
    except Exception:
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        gc.collect()
        reset_terminal()
        sys.exit(1)
    finally:
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        if meta['debug']:
            console.print("[yellow]All capture tasks finished. Cleaning up...[/yellow]")

    if not force_screenshots and meta['debug']:
        console.print(f"[green]Successfully captured {len(capture_results)} screenshots.")

    valid_results = []
    remaining_retakes = []
    for image_path in capture_results:
        if "Error" in image_path:
            console.print(f"[red]{image_path}")
            continue

        retake = False
        image_size = os.path.getsize(image_path)
        if meta['debug']:
            console.print(f"[yellow]Checking image {image_path} (size: {image_size} bytes) for image host: {img_host}[/yellow]")
        if not manual_frames:
            if image_size <= 75000:
                console.print(f"[yellow]Image {image_path} is incredibly small, retaking.")
                retake = True
            else:
                if "imgbb" in img_host:
                    if image_size <= 31000000:
                        if meta['debug']:
                            console.print(f"[green]Image {image_path} meets size requirements for imgbb.[/green]")
                    else:
                        console.print(f"[red]Image {image_path} with size {image_size} bytes: does not meet size requirements for imgbb, retaking.")
                        retake = True
                elif img_host in ["imgbox", "pixhost"]:
                    if 75000 < image_size <= 10000000:
                        if meta['debug']:
                            console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
                    else:
                        console.print(f"[red]Image {image_path} with size {image_size} bytes: does not meet size requirements for {img_host}, retaking.")
                        retake = True
                elif img_host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"]:
                    if meta['debug']:
                        console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
                else:
                    console.print(f"[red]Unknown image host or image doesn't meet requirements for host: {img_host}, retaking.")
                    retake = True

        if retake:
            retry_attempts = 5
            retry_offsets = [5.0, 10.0, -10.0, 100.0, -100.0]
            frame_rate = meta.get('frame_rate', 24.0)
            original_index = int(image_path.rsplit('-', 1)[-1].split('.')[0])
            original_time = ss_times[original_index] if 'ss_times' in locals() and original_index < len(ss_times) else None

            for attempt in range(1, retry_attempts + 1):
                if original_time is not None:
                    for offset in retry_offsets:
                        adjusted_time = max(0, original_time + offset)
                        console.print(f"[yellow]Retaking screenshot for: {image_path} (Attempt {attempt}/{retry_attempts}) at {adjusted_time:.2f}s (offset {offset:+.2f}s)[/yellow]")
                        try:
                            if os.path.exists(image_path):
                                os.remove(image_path)

                            screenshot_response = await capture_screenshot((
                                original_index, path, adjusted_time, image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta
                            ))

                            if not isinstance(screenshot_response, tuple) or len(screenshot_response) != 2:
                                continue

                            _, screenshot_path = screenshot_response

                            if not screenshot_path or not os.path.exists(screenshot_path):
                                continue

                            new_size = os.path.getsize(screenshot_path)
                            valid_image = False

                            if "imgbb" in img_host:
                                if 75000 < new_size <= 31000000:
                                    console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                    valid_image = True
                            elif img_host in ["imgbox", "pixhost"]:
                                if 75000 < new_size <= 10000000:
                                    console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                    valid_image = True
                            elif img_host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"]:
                                if new_size > 75000:
                                    console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                    valid_image = True

                            if valid_image:
                                valid_results.append(screenshot_response)
                                break
                        except Exception as e:
                            console.print(f"[red]Error retaking screenshot for {image_path} at {adjusted_time:.2f}s: {e}[/red]")
                    else:
                        continue
                    break
                else:
                    # Fallback: use random time if original_time is not available
                    random_time = random.uniform(0, length)
                    console.print(f"[yellow]Retaking screenshot for: {image_path} (Attempt {attempt}/{retry_attempts}) at random time {random_time:.2f}s[/yellow]")
                    try:
                        if os.path.exists(image_path):
                            os.remove(image_path)

                        screenshot_response = await capture_screenshot((
                            original_index, path, random_time, image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta
                        ))

                        if not isinstance(screenshot_response, tuple) or len(screenshot_response) != 2:
                            continue

                        _, screenshot_path = screenshot_response

                        if not screenshot_path or not os.path.exists(screenshot_path):
                            continue

                        new_size = os.path.getsize(screenshot_path)
                        valid_image = False

                        if "imgbb" in img_host:
                            if 75000 < new_size <= 31000000:
                                valid_image = True
                        elif img_host in ["imgbox", "pixhost"]:
                            if 75000 < new_size <= 10000000:
                                valid_image = True
                        elif img_host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"]:
                            if new_size > 75000:
                                valid_image = True

                        if valid_image:
                            valid_results.append(screenshot_response)
                            break
                    except Exception as e:
                        console.print(f"[red]Error retaking screenshot for {image_path} at random time {random_time:.2f}s: {e}[/red]")
            else:
                console.print(f"[red]All retry attempts failed for {image_path}. Skipping.[/red]")
                remaining_retakes.append(image_path)
                gc.collect()

        else:
            valid_results.append(image_path)

    if remaining_retakes:
        console.print(f"[red]The following images could not be retaken successfully: {remaining_retakes}[/red]")

    if meta['debug']:
        console.print(f"[green]Successfully processed {len(valid_results)} screenshots.")

    if meta['debug']:
        finish_time = time.time()
        console.print(f"Screenshots processed in {finish_time - start_time:.4f} seconds")

    multi_screens = int(config['DEFAULT'].get('multiScreens', 2))
    discs = meta.get('discs', [])
    one_disc = True
    if discs and len(discs) == 1:
        one_disc = True
    elif discs and len(discs) > 1:
        one_disc = False

    if (not meta.get('tv_pack') and one_disc) or multi_screens == 0:
        await cleanup()


async def capture_screenshot(args):
    index, path, ss_time, image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta = args

    try:
        def set_ffmpeg_threads():
            threads_value = '1'
            os.environ['FFREPORT'] = 'level=32'  # Reduce ffmpeg logging overhead
            return ['-threads', threads_value]
        if width <= 0 or height <= 0:
            return "Error: Invalid width or height for scaling"

        if ss_time < 0:
            return f"Error: Invalid timestamp {ss_time}"

        # Normalize path for cross-platform compatibility
        path = os.path.normpath(path)

        # If path is a directory and meta has a filelist, use the first file from the filelist
        if os.path.isdir(path):
            error_msg = f"Error: Path is a directory, not a file: {path}"
            console.print(f"[yellow]{error_msg}[/yellow]")

            # Use meta that's passed directly to the function
            if meta and isinstance(meta, dict) and 'filelist' in meta and meta['filelist']:
                video_file = meta['filelist'][0]
                console.print(f"[green]Using first file from filelist: {video_file}[/green]")
                path = video_file
            else:
                return error_msg

        # After potential path correction, validate again
        if not os.path.exists(path):
            error_msg = f"Error: Input file does not exist: {path}"
            console.print(f"[red]{error_msg}[/red]")
            return error_msg

        # Debug output showing the exact path being used
        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            console.print(f"[cyan]Processing file: {path}[/cyan]")

        if not meta.get('frame_overlay', False):
            # Warm-up (only for first screenshot index or if not warmed)
            if use_libplacebo:
                warm_up = config['DEFAULT'].get('ffmpeg_warmup', False)
                if warm_up:
                    meta['_libplacebo_warmed'] = False
                else:
                    meta['_libplacebo_warmed'] = True
                if "_libplacebo_warmed" not in meta:
                    meta['_libplacebo_warmed'] = False
                if hdr_tonemap and meta.get('libplacebo') and not meta.get('_libplacebo_warmed'):
                    await libplacebo_warmup(path, meta, loglevel)

            threads_value = set_ffmpeg_threads()
            threads_val = threads_value[1]
            vf_filters = []

            if w_sar != 1 or h_sar != 1:
                scaled_w = int(round(width * w_sar))
                scaled_h = int(round(height * h_sar))
                vf_filters.append(f"scale={scaled_w}:{scaled_h}")
                if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                    console.print(f"[cyan]Applied PAR scale -> {scaled_w}x{scaled_h}[/cyan]")

            if hdr_tonemap:
                if meta.get('libplacebo', False):
                    vf_filters.append(
                        "libplacebo=tonemapping=hable:colorspace=bt709:"
                        "color_primaries=bt709:color_trc=bt709:range=tv"
                    )
                    if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                        console.print("[cyan]Using libplacebo tonemapping[/cyan]")
                else:
                    vf_filters.extend([
                        "zscale=transfer=linear",
                        f"tonemap=tonemap={algorithm}:desat={desat}",
                        "zscale=transfer=bt709"
                    ])
                    if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                        console.print(f"[cyan]Using zscale tonemap chain (algo={algorithm}, desat={desat})[/cyan]")

            vf_filters.append("format=rgb24")
            vf_chain = ",".join(vf_filters) if vf_filters else "format=rgb24"

            if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                console.print(f"[cyan]Final -vf chain: {vf_chain}[/cyan]")

            threads_value = ['-threads', '1']
            threads_val = threads_value[1]

            def build_cmd(use_libplacebo=True):
                cmd_local = [
                    "ffmpeg",
                    "-y",
                    "-ss", str(ss_time),
                    "-i", path,
                    "-map", "0:v:0",
                    "-an",
                    "-sn",
                ]
                if use_libplacebo and meta.get('libplacebo', False):
                    cmd_local += ["-init_hw_device", "vulkan"]
                cmd_local += [
                    "-vframes", "1",
                    "-vf", vf_chain,
                    "-compression_level", ffmpeg_compression,
                    "-pred", "mixed",
                    "-loglevel", loglevel,
                ]
                if ffmpeg_limit:
                    cmd_local += ["-threads", threads_val]
                cmd_local.append(image_path)
                return cmd_local

            cmd = build_cmd(use_libplacebo=True)

            if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                # Disable emoji translation so 0:v:0 stays literal
                console.print(f"[cyan]FFmpeg command: {' '.join(cmd)}[/cyan]", emoji=False)

            # --- Execute with retry/fallback if libplacebo fails ---
            async def run_cmd(run_cmd_list, timeout_sec):
                proc = await asyncio.create_subprocess_exec(
                    *run_cmd_list,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
                except asyncio.TimeoutError:
                    proc.kill()
                    try:
                        await proc.wait()
                    except Exception:
                        pass
                    return -1, b"", b"Timeout"
                return proc.returncode, stdout, stderr

            returncode, stdout, stderr = await run_cmd(cmd, 140)  # a bit longer for first pass
            if returncode != 0 and hdr_tonemap and meta.get('libplacebo'):
                # Retry once (shader compile might have delayed first invocation)
                if loglevel == 'verbose' or meta.get('debug', False):
                    console.print("[yellow]First libplacebo attempt failed; retrying once...[/yellow]")
                await asyncio.sleep(1.0)
                returncode, stdout, stderr = await run_cmd(cmd, 160)

            if returncode != 0 and hdr_tonemap and meta.get('libplacebo'):
                # Fallback: switch to zscale tonemap chain
                if loglevel == 'verbose' or meta.get('debug', False):
                    console.print("[red]libplacebo failed twice; falling back to zscale tonemap[/red]")
                meta['libplacebo'] = False
                # Rebuild chain with zscale
                z_vf_filters = []
                if w_sar != 1 or h_sar != 1:
                    z_vf_filters.append(f"scale={scaled_w}:{scaled_h}")
                z_vf_filters.extend([
                    "zscale=transfer=linear",
                    f"tonemap=tonemap={algorithm}:desat={desat}",
                    "zscale=transfer=bt709",
                    "format=rgb24"
                ])
                vf_chain = ",".join(z_vf_filters)
                fallback_cmd = build_cmd(use_libplacebo=False)
                # Replace the -vf argument with new chain
                for i, tok in enumerate(fallback_cmd):
                    if tok == "-vf":
                        fallback_cmd[i+1] = vf_chain
                        break
                if loglevel == 'verbose' or meta.get('debug', False):
                    console.print(f"[cyan]Fallback FFmpeg command: {' '.join(fallback_cmd)}[/cyan]", emoji=False)
                returncode, stdout, stderr = await run_cmd(fallback_cmd, 140)
                cmd = fallback_cmd  # for logging below

            if returncode == 0 and os.path.exists(image_path):
                if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                    console.print(f"[green]Screenshot captured successfully: {image_path}[/green]")
                return (index, image_path)
            else:
                if loglevel == 'verbose' or (meta and meta.get('debug', False)):
                    err_txt = (stderr or b"").decode(errors='replace').strip()
                    console.print(f"[red]FFmpeg process failed (final): {err_txt}[/red]")
                return (index, None)

        # Proceed with screenshot capture
        threads_value = set_ffmpeg_threads()
        threads_val = threads_value[1]

        # Build filter chain
        vf_filters = []

        if w_sar != 1 or h_sar != 1:
            scaled_w = int(round(width * w_sar))
            scaled_h = int(round(height * h_sar))
            vf_filters.append(f"scale={scaled_w}:{scaled_h}")

        if hdr_tonemap:
            vf_filters.extend([
                "zscale=transfer=linear",
                f"tonemap=tonemap={algorithm}:desat={desat}",
                "zscale=transfer=bt709",
                "format=rgb24"
            ])

        if meta.get('frame_overlay', False):
            # Get frame info from pre-collected data if available
            frame_info = meta.get('frame_info_map', {}).get(ss_time, {})

            frame_rate = meta.get('frame_rate', 24.0)
            frame_number = int(ss_time * frame_rate)

            # If we have PTS time from frame info, use it to calculate a more accurate frame number
            if 'pts_time' in frame_info:
                # Only use PTS time for frame number calculation if it makes sense
                # (sometimes seeking can give us a frame from the beginning instead of where we want)
                pts_time = frame_info.get('pts_time', 0)
                if pts_time > 1.0 and abs(pts_time - ss_time) < 10:
                    frame_number = int(pts_time * frame_rate)

            frame_type = frame_info.get('frame_type', 'Unknown')

            text_size = int(config['DEFAULT'].get('overlay_text_size', 18))
            # Get the resolution and convert it to integer
            resol = int(''.join(filter(str.isdigit, meta.get('resolution', '1080p'))))
            font_size = round(text_size*resol/1080)
            x_all = round(10*resol/1080)

            # Scale vertical spacing based on font size
            line_spacing = round(font_size * 1.1)
            y_number = x_all
            y_type = y_number + line_spacing
            y_hdr = y_type + line_spacing

            # Frame number
            vf_filters.append(
                f"drawtext=text='Frame Number\\: {frame_number}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_number}:box=1:boxcolor=black@0.5"
            )

            # Frame type
            vf_filters.append(
                f"drawtext=text='Frame Type\\: {frame_type}':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_type}:box=1:boxcolor=black@0.5"
            )

            # HDR status
            if hdr_tonemap:
                vf_filters.append(
                    f"drawtext=text='Tonemapped HDR':fontcolor=white:fontsize={font_size}:x={x_all}:y={y_hdr}:box=1:boxcolor=black@0.5"
                )

        # Build command
        # Always ensure at least format filter is present for PNG compression to work
        vf_filters.append("format=rgb24")
        vf_chain = ",".join(vf_filters)

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", loglevel,
            "-hide_banner",
            "-ss", str(ss_time),
            "-i", path,
            "-vframes", "1",
            "-vf", vf_chain,
            "-compression_level", ffmpeg_compression,
            "-pred", "mixed",
            image_path
        ]

        if ffmpeg_limit:
            # Insert threads before compression options
            cmd.insert(-3, "-threads")
            cmd.insert(-3, threads_val)

        # Print the command for debugging
        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            console.print(f"[cyan]FFmpeg command: {' '.join(cmd)}[/cyan]")

        try:
            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            returncode = process.returncode

            # Print stdout and stderr if in verbose mode
            if loglevel == 'verbose':
                if stdout:
                    console.print(f"[blue]FFmpeg stdout:[/blue]\n{stdout.decode('utf-8', errors='replace')}")
                if stderr:
                    console.print(f"[yellow]FFmpeg stderr:[/yellow]\n{stderr.decode('utf-8', errors='replace')}")

        except asyncio.CancelledError:
            console.print(traceback.format_exc())
            raise

        if returncode == 0:
            return (index, image_path)
        else:
            stderr_text = stderr.decode('utf-8', errors='replace')
            if "Error initializing complex filters" in stderr_text:
                console.print("[red]FFmpeg complex filters error: see https://github.com/Audionut/Upload-Assistant/wiki/ffmpeg---max-workers-issues[/red]")
            else:
                console.print(f"[red]FFmpeg error capturing screenshot: {stderr_text}[/red]")
            return (index, None)
    except Exception as e:
        console.print(traceback.format_exc())
        return f"Error: {str(e)}"


async def valid_ss_time(ss_times, num_screens, length, frame_rate, meta, retake=False):
    if meta['is_disc']:
        total_screens = num_screens + 1
    else:
        total_screens = num_screens
    total_frames = int(length * frame_rate)

    # Track retake calls and adjust start frame accordingly
    retake_offset = 0
    if retake and meta is not None:
        if 'retake_call_count' not in meta:
            meta['retake_call_count'] = 0

        meta['retake_call_count'] += 1
        retake_offset = meta['retake_call_count'] * 0.01

        if meta['debug']:
            console.print(f"[cyan]Retake call #{meta['retake_call_count']}, adding {retake_offset:.1%} offset[/cyan]")

    # Calculate usable portion (from 1% to 90% of video)
    if meta['category'] == "TV" and retake:
        start_frame = int(total_frames * (0.1 + retake_offset))
        end_frame = int(total_frames * 0.9)
    elif meta['category'] == "Movie" and retake:
        start_frame = int(total_frames * (0.05 + retake_offset))
        end_frame = int(total_frames * 0.9)
    else:
        start_frame = int(total_frames * (0.05 + retake_offset))
        end_frame = int(total_frames * 0.9)

    # Ensure start_frame doesn't exceed reasonable bounds
    max_start_frame = int(total_frames * 0.4)  # Don't start beyond 40%
    start_frame = min(start_frame, max_start_frame)

    usable_frames = end_frame - start_frame
    chosen_frames = []

    if total_screens > 1:
        frame_interval = usable_frames // total_screens
    else:
        frame_interval = usable_frames

    result_times = ss_times.copy()

    for i in range(total_screens):
        frame = start_frame + (i * frame_interval)
        chosen_frames.append(frame)
        time = frame / frame_rate
        result_times.append(time)

    if meta['debug']:
        console.print(f"[purple]Screenshots information:[/purple] \n[slate_blue3]Screenshots: [gold3]{total_screens}[/gold3] \nTotal Frames: [gold3]{total_frames}[/gold3]")
        console.print(f"[slate_blue3]Start frame: [gold3]{start_frame}[/gold3] \nEnd frame: [gold3]{end_frame}[/gold3] \nUsable frames: [gold3]{usable_frames}[/gold3][/slate_blue3]")
        console.print(f"[yellow]frame interval: {frame_interval} \n[purple]Chosen Frames[/purple]\n[gold3]{chosen_frames}[/gold3]\n")

    result_times = sorted(result_times)
    return result_times


async def kill_all_child_processes():
    """Ensures all child processes are terminated."""
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)  # Get child processes once

        for child in children:
            console.print(f"[red]Killing stuck worker process: {child.pid}[/red]")
            child.terminate()

        gone, still_alive = psutil.wait_procs(children, timeout=3)  # Wait for termination
        for process in still_alive:
            console.print(f"[red]Force killing stubborn process: {process.pid}[/red]")
            process.kill()
    except (psutil.AccessDenied, PermissionError) as e:
        # Handle restricted environments like Termux/Android where /proc/stat is inaccessible
        console.print(f"[yellow]Warning: Unable to access process information (restricted environment): {e}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Warning: Error during child process cleanup: {e}[/yellow]")


async def get_frame_info(path, ss_time, meta):
    """Get frame information (type, exact timestamp) for a specific frame"""
    try:
        info_ff = ffmpeg.input(path, ss=ss_time)
        # Use video stream selector and apply showinfo filter
        filtered = info_ff['v:0'].filter('showinfo')
        info_command = (
            filtered
            .output('-', format='null', vframes=1)
            .global_args('-loglevel', 'info')
        )

        # Print the actual FFmpeg command for debugging
        cmd = info_command.compile()
        if meta.get('debug', False):
            console.print(f"[cyan]FFmpeg showinfo command: {' '.join(cmd)}[/cyan]", emoji=False)

        returncode, _, stderr = await run_ffmpeg(info_command)
        assert returncode is not None
        stderr_text = stderr.decode('utf-8', errors='replace')

        # Calculate frame number based on timestamp and framerate
        frame_rate = meta.get('frame_rate', 24.0)
        calculated_frame = int(ss_time * frame_rate)

        # Default values
        frame_info = {
            'frame_type': 'Unknown',
            'frame_number': calculated_frame
        }

        pict_type_match = re.search(r'pict_type:(\w)', stderr_text)
        if pict_type_match:
            frame_info['frame_type'] = pict_type_match.group(1)
        else:
            # Try alternative patterns that might appear in newer FFmpeg versions
            alt_match = re.search(r'type:(\w)\s', stderr_text)
            if alt_match:
                frame_info['frame_type'] = alt_match.group(1)

        pts_time_match = re.search(r'pts_time:(\d+\.\d+)', stderr_text)
        if pts_time_match:
            exact_time = float(pts_time_match.group(1))
            frame_info['pts_time'] = exact_time
            # Recalculate frame number based on exact PTS time if available
            frame_info['frame_number'] = int(exact_time * frame_rate)

        return frame_info

    except Exception as e:
        console.print(f"[yellow]Error getting frame info: {e}. Will use estimated values.[/yellow]")
        if meta.get('debug', False):
            console.print(traceback.format_exc())
        return {
            'frame_type': 'Unknown',
            'frame_number': int(ss_time * meta.get('frame_rate', 24.0))
        }


async def check_libplacebo_compatibility(w_sar, h_sar, width, height, path, ss_time, image_path, loglevel, meta):
    test_image_path = image_path.replace('.png', '_test.png')

    async def run_check(w_sar, h_sar, width, height, path, ss_time, image_path, loglevel, meta, try_libplacebo=False, test_image_path=None):
        filter_parts = []
        input_label = "[0:v]"
        output_map = "0:v"  # Default output mapping

        if w_sar != 1 or h_sar != 1:
            filter_parts.append(f"{input_label}scale={int(round(width * w_sar))}:{int(round(height * h_sar))}[scaled]")
            input_label = "[scaled]"
            output_map = "[scaled]"

        # Add libplacebo filter with output label
        if try_libplacebo:
            filter_parts.append(f"{input_label}libplacebo=tonemapping=auto:colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[out]")
            output_map = "[out]"
            cmd = [
                "ffmpeg",
                "-init_hw_device", "vulkan",
                "-ss", str(ss_time),
                "-i", path,
                "-filter_complex", ",".join(filter_parts),
                "-map", output_map,
                "-vframes", "1",
                "-pix_fmt", "rgb24",
                "-y",
                "-loglevel", "quiet",
                test_image_path
            ]
        else:
            # Use -vf for zscale/tonemap chain, no output label or -map needed
            vf_chain = f"zscale=transfer=linear,tonemap=tonemap={algorithm}:desat={desat},zscale=transfer=bt709,format=rgb24"
            cmd = [
                "ffmpeg",
                "-ss", str(ss_time),
                "-i", path,
                "-vf", vf_chain,
                "-vframes", "1",
                "-pix_fmt", "rgb24",
                "-y",
                "-loglevel", "quiet",
                test_image_path
            ]

        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            console.print(f"[cyan]libplacebo compatibility test command: {' '.join(cmd)}[/cyan]")

        # Add timeout to prevent hanging
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 second timeout for compatibility test
            )
            return process.returncode
        except asyncio.TimeoutError:
            console.print("[red]libplacebo compatibility test timed out after 30 seconds[/red]")
            process.kill()
            try:
                await process.wait()
            except Exception:
                pass
            return False

    if not meta['is_disc']:
        is_libplacebo_compatible = await run_check(w_sar, h_sar, width, height, path, ss_time, image_path, loglevel, meta, try_libplacebo=True, test_image_path=test_image_path)
        if is_libplacebo_compatible == 0:
            if meta['debug']:
                console.print("[green]libplacebo compatibility test succeeded[/green]")
            try:
                if os.path.exists(test_image_path):
                    os.remove(test_image_path)
            except Exception:
                pass
            return True, True
        else:
            can_hdr = await run_check(w_sar, h_sar, width, height, path, ss_time, image_path, loglevel, meta, try_libplacebo=False, test_image_path=test_image_path)
            if can_hdr == 0:
                if meta['debug']:
                    console.print("[yellow]libplacebo compatibility test failed, but zscale HDR tonemapping is compatible[/yellow]")
                # Clean up the test image regardless of success/failure
                try:
                    if os.path.exists(test_image_path):
                        os.remove(test_image_path)
                except Exception:
                    pass
                return False, True
    return False, False


async def libplacebo_warmup(path, meta, loglevel):
    if not meta.get('libplacebo') or meta.get('_libplacebo_warmed'):
        return
    if not os.path.exists(path):
        return
    # Use a very small seek (0.1s) to avoid issues at pts 0
    cmd = [
        "ffmpeg",
        "-ss", "0.1",
        "-i", path,
        "-map", "0:v:0",
        "-an", "-sn",
        "-init_hw_device", "vulkan",
        "-vf", "libplacebo=tonemapping=hable:colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv,format=rgb24",
        "-vframes", "1",
        "-f", "null",
        "-",
        "-loglevel", "error"
    ]
    if loglevel == 'verbose' or meta.get('debug', False):
        console.print("[cyan]Running libplacebo warm-up...[/cyan]", emoji=False)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=40)
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await proc.wait()
            except Exception:
                pass
            if loglevel == 'verbose' or meta.get('debug', False):
                console.print("[yellow]libplacebo warm-up timed out (continuing anyway)[/yellow]")
        meta['_libplacebo_warmed'] = True
    except Exception as e:
        if loglevel == 'verbose' or meta.get('debug', False):
            console.print(f"[yellow]libplacebo warm-up failed: {e} (continuing)[/yellow]")


async def get_image_host(meta):
    if meta.get('imghost') is not None:
        host = meta['imghost']

        if isinstance(host, str):
            return host.lower().strip()

        elif isinstance(host, list):
            for item in host:
                if item and isinstance(item, str):
                    return item.lower().strip()
    else:
        img_host_config = [
            config["DEFAULT"][key].lower()
            for key in sorted(config["DEFAULT"].keys())
            if key.startswith("img_host_1") and not key.endswith("0")
        ]
        if img_host_config:
            return str(img_host_config[0])
