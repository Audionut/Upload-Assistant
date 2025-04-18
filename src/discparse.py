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
from src.exportmi import combine_hddvd_mediainfo


class DiscParse():
    def __init__(self):
        self.config = config
        # Map of non-standard language codes to ISO 639-1 codes
        self.language_code_map = {
            "jp": "ja",  # Japanese
            "se": "sv",  # Swedish
            "dk": "da",  # Danish
            "br": "pt",  # Brazilian Portuguese
            "cz": "cs",  # Czech
        }
        pass

    """
    Get and parse bdinfo
    """
    async def get_bdinfo(self, meta, discs, folder_id, base_dir, meta_discs):
        use_largest = int(self.config['DEFAULT'].get('use_largest_playlist', False))
        save_dir = f"{base_dir}/tmp/{folder_id}"
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)

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
                    console.print(f"[bold red]No valid playlists found for disc {path}")
                    continue

                if use_largest:
                    console.print("[yellow]Auto-selecting the largest playlist based on configuration.")
                    selected_playlists = [max(valid_playlists, key=lambda p: sum(item['size'] for item in p['items']))]
                else:
                    # Allow user to select playlists
                    if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
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
                            # Scanning playlist block (as before)
                            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                                proc = await asyncio.create_subprocess_exec(
                                    'mono', f"{base_dir}/bin/BDInfo/BDInfo.exe", path, '-m', playlist['file'], save_dir
                                )
                            elif sys.platform.startswith('win32'):
                                proc = await asyncio.create_subprocess_exec(
                                    f"{base_dir}/bin/BDInfo/BDInfo.exe", '-m', playlist['file'], path, save_dir
                                )
                            else:
                                console.print("[red]Unsupported platform for BDInfo.")
                                continue

                            await proc.wait()

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

                            with open(summary_file, 'w', encoding="utf-8", errors="replace") as f:
                                f.write(bd_summary.strip())
                            with open(extended_summary_file, 'w', encoding="utf-8", errors="replace") as f:
                                f.write(ext_bd_summary.strip())

                            bdinfo = self.parse_bdinfo(bd_summary, files[1], path)

                            # Prompt user for custom edition if conditions are met
                            if len(selected_playlists) > 1:
                                current_label = bdinfo.get('label', f"Playlist {idx}")
                                console.print(f"[bold yellow]Current label for playlist {playlist['file']}: {current_label}")

                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    console.print("[bold green]You can create a custom Edition for this playlist.")
                                    user_input = input(f"Enter a new Edition title for playlist {playlist['file']} (or press Enter to keep the current label): ").strip()
                                    if user_input:
                                        bdinfo['edition'] = user_input
                                        console.print(f"[bold green]Edition updated to: {bdinfo['edition']}")
                                else:
                                    console.print("[bold yellow]Unattended mode: Custom edition not added.")

                            # Save to discs array
                            if idx == 0:
                                discs[i]['summary'] = bd_summary.strip()
                                discs[i]['bdinfo'] = bdinfo
                                discs[i]['playlists'] = selected_playlists
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
    async def get_dvdinfo(self, discs):
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
                    vob_set_mi = MediaInfo.parse(f"VTS_{vob_set[0][:2]}_0.IFO", output='JSON')
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

                vob_set_duration_float = float(vob_set_duration)

                # If the duration of the new vob set > main set by more than 10%, it's the new main set
                # This should make it so TV shows pick the first episode
                if (vob_set_duration_float * 1.00) > (float(main_set_duration) * 1.10) or len(main_set) < 1:
                    main_set = vob_set
                    main_set_duration = vob_set_duration_float

            each['main_set'] = main_set
            set = main_set[0][:2]
            each['vob'] = vob = f"{path}/VTS_{set}_1.VOB"
            each['ifo'] = ifo = f"{path}/VTS_{set}_0.IFO"
            each['vob_mi'] = MediaInfo.parse(os.path.basename(vob), output='STRING', full=False).replace('\r\n', '\n')
            each['ifo_mi'] = MediaInfo.parse(os.path.basename(ifo), output='STRING', full=False).replace('\r\n', '\n')
            each['vob_mi_full'] = MediaInfo.parse(vob, output='STRING', full=False).replace('\r\n', '\n')
            each['ifo_mi_full'] = MediaInfo.parse(ifo, output='STRING', full=False).replace('\r\n', '\n')

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
                elif meta['unattended'] and not meta.get('unattended-confirm', False):
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

                try:
                    os.makedirs(f"{meta['base_dir']}/tmp/{meta['uuid']}", exist_ok=True)

                    # Get the original XML string by reading the file
                    with open(playlist_file, 'r', encoding='utf-8') as f:
                        xml_content = f.read()

                    # Format the selected playlist for the description, including the XML
                    playlist_description = self.format_playlist_for_description(
                        [selected_playlist],
                        include_xml=True,
                        xml_string=xml_content
                    )

                    header = f"{os.path.basename(meta['path'])}\n\n"

                    full_description = header + playlist_description
                    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.nfo", 'w', encoding='utf-8', newline="") as f:
                        f.write(full_description)

                    console.print("[green]Generated description file from HD DVD playlist")

                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to generate description file: {e}")
                    console.print(traceback.format_exc())

                # Overwrite mediainfo File size and Duration
                if evo_files:
                    # Filter out non-existent files
                    existing_evo_files = [evo for evo in evo_files if os.path.exists(evo)]

                    if existing_evo_files:
                        # Create a list to store MediaInfo data for each EVO file
                        mediainfo_data = []

                        # Generate MediaInfo for each EVO file
                        for evo_file in existing_evo_files:
                            evo_filename = os.path.basename(evo_file)
                            console.print(f"[yellow]Generating MediaInfo for {evo_filename}...")

                            # Generate MediaInfo
                            evo_mediainfo = MediaInfo.parse(evo_file, output='STRING', full=False)

                            # Add to the list
                            mediainfo_data.append({
                                'file': evo_filename,
                                'path': evo_file,
                                'mediainfo': evo_mediainfo
                            })

                        # Store the MediaInfo data in the disc object
                        each['evo_files'] = mediainfo_data

                        # Combine all MediaInfo files
                        console.print("[yellow]Combining MediaInfo from all EVO files...")
                        combined_mediainfo = await combine_hddvd_mediainfo(
                            mediainfo_data,
                            total_size,
                            self.format_duration(selected_playlist['titleDuration'])
                        )

                        # Now modify the combined MediaInfo with additional details
                        modified_mediainfo = combined_mediainfo

                        # Split MediaInfo into blocks for easier manipulation
                        mediainfo_blocks = modified_mediainfo.replace("\r\n", "\n").split("\n\n")

                        # Add language details to the correct "Audio #X" block
                        for audio_track in selected_playlist.get('audioTracks', []):
                            track_number = int(audio_track.get('track', '1'))
                            language = audio_track.get('language', '')
                            langcode = audio_track.get('langcode', '')
                            description = audio_track.get('description', '')

                            # Debugging: Print the current audio track information
                            console.print(f"[Debug] Processing Audio Track: {track_number}")
                            console.print(f"        Language: {language}")
                            console.print(f"        Langcode: {langcode}")

                            # Find the corresponding audio block in MediaInfo
                            found_block = False
                            for i, block in enumerate(mediainfo_blocks):
                                # Check for both "Audio #X" format and plain "Audio" (when there's only one track)
                                if (re.match(rf"^\s*Audio #\s*{track_number}\b.*", block) or
                                        (track_number == 1 and block.strip().startswith("Audio") and not block.strip().startswith("Audio #"))):

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
                        for subtitle_track in selected_playlist.get("subtitleTracks", []):
                            track_number = int(subtitle_track.get("track", "1"))  # Ensure track number is an integer
                            language = subtitle_track.get("language", "")
                            langcode = subtitle_track.get("langcode", "")

                            # Debugging: Print current subtitle track info
                            console.print(f"[Debug] Processing Subtitle Track: {track_number}")
                            console.print(f"        Language: {language}")
                            console.print(f"        Langcode: {langcode}")

                            # Find the corresponding Text block in MediaInfo
                            found_block = False
                            for i, block in enumerate(mediainfo_blocks):
                                # Check for both "Text #X" format and plain "Text" (when there's only one track)
                                if (re.match(rf"^\s*Text #\s*{track_number}\b", block) or
                                        (track_number == 1 and block.strip().startswith("Text") and not block.strip().startswith("Text #"))):

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

                        chapters = selected_playlist.get("chapters", [])
                        console.print(f"[Debug] Found {len(chapters)} chapters in the playlist.")
                        if chapters:
                            console.print("[yellow]Adding chapter information to MediaInfo...")

                            # Find the Menu block or create a new one if it doesn't exist
                            menu_block_index = -1
                            for i, block in enumerate(mediainfo_blocks):
                                if block.strip().startswith("Menu"):
                                    menu_block_index = i
                                    break

                            # Create the Menu block content
                            menu_content = "Menu"
                            menu_content += "\nFormat                                   : HD DVD-Video"
                            menu_content += "\n"  # Ensure there's a newline

                            # Format and add each chapter
                            for chapter in chapters:
                                chapter_time = chapter.get("titleTimeBegin", "00:00:00:00")
                                chapter_name = chapter.get("displayName", "")

                                # Convert chapter time from HH:MM:SS:FF to HH:MM:SS.mmm format for MediaInfo
                                parts = chapter_time.split(":")
                                if len(parts) == 4:
                                    hours, minutes, seconds, frames = map(int, parts)
                                    # Convert frames to milliseconds (assuming 24 frames per second)
                                    milliseconds = int((frames / 24) * 1000)

                                    # Format with exactly 3 digits for milliseconds to ensure proper alignment
                                    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

                                    # Create properly spaced chapter entry - exactly 42 characters before the colon
                                    chapter_entry = formatted_time.ljust(42)

                                    # Add formatted chapter entry
                                    if chapter_name:
                                        menu_content += f"{chapter_entry}: {chapter_name}\n"
                                    else:
                                        menu_content += f"{chapter_entry}: Chapter {chapters.index(chapter) + 1}\n"

                            # If a Menu block was found, update it
                            if menu_block_index != -1:
                                mediainfo_blocks[menu_block_index] = menu_content
                            else:
                                # If no Menu block exists, add it to the end of the mediainfo_blocks
                                mediainfo_blocks.append(menu_content)

                            # Add more debug output to confirm chapter creation
                            console.print(f"[Debug] Created Menu block with {len(chapters)} chapters")
                            console.print("[Debug] First few chapter entries:")
                            chapter_entries = menu_content.strip().split('\n')[2:5]  # Skip header lines, show first 3 chapters
                            for entry in chapter_entries:
                                console.print(f"[Debug]   {entry}")

                        # Rejoin the modified MediaInfo blocks
                        # Get all Audio sections in their original order
                        audio_sections = []
                        for i, block in enumerate(mediainfo_blocks):
                            if block.strip().startswith("Audio"):
                                # Extract track number from "Audio #X" format
                                track_match = re.search(r"Audio #(\d+)", block)
                                if track_match:
                                    track_num = int(track_match.group(1))
                                else:
                                    # For "Audio" without a number, assume it's track 1
                                    track_num = 1

                                audio_sections.append((track_num, block))

                        # Get all Text sections with track numbers
                        text_sections = []
                        for i, block in enumerate(mediainfo_blocks):
                            if block.strip().startswith("Text"):
                                # Extract track number from "Text #X" format
                                track_match = re.search(r"Text #(\d+)", block)
                                if track_match:
                                    track_num = int(track_match.group(1))
                                else:
                                    # For "Text" without a number, assume it's track 1
                                    track_num = 1

                                text_sections.append((track_num, block))

                        # Find Menu section
                        menu_section = None
                        for block in mediainfo_blocks:
                            if block.strip().startswith("Menu"):
                                menu_section = block
                                break

                        # Other blocks that don't fit the above categories
                        other_blocks = []
                        for i, block in enumerate(mediainfo_blocks):
                            if (not block.strip().startswith("General") and
                                    not block.strip().startswith("Video") and
                                    not block.strip().startswith("Audio") and
                                    not block.strip().startswith("Text") and
                                    not block.strip().startswith("Menu")):
                                other_blocks.append(block)

                        # Define the standard MediaInfo section order
                        standard_section_order = ["General", "Video"]

                        # Build ordered MediaInfo blocks based on standard order
                        ordered_blocks = []

                        # First add sections in the standard order
                        for section_type in standard_section_order:
                            for block in mediainfo_blocks:
                                if block.strip().startswith(section_type):
                                    ordered_blocks.append(block)

                        # Then add Audio sections in their original order
                        for _, block in sorted(audio_sections, key=lambda x: x[0]):
                            ordered_blocks.append(block)

                        # Add Text sections in numerical track order
                        for _, block in sorted(text_sections, key=lambda x: x[0]):
                            ordered_blocks.append(block)

                        # Add Menu section if it exists
                        if menu_section:
                            ordered_blocks.append(menu_section)

                        # Add any other sections
                        for block in other_blocks:
                            ordered_blocks.append(block)

                        # Replace mediainfo_blocks with the ordered blocks
                        mediainfo_blocks = ordered_blocks

                        # Rejoin the modified MediaInfo blocks
                        modified_mediainfo = "\n\n".join(mediainfo_blocks)

                        # Add a final verification
                        menu_in_result = "Menu" in modified_mediainfo

                        # Quick check of the actual content - first 100 chars of the Menu section if found
                        if menu_in_result:
                            menu_start = modified_mediainfo.find("Menu")
                            menu_extract = modified_mediainfo[menu_start:menu_start+200].replace('\n', '\\n')
                            console.print(f"[Debug] Menu section preview: {menu_extract}")

                        # Update the dictionary with the modified MediaInfo and file path
                        each['evo_mi'] = modified_mediainfo
                        each['largest_evo'] = existing_evo_files[0]

                        # Now create a JSON version of the MediaInfo
                        try:
                            # Parse the combined MediaInfo text back to JSON format
                            json_mediainfo = MediaInfo.parse(existing_evo_files[0], output='JSON')
                            json_data = json.loads(json_mediainfo)

                            # Create a copy of the parsed data to modify
                            combined_json = json_data.copy()

                            # Update the general track with combined size and duration
                            for track in combined_json.get('media', {}).get('track', []):
                                if track.get('@type') == 'General':
                                    # Update file size
                                    track['FileSize'] = str(total_size)

                                    # Update duration if available in the playlist
                                    if 'titleDuration' in selected_playlist:
                                        duration_str = self.format_duration(selected_playlist['titleDuration'])
                                        # Convert to milliseconds for JSON format
                                        try:
                                            h, m, s = map(int, duration_str.split(':'))
                                            duration_ms = ((h * 60 + m) * 60 + s) * 1000
                                            track['Duration'] = str(duration_ms)
                                        except ValueError:
                                            pass

                                    # Add source file information
                                    file_list = [os.path.basename(evo['path']) for evo in mediainfo_data]
                                    track['SourceFiles'] = ', '.join(file_list)
                                    break

                            # Add language information to audio tracks
                            for audio_track in selected_playlist.get('audioTracks', []):
                                track_number = int(audio_track.get('track', '1'))
                                language = audio_track.get('language', '')

                                # Find matching track in JSON
                                for track in combined_json.get('media', {}).get('track', []):
                                    if track.get('@type') == 'Audio':
                                        # For the first audio track, StreamOrder might be missing or "0"
                                        track_stream_order = track.get('StreamOrder')
                                        if (track_stream_order is None and track_number == 1) or \
                                                (track_stream_order is not None and int(track_stream_order) == track_number - 1):
                                            if language:
                                                track['Language'] = language
                                            break

                            # Add language information to subtitle tracks
                            for subtitle_track in selected_playlist.get('subtitleTracks', []):
                                track_number = int(subtitle_track.get('track', '1'))
                                language = subtitle_track.get('language', '')

                                # Find matching track in JSON
                                for track in combined_json.get('media', {}).get('track', []):
                                    if track.get('@type') == 'Text' and int(track.get('StreamOrder', '0')) == track_number - 1:
                                        if language:
                                            track['Language'] = language

                            # Add chapter information
                            if selected_playlist.get('chapters'):
                                chapters_track = {
                                    '@type': 'Menu',
                                    'Format': 'HD DVD-Video',
                                    'Chapters': []
                                }

                                for chapter in selected_playlist.get('chapters', []):
                                    chapter_time = chapter.get('titleTimeBegin', '00:00:00:00')
                                    chapter_name = chapter.get('displayName', '') or f"Chapter {selected_playlist['chapters'].index(chapter) + 1}"

                                    # Convert HH:MM:SS:FF to milliseconds
                                    parts = chapter_time.split(':')
                                    if len(parts) == 4:
                                        hours, minutes, seconds, frames = map(int, parts)
                                        milliseconds = ((hours * 60 + minutes) * 60 + seconds) * 1000 + int((frames / 24) * 1000)

                                        chapters_track['Chapters'].append({
                                            'time': milliseconds,
                                            'name': chapter_name
                                        })

                                # Add chapters track if it has entries
                                if chapters_track['Chapters']:
                                    combined_json['media']['track'].append(chapters_track)

                            # Write JSON MediaInfo to file
                            json_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.json"
                            with open(json_path, 'w', encoding='utf-8') as json_file:
                                json.dump(combined_json, json_file, indent=2)

                            console.print(f"[green]MediaInfo JSON exported to {json_path}")

                        except Exception as e:
                            console.print(f"[red]Error creating JSON MediaInfo: {str(e)}")

                    else:
                        console.print("[bold red]No valid EVO files found in the playlist.")

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

            # Extract namespace - handle both with and without namespace
            namespace = {}
            if root.tag.startswith('{'):
                # Extract namespace from the root tag if it exists
                ns_uri = root.tag.split('}')[0][1:]
                namespace = {'ns': ns_uri}
                find_title_path = ".//ns:Title"
            else:
                # No namespace, use direct path
                find_title_path = ".//Title"

            # Try different approaches to find Title elements
            title_elements = []
            try:
                # First try with namespace if available
                if namespace:
                    title_elements = root.findall(find_title_path, namespaces=namespace)
                else:
                    title_elements = root.findall(find_title_path)

                # If no titles found, try alternative approaches
                if not title_elements:
                    # Try direct TitleSet/Title path for TOSHIBA format
                    title_elements = root.findall(".//TitleSet/Title")
            except Exception as e:
                console.print(f"[yellow]Initial title search failed: {e}. Trying alternative methods...")

                # Fallback method: search for any element with "Title" in the name
                for elem in root.iter():
                    tag = elem.tag
                    if isinstance(tag, str) and 'Title' in tag.split('}')[-1]:
                        title_elements.append(elem)

            console.print(f"[Debug] Found {len(title_elements)} title elements in playlist")

            for title in title_elements:
                try:
                    # Get title attributes with fallbacks
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

                    # Extract PrimaryAudioVideoClip details - handle both namespaced and non-namespaced
                    clips = []
                    try:
                        if namespace:
                            clips = title.findall(".//ns:PrimaryAudioVideoClip", namespaces=namespace)
                        else:
                            clips = title.findall(".//PrimaryAudioVideoClip")
                    except Exception:
                        # Try direct search without path
                        for child in title.iter():
                            if child.tag.endswith('PrimaryAudioVideoClip'):
                                clips.append(child)

                    for clip in clips:
                        clip_data = {
                            "src": clip.get("src"),
                            "titleTimeBegin": clip.get("titleTimeBegin"),
                            "titleTimeEnd": clip.get("titleTimeEnd"),
                            "seamless": clip.get("seamless"),
                            "audioTracks": [],
                            "subtitleTracks": [],
                        }

                        # Extract Audio tracks within PrimaryAudioVideoClip
                        audio_tracks = []
                        try:
                            if namespace:
                                audio_tracks = clip.findall(".//ns:Audio", namespaces=namespace)
                            else:
                                audio_tracks = clip.findall(".//Audio")
                        except Exception:
                            # Try direct search
                            for child in clip.iter():
                                if child.tag.endswith('Audio'):
                                    audio_tracks.append(child)

                        for audio in audio_tracks:
                            clip_data["audioTracks"].append({
                                "track": audio.get("track"),
                                "streamNumber": audio.get("streamNumber"),
                                "mediaAttr": audio.get("mediaAttr"),
                                "description": audio.get("description"),
                            })

                        # Extract Subtitle tracks - similar approach
                        subtitle_tracks = []
                        try:
                            if namespace:
                                subtitle_tracks = clip.findall(".//ns:Subtitle", namespaces=namespace)
                            else:
                                subtitle_tracks = clip.findall(".//Subtitle")
                        except Exception:
                            for child in clip.iter():
                                if child.tag.endswith('Subtitle'):
                                    subtitle_tracks.append(child)

                        for subtitle in subtitle_tracks:
                            clip_data["subtitleTracks"].append({
                                "track": subtitle.get("track"),
                                "streamNumber": subtitle.get("streamNumber"),
                                "mediaAttr": subtitle.get("mediaAttr"),
                                "description": subtitle.get("description"),
                            })

                        title_data["primaryClips"].append(clip_data)

                    # Extract chapter details with error handling
                    try:
                        chapters = []
                        if namespace:
                            chapters = title.findall(".//ns:ChapterList/ns:Chapter", namespaces=namespace)
                        else:
                            chapters = title.findall(".//ChapterList/Chapter")

                        if not chapters:
                            # Try alternative paths
                            chapters = []
                            for node in title.iter():
                                if node.tag.endswith('Chapter'):
                                    chapters.append(node)

                        for chapter in chapters:
                            title_data["chapters"].append({
                                "displayName": chapter.get("displayName", ""),
                                "titleTimeBegin": chapter.get("titleTimeBegin", "00:00:00:00"),
                            })
                    except Exception as e:
                        console.print(f"[yellow]Warning: Error extracting chapters: {e}")

                    # Extract TrackNavigationList details with error handling
                    try:
                        # Audio tracks in TrackNavigationList
                        audio_nav_tracks = []
                        if namespace:
                            audio_nav_tracks = title.findall(".//ns:TrackNavigationList/ns:AudioTrack", namespaces=namespace)
                        else:
                            audio_nav_tracks = title.findall(".//TrackNavigationList/AudioTrack")

                        if not audio_nav_tracks:
                            # Try alternative path
                            for node in title.iter():
                                if node.tag.endswith('AudioTrack') and node.tag != 'Audio':
                                    audio_nav_tracks.append(node)

                        for audio_track in audio_nav_tracks:
                            try:
                                langcode = audio_track.get("langcode", "")
                                # Extract the 2-letter language code before the colon or asterisk
                                if ":" in langcode:
                                    langcode_short = langcode.split(":")[0]
                                elif "*" in langcode:
                                    langcode_short = "und"  # undefined for asterisk
                                else:
                                    langcode_short = langcode

                                # Try to convert the language code, with fallback for invalid codes
                                try:
                                    if langcode_short in self.language_code_map:
                                        langcode_short = self.language_code_map[langcode_short]

                                    if langcode_short and langcode_short != "*" and langcode_short != "und":
                                        try:
                                            language_name = Language.get(langcode_short).display_name()
                                        except (KeyError, ValueError):
                                            language_name = langcode_short.upper()
                                    else:
                                        language_name = "Undefined"
                                except Exception:
                                    language_name = "Unknown"

                                title_data["audioTracks"].append({
                                    "track": audio_track.get("track"),
                                    "langcode": langcode_short,
                                    "language": language_name,
                                    "description": audio_track.get("description", ""),
                                    "selectable": audio_track.get("selectable", "true"),
                                })
                            except Exception as e:
                                console.print(f"[yellow]Warning: Error processing audio track: {e}")

                        # Subtitle tracks in TrackNavigationList
                        subtitle_nav_tracks = []
                        if namespace:
                            subtitle_nav_tracks = title.findall(".//ns:TrackNavigationList/ns:SubtitleTrack", namespaces=namespace)
                        else:
                            subtitle_nav_tracks = title.findall(".//TrackNavigationList/SubtitleTrack")

                        if not subtitle_nav_tracks:
                            # Alternative search
                            for node in title.iter():
                                if node.tag.endswith('SubtitleTrack'):
                                    subtitle_nav_tracks.append(node)

                        for subtitle_track in subtitle_nav_tracks:
                            try:
                                langcode = subtitle_track.get("langcode", "")
                                if ":" in langcode:
                                    langcode_short = langcode.split(":")[0]
                                elif "*" in langcode:
                                    langcode_short = "und"
                                else:
                                    langcode_short = langcode

                                try:
                                    if langcode_short in self.language_code_map:
                                        langcode_short = self.language_code_map[langcode_short]

                                    if langcode_short and langcode_short != "*" and langcode_short != "und":
                                        try:
                                            language_name = Language.get(langcode_short).display_name()
                                        except (KeyError, ValueError):
                                            language_name = langcode_short.upper()
                                    else:
                                        language_name = "Undefined"
                                except Exception:
                                    language_name = "Unknown"

                                title_data["subtitleTracks"].append({
                                    "track": subtitle_track.get("track"),
                                    "langcode": langcode_short,
                                    "language": language_name,
                                    "selectable": subtitle_track.get("selectable", "true"),
                                })
                            except Exception as e:
                                console.print(f"[yellow]Warning: Error processing subtitle track: {e}")
                    except Exception as e:
                        console.print(f"[yellow]Warning: Error extracting track navigation list: {e}")

                    # Extract ApplicationSegment with error handling
                    try:
                        app_segments = []
                        if namespace:
                            app_segments = title.findall(".//ns:ApplicationSegment", namespaces=namespace)
                        else:
                            app_segments = title.findall(".//ApplicationSegment")

                        if not app_segments:
                            for node in title.iter():
                                if node.tag.endswith('ApplicationSegment'):
                                    app_segments.append(node)

                        for app_segment in app_segments:
                            app_data = {
                                "src": app_segment.get("src", ""),
                                "titleTimeBegin": app_segment.get("titleTimeBegin", ""),
                                "titleTimeEnd": app_segment.get("titleTimeEnd", ""),
                                "sync": app_segment.get("sync", ""),
                                "zOrder": app_segment.get("zOrder", ""),
                                "resources": [],
                            }

                            # Extract ApplicationResource details
                            resources = []
                            if namespace:
                                resources = app_segment.findall(".//ns:ApplicationResource", namespaces=namespace)
                            else:
                                resources = app_segment.findall(".//ApplicationResource")

                            if not resources:
                                for node in app_segment.iter():
                                    if node.tag.endswith('ApplicationResource'):
                                        resources.append(node)

                            for resource in resources:
                                app_data["resources"].append({
                                    "src": resource.get("src", ""),
                                    "size": resource.get("size", ""),
                                    "priority": resource.get("priority", ""),
                                    "multiplexed": resource.get("multiplexed", ""),
                                })

                            title_data["applicationSegments"].append(app_data)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Error extracting application segments: {e}")

                    # Add the fully extracted title data to the list
                    titles.append(title_data)

                except Exception as e:
                    console.print(f"[yellow]Warning: Error processing title: {e}")
                    continue

        except ET.ParseError as e:
            console.print(f"[red]Error parsing XPL file: {e}")
        except Exception as e:
            console.print(f"[red]Unexpected error parsing HD DVD playlist: {e}")
            import traceback
            console.print(traceback.format_exc())

        console.print(f"[green]Successfully parsed {len(titles)} valid titles from playlist")
        return titles

    def timecode_to_seconds(self, timecode):
        parts = timecode.split(":")
        if len(parts) != 4:
            return 0
        hours, minutes, seconds, frames = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds

    def format_playlist_for_description(self, playlist_data, include_xml=True, xml_string=None):
        """Format playlist data for description - raw XML only mode."""
        output = []

        # Get the selected title ID to extract only that portion
        if playlist_data and len(playlist_data) > 0:
            selected_title_id = playlist_data[0].get("id")
            selected_title_number = playlist_data[0].get("titleNumber")

            # If we have the XML content and a title ID to look for
            if include_xml and xml_string and (selected_title_id or selected_title_number):
                # Try to find and extract just the XML for this specific title
                try:
                    # Look for the title element with matching ID or number
                    id_pattern = rf'<Title[^>]*\bid="{selected_title_id}".*?</Title>'
                    number_pattern = rf'<Title[^>]*\btitleNumber="{selected_title_number}".*?</Title>'

                    # Try to match the title by ID first, then by number
                    title_match = re.search(id_pattern, xml_string, re.DOTALL)
                    if not title_match and selected_title_number:
                        title_match = re.search(number_pattern, xml_string, re.DOTALL)

                    # If we found a match, just use that title's XML
                    if title_match:
                        output.append(title_match.group(0))
                    else:
                        # If no specific match found, include the whole XML
                        output.append(xml_string)
                except Exception:
                    # Fallback to the full XML on any error
                    output.append(xml_string)
            elif include_xml and xml_string:
                # No specific title info, include the whole XML
                output.append(xml_string)

        return "\n".join(output)
