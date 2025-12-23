# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
import json
import cli_ui
from collections import defaultdict
from src.uploadscreens import upload_screens
from data.config import config
from src.console import console


async def add_comparison(meta):
    comparison_path = meta.get('comparison')
    if not comparison_path or not os.path.isdir(comparison_path):
        return []

    comparison_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/comparison_data.json"
    if os.path.exists(comparison_data_file):
        try:
            with open(comparison_data_file, 'r') as f:
                saved_comparison_data = json.load(f)
                if meta.get('debug'):
                    console.print(f"[cyan]Loading previously saved comparison data from {comparison_data_file}")
                meta["comparison_groups"] = saved_comparison_data

                comparison_index = meta.get('comparison_index')
                if comparison_index and comparison_index in saved_comparison_data:
                    if 'image_list' not in meta:
                        meta['image_list'] = []

                    urls_to_add = saved_comparison_data[comparison_index].get('urls', [])
                    if meta.get('debug'):
                        console.print(f"[cyan]Adding {len(urls_to_add)} images from comparison group {comparison_index} to image_list")

                    for url_info in urls_to_add:
                        if url_info not in meta['image_list']:
                            meta['image_list'].append(url_info)

                return saved_comparison_data
        except Exception as e:
            console.print(f"[yellow]Error loading saved comparison data: {e}")

    files = [f for f in os.listdir(comparison_path) if f.lower().endswith('.png')]
    pattern = re.compile(r"(\d+)-(\d+)-(.+)\.png", re.IGNORECASE)

    groups = defaultdict(list)
    suffixes = {}

    for f in files:
        match = pattern.match(f)
        if match:
            first, second, suffix = match.groups()
            groups[second].append((int(first), f))
            if second not in suffixes:
                suffixes[second] = suffix

    meta_comparisons = {}
    img_host_keys = [k for k in config.get('DEFAULT', {}) if k.startswith('img_host_')]
    img_host_indices = [int(k.split('_')[-1]) for k in img_host_keys]
    img_host_indices.sort()

    if not img_host_indices:
        raise ValueError("No image hosts found in config. Please ensure at least one 'img_host_X' key is present in config.")

    for idx, second in enumerate(sorted(groups, key=lambda x: int(x)), 1):
        img_host_num = img_host_indices[0]
        current_img_host_key = f'img_host_{img_host_num}'
        current_img_host = config.get('DEFAULT', {}).get(current_img_host_key)

        group = sorted(groups[second], key=lambda x: x[0])
        group_files = [f for _, f in group]
        custom_img_list = [os.path.join(comparison_path, filename) for filename in group_files]
        upload_meta = meta.copy()
        console.print(f"[cyan]Uploading comparison group {second} with files: {group_files}")

        upload_result, _ = await upload_screens(
            upload_meta, custom_img_list, img_host_num, 0, len(custom_img_list), custom_img_list, {}
        )

        uploaded_infos = [
            {k: item.get(k) for k in ("img_url", "raw_url", "web_url")}
            for item in upload_result
        ]

        group_name = suffixes.get(second, "")

        meta_comparisons[second] = {
            "files": group_files,
            "urls": uploaded_infos,
            "img_host": current_img_host,
            "name": group_name
        }

    comparison_index = meta.get('comparison_index')
    if not comparison_index:
        console.print("[red]No comparison index provided. Please specify a comparison index matching the input file.")
        while True:
            cli_input = cli_ui.input("Enter comparison index number: ")
            try:
                comparison_index = str(int(cli_input.strip()))
                break
            except Exception:
                console.print(f"[red]Invalid comparison index: {cli_input.strip()}")
    if comparison_index and comparison_index in meta_comparisons:
        if 'image_list' not in meta:
            meta['image_list'] = []

        urls_to_add = meta_comparisons[comparison_index].get('urls', [])
        if meta.get('debug'):
            console.print(f"[cyan]Adding {len(urls_to_add)} images from comparison group {comparison_index} to image_list")

        for url_info in urls_to_add:
            if url_info not in meta['image_list']:
                meta['image_list'].append(url_info)

    meta["comparison_groups"] = meta_comparisons

    try:
        with open(comparison_data_file, 'w') as f:
            json.dump(meta_comparisons, f, indent=4)
        if meta.get('debug'):
            console.print(f"[cyan]Saved comparison data to {comparison_data_file}")
    except Exception as e:
        console.print(f"[yellow]Failed to save comparison data: {e}")

    return meta_comparisons
