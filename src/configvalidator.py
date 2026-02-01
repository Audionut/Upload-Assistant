# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
"""
Config validation helper for Upload Assistant.
Validates the user's config.py against expected structure and types.
"""
from typing import Any, Optional, cast

# Required top-level sections
REQUIRED_SECTIONS = ["DEFAULT", "TRACKERS"]

# Optional top-level sections
OPTIONAL_SECTIONS = ["IMAGES", "TORRENT_CLIENTS", "DISCORD"]

# Required keys in DEFAULT section (critical for operation)
REQUIRED_DEFAULT_KEYS: dict[str, type] = {
    "tmdb_api": str,
}

# Expected types for common DEFAULT keys (for type validation, not required)
DEFAULT_KEY_TYPES: dict[str, tuple[type, ...]] = {
    "update_notification": (bool,),
    "verbose_notification": (bool,),
    "tmdb_api": (str,),
    "btn_api": (str,),
    "img_host_1": (str,),
    "img_host_2": (str,),
    "img_host_3": (str,),
    "imgbb_api": (str,),
    "ptpimg_api": (str,),
    "lensdump_api": (str,),
    "ptscreens_api": (str,),
    "onlyimage_api": (str,),
    "add_logo": (bool,),
    "logo_size": (str, int),
    "episode_overview": (bool,),
    "screens": (str, int),
    "cutoff_screens": (str, int),
    "thumbnail_size": (str, int),
    "frame_overlay": (bool,),
    "tone_map": (bool,),
    "use_libplacebo": (bool,),
    "ffmpeg_is_good": (bool,),
    "ffmpeg_warmup": (bool,),
    "ffmpeg_compression": (str, int),
    "process_limit": (str, int),
    "threads": (str, int),
    "ffmpeg_limit": (bool,),
    "multiScreens": (str, int),
    "pack_thumb_size": (str, int),
    "charLimit": (str, int),
    "fileLimit": (str, int),
    "processLimit": (str, int),
    "default_torrent_client": (str,),
    "skip_auto_torrent": (bool,),
    "sfx_on_prompt": (bool,),
    "tracker_pass_checks": (str, int),
    "use_largest_playlist": (bool,),
    "keep_images": (bool,),
    "only_id": (bool,),
    "use_sonarr": (bool,),
    "use_radarr": (bool,),
    "mkbrr": (bool,),
    "mkbrr_threads": (str, int),
    "user_overrides": (bool,),
    "ping_unit3d": (bool,),
    "get_bluray_info": (bool,),
    "add_bluray_link": (bool,),
    "use_bluray_images": (bool,),
    "bluray_image_size": (str, int),
    "bluray_score": (float, int),
    "bluray_single_score": (float, int),
    "keep_meta": (bool,),
    "show_upload_duration": (bool,),
    "print_tracker_messages": (bool,),
    "print_tracker_links": (bool,),
    "emby_dir": (str, type(None)),
    "emby_tv_dir": (str, type(None)),
    "search_requests": (bool,),
    "check_predb": (bool,),
    "prefer_max_16_torrent": (bool,),
    "cross_seeding": (bool,),
    "cross_seed_check_everything": (bool,),
    "auto_mode": (bool, str),
}

# Valid image hosts
VALID_IMAGE_HOSTS = [
    "imgbb", "ptpimg", "imgbox", "pixhost", "lensdump", "ptscreens",
    "onlyimage", "dalexni", "zipline", "passtheimage", "seedpool_cdn", "sharex", "utppm", ""
]

# Image hosts that require API keys and their corresponding config key names
IMAGE_HOST_API_KEYS: dict[str, str] = {
    "imgbb": "imgbb_api",
    "ptpimg": "ptpimg_api",
    "lensdump": "lensdump_api",
    "ptscreens": "ptscreens_api",
    "onlyimage": "onlyimage_api",
    "dalexni": "dalexni_api",
    "passtheimage": "passtheima_ge_api",
    "seedpool_cdn": "seedpool_cdn_api",
    "sharex": "sharex_api_key",
    "zipline": "zipline_api_key",
    "utppm": "utppm_api",
    # imgbox and pixhost don't require API keys
}

# Valid torrent client types (must match example-config.py)
VALID_TORRENT_CLIENTS = ["qbit", "rtorrent", "deluge", "transmission", "watch"]


class ConfigValidationError(Exception):
    """Raised when config validation fails with critical errors."""
    pass


class ConfigValidationWarning:
    """Represents a non-critical config warning."""
    def __init__(self, message: str, key: str = "", section: str = ""):
        self.message = message
        self.key = key
        self.section = section

    def __str__(self) -> str:
        location = ""
        if self.section:
            location = f"[{self.section}]"
            if self.key:
                location += f"[{self.key}]"
        elif self.key:
            location = f"[{self.key}]"

        return f"{location} {self.message}" if location else self.message


def _as_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def validate_config(
    config: Any,
    active_trackers: Optional[list[str]] = None,
    active_imghost: Optional[str] = None
) -> tuple[bool, list[str], list[ConfigValidationWarning]]:
    """
    Validate the config dictionary structure and types.

    Args:
        config: The config object to validate
        active_trackers: List of tracker names that will be used (from meta['trackers'])
                        If None, uses default_trackers from config
        active_imghost: The image host to use (from meta['imghost'])
                       If None, uses img_host_1 from config

    Returns:
        Tuple of (is_valid, errors, warnings)
        - is_valid: True if config passes critical validation
        - errors: List of critical error messages
        - warnings: List of non-critical warnings
    """
    errors: list[str] = []
    warnings: list[ConfigValidationWarning] = []

    # Check if config is a dictionary
    if not isinstance(config, dict):
        errors.append(f"Config must be a dictionary, got {type(config).__name__}")
        return False, errors, warnings

    config_dict = cast(dict[str, Any], config)

    # Check required sections
    for section in REQUIRED_SECTIONS:
        if section not in config_dict:
            errors.append(f"Missing required config section: '{section}'")
        elif not isinstance(config_dict[section], dict):
            errors.append(f"Config section '{section}' must be a dictionary, got {type(config_dict[section]).__name__}")

    # If we have critical section errors, return early
    if errors:
        return False, errors, warnings

    # Validate DEFAULT section
    default_errors, default_warnings = _validate_default_section(_as_dict(config_dict.get("DEFAULT")))
    errors.extend(default_errors)
    warnings.extend(default_warnings)

    # Validate TRACKERS section
    # Determine which trackers are active
    trackers_section = _as_dict(config_dict.get("TRACKERS"))
    if active_trackers is None:
        # Fall back to default_trackers from config
        default_trackers_val = trackers_section.get("default_trackers", "")
        if isinstance(default_trackers_val, str) and default_trackers_val.strip():
            active_trackers = [t.strip().upper() for t in default_trackers_val.split(",") if t.strip()]
        elif isinstance(default_trackers_val, list):
            active_trackers = [
                str(t).strip().upper()
                for t in cast(list[Any], default_trackers_val)
                if isinstance(t, str) and t.strip()
            ]
        else:
            active_trackers = []

    tracker_errors, tracker_warnings = _validate_trackers_section(trackers_section, active_trackers)
    errors.extend(tracker_errors)
    warnings.extend(tracker_warnings)

    # Validate TORRENT_CLIENTS section if present
    if "TORRENT_CLIENTS" in config_dict:
        client_errors, client_warnings = _validate_torrent_clients_section(_as_dict(config_dict.get("TORRENT_CLIENTS")))
        errors.extend(client_errors)
        warnings.extend(client_warnings)

    # Validate DISCORD section if present
    if "DISCORD" in config_dict:
        discord_errors, discord_warnings = _validate_discord_section(_as_dict(config_dict.get("DISCORD")))
        errors.extend(discord_errors)
        warnings.extend(discord_warnings)

    # Cross-reference validation for torrent client configuration
    default_section = _as_dict(config_dict.get("DEFAULT"))
    torrent_clients = _as_dict(config_dict.get("TORRENT_CLIENTS"))
    defined_clients = list(torrent_clients.keys())

    if default_section:
        default_client = default_section.get("default_torrent_client", "")

        # Validate injecting_client_list
        injecting_list = default_section.get("injecting_client_list")
        injecting_clients: list[str] = []
        if injecting_list is not None:
            if isinstance(injecting_list, str):
                # String is valid - gets converted to single-item list at runtime
                if injecting_list.strip():
                    injecting_clients = [injecting_list.strip()]
            elif isinstance(injecting_list, list):
                # List is valid - validate each item
                for i, item in enumerate(cast(list[Any], injecting_list)):
                    if item and isinstance(item, str) and item.strip():
                        injecting_clients.append(item.strip())
                    elif item and not isinstance(item, str):
                        warnings.append(ConfigValidationWarning(
                            f"Item at index {i} should be a string, got {type(item).__name__}",
                            key="injecting_client_list",
                            section="DEFAULT"
                        ))
            else:
                warnings.append(ConfigValidationWarning(
                    f"Should be a list or string, got {type(injecting_list).__name__}. "
                    "Will fall back to default_torrent_client. "
                    "Example: ['Client1', 'Client2'] or 'Client1'",
                    key="injecting_client_list",
                    section="DEFAULT"
                ))

        # Validate searching_client_list
        searching_list = default_section.get("searching_client_list")
        searching_clients: list[str] = []
        if searching_list is not None:
            if isinstance(searching_list, list):
                for i, item in enumerate(cast(list[Any], searching_list)):
                    if item and isinstance(item, str) and item.strip():
                        searching_clients.append(item.strip())
                    elif item and not isinstance(item, str):
                        warnings.append(ConfigValidationWarning(
                            f"Item at index {i} should be a string, got {type(item).__name__}",
                            key="searching_client_list",
                            section="DEFAULT"
                        ))
            else:
                warnings.append(ConfigValidationWarning(
                    f"Should be a list, got {type(searching_list).__name__}. "
                    "Will fall back to default_torrent_client. "
                    "Example: ['Client1', 'Client2']",
                    key="searching_client_list",
                    section="DEFAULT"
                ))

        # Check that referenced client names exist in TORRENT_CLIENTS
        if torrent_clients:
            warnings.extend([
                ConfigValidationWarning(
                    f"References undefined client '{client_name}'",
                    key="injecting_client_list",
                    section="DEFAULT"
                )
                for client_name in injecting_clients
                if client_name != "none" and client_name not in torrent_clients
            ])

            warnings.extend([
                ConfigValidationWarning(
                    f"References undefined client '{client_name}'",
                    key="searching_client_list",
                    section="DEFAULT"
                )
                for client_name in searching_clients
                if client_name != "none" and client_name not in torrent_clients
            ])

        # Check default_torrent_client - only required if no client lists are populated
        if default_client:
            if default_client not in torrent_clients:
                if defined_clients:
                    warnings.append(ConfigValidationWarning(
                        f"References undefined client '{default_client}'. Defined clients: {', '.join(defined_clients)}",
                        key="default_torrent_client",
                        section="DEFAULT"
                    ))
                else:
                    warnings.append(ConfigValidationWarning(
                        f"References '{default_client}' but no clients defined in TORRENT_CLIENTS",
                        key="default_torrent_client",
                        section="DEFAULT"
                    ))
        elif not injecting_clients and not searching_clients and defined_clients:
            # Only warn if default_torrent_client is empty AND no client lists are configured
            warnings.append(ConfigValidationWarning(
                "No default_torrent_client, injecting_client_list, or searching_client_list configured",
                key="default_torrent_client",
                section="DEFAULT"
            ))

    # Check for unknown top-level sections (warning only)
    known_sections = set(REQUIRED_SECTIONS + OPTIONAL_SECTIONS)
    warnings.extend([
        ConfigValidationWarning(
            f"Unknown config section '{section}' - this may be intentional",
            section=section
        )
        for section in config_dict
        if section not in known_sections
    ])

    # Validate image host API keys
    default_section = _as_dict(config_dict.get("DEFAULT"))
    if default_section:
        # Determine which image hosts are active
        active_hosts: list[str] = []

        # If imghost specified from command line, use that
        if active_imghost and active_imghost.strip():
            active_hosts = [active_imghost.strip()]
        else:
            # Collect all configured img_host_* values
            for i in range(1, 10):
                host_key = f"img_host_{i}"
                host_value = default_section.get(host_key, "")
                if isinstance(host_value, str) and host_value.strip():
                    active_hosts.append(host_value.strip())

        # Check that each active host has its required API key
        for host in active_hosts:
            if host in IMAGE_HOST_API_KEYS:
                api_key_name = IMAGE_HOST_API_KEYS[host]
                api_key_value = default_section.get(api_key_name, "")
                if not api_key_value or (isinstance(api_key_value, str) and not api_key_value.strip()):
                    errors.append(
                        f"Image host '{host}' requires API key '{api_key_name}' but it is not set"
                    )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def _validate_default_section(default: dict[str, Any]) -> tuple[list[str], list[ConfigValidationWarning]]:
    """Validate the DEFAULT config section."""
    errors: list[str] = []
    warnings: list[ConfigValidationWarning] = []

    # Check required keys
    for key, expected_type in REQUIRED_DEFAULT_KEYS.items():
        if key not in default:
            errors.append(f"Missing required key in DEFAULT section: '{key}'")
        elif not isinstance(default[key], expected_type):
            errors.append(
                f"DEFAULT['{key}'] must be {expected_type.__name__}, "
                f"got {type(default[key]).__name__}"
            )

    # Check tmdb_api is not empty (critical)
    tmdb_api = default.get("tmdb_api", "")
    if isinstance(tmdb_api, str) and not tmdb_api.strip():
        errors.append("DEFAULT['tmdb_api'] is empty - TMDB API key is required for operation")

    # Validate types for known keys (warnings only for type mismatches)
    for key, expected_types in DEFAULT_KEY_TYPES.items():
        if key in default and default[key] is not None:
            value = default[key]
            if not isinstance(value, expected_types):
                warnings.append(ConfigValidationWarning(
                    f"Expected type {' or '.join(t.__name__ for t in expected_types)}, "
                    f"got {type(value).__name__}",
                    key=key,
                    section="DEFAULT"
                ))

    # Validate image hosts
    for i in range(1, 10):
        host_key = f"img_host_{i}"
        if host_key in default:
            host_value = default[host_key]
            if isinstance(host_value, str) and host_value and host_value not in VALID_IMAGE_HOSTS:
                warnings.append(ConfigValidationWarning(
                    f"Unknown image host '{host_value}'. Valid hosts: {', '.join(h for h in VALID_IMAGE_HOSTS if h)}",
                    key=host_key,
                    section="DEFAULT"
                ))

    # Validate numeric string values can be parsed
    numeric_keys = ["screens", "cutoff_screens", "thumbnail_size", "process_limit", "threads",
                    "multiScreens", "pack_thumb_size", "charLimit", "fileLimit", "processLimit",
                    "tracker_pass_checks", "mkbrr_threads", "ffmpeg_compression"]
    for key in numeric_keys:
        if key in default:
            value = default[key]
            if isinstance(value, str):
                try:
                    int(value)
                except ValueError:
                    warnings.append(ConfigValidationWarning(
                        f"Cannot parse '{value}' as integer",
                        key=key,
                        section="DEFAULT"
                    ))

    return errors, warnings


def _validate_trackers_section(
    trackers: dict[str, Any],
    active_trackers: list[str]
) -> tuple[list[str], list[ConfigValidationWarning]]:
    """Validate the TRACKERS config section."""
    errors: list[str] = []
    warnings: list[ConfigValidationWarning] = []

    # Normalize active trackers to uppercase for comparison
    active_set = {t.upper() for t in active_trackers}

    # Check for default_trackers key
    if "default_trackers" not in trackers:
        warnings.append(ConfigValidationWarning(
            "No 'default_trackers' defined - you'll need to specify trackers via command line",
            key="default_trackers",
            section="TRACKERS"
        ))

    # Validate individual tracker configs
    for tracker_name, tracker_config in trackers.items():
        if tracker_name == "default_trackers":
            continue

        is_active = tracker_name.upper() in active_set

        if not isinstance(tracker_config, dict):
            warnings.append(ConfigValidationWarning(
                f"Tracker config must be a dictionary, got {type(tracker_config).__name__}",
                key=tracker_name,
                section="TRACKERS"
            ))
            continue
        tracker_config_dict = cast(dict[str, Any], tracker_config)

        # Check for common tracker config issues
        if "api_key" in tracker_config_dict:
            api_key = tracker_config_dict["api_key"]
            if isinstance(api_key, str) and api_key and not api_key.strip():
                warnings.append(ConfigValidationWarning(
                    "api_key is whitespace-only",
                    key=tracker_name,
                    section="TRACKERS"
                ))

        # Only check announce_url placeholders for active trackers
        if is_active and "announce_url" in tracker_config_dict:
            announce = tracker_config_dict["announce_url"]
            if isinstance(announce, str) and announce and "<" in announce and ">" in announce:
                # This is an error for active trackers, not just a warning
                errors.append(
                    f"[TRACKERS][{tracker_name}] announce_url contains placeholder "
                    f"(e.g., <PASSKEY>) - replace with actual value"
                )

        # Check boolean fields are actually booleans (must be real bool, not string)
        bool_fields = ["anon", "useAPI", "modq", "draft", "draft_default", "img_rehost"]
        for field in bool_fields:
            if field in tracker_config_dict:
                value = tracker_config_dict[field]
                if not isinstance(value, bool):
                    warnings.append(ConfigValidationWarning(
                        f"'{field}' must be a boolean type (True/False), got {type(value).__name__}: {value!r}",
                        key=tracker_name,
                        section="TRACKERS"
                    ))

    return errors, warnings


def _validate_torrent_clients_section(clients: dict[str, Any]) -> tuple[list[str], list[ConfigValidationWarning]]:
    """Validate the TORRENT_CLIENTS config section."""
    errors: list[str] = []
    warnings: list[ConfigValidationWarning] = []

    for client_name, client_config in clients.items():
        if not isinstance(client_config, dict):
            warnings.append(ConfigValidationWarning(
                f"Client config must be a dictionary, got {type(client_config).__name__}",
                key=client_name,
                section="TORRENT_CLIENTS"
            ))
            continue
        client_config_dict = cast(dict[str, Any], client_config)

        # Check torrent_client type is valid
        client_type = client_config_dict.get("torrent_client", "")
        if client_type and client_type not in VALID_TORRENT_CLIENTS:
            warnings.append(ConfigValidationWarning(
                f"Unknown torrent_client type '{client_type}'",
                key=client_name,
                section="TORRENT_CLIENTS"
            ))

        # Validate linking option
        linking = client_config_dict.get("linking", "")
        if linking and linking not in ("symlink", "hardlink", ""):
            warnings.append(ConfigValidationWarning(
                f"Invalid linking option '{linking}'. Use 'symlink', 'hardlink', or empty string",
                key=client_name,
                section="TORRENT_CLIENTS"
            ))

        # Check path mappings have matching lengths
        local_paths = client_config_dict.get("local_path", [])
        remote_paths = client_config_dict.get("remote_path", [])
        if isinstance(local_paths, list) and isinstance(remote_paths, list):
            local_paths_list = cast(list[Any], local_paths)
            remote_paths_list = cast(list[Any], remote_paths)
            if len(local_paths_list) != len(remote_paths_list) and local_paths_list and remote_paths_list:
                warnings.append(ConfigValidationWarning(
                    f"local_path ({len(local_paths_list)} items) and remote_path ({len(remote_paths_list)} items) should have matching lengths",
                    key=client_name,
                    section="TORRENT_CLIENTS"
                ))

    return errors, warnings


def _validate_discord_section(discord: dict[str, Any]) -> tuple[list[str], list[ConfigValidationWarning]]:
    """Validate the DISCORD config section."""
    errors: list[str] = []
    warnings: list[ConfigValidationWarning] = []

    use_discord = discord.get("use_discord", False)
    if use_discord:
        # If Discord is enabled, check for required fields
        if not discord.get("discord_bot_token"):
            warnings.append(ConfigValidationWarning(
                "Discord is enabled but 'discord_bot_token' is empty",
                key="discord_bot_token",
                section="DISCORD"
            ))
        if not discord.get("discord_channel_id"):
            warnings.append(ConfigValidationWarning(
                "Discord is enabled but 'discord_channel_id' is empty",
                key="discord_channel_id",
                section="DISCORD"
            ))

    return errors, warnings


def group_warnings(warnings: list[ConfigValidationWarning]) -> list[str]:
    """
    Group warnings with the same section and message, combining keys.

    For example, multiple trackers with the same warning become:
    [TRACKERS][BLU, HDB] api_key is whitespace-only
    """
    from collections import defaultdict

    # Group by (section, message) -> list of keys
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)

    for warning in warnings:
        group_key = (warning.section, warning.message)
        if warning.key:
            grouped[group_key].append(warning.key)
        else:
            # Warnings without keys get their own entry
            grouped[group_key].append("")

    result: list[str] = []
    for (section, message), keys in grouped.items():
        # Filter out empty keys and deduplicate
        non_empty_keys = [k for k in keys if k]

        if section:
            if non_empty_keys:
                # Multiple keys with same message - combine them
                keys_str = ", ".join(non_empty_keys)
                result.append(f"[{section}][{keys_str}] {message}")
            else:
                result.append(f"[{section}] {message}")
        elif non_empty_keys:
            keys_str = ", ".join(non_empty_keys)
            result.append(f"[{keys_str}] {message}")
        else:
            result.append(message)

    return result


def format_validation_results(
    is_valid: bool,
    errors: list[str],
    warnings: list[ConfigValidationWarning],
    show_warnings: bool = True
) -> str:
    """Format validation results for display."""
    lines: list[str] = []

    if errors:
        lines.append("Config Validation Errors:")
        lines.extend([f"  ✗ {error}" for error in errors])

    if show_warnings and warnings:
        if lines:
            lines.append("")
        lines.append("Config Validation Warnings:")
        grouped = group_warnings(warnings)
        lines.extend([f"  ⚠ {warning_str}" for warning_str in grouped])

    if is_valid and not warnings:
        lines.append("Config validation passed.")
    elif is_valid:
        lines.append(f"\nConfig validation passed with {len(warnings)} warning(s).")

    return "\n".join(lines)
