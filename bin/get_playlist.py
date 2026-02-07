"""Minimal MPLS parser for Blu-ray Movie Playlists.

Original code; https://github.com/Ichunjo/pyparsebluray

This module keeps only what is required for:
    header = load_movie_playlist(mpls_file)
    mpls_file.seek(header.playlist_start_address, os.SEEK_SET)
    playlist = load_playlist(mpls_file)
"""

__all__ = [
    'MplsParser',
    'load_movie_playlist',
    'load_playlist',
]

from io import BufferedReader
from pprint import pformat
from struct import unpack
from types import SimpleNamespace
from typing import Any


class MplsParser:
    """Single-class MPLS parser (minimal fields only)."""
    mpls: BufferedReader

    def __init__(self, mpls: BufferedReader) -> None:
        self.mpls = mpls

    def __repr__(self) -> str:
        return pformat(vars(self), sort_dicts=False)

    def _get_pos(self) -> int:
        return self.mpls.tell()

    def _unpack_byte(self, n: int) -> tuple[Any, ...]:
        formats: dict[int, str] = {1: '>B', 2: '>H', 4: '>I', 8: '>Q'}
        return unpack(formats[n], self.mpls.read(n))

    def _as_namespace(self, data: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(**data)

    def load_movie_playlist(self) -> SimpleNamespace:
        """Load and parse the MPLS file header.

        https://github.com/lw/BluRay/wiki/MPLS
        """
        pos = self._get_pos()
        if pos != 0:
            raise ValueError('MoviePlaylist: You should call it at the start of the mpls file!')

        data: dict[str, Any] = {
            "type_indicator": self.mpls.read(4).decode('ascii'),
            "version_number": self.mpls.read(4).decode('ascii'),
            "playlist_start_address": self._unpack_byte(4)[0],
            "playlist_mark_start_address": self._unpack_byte(4)[0],
            "extension_data_start_address": self._unpack_byte(4)[0],
        }
        self.mpls.read(20)  # Reserved
        return self._as_namespace(data)

    def _load_play_item(self) -> SimpleNamespace:
        """Load and parse a single PlayItem.

        https://github.com/lw/BluRay/wiki/PlayItem
        """
        pos = self._get_pos()
        length = self._unpack_byte(2)[0]

        data: dict[str, Any] = {
            "length": length,
            "clip_information_filename": None,
            "intime": None,
            "outtime": None,
        }

        if length != 0:
            data["clip_information_filename"] = self.mpls.read(5).decode('utf-8')
            self.mpls.read(4)  # clip_codec_identifier
            self.mpls.read(2)  # misc_flags_1
            self.mpls.read(1)  # ref_to_stcid
            data["intime"] = self._unpack_byte(4)[0]
            data["outtime"] = self._unpack_byte(4)[0]

        self.mpls.seek(pos + length + 2)
        return self._as_namespace(data)

    def load_playlist(self) -> SimpleNamespace:
        """Load and parse the main playlist.

        https://github.com/lw/BluRay/wiki/PlayList
        """
        pos = self._get_pos()
        length = self._unpack_byte(4)[0]

        data: dict[str, Any] = {
            "length": length,
            "nb_play_items": None,
            "nb_sub_paths": None,
            "play_items": None,
        }

        if length != 0:
            self.mpls.read(2)  # reserved
            data["nb_play_items"] = self._unpack_byte(2)[0]
            data["nb_sub_paths"] = self._unpack_byte(2)[0]
            data["play_items"] = [self._load_play_item() for _ in range(data["nb_play_items"])]

        self.mpls.seek(pos + length + 4)
        return self._as_namespace(data)


def load_movie_playlist(mpls: BufferedReader) -> SimpleNamespace:
    """Load and parse the MPLS file header."""
    return MplsParser(mpls).load_movie_playlist()


def load_playlist(mpls: BufferedReader) -> SimpleNamespace:
    """Load and parse the main playlist."""
    return MplsParser(mpls).load_playlist()
