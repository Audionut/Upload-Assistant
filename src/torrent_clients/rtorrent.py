# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import contextlib
import errno
import os
import platform
import shutil
import ssl
import time
import traceback
import xmlrpc.client  # nosec B411 - Secured with defusedxml.xmlrpc.monkey_patch() below
from typing import Any, Callable, Optional, cast

import bencode
import defusedxml.xmlrpc
from torf import Torrent

from cogs.redaction import Redaction
from src.console import console
from src.torrentcreate import TorrentCreator

# Secure XML-RPC client using defusedxml to prevent XML attacks
defusedxml.xmlrpc.monkey_patch()


bencode_any = cast(Any, bencode)
_bencode_bread = cast(Callable[[str], dict[str, Any]], bencode_any.bread)
_bencode_bencode = cast(Callable[[Any], bytes], bencode_any.bencode)
_bencode_bwrite = cast(Callable[[Any, str], None], bencode_any.bwrite)


class RtorrentClientMixin:
    config: dict[str, Any]

    async def is_valid_torrent(self, meta: dict[str, Any], torrent_path: str, torrenthash: str, torrent_client: str, client: dict[str, Any]) -> tuple[bool, str]:
        raise NotImplementedError

    @staticmethod
    def _extract_tracker_ids_from_comment(comment: str) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _coerce_str_list(value: Any) -> list[str]:
        if isinstance(value, list):
            value_list = cast(list[Any], value)
            return [str(v) for v in value_list if str(v)]
        return [str(value)] if value is not None else []

    def rtorrent(self, path: str, torrent_path: str, torrent: Torrent, meta: dict[str, Any], local_path: str, remote_path: str, client: dict[str, Any], tracker: str) -> None:
        # Get the appropriate source path (same as in qbittorrent method)
        tracker_dir: Optional[str] = None
        dst = path
        filelist = self._coerce_str_list(meta.get('filelist', []))
        src = (
            filelist[0]
            if len(filelist) == 1 and os.path.isfile(filelist[0]) and not meta.get('keep_folder')
            else meta.get('path')
        )

        if not src:
            error_msg = "[red]No source path found in meta."
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        # Determine linking method
        linking_method = client.get('linking')  # "symlink", "hardlink", or None
        if meta.get('debug', False):
            console.print("Linking method:", linking_method)
        use_symlink = linking_method == "symlink"
        use_hardlink = linking_method == "hardlink"

        # Process linking if enabled
        if use_symlink or use_hardlink:
            # Get linked folder for this drive
            linked_folder = self._coerce_str_list(client.get('linked_folder', []))
            if meta.get('debug', False):
                console.print(f"Linked folders: {linked_folder}")

            # Determine drive letter (Windows) or root (Linux)
            if platform.system() == "Windows":
                src_drive = os.path.splitdrive(src)[0]
            else:
                # On Unix/Linux, use the root directory or first directory component
                src_drive = "/"
                # Extract the first directory component for more specific matching
                src_parts = src.strip('/').split('/')
                if src_parts:
                    src_root_dir = '/' + src_parts[0]
                    # Check if any linked folder contains this root
                    for folder in linked_folder:
                        if src_root_dir in folder or folder in src_root_dir:
                            src_drive = src_root_dir
                            break

            # Find a linked folder that matches the drive
            link_target = None
            if platform.system() == "Windows":
                # Windows matching based on drive letters
                for folder in linked_folder:
                    folder_drive = os.path.splitdrive(folder)[0]
                    if folder_drive == src_drive:
                        link_target = folder
                        break
            else:
                # Unix/Linux matching based on path containment
                for folder in linked_folder:
                    # Check if source path is in the linked folder or vice versa
                    if src.startswith(folder) or folder.startswith(src) or folder.startswith(src_drive):
                        link_target = folder
                        break

            if meta.get('debug', False):
                console.print(f"Source drive: {src_drive}")
                console.print(f"Link target: {link_target}")

            # If using symlinks and no matching drive folder, allow any available one
            if use_symlink and not link_target and linked_folder:
                link_target = linked_folder[0]

            if (use_symlink or use_hardlink) and not link_target:
                error_msg = f"No suitable linked folder found for drive {src_drive}"
                console.print(f"[bold red]{error_msg}")
                raise ValueError(error_msg)

            # Create tracker-specific directory inside linked folder
            if use_symlink or use_hardlink:
                # allow overridden folder name with link_dir_name config var
                tracker_cfg = cast(dict[str, Any], self.config.get("TRACKERS", {})).get(tracker.upper(), {})
                link_dir_name = str(tracker_cfg.get("link_dir_name", "")).strip()
                if link_target is None:
                    raise RuntimeError("link_target cannot be None")
                tracker_dir = os.path.join(link_target, link_dir_name or tracker)
                os.makedirs(tracker_dir, exist_ok=True)

                if meta.get('debug', False):
                    console.print(f"[bold yellow]Linking to tracker directory: {tracker_dir}")
                    console.print(f"[cyan]Source path: {src}")

                # Extract only the folder or file name from `src`
                src_name = os.path.basename(src.rstrip(os.sep))  # Ensure we get just the name
                dst = os.path.join(tracker_dir, src_name)  # Destination inside linked folder

                # path magic
                if os.path.exists(dst) or os.path.islink(dst):
                    if meta.get('debug', False):
                        console.print(f"[yellow]Skipping linking, path already exists: {dst}")
                else:
                    if use_hardlink:
                        try:
                            # Check if we're linking a file or directory
                            if os.path.isfile(src):
                                # For a single file, create a hardlink directly
                                try:
                                    os.link(src, dst)
                                    if meta.get('debug', False):
                                        console.print(f"[green]Hard link created: {dst} -> {src}")
                                except OSError as e:
                                    # If hardlink fails, try to copy the file instead
                                    console.print(f"[yellow]Hard link failed: {e}")
                                    console.print(f"[yellow]Falling back to file copy for: {src}")
                                    shutil.copy2(src, dst)  # copy2 preserves metadata
                                    console.print(f"[green]File copied instead: {dst}")
                            else:
                                # For directories, we need to link each file inside
                                os.makedirs(dst, exist_ok=True)

                                for root, _, files in os.walk(src):
                                    # Get the relative path from source
                                    rel_path = os.path.relpath(root, src)

                                    dst_dir = dst

                                    # Create corresponding directory in destination
                                    if rel_path != '.':
                                        dst_dir = os.path.join(dst, rel_path)
                                        os.makedirs(dst_dir, exist_ok=True)

                                    # Create hardlinks for each file
                                    for idx, file in enumerate(files):
                                        src_file = os.path.join(root, file)
                                        dst_file = os.path.join(dst if rel_path == '.' else dst_dir, file)
                                        try:
                                            os.link(src_file, dst_file)
                                            if meta.get('debug', False) and idx == 0:
                                                console.print(f"[green]Hard link created for file: {dst_file} -> {src_file}")
                                        except OSError as e:
                                            # If hardlink fails, copy file instead
                                            console.print(f"[yellow]Hard link failed for file {file}: {e}")
                                            shutil.copy2(src_file, dst_file)  # copy2 preserves metadata
                                            console.print(f"[yellow]File copied instead: {dst_file}")

                                if meta.get('debug', False):
                                    console.print(f"[green]Directory structure and files processed: {dst}")
                        except OSError as e:
                            error_msg = f"Failed to create link: {e}"
                            console.print(f"[bold red]{error_msg}")
                            if meta.get('debug', False):
                                console.print(f"[yellow]Source: {src} (exists: {os.path.exists(src)})")
                                console.print(f"[yellow]Destination: {dst}")
                            # Don't raise exception - just warn and continue
                            console.print("[yellow]Continuing with rTorrent addition despite linking failure")

                    elif use_symlink:
                        try:
                            if platform.system() == "Windows":
                                os.symlink(src, dst, target_is_directory=os.path.isdir(src))
                            else:
                                os.symlink(src, dst)

                            if meta.get('debug', False):
                                console.print(f"[green]Symbolic link created: {dst} -> {src}")

                        except OSError as e:
                            error_msg = f"Failed to create symlink: {e}"
                            console.print(f"[bold red]{error_msg}")
                            # Don't raise exception - just warn and continue
                            console.print("[yellow]Continuing with rTorrent addition despite linking failure")

                # Use the linked path for rTorrent if linking was successful
                if (use_symlink or use_hardlink) and os.path.exists(dst):
                    path = dst

        # Apply remote pathing to `tracker_dir` before assigning `save_path`
        if use_symlink or use_hardlink:
            if tracker_dir is None:
                raise ValueError("Linking enabled but tracker_dir was not set")
            save_path = tracker_dir  # Default to linked directory
        else:
            save_path = path  # Default to the original path

        # Handle remote path mapping
        if local_path and remote_path and local_path.lower() != remote_path.lower():
            # Normalize paths for comparison
            norm_save_path = os.path.normpath(save_path).lower()
            norm_local_path = os.path.normpath(local_path).lower()

            # Check if the save_path starts with local_path
            if norm_save_path.startswith(norm_local_path):
                # Get the relative part of the path
                rel_path = os.path.relpath(save_path, local_path)
                # Combine remote path with relative path
                save_path = os.path.join(remote_path, rel_path)

            # For direct replacement if the above approach doesn't work
            elif local_path.lower() in save_path.lower():
                save_path = save_path.replace(local_path, remote_path, 1)  # Replace only at the beginning

        if meta.get('debug', False):
            console.print(f"[cyan]Original path: {path}")
            console.print(f"[cyan]Mapped save path: {save_path}")

        ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        with contextlib.suppress(AttributeError):
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        rtorrent = xmlrpc.client.Server(client['rtorrent_url'], context=ssl_context)
        metainfo = _bencode_bread(torrent_path)
        if meta.get('debug', False):
            console.print(f"rtorrent: {Redaction.redact_private_info(str(rtorrent))}", markup=False)
            console.print(f"metainfo: {Redaction.redact_private_info(str(metainfo))}", markup=False)
        try:
            # Use dst path if linking was successful, otherwise use original path
            resume_path = dst if (use_symlink or use_hardlink) and os.path.exists(dst) else path
            if meta.get('debug', False):
                console.print(f"[cyan]Using resume path: {resume_path}")
            fast_resume = self.add_fast_resume(metainfo, resume_path, torrent)
        except OSError as exc:
            console.print(f"[red]Error making fast-resume data ({exc})")
            raise

        fr_file = torrent_path
        original_meta_bytes = _bencode_bencode(metainfo)
        new_meta = _bencode_bencode(fast_resume)
        if new_meta != original_meta_bytes:
            fr_file = torrent_path.replace('.torrent', '-resume.torrent')
            if meta.get('debug', False):
                console.print("Creating fast resume file:", fr_file)
            _bencode_bwrite(fast_resume, fr_file)

        # Use dst path if linking was successful, otherwise use original path
        path = dst if (use_symlink or use_hardlink) and os.path.exists(dst) else path

        isdir = os.path.isdir(path)
        # Remote path mount
        modified_fr = False
        path_dir = ""
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path_dir = os.path.dirname(path)
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')
            shutil.copy(fr_file, f"{path_dir}/fr.torrent")
            fr_file = f"{os.path.dirname(path)}/fr.torrent"
            modified_fr = True
            if meta.get('debug', False):
                console.print(f"[cyan]Modified fast resume file path because path mapping: {fr_file}")
        if isdir is False:
            path = os.path.dirname(path)
        if meta.get('debug', False):
            console.print(f"[cyan]Final path for rTorrent: {path}")

        console.print("[bold yellow]Adding and starting torrent")
        rtorrent.load.start_verbose('', fr_file, f"d.directory_base.set={path}")
        if meta.get('debug', False):
            console.print(f"[green]rTorrent load start for {fr_file} with d.directory_base.set={path}")
        time.sleep(1)
        # Add labels
        if client.get('rtorrent_label') is not None:
            if meta.get('debug', False):
                console.print(f"[cyan]Setting rTorrent label: {client['rtorrent_label']}")
            rtorrent.d.custom1.set(torrent.infohash, client['rtorrent_label'])
        if meta.get('rtorrent_label') is not None:
            rtorrent.d.custom1.set(torrent.infohash, meta['rtorrent_label'])
            if meta.get('debug', False):
                console.print(f"[cyan]Setting rTorrent label from meta: {meta['rtorrent_label']}")

        # Delete modified fr_file location
        if modified_fr:
            if meta.get('debug', False):
                console.print(f"[cyan]Removing modified fast resume file: {fr_file}")
            os.remove(f"{path_dir}/fr.torrent")
        if meta.get('debug', False):
            console.print(f"[cyan]Path: {path}")

    def add_fast_resume(self, metainfo: dict[str, Any], datapath: str, _torrent: Torrent) -> dict[str, Any]:
        """ Add fast resume data to a metafile dict.
        """
        # Get list of files
        files = metainfo["info"].get("files", None)
        single = files is None
        if single:
            if os.path.isdir(datapath):
                datapath = os.path.join(datapath, metainfo["info"]["name"])
            files = [{
                "path": [os.path.abspath(datapath)],
                "length": metainfo["info"]["length"],
            }]

        # Prepare resume data
        resume = metainfo.setdefault("libtorrent_resume", {})
        resume["bitfield"] = len(metainfo["info"]["pieces"]) // 20
        resume["files"] = []
        piece_length_value = metainfo["info"]["piece length"]
        piece_length = int(piece_length_value) if isinstance(piece_length_value, (int, float, str)) else 0
        if piece_length <= 0:
            raise ValueError(f"Invalid piece length: {piece_length_value!r}")
        offset = 0

        for fileinfo in files:
            # Get the path into the filesystem
            filepath = os.sep.join(fileinfo["path"])
            if not single:
                filepath = os.path.join(datapath, filepath.strip(os.sep))

            # Check file size
            file_length_value = fileinfo["length"]
            file_length = int(file_length_value) if isinstance(file_length_value, (int, float, str)) else 0
            if os.path.getsize(filepath) != file_length:
                raise OSError(
                    errno.EINVAL,
                    f"File size mismatch for {filepath!r} [is {os.path.getsize(filepath)}, expected {file_length}]",
                )

            # Add resume data for this file
            resume["files"].append({
                'priority': 1,
                'mtime': int(os.path.getmtime(filepath)),
                'completed': (
                    (offset + file_length + piece_length - 1) // piece_length -
                    offset // piece_length
                ),
            })
            offset += file_length

        return metainfo

    async def get_ptp_from_hash_rtorrent(self, meta: dict[str, Any], pathed: bool = False) -> dict[str, Any]:
        default_cfg = cast(dict[str, Any], self.config.get('DEFAULT', {}))
        default_client_value = default_cfg.get('default_torrent_client')
        if not isinstance(default_client_value, str) or not default_client_value:
            console.print("[yellow]Missing default torrent client for rTorrent")
            return meta
        clients_cfg = cast(dict[str, Any], self.config.get('TORRENT_CLIENTS', {}))
        client = cast(dict[str, Any], clients_cfg.get(default_client_value, {}))
        torrent_storage_dir_value = client.get('torrent_storage_dir')
        torrent_storage_dir = str(torrent_storage_dir_value) if isinstance(torrent_storage_dir_value, str) else None
        info_hash_value = meta.get('infohash')
        info_hash_v1 = str(info_hash_value) if isinstance(info_hash_value, str) else None

        if not torrent_storage_dir or not info_hash_v1:
            console.print("[yellow]Missing torrent storage directory or infohash")
            return meta

        # Normalize info hash format for rTorrent (uppercase)
        info_hash_v1 = info_hash_v1.upper().strip()
        torrent_path = os.path.join(torrent_storage_dir, f"{info_hash_v1}.torrent")

        # Extract folder ID for use in temporary file path
        folder_id = os.path.basename(meta['path'])
        if meta.get('uuid') is None:
            meta['uuid'] = folder_id

        extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
        os.makedirs(extracted_torrent_dir, exist_ok=True)

        # Check if the torrent file exists directly
        if os.path.exists(torrent_path):
            console.print(f"[green]Found matching torrent file: {torrent_path}")
        else:
            # Try to find the torrent file in storage directory (case insensitive)
            found = False
            console.print(f"[yellow]Searching for torrent file with hash {info_hash_v1} in {torrent_storage_dir}")

            if os.path.exists(torrent_storage_dir):
                for filename in os.listdir(torrent_storage_dir):
                    filename_str = str(filename)
                    if filename_str.lower().endswith(".torrent"):
                        file_hash = os.path.splitext(filename_str)[0]  # Remove .torrent extension
                        if file_hash.upper() == info_hash_v1:
                            torrent_path = os.path.join(torrent_storage_dir, filename_str)
                            found = True
                            console.print(f"[green]Found torrent file with matching hash: {filename_str}")
                            break

            if not found:
                console.print(f"[bold red]No torrent file found for hash: {info_hash_v1}")
                return meta

        # Parse the torrent file to get the comment
        try:
            torrent = Torrent.read(torrent_path)
            comment = torrent.comment or ""

            # Try to find tracker IDs in the comment
            if meta.get('debug'):
                console.print(f"[cyan]Torrent comment: {comment}")

            torrent_comments_value = meta.get('torrent_comments')
            torrent_comments_list = (
                cast(list[Any], torrent_comments_value)
                if isinstance(torrent_comments_value, list)
                else []
            )
            torrent_comments = [
                cast(dict[str, Any], entry)
                for entry in torrent_comments_list
                if isinstance(entry, dict)
            ]
            meta['torrent_comments'] = torrent_comments

            comment_data = {
                'hash': getattr(torrent, 'infohash_v1', '') or '',
                'name': getattr(torrent, 'name', '') or '',
                'comment': comment,
            }
            torrent_comments.append(comment_data)

            if meta.get('debug', False):
                console.print(f"[cyan]Stored comment for torrent: {comment[:100]}...")

            # Handle various tracker URL formats in the comment
            tracker_ids = self._extract_tracker_ids_from_comment(comment)
            meta.update(tracker_ids)

            # If we found a tracker ID, log it
            for tracker in ['ptp', 'bhd', 'btn', 'blu', 'aither', 'lst', 'oe', 'hdb']:
                if meta.get(tracker):
                    console.print(f"[bold cyan]meta updated with {tracker.upper()} ID: {meta[tracker]}")

            if torrent_comments and meta.get('debug', False):
                console.print(f"[green]Stored {len(torrent_comments)} torrent comments for later use")

            if not pathed:
                valid, resolved_path = await self.is_valid_torrent(
                    meta, torrent_path, info_hash_v1, 'rtorrent', client
                )

                if valid:
                    base_torrent_path = os.path.join(extracted_torrent_dir, "BASE.torrent")

                    try:
                        await TorrentCreator.create_base_from_existing_torrent(resolved_path, meta['base_dir'], meta['uuid'])
                        if meta['debug']:
                            console.print("[green]Created BASE.torrent from existing torrent")
                    except Exception as e:
                        console.print(f"[bold red]Error creating BASE.torrent: {e}")
                        try:
                            shutil.copy2(resolved_path, base_torrent_path)
                            console.print(f"[yellow]Created simple torrent copy as fallback: {base_torrent_path}")
                        except Exception as copy_err:
                            console.print(f"[bold red]Failed to create backup copy: {copy_err}")

        except Exception as e:
            console.print(f"[bold red]Error reading torrent file: {e}")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return meta
