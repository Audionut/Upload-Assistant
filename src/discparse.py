# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import sys
import asyncio
import shutil
import traceback
from glob import glob
from pymediainfo import MediaInfo
from collections import OrderedDict
import json
from pyparsebluray import mpls
from xml.etree import ElementTree as ET
import re
from langcodes import Language
from collections import defaultdict
from src.console import console
from data.config import config
from src.exportmi import setup_mediainfo_library


class DiscParse():
    def __init__(self):
        self.config = config
        self.mediainfo_config = None
        pass

    def setup_mediainfo_for_dvd(self, base_dir, debug=False):
        """Setup MediaInfo binary for DVD processing using the complete setup from exportmi"""
        if self.mediainfo_config is None:
            self.mediainfo_config = setup_mediainfo_library(base_dir, debug)

        if self.mediainfo_config and self.mediainfo_config['cli']:
            return self.mediainfo_config['cli']
        return None

    """
    Get and parse bdinfo
    """

    async def get_bdinfo(self, meta, discs, folder_id, base_dir, meta_discs):
        use_largest = int(self.config['DEFAULT'].get('use_largest_playlist', False))
        save_dir = f"{base_dir}/tmp/{folder_id}"
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)

        if meta.get('emby', False):
            return discs, meta_discs

        for i in range(len(discs)):
            bdinfo_text = None
            path = os.path.abspath(discs[i]['path'])
            for file in os.listdir(save_dir):
                if file == f"BD_SUMMARY_{str(i).zfill(2)}.txt":
                    bdinfo_text = save_dir + "/" + file
            if bdinfo_text is None or meta_discs == []:
                bdinfo_text = ""
                playlists_path = os.path.join(path, "PLAYLIST")

                if not os.path.exists(playlists_path):
                    console.print(f"[bold red]PLAYLIST directory not found for disc {path}")
                    continue

                # Parse playlists
                valid_playlists = []
                for file_name in os.listdir(playlists_path):
                    if file_name.endswith(".mpls"):
                        mpls_path = os.path.join(playlists_path, file_name)
                        try:
                            with open(mpls_path, "rb") as mpls_file:
                                header = mpls.load_movie_playlist(mpls_file)
                                mpls_file.seek(header.playlist_start_address, os.SEEK_SET)
                                playlist_data = mpls.load_playlist(mpls_file)

                                duration = 0
                                items = []  # Collect .m2ts file paths and sizes
                                stream_directory = os.path.join(path, "STREAM")
                                file_counts = defaultdict(int)  # Tracks the count of each .m2ts file
                                file_sizes = {}  # Stores the size of each unique .m2ts file

                                for item in playlist_data.play_items:
                                    duration += (item.outtime - item.intime) / 45000
                                    try:
                                        m2ts_file = os.path.join(stream_directory, item.clip_information_filename.strip() + ".m2ts")
                                        if os.path.exists(m2ts_file):
                                            size = os.path.getsize(m2ts_file)
                                            file_counts[m2ts_file] += 1  # Increment the count
                                            file_sizes[m2ts_file] = size  # Store individual file size
                                    except AttributeError as e:
                                        console.print(f"[bold red]Error accessing clip information for item in {file_name}: {e}")

                                # Process unique playlists with only one instance of each file
                                if all(count == 1 for count in file_counts.values()):
                                    items = [{"file": file, "size": file_sizes[file]} for file in file_counts]

                                    # Save playlists with duration >= 10 minutes
                                    if duration >= 600:
                                        valid_playlists.append({
                                            "file": file_name,
                                            "duration": duration,
                                            "path": mpls_path,
                                            "items": items
                                        })
                        except Exception as e:
                            console.print(f"[bold red]Error parsing playlist {mpls_path}: {e}")

                if not valid_playlists:
                    # Find all playlists regardless of duration
                    all_playlists = []
                    for file_name in os.listdir(playlists_path):
                        if file_name.endswith(".mpls"):
                            mpls_path = os.path.join(playlists_path, file_name)
                            try:
                                with open(mpls_path, "rb") as mpls_file:
                                    header = mpls.load_movie_playlist(mpls_file)
                                    mpls_file.seek(header.playlist_start_address, os.SEEK_SET)
                                    playlist_data = mpls.load_playlist(mpls_file)

                                    duration = 0
                                    items = []
                                    stream_directory = os.path.join(path, "STREAM")
                                    file_counts = defaultdict(int)
                                    file_sizes = {}

                                    for item in playlist_data.play_items:
                                        duration += (item.outtime - item.intime) / 45000
                                        try:
                                            m2ts_file = os.path.join(stream_directory, item.clip_information_filename.strip() + ".m2ts")
                                            if os.path.exists(m2ts_file):
                                                size = os.path.getsize(m2ts_file)
                                                file_counts[m2ts_file] += 1
                                                file_sizes[m2ts_file] = size
                                        except AttributeError as e:
                                            console.print(f"[bold red]Error accessing clip info for item in {file_name}: {e}")

                                    if all(count == 1 for count in file_counts.values()):
                                        items = [{"file": file, "size": file_sizes[file]} for file in file_counts]
                                        all_playlists.append({
                                            "file": file_name,
                                            "duration": duration,
                                            "path": mpls_path,
                                            "items": items
                                        })
                            except Exception as e:
                                console.print(f"[bold red]Error parsing playlist {mpls_path}: {e}")

                    if all_playlists:
                        console.print("[yellow]Using available playlists with any duration")
                        # Select the largest playlist by total size
                        largest_playlist = max(all_playlists, key=lambda p: sum(item['size'] for item in p['items']))
                        console.print(f"[green]Selected largest playlist {largest_playlist['file']} with duration {largest_playlist['duration']:.2f} seconds")
                        valid_playlists = [largest_playlist]
                    else:
                        console.print(f"[bold red]No playlists found for disc {path}")
                        continue

                if use_largest:
                    console.print("[yellow]Auto-selecting the largest playlist based on configuration.")
                    selected_playlists = [max(valid_playlists, key=lambda p: sum(item['size'] for item in p['items']))]
                else:
                    # Allow user to select playlists
                    if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                        if len(valid_playlists) == 1:
                            console.print("[yellow]Only one valid playlist found. Automatically selecting.")
                            selected_playlists = valid_playlists
                        else:
                            while True:  # Loop until valid input is provided
                                console.print("[bold green]Available playlists:")
                                for idx, playlist in enumerate(valid_playlists):
                                    duration_str = f"{int(playlist['duration'] // 3600)}h {int((playlist['duration'] % 3600) // 60)}m {int(playlist['duration'] % 60)}s"
                                    items_str = ', '.join(f"{os.path.basename(item['file'])} ({item['size'] // (1024 * 1024)} MB)" for item in playlist['items'])
                                    console.print(f"[{idx}] {playlist['file']} - {duration_str} - {items_str}")

                                console.print("[bold yellow]Enter playlist numbers separated by commas, 'ALL' to select all, or press Enter to select the biggest playlist:")
                                user_input = input("Select playlists: ").strip()

                                if user_input.lower() == "all":
                                    selected_playlists = valid_playlists
                                    break
                                elif user_input == "":
                                    # Select the playlist with the largest total size
                                    console.print("[yellow]Selecting the playlist with the largest size:")
                                    selected_playlists = [max(valid_playlists, key=lambda p: sum(item['size'] for item in p['items']))]
                                    break
                                else:
                                    try:
                                        selected_indices = [int(x) for x in user_input.split(',')]
                                        selected_playlists = [valid_playlists[idx] for idx in selected_indices if 0 <= idx < len(valid_playlists)]
                                        break
                                    except ValueError:
                                        console.print("[bold red]Invalid input. Please try again.")
                    else:
                        # Automatically select the largest playlist if unattended without confirmation
                        console.print("[yellow]Auto-selecting the largest playlist based on unattended configuration.")
                        selected_playlists = [max(valid_playlists, key=lambda p: sum(item['size'] for item in p['items']))]

                for idx, playlist in enumerate(selected_playlists):
                    console.print(f"[bold green]Scanning playlist {playlist['file']} with duration {int(playlist['duration'] // 3600)} hours {int((playlist['duration'] % 3600) // 60)} minutes {int(playlist['duration'] % 60)} seconds")
                    playlist_number = playlist['file'].replace(".mpls", "")
                    playlist_report_path = os.path.join(save_dir, f"Disc{i + 1}_{playlist_number}_FULL.txt")

                    if os.path.exists(playlist_report_path):
                        bdinfo_text = playlist_report_path
                    else:
                        try:
                            bdinfo_executable = None
                            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                                bdinfo_exe_path = f"{base_dir}/bin/BDInfo/BDInfo.exe"
                                if shutil.which("mono") and os.path.exists(bdinfo_exe_path):
                                    bdinfo_executable = ['mono', bdinfo_exe_path, path, '-m', playlist['file'], save_dir]
                                elif shutil.which("bdinfo"):
                                    bdinfo_executable = ["bdinfo", path, '-m', playlist['file'], save_dir]
                                elif shutil.which("BDInfo"):
                                    bdinfo_executable = ["BDInfo", path, '-m', playlist['file'], save_dir]
                                else:
                                    console.print(f"[bold red]BDInfo not found. Please install mono and place BDInfo.exe in {base_dir}/bin/BDInfo/ or install native bdinfo[/bold red]")
                                    continue
                            elif sys.platform.startswith('win32'):
                                bdinfo_exe_path = f"{base_dir}/bin/BDInfo/BDInfo.exe"
                                if os.path.exists(bdinfo_exe_path):
                                    bdinfo_executable = [bdinfo_exe_path, '-m', playlist['file'], path, save_dir]
                                else:
                                    console.print(f"[bold red]BDInfo.exe not found at {bdinfo_exe_path}[/bold red]")
                                    console.print(f"[yellow]Please download BDInfo and place BDInfo.exe in {base_dir}/bin/BDInfo/[/yellow]")
                                    continue
                            else:
                                console.print("[red]Unsupported platform for BDInfo.")
                                continue

                            if bdinfo_executable:
                                proc = await asyncio.create_subprocess_exec(
                                    *bdinfo_executable
                                )
                                await proc.wait()

                                if proc.returncode != 0:
                                    console.print(f"[bold red]BDInfo failed with return code {proc.returncode}[/bold red]")
                                    continue

                                # Rename the output to playlist_report_path
                                for file in os.listdir(save_dir):
                                    if file.startswith("BDINFO") and file.endswith(".txt"):
                                        bdinfo_text = os.path.join(save_dir, file)
                                        shutil.move(bdinfo_text, playlist_report_path)
                                        bdinfo_text = playlist_report_path  # Update bdinfo_text to the renamed file
                                        break
                        except Exception as e:
                            console.print(f"[bold red]Error scanning playlist {playlist['file']}: {e}")
                            continue

                    # Process the BDInfo report in the while True loop
                    while True:
                        try:
                            if not os.path.exists(bdinfo_text):
                                console.print(f"[bold red]No valid BDInfo file found for playlist {playlist_number}.")
                                break

                            with open(bdinfo_text, 'r', encoding="utf-8", errors="replace") as f:
                                text = f.read()
                                result = text.split("QUICK SUMMARY:", 2)
                                files = result[0].split("FILES:", 2)[1].split("CHAPTERS:", 2)[0].split("-------------")
                                result2 = result[1].rstrip(" \n")
                                result = result2.split("********************", 1)
                                bd_summary = result[0].rstrip(" \n")

                            with open(bdinfo_text, 'r', encoding="utf-8", errors="replace") as f:
                                text = f.read()
                                result = text.split("[code]", 3)
                                result2 = result[2].rstrip(" \n")
                                result = result2.split("FILES:", 1)
                                ext_bd_summary = result[0].rstrip(" \n")

                            # Save summaries and bdinfo for each playlist
                            if idx == 0:
                                summary_file = f"{save_dir}/BD_SUMMARY_{str(i).zfill(2)}.txt"
                                extended_summary_file = f"{save_dir}/BD_SUMMARY_EXT_{str(i).zfill(2)}.txt"
                            else:
                                summary_file = f"{save_dir}/BD_SUMMARY_{str(i).zfill(2)}_{idx}.txt"
                                extended_summary_file = f"{save_dir}/BD_SUMMARY_EXT_{str(i).zfill(2)}_{idx}.txt"

                            # Strip multiple spaces to single spaces before saving
                            bd_summary_cleaned = re.sub(r' +', ' ', bd_summary.strip())
                            ext_bd_summary_cleaned = re.sub(r' +', ' ', ext_bd_summary.strip())

                            with open(summary_file, 'w', encoding="utf-8", errors="replace") as f:
                                f.write(bd_summary_cleaned)
                            with open(extended_summary_file, 'w', encoding="utf-8", errors="replace") as f:
                                f.write(ext_bd_summary_cleaned)

                            bdinfo = self.parse_bdinfo(bd_summary, files[1], path)

                            # Prompt user for custom edition if conditions are met
                            if len(selected_playlists) > 1:
                                current_label = bdinfo.get('label', f"Playlist {idx}")
                                console.print(f"[bold yellow]Current label for playlist {playlist['file']}: {current_label}")

                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                    console.print("[bold green]You can create a custom Edition for this playlist.")
                                    user_input = input(f"Enter a new Edition title for playlist {playlist['file']} (or press Enter to keep the current label): ").strip()
                                    if user_input:
                                        bdinfo['edition'] = user_input
                                        selected_playlists[idx]['edition'] = user_input
                                        console.print(f"[bold green]Edition updated to: {bdinfo['edition']}")
                                else:
                                    console.print("[bold yellow]Unattended mode: Custom edition not added.")

                            # Save to discs array
                            if idx == 0:
                                discs[i]['summary'] = bd_summary.strip()
                                discs[i]['bdinfo'] = bdinfo
                                discs[i]['playlists'] = selected_playlists
                                if valid_playlists and meta['unattended'] and not meta.get('unattended_confirm', False):
                                    simplified_playlists = [{"file": p["file"], "duration": p["duration"]} for p in valid_playlists]
                                    duration_map = {}

                                    # Store simplified version with only file and duration, keeping only one per unique duration
                                    for playlist in valid_playlists:
                                        rounded_duration = round(playlist["duration"])
                                        if rounded_duration in duration_map:
                                            continue

                                        duration_map[rounded_duration] = {
                                            "file": playlist["file"],
                                            "duration": playlist["duration"]
                                        }

                                    simplified_playlists = list(duration_map.values())
                                    simplified_playlists.sort(key=lambda x: x["duration"], reverse=True)
                                    discs[i]['all_valid_playlists'] = simplified_playlists

                                    if meta['debug']:
                                        console.print(f"[cyan]Stored {len(simplified_playlists)} unique playlists by duration (from {len(valid_playlists)} total)")
                            else:
                                discs[i][f'summary_{idx}'] = bd_summary.strip()
                                discs[i][f'bdinfo_{idx}'] = bdinfo

                        except Exception:
                            console.print(traceback.format_exc())
                            await asyncio.sleep(5)
                            continue
                        break

            else:
                discs = meta_discs

        return discs, discs[0]['bdinfo']

    def parse_bdinfo_files(self, files):
        """
        Parse the FILES section of the BDInfo input.
        Handles filenames with markers like "(1)" and variable spacing.
        """
        bdinfo_files = []
        for line in files.splitlines():
            line = line.strip()  # Remove leading/trailing whitespace
            if not line:  # Skip empty lines
                continue

            try:
                # Split the line manually by whitespace and account for variable columns
                parts = line.split()
                if len(parts) < 5:  # Ensure the line has enough columns
                    continue

                # Handle cases where the file name has additional markers like "(1)"
                if parts[1].startswith("(") and ")" in parts[1]:
                    file_name = f"{parts[0]} {parts[1]}"  # Combine file name and marker
                    parts = [file_name] + parts[2:]  # Rebuild parts with corrected file name
                else:
                    file_name = parts[0]

                m2ts = {
                    "file": file_name,
                    "length": parts[2],  # Length is the 3rd column
                }
                bdinfo_files.append(m2ts)

            except Exception as e:
                print(f"Failed to process bdinfo line: {line} -> {e}")

        return bdinfo_files

    def parse_bdinfo(self, bdinfo_input, files, path):
        bdinfo = dict()
        bdinfo['video'] = list()
        bdinfo['audio'] = list()
        bdinfo['subtitles'] = list()
        bdinfo['path'] = path
        lines = bdinfo_input.splitlines()
        for l in lines:  # noqa E741
            line = l.strip().lower()
            if line.startswith("*"):
                line = l.replace("*", "").strip().lower()
            if line.startswith("playlist:"):
                playlist = l.split(':', 1)[1]
                bdinfo['playlist'] = playlist.split('.', 1)[0].strip()
            if line.startswith("disc size:"):
                size = l.split(':', 1)[1]
                size = size.split('bytes', 1)[0].replace(',', '')
                size = float(size) / float(1 << 30)
                bdinfo['size'] = size
            if line.startswith("length:"):
                length = l.split(':', 1)[1]
                bdinfo['length'] = length.split('.', 1)[0].strip()
            if line.startswith("video:"):
                split1 = l.split(':', 1)[1]
                split2 = split1.split('/', 12)
                while len(split2) != 9:
                    split2.append("")
                n = 0
                if "Eye" in split2[2].strip():
                    n = 1
                    three_dim = split2[2].strip()
                else:
                    three_dim = ""
                try:
                    bit_depth = split2[n + 6].strip()
                    hdr_dv = split2[n + 7].strip()
                    color = split2[n + 8].strip()
                except Exception:
                    bit_depth = ""
                    hdr_dv = ""
                    color = ""
                bdinfo['video'].append({
                    'codec': split2[0].strip(),
                    'bitrate': split2[1].strip(),
                    'res': split2[n + 2].strip(),
                    'fps': split2[n + 3].strip(),
                    'aspect_ratio': split2[n + 4].strip(),
                    'profile': split2[n + 5].strip(),
                    'bit_depth': bit_depth,
                    'hdr_dv': hdr_dv,
                    'color': color,
                    '3d': three_dim,
                })
            elif line.startswith("audio:"):
                if "(" in l:
                    l = l.split("(")[0]  # noqa E741
                l = l.strip()  # noqa E741
                split1 = l.split(':', 1)[1]
                split2 = split1.split('/')
                n = 0
                if "Atmos" in split2[2].strip():
                    n = 1
                    fuckatmos = split2[2].strip()
                else:
                    fuckatmos = ""
                try:
                    bit_depth = split2[n + 5].strip()
                except Exception:
                    bit_depth = ""
                bdinfo['audio'].append({
                    'language': split2[0].strip(),
                    'codec': split2[1].strip(),
                    'channels': split2[n + 2].strip(),
                    'sample_rate': split2[n + 3].strip(),
                    'bitrate': split2[n + 4].strip(),
                    'bit_depth': bit_depth,  # Also DialNorm, but is not in use anywhere yet
                    'atmos_why_you_be_like_this': fuckatmos,
                })
            elif line.startswith("disc title:"):
                title = l.split(':', 1)[1]
                bdinfo['title'] = title
            elif line.startswith("disc label:"):
                label = l.split(':', 1)[1]
                bdinfo['label'] = label
            elif line.startswith('subtitle:'):
                split1 = l.split(':', 1)[1]
                split2 = split1.split('/')
                bdinfo['subtitles'].append(split2[0].strip())
        files = self.parse_bdinfo_files(files)
        bdinfo['files'] = files
        for line in files:
            try:
                stripped = line.split()
                m2ts = {}
                bd_file = stripped[0]
                time_in = stripped[1]  # noqa F841
                bd_length = stripped[2]
                bd_size = stripped[3]  # noqa F841
                bd_bitrate = stripped[4]  # noqa F841
                m2ts['file'] = bd_file
                m2ts['length'] = bd_length
                bdinfo['files'].append(m2ts)
            except Exception:
                pass
        return bdinfo

    """
    Parse VIDEO_TS and get mediainfos
    """

    async def get_dvdinfo(self, discs, base_dir=None, debug=False):
        mediainfo_binary = self.setup_mediainfo_for_dvd(base_dir, debug=debug)

        for each in discs:
            path = each.get('path')
            os.chdir(path)
            files = glob("VTS_*.VOB")
            files.sort()
            filesdict = OrderedDict()
            main_set = []
            for file in files:
                trimmed = file[4:]
                if trimmed[:2] not in filesdict:
                    filesdict[trimmed[:2]] = []
                filesdict[trimmed[:2]].append(trimmed)
            main_set_duration = 0

            for vob_set in filesdict.values():
                try:
                    ifo_file = f"VTS_{vob_set[0][:2]}_0.IFO"

                    try:
                        if mediainfo_binary:
                            process = await asyncio.create_subprocess_exec(
                                mediainfo_binary, "--Output=JSON", ifo_file,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await process.communicate()

                            if process.returncode == 0 and stdout:
                                vob_set_mi = stdout.decode()
                            else:
                                console.print(f"[yellow]Specialized MediaInfo failed for {ifo_file}, falling back to standard[/yellow]")
                                if stderr:
                                    console.print(f"[red]MediaInfo stderr: {stderr.decode()}[/red]")
                                vob_set_mi = MediaInfo.parse(ifo_file, output='JSON')
                        else:
                            vob_set_mi = MediaInfo.parse(ifo_file, output='JSON')

                    except Exception as e:
                        console.print(f"[yellow]Error with DVD MediaInfo binary for JSON: {str(e)}")
                        # Fall back to standard MediaInfo
                        vob_set_mi = MediaInfo.parse(ifo_file, output='JSON')

                    vob_set_mi = json.loads(vob_set_mi)
                    tracks = vob_set_mi.get('media', {}).get('track', [])

                    if len(tracks) > 1:
                        vob_set_duration = tracks[1].get('Duration', "Unknown")
                    else:
                        console.print("Warning: Expected track[1] is missing.")
                        vob_set_duration = "Unknown"

                except Exception as e:
                    console.print(f"Error processing VOB set: {e}")
                    vob_set_duration = "Unknown"

                if vob_set_duration == "Unknown" or not vob_set_duration.replace('.', '', 1).isdigit():
                    console.print(f"Skipping VOB set due to invalid duration: {vob_set_duration}")
                    continue

                # If the duration of the new vob set > main set by more than 10%, it's the new main set
                # This should make it so TV shows pick the first episode
                vob_set_duration_float = float(vob_set_duration)
                if (vob_set_duration_float * 1.00) > (float(main_set_duration) * 1.10) or len(main_set) < 1:
                    main_set = vob_set
                    main_set_duration = vob_set_duration_float

            each['main_set'] = main_set
            set = main_set[0][:2]
            each['vob'] = vob = f"{path}/VTS_{set}_1.VOB"
            each['ifo'] = ifo = f"{path}/VTS_{set}_0.IFO"

            # Use basenames for mediainfo processing to avoid full paths in output
            vob_basename = os.path.basename(vob)
            ifo_basename = os.path.basename(ifo)

            try:
                # Process VOB file
                try:
                    if mediainfo_binary:
                        process = await asyncio.create_subprocess_exec(
                            mediainfo_binary, vob_basename,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()

                        if process.returncode == 0 and stdout:
                            vob_mi_output = stdout.decode().replace('\r\n', '\n')
                        else:
                            console.print("[yellow]Specialized MediaInfo failed for VOB, falling back[/yellow]")
                            if stderr:
                                console.print(f"[red]MediaInfo stderr: {stderr.decode()}[/red]")
                            vob_mi_output = MediaInfo.parse(vob_basename, output='STRING', full=False).replace('\r\n', '\n')
                    else:
                        vob_mi_output = MediaInfo.parse(vob_basename, output='STRING', full=False).replace('\r\n', '\n')
                except Exception as e:
                    console.print(f"[yellow]Error with DVD MediaInfo binary for VOB: {str(e)}")
                    vob_mi_output = MediaInfo.parse(vob_basename, output='STRING', full=False).replace('\r\n', '\n')

                # Store VOB mediainfo (same output for both keys)
                each['vob_mi'] = vob_mi_output
                each['vob_mi_full'] = vob_mi_output

                # Process IFO file
                try:
                    if mediainfo_binary:
                        process = await asyncio.create_subprocess_exec(
                            mediainfo_binary, ifo_basename,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()

                        if process.returncode == 0 and stdout:
                            ifo_mi_output = stdout.decode().replace('\r\n', '\n')
                        else:
                            console.print("[yellow]Specialized MediaInfo failed for IFO, falling back[/yellow]")
                            if stderr:
                                console.print(f"[red]MediaInfo stderr: {stderr.decode()}[/red]")
                            ifo_mi_output = MediaInfo.parse(ifo_basename, output='STRING', full=False).replace('\r\n', '\n')
                    else:
                        ifo_mi_output = MediaInfo.parse(ifo_basename, output='STRING', full=False).replace('\r\n', '\n')
                except Exception as e:
                    console.print(f"[yellow]Error with DVD MediaInfo binary for IFO: {str(e)}")
                    ifo_mi_output = MediaInfo.parse(ifo_basename, output='STRING', full=False).replace('\r\n', '\n')

                each['ifo_mi'] = ifo_mi_output
                each['ifo_mi_full'] = ifo_mi_output

            except Exception as e:
                console.print(f"[yellow]Error using DVD MediaInfo binary, falling back to standard: {e}")
                # Fallback to standard MediaInfo using basenames
                vob_mi_output = MediaInfo.parse(vob_basename, output='STRING', full=False).replace('\r\n', '\n')
                ifo_mi_output = MediaInfo.parse(ifo_basename, output='STRING', full=False).replace('\r\n', '\n')
                each['vob_mi'] = vob_mi_output
                each['ifo_mi'] = ifo_mi_output
                each['vob_mi_full'] = vob_mi_output
                each['ifo_mi_full'] = ifo_mi_output

            size = sum(os.path.getsize(f) for f in os.listdir('.') if os.path.isfile(f)) / float(1 << 30)
            each['disc_size'] = round(size, 2)
            if size <= 7.95:
                dvd_size = "DVD9"
                if size <= 4.37:
                    dvd_size = "DVD5"
            each['size'] = dvd_size
        return discs

    async def get_hddvd_info(self, discs, meta):
        use_largest = int(self.config['DEFAULT'].get('use_largest_playlist', False))
        for each in discs:
            path = each.get('path')
            os.chdir(path)

            try:
                # Define the playlist path
                playlist_path = os.path.join(meta['path'], "ADV_OBJ")
                xpl_files = glob(f"{playlist_path}/*.xpl")
                if meta['debug']:
                    console.print(f"Found {xpl_files} in {playlist_path}")

                if not xpl_files:
                    raise FileNotFoundError(f"No .xpl files found in {playlist_path}")

                # Use the first .xpl file found
                playlist_file = xpl_files[0]
                playlist_info = self.parse_hddvd_playlist(playlist_file)

                # Filter valid playlists (at least one clip with valid size)
                valid_playlists = []
                for playlist in playlist_info:
                    primary_clips = playlist.get("primaryClips", [])
                    evo_files = [os.path.abspath(f"{path}/{os.path.basename(clip.get('src').replace('.MAP', '.EVO'))}")
                                 for clip in primary_clips]
                    total_size = sum(os.path.getsize(evo) for evo in evo_files if os.path.exists(evo))
                    if total_size > 0:
                        playlist["totalSize"] = total_size
                        playlist["evoFiles"] = evo_files
                        valid_playlists.append(playlist)

                if not valid_playlists:
                    raise ValueError("No valid playlists found with accessible .EVO files.")

                if use_largest:
                    console.print("[yellow]Auto-selecting the largest playlist based on size.")
                    selected_playlists = [
                        max(
                            valid_playlists,
                            key=lambda p: p["totalSize"]
                        )
                    ]
                elif meta['unattended'] and not meta.get('unattended_confirm', False):
                    console.print("[yellow]Unattended mode: Auto-selecting the largest playlist.")
                    selected_playlists = [
                        max(
                            valid_playlists,
                            key=lambda p: p["totalSize"]
                        )
                    ]
                else:
                    # Allow user to select playlists
                    while True:
                        console.print("[cyan]Available playlists:")
                        for idx, playlist in enumerate(valid_playlists, start=1):
                            duration = playlist.get("titleDuration", "Unknown")
                            title_number = playlist.get("titleNumber", "")
                            playlist_id = playlist.get("id", "")
                            description = playlist.get("description", "")
                            total_size = playlist.get("totalSize", 0)
                            additional_info = []
                            if playlist_id:
                                additional_info.append(f"[yellow]ID:[/yellow] {playlist_id}")
                            if description:
                                additional_info.append(f"[yellow]Description:[/yellow] {description}")
                            additional_info.append(f"[yellow]Size:[/yellow] {total_size / (1024 * 1024):.2f} MB")
                            additional_info_str = ", ".join(additional_info)
                            console.print(f"{idx}: Duration: {duration} Playlist: {title_number}" + (f" ({additional_info_str})" if additional_info else ""))

                        user_input = input("Enter the number of the playlist you want to select: ").strip()

                        try:
                            selected_indices = [int(x) - 1 for x in user_input.split(",")]
                            if any(i < 0 or i >= len(valid_playlists) for i in selected_indices):
                                raise ValueError("Invalid playlist number.")

                            selected_playlists = [valid_playlists[i] for i in selected_indices]
                            break  # Exit the loop when valid input is provided
                        except (ValueError, IndexError):
                            console.print("[red]Invalid input. Please try again.")

                # Extract the .EVO files from the selected playlists
                primary_clips = []
                for playlist in selected_playlists:
                    primary_clips.extend(playlist.get("primaryClips", []))

                # Validate that the correct EVO files are being used
                for playlist in selected_playlists:
                    expected_evo_files = playlist.get("evoFiles", [])
                    if not expected_evo_files or any(not os.path.exists(evo) for evo in expected_evo_files):
                        raise ValueError(f"Expected EVO files for playlist {playlist['id']} do not exist.")

                    # Calculate the total size for the selected playlist
                    playlist["totalSize"] = sum(os.path.getsize(evo) for evo in expected_evo_files if os.path.exists(evo))

                    # Assign the valid EVO files
                    playlist["evoFiles"] = expected_evo_files

                if not primary_clips:
                    raise ValueError("No primary clips found in the selected playlists.")

                selected_playlist = selected_playlists[0]  # Assuming you're working with the largest or user-selected playlist
                evo_files = selected_playlist["evoFiles"]
                total_size = selected_playlist["totalSize"]

                # Overwrite mediainfo File size and Duration
                if evo_files:
                    # Filter out non-existent files
                    existing_evo_files = [evo for evo in evo_files if os.path.exists(evo)]

                    if len(existing_evo_files) >= 2:
                        # Select the second .EVO file
                        selected_evo_path = existing_evo_files[1]
                    else:
                        # Fallback to the largest file
                        selected_evo_path = max(
                            existing_evo_files,
                            key=os.path.getsize
                        )

                    if not os.path.exists(selected_evo_path):
                        raise FileNotFoundError(f"Selected .EVO file {selected_evo_path} does not exist.")

                    # Parse MediaInfo for the largest .EVO file
                    original_mediainfo = MediaInfo.parse(selected_evo_path, output='STRING', full=False)

                    modified_mediainfo = re.sub(
                        r"File size\s+:\s+[^\r\n]+",
                        f"File size                                : {total_size / (1024 ** 3):.2f} GiB",
                        original_mediainfo
                    )
                    modified_mediainfo = re.sub(
                        r"Duration\s+:\s+[^\r\n]+",
                        f"Duration                                 : {self.format_duration(selected_playlist['titleDuration'])}",
                        modified_mediainfo
                    )

                    # Split MediaInfo into blocks for easier manipulation
                    mediainfo_blocks = modified_mediainfo.replace("\r\n", "\n").split("\n\n")

                    # Add language details to the correct "Audio #X" block
                    audio_tracks = selected_playlist.get("audioTracks", [])
                    for audio_track in audio_tracks:
                        # Extract track information from the playlist
                        track_number = int(audio_track.get("track", "1"))  # Ensure track number is an integer
                        language = audio_track.get("language", "")
                        langcode = audio_track.get("langcode", "")
                        description = audio_track.get("description", "")

                        # Debugging: Print the current audio track information
                        console.print(f"[Debug] Processing Audio Track: {track_number}")
                        console.print(f"        Language: {language}")
                        console.print(f"        Langcode: {langcode}")

                        # Find the corresponding "Audio #X" block in MediaInfo
                        found_block = False
                        for i, block in enumerate(mediainfo_blocks):
                            # console.print(mediainfo_blocks)
                            if re.match(rf"^\s*Audio #\s*{track_number}\b.*", block):  # Match the correct Audio # block
                                found_block = True
                                console.print(f"[Debug] Found matching MediaInfo block for Audio Track {track_number}.")

                                # Check if Language is already present
                                if language and not re.search(rf"Language\s+:\s+{re.escape(language)}", block):
                                    # Locate "Compression mode" line
                                    compression_mode_index = block.find("Compression mode")
                                    if compression_mode_index != -1:
                                        # Find the end of the "Compression mode" line
                                        line_end = block.find("\n", compression_mode_index)
                                        if line_end == -1:
                                            line_end = len(block)  # If no newline, append to the end of the block

                                        # Construct the new Language entry
                                        language_entry = f"\nLanguage                                 : {language}"

                                        # Insert the new entry
                                        updated_block = (
                                            block[:line_end]  # Up to the end of the "Compression mode"
                                            + language_entry
                                            + block[line_end:]  # Rest of the block
                                        )
                                        mediainfo_blocks[i] = updated_block
                                        console.print(f"[Debug] Updated MediaInfo Block for Audio Track {track_number}:")
                                        console.print(updated_block)
                                break  # Stop processing once the correct block is modified

                        # Debugging: Log if no matching block was found
                        if not found_block:
                            console.print(f"[Debug] No matching MediaInfo block found for Audio Track {track_number}.")

                    # Add subtitle track languages to the correct "Text #X" block
                    subtitle_tracks = selected_playlist.get("subtitleTracks", [])
                    for subtitle_track in subtitle_tracks:
                        track_number = int(subtitle_track.get("track", "1"))  # Ensure track number is an integer
                        language = subtitle_track.get("language", "")
                        langcode = subtitle_track.get("langcode", "")

                        # Debugging: Print current subtitle track info
                        console.print(f"[Debug] Processing Subtitle Track: {track_number}")
                        console.print(f"        Language: {language}")
                        console.print(f"        Langcode: {langcode}")

                        # Find the corresponding "Text #X" block
                        found_block = False
                        for i, block in enumerate(mediainfo_blocks):
                            if re.match(rf"^\s*Text #\s*{track_number}\b", block):  # Match the correct Text # block
                                found_block = True
                                console.print(f"[Debug] Found matching MediaInfo block for Subtitle Track {track_number}.")

                                # Insert Language details if not already present
                                if language and not re.search(rf"Language\s+:\s+{re.escape(language)}", block):
                                    # Locate the "Format" line
                                    format_index = block.find("Format")
                                    if format_index != -1:
                                        # Find the end of the "Format" line
                                        insertion_point = block.find("\n", format_index)
                                        if insertion_point == -1:
                                            insertion_point = len(block)  # If no newline, append to the end of the block

                                        # Construct the new Language entry
                                        language_entry = f"\nLanguage                                 : {language}"

                                        # Insert the new entry
                                        updated_block = (
                                            block[:insertion_point]  # Up to the end of the "Format" line
                                            + language_entry
                                            + block[insertion_point:]  # Rest of the block
                                        )
                                        mediainfo_blocks[i] = updated_block
                                        console.print(f"[Debug] Updated MediaInfo Block for Subtitle Track {track_number}:")
                                        console.print(updated_block)
                                break  # Stop processing once the correct block is modified

                        # Debugging: Log if no matching block was found
                        if not found_block:
                            console.print(f"[Debug] No matching MediaInfo block found for Subtitle Track {track_number}.")

                    # Rejoin the modified MediaInfo blocks
                    modified_mediainfo = "\n\n".join(mediainfo_blocks)

                    # Update the dictionary with the modified MediaInfo and file path
                    each['evo_mi'] = modified_mediainfo
                    each['largest_evo'] = selected_evo_path

                # Save playlist information in meta under HDDVD_PLAYLIST
                meta["HDDVD_PLAYLIST"] = selected_playlist

            except (FileNotFoundError, ValueError, ET.ParseError) as e:
                console.print(f"Playlist processing failed: {e}. Falling back to largest EVO file detection.")

                # Fallback to largest .EVO file
                files = glob("*.EVO")
                if not files:
                    console.print("No EVO files found in the directory.")
                    continue

                size = 0
                largest = files[0]

                # Get largest file from files
                for file in files:
                    file_size = os.path.getsize(file)
                    if file_size > size:
                        largest = file
                        size = file_size

                # Generate MediaInfo for the largest EVO file
                each['evo_mi'] = MediaInfo.parse(os.path.basename(largest), output='STRING', full=False)
                each['largest_evo'] = os.path.abspath(f"{path}/{largest}")

        return discs

    def format_duration(self, timecode):
        parts = timecode.split(":")
        if len(parts) != 4:
            return "Unknown duration"

        hours, minutes, seconds, _ = map(int, parts)
        duration = ""
        if hours > 0:
            duration += f"{hours} h "
        if minutes > 0:
            duration += f"{minutes} min"
        return duration.strip()

    def parse_hddvd_playlist(self, file_path):
        titles = []
        try:
            # Parse the XML structure
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract namespace
            namespace = {'ns': 'http://www.dvdforum.org/2005/HDDVDVideo/Playlist'}

            for title in root.findall(".//ns:Title", namespaces=namespace):
                title_duration = title.get("titleDuration", "00:00:00:00")
                duration_seconds = self.timecode_to_seconds(title_duration)

                # Skip titles with a duration of 10 minutes or less
                if duration_seconds <= 600:
                    continue

                title_data = {
                    "titleNumber": title.get("titleNumber"),
                    "id": title.get("id"),
                    "description": title.get("description"),
                    "titleDuration": title_duration,
                    "displayName": title.get("displayName"),
                    "onEnd": title.get("onEnd"),
                    "alternativeSDDisplayMode": title.get("alternativeSDDisplayMode"),
                    "primaryClips": [],
                    "chapters": [],
                    "audioTracks": [],
                    "subtitleTracks": [],
                    "applicationSegments": [],
                }

                # Extract PrimaryAudioVideoClip details
                for clip in title.findall(".//ns:PrimaryAudioVideoClip", namespaces=namespace):
                    clip_data = {
                        "src": clip.get("src"),
                        "titleTimeBegin": clip.get("titleTimeBegin"),
                        "titleTimeEnd": clip.get("titleTimeEnd"),
                        "seamless": clip.get("seamless"),
                        "audioTracks": [],
                        "subtitleTracks": [],
                    }

                    # Extract Audio tracks within PrimaryAudioVideoClip
                    for audio in clip.findall(".//ns:Audio", namespaces=namespace):
                        clip_data["audioTracks"].append({
                            "track": audio.get("track"),
                            "streamNumber": audio.get("streamNumber"),
                            "mediaAttr": audio.get("mediaAttr"),
                            "description": audio.get("description"),
                        })

                    # Extract Subtitle tracks within PrimaryAudioVideoClip
                    for subtitle in clip.findall(".//ns:Subtitle", namespaces=namespace):
                        clip_data["subtitleTracks"].append({
                            "track": subtitle.get("track"),
                            "streamNumber": subtitle.get("streamNumber"),
                            "mediaAttr": subtitle.get("mediaAttr"),
                            "description": subtitle.get("description"),
                        })

                    title_data["primaryClips"].append(clip_data)

                # Extract ChapterList details
                for chapter in title.findall(".//ns:ChapterList/ns:Chapter", namespaces=namespace):
                    title_data["chapters"].append({
                        "displayName": chapter.get("displayName"),
                        "titleTimeBegin": chapter.get("titleTimeBegin"),
                    })

                # Extract TrackNavigationList details (AudioTracks and SubtitleTracks)
                for audio_track in title.findall(".//ns:TrackNavigationList/ns:AudioTrack", namespaces=namespace):
                    langcode = audio_track.get("langcode", "")
                    # Extract the 2-letter language code before the colon
                    langcode_short = langcode.split(":")[0] if ":" in langcode else langcode
                    # Convert the short language code to the full language name
                    language_name = Language.get(langcode_short).display_name()

                    title_data["audioTracks"].append({
                        "track": audio_track.get("track"),
                        "langcode": langcode_short,
                        "language": language_name,
                        "description": audio_track.get("description"),
                        "selectable": audio_track.get("selectable"),
                    })

                for subtitle_track in title.findall(".//ns:TrackNavigationList/ns:SubtitleTrack", namespaces=namespace):
                    langcode = subtitle_track.get("langcode", "")
                    # Extract the 2-letter language code before the colon
                    langcode_short = langcode.split(":")[0] if ":" in langcode else langcode
                    # Convert the short language code to the full language name
                    language_name = Language.get(langcode_short).display_name()

                    title_data["subtitleTracks"].append({
                        "track": subtitle_track.get("track"),
                        "langcode": langcode_short,
                        "language": language_name,
                        "selectable": subtitle_track.get("selectable"),
                    })

                # Extract ApplicationSegment details
                for app_segment in title.findall(".//ns:ApplicationSegment", namespaces=namespace):
                    app_data = {
                        "src": app_segment.get("src"),
                        "titleTimeBegin": app_segment.get("titleTimeBegin"),
                        "titleTimeEnd": app_segment.get("titleTimeEnd"),
                        "sync": app_segment.get("sync"),
                        "zOrder": app_segment.get("zOrder"),
                        "resources": [],
                    }

                    # Extract ApplicationResource details
                    for resource in app_segment.findall(".//ns:ApplicationResource", namespaces=namespace):
                        app_data["resources"].append({
                            "src": resource.get("src"),
                            "size": resource.get("size"),
                            "priority": resource.get("priority"),
                            "multiplexed": resource.get("multiplexed"),
                        })

                    title_data["applicationSegments"].append(app_data)

                # Add the fully extracted title data to the list
                titles.append(title_data)

        except ET.ParseError as e:
            print(f"Error parsing XPL file: {e}")
        return titles

    def timecode_to_seconds(self, timecode):
        parts = timecode.split(":")
        if len(parts) != 4:
            return 0
        hours, minutes, seconds, frames = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
