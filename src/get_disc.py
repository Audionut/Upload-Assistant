# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import itertools
from bin.MI.get_linux_mi import download_dvd_mediainfo
from src.discparse import DiscParse


async def get_disc(meta):
    is_disc = None
    videoloc = meta['path']
    bdinfo = None
    bd_summary = None  # noqa: F841
    discs = []
    parse = DiscParse()
    for path, directories, files in sorted(os.walk(meta['path'])):
        for each in directories:
            if each.upper() == "BDMV":  # BDMVs
                is_disc = "BDMV"
                disc = {
                    'path': f"{path}/{each}",
                    'name': os.path.basename(path),
                    'type': 'BDMV',
                    'summary': "",
                    'bdinfo': ""
                }
                discs.append(disc)
            elif each == "VIDEO_TS":  # DVDs
                is_disc = "DVD"
                disc = {
                    'path': f"{path}/{each}",
                    'name': os.path.basename(path),
                    'type': 'DVD',
                    'vob_mi': '',
                    'ifo_mi': '',
                    'main_set': [],
                    'size': ""
                }
                discs.append(disc)
            elif each == "HVDVD_TS":
                is_disc = "HDDVD"
                disc = {
                    'path': f"{path}/{each}",
                    'name': os.path.basename(path),
                    'type': 'HDDVD',
                    'evo_mi': '',
                    'largest_evo': ""
                }
                discs.append(disc)
    if is_disc == "BDMV":
        if meta.get('site_check', False):
            print('BDMV disc checking is not supported in site_check mode, yet.')
            return Exception
        if meta.get('edit', False) is False:
            discs, bdinfo = await parse.get_bdinfo(meta, discs, meta['uuid'], meta['base_dir'], meta.get('discs', []))
        else:
            discs, bdinfo = await parse.get_bdinfo(meta, meta['discs'], meta['uuid'], meta['base_dir'], meta['discs'])
    elif is_disc == "DVD" and not meta.get('emby', False):
        download_dvd_mediainfo(meta['base_dir'], debug=meta['debug'])
        discs = await parse.get_dvdinfo(discs, base_dir=meta['base_dir'], debug=meta['debug'])
    elif is_disc == "HDDVD":
        discs = await parse.get_hddvd_info(discs, meta)
        export = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8')
        export.write(discs[0]['evo_mi'])
        export.close()
    discs = sorted(discs, key=lambda d: d['name'])
    return is_disc, videoloc, bdinfo, discs


async def get_dvd_size(discs, manual_dvds):
    sizes = []
    dvd_sizes = []
    for each in discs:
        sizes.append(each['size'])
    grouped_sizes = [list(i) for j, i in itertools.groupby(sorted(sizes))]
    for each in grouped_sizes:
        if len(each) > 1:
            dvd_sizes.append(f"{len(each)}x{each[0]}")
        else:
            dvd_sizes.append(each[0])
    dvd_sizes.sort()
    compact = " ".join(dvd_sizes)

    if manual_dvds:
        compact = str(manual_dvds)

    return compact
