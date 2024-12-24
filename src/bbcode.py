import re
import html
import urllib.parse
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
            "https://github.com/edge20200/Only-Uploader"
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
            \[center\]\[url=https:\/\/github\.com\/z-ink\/uploadrr\]\[img=\d+\]https:\/\/i\.ibb\.co\/2NVWb0c\/uploadrr\.webp\[\/img\]\[\/url\]\[\/center\]
        """
        desc = re.sub(bot_signature_regex, "", desc, flags=re.IGNORECASE | re.VERBOSE)
        desc = re.sub(r"\[center\].*Created by L4G's Upload Assistant.*\[\/center\]", "", desc, flags=re.IGNORECASE)

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
