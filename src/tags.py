import os
import re
import json
from guessit import guessit
from src.console import console


async def get_tag(video, meta):
    # Using regex from cross-seed (https://github.com/cross-seed/cross-seed/tree/master?tab=Apache-2.0-1-ov-file)
    release_group = None
    basename = os.path.basename(video)

    # Try specialized regex patterns first
    if meta.get('anime', False):
        # Anime pattern: [Group] at the beginning
        basename_stripped = os.path.splitext(basename)[0]
        anime_match = re.search(r'^\s*\[(.+?)\]', basename_stripped)
        if anime_match:
            release_group = anime_match.group(1)
            if meta['debug']:
                console.print(f"Anime regex match: {release_group}")
    else:
        if not meta.get('is_disc') == "BDMV":
            # Non-anime pattern: group at the end after last hyphen, avoiding resolutions and numbers
            basename_stripped = os.path.splitext(basename)[0]
            non_anime_match = re.search(r'(?<=-)((?:\W|\b)(?!(?:\d{3,4}[ip]))(?!\d+\b)(?:\W|\b)([\w .]+?))(?:\[.+\])?(?:\))?(?:\s\[.+\])?$', basename_stripped)
            if non_anime_match:
                release_group = non_anime_match.group(1).strip()
                if meta['debug']:
                    console.print(f"Non-anime regex match: {release_group}")

    # If regex patterns didn't work, fall back to guessit
    if not release_group:
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
    if tag and tag[1:].lower() in ["nogroup", "nogrp", "hd.ma.5.1"]:
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
                        meta['desc_template'] = value.get(key)
                    else:
                        meta[key] = value.get(key)
    except Exception as e:
        console.print(f"Error while loading tags.json: {e}")
        return meta
    return meta


def _is_true(self, value):
    return str(value).strip().lower() == "true"
