# -*- coding: utf-8 -*-
import re
from src.console import console
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class ITT(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='ITT')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ITT'
        self.source_flag = 'ItaTorrents'
        self.base_url = 'https://itatorrents.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_type_id(self, meta):
        type_id = {
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
            'DVDRip': '24',
            'Cinema-MD': '14',
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_name(self, meta):
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        year = meta.get('year', "")
        if int(meta.get('manual_year')) > 0:
            year = meta.get('manual_year')
        resolution = meta.get('resolution', "")
        if resolution == "OTHER":
            resolution = ""
        audio = meta.get('audio', "")
        season = meta.get('season') or ""
        episode = meta.get('episode') or ""
        repack = meta.get('repack', "")
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "")
        source = meta.get('source', "")
        hdr = meta.get('hdr', "")
        if meta.get('is_disc', "") == "BDMV":
            video_codec = meta.get('video_codec', "")
            region = meta.get('region', "") if meta.get('region', "") is not None else ""
        elif meta.get('is_disc', "") == "DVD":
            region = meta.get('region', "") if meta.get('region', "") is not None else ""
        else:
            video_codec = meta.get('video_codec', "")
        edition = meta.get('edition', "")
        if 'hybrid' in edition.upper():
            edition = edition.replace('Hybrid', '').strip()

        if meta['category'] == "TV":
            if meta['search_year'] != "":
                year = meta['year']
            else:
                year = ""
            if meta.get('manual_date'):
                season = ''
                episode = ''
        if meta.get('no_season', False) is True:
            season = ''
        if meta.get('no_year', False) is True:
            year = ''

        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        dubs = ''
        audio_languages = set(meta.get('audio_languages', []))
        if audio_languages:
            dubs = " ".join([lang[:3].upper() for lang in audio_languages])

        """
        From https://itatorrents.xyz/wikis/20

        Struttura Titolo per: Full Disc, Remux
        Name Year S##E## Cut REPACK Resolution Edition Region 3D SOURCE TYPE Hi10P HDR VCodec Dub ACodec Channels Object-Tag

        Struttura Titolo per: Encode, WEB-DL, WEBRip, HDTV, DLMux, BDMux, WEBMux, DVDMux, BDRip, DVDRip
        Name Year S##E## Cut REPACK Resolution Edition 3D SOURCE TYPE Dub ACodec Channels Object Hi10P HDR VCodec-Tag
        """

        if type == 'DISC' or type == "REMUX":
            # Name Year S##E## Cut REPACK Resolution Edition Region 3D SOURCE TYPE Hi10P HDR VCodec Dub ACodec Channels Object-Tag
            itt_name = f"{title} {year} {season}{episode} {repack} {resolution} {edition} {region} {three_d} {source} {'REMUX' if type == 'REMUX' else ''} {hdr} {video_codec} {dubs} {audio}"

        else:
            # Name Year S##E## Cut REPACK Resolution Edition 3D SOURCE TYPE Dub ACodec Channels Object Hi10P HDR VCodec-Tag
            itt_name = f"{title} {year} {season}{episode} {repack} {resolution} {edition} {three_d} {source} {type} {dubs} {audio} {hdr} {video_codec}"

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

        return {"name": re.sub(r"\s{2,}", " ", itt_name)}

    async def get_additional_checks(self, meta):
        should_continue = True
        if not meta.get("language_checked", False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        italian_languages = ["Italian", "Italiano"]
        if not any(
            lang in meta.get("audio_languages", []) for lang in italian_languages
        ):
            console.print(
                "[bold red]ITA: Non sono ammessi film e serie tv che non comprendono il doppiaggio in italiano.[/bold red]\n"
                "[bold red]ENG: Films and TV series that do not include Italian dubbing are not permitted.[/bold red]\n"
                "Upload Rules: https://itatorrents.xyz/wikis/5"
            )
            return False

        return should_continue
