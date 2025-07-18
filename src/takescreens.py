import os
import re
import glob
import time
import ffmpeg
import random
import json
import platform
import asyncio
import oxipng
import psutil
import sys
import concurrent.futures
import signal
import gc
import traceback
from pymediainfo import MediaInfo
from src.console import console
from data.config import config
from src.cleanup import cleanup, reset_terminal

img_host = [
    config["DEFAULT"][key].lower()
    for key in sorted(config["DEFAULT"].keys())
    if key.startswith("img_host_1") and not key.endswith("0")
]
task_limit = int(config['DEFAULT'].get('process_limit', 1))
threads = str(config['DEFAULT'].get('threads', '1'))
cutoff = int(config['DEFAULT'].get('cutoff_screens', 1))
ffmpeg_limit = config['DEFAULT'].get('ffmpeg_limit', False)

try:
    task_limit = int(task_limit)  # Convert to integer
except ValueError:
    task_limit = 1
tone_map = config['DEFAULT'].get('tone_map', False)
optimize_images = config['DEFAULT'].get('optimize_images', True)
algorithm = config['DEFAULT'].get('algorithm', 'mobius').strip()
desat = float(config['DEFAULT'].get('desat', 10.0))
frame_overlay = config['DEFAULT'].get('frame_overlay', False)


async def sanitize_filename(filename):
    # Replace invalid characters like colons with an underscore
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def disc_screenshots(meta, filename, bdinfo, folder_id, base_dir, use_vs, image_list, ffdebug, num_screens=None, force_screenshots=False):
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

    if frame_overlay:
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
        capture_tasks = [
            capture_disc_task(
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

        optimized_results = []
        valid_images = [image for image in capture_results if os.path.exists(image)]

        if not valid_images:
            console.print("[red]No valid images found for optimization.[/red]")
            return []

        # Dynamically determine the number of processes
        num_tasks = len(valid_images)
        num_workers = min(num_tasks, task_limit)
        if optimize_images:
            if meta['debug']:
                console.print("[yellow]Now optimizing images...[/yellow]")

            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()

            def handle_sigint(sig, frame):
                console.print("\n[red]CTRL+C detected. Cancelling optimization...[/red]")
                executor.shutdown(wait=False)
                stop_event.set()
                for task in asyncio.all_tasks(loop):
                    task.cancel()

            signal.signal(signal.SIGINT, handle_sigint)

            try:
                with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
                    tasks = [asyncio.create_task(worker_wrapper(image, optimize_image_task, executor)) for image in valid_images]

                    optimized_results = await asyncio.gather(*tasks, return_exceptions=True)

            except KeyboardInterrupt:
                console.print("\n[red]CTRL+C detected. Cancelling tasks...[/red]")
                executor.shutdown(wait=False)
                await kill_all_child_processes()
                console.print("[red]All tasks cancelled. Exiting.[/red]")
                sys.exit(1)

            finally:
                if meta['debug']:
                    console.print("[yellow]Shutting down optimization workers...[/yellow]")
                executor.shutdown(wait=False)
                await asyncio.sleep(0.1)
                await kill_all_child_processes()
                gc.collect()

            optimized_results = [res for res in optimized_results if not isinstance(res, str) or not res.startswith("Error")]
            if meta['debug']:
                console.print("Optimized results:", optimized_results)

            if not force_screenshots and meta['debug']:
                console.print(f"[green]Successfully optimized {len(optimized_results)} images.[/green]")
        else:
            optimized_results = valid_images

        valid_results = []
        remaining_retakes = []
        for image_path in optimized_results:
            if "Error" in image_path:
                console.print(f"[red]{image_path}")
                continue

            retake = False
            image_size = os.path.getsize(image_path)
            if image_size <= 75000:
                console.print(f"[yellow]Image {image_path} is incredibly small, retaking.")
                retake = True
            elif "imgbb" in img_host and image_size <= 31000000:
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for imgbb.[/green]")
            elif any(host in ["imgbox", "pixhost"] for host in img_host) and image_size <= 10000000:
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
            elif any(host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"] for host in img_host):
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
            else:
                console.print("[red]Image size does not meet requirements for your image host, retaking.")
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
                        if optimize_images:
                            optimize_image_task(screenshot_response)
                        new_size = os.path.getsize(screenshot_response)
                        valid_image = False

                        if "imgbb" in img_host and new_size > 75000 and new_size <= 31000000:
                            console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                            valid_image = True
                        elif new_size > 75000 and new_size <= 10000000 and any(host in ["imgbox", "pixhost"] for host in img_host):
                            console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                            valid_image = True
                        elif new_size > 75000 and any(host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"] for host in img_host):
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
    await cleanup()


async def capture_disc_task(index, file, ss_time, image_path, keyframe, loglevel, hdr_tonemap, meta):
    try:
        ff = ffmpeg.input(file, ss=ss_time, skip_frame=keyframe)
        if hdr_tonemap:
            ff = (
                ff
                .filter('zscale', transfer='linear')
                .filter('tonemap', tonemap=algorithm, desat=desat)
                .filter('zscale', transfer='bt709')
                .filter('format', 'rgb24')
            )

        if frame_overlay:
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

            # Use the filtered output with frame info
            base_text = ff

            # Frame number
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Number: {frame_number}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_number,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # Frame type
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Type: {frame_type}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_type,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # HDR status
            if hdr_tonemap:
                base_text = base_text.filter('drawtext',
                                             text="Tonemapped HDR",
                                             fontcolor='white',
                                             fontsize=font_size,
                                             x=x_all,
                                             y=y_hdr,
                                             box=1,
                                             boxcolor='black@0.5'
                                             )

            # Use the filtered output with frame info
            ff = base_text

        command = (
            ff
            .output(image_path, vframes=1, pix_fmt="rgb24")
            .overwrite_output()
            .global_args('-loglevel', loglevel)
        )
        process = await asyncio.create_subprocess_exec(*command.compile(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
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

        if frame_overlay:
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

        for i in range(num_screens + 1):
            if not os.path.exists(image_paths[i]) or meta.get('retake', False):
                capture_tasks.append(
                    capture_dvd_screenshot(
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

        optimized_results = []

        # Filter out non-existent files first
        valid_images = [image for image in capture_results if os.path.exists(image)]

        # Dynamically determine the number of processes
        num_tasks = len(valid_images)
        num_workers = min(num_tasks, task_limit)

        if optimize_images:
            if num_workers == 0:
                console.print("[red]No valid images found for optimization.[/red]")
                return
            if meta['debug']:
                console.print("[yellow]Now optimizing images...[/yellow]")

            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()

            def handle_sigint(sig, frame):
                console.print("\n[red]CTRL+C detected. Cancelling optimization...[/red]")
                executor.shutdown(wait=False)
                stop_event.set()
                for task in asyncio.all_tasks(loop):
                    task.cancel()

            signal.signal(signal.SIGINT, handle_sigint)

            try:
                with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
                    # Start all tasks in parallel using worker_wrapper()
                    tasks = [asyncio.create_task(worker_wrapper(image, optimize_image_task, executor)) for image in valid_images]

                    # Wait for all tasks to complete
                    optimized_results = await asyncio.gather(*tasks, return_exceptions=True)
            except KeyboardInterrupt:
                console.print("\n[red]CTRL+C detected. Cancelling tasks...[/red]")
                executor.shutdown(wait=False)
                await kill_all_child_processes()
                console.print("[red]All tasks cancelled. Exiting.[/red]")
                sys.exit(1)
            finally:
                if meta['debug']:
                    console.print("[yellow]Shutting down optimization workers...[/yellow]")
                await asyncio.sleep(0.1)
                await kill_all_child_processes()
                executor.shutdown(wait=False)
                gc.collect()

            optimized_results = [res for res in optimized_results if not isinstance(res, str) or not res.startswith("Error")]

            if meta['debug']:
                console.print("Optimized results:", optimized_results)
            if not retry_cap and meta['debug']:
                console.print(f"[green]Successfully optimized {len(optimized_results)} images.")

            executor.shutdown(wait=True)  # Ensure cleanup
        else:
            optimized_results = valid_images

        valid_results = []
        remaining_retakes = []

        for image in optimized_results:
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

                        if optimize_images:
                            optimize_image_task(screenshot_result)

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
    await cleanup()


async def capture_dvd_screenshot(task):
    index, input_file, image, seek_time, meta, width, height, w_sar, h_sar = task

    try:
        loglevel = 'verbose' if meta.get('ffdebug', False) else 'quiet'
        media_info = MediaInfo.parse(input_file)
        video_duration = next((track.duration for track in media_info.tracks if track.track_type == "Video"), None)

        if video_duration and seek_time > video_duration:
            seek_time = max(0, video_duration - 1)

        # Construct ffmpeg command
        ff = ffmpeg.input(input_file, ss=seek_time)
        if w_sar != 1 or h_sar != 1:
            ff = ff.filter('scale', int(round(width * w_sar)), int(round(height * h_sar)))

        if frame_overlay:
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

            # Use the filtered output with frame info
            base_text = ff

            # Frame number
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Number: {frame_number}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_number,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # Frame type
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Type: {frame_type}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_type,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # Use the filtered output with frame info
            ff = base_text

        cmd = ff.output(image, vframes=1, pix_fmt="rgb24").overwrite_output().global_args('-loglevel', loglevel, '-accurate_seek').compile()

        # Run ffmpeg asynchronously
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
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

    if tone_map and "HDR" in meta['hdr']:
        hdr_tonemap = True
        meta['tonemapped'] = True
    else:
        hdr_tonemap = False

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

    if frame_overlay:
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

    if meta['debug']:
        console.print(f"Using {num_workers} worker(s) for {num_capture} image(s)")

    capture_tasks = []
    for i in range(num_capture):
        image_index = existing_images_count + i
        image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{image_index}.png")
        if not os.path.exists(image_path) or meta.get('retake', False):
            capture_tasks.append(
                capture_screenshot(  # Direct async function call
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
    except Exception as e:
        console.print(f"[red]Error during screenshot capture: {e}[/red]")
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

    optimized_results = []
    valid_images = [image for image in capture_results if os.path.exists(image)]
    num_workers = min(task_limit, len(valid_images))
    if optimize_images:
        if meta['debug']:
            console.print("[yellow]Now optimizing images...[/yellow]")
            console.print(f"Using {num_workers} worker(s) for {len(valid_images)} image(s)")

        executor = concurrent.futures.ProcessPoolExecutor(max_workers=num_workers)
        try:
            with executor:
                # Start all tasks in parallel using worker_wrapper()
                tasks = [asyncio.create_task(worker_wrapper(image, optimize_image_task, executor)) for image in valid_images]

                # Wait for all tasks to complete
                optimized_results = await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            console.print("\n[red]CTRL+C detected. Cancelling optimization tasks...[/red]")
            await asyncio.sleep(0.1)
            executor.shutdown(wait=True, cancel_futures=True)
            await kill_all_child_processes()
            console.print("[red]All tasks cancelled. Exiting.[/red]")
            gc.collect()
            reset_terminal()
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error during image optimization: {e}[/red]")
            await asyncio.sleep(0.1)
            executor.shutdown(wait=True, cancel_futures=True)
            await kill_all_child_processes()
            gc.collect()
            reset_terminal()
            sys.exit(1)
        finally:
            if meta['debug']:
                console.print("[yellow]Shutting down optimization workers...[/yellow]")
            await asyncio.sleep(0.1)
            executor.shutdown(wait=True, cancel_futures=True)
            for task in tasks:
                task.cancel()
            await kill_all_child_processes()
            gc.collect()

        # Filter out failed results
        optimized_results = [res for res in optimized_results if isinstance(res, str) and "Error" not in res]
        if not force_screenshots and meta['debug']:
            console.print(f"[green]Successfully optimized {len(optimized_results)} images.[/green]")
    else:
        optimized_results = valid_images

    valid_results = []
    remaining_retakes = []
    for image_path in optimized_results:
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
            elif "imgbb" in img_host and image_size <= 31000000:
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for imgbb.[/green]")
            elif any(host in ["imgbox", "pixhost"] for host in img_host) and image_size <= 10000000:
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
            elif any(host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"] for host in img_host):
                if meta['debug']:
                    console.print(f"[green]Image {image_path} meets size requirements for {img_host}.[/green]")
            else:
                console.print("[red]Image size does not meet requirements for your image host, retaking.")
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

                            if optimize_images:
                                optimize_image_task(screenshot_path)
                            new_size = os.path.getsize(screenshot_path)
                            valid_image = False

                            if "imgbb" in img_host and 75000 < new_size <= 31000000:
                                console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                valid_image = True
                            elif 75000 < new_size <= 10000000 and any(host in ["imgbox", "pixhost"] for host in img_host):
                                console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                                valid_image = True
                            elif new_size > 75000 and any(host in ["ptpimg", "lensdump", "ptscreens", "onlyimage", "dalexni", "zipline", "passtheimage"] for host in img_host):
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

                        if optimize_images:
                            optimize_image_task(screenshot_path)
                        new_size = os.path.getsize(screenshot_path)
                        valid_image = False

                        if "imgbb" in img_host and 75000 < new_size <= 31000000:
                            valid_image = True
                        elif 75000 < new_size <= 10000000 and any(host in ["imgbox", "pixhost"] for host in img_host):
                            valid_image = True
                        elif new_size > 75000 and any(host in ["ptpimg", "lensdump", "ptscreens", "onlyimage"] for host in img_host):
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

        # Proceed with screenshot capture
        threads_value = set_ffmpeg_threads()
        threads_val = threads_value[1]
        if ffmpeg_limit:
            ff = (
                ffmpeg
                .input(path, ss=ss_time, threads=threads_val)
            )
        else:
            ff = ffmpeg.input(path, ss=ss_time)
        if w_sar != 1 or h_sar != 1:
            ff = ff.filter('scale', int(round(width * w_sar)), int(round(height * h_sar)))

        if hdr_tonemap:
            ff = (
                ff
                .filter('zscale', transfer='linear')
                .filter('tonemap', tonemap=algorithm, desat=desat)
                .filter('zscale', transfer='bt709')
                .filter('format', 'rgb24')
            )

        if frame_overlay:
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

            # Use the filtered output with frame info
            base_text = ff

            # Frame number
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Number: {frame_number}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_number,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # Frame type
            base_text = base_text.filter('drawtext',
                                         text=f"Frame Type: {frame_type}",
                                         fontcolor='white',
                                         fontsize=font_size,
                                         x=x_all,
                                         y=y_type,
                                         box=1,
                                         boxcolor='black@0.5'
                                         )

            # HDR status
            if hdr_tonemap:
                base_text = base_text.filter('drawtext',
                                             text="Tonemapped HDR",
                                             fontcolor='white',
                                             fontsize=font_size,
                                             x=x_all,
                                             y=y_hdr,
                                             box=1,
                                             boxcolor='black@0.5'
                                             )

            # Use the filtered output with frame info
            ff = base_text

        if ffmpeg_limit:
            command = (
                ff
                .output(image_path, vframes=1, pix_fmt="rgb24", **{'threads': threads_val})
                .overwrite_output()
                .global_args('-loglevel', loglevel)
            )
        else:
            command = (
                ff
                .output(image_path, vframes=1, pix_fmt="rgb24")
                .overwrite_output()
                .global_args('-loglevel', loglevel)
            )

        # Print the command for debugging
        if loglevel == 'verbose' or (meta and meta.get('debug', False)):
            cmd = command.compile()
            console.print(f"[cyan]FFmpeg command: {' '.join(cmd)}[/cyan]")

        process = await asyncio.create_subprocess_exec(
            *command.compile(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Ensure process completes and doesn't leak
        try:
            stdout, stderr = await process.communicate()

            # Print stdout and stderr if in verbose mode
            if loglevel == 'verbose':
                if stdout:
                    console.print(f"[blue]FFmpeg stdout:[/blue]\n{stdout.decode('utf-8', errors='replace')}")
                if stderr:
                    console.print(f"[yellow]FFmpeg stderr:[/yellow]\n{stderr.decode('utf-8', errors='replace')}")

        except asyncio.CancelledError:
            console.print(traceback.format_exc())
            process.kill()
            raise

        if process.returncode == 0:
            return (index, image_path)
        else:
            stderr_text = stderr.decode('utf-8', errors='replace')
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


async def worker_wrapper(image, optimize_image_task, executor):
    """ Async wrapper to run optimize_image_task in a separate process """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(executor, optimize_image_task, image)
    except KeyboardInterrupt:
        console.print(f"[red][{time.strftime('%X')}] Worker interrupted while processing {image}[/red]")
        gc.collect()
        return None
    except Exception as e:
        console.print(f"[red][{time.strftime('%X')}] Worker error on {image}: {e}[/red]")
        gc.collect()
        return f"Error: {e}"
    finally:
        gc.collect()


async def kill_all_child_processes():
    """Ensures all child processes (e.g., ProcessPoolExecutor workers) are terminated."""
    current_process = psutil.Process()
    children = current_process.children(recursive=True)  # Get child processes once

    for child in children:
        console.print(f"[red]Killing stuck worker process: {child.pid}[/red]")
        child.terminate()

    gone, still_alive = psutil.wait_procs(children, timeout=3)  # Wait for termination
    for process in still_alive:
        console.print(f"[red]Force killing stubborn process: {process.pid}[/red]")
        process.kill()


def optimize_image_task(image):
    """Optimizes an image using oxipng in a separate process."""
    try:
        if optimize_images:
            os.environ['RAYON_NUM_THREADS'] = threads
            if not os.path.exists(image):
                error_msg = f"ERROR: File not found - {image}"
                console.print(f"[red]{error_msg}[/red]")
                return error_msg

            pyver = platform.python_version_tuple()
            if int(pyver[0]) == 3 and int(pyver[1]) >= 7:
                level = 6 if os.path.getsize(image) >= 16000000 else 2

                # Run optimization directly in the process
                oxipng.optimize(image, level=level)

            return image
        else:
            return image

    except Exception as e:
        error_message = f"ERROR optimizing {image}: {e}"
        console.print(f"[red]{error_message}[/red]")
        console.print(traceback.format_exc())  # Print detailed traceback
        return None


async def get_frame_info(path, ss_time, meta):
    """Get frame information (type, exact timestamp) for a specific frame"""
    try:
        info_ff = ffmpeg.input(path, ss=ss_time)
        info_command = (
            info_ff
            .filter('showinfo')
            .output('-', format='null', vframes=1)
            .global_args('-loglevel', 'info')
        )

        # Print the actual FFmpeg command for debugging
        cmd = info_command.compile()
        if meta.get('debug', False):
            console.print(f"[cyan]FFmpeg showinfo command: {' '.join(cmd)}[/cyan]")

        # Execute the info gathering command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()
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
