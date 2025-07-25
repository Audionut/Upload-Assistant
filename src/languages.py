import aiofiles
import os
import cli_ui
import re
from src.console import console


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
                    for audio_track in parsed_info.get('audio', []):
                        if 'language' not in audio_track:
                            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                console.print("No audio language/s found, you must enter (comma-separated) languages")
                                audio_lang = cli_ui.ask_string('for all audio tracks, eg: English, Spanish:')
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
                        else:
                            if "title" in audio_track and "commentary" not in audio_track['title']:
                                meta['audio_languages'].append(audio_track['language'])
                            elif "title" not in audio_track:
                                meta['audio_languages'].append(audio_track['language'])
                        if meta['audio_languages']:
                            meta['audio_languages'] = [lang.split()[0] for lang in meta['audio_languages']]

                if (not meta.get('unattended_subtitle_skip', False) or not meta.get('unattended_audio_skip', False)) and (not subtitle_languages or subtitle_languages is None):
                    if 'text' in parsed_info:
                        for text_track in parsed_info.get('text', []):
                            if 'language' not in text_track:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    console.print("No subtitle language/s found, you must enter (comma-separated) languages")
                                    subtitle_lang = cli_ui.ask_string('for all subtitle tracks, eg: English, Spanish:')
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
                            else:
                                meta['subtitle_languages'].append(text_track['language'])
                            if meta['subtitle_languages']:
                                meta['subtitle_languages'] = [lang.split()[0] for lang in meta['subtitle_languages']]
                    if meta.get('hardcoded-subs', False):
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                            hc_lang = cli_ui.ask_string("What language/s are the hardcoded subtitles?")
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
                    else:
                        meta['no_subs'] = True

            if meta['audio_languages'] and meta['write_audio_languages'] and desc is not None:
                await desc.write(f"[code]Audio Language/s: {', '.join(meta['audio_languages'])}[/code]\n")

            if meta['subtitle_languages'] and meta['write_subtitle_languages'] and desc is not None:
                await desc.write(f"[code]Subtitle Language/s: {', '.join(meta['subtitle_languages'])}[/code]\n")
            if meta['subtitle_languages'] and meta['write_hc_languages'] and desc is not None:
                await desc.write(f"[code]Hardcoded Subtitle Language/s: {', '.join(meta['subtitle_languages'])}[/code]\n")

        except Exception as e:
            console.print(f"[red]Error processing mediainfo languages: {e}[/red]")

        return desc if desc is not None else None

    elif meta['is_disc'] == "BDMV":
        if 'bluray_audio_skip' not in meta:
            meta['bluray_audio_skip'] = False
        audio_languages = []
        if meta.get('audio_languages'):
            audio_languages = meta['audio_languages']
        else:
            meta['audio_languages'] = []
        try:
            bdinfo = meta.get('bdinfo', {})
            audio_tracks = bdinfo.get("audio", [])
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
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                            console.print(f"Audio track '{lang}' has a bitrate of {bitrate_num} kbps. Probably commentary and should be removed.")
                            if cli_ui.ask_yes_no(f"Remove '{lang}' from audio languages?", default=True):
                                audio_languages.discard(lang) if isinstance(audio_languages, set) else audio_languages.remove(lang)
                        else:
                            audio_languages.discard(lang) if isinstance(audio_languages, set) else audio_languages.remove(lang)
                        meta['bluray_audio_skip'] = True

            subtitle_tracks = bdinfo.get("subtitles", [])
            if subtitle_tracks and isinstance(subtitle_tracks[0], dict):
                subtitle_languages = {track.get("language", "") for track in subtitle_tracks if "language" in track}
            else:
                subtitle_languages = set(subtitle_tracks)
            if subtitle_languages:
                meta['subtitle_languages'] = list(subtitle_languages)

            meta['audio_languages'] = list(audio_languages)
        except Exception as e:
            console.print(f"[red]Error processing BDInfo languages: {e}[/red]")

        return desc if desc is not None else None

    else:
        return desc if desc is not None else None


async def has_english_language(languages):
    """Check if any language in the list contains 'english'"""
    if isinstance(languages, str):
        languages = [languages]
    if not languages:
        return False
    return any('english' in lang.lower() for lang in languages)
