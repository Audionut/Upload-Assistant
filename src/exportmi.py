from src.console import console
from pymediainfo import MediaInfo
import json
import os


async def mi_resolution(res, guess, width, scan, height, actual_height):
    res_map = {
        "3840x2160p": "2160p", "2160p": "2160p",
        "2560x1440p": "1440p", "1440p": "1440p",
        "1920x1080p": "1080p", "1080p": "1080p",
        "1920x1080i": "1080i", "1080i": "1080i",
        "1280x720p": "720p", "720p": "720p",
        "1280x540p": "720p", "1280x576p": "720p",
        "1024x576p": "576p", "576p": "576p",
        "1024x576i": "576i", "576i": "576i",
        "960x540p": "540p", "540p": "540p",
        "960x540i": "540i", "540i": "540i",
        "854x480p": "480p", "480p": "480p",
        "854x480i": "480i", "480i": "480i",
        "720x576p": "576p", "576p": "576p",
        "720x576i": "576i", "576i": "576i",
        "720x480p": "480p", "480p": "480p",
        "720x480i": "480i", "480i": "480i",
        "15360x8640p": "8640p", "8640p": "8640p",
        "7680x4320p": "4320p", "4320p": "4320p",
        "OTHER": "OTHER"}
    resolution = res_map.get(res, None)
    if resolution is None:
        try:
            resolution = guess['screen_size']
            # Check if the resolution from guess exists in our map
            if resolution not in res_map:
                # If not in the map, use width-based mapping
                width_map = {
                    '3840p': '2160p',
                    '2560p': '1550p',
                    '1920p': '1080p',
                    '1920i': '1080i',
                    '1280p': '720p',
                    '1024p': '576p',
                    '1024i': '576i',
                    '960p': '540p',
                    '960i': '540i',
                    '854p': '480p',
                    '854i': '480i',
                    '720p': '576p',
                    '720i': '576i',
                    '15360p': '4320p',
                    'OTHERp': 'OTHER'
                }
                resolution = width_map.get(f"{width}{scan}", "OTHER")
        except Exception:
            # If we can't get from guess, use width-based mapping
            width_map = {
                '3840p': '2160p',
                '2560p': '1550p',
                '1920p': '1080p',
                '1920i': '1080i',
                '1280p': '720p',
                '1024p': '576p',
                '1024i': '576i',
                '960p': '540p',
                '960i': '540i',
                '854p': '480p',
                '854i': '480i',
                '720p': '576p',
                '720i': '576i',
                '15360p': '4320p',
                'OTHERp': 'OTHER'
            }
            resolution = width_map.get(f"{width}{scan}", "OTHER")

    # Final check to ensure we have a valid resolution
    if resolution not in res_map:
        resolution = "OTHER"

    return resolution


async def exportInfo(video, isdir, folder_id, base_dir, export_text):
    def filter_mediainfo(data):
        filtered = {
            "creatingLibrary": data.get("creatingLibrary"),
            "media": {
                "@ref": data["media"]["@ref"],
                "track": []
            }
        }

        for track in data["media"]["track"]:
            if track["@type"] == "General":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "UniqueID": track.get("UniqueID", {}),
                    "VideoCount": track.get("VideoCount", {}),
                    "AudioCount": track.get("AudioCount", {}),
                    "TextCount": track.get("TextCount", {}),
                    "MenuCount": track.get("MenuCount", {}),
                    "FileExtension": track.get("FileExtension", {}),
                    "Format": track.get("Format", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "FileSize": track.get("FileSize", {}),
                    "Duration": track.get("Duration", {}),
                    "OverallBitRate": track.get("OverallBitRate", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "IsStreamable": track.get("IsStreamable", {}),
                    "File_Created_Date": track.get("File_Created_Date", {}),
                    "File_Created_Date_Local": track.get("File_Created_Date_Local", {}),
                    "File_Modified_Date": track.get("File_Modified_Date", {}),
                    "File_Modified_Date_Local": track.get("File_Modified_Date_Local", {}),
                    "Encoded_Application": track.get("Encoded_Application", {}),
                    "Encoded_Library": track.get("Encoded_Library", {}),
                })
            elif track["@type"] == "Video":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "Format_Profile": track.get("Format_Profile", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "Format_Level": track.get("Format_Level", {}),
                    "Format_Tier": track.get("Format_Tier", {}),
                    "HDR_Format": track.get("HDR_Format", {}),
                    "HDR_Format_Version": track.get("HDR_Format_Version", {}),
                    "HDR_Format_String": track.get("HDR_Format_String", {}),
                    "HDR_Format_Profile": track.get("HDR_Format_Profile", {}),
                    "HDR_Format_Level": track.get("HDR_Format_Level", {}),
                    "HDR_Format_Settings": track.get("HDR_Format_Settings", {}),
                    "HDR_Format_Compression": track.get("HDR_Format_Compression", {}),
                    "HDR_Format_Compatibility": track.get("HDR_Format_Compatibility", {}),
                    "CodecID": track.get("CodecID", {}),
                    "CodecID_Hint": track.get("CodecID_Hint", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate": track.get("BitRate", {}),
                    "Width": track.get("Width", {}),
                    "Height": track.get("Height", {}),
                    "Stored_Height": track.get("Stored_Height", {}),
                    "Sampled_Width": track.get("Sampled_Width", {}),
                    "Sampled_Height": track.get("Sampled_Height", {}),
                    "PixelAspectRatio": track.get("PixelAspectRatio", {}),
                    "DisplayAspectRatio": track.get("DisplayAspectRatio", {}),
                    "FrameRate_Mode": track.get("FrameRate_Mode", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameRate_Num": track.get("FrameRate_Num", {}),
                    "FrameRate_Den": track.get("FrameRate_Den", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "Standard": track.get("Standard", {}),
                    "ColorSpace": track.get("ColorSpace", {}),
                    "ChromaSubsampling": track.get("ChromaSubsampling", {}),
                    "ChromaSubsampling_Position": track.get("ChromaSubsampling_Position", {}),
                    "BitDepth": track.get("BitDepth", {}),
                    "ScanType": track.get("ScanType", {}),
                    "ScanOrder": track.get("ScanOrder", {}),
                    "Delay": track.get("Delay", {}),
                    "Delay_Source": track.get("Delay_Source", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Language": track.get("Language", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                    "colour_description_present": track.get("colour_description_present", {}),
                    "colour_description_present_Source": track.get("colour_description_present_Source", {}),
                    "colour_range": track.get("colour_range", {}),
                    "colour_range_Source": track.get("colour_range_Source", {}),
                    "colour_primaries": track.get("colour_primaries", {}),
                    "colour_primaries_Source": track.get("colour_primaries_Source", {}),
                    "transfer_characteristics": track.get("transfer_characteristics", {}),
                    "transfer_characteristics_Source": track.get("transfer_characteristics_Source", {}),
                    "transfer_characteristics_Original": track.get("transfer_characteristics_Original", {}),
                    "matrix_coefficients": track.get("matrix_coefficients", {}),
                    "matrix_coefficients_Source": track.get("matrix_coefficients_Source", {}),
                    "MasteringDisplay_ColorPrimaries": track.get("MasteringDisplay_ColorPrimaries", {}),
                    "MasteringDisplay_ColorPrimaries_Source": track.get("MasteringDisplay_ColorPrimaries_Source", {}),
                    "MasteringDisplay_Luminance": track.get("MasteringDisplay_Luminance", {}),
                    "MasteringDisplay_Luminance_Source": track.get("MasteringDisplay_Luminance_Source", {}),
                    "MaxCLL": track.get("MaxCLL", {}),
                    "MaxCLL_Source": track.get("MaxCLL_Source", {}),
                    "MaxFALL": track.get("MaxFALL", {}),
                    "MaxFALL_Source": track.get("MaxFALL_Source", {}),
                    "Encoded_Library_Settings": track.get("Encoded_Library_Settings", {}),
                })
            elif track["@type"] == "Audio":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "Format_Version": track.get("Format_Version", {}),
                    "Format_Profile": track.get("Format_Profile", {}),
                    "Format_Settings": track.get("Format_Settings", {}),
                    "Format_Commercial_IfAny": track.get("Format_Commercial_IfAny", {}),
                    "Format_Settings_Endianness": track.get("Format_Settings_Endianness", {}),
                    "Format_AdditionalFeatures": track.get("Format_AdditionalFeatures", {}),
                    "CodecID": track.get("CodecID", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate_Mode": track.get("BitRate_Mode", {}),
                    "BitRate": track.get("BitRate", {}),
                    "Channels": track.get("Channels", {}),
                    "ChannelPositions": track.get("ChannelPositions", {}),
                    "ChannelLayout": track.get("ChannelLayout", {}),
                    "Channels_Original": track.get("Channels_Original", {}),
                    "ChannelLayout_Original": track.get("ChannelLayout_Original", {}),
                    "SamplesPerFrame": track.get("SamplesPerFrame", {}),
                    "SamplingRate": track.get("SamplingRate", {}),
                    "SamplingCount": track.get("SamplingCount", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "Compression_Mode": track.get("Compression_Mode", {}),
                    "Delay": track.get("Delay", {}),
                    "Delay_Source": track.get("Delay_Source", {}),
                    "Video_Delay": track.get("Video_Delay", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Title": track.get("Title", {}),
                    "Language": track.get("Language", {}),
                    "ServiceKind": track.get("ServiceKind", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                    "extra": track.get("extra", {}),
                })
            elif track["@type"] == "Text":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "@typeorder": track.get("@typeorder", {}),
                    "StreamOrder": track.get("StreamOrder", {}),
                    "ID": track.get("ID", {}),
                    "UniqueID": track.get("UniqueID", {}),
                    "Format": track.get("Format", {}),
                    "CodecID": track.get("CodecID", {}),
                    "Duration": track.get("Duration", {}),
                    "BitRate": track.get("BitRate", {}),
                    "FrameRate": track.get("FrameRate", {}),
                    "FrameCount": track.get("FrameCount", {}),
                    "ElementCount": track.get("ElementCount", {}),
                    "StreamSize": track.get("StreamSize", {}),
                    "Title": track.get("Title", {}),
                    "Language": track.get("Language", {}),
                    "Default": track.get("Default", {}),
                    "Forced": track.get("Forced", {}),
                })
            elif track["@type"] == "Menu":
                filtered["media"]["track"].append({
                    "@type": track["@type"],
                    "extra": track.get("extra", {}),
                })
        return filtered

    if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt") and export_text:
        console.print("[bold yellow]Exporting MediaInfo...")
        if not isdir:
            os.chdir(os.path.dirname(video))
        media_info = MediaInfo.parse(video, output="STRING", full=False)
        filtered_media_info = "\n".join(
            line for line in media_info.splitlines()
            if not line.strip().startswith("ReportBy") and not line.strip().startswith("Report created by ")
        )
        with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8') as export:
            export.write(filtered_media_info.replace(video, os.path.basename(video)))
        with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8') as export_cleanpath:
            export_cleanpath.write(filtered_media_info.replace(video, os.path.basename(video)))
        console.print("[bold green]MediaInfo Exported.")

    if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MediaInfo.json"):
        media_info_json = MediaInfo.parse(video, output="JSON")
        media_info_dict = json.loads(media_info_json)
        filtered_info = filter_mediainfo(media_info_dict)
        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'w', encoding='utf-8') as export:
            json.dump(filtered_info, export, indent=4)

    with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'r', encoding='utf-8') as f:
        mi = json.load(f)

    return mi


async def combine_dvd_mediainfo(vob_mi, ifo_mi, output_path, disc_size=None):
    # Parse the MediaInfo texts into structured sections
    def parse_mediainfo(mi_text):
        sections = {}
        current_section = None
        current_content = []

        lines = mi_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Check if this is a section header
            if ":" not in line and line and not line.startswith(" "):
                if current_section:
                    # Store previous section
                    sections[current_section] = current_content

                # Start new section
                current_section = line
                current_content = []
            else:
                # Add content to current section
                if current_section:
                    current_content.append(line)

            i += 1

        # Add the last section
        if current_section:
            sections[current_section] = current_content

        return sections

    # Parse both MediaInfo outputs
    vob_sections = parse_mediainfo(vob_mi)
    ifo_sections = parse_mediainfo(ifo_mi)

    # Merge sections
    merged_sections = {}

    # Special handling for General section - use IFO as primary
    if "General" in ifo_sections:
        merged_sections["General"] = ifo_sections["General"].copy()

        # Find and modify File size line (don't remove it)
        if disc_size is not None:
            for i, line in enumerate(merged_sections["General"]):
                if line.strip().startswith("File size"):
                    # Replace the File size line with the disc size value
                    merged_sections["General"][i] = f"File size                                : {disc_size} GiB"
                    break
            # If no File size found, add it
            if not any(line.strip().startswith("File size") for line in merged_sections["General"]):
                merged_sections["General"].append(f"File size                                : {disc_size} GiB")

        # Always take "Overall bit rate" from VOB if available
        if "General" in vob_sections:
            # Find Overall bit rate in VOB
            overall_bit_rate = None
            for line in vob_sections["General"]:
                if line.strip().startswith("Overall bit rate"):
                    overall_bit_rate = line
                    break

            # Add Overall bit rate from VOB if found
            if overall_bit_rate:
                # First remove any existing Overall bit rate
                merged_sections["General"] = [line for line in merged_sections["General"]
                                              if not line.strip().startswith("Overall bit rate")]
                # Then add the VOB version
                merged_sections["General"].append(overall_bit_rate)

            # Add other VOB General info that's not in IFO
            ifo_lines = [line.split(':', 1)[0].strip() for line in merged_sections["General"]]
            for vob_line in vob_sections["General"]:
                if not vob_line:
                    continue

                if ':' in vob_line:
                    vob_key = vob_line.split(':', 1)[0].strip()
                    # Skip File size as we've already handled it
                    if vob_key not in ifo_lines and vob_key != "File size":
                        merged_sections["General"].append(vob_line)

    # For VOB General section when no IFO is available:
    elif "General" in vob_sections:
        # If no IFO General section, use VOB
        merged_sections["General"] = vob_sections["General"].copy()

        # Update File size with disc size value if provided
        if disc_size is not None:
            for i, line in enumerate(merged_sections["General"]):
                if line.strip().startswith("File size"):
                    # Replace the File size line with the disc size value
                    merged_sections["General"][i] = f"File size                                : {disc_size} GiB"
                    break
            # If no File size found, add it
            if not any(line.strip().startswith("File size") for line in merged_sections["General"]):
                merged_sections["General"].append(f"File size                                : {disc_size} GiB")

    # For all other sections, add VOB sections first
    for section, content in vob_sections.items():
        if section != "General":  # Skip General section as it's handled above
            merged_sections[section] = content.copy()

    # Then add IFO information not present in VOB for non-General sections
    for section, ifo_content in ifo_sections.items():
        if section == "General":
            continue  # Skip General section as it's handled above

        # Extract the base section name (e.g., "Audio #1" -> "Audio")
        base_section = section.split(' #')[0] if ' #' in section else section
        section_num = section.split(' #')[1] if ' #' in section else ""

        if section in merged_sections:
            # Section exists in both - add lines from IFO that aren't in VOB
            vob_content = merged_sections[section]
            vob_lines = [line.split(':', 1)[0].strip() for line in vob_content]

            for ifo_line in ifo_content:
                if not ifo_line:
                    continue

                # Only add lines that aren't already present
                if ':' in ifo_line:
                    ifo_key = ifo_line.split(':', 1)[0].strip()
                    if ifo_key not in vob_lines:
                        merged_sections[section].append(ifo_line)
        elif section_num and any(s.startswith(f"{base_section} #{section_num}") for s in merged_sections.keys()):
            # Find the matching section number in VOB
            matching_section = next(s for s in merged_sections.keys() if s.startswith(f"{base_section} #{section_num}"))

            # Add lines from IFO that aren't in the matching VOB section
            vob_content = merged_sections[matching_section]
            vob_lines = [line.split(':', 1)[0].strip() for line in vob_content]

            for ifo_line in ifo_content:
                if not ifo_line:
                    continue

                # Only add lines that aren't already present
                if ':' in ifo_line:
                    ifo_key = ifo_line.split(':', 1)[0].strip()
                    if ifo_key not in vob_lines:
                        merged_sections[matching_section].append(ifo_line)
        else:
            # Section only exists in IFO - add it to merged_sections
            merged_sections[section] = ifo_content.copy()

    # Build the combined MediaInfo text
    combined_text = []

    # Standard section order
    section_order = [
        "General",
        "Video"
    ]

    # Add audio, text, and other sections in order
    audio_sections = sorted([s for s in merged_sections.keys() if s.startswith("Audio")])
    text_sections = sorted([s for s in merged_sections.keys() if s.startswith("Text")])

    section_order.extend(audio_sections)
    section_order.extend(text_sections)
    section_order.append("Menu")

    # Other sections not in standard order
    other_sections = [s for s in merged_sections.keys() if s not in section_order and s in merged_sections]
    section_order.extend(other_sections)

    # Build output text in order
    for section in section_order:
        if section in merged_sections:
            combined_text.append(section)
            combined_text.extend(merged_sections[section])
            combined_text.append("")  # Empty line between sections

    # Write to file
    with open(output_path, 'w', newline="", encoding='utf-8') as f:
        f.write('\n'.join(combined_text))

    return '\n'.join(combined_text)


async def combine_hddvd_mediainfo(evo_mediainfo_list, total_size, duration):
    # Parse MediaInfo texts into structured sections
    def parse_mediainfo(mi_text):
        sections = {}
        current_section = None
        current_content = []

        lines = mi_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Check if this is a section header
            if ":" not in line and line and not line.startswith(" "):
                if current_section:
                    # Store previous section
                    sections[current_section] = current_content

                # Start new section
                current_section = line
                current_content = []
            else:
                # Add content to current section
                if current_section:
                    current_content.append(line)

            i += 1

        # Add the last section
        if current_section:
            sections[current_section] = current_content

        return sections

    # Use the first EVO file's MediaInfo as base
    first_mi = evo_mediainfo_list[0]['mediainfo']

    # Parse sections from base MediaInfo
    base_sections = parse_mediainfo(first_mi)

    # Parse each additional EVO MediaInfo
    additional_sections = []
    for evo_data in evo_mediainfo_list[1:]:
        additional_sections.append(parse_mediainfo(evo_data['mediainfo']))

    # Modify the General section to use the total size and duration
    if "General" in base_sections:
        # Replace file size with total size
        base_sections["General"] = [line for line in base_sections["General"]
                                    if not line.strip().startswith("File size")]
        base_sections["General"].append(f"File size                                : {total_size / (1024 ** 3):.2f} GiB")

        # Replace duration with the playlist duration
        base_sections["General"] = [line for line in base_sections["General"]
                                    if not line.strip().startswith("Duration")]
        # Format duration for MediaInfo style
        formatted_duration = duration
        base_sections["General"].append(f"Duration                                 : {formatted_duration}")

    # Add unique audio/subtitle tracks from other EVO files
    for sections in additional_sections:
        for section, content in sections.items():
            # Skip General section as it's already handled
            if section == "General" or section == "Video":
                continue

            # If it's a new section type, add it
            if section not in base_sections:
                base_sections[section] = content
                continue

            # For existing section types, check if it's a new instance
            if section.startswith("Audio") or section.startswith("Text"):
                # Extract ID or other uniquely identifying information
                section_id = None
                for line in content:
                    if line.strip().startswith("ID"):
                        section_id = line
                        break

                # Check if this ID already exists in base_sections
                exists = False
                for existing_content in base_sections.values():
                    for line in existing_content:
                        if line == section_id:
                            exists = True
                            break
                    if exists:
                        break

                # If it's a new ID, create a new section
                if not exists and section_id:
                    # Find the highest existing section number
                    section_prefix = section.split(" #")[0]
                    existing_sections = [s for s in base_sections.keys() if s.startswith(section_prefix)]
                    max_num = 0
                    for s in existing_sections:
                        try:
                            num = int(s.split(" #")[1])
                            max_num = max(max_num, num)
                        except (IndexError, ValueError):
                            pass

                    # Create a new section with the next number
                    new_section = f"{section_prefix} #{max_num + 1}"
                    base_sections[new_section] = content

    for section_name, content in list(base_sections.items()):
        if section_name.startswith("Audio"):
            # Check if the section has a Maximum bit rate but no Bit rate
            has_max_bitrate = False
            max_bitrate_value = None
            has_bitrate = False

            console.print(f"[yellow]Checking audio section: {section_name}")

            # First pass: detect if we have Maximum bit rate but no Bit rate
            for line in content:
                line_text = line.strip()
                if "Maximum bit rate" in line_text:
                    has_max_bitrate = True
                    # Extract the Maximum bit rate value
                    try:
                        max_bitrate_value = line_text.split(':', 1)[1].strip()
                        console.print(f"[yellow]Found Maximum bit rate: {max_bitrate_value}")
                    except IndexError:
                        console.print(f"[red]Invalid Maximum bit rate line format: {line_text}")
                elif "Bit rate" in line_text and "mode" not in line_text.lower():
                    has_bitrate = True
                    console.print("[yellow]Found Bit rate already exists")

            # Second pass: add Bit rate line if needed
            if has_max_bitrate and not has_bitrate and max_bitrate_value:
                console.print(f"[green]Adding Bit rate line to {section_name} using value: {max_bitrate_value}")

                # Create a new Bit rate line with proper spacing
                bitrate_line = f"Bit rate                                 : {max_bitrate_value}"

                # Add the new Bit rate line at an appropriate position
                insertion_point = 0
                for i, line in enumerate(content):
                    if "Maximum bit rate" in line.strip():
                        insertion_point = i + 1
                        break

                # Insert the new line
                base_sections[section_name].insert(insertion_point, bitrate_line)
                console.print(f"[green]Added Bit rate line to {section_name}")

    # Build the combined MediaInfo text
    combined_text = []

    # Standard section order
    section_order = [
        "General",
        "Video"
    ]

    # Add audio, text, and other sections in order
    audio_sections = sorted([s for s in base_sections.keys() if s.startswith("Audio")])
    text_sections = sorted([s for s in base_sections.keys() if s.startswith("Text")])

    section_order.extend(audio_sections)
    section_order.extend(text_sections)
    section_order.append("Menu")

    # Other sections not in standard order
    other_sections = [s for s in base_sections.keys() if s not in section_order and s in base_sections]
    section_order.extend(other_sections)

    # Build output text in order
    for section in section_order:
        if section in base_sections:
            combined_text.append(section)
            combined_text.extend(base_sections[section])
            combined_text.append("")  # Empty line between sections

    return '\n'.join(combined_text)
