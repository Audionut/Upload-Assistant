import os
import json
import re
import glob
import cli_ui
from src.console import console
from src.exportmi import mi_resolution


async def get_uhd(type, guess, resolution, path):
    try:
        source = guess['Source']
        other = guess['Other']
    except Exception:
        source = ""
        other = ""
    uhd = ""
    if source == 'Blu-ray' and other == "Ultra HD" or source == "Ultra HD Blu-ray":
        uhd = "UHD"
    elif "UHD" in path:
        uhd = "UHD"
    elif type in ("DISC", "REMUX", "ENCODE", "WEBRIP"):
        uhd = ""

    if type in ("DISC", "REMUX", "ENCODE") and resolution == "2160p":
        uhd = "UHD"

    return uhd


async def get_hdr(mi, bdinfo):
    hdr = ""
    dv = ""
    if bdinfo is not None:  # Disks
        hdr_mi = bdinfo['video'][0]['hdr_dv']
        if "HDR10+" in hdr_mi:
            hdr = "HDR10+"
        elif hdr_mi == "HDR10":
            hdr = "HDR"
        try:
            if bdinfo['video'][1]['hdr_dv'] == "Dolby Vision":
                dv = "DV"
        except Exception:
            pass
    else:
        video_track = mi['media']['track'][1]
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
                elif "HDR10" in hdr_format_string:
                    hdr = "HDR"
                elif "SMPTE ST 2094 App 4" in hdr_format_string:
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


async def get_video_codec(bdinfo):
    codecs = {
        "MPEG-2 Video": "MPEG-2",
        "MPEG-4 AVC Video": "AVC",
        "MPEG-H HEVC Video": "HEVC",
        "VC-1 Video": "VC-1"
    }
    codec = codecs.get(bdinfo['video'][0]['codec'], "")
    return codec


async def get_video_encode(mi, type, bdinfo):
    video_encode = ""
    codec = ""
    bit_depth = '0'
    has_encode_settings = False
    try:
        format = mi['media']['track'][1]['Format']
        format_profile = mi['media']['track'][1].get('Format_Profile', format)
        if mi['media']['track'][1].get('Encoded_Library_Settings', None):
            has_encode_settings = True
        bit_depth = mi['media']['track'][1].get('BitDepth', '0')
    except Exception:
        format = bdinfo['video'][0]['codec']
        format_profile = bdinfo['video'][0]['profile']
    if type in ("ENCODE", "WEBRIP", "DVDRIP"):  # ENCODE or WEBRIP or DVDRIP
        if format == 'AVC':
            codec = 'x264'
        elif format == 'HEVC':
            codec = 'x265'
        elif format == 'AV1':
            codec = 'AV1'
    elif type in ('WEBDL', 'HDTV'):  # WEB-DL
        if format == 'AVC':
            codec = 'H.264'
        elif format == 'HEVC':
            codec = 'H.265'
        elif format == 'AV1':
            codec = 'AV1'

        if type == 'HDTV' and has_encode_settings is True:
            codec = codec.replace('H.', 'x')
    elif format == "VP9":
        codec = "VP9"
    elif format == "VC-1":
        codec = "VC-1"
    if format_profile == 'High 10':
        profile = "Hi10P"
    else:
        profile = ""
    video_encode = f"{profile} {codec}"
    video_codec = format
    if video_codec == "MPEG Video":
        video_codec = f"MPEG-{mi['media']['track'][1].get('Format_Version')}"
    return video_encode, video_codec, has_encode_settings, bit_depth


async def get_video(videoloc, mode):
    filelist = []
    videoloc = os.path.abspath(videoloc)
    if os.path.isdir(videoloc):
        globlist = glob.glob1(videoloc, "*.mkv") + glob.glob1(videoloc, "*.mp4") + glob.glob1(videoloc, "*.ts")
        for file in globlist:
            if not file.lower().endswith('sample.mkv') or "!sample" in file.lower():
                filelist.append(os.path.abspath(f"{videoloc}{os.sep}{file}"))
                filelist = sorted(filelist)
                if len(filelist) > 1:
                    for f in filelist:
                        if "sample" in os.path.basename(f).lower():
                            console.print("[green]Filelist:[/green]")
                            for tf in filelist:
                                console.print(f"[cyan]{tf}")
                            console.print(f"[bold red]Possible sample file detected in filelist!: [yellow]{f}")
                            if cli_ui.ask_yes_no("Do you want to remove it?", default="yes"):
                                filelist.remove(f)
        try:
            video = sorted(filelist)[0]
        except IndexError:
            console.print("[bold red]No Video files found")
            if mode == 'cli':
                exit()
    else:
        video = videoloc
        filelist.append(videoloc)
    filelist = sorted(filelist)
    return video, filelist


async def get_resolution(guess, folder_id, base_dir):
    hfr = False
    with open(f'{base_dir}/tmp/{folder_id}/MediaInfo.json', 'r', encoding='utf-8') as f:
        mi = json.load(f)
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
        if scan == "Progressive":
            scan = "p"
        elif scan == "Interlaced":
            scan = 'i'
        elif framerate == "25.000":
            scan = "p"
        else:
            # Fallback using regex on meta['uuid'] - mainly for HUNO fun and games.
            match = re.search(r'\b(1080p|720p|2160p|576p|480p)\b', folder_id, re.IGNORECASE)
            if match:
                scan = "p"  # Assume progressive based on common resolution markers
            else:
                scan = "i"  # Default to interlaced if no indicators are found
        width_list = [3840, 2560, 1920, 1280, 1024, 854, 720, 15360, 7680, 0]
        height_list = [2160, 1440, 1080, 720, 576, 540, 480, 8640, 4320, 0]
        width = await closest(width_list, int(width))
        actual_height = int(height)
        height = await closest(height_list, int(height))
        res = f"{width}x{height}{scan}"
        resolution = await mi_resolution(res, guess, width, scan, height, actual_height)
    return resolution, hfr


async def closest(lst, K):
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


async def get_type(video, scene, is_disc, meta):
    if meta.get('manual_type'):
        type = meta.get('manual_type')
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


async def is_3d(mi, bdinfo):
    if bdinfo is not None:
        if bdinfo['video'][0]['3d'] != "":
            return "3D"
        else:
            return ""
    else:
        return ""


async def is_sd(resolution):
    if resolution in ("480i", "480p", "576i", "576p", "540p"):
        sd = 1
    else:
        sd = 0
    return sd
