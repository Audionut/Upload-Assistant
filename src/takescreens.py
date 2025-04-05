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

img_host = [
    config["DEFAULT"][key].lower()
    for key in sorted(config["DEFAULT"].keys())
    if key.startswith("img_host_1")
]
task_limit = int(config['DEFAULT'].get('process_limit', 1))
threads = str(config['DEFAULT'].get('threads', '1'))
cutoff = int(config['DEFAULT'].get('cutoff_screens', 1))

try:
    task_limit = int(task_limit)  # Convert to integer
except ValueError:
    task_limit = 1
tone_map = config['DEFAULT'].get('tone_map', False)
optimize_images = config['DEFAULT'].get('optimize_images', True)


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
    else:
        hdr_tonemap = False
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

        ss_times = await valid_ss_time([], num_screens + 1, length, frame_rate)
        existing_indices = {int(p.split('-')[-1].split('.')[0]) for p in existing_screens}
        capture_tasks = [
            capture_disc_task(
                i,
                file,
                ss_times[i],
                os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{len(existing_indices) + i}.png"),
                keyframe,
                loglevel,
                hdr_tonemap
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

        console.print(f"[green]Successfully captured {len(capture_results)} screenshots.")

        optimized_results = []
        valid_images = [image for image in capture_results if os.path.exists(image)]

        if not valid_images:
            console.print("[red]No valid images found for optimization.[/red]")
            return []

        # Dynamically determine the number of processes
        num_tasks = len(valid_images)
        num_workers = min(num_tasks, task_limit)
        console.print("[yellow]Now optimizing images...[/yellow]")
        if meta['debug']:
            console.print(f"Using {num_workers} worker(s) for {num_tasks} image(s)")
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

        console.print(f"[green]Successfully optimized {len(optimized_results)} images.[/green]")

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
            elif any(host in ["ptpimg", "lensdump", "ptscreens", "oeimg"] for host in img_host):
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
                            (index, file, random_time, image_path, keyframe, loglevel, hdr_tonemap)
                        )

                        await optimize_image_task(screenshot_response)
                        new_size = os.path.getsize(screenshot_response)
                        valid_image = False

                        if "imgbb" in img_host and new_size > 75000 and new_size <= 31000000:
                            console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                            valid_image = True
                        elif new_size > 75000 and new_size <= 10000000 and any(host in ["imgbox", "pixhost"] for host in img_host):
                            console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                            valid_image = True
                        elif new_size > 75000 and any(host in ["ptpimg", "lensdump", "ptscreens", "oeimg", "zipline"] for host in img_host):
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

    console.print(f"[green]Successfully captured {len(valid_results)} screenshots.")

    if meta['debug']:
        finish_time = time.time()
        console.print(f"Screenshots processed in {finish_time - start_time:.4f} seconds")


async def capture_disc_task(index, file, ss_time, image_path, keyframe, loglevel, hdr_tonemap):
    try:
        ff = ffmpeg.input(file, ss=ss_time, skip_frame=keyframe)
        if hdr_tonemap:
            ff = (
                ff
                .filter('zscale', transfer='linear')
                .filter('tonemap', tonemap='mobius', desat=8.0)
                .filter('zscale', transfer='bt709')
                .filter('format', 'rgb24')
            )
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
    ss_times = await valid_ss_time([], num_screens + 1, voblength, frame_rate)
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
        for i in range(num_screens + 1):
            image = f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][disc_num]['name']}-{i}.png"
            input_file = f"{meta['discs'][disc_num]['path']}/VTS_{main_set[i % len(main_set)]}"
            if not os.path.exists(image) or meta.get('retake', False):
                capture_tasks.append(
                    capture_dvd_screenshot(
                        (i, input_file, image, ss_times[i], meta, width, height, w_sar, h_sar)
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

        if num_workers == 0:
            console.print("[red]No valid images found for optimization.[/red]")
            return
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
            console.print("[yellow]Shutting down optimization workers...[/yellow]")
            await asyncio.sleep(0.1)
            await kill_all_child_processes()
            executor.shutdown(wait=False)
            gc.collect()

        optimized_results = [res for res in optimized_results if not isinstance(res, str) or not res.startswith("Error")]

        if meta['debug']:
            console.print("Optimized results:", optimized_results)
        console.print(f"[green]Successfully optimized {len(optimized_results)} images.")

        executor.shutdown(wait=True)  # Ensure cleanup

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

                        await optimize_image_task(screenshot_result)

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

    console.print(f"[green]Successfully captured {len(valid_results)} screenshots.")


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

    if num_screens is None:
        num_screens = screens - len(existing_images)
    if num_screens <= 0:
        return

    try:
        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", encoding='utf-8') as f:
            mi = json.load(f)
            video_track = mi['media']['track'][1]
            length = float(video_track.get('Duration', mi['media']['track'][0]['Duration']))
            width = float(video_track.get('Width'))
            height = float(video_track.get('Height'))
            par = float(video_track.get('PixelAspectRatio', 1))
            dar = float(video_track.get('DisplayAspectRatio'))
            frame_rate = float(video_track.get('FrameRate', 24.0)) if isinstance(video_track.get('FrameRate'), str) else 24.0

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
        return

    loglevel = 'verbose' if meta.get('ffdebug', False) else 'quiet'
    os.chdir(f"{base_dir}/tmp/{folder_id}")

    if manual_frames:
        if meta.get('debug', False):
            console.print(f"[yellow]Using manual frames: {manual_frames}")

        try:
            if isinstance(manual_frames, str):
                manual_frames = [int(frame.strip()) for frame in manual_frames.split(',')]
            elif isinstance(manual_frames, list):
                manual_frames = [int(frame) if isinstance(frame, str) else frame for frame in manual_frames]

            ss_times = [frame / frame_rate for frame in manual_frames]
        except (TypeError, ValueError) as e:
            console.print(f"[red]Error processing manual frames: {e}. Using auto-generated frames.[/red]")
            ss_times = await valid_ss_time([], num_screens + 1, length, frame_rate, exclusion_zone=500)
    else:
        ss_times = await valid_ss_time([], num_screens + 1, length, frame_rate, exclusion_zone=500)

    if meta['debug']:
        console.print(f"[green]Final list of frames for screenshots: {ss_times}")

    sanitized_filename = await sanitize_filename(filename)

    if tone_map and "HDR" in meta['hdr']:
        hdr_tonemap = True
    else:
        hdr_tonemap = False

    existing_images_count = 0
    existing_image_paths = []
    for i in range(num_screens + 1):
        image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png")
        if os.path.exists(image_path) and not meta.get('retake', False):
            existing_images_count += 1
            existing_image_paths.append(image_path)

    if existing_images_count == num_screens and not meta.get('retake', False):
        console.print("[yellow]The correct number of screenshots already exists. Skipping capture process.")
        return existing_image_paths

    meta['frame_overlay'] = config['DEFAULT'].get('frame_overlay', False)
    if meta['frame_overlay']:
        console.print("[yellow]Getting frame information for overlays...")
        frame_info_tasks = [
            get_frame_info(path, ss_times[i], meta)
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

    num_capture = num_screens + 1 - existing_images_count
    num_tasks = num_capture
    num_workers = min(num_tasks, task_limit)

    if meta['debug']:
        console.print(f"Using {num_workers} worker(s) for {num_capture} image(s)")

    capture_tasks = []
    for i in range(num_screens + 1):
        image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png")
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
        sys.exit(1)
    except asyncio.CancelledError:
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        gc.collect()
        raise
    except Exception as e:
        console.print(f"[red]Error during screenshot capture: {e}[/red]")
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        gc.collect()
        return []
    finally:
        await asyncio.sleep(0.1)
        await kill_all_child_processes()
        console.print("[yellow]All capture tasks finished. Cleaning up...[/yellow]")

    console.print(f"[green]Successfully captured {len(capture_results)} screenshots.")

    if len(capture_results) > num_screens:
        smallest = min(capture_results, key=os.path.getsize)
        if meta['debug']:
            console.print(f"[yellow]Removing smallest image: {smallest} ({os.path.getsize(smallest)} bytes)")
        os.remove(smallest)
        capture_results.remove(smallest)

    optimized_results = []
    valid_images = [image for image in capture_results if os.path.exists(image)]
    num_workers = min(task_limit, len(capture_results))
    console.print("[yellow]Now optimizing images...[/yellow]")
    if meta['debug']:
        console.print(f"Using {num_workers} worker(s) for {len(capture_results)} image(s)")

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
        sys.exit(1)
    finally:
        console.print("[yellow]Shutting down optimization workers...[/yellow]")
        await asyncio.sleep(0.1)
        executor.shutdown(wait=True, cancel_futures=True)
        for task in tasks:
            task.cancel()
        await kill_all_child_processes()
        gc.collect()

    # Filter out failed results
    optimized_results = [res for res in optimized_results if isinstance(res, str) and "Error" not in res]
    console.print(f"[green]Successfully optimized {len(optimized_results)} images.[/green]")

    valid_results = []
    remaining_retakes = []
    for image_path in optimized_results:
        if "Error" in image_path:
            console.print(f"[red]{image_path}")
            continue

        retake = False
        image_size = os.path.getsize(image_path)
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
            elif any(host in ["ptpimg", "lensdump", "ptscreens", "oeimg", "zipline"] for host in img_host):
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
                    screenshot_response = await capture_screenshot(
                        (index, path, random_time, image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta)
                    )

                    if not os.path.exists(screenshot_response):
                        raise FileNotFoundError(f"Screenshot {screenshot_response} was not created successfully.")

                    await optimize_image_task(screenshot_response)
                    new_size = os.path.getsize(screenshot_response)
                    valid_image = False

                    if "imgbb" in img_host and 75000 < new_size <= 31000000:
                        console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                        valid_image = True
                    elif 75000 < new_size <= 10000000 and any(host in ["imgbox", "pixhost"] for host in img_host):
                        console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                        valid_image = True
                    elif new_size > 75000 and any(host in ["ptpimg", "lensdump", "ptscreens", "oeimg"] for host in img_host):
                        console.print(f"[green]Successfully retaken screenshot for: {screenshot_response} ({new_size} bytes)[/green]")
                        valid_image = True

                    if valid_image:
                        valid_results.append(screenshot_response)
                        break  # Exit retry loop on success
                    else:
                        console.print(f"[red]Retaken image {screenshot_response} does not meet the size requirements for {img_host}. Retrying...[/red]")

                except asyncio.CancelledError:
                    gc.collect()
                    raise  # Ensure cancellation propagates

                except FileNotFoundError as e:
                    console.print(f"[red]File error during screenshot retake: {e}[/red]")

                except OSError as e:
                    console.print(f"[red]OS error while processing {image_path}: {e}[/red]")

                except ValueError as e:
                    console.print(f"[red]Value error in screenshot retake process: {e}[/red]")

                except Exception as e:
                    console.print(f"[red]Unexpected error retaking screenshot for {image_path}: {e}[/red]")

                finally:
                    gc.collect()

            else:
                console.print(f"[red]All retry attempts failed for {image_path}. Skipping.[/red]")
                remaining_retakes.append(image_path)
                gc.collect()

        else:
            valid_results.append(image_path)

    if remaining_retakes:
        console.print(f"[red]The following images could not be retaken successfully: {remaining_retakes}[/red]")

    console.print(f"[green]Successfully processed {len(valid_results)} screenshots.")

    if meta['debug']:
        finish_time = time.time()
        console.print(f"Screenshots processed in {finish_time - start_time:.4f} seconds")


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


async def capture_screenshot(args):
    index, path, ss_time, image_path, width, height, w_sar, h_sar, loglevel, hdr_tonemap, meta = args

    try:
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
        ff = ffmpeg.input(path, ss=ss_time)
        if w_sar != 1 or h_sar != 1:
            ff = ff.filter('scale', int(round(width * w_sar)), int(round(height * h_sar)))

        if hdr_tonemap:
            ff = (
                ff
                .filter('zscale', transfer='linear')
                .filter('tonemap', tonemap='mobius', desat=10.0)
                .filter('zscale', transfer='bt709')
                .filter('format', 'rgb24')
            )

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

            # Get the resolution and convert it to integer
            resol = int(''.join(filter(str.isdigit, meta.get('resolution','1080p'))))
            # Assess the font size from the resolution
            font_size = round(24*resol/1080)
            x_all = round(10*resol/1080)
            y_number = round(10*resol/1080)
            y_type = round(40*resol/1080)
            y_hdr = round(70*resol/1080)

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


async def valid_ss_time(ss_times, num_screens, length, frame_rate, exclusion_zone=None):
    total_screens = num_screens + 1

    if exclusion_zone is None:
        exclusion_zone = max(length / (3 * total_screens), length / 15)

    result_times = ss_times.copy()
    section_size = (round(4 * length / 5) - round(length / 5)) / total_screens * 1.3
    section_starts = [round(length / 5) + i * (section_size * 0.9) for i in range(total_screens)]

    for section_index in range(total_screens):
        valid_time = False
        attempts = 0
        start_frame = round(section_starts[section_index] * frame_rate)
        end_frame = round((section_starts[section_index] + section_size) * frame_rate)

        while not valid_time and attempts < 50:
            attempts += 1
            frame = random.randint(start_frame, end_frame)
            time = frame / frame_rate

            if all(abs(frame - existing_time * frame_rate) > exclusion_zone * frame_rate for existing_time in result_times):
                result_times.append(time)
                valid_time = True

        if not valid_time:
            midpoint_frame = (start_frame + end_frame) // 2
            result_times.append(midpoint_frame / frame_rate)

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
