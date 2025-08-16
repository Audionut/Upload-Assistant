import re
import html
import urllib.parse
import os
from src.console import console

# Bold - KEEP
# Italic - KEEP
# Underline - KEEP
# Strikethrough - KEEP
# Color - KEEP
# URL - KEEP
# PARSING - Probably not exist in uploads
# Spoiler - KEEP

# QUOTE - CONVERT to CODE
# PRE - CONVERT to CODE
# Hide - CONVERT to SPOILER
# COMPARISON - CONVERT

# LIST - REMOVE TAGS/REPLACE with * or something

# Size - REMOVE TAGS

# Align - REMOVE (ALL LEFT ALIGNED)
# VIDEO - REMOVE
# HR - REMOVE
# MEDIAINFO - REMOVE
# MOVIE - REMOVE
# PERSON - REMOVE
# USER - REMOVE
# IMG - REMOVE?
# INDENT - Probably not an issue, but maybe just remove tags


class BBCODE:
    def __init__(self):
        pass

    def clean_hdb_description(self, description):
        # Unescape html
        desc = html.unescape(description)
        desc = desc.replace('\r\n', '\n')
        imagelist = []

        # First pass: Remove entire comparison sections
        # Start by finding section headers for comparisons
        comparison_sections = re.finditer(r"\[center\]\s*\[b\].*?(Comparison|vs).*?\[\/b\][\s\S]*?\[\/center\]",
                                          desc, flags=re.IGNORECASE)
        for section in comparison_sections:
            section_text = section.group(0)
            # If section contains hdbits.org, remove the entire section
            if re.search(r"hdbits\.org", section_text, flags=re.IGNORECASE):
                desc = desc.replace(section_text, '')

        # Handle individual comparison lines
        comparison_lines = re.finditer(r"(.*comparison.*)\n", desc, flags=re.IGNORECASE)
        for comp_match in comparison_lines:
            comp_pos = comp_match.start()

            # Get the next lines after the comparison line
            next_lines = desc[comp_pos:comp_pos+500].split('\n', 3)[:3]  # Get comparison line + 2 more lines
            next_lines_text = '\n'.join(next_lines)

            # Check if any of these lines contain HDBits URLs
            if re.search(r"hdbits\.org", next_lines_text, flags=re.IGNORECASE):
                # Replace the entire section (comparison line + next 2 lines)
                line_end_pos = comp_pos + len(next_lines_text)
                to_remove = desc[comp_pos:line_end_pos]
                desc = desc.replace(to_remove, '')

        # Remove all empty URL tags containing hdbits.org
        desc = re.sub(r"\[url=https?:\/\/(img\.|t\.)?hdbits\.org[^\]]*\]\[\/url\]", "", desc, flags=re.IGNORECASE)

        # Remove URL tags with visible content
        hdbits_urls = re.findall(r"(\[url[\=\]]https?:\/\/(img\.|t\.)?hdbits\.org[^\]]+\])(.*?)(\[\/url\])?", desc, flags=re.IGNORECASE)
        for url_parts in hdbits_urls:
            full_url = ''.join(url_parts)
            desc = desc.replace(full_url, '')

        # Remove HDBits image tags
        hdbits_imgs = re.findall(r"\[img\][\s\S]*?(img\.|t\.)?hdbits\.org[\s\S]*?\[\/img\]", desc, flags=re.IGNORECASE)
        for img_tag in hdbits_imgs:
            desc = desc.replace(img_tag, '')

        # Remove any standalone HDBits URLs
        standalone_urls = re.findall(r"https?:\/\/(img\.|t\.)?hdbits\.org\/[^\s\[\]]+", desc, flags=re.IGNORECASE)
        for url in standalone_urls:
            desc = desc.replace(url, '')

        # Catch any remaining URL tags with hdbits.org in them
        desc = re.sub(r"\[url[^\]]*hdbits\.org[^\]]*\](.*?)\[\/url\]", "", desc, flags=re.IGNORECASE)

        # Double-check for any self-closing URL tags that might have been missed
        desc = re.sub(r"\[url=https?:\/\/[^\]]*hdbits\.org[^\]]*\]\[\/url\]", "", desc, flags=re.IGNORECASE)

        # Remove empty comparison section headers and center tags
        desc = re.sub(r"\[center\]\s*\[b\].*?(Comparison|vs).*?\[\/b\][\s\S]*?\[\/center\]",
                      "", desc, flags=re.IGNORECASE)

        # Remove any empty center tags that might be left
        desc = re.sub(r"\[center\]\s*\[\/center\]", "", desc, flags=re.IGNORECASE)

        # Clean up multiple consecutive newlines
        desc = re.sub(r"\n{3,}", "\n\n", desc)

        # Extract images wrapped in URL tags (e.g., [url=https://imgbox.com/xxx][img]https://thumbs.imgbox.com/xxx[/img][/url])
        url_img_pattern = r"\[url=(https?:\/\/[^\]]+)\]\[img\](https?:\/\/[^\]]+)\[\/img\]\[\/url\]"
        url_img_matches = re.findall(url_img_pattern, desc, flags=re.IGNORECASE)
        for web_url, img_url in url_img_matches:
            # Skip HDBits images
            if "hdbits.org" in web_url.lower() or "hdbits.org" in img_url.lower():
                desc = desc.replace(f"[url={web_url}][img]{img_url}[/img][/url]", '')
                continue

            raw_url = img_url
            if "thumbs2.imgbox.com" in img_url:
                raw_url = img_url.replace("thumbs2.imgbox.com", "images2.imgbox.com")
                raw_url = raw_url.replace("_t.png", "_o.png")

            image_dict = {
                'img_url': img_url,
                'raw_url': raw_url,
                'web_url': web_url
            }
            imagelist.append(image_dict)
            desc = desc.replace(f"[url={web_url}][img]{img_url}[/img][/url]", '')

        description = desc.strip()
        return description, imagelist

    def clean_bhd_description(self, description, meta):
        # Unescape html
        desc = html.unescape(description)
        desc = desc.replace('\r\n', '\n')
        imagelist = []

        if "framestor" in meta and meta['framestor']:
            framestor_desc = desc
            save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
            os.makedirs(save_path, exist_ok=True)
            nfo_file_path = os.path.join(save_path, "bhd.nfo")
            with open(nfo_file_path, 'w', encoding='utf-8') as f:
                try:
                    f.write(framestor_desc)
                finally:
                    f.close()
            console.print(f"[green]FraMeSToR NFO saved to {nfo_file_path}")
            meta['nfo'] = True
            meta['bhd_nfo'] = True

        # Remove size tags
        desc = re.sub(r"\[size=.*?\]", "", desc)
        desc = desc.replace("[/size]", "")
        desc = desc.replace("<", "/")
        desc = desc.replace("<", "\\")

        # Remove Images in IMG tags
        desc = re.sub(r"\[img\][\s\S]*?\[\/img\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[img=[\s\S]*?\]", "", desc, flags=re.IGNORECASE)

        # Extract loose images and add to imagelist as dictionaries
        loose_images = re.findall(r"(https?:\/\/[^\s\[\]]+\.(?:png|jpg))", desc, flags=re.IGNORECASE)
        for img_url in loose_images:
            image_dict = {
                'img_url': img_url,
                'raw_url': img_url,
                'web_url': img_url
            }
            imagelist.append(image_dict)
            desc = desc.replace(img_url, '')

        # Now, remove matching URLs from [URL] tags
        for img in imagelist:
            img_url = re.escape(img['img_url'])
            desc = re.sub(rf"\[URL={img_url}\]\[/URL\]", '', desc, flags=re.IGNORECASE)
            desc = re.sub(rf"\[URL={img_url}\]\[img[^\]]*\]{img_url}\[/img\]\[/URL\]", '', desc, flags=re.IGNORECASE)

        # Remove leftover [img] or [URL] tags in the description
        desc = re.sub(r"\[img\][\s\S]*?\[\/img\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[img=[\s\S]*?\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[URL=[\s\S]*?\]\[\/URL\]", "", desc, flags=re.IGNORECASE)

        if meta.get('flux', False):
            # Strip trailing whitespace and newlines:
            desc = desc.rstrip()

            # Strip blank lines:
            desc = desc.strip('\n')
            desc = re.sub("\n\n+", "\n\n", desc)
            while desc.startswith('\n'):
                desc = desc.replace('\n', '', 1)
            desc = desc.strip('\n')

            if desc.replace('\n', '').strip() == '':
                console.print("[yellow]Description is empty after cleaning.")
                return "", imagelist

            description = f"[code]{desc}[/code]"
        else:
            description = ""

        return description, imagelist

    def clean_ptp_description(self, desc, is_disc):
        # console.print("[yellow]Cleaning PTP description...")

        # Convert Bullet Points to -
        desc = desc.replace("&bull;", "-")

        # Unescape html
        desc = html.unescape(desc)
        desc = desc.replace('\r\n', '\n')

        # Remove url tags with PTP/HDB links
        url_tags = re.findall(
            r"(?:\[url(?:=|\])[^\]]*https?:\/\/passthepopcorn\.m[^\]]*\]|\bhttps?:\/\/passthepopcorn\.m[^\s]+)",
            desc,
            flags=re.IGNORECASE,
        )
        url_tags += re.findall(r"(\[url[\=\]]https?:\/\/hdbits\.o[^\]]+)([^\[]+)(\[\/url\])?", desc, flags=re.IGNORECASE)
        if url_tags:
            for url_tag in url_tags:
                url_tag = ''.join(url_tag)
                url_tag_removed = re.sub(r"(\[url[\=\]]https?:\/\/passthepopcorn\.m[^\]]+])", "", url_tag, flags=re.IGNORECASE)
                url_tag_removed = re.sub(r"(\[url[\=\]]https?:\/\/hdbits\.o[^\]]+])", "", url_tag_removed, flags=re.IGNORECASE)
                url_tag_removed = url_tag_removed.replace("[/url]", "")
                desc = desc.replace(url_tag, url_tag_removed)

        # Remove links to PTP/HDB
        desc = desc.replace('http://passthepopcorn.me', 'PTP').replace('https://passthepopcorn.me', 'PTP')
        desc = desc.replace('http://hdbits.org', 'HDB').replace('https://hdbits.org', 'HDB')

        # Catch Stray Images and Prepare Image List
        imagelist = []
        excluded_urls = set()

        source_encode_comps = re.findall(r"\[comparison=Source, Encode\][\s\S]*", desc, flags=re.IGNORECASE)
        source_vs_encode_sections = re.findall(r"Source Vs Encode:[\s\S]*", desc, flags=re.IGNORECASE)
        specific_cases = source_encode_comps + source_vs_encode_sections

        # Extract URLs and update excluded_urls
        for block in specific_cases:
            urls = re.findall(r"(https?:\/\/[^\s\[\]]+\.(?:png|jpg))", block, flags=re.IGNORECASE)
            excluded_urls.update(urls)
            desc = desc.replace(block, '')

        # General [comparison=...] handling
        comps = re.findall(r"\[comparison=[\s\S]*?\[\/comparison\]", desc, flags=re.IGNORECASE)
        hides = re.findall(r"\[hide[\s\S]*?\[\/hide\]", desc, flags=re.IGNORECASE)
        comps.extend(hides)
        nocomp = desc

        # Exclude URLs from exculed array fom `nocomp`
        for url in excluded_urls:
            nocomp = nocomp.replace(url, '')

        comp_placeholders = []

        # Replace comparison/hide tags with placeholder because sometimes uploaders use comp images as loose images
        for i, comp in enumerate(comps):
            nocomp = nocomp.replace(comp, '')
            desc = desc.replace(comp, f"COMPARISON_PLACEHOLDER-{i} ")
            comp_placeholders.append(comp)

        # as the name implies, protect image links while doing regex things
        def protect_links(desc):
            links = re.findall(r'https?://\S+', desc)
            for i, link in enumerate(links):
                desc = desc.replace(link, f'__LINK_PLACEHOLDER_{i}__')
            return desc, links

        def restore_links(desc, links):
            for i, link in enumerate(links):
                desc = desc.replace(f'__LINK_PLACEHOLDER_{i}__', link)
            return desc

        links = []

        if is_disc == "DVD":
            desc = re.sub(r"\[mediainfo\][\s\S]*?\[\/mediainfo\]", "", desc)

        elif is_disc == "BDMV":
            desc = re.sub(r"\[mediainfo\][\s\S]*?\[\/mediainfo\]", "", desc)
            desc = re.sub(r"DISC INFO:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Disc Title:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Disc Size:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Protection:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"BD-Java:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"BDInfo:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"PLAYLIST REPORT:[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Name:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Length:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Size:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Total Bitrate:[\s\S]*?(\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"VIDEO:[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"AUDIO:[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"SUBTITLES:[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Codec\s+Bitrate\s+Description[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"Codec\s+Language\s+Bitrate\s+Description[\s\S]*?(?=\n\n|$)", "", desc, flags=re.IGNORECASE)

        else:
            desc = re.sub(r"\[mediainfo\][\s\S]*?\[\/mediainfo\]", "", desc)
            desc = re.sub(r"(^general\nunique)(.*?)^$", "", desc, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
            desc = re.sub(r"(^general\ncomplete)(.*?)^$", "", desc, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
            desc = re.sub(r"(^(Format[\s]{2,}:))(.*?)^$", "", desc, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
            desc = re.sub(r"(^(video|audio|text)( #\d+)?\nid)(.*?)^$", "", desc, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
            desc = re.sub(r"(^(menu)( #\d+)?\n)(.*?)^$", "", f"{desc}\n\n", flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)

            desc, links = protect_links(desc)

            desc = re.sub(
                r"\[b\](.*?)(Matroska|DTS|AVC|x264|Progressive|23\.976 fps|16:9|[0-9]+x[0-9]+|[0-9]+ MiB|[0-9]+ Kbps|[0-9]+ bits|cabac=.*?/ aq=.*?|\d+\.\d+ Mbps)\[/b\]",
                "",
                desc,
                flags=re.IGNORECASE | re.DOTALL,
            )
            desc = re.sub(
                r"(Matroska|DTS|AVC|x264|Progressive|23\.976 fps|16:9|[0-9]+x[0-9]+|[0-9]+ MiB|[0-9]+ Kbps|[0-9]+ bits|cabac=.*?/ aq=.*?|\d+\.\d+ Mbps|[0-9]+\s+channels|[0-9]+\.[0-9]+\s+KHz|[0-9]+ KHz|[0-9]+\s+bits)",
                "",
                desc,
                flags=re.IGNORECASE | re.DOTALL,
            )
            desc = re.sub(
                r"\[u\](Format|Bitrate|Channels|Sampling Rate|Resolution):\[/u\]\s*\d*.*?",
                "",
                desc,
                flags=re.IGNORECASE,
            )
            desc = re.sub(
                r"^\s*\d+\s*(channels|KHz|bits)\s*$",
                "",
                desc,
                flags=re.MULTILINE | re.IGNORECASE,
            )

            desc = re.sub(r"^\s+$", "", desc, flags=re.MULTILINE)
            desc = re.sub(r"\n{2,}", "\n", desc)

        desc = restore_links(desc, links)

        # Convert Quote tags:
        desc = re.sub(r"\[quote.*?\]", "[code]", desc)
        desc = desc.replace("[/quote]", "[/code]")

        # Remove Alignments:
        desc = re.sub(r"\[align=.*?\]", "", desc)
        desc = desc.replace("[/align]", "")

        # Remove size tags
        desc = re.sub(r"\[size=.*?\]", "", desc)
        desc = desc.replace("[/size]", "")

        # Remove Videos
        desc = re.sub(r"\[video\][\s\S]*?\[\/video\]", "", desc)

        # Remove Staff tags
        desc = re.sub(r"\[staff[\s\S]*?\[\/staff\]", "", desc)

        # Remove Movie/Person/User/hr/Indent
        remove_list = [
            '[movie]', '[/movie]',
            '[artist]', '[/artist]',
            '[user]', '[/user]',
            '[indent]', '[/indent]',
            '[size]', '[/size]',
            '[hr]'
        ]
        for each in remove_list:
            desc = desc.replace(each, '')

        # Remove Images in IMG tags
        desc = re.sub(r"\[img\][\s\S]*?\[\/img\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[img=[\s\S]*?\]", "", desc, flags=re.IGNORECASE)

        # Extract loose images and add to imagelist as dictionaries
        loose_images = re.findall(r"(https?:\/\/[^\s\[\]]+\.(?:png|jpg))", nocomp, flags=re.IGNORECASE)
        for img_url in loose_images:
            if img_url not in excluded_urls:  # Only include URLs not part of excluded sections
                image_dict = {
                    'img_url': img_url,
                    'raw_url': img_url,
                    'web_url': img_url
                }
                imagelist.append(image_dict)
                desc = desc.replace(img_url, '')

        # Re-place comparisons
        for i, comp in enumerate(comp_placeholders):
            comp = re.sub(r"\[\/?img[\s\S]*?\]", "", comp, flags=re.IGNORECASE)
            desc = desc.replace(f"COMPARISON_PLACEHOLDER-{i} ", comp)

        # Convert hides with multiple images to comparison
        desc = self.convert_collapse_to_comparison(desc, "hide", hides)

        # Strip blank lines:
        desc = desc.strip('\n')
        desc = re.sub("\n\n+", "\n\n", desc)
        while desc.startswith('\n'):
            desc = desc.replace('\n', '', 1)
        desc = desc.strip('\n')

        if desc.replace('\n', '').strip() == '':
            console.print("[yellow]Description is empty after cleaning.")
            return "", imagelist

        return desc, imagelist

    def clean_unit3d_description(self, desc, site):
        # Unescape HTML
        desc = html.unescape(desc)
        # Replace carriage returns with newlines
        desc = desc.replace('\r\n', '\n')

        # Remove links to site
        site_netloc = urllib.parse.urlparse(site).netloc
        site_regex = rf"(\[url[\=\]]https?:\/\/{site_netloc}/[^\]]+])([^\[]+)(\[\/url\])?"
        site_url_tags = re.findall(site_regex, desc)
        if site_url_tags:
            for site_url_tag in site_url_tags:
                site_url_tag = ''.join(site_url_tag)
                url_tag_regex = rf"(\[url[\=\]]https?:\/\/{site_netloc}[^\]]+])"
                url_tag_removed = re.sub(url_tag_regex, "", site_url_tag)
                url_tag_removed = url_tag_removed.replace("[/url]", "")
                desc = desc.replace(site_url_tag, url_tag_removed)

        desc = desc.replace(site_netloc, site_netloc.split('.')[0])

        # Temporarily hide spoiler tags
        spoilers = re.findall(r"\[spoiler[\s\S]*?\[\/spoiler\]", desc)
        nospoil = desc
        spoiler_placeholders = []
        for i in range(len(spoilers)):
            nospoil = nospoil.replace(spoilers[i], '')
            desc = desc.replace(spoilers[i], f"SPOILER_PLACEHOLDER-{i} ")
            spoiler_placeholders.append(spoilers[i])

        # Get Images from [img] tags and remove them from the description
        imagelist = []
        img_tags = re.findall(r"\[img[^\]]*\](.*?)\[/img\]", desc, re.IGNORECASE)
        if img_tags:
            for img_url in img_tags:
                image_dict = {
                    'img_url': img_url.strip(),
                    'raw_url': img_url.strip(),
                    'web_url': img_url.strip(),
                }
                imagelist.append(image_dict)
                # Remove the [img] tag and its contents from the description
                desc = re.sub(rf"\[img[^\]]*\]{re.escape(img_url)}\[/img\]", '', desc, flags=re.IGNORECASE)

        # Now, remove matching URLs from [URL] tags
        for img in imagelist:
            img_url = re.escape(img['img_url'])
            desc = re.sub(rf"\[URL={img_url}\]\[/URL\]", '', desc, flags=re.IGNORECASE)
            desc = re.sub(rf"\[URL={img_url}\]\[img[^\]]*\]{img_url}\[/img\]\[/URL\]", '', desc, flags=re.IGNORECASE)

        # Filter out bot images from imagelist
        bot_image_urls = [
            "https://blutopia.xyz/favicon.ico",  # Example bot image URL
            "https://i.ibb.co/2NVWb0c/uploadrr.webp",
            "https://blutopia/favicon.ico",
            "https://ptpimg.me/606tk4.png",
            # Add any other known bot image URLs here
        ]
        imagelist = [
            img for img in imagelist
            if img['img_url'] not in bot_image_urls and not re.search(r'thumbs', img['img_url'], re.IGNORECASE)
        ]

        # Restore spoiler tags
        if spoiler_placeholders:
            for i, spoiler in enumerate(spoiler_placeholders):
                desc = desc.replace(f"SPOILER_PLACEHOLDER-{i} ", spoiler)

        # Check for and clean up empty [center] tags
        centers = re.findall(r"\[center[\s\S]*?\[\/center\]", desc)
        if centers:
            for center in centers:
                # If [center] contains only whitespace or empty tags, remove the entire tag
                cleaned_center = re.sub(r'\[center\]\s*\[\/center\]', '', center)
                cleaned_center = re.sub(r'\[center\]\s+', '[center]', cleaned_center)
                cleaned_center = re.sub(r'\s*\[\/center\]', '[/center]', cleaned_center)
                if cleaned_center == '[center][/center]':
                    desc = desc.replace(center, '')
                else:
                    desc = desc.replace(center, cleaned_center.strip())

        # Remove bot signatures
        bot_signature_regex = r"""
            \[center\]\s*\[img=\d+\]https:\/\/blutopia\.xyz\/favicon\.ico\[\/img\]\s*\[b\]
            Uploaded\sUsing\s\[url=https:\/\/github\.com\/HDInnovations\/UNIT3D\]UNIT3D\[\/url\]\s
            Auto\sUploader\[\/b\]\s*\[img=\d+\]https:\/\/blutopia\.xyz\/favicon\.ico\[\/img\]\s*\[\/center\]|
            \[center\]\s*\[b\]Uploaded\sUsing\s\[url=https:\/\/github\.com\/HDInnovations\/UNIT3D\]UNIT3D\[\/url\]
            \sAuto\sUploader\[\/b\]\s*\[\/center\]|
            \[center\]\[url=https:\/\/github\.com\/z-ink\/uploadrr\]\[img=\d+\]https:\/\/i\.ibb\.co\/2NVWb0c\/uploadrr\.webp\[\/img\]\[\/url\]\[\/center\]|
            \n\[center\]\[url=https:\/\/github\.com\/edge20200\/Only-Uploader\]Powered\sby\s
            Only-Uploader\[\/url\]\[\/center\]
        """
        desc = re.sub(bot_signature_regex, "", desc, flags=re.IGNORECASE | re.VERBOSE)
        desc = re.sub(r"\[center\].*Created by (L4G|Audionut)('?s)? Upload Assistant.*\[\/center\]", "", desc, flags=re.IGNORECASE)

        # Remove leftover [img] or [URL] tags in the description
        desc = re.sub(r"\[img\][\s\S]*?\[\/img\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[img=[\s\S]*?\]", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\[URL=[\s\S]*?\]\[\/URL\]", "", desc, flags=re.IGNORECASE)

        # Strip trailing whitespace and newlines:
        desc = desc.rstrip()

        if desc.replace('\n', '') == '':
            return "", imagelist
        return desc, imagelist

    def convert_pre_to_code(self, desc):
        desc = desc.replace('[pre]', '[code]')
        desc = desc.replace('[/pre]', '[/code]')
        return desc

    def convert_hide_to_spoiler(self, desc):
        desc = desc.replace('[hide', '[spoiler')
        desc = desc.replace('[/hide]', '[/spoiler]')
        return desc

    def convert_spoiler_to_hide(self, desc):
        desc = desc.replace('[spoiler', '[hide')
        desc = desc.replace('[/spoiler]', '[/hide]')
        return desc

    def remove_spoiler(self, desc):
        desc = re.sub(r"\[\/?spoiler[\s\S]*?\]", "", desc, flags=re.IGNORECASE)
        return desc

    def convert_spoiler_to_code(self, desc):
        desc = desc.replace('[spoiler', '[code')
        desc = desc.replace('[/spoiler]', '[/code]')
        return desc

    def convert_code_to_quote(self, desc):
        desc = desc.replace('[code', '[quote')
        desc = desc.replace('[/code]', '[/quote]')
        return desc

    def convert_comparison_to_collapse(self, desc, max_width):
        comparisons = re.findall(r"\[comparison=[\s\S]*?\[\/comparison\]", desc)
        for comp in comparisons:
            line = []
            output = []
            comp_sources = comp.split(']', 1)[0].replace('[comparison=', '').replace(' ', '').split(',')
            comp_images = comp.split(']', 1)[1].replace('[/comparison]', '').replace(',', '\n').replace(' ', '\n')
            comp_images = re.findall(r"(https?:\/\/.*\.(?:png|jpg))", comp_images, flags=re.IGNORECASE)
            screens_per_line = len(comp_sources)
            img_size = int(max_width / screens_per_line)
            if img_size > 350:
                img_size = 350
            for img in comp_images:
                img = img.strip()
                if img != "":
                    bb = f"[url={img}][img={img_size}]{img}[/img][/url]"
                    line.append(bb)
                    if len(line) == screens_per_line:
                        output.append(''.join(line))
                        line = []
            output = '\n'.join(output)
            new_bbcode = f"[spoiler={' vs '.join(comp_sources)}][center]{' | '.join(comp_sources)}[/center]\n{output}[/spoiler]"
            desc = desc.replace(comp, new_bbcode)
        return desc

    def convert_comparison_to_centered(self, desc, max_width):
        comparisons = re.findall(r"\[comparison=[\s\S]*?\[\/comparison\]", desc)
        for comp in comparisons:
            line = []
            output = []
            comp_sources = comp.split(']', 1)[0].replace('[comparison=', '').strip()
            comp_sources = re.split(r"\s*,\s*", comp_sources)
            comp_images = comp.split(']', 1)[1].replace('[/comparison]', '').replace(',', '\n').replace(' ', '\n')
            comp_images = re.findall(r"(https?:\/\/.*\.(?:png|jpg))", comp_images, flags=re.IGNORECASE)
            screens_per_line = len(comp_sources)
            img_size = int(max_width / screens_per_line)
            if img_size > 350:
                img_size = 350
            for img in comp_images:
                img = img.strip()
                if img != "":
                    bb = f"[url={img}][img={img_size}]{img}[/img][/url]"
                    line.append(bb)
                    if len(line) == screens_per_line:
                        output.append(''.join(line))
                        line = []
            output = '\n'.join(output)
            new_bbcode = f"[center]{' | '.join(comp_sources)}\n{output}[/center]"
            desc = desc.replace(comp, new_bbcode)
        return desc

    def convert_collapse_to_comparison(self, desc, spoiler_hide, collapses):
        # Convert Comparison spoilers to [comparison=]
        if collapses != []:
            for i in range(len(collapses)):
                tag = collapses[i]
                images = re.findall(r"\[img[\s\S]*?\[\/img\]", tag, flags=re.IGNORECASE)
                if len(images) >= 6:
                    comp_images = []
                    final_sources = []
                    for image in images:
                        image_url = re.sub(r"\[img[\s\S]*\]", "", image.replace('[/img]', ''), flags=re.IGNORECASE)
                        comp_images.append(image_url)
                    if spoiler_hide == "spoiler":
                        sources = re.match(r"\[spoiler[\s\S]*?\]", tag)[0].replace('[spoiler=', '')[:-1]
                    elif spoiler_hide == "hide":
                        sources = re.match(r"\[hide[\s\S]*?\]", tag)[0].replace('[hide=', '')[:-1]
                    sources = re.sub("comparison", "", sources, flags=re.IGNORECASE)
                    for each in ['vs', ',', '|']:
                        sources = sources.split(each)
                        sources = "$".join(sources)
                    sources = sources.split("$")
                    for source in sources:
                        final_sources.append(source.strip())
                    comp_images = '\n'.join(comp_images)
                    final_sources = ', '.join(final_sources)
                    spoil2comp = f"[comparison={final_sources}]{comp_images}[/comparison]"
                    desc = desc.replace(tag, spoil2comp)
        return desc
