import aiofiles
import os
import cli_ui
import re
from src.console import console


async def parsed_mediainfo(mediainfo_content):
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


async def process_desc_language(meta, desc, tracker):
    if meta['is_disc'] == "DVD":
        try:
            mediainfo_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
            if os.path.exists(mediainfo_file):
                async with aiofiles.open(mediainfo_file, 'r', encoding='utf-8') as f:
                    mediainfo_content = await f.read()

                parsed_info = await parsed_mediainfo(mediainfo_content)
                audio_languages = []
                subtitle_languages = []
                if meta.get('audio_languages') is not None:
                    audio_languages = meta['audio_languages']
                if meta.get('subtitle_languages') is not None:
                    subtitle_languages = meta['subtitle_languages']
                if not audio_languages or not subtitle_languages:
                    if not audio_languages or audio_languages is None:
                        for audio_track in parsed_info.get('audio', []):
                            if 'language' not in audio_track:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    audio_lang = cli_ui.ask_string('No audio language present, you must enter one:')
                                    if audio_lang:
                                        audio_languages.append(audio_lang)
                                        meta['audio_languages'] = audio_languages
                                    else:
                                        audio_languages = None
                                        meta['tracker_status'][tracker]['skip_upload'] = True
                                else:
                                    meta['tracker_status'][tracker]['skip_upload'] = True
                    if not subtitle_languages or subtitle_languages is None:
                        for text_track in parsed_info.get('text', []):
                            if 'language' not in text_track:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    subtitle_lang = cli_ui.ask_string('No subtitle language present, you must enter one:')
                                    if subtitle_lang:
                                        subtitle_languages.append(subtitle_lang)
                                        meta['subtitle_languages'] = subtitle_languages
                                    else:
                                        subtitle_languages = None
                                        meta['tracker_status'][tracker]['skip_upload'] = True
                                else:
                                    meta['tracker_status'][tracker]['skip_upload'] = True

                    if meta['audio_languages']:
                        await desc.write(f"[code]Audio Language: {', '.join(meta['audio_languages'])}[/code]\n")

                    if meta['subtitle_languages']:
                        await desc.write(f"[code]Subtitle Language: {', '.join(meta['subtitle_languages'])}[/code]\n")

        except Exception as e:
            if meta['debug']:
                console.print(f"[red]Error processing DVD mediainfo: {e}[/red]")

        return desc

    elif not meta['is_disc'] == "BDMV":
        def process_languages(tracks):
            audio_languages = []
            subtitle_languages = []
            if meta.get('audio_languages') is not None:
                audio_languages = meta['audio_languages']
            if meta.get('subtitle_languages') is not None:
                subtitle_languages = meta['subtitle_languages']
            if not audio_languages or not subtitle_languages:
                for track in tracks:
                    if track.get('@type') == 'Audio':
                        if not audio_languages or audio_languages is None:
                            language = track.get('Language')
                            if not language or language is None:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    audio_lang = cli_ui.ask_string('No audio language present, you must enter one:')
                                    if audio_lang:
                                        audio_languages.append(audio_lang)
                                        meta['audio_languages'] = audio_languages
                                    else:
                                        audio_languages = None
                                        meta['tracker_status'][tracker]['skip_upload'] = True
                                else:
                                    meta['tracker_status'][tracker]['skip_upload'] = True
                            else:
                                audio_languages = None
                    if track.get('@type') == 'Text':
                        if not subtitle_languages or subtitle_languages is None:
                            language = track.get('Language')
                            if not language or language is None:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                                    subtitle_lang = cli_ui.ask_string('No subtitle language present, you must enter one:')
                                    if subtitle_lang:
                                        subtitle_languages.append(subtitle_lang)
                                        meta['subtitle_languages'] = subtitle_languages
                                    else:
                                        subtitle_languages = None
                                        meta['tracker_status'][tracker]['skip_upload'] = True
                                else:
                                    meta['tracker_status'][tracker]['skip_upload'] = True
                            else:
                                subtitle_languages = None

            return audio_languages, subtitle_languages

        media_data = meta.get('mediainfo', {})
        if media_data:
            tracks = media_data.get('media', {}).get('track', [])
            if tracks:
                audio_languages, subtitle_languages = process_languages(tracks)
                if meta['audio_languages'] or meta['subtitle_languages']:
                    if meta['audio_languages']:
                        desc.write(f"[code]Audio Language: {', '.join(meta['audio_languages'])}[/code]\n")

                    if meta['subtitle_languages']:
                        desc.write(f"[code]Subtitle Language: {', '.join(meta['subtitle_languages'])}[/code]\n")
                    return desc
                else:
                    return desc
        else:
            if meta['debug']:
                console.print("[red]No media information available in meta.[/red]")
            return desc
    else:
        return desc
