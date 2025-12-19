# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import traceback
from guessit import guessit
from src.console import console
from src.exceptions import *  # noqa: F403


async def get_source(type, video, path, is_disc, meta, folder_id, base_dir):
    if not meta.get('is_disc') == "BDMV":
        try:
            with open(f'{base_dir}/tmp/{folder_id}/MediaInfo.json', 'r', encoding='utf-8') as f:
                mi = json.load(f)
        except Exception:
            if meta['debug']:
                console.print("No mediainfo.json")
    try:
        if meta.get('manual_source', None):
            source = meta['manual_source']
        else:
            try:
                source = guessit(video)['source']
            except Exception:
                try:
                    source = guessit(path)['source']
                except Exception:
                    source = "BluRay"
        if source in ("Blu-ray", "Ultra HD Blu-ray", "BluRay", "BR") or is_disc == "BDMV":
            if type == "DISC":
                source = "Blu-ray"
            elif type in ('ENCODE', 'REMUX'):
                source = "BluRay"
        if is_disc == "DVD" or source in ("DVD", "dvd"):
            try:
                mediainfo = mi
                for track in mediainfo['media']['track']:
                    if track['@type'] == "Video":
                        system = track.get('Standard', '')
                if system not in ("PAL", "NTSC"):
                    raise WeirdSystem  # noqa: F405
            except Exception:
                try:
                    other = guessit(video)['other']
                    if "PAL" in other:
                        system = "PAL"
                    elif "NTSC" in other:
                        system = "NTSC"
                except Exception:
                    system = ""
                if system == "" or system is None or system not in ("PAL", "NTSC"):
                    try:
                        framerate = mi['media']['track'][1].get('FrameRate', '')
                        if '25' in framerate or '50' in framerate:
                            system = "PAL"
                        elif framerate:
                            system = "NTSC"
                        else:
                            system = ""
                    except Exception:
                        system = ""
            finally:
                if system is None:
                    system = ""
                if type == "REMUX":
                    system = f"{system} DVD".strip()
                source = system
        if source in ("Web", "WEB"):
            if type == "ENCODE":
                type = "WEBRIP"
        if source in ("HD-DVD", "HD DVD", "HDDVD"):
            if is_disc == "HDDVD":
                source = "HD DVD"
            if type in ("ENCODE", "REMUX"):
                source = "HDDVD"
        if type in ("WEBDL", 'WEBRIP'):
            source = "Web"
        if source == "Ultra HDTV":
            source = "UHDTV"
    except Exception:
        console.print(traceback.format_exc())
        source = "BluRay"

    return source, type
