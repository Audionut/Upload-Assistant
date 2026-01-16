# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import platform
from typing import Any, Optional

from src.console import console


class Search:
    """
    Logic for searching
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        pass

    async def searchFile(self, filename: str) -> Optional[list[str]]:
        os_info = platform.platform()  # noqa F841
        filename = filename.lower()
        files_total: list[str] = []
        if filename == "":
            console.print("nothing entered")
            return None
        file_found = False  # noqa F841
        words = filename.split()

        async def search_file(search_dir: str) -> list[str]:
            files_total_search: list[str] = []
            console.print(f"Searching {search_dir}")
            for root, _dirs, files in os.walk(search_dir, topdown=False):
                for name in files:
                    if not name.endswith('.nfo'):
                        l_name = name.lower()
                        os_info = platform.platform()
                        if await self.file_search(l_name, words):
                            file_found = True  # noqa F841
                            if ('Windows' in os_info):
                                files_total_search.append(root + '\\' + name)
                            else:
                                files_total_search.append(root + '/' + name)
            return files_total_search
        config_dir = self.config['DISCORD']['search_dir']
        if isinstance(config_dir, list):
            for each in config_dir:
                files = await search_file(each)
                files_total = files_total + files
        else:
            files_total = await search_file(config_dir)
        return files_total

    async def searchFolder(self, foldername: str) -> Optional[list[str]]:
        os_info = platform.platform()  # noqa F841
        foldername = foldername.lower()
        folders_total: list[str] = []
        if foldername == "":
            console.print("nothing entered")
            return None
        folders_found = False  # noqa F841
        words = foldername.split()

        async def search_dir(search_dir: str) -> list[str]:
            console.print(f"Searching {search_dir}")
            folders_total_search: list[str] = []
            for root, dirs, _files in os.walk(search_dir, topdown=False):

                for name in dirs:
                    l_name = name.lower()

                    os_info = platform.platform()

                    if await self.file_search(l_name, words):
                        folder_found = True  # noqa F841
                        if ('Windows' in os_info):
                            folders_total_search.append(root + '\\' + name)
                        else:
                            folders_total_search.append(root + '/' + name)

            return folders_total_search
        config_dir = self.config['DISCORD']['search_dir']
        if isinstance(config_dir, list):
            for each in config_dir:
                folders = await search_dir(each)

                folders_total = folders_total + folders
        else:
            folders_total = await search_dir(config_dir)

        return folders_total

    async def file_search(self, name: str, name_words: list[str]) -> bool:
        check = True
        for word in name_words:
            if word not in name:
                check = False
                break
        return check
