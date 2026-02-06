# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import re
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional, Union, cast

import cli_ui
import langcodes

from src.console import console
from src.trackers.COMMON import COMMON


# Specific exception for lossy DTS core duplicate detection
class LossyDtsDuplicateError(ValueError):
    pass

Meta = dict[str, Any]
TrackDict = dict[str, Any]


class AudioManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def get_audio_v2(
        self,
        mi: Mapping[str, Any],
        meta: Meta,
        bdinfo: Optional[Mapping[str, Any]],
    ) -> tuple[str, str, bool]:
        return await _get_audio_v2(self.config, mi, meta, bdinfo)


def determine_channel_count(
    channels: Any,
    channel_layout: Optional[str],
    additional: Any,
    format: Any,
) -> str:
    # Coerce channels to string and extract first integer (handles values like "6 channels", "8 / 6", etc.)
    s = str(channels).strip() if channels is not None else ""
    m = re.search(r"\d+", s)
    if not m:
        return "Unknown"

    channels = int(m.group(0))
    channel_layout = channel_layout.strip() if channel_layout else ""

    # Handle specific Atmos/immersive audio cases first
    if is_atmos_or_immersive_audio(additional, format, channel_layout) and channel_layout:
        return handle_atmos_channel_count(channels, channel_layout)

    # Handle standard channel layouts with proper LFE detection
    if channel_layout:
        return parse_channel_layout(channels, channel_layout)

    # Fallback for when no layout information is available
    return fallback_channel_count(channels)


def is_atmos_or_immersive_audio(additional: Any, format: Any, channel_layout: Optional[str]) -> bool:
    """Check if this is Dolby Atmos, DTS:X, or other immersive audio format."""
    atmos_indicators = [
        'JOC', 'Atmos', '16-ch', 'Atmos Audio',
        'TrueHD Atmos', 'E-AC-3 JOC', 'Dolby Atmos'
    ]

    dtsx_indicators = ['DTS:X', 'XLL X']

    # Check in additional features
    if additional and any(indicator in str(additional) for indicator in atmos_indicators + dtsx_indicators):
        return True

    # Check in format
    if format and any(indicator in str(format) for indicator in atmos_indicators + dtsx_indicators):
        return True

    # Check for height channels in layout (indicating immersive audio)
    if channel_layout:
        height_indicators = [
            'Tfc', 'Tfl', 'Tfr', 'Tbl', 'Tbr', 'Tbc',  # Top channels
            'TFC', 'TFL', 'TFR', 'TBL', 'TBR', 'TBC',  # Top channels (uppercase)
            'Vhc', 'Vhl', 'Vhr',  # Vertical height channels
            'Ch', 'Lh', 'Rh', 'Chr', 'Lhr', 'Rhr',  # Height variants
            'Top', 'Height'  # Generic height indicators
        ]
        if any(indicator in channel_layout for indicator in height_indicators):
            return True

    return False


def handle_atmos_channel_count(channels: int, channel_layout: str) -> str:
    """Handle Dolby Atmos and immersive audio channel counting."""

    # Parse the layout to count bed and height channels
    bed_channels, lfe_count, height_channels = parse_atmos_layout(channel_layout)

    if height_channels > 0:
        if lfe_count > 0:
            return f"{bed_channels}.{lfe_count}.{height_channels}"
        else:
            return f"{bed_channels}.0.{height_channels}"
    else:
        # Fallback to standard counting
        return parse_channel_layout(channels, channel_layout)


def parse_atmos_layout(channel_layout: Optional[str]) -> tuple[int, int, int]:
    """Parse channel layout to separate bed channels, LFE, and height channels."""
    if not channel_layout:
        return 0, 0, 0

    layout = channel_layout.upper()

    # Split by spaces to get individual channel identifiers
    channels = layout.split()
    bed_count = 0
    height_count = 0
    lfe_count = 0

    for channel in channels:
        channel = channel.strip()
        if not channel:
            continue

        # Check for LFE first
        if 'LFE' in channel:
            lfe_count += 1
        # Check for height channels
        elif any(height_indicator in channel for height_indicator in [
            'TFC', 'TFL', 'TFR', 'TBL', 'TBR', 'TBC',  # Top channels
            'VHC', 'VHL', 'VHR',  # Vertical height
            'CH', 'LH', 'RH', 'CHR', 'LHR', 'RHR',  # Height variants
            'TSL', 'TSR', 'TLS', 'TRS'  # Top surround
        ]):
            height_count += 1
        # Everything else is a bed channel
        elif channel in ['L', 'R', 'C', 'FC', 'LS', 'RS', 'SL', 'SR',
                         'BL', 'BR', 'BC', 'SB', 'FLC', 'FRC', 'LC', 'RC',
                         'LW', 'RW', 'FLW', 'FRW', 'LSS', 'RSS', 'SIL', 'SIR',
                         'LB', 'RB', 'CB', 'CS']:
            bed_count += 1

    return bed_count, lfe_count, height_count


def parse_channel_layout(channels: int, channel_layout: str) -> str:
    """Parse standard channel layout to determine proper channel count notation."""
    layout = channel_layout.upper()

    # Count LFE channels
    lfe_count = layout.count('LFE')
    if lfe_count == 0 and 'LFE' in layout:
        lfe_count = 1

    # Handle multiple LFE channels (rare but possible)
    if lfe_count > 1:
        main_channels = channels - lfe_count
        return f"{main_channels}.{lfe_count}"
    elif lfe_count == 1:
        return f"{channels - 1}.1"
    else:
        if "object" in channel_layout.lower() and channels > 7:
            channels -= 1
            # Object-based audio without LFE, assume .1 configuration
            return f"{channels}.1"
        # No LFE detected
        if channels <= 2:
            return f"{channels}.0"
        else:
            # Check for specific mono layouts
            if 'MONO' in layout or channels == 1:
                return "1.0"
            # Check for specific stereo layouts
            elif channels == 2:
                return "2.0"
            # For multichannel without LFE, assume it's a .0 configuration
            else:
                return f"{channels}.0"


def fallback_channel_count(channels: int) -> str:
    """Fallback channel counting when no layout information is available."""
    if channels <= 2:
        return f"{channels}.0"
    elif channels == 3:
        return "2.1"  # Assume L/R/LFE
    elif channels == 4:
        return "3.1"  # Assume L/R/C/LFE
    elif channels == 5:
        return "4.1"  # Assume L/R/Ls/Rs/LFE
    elif channels == 6:
        return "5.1"  # Standard 5.1
    elif channels == 7:
        return "6.1"  # 6.1 or 7.0
    elif channels == 8:
        return "7.1"  # Standard 7.1
    else:
        return f"{channels - 1}.1"


async def _get_audio_v2(
    config: dict[str, Any],
    mi: Mapping[str, Any],
    meta: Meta,
    bdinfo: Optional[Mapping[str, Any]],
) -> tuple[str, str, bool]:
    extra = ""
    dual = ""
    has_commentary = False
    meta['bloated'] = False
    is_auro3d = False
    bd_mi = None
    additional: Any = ""
    format: Any = ""
    commercial: Any = ""
    chan: str = ""
    format_settings: str = ""
    format_profile: str = ""
    channel_layout: str = ""
    codec: str = ""

    # Get formats
    if bdinfo is not None:  # Disks
        audio_entries = cast(list[dict[str, Any]], bdinfo.get('audio', [{}]))
        first_audio: dict[str, Any] = audio_entries[0] if audio_entries else {}
        additional = first_audio.get('atmos_why_you_be_like_this', '')
        if isinstance(additional, str) and 'atmos' in additional.lower():
            common = COMMON(config)
            bd_mi = await common.get_bdmv_mediainfo(meta)
            try:
                base_dir = meta.get('base_dir')
                folder_id = meta.get('uuid') or meta.get('folder_id')
                if base_dir and folder_id:
                    mi_path = os.path.join(base_dir, 'tmp', folder_id, 'MediaInfo.json')
                    if os.path.exists(mi_path):
                        mi_text = await asyncio.to_thread(Path(mi_path).read_text, encoding='utf-8')
                        mi = json.loads(mi_text)
                        if meta.get('debug'):
                            console.print(f"[yellow]Loaded MediaInfo from file:[/yellow] {mi_path}")
            except Exception:
                if meta.get('debug'):
                    console.print("[red]Failed to load MediaInfo.json from tmp directory[/red]")
                    console.print(traceback.format_exc())
                bd_mi = None
        else:
            format_settings = ""
            format = first_audio.get('codec', '')
            commercial = format
            chan = str(first_audio.get('channels', '') or '')

    if bdinfo is None or bd_mi is not None:  # Rips or BD with mediainfo
        mi_map = mi
        tracks = cast(list[TrackDict], cast(Mapping[str, Any], mi_map.get('media', {})).get('track', []))
        audio_tracks = [t for t in tracks if t.get('@type') == "Audio"]
        meta["has_multiple_default_audio_tracks"] = len(
            [track for track in audio_tracks if track.get("Default") == "Yes"]) > 1
        meta["non_disc_has_pcm_audio_tracks"] = meta.get("type") != "DISC" and any(
            track.get("Format") == "PCM" for track in audio_tracks)
        first_audio_track = None
        if audio_tracks:
            tracks_with_order = [t for t in audio_tracks if t.get('StreamOrder') and not isinstance(t.get('StreamOrder'), dict)]
            if tracks_with_order:
                try:
                    first_audio_track = min(tracks_with_order, key=lambda x: int(str(x.get('StreamOrder', '999'))))
                except (ValueError, TypeError):
                    first_audio_track = tracks_with_order[0]
            else:
                tracks_with_id = [t for t in audio_tracks if t.get('ID') and not isinstance(t.get('ID'), dict)]
                if tracks_with_id:
                    try:
                        # Extract numeric part from ID (e.g., "128 (0x80)" -> 128)
                        def get_id_num(x: Mapping[str, Any]) -> int:
                            id_match = re.search(r'\d+', str(x.get('ID', '999')))
                            return int(id_match.group()) if id_match else 999
                        first_audio_track = min(tracks_with_id, key=get_id_num)
                    except (ValueError, TypeError, AttributeError):
                        first_audio_track = tracks_with_id[0]
                else:
                    first_audio_track = audio_tracks[0]

        track: TrackDict = first_audio_track or {}
        format = track.get('Format', '')
        commercial = track.get('Format_Commercial', '') or track.get('Format_Commercial_IfAny', '')
        if track.get('Language', '') == "zxx":
            meta['silent'] = True

        additional = track.get('Format_AdditionalFeatures', '')

        format_settings = str(track.get('Format_Settings') or "")
        if format_settings in ['Explicit']:
            format_settings = ""
        format_profile = track.get('Format_Profile', '')
        # Channels
        channels = track.get('Channels_Original', track.get('Channels'))
        if not str(channels).isnumeric():
            channels = track.get('Channels')
        try:
            channel_layout = (
                track.get('ChannelLayout', '')
                or track.get('ChannelLayout_Original', '')
                or track.get('ChannelPositions', '')
            )
        except Exception:
            channel_layout = ''

        # Enhanced channel count determination based on MediaArea AudioChannelLayout
        if meta.get('debug'):
            console.print(f"DEBUG: Channels: {channels}, Channel Layout: {channel_layout}, Additional: {additional}, Format: {format}")
        chan = determine_channel_count(channels, channel_layout, additional, format)

        try:
            dts_core_additional_check(meta)
        except LossyDtsDuplicateError:
            # Propagate specific error so callers can handle it explicitly
            raise

        if meta.get('dual_audio', False):
            dual = "Dual-Audio"
        else:
            # if not meta.get('original_language', '').startswith('en'):
            if not meta['is_disc']:
                eng, orig, non_en_non_commentary = False, False, False
                orig_lang = meta.get('original_language', '').lower()
                if meta['debug']:
                    console.print(f"DEBUG: Original Language: {orig_lang}")
                try:
                    tracks = cast(list[TrackDict], cast(Mapping[str, Any], mi_map.get('media', {})).get('track', []))
                    # no proper auro3d marker in mediainfo, which leaves us vulnerable to misdetection
                    # only scope the first track to reduce false positives
                    first_audio_track = next((t for t in tracks if t.get('@type') == "Audio"), None)
                    first_audio_title = None
                    if first_audio_track:
                        first_audio_title = first_audio_track.get('title') or first_audio_track.get('Title')
                    is_auro3d = bool(first_audio_title and 'auro3d' in str(first_audio_title).lower())
                    has_commentary = False
                    has_compatibility = False
                    has_coms = [t for t in tracks if "commentary" in str(t.get('Title') or '').lower()]
                    has_compat = [t for t in tracks if "compatibility" in str(t.get('Title') or '').lower()]
                    if has_coms:
                        has_commentary = True
                    if has_compat:
                        has_compatibility = True
                    if meta['debug']:
                        console.print(f"DEBUG: Found {len(has_coms)} commentary tracks, has_commentary = {has_commentary}")
                        console.print(f"DEBUG: Found {len(has_compat)} compatibility tracks, has_compatibility = {has_compatibility}")
                    audio_tracks = [
                        t
                        for t in tracks
                        if t.get('@type') == "Audio"
                        and "commentary" not in str(t.get('Title') or '').lower()
                        and "compatibility" not in str(t.get('Title') or '').lower()
                    ]
                    audio_language = None
                    if meta['debug']:
                        console.print(f"DEBUG: Audio Tracks (not commentary)= {len(audio_tracks)}")

                    # First pass: collect all audio languages and set flags
                    non_eng_non_orig_languages: list[str] = []
                    for t in audio_tracks:
                        audio_language = str(t.get('Language') or '')
                        if meta['debug']:
                            console.print(f"DEBUG: Audio Language = {audio_language}")
                        audio_language = audio_language.lower().strip()
                        if audio_language.startswith("en"):
                            if meta['debug']:
                                console.print(f"DEBUG: Found English audio track: {audio_language}")
                            eng = True

                        if audio_language and "en" not in audio_language and audio_language.startswith(orig_lang):
                            if meta['debug']:
                                console.print(f"DEBUG: Found original language audio track: {audio_language}")
                            orig = True

                        variants = ['zh', 'cn', 'cmn', 'no', 'nb']
                        if any(audio_language.startswith(var) for var in variants) and any(orig_lang.startswith(var) for var in variants):
                            if meta['debug']:
                                console.print(f"DEBUG: Found original language audio track with variant: {audio_language}")
                            orig = True

                        if audio_language and not audio_language.startswith(orig_lang) and not audio_language.startswith("en") and not audio_language.startswith("zx"):
                            non_en_non_commentary = True
                            non_eng_non_orig_languages.append(audio_language)

                    # Second pass: now that we have complete information about all tracks, check for bloat
                    if non_eng_non_orig_languages:
                        # Compute is_eng_original once with complete track information
                        is_eng_original = (orig_lang == "en" and eng and non_en_non_commentary)

                        # Check all non-English, non-original languages for bloat
                        bloated_check(meta, non_eng_non_orig_languages, is_eng_original_with_non_eng=is_eng_original)

                    if ((eng and (orig or non_en_non_commentary)) or (orig and non_en_non_commentary)) and len(audio_tracks) > 1 and not meta.get('no_dual', False):
                        dual = "Dual-Audio"
                        meta['dual_audio'] = True
                    elif eng and not orig and orig_lang not in ['zxx', 'xx', 'en', None] and not meta.get('no_dub', False):
                        dual = "Dubbed"
                except Exception:
                    console.print(traceback.format_exc())
                    pass

    # Convert commercial name to naming conventions
    audio_codec_map = {
        "DTS": "DTS",
        "AAC": "AAC",
        "AAC LC": "AAC",
        "AC-3": "DD",
        "E-AC-3": "DD+",
        "A_EAC3": "DD+",
        "Enhanced AC-3": "DD+",
        "MLP FBA": "TrueHD",
        "FLAC": "FLAC",
        "Opus": "Opus",
        "Vorbis": "VORBIS",
        "PCM": "LPCM",
        "LPCM Audio": "LPCM",
        "Dolby Digital Audio": "DD",
        "Dolby Digital Plus Audio": "DD+",
        "Dolby Digital Plus": "DD+",
        "Dolby TrueHD Audio": "TrueHD",
        "DTS Audio": "DTS",
        "DTS-HD Master Audio": "DTS-HD MA",
        "DTS-HD High-Res Audio": "DTS-HD HRA",
        "DTS:X Master Audio": "DTS:X"
    }
    audio_extra = {
        "XLL": "-HD MA",
        "XLL X": ":X",
        "ES": "-ES",
    }
    format_extra = {
        "JOC": " Atmos",
        "16-ch": " Atmos",
        "Atmos Audio": " Atmos",
    }
    format_settings_extra = {
        "Dolby Surround EX": "EX"
    }

    commercial_names = {
        "Dolby Digital": "DD",
        "Dolby Digital Plus": "DD+",
        "Dolby TrueHD": "TrueHD",
        "DTS-ES": "DTS-ES",
        "DTS-HD High": "DTS-HD HRA",
        "Free Lossless Audio Codec": "FLAC",
        "DTS-HD Master Audio": "DTS-HD MA"
    }

    search_format = True

    if isinstance(additional, dict):
        additional = ""  # Set empty string if additional is a dictionary

    additional_str = str(additional or "")
    format_str = str(format or "")
    commercial_str = str(commercial or "")

    if commercial_str:
        for key, value in commercial_names.items():
            if key in commercial_str:
                codec = value
                search_format = False
            if "Atmos" in commercial_str or format_extra.get(additional_str, "") == " Atmos":
                extra = " Atmos"

    if search_format:
        codec = audio_codec_map.get(format_str, "") + audio_extra.get(additional_str, "")
        extra = format_extra.get(additional_str, "")

    format_settings = format_settings_extra.get(format_settings, "")
    format_settings = "EX" if format_settings == "EX" and chan == "5.1" else ""

    if codec == "":
        codec = format_str

    if format_str.startswith("DTS") and additional_str and additional_str.endswith("X"):
        codec = "DTS:X"

    if format_str == "MPEG Audio":
        if format_profile == "Layer 2":
            codec = "MP2"
        elif format_profile == "Layer 3":
            codec = "MP3"

    if codec == "DD" and chan == "7.1":
        console.print("[warning] Detected codec is DD but channel count is 7.1, correcting to DD+")
        codec = "DD+"

    if not extra and is_auro3d:
        extra = " Auro3D"

    audio = f"{dual} {codec or ''} {format_settings or ''} {chan or ''}{extra or ''}"
    audio = ' '.join(audio.split())
    return audio, chan, has_commentary


def bloated_check(meta: Meta, audio_languages: Union[Sequence[str], str], is_eng_original_with_non_eng: bool = False) -> None:
    # Normalize to list
    if isinstance(audio_languages, str):
        audio_languages = [audio_languages]

    bloat_is_allowed = ["ASC", "BJS", "BT", "CBR", "DC", "FF", "LCD", "SAM", "SHRI", "SP", "TL", "TOS"]
    # Trackers that allow specific languages (list of allowed language codes per tracker)
    tracker_allowed_bloat_languages = {
        "AITHER": ["en"],
        "ANT": ["en"],
        "BLU": ["en"],
        "ITT": ["it"],
        "LT": ["es"],
        "PT": ["pt"],
        "SPD": ["ro"],
        "TTR": ["es"],
        "UTP": ["uk", "en"],
    }

    # Track whether we've already printed messages
    printed_not_allowed = False
    printed_warning = False

    # Loop through each audio language
    for audio_language in audio_languages:
        trackers_to_warn: list[str] = []

        for tracker in cast(list[str], meta.get("trackers", [])):
            # Check if this language is in the tracker's allowed languages list
            if tracker in tracker_allowed_bloat_languages:
                allowed_langs = tracker_allowed_bloat_languages[tracker]
                if any(audio_language.lower().startswith(lang.lower()) for lang in allowed_langs):
                    continue
            if tracker not in bloat_is_allowed:
                trackers_to_warn.append(tracker)

        # If no trackers to warn about for this language, continue to next
        if not trackers_to_warn:
            continue

        # Convert language code to full language name
        language_display = audio_language
        try:
            # Clean up the language code - take only the first part before any dash or underscore
            clean_lang = audio_language.split('-')[0].split('_')[0].strip().lower()
            if clean_lang:
                lang = langcodes.Language.get(clean_lang)
                language_display = lang.display_name()
        except (LookupError, AttributeError, ValueError) as e:
            # Silently fall back to the original language code
            if meta.get('debug'):
                console.print(f"[yellow]Debug: Unable to convert language code '{audio_language}' to full name: {e}[/yellow]")

        # Separate trackers that don't allow bloat at all vs those that just warn
        # Only remove trackers if this is an English original with English and non-English tracks
        not_allowed_trackers = []
        warning_trackers = []

        if is_eng_original_with_non_eng:
            not_allowed_trackers = [t for t in trackers_to_warn if t in ["ANT", "BHD", "ULCX", "MTV"]]
            warning_trackers = [t for t in trackers_to_warn if t not in ["ANT", "BHD", "ULCX", "MTV"]]
        else:
            warning_trackers = trackers_to_warn

        # Handle trackers that don't allow bloated releases (only for English original with English and non-English audio)
        if not_allowed_trackers and not printed_not_allowed:
            not_allowed_list = ", ".join(not_allowed_trackers)
            console.print(f"[bold red]This release is English original, has English audio, but also has [bold yellow]{language_display}[/bold yellow] audio and is not allowed on [yellow]{not_allowed_list}[/yellow][/bold red]")
            # Remove these trackers from meta['trackers']
            meta['trackers'] = [t for t in meta.get('trackers', []) if t not in not_allowed_trackers]
            meta['bloated'] = True
            printed_not_allowed = True
            if meta['debug']:
                console.print(f"[yellow]Removed trackers: {not_allowed_list}[/yellow]")
                console.print(f"[yellow]Remaining trackers: {', '.join(meta['trackers']) if meta['trackers'] else 'None'}[/yellow]")

        # Handle trackers that warn about bloat (only print once)
        if warning_trackers and not printed_warning:
            trackers = ", ".join(warning_trackers)
            # If we already printed the not_allowed message, use a simplified message
            if printed_not_allowed:
                warning_msg = f"[bold red]This release may also be considered bloated on [yellow]{trackers}[/yellow][/bold red]"
            else:
                # Build warning message based on context
                if is_eng_original_with_non_eng:
                    warning_msg = f"[bold red]This release is English original, has English audio, but also has [bold yellow]{language_display}[/bold yellow] audio (not commentary).\nThis may be considered bloated on [yellow]{trackers}[/yellow][/bold red]"
                else:
                    warning_msg = f"[bold red]This release has a(n) [bold yellow]{language_display}[/bold yellow] audio track, which is not original language, not English\nand may be considered bloated on [yellow]{trackers}[/yellow][/bold red]"

            console.print(warning_msg)
            printed_warning = True
            meta['bloated'] = True

        # Early exit if we've printed both messages
        if printed_not_allowed and printed_warning:
            return

def dts_core_additional_check(meta: Meta) -> None:
    mediainfo_tracks = meta.get("mediainfo", {}).get("media", {}).get("track") or []
    audio_tracks = [track for track in mediainfo_tracks if track.get("@type") == "Audio"]
    warned_once = False
    # Iterate pairs once (i < j) to avoid duplicate comparisons
    n = len(audio_tracks)
    for i in range(n):
        track_one = audio_tracks[i]
        for j in range(i + 1, n):
            track_two = audio_tracks[j]
            track_one_is_dts_hd_ma = track_one.get("Format_Commercial_IfAny") == "DTS-HD Master Audio"
            track_two_is_dts_hd_ma = track_two.get("Format_Commercial_IfAny") == "DTS-HD Master Audio"
            track_one_is_lossy_dts = (
                track_one.get("Format_Commercial_IfAny") != "DTS-HD Master Audio" and track_one.get("Format") == "DTS"
            )
            track_two_is_lossy_dts = (
                track_two.get("Format_Commercial_IfAny") != "DTS-HD Master Audio" and track_two.get("Format") == "DTS"
            )
            track_one_properties = (
                track_one.get("Duration"),
                track_one.get("FrameRate"),
                track_one.get("FrameCount"),
                track_one.get("Language"),
            )
            track_two_properties = (
                track_two.get("Duration"),
                track_two.get("FrameRate"),
                track_two.get("FrameCount"),
                track_two.get("Language"),
            )
            # Ensure at least one property across both tracks is non-None to avoid matching on empty metadata
            has_meaningful_properties = any(p is not None for p in (*track_one_properties, *track_two_properties))
            # Order-agnostic detection: one track is DTS-HD MA and the other is lossy DTS
            is_pair_hd_lossy = (
                (track_one_is_dts_hd_ma and track_two_is_lossy_dts) or (track_two_is_dts_hd_ma and track_one_is_lossy_dts)
            )
            if is_pair_hd_lossy and has_meaningful_properties and track_one_properties == track_two_properties:
                # Determine which index is HD MA and which is the lossy core for messages
                if track_one_is_dts_hd_ma and track_two_is_lossy_dts:
                    hd_idx, lossy_idx = i + 1, j + 1
                    hd_track = track_one
                else:
                    hd_idx, lossy_idx = j + 1, i + 1
                    hd_track = track_two

                if meta.get("debug"):
                    console.print(
                        f"[yellow]DEBUG: Detected potential DTS core duplicate between tracks {i+1} and {j+1}, matched on properties: (Duration={hd_track.get('Duration')}, FrameRate={hd_track.get('FrameRate')}, FrameCount={hd_track.get('FrameCount')}, Language={hd_track.get('Language')})[/yellow]"
                    )
                if not warned_once:
                    warned_once = True
                    console.print(
                        f"[bold red]DTS audio track #{lossy_idx} appears to be a lossy duplicate of DTS-HD MA track #{hd_idx}.[/bold red]"
                    )
                    if not meta.get("unattended", False) or meta.get("unattended_confirm", False):
                        try:
                            allow = cli_ui.ask_yes_no("Do you want to upload anyway?", default=False)
                        except Exception:
                            allow = False
                        if allow:
                            return
                        else:
                            raise LossyDtsDuplicateError("Upload cancelled due to lossy DTS core duplicate detected.")
                    else:
                        raise LossyDtsDuplicateError("Upload cancelled due to lossy DTS core duplicate detected.")
