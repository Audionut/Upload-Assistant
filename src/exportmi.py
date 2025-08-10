from src.console import console
from pymediainfo import MediaInfo
import json
import os
import platform


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
    if is_dvd:
        if debug:
            console.print("[bold yellow]DVD detected, using specialized MediaInfo binary...")
        mediainfo_binary = os.path.join(base_dir, "bin", "MI", "windows", "MediaInfo.exe")

        if platform.system() == "windows" and os.path.exists(mediainfo_binary):
            mediainfo_cmd = mediainfo_binary

    if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt") and export_text:
        if debug:
            console.print("[bold yellow]Exporting MediaInfo...")
        if not isdir:
            os.chdir(os.path.dirname(video))

        if mediainfo_cmd:
            import subprocess
            try:
                # Handle both string and list command formats
                if isinstance(mediainfo_cmd, list):
                    result = subprocess.run(mediainfo_cmd + [video], capture_output=True, text=True)
                else:
                    result = subprocess.run([mediainfo_cmd, video], capture_output=True, text=True)
                media_info = result.stdout
            except Exception as e:
                console.print(f"[bold red]Error using specialized MediaInfo binary: {e}")
                console.print("[bold yellow]Falling back to standard MediaInfo...")
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

        with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8') as export:
            export.write(filtered_media_info.replace(video, os.path.basename(video)))
        with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8') as export_cleanpath:
            export_cleanpath.write(filtered_media_info.replace(video, os.path.basename(video)))
        if debug:
            console.print("[bold green]MediaInfo Exported.")

    if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MediaInfo.json"):
        if mediainfo_cmd:
            import subprocess
            try:
                # Handle both string and list command formats
                if isinstance(mediainfo_cmd, list):
                    result = subprocess.run(mediainfo_cmd + ["--Output=JSON", video], capture_output=True, text=True)
                else:
                    result = subprocess.run([mediainfo_cmd, "--Output=JSON", video], capture_output=True, text=True)
                media_info_json = result.stdout
                media_info_dict = json.loads(media_info_json)
            except Exception as e:
                console.print(f"[bold red]Error getting JSON from specialized MediaInfo binary: {e}")
                console.print("[bold yellow]Falling back to standard MediaInfo for JSON...")
                media_info_json = MediaInfo.parse(video, output="JSON")
                media_info_dict = json.loads(media_info_json)
        else:
            media_info_json = MediaInfo.parse(video, output="JSON")
            media_info_dict = json.loads(media_info_json)

        filtered_info = filter_mediainfo(media_info_dict)
        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'w', encoding='utf-8') as export:
            json.dump(filtered_info, export, indent=4)

    with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'r', encoding='utf-8') as f:
        mi = json.load(f)

    return mi


def validate_mediainfo(base_dir, folder_id, path, filelist, debug):
    if not (path.lower().endswith('.mkv') or any(str(f).lower().endswith('.mkv') for f in filelist)):
        if debug:
            console.print(f"[yellow]Skipping {path} (not an .mkv file)[/yellow]")
        return True
    mediainfo_path = f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt"
    unique_id = None
    in_general = False

    if debug:
        console.print(f"[cyan]Validating MediaInfo at: {mediainfo_path}")

    try:
        with open(mediainfo_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() == "General":
                    in_general = True
                    continue
                if in_general:
                    if line.strip() == "":
                        break
                    if line.strip().startswith("Unique ID"):
                        unique_id = line.split(":", 1)[1].strip()
                        break
    except FileNotFoundError:
        console.print(f"[red]MediaInfo file not found: {mediainfo_path}[/red]")
        return False

    if debug:
        if unique_id:
            console.print(f"[green]Found Unique ID: {unique_id}[/green]")
        else:
            console.print("[yellow]Unique ID not found in General section.[/yellow]")

    return bool(unique_id)
