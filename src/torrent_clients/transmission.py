# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
from typing import Any

import transmission_rpc
from torf import Torrent

from src.console import console


class TransmissionClientMixin:
    def transmission(self, path: str, torrent: Torrent, local_path: str, remote_path: str, client: dict[str, Any], meta: dict[str, Any]) -> None:
        try:
            tr_client = transmission_rpc.Client(
                protocol=client['transmission_protocol'],
                host=client['transmission_host'],
                port=int(client['transmission_port']),
                username=client['transmission_username'],
                password=client['transmission_password'],
                path=client.get('transmission_path', "/transmission/rpc")
            )
        except Exception as e:
            console.print(f"[bold red]Unable to connect to transmission: {e}")
            return

        console.print("Connected to Transmission")
        # Remote path mount
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')

        path = os.path.dirname(path)

        if meta.get('transmission_label') is not None:
            label = [meta['transmission_label']]
        elif client.get('transmission_label') is not None:
            label = [client['transmission_label']]
        else:
            label = None

        tr_client.add_torrent(
            torrent=torrent.dump(),
            download_dir=path,
            labels=label
        )

        if meta.get('debug', False):
            console.print(f"[cyan]Path: {path}")
