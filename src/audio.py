import time
import traceback
from src.console import console


def get_channels(track):
    channels = track.get('Channels_Original', track.get('Channels'))
    additional_features = track.get('Format_AdditionalFeatures', '')

    if not str(channels).isnumeric():
        channels = track.get('Channels')
    try:
        channel_layout = track.get('ChannelLayout', '') or track.get('ChannelLayout_Original', '') or track.get('ChannelPositions', '')
    except Exception:
        channel_layout = ''

    if (channel_layout and "LFE" in channel_layout) or additional_features and additional_features.endswith("X"):
        chan = f"{int(channels) - 1}.1"
    elif channel_layout == "":
        if int(channels) <= 2:
            chan = f"{int(channels)}.0"
        else:
            chan = f"{int(channels) - 1}.1"
    else:
        chan = f"{channels}.0"

    return chan


def get_codec(commercial_name, additional_features, format, format_settings, format_profile, channels):
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

    extra = ""
    search_format = True

    if isinstance(additional_features, dict):
        additional_features = ""  # Set empty string if additional_features is a dictionary

    if commercial_name:
        for key, value in commercial_names.items():
            if key in commercial_name:
                codec = value
                search_format = False
            if "Atmos" in commercial_name or format_extra.get(additional_features, "") == " Atmos":
                extra = " Atmos"

    if search_format:
        codec = audio.get(format, "") + audio_extra.get(additional_features, "")
        extra = format_extra.get(additional_features, "")

    format_settings = format_settings_extra.get(format_settings, "")
    if format_settings == "EX" and channels == "5.1":
        format_settings = "EX"
    else:
        format_settings = ""

    if codec == "":
        codec = format

    if format.startswith("DTS"):
        if additional_features and additional_features.endswith("X"):
            codec = "DTS:X"

    if format == "MPEG Audio":
        if format_profile == "Layer 2":
            codec = "MP2"
        elif format_profile == "Layer 3":
            codec = "MP3"

    if codec == "DD" and channels == "7.1":
        console.print("[warning] Detected codec is DD but channel count is 7.1, correcting to DD+")
        codec = "DD+"

    return codec, extra


async def get_audio_v2(mi, meta, bdinfo):
    extra = dual = ""
    has_commentary = False
    meta['bloated'] = False

    # Get formats
    if bdinfo is not None:  # Disks
        format_settings = ""
        format = bdinfo.get('audio', [{}])[0].get('codec', '')
        commercial = format
        additional = bdinfo.get('audio', [{}])[0].get('atmos_why_you_be_like_this', '')

        # Channels
        chan = bdinfo.get('audio', [{}])[0].get('channels', '')
    else:
        tracks = mi.get('media', {}).get('track', [])
        audio_tracks = [t for t in tracks if t.get('@type') == "Audio"]
        first_audio_track = None
        if audio_tracks:
            tracks_with_order = [t for t in audio_tracks if t.get('StreamOrder')]
            if tracks_with_order:
                first_audio_track = min(tracks_with_order, key=lambda x: int(x.get('StreamOrder', '999')))
            else:
                tracks_with_id = [t for t in audio_tracks if t.get('ID')]
                if tracks_with_id:
                    first_audio_track = min(tracks_with_id, key=lambda x: int(x.get('ID', '999')))
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

        chan = get_channels(track)

    if format.startswith("DTS"):
        if meta.get('dual_audio', False):
            dual = "Dual-Audio"
        else:
            # if not meta.get('original_language', '').startswith('en'):
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
                    if t.get('@type') == "Audio" and not has_commentary and not has_compatibility
                ]
                audio_language = None
                if meta['debug']:
                    console.print(f"DEBUG: Audio Tracks (not commentary)= {len(audio_tracks)}")
                for t in audio_tracks:
                    audio_language = t.get('Language', '')
                    if meta['debug']:
                        console.print(f"DEBUG: Audio Language = {audio_language}")

                    if isinstance(audio_language, str):
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

                    if isinstance(audio_language, str):
                        audio_language = audio_language.strip().lower()
                        if audio_language and not audio_language.startswith(orig_lang) and not audio_language.startswith("en"):
                            non_en_non_commentary = True
                            console.print(f"[bold red]This release has a(n) {audio_language} audio track, and may be considered bloated")
                            time.sleep(5)

                if (
                    orig_lang == "en"
                    and eng
                    and non_en_non_commentary
                ):
                    console.print("[bold red]This release is English original, has English audio, but also has other non-English audio tracks (not commentary). This may be considered bloated.[/bold red]")
                    meta['bloated'] = True
                    time.sleep(5)

                if ((eng and (orig or non_en_non_commentary)) or (orig and non_en_non_commentary)) and len(audio_tracks) > 1 and not meta.get('no_dual', False):
                    dual = "Dual-Audio"
                    meta['dual_audio'] = True
                elif eng and not orig and orig_lang not in ['zxx', 'xx', 'en', None] and not meta.get('no_dub', False):
                    dual = "Dubbed"
            except Exception:
                console.print(traceback.format_exc())
                pass

    codec, extra = get_codec(commercial, additional, format, format_settings, format_profile, chan)

    audio = f"{dual} {codec or ''} {format_settings or ''} {chan or ''}{extra or ''}"
    audio = ' '.join(audio.split())
    return audio, chan, has_commentary
