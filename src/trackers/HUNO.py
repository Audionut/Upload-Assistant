# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import os
import re
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language
from src.rehostimages import check_hosts
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class HUNO(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='HUNO')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'HUNO'
        self.source_flag = 'HUNO'
        self.base_url = 'https://hawke.uno'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '4K4U', 'Bearfish', 'BiTOR', 'BONE', 'D3FiL3R', 'd3g', 'DTR', 'ELiTE',
            'EVO', 'eztv', 'EzzRips', 'FGT', 'HashMiner', 'HETeam', 'HEVCBay', 'HiQVE',
            'HR-DR', 'iFT', 'ION265', 'iVy', 'JATT', 'Joy', 'LAMA', 'm3th', 'MeGusta',
            'MRN', 'Musafirboy', 'OEPlus', 'Pahe.in', 'PHOCiS', 'PSA', 'RARBG', 'RMTeam',
            'ShieldBearer', 'SiQ', 'TBD', 'Telly', 'TSP', 'VXT', 'WKS', 'YAWNiX', 'YIFY', 'YTS'
        ]
        self.approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'pixhost', 'bam']
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        if await self.get_audio(meta) == "SKIPPED":
            console.print(f'{self.tracker}: No audio languages were found, the upload cannot continue.')
            return False

        if meta['video_codec'] != "HEVC" and meta['type'] in {"ENCODE", "WEBRIP", "DVDRIP", "HDTV"}:
            if not meta['unattended']:
                console.print('[bold red]Only x265/HEVC encodes are allowed at HUNO')
            return False

        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        if not meta['is_disc'] and meta['type'] in ['ENCODE', 'WEBRIP', 'DVDRIP', 'HDTV']:
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            for track in tracks:
                if track.get('@type') == "Video":
                    encoding_settings = track.get('Encoded_Library_Settings', {})

                    if encoding_settings:
                        crf_match = re.search(r'crf[ =:]+([\d.]+)', encoding_settings, re.IGNORECASE)
                        if crf_match:
                            if meta.get('debug', False):
                                console.print(f"Found CRF value: {crf_match.group(1)}")
                            crf_value = float(crf_match.group(1))
                            if crf_value > 22:
                                if not meta['unattended']:
                                    console.print(f"CRF value too high: {crf_value} for HUNO")
                                return False
                        else:
                            if meta.get('debug', False):
                                console.print("No CRF value found in encoding settings.")
                            bit_rate = track.get('BitRate')
                            if bit_rate and "Animation" not in meta.get('genre', ""):
                                try:
                                    bit_rate_num = int(bit_rate)
                                except (ValueError, TypeError):
                                    bit_rate_num = None

                                if bit_rate_num is not None:
                                    bit_rate_kbps = bit_rate_num / 1000

                                    if bit_rate_kbps < 3000:
                                        if not meta.get('unattended', False):
                                            console.print(f"Video bitrate too low: {bit_rate_kbps:.0f} kbps for HUNO")
                                        return False

        return should_continue

    async def get_stream(self, meta):
        return {'stream': await self.is_plex_friendly(meta)}

    async def check_image_hosts(self, meta):
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "imagebam.com": "bam",
        }
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=self.approved_image_hosts)

    async def get_description(self, meta):
        if 'HUNO_images_key' in meta:
            image_list = meta['HUNO_images_key']
        else:
            image_list = meta['image_list']

        return {'description': await DescriptionBuilder(self.config).unit3d_edit_desc(meta, self.tracker, image_list=image_list, approved_image_hosts=self.approved_image_hosts)}

    async def get_mediainfo(self, meta):
        if meta['bdinfo'] is not None:
            mediainfo = await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'])
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as f:
                mediainfo = await f.read()

        return {'mediainfo': mediainfo}

    async def get_featured(self, meta):
        return {}

    async def get_free(self, meta):
        if meta.get('freeleech', 0) != 0:
            free = meta.get('freeleech', 0)
            return {'free': free}
        return {}

    async def get_doubleup(self, meta):
        return {}

    async def get_sticky(self, meta):
        return {}

    async def get_season_number(self, meta):
        if meta.get('category') == 'TV' and meta.get('tv_pack') == 1:
            return {'season_pack': 1}
        return {}

    async def get_episode_number(self, meta):
        return {}

    async def get_personal_release(self, meta):
        return {}

    async def get_internal(self, meta):
        internal = 0
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != '' and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                internal = 1

        return {'internal': internal}

    async def get_additional_files(self, meta):
        return {}

    async def get_audio(self, meta):
        channels = meta.get('channels', "")
        codec = meta.get('audio', "").replace("DD+", "DDP").replace("EX", "").replace("Dual-Audio", "").replace("Dubbed", "").replace(channels, "")
        languages = ""

        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        if meta.get('audio_languages'):
            languages = meta['audio_languages']
            languages = set(languages)
            if len(languages) > 2:
                languages = "Multi"
            elif len(languages) > 1:
                languages = "Dual"
            else:
                languages = list(languages)[0]

            if "zxx" in languages:
                languages = "NONE"
            elif not languages:
                languages = "SKIPPED"
        else:
            languages = "SKIPPED"

        return f'{codec} {channels} {languages}'

    def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def get_name(self, meta):
        distributor_name = meta.get('distributor', "")
        region = meta.get('region', '')

        basename = self.get_basename(meta)
        if meta.get('hardcoded-subs'):
            hc = "Hardsubbed"
        else:
            hc = ""
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        year = meta.get('year', "")
        resolution = meta.get('resolution', "")
        audio = await self.get_audio(meta)
        service = meta.get('service', "")
        season = meta.get('season', "")
        if meta.get('tvdb_season_number', ""):
            season_int = meta.get('tvdb_season_number')
            season = f"S{str(season_int).zfill(2)}"
        episode = meta.get('episode', "")
        if meta.get('tvdb_episode_number', ""):
            episode_int = meta.get('tvdb_episode_number')
            episode = f"E{str(episode_int).zfill(2)}"
        repack = meta.get('repack', "")
        if repack.strip():
            repack = f"[{repack}]"
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "").replace("-", "- ")
        tag_lower = tag.lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                tag = re.sub(f"- {invalid_tag}", "", tag, flags=re.IGNORECASE)
            tag = "- NOGRP"
        source = meta.get('source', "").replace("Blu-ray", "BluRay")
        if source == "BluRay" and "2160" in resolution:
            source = "UHD BluRay"
        if any(x in source.lower() for x in ["pal", "ntsc"]) and type == "ENCODE":
            source = "DVD"
        hdr = meta.get('hdr', "")
        if not hdr.strip():
            hdr = "SDR"
        if distributor_name and distributor_name.upper() in ['CRITERION', 'BFI', 'SHOUT FACTORY']:
            distributor = distributor_name.title()
        else:
            if meta.get('distributor', "") and meta.get('distributor').upper() in ['CRITERION', 'BFI', 'SHOUT FACTORY']:
                distributor = meta.get('distributor').title()
            else:
                distributor = ""
        video_codec = meta.get('video_codec', "")
        video_encode = meta.get('video_encode', "").replace(".", "")
        if 'x265' in basename and not meta.get('type') == "WEBDL":
            video_encode = video_encode.replace('H', 'x')
        dvd_size = meta.get('dvd_size', "")
        edition = meta.get('edition', "")
        hybrid = 'Hybrid' if meta.get('webdv', "") else ''
        scale = "DS4K" if "DS4K" in basename.upper() else "RM4K" if "RM4K" in basename.upper() else ""
        hfr = "HFR" if meta.get('hfr', '') else ""

        # YAY NAMING FUN
        if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {region} {three_d} {source} {hybrid} {video_codec} {hdr} {hfr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {source} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source.endswith("BluRay"):  # BluRay Remux
                name = f"{title} ({year}) {edition} ({resolution} {three_d} {source} {hybrid} REMUX {video_codec} {hdr} {hfr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({year}) {edition} {hc} ({resolution} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "ENCODE":  # Encode
                name = f"{title} ({year}) {edition} {hc} ({resolution} {scale} {source} {hybrid} {video_encode} {hdr} {hfr} {audio} {tag}) {repack}"
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({year}) {edition} {hc} ({resolution} {scale} {service} WEB-DL {hybrid} {video_encode} {hdr} {hfr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({year}) {edition} {hc} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"
            elif type == "DVDRIP":
                name = f"{title} ({year}) {edition} {hc} ({resolution} {source} {video_encode} {hdr} {audio} {tag}) {repack}"
        elif meta['category'] == "TV":  # TV SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {season}{episode} {distributor} {edition} {hc} ({resolution} {region} {three_d} {source} {hybrid} {video_codec} {hdr} {hfr} {audio} {tag}) {repack}"
                if meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {season}{episode} {distributor} {edition} {hc} ({resolution} {source} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay":  # BluRay Remux
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {three_d} {source} {hybrid} REMUX {video_codec} {hdr} {hfr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "ENCODE":  # Encode
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {scale} {source} {hybrid} {video_encode} {hdr} {hfr} {audio} {tag}) {repack}"  # SOURCE
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {scale} {service} WEB-DL {hybrid} {video_encode} {hdr} {hfr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"

        name = ' '.join(name.split()).replace(": ", " - ")
        name = re.sub(r'\s{2,}', ' ', name)
        return {'name': name}

    async def get_type_id(self, meta):
        type_value = (meta.get('type') or '').lower()
        video_encode = (meta.get('video_encode') or '').lower()

        if type_value == 'remux':
            type_id = '2'
        elif type_value in ('webdl', 'webrip'):
            type_id = '15' if 'x265' in video_encode else '3'
        elif type_value in ('encode', 'hdtv'):
            type_id = '15'
        elif type_value == 'disc':
            type_id = '1'
        else:
            type_id = '0'

        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution_id = {
            'Other': '10',
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '540p': '11',
            # no mapping for 540i
            '540i': '11',
            '480p': '8',
            '480i': '9'
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    async def is_plex_friendly(self, meta):
        lossy_audio_codecs = ["AAC", "DD", "DD+", "OPUS"]

        if any(codec in meta["audio"] for codec in lossy_audio_codecs):
            return 1

        return 0
