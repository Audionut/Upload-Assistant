# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import itertools
import os
from collections.abc import Iterable
from typing import Any, Optional, cast

import aiofiles

from bin.get_bdinfo import BDInfoBinaryManager
from bin.MI.get_linux_mi import download_dvd_mediainfo
from src.console import console
from src.discparse import DiscParse

Meta = dict[str, Any]
Disc = dict[str, Any]


class DiscInfoManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self._parser = DiscParse(config)

    async def get_disc(self, meta: Meta) -> tuple[Optional[str], str, Any, list[Disc]]:
        is_disc: Optional[str] = None
        base_path = str(meta['path'])
        videoloc = base_path
        bdinfo: Any = None
        discs: list[Disc] = []

        for path, directories, _files in sorted(os.walk(base_path)):
            for each in directories:
                if each.upper() == "BDMV":  # BDMVs
                    is_disc = "BDMV"
                    discs.append({
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'BDMV',
                        'summary': "",
                        'bdinfo': ""
                    })
                elif each == "VIDEO_TS":  # DVDs
                    is_disc = "DVD"
                    discs.append({
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'DVD',
                        'vob_mi': '',
                        'ifo_mi': '',
                        'main_set': [],
                        'size': ""
                    })
                elif each == "HVDVD_TS":
                    is_disc = "HDDVD"
                    discs.append({
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'HDDVD',
                        'evo_mi': '',
                        'largest_evo': ""
                    })

        if is_disc == "BDMV":
            if meta.get('site_check', False):
                console.print('BDMV disc checking is not supported in site_check mode, yet.', markup=False)
                raise RuntimeError("BDMV disc checking is not supported in site_check mode.")
            # Ensure bdinfo binary is present for BDMV processing
            try:
                await BDInfoBinaryManager.ensure_bdinfo_binary(meta['base_dir'], meta.get('debug', False), "v1.0.6")
            except Exception as e:
                console.print(f"[red]Failed to ensure bdinfo binary: {e}[/red]", markup=False)
                raise

            if meta.get('edit', False) is False:
                discs, bdinfo = await self._parser.get_bdinfo(meta, discs, meta['uuid'], meta['base_dir'], meta.get('discs', []))
            else:
                discs, bdinfo = await self._parser.get_bdinfo(meta, meta['discs'], meta['uuid'], meta['base_dir'], meta['discs'])
        elif is_disc == "DVD" and not meta.get('emby', False):
            download_dvd_mediainfo(meta['base_dir'], debug=meta['debug'])
            discs = cast(list[Disc], await cast(Any, self._parser).get_dvdinfo(discs, base_dir=meta['base_dir'], debug=meta['debug']))
        elif is_disc == "HDDVD":
            discs = await self._parser.get_hddvd_info(discs, meta)
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt",
                "w",
                newline="",
                encoding="utf-8",
            ) as export:
                await export.write(discs[0]['evo_mi'])

        discs = sorted(discs, key=lambda d: d['name'])
        return is_disc, videoloc, bdinfo, discs

    async def get_dvd_size(self, discs: Iterable[Disc], manual_dvds: Any) -> str:
        sizes = [str(each['size']) for each in discs]
        dvd_sizes: list[str] = []

        grouped_sizes = [list(i) for _j, i in itertools.groupby(sorted(sizes))]
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

