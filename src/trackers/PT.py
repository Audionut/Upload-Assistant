# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from typing import Any, Optional, cast

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class PT(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='PT')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'PT'
        self.base_url = 'https://portugas.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []

    def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (type, reverse, mapping_only)
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '39',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(str(meta.get('type', '')), '0')
        return {'type_id': type_id}

    def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        _ = (resolution, reverse, mapping_only)
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1440p': '13',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '540p': '11',
            '480p': '8',
            '480i': '9'
        }.get(str(meta.get('resolution', '')), '10')
        return {'resolution_id': resolution_id}

    def get_name(self, meta: Meta) -> dict[str, str]:
        name = str(meta.get('name', '')).replace(' ', '.')

        pt_name = name
        tag_value = str(meta.get('tag', ''))
        tag_lower = tag_value.lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if tag_value == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                pt_name = re.sub(f"-{invalid_tag}", "", pt_name, flags=re.IGNORECASE)
            pt_name = f"{pt_name}-NOGROUP"

        return {'name': pt_name}

    def get_audio(self, meta: Meta) -> int:
        found_portuguese_audio = False

        if meta.get('is_disc') == "BDMV":
            bdinfo = cast(dict[str, Any], meta.get('bdinfo', {}))
            audio_tracks = cast(list[dict[str, Any]], bdinfo.get("audio", []))
            if audio_tracks:
                for track in audio_tracks:
                    lang = str(track.get("language", ""))
                    if lang and lang.lower() == "portuguese":
                        found_portuguese_audio = True
                        break

        needs_mediainfo_check = (meta.get('is_disc') != "BDMV") or (meta.get('is_disc') == "BDMV" and not found_portuguese_audio)

        if needs_mediainfo_check:
            base_dir = str(meta.get('base_dir', '.'))
            uuid = str(meta.get('uuid', 'default_uuid'))
            media_info_path = os.path.join(base_dir, 'tmp', uuid, 'MEDIAINFO.txt')

            try:
                if os.path.exists(media_info_path):
                    with open(media_info_path, encoding='utf-8') as f:
                        media_info_text = f.read()

                    if not found_portuguese_audio:
                        audio_sections = re.findall(r'Audio(?: #\d+)?\s*\n((?:(?!\n\n(?:Audio|Video|Text|Menu)).)*)', media_info_text, re.DOTALL | re.IGNORECASE)
                        for section in audio_sections:
                            language_match = re.search(r'Language\s*:\s*(.+)', section, re.IGNORECASE)
                            title_match = re.search(r'Title\s*:\s*(.+)', section, re.IGNORECASE)

                            lang_raw = language_match.group(1).strip() if language_match else ""
                            title_raw = title_match.group(1).strip() if title_match else ""

                            text = f'{lang_raw} {title_raw}'.lower()

                            if "portuguese" in text and not any(keyword in text for keyword in ["(br)", "brazilian"]):
                                found_portuguese_audio = True
                                break

            except FileNotFoundError:
                pass
            except Exception as e:
                console.print(f"ERRO: Falha ao processar MediaInfo para verificar áudio Português: {e}", markup=False)

        return 1 if found_portuguese_audio else 0

    def get_subtitles(self, meta: Meta) -> int:
        found_portuguese_subtitle = False

        if meta.get('is_disc') == "BDMV":
            bdinfo = cast(dict[str, Any], meta.get('bdinfo', {}))
            subtitle_tracks = cast(list[Any], bdinfo.get("subtitles", []))
            if subtitle_tracks:
                found_portuguese_subtitle = False
                for track in subtitle_tracks:
                    if isinstance(track, str) and track.lower() == "portuguese":
                        found_portuguese_subtitle = True
                        break

        needs_mediainfo_check = (meta.get('is_disc') != "BDMV") or (meta.get('is_disc') == "BDMV" and not found_portuguese_subtitle)

        if needs_mediainfo_check:
            base_dir = str(meta.get('base_dir', '.'))
            uuid = str(meta.get('uuid', 'default_uuid'))
            media_info_path = os.path.join(base_dir, 'tmp', uuid, 'MEDIAINFO.txt')

            try:
                if os.path.exists(media_info_path):
                    with open(media_info_path, encoding='utf-8') as f:
                        media_info_text = f.read()

                    if not found_portuguese_subtitle:
                        text_sections = re.findall(r'Text(?: #\d+)?\s*\n((?:(?!\n\n(?:Audio|Video|Text|Menu)).)*)', media_info_text, re.DOTALL | re.IGNORECASE)
                        if not text_sections:
                            text_sections = re.findall(r'Subtitle(?: #\d+)?\s*\n((?:(?!\n\n(?:Audio|Video|Text|Menu)).)*)', media_info_text, re.DOTALL | re.IGNORECASE)

                        for section in text_sections:
                            language_match = re.search(r'Language\s*:\s*(.+)', section, re.IGNORECASE)
                            title_match = re.search(r'Title\s*:\s*(.+)', section, re.IGNORECASE)

                            lang_raw = language_match.group(1).strip() if language_match else ""
                            title_raw = title_match.group(1).strip() if title_match else ""

                            text = f'{lang_raw} {title_raw}'.lower()

                            if "portuguese" in text and not any(keyword in text for keyword in ["(br)", "brazilian"]):
                                found_portuguese_subtitle = True
                                break

            except FileNotFoundError:
                pass
            except Exception as e:
                console.print(f"ERRO: Falha ao processar MediaInfo para verificar legenda Português: {e}", markup=False)

        return 1 if found_portuguese_subtitle else 0

    def get_distributor_ids(self, _meta: Meta) -> dict[str, str]:
        return {}

    def get_region_id(self, meta: Meta) -> dict[str, str]:
        _ = meta
        return {}

    def get_additional_data(self, meta: Meta) -> dict[str, str]:
        audio_flag = self.get_audio(meta)
        subtitle_flag = self.get_subtitles(meta)

        data: dict[str, str] = {
            'audio_pt': str(audio_flag),
            'legenda_pt': str(subtitle_flag),
        }

        return data
