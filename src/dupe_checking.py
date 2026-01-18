# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from collections.abc import MutableMapping, Sequence
from typing import Any, Callable, Optional, TypedDict, Union, cast

from typing_extensions import TypeAlias

from cogs.redaction import Redaction
from src.console import console
from src.trackers.HUNO import HUNO

Meta: TypeAlias = MutableMapping[str, Any]


class DupeEntry(TypedDict, total=False):
    name: str
    size: Optional[Union[int, str]]
    files: list[str]
    file_count: int
    trumpable: bool
    link: Optional[str]
    download: Optional[str]
    flags: list[str]
    id: Optional[Union[int, str]]
    type: Optional[str]
    res: Optional[str]
    internal: Union[int, bool]
    bd_info: Optional[str]
    description: Optional[str]


DupeInput: TypeAlias = Union[str, DupeEntry, MutableMapping[str, Any]]


class AttributeCheck(TypedDict):
    key: str
    uuid_flag: bool
    condition: Callable[[str], bool]
    exclude_msg: Callable[[str], str]


class DupeChecker:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def filter_dupes(self, dupes: Sequence[DupeInput], meta: Meta, tracker_name: str) -> list[DupeEntry]:
        """
        Filter duplicates by applying exclusion rules. Only non-excluded entries are returned.
        Everything is a dupe, until it matches a criteria to be excluded.
        """
        if meta.get('debug'):
            console.log(f"[cyan]Pre-filtered dupes from {tracker_name}")
            # Limit dupe output for readability
            if dupes:
                dupes_to_print: list[dict[str, Any]] = []
                for dupe in dupes:
                    if isinstance(dupe, dict) and 'files' in dupe and isinstance(dupe['files'], list):
                        # Limit files list to first 10 items
                        limited_dupe = Redaction.redact_private_info(dupe).copy()
                        limited_files = cast(list[str], limited_dupe.get('files', []))
                        if len(limited_files) > 10:
                            dupe_files = cast(list[str], dupe.get('files', []))
                            limited_dupe['files'] = limited_files[:10] + [f"... and {len(dupe_files) - 10} more files"]
                        dupes_to_print.append(limited_dupe)
                    else:
                        dupes_to_print.append(Redaction.redact_private_info(dupe))
                console.log(dupes_to_print)
            else:
                console.log(dupes)

        meta['trumpable_id'] = None
        processed_dupes: list[DupeEntry] = []
        for d in dupes:
            if isinstance(d, str):
                # Case 1: Simple string (just name)
                processed_dupes.append({
                    'name': d,
                    'size': None,
                    'files': [],
                    'file_count': 0,
                    'trumpable': False,
                    'link': None,
                    'download': None,
                    'flags': [],
                    'id': None,
                    'type': None,
                    'res': None,
                    'internal': 0,
                    'bd_info': None,
                    'description': None,
                })
            elif isinstance(d, dict):
                # Create a base entry with default values
                entry: DupeEntry = {
                    'name': str(d.get('name', '')),
                    'size': d.get('size'),
                    'files': [],
                    'file_count': 0,
                    'trumpable': bool(d.get('trumpable', False)),
                    'link': d.get('link', None),
                    'download': d.get('download', None),
                    'flags': d.get('flags', []),
                    'id': d.get('id', None),
                    'type': d.get('type', None),
                    'res': d.get('res', None),
                    'internal': d.get('internal', 0),
                    'bd_info': d.get('bd_info', ''),
                    'description': d.get('description', ''),
                }

                # Case 3: Dict with files and file_count
                if 'files' in d:
                    if isinstance(d['files'], list):
                        entry_files = cast(list[Any], d['files'])
                        entry['files'] = [str(file) for file in entry_files]
                    elif isinstance(d['files'], str) and d['files']:
                        entry['files'] = [d['files']]
                    entry['file_count'] = len(entry['files'])
                if 'file_count' in d:
                    try:
                        entry['file_count'] = int(d['file_count'])
                    except (ValueError, TypeError):
                        entry['file_count'] = 0

                processed_dupes.append(entry)

        def coerce_int(value: Any) -> Optional[int]:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        new_dupes: list[DupeEntry]

        has_repack_in_uuid = "repack" in str(meta.get('uuid', '')).lower()
        video_encode_value = meta.get("video_encode")
        video_encode = str(video_encode_value) if video_encode_value else ""
        normalized_encoder = await DupeChecker.normalize_filename(video_encode) if video_encode else ""
        video_encode_lower = video_encode.lower()

        file_size: Optional[int] = None
        if meta.get('is_disc') != "BDMV":
            mediainfo = cast(dict[str, Any], meta.get('mediainfo', {}))
            tracks = cast(list[dict[str, Any]], mediainfo.get('media', {}).get('track', []))
            if tracks:
                file_size = coerce_int(tracks[0].get('FileSize'))

        has_is_disc = bool(meta.get('is_disc', False))
        target_hdr = await DupeChecker.refine_hdr_terms(cast(Optional[str], meta.get("hdr")))
        target_season = meta.get("season")
        target_episode = meta.get("episode")
        target_resolution = str(meta.get("resolution", ""))
        tag = str(meta.get("tag", "")).lower().replace("-", " ")
        is_dvd = meta.get('is_disc') == "DVD"
        is_dvdrip = meta.get('type') == "DVDRIP"
        web_dl = meta.get('type') == "WEBDL"
        is_hdtv = meta.get('type') == "HDTV"
        target_source = str(meta.get("source", ""))
        is_sd = int(meta.get('sd') or 0)

        filenames: list[str] = []
        filelist_value = meta.get('filelist')
        filelist: list[str] = []
        if not meta.get('is_disc'):
            if isinstance(filelist_value, Sequence) and not isinstance(filelist_value, (str, bytes)):
                filelist = [str(file_path) for file_path in cast(Sequence[Any], filelist_value)]
                for file_path in filelist:
                    # Extract just the filename without the path
                    filename = os.path.basename(file_path)
                    filenames.append(filename)
            if meta.get('debug'):
                console.log(f"dupe checking filenames: {filenames[:10]}{'...' if len(filenames) > 10 else ''}")

        attribute_checks: list[AttributeCheck] = [
            {
                "key": "remux",
                "uuid_flag": "remux" in str(meta.get('name', '')).lower(),
                "condition": lambda each: "remux" in each.lower(),
                "exclude_msg": lambda each: f"Excluding result due to 'remux' mismatch: {each}",
            },
            {
                "key": "uhd",
                "uuid_flag": "uhd" in str(meta.get('name', '')).lower(),
                "condition": lambda each: "uhd" in each.lower(),
                "exclude_msg": lambda each: f"Excluding result due to 'UHD' mismatch: {each}",
            },
        ]

        async def log_exclusion(reason: str, item: str) -> None:
            if meta.get('debug'):
                console.log(f"[yellow]Excluding result due to {reason}: {item}")

        async def process_exclusion(entry: DupeEntry) -> bool:
            """
            Determine if an entry should be excluded.
            Returns True if the entry should be excluded, otherwise allowed as dupe.
            """
            each = str(entry.get('name', ''))
            sized = entry.get('size')  # This may come as a string, such as "1.5 GB"

            files_value = cast(list[Any], entry.get('files') or [])
            files = [str(file) for file in files_value]

            # Handle case where files might be comma-separated strings in a list
            if files and len(files) == 1 and ',' in files[0]:
                # Split comma-separated string into individual filenames
                files = [f.strip() for f in files[0].split(',')]

            file_count_raw = entry.get('file_count', 0)
            file_count = coerce_int(file_count_raw) or 0
            normalized = await DupeChecker.normalize_filename(each)
            type_id = entry.get('type', None)
            res_id = entry.get('res', None)

            # Use flags field if available for more accurate HDR detection
            flags_value = cast(list[Any], entry.get('flags') or [])
            flags = [str(flag) for flag in flags_value]

            if flags:
                # If flags are provided, use them directly for HDR information
                file_hdr: set[str] = set()
                for flag in flags:
                    flag_upper = str(flag).upper()
                    if flag_upper == 'DV':
                        file_hdr.add('DV')
                    elif flag_upper in ['HDR', 'HDR10', 'HDR10+']:
                        file_hdr.add('HDR')
                if meta.get('debug'):
                    console.log(f"[debug] Using flags for HDR detection: {flags} -> {file_hdr}")
            else:
                # Fall back to parsing filename for HDR terms
                file_hdr = await DupeChecker.refine_hdr_terms(normalized)

            if meta.get('debug'):
                console.log(f"[debug] Evaluating dupe: {each}")
                console.log(f"[debug] Normalized dupe: {normalized}")
                console.log(f"[debug] Target resolution: {target_resolution}")
                console.log(f"[debug] Target source: {target_source}")
                console.log(f"[debug] File HDR terms: {file_hdr}")
                console.log(f"[debug] Flags: {flags}")
                console.log(f"[debug] Target HDR terms: {target_hdr}")
                console.log(f"[debug] Target Season: {target_season}")
                console.log(f"[debug] Target Episode: {target_episode}")
                console.log(f"[debug] TAG: {tag}")
                console.log("[debug] Evaluating repack condition:")
                console.log(f"  has_repack_in_uuid: {has_repack_in_uuid}")
                console.log(f"  'repack' in each.lower(): {'repack' in each.lower()}")
                console.log(f"[debug] meta['uuid']: {meta.get('uuid', '')}")
                console.log(f"[debug] normalized encoder: {normalized_encoder}")
                console.log(f"[debug] type_id: {type_id}, res_id: {res_id}")
                console.log(f"[debug] link: {entry.get('link', None)}")
                console.log(f"[debug] files: {files[:10]}{'...' if len(files) > 10 else ''}")
                console.log(f"[debug] file_count: {file_count}")

            def remember_match(reason: str) -> None:
                """Persist details about the dupe that triggered a match for later use."""
                matched_name_key = f"{tracker_name}_matched_name"
                matched_link_key = f"{tracker_name}_matched_link"
                matched_download_key = f"{tracker_name}_matched_download"
                matched_reason_key = f"{tracker_name}_matched_reason"
                matched_count_key = f"{tracker_name}_matched_file_count"
                matched_torrent_id = f"{tracker_name}_matched_id"

                meta[matched_name_key] = entry.get('name')
                if entry.get('link'):
                    meta[matched_link_key] = entry.get('link')
                if entry.get('download'):
                    meta[matched_download_key] = entry.get('download')
                meta[matched_reason_key] = reason
                if file_count:
                    meta[matched_count_key] = file_count
                if entry.get('id'):
                    meta[matched_torrent_id] = entry.get('id')

            # Aither-specific trumping logic - no internal checking, if it's marked trumpable, it's trumpable
            if tracker_name == "AITHER" and entry.get('trumpable', False) and res_id and target_resolution == res_id:
                meta['trumpable_id'] = entry.get('id')
                remember_match('trumpable_id')

            if not meta.get('is_disc'):
                for file in filenames:
                    if tracker_name in ["MTV", "AR", "RTF"]:
                        # MTV: check if any dupe file is a substring of our file (ignoring extension)
                        if any(f.lower() in file.lower() for f in files):
                            meta['filename_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                            remember_match('filename')
                            if file_count and file_count == len(filelist):
                                meta['file_count_match'] = file_count
                                remember_match('file_count')
                                return False
                        entry_size = coerce_int(entry.get('size'))
                        source_size = coerce_int(meta.get('source_size'))
                        if entry_size is not None and source_size is not None and entry_size == source_size:
                            meta['size_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                            remember_match('size')
                            return False
                        if meta.get('debug') and entry_size is None and meta.get('source_size') is not None:
                            console.log(
                                f"[debug] Size comparison failed due to ValueError: entry_size={entry.get('size')}, source_size={meta.get('source_size')}"
                            )
                    else:
                        if meta.get('debug'):
                            console.log(f"[debug] Comparing file: {file} against dupe files list.")
                            console.log(f"[debug] Dupe files list: {files[:10]}{'...' if len(files) > 10 else files}")
                        if any(file.lower() == f.lower() for f in files):
                            meta['filename_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                            if meta.get('debug'):
                                console.log(f"[debug] Filename match found: {meta['filename_match']}")
                            remember_match('filename')
                            remember_match('id')
                            if file_count and file_count == len(filelist):
                                meta['file_count_match'] = file_count
                                if meta.get('debug'):
                                    console.log(f"[debug] File count match found: {meta['file_count_match']}")
                                remember_match('file_count')
                                return False
                if tracker_name in ["BHD"]:
                    # BHD: compare sizes
                    entry_size = coerce_int(entry.get('size'))
                    source_size = coerce_int(meta.get('source_size'))
                    if entry_size is not None and source_size is not None:
                        if meta.get('debug'):
                            console.log(f"[debug] Comparing sizes: Entry size {entry_size} vs Source size {source_size}")
                        if entry_size == source_size:
                            meta['size_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                            remember_match('size')
                            return False
                    elif meta.get('debug') and entry_size is None and meta.get('source_size') is not None:
                        console.log(
                            f"[debug] Size comparison failed due to ValueError: entry_size={entry.get('size')}, source_size={meta.get('source_size')}"
                        )

            else:
                entry_size = coerce_int(entry.get('size'))
                source_size = coerce_int(meta.get('source_size'))
                if entry_size is not None and source_size is not None:
                    if meta.get('debug'):
                        console.log(f"[debug] Comparing sizes: Entry size {entry_size} vs Source size {source_size}")
                    if entry_size == source_size:
                        meta['size_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                        remember_match('size')
                        return False
                elif meta.get('debug') and entry_size is None and meta.get('source_size') is not None:
                    console.log(
                        f"[debug] Size comparison failed due to ValueError: entry_size={entry.get('size')}, source_size={meta.get('source_size')}"
                    )

            if meta.get('is_disc') and file_count and file_count < 2:
                await log_exclusion("file count less than 2 for disc upload", each)
                return True

            if has_repack_in_uuid and "repack" not in normalized and str(meta.get('tag', '')).lower() in normalized:
                await log_exclusion('repack release', each)
                return True

            if tracker_name == "MTV":
                target_name = str(meta.get('name', '')).replace(' ', '.').replace('DD+', 'DDP')
                dupe_name = str(entry.get('name', ''))

                def normalize_mtv_name(name: str) -> str:
                    # Handle audio format variations: DDP.5.1 <-> DDP5.1
                    name = re.sub(r'\.DDP\.(\d)', r'.DDP\1', name)
                    name = re.sub(r'\.DD\.(\d)', r'.DD\1', name)
                    name = re.sub(r'\.AC3\.(\d)', r'.AC3\1', name)
                    name = re.sub(r'\.DTS\.(\d)', r'.DTS\1', name)
                    return name

                normalized_target = normalize_mtv_name(target_name)
                if normalized_target == dupe_name:
                    meta['filename_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                    return False

            if tracker_name == "BHD":
                target_name = str(meta.get('name', '')).replace('DD+', 'DDP')
                if str(entry.get('name')) == target_name:
                    meta['filename_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                    return False

            if tracker_name == "HUNO":
                huno = HUNO(config=self.config)
                huno_name_result: Any = await huno.get_name(cast(dict[str, Any], meta))
                huno_name_map = cast(dict[str, Any], huno_name_result)
                huno_name = str(huno_name_map.get('name', huno_name_result)) if isinstance(huno_name_result, dict) else str(huno_name_result)
                if str(entry.get('name')) == huno_name:
                    meta['filename_match'] = f"{entry.get('name')} = {entry.get('link', None)}"
                    return False

            if tracker_name in ["BHD", "MTV", "RTF", "AR"] and (
                ('2160p' in target_resolution and '2160p' in each)
                and ('framestor' in each.lower() or 'framestor' in str(meta.get('uuid', '')).lower())
            ):
                return False

            if has_is_disc and each.lower().endswith(".m2ts"):
                return False

            if has_is_disc and re.search(r'\.\w{2,4}$', each):
                await log_exclusion("file extension mismatch (is_disc=True)", each)
                return True

            if meta.get('is_disc') == "BDMV" and tracker_name in ["HDB", "BHD"]:
                if len(each) >= 1 and tag == "":
                    return False
                return not (tag.strip() and tag.strip() in normalized)

            if is_sd == 1 and tracker_name in {"BHD", "AITHER"} and any(str(res) in each for res in [1080, 720, 2160]):
                return False

            if target_hdr and '1080p' in target_resolution and '2160p' in each:
                await log_exclusion("No 1080p HDR when 4K exists", each)
                return False

            if tracker_name in ["AITHER", "LST"] and is_dvd:
                if len(each) >= 1 and tag == "":
                    return False
                return not (tag.strip() and tag.strip() in normalized)

            if web_dl:
                if "hdtv" in normalized and not any(web_term in normalized for web_term in ["web-dl", "web -dl", "webdl", "web dl"]):
                    await log_exclusion("source mismatch: WEB-DL vs HDTV", each)
                    return True
                if any(term in normalized for term in ['blu-ray', 'blu ray', 'bluray', 'blu -ray']) and not any(
                    web_term in normalized for web_term in ["web-dl", "web -dl", "webdl", "web dl"]
                ):
                    await log_exclusion("source mismatch: WEB-DL vs BluRay", each)
                    return True
            if not web_dl and any(web_term in normalized for web_term in ["web-dl", "web -dl", "webdl", "web dl"]):
                await log_exclusion("source mismatch: non-WEB-DL vs WEB-DL", each)
                return True

            skip_resolution_check = bool(is_dvd or "DVD" in target_source or is_dvdrip)

            if not skip_resolution_check:
                if target_resolution and target_resolution not in each:
                    await log_exclusion(f"resolution '{target_resolution}' mismatch", each)
                    return True
                if not await DupeChecker.has_matching_hdr(file_hdr, target_hdr, meta, tracker=tracker_name):
                    await log_exclusion(f"HDR mismatch: Expected {target_hdr}, got {file_hdr}", each)
                    return True

            if is_dvd and tracker_name != "BHD" and any(str(res) in each for res in [1080, 720, 2160]):
                await log_exclusion(f"resolution '{target_resolution}' mismatch", each)
                return False

            for check in attribute_checks:
                if check["key"] == "repack":
                    if has_repack_in_uuid and "repack" not in normalized and tag and tag in normalized:
                        await log_exclusion("missing 'repack'", each)
                        return True
                elif check["key"] == "remux":
                    # Bidirectional check: if your upload is a REMUX, dupe must be REMUX
                    # If your upload is NOT a REMUX (i.e., an encode), dupe must NOT be a REMUX
                    uuid_has_remux = check["uuid_flag"]
                    dupe_has_remux = check["condition"](normalized)

                    if meta.get('debug'):
                        console.log(f"[debug] Remux check: uuid_has_remux={uuid_has_remux}, dupe_has_remux={dupe_has_remux}")

                    if uuid_has_remux and not dupe_has_remux:
                        await log_exclusion("missing 'remux'", each)
                        return True
                    if not uuid_has_remux and dupe_has_remux:
                        await log_exclusion("dupe is remux but upload is not", each)
                        return True

            if meta.get('category') == "TV":
                season_episode_match, is_season = await DupeChecker.is_season_episode_match(normalized, target_season, target_episode)
                if meta.get('debug'):
                    console.log(f"[debug] Season/Episode match result: {season_episode_match}")
                    console.log(f"[debug] is_season: {is_season}")
                # Aither episode trumping logic
                if is_season and tracker_name == "AITHER":
                    # Null-safe normalization for comparisons
                    target_source_lower = (target_source or "").lower()
                    type_id_lower = (type_id or "").lower()
                    res_id_safe = res_id or ""
                    target_resolution_safe = target_resolution or ""

                    if type_id_lower and res_id_safe:
                        if meta.get('debug'):
                            console.log(
                                f"[debug] Checking trumping: target_source='{target_source_lower}', type_id='{type_id_lower}', target_res='{target_resolution_safe}', res_id='{res_id_safe}'"
                            )
                        if target_source_lower in type_id_lower and target_resolution_safe == res_id_safe:
                            if meta.get('debug'):
                                console.log(f"[debug] Episode with matching source and resolution found for trumping: {each}")

                            is_internal = False
                            if entry.get('internal', 0) == 1:
                                trackers_section: dict[str, Any] = cast(dict[str, Any], self.config.get('TRACKERS', {}))
                                aither_settings: dict[str, Any] = trackers_section.get('AITHER', {})
                                if aither_settings.get('internal') is True:
                                    internal_groups = aither_settings.get('internal_groups', [])
                                    if isinstance(internal_groups, list):
                                        tag_without_prefix = tag[1:] if tag else ""
                                        if tag_without_prefix in internal_groups and tag_without_prefix.lower() in normalized:
                                            is_internal = True
                                if not is_internal and meta.get('debug'):
                                    console.log("[debug] Skipping internal episode for trumping since you're not the internal uploader.")

                            if not entry.get('internal', False) or is_internal:
                                # Store the matched episode ID/s for later use
                                # is_season=True means seasons match, which is sufficient for trump targeting
                                # (season pack can trump individual episodes from same season)
                                matched_episode_ids = cast(list[dict[str, Any]], meta.setdefault('matched_episode_ids', []))

                                entry_id = entry.get('id')
                                entry_link = entry.get('link')

                                # De-duplication guard: check if this entry already exists
                                already_exists = (
                                    any(
                                        existing.get('id') == entry_id
                                        or (existing.get('link') == entry_link and existing.get('tracker') == tracker_name)
                                        for existing in matched_episode_ids
                                    )
                                    if entry_id or entry_link
                                    else False
                                )

                                if entry_id and not already_exists:
                                    matched_episode_ids.append({
                                        'id': entry_id,
                                        'name': each,
                                        'link': entry_link,
                                        'tracker': tracker_name,
                                        'internal': entry.get('internal', 0),
                                    })
                                    if meta.get('debug'):
                                        console.log(f"[debug] Added episode ID {entry_id} to matched list")
                                    # Don't exclude this entry - it's a valid trump target
                                    return False
                                if already_exists and meta.get('debug'):
                                    console.log(f"[debug] Skipping duplicate entry for episode ID {entry_id}")

                # Normal season/episode matching
                if not season_episode_match:
                    await log_exclusion("season/episode mismatch", each)
                    return True

                # Check if uploading an episode but a matching season pack exists
                if is_season and target_episode:
                    # We're uploading an episode and found a matching season pack
                    meta['season_pack_exists'] = True
                    meta['season_pack_name'] = each
                    meta['season_pack_link'] = entry.get('link')
                    meta['season_pack_id'] = entry.get('id')
                    if meta.get('debug'):
                        console.log(f"[yellow]Season pack detected for episode upload: {each}")
                        console.log(f"[yellow]Your episode {target_season}{target_episode} is contained in existing season pack")
                    remember_match('season_pack_contains_episode')
                    return False

            if is_hdtv and any(web_term in normalized for web_term in ["web-dl", "web -dl", "webdl", "web dl"]):
                return False

            if (
                len(dupes) == 1
                and meta.get('is_disc') != "BDMV"
                and tracker_name in ["AITHER", "BHD", "HUNO", "OE", "ULCX"]
                and file_size is not None
                and "1080" in target_resolution
                and 'x264' in video_encode_lower
            ):
                target_size = file_size
                dupe_size = coerce_int(sized)

                if dupe_size is not None and dupe_size != 0:
                    size_difference = (target_size - dupe_size) / dupe_size
                    if meta.get('debug'):
                        console.print(f"Your size: {target_size}, Dupe size: {dupe_size}, Size difference: {size_difference:.4f}")
                    if size_difference >= 0.20:
                        await log_exclusion(f"Your file is significantly larger ({size_difference * 100:.2f}%)", each)
                        return True
            if len(dupes) == 1 and meta.get('is_disc') != "BDMV" and tracker_name == "RF":
                if tag.strip() and tag.strip() in normalized:
                    return False
                if tag.strip() and tag.strip() not in normalized:
                    await log_exclusion(f"Tag '{tag}' not found in normalized name", each)
                    return True

            if meta.get('debug'):
                console.log(f"[debug] Passed all checks: {each}")
            return False

        new_dupes = [each for each in processed_dupes if not await process_exclusion(each)]

        if new_dupes and not meta.get('unattended', False) and meta.get('debug'):
            console.log(f"[yellow]Filtered dupes on {tracker_name}: ")
            # Limit filtered dupe output for readability
            filtered_dupes_to_print: list[dict[str, Any]] = []

            for dupe in new_dupes:
                limited_dupe = Redaction.redact_private_info(dupe).copy()
                # Limit files list to first 10 items
                limited_files = limited_dupe.get('files', [])
                if len(limited_files) > 10:
                    dupe_files = dupe.get('files', [])
                    limited_dupe['files'] = limited_files[:10] + [f"... and {len(dupe_files) - 10} more files"]

                if isinstance(limited_dupe.get('description'), str) and len(limited_dupe['description']) > 200:
                    limited_dupe['description'] = limited_dupe['description'][:200] + "..."

                filtered_dupes_to_print.append(limited_dupe)

            console.log(filtered_dupes_to_print)

        return new_dupes

    @staticmethod
    async def normalize_filename(filename: Union[str, MutableMapping[str, Any]]) -> str:
        if isinstance(filename, dict):
            filename = str(filename.get('name', ''))
        if not isinstance(filename, str):
            raise ValueError(f"Expected a string or a dictionary with a 'name' key, but got: {type(filename)}")
        normalized = filename.lower().replace("-", " -").replace(" ", " ").replace(".", " ")

        return normalized

    @staticmethod
    async def is_season_episode_match(
        filename: str,
        target_season: Optional[Union[str, int]],
        target_episode: Optional[Union[str, int]],
    ) -> tuple[bool, bool]:
        """
        Check if the filename matches the given season and episode.
        """
        season_match = re.search(r'[sS](\d+)', str(target_season))
        target_season_value = int(season_match.group(1)) if season_match else None

        if target_episode:
            episode_matches = re.findall(r'\d+', str(target_episode))
            target_episodes = [int(ep) for ep in episode_matches]
        else:
            target_episodes = []

        season_pattern = rf"[sS]{target_season_value:02}" if target_season_value is not None else None
        episode_patterns = [rf"[eE]{ep:02}" for ep in target_episodes] if target_episodes else []

        # Determine if filename represents a season pack (no explicit episode pattern)
        is_season_pack = not re.search(r"[eE]\d{2}", filename, re.IGNORECASE)

        # If `target_episode` is empty, match only season packs
        if not target_episodes:
            season_matches = bool(season_pattern and re.search(season_pattern, filename, re.IGNORECASE))
            return (season_matches and is_season_pack, season_matches)

        # If `target_episode` is provided, match both season packs and episode files
        if season_pattern:
            if is_season_pack:
                return (bool(re.search(season_pattern, filename, re.IGNORECASE)), True)  # Match season pack
            if episode_patterns:
                return (
                    bool(re.search(season_pattern, filename, re.IGNORECASE))
                    and any(re.search(ep, filename, re.IGNORECASE) for ep in episode_patterns),
                    False,
                )  # Match episode file

        return (False, False)  # No match

    @staticmethod
    async def refine_hdr_terms(hdr: Optional[str]) -> set[str]:
        """
        Normalize HDR terms for consistent comparison.
        Simplifies all HDR entries to 'HDR' and DV entries to 'DV'.
        """
        if hdr is None:
            return set()
        hdr_upper = str(hdr).upper()
        terms: set[str] = set()
        if "DV" in hdr_upper or "DOVI" in hdr_upper:
            terms.add("DV")
        if "HDR" in hdr_upper:  # Any HDR-related term is normalized to 'HDR'
            terms.add("HDR")
        return terms

    @staticmethod
    async def has_matching_hdr(file_hdr: set[str], target_hdr: set[str], meta: Meta, tracker: Optional[str] = None) -> bool:
        """
        Check if the HDR terms match or are compatible.
        """
        def simplify_hdr(hdr_set: set[str], tracker_name: Optional[str] = None) -> set[str]:
            """Simplify HDR terms to just HDR and DV."""
            simplified: set[str] = set()
            if any(h in hdr_set for h in {"HDR", "HDR10", "HDR10+"}):
                simplified.add("HDR")
            if any(h == "DV" or "DV" in h for h in hdr_set):
                simplified.add("DV")
                meta_type = str(meta.get('type', '')).lower()
                if 'web' not in meta_type:
                    simplified.add("HDR")
                if tracker_name == "ANT":
                    simplified.add("HDR")
            return simplified

        file_hdr_simple = simplify_hdr(file_hdr, tracker)
        target_hdr_simple = simplify_hdr(target_hdr, tracker)

        if file_hdr_simple in [{"DV", "HDR"}, {"HDR", "DV"}]:
            file_hdr_simple = {"HDR"}
            if target_hdr_simple in [{"DV", "HDR"}, {"HDR", "DV"}]:
                target_hdr_simple = {"HDR"}

        return file_hdr_simple == target_hdr_simple


async def filter_dupes(dupes: Sequence[DupeInput], meta: Meta, tracker_name: str, config: dict[str, Any]) -> list[DupeEntry]:
    return await DupeChecker(config).filter_dupes(dupes, meta, tracker_name)


async def normalize_filename(filename: Union[str, MutableMapping[str, Any]]) -> str:
    return await DupeChecker.normalize_filename(filename)


async def is_season_episode_match(
    filename: str,
    target_season: Optional[Union[str, int]],
    target_episode: Optional[Union[str, int]],
) -> tuple[bool, bool]:
    return await DupeChecker.is_season_episode_match(filename, target_season, target_episode)


async def refine_hdr_terms(hdr: Optional[str]) -> set[str]:
    return await DupeChecker.refine_hdr_terms(hdr)


async def has_matching_hdr(
    file_hdr: set[str],
    target_hdr: set[str],
    meta: Meta,
    tracker: Optional[str] = None,
) -> bool:
    return await DupeChecker.has_matching_hdr(file_hdr, target_hdr, meta, tracker=tracker)
