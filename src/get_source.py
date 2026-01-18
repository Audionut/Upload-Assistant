# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import traceback
from pathlib import Path
from typing import Any, Callable, Optional, cast

import guessit

from src.console import console
from src.exceptions import WeirdSystem

guessit_module: Any = cast(Any, guessit)
GuessitFn = Callable[[str, Optional[dict[str, Any]]], dict[str, Any]]


def guessit_fn(value: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return cast(dict[str, Any], guessit_module.guessit(value, options))


async def get_source(type: str, video: str, path: str, is_disc: str, meta: dict[str, Any], folder_id: str, base_dir: str) -> tuple[str, str]:
    source = "BluRay"
    system = ""
    mi: dict[str, Any] = {}
    if meta.get('is_disc') != "BDMV":
        try:
            mi_text = await asyncio.to_thread(Path(f"{base_dir}/tmp/{folder_id}/MediaInfo.json").read_text, encoding="utf-8")
            mi = json.loads(mi_text)
        except Exception:
            if meta['debug']:
                console.print("No mediainfo.json")
    try:
        if meta.get('manual_source'):
            source = str(meta['manual_source'])
        else:
            try:
                source = guessit_fn(video).get('source', source)
            except Exception:
                try:
                    source = guessit_fn(path).get('source', source)
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
                        system = str(track.get('Standard', ''))
                if system not in ("PAL", "NTSC"):
                    raise WeirdSystem  # noqa: F405
            except Exception:
                try:
                    other = cast(list[str], guessit_fn(video).get('other', []))
                    if "PAL" in other:
                        system = "PAL"
                    elif "NTSC" in other:
                        system = "NTSC"
                except Exception:
                    system = ""
                if system == "" or system not in ("PAL", "NTSC"):
                    try:
                        framerate = str(mi['media']['track'][1].get('FrameRate', ''))
                        if '25' in framerate or '50' in framerate:
                            system = "PAL"
                        elif framerate:
                            system = "NTSC"
                        else:
                            system = ""
                    except Exception:
                        system = ""
            finally:
                if type == "REMUX":
                    system = f"{system} DVD".strip()
                source = system
        if source in ("Web", "WEB") and type == "ENCODE":
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
