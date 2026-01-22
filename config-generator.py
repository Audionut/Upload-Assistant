#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional, TypedDict, Union, cast

from src.console import console


class LinkedSetting(TypedDict):
    condition: Callable[[str], bool]
    settings: list[str]


ConfigDict = dict[str, Any]
ConfigComments = dict[str, list[str]]
UnexpectedKey = tuple[str, ConfigDict, str]


def read_example_config() -> tuple[Optional[ConfigDict], ConfigComments]:
    """Read the example config file and return its structure and comments"""
    example_path = Path("data/example-config.py")
    comments: ConfigComments = {}

    if not example_path.exists():
        console.print("[!] Warning: Could not find data/example-config.py", markup=False)
        console.print("[i] Using built-in default structure instead", markup=False)
        return None, comments

    try:
        with open(example_path, encoding="utf-8") as file:
            lines = file.readlines()

        current_comments: list[str] = []
        key_stack: list[str] = []
        indent_stack = [0]

        for _idx, line in enumerate(lines):
            line = line.rstrip("\n")
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # Track nesting for fully qualified keys
            if "{" in stripped and ":" in stripped:
                key = stripped.split(":", 1)[0].strip().strip('"\'')
                while indent_stack and indent <= indent_stack[-1]:
                    key_stack.pop()
                    indent_stack.pop()
                key_stack.append(key)
                indent_stack.append(indent)
            elif "}" in stripped:
                while indent_stack and indent <= indent_stack[-1]:
                    if key_stack:  # Avoid popping from empty list
                        key_stack.pop()
                    indent_stack.pop()

            if stripped.startswith("#"):
                current_comments.append(stripped)
            elif ":" in stripped and not stripped.startswith("{"):
                key = stripped.split(":", 1)[0].strip().strip('"\'')
                # Build fully qualified key path
                fq_key = ".".join(key_stack + [key]) if key_stack else key

                if current_comments:
                    comments[key] = list(current_comments)
                    comments[fq_key] = list(current_comments)
                    current_comments = []
            elif not stripped or stripped in ["},", "}"]:  # Empty line
                pass  # Keep the comments for the next key
            else:
                current_comments = []  # Clear comments on other lines

        # Extract the config dict from the file content
        content = ''.join(lines)
        match = re.search(r"config\s*=\s*({.*})", content, re.DOTALL)
        if not match:
            console.print("[!] Warning: Could not parse example config", markup=False)
            return None, comments

        config_dict_str = match.group(1)
        example_config = ast.literal_eval(config_dict_str)
        if not isinstance(example_config, dict):
            console.print("[!] Warning: Example config is not a dict", markup=False)
            return None, comments

        console.print("[✓] Successfully loaded example config template", markup=False)
        return cast(ConfigDict, example_config), comments
    except Exception as e:
        console.print(f"[!] Error parsing example config: {str(e)}", markup=False)
        return None, comments


def load_existing_config() -> tuple[Optional[ConfigDict], Optional[Path]]:
    """Load an existing config file if available"""
    config_paths = [
        Path("data/config.py"),
        Path("data/config1.py")
    ]

    for path in config_paths:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as file:
                    content = file.read()

                # Extract the config dict from the file
                match = re.search(r"config\s*=\s*({.*})", content, re.DOTALL)
                if match:
                    config_dict_str = match.group(1)
                    # Convert to proper Python dict
                    config_dict = ast.literal_eval(config_dict_str)
                    if not isinstance(config_dict, dict):
                        console.print(f"\n[!] Error loading config from {path}: config is not a dict", markup=False)
                        continue
                    console.print(f"\n[✓] Found existing config at {path}", markup=False)
                    return cast(ConfigDict, config_dict), path
            except Exception as e:
                console.print(f"\n[!] Error loading config from {path}: {e}", markup=False)

    return None, None


def validate_config(existing_config: ConfigDict, example_config: ConfigDict) -> ConfigDict:
    """
    Validate the existing config against the example structure.
    Returns a cleaned version with only valid keys.
    """
    if not existing_config or not example_config:
        return existing_config

    unexpected_keys: list[UnexpectedKey] = []

    # Helper function to find unexpected keys at any level
    def find_unexpected_keys(existing_section: ConfigDict, example_section: ConfigDict, path: str = "") -> None:

        for key in existing_section:
            current_path = f"{path}.{key}" if path else key

            if key not in example_section:
                unexpected_keys.append((current_path, existing_section, key))
            elif isinstance(existing_section[key], dict) and isinstance(example_section.get(key), dict):
                # Recursively check nested dictionaries
                find_unexpected_keys(cast(ConfigDict, existing_section[key]), cast(ConfigDict, example_section[key]), current_path)

    # Check main sections first
    for section in existing_config:
        if section not in example_config:
            unexpected_keys.append((section, existing_config, section))
        elif isinstance(existing_config[section], dict) and isinstance(example_config[section], dict):
            # Check keys within valid sections
            find_unexpected_keys(cast(ConfigDict, existing_config[section]), cast(ConfigDict, example_config[section]), section)

    # If unexpected keys were found, ask about each one individually
    if unexpected_keys:
        console.print("\n[!] The following keys in your existing configuration are not in the example config:", markup=False)
        for i, (key_path, _parent_dict, _key) in enumerate(unexpected_keys):
            console.print(f"  {i+1}. {key_path}", markup=False)

        console.print("\n\n[i] The keys have been removed or renamed.", markup=False)
        console.print("[i] You can choose what to do with each key:", markup=False)

        for i, (key_path, parent_dict, key) in enumerate(unexpected_keys):
            value = parent_dict[key]
            value_display = str(value)
            if isinstance(value, dict):
                value_display = "{...}"  # Just show placeholder for dictionaries

            # Handle nested structures by limiting display length
            if len(value_display) > 50:
                value_display = value_display[:47] + "..."

            console.print(f"\nKey {i+1}/{len(unexpected_keys)}: {key_path} = {value_display}", markup=False)
            keep = input("Keep this key? (y/N): ").lower()

            # Remove the key if user chooses not to keep it
            if keep == "y":
                console.print(f"[i] Keeping key: {key_path}", markup=False)
            else:
                console.print(f"[i] Removing key: {key_path}", markup=False)
                del parent_dict[key]

        return existing_config

    # Return original if no unexpected keys
    return existing_config


def find_missing_keys(existing_config: ConfigDict, example_config: ConfigDict) -> list[str]:
    """Find keys that exist in example config but are missing in existing config"""
    missing_keys: list[str] = []

    # Helper function to find missing keys at any level
    def find_missing_recursive(example_section: ConfigDict, existing_section: ConfigDict, path: str = "") -> None:

        for key in example_section:
            current_path = f"{path}.{key}" if path else key

            if key not in existing_section:
                missing_keys.append(current_path)
            elif isinstance(example_section[key], dict) and isinstance(existing_section.get(key), dict):
                # Recursively check nested dictionaries
                find_missing_recursive(cast(ConfigDict, example_section[key]), cast(ConfigDict, existing_section[key]), current_path)

    # Check main sections first
    for section in example_config:
        if section not in existing_config:
            missing_keys.append(section)
        elif isinstance(example_config[section], dict) and isinstance(existing_config[section], dict):
            # Check keys within valid sections
            find_missing_recursive(cast(ConfigDict, example_config[section]), cast(ConfigDict, existing_config[section]), section)

    return missing_keys


def get_user_input(
    prompt: str,
    default: str = "",
    is_password: bool = False,
    is_announce_url: bool = False,
    existing_value: Optional[Any] = None,
) -> str:
    """Get input from user with default value and optional existing value"""
    display = prompt

    # If we have an existing value, show it as an option
    if existing_value is not None:
        existing_value_str = str(existing_value)
        display_value = existing_value_str
        # For password fields: show first 6 chars and mask the rest
        if is_password and existing_value_str:
            visible_part = existing_value_str[:6]
            masked_part = "*" * min(8, max(0, len(existing_value_str) - 6))
            display_value = f"{visible_part}{masked_part}" if len(existing_value_str) > 6 else existing_value_str
        elif is_announce_url and existing_value_str:
            # For announce_urls, show the first 10 chars and last 6 chars with * in between
            if len(existing_value_str) > 20:  # Only mask if long enough
                visible_prefix = existing_value_str[:15]
                visible_suffix = existing_value_str[-6:]
                masked_length = len(existing_value_str) - 16
                masked_part = "*" * min(masked_length, 15)  # Limit number of asterisks
                display_value = f"{visible_prefix}...{masked_part}...{visible_suffix}"
        else:
            display_value = existing_value_str
        display = f"{prompt} [existing: {display_value}]"

    # Show default if available
    if default and existing_value is None:
        display = f"{display} [default: {default}]"

    display = f"{display}: "

    # Prompt for input
    value = input(display)

    # Use existing value if user just pressed Enter and we have an existing value
    if value == "" and existing_value is not None:
        return str(existing_value)

    # Use default if no input and no existing value
    if value == "" and default:
        return str(default)

    return str(value)


def configure_default_section(
    existing_defaults: ConfigDict,
    example_defaults: ConfigDict,
    config_comments: ConfigComments,
    quick_setup: bool = False,
) -> ConfigDict:
    """
    Helper to configure the DEFAULT section.
    Returns a dict with the configured DEFAULT values.
    """
    console.print("\n====== DEFAULT CONFIGURATION ======", markup=False)
    console.print("\n[i] Press enter to accept the default values/skip, or input your own values.", markup=False)
    config_defaults: dict[str, Any] = {}

    # Settings that should only be prompted if a parent setting has a specific value
    linked_settings: dict[str, LinkedSetting] = {
        "update_notification": {
            "condition": lambda value: value.lower() == "true",
            "settings": ["verbose_notification"]
        },
        "tone_map": {
            "condition": lambda value: value.lower() == "true",
            "settings": ["algorithm", "desat", "tonemapped_header"]
        },
        "add_logo": {
            "condition": lambda value: value.lower() == "true",
            "settings": ["logo_size", "logo_language"]
        },
        "frame_overlay": {
            "condition": lambda value: value.lower() == "true",
            "settings": ["overlay_text_size"]
        },
        "multiScreens": {
            "condition": lambda value: (value.isdigit() and int(value) > 0),
            "settings": ["pack_thumb_size", "charLimit", "fileLimit", "processLimit", ]
        },
        "get_bluray_info": {
            "condition": lambda value: value.lower() == "true",
            "settings": ["add_bluray_link", "use_bluray_images", "bluray_image_size", "bluray_score", "bluray_single_score"]
        }
    }

    # Store which settings should be skipped based on linked settings
    skip_settings: set[str] = set()

    # If this is a fresh config (no existing defaults), offer quick setup
    do_quick_setup = False
    if quick_setup:
        do_quick_setup = input("\n[i] Do you want to quick setup with just essential settings? (y/N): ").lower() == "y"
        if do_quick_setup:
            console.print("[i] Quick setup selected. You'll only be prompted for essential settings.", markup=False)

    # Define essential settings for quick setup mode
    essential_settings = [
        "tmdb_api"
    ]

    for key, default_value in example_defaults.items():
        if key in ["default_torrent_client"]:
            continue

        # Skip if this setting should be skipped based on linked settings
        if key in skip_settings:
            # Copy default value from example config
            config_defaults[key] = default_value
            continue

        # Skip non-essential settings in quick setup mode
        if do_quick_setup and key not in essential_settings:
            config_defaults[key] = default_value
            continue

        if key in config_comments:
            console.print("\n[i] " + "\n[i] ".join(config_comments[key]), markup=False)

        if isinstance(default_value, bool):
            default_str = str(default_value)
            existing_value = str(existing_defaults.get(key, default_value))
            value = get_user_input(f"Setting '{key}'? (True/False)",
                                   default=default_str,
                                   existing_value=existing_value)
            config_defaults[key] = value

            # Check if this is a linked setting that controls other settings
            if key in linked_settings:
                linked_group = linked_settings[key]
                # If the condition is not met, add all linked settings to the skip list
                if not linked_group["condition"](value):
                    console.print(f"[i] Skipping {key}-related settings since {key} is {value}", markup=False)
                    skip_settings.update(linked_group["settings"])
        else:
            is_password = key in ["api_key", "passkey", "rss_key", "tvdb_token", "tmdb_api", "tvdb_api", "btn_api"] or "password" in key.lower() or key.endswith("_key") or key.endswith("_api") or key.endswith("_url")
            value = get_user_input(
                f"Setting '{key}'",
                default=str(default_value),
                is_password=is_password,
                existing_value=existing_defaults.get(key)
            )

            if default_value is None and (value == "" or value == "None"):
                config_defaults[key] = None
            else:
                config_defaults[key] = value

            if key in linked_settings:
                linked_group = linked_settings[key]
                if not linked_group["condition"](config_defaults[key]):
                    console.print(f"[i] Skipping {key}-related settings since {key} is {config_defaults[key]}", markup=False)
                    skip_settings.update(linked_group["settings"])

    if do_quick_setup:
        get_img_host(config_defaults, existing_defaults, example_defaults, config_comments)
        console.print("\n[i] Applied default values from example config for non-essential settings.", markup=False)

    return config_defaults


# Process image hosts
def get_img_host(
    config_defaults: ConfigDict,
    existing_defaults: ConfigDict,
    example_defaults: ConfigDict,
    config_comments: ConfigComments,
) -> None:
    img_host_api_map: dict[str, Union[str, list[str], None]] = {
        "imgbb": "imgbb_api",
        "ptpimg": "ptpimg_api",
        "lensdump": "lensdump_api",
        "ptscreens": "ptscreens_api",
        "onlyimage": "onlyimage_api",
        "dalexni": "dalexni_api",
        "ziplinestudio": ["zipline_url", "zipline_api_key"],
        "passtheimage": "passtheima_ge_api",
        "seedpool_cdn": "seedpool_cdn_api",
        "sharex": ["sharex_url", "sharex_api_key"],
        "imgbox": None,
        "pixhost": None
    }

    console.print("\n==== IMAGE HOST CONFIGURATION ====", markup=False)
    console.print("[i] Available image hosts: " + ", ".join(img_host_api_map.keys()), markup=False)
    console.print("[i] Note: imgbox and pixhost don't require API keys", markup=False)

    # Get existing image hosts if available
    existing_hosts: list[str] = []
    for i in range(1, 11):
        key = f"img_host_{i}"
        if key in existing_defaults and existing_defaults[key]:
            existing_hosts.append(str(existing_defaults[key]).strip().lower())

    if existing_hosts:
        console.print(f"\n[i] Your existing image hosts: {', '.join(existing_hosts)}", markup=False)

    default_count = len(existing_hosts) if existing_hosts else 1
    try:
        number_hosts = int(input(f"\n[i] How many image hosts would you like to configure? (1-10) [default: {default_count}]: ") or default_count)
        number_hosts = max(1, min(10, number_hosts))  # Limit between 1 and 10
    except ValueError:
        console.print(f"[!] Invalid input. Defaulting to {default_count} image host(s).", markup=False)
        number_hosts = default_count

    # Ask for each image host in sequence
    for i in range(1, number_hosts + 1):
        # Get existing value for this position if available
        existing_host = existing_hosts[i-1] if i <= len(existing_hosts) else None
        existing_display = f" [existing: {existing_host}]" if existing_host else ""

        valid_host = False
        while not valid_host:
            host_input = input(f"\n[i] Enter image host #{i}{existing_display} (e.g., ptpimg, imgbb, imgbox): ").strip().lower()

            if host_input == "" and existing_host:
                host_input = existing_host

            if host_input in img_host_api_map:
                valid_host = True
                host_key = f"img_host_{i}"
                config_defaults[host_key] = host_input

                # Configure API key(s) for this host, if needed
                api_keys = img_host_api_map.get(host_input)
                if api_keys is None:
                    console.print(f"[i] {host_input} doesn't require an API key.", markup=False)
                    continue

                # Convert single string to list for consistent handling
                if isinstance(api_keys, str):
                    api_keys = [api_keys]

                # Process each key for this host
                for api_key in api_keys:
                    if api_key in example_defaults:
                        if api_key in config_comments:
                            console.print("\n[i] " + "\n[i] ".join(config_comments[api_key]), markup=False)

                        is_password = api_key.endswith("_url") or api_key.endswith("_key") or api_key.endswith("_api")
                        config_defaults[api_key] = get_user_input(
                            f"Setting '{api_key}' for {host_input}",
                            default=str(example_defaults.get(api_key, "")),
                            is_password=is_password,
                            existing_value=existing_defaults.get(api_key)
                        )
            else:
                console.print(f"[!] Invalid host: {host_input}. Available hosts: {', '.join(img_host_api_map.keys())}", markup=False)

    # Set unused image host API keys to empty string
    for api_key_item in img_host_api_map.values():
        if api_key_item is None:
            # Skip hosts that don't need API keys
            continue

        api_keys = [api_key_item] if isinstance(api_key_item, str) else api_key_item

        for api_key in api_keys:
            if api_key in example_defaults and api_key not in config_defaults:
                config_defaults[api_key] = ""


def configure_trackers(
    existing_trackers: ConfigDict,
    example_trackers: ConfigDict,
    config_comments: ConfigComments,
) -> ConfigDict:
    """
    Helper to configure the TRACKERS section.
    Returns a dict with the configured trackers.
    """
    console.print("\n====== TRACKERS ======", markup=False)

    # Get list of trackers to configure
    example_tracker_list = [
        t for t in example_trackers
        if t != "default_trackers" and isinstance(example_trackers[t], dict)
    ]
    if example_tracker_list:
        console.print(f"[i] Available trackers in example config: \n{', '.join(example_tracker_list)}", markup=False)
        console.print("\n[i] (default trackers list) Only add the trackers you want to upload to on a regular basis.", markup=False)
        console.print("[i] You can add other tracker configs later if needed.", markup=False)

    existing_trackers_value = existing_trackers.get("default_trackers", "")
    existing_tracker_str = str(existing_trackers_value) if existing_trackers_value else ""
    existing_tracker_list = existing_tracker_str.split(",") if existing_tracker_str else []
    existing_tracker_list = [t.strip() for t in existing_tracker_list if t.strip()]
    existing_trackers_str = ", ".join(existing_tracker_list)

    trackers_input = get_user_input(
        "\nEnter tracker acronyms separated by commas (e.g. BHD, PTP, AITHER)",
        existing_value=existing_trackers_str
    ).upper()
    trackers_list = [t.strip().upper() for t in trackers_input.split(",") if t.strip()]

    trackers_config: dict[str, Any] = {"default_trackers": ", ".join(trackers_list)}

    # Ask if user wants to update all trackers or specific ones
    update_all = input("\n[i] Do you want to update ALL trackers in your default trackers list? (Y/n): ").lower() != "n"

    if not update_all:
        # Ask which specific trackers to update
        update_specific = input("\nEnter tracker acronyms to update (comma separated), or leave blank to skip all: ").upper()
        update_trackers_list = [t.strip() for t in update_specific.split(",") if t.strip()]
    else:
        # Update all trackers in the list
        update_trackers_list = trackers_list.copy()

    # Only update trackers in the update list
    for tracker in trackers_list:
        # Skip if not in update list (unless updating all)
        if not update_all and tracker not in update_trackers_list:
            console.print(f"\nSkipping configuration for {tracker}", markup=False)
            # Copy existing config if available
            if tracker in existing_trackers:
                trackers_config[tracker] = existing_trackers[tracker]
            continue

        console.print(f"\n\nConfiguring **{tracker}**:", markup=False)
        existing_tracker_config: ConfigDict = cast(ConfigDict, existing_trackers.get(tracker, {}))
        example_tracker: ConfigDict = cast(ConfigDict, example_trackers.get(tracker, {}))
        tracker_config: dict[str, Any] = {}

        if example_tracker:
            for key, default_value in example_tracker.items():
                # Skip keys that should not be prompted
                if tracker == "HDT" and key == "announce_url":
                    tracker_config[key] = example_tracker[key]
                    continue

                comment_key = f"TRACKERS.{tracker}.{key}"
                if comment_key in config_comments:
                    console.print("\n[i] " + "\n[i] ".join(config_comments[comment_key]), markup=False)

                if isinstance(default_value, bool):
                    default_str = str(default_value)
                    existing_value = str(existing_tracker_config.get(key, default_value))
                    value = get_user_input(f"Tracker setting '{key}'? (True/False)",
                                           default=default_str,
                                           existing_value=existing_value)
                    tracker_config[key] = value
                else:
                    is_password = key in ["api_key", "passkey", "rss_key", "password", "opt_uri"] or key.endswith("rss_key")
                    is_announce_url = key.endswith("announce_url")
                    tracker_config[key] = get_user_input(
                        f"Tracker setting '{key}'",
                        default=str(default_value) if default_value else "",
                        is_password=is_password,
                        is_announce_url=is_announce_url,
                        existing_value=existing_tracker_config.get(key)
                    )
        else:
            console.print(f"[!] No example config found for tracker '{tracker}'.", markup=False)

        trackers_config[tracker] = tracker_config

    # Offer to add more trackers from the example config
    remaining_trackers = [t for t in example_tracker_list if t.upper() not in [x.upper() for x in trackers_list]]
    if remaining_trackers:
        console.print("\n[i] Other trackers available in the example config that are not in your default list:", markup=False)
        console.print(", ".join(remaining_trackers), markup=False)
        console.print("\n[i] This just adds the tracker config, not to your list of default trackers.", markup=False)
        console.print("\nFor example so you can use with -tk.", markup=False)
        add_more = get_user_input(
            "\nEnter any additional tracker acronyms to add (comma separated), or leave blank to skip"
        )
        additional = [t.strip().upper() for t in add_more.split(",") if t.strip()]
        for tracker in additional:
            if tracker in trackers_config:
                continue  # Already configured
            console.print(f"\n\nConfiguring **{tracker}**:", markup=False)
            example_tracker = cast(ConfigDict, example_trackers.get(tracker, {}))
            additional_tracker_config: dict[str, Any] = {}
            if example_tracker:
                for key, default_value in example_tracker.items():
                    if tracker == "HDT" and key == "announce_url":
                        additional_tracker_config[key] = example_tracker[key]
                        continue
                    comment_key = f"TRACKERS.{tracker}.{key}"
                    if comment_key in config_comments:
                        console.print("\n[i] " + "\n[i] ".join(config_comments[comment_key]), markup=False)

                    if isinstance(default_value, bool):
                        default_str = str(default_value)
                        value = get_user_input(f"Tracker setting '{key}'? (True/False)",
                                               default=default_str)
                        additional_tracker_config[key] = value
                    else:
                        is_password = key in ["api_key", "passkey", "rss_key", "password", "opt_uri"] or key.endswith("rss_key")
                        is_announce_url = key.endswith("announce_url")
                        additional_tracker_config[key] = get_user_input(
                            f"Tracker setting '{key}'",
                            default=str(default_value) if default_value else "",
                            is_password=is_password,
                            is_announce_url=is_announce_url
                        )
            else:
                console.print(f"[!] No example config found for tracker '{tracker}'.", markup=False)
            trackers_config[tracker] = additional_tracker_config

    return trackers_config


def configure_torrent_clients(
    existing_clients: Optional[ConfigDict] = None,
    example_clients: Optional[ConfigDict] = None,
    default_client_name: Optional[str] = None,
    config_comments: Optional[ConfigComments] = None,
) -> tuple[ConfigDict, Optional[str]]:
    """
    Helper to configure the TORRENT_CLIENTS section.
    Returns a dict with the configured client(s) and the selected default client name.
    """
    config_clients: ConfigDict = {}
    existing_clients = existing_clients or {}
    example_clients = example_clients or {}
    config_comments = config_comments or {}

    # Only use default_client_name if provided and in existing_clients
    if default_client_name and default_client_name in existing_clients:
        keep_existing_client = input(f"\nDo you want to keep the existing client '{default_client_name}'? (y/n): ").lower() == "y"
        if not keep_existing_client:
            console.print("What client do you want to use instead?", markup=False)
            console.print("Available clients in example config:", markup=False)
            for client_name in example_clients:
                console.print(f"  - {client_name}", markup=False)
            new_client = get_user_input("Enter the name of the torrent client to use",
                                        default="qbittorrent",
                                        existing_value=default_client_name)
            default_client_name = new_client
    else:
        # No default client specified or not in existing_clients, ask user to select one
        console.print("No default client found. Let's configure one.", markup=False)
        console.print("What client do you want to use?", markup=False)
        console.print("Available clients in example config:", markup=False)
        for client_name in example_clients:
            console.print(f"  - {client_name}", markup=False)
        default_client_name = get_user_input("Enter the name of the torrent client to use",
                                             default="qbittorrent")

    # Configure the default client
    console.print(f"\nConfiguring default client: {default_client_name}", markup=False)
    config_clients = configure_single_client(default_client_name, existing_clients, example_clients, config_clients, config_comments)

    # After configuring the default client, ask if the user wants to add additional clients
    while True:
        add_another = input("\n\n[i] Do you want to add configuration for another torrent client? (y/N): ").lower() == "y"
        if not add_another:
            break

        # Show available clients not yet configured
        available_clients = [c for c in example_clients if c not in config_clients]
        if not available_clients:
            console.print("All available clients from the example config have been configured.", markup=False)
            break

        console.print("\nAvailable clients to configure:", markup=False)
        for client_name in available_clients:
            console.print(f"  - {client_name}", markup=False)

        additional_client = get_user_input("Enter the name of the torrent client to configure")
        if not additional_client:
            console.print("No client name provided, skipping additional client configuration.", markup=False)
            continue

        if additional_client in config_clients:
            console.print(f"Client '{additional_client}' is already configured.", markup=False)
            continue

        if additional_client not in example_clients:
            console.print(f"Client '{additional_client}' not found in example config. Available clients: {', '.join(available_clients)}", markup=False)
            continue

        # Configure the additional client
        console.print(f"\nConfiguring additional client: {additional_client}", markup=False)
        config_clients = configure_single_client(additional_client, existing_clients, example_clients, config_clients, config_comments)

    return config_clients, default_client_name


def configure_single_client(
    client_name: str,
    existing_clients: ConfigDict,
    example_clients: ConfigDict,
    config_clients: ConfigDict,
    config_comments: ConfigComments,
) -> ConfigDict:
    """Helper function to configure a single torrent client"""
    # Use existing config for the selected client if present, else use example config
    existing_client_config = cast(ConfigDict, existing_clients.get(client_name, {}))
    example_client_config = cast(ConfigDict, example_clients.get(client_name, {}))

    if not example_client_config:
        console.print(f"[!] No example config found for client '{client_name}'.", markup=False)
        if existing_client_config:
            console.print(f"[i] Using existing config for '{client_name}'", markup=False)
            config_clients[client_name] = existing_client_config
        return config_clients

    # Set the client type from the example config
    client_type = example_client_config.get("torrent_client", client_name)
    client_config = {"torrent_client": client_type}

    # Process all other client settings
    for key, default_value in example_client_config.items():
        # this is never edited
        if key == "torrent_client":
            continue

        comment_key = f"TORRENT_CLIENTS.{client_name}.{key}"
        if comment_key in config_comments:
            console.print("\n[i] " + "\n[i] ".join(config_comments[comment_key]), markup=False)
        elif key in config_comments:
            console.print("\n[i] " + "\n[i] ".join(config_comments[key]), markup=False)

        if isinstance(default_value, bool):
            default_str = str(default_value)
            existing_value = str(existing_client_config.get(key, default_value))
            value = get_user_input(f"Client setting '{key}'? (True/False)",
                                   default=default_str,
                                   existing_value=existing_value)
            client_config[key] = value
        else:
            is_password = key.endswith("pass") or key.endswith("password")
            client_config[key] = get_user_input(
                f"Client setting '{key}'",
                default=str(default_value) if default_value is not None else "",
                is_password=is_password,
                existing_value=existing_client_config.get(key)
            )

    config_clients[client_name] = client_config
    return config_clients


def configure_discord(
    existing_discord: ConfigDict,
    example_discord: ConfigDict,
    config_comments: ConfigComments,
) -> ConfigDict:
    """
    Helper to configure the DISCORD section.
    Returns a dict with the configured Discord settings.
    """
    console.print("\n====== DISCORD CONFIGURATION ======", markup=False)
    console.print("[i] Configure Discord bot settings for upload notifications", markup=False)

    discord_config: ConfigDict = {}
    existing_use_discord = existing_discord.get("use_discord", False)
    enable_discord = get_user_input(
        "Enable Discord bot functionality? (True/False)",
        default="False",
        existing_value=str(existing_use_discord)
    )
    discord_config["use_discord"] = enable_discord

    # If Discord is disabled, set defaults and return
    if enable_discord.lower() != "true":
        console.print("[i] Discord disabled. Setting default values for other Discord settings.", markup=False)
        discord_config = example_discord.copy()
        discord_config["use_discord"] = enable_discord
        return discord_config

    # Configure other Discord settings if enabled
    for key, default_value in example_discord.items():
        if key == "use_discord":
            continue

        comment_key = f"DISCORD.{key}"
        if comment_key in config_comments:
            console.print("\n[i] " + "\n[i] ".join(config_comments[comment_key]), markup=False)

        if isinstance(default_value, bool):
            default_str = str(default_value)
            existing_value = str(existing_discord.get(key, default_value))
            value = get_user_input(
                f"Discord setting '{key}'? (True/False)",
                default=default_str,
                existing_value=existing_value
            )
            discord_config[key] = value
        else:
            is_password = key in ["discord_bot_token"]
            discord_config[key] = get_user_input(
                f"Discord setting '{key}'",
                default=str(default_value) if default_value else "",
                is_password=is_password,
                existing_value=existing_discord.get(key)
            )

    return discord_config


def generate_config_file(config_data: ConfigDict, existing_path: Optional[Path] = None) -> bool:
    """Generate the config.py file from the config dictionary"""
    # Create output directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Determine the output path
    if existing_path:
        config_path = existing_path
        backup_path = Path(f"{existing_path}.bak")
        # Create backup of existing config
        if existing_path.exists():
            with open(existing_path, encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            console.print(f"\n[✓] Created backup of existing config at {backup_path}", markup=False)
    else:
        config_path = Path("data/config.py")
        backup_path = Path("data/config.py.bak")
        if config_path.exists():
            overwrite = input(f"{config_path} already exists. Overwrite? (y/n): ").lower()
            if overwrite == "y":
                with open(config_path, encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
                console.print(f"\n[✓] Created backup of existing config at {backup_path}", markup=False)
            else:
                return False

    # Convert boolean values in config to proper Python booleans
    def format_config(obj: Any) -> Any:
        if isinstance(obj, dict):
            # Process each key-value pair in dictionaries
            obj_dict = cast(dict[Any, Any], obj)
            return {str(k): format_config(v) for k, v in obj_dict.items()}
        elif isinstance(obj, list):
            # Process each item in lists
            obj_list = cast(list[Any], obj)
            return [format_config(item) for item in obj_list]
        elif isinstance(obj, str):
            # Convert string "true"/"false" to Python True/False
            if obj.lower() == "true":
                return True
            elif obj.lower() == "false":
                return False
        # Return unchanged for other types
        return obj

    # Format config with proper Python booleans
    formatted_config = cast(ConfigDict, format_config(config_data))

    # Generate the config file with properly formatted Python syntax
    with open(config_path, "w", encoding="utf-8") as file:
        file.write("config = {\n")

        # Custom formatting function to create Python dict with trailing commas
        def write_dict(d: ConfigDict, indent_level: int = 1) -> None:
            indent = "    " * indent_level
            for key, value in d.items():
                file.write(f"{indent}{json.dumps(key)}: ")

                if isinstance(value, dict):
                    file.write("{\n")
                    write_dict(cast(ConfigDict, value), indent_level + 1)
                    file.write(f"{indent}}},\n")
                elif isinstance(value, bool):
                    # Ensure booleans are capitalized
                    file.write(f"{str(value).capitalize()},\n")
                elif isinstance(value, type(None)):
                    # Handle None values
                    file.write("None,\n")
                else:
                    # Other values with trailing comma
                    file.write(f"{json.dumps(value, ensure_ascii=False)},\n")

        write_dict(formatted_config)
        file.write("}\n")

    console.print(f"\n[✓] Configuration file created at {config_path}", markup=False)
    return True


if __name__ == "__main__":
    console.print("\nUpload Assistant Configuration Generator", markup=False)
    console.print("========================================", markup=False)

    # Get example configuration structure first
    example_config, config_comments = read_example_config()

    if not example_config:
        console.print("[!] Example config is missing or invalid. Exiting.", markup=False)
        raise SystemExit(1)

    # Try to load existing config
    existing_config, existing_path = load_existing_config()

    if existing_config and example_config:
        just_updating = input("\nExisting config found. Are you just updating to grab any new UA config options? (Y/n): ").lower()
        if just_updating == "n":
            use_existing = input("\nWould you like to edit existing instead of starting fresh? (Y/n): ").lower()
            if use_existing == "n":
                console.print("\n[i] Starting with fresh configuration.", markup=False)
                console.print("Enter to accept the default values/skip, or enter your own values.", markup=False)
                config_data = {}

                # DEFAULT section
                example_defaults = example_config.get("DEFAULT", {})
                config_data["DEFAULT"] = configure_default_section({}, example_defaults, config_comments, quick_setup=True)
                # Set default client name if not set
                config_data["DEFAULT"]["default_torrent_client"] = config_data["DEFAULT"].get("default_torrent_client", "qbittorrent")

                # TRACKERS section
                example_trackers = example_config.get("TRACKERS", {})
                config_data["TRACKERS"] = configure_trackers({}, example_trackers, config_comments)

                # TORRENT_CLIENTS section
                example_clients = example_config.get("TORRENT_CLIENTS", {})
                default_client = None
                client_configs, default_client = configure_torrent_clients(
                    {}, example_clients, default_client, config_comments
                )
                config_data["TORRENT_CLIENTS"] = client_configs
                config_data["DEFAULT"]["default_torrent_client"] = default_client

                example_discord = example_config.get("DISCORD", {})
                config_data["DISCORD"] = configure_discord({}, example_discord, config_comments)

                generate_config_file(config_data)
            else:
                console.print("\n[i] Using existing configuration as a template.", markup=False)
                console.print("[i] Existing config will be renamed config.py.bak.", markup=False)
                console.print("[i] Press enter to accept the default values/skip, or input your own values.", markup=False)

                # Check for unexpected keys in existing config
                existing_config = validate_config(existing_config, example_config)

                # Start with the existing config
                config_data = existing_config.copy()

                # Ask about updating each main section separately
                console.print("\n\n[i] Lets work on one section at a time.", markup=False)
                console.print(, markup=False)

                # DEFAULT section
                update_default = input("Do you want to update something in the DEFAULT section? (y/n): ").lower() == "y"
                if update_default:
                    existing_defaults = existing_config.get("DEFAULT", {})
                    example_defaults = example_config.get("DEFAULT", {})
                    config_data["DEFAULT"] = configure_default_section(existing_defaults, example_defaults, config_comments)
                    # Set default client name (if needed)
                    config_data["DEFAULT"]["default_torrent_client"] = config_data["DEFAULT"].get("default_torrent_client", "qbittorrent")
                else:
                    console.print("[i] Keeping existing DEFAULT section", markup=False)
                    console.print(, markup=False)

                # TRACKERS section
                update_trackers = input("Do you want to update something in the TRACKERS section? (y/n): ").lower() == "y"
                if update_trackers:
                    existing_trackers = existing_config.get("TRACKERS", {})
                    example_trackers = example_config.get("TRACKERS", {})
                    config_data["TRACKERS"] = configure_trackers(existing_trackers, example_trackers, config_comments)
                else:
                    console.print("[i] Keeping existing TRACKERS section", markup=False)
                    console.print(, markup=False)

                # TORRENT_CLIENTS section
                update_clients = input("\nDo you want to update something in the TORRENT_CLIENTS section? (y/n): ").lower() == "y"
                if update_clients:
                    console.print("\n====== TORRENT CLIENT ======", markup=False)
                    existing_clients = existing_config.get("TORRENT_CLIENTS", {})
                    example_clients = example_config.get("TORRENT_CLIENTS", {})
                    default_client = config_data["DEFAULT"].get("default_torrent_client", None)

                    # Get updated client config and default client name
                    client_configs, default_client = configure_torrent_clients(
                        existing_clients, example_clients, default_client, config_comments
                    )

                    # Update client configs and default client name
                    config_data["TORRENT_CLIENTS"] = client_configs
                    config_data["DEFAULT"]["default_torrent_client"] = default_client
                else:
                    console.print("[i] Keeping existing TORRENT_CLIENTS section", markup=False)
                    console.print(, markup=False)

                # DISCORD section update
                update_discord = input("Do you want to update something in the DISCORD section? (y/n): ").lower() == "y"
                if update_discord:
                    existing_discord = existing_config.get("DISCORD", {})
                    example_discord = example_config.get("DISCORD", {})
                    config_data["DISCORD"] = configure_discord(existing_discord, example_discord, config_comments)
                else:
                    console.print("[i] Keeping existing DISCORD section", markup=False)
                    console.print(, markup=False)

                missing_discord_keys: list[str] = []
                missing_default_keys: list[str] = []
                if "DEFAULT" in example_config and "DEFAULT" in config_data:
                    def find_missing_default_keys(example_section: ConfigDict, existing_section: ConfigDict, _path: str = "") -> None:
                        for key in example_section:
                            if key not in existing_section:
                                missing_default_keys.append(key)
                    find_missing_default_keys(cast(ConfigDict, example_config["DEFAULT"]), cast(ConfigDict, config_data["DEFAULT"]))

                if missing_default_keys:
                    console.print("\n\n[!] Your existing config is missing these keys from example-config:", markup=False)

                    # Only prompt for the missing keys
                    missing_defaults = {k: example_config["DEFAULT"][k] for k in missing_default_keys}
                    # Use empty dict for existing values so only defaults are shown
                    added_defaults = configure_default_section({}, missing_defaults, config_comments)
                    config_data["DEFAULT"].update(added_defaults)

                if "DISCORD" in example_config:
                    if "DISCORD" not in config_data:
                        # Entire DISCORD section is missing
                        console.print("\n[!] DISCORD section is missing from your config", markup=False)
                        add_discord = input("Do you want to add Discord configuration? (y/n): ").lower() == "y"
                        if add_discord:
                            example_discord = example_config.get("DISCORD", {})
                            config_data["DISCORD"] = configure_discord({}, example_discord, config_comments)
                        else:
                            config_data["DISCORD"] = example_config["DISCORD"].copy()
                    else:
                        # Check for missing keys within DISCORD section
                        def find_missing_discord_keys(example_section: ConfigDict, existing_section: ConfigDict) -> None:
                            for key in example_section:
                                if key not in existing_section:
                                    missing_discord_keys.append(key)
                        find_missing_discord_keys(cast(ConfigDict, example_config["DISCORD"]), cast(ConfigDict, config_data["DISCORD"]))

                if missing_discord_keys:
                    console.print(f"\n[!] Your DISCORD config is missing these keys: {', '.join(missing_discord_keys)}", markup=False)
                    add_missing_discord = input("Do you want to configure the missing Discord settings? (y/n): ").lower() == "y"
                    if add_missing_discord:
                        missing_discord_config = {k: example_config["DISCORD"][k] for k in missing_discord_keys}
                        added_discord = configure_discord({}, missing_discord_config, config_comments)
                        config_data["DISCORD"].update(added_discord)
                    else:
                        for key in missing_discord_keys:
                            config_data["DISCORD"][key] = example_config["DISCORD"][key]

                # Generate the updated config file
                generate_config_file(config_data, existing_path)
        else:
            existing_config = validate_config(existing_config, example_config)
            config_data = existing_config.copy()
            missing_default_keys: list[str] = []
            if "DEFAULT" in example_config and "DEFAULT" in config_data:
                def find_missing_default_keys(example_section: ConfigDict, existing_section: ConfigDict, _path: str = "") -> None:
                    for key in example_section:
                        if key not in existing_section:
                            missing_default_keys.append(key)
                find_missing_default_keys(cast(ConfigDict, example_config["DEFAULT"]), cast(ConfigDict, config_data["DEFAULT"]))

            if missing_default_keys:
                console.print("\n[!] Your existing config is missing these keys from example-config:", markup=False)

                # Only prompt for the missing keys
                missing_defaults = {k: example_config["DEFAULT"][k] for k in missing_default_keys}
                added_defaults = configure_default_section({}, missing_defaults, config_comments)
                config_data["DEFAULT"].update(added_defaults)

            if "DISCORD" not in config_data and "DISCORD" in example_config:
                console.print("\n[!] DISCORD section is missing from your config", markup=False)
                config_data["DISCORD"] = example_config["DISCORD"].copy()
                console.print("[i] Added DISCORD section with default values", markup=False)
            elif "DISCORD" in config_data and "DISCORD" in example_config:
                # Check for missing DISCORD keys
                missing_discord_keys: list[str] = []
                for key in example_config["DISCORD"]:
                    if key not in config_data["DISCORD"]:
                        missing_discord_keys.append(key)

                if missing_discord_keys:
                    console.print(f"\n[!] Your DISCORD config is missing these keys: {', '.join(missing_discord_keys)}", markup=False)
                    for key in missing_discord_keys:
                        config_data["DISCORD"][key] = example_config["DISCORD"][key]
                    console.print("[i] Added missing DISCORD keys with default values", markup=False)

            # Generate the updated config file
            generate_config_file(config_data, existing_path)

    else:
        console.print("\n[i] No existing configuration found. Creating a new one.", markup=False)
        console.print("[i] Enter to accept the default values/skip, or enter your own values.", markup=False)

        config_data: ConfigDict = {}

        # DEFAULT section
        example_defaults = example_config.get("DEFAULT", {})
        config_data["DEFAULT"] = configure_default_section({}, example_defaults, config_comments, quick_setup=True)
        # Set default client name if not set
        config_data["DEFAULT"]["default_torrent_client"] = config_data["DEFAULT"].get("default_torrent_client", "qbittorrent")

        # TRACKERS section
        example_trackers = example_config.get("TRACKERS", {})
        config_data["TRACKERS"] = configure_trackers({}, example_trackers, config_comments)

        # TORRENT_CLIENTS section
        example_clients = example_config.get("TORRENT_CLIENTS", {})
        default_client = None
        client_configs, default_client = configure_torrent_clients(
            {}, example_clients, default_client, config_comments
        )
        config_data["TORRENT_CLIENTS"] = client_configs
        config_data["DEFAULT"]["default_torrent_client"] = default_client

        # DISCORD section
        example_discord = example_config.get("DISCORD", {})
        config_data["DISCORD"] = configure_discord({}, example_discord, config_comments)

        generate_config_file(config_data)
