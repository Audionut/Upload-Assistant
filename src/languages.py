# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import aiofiles
import cli_ui
import langcodes
import os
import re
import sys

from src.cleanup import cleanup, reset_terminal
from src.console import console


async def parse_blu_ray(meta):
    try:
        bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
        if not os.path.exists(bd_summary_file):
            console.print(f"[yellow]BD_SUMMARY_00.txt not found at {bd_summary_file}[/yellow]")
            return {}

        async with aiofiles.open(bd_summary_file, 'r', encoding='utf-8') as f:
            content = await f.read()
    except Exception as e:
        console.print(f"[red]Error reading BD_SUMMARY file: {e}[/red]")
        return {}

    parsed_data = {
        'disc_info': {},
        'playlist_info': {},
        'video': {},
        'audio': [],
        'subtitles': []
    }

    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key in ['Disc Title', 'Disc Label', 'Disc Size', 'Protection']:
                parsed_data['disc_info'][key.lower().replace(' ', '_')] = value

            elif key in ['Playlist', 'Size', 'Length', 'Total Bitrate']:
                parsed_data['playlist_info'][key.lower().replace(' ', '_')] = value

            elif key == 'Video':
                video_parts = [part.strip() for part in value.split('/')]
                if len(video_parts) >= 6:
                    parsed_data['video'] = {
                        'format': video_parts[0],
                        'bitrate': video_parts[1],
                        'resolution': video_parts[2],
                        'framerate': video_parts[3],
                        'aspect_ratio': video_parts[4],
                        'profile': video_parts[5]
                    }
                else:
                    parsed_data['video']['format'] = value

            elif key == 'Audio' or (key.startswith('*') and 'Audio' in key):
                is_commentary = key.startswith('*')
                audio_parts = [part.strip() for part in value.split('/')]

                audio_track = {
                    'is_commentary': is_commentary
                }

                if len(audio_parts) >= 1:
                    audio_track['language'] = audio_parts[0]
                if len(audio_parts) >= 2:
                    audio_track['format'] = audio_parts[1]
                if len(audio_parts) >= 3:
                    audio_track['channels'] = audio_parts[2]
                if len(audio_parts) >= 4:
                    audio_track['sample_rate'] = audio_parts[3]
                if len(audio_parts) >= 5:
                    bitrate_str = audio_parts[4].strip()
                    bitrate_match = re.search(r'(\d+)\s*kbps', bitrate_str)
                    if bitrate_match:
                        audio_track['bitrate_num'] = int(bitrate_match.group(1))
                    audio_track['bitrate'] = bitrate_str
                if len(audio_parts) >= 6:
                    audio_track['bit_depth'] = audio_parts[5].split('(')[0].strip()

                parsed_data['audio'].append(audio_track)

            elif key == 'Subtitle' or (key.startswith('*') and 'Subtitle' in key):
                is_commentary = key.startswith('*')
                subtitle_parts = [part.strip() for part in value.split('/')]

                subtitle_track = {
                    'is_commentary': is_commentary
                }

                if len(subtitle_parts) >= 1:
                    subtitle_track['language'] = subtitle_parts[0]
                if len(subtitle_parts) >= 2:
                    subtitle_track['bitrate'] = subtitle_parts[1]

                parsed_data['subtitles'].append(subtitle_track)

    return parsed_data


async def parsed_mediainfo(meta):
    try:
        mediainfo_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
        if os.path.exists(mediainfo_file):
            async with aiofiles.open(mediainfo_file, 'r', encoding='utf-8') as f:
                mediainfo_content = await f.read()
    except Exception as e:
        console.print(f"[red]Error reading MEDIAINFO file: {e}[/red]")
        return {}

    parsed_data = {
        'general': {},
        'video': [],
        'audio': [],
        'text': []
    }

    current_section = None
    current_track = {}

    lines = mediainfo_content.strip().split('\n')

    section_header_re = re.compile(r'^(General|Video|Audio|Text|Menu)(?:\s*#\d+)?$', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        section_match = section_header_re.match(line)
        if section_match:
            if current_section and current_track:
                if current_section in ['video', 'audio', 'text']:
                    parsed_data[current_section].append(current_track)
                elif current_section == 'general':
                    parsed_data['general'] = current_track

            current_section = section_match.group(1).lower()
            current_track = {}
            continue

        if ':' in line and current_section:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()

            if current_section == 'video':
                if key in ['format', 'duration', 'bit rate', 'encoding settings', 'title']:
                    current_track[key.replace(' ', '_')] = value
            elif current_section == 'audio':
                if key in ['format', 'duration', 'bit rate', 'language', 'commercial name', 'channel', 'channel (s)', 'title']:
                    current_track[key.replace(' ', '_')] = value
            elif current_section == 'text':
                if key in ['format', 'duration', 'bit rate', 'language', 'title']:
                    current_track[key.replace(' ', '_')] = value
            elif current_section == 'general':
                current_track[key.replace(' ', '_')] = value

    if current_section and current_track:
        if current_section in ['video', 'audio', 'text']:
            parsed_data[current_section].append(current_track)
        elif current_section == 'general':
            parsed_data['general'] = current_track

    return parsed_data


async def process_desc_language(meta, desc=None, tracker=None):
    if 'language_checked' not in meta:
        meta['language_checked'] = False
    if 'tracker_status' not in meta:
        meta['tracker_status'] = {}
    if tracker not in meta['tracker_status']:
        meta['tracker_status'][tracker] = {}
    if 'unattended_audio_skip' not in meta:
        meta['unattended_audio_skip'] = False
    if 'unattended_subtitle_skip' not in meta:
        meta['unattended_subtitle_skip'] = False
    if 'no_subs' not in meta:
        meta['no_subs'] = False
    if 'write_hc_languages' not in meta:
        meta['write_hc_languages'] = False
    if 'write_audio_languages' not in meta:
        meta['write_audio_languages'] = False
    if 'write_subtitle_languages' not in meta:
        meta['write_subtitle_languages'] = False
    if 'write_hc_languages' not in meta:
        meta['write_hc_languages'] = False
    if not meta['is_disc'] == "BDMV":
        try:
            parsed_info = await parsed_mediainfo(meta)
            audio_languages = []
            subtitle_languages = []
            if 'write_audio_languages' not in meta:
                meta['write_audio_languages'] = False
            if 'write_subtitle_languages' not in meta:
                meta['write_subtitle_languages'] = False
            if meta.get('audio_languages'):
                audio_languages = meta['audio_languages']
            else:
                meta['audio_languages'] = []
            if meta.get('subtitle_languages'):
                subtitle_languages = meta['subtitle_languages']
            else:
                meta['subtitle_languages'] = []
            if not audio_languages or not subtitle_languages:
                if not meta.get('unattended_audio_skip', False) and (not audio_languages or audio_languages is None):
                    found_any_language = False
                    tracks_without_language = []

                    for track_index, audio_track in enumerate(parsed_info.get('audio', []), 1):
                        language_found = None

                        # Skip commentary tracks
                        if "title" in audio_track and "commentary" in audio_track['title'].lower():
                            if meta['debug']:
                                console.print(f"Skipping commentary track: {audio_track['title']}")
                            continue

                        if 'language' in audio_track:
                            language_found = audio_track['language']

                        if not language_found and 'title' in audio_track:
                            if meta['debug']:
                                console.print(f"Attempting to extract language from title: {audio_track['title']}")
                            title_language = extract_language_from_title(audio_track['title'])
                            if title_language:
                                language_found = title_language
                                console.print(f"Extracted language: {title_language}")

                        if language_found:
                            meta['audio_languages'].append(language_found)
                            found_any_language = True
                        else:

                            track_info = f"Track #{track_index}"
                            if 'title' in audio_track:
                                track_info += f" (Title: {audio_track['title']})"
                            tracks_without_language.append(track_info)

                    if not found_any_language:
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                            console.print("No audio language/s found for the following tracks:")
                            for track_info in tracks_without_language:
                                console.print(f"  - {track_info}")
                            console.print("You must enter (comma-separated) languages")
                            try:
                                audio_lang = cli_ui.ask_string('for all audio tracks, eg: English, Spanish:')
                            except EOFError:
                                console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                await cleanup()
                                reset_terminal()
                                sys.exit(1)
                            if audio_lang:
                                audio_languages.extend([lang.strip() for lang in audio_lang.split(',')])
                                meta['audio_languages'] = audio_languages
                                meta['write_audio_languages'] = True
                            else:
                                meta['audio_languages'] = None
                                meta['unattended_audio_skip'] = True
                                meta['tracker_status'][tracker]['skip_upload'] = True
                        else:
                            meta['unattended_audio_skip'] = True
                            meta['tracker_status'][tracker]['skip_upload'] = True
                            if meta['debug']:
                                meta['audio_languages'] = ['English, Portuguese']

                    if meta['audio_languages']:
                        meta['audio_languages'] = [lang.split()[0] for lang in meta['audio_languages']]

                if (not meta.get('unattended_subtitle_skip', False) or not meta.get('unattended_audio_skip', False)) and (not subtitle_languages or subtitle_languages is None):
                    if 'text' in parsed_info:
                        tracks_without_language = []

                        for track_index, text_track in enumerate(parsed_info.get('text', []), 1):
                            if 'language' not in text_track:
                                track_info = f"Track #{track_index}"
                                if 'title' in text_track:
                                    track_info += f" (Title: {text_track['title']})"
                                tracks_without_language.append(track_info)
                            else:
                                meta['subtitle_languages'].append(text_track['language'])

                        if tracks_without_language:
                            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                console.print("No subtitle language/s found for the following tracks:")
                                for track_info in tracks_without_language:
                                    console.print(f"  - {track_info}")
                                console.print("You must enter (comma-separated) languages")
                                try:
                                    subtitle_lang = cli_ui.ask_string('for all subtitle tracks, eg: English, Spanish:')
                                except EOFError:
                                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                    await cleanup()
                                    reset_terminal()
                                    sys.exit(1)
                                if subtitle_lang:
                                    subtitle_languages.extend([lang.strip() for lang in subtitle_lang.split(',')])
                                    meta['subtitle_languages'] = subtitle_languages
                                    meta['write_subtitle_languages'] = True
                                else:
                                    meta['subtitle_languages'] = None
                                    meta['unattended_subtitle_skip'] = True
                                    meta['tracker_status'][tracker]['skip_upload'] = True
                            else:
                                meta['unattended_subtitle_skip'] = True
                                meta['tracker_status'][tracker]['skip_upload'] = True
                                if meta['debug']:
                                    meta['subtitle_languages'] = ['English, Portuguese']

                        if meta['subtitle_languages']:
                            meta['subtitle_languages'] = [lang.split()[0] for lang in meta['subtitle_languages']]

                    if meta.get('hardcoded-subs', False):
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                            try:
                                hc_lang = cli_ui.ask_string("What language/s are the hardcoded subtitles?")
                            except EOFError:
                                console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                await cleanup()
                                reset_terminal()
                                sys.exit(1)
                            if hc_lang:
                                meta['subtitle_languages'] = [hc_lang]
                                meta['write_hc_languages'] = True
                            else:
                                meta['subtitle_languages'] = None
                                meta['unattended_subtitle_skip'] = True
                                meta['tracker_status'][tracker]['skip_upload'] = True
                        else:
                            meta['subtitle_languages'] = "English"
                            meta['write_hc_languages'] = True
                    if 'text' not in parsed_info and not meta.get('hardcoded-subs', False):
                        meta['no_subs'] = True

        except Exception as e:
            console.print(f"[red]Error processing mediainfo languages: {e}[/red]")

        meta['language_checked'] = True
        return desc if desc is not None else None

    elif meta['is_disc'] == "BDMV":
        if "language_checked" not in meta:
            meta['language_checked'] = False
        if 'bluray_audio_skip' not in meta:
            meta['bluray_audio_skip'] = False
        audio_languages = []
        if meta.get('audio_languages'):
            audio_languages = meta['audio_languages']
        else:
            meta['audio_languages'] = []
        if meta.get('subtitle_languages'):
            subtitle_languages = meta['subtitle_languages']
        else:
            meta['subtitle_languages'] = []
        try:
            bluray = await parse_blu_ray(meta)
            audio_tracks = bluray.get("audio", [])
            commentary_tracks = [track for track in audio_tracks if track.get("is_commentary")]
            if commentary_tracks:
                for track in commentary_tracks:
                    if meta['debug']:
                        console.print(f"Skipping commentary track: {track}")
                    audio_tracks.remove(track)
            audio_languages = {track.get("language", "") for track in audio_tracks if "language" in track}
            for track in audio_tracks:
                bitrate_str = track.get("bitrate", "")
                bitrate_num = None
                if bitrate_str:
                    match = re.search(r'([\d.]+)\s*([kM]?b(?:ps|/s))', bitrate_str.replace(',', ''), re.IGNORECASE)
                    if match:
                        value = float(match.group(1))
                        unit = match.group(2).lower()
                        if unit in ['mbps', 'mb/s']:
                            bitrate_num = int(value * 1000)
                        elif unit in ['kbps', 'kb/s']:
                            bitrate_num = int(value)
                        else:
                            bitrate_num = int(value)

                lang = track.get("language", "")
                if bitrate_num is not None and bitrate_num < 258:
                    if lang and lang in audio_languages and len(lang) > 1 and not meta['bluray_audio_skip']:
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                            console.print(f"Audio track '{lang}' has a bitrate of {bitrate_num} kbps. Probably commentary and should be removed.")
                            try:
                                if cli_ui.ask_yes_no(f"Remove '{lang}' from audio languages?", default=True):
                                    audio_languages.discard(lang) if isinstance(audio_languages, set) else audio_languages.remove(lang)
                            except EOFError:
                                console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                await cleanup()
                                reset_terminal()
                                sys.exit(1)
                        else:
                            audio_languages.discard(lang) if isinstance(audio_languages, set) else audio_languages.remove(lang)
                        meta['bluray_audio_skip'] = True

            subtitle_tracks = bluray.get("subtitles", [])
            sub_commentary_tracks = [track for track in subtitle_tracks if track.get("is_commentary")]
            if sub_commentary_tracks:
                for track in sub_commentary_tracks:
                    if meta['debug']:
                        console.print(f"Skipping commentary subtitle track: {track}")
                    subtitle_tracks.remove(track)
            if subtitle_tracks and isinstance(subtitle_tracks[0], dict):
                subtitle_languages = {track.get("language", "") for track in subtitle_tracks if "language" in track}
            else:
                subtitle_languages = set(subtitle_tracks)
            if subtitle_languages:
                meta['subtitle_languages'] = list(subtitle_languages)

            meta['audio_languages'] = list(audio_languages)
        except Exception as e:
            console.print(f"[red]Error processing BDInfo languages: {e}[/red]")

        meta['language_checked'] = True
        return desc if desc is not None else None

    else:
        meta['language_checked'] = True
        return desc if desc is not None else None


async def has_english_language(languages):
    """Check if any language in the list contains 'english'"""
    if isinstance(languages, str):
        languages = [languages]
    if not languages:
        return False
    return any('english' in lang.lower() for lang in languages)


def extract_language_from_title(title):
    """Extract language from title field using langcodes library"""
    if not title:
        return None

    title_lower = title.lower()
    words = re.findall(r'\b[a-zA-Z]+\b', title_lower)

    for word in words:
        try:
            lang = langcodes.find(word)
            if lang and lang.is_valid():
                return lang.display_name()
        except (langcodes.LanguageTagError, LookupError):
            continue

    return None
