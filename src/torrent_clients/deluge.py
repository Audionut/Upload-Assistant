# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import base64
import os
from typing import Any

from deluge_client import DelugeRPCClient
from torf import Torrent

from src.console import console


class DelugeClientMixin:
    def deluge(self, path: str, torrent_path: str, torrent: Torrent, local_path: str, remote_path: str, client: dict[str, Any], meta: dict[str, Any]) -> None:
        deluge_client: Any = DelugeRPCClient(client['deluge_url'], int(client['deluge_port']), client['deluge_user'], client['deluge_pass'])
        # deluge_client = LocalDelugeRPCClient()
        deluge_client.connect()
        if deluge_client.connected:
            console.print("Connected to Deluge")
            # Remote path mount
            if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
                path = path.replace(local_path, remote_path)
                path = path.replace(os.sep, '/')

            path = os.path.dirname(path)

            deluge_client.call('core.add_torrent_file', torrent_path, base64.b64encode(torrent.dump()), {'download_location': path, 'seed_mode': True})
            if meta.get('debug', False):
                console.print(f"[cyan]Path: {path}")
        else:
            console.print("[bold red]Unable to connect to deluge")
