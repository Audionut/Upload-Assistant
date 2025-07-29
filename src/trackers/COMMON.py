from torf import Torrent
import os
import requests
import re
import json
import click
import sys
import glob
from pymediainfo import MediaInfo
import secrets
from src.bbcode import BBCODE
from src.console import console
from src.uploadscreens import upload_screens
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.languages import process_desc_language


class COMMON():
    def __init__(self, config):
        self.config = config
        self.parser = self.MediaInfoParser()
        pass

    async def edit_torrent(self, meta, tracker, source_flag, torrent_filename="BASE"):
        if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/{torrent_filename}.torrent"):
            new_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/{torrent_filename}.torrent")
            for each in list(new_torrent.metainfo):
                if each not in ('announce', 'comment', 'creation date', 'created by', 'encoding', 'info'):
                    new_torrent.metainfo.pop(each, None)
            new_torrent.metainfo['announce'] = self.config['TRACKERS'][tracker].get('announce_url', "https://fake.tracker").strip()
            new_torrent.metainfo['info']['source'] = source_flag
            if 'created by' in new_torrent.metainfo and isinstance(new_torrent.metainfo['created by'], str):
                created_by = new_torrent.metainfo['created by']
                if "mkbrr" in created_by.lower():
                    new_torrent.metainfo['created by'] = f"{created_by} using Audionut's Upload Assistant"
            if int(meta.get('entropy', None)) == 32:
                new_torrent.metainfo['info']['entropy'] = secrets.randbelow(2**31)
            elif int(meta.get('entropy', None)) == 64:
                new_torrent.metainfo['info']['entropy'] = secrets.randbelow(2**64)
            # setting comment as blank as if BASE.torrent is manually created then it can result in private info such as download link being exposed.
            new_torrent.metainfo['comment'] = ''

            Torrent.copy(new_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent", overwrite=True)

    # used to add tracker url, comment and source flag to torrent file
    async def add_tracker_torrent(self, meta, tracker, source_flag, new_tracker, comment):
        if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent"):
            new_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent")
            new_torrent.metainfo['announce'] = new_tracker
            new_torrent.metainfo['comment'] = comment
            new_torrent.metainfo['info']['source'] = source_flag
            Torrent.copy(new_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent", overwrite=True)

    async def unit3d_edit_desc(self, meta, tracker, signature, comparison=False, desc_header="", image_list=None):
        if image_list is not None:
            images = image_list
            multi_screens = 0
        else:
            images = meta['image_list']
            multi_screens = int(self.config['DEFAULT'].get('multiScreens', 2))

        # Check for saved pack_image_links.json file
        pack_images_file = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "pack_image_links.json")
        pack_images_data = {}
        if os.path.exists(pack_images_file):
            try:
                with open(pack_images_file, 'r', encoding='utf-8') as f:
                    pack_images_data = json.load(f)
                    if meta['debug']:
                        console.print(f"[green]Loaded previously uploaded images from {pack_images_file}")
                        console.print(f"[blue]Found {pack_images_data.get('total_count', 0)} previously uploaded images")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load pack image data: {str(e)}[/yellow]")

        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf8').read()
        char_limit = int(self.config['DEFAULT'].get('charLimit', 14000))
        file_limit = int(self.config['DEFAULT'].get('fileLimit', 5))
        thumb_size = int(self.config['DEFAULT'].get('pack_thumb_size', '300'))
        cover_size = int(self.config['DEFAULT'].get('bluray_image_size', '250'))
        process_limit = int(self.config['DEFAULT'].get('processLimit', 10))
        episode_overview = int(self.config['DEFAULT'].get('episode_overview', False))
        try:
            # If tracker has screenshot header specified in config, use that. Otherwise, check if screenshot default is used. Otherwise, fall back to None
            screenheader = self.config['TRACKERS'][tracker].get('custom_screenshot_header', self.config['DEFAULT'].get('screenshot_header', None))
        except Exception:
            screenheader = None
        try:
            # If tracker has description header specified in config, use that. Otherwise, check if custom description header default is used.
            desc_header = self.config['TRACKERS'][tracker].get('custom_description_header', self.config['DEFAULT'].get('custom_description_header', desc_header))
        except Exception as e:
            console.print(f"[yellow]Warning: Error setting custom description header: {str(e)}[/yellow]")
        try:
            # If screensPerRow is set, use that to determine how many screenshots should be on each row. Otherwise, use 2 as default
            screensPerRow = int(self.config['DEFAULT'].get('screens_per_row', 2))
        except Exception:
            screensPerRow = 2
        try:
            # If custom signature set and isn't empty, use that instead of the signature parameter
            custom_signature = self.config['TRACKERS'][tracker].get('custom_signature', signature)
            if custom_signature != '':
                signature = custom_signature
        except Exception as e:
            console.print(f"[yellow]Warning: Error setting custom signature: {str(e)}[/yellow]")
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            if desc_header:
                if not desc_header.endswith('\n'):
                    descfile.write(desc_header + '\n')
                else:
                    descfile.write(desc_header)
            await process_desc_language(meta, descfile, tracker)
            add_logo_enabled = self.config["DEFAULT"].get("add_logo", False)
            if add_logo_enabled and 'logo' in meta:
                logo = meta['logo']
                logo_size = self.config["DEFAULT"].get("logo_size", 420)
                if logo != "":
                    descfile.write(f"[center][img={logo_size}]{logo}[/img][/center]\n\n")
            bluray_link = self.config['DEFAULT'].get("add_bluray_link", False)
            if meta.get('is_disc') == "BDMV" and bluray_link and meta.get('release_url', ''):
                descfile.write(f"[center]{meta['release_url']}[/center]\n")
            covers = False
            if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/covers.json"):
                covers = True
            if meta.get('is_disc') == "BDMV" and self.config['DEFAULT'].get('use_bluray_images', False) and covers:
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/covers.json", 'r', encoding='utf-8') as f:
                    cover_data = json.load(f)
                if isinstance(cover_data, list):
                    descfile.write("[center]")

                    for img_data in cover_data:
                        if 'raw_url' in img_data and 'web_url' in img_data:
                            web_url = img_data['web_url']
                            raw_url = img_data['raw_url']
                            descfile.write(f"[url={web_url}][img={cover_size}]{raw_url}[/img][/url]")

                    descfile.write("[/center]\n\n")
            season_name = meta.get('tvdb_season_name') if meta.get('tvdb_season_name') is not None and meta.get('tvdb_season_name') != "" else None
            season_number = meta.get('tvdb_season_number') if meta.get('tvdb_season_number') is not None and meta.get('tvdb_season_number') != "" else None
            episode_number = meta.get('tvdb_episode_number') if meta.get('tvdb_episode_number') is not None and meta.get('tvdb_episode_number') != "" else None
            episode_title = meta.get('auto_episode_title') if meta.get('auto_episode_title') is not None and meta.get('auto_episode_title') != "" else None
            if episode_title is None:
                episode_title = meta.get('tvmaze_episode_data', {}).get('episode_name') if meta.get('tvmaze_episode_data', {}).get('episode_name') else None
            if episode_overview and season_name and season_number and episode_number and episode_title:
                if not tracker == "HUNO":
                    descfile.write("[center][pre]")
                else:
                    descfile.write("[center]")
                descfile.write(f"{season_name} - S{season_number}E{episode_number}: {episode_title}")
                if not tracker == "HUNO":
                    descfile.write("[/pre][/center]\n\n")
                else:
                    descfile.write("[/center]\n\n")
            if episode_overview and meta.get('overview_meta') is not None and meta.get('overview_meta') != "":
                episode_data = meta.get('overview_meta')
                if not tracker == "HUNO":
                    descfile.write("[center][pre]")
                else:
                    descfile.write("[center]")
                descfile.write(episode_data)
                if not tracker == "HUNO":
                    descfile.write("[/pre][/center]\n\n")
                else:
                    descfile.write("[/center]\n\n")

            try:
                if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                    descfile.write(self.config['DEFAULT'].get('tonemapped_header'))
            except Exception as e:
                console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")

            bbcode = BBCODE()
            discs = meta.get('discs', [])
            filelist = meta.get('filelist', [])
            desc = base
            desc = re.sub(r'\[center\]\[spoiler=Scene NFO:\].*?\[/center\]', '', desc, flags=re.DOTALL)
            if not tracker == "AITHER":
                desc = re.sub(r'\[center\]\[spoiler=FraMeSToR NFO:\].*?\[/center\]', '', desc, flags=re.DOTALL)
            else:
                if "framestor" in meta and meta['framestor']:
                    desc = re.sub(r'\[center\]\[spoiler=FraMeSToR NFO:\]', '', desc, count=1)
                    desc = re.sub(r'\[/spoiler\]\[/center\]', '', desc, count=1)
                    desc = desc.replace("https://i.imgur.com/e9o0zpQ.png", "https://beyondhd.co/images/2017/11/30/c5802892418ee2046efba17166f0cad9.png")
                    images = []
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = desc.replace("[user]", "").replace("[/user]", "")
            desc = desc.replace("[hr]", "").replace("[/hr]", "")
            desc = desc.replace("[ul]", "").replace("[/ul]", "")
            desc = desc.replace("[ol]", "").replace("[/ol]", "")
            if comparison is False:
                desc = bbcode.convert_comparison_to_collapse(desc, 1000)
            desc = desc.replace('[img]', '[img=300]')
            descfile.write(desc)
            # Handle single disc case
            if len(discs) == 1:
                each = discs[0]
                if each['type'] == "DVD":
                    descfile.write("[center]")
                    descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler]\n\n")
                    descfile.write("[/center]")
                if screenheader is not None:
                    descfile.write(screenheader + '\n')
                descfile.write("[center]")
                for img_index in range(len(images[:int(meta['screens'])])):
                    web_url = images[img_index]['web_url']
                    raw_url = images[img_index]['raw_url']
                    descfile.write(f"[url={web_url}][img={self.config['DEFAULT'].get('thumbnail_size', '350')}]{raw_url}[/img][/url] ")

                    # If screensPerRow is set and we have reached that number of screenshots, add a new line
                    if screensPerRow and (img_index + 1) % screensPerRow == 0:
                        descfile.write("\n")
                descfile.write("[/center]")
                if each['type'] == "BDMV":
                    bdinfo_keys = [key for key in each if key.startswith("bdinfo")]
                    if len(bdinfo_keys) > 1:
                        if 'retry_count' not in meta:
                            meta['retry_count'] = 0

                        for i, key in enumerate(bdinfo_keys[1:], start=1):  # Skip the first bdinfo
                            new_images_key = f'new_images_playlist_{i}'
                            bdinfo = each[key]
                            edition = bdinfo.get("edition", "Unknown Edition")

                            # Find the corresponding summary for this bdinfo
                            summary_key = f"summary_{i}" if i > 0 else "summary"
                            summary = each.get(summary_key, "No summary available")

                            # Check for saved images first
                            if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                                saved_images = pack_images_data['keys'][new_images_key]['images']
                                if saved_images:
                                    if meta['debug']:
                                        console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                                    meta[new_images_key] = []
                                    for img in saved_images:
                                        meta[new_images_key].append({
                                            'img_url': img.get('img_url', ''),
                                            'raw_url': img.get('raw_url', ''),
                                            'web_url': img.get('web_url', '')
                                        })

                            if new_images_key in meta and meta[new_images_key]:
                                descfile.write("[center]\n\n")
                                # Use the summary corresponding to the current bdinfo
                                descfile.write(f"[spoiler={edition}][code]{summary}[/code][/spoiler]\n\n")
                                if meta['debug']:
                                    console.print("[yellow]Using original uploaded images for first disc")
                                descfile.write("[center]")
                                for img in meta[new_images_key]:
                                    web_url = img['web_url']
                                    raw_url = img['raw_url']
                                    image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                    descfile.write(image_str)
                                descfile.write("[/center]\n ")
                            else:
                                descfile.write("[center]\n\n")
                                # Use the summary corresponding to the current bdinfo
                                descfile.write(f"[spoiler={edition}][code]{summary}[/code][/spoiler]\n\n")
                                descfile.write("[/center]\n\n")
                                meta['retry_count'] += 1
                                meta[new_images_key] = []
                                new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png")
                                if not new_screens:
                                    use_vs = meta.get('vapoursynth', False)
                                    try:
                                        await disc_screenshots(meta, f"PLAYLIST_{i}", bdinfo, meta['uuid'], meta['base_dir'], use_vs, [], meta.get('ffdebug', False), multi_screens, True)
                                    except Exception as e:
                                        print(f"Error during BDMV screenshot capture: {e}")
                                    new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"PLAYLIST_{i}-*.png")
                                if new_screens and not meta.get('skip_imghost_upload', False):
                                    uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
                                    if uploaded_images and not meta.get('skip_imghost_upload', False):
                                        await self.save_image_links(meta, new_images_key, uploaded_images)
                                    for img in uploaded_images:
                                        meta[new_images_key].append({
                                            'img_url': img['img_url'],
                                            'raw_url': img['raw_url'],
                                            'web_url': img['web_url']
                                        })

                                    descfile.write("[center]")
                                    for img in uploaded_images:
                                        web_url = img['web_url']
                                        raw_url = img['raw_url']
                                        image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                        descfile.write(image_str)
                                    descfile.write("[/center]\n")

                                meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                                with open(meta_filename, 'w') as f:
                                    json.dump(meta, f, indent=4)

            # Handle multiple discs case
            elif len(discs) > 1:
                # Initialize retry_count if not already set
                if 'retry_count' not in meta:
                    meta['retry_count'] = 0

                total_discs_to_process = min(len(discs), process_limit)
                processed_count = 0
                if multi_screens != 0:
                    console.print("[cyan]Processing screenshots for packed content (multiScreens)[/cyan]")
                    console.print(f"[cyan]{total_discs_to_process} files (processLimit)[/cyan]")

                for i, each in enumerate(discs):
                    # Set a unique key per disc for managing images
                    new_images_key = f'new_images_disc_{i}'

                    if i == 0:
                        descfile.write("[center]")
                        if each['type'] == "BDMV":
                            descfile.write(f"{each.get('name', 'BDINFO')}\n\n")
                        elif each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler]")
                            descfile.write(f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n")
                        # For the first disc, use images from `meta['image_list']` and add screenheader if applicable
                        if meta['debug']:
                            console.print("[yellow]Using original uploaded images for first disc")
                        if screenheader is not None:
                            descfile.write("[/center]\n\n")
                            descfile.write(screenheader + '\n')
                            descfile.write("[center]")
                        for img_index in range(len(images[:int(meta['screens'])])):
                            web_url = images[img_index]['web_url']
                            raw_url = images[img_index]['raw_url']
                            image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                            descfile.write(image_str)

                            # If screensPerRow is set and we have reached that number of screenshots, add a new line
                            if screensPerRow and (img_index + 1) % screensPerRow == 0:
                                descfile.write("\n")
                        descfile.write("[/center]\n\n")
                    else:
                        if multi_screens != 0:
                            processed_count += 1
                            disc_name = each.get('name', f"Disc {i}")
                            print(f"\rProcessing disc {processed_count}/{total_discs_to_process}: {disc_name[:40]}{'...' if len(disc_name) > 40 else ''}", end="", flush=True)
                            # Check if screenshots exist for the current disc key
                            # Check for saved images first
                            if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                                saved_images = pack_images_data['keys'][new_images_key]['images']
                                if saved_images:
                                    if meta['debug']:
                                        console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                                    meta[new_images_key] = []
                                    for img in saved_images:
                                        meta[new_images_key].append({
                                            'img_url': img.get('img_url', ''),
                                            'raw_url': img.get('raw_url', ''),
                                            'web_url': img.get('web_url', '')
                                        })
                            if new_images_key in meta and meta[new_images_key]:
                                if meta['debug']:
                                    console.print(f"[yellow]Found needed image URLs for {new_images_key}")
                                descfile.write("[center]")
                                if each['type'] == "BDMV":
                                    descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                                elif each['type'] == "DVD":
                                    descfile.write(f"{each['name']}:\n")
                                    descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler] ")
                                    descfile.write(f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n")
                                descfile.write("[/center]\n\n")
                                # Use existing URLs from meta to write to descfile
                                descfile.write("[center]")
                                for img in meta[new_images_key]:
                                    web_url = img['web_url']
                                    raw_url = img['raw_url']
                                    image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url]"
                                    descfile.write(image_str)
                                descfile.write("[/center]\n\n")
                            else:
                                # Increment retry_count for tracking but use unique disc keys for each disc
                                meta['retry_count'] += 1
                                meta[new_images_key] = []
                                descfile.write("[center]")
                                if each['type'] == "BDMV":
                                    descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                                elif each['type'] == "DVD":
                                    descfile.write(f"{each['name']}:\n")
                                    descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code]{each['vob_mi']}[/code][/spoiler] ")
                                    descfile.write(f"[spoiler={os.path.basename(each['ifo'])}][code]{each['ifo_mi']}[/code][/spoiler]\n\n")
                                descfile.write("[/center]\n\n")
                                # Check if new screenshots already exist before running prep.screenshots
                                if each['type'] == "BDMV":
                                    new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                                elif each['type'] == "DVD":
                                    new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png")
                                if not new_screens:
                                    if meta['debug']:
                                        console.print(f"[yellow]No new screens for {new_images_key}; creating new screenshots")
                                    # Run prep.screenshots if no screenshots are present
                                    if each['type'] == "BDMV":
                                        use_vs = meta.get('vapoursynth', False)
                                        try:
                                            await disc_screenshots(meta, f"FILE_{i}", each['bdinfo'], meta['uuid'], meta['base_dir'], use_vs, [], meta.get('ffdebug', False), multi_screens, True)
                                        except Exception as e:
                                            print(f"Error during BDMV screenshot capture: {e}")
                                        new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")
                                    if each['type'] == "DVD":
                                        try:
                                            await dvd_screenshots(meta, i, multi_screens, True)
                                        except Exception as e:
                                            print(f"Error during DVD screenshot capture: {e}")
                                        new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['discs'][i]['name']}-*.png")

                                if new_screens and not meta.get('skip_imghost_upload', False):
                                    uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
                                    if uploaded_images and not meta.get('skip_imghost_upload', False):
                                        await self.save_image_links(meta, new_images_key, uploaded_images)
                                    # Append each uploaded image's data to `meta[new_images_key]`
                                    for img in uploaded_images:
                                        meta[new_images_key].append({
                                            'img_url': img['img_url'],
                                            'raw_url': img['raw_url'],
                                            'web_url': img['web_url']
                                        })

                                    # Write new URLs to descfile
                                    descfile.write("[center]")
                                    for img in uploaded_images:
                                        web_url = img['web_url']
                                        raw_url = img['raw_url']
                                        image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                        descfile.write(image_str)
                                    descfile.write("[/center]\n")

                                # Save the updated meta to `meta.json` after upload
                                meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
                                with open(meta_filename, 'w') as f:
                                    json.dump(meta, f, indent=4)
                            console.print()

            # Handle single file case
            if len(filelist) == 1:
                if meta.get('comparison') and meta.get('comparison_groups'):
                    descfile.write("[center]")
                    comparison_groups = meta.get('comparison_groups', {})
                    sorted_group_indices = sorted(comparison_groups.keys(), key=lambda x: int(x))

                    comp_sources = []
                    for group_idx in sorted_group_indices:
                        group_data = comparison_groups[group_idx]
                        group_name = group_data.get('name', f'Group {group_idx}')
                        comp_sources.append(group_name)

                    sources_string = ", ".join(comp_sources)
                    descfile.write(f"[comparison={sources_string}]\n")

                    images_per_group = min([
                        len(comparison_groups[idx].get('urls', []))
                        for idx in sorted_group_indices
                    ])

                    for img_idx in range(images_per_group):
                        for group_idx in sorted_group_indices:
                            group_data = comparison_groups[group_idx]
                            urls = group_data.get('urls', [])
                            if img_idx < len(urls):
                                img_url = urls[img_idx].get('raw_url', '')
                                if img_url:
                                    descfile.write(f"{img_url}\n")

                    descfile.write("[/comparison][/center]\n\n")

                if screenheader is not None:
                    descfile.write(screenheader + '\n')
                descfile.write("[center]")
                for img_index in range(len(images[:int(meta['screens'])])):
                    web_url = images[img_index]['web_url']
                    raw_url = images[img_index]['raw_url']
                    descfile.write(f"[url={web_url}][img={self.config['DEFAULT'].get('thumbnail_size', '350')}]{raw_url}[/img][/url] ")
                    if screensPerRow and (img_index + 1) % screensPerRow == 0:
                        descfile.write("\n")
                descfile.write("[/center]")

            # Handle multiple files case
            # Initialize character counter
            char_count = 0
            max_char_limit = char_limit  # Character limit
            other_files_spoiler_open = False  # Track if "Other files" spoiler has been opened
            total_files_to_process = min(len(filelist), process_limit)
            processed_count = 0
            if multi_screens != 0 and total_files_to_process > 1:
                console.print("[cyan]Processing screenshots for packed content (multiScreens)[/cyan]")
                console.print(f"[cyan]{total_files_to_process} files (processLimit)[/cyan]")

            # First Pass: Create and Upload Images for Each File
            for i, file in enumerate(filelist):
                if i >= process_limit:
                    # console.print("[yellow]Skipping processing more files as they exceed the process limit.")
                    continue
                if multi_screens != 0:
                    if total_files_to_process > 1:
                        processed_count += 1
                        filename = os.path.basename(file)
                        print(f"\rProcessing file {processed_count}/{total_files_to_process}: {filename[:40]}{'...' if len(filename) > 40 else ''}", end="", flush=True)
                    if i > 0:
                        new_images_key = f'new_images_file_{i}'
                        # Check for saved images first
                        if pack_images_data and 'keys' in pack_images_data and new_images_key in pack_images_data['keys']:
                            saved_images = pack_images_data['keys'][new_images_key]['images']
                            if saved_images:
                                if meta['debug']:
                                    console.print(f"[yellow]Using saved images from pack_image_links.json for {new_images_key}")

                                meta[new_images_key] = []
                                for img in saved_images:
                                    meta[new_images_key].append({
                                        'img_url': img.get('img_url', ''),
                                        'raw_url': img.get('raw_url', ''),
                                        'web_url': img.get('web_url', '')
                                    })
                        if new_images_key not in meta or not meta[new_images_key]:
                            meta[new_images_key] = []
                            # Proceed with image generation if not already present
                            new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")

                            # If no screenshots exist, create them
                            if not new_screens:
                                if meta['debug']:
                                    console.print(f"[yellow]No existing screenshots for {new_images_key}; generating new ones.")
                            try:
                                await screenshots(file, f"FILE_{i}", meta['uuid'], meta['base_dir'], meta, multi_screens, True, None)
                            except Exception as e:
                                print(f"Error during generic screenshot capture: {e}")

                            new_screens = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"FILE_{i}-*.png")

                            # Upload generated screenshots
                            if new_screens and not meta.get('skip_imghost_upload', False):
                                uploaded_images, _ = await upload_screens(meta, multi_screens, 1, 0, multi_screens, new_screens, {new_images_key: meta[new_images_key]})
                                if uploaded_images and not meta.get('skip_imghost_upload', False):
                                    await self.save_image_links(meta, new_images_key, uploaded_images)
                                for img in uploaded_images:
                                    meta[new_images_key].append({
                                        'img_url': img['img_url'],
                                        'raw_url': img['raw_url'],
                                        'web_url': img['web_url']
                                    })

            # Save updated meta
            meta_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json"
            with open(meta_filename, 'w') as f:
                json.dump(meta, f, indent=4)

            # Second Pass: Process MediaInfo and Write Descriptions
            if len(filelist) > 1:
                for i, file in enumerate(filelist):
                    if i >= process_limit:
                        continue
                    # Extract filename directly from the file path
                    filename = os.path.splitext(os.path.basename(file.strip()))[0].replace('[', '').replace(']', '')

                    # If we are beyond the file limit, add all further files in a spoiler
                    if multi_screens != 0:
                        if i >= file_limit:
                            if not other_files_spoiler_open:
                                descfile.write("[center][spoiler=Other files]\n")
                                char_count += len("[center][spoiler=Other files]\n")
                                other_files_spoiler_open = True

                    # Write filename in BBCode format with MediaInfo in spoiler if not the first file
                    if multi_screens != 0:
                        if i > 0 and char_count < max_char_limit:
                            mi_dump = MediaInfo.parse(file, output="STRING", full=False, mediainfo_options={'inform_version': '1'})
                            parsed_mediainfo = self.parser.parse_mediainfo(mi_dump)
                            formatted_bbcode = self.parser.format_bbcode(parsed_mediainfo)
                            descfile.write(f"[center][spoiler={filename}]{formatted_bbcode}[/spoiler][/center]\n")
                            char_count += len(f"[center][spoiler={filename}]{formatted_bbcode}[/spoiler][/center]\n")
                        else:
                            # If there are screen shots and screen shot header, write the header above the first filename
                            if i == 0 and images and screenheader is not None:
                                descfile.write(screenheader + '\n')
                                char_count += len(screenheader + '\n')
                            descfile.write(f"[center]{filename}\n[/center]\n")
                            char_count += len(f"[center]{filename}\n[/center]\n")

                    # Write images if they exist
                    new_images_key = f'new_images_file_{i}'
                    if i == 0:  # For the first file, use 'image_list' key and add screenheader if applicable
                        if images:
                            descfile.write("[center]")
                            char_count += len("[center]")
                            for img_index in range(len(images)):
                                web_url = images[img_index]['web_url']
                                raw_url = images[img_index]['raw_url']
                                image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                descfile.write(image_str)
                                char_count += len(image_str)

                                # If screensPerRow is set and we have reached that number of screenshots, add a new line
                                if screensPerRow and (img_index + 1) % screensPerRow == 0:
                                    descfile.write("\n")
                            descfile.write("[/center]\n\n")
                            char_count += len("[/center]\n\n")
                    elif multi_screens != 0:
                        if new_images_key in meta and meta[new_images_key]:
                            descfile.write("[center]")
                            char_count += len("[center]")
                            for img in meta[new_images_key]:
                                web_url = img['web_url']
                                raw_url = img['raw_url']
                                image_str = f"[url={web_url}][img={thumb_size}]{raw_url}[/img][/url] "
                                descfile.write(image_str)
                                char_count += len(image_str)
                            descfile.write("[/center]\n")
                            char_count += len("[/center]\n\n")

                if other_files_spoiler_open:
                    descfile.write("[/spoiler][/center]\n")
                    char_count += len("[/spoiler][/center]\n")

            if char_count >= 1 and meta['debug']:
                console.print(f"[yellow]Total characters written to description: {char_count}")
            if total_files_to_process > 1:
                console.print()

            # Append signature if provided
            if signature:
                descfile.write(signature)
            descfile.close()
        return

    async def save_image_links(self, meta, image_key, image_list=None):
        if image_list is None:
            console.print("[yellow]No image links to save.[/yellow]")
            return None

        output_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "pack_image_links.json")

        # Load existing data if the file exists
        existing_data = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load existing image data: {str(e)}[/yellow]")

        # Create data structure if it doesn't exist yet
        if not existing_data:
            existing_data = {
                "keys": {},
                "total_count": 0
            }

        # Update the data with the new images under the specific key
        if image_key not in existing_data["keys"]:
            existing_data["keys"][image_key] = {
                "count": 0,
                "images": []
            }

        # Add new images to the specific key
        for idx, img in enumerate(image_list):
            image_entry = {
                "index": existing_data["keys"][image_key]["count"] + idx,
                "raw_url": img.get("raw_url", ""),
                "web_url": img.get("web_url", ""),
                "img_url": img.get("img_url", ""),
            }
            existing_data["keys"][image_key]["images"].append(image_entry)

        # Update counts
        existing_data["keys"][image_key]["count"] = len(existing_data["keys"][image_key]["images"])
        existing_data["total_count"] = sum(key_data["count"] for key_data in existing_data["keys"].values())

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)

            if meta['debug']:
                console.print(f"[green]Saved {len(image_list)} new images for key '{image_key}' (total: {existing_data['total_count']}):[/green]")
                console.print(f"[blue]  - JSON: {output_file}[/blue]")

            return output_file
        except Exception as e:
            console.print(f"[bold red]Error saving image links: {e}[/bold red]")
            return None

    async def unit3d_region_ids(self, region, reverse=False, region_id=None):
        region_map = {
            'AFG': 1, 'AIA': 2, 'ALA': 3, 'ALG': 4, 'AND': 5, 'ANG': 6, 'ARG': 7, 'ARM': 8, 'ARU': 9,
            'ASA': 10, 'ATA': 11, 'ATF': 12, 'ATG': 13, 'AUS': 14, 'AUT': 15, 'AZE': 16, 'BAH': 17,
            'BAN': 18, 'BDI': 19, 'BEL': 20, 'BEN': 21, 'BER': 22, 'BES': 23, 'BFA': 24, 'BHR': 25,
            'BHU': 26, 'BIH': 27, 'BLM': 28, 'BLR': 29, 'BLZ': 30, 'BOL': 31, 'BOT': 32, 'BRA': 33,
            'BRB': 34, 'BRU': 35, 'BVT': 36, 'CAM': 37, 'CAN': 38, 'CAY': 39, 'CCK': 40, 'CEE': 41,
            'CGO': 42, 'CHA': 43, 'CHI': 44, 'CHN': 45, 'CIV': 46, 'CMR': 47, 'COD': 48, 'COK': 49,
            'COL': 50, 'COM': 51, 'CPV': 52, 'CRC': 53, 'CRO': 54, 'CTA': 55, 'CUB': 56, 'CUW': 57,
            'CXR': 58, 'CYP': 59, 'DJI': 60, 'DMA': 61, 'DOM': 62, 'ECU': 63, 'EGY': 64, 'ENG': 65,
            'EQG': 66, 'ERI': 67, 'ESH': 68, 'ESP': 69, 'ETH': 70, 'FIJ': 71, 'FLK': 72, 'FRA': 73,
            'FRO': 74, 'FSM': 75, 'GAB': 76, 'GAM': 77, 'GBR': 78, 'GEO': 79, 'GER': 80, 'GGY': 81,
            'GHA': 82, 'GIB': 83, 'GLP': 84, 'GNB': 85, 'GRE': 86, 'GRL': 87, 'GRN': 88, 'GUA': 89,
            'GUF': 90, 'GUI': 91, 'GUM': 92, 'GUY': 93, 'HAI': 94, 'HKG': 95, 'HMD': 96, 'HON': 97,
            'HUN': 98, 'IDN': 99, 'IMN': 100, 'IND': 101, 'IOT': 102, 'IRL': 103, 'IRN': 104, 'IRQ': 105,
            'ISL': 106, 'ISR': 107, 'ITA': 108, 'JAM': 109, 'JEY': 110, 'JOR': 111, 'JPN': 112, 'KAZ': 113,
            'KEN': 114, 'KGZ': 115, 'KIR': 116, 'KNA': 117, 'KOR': 118, 'KSA': 119, 'KUW': 120, 'KVX': 121,
            'LAO': 122, 'LBN': 123, 'LBR': 124, 'LBY': 125, 'LCA': 126, 'LES': 127, 'LIE': 128, 'LKA': 129,
            'LUX': 130, 'MAC': 131, 'MAD': 132, 'MAF': 133, 'MAR': 134, 'MAS': 135, 'MDA': 136, 'MDV': 137,
            'MEX': 138, 'MHL': 139, 'MKD': 140, 'MLI': 141, 'MLT': 142, 'MNG': 143, 'MNP': 144, 'MON': 145,
            'MOZ': 146, 'MRI': 147, 'MSR': 148, 'MTN': 149, 'MTQ': 150, 'MWI': 151, 'MYA': 152, 'MYT': 153,
            'NAM': 154, 'NCA': 155, 'NCL': 156, 'NEP': 157, 'NFK': 158, 'NIG': 159, 'NIR': 160, 'NIU': 161,
            'NLD': 162, 'NOR': 163, 'NRU': 164, 'NZL': 165, 'OMA': 166, 'PAK': 167, 'PAN': 168, 'PAR': 169,
            'PCN': 170, 'PER': 171, 'PHI': 172, 'PLE': 173, 'PLW': 174, 'PNG': 175, 'POL': 176, 'POR': 177,
            'PRK': 178, 'PUR': 179, 'QAT': 180, 'REU': 181, 'ROU': 182, 'RSA': 183, 'RUS': 184, 'RWA': 185,
            'SAM': 186, 'SCO': 187, 'SDN': 188, 'SEN': 189, 'SEY': 190, 'SGS': 191, 'SHN': 192, 'SIN': 193,
            'SJM': 194, 'SLE': 195, 'SLV': 196, 'SMR': 197, 'SOL': 198, 'SOM': 199, 'SPM': 200, 'SRB': 201,
            'SSD': 202, 'STP': 203, 'SUI': 204, 'SUR': 205, 'SWZ': 206, 'SXM': 207, 'SYR': 208, 'TAH': 209,
            'TAN': 210, 'TCA': 211, 'TGA': 212, 'THA': 213, 'TJK': 214, 'TKL': 215, 'TKM': 216, 'TLS': 217,
            'TOG': 218, 'TRI': 219, 'TUN': 220, 'TUR': 221, 'TUV': 222, 'TWN': 223, 'UAE': 224, 'UGA': 225,
            'UKR': 226, 'UMI': 227, 'URU': 228, 'USA': 229, 'UZB': 230, 'VAN': 231, 'VAT': 232, 'VEN': 233,
            'VGB': 234, 'VIE': 235, 'VIN': 236, 'VIR': 237, 'WAL': 238, 'WLF': 239, 'YEM': 240, 'ZAM': 241,
            'ZIM': 242, 'EUR': 243
        }

        if reverse:
            # Reverse lookup: Find region code by ID
            for code, id_value in region_map.items():
                if id_value == region_id:
                    return code
            return None
        else:
            # Forward lookup: Find region ID by code
            return region_map.get(region, 0)

    async def unit3d_distributor_ids(self, distributor, reverse=False, distributor_id=None):
        distributor_map = {
            '01 DISTRIBUTION': 1, '100 DESTINATIONS TRAVEL FILM': 2, '101 FILMS': 3, '1FILMS': 4, '2 ENTERTAIN VIDEO': 5, '20TH CENTURY FOX': 6, '2L': 7, '3D CONTENT HUB': 8, '3D MEDIA': 9, '3L FILM': 10, '4DIGITAL': 11, '4DVD': 12, '4K ULTRA HD MOVIES': 13, '4K UHD': 13, '8-FILMS': 14, '84 ENTERTAINMENT': 15, '88 FILMS': 16, '@ANIME': 17, 'ANIME': 17, 'A CONTRACORRIENTE': 18, 'A CONTRACORRIENTE FILMS': 19, 'A&E HOME VIDEO': 20, 'A&E': 20, 'A&M RECORDS': 21, 'A+E NETWORKS': 22, 'A+R': 23, 'A-FILM': 24, 'AAA': 25, 'AB VIDÉO': 26, 'AB VIDEO': 26, 'ABC - (AUSTRALIAN BROADCASTING CORPORATION)': 27, 'ABC': 27, 'ABKCO': 28, 'ABSOLUT MEDIEN': 29, 'ABSOLUTE': 30, 'ACCENT FILM ENTERTAINMENT': 31, 'ACCENTUS': 32, 'ACORN MEDIA': 33, 'AD VITAM': 34, 'ADA': 35, 'ADITYA VIDEOS': 36, 'ADSO FILMS': 37, 'AFM RECORDS': 38, 'AGFA': 39, 'AIX RECORDS': 40, 'ALAMODE FILM': 41, 'ALBA RECORDS': 42, 'ALBANY RECORDS': 43, 'ALBATROS': 44, 'ALCHEMY': 45, 'ALIVE': 46, 'ALL ANIME': 47, 'ALL INTERACTIVE ENTERTAINMENT': 48, 'ALLEGRO': 49, 'ALLIANCE': 50, 'ALPHA MUSIC': 51, 'ALTERDYSTRYBUCJA': 52, 'ALTERED INNOCENCE': 53, 'ALTITUDE FILM DISTRIBUTION': 54, 'ALUCARD RECORDS': 55, 'AMAZING D.C.': 56, 'AMAZING DC': 56, 'AMMO CONTENT': 57, 'AMUSE SOFT ENTERTAINMENT': 58, 'ANCONNECT': 59, 'ANEC': 60, 'ANIMATSU': 61, 'ANIME HOUSE': 62, 'ANIME LTD': 63, 'ANIME WORKS': 64, 'ANIMEIGO': 65, 'ANIPLEX': 66, 'ANOLIS ENTERTAINMENT': 67, 'ANOTHER WORLD ENTERTAINMENT': 68, 'AP INTERNATIONAL': 69, 'APPLE': 70, 'ARA MEDIA': 71, 'ARBELOS': 72, 'ARC ENTERTAINMENT': 73, 'ARP SÉLECTION': 74, 'ARP SELECTION': 74, 'ARROW': 75, 'ART SERVICE': 76, 'ART VISION': 77, 'ARTE ÉDITIONS': 78, 'ARTE EDITIONS': 78, 'ARTE VIDÉO': 79, 'ARTE VIDEO': 79, 'ARTHAUS MUSIK': 80, 'ARTIFICIAL EYE': 81, 'ARTSPLOITATION FILMS': 82, 'ARTUS FILMS': 83, 'ASCOT ELITE HOME ENTERTAINMENT': 84, 'ASIA VIDEO': 85, 'ASMIK ACE': 86, 'ASTRO RECORDS & FILMWORKS': 87, 'ASYLUM': 88, 'ATLANTIC FILM': 89, 'ATLANTIC RECORDS': 90, 'ATLAS FILM': 91, 'AUDIO VISUAL ENTERTAINMENT': 92, 'AURO-3D CREATIVE LABEL': 93, 'AURUM': 94, 'AV VISIONEN': 95, 'AV-JET': 96, 'AVALON': 97, 'AVENTI': 98, 'AVEX TRAX': 99, 'AXIOM': 100, 'AXIS RECORDS': 101, 'AYNGARAN': 102, 'BAC FILMS': 103, 'BACH FILMS': 104, 'BANDAI VISUAL': 105, 'BARCLAY': 106, 'BBC': 107, 'BRITISH BROADCASTING CORPORATION': 107, 'BBI FILMS': 108, 'BBI': 108, 'BCI HOME ENTERTAINMENT': 109, 'BEGGARS BANQUET': 110, 'BEL AIR CLASSIQUES': 111, 'BELGA FILMS': 112, 'BELVEDERE': 113, 'BENELUX FILM DISTRIBUTORS': 114, 'BENNETT-WATT MEDIA': 115, 'BERLIN CLASSICS': 116, 'BERLINER PHILHARMONIKER RECORDINGS': 117, 'BEST ENTERTAINMENT': 118, 'BEYOND HOME ENTERTAINMENT': 119, 'BFI VIDEO': 120, 'BFI': 120, 'BRITISH FILM INSTITUTE': 120, 'BFS ENTERTAINMENT': 121, 'BFS': 121, 'BHAVANI': 122, 'BIBER RECORDS': 123, 'BIG HOME VIDEO': 124, 'BILDSTÖRUNG': 125, 'BILDSTORUNG': 125, 'BILL ZEBUB': 126, 'BIRNENBLATT': 127, 'BIT WEL': 128, 'BLACK BOX': 129, 'BLACK HILL PICTURES': 130, 'BLACK HILL': 130, 'BLACK HOLE RECORDINGS': 131, 'BLACK HOLE': 131, 'BLAQOUT': 132, 'BLAUFIELD MUSIC': 133, 'BLAUFIELD': 133, 'BLOCKBUSTER ENTERTAINMENT': 134, 'BLOCKBUSTER': 134, 'BLU PHASE MEDIA': 135, 'BLU-RAY ONLY': 136, 'BLU-RAY': 136, 'BLURAY ONLY': 136, 'BLURAY': 136, 'BLUE GENTIAN RECORDS': 137, 'BLUE KINO': 138, 'BLUE UNDERGROUND': 139, 'BMG/ARISTA': 140, 'BMG': 140, 'BMGARISTA': 140, 'BMG ARISTA': 140, 'ARISTA':
            140, 'ARISTA/BMG': 140, 'ARISTABMG': 140, 'ARISTA BMG': 140, 'BONTON FILM': 141, 'BONTON': 141, 'BOOMERANG PICTURES': 142, 'BOOMERANG': 142, 'BQHL ÉDITIONS': 143, 'BQHL EDITIONS': 143, 'BQHL': 143, 'BREAKING GLASS': 144, 'BRIDGESTONE': 145, 'BRINK': 146, 'BROAD GREEN PICTURES': 147, 'BROAD GREEN': 147, 'BUSCH MEDIA GROUP': 148, 'BUSCH': 148, 'C MAJOR': 149, 'C.B.S.': 150, 'CAICHANG': 151, 'CALIFÓRNIA FILMES': 152, 'CALIFORNIA FILMES': 152, 'CALIFORNIA': 152, 'CAMEO': 153, 'CAMERA OBSCURA': 154, 'CAMERATA': 155, 'CAMP MOTION PICTURES': 156, 'CAMP MOTION': 156, 'CAPELIGHT PICTURES': 157, 'CAPELIGHT': 157, 'CAPITOL': 159, 'CAPITOL RECORDS': 159, 'CAPRICCI': 160, 'CARGO RECORDS': 161, 'CARLOTTA FILMS': 162, 'CARLOTTA': 162, 'CARLOTA': 162, 'CARMEN FILM': 163, 'CASCADE': 164, 'CATCHPLAY': 165, 'CAULDRON FILMS': 166, 'CAULDRON': 166, 'CBS TELEVISION STUDIOS': 167, 'CBS': 167, 'CCTV': 168, 'CCV ENTERTAINMENT': 169, 'CCV': 169, 'CD BABY': 170, 'CD LAND': 171, 'CECCHI GORI': 172, 'CENTURY MEDIA': 173, 'CHUAN XUN SHI DAI MULTIMEDIA': 174, 'CINE-ASIA': 175, 'CINÉART': 176, 'CINEART': 176, 'CINEDIGM': 177, 'CINEFIL IMAGICA': 178, 'CINEMA EPOCH': 179, 'CINEMA GUILD': 180, 'CINEMA LIBRE STUDIOS': 181, 'CINEMA MONDO': 182, 'CINEMATIC VISION': 183, 'CINEPLOIT RECORDS': 184, 'CINESTRANGE EXTREME': 185, 'CITEL VIDEO': 186, 'CITEL': 186, 'CJ ENTERTAINMENT': 187, 'CJ': 187, 'CLASSIC MEDIA': 188, 'CLASSICFLIX': 189, 'CLASSICLINE': 190, 'CLAUDIO RECORDS': 191, 'CLEAR VISION': 192, 'CLEOPATRA': 193, 'CLOSE UP': 194, 'CMS MEDIA LIMITED': 195, 'CMV LASERVISION': 196, 'CN ENTERTAINMENT': 197, 'CODE RED': 198, 'COHEN MEDIA GROUP': 199, 'COHEN': 199, 'COIN DE MIRE CINÉMA': 200, 'COIN DE MIRE CINEMA': 200, 'COLOSSEO FILM': 201, 'COLUMBIA': 203, 'COLUMBIA PICTURES': 203, 'COLUMBIA/TRI-STAR': 204, 'TRI-STAR': 204, 'COMMERCIAL MARKETING': 205, 'CONCORD MUSIC GROUP': 206, 'CONCORDE VIDEO': 207, 'CONDOR': 208, 'CONSTANTIN FILM': 209, 'CONSTANTIN': 209, 'CONSTANTINO FILMES': 210, 'CONSTANTINO': 210, 'CONSTRUCTIVE MEDIA SERVICE': 211, 'CONSTRUCTIVE': 211, 'CONTENT ZONE': 212, 'CONTENTS GATE': 213, 'COQUEIRO VERDE': 214, 'CORNERSTONE MEDIA': 215, 'CORNERSTONE': 215, 'CP DIGITAL': 216, 'CREST MOVIES': 217, 'CRITERION': 218, 'CRITERION COLLECTION':
            218, 'CC': 218, 'CRYSTAL CLASSICS': 219, 'CULT EPICS': 220, 'CULT FILMS': 221, 'CULT VIDEO': 222, 'CURZON FILM WORLD': 223, 'D FILMS': 224, "D'AILLY COMPANY": 225, 'DAILLY COMPANY': 225, 'D AILLY COMPANY': 225, "D'AILLY": 225, 'DAILLY': 225, 'D AILLY': 225, 'DA CAPO': 226, 'DA MUSIC': 227, "DALL'ANGELO PICTURES": 228, 'DALLANGELO PICTURES': 228, "DALL'ANGELO": 228, 'DALL ANGELO PICTURES': 228, 'DALL ANGELO': 228, 'DAREDO': 229, 'DARK FORCE ENTERTAINMENT': 230, 'DARK FORCE': 230, 'DARK SIDE RELEASING': 231, 'DARK SIDE': 231, 'DAZZLER MEDIA': 232, 'DAZZLER': 232, 'DCM PICTURES': 233, 'DCM': 233, 'DEAPLANETA': 234, 'DECCA': 235, 'DEEPJOY': 236, 'DEFIANT SCREEN ENTERTAINMENT': 237, 'DEFIANT SCREEN': 237, 'DEFIANT': 237, 'DELOS': 238, 'DELPHIAN RECORDS': 239, 'DELPHIAN': 239, 'DELTA MUSIC & ENTERTAINMENT': 240, 'DELTA MUSIC AND ENTERTAINMENT': 240, 'DELTA MUSIC ENTERTAINMENT': 240, 'DELTA MUSIC': 240, 'DELTAMAC CO. LTD.': 241, 'DELTAMAC CO LTD': 241, 'DELTAMAC CO': 241, 'DELTAMAC': 241, 'DEMAND MEDIA': 242, 'DEMAND': 242, 'DEP': 243, 'DEUTSCHE GRAMMOPHON': 244, 'DFW': 245, 'DGM': 246, 'DIAPHANA': 247, 'DIGIDREAMS STUDIOS': 248, 'DIGIDREAMS': 248, 'DIGITAL ENVIRONMENTS': 249, 'DIGITAL': 249, 'DISCOTEK MEDIA': 250, 'DISCOVERY CHANNEL': 251, 'DISCOVERY': 251, 'DISK KINO': 252, 'DISNEY / BUENA VISTA': 253, 'DISNEY': 253, 'BUENA VISTA': 253, 'DISNEY BUENA VISTA': 253, 'DISTRIBUTION SELECT': 254, 'DIVISA': 255, 'DNC ENTERTAINMENT': 256, 'DNC': 256, 'DOGWOOF': 257, 'DOLMEN HOME VIDEO': 258, 'DOLMEN': 258, 'DONAU FILM': 259, 'DONAU': 259, 'DORADO FILMS': 260, 'DORADO': 260, 'DRAFTHOUSE FILMS': 261, 'DRAFTHOUSE': 261, 'DRAGON FILM ENTERTAINMENT': 262, 'DRAGON ENTERTAINMENT': 262, 'DRAGON FILM': 262, 'DRAGON': 262, 'DREAMWORKS': 263, 'DRIVE ON RECORDS': 264, 'DRIVE ON': 264, 'DRIVE-ON': 264, 'DRIVEON': 264, 'DS MEDIA': 265, 'DTP ENTERTAINMENT AG': 266, 'DTP ENTERTAINMENT': 266, 'DTP AG': 266, 'DTP': 266, 'DTS ENTERTAINMENT': 267, 'DTS': 267, 'DUKE MARKETING': 268, 'DUKE VIDEO DISTRIBUTION': 269, 'DUKE': 269, 'DUTCH FILMWORKS': 270, 'DUTCH': 270, 'DVD INTERNATIONAL': 271, 'DVD': 271, 'DYBEX': 272, 'DYNAMIC': 273, 'DYNIT': 274, 'E1 ENTERTAINMENT': 275, 'E1': 275, 'EAGLE ENTERTAINMENT': 276, 'EAGLE HOME ENTERTAINMENT PVT.LTD.':
            277, 'EAGLE HOME ENTERTAINMENT PVTLTD': 277, 'EAGLE HOME ENTERTAINMENT PVT LTD': 277, 'EAGLE HOME ENTERTAINMENT': 277, 'EAGLE PICTURES': 278, 'EAGLE ROCK ENTERTAINMENT': 279, 'EAGLE ROCK': 279, 'EAGLE VISION MEDIA': 280, 'EAGLE VISION': 280, 'EARMUSIC': 281, 'EARTH ENTERTAINMENT': 282, 'EARTH': 282, 'ECHO BRIDGE ENTERTAINMENT': 283, 'ECHO BRIDGE': 283, 'EDEL GERMANY GMBH': 284, 'EDEL GERMANY': 284, 'EDEL RECORDS': 285, 'EDITION TONFILM': 286, 'EDITIONS MONTPARNASSE': 287, 'EDKO FILMS LTD.': 288, 'EDKO FILMS LTD': 288, 'EDKO FILMS': 288, 'EDKO': 288, "EIN'S M&M CO": 289, 'EINS M&M CO': 289, "EIN'S M&M": 289, 'EINS M&M': 289, 'ELEA-MEDIA': 290, 'ELEA MEDIA': 290, 'ELEA': 290, 'ELECTRIC PICTURE': 291, 'ELECTRIC': 291, 'ELEPHANT FILMS': 292, 'ELEPHANT': 292, 'ELEVATION': 293, 'EMI': 294, 'EMON': 295, 'EMS': 296, 'EMYLIA': 297, 'ENE MEDIA': 298, 'ENE': 298, 'ENTERTAINMENT IN VIDEO': 299, 'ENTERTAINMENT IN': 299, 'ENTERTAINMENT ONE': 300, 'ENTERTAINMENT ONE FILMS CANADA INC.': 301, 'ENTERTAINMENT ONE FILMS CANADA INC': 301, 'ENTERTAINMENT ONE FILMS CANADA': 301, 'ENTERTAINMENT ONE CANADA INC': 301,
            'ENTERTAINMENT ONE CANADA': 301, 'ENTERTAINMENTONE': 302, 'EONE': 303, 'EOS': 304, 'EPIC PICTURES': 305, 'EPIC': 305, 'EPIC RECORDS': 306, 'ERATO': 307, 'EROS': 308, 'ESC EDITIONS': 309, 'ESCAPI MEDIA BV': 310, 'ESOTERIC RECORDINGS': 311, 'ESPN FILMS': 312, 'EUREKA ENTERTAINMENT': 313, 'EUREKA': 313, 'EURO PICTURES': 314, 'EURO VIDEO': 315, 'EUROARTS': 316, 'EUROPA FILMES': 317, 'EUROPA': 317, 'EUROPACORP': 318, 'EUROZOOM': 319, 'EXCEL': 320, 'EXPLOSIVE MEDIA': 321, 'EXPLOSIVE': 321, 'EXTRALUCID FILMS': 322, 'EXTRALUCID': 322, 'EYE SEE MOVIES': 323, 'EYE SEE': 323, 'EYK MEDIA': 324, 'EYK': 324, 'FABULOUS FILMS': 325, 'FABULOUS': 325, 'FACTORIS FILMS': 326, 'FACTORIS': 326, 'FARAO RECORDS': 327, 'FARBFILM HOME ENTERTAINMENT': 328, 'FARBFILM ENTERTAINMENT': 328, 'FARBFILM HOME': 328, 'FARBFILM': 328, 'FEELGOOD ENTERTAINMENT': 329, 'FEELGOOD': 329, 'FERNSEHJUWELEN': 330, 'FILM CHEST': 331, 'FILM MEDIA': 332, 'FILM MOVEMENT': 333, 'FILM4': 334, 'FILMART': 335, 'FILMAURO': 336, 'FILMAX': 337, 'FILMCONFECT HOME ENTERTAINMENT': 338, 'FILMCONFECT ENTERTAINMENT': 338, 'FILMCONFECT HOME': 338, 'FILMCONFECT': 338, 'FILMEDIA': 339, 'FILMJUWELEN': 340, 'FILMOTEKA NARODAWA': 341, 'FILMRISE': 342, 'FINAL CUT ENTERTAINMENT': 343, 'FINAL CUT': 343, 'FIREHOUSE 12 RECORDS': 344, 'FIREHOUSE 12': 344, 'FIRST INTERNATIONAL PRODUCTION': 345, 'FIRST INTERNATIONAL': 345, 'FIRST LOOK STUDIOS': 346, 'FIRST LOOK': 346, 'FLAGMAN TRADE': 347, 'FLASHSTAR FILMES': 348, 'FLASHSTAR': 348, 'FLICKER ALLEY': 349, 'FNC ADD CULTURE': 350, 'FOCUS FILMES': 351, 'FOCUS': 351, 'FOKUS MEDIA': 352, 'FOKUSA': 352, 'FOX PATHE EUROPA': 353, 'FOX PATHE': 353, 'FOX EUROPA': 353, 'FOX/MGM': 354, 'FOX MGM': 354, 'MGM': 354, 'MGM/FOX': 354, 'FOX': 354, 'FPE': 355, 'FRANCE TÉLÉVISIONS DISTRIBUTION': 356, 'FRANCE TELEVISIONS DISTRIBUTION': 356, 'FRANCE TELEVISIONS': 356, 'FRANCE': 356, 'FREE DOLPHIN ENTERTAINMENT': 357, 'FREE DOLPHIN': 357, 'FREESTYLE DIGITAL MEDIA': 358, 'FREESTYLE DIGITAL': 358, 'FREESTYLE': 358, 'FREMANTLE HOME ENTERTAINMENT': 359, 'FREMANTLE ENTERTAINMENT': 359, 'FREMANTLE HOME': 359, 'FREMANTL': 359, 'FRENETIC FILMS': 360, 'FRENETIC': 360, 'FRONTIER WORKS': 361, 'FRONTIER': 361, 'FRONTIERS MUSIC': 362, 'FRONTIERS RECORDS': 363, 'FS FILM OY': 364, 'FS FILM':
            364, 'FULL MOON FEATURES': 365, 'FULL MOON': 365, 'FUN CITY EDITIONS': 366, 'FUN CITY': 366, 'FUNIMATION ENTERTAINMENT': 367, 'FUNIMATION': 367, 'FUSION': 368, 'FUTUREFILM': 369, 'G2 PICTURES': 370, 'G2': 370, 'GAGA COMMUNICATIONS': 371, 'GAGA': 371, 'GAIAM': 372, 'GALAPAGOS': 373, 'GAMMA HOME ENTERTAINMENT': 374, 'GAMMA ENTERTAINMENT': 374, 'GAMMA HOME': 374, 'GAMMA': 374, 'GARAGEHOUSE PICTURES': 375, 'GARAGEHOUSE': 375, 'GARAGEPLAY (車庫娛樂)': 376, '車庫娛樂': 376, 'GARAGEPLAY (Che Ku Yu Le )': 376, 'GARAGEPLAY': 376, 'Che Ku Yu Le': 376, 'GAUMONT': 377, 'GEFFEN': 378, 'GENEON ENTERTAINMENT': 379, 'GENEON': 379, 'GENEON UNIVERSAL ENTERTAINMENT': 380, 'GENERAL VIDEO RECORDING': 381, 'GLASS DOLL FILMS': 382, 'GLASS DOLL': 382, 'GLOBE MUSIC MEDIA': 383, 'GLOBE MUSIC': 383, 'GLOBE MEDIA': 383, 'GLOBE': 383, 'GO ENTERTAIN': 384, 'GO': 384, 'GOLDEN HARVEST': 385, 'GOOD!MOVIES': 386,
            'GOOD! MOVIES': 386, 'GOOD MOVIES': 386, 'GRAPEVINE VIDEO': 387, 'GRAPEVINE': 387, 'GRASSHOPPER FILM': 388, 'GRASSHOPPER FILMS': 388, 'GRASSHOPPER': 388, 'GRAVITAS VENTURES': 389, 'GRAVITAS': 389, 'GREAT MOVIES': 390, 'GREAT': 390,
            'GREEN APPLE ENTERTAINMENT': 391, 'GREEN ENTERTAINMENT': 391, 'GREEN APPLE': 391, 'GREEN': 391, 'GREENNARAE MEDIA': 392, 'GREENNARAE': 392, 'GRINDHOUSE RELEASING': 393, 'GRINDHOUSE': 393, 'GRIND HOUSE': 393, 'GRYPHON ENTERTAINMENT': 394, 'GRYPHON': 394, 'GUNPOWDER & SKY': 395, 'GUNPOWDER AND SKY': 395, 'GUNPOWDER SKY': 395, 'GUNPOWDER + SKY': 395, 'GUNPOWDER': 395, 'HANABEE ENTERTAINMENT': 396, 'HANABEE': 396, 'HANNOVER HOUSE': 397, 'HANNOVER': 397, 'HANSESOUND': 398, 'HANSE SOUND': 398, 'HANSE': 398, 'HAPPINET': 399, 'HARMONIA MUNDI': 400, 'HARMONIA': 400, 'HBO': 401, 'HDC': 402, 'HEC': 403, 'HELL & BACK RECORDINGS': 404, 'HELL AND BACK RECORDINGS': 404, 'HELL & BACK': 404, 'HELL AND BACK': 404, "HEN'S TOOTH VIDEO": 405, 'HENS TOOTH VIDEO': 405, "HEN'S TOOTH": 405, 'HENS TOOTH': 405, 'HIGH FLIERS': 406, 'HIGHLIGHT': 407, 'HILLSONG': 408, 'HISTORY CHANNEL': 409, 'HISTORY': 409, 'HK VIDÉO': 410, 'HK VIDEO': 410, 'HK': 410, 'HMH HAMBURGER MEDIEN HAUS': 411, 'HAMBURGER MEDIEN HAUS': 411, 'HMH HAMBURGER MEDIEN': 411, 'HMH HAMBURGER': 411, 'HMH': 411, 'HOLLYWOOD CLASSIC ENTERTAINMENT': 412, 'HOLLYWOOD CLASSIC': 412, 'HOLLYWOOD PICTURES': 413, 'HOLLYWOOD': 413, 'HOPSCOTCH ENTERTAINMENT': 414, 'HOPSCOTCH': 414, 'HPM': 415, 'HÄNNSLER CLASSIC': 416, 'HANNSLER CLASSIC': 416, 'HANNSLER': 416, 'I-CATCHER': 417, 'I CATCHER': 417, 'ICATCHER': 417, 'I-ON NEW MEDIA': 418, 'I ON NEW MEDIA': 418, 'ION NEW MEDIA': 418, 'ION MEDIA': 418, 'I-ON': 418, 'ION': 418, 'IAN PRODUCTIONS': 419, 'IAN': 419, 'ICESTORM': 420, 'ICON FILM DISTRIBUTION': 421, 'ICON DISTRIBUTION': 421, 'ICON FILM': 421, 'ICON': 421, 'IDEALE AUDIENCE': 422, 'IDEALE': 422, 'IFC FILMS': 423, 'IFC': 423, 'IFILM': 424, 'ILLUSIONS UNLTD.': 425, 'ILLUSIONS UNLTD': 425, 'ILLUSIONS': 425, 'IMAGE ENTERTAINMENT': 426, 'IMAGE': 426,
            'IMAGEM FILMES': 427, 'IMAGEM': 427, 'IMOVISION': 428, 'IMPERIAL CINEPIX': 429, 'IMPRINT': 430, 'IMPULS HOME ENTERTAINMENT': 431, 'IMPULS ENTERTAINMENT': 431, 'IMPULS HOME': 431, 'IMPULS': 431, 'IN-AKUSTIK': 432, 'IN AKUSTIK': 432, 'INAKUSTIK': 432, 'INCEPTION MEDIA GROUP': 433, 'INCEPTION MEDIA': 433, 'INCEPTION GROUP': 433, 'INCEPTION': 433, 'INDEPENDENT': 434, 'INDICAN': 435, 'INDIE RIGHTS': 436, 'INDIE': 436, 'INDIGO': 437, 'INFO': 438, 'INJOINGAN': 439, 'INKED PICTURES': 440, 'INKED': 440, 'INSIDE OUT MUSIC': 441, 'INSIDE MUSIC': 441, 'INSIDE OUT': 441, 'INSIDE': 441, 'INTERCOM': 442, 'INTERCONTINENTAL VIDEO': 443, 'INTERCONTINENTAL': 443, 'INTERGROOVE': 444,
            'INTERSCOPE': 445, 'INVINCIBLE PICTURES': 446, 'INVINCIBLE': 446, 'ISLAND/MERCURY': 447, 'ISLAND MERCURY': 447, 'ISLANDMERCURY': 447, 'ISLAND & MERCURY': 447, 'ISLAND AND MERCURY': 447, 'ISLAND': 447, 'ITN': 448, 'ITV DVD': 449, 'ITV': 449, 'IVC': 450, 'IVE ENTERTAINMENT': 451, 'IVE': 451, 'J&R ADVENTURES': 452, 'J&R': 452, 'JR': 452, 'JAKOB': 453, 'JONU MEDIA': 454, 'JONU': 454, 'JRB PRODUCTIONS': 455, 'JRB': 455, 'JUST BRIDGE ENTERTAINMENT': 456, 'JUST BRIDGE': 456, 'JUST ENTERTAINMENT': 456, 'JUST': 456, 'KABOOM ENTERTAINMENT': 457, 'KABOOM': 457, 'KADOKAWA ENTERTAINMENT': 458, 'KADOKAWA': 458, 'KAIROS': 459, 'KALEIDOSCOPE ENTERTAINMENT': 460, 'KALEIDOSCOPE': 460, 'KAM & RONSON ENTERPRISES': 461, 'KAM & RONSON': 461, 'KAM&RONSON ENTERPRISES': 461, 'KAM&RONSON': 461, 'KAM AND RONSON ENTERPRISES': 461, 'KAM AND RONSON': 461, 'KANA HOME VIDEO': 462, 'KARMA FILMS': 463, 'KARMA': 463, 'KATZENBERGER': 464, 'KAZE': 465, 'KBS MEDIA': 466, 'KBS': 466, 'KD MEDIA': 467, 'KD': 467, 'KING MEDIA': 468, 'KING': 468, 'KING RECORDS': 469, 'KINO LORBER': 470, 'KINO': 470, 'KINO SWIAT': 471, 'KINOKUNIYA': 472, 'KINOWELT HOME ENTERTAINMENT/DVD': 473, 'KINOWELT HOME ENTERTAINMENT': 473, 'KINOWELT ENTERTAINMENT': 473, 'KINOWELT HOME DVD': 473, 'KINOWELT ENTERTAINMENT/DVD': 473, 'KINOWELT DVD': 473, 'KINOWELT': 473, 'KIT PARKER FILMS': 474, 'KIT PARKER': 474, 'KITTY MEDIA': 475, 'KNM HOME ENTERTAINMENT': 476, 'KNM ENTERTAINMENT': 476, 'KNM HOME': 476, 'KNM': 476, 'KOBA FILMS': 477, 'KOBA': 477, 'KOCH ENTERTAINMENT': 478, 'KOCH MEDIA': 479, 'KOCH': 479, 'KRAKEN RELEASING': 480, 'KRAKEN': 480, 'KSCOPE': 481, 'KSM': 482, 'KULTUR': 483, "L'ATELIER D'IMAGES": 484, "LATELIER D'IMAGES": 484, "L'ATELIER DIMAGES": 484, 'LATELIER DIMAGES': 484, "L ATELIER D'IMAGES": 484, "L'ATELIER D IMAGES": 484,
            'L ATELIER D IMAGES': 484, "L'ATELIER": 484, 'L ATELIER': 484, 'LATELIER': 484, 'LA AVENTURA AUDIOVISUAL': 485, 'LA AVENTURA': 485, 'LACE GROUP': 486, 'LACE': 486, 'LASER PARADISE': 487, 'LAYONS': 488, 'LCJ EDITIONS': 489, 'LCJ': 489, 'LE CHAT QUI FUME': 490, 'LE PACTE': 491, 'LEDICK FILMHANDEL': 492, 'LEGEND': 493, 'LEOMARK STUDIOS': 494, 'LEOMARK': 494, 'LEONINE FILMS': 495, 'LEONINE': 495, 'LICHTUNG MEDIA LTD': 496, 'LICHTUNG LTD': 496, 'LICHTUNG MEDIA LTD.': 496, 'LICHTUNG LTD.': 496, 'LICHTUNG MEDIA': 496, 'LICHTUNG': 496, 'LIGHTHOUSE HOME ENTERTAINMENT': 497, 'LIGHTHOUSE ENTERTAINMENT': 497, 'LIGHTHOUSE HOME': 497, 'LIGHTHOUSE': 497, 'LIGHTYEAR': 498, 'LIONSGATE FILMS': 499, 'LIONSGATE': 499, 'LIZARD CINEMA TRADE': 500, 'LLAMENTOL': 501, 'LOBSTER FILMS': 502, 'LOBSTER': 502, 'LOGON': 503, 'LORBER FILMS': 504, 'LORBER': 504, 'LOS BANDITOS FILMS': 505, 'LOS BANDITOS': 505, 'LOUD & PROUD RECORDS': 506, 'LOUD AND PROUD RECORDS': 506, 'LOUD & PROUD': 506, 'LOUD AND PROUD': 506, 'LSO LIVE': 507, 'LUCASFILM': 508, 'LUCKY RED': 509, 'LUMIÈRE HOME ENTERTAINMENT': 510, 'LUMIERE HOME ENTERTAINMENT': 510, 'LUMIERE ENTERTAINMENT': 510, 'LUMIERE HOME': 510, 'LUMIERE': 510, 'M6 VIDEO': 511, 'M6': 511, 'MAD DIMENSION': 512, 'MADMAN ENTERTAINMENT': 513, 'MADMAN': 513, 'MAGIC BOX': 514, 'MAGIC PLAY': 515, 'MAGNA HOME ENTERTAINMENT': 516, 'MAGNA ENTERTAINMENT': 516, 'MAGNA HOME': 516, 'MAGNA': 516, 'MAGNOLIA PICTURES': 517, 'MAGNOLIA': 517, 'MAIDEN JAPAN': 518, 'MAIDEN': 518, 'MAJENG MEDIA': 519, 'MAJENG': 519, 'MAJESTIC HOME ENTERTAINMENT': 520, 'MAJESTIC ENTERTAINMENT': 520, 'MAJESTIC HOME': 520, 'MAJESTIC': 520, 'MANGA HOME ENTERTAINMENT': 521, 'MANGA ENTERTAINMENT': 521, 'MANGA HOME': 521, 'MANGA': 521, 'MANTA LAB': 522, 'MAPLE STUDIOS': 523, 'MAPLE': 523, 'MARCO POLO PRODUCTION':
            524, 'MARCO POLO': 524, 'MARIINSKY': 525, 'MARVEL STUDIOS': 526, 'MARVEL': 526, 'MASCOT RECORDS': 527, 'MASCOT': 527, 'MASSACRE VIDEO': 528, 'MASSACRE': 528, 'MATCHBOX': 529, 'MATRIX D': 530, 'MAXAM': 531, 'MAYA HOME ENTERTAINMENT': 532, 'MAYA ENTERTAINMENT': 532, 'MAYA HOME': 532, 'MAYAT': 532, 'MDG': 533, 'MEDIA BLASTERS': 534, 'MEDIA FACTORY': 535, 'MEDIA TARGET DISTRIBUTION': 536, 'MEDIA TARGET': 536, 'MEDIAINVISION': 537, 'MEDIATOON': 538, 'MEDIATRES ESTUDIO': 539, 'MEDIATRES STUDIO': 539, 'MEDIATRES': 539, 'MEDICI ARTS': 540, 'MEDICI CLASSICS': 541, 'MEDIUMRARE ENTERTAINMENT': 542, 'MEDIUMRARE': 542, 'MEDUSA': 543, 'MEGASTAR': 544, 'MEI AH': 545, 'MELI MÉDIAS': 546, 'MELI MEDIAS': 546, 'MEMENTO FILMS': 547, 'MEMENTO': 547, 'MENEMSHA FILMS': 548, 'MENEMSHA': 548, 'MERCURY': 549, 'MERCURY STUDIOS': 550, 'MERGE SOFT PRODUCTIONS': 551, 'MERGE PRODUCTIONS': 551, 'MERGE SOFT': 551, 'MERGE': 551, 'METAL BLADE RECORDS': 552, 'METAL BLADE': 552, 'METEOR': 553, 'METRO-GOLDWYN-MAYER': 554, 'METRO GOLDWYN MAYER': 554, 'METROGOLDWYNMAYER': 554, 'METRODOME VIDEO': 555, 'METRODOME': 555, 'METROPOLITAN': 556, 'MFA+':
            557, 'MFA': 557, 'MIG FILMGROUP': 558, 'MIG': 558, 'MILESTONE': 559, 'MILL CREEK ENTERTAINMENT': 560, 'MILL CREEK': 560, 'MILLENNIUM MEDIA': 561, 'MILLENNIUM': 561, 'MIRAGE ENTERTAINMENT': 562, 'MIRAGE': 562, 'MIRAMAX': 563,
            'MISTERIYA ZVUKA': 564, 'MK2': 565, 'MODE RECORDS': 566, 'MODE': 566, 'MOMENTUM PICTURES': 567, 'MONDO HOME ENTERTAINMENT': 568, 'MONDO ENTERTAINMENT': 568, 'MONDO HOME': 568, 'MONDO MACABRO': 569, 'MONGREL MEDIA': 570, 'MONOLIT': 571, 'MONOLITH VIDEO': 572, 'MONOLITH': 572, 'MONSTER PICTURES': 573, 'MONSTER': 573, 'MONTEREY VIDEO': 574, 'MONTEREY': 574, 'MONUMENT RELEASING': 575, 'MONUMENT': 575, 'MORNINGSTAR': 576, 'MORNING STAR': 576, 'MOSERBAER': 577, 'MOVIEMAX': 578, 'MOVINSIDE': 579, 'MPI MEDIA GROUP': 580, 'MPI MEDIA': 580, 'MPI': 580, 'MR. BONGO FILMS': 581, 'MR BONGO FILMS': 581, 'MR BONGO': 581, 'MRG (MERIDIAN)': 582, 'MRG MERIDIAN': 582, 'MRG': 582, 'MERIDIAN': 582, 'MUBI': 583, 'MUG SHOT PRODUCTIONS': 584, 'MUG SHOT': 584, 'MULTIMUSIC': 585, 'MULTI-MUSIC': 585, 'MULTI MUSIC': 585, 'MUSE': 586, 'MUSIC BOX FILMS': 587, 'MUSIC BOX': 587, 'MUSICBOX': 587, 'MUSIC BROKERS': 588, 'MUSIC THEORIES': 589, 'MUSIC VIDEO DISTRIBUTORS': 590, 'MUSIC VIDEO': 590, 'MUSTANG ENTERTAINMENT': 591, 'MUSTANG': 591, 'MVD VISUAL': 592, 'MVD': 592, 'MVD/VSC': 593, 'MVL': 594, 'MVM ENTERTAINMENT': 595, 'MVM': 595, 'MYNDFORM': 596, 'MYSTIC NIGHT PICTURES': 597, 'MYSTIC NIGHT': 597, 'NAMELESS MEDIA': 598, 'NAMELESS': 598, 'NAPALM RECORDS': 599, 'NAPALM': 599, 'NATIONAL ENTERTAINMENT MEDIA': 600, 'NATIONAL ENTERTAINMENT': 600, 'NATIONAL MEDIA': 600, 'NATIONAL FILM ARCHIVE': 601, 'NATIONAL ARCHIVE': 601, 'NATIONAL FILM': 601, 'NATIONAL GEOGRAPHIC': 602, 'NAT GEO TV': 602, 'NAT GEO': 602, 'NGO': 602, 'NAXOS': 603, 'NBCUNIVERSAL ENTERTAINMENT JAPAN': 604, 'NBC UNIVERSAL ENTERTAINMENT JAPAN': 604, 'NBCUNIVERSAL JAPAN': 604, 'NBC UNIVERSAL JAPAN': 604, 'NBC JAPAN': 604, 'NBO ENTERTAINMENT': 605, 'NBO': 605, 'NEOS': 606, 'NETFLIX': 607, 'NETWORK': 608, 'NEW BLOOD': 609, 'NEW DISC': 610, 'NEW KSM': 611, 'NEW LINE CINEMA': 612, 'NEW LINE': 612, 'NEW MOVIE TRADING CO. LTD': 613, 'NEW MOVIE TRADING CO LTD': 613, 'NEW MOVIE TRADING CO': 613, 'NEW MOVIE TRADING': 613, 'NEW WAVE FILMS': 614, 'NEW WAVE': 614, 'NFI': 615,
            'NHK': 616, 'NIPPONART': 617, 'NIS AMERICA': 618, 'NJUTAFILMS': 619, 'NOBLE ENTERTAINMENT': 620, 'NOBLE': 620, 'NORDISK FILM': 621, 'NORDISK': 621, 'NORSK FILM': 622, 'NORSK': 622, 'NORTH AMERICAN MOTION PICTURES': 623, 'NOS AUDIOVISUAIS': 624, 'NOTORIOUS PICTURES': 625, 'NOTORIOUS': 625, 'NOVA MEDIA': 626, 'NOVA': 626, 'NOVA SALES AND DISTRIBUTION': 627, 'NOVA SALES & DISTRIBUTION': 627, 'NSM': 628, 'NSM RECORDS': 629, 'NUCLEAR BLAST': 630, 'NUCLEUS FILMS': 631, 'NUCLEUS': 631, 'OBERLIN MUSIC': 632, 'OBERLIN': 632, 'OBRAS-PRIMAS DO CINEMA': 633, 'OBRAS PRIMAS DO CINEMA': 633, 'OBRASPRIMAS DO CINEMA': 633, 'OBRAS-PRIMAS CINEMA': 633, 'OBRAS PRIMAS CINEMA': 633, 'OBRASPRIMAS CINEMA': 633, 'OBRAS-PRIMAS': 633, 'OBRAS PRIMAS': 633, 'OBRASPRIMAS': 633, 'ODEON': 634, 'OFDB FILMWORKS': 635, 'OFDB': 635, 'OLIVE FILMS': 636, 'OLIVE': 636, 'ONDINE': 637, 'ONSCREEN FILMS': 638, 'ONSCREEN': 638, 'OPENING DISTRIBUTION': 639, 'OPERA AUSTRALIA': 640, 'OPTIMUM HOME ENTERTAINMENT': 641, 'OPTIMUM ENTERTAINMENT': 641, 'OPTIMUM HOME': 641, 'OPTIMUM': 641, 'OPUS ARTE': 642, 'ORANGE STUDIO': 643, 'ORANGE': 643, 'ORLANDO EASTWOOD FILMS': 644, 'ORLANDO FILMS': 644, 'ORLANDO EASTWOOD': 644, 'ORLANDO': 644, 'ORUSTAK PICTURES': 645, 'ORUSTAK': 645, 'OSCILLOSCOPE PICTURES': 646, 'OSCILLOSCOPE': 646, 'OUTPLAY': 647, 'PALISADES TARTAN': 648, 'PAN VISION': 649, 'PANVISION': 649, 'PANAMINT CINEMA': 650, 'PANAMINT': 650, 'PANDASTORM ENTERTAINMENT': 651, 'PANDA STORM ENTERTAINMENT': 651, 'PANDASTORM': 651, 'PANDA STORM': 651, 'PANDORA FILM': 652, 'PANDORA': 652, 'PANEGYRIC': 653, 'PANORAMA': 654, 'PARADE DECK FILMS': 655, 'PARADE DECK': 655, 'PARADISE': 656, 'PARADISO FILMS': 657, 'PARADOX': 658, 'PARAMOUNT PICTURES': 659, 'PARAMOUNT': 659, 'PARIS FILMES': 660, 'PARIS FILMS': 660, 'PARIS': 660, 'PARK CIRCUS': 661, 'PARLOPHONE': 662, 'PASSION RIVER': 663, 'PATHE DISTRIBUTION': 664, 'PATHE': 664, 'PBS': 665, 'PEACE ARCH TRINITY': 666, 'PECCADILLO PICTURES': 667, 'PEPPERMINT': 668, 'PHASE 4 FILMS': 669, 'PHASE 4': 669, 'PHILHARMONIA BAROQUE': 670, 'PICTURE HOUSE ENTERTAINMENT': 671, 'PICTURE ENTERTAINMENT': 671, 'PICTURE HOUSE': 671, 'PICTURE': 671, 'PIDAX': 672, 'PINK FLOYD RECORDS': 673, 'PINK FLOYD': 673, 'PINNACLE FILMS': 674, 'PINNACLE': 674, 'PLAIN': 675, 'PLATFORM ENTERTAINMENT LIMITED': 676, 'PLATFORM ENTERTAINMENT LTD': 676, 'PLATFORM ENTERTAINMENT LTD.': 676, 'PLATFORM ENTERTAINMENT': 676, 'PLATFORM': 676, 'PLAYARTE': 677, 'PLG UK CLASSICS': 678, 'PLG UK':
            678, 'PLG': 678, 'POLYBAND & TOPPIC VIDEO/WVG': 679, 'POLYBAND AND TOPPIC VIDEO/WVG': 679, 'POLYBAND & TOPPIC VIDEO WVG': 679, 'POLYBAND & TOPPIC VIDEO AND WVG': 679, 'POLYBAND & TOPPIC VIDEO & WVG': 679, 'POLYBAND AND TOPPIC VIDEO WVG': 679, 'POLYBAND AND TOPPIC VIDEO AND WVG': 679, 'POLYBAND AND TOPPIC VIDEO & WVG': 679, 'POLYBAND & TOPPIC VIDEO': 679, 'POLYBAND AND TOPPIC VIDEO': 679, 'POLYBAND & TOPPIC': 679, 'POLYBAND AND TOPPIC': 679, 'POLYBAND': 679, 'WVG': 679, 'POLYDOR': 680, 'PONY': 681, 'PONY CANYON': 682, 'POTEMKINE': 683, 'POWERHOUSE FILMS': 684, 'POWERHOUSE': 684, 'POWERSTATIOM': 685, 'PRIDE & JOY': 686, 'PRIDE AND JOY': 686, 'PRINZ MEDIA': 687, 'PRINZ': 687, 'PRIS AUDIOVISUAIS': 688, 'PRO VIDEO': 689, 'PRO-VIDEO': 689, 'PRO-MOTION': 690, 'PRO MOTION': 690, 'PROD. JRB': 691, 'PROD JRB': 691, 'PRODISC': 692, 'PROKINO': 693, 'PROVOGUE RECORDS': 694, 'PROVOGUE': 694, 'PROWARE': 695, 'PULP VIDEO': 696, 'PULP': 696, 'PULSE VIDEO': 697, 'PULSE': 697, 'PURE AUDIO RECORDINGS': 698, 'PURE AUDIO': 698, 'PURE FLIX ENTERTAINMENT': 699, 'PURE FLIX': 699, 'PURE ENTERTAINMENT': 699, 'PYRAMIDE VIDEO': 700, 'PYRAMIDE': 700, 'QUALITY FILMS': 701, 'QUALITY': 701, 'QUARTO VALLEY RECORDS': 702, 'QUARTO VALLEY': 702, 'QUESTAR': 703, 'R SQUARED FILMS': 704, 'R SQUARED': 704, 'RAPID EYE MOVIES': 705, 'RAPID EYE': 705, 'RARO VIDEO': 706, 'RARO': 706, 'RAROVIDEO U.S.': 707, 'RAROVIDEO US': 707, 'RARO VIDEO US': 707, 'RARO VIDEO U.S.': 707, 'RARO U.S.': 707, 'RARO US': 707, 'RAVEN BANNER RELEASING': 708, 'RAVEN BANNER': 708, 'RAVEN': 708, 'RAZOR DIGITAL ENTERTAINMENT': 709, 'RAZOR DIGITAL': 709, 'RCA': 710, 'RCO LIVE': 711, 'RCO': 711, 'RCV': 712, 'REAL GONE MUSIC': 713, 'REAL GONE': 713, 'REANIMEDIA': 714, 'REANI MEDIA': 714, 'REDEMPTION': 715, 'REEL': 716, 'RELIANCE HOME VIDEO & GAMES': 717, 'RELIANCE HOME VIDEO AND GAMES': 717, 'RELIANCE HOME VIDEO': 717, 'RELIANCE VIDEO': 717, 'RELIANCE HOME': 717, 'RELIANCE': 717, 'REM CULTURE': 718, 'REMAIN IN LIGHT': 719, 'REPRISE': 720, 'RESEN': 721, 'RETROMEDIA': 722, 'REVELATION FILMS LTD.': 723, 'REVELATION FILMS LTD': 723, 'REVELATION FILMS': 723, 'REVELATION LTD.': 723, 'REVELATION LTD': 723, 'REVELATION': 723, 'REVOLVER ENTERTAINMENT': 724, 'REVOLVER': 724, 'RHINO MUSIC': 725, 'RHINO': 725, 'RHV': 726, 'RIGHT STUF': 727, 'RIMINI EDITIONS': 728, 'RISING SUN MEDIA': 729, 'RLJ ENTERTAINMENT': 730, 'RLJ': 730, 'ROADRUNNER RECORDS': 731, 'ROADSHOW ENTERTAINMENT': 732, 'ROADSHOW': 732, 'RONE': 733, 'RONIN FLIX': 734, 'ROTANA HOME ENTERTAINMENT': 735, 'ROTANA ENTERTAINMENT': 735, 'ROTANA HOME': 735, 'ROTANA': 735, 'ROUGH TRADE': 736, 'ROUNDER': 737, 'SAFFRON HILL FILMS': 738, 'SAFFRON HILL': 738, 'SAFFRON': 738, 'SAMUEL GOLDWYN FILMS': 739, 'SAMUEL GOLDWYN': 739, 'SAN FRANCISCO SYMPHONY': 740, 'SANDREW METRONOME': 741, 'SAPHRANE': 742, 'SAVOR': 743, 'SCANBOX ENTERTAINMENT': 744, 'SCANBOX': 744, 'SCENIC LABS': 745, 'SCHRÖDERMEDIA': 746, 'SCHRODERMEDIA': 746, 'SCHRODER MEDIA': 746, 'SCORPION RELEASING': 747, 'SCORPION': 747, 'SCREAM TEAM RELEASING': 748, 'SCREAM TEAM': 748, 'SCREEN MEDIA': 749, 'SCREEN': 749, 'SCREENBOUND PICTURES': 750, 'SCREENBOUND': 750, 'SCREENWAVE MEDIA': 751, 'SCREENWAVE': 751, 'SECOND RUN': 752, 'SECOND SIGHT': 753, 'SEEDSMAN GROUP': 754, 'SELECT VIDEO': 755, 'SELECTA VISION': 756, 'SENATOR': 757, 'SENTAI FILMWORKS': 758, 'SENTAI': 758, 'SEVEN7': 759, 'SEVERIN FILMS': 760, 'SEVERIN': 760, 'SEVILLE': 761, 'SEYONS ENTERTAINMENT': 762, 'SEYONS': 762, 'SF STUDIOS': 763, 'SGL ENTERTAINMENT': 764, 'SGL': 764, 'SHAMELESS': 765, 'SHAMROCK MEDIA': 766, 'SHAMROCK': 766, 'SHANGHAI EPIC MUSIC ENTERTAINMENT': 767, 'SHANGHAI EPIC ENTERTAINMENT': 767, 'SHANGHAI EPIC MUSIC': 767, 'SHANGHAI MUSIC ENTERTAINMENT': 767, 'SHANGHAI ENTERTAINMENT': 767, 'SHANGHAI MUSIC': 767, 'SHANGHAI': 767, 'SHEMAROO': 768, 'SHOCHIKU': 769, 'SHOCK': 770, 'SHOGAKU KAN': 771, 'SHOUT FACTORY': 772, 'SHOUT! FACTORY': 772, 'SHOUT': 772, 'SHOUT!': 772, 'SHOWBOX': 773, 'SHOWTIME ENTERTAINMENT': 774, 'SHOWTIME': 774, 'SHRIEK SHOW': 775, 'SHUDDER': 776, 'SIDONIS': 777, 'SIDONIS CALYSTA': 778, 'SIGNAL ONE ENTERTAINMENT': 779, 'SIGNAL ONE': 779, 'SIGNATURE ENTERTAINMENT': 780, 'SIGNATURE': 780, 'SILVER VISION': 781, 'SINISTER FILM': 782, 'SINISTER': 782, 'SIREN VISUAL ENTERTAINMENT': 783, 'SIREN VISUAL': 783, 'SIREN ENTERTAINMENT': 783, 'SIREN': 783, 'SKANI': 784, 'SKY DIGI': 785, 'SLASHER // VIDEO': 786, 'SLASHER / VIDEO': 786, 'SLASHER VIDEO': 786, 'SLASHER': 786, 'SLOVAK FILM INSTITUTE': 787, 'SLOVAK FILM': 787,
            'SFI': 787, 'SM LIFE DESIGN GROUP': 788, 'SMOOTH PICTURES': 789, 'SMOOTH': 789, 'SNAPPER MUSIC': 790, 'SNAPPER': 790, 'SODA PICTURES': 791, 'SODA': 791, 'SONO LUMINUS': 792, 'SONY MUSIC': 793, 'SONY PICTURES': 794, 'SONY': 794, 'SONY PICTURES CLASSICS': 795, 'SONY CLASSICS': 795, 'SOUL MEDIA': 796, 'SOUL': 796, 'SOULFOOD MUSIC DISTRIBUTION': 797, 'SOULFOOD DISTRIBUTION': 797, 'SOULFOOD MUSIC': 797, 'SOULFOOD': 797, 'SOYUZ': 798, 'SPECTRUM': 799,
            'SPENTZOS FILM': 800, 'SPENTZOS': 800, 'SPIRIT ENTERTAINMENT': 801, 'SPIRIT': 801, 'SPIRIT MEDIA GMBH': 802, 'SPIRIT MEDIA': 802, 'SPLENDID ENTERTAINMENT': 803, 'SPLENDID FILM': 804, 'SPO': 805, 'SQUARE ENIX': 806, 'SRI BALAJI VIDEO': 807, 'SRI BALAJI': 807, 'SRI': 807, 'SRI VIDEO': 807, 'SRS CINEMA': 808, 'SRS': 808, 'SSO RECORDINGS': 809, 'SSO': 809, 'ST2 MUSIC': 810, 'ST2': 810, 'STAR MEDIA ENTERTAINMENT': 811, 'STAR ENTERTAINMENT': 811, 'STAR MEDIA': 811, 'STAR': 811, 'STARLIGHT': 812, 'STARZ / ANCHOR BAY': 813, 'STARZ ANCHOR BAY': 813, 'STARZ': 813, 'ANCHOR BAY': 813, 'STER KINEKOR': 814, 'STERLING ENTERTAINMENT': 815, 'STERLING': 815, 'STINGRAY': 816, 'STOCKFISCH RECORDS': 817, 'STOCKFISCH': 817, 'STRAND RELEASING': 818, 'STRAND': 818, 'STUDIO 4K': 819, 'STUDIO CANAL': 820, 'STUDIO GHIBLI': 821, 'GHIBLI': 821, 'STUDIO HAMBURG ENTERPRISES': 822, 'HAMBURG ENTERPRISES': 822, 'STUDIO HAMBURG': 822, 'HAMBURG': 822, 'STUDIO S': 823, 'SUBKULTUR ENTERTAINMENT': 824, 'SUBKULTUR': 824, 'SUEVIA FILMS': 825, 'SUEVIA': 825, 'SUMMIT ENTERTAINMENT': 826, 'SUMMIT': 826, 'SUNFILM ENTERTAINMENT': 827, 'SUNFILM': 827, 'SURROUND RECORDS': 828, 'SURROUND': 828, 'SVENSK FILMINDUSTRI': 829, 'SVENSK': 829, 'SWEN FILMES': 830, 'SWEN FILMS': 830, 'SWEN': 830, 'SYNAPSE FILMS': 831, 'SYNAPSE': 831, 'SYNDICADO': 832, 'SYNERGETIC': 833, 'T- SERIES': 834, 'T-SERIES': 834, 'T SERIES': 834, 'TSERIES': 834, 'T.V.P.': 835, 'TVP': 835, 'TACET RECORDS': 836, 'TACET': 836, 'TAI SENG': 837, 'TAI SHENG': 838, 'TAKEONE': 839, 'TAKESHOBO': 840, 'TAMASA DIFFUSION': 841, 'TC ENTERTAINMENT': 842, 'TC': 842, 'TDK': 843, 'TEAM MARKETING': 844, 'TEATRO REAL': 845, 'TEMA DISTRIBUCIONES': 846, 'TEMPE DIGITAL': 847, 'TF1 VIDÉO': 848, 'TF1 VIDEO': 848, 'TF1': 848, 'THE BLU': 849, 'BLU': 849, 'THE ECSTASY OF FILMS': 850, 'THE FILM DETECTIVE': 851, 'FILM DETECTIVE': 851, 'THE JOKERS': 852, 'JOKERS': 852, 'THE ON': 853, 'ON': 853, 'THIMFILM': 854, 'THIM FILM': 854, 'THIM': 854, 'THIRD WINDOW FILMS': 855, 'THIRD WINDOW': 855, '3RD WINDOW FILMS': 855, '3RD WINDOW': 855, 'THUNDERBEAN ANIMATION': 856, 'THUNDERBEAN': 856, 'THUNDERBIRD RELEASING': 857, 'THUNDERBIRD': 857, 'TIBERIUS FILM': 858, 'TIME LIFE': 859, 'TIMELESS MEDIA GROUP': 860, 'TIMELESS MEDIA': 860, 'TIMELESS GROUP': 860, 'TIMELESS': 860, 'TLA RELEASING': 861, 'TLA': 861, 'TOBIS FILM': 862, 'TOBIS': 862, 'TOEI': 863, 'TOHO': 864, 'TOKYO SHOCK': 865, 'TOKYO': 865, 'TONPOOL MEDIEN GMBH': 866, 'TONPOOL MEDIEN': 866, 'TOPICS ENTERTAINMENT': 867, 'TOPICS': 867, 'TOUCHSTONE PICTURES': 868, 'TOUCHSTONE': 868, 'TRANSMISSION FILMS': 869, 'TRANSMISSION': 869, 'TRAVEL VIDEO STORE': 870, 'TRIART': 871, 'TRIGON FILM': 872, 'TRIGON': 872, 'TRINITY HOME ENTERTAINMENT': 873, 'TRINITY ENTERTAINMENT': 873, 'TRINITY HOME': 873, 'TRINITY': 873, 'TRIPICTURES': 874, 'TRI-PICTURES': 874, 'TRI PICTURES': 874, 'TROMA': 875, 'TURBINE MEDIEN': 876, 'TURTLE RECORDS': 877, 'TURTLE': 877, 'TVA FILMS': 878, 'TVA': 878, 'TWILIGHT TIME': 879, 'TWILIGHT': 879, 'TT': 879, 'TWIN CO., LTD.': 880, 'TWIN CO, LTD.': 880, 'TWIN CO., LTD': 880, 'TWIN CO, LTD': 880, 'TWIN CO LTD': 880, 'TWIN LTD': 880, 'TWIN CO.': 880, 'TWIN CO': 880, 'TWIN': 880, 'UCA': 881, 'UDR': 882, 'UEK': 883, 'UFA/DVD': 884, 'UFA DVD': 884, 'UFADVD': 884, 'UGC PH': 885, 'ULTIMATE3DHEAVEN': 886, 'ULTRA': 887, 'UMBRELLA ENTERTAINMENT': 888, 'UMBRELLA': 888, 'UMC': 889, "UNCORK'D ENTERTAINMENT": 890, 'UNCORKD ENTERTAINMENT': 890, 'UNCORK D ENTERTAINMENT': 890, "UNCORK'D": 890, 'UNCORK D': 890, 'UNCORKD': 890, 'UNEARTHED FILMS': 891, 'UNEARTHED': 891, 'UNI DISC': 892, 'UNIMUNDOS': 893, 'UNITEL': 894, 'UNIVERSAL MUSIC': 895, 'UNIVERSAL SONY PICTURES HOME ENTERTAINMENT': 896, 'UNIVERSAL SONY PICTURES ENTERTAINMENT': 896, 'UNIVERSAL SONY PICTURES HOME': 896, 'UNIVERSAL SONY PICTURES': 896, 'UNIVERSAL HOME ENTERTAINMENT':
            896, 'UNIVERSAL ENTERTAINMENT': 896, 'UNIVERSAL HOME': 896, 'UNIVERSAL STUDIOS': 897, 'UNIVERSAL': 897, 'UNIVERSE LASER & VIDEO CO.': 898, 'UNIVERSE LASER AND VIDEO CO.': 898, 'UNIVERSE LASER & VIDEO CO': 898, 'UNIVERSE LASER AND VIDEO CO': 898, 'UNIVERSE LASER CO.': 898, 'UNIVERSE LASER CO': 898, 'UNIVERSE LASER': 898, 'UNIVERSUM FILM': 899, 'UNIVERSUM': 899, 'UTV': 900, 'VAP': 901, 'VCI': 902, 'VENDETTA FILMS': 903, 'VENDETTA': 903, 'VERSÁTIL HOME VIDEO': 904, 'VERSÁTIL VIDEO': 904, 'VERSÁTIL HOME': 904, 'VERSÁTIL': 904, 'VERSATIL HOME VIDEO': 904, 'VERSATIL VIDEO': 904, 'VERSATIL HOME': 904, 'VERSATIL': 904, 'VERTICAL ENTERTAINMENT': 905, 'VERTICAL': 905, 'VÉRTICE 360º': 906, 'VÉRTICE 360': 906, 'VERTICE 360o': 906, 'VERTICE 360': 906, 'VERTIGO BERLIN': 907, 'VÉRTIGO FILMS': 908, 'VÉRTIGO': 908, 'VERTIGO FILMS': 908, 'VERTIGO': 908, 'VERVE PICTURES': 909, 'VIA VISION ENTERTAINMENT': 910, 'VIA VISION': 910, 'VICOL ENTERTAINMENT': 911, 'VICOL': 911, 'VICOM': 912, 'VICTOR ENTERTAINMENT': 913, 'VICTOR': 913, 'VIDEA CDE': 914, 'VIDEO FILM EXPRESS': 915, 'VIDEO FILM': 915, 'VIDEO EXPRESS': 915, 'VIDEO MUSIC, INC.': 916, 'VIDEO MUSIC, INC': 916, 'VIDEO MUSIC INC.': 916, 'VIDEO MUSIC INC': 916, 'VIDEO MUSIC': 916, 'VIDEO SERVICE CORP.': 917, 'VIDEO SERVICE CORP': 917, 'VIDEO SERVICE': 917, 'VIDEO TRAVEL': 918, 'VIDEOMAX': 919, 'VIDEO MAX': 919, 'VII PILLARS ENTERTAINMENT': 920, 'VII PILLARS': 920, 'VILLAGE FILMS': 921, 'VINEGAR SYNDROME': 922, 'VINEGAR': 922, 'VS': 922, 'VINNY MOVIES': 923, 'VINNY': 923, 'VIRGIL FILMS & ENTERTAINMENT': 924, 'VIRGIL FILMS AND ENTERTAINMENT': 924, 'VIRGIL ENTERTAINMENT': 924, 'VIRGIL FILMS': 924, 'VIRGIL': 924, 'VIRGIN RECORDS': 925, 'VIRGIN': 925, 'VISION FILMS': 926, 'VISION': 926, 'VISUAL ENTERTAINMENT GROUP': 927, 'VISUAL GROUP': 927, 'VISUAL ENTERTAINMENT': 927, 'VISUAL': 927, 'VIVENDI VISUAL ENTERTAINMENT': 928, 'VIVENDI VISUAL': 928, 'VIVENDI': 928, 'VIZ PICTURES': 929, 'VIZ': 929, 'VLMEDIA': 930, 'VL MEDIA': 930, 'VL': 930, 'VOLGA': 931, 'VVS FILMS': 932,
            'VVS': 932, 'VZ HANDELS GMBH': 933, 'VZ HANDELS': 933, 'WARD RECORDS': 934, 'WARD': 934, 'WARNER BROS.': 935, 'WARNER BROS': 935, 'WARNER ARCHIVE': 935, 'WARNER ARCHIVE COLLECTION': 935, 'WAC': 935, 'WARNER': 935, 'WARNER MUSIC': 936, 'WEA': 937, 'WEINSTEIN COMPANY': 938, 'WEINSTEIN': 938, 'WELL GO USA': 939, 'WELL GO': 939, 'WELTKINO FILMVERLEIH': 940, 'WEST VIDEO': 941, 'WEST': 941, 'WHITE PEARL MOVIES': 942, 'WHITE PEARL': 942,
            'WICKED-VISION MEDIA': 943, 'WICKED VISION MEDIA': 943, 'WICKEDVISION MEDIA': 943, 'WICKED-VISION': 943, 'WICKED VISION': 943, 'WICKEDVISION': 943, 'WIENERWORLD': 944, 'WILD BUNCH': 945, 'WILD EYE RELEASING': 946, 'WILD EYE': 946, 'WILD SIDE VIDEO': 947, 'WILD SIDE': 947, 'WME': 948, 'WOLFE VIDEO': 949, 'WOLFE': 949, 'WORD ON FIRE': 950, 'WORKS FILM GROUP': 951, 'WORLD WRESTLING': 952, 'WVG MEDIEN': 953, 'WWE STUDIOS': 954, 'WWE': 954, 'X RATED KULT': 955, 'X-RATED KULT': 955, 'X RATED CULT': 955, 'X-RATED CULT': 955, 'X RATED': 955, 'X-RATED': 955, 'XCESS': 956, 'XLRATOR': 957, 'XT VIDEO': 958, 'XT': 958, 'YAMATO VIDEO': 959, 'YAMATO': 959, 'YASH RAJ FILMS': 960, 'YASH RAJS': 960, 'ZEITGEIST FILMS': 961, 'ZEITGEIST': 961, 'ZENITH PICTURES': 962, 'ZENITH': 962, 'ZIMA': 963, 'ZYLO': 964, 'ZYX MUSIC': 965, 'ZYX': 965
        }

        if reverse:
            for name, id_value in distributor_map.items():
                if id_value == distributor_id:
                    return name
            return None
        else:
            return distributor_map.get(distributor, 0)

    async def prompt_user_for_id_selection(self, meta, tmdb=None, imdb=None, tvdb=None, mal=None, filename=None, tracker_name=None):
        if not tracker_name:
            tracker_name = "Tracker"  # Fallback if tracker_name is not provided

        if imdb:
            imdb = str(imdb).zfill(7)  # Convert to string and ensure IMDb ID is 7 characters long by adding leading zeros
            # console.print(f"[cyan]Found IMDb ID: https://www.imdb.com/title/tt{imdb}[/cyan]")

        if any([tmdb, imdb, tvdb, mal]):
            console.print(f"[cyan]Found the following IDs on {tracker_name}:")
            if tmdb:
                console.print(f"TMDb ID: {tmdb}")
            if imdb:
                console.print(f"IMDb ID: https://www.imdb.com/title/tt{imdb}")
            if tvdb:
                console.print(f"TVDb ID: {tvdb}")
            if mal:
                console.print(f"MAL ID: {mal}")

        if filename:
            console.print(f"Filename: {filename}")  # Ensure filename is printed if available

        if not meta['unattended']:
            selection = input(f"Do you want to use these IDs from {tracker_name}? (Y/n): ").strip().lower()
            try:
                if selection == '' or selection == 'y' or selection == 'yes':
                    return True
                else:
                    return False
            except (KeyboardInterrupt, EOFError):
                sys.exit(1)
        else:
            return True

    async def prompt_user_for_confirmation(self, message):
        response = input(f"{message} (Y/n): ").strip().lower()
        if response == '' or response == 'y':
            return True
        return False

    async def unit3d_region_distributor(self, meta, tracker, torrent_url, id=None):
        """Get region and distributor information from API response"""
        params = {'api_token': self.config['TRACKERS'][tracker].get('api_key', '')}
        url = f"{torrent_url}{id}"
        response = requests.get(url=url, params=params)
        try:
            json_response = response.json()
        except ValueError:
            return
        try:
            data = json_response.get('data', [])
            if data == "404":
                console.print("[yellow]No data found (404). Returning None.[/yellow]")
                return
            if data and isinstance(data, list):
                attributes = data[0].get('attributes', {})

                region_id = attributes.get('region_id')
                distributor_id = attributes.get('distributor_id')

                if meta['debug']:
                    console.print(f"[blue]Region ID: {region_id}[/blue]")
                    console.print(f"[blue]Distributor ID: {distributor_id}[/blue]")

                # use reverse to reverse map the id to the name
                if not meta.get('region') and region_id:
                    region_name = await self.unit3d_region_ids(None, reverse=True, region_id=region_id)
                    if region_name:
                        meta['region'] = region_name
                        if meta['debug']:
                            console.print(f"[green]Mapped region_id {region_id} to '{region_name}'[/green]")

                # use reverse to reverse map the id to the name
                if not meta.get('distributor') and distributor_id:
                    distributor_name = await self.unit3d_distributor_ids(None, reverse=True, distributor_id=distributor_id)
                    if distributor_name:
                        meta['distributor'] = distributor_name
                        if meta['debug']:
                            console.print(f"[green]Mapped distributor_id {distributor_id} to '{distributor_name}'[/green]")
                return

            else:
                # Handle direct attributes from JSON response (when not in a list)
                attributes = json_response.get('attributes', {})
                if attributes:
                    region_id = attributes.get('region_id')
                    distributor_id = attributes.get('distributor_id')

                    if meta['debug']:
                        console.print(f"[blue]Region ID: {region_id}[/blue]")
                        console.print(f"[blue]Distributor ID: {distributor_id}[/blue]")

                    if not meta.get('region') and region_id:
                        region_name = await self.unit3d_region_ids(None, reverse=True, region_id=region_id)
                        if region_name:
                            meta['region'] = region_name
                            if meta['debug']:
                                console.print(f"[green]Mapped region_id {region_id} to '{region_name}'[/green]")

                    if not meta.get('distributor') and distributor_id:
                        distributor_name = await self.unit3d_distributor_ids(None, reverse=True, distributor_id=distributor_id)
                        if distributor_name:
                            meta['distributor'] = distributor_name
                            if meta['debug']:
                                console.print(f"[green]Mapped distributor_id {distributor_id} to '{distributor_name}'[/green]")
        except Exception as e:
            console.print_exception()
            console.print(f"[yellow]Invalid Response from {tracker} API. Error: {str(e)}[/yellow]")
            return

    async def unit3d_torrent_info(self, tracker, torrent_url, search_url, meta, id=None, file_name=None, only_id=False):
        tmdb = imdb = tvdb = description = category = infohash = mal = files = None  # noqa F841
        imagelist = []

        # Build the params for the API request
        params = {'api_token': self.config['TRACKERS'][tracker].get('api_key', '')}

        # Determine the search method and add parameters accordingly
        if file_name:
            params['file_name'] = file_name   # Add file_name to params
            if meta.get('debug'):
                console.print(f"[green]Searching {tracker} by file name: [bold yellow]{file_name}[/bold yellow]")
            url = search_url
        elif id:
            url = f"{torrent_url}{id}"
            if meta.get('debug'):
                console.print(f"[green]Searching {tracker} by ID: [bold yellow]{id}[/bold yellow] via {url}")
        else:
            if meta.get('debug'):
                console.print("[red]No ID or file name provided for search.[/red]")
            return None, None, None, None, None, None, None, None, None

        # Make the GET request with proper encoding handled by 'params'
        response = requests.get(url=url, params=params)
        # console.print(f"[blue]Raw API Response: {response}[/blue]")

        try:
            json_response = response.json()

            # console.print(f"Raw API Response: {json_response}", markup=False)

        except ValueError:
            return None, None, None, None, None, None, None, None, None

        try:
            # Handle response when searching by file name (which might return a 'data' array)
            data = json_response.get('data', [])
            if data == "404":
                console.print("[yellow]No data found (404). Returning None.[/yellow]")
                return None, None, None, None, None, None, None, None, None

            if data and isinstance(data, list):  # Ensure data is a list before accessing it
                attributes = data[0].get('attributes', {})

                # Extract data from the attributes
                category = attributes.get('category')
                description = attributes.get('description')
                tmdb = attributes.get('tmdb_id')
                tvdb = attributes.get('tvdb_id')
                mal = attributes.get('mal_id')
                imdb = attributes.get('imdb_id')
                infohash = attributes.get('info_hash')
                tmdb = 0 if tmdb == 0 else tmdb
                tvdb = 0 if tvdb == 0 else tvdb
                mal = 0 if mal == 0 else mal
                imdb = 0 if imdb == 0 else imdb
                if not meta.get('region') and meta.get('is_disc') == "BDMV":
                    region_id = attributes.get('region_id')
                    region_name = await self.unit3d_region_ids(None, reverse=True, region_id=region_id)
                    if region_name:
                        meta['region'] = region_name
                if not meta.get('distributor') and meta.get('is_disc') == "BDMV":
                    distributor_id = attributes.get('distributor_id')
                    distributor_name = await self.unit3d_distributor_ids(None, reverse=True, distributor_id=distributor_id)
                    if distributor_name:
                        meta['distributor'] = distributor_name
            else:
                # Handle response when searching by ID
                if id and not data:
                    attributes = json_response.get('attributes', {})

                    # Extract data from the attributes
                    category = attributes.get('category')
                    description = attributes.get('description')
                    tmdb = attributes.get('tmdb_id')
                    tvdb = attributes.get('tvdb_id')
                    mal = attributes.get('mal_id')
                    imdb = attributes.get('imdb_id')
                    infohash = attributes.get('info_hash')
                    tmdb = 0 if tmdb == 0 else tmdb
                    tvdb = 0 if tvdb == 0 else tvdb
                    mal = 0 if mal == 0 else mal
                    imdb = 0 if imdb == 0 else imdb
                    if not meta.get('region') and meta.get('is_disc') == "BDMV":
                        region_id = attributes.get('region_id')
                        region_name = await self.unit3d_region_ids(None, reverse=True, region_id=region_id)
                        if region_name:
                            meta['region'] = region_name
                    if not meta.get('distributor') and meta.get('is_disc') == "BDMV":
                        distributor_id = attributes.get('distributor_id')
                        distributor_name = await self.unit3d_distributor_ids(None, reverse=True, distributor_id=distributor_id)
                        if distributor_name:
                            meta['distributor'] = distributor_name
                    # Handle file name extraction
                    files = attributes.get('files', [])
                    if files:
                        if len(files) == 1:
                            file_name = files[0]['name']
                        else:
                            file_name = [file['name'] for file in files[:5]]  # Return up to 5 filenames

                    if meta.get('debug'):
                        console.print(f"[blue]Extracted filename(s): {file_name}[/blue]")  # Print the extracted filename(s)

                    if imdb != 0:
                        imdb_str = str(f'tt{imdb}').zfill(7)
                    else:
                        imdb_str = None

                    console.print(f"[green]Valid IDs found from {tracker}: TMDb: {tmdb}, IMDb: {imdb_str}, TVDb: {tvdb}, MAL: {mal}[/green]")

            if tmdb or imdb or tvdb:
                if not id:
                    # Only prompt the user for ID selection if not searching by ID
                    try:
                        if not await self.prompt_user_for_id_selection(meta, tmdb, imdb, tvdb, mal, file_name, tracker_name=tracker):
                            console.print("[yellow]User chose to skip based on IDs.[/yellow]")
                            return None, None, None, None, None, None, None, None, None
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)

            if description:
                bbcode = BBCODE()
                description, imagelist = bbcode.clean_unit3d_description(description, torrent_url)
                if not only_id:
                    console.print(f"[green]Successfully grabbed description from {tracker}")
                    console.print(f"Extracted description: {description}", markup=False)

                    if meta.get('unattended') or (meta.get('blu') or meta.get('aither') or meta.get('lst') or meta.get('oe') or meta.get('huno') or meta.get('ulcx')):
                        meta['description'] = description
                        meta['saved_description'] = True
                    else:
                        console.print("[cyan]Do you want to edit, discard or keep the description?[/cyan]")
                        edit_choice = input("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is:")

                        if edit_choice.lower() == 'e':
                            edited_description = click.edit(description)
                            if edited_description:
                                description = edited_description.strip()
                            meta['description'] = description
                            meta['saved_description'] = True
                        elif edit_choice.lower() == 'd':
                            description = None
                            imagelist = []
                            console.print("[yellow]Description discarded.[/yellow]")
                        else:
                            console.print("[green]Keeping the original description.[/green]")
                            meta['description'] = description
                            meta['saved_description'] = True
                    if not meta.get('keep_images'):
                        imagelist = []
                else:
                    description = ""
                    if not meta.get('keep_images'):
                        imagelist = []

            return tmdb, imdb, tvdb, mal, description, category, infohash, imagelist, file_name

        except Exception as e:
            console.print_exception()
            console.print(f"[yellow]Invalid Response from {tracker} API. Error: {str(e)}[/yellow]")
            return None, None, None, None, None, None, None, None, None

    async def parseCookieFile(self, cookiefile):
        """Parse a cookies.txt file and return a dictionary of key value pairs
        compatible with requests."""

        cookies = {}
        with open(cookiefile, 'r') as fp:
            for line in fp:
                if not line.startswith(("# ", "\n", "#\n")):
                    lineFields = re.split(' |\t', line.strip())
                    lineFields = [x for x in lineFields if x != ""]
                    cookies[lineFields[5]] = lineFields[6]
        return cookies

    async def ptgen(self, meta, ptgen_site="", ptgen_retry=3):
        ptgen = ""
        url = 'https://ptgen.zhenzhen.workers.dev'
        if ptgen_site != '':
            url = ptgen_site
        params = {}
        data = {}
        # get douban url
        if int(meta.get('imdb_id')) != 0:
            data['search'] = f"tt{meta['imdb_id']}"
            ptgen = requests.get(url, params=data)
            if ptgen.json()["error"] is not None:
                for retry in range(ptgen_retry):
                    try:
                        ptgen = requests.get(url, params=params)
                        if ptgen.json()["error"] is None:
                            break
                    except requests.exceptions.JSONDecodeError:
                        continue
            try:
                params['url'] = ptgen.json()['data'][0]['link']
            except Exception:
                console.print("[red]Unable to get data from ptgen using IMDb")
                params['url'] = console.input("[red]Please enter [yellow]Douban[/yellow] link: ")
        else:
            console.print("[red]No IMDb id was found.")
            params['url'] = console.input("[red]Please enter [yellow]Douban[/yellow] link: ")
        try:
            ptgen = requests.get(url, params=params)
            if ptgen.json()["error"] is not None:
                for retry in range(ptgen_retry):
                    ptgen = requests.get(url, params=params)
                    if ptgen.json()["error"] is None:
                        break
            ptgen = ptgen.json()
            meta['ptgen'] = ptgen
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
                json.dump(meta, f, indent=4)
                f.close()
            ptgen = ptgen['format']
            if "[/img]" in ptgen:
                ptgen = ptgen.split("[/img]")[1]
            ptgen = f"[img]{meta.get('imdb_info', {}).get('cover', meta.get('cover', ''))}[/img]{ptgen}"
        except Exception:
            console.print_exception()
            console.print(ptgen.text)
            console.print("[bold red]There was an error getting the ptgen \nUploading without ptgen")
            return ""
        return ptgen

    class MediaInfoParser:
        # Language to ISO country code mapping
        LANGUAGE_CODE_MAP = {
            "afrikaans": ("https://ptpimg.me/i9pt6k.png", "20"),
            "albanian": ("https://ptpimg.me/sfhik8.png", "20"),
            "amharic": ("https://ptpimg.me/zm816y.png", "20"),
            "arabic": ("https://ptpimg.me/5g8i9u.png", "26x10"),
            "armenian": ("https://ptpimg.me/zm816y.png", "20"),
            "azerbaijani": ("https://ptpimg.me/h3rbe0.png", "20"),
            "basque": ("https://ptpimg.me/xj51b9.png", "20"),
            "belarusian": ("https://ptpimg.me/iushg1.png", "20"),
            "bengali": ("https://ptpimg.me/jq996n.png", "20"),
            "bosnian": ("https://ptpimg.me/19t9rv.png", "20"),
            "brazilian": ("https://ptpimg.me/p8sgla.png", "20"),
            "bulgarian": ("https://ptpimg.me/un9dc6.png", "20"),
            "catalan": ("https://ptpimg.me/v4h5bf.png", "20"),
            "chinese": ("https://ptpimg.me/ea3yv3.png", "20"),
            "croatian": ("https://ptpimg.me/rxi533.png", "20"),
            "czech": ("https://ptpimg.me/5m75n3.png", "20"),
            "danish": ("https://ptpimg.me/m35c41.png", "20"),
            "dutch": ("https://ptpimg.me/6nmwpx.png", "20"),
            "dzongkha": ("https://ptpimg.me/56e7y5.png", "20"),
            "english": ("https://ptpimg.me/ine2fd.png", "25x10"),
            "english (gb)": ("https://ptpimg.me/a9w539.png", "20"),
            "estonian": ("https://ptpimg.me/z25pmk.png", "20"),
            "filipino": ("https://ptpimg.me/9d3z9w.png", "20"),
            "finnish": ("https://ptpimg.me/p4354c.png", "20"),
            "french (canada)": ("https://ptpimg.me/ei4s6u.png", "20"),
            "french canadian": ("https://ptpimg.me/ei4s6u.png", "20"),
            "french": ("https://ptpimg.me/m7mfoi.png", "20"),
            "galician": ("https://ptpimg.me/xj51b9.png", "20"),
            "georgian": ("https://ptpimg.me/pp412q.png", "20"),
            "german": ("https://ptpimg.me/dw8d04.png", "30x10"),
            "greek": ("https://ptpimg.me/px1u3e.png", "20"),
            "gujarati": ("https://ptpimg.me/d0l479.png", "20"),
            "haitian creole": ("https://ptpimg.me/f64wlp.png", "20"),
            "hebrew": ("https://ptpimg.me/5jw1jp.png", "20"),
            "hindi": ("https://ptpimg.me/d0l479.png", "20"),
            "hungarian": ("https://ptpimg.me/fr4aj7.png", "30x10"),
            "icelandic": ("https://ptpimg.me/40o553.png", "20"),
            "indonesian": ("https://ptpimg.me/f00c8u.png", "20"),
            "irish": ("https://ptpimg.me/71x9mk.png", "20"),
            "italian": ("https://ptpimg.me/ao762a.png", "20"),
            "japanese": ("https://ptpimg.me/o1amm3.png", "20"),
            "kannada": ("https://ptpimg.me/d0l479.png", "20"),
            "kazakh": ("https://ptpimg.me/tq1h8b.png", "20"),
            "khmer": ("https://ptpimg.me/0p1tli.png", "20"),
            "korean": ("https://ptpimg.me/2tvwgn.png", "20"),
            "kurdish": ("https://ptpimg.me/g290wo.png", "20"),
            "kyrgyz": ("https://ptpimg.me/336unh.png", "20"),
            "lao": ("https://ptpimg.me/n3nan1.png", "20"),
            "latin american": ("https://ptpimg.me/11350x.png", "20"),
            "latvian": ("https://ptpimg.me/3x2y1b.png", "25x10"),
            "lithuanian": ("https://ptpimg.me/b444z8.png", "20"),
            "luxembourgish": ("https://ptpimg.me/52x189.png", "20"),
            "macedonian": ("https://ptpimg.me/2g5lva.png", "20"),
            "malagasy": ("https://ptpimg.me/n5120r.png", "20"),
            "malay": ("https://ptpimg.me/02e17w.png", "30x10"),
            "malayalam": ("https://ptpimg.me/d0l479.png", "20"),
            "maltese": ("https://ptpimg.me/ua46c2.png", "20"),
            "maori": ("https://ptpimg.me/2fw03g.png", "20"),
            "marathi": ("https://ptpimg.me/d0l479.png", "20"),
            "mongolian": ("https://ptpimg.me/z2h682.png", "20"),
            "nepali": ("https://ptpimg.me/5yd3sp.png", "20"),
            "norwegian": ("https://ptpimg.me/1t11u4.png", "20"),
            "pashto": ("https://ptpimg.me/i9pt6k.png", "20"),
            "persian": ("https://ptpimg.me/i0y103.png", "20"),
            "polish": ("https://ptpimg.me/m73uwa.png", "20"),
            "portuguese": ("https://ptpimg.me/5j1a7q.png", "20"),
            "portuguese (brazil)": ("https://ptpimg.me/p8sgla.png", "20"),
            "punjabi": ("https://ptpimg.me/d0l479.png", "20"),
            "romanian": ("https://ptpimg.me/ux94x0.png", "20"),
            "russian": ("https://ptpimg.me/v33j64.png", "20"),
            "samoan": ("https://ptpimg.me/8nt3zq.png", "20"),
            "serbian": ("https://ptpimg.me/2139p2.png", "20"),
            "slovak": ("https://ptpimg.me/70994n.png", "20"),
            "slovenian": ("https://ptpimg.me/61yp81.png", "25x10"),
            "somali": ("https://ptpimg.me/320pa6.png", "20"),
            "spanish": ("https://ptpimg.me/xj51b9.png", "20"),
            "spanish (latin america)": ("https://ptpimg.me/11350x.png", "20"),
            "swahili": ("https://ptpimg.me/d0l479.png", "20"),
            "swedish": ("https://ptpimg.me/082090.png", "20"),
            "tamil": ("https://ptpimg.me/d0l479.png", "20"),
            "telugu": ("https://ptpimg.me/d0l479.png", "20"),
            "thai": ("https://ptpimg.me/38ru43.png", "20"),
            "turkish": ("https://ptpimg.me/g4jg39.png", "20"),
            "ukrainian": ("https://ptpimg.me/d8fp6k.png", "20"),
            "urdu": ("https://ptpimg.me/z23gg5.png", "20"),
            "uzbek": ("https://ptpimg.me/89854s.png", "20"),
            "vietnamese": ("https://ptpimg.me/qnuya2.png", "20"),
            "welsh": ("https://ptpimg.me/a9w539.png", "20"),
            "xhosa": ("https://ptpimg.me/7teg09.png", "20"),
            "yiddish": ("https://ptpimg.me/5jw1jp.png", "20"),
            "yoruba": ("https://ptpimg.me/9l34il.png", "20"),
            "zulu": ("https://ptpimg.me/7teg09.png", "20")
        }

        def parse_mediainfo(self, mediainfo_text):
            # Patterns for matching sections and fields
            section_pattern = re.compile(r"^(General|Video|Audio|Text|Menu)(?:\s#\d+)?", re.IGNORECASE)
            parsed_data = {"general": {}, "video": [], "audio": [], "text": []}
            current_section = None
            current_track = {}

            # Field lists based on PHP definitions
            general_fields = {'file_name', 'format', 'duration', 'file_size', 'bit_rate'}
            video_fields = {
                'format', 'format_version', 'codec', 'width', 'height', 'stream_size',
                'framerate_mode', 'frame_rate', 'aspect_ratio', 'bit_rate', 'bit_rate_mode', 'bit_rate_nominal',
                'bit_pixel_frame', 'bit_depth', 'language', 'format_profile',
                'color_primaries', 'title', 'scan_type', 'transfer_characteristics', 'hdr_format'
            }
            audio_fields = {
                'codec', 'format', 'bit_rate', 'channels', 'title', 'language', 'format_profile', 'stream_size'
            }
            # text_fields = {'title', 'language'}

            # Split MediaInfo by lines and process each line
            for line in mediainfo_text.splitlines():
                line = line.strip()

                # Detect a new section
                section_match = section_pattern.match(line)
                if section_match:
                    # Save the last track data if moving to a new section
                    if current_section and current_track:
                        if current_section in ["video", "audio", "text"]:
                            parsed_data[current_section].append(current_track)
                        else:
                            parsed_data[current_section] = current_track
                        # Debug output for finalizing the current track data
                        # print(f"Final processed track data for section '{current_section}': {current_track}")
                        current_track = {}  # Reset current track

                    # Update the current section
                    current_section = section_match.group(1).lower()
                    continue

                # Split each line on the first colon to separate property and value
                if ":" in line:
                    property_name, property_value = map(str.strip, line.split(":", 1))
                    property_name = property_name.lower().replace(" ", "_")

                    # Add property if it's a recognized field for the current section
                    if current_section == "general" and property_name in general_fields:
                        current_track[property_name] = property_value
                    elif current_section == "video" and property_name in video_fields:
                        current_track[property_name] = property_value
                    elif current_section == "audio" and property_name in audio_fields:
                        current_track[property_name] = property_value
                    elif current_section == "text":
                        # Processing specific properties for text
                        # Process title field
                        if property_name == "title" and "title" not in current_track:
                            title_lower = property_value.lower()
                            # print(f"\nProcessing Title: '{property_value}'")  # Debugging output

                            # Store the title as-is since it should remain descriptive
                            current_track["title"] = property_value
                            # print(f"Stored title: '{property_value}'")

                            # If there's an exact match in LANGUAGE_CODE_MAP, add country code to language field
                            if title_lower in self.LANGUAGE_CODE_MAP:
                                country_code, size = self.LANGUAGE_CODE_MAP[title_lower]
                                current_track["language"] = f"[img={size}]{country_code}[/img]"
                                # print(f"Exact match found for title '{title_lower}' with country code: {country_code}")

                        # Process language field only if it hasn't already been set
                        elif property_name == "language" and "language" not in current_track:
                            language_lower = property_value.lower()
                            # print(f"\nProcessing Language: '{property_value}'")  # Debugging output

                            if language_lower in self.LANGUAGE_CODE_MAP:
                                country_code, size = self.LANGUAGE_CODE_MAP[language_lower]
                                current_track["language"] = f"[img={size}]{country_code}[/img]"
                                # print(f"Matched language '{language_lower}' to country code: {country_code}")
                            else:
                                # If no match in LANGUAGE_CODE_MAP, store language as-is
                                current_track["language"] = property_value
                                # print(f"No match found for language '{property_value}', stored as-is.")

            # Append the last track to the parsed data if it exists
            if current_section and current_track:
                if current_section in ["video", "audio", "text"]:
                    parsed_data[current_section].append(current_track)
                else:
                    parsed_data[current_section] = current_track
                # Final debug output for the last track data
                # print(f"Final processed track data for last section '{current_section}': {current_track}")

            # Debug output for the complete parsed_data
            # print("\nComplete Parsed Data:")
            # for section, data in parsed_data.items():
            #    print(f"{section}: {data}")

            return parsed_data

        def format_bbcode(self, parsed_mediainfo):
            bbcode_output = "\n"

            # Format General Section
            if "general" in parsed_mediainfo:
                bbcode_output += "[b]General[/b]\n"
                for prop, value in parsed_mediainfo["general"].items():
                    bbcode_output += f"[b]{prop.replace('_', ' ').capitalize()}:[/b] {value}\n"

            # Format Video Section
            if "video" in parsed_mediainfo:
                bbcode_output += "\n[b]Video[/b]\n"
                for track in parsed_mediainfo["video"]:
                    for prop, value in track.items():
                        bbcode_output += f"[b]{prop.replace('_', ' ').capitalize()}:[/b] {value}\n"

            # Format Audio Section
            if "audio" in parsed_mediainfo:
                bbcode_output += "\n[b]Audio[/b]\n"
                for index, track in enumerate(parsed_mediainfo["audio"], start=1):  # Start enumeration at 1
                    parts = [f"{index}."]  # Start with track number without a trailing slash

                    # Language flag image
                    language = track.get("language", "").lower()
                    result = self.LANGUAGE_CODE_MAP.get(language)

                    # Check if the language was found in LANGUAGE_CODE_MAP
                    if result is not None:
                        country_code, size = result
                        parts.append(f"[img={size}]{country_code}[/img]")
                    else:
                        # If language is not found, use a fallback or display the language as plain text
                        parts.append(language.capitalize() if language else "")

                    # Other properties to concatenate
                    properties = ["language", "codec", "format", "channels", "bit_rate", "format_profile", "stream_size"]
                    for prop in properties:
                        if prop in track and track[prop]:  # Only add non-empty properties
                            parts.append(track[prop])

                    # Join parts (starting from index 1, after the track number) with slashes and add to bbcode_output
                    bbcode_output += f"{parts[0]} " + " / ".join(parts[1:]) + "\n"

            # Format Text Section - Centered with flags or text, spaced apart
            if "text" in parsed_mediainfo:
                bbcode_output += "\n[b]Subtitles[/b]\n"
                subtitle_entries = []
                for track in parsed_mediainfo["text"]:
                    language_display = track.get("language", "")
                    subtitle_entries.append(language_display)
                bbcode_output += " ".join(subtitle_entries)

            bbcode_output += "\n"
            return bbcode_output
