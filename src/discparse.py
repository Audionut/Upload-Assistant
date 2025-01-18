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
from src.console import console


class DiscParse():
    def __init__(self):
        pass

    """
    Get and parse bdinfo
    """
    async def get_bdinfo(self, meta, discs, folder_id, base_dir, meta_discs):
        save_dir = f"{base_dir}/tmp/{folder_id}"
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)

        for i in range(len(discs)):
            bdinfo_text = None
            path = os.path.abspath(discs[i]['path'])

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
                                for item in playlist_data.play_items:
                                    duration += (item.outtime - item.intime) / 45000
                                    try:
                                        m2ts_file = os.path.join(stream_directory, item.clip_information_filename.strip() + ".m2ts")
                                        size = os.path.getsize(m2ts_file) if os.path.exists(m2ts_file) else 0
                                        items.append({"file": m2ts_file, "size": size})
                                    except AttributeError as e:
                                        console.print(f"[bold red]Error accessing clip information for item in {file_name}: {e}")

                                # Save playlists with duration >= 3 minutes
                                if duration >= 180:
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

                # Allow user to select playlists
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    console.print("[bold green]Available playlists:")
                    for idx, playlist in enumerate(valid_playlists):
                        duration_str = f"{int(playlist['duration'] // 3600)}h {int((playlist['duration'] % 3600) // 60)}m {int(playlist['duration'] % 60)}s"
                        items_str = ', '.join(f"{os.path.basename(item['file'])} ({item['size'] // (1024 * 1024)} MB)" for item in playlist['items'])
                        console.print(f"[{idx}] {playlist['file']} - {duration_str} - {items_str}")
                    console.print("[bold yellow]Enter playlist numbers separated by commas, or 'ALL' to select all:")

                    user_input = input("Select playlists: ").strip()

                    if user_input.lower() == "all":
                        selected_playlists = valid_playlists
                    else:
                        try:
                            selected_indices = [int(x) for x in user_input.split(',')]
                            selected_playlists = [valid_playlists[idx] for idx in selected_indices if 0 <= idx < len(valid_playlists)]
                        except ValueError:
                            console.print("[bold red]Invalid input. Skipping playlist selection.")
                            continue
                else:
                    # Select the playlist with the largest total size
                    console.print("[yellow]Selecting the playlist with the largest size:")
                    selected_playlists = [max(valid_playlists, key=lambda p: sum(item['size'] for item in p['items']))]

                for idx, playlist in enumerate(selected_playlists):
                    console.print(f"[bold green]Scanning playlist {playlist['file']} with duration {int(playlist['duration'] // 3600)} hours {int((playlist['duration'] % 3600) // 60)} minutes {int(playlist['duration'] % 60)} seconds")
                    playlist_number = playlist['file'].replace(".mpls", "")
                    playlist_report_path = os.path.join(save_dir, f"{playlist_number}_FULL.txt")

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

                            with open(bdinfo_text, 'r') as f:
                                text = f.read()
                                result = text.split("QUICK SUMMARY:", 2)
                                files = result[0].split("FILES:", 2)[1].split("CHAPTERS:", 2)[0].split("-------------")
                                result2 = result[1].rstrip(" \n")
                                result = result2.split("********************", 1)
                                bd_summary = result[0].rstrip(" \n")

                            with open(bdinfo_text, 'r') as f:
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

                            with open(summary_file, 'w') as f:
                                f.write(bd_summary.strip())
                            with open(extended_summary_file, 'w') as f:
                                f.write(ext_bd_summary.strip())

                            bdinfo = self.parse_bdinfo(bd_summary, files[1], path)

                            # Prompt user for custom label if conditions are met
                            if len(selected_playlists) > 1:
                                current_label = bdinfo.get('label', f"Playlist {idx}")
                                console.print(f"[bold yellow]Current label for playlist {playlist['file']}: {current_label}")

                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    console.print("[bold green]You can create a custom Edition for this playlist.")
                                    user_input = input(f"Enter a new Edition for playlist {playlist['file']} (or press Enter to keep the current label): ").strip()
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
            each['vob_mi'] = MediaInfo.parse(os.path.basename(vob), output='STRING', full=False, mediainfo_options={'inform_version': '1'}).replace('\r\n', '\n')
            each['ifo_mi'] = MediaInfo.parse(os.path.basename(ifo), output='STRING', full=False, mediainfo_options={'inform_version': '1'}).replace('\r\n', '\n')
            each['vob_mi_full'] = MediaInfo.parse(vob, output='STRING', full=False, mediainfo_options={'inform_version': '1'}).replace('\r\n', '\n')
            each['ifo_mi_full'] = MediaInfo.parse(ifo, output='STRING', full=False, mediainfo_options={'inform_version': '1'}).replace('\r\n', '\n')

            size = sum(os.path.getsize(f) for f in os.listdir('.') if os.path.isfile(f)) / float(1 << 30)
            if size <= 7.95:
                dvd_size = "DVD9"
                if size <= 4.37:
                    dvd_size = "DVD5"
            each['size'] = dvd_size
        return discs

    async def get_hddvd_info(self, discs):
        for each in discs:
            path = each.get('path')
            os.chdir(path)
            files = glob("*.EVO")
            size = 0
            largest = files[0]
            # get largest file from files
            for file in files:
                file_size = os.path.getsize(file)
                if file_size > size:
                    largest = file
                    size = file_size
            each['evo_mi'] = MediaInfo.parse(os.path.basename(largest), output='STRING', full=False, mediainfo_options={'inform_version': '1'})
            each['largest_evo'] = os.path.abspath(f"{path}/{largest}")
        return discs
