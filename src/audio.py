# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import langcodes
import os
import traceback
import re

from data.config import config
from src.console import console
from src.trackers.COMMON import COMMON


def determine_channel_count(channels, channel_layout, additional, format):
    # Coerce channels to string and extract first integer (handles values like "6 channels", "8 / 6", etc.)
    s = str(channels).strip() if channels is not None else ""
    m = re.search(r"\d+", s)
    if not m:
        return "Unknown"

    channels = int(m.group(0))
    channel_layout = channel_layout.strip() if channel_layout else ""

    # Handle specific Atmos/immersive audio cases first
    if is_atmos_or_immersive_audio(additional, format, channel_layout):
        if channel_layout:
            return handle_atmos_channel_count(channels, channel_layout)

    # Handle standard channel layouts with proper LFE detection
    if channel_layout:
        return parse_channel_layout(channels, channel_layout)

    # Fallback for when no layout information is available
    return fallback_channel_count(channels)


def is_atmos_or_immersive_audio(additional, format, channel_layout):
    """Check if this is Dolby Atmos, DTS:X, or other immersive audio format."""
    atmos_indicators = [
        'JOC', 'Atmos', '16-ch', 'Atmos Audio',
        'TrueHD Atmos', 'E-AC-3 JOC', 'Dolby Atmos'
    ]

    dtsx_indicators = ['DTS:X', 'XLL X']

    # Check in additional features
    if additional:
        if any(indicator in str(additional) for indicator in atmos_indicators + dtsx_indicators):
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


def handle_atmos_channel_count(channels, channel_layout):
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


def parse_atmos_layout(channel_layout):
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


def parse_channel_layout(channels, channel_layout):
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


def fallback_channel_count(channels):
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


async def get_audio_v2(mi, meta, bdinfo):
    extra = dual = ""
    has_commentary = False
    meta['bloated'] = False
    bd_mi = None

    # Get formats
    if bdinfo is not None:  # Disks
        additional = bdinfo.get('audio', [{}])[0].get('atmos_why_you_be_like_this', '')
        if 'atmos' in additional.lower():
            common = COMMON(config)
            bd_mi = await common.get_bdmv_mediainfo(meta)
            try:
                base_dir = meta.get('base_dir')
                folder_id = meta.get('uuid') or meta.get('folder_id')
                if base_dir and folder_id:
                    mi_path = os.path.join(base_dir, 'tmp', folder_id, 'MediaInfo.json')
                    if os.path.exists(mi_path):
                        with open(mi_path, 'r', encoding='utf-8') as f:
                            mi = json.load(f)
                        if meta.get('debug'):
                            console.print(f"[yellow]Loaded MediaInfo from file:[/yellow] {mi_path}")
            except Exception:
                if meta.get('debug'):
                    console.print("[red]Failed to load MediaInfo.json from tmp directory[/red]")
                    console.print(traceback.format_exc())
                bd_mi = None
        else:
            format_settings = ""
            format = bdinfo.get('audio', [{}])[0].get('codec', '')
            commercial = format
            chan = bdinfo.get('audio', [{}])[0].get('channels', '')

    if bdinfo is None or bd_mi is not None:  # Rips or BD with mediainfo
        tracks = mi.get('media', {}).get('track', [])
        audio_tracks = [t for t in tracks if t.get('@type') == "Audio"]
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
                        first_audio_track = min(tracks_with_id, key=lambda x: int(re.search(r'\d+', str(x.get('ID', '999'))).group()))
                    except (ValueError, TypeError, AttributeError):
                        first_audio_track = tracks_with_id[0]
                else:
                    first_audio_track = audio_tracks[0]

        track = first_audio_track if first_audio_track else {}
        format = track.get('Format', '')
        commercial = track.get('Format_Commercial', '') or track.get('Format_Commercial_IfAny', '')
        if track.get('Language', '') == "zxx":
            meta['silent'] = True

        additional = track.get('Format_AdditionalFeatures', '')

        format_settings = track.get('Format_Settings', '')
        if not isinstance(format_settings, str):
            format_settings = ""
        if format_settings in ['Explicit']:
            format_settings = ""
        format_profile = track.get('Format_Profile', '')
        # Channels
        channels = track.get('Channels_Original', track.get('Channels'))
        if not str(channels).isnumeric():
            channels = track.get('Channels')
        try:
            channel_layout = track.get('ChannelLayout', '') or track.get('ChannelLayout_Original', '') or track.get('ChannelPositions', '')
        except Exception:
            channel_layout = ''

        # Enhanced channel count determination based on MediaArea AudioChannelLayout
        chan = determine_channel_count(channels, channel_layout, additional, format)

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
                    tracks = mi.get('media', {}).get('track', [])
                    has_commentary = False
                    has_compatibility = False
                    has_coms = [t for t in tracks if "commentary" in (t.get('Title') or '').lower()]
                    has_compat = [t for t in tracks if "compatibility" in (t.get('Title') or '').lower()]
                    if has_coms:
                        has_commentary = True
                    if has_compat:
                        has_compatibility = True
                    if meta['debug']:
                        console.print(f"DEBUG: Found {len(has_coms)} commentary tracks, has_commentary = {has_commentary}")
                        console.print(f"DEBUG: Found {len(has_compat)} compatibility tracks, has_compatibility = {has_compatibility}")
                    audio_tracks = [
                        t for t in tracks
                        if t.get('@type') == "Audio" and "commentary" not in (t.get('Title') or '').lower() and "compatibility" not in (t.get('Title') or '').lower()
                    ]
                    audio_language = None
                    if meta['debug']:
                        console.print(f"DEBUG: Audio Tracks (not commentary)= {len(audio_tracks)}")

                    # First pass: collect all audio languages and set flags
                    non_eng_non_orig_languages = []
                    for t in audio_tracks:
                        audio_language = t.get('Language', '')
                        if meta['debug']:
                            console.print(f"DEBUG: Audio Language = {audio_language}")

                        if isinstance(audio_language, str):
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
    audio = {
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

    if commercial:
        for key, value in commercial_names.items():
            if key in commercial:
                codec = value
                search_format = False
            if "Atmos" in commercial or format_extra.get(additional, "") == " Atmos":
                extra = " Atmos"

    if search_format:
        codec = audio.get(format, "") + audio_extra.get(additional, "")
        extra = format_extra.get(additional, "")

    format_settings = format_settings_extra.get(format_settings, "")
    if format_settings == "EX" and chan == "5.1":
        format_settings = "EX"
    else:
        format_settings = ""

    if codec == "":
        codec = format

    if format.startswith("DTS"):
        if additional and additional.endswith("X"):
            codec = "DTS:X"

    if format == "MPEG Audio":
        if format_profile == "Layer 2":
            codec = "MP2"
        elif format_profile == "Layer 3":
            codec = "MP3"

    if codec == "DD" and chan == "7.1":
        console.print("[warning] Detected codec is DD but channel count is 7.1, correcting to DD+")
        codec = "DD+"

    audio = f"{dual} {codec or ''} {format_settings or ''} {chan or ''}{extra or ''}"
    audio = ' '.join(audio.split())
    return audio, chan, has_commentary


def bloated_check(meta, audio_languages, is_eng_original_with_non_eng=False):
    # Normalize to list
    if isinstance(audio_languages, str):
        audio_languages = [audio_languages]

    bloat_is_allowed = ["ASC", "BJS", "BT", "CBR", "DC", "FF", "LCD", "SAM", "SHRI", "SP", "TL"]
    tracker_allowed_bloat_language = {
        "AITHER": "en",
        "ANT": "en",
        "BLU": "en",
        "ITT": "it",
        "LT": "es",
        "PT": "pt",
        "SPD": "ro",
        "TTR": "es",
    }

    # Track whether we've already printed messages
    printed_not_allowed = False
    printed_warning = False

    # Loop through each audio language
    for audio_language in audio_languages:
        trackers_to_warn = []

        for tracker in meta.get("trackers", []):
            if tracker in tracker_allowed_bloat_language:
                if audio_language.lower().startswith(tracker_allowed_bloat_language[tracker].lower()):
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
        except (langcodes.LanguageTagError, LookupError, AttributeError, ValueError) as e:
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
