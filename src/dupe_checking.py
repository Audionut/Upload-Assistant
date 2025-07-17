import re
from src.console import console


async def filter_dupes(dupes, meta, tracker_name):
    """
    Filter duplicates by applying exclusion rules. Only non-excluded entries are returned.
    Everything is a dupe, until it matches a criteria to be excluded.
    """
    if meta['debug']:
        console.log(f"[cyan]Pre-filtered dupes from {tracker_name}")
        console.log(dupes)

    processed_dupes = [
        {'name': d, 'size': None} if isinstance(d, str) else {'name': d['name'], 'size': d['size']}
        for d in dupes
    ]

    new_dupes = []

    has_repack_in_uuid = "repack" in meta.get('uuid', '').lower()
    video_encode = meta.get("video_encode")
    if video_encode is not None:
        has_encoder_in_name = video_encode.lower()
        normalized_encoder = await normalize_filename(has_encoder_in_name)
    else:
        normalized_encoder = False
    if not meta['is_disc'] == "BDMV":
        tracks = meta.get('mediainfo').get('media', {}).get('track', [])
        fileSize = tracks[0].get('FileSize', '')
    has_is_disc = bool(meta.get('is_disc', False))
    target_hdr = await refine_hdr_terms(meta.get("hdr"))
    target_season = meta.get("season")
    target_episode = meta.get("episode")
    target_resolution = meta.get("resolution")
    tag = meta.get("tag").lower().replace("-", " ")
    is_dvd = meta['is_disc'] == "DVD"
    is_dvdrip = meta['type'] == "DVDRIP"
    web_dl = meta.get('type') == "WEBDL"
    is_hdtv = meta.get('type') == "HDTV"
    target_source = meta.get("source")
    is_sd = meta.get('sd')

    attribute_checks = [
        {
            "key": "repack",
            "uuid_flag": has_repack_in_uuid,
            "condition": lambda each: meta['tag'].lower() in each and has_repack_in_uuid and "repack" not in each.lower(),
            "exclude_msg": lambda each: f"Excluding result because it lacks 'repack' and matches tag '{meta['tag']}': {each}"
        },
        {
            "key": "remux",
            "uuid_flag": "remux" in meta.get('name', '').lower(),
            "condition": lambda each: "remux" in each.lower(),
            "exclude_msg": lambda each: f"Excluding result due to 'remux' mismatch: {each}"
        },
        {
            "key": "uhd",
            "uuid_flag": "uhd" in meta.get('name', '').lower(),
            "condition": lambda each: "uhd" in each.lower(),
            "exclude_msg": lambda each: f"Excluding result due to 'UHD' mismatch: {each}"
        },
    ]

    async def log_exclusion(reason, item):
        if meta['debug']:
            console.log(f"[yellow]Excluding result due to {reason}: {item}")

    async def process_exclusion(entry):
        """
        Determine if an entry should be excluded.
        Returns True if the entry should be excluded, otherwise allowed as dupe.
        """
        each = entry['name']
        sized = entry['size']
        normalized = await normalize_filename(each)
        file_hdr = await refine_hdr_terms(normalized)

        if meta['debug']:
            console.log(f"[debug] Evaluating dupe: {each}")
            console.log(f"[debug] Normalized dupe: {normalized}")
            console.log(f"[debug] Target resolution: {target_resolution}")
            console.log(f"[debug] Target source: {target_source}")
            console.log(f"[debug] File HDR terms: {file_hdr}")
            console.log(f"[debug] Target HDR terms: {target_hdr}")
            console.log(f"[debug] Target Season: {target_season}")
            console.log(f"[debug] Target Episode: {target_episode}")
            console.log(f"[debug] TAG: {tag}")
            console.log("[debug] Evaluating repack condition:")
            console.log(f"  has_repack_in_uuid: {has_repack_in_uuid}")
            console.log(f"  'repack' in each.lower(): {'repack' in each.lower()}")
            console.log(f"[debug] meta['uuid']: {meta.get('uuid', '')}")
            console.log(f"[debug] normalized encoder: {normalized_encoder}")

        if has_is_disc and each.lower().endswith(".m2ts"):
            return False

        if has_is_disc and re.search(r'\.\w{2,4}$', each):
            await log_exclusion("file extension mismatch (is_disc=True)", each)
            return True

        if meta.get('is_disc') == "BDMV" and tracker_name in ["AITHER", "LST", "HDB", "BHD"]:
            if len(each) > 1 and tag == "":
                return False
            if tag and tag.strip() and tag.strip() in normalized:
                return False
            return True

        if is_sd == 1 and (tracker_name == "BHD" or tracker_name == "AITHER"):
            if any(str(res) in each for res in [1080, 720, 2160]):
                return False

        if target_hdr and '1080p' in target_resolution and '2160p' in each:
            await log_exclusion("No 1080p HDR when 4K exists", each)
            return False

        if tracker_name in ["AITHER", "LST"] and is_dvd:
            return True

        if web_dl:
            if "hdtv" in normalized and not any(web_term in normalized for web_term in ["web-dl", "webdl", "web dl"]):
                await log_exclusion("source mismatch: WEB-DL vs HDTV", each)
                return True

        if is_dvd or "DVD" in target_source or is_dvdrip:
            skip_resolution_check = True
        else:
            skip_resolution_check = False

        if not skip_resolution_check:
            if target_resolution and target_resolution not in each:
                await log_exclusion(f"resolution '{target_resolution}' mismatch", each)
                return True
            if not await has_matching_hdr(file_hdr, target_hdr, meta, tracker=tracker_name):
                await log_exclusion(f"HDR mismatch: Expected {target_hdr}, got {file_hdr}", each)
                return True

        if is_dvd and not tracker_name == "BHD":
            if any(str(res) in each for res in [1080, 720, 2160]):
                await log_exclusion(f"resolution '{target_resolution}' mismatch", each)
                return False

        for check in attribute_checks:
            if check["key"] == "repack":
                if has_repack_in_uuid and "repack" not in normalized:
                    if tag and tag in normalized:
                        await log_exclusion("missing 'repack'", each)
                        return True
            elif check["uuid_flag"] != check["condition"](each):
                await log_exclusion(f"{check['key']} mismatch", each)
                return True

        if meta.get('category') == "TV":
            season_episode_match = await is_season_episode_match(normalized, target_season, target_episode)
            if meta['debug']:
                console.log(f"[debug] Season/Episode match result: {season_episode_match}")
            if not season_episode_match:
                await log_exclusion("season/episode mismatch", each)
                return True

        if is_hdtv:
            if any(web_term in normalized for web_term in ["web-dl", "webdl", "web dl"]):
                return False

        if len(dupes) == 1 and meta.get('is_disc') != "BDMV":
            if tracker_name in ["AITHER", "BHD", "HUNO", "OE", "ULCX"]:
                if fileSize and "1080" in target_resolution and 'x264' in video_encode:
                    target_size = int(fileSize)
                    dupe_size = sized

                    if dupe_size is not None and target_size is not None:
                        size_difference = (target_size - dupe_size) / dupe_size
                        if meta['debug']:
                            console.print(f"Your size: {target_size}, Dupe size: {dupe_size}, Size difference: {size_difference:.4f}")
                        if size_difference >= 0.20:
                            await log_exclusion(f"Your file is significantly larger ({size_difference * 100:.2f}%)", each)
                            return True
            if tracker_name == "RF":
                if tag and tag.strip() and tag.strip() in normalized:
                    return False
                elif tag and tag.strip() and tag.strip() not in normalized:
                    await log_exclusion(f"Tag '{tag}' not found in normalized name", each)
                    return True

        if meta['debug']:
            console.log(f"[debug] Passed all checks: {each}")
        return False

    for each in processed_dupes:
        if not await process_exclusion(each):
            new_dupes.append(each)

    if new_dupes and not meta.get('unattended', False) and meta['debug']:
        console.print(f"[cyan]Final dupes on {tracker_name}: {new_dupes}")

    return new_dupes


async def normalize_filename(filename):
    if isinstance(filename, dict):
        filename = filename.get('name', '')
    if not isinstance(filename, str):
        raise ValueError(f"Expected a string or a dictionary with a 'name' key, but got: {type(filename)}")
    normalized = filename.lower().replace("-", " -").replace(" ", " ").replace(".", " ")

    return normalized


async def is_season_episode_match(filename, target_season, target_episode):
    """
    Check if the filename matches the given season and episode.
    """
    season_match = re.search(r'[sS](\d+)', str(target_season))
    target_season = int(season_match.group(1)) if season_match else None

    if target_episode:
        episode_matches = re.findall(r'\d+', str(target_episode))
        target_episodes = [int(ep) for ep in episode_matches]
    else:
        target_episodes = []

    season_pattern = rf"[sS]{target_season:02}" if target_season is not None else None
    episode_patterns = [rf"[eE]{ep:02}" for ep in target_episodes] if target_episodes else []

    # Determine if filename represents a season pack (no explicit episode pattern)
    is_season_pack = not re.search(r"[eE]\d{2}", filename, re.IGNORECASE)

    # If `target_episode` is empty, match only season packs
    if not target_episodes:
        return bool(season_pattern and re.search(season_pattern, filename, re.IGNORECASE)) and is_season_pack

    # If `target_episode` is provided, match both season packs and episode files
    if season_pattern:
        if is_season_pack:
            return bool(re.search(season_pattern, filename, re.IGNORECASE))  # Match season pack
        if episode_patterns:
            return bool(re.search(season_pattern, filename, re.IGNORECASE)) and any(
                re.search(ep, filename, re.IGNORECASE) for ep in episode_patterns
            )  # Match episode file

    return False  # No match


async def refine_hdr_terms(hdr):
    """
    Normalize HDR terms for consistent comparison.
    Simplifies all HDR entries to 'HDR' and DV entries to 'DV'.
    """
    if hdr is None:
        return set()
    hdr = hdr.upper()
    terms = set()
    if "DV" in hdr or "DOVI" in hdr:
        terms.add("DV")
    if "HDR" in hdr:  # Any HDR-related term is normalized to 'HDR'
        terms.add("HDR")
    return terms


async def has_matching_hdr(file_hdr, target_hdr, meta, tracker=None):
    """
    Check if the HDR terms match or are compatible.
    """
    def simplify_hdr(hdr_set, tracker=None):
        """Simplify HDR terms to just HDR and DV."""
        simplified = set()
        if any(h in hdr_set for h in {"HDR", "HDR10", "HDR10+"}):
            simplified.add("HDR")
        if "DV" in hdr_set or "DOVI" in hdr_set:
            simplified.add("DV")
            if 'web' not in meta['type'].lower():
                simplified.add("HDR")
            if tracker == "ANT":
                simplified.add("HDR")
        return simplified

    file_hdr_simple = simplify_hdr(file_hdr, tracker)
    target_hdr_simple = simplify_hdr(target_hdr, tracker)

    if file_hdr_simple == {"DV", "HDR"} or file_hdr_simple == {"HDR", "DV"}:
        file_hdr_simple = {"HDR"}
        if target_hdr_simple == {"DV", "HDR"} or target_hdr_simple == {"HDR", "DV"}:
            target_hdr_simple = {"HDR"}

    return file_hdr_simple == target_hdr_simple
