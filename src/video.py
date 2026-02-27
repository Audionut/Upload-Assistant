# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import os
import re
import sys
from typing import Any, Optional, cast

import aiofiles
import cli_ui

from src.cleanup import cleanup_manager
from src.console import console
from src.exportmi import mi_resolution


class VideoManager:
    async def get_uhd(self, type: str, guess: Any, resolution: str, path: str) -> str:
        try:
            guess_dict = cast(dict[str, Any], guess)
            source = guess_dict['Source']
            other = guess_dict['Other']
        except Exception:
            source = ""
            other = ""
        uhd = ""
        if source == 'Blu-ray' and other == "Ultra HD" or source == "Ultra HD Blu-ray" or "UHD" in path:
            uhd = "UHD"
        elif type in ("DISC", "REMUX", "ENCODE", "WEBRIP"):
            uhd = ""

        if type in ("DISC", "REMUX", "ENCODE") and resolution == "2160p":
            uhd = "UHD"

        return uhd

    async def get_hdr(self, mi: Any, bdinfo: Optional[Any]) -> str:
        hdr = ""
        dv = ""
        if bdinfo is not None:  # Disks
            bdinfo_dict = cast(dict[str, Any], bdinfo)
            hdr_mi = bdinfo_dict['video'][0]['hdr_dv']
            if "HDR10+" in hdr_mi:
                hdr = "HDR10+"
            elif hdr_mi == "HDR10":
                hdr = "HDR"
            try:
                if bdinfo_dict['video'][1]['hdr_dv'] == "Dolby Vision":
                    dv = "DV"
            except Exception:
                pass
        else:
            mi_dict = cast(dict[str, Any], mi)
            video_track = mi_dict['media']['track'][1]
            try:
                hdr_mi = video_track['colour_primaries']
                if hdr_mi in ("BT.2020", "REC.2020"):
                    hdr = ""
                    hdr_fields = [
                        video_track.get('HDR_Format_Compatibility', ''),
                        video_track.get('HDR_Format_String', ''),
                        video_track.get('HDR_Format', '')
                    ]
                    hdr_format_string = next((v for v in hdr_fields if isinstance(v, str) and v.strip()), "")
                    if "HDR10+" in hdr_format_string:
                        hdr = "HDR10+"
                    elif "HDR10" in hdr_format_string or "SMPTE ST 2094 App 4" in hdr_format_string:
                        hdr = "HDR"
                    if hdr_format_string and "HLG" in hdr_format_string:
                        hdr = f"{hdr} HLG"
                    if hdr_format_string == "" and "PQ" in (video_track.get('transfer_characteristics'), video_track.get('transfer_characteristics_Original', None)):
                        hdr = "PQ10"
                    transfer_characteristics = video_track.get('transfer_characteristics_Original', None)
                    if "HLG" in transfer_characteristics:
                        hdr = "HLG"
                    if hdr != "HLG" and "BT.2020 (10-bit)" in transfer_characteristics:
                        hdr = "WCG"
            except Exception:
                pass

            try:
                if "Dolby Vision" in video_track.get('HDR_Format', '') or "Dolby Vision" in video_track.get('HDR_Format_String', ''):
                    dv = "DV"
            except Exception:
                pass

        hdr = f"{dv} {hdr}".strip()
        return hdr

    async def get_video_codec(self, bdinfo: Any) -> str:
        codecs = {
            "MPEG-2 Video": "MPEG-2",
            "MPEG-4 AVC Video": "AVC",
            "MPEG-H HEVC Video": "HEVC",
            "VC-1 Video": "VC-1"
        }
        bdinfo_dict = cast(dict[str, Any], bdinfo)
        codec = codecs.get(bdinfo_dict['video'][0]['codec'], "")
        return codec

    async def get_video_encode(self, mi: Any, type: str, bdinfo: Any) -> tuple[str, str, bool, str]:
        video_encode = ""
        codec = ""
        bit_depth = '0'
        has_encode_settings = False
        try:
            mi_dict = cast(dict[str, Any], mi)
            format = mi_dict['media']['track'][1]['Format']
            format_profile = mi_dict['media']['track'][1].get('Format_Profile', format)
            if mi_dict['media']['track'][1].get('Encoded_Library_Settings', None):
                has_encode_settings = True
            bit_depth = mi_dict['media']['track'][1].get('BitDepth', '0')
            encoded_library_name = mi_dict['media']['track'][1].get('Encoded_Library_Name', None)
        except Exception:
            bdinfo_dict = cast(dict[str, Any], bdinfo)
            format = bdinfo_dict['video'][0]['codec']
            format_profile = bdinfo_dict['video'][0]['profile']
            encoded_library_name = None
        if format in ('AV1', 'VP9', 'VC-1'):
            codec = format
        elif type in ("ENCODE", "WEBRIP", "DVDRIP"):  # ENCODE or WEBRIP or DVDRIP
            if format == 'AVC':
                codec = 'x264'
            elif format == 'HEVC':
                codec = 'x265'
            elif format == 'MPEG-4 Visual' and encoded_library_name:
                if 'xvid' in encoded_library_name.lower():
                    codec = 'XviD'
                elif 'divx' in encoded_library_name.lower():
                    codec = 'DivX'
        elif type in ('WEBDL', 'HDTV'):  # WEB-DL
            if format == 'AVC':
                codec = 'H.264'
            elif format == 'HEVC':
                codec = 'H.265'

            if type == 'HDTV' and has_encode_settings is True:
                codec = codec.replace('H.', 'x')
        profile = "Hi10P" if format_profile == 'High 10' else ""
        video_encode = f"{profile} {codec}"
        video_codec = format
        if video_codec == "MPEG Video":
            mi_dict = cast(dict[str, Any], mi)
            video_codec = f"MPEG-{mi_dict['media']['track'][1].get('Format_Version')}"
        return video_encode, video_codec, has_encode_settings, bit_depth

    async def get_video(self, videoloc: str, mode: str, sorted_filelist: bool = False, debug: bool = False) -> tuple[str, list[str]]:
        filelist: list[str] = []
        videoloc = os.path.abspath(videoloc)
        if debug:
            console.print(f"[blue]Video location: [yellow]{videoloc}[/yellow][/blue]")
        video = ""
        if os.path.isdir(videoloc):
            if debug:
                console.print("[blue]Scanning directory for video files...[/blue]")
            try:
                # entries = [e for e in os.listdir(videoloc) if os.path.isfile(os.path.join(videoloc, e))]
                entries = [os.path.join(dp, f) for dp, dn, filenames in os.walk(videoloc) for f in filenames ]
                #entries = list (os.walk(videoloc))
            except Exception:
                entries = []

            video_exts = {'.mkv', '.mp4', '.ts'}
            for file in entries:
                fname_lower = file.lower()
                ext = os.path.splitext(file)[1].lower()
                if ext not in video_exts:
                    continue

                # Skip obvious sample files unless explicitly marked with !sample
                if 'sample' in fname_lower and '!sample' not in fname_lower:
                    continue

                filelist.append(os.path.abspath(os.path.join(videoloc, file)))

            filelist = sorted(filelist)
            if debug and filelist:
                console.print(f"[blue]Found {len(filelist)} video files in directory.[/blue]")
            if len(filelist) > 1:
                for f in list(filelist):
                    if 'sample' in os.path.basename(f).lower() and '!sample' not in os.path.basename(f).lower():
                        console.print("[green]Filelist:[/green]")
                        for tf in filelist:
                            console.print(f"[cyan]{tf}")
                        console.print(f"[bold red]Possible sample file detected in filelist!: [yellow]{f}")
                        try:
                            if cli_ui.ask_yes_no("Do you want to remove it?", default=True):
                                filelist.remove(f)
                        except EOFError:
                            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                            await cleanup_manager.cleanup()
                            cleanup_manager.reset_terminal()
                            sys.exit(1)
            for file in filelist:
                if any(tag in file for tag in ['{tmdb-', '{imdb-', '{tvdb-']):
                    console.print(f"[bold red]This looks like some *arr renamed file which is not allowed: [yellow]{file}")
                    try:
                        if cli_ui.ask_yes_no("Do you want to upload with this file?", default=False):
                            pass
                        else:
                            console.print("[red]Exiting on user request[/red]")
                            await cleanup_manager.cleanup()
                            cleanup_manager.reset_terminal()
                            sys.exit(1)
                    except EOFError:
                        console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                        await cleanup_manager.cleanup()
                        cleanup_manager.reset_terminal()
                        sys.exit(1)
            try:
                video = sorted(filelist, key=os.path.getsize, reverse=True)[0] if sorted_filelist else sorted(filelist)[0]
            except IndexError:
                console.print("[bold red]No Video files found")
                if mode == 'cli':
                    exit()
                return "", []
        else:
            video = videoloc
            filelist.append(videoloc)
            if any(tag in videoloc for tag in ['{tmdb-', '{imdb-', '{tvdb-']):
                console.print(f"[bold red]This looks like some *arr renamed file which is not allowed: [yellow]{videoloc}")
                try:
                    if cli_ui.ask_yes_no("Do you want to upload with this file?", default=False):
                        pass
                    else:
                        console.print("[red]Exiting on user request[/red]")
                        await cleanup_manager.cleanup()
                        cleanup_manager.reset_terminal()
                        sys.exit(1)
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup_manager.cleanup()
                    cleanup_manager.reset_terminal()
                    sys.exit(1)
        filelist = sorted(filelist, key=os.path.getsize, reverse=True) if sorted_filelist else sorted(filelist)
        return video, filelist

    async def get_resolution(self, guess: Any, folder_id: str, base_dir: str) -> tuple[str, bool]:
        hfr = False
        async with aiofiles.open(f'{base_dir}/tmp/{folder_id}/MediaInfo.json', encoding='utf-8') as f:
            mi = cast(dict[str, Any], json.loads(await f.read()))
            try:
                width = mi['media']['track'][1]['Width']
                height = mi['media']['track'][1]['Height']
            except Exception:
                width = 0
                height = 0

            framerate = mi['media']['track'][1].get('FrameRate')
            if not framerate or framerate == '0':
                framerate = mi['media']['track'][1].get('FrameRate_Original')
            if not framerate or framerate == '0':
                framerate = mi['media']['track'][1].get('FrameRate_Num')
            if framerate:
                try:
                    if int(float(framerate)) > 30:
                        hfr = True
                except Exception:
                    hfr = False
            else:
                framerate = "24.000"

            try:
                scan = mi['media']['track'][1]['ScanType']
            except Exception:
                scan = "Progressive"
            if not scan or scan == "Progressive":
                scan = "p"
            elif scan == "Interlaced":
                scan = 'i'
            elif framerate == "25.000":
                scan = "p"
            else:
                # Fallback using regex on meta['uuid'] - mainly for HUNO fun and games.
                match = re.search(r'\b(1080p|720p|2160p|576p|480p)\b', folder_id, re.IGNORECASE)
                scan = "p" if match else "i"  # Assume progressive based on common resolution markers
            width_list = [3840, 2560, 1920, 1280, 1024, 854, 720, 15360, 7680, 0]
            height_list = [2160, 1440, 1080, 720, 576, 540, 480, 8640, 4320, 0]
            width = await self.closest(width_list, int(width))
            height = await self.closest(height_list, int(height))
            res = f"{width}x{height}{scan}"
            resolution = await mi_resolution(res, guess, width, scan)
        return resolution, hfr

    async def closest(self, lst: list[int], K: int) -> int:
        # Get closest, but not over
        lst = sorted(lst)
        mi_input = K
        res = 0
        for each in lst:
            if mi_input > each:
                pass
            else:
                res = each
                break
        return res

    async def get_type(self, video: str, _scene: bool, is_disc: Optional[str], meta: dict[str, Any]) -> str:
        if meta.get('manual_type'):
            type = cast(str, meta.get('manual_type'))
        else:
            filename = os.path.basename(video).lower()
            if "remux" in filename:
                type = "REMUX"
            elif any(word in filename for word in [" web ", ".web.", "web-dl", "webdl"]):
                type = "WEBDL"
            elif "webrip" in filename:
                type = "WEBRIP"
            # elif scene == True:
                # type = "ENCODE"
            elif "hdtv" in filename:
                type = "HDTV"
            elif is_disc is not None:
                type = "DISC"
            elif "dvdrip" in filename:
                type = "DVDRIP"
                # exit()
            else:
                type = "ENCODE"
        return type

    async def is_3d(self, bdinfo: Optional[Any]) -> str:
        if bdinfo is not None:
            if bdinfo['video'][0]['3d'] != "":
                return "3D"
            else:
                return ""
        else:
            return ""

    async def is_sd(self, resolution: str) -> int:
        sd = 1 if resolution in ("480i", "480p", "576i", "576p", "540p") else 0
        return sd

    async def get_video_duration(self, meta: dict[str, Any]) -> Optional[int]:
        if meta.get('is_disc') != "BDMV" and meta.get('mediainfo', {}).get('media', {}).get('track'):
            general_track = next((track for track in meta['mediainfo']['media']['track']
                                  if track.get('@type') == 'General'), None)

            if general_track and general_track.get('Duration'):
                try:
                    media_duration_seconds = float(general_track['Duration'])
                    formatted_duration = int(media_duration_seconds // 60)
                    return formatted_duration
                except ValueError:
                    if meta['debug']:
                        console.print(f"[red]Invalid duration value: {general_track['Duration']}[/red]")
                    return None
            else:
                if meta['debug']:
                    console.print("[red]No valid duration found in MediaInfo General track[/red]")
                return None
        else:
            return None

    async def get_container(self, meta: dict[str, Any]) -> str:
        if meta.get('is_disc', '') == 'BDMV':
            return 'm2ts'
        elif meta.get('is_disc', '') == 'HDDVD':
            return 'evo'
        elif meta.get('is_disc', '') == 'DVD':
            return 'vob'
        else:
            file_list = meta.get('filelist', [])

            if not file_list:
                console.print("[red]No files found to determine container[/red]")
                return ''

            try:
                largest_file_path = max(file_list, key=os.path.getsize)
            except (OSError, ValueError) as e:
                console.print(f"[red]Error getting container for file: {e}[/red]")
                return ''

            extension = os.path.splitext(largest_file_path)[1]
            return extension.lstrip('.').lower() if extension else ''


video_manager = VideoManager()
