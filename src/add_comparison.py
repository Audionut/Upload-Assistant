# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import os
import re
from collections import defaultdict
from collections.abc import Mapping, MutableMapping
from typing import Any, Union, cast

import cli_ui

from src.console import console
from src.uploadscreens import UploadScreensManager

ComparisonGroup = dict[str, Any]
ComparisonData = dict[str, ComparisonGroup]


class ComparisonManager:
    def __init__(self, meta: MutableMapping[str, Any], config: Mapping[str, Any]) -> None:
        self.meta = meta
        default_config = cast(Mapping[str, Any], config.get('DEFAULT', {}))
        if not isinstance(default_config, dict):
            raise ValueError("'DEFAULT' config section must be a dict")
        self.default_config = default_config
        self.uploadscreens_manager = UploadScreensManager(cast(dict[str, Any], config))

    async def add_comparison(self) -> Union[ComparisonData, list[ComparisonGroup]]:
        comparison_path = self.meta.get('comparison')
        if not isinstance(comparison_path, str) or not os.path.isdir(comparison_path):
            return []

        comparison_data_file = f"{self.meta['base_dir']}/tmp/{self.meta['uuid']}/comparison_data.json"
        if os.path.exists(comparison_data_file):
            try:
                with open(comparison_data_file) as f:
                    raw_data: Any = json.load(f)
                    saved_comparison_data: Union[ComparisonData, list[ComparisonGroup]]
                    if isinstance(raw_data, dict):
                        raw_dict = cast(dict[str, Any], raw_data)
                        if not all(isinstance(v, dict) for v in raw_dict.values()):
                            raise ValueError("Invalid comparison data format: must be a dict of dicts")
                        saved_comparison_data = cast(ComparisonData, raw_dict)
                    elif isinstance(raw_data, list):
                        raw_list = cast(list[Any], raw_data)
                        if not all(isinstance(item, dict) for item in raw_list):
                            raise ValueError("Invalid comparison data format: must be a list of dicts")
                        saved_comparison_data = cast(list[ComparisonGroup], raw_list)
                    else:
                        raise ValueError("Invalid comparison data format: must be a dict of dicts or a list of dicts")
                    if self.meta.get('debug'):
                        console.print(f"[cyan]Loading previously saved comparison data from {comparison_data_file}")
                    self.meta["comparison_groups"] = saved_comparison_data

                    comparison_index = self.meta.get('comparison_index')
                    if comparison_index is not None:
                        # Normalize comparison_index to string once
                        comparison_index_str = str(comparison_index).strip()

                        # Initialize image_list once if needed
                        if 'image_list' not in self.meta:
                            self.meta['image_list'] = []

                        urls_to_add: list[dict[str, Any]] = []
                        found = False

                        if isinstance(saved_comparison_data, dict):
                            if comparison_index_str in saved_comparison_data:
                                group_data = saved_comparison_data[comparison_index_str]
                                urls_to_add = cast(list[dict[str, Any]], group_data.get('urls', []))
                                found = True
                            else:
                                console.print(f"[yellow]Comparison index '{comparison_index_str}' not found in saved data; available keys: {list(saved_comparison_data.keys())}[/yellow]")
                        else:
                            try:
                                idx = int(comparison_index_str)
                                if 0 <= idx < len(saved_comparison_data):
                                    list_item = saved_comparison_data[idx]
                                    urls_to_add = cast(list[dict[str, Any]], list_item.get('urls', []))
                                    found = True
                                else:
                                    console.print(f"[yellow]Comparison index '{comparison_index_str}' out of range; valid range: 0-{len(saved_comparison_data) - 1}[/yellow]")
                            except ValueError:
                                console.print(f"[yellow]Comparison index '{comparison_index_str}' is not a valid integer for list data[/yellow]")

                        if found and urls_to_add:
                            if self.meta.get('debug'):
                                console.print(f"[cyan]Adding {len(urls_to_add)} images from comparison group {comparison_index_str} to image_list")
                            image_list = cast(list[dict[str, Any]], self.meta.get('image_list', []))
                            self.meta['image_list'] = image_list
                            for url_info in urls_to_add:
                                if url_info not in image_list:
                                    image_list.append(url_info)

                    return saved_comparison_data
            except Exception as e:
                console.print(f"[yellow]Error loading saved comparison data: {e}")

        files: list[str] = [f for f in os.listdir(comparison_path) if f.lower().endswith('.png')]
        pattern = re.compile(r"(\d+)-(\d+)-(.+)\.png", re.IGNORECASE)

        groups: defaultdict[str, list[tuple[int, str]]] = defaultdict(list)
        suffixes: dict[str, str] = {}

        for f in files:
            match = pattern.match(f)
            if match:
                first, second, suffix = match.groups()
                groups[second].append((int(first), f))
                if second not in suffixes:
                    suffixes[second] = suffix

        meta_comparisons: ComparisonData = {}
        img_host_keys = [k for k in self.default_config if k.startswith('img_host_')]
        img_host_indices = [int(k.split('_')[-1]) for k in img_host_keys if k.split('_')[-1].isdigit()]
        img_host_indices.sort()

        if not img_host_indices:
            raise ValueError("No image hosts found in config. Please ensure at least one 'img_host_X' key is present in config.")

        for _idx, second in enumerate(sorted(groups, key=lambda x: int(x)), 1):
            img_host_num = img_host_indices[0]
            current_img_host_key = f'img_host_{img_host_num}'
            current_img_host = self.default_config.get(current_img_host_key)
            if current_img_host is not None and not isinstance(current_img_host, str):
                current_img_host = str(current_img_host)

            group = sorted(groups[second], key=lambda x: x[0])
            group_files: list[str] = [f for _, f in group]
            custom_img_list: list[str] = [os.path.join(comparison_path, filename) for filename in group_files]
            upload_meta = dict(self.meta)
            console.print(f"[cyan]Uploading comparison group {second} with files: {group_files}")

            upload_result, _ = await self.uploadscreens_manager.upload_screens(
                upload_meta, len(custom_img_list), img_host_num, 0, len(custom_img_list), custom_img_list, {}
            )

            upload_result_list = cast(list[Mapping[str, Any]], upload_result)
            uploaded_infos: list[dict[str, Any]] = [
                {k: item.get(k) for k in ("img_url", "raw_url", "web_url")}
                for item in upload_result_list
            ]

            group_name = suffixes.get(second, "")

            meta_comparisons[second] = {
                "files": group_files,
                "urls": uploaded_infos,
                "img_host": current_img_host,
                "name": group_name
            }

        comparison_index = self.meta.get('comparison_index')
        if comparison_index is None:
            console.print("[red]No comparison index provided. Please specify a comparison index matching the input file.")
            while True:
                cli_input = cli_ui.ask_string("Enter comparison index number: ") or ""
                try:
                    comparison_index = str(int(cli_input.strip()))
                    break
                except Exception:
                    console.print(f"[red]Invalid comparison index: {cli_input.strip()}")
        comparison_index_str = str(comparison_index).strip() if comparison_index is not None else ""
        if comparison_index_str and comparison_index_str in meta_comparisons:
            if 'image_list' not in self.meta:
                self.meta['image_list'] = []

            urls_to_add = cast(list[dict[str, Any]], meta_comparisons[comparison_index_str].get('urls', []))
            if self.meta.get('debug'):
                console.print(f"[cyan]Adding {len(urls_to_add)} images from comparison group {comparison_index_str} to image_list")

            image_list = cast(list[dict[str, Any]], self.meta.get('image_list', []))
            self.meta['image_list'] = image_list
            for url_info in urls_to_add:
                if url_info not in image_list:
                    image_list.append(url_info)

        self.meta["comparison_groups"] = meta_comparisons

        try:
            with open(comparison_data_file, 'w') as f:
                json.dump(meta_comparisons, f, indent=4)
            if self.meta.get('debug'):
                console.print(f"[cyan]Saved comparison data to {comparison_data_file}")
        except Exception as e:
            console.print(f"[yellow]Failed to save comparison data: {e}")

        return meta_comparisons
