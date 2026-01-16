# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, Optional, cast

from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class ITT(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='ITT')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'ITT'
        self.base_url = 'https://itatorrents.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_type_name(self, meta: Meta) -> Optional[str]:
        type_name: Optional[str] = None

        uuid_string = meta.get('uuid', '')
        if uuid_string:
            lower_uuid = uuid_string.lower()

            if 'dlmux' in lower_uuid:
                type_name = 'DLMux'
            elif 'bdmux' in lower_uuid:
                type_name = 'BDMux'
            elif 'webmux' in lower_uuid:
                type_name = 'WEBMux'
            elif 'dvdmux' in lower_uuid:
                type_name = 'DVDMux'
            elif 'bdrip' in lower_uuid:
                type_name = 'BDRip'

        if type_name is None:
            type_value = meta.get('type')
            type_name = str(type_value) if type_value else None

        return type_name

    async def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        type_id_map = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DLMux': '27',
            'BDMux': '29',
            'WEBMux': '26',
            'DVDMux': '39',
            'BDRip': '25',
            'DVDRIP': '24',
            'Cinema-MD': '14',
        }
        if mapping_only:
            return type_id_map
        if reverse:
            return {v: k for k, v in type_id_map.items()}
        if type is not None:
            return {'type_id': type_id_map.get(type, '0')}

        resolved_type = await self.get_type_name(meta)
        type_id = type_id_map.get(resolved_type or '', '0')

        return {'type_id': type_id}

    async def get_name(self, meta: Meta) -> dict[str, str]:
        type_name = await self.get_type_name(meta) or ''
        title = str(meta.get('title', ""))
        year = str(meta.get('year', ""))
        if int(meta.get('manual_year') or 0) > 0:
            year = str(meta.get('manual_year'))
        resolution = str(meta.get('resolution', ""))
        if resolution == "OTHER":
            resolution = ""
        audio = str(meta.get('audio', ""))
        season = str(meta.get('season') or "")
        episode = str(meta.get('episode') or "")
        repack = str(meta.get('repack', ""))
        three_d = str(meta.get('3D', ""))
        tag = str(meta.get('tag', ""))
        source = str(meta.get('source', ""))
        hdr = str(meta.get('hdr', ""))
        video_codec = str(meta.get('video_codec', ""))
        region = str(meta.get('region', ""))
        if meta.get('is_disc', "") == "BDMV":
            video_codec = str(meta.get('video_codec', ""))
            region = str(meta.get('region', ""))
        elif meta.get('is_disc', "") == "DVD":
            region = str(meta.get('region', ""))
        edition = str(meta.get('edition', ""))
        if 'hybrid' in edition.upper():
            edition = edition.replace('Hybrid', '').strip()

        if meta.get('category') == "TV":
            year = str(meta.get('year', '')) if meta.get('search_year', "") != "" else ""
            if meta.get('manual_date'):
                season = ''
                episode = ''
        if meta.get('no_season', False) is True:
            season = ''
        if meta.get('no_year', False) is True:
            year = ''

        dubs = await self.get_dubs(meta)

        """
        From https://itatorrents.xyz/wikis/20

        Struttura Titolo per: Full Disc, Remux
        Name Year S##E## Cut REPACK Resolution Edition Region 3D SOURCE TYPE Hi10P HDR VCodec Dub ACodec Channels Object-Tag

        Struttura Titolo per: Encode, WEB-DL, WEBRip, HDTV, DLMux, BDMux, WEBMux, DVDMux, BDRip, DVDRip
        Name Year S##E## Cut REPACK Resolution Edition 3D SOURCE TYPE Dub ACodec Channels Object Hi10P HDR VCodec-Tag
        """

        if type_name == 'DISC' or type_name == "REMUX":
            itt_name = f"{title} {year} {season}{episode} {repack} {resolution} {edition} {region} {three_d} {source} {'REMUX' if type_name == 'REMUX' else ''} {hdr} {video_codec} {dubs} {audio}"

        else:
            type_name = (
                type_name
                .replace('WEBDL', 'WEB-DL')
                .replace('WEBRIP', 'WEBRip')
                .replace('DVDRIP', 'DVDRip')
                .replace('ENCODE', 'BluRay')
            )
            itt_name = f"{title} {year} {season}{episode} {repack} {resolution} {edition} {three_d} {type_name} {dubs} {audio} {hdr} {video_codec}"

        try:
            itt_name = ' '.join(itt_name.split())
        except Exception:
            console.print("[bold red]Unable to generate name. Please re-run and correct any of the following args if needed.")
            console.print(f"--category [yellow]{meta['category']}")
            console.print(f"--type [yellow]{meta['type']}")
            console.print(f"--source [yellow]{meta['source']}")
            console.print("[bold green]If you specified type, try also specifying source")

            exit()
        name_notag = itt_name
        itt_name = name_notag + tag
        itt_name = itt_name.replace('Dubbed', '').replace('Dual-Audio', '')

        return {"name": re.sub(r"\s{2,}", " ", itt_name)}

    async def get_dubs(self, meta: Meta) -> str:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
        dubs = ''
        audio_languages_value = meta.get('audio_languages', [])
        audio_languages: set[str] = set()
        if isinstance(audio_languages_value, list):
            audio_languages_list = cast(list[Any], audio_languages_value)
            audio_languages = {str(lang) for lang in audio_languages_list}
        if audio_languages:
            dubs = " ".join(lang[:3].upper() for lang in audio_languages)
        return dubs

    async def get_additional_checks(self, meta: Meta) -> bool:
        # From rules:
        # "Non sono ammessi film e serie tv che non comprendono il doppiaggio in italiano."
        # Translates to "Films and TV series that do not include Italian dubbing are not permitted."
        italian_languages = ["italian", "italiano"]
        if not await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=italian_languages, check_audio=True
        ):
            console.print(
                "Upload Rules: https://itatorrents.xyz/wikis/5"
            )
            return False
        return True
