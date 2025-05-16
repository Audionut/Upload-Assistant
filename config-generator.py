#!/usr/bin/env python3

import os
import re
import json
from pathlib import Path
import getpass
import ast


def read_example_config():
    """Read the example config file and return its structure and comments"""
    example_path = Path("data/example-config.py")
    comments = {}

    if not example_path.exists():
        print("[!] Warning: Could not find data/example-config.py")
        print("[i] Using built-in default structure instead")
        return None, comments

    try:
        with open(example_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        current_comments = []
        key_stack = []
        indent_stack = [0]

        for idx, line in enumerate(lines):
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
            elif not stripped:  # Empty line
                pass  # Keep the comments for the next key
            elif stripped in ["},", "}"]:
                pass  # Keep the comments for the next key
            else:
                current_comments = []  # Clear comments on other lines

        # Extract the config dict from the file content
        content = ''.join(lines)
        match = re.search(r"config\s*=\s*({.*})", content, re.DOTALL)
        if not match:
            print("[!] Warning: Could not parse example config")
            return None, comments

        config_dict_str = match.group(1)
        example_config = ast.literal_eval(config_dict_str)

        print("[✓] Successfully loaded example config template")
        return example_config, comments
    except Exception as e:
        print(f"[!] Error parsing example config: {str(e)}")
        return None, comments


def load_existing_config():
    """Load an existing config file if available"""
    config_paths = [
        Path("data/config.py"),
        Path("data/config1.py")
    ]

    for path in config_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()

                # Extract the config dict from the file
                match = re.search(r"config\s*=\s*({.*})", content, re.DOTALL)
                if match:
                    config_dict_str = match.group(1)
                    # Convert to proper Python dict
                    config_dict = ast.literal_eval(config_dict_str)
                    print(f"\n[✓] Found existing config at {path}")
                    return config_dict, path
            except Exception as e:
                print(f"\n[!] Error loading config from {path}: {e}")

    return None, None


def validate_config(existing_config, example_config):
    """
    Validate the existing config against the example structure.
    Returns a cleaned version with only valid keys.
    """
    if not existing_config or not example_config:
        return existing_config

    unexpected_keys = []

    # Helper function to find unexpected keys at any level
    def find_unexpected_keys(existing_section, example_section, path=""):
        if not isinstance(existing_section, dict) or not isinstance(example_section, dict):
            return

        for key in existing_section:
            current_path = f"{path}.{key}" if path else key

            if key not in example_section:
                unexpected_keys.append((current_path, existing_section, key))
            elif isinstance(existing_section[key], dict) and isinstance(example_section.get(key), dict):
                # Recursively check nested dictionaries
                find_unexpected_keys(existing_section[key], example_section[key], current_path)

    # Check main sections first
    for section in existing_config:
        if section not in example_config:
            unexpected_keys.append((section, existing_config, section))
        elif isinstance(existing_config[section], dict) and isinstance(example_config[section], dict):
            # Check keys within valid sections
            find_unexpected_keys(existing_config[section], example_config[section], section)

    # If unexpected keys were found, ask about each one individually
    if unexpected_keys:
        print("\n[!] The following keys in your existing configuration are not in the example config:")
        for i, (key_path, parent_dict, key) in enumerate(unexpected_keys):
            print(f"  {i+1}. {key_path}")

        print("\nYou can choose what to do with each key:")

        for i, (key_path, parent_dict, key) in enumerate(unexpected_keys):
            value = parent_dict[key]
            value_display = str(value)
            if isinstance(value, dict):
                value_display = "{...}"  # Just show placeholder for dictionaries

            # Handle nested structures by limiting display length
            if len(value_display) > 50:
                value_display = value_display[:47] + "..."

            print(f"\nKey {i+1}/{len(unexpected_keys)}: {key_path} = {value_display}")
            keep = input("Keep this key? (y/n) [default: n]: ").lower()

            # Remove the key if user chooses not to keep it
            if keep == "y":
                print(f"[i] Keeping key: {key_path}")
            else:
                print(f"[i] Removing key: {key_path}")
                del parent_dict[key]

        return existing_config

    # Return original if no unexpected keys
    return existing_config


def find_missing_keys(existing_config, example_config):
    """Find keys that exist in example config but are missing in existing config"""
    missing_keys = []

    # Helper function to find missing keys at any level
    def find_missing_recursive(example_section, existing_section, path=""):
        if not isinstance(example_section, dict) or not isinstance(existing_section, dict):
            return

        for key in example_section:
            current_path = f"{path}.{key}" if path else key

            if key not in existing_section:
                missing_keys.append(current_path)
            elif isinstance(example_section[key], dict) and isinstance(existing_section.get(key), dict):
                # Recursively check nested dictionaries
                find_missing_recursive(example_section[key], existing_section[key], current_path)

    # Check main sections first
    for section in example_config:
        if section not in existing_config:
            missing_keys.append(section)
        elif isinstance(example_config[section], dict) and isinstance(existing_config[section], dict):
            # Check keys within valid sections
            find_missing_recursive(example_config[section], existing_config[section], section)

    return missing_keys


def get_user_input(prompt, default="", is_password=False, existing_value=None):
    """Get input from user with default value and optional existing value"""
    display = prompt

    # If we have an existing value, show it as an option
    if existing_value is not None:
        # Mask passwords in display
        display_value = "********" if is_password and existing_value else existing_value
        display = f"{prompt} [existing: {display_value}]"

    # Show default if available
    if default and existing_value is None:
        display = f"{display} [default: {default}]"

    display = f"{display}: "

    # Prompt for input
    if is_password:
        value = getpass.getpass(display)
    else:
        value = input(display)

    # Use existing value if user just pressed Enter and we have an existing value
    if value == "" and existing_value is not None:
        return existing_value

    # Use default if no input and no existing value
    if value == "" and default:
        return default

    return value


def configure_default_section(existing_defaults, example_defaults, config_comments):
    """
    Helper to configure the DEFAULT section.
    Returns a dict with the configured DEFAULT values.
    """
    print("\n====== DEFAULT CONFIGURATION ======")
    config_defaults = {}

    for key, default_value in example_defaults.items():
        # Skip special keys that we'll handle separately
        if key in ["default_torrent_client"]:
            continue

        if key in config_comments:
            print("\n" + "\n".join(config_comments[key]))

        # Handle different value types
        if isinstance(default_value, bool):
            default_str = str(default_value)
            existing_value = str(existing_defaults.get(key, default_value))
            value = get_user_input(f"Setting '{key}'? (True/False)",
                                   default=default_str,
                                   existing_value=existing_value)
            config_defaults[key] = value
        else:
            config_defaults[key] = get_user_input(
                f"Setting '{key}'",
                default=str(default_value),
                existing_value=existing_defaults.get(key)
            )

    return config_defaults


def configure_trackers(existing_trackers, example_trackers, config_comments):
    """
    Helper to configure the TRACKERS section.
    Returns a dict with the configured trackers.
    """
    print("\n====== TRACKERS ======")

    # Get list of trackers to configure
    example_tracker_list = [
        t for t in example_trackers
        if t != "default_trackers" and isinstance(example_trackers[t], dict)
    ]
    if example_tracker_list:
        print(f"Available trackers in example config: {', '.join(example_tracker_list)}")

    existing_tracker_list = existing_trackers.get("default_trackers", "").split(",") if existing_trackers.get("default_trackers") else []
    existing_tracker_list = [t.strip() for t in existing_tracker_list if t.strip()]
    existing_trackers_str = ", ".join(existing_tracker_list)

    trackers_input = get_user_input(
        "Enter tracker acronyms separated by commas (e.g., BHD,PTP,AITHER)",
        existing_value=existing_trackers_str
    )
    trackers_list = [t.strip().upper() for t in trackers_input.split(",") if t.strip()]

    trackers_config = {"default_trackers": ", ".join(trackers_list)}

    # Configure trackers from the list
    for tracker in trackers_list:
        print(f"\nConfiguring {tracker}:")
        existing_tracker_config = existing_trackers.get(tracker, {})
        example_tracker = example_trackers.get(tracker, {})
        tracker_config = {}

        if example_tracker and isinstance(example_tracker, dict):
            for key, default_value in example_tracker.items():
                comment_key = f"TRACKERS.{tracker}.{key}"
                if comment_key in config_comments:
                    print("\n" + "\n".join(config_comments[comment_key]))

                if isinstance(default_value, bool):
                    default_str = str(default_value)
                    existing_value = str(existing_tracker_config.get(key, default_value))
                    value = get_user_input(f"Tracker setting '{key}'? (True/False)",
                                           default=default_str,
                                           existing_value=existing_value)
                    tracker_config[key] = value
                else:
                    is_password = key in ["api_key", "passkey", "rss_key"]
                    tracker_config[key] = get_user_input(
                        f"Tracker setting '{key}'",
                        default=str(default_value) if default_value else "",
                        is_password=is_password,
                        existing_value=existing_tracker_config.get(key)
                    )
        else:
            print(f"[!] No example config found for tracker '{tracker}'.")

        trackers_config[tracker] = tracker_config

    # Offer to add more trackers from the example config
    remaining_trackers = [t for t in example_tracker_list if t.upper() not in [x.upper() for x in trackers_list]]
    if remaining_trackers:
        print("\nOther trackers available in the example config that are not in your list:")
        print(", ".join(remaining_trackers))
        add_more = get_user_input(
            "Enter any additional tracker acronyms to add (comma separated), or leave blank to skip"
        )
        additional = [t.strip().upper() for t in add_more.split(",") if t.strip()]
        for tracker in additional:
            if tracker in trackers_config:
                continue  # Already configured
            print(f"\nConfiguring {tracker}:")
            example_tracker = example_trackers.get(tracker, {})
            tracker_config = {}
            if example_tracker and isinstance(example_tracker, dict):
                for key, default_value in example_tracker.items():
                    comment_key = f"TRACKERS.{tracker}.{key}"
                    if comment_key in config_comments:
                        print("\n" + "\n".join(config_comments[comment_key]))

                    if isinstance(default_value, bool):
                        default_str = str(default_value)
                        value = get_user_input(f"Tracker setting '{key}'? (True/False)",
                                               default=default_str)
                        tracker_config[key] = value
                    else:
                        is_password = key in ["api_key", "passkey", "rss_key"]
                        tracker_config[key] = get_user_input(
                            f"Tracker setting '{key}'",
                            default=str(default_value) if default_value else "",
                            is_password=is_password
                        )
            else:
                print(f"[!] No example config found for tracker '{tracker}'.")
            trackers_config[tracker] = tracker_config

    return trackers_config


def configure_torrent_clients(existing_clients=None, example_clients=None, default_client_name=None, config_comments=None):
    """
    Helper to configure the TORRENT_CLIENTS section.
    Returns a dict with the configured client(s) and the selected default client name.
    """
    config_clients = {}
    existing_clients = existing_clients or {}
    example_clients = example_clients or {}
    config_comments = config_comments or {}

    # Only use default_client_name if provided and in existing_clients
    if default_client_name and default_client_name in existing_clients:
        keep_existing_client = input(f"Do you want to keep the existing client '{default_client_name}'? (y/n): ").lower() == "y"
        if not keep_existing_client:
            print("What client do you want to use instead?")
            print("Available clients in example config:")
            for client_name in example_clients:
                print(f"  - {client_name}")
            new_client = get_user_input("Enter the name of the torrent client to use",
                                        default="qbittorrent",
                                        existing_value=default_client_name)
            default_client_name = new_client
    else:
        # No default client specified or not in existing_clients, ask user to select one
        print("No default client found. Let's configure one.")
        print("What client do you want to use?")
        print("Available clients in example config:")
        for client_name in example_clients:
            print(f"  - {client_name}")
        default_client_name = get_user_input("Enter the name of the torrent client to use",
                                             default="qbittorrent")

    # Use existing config for the selected client if present, else use example config
    existing_client_config = existing_clients.get(default_client_name, {})
    example_client_config = example_clients.get(default_client_name, {})

    if not example_client_config:
        print(f"[!] No example config found for client '{default_client_name}'.")
        if existing_client_config:
            print(f"[i] Using existing config for '{default_client_name}'")
            config_clients[default_client_name] = existing_client_config
        return config_clients, default_client_name

    print(f"\nConfiguring client: {default_client_name}")

    # Set the client type from the example config, never prompt the user
    client_type = example_client_config.get("torrent_client", default_client_name)
    client_config = {"torrent_client": client_type}

    # Process all other client settings
    for key, default_value in example_client_config.items():
        if key == "torrent_client":
            continue  # Already handled above

        comment_key = f"TORRENT_CLIENTS.{default_client_name}.{key}"
        if comment_key in config_comments:
            print("\n" + "\n".join(config_comments[comment_key]))
        elif key in config_comments:
            print("\n" + "\n".join(config_comments[key]))

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

    config_clients[default_client_name] = client_config
    return config_clients, default_client_name


def generate_config_file(config_data, existing_path=None):
    """Generate the config.py file from the config dictionary"""
    # Create output directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Determine the output path
    if existing_path:
        config_path = existing_path
        backup_path = Path(f"{existing_path}.bak")
        # Create backup of existing config
        if existing_path.exists():
            with open(existing_path, "r", encoding="utf-8") as src:
                with open(backup_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            print(f"\n[✓] Created backup of existing config at {backup_path}")
    else:
        config_path = Path("data/config.py")
        if config_path.exists():
            overwrite = input(f"{config_path} already exists. Overwrite? (y/n): ").lower()
            if overwrite != "y":
                print("Aborted.")
                return False

    # Convert boolean values in config to proper Python booleans
    def format_config(obj):
        if isinstance(obj, dict):
            # Process each key-value pair in dictionaries
            return {k: format_config(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Process each item in lists
            return [format_config(item) for item in obj]
        elif isinstance(obj, str):
            # Convert string "true"/"false" to Python True/False
            if obj.lower() == "true":
                return True
            elif obj.lower() == "false":
                return False
        # Return unchanged for other types
        return obj

    # Format config with proper Python booleans
    formatted_config = format_config(config_data)

    # Generate the config file with properly formatted Python syntax
    with open(config_path, "w", encoding="utf-8") as file:
        file.write("config = {\n")

        # Custom formatting function to create Python dict with trailing commas
        def write_dict(d, indent_level=1):
            indent = "    " * indent_level
            for key, value in d.items():
                file.write(f"{indent}{json.dumps(key)}: ")

                if isinstance(value, dict):
                    file.write("{\n")
                    write_dict(value, indent_level + 1)
                    file.write(f"{indent}}},\n")
                elif isinstance(value, bool):
                    # Ensure booleans are capitalized
                    file.write(f"{str(value).capitalize()},\n")
                else:
                    # Other values with trailing comma
                    file.write(f"{json.dumps(value, ensure_ascii=False)},\n")

        write_dict(formatted_config)
        file.write("}\n")

    print(f"\n[✓] Configuration file created at {config_path}")
    print("Remember to add more trackers or configure additional settings by editing this file directly.")
    return True


if __name__ == "__main__":
    print("Upload Assistant Configuration Generator")
    print("========================================")

    # Get example configuration structure first
    example_config, config_comments = read_example_config()

    # Try to load existing config
    existing_config, existing_path = load_existing_config()

    if existing_config and example_config:
        use_existing = input("\nExisting configuration found. Would you like to use it as a starting point? (y/n): ").lower()
        if use_existing == "y":
            print("\n[i] Using existing configuration as a template.")

            # Check for unexpected keys in existing config
            existing_config = validate_config(existing_config, example_config)

            # Start with the existing config
            config_data = existing_config.copy()

            # Ask about updating each main section separately
            print("\nYou can choose which sections of the configuration to update:")

            # DEFAULT section
            update_default = input("Update DEFAULT section? (y/n): ").lower() == "y"
            if update_default:
                existing_defaults = existing_config.get("DEFAULT", {})
                example_defaults = example_config.get("DEFAULT", {})
                config_data["DEFAULT"] = configure_default_section(existing_defaults, example_defaults, config_comments)
                # Set default client name (if needed)
                config_data["DEFAULT"]["default_torrent_client"] = config_data["DEFAULT"].get("default_torrent_client", "qbittorrent")
            else:
                print("[i] Keeping existing DEFAULT section")
                print()

            # TRACKERS section
            update_trackers = input("Update TRACKERS section? (y/n): ").lower() == "y"
            if update_trackers:
                existing_trackers = existing_config.get("TRACKERS", {})
                example_trackers = example_config.get("TRACKERS", {})
                config_data["TRACKERS"] = configure_trackers(existing_trackers, example_trackers, config_comments)
            else:
                print("[i] Keeping existing TRACKERS section")
                print()

            # TORRENT_CLIENTS section
            update_clients = input("Update TORRENT_CLIENTS section? (y/n): ").lower() == "y"
            if update_clients:
                print("\n====== TORRENT CLIENT ======")
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
                print("[i] Keeping existing TORRENT_CLIENTS section")
                print()

            missing_default_keys = []
            if "DEFAULT" in example_config and "DEFAULT" in config_data:
                def find_missing_default_keys(example_section, existing_section, path=""):
                    for key in example_section:
                        if key not in existing_section:
                            missing_default_keys.append(key)
                find_missing_default_keys(example_config["DEFAULT"], config_data["DEFAULT"])

            if missing_default_keys:
                print("\n[!] Your existing config is missing these keys from example-config:")

                # Only prompt for the missing keys
                missing_defaults = {k: example_config["DEFAULT"][k] for k in missing_default_keys}
                # Use empty dict for existing values so only defaults are shown
                added_defaults = configure_default_section({}, missing_defaults, config_comments)
                config_data["DEFAULT"].update(added_defaults)

            # Generate the updated config file
            generate_config_file(config_data, existing_path)
        else:
            print("\n[i] Starting with fresh configuration.")
            config_data = {}

            # DEFAULT section
            example_defaults = example_config.get("DEFAULT", {})
            config_data["DEFAULT"] = configure_default_section({}, example_defaults, config_comments)
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

            generate_config_file(config_data)
    else:
        print("\n[i] No existing configuration found. Creating a new one.")

        config_data = {}

        # DEFAULT section
        example_defaults = example_config.get("DEFAULT", {})
        config_data["DEFAULT"] = configure_default_section({}, example_defaults, config_comments)
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

        generate_config_file(config_data)
