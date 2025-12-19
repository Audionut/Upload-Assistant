# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
import json
from guessit import guessit
from src.console import console


async def get_tag(video, meta):
    # Using regex from cross-seed (https://github.com/cross-seed/cross-seed/tree/master?tab=Apache-2.0-1-ov-file)
    release_group = None
    basename = os.path.basename(video)
    matched_anime = False

    # Try specialized regex patterns first
    if meta.get('anime', False):
        # Anime pattern: [Group] at the beginning
        basename_stripped = os.path.splitext(basename)[0]
        anime_match = re.search(r'^\s*\[(.+?)\]', basename_stripped)
        if anime_match:
            matched_anime = True
            release_group = anime_match.group(1)
            if meta['debug']:
                console.print(f"Anime regex match: {release_group}")
    if not meta.get('anime', False) or not matched_anime:
        if not meta.get('is_disc') == "BDMV":
            # Non-anime pattern: group at the end after last hyphen, avoiding resolutions and numbers
            if os.path.isdir(video):
                # If video is a directory, use the directory name as basename
                basename_stripped = os.path.basename(os.path.normpath(video))
            elif meta.get('tv_pack', False) or meta.get('keep_folder', False):
                basename_stripped = meta['uuid']
            else:
                # If video is a file, use the filename without extension
                basename_no_path = os.path.basename(video)
                name, ext = os.path.splitext(basename_no_path)
                # If the extension contains a hyphen, it's not a real extension
                if ext and '-' in ext:
                    basename_stripped = basename_no_path
                else:
                    basename_stripped = name
            non_anime_match = re.search(r'(?<=-)((?!\s*(?:WEB-DL|Blu-ray|H-264|H-265))(?:\W|\b)(?!(?:\d{3,4}[ip]))(?!\d+\b)(?:\W|\b)([\w .]+?))(?:\[.+\])?(?:\))?(?:\s\[.+\])?$', basename_stripped)
            if non_anime_match:
                release_group = non_anime_match.group(1).strip()
                if "Z0N3" in release_group:
                    release_group = release_group.replace("Z0N3", "D-Z0N3")
                if not meta.get('scene', False):
                    if release_group and len(release_group) > 12:
                        release_group = None
                if meta['debug']:
                    console.print(f"Non-anime regex match: {release_group}")

    # If regex patterns didn't work, fall back to guessit
    if not release_group and meta.get('is_disc'):
        try:
            parsed = guessit(video)
            release_group = parsed.get('release_group')
            if meta['debug']:
                console.print(f"Guessit match: {release_group}")

        except Exception as e:
            console.print(f"Error while parsing group tag: {e}")
            release_group = None

    # BDMV validation
    if meta['is_disc'] == "BDMV" and release_group:
        if f"{release_group}" not in video:
            release_group = None

    # Format the tag
    tag = f"-{release_group}" if release_group else ""

    # Clean up any tags that are just a hyphen
    if tag == "-":
        tag = ""

    # Remove generic "no group" tags
    if tag and tag[1:].lower() in ["hd.ma.5.1", "untouched"]:
        tag = ""

    return tag


async def tag_override(meta):
    try:
        with open(f"{meta['base_dir']}/data/tags.json", 'r', encoding="utf-8") as f:
            tags = json.load(f)
            f.close()

        for tag in tags:
            value = tags.get(tag)
            if value.get('in_name', "") == tag and tag in meta['path']:
                meta['tag'] = f"-{tag}"
            if meta['tag'][1:] == tag:
                for key in value:
                    if key == 'type':
                        if meta[key] == "ENCODE":
                            meta[key] = value.get(key)
                        else:
                            pass
                    elif key == 'personalrelease':
                        meta[key] = _is_true(value.get(key, "False"))
                    elif key == 'template':
                        meta['description_template'] = value.get(key)
                    else:
                        meta[key] = value.get(key)
    except Exception as e:
        console.print(f"Error while loading tags.json: {e}")
        return meta
    return meta


def _is_true(value):
    return str(value).strip().lower() == "true"
