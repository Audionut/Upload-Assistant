# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import aiofiles
import json
import os
import platform
import subprocess
from pymediainfo import MediaInfo
from src.console import console


def setup_mediainfo_library(base_dir, debug=False):
    system = platform.system().lower()

    if system == 'windows':
        cli_path = os.path.join(base_dir, "bin", "MI", "windows", "MediaInfo.exe")
        if os.path.exists(cli_path):
            if debug:
                console.print(f"[blue]Windows MediaInfo CLI: {cli_path} (found)[/blue]")
            return {
                'cli': cli_path,
                'lib': None,  # Windows uses CLI only
                'lib_dir': None
            }
        else:
            if debug:
                console.print(f"[yellow]Windows MediaInfo CLI: {cli_path} (not found)[/yellow]")
            return None

    elif system == 'linux':
        if base_dir.endswith("bin/MI") or base_dir.endswith("bin\\MI"):
            lib_dir = os.path.join(base_dir, "linux")
        else:
            lib_dir = os.path.join(base_dir, "bin", "MI", "linux")

        mediainfo_lib = os.path.join(lib_dir, "libmediainfo.so.0")
        mediainfo_cli = os.path.join(lib_dir, "mediainfo")
        cli_available = os.path.exists(mediainfo_cli)
        lib_available = os.path.exists(mediainfo_lib)

        if debug:
            console.print(f"[blue]MediaInfo CLI binary: {mediainfo_cli} ({'found' if cli_available else 'not found'})[/blue]")
            console.print(f"[blue]MediaInfo library: {mediainfo_lib} ({'found' if lib_available else 'not found'})[/blue]")

        if lib_available:
            # Set library directory for LD_LIBRARY_PATH
            current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
            if lib_dir not in current_ld_path:
                if current_ld_path:
                    os.environ['LD_LIBRARY_PATH'] = f"{lib_dir}:{current_ld_path}"
                else:
                    os.environ['LD_LIBRARY_PATH'] = lib_dir
                if debug:
                    console.print(f"[blue]Updated LD_LIBRARY_PATH to include: {lib_dir}[/blue]")

        return {
            'cli': mediainfo_cli if cli_available else None,
            'lib': mediainfo_lib if lib_available else None,
            'lib_dir': lib_dir
        }
    return None


async def mi_resolution(res, guess, width, scan, height, actual_height):
    res_map = {
        "3840x2160p": "2160p", "2160p": "2160p",
        "2560x1440p": "1440p", "1440p": "1440p",
        "1920x1080p": "1080p", "1080p": "1080p",
        "1920x1080i": "1080i", "1080i": "1080i",
        "1280x720p": "720p", "720p": "720p",
        "1280x540p": "720p", "1280x576p": "720p",
        "1024x576p": "576p", "576p": "576p",
        "1024x576i": "576i", "576i": "576i",
        "960x540p": "540p", "540p": "540p",
        "960x540i": "540i", "540i": "540i",
        "854x480p": "480p", "480p": "480p",
        "854x480i": "480i", "480i": "480i",
        "720x576p": "576p", "576p": "576p",
        "720x576i": "576i", "576i": "576i",
        "720x480p": "480p", "480p": "480p",
        "720x480i": "480i", "480i": "480i",
        "15360x8640p": "8640p", "8640p": "8640p",
        "7680x4320p": "4320p", "4320p": "4320p",
        "OTHER": "OTHER"}
    resolution = res_map.get(res, None)
    if resolution is None:
        try:
            resolution = guess['screen_size']
            # Check if the resolution from guess exists in our map
            if resolution not in res_map:
                # If not in the map, use width-based mapping
                width_map = {
                    '3840p': '2160p',
                    '2560p': '1550p',
                    '1920p': '1080p',
                    '1920i': '1080i',
                    '1280p': '720p',
                    '1024p': '576p',
                    '1024i': '576i',
                    '960p': '540p',
                    '960i': '540i',
                    '854p': '480p',
                    '854i': '480i',
                    '720p': '576p',
                    '720i': '576i',
                    '15360p': '4320p',
                    'OTHERp': 'OTHER'
                }
                resolution = width_map.get(f"{width}{scan}", "OTHER")
        except Exception:
            # If we can't get from guess, use width-based mapping
            width_map = {
                '3840p': '2160p',
                '2560p': '1550p',
                '1920p': '1080p',
                '1920i': '1080i',
                '1280p': '720p',
                '1024p': '576p',
                '1024i': '576i',
                '960p': '540p',
                '960i': '540i',
                '854p': '480p',
                '854i': '480i',
                '720p': '576p',
                '720i': '576i',
                '15360p': '4320p',
                'OTHERp': 'OTHER'
            }
            resolution = width_map.get(f"{width}{scan}", "OTHER")

    # Final check to ensure we have a valid resolution
    if resolution not in res_map:
        resolution = "OTHER"

    return resolution


async def exportInfo(video, isdir, folder_id, base_dir, export_text, is_dvd=False, debug=False):

    def filter_mediainfo(data):
        filtered = {
            "creatingLibrary": data.get("creatingLibrary"),
            "media": {
                "@ref": data["media"]["@ref"],
                "track": []
            }
        }

        for track in data["media"]["track"]:
            if track["@type"] == "General":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "UniqueID": track.get("UniqueID", {}),
                    "VideoCount": track.get("VideoCount", {}),
                    "AudioCount": track.get("AudioCount", {}),
                    "TextCount": track.get("TextCount", {}),
                    "MenuCount": track.get("MenuCount", {}),
                    "FileExtension": track.get("FileExtension", {}),
                    "Format": track.get("Format", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "FileSize": track.get("FileSize", {}),
                    "Duration": track.get("Duration", {}),
                    "OverallBitRate": track.get("OverallBitRate", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "IsStreamable": track.get("IsStreamable", {}),
                    "File_Created_Date": track.get("File_Created_Date", {}),
                    "File_Created_Date_Local": track.get("File_Created_Date_Local", {}),
                    "File_Modified_Date": track.get("File_Modified_Date", {}),
                    "File_Modified_Date_Local": track.get("File_Modified_Date_Local", {}),
                    "Encoded_Application": track.get("Encoded_Application", {}),
                    "Encoded_Library": track.get("Encoded_Library", {}),
                    "extra": track.get("extra", {}),
                })
            elif track["@type"] == "Video":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "Format_Profile": track.get("Format_Profile", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "Format_Level": track.get("Format_Level", {}),
                    "Format_Tier": track.get("Format_Tier", {}),
                    "HDR_Format": track.get("HDR_Format", {}),
                    "HDR_Format_Version": track.get("HDR_Format_Version", {}),
                    "HDR_Format_String": track.get("HDR_Format_String", {}),
                    "HDR_Format_Profile": track.get("HDR_Format_Profile", {}),
                    "HDR_Format_Level": track.get("HDR_Format_Level", {}),
                    "HDR_Format_Settings": track.get("HDR_Format_Settings", {}),
                    "HDR_Format_Compression": track.get("HDR_Format_Compression", {}),
                    "HDR_Format_Compatibility": track.get("HDR_Format_Compatibility", {}),
                    "CodecID": track.get("CodecID", {}),
                    "CodecID_Hint": track.get("CodecID_Hint", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate": track.get("BitRate", {}),
                    "Width": track.get("Width", {}),
                    "Height": track.get("Height", {}),
                    "Stored_Height": track.get("Stored_Height", {}),
                    "Sampled_Width": track.get("Sampled_Width", {}),
                    "Sampled_Height": track.get("Sampled_Height", {}),
                    "PixelAspectRatio": track.get("PixelAspectRatio", {}),
                    "DisplayAspectRatio": track.get("DisplayAspectRatio", {}),
                    "FrameRate_Mode": track.get("FrameRate_Mode", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameRate_Original": track.get("FrameRate_Original", {}),
                    "FrameRate_Num": track.get("FrameRate_Num", {}),
                    "FrameRate_Den": track.get("FrameRate_Den", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "Standard": track.get("Standard", {}),
                    "ColorSpace": track.get("ColorSpace", {}),
                    "ChromaSubsampling": track.get("ChromaSubsampling", {}),
                    "ChromaSubsampling_Position": track.get("ChromaSubsampling_Position", {}),
                    "BitDepth": track.get("BitDepth", {}),
                    "ScanType": track.get("ScanType", {}),
                    "ScanOrder": track.get("ScanOrder", {}),
                    "Delay": track.get("Delay", {}),
                    "Delay_Source": track.get("Delay_Source", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Language": track.get("Language", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                    "colour_description_present": track.get("colour_description_present", {}),
                    "colour_description_present_Source": track.get("colour_description_present_Source", {}),
                    "colour_range": track.get("colour_range", {}),
                    "colour_range_Source": track.get("colour_range_Source", {}),
                    "colour_primaries": track.get("colour_primaries", {}),
                    "colour_primaries_Source": track.get("colour_primaries_Source", {}),
                    "transfer_characteristics": track.get("transfer_characteristics", {}),
                    "transfer_characteristics_Source": track.get("transfer_characteristics_Source", {}),
                    "transfer_characteristics_Original": track.get("transfer_characteristics_Original", {}),
                    "matrix_coefficients": track.get("matrix_coefficients", {}),
                    "matrix_coefficients_Source": track.get("matrix_coefficients_Source", {}),
                    "MasteringDisplay_ColorPrimaries": track.get("MasteringDisplay_ColorPrimaries", {}),
                    "MasteringDisplay_ColorPrimaries_Source": track.get("MasteringDisplay_ColorPrimaries_Source", {}),
                    "MasteringDisplay_Luminance": track.get("MasteringDisplay_Luminance", {}),
                    "MasteringDisplay_Luminance_Source": track.get("MasteringDisplay_Luminance_Source", {}),
                    "MaxCLL": track.get("MaxCLL", {}),
                    "MaxCLL_Source": track.get("MaxCLL_Source", {}),
                    "MaxFALL": track.get("MaxFALL", {}),
                    "MaxFALL_Source": track.get("MaxFALL_Source", {}),
                    "Encoded_Library_Settings": track.get("Encoded_Library_Settings", {}),
                    "Encoded_Library": track.get("Encoded_Library", {}),
                    "Encoded_Library_Name": track.get("Encoded_Library_Name", {}),
                })
            elif track["@type"] == "Audio":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "Format_Profile": track.get("Format_Profile", {}),
                    "Format_Settings": track.get("Format_Settings", {}),
                    "Format_Commercial_IfAny": track.get("Format_Commercial_IfAny", {}),
                    "Format_Settings_Endianness": track.get("Format_Settings_Endianness", {}),
                    "Format_AdditionalFeatures": track.get("Format_AdditionalFeatures", {}),
                    "CodecID": track.get("CodecID", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate_Mode": track.get("BitRate_Mode", {}),
                    "BitRate": track.get("BitRate", {}),
                    "Channels": track.get("Channels", {}),
                    "ChannelPositions": track.get("ChannelPositions", {}),
                    "ChannelLayout": track.get("ChannelLayout", {}),
                    "Channels_Original": track.get("Channels_Original", {}),
                    "ChannelLayout_Original": track.get("ChannelLayout_Original", {}),
                    "SamplesPerFrame": track.get("SamplesPerFrame", {}),
                    "SamplingRate": track.get("SamplingRate", {}),
                    "SamplingCount": track.get("SamplingCount", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "Compression_Mode": track.get("Compression_Mode", {}),
                    "Delay": track.get("Delay", {}),
                    "Delay_Source": track.get("Delay_Source", {}),
                    "Video_Delay": track.get("Video_Delay", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Title": track.get("Title", {}),
                    "Language": track.get("Language", {}),
                    "ServiceKind": track.get("ServiceKind", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                    "extra": track.get("extra", {}),
                })
            elif track["@type"] == "Text":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "@typeorder": track.get("@typeorder", {}),
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "CodecID": track.get("CodecID", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate": track.get("BitRate", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "ElementCount": track.get("ElementCount", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Title": track.get("Title", {}),
                    "Language": track.get("Language", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                })
            elif track["@type"] == "Menu":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "extra": track.get("extra", {}),
                })
        return filtered

    mediainfo_cmd = None
    mediainfo_config = None

    if is_dvd:
        if debug:
            console.print("[bold yellow]DVD detected, using specialized MediaInfo...")

        current_platform = platform.system().lower()

        if current_platform in ["linux", "windows"]:
            mediainfo_config = setup_mediainfo_library(base_dir, debug=debug)
            if mediainfo_config:
                if mediainfo_config['cli']:
                    mediainfo_cmd = mediainfo_config['cli']

                # Configure library if available (Linux only)
                if mediainfo_config['lib']:
                    try:
                        if hasattr(MediaInfo, '_library_file'):
                            MediaInfo._library_file = mediainfo_config['lib']

                        test_parse = MediaInfo.can_parse()
                        if debug:
                            console.print(f"[green]Configured specialized MediaInfo library (can_parse: {test_parse})[/green]")

                        if not test_parse:
                            if debug:
                                console.print("[yellow]Library test failed, may fall back to system MediaInfo[/yellow]")

                    except Exception as e:
                        if debug:
                            console.print(f"[yellow]Could not configure specialized library: {e}[/yellow]")
                else:
                    if debug:
                        console.print("[yellow]MediaInfo library not available[/yellow]")
            else:
                if debug:
                    console.print("[yellow]No specialized MediaInfo components found, using system MediaInfo[/yellow]")
        else:
            if debug:
                console.print(f"[yellow]DVD processing on {current_platform} not supported with specialized MediaInfo[/yellow]")

    if debug:
        console.print("[bold yellow]Exporting MediaInfo...")
    if not isdir:
        os.chdir(os.path.dirname(video))

    if mediainfo_cmd and is_dvd:
        try:
            cmd = [mediainfo_cmd, video]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                media_info = result.stdout
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        except subprocess.TimeoutExpired:
            console.print("[bold red]Specialized MediaInfo timed out (30s) - falling back to standard MediaInfo[/bold red]")
            media_info = MediaInfo.parse(video, output="STRING", full=False)
        except (subprocess.CalledProcessError, Exception) as e:
            console.print(f"[bold red]Error getting text from specialized MediaInfo: {e}")
            if debug and 'result' in locals():
                console.print(f"[red]Subprocess stderr: {result.stderr}[/red]")
                console.print(f"[red]Subprocess returncode: {result.returncode}[/red]")
            console.print("[bold yellow]Falling back to standard MediaInfo for text...")
            media_info = MediaInfo.parse(video, output="STRING", full=False)
    else:
        media_info = MediaInfo.parse(video, output="STRING", full=False)

    if isinstance(media_info, str):
        filtered_media_info = "\n".join(
            line for line in media_info.splitlines()
            if not line.strip().startswith("ReportBy") and not line.strip().startswith("Report created by ")
        )
    else:
        filtered_media_info = "\n".join(
            line for line in media_info.splitlines()
            if not line.strip().startswith("ReportBy") and not line.strip().startswith("Report created by ")
        )

    async with aiofiles.open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8') as export:
        await export.write(filtered_media_info.replace(video, os.path.basename(video)))
    async with aiofiles.open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8') as export_cleanpath:
        await export_cleanpath.write(filtered_media_info.replace(video, os.path.basename(video)))
    if debug:
        console.print("[bold green]MediaInfo Exported.")

    if mediainfo_cmd and is_dvd:
        try:
            cmd = [mediainfo_cmd, "--Output=JSON", video]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                media_info_json = result.stdout
                media_info_dict = json.loads(media_info_json)
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        except subprocess.TimeoutExpired:
            console.print("[bold red]Specialized MediaInfo timed out (30s) - falling back to standard MediaInfo[/bold red]")
            media_info_json = MediaInfo.parse(video, output="JSON")
            media_info_dict = json.loads(media_info_json)
        except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
            console.print(f"[bold red]Error getting JSON from specialized MediaInfo: {e}")
            if debug and 'result' in locals():
                console.print(f"[red]Subprocess stderr: {result.stderr}[/red]")
                console.print(f"[red]Subprocess returncode: {result.returncode}[/red]")
                if result.stdout:
                    console.print(f"[red]Subprocess stdout preview: {result.stdout[:200]}...[/red]")
            console.print("[bold yellow]Falling back to standard MediaInfo for JSON...[/bold yellow]")
            media_info_json = MediaInfo.parse(video, output="JSON")
            media_info_dict = json.loads(media_info_json)
    else:
        # Use standard MediaInfo library for non-DVD or when specialized CLI not available
        media_info_json = MediaInfo.parse(video, output="JSON")
        media_info_dict = json.loads(media_info_json)

    filtered_info = filter_mediainfo(media_info_dict)

    async with aiofiles.open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'w', encoding='utf-8') as export:
        await export.write(json.dumps(filtered_info, indent=4))
        if debug:
            console.print(f"[green]JSON file written to: {base_dir}/tmp/{folder_id}/MediaInfo.json[/green]")

    async with aiofiles.open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'r', encoding='utf-8') as f:
        mi = json.loads(await f.read())

    # Cleanup: Reset library configuration if we modified it
    if is_dvd and platform.system().lower() in ['linux', 'windows']:
        # Reset MediaInfo library file to default (Linux only)
        if hasattr(MediaInfo, '_library_file'):
            MediaInfo._library_file = None
        if debug:
            console.print("[blue]Reset MediaInfo library configuration[/blue]")

    return mi


def validate_mediainfo(meta, debug, settings=False):
    if not any(str(f).lower().endswith('.mkv') for f in meta.get('filelist', [])):
        if debug:
            console.print(f"[yellow]Skipping {meta.get('path')} (not an .mkv file)[/yellow]")
        return True

    unique_id = None
    valid_settings = False

    if debug:
        console.print("[cyan]Validating MediaInfo")

    mediainfo_data = meta.get('mediainfo', {})

    if "media" in mediainfo_data and "track" in mediainfo_data["media"]:
        tracks = mediainfo_data["media"]["track"]
        has_audio = any(track.get("@type", "") == "Audio" for track in tracks)

        if not has_audio:
            raise Exception("Upload Assistant does not support no audio media.")

        for track in tracks:
            track_type = track.get("@type", "")

            if settings and track_type == "Video":
                encoding_settings = track.get("Encoded_Library_Settings")
                if encoding_settings and encoding_settings != {} and str(encoding_settings).strip():
                    valid_settings = True
                    if debug:
                        console.print(f"[green]Found encoding settings: {encoding_settings}[/green]")
                    break

            elif not settings and track_type == "General":
                unique_id_value = track.get("UniqueID")
                if unique_id_value and unique_id_value != {} and str(unique_id_value).strip():
                    unique_id = str(unique_id_value)
                    if debug:
                        console.print(f"[green]Found Unique ID: {unique_id}[/green]")
                    break

    if debug:
        if settings and not valid_settings:
            console.print("[yellow]Mediainfo failed validation (no encoding settings)[/yellow]")
        elif not settings and not unique_id:
            console.print("[yellow]Mediainfo failed validation (no unique ID)[/yellow]")

    return bool(valid_settings) if settings else bool(unique_id)


async def get_conformance_error(meta):
    if not meta.get('is_disc') == "BDMV" and meta.get('mediainfo', {}).get('media', {}).get('track'):
        general_track = next((track for track in meta['mediainfo']['media']['track']
                              if track.get('@type') == 'General'), None)
        if general_track and general_track.get('extra', {}).get('ConformanceErrors', {}):
            try:
                return True
            except ValueError:
                if meta['debug']:
                    console.print(f"[red]Unexpected value: {general_track['extra']['ConformanceErrors']}[/red]")
                return True
        else:
            if meta['debug']:
                console.print("[green]No Conformance errors found in MediaInfo General track[/green]")
            return False
    else:
        return False
