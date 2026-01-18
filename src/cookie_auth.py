# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import http.cookiejar
import importlib
import json
import os
import pickle  # nosec B403 - Only used for legacy cookie migration
import re
import stat
import traceback
from typing import Any, Optional, Union, cast

import aiofiles
import httpx
from bs4 import BeautifulSoup
from bs4.element import AttributeValueList
from rich.panel import Panel
from rich.table import Table

from src.console import console
from src.trackers.COMMON import COMMON


def _attr_to_string(value: Union[str, AttributeValueList, None]) -> str:
    """Convert BeautifulSoup attribute values to a plain string."""
    if isinstance(value, str):
        return value
    if isinstance(value, AttributeValueList):
        return " ".join(value)
    return ""


class CookieValidator:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        pass

    async def load_session_cookies(self, meta: dict[str, Any], tracker: str) -> Optional[http.cookiejar.MozillaCookieJar]:
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{tracker}.txt")
        cookie_jar = http.cookiejar.MozillaCookieJar(cookie_file)

        try:
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except http.cookiejar.LoadError as e:
            console.print(f"{tracker}: Failed to load the cookie file: {e}")
            console.print(f"{tracker}: Please ensure the cookie file is in the correct format (Netscape).")
            return None
        except FileNotFoundError:
            # Attempt automatic login for AR tracker
            if tracker == 'AR':
                console.print(f"{tracker}: [yellow]Cookie file not found. Attempting automatic login...[/yellow]")
                if await self.ar_login(meta, tracker, cookie_file):
                    # Try loading the newly created cookie file
                    try:
                        cookie_jar.load(ignore_discard=True, ignore_expires=True)
                        return cookie_jar
                    except Exception as e:
                        console.print(f"{tracker}: Failed to load cookies after login: {e}")
                        return None
                else:
                    console.print(f"{tracker}: Automatic login failed.")
                    return None

            console.print(
                f"{tracker}: [red]Cookie file not found.[/red]\n"
                f"{tracker}: You must first log in through your usual browser and export the cookies to: [yellow]{cookie_file}[/yellow]\n"
                f'{tracker}: Cookies can be exported using browser extensions like "cookies.txt" (Firefox) or "Get cookies.txt LOCALLY" (Chrome).'
            )
            return None

        return cookie_jar

    async def save_session_cookies(self, tracker: str, cookie_jar: Optional[http.cookiejar.MozillaCookieJar]) -> None:
        """Save updated cookies after a successful validation."""
        if not cookie_jar:
            console.print(f"{tracker}: Cookie jar not initialized, cannot save cookies.")
            return

        try:
            cookie_jar.save(ignore_discard=True, ignore_expires=True)
        except Exception as e:
            console.print(f"{tracker}: Failed to update the cookie file: {e}")

    async def get_ar_auth_key(self, meta: dict[str, Any], tracker: str) -> Optional[str]:
        """Retrieve the saved auth key for AR tracker."""
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{tracker}.txt")
        auth_file = cookie_file.replace('.txt', '_auth.txt')

        if os.path.exists(auth_file):
            try:
                async with aiofiles.open(auth_file, encoding='utf-8') as f:
                    auth_key = await f.read()
                    auth_key = str(auth_key).strip()
                    if auth_key:
                        return auth_key
            except Exception as e:
                console.print(f"{tracker}: Error reading auth key: {e}")

        return None

    async def ar_login(self, meta: dict[str, Any], tracker: str, cookie_file: str) -> bool:
        """Perform automatic login to AR and save cookies in Netscape format."""
        username = self.config['TRACKERS'][tracker].get('username', '').strip()
        password = self.config['TRACKERS'][tracker].get('password', '').strip()

        if not username or not password:
            console.print(f"{tracker}: Username or password not configured in config.")
            return False

        base_url = 'https://alpharatio.cc'
        login_url = f'{base_url}/login.php'

        headers = {
            "User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
                # Perform login
                login_data = {
                    "username": username,
                    "password": password,
                    "keeplogged": "1",
                    "login": "Login",
                }

                response = await client.post(login_url, data=login_data)

                if response.status_code != 200:
                    console.print(f"{tracker}: Login failed with status code {response.status_code}")
                    return False

                # Check for login success by looking for error indicators
                if 'login.php?act=recover' in response.text or 'Forgot your password' in response.text:
                    console.print(f"{tracker}: [red]Login failed. Please check your username and password.[/red]")
                    if meta.get('debug', False):
                        failure_path = f"{meta['base_dir']}/tmp/{meta.get('uuid', 'debug')}/[{tracker}]Failed_Login.html"
                        os.makedirs(os.path.dirname(failure_path), exist_ok=True)
                        async with aiofiles.open(failure_path, "w", encoding="utf-8") as f:
                            await f.write(response.text)
                        console.print(f"Login response saved to [yellow]{failure_path}[/yellow] for debugging.")
                    return False

                # Validate we're logged in by checking the torrents page
                test_response = await client.get(f'{base_url}/torrents.php')
                if test_response.status_code == 200 and 'login.php?act=recover' not in test_response.text:
                    console.print(f"{tracker}: [green]Login successful![/green]")

                    # Extract auth key from the response page
                    auth_key = None
                    soup = BeautifulSoup(test_response.text, 'html.parser')
                    logout_link = soup.find('a', href=True, text='Logout')
                    if logout_link:
                        href = _attr_to_string(logout_link.get('href'))
                        auth_match = re.search(r'auth=([^&]+)', href)
                        if auth_match:
                            auth_key = auth_match.group(1)
                            console.print(f"{tracker}: [green]Auth key extracted successfully[/green]")

                    # Save cookies in Netscape format
                    os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
                    cookie_jar = http.cookiejar.MozillaCookieJar(cookie_file)

                    # Convert httpx cookies to MozillaCookieJar format
                    for cookie_name in client.cookies:
                        # Get the cookie object for additional attributes
                        for cookie in client.cookies.jar:
                            if cookie.name == cookie_name:
                                rest = getattr(cookie, "_rest", {})
                                rest_map = cast(dict[str, Any], rest) if isinstance(rest, dict) else {}
                                ck = http.cookiejar.Cookie(
                                    version=0,
                                    name=cookie.name,
                                    value=cookie.value,
                                    port=None,
                                    port_specified=False,
                                    domain=cookie.domain if cookie.domain else '.alpharatio.cc',
                                    domain_specified=True,
                                    domain_initial_dot=(cookie.domain or '.alpharatio.cc').startswith('.'),
                                    path=cookie.path if cookie.path else '/',
                                    path_specified=True,
                                    secure=bool(rest_map.get('secure')) if rest_map else True,
                                    expires=None,
                                    discard=False,
                                    comment=None,
                                    comment_url=None,
                                    rest={},
                                    rfc2109=False
                                )
                                cookie_jar.set_cookie(ck)
                                break

                    cookie_jar.save(ignore_discard=True, ignore_expires=True)
                    console.print(f"{tracker}: [green]Cookies saved to {cookie_file}[/green]")

                    # Save auth key to a separate file if found
                    if auth_key:
                        auth_file = cookie_file.replace('.txt', '_auth.txt')
                        async with aiofiles.open(auth_file, 'w', encoding='utf-8') as f:
                            await f.write(auth_key)
                        console.print(f"{tracker}: [green]Auth key saved to {auth_file}[/green]")

                    return True

                console.print(f"{tracker}: [red]Login validation failed.[/red]")
                return False

        except httpx.TimeoutException:
            console.print(f"{tracker}: Connection timed out. The site may be down or unreachable.")
            return False
        except httpx.ConnectError:
            console.print(f"{tracker}: Failed to connect. The site may be down or your connection is blocked.")
            return False
        except Exception as e:
            console.print(f"{tracker}: Login error: {e}")
            if meta.get('debug', False):
                console.print(traceback.format_exc())
            return False

    async def cookie_validation(
        self,
        meta: dict[str, Any],
        tracker: str,
        test_url: str = "",
        status_code: str = "",
        error_text: str = "",
        success_text: str = "",
        token_pattern: str = "",
    ) -> bool:
        """
        Validate login cookies for a tracker by checking specific indicators on a test page.
        Return False to skip the upload if credentials are invalid.
        """
        cookie_jar = await self.load_session_cookies(meta, tracker)
        if not cookie_jar:
            return False

        headers = {
            "User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=20.0, cookies=cookie_jar) as session:
                response = await session.get(test_url)
                text = response.text
                # if meta.get('debug', False):
                #    console.print(text)

                # Check for key indicators of successful login
                # This is the most precise method if you can find a unique string that only appears when logged in
                if success_text and success_text not in text:
                    await self.handle_validation_failure(meta, tracker, text)
                    return False

                # Check for key indicators of failed login
                # For example, “Forgot your password” <- this indicates that you are on the login page
                if error_text and error_text in text:
                    await self.handle_validation_failure(meta, tracker, text)
                    return False

                # Check for status code
                # This is often not very accurate, as websites may use the same status code for successful uploads and failures
                if status_code and response.status_code != int(status_code):
                    await self.handle_validation_failure(meta, tracker, text)
                    return False

                # Find the auth token if it is needed
                if token_pattern:
                    match = re.search(token_pattern, text)
                    if not match:
                        await self.handle_validation_failure(meta, tracker, text)
                        return False
                    # Dynamically set a class attribute to store the token
                    cls = getattr(
                        importlib.import_module(f'src.trackers.{tracker}'),
                        tracker
                    )
                    cls.secret_token = str(match.group(1))

                # Save cookies only after a confirmed valid login
                await self.save_session_cookies(tracker, cookie_jar)
                return True

        except httpx.ConnectTimeout:
            console.print(f"{tracker}: Connection timeout. Server took too long to respond.")
        except httpx.ReadTimeout:
            console.print(f"{tracker}: Read timeout. Data transfer stopped prematurely.")
        except httpx.ConnectError:
            console.print(f"{tracker}: Connection failed. Check URL, port, and network status.")
        except httpx.ProxyError:
            console.print(f"{tracker}: Proxy error. Failed to connect via proxy.")
        except httpx.DecodingError:
            console.print(
                f"{tracker}: Decoding failed. Response content is not valid (e.g., unexpected encoding)."
            )
        except httpx.TooManyRedirects:
            console.print(f"{tracker}: Too many redirects. Request exceeded the maximum redirect limit.")
        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            reason = e.response.reason_phrase if e.response.reason_phrase else "Unknown Reason"
            url = e.request.url
            console.print(f"{tracker}: HTTP status error {status_code}: {reason} for {url}")
        except httpx.RequestError as e:
            console.print(f"{tracker}: General request error: {e}")
        except Exception as e:
            console.print(f"{tracker}: Unexpected validation error: {e}")

        return False

    async def handle_validation_failure(self, meta: dict[str, Any], tracker: str, text: str) -> None:
        console.print(
            f"{tracker}: Validation failed. The cookie appears to be expired or invalid.\n"
            f"{tracker}: Please log in through your usual browser and export the cookies again."
        )
        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]Failed_Login.html"
        os.makedirs(os.path.dirname(failure_path), exist_ok=True)
        async with aiofiles.open(failure_path, "w", encoding="utf-8") as f:
            await f.write(text)
        console.print(
            f"The web page has been saved to [yellow]{failure_path}[/yellow] for analysis.\n"
            "[red]Do not share this file publicly[/red], as it may contain confidential information such as passkeys, IP address, e-mail, etc.\n"
            "You can open this file in a web browser to see what went wrong.\n"
        )

        return

    async def find_html_token(self, tracker: str, token_pattern: str, response: str) -> Optional[str]:
        """Find the auth token in a web page using a regular expression pattern."""
        auth_match = re.search(token_pattern, response)
        if not auth_match:
            console.print(
                f"{tracker}: The required token could not be found in the page's HTML. Pattern used: {token_pattern}\n"
                f"{tracker}: This can happen if the site HTML has changed or if the login failed silently."
            )
            return None
        else:
            return str(auth_match.group(1))

    def _save_cookies_secure(self, session_cookies: Any, cookiefile: str) -> None:
        """Securely save session cookies using JSON instead of pickle"""
        try:
            # Convert RequestsCookieJar to dictionary for JSON serialization
            cookie_dict = {}
            for cookie in session_cookies:
                cookie_dict[cookie.name] = {
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure,
                    'expires': cookie.expires
                }

            with open(cookiefile, 'w', encoding='utf-8') as f:
                json.dump(cookie_dict, f, indent=2)

            # Set restrictive permissions (0o600) to protect cookie secrets
            os.chmod(cookiefile, stat.S_IRUSR | stat.S_IWUSR)

        except OSError as e:
            console.print(f"[red]Error with cookie file operations: {e}[/red]")
            raise
        except (TypeError, ValueError) as e:
            console.print(f"[red]Error encoding cookies to JSON: {e}[/red]")
            raise

    def _load_cookies_secure(self, session: Any, cookiefile: str, tracker: str) -> None:
        """Securely load session cookies from JSON instead of pickle"""

        # Check for legacy pickle file and migrate if needed
        pickle_file = cookiefile.replace('.json', '.pickle')
        legacy_pickle_file = f"{os.path.dirname(cookiefile)}/{tracker}"  # Legacy filename without extension

        # Try to migrate from pickle files
        for potential_pickle in [pickle_file, legacy_pickle_file]:
            if os.path.exists(potential_pickle) and not os.path.exists(cookiefile):
                try:
                    console.print(f"[yellow]Migrating legacy cookie file from {potential_pickle} to {cookiefile}[/yellow]")

                    # Load the pickle file
                    with open(potential_pickle, 'rb') as f:
                        session_cookies = pickle.load(f)  # nosec B301 - Legacy migration only

                    # Convert to JSON format
                    cookie_dict = {}
                    for cookie in session_cookies:
                        cookie_dict[cookie.name] = {
                            'value': cookie.value,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'secure': cookie.secure,
                            'expires': getattr(cookie, 'expires', None)
                        }

                    # Save as JSON
                    with open(cookiefile, 'w', encoding='utf-8') as f:
                        json.dump(cookie_dict, f, indent=2)

                    # Set restrictive permissions
                    os.chmod(cookiefile, stat.S_IRUSR | stat.S_IWUSR)

                    # Verify the migration was successful by loading the JSON
                    try:
                        with open(cookiefile, encoding='utf-8') as f:
                            json.load(f)  # Just verify it can be loaded

                        # Migration verified successful - delete the old pickle file
                        os.remove(potential_pickle)
                        console.print(f"[green]Successfully migrated cookies to JSON format and removed legacy file {potential_pickle}[/green]")

                    except (OSError, json.JSONDecodeError) as verify_error:
                        console.print(f"[red]Migration verification failed: {verify_error}. Keeping original file {potential_pickle}[/red]")
                        # Remove the potentially corrupted JSON file
                        if os.path.exists(cookiefile):
                            os.remove(cookiefile)
                        raise

                    break

                except Exception as e:
                    console.print(f"[red]Error migrating cookie file {potential_pickle}: {e}[/red]")
                    # Continue to try next potential file or load JSON normally
                    continue

            elif os.path.exists(potential_pickle) and os.path.exists(cookiefile):
                os.remove(potential_pickle)
                console.print(f"[yellow]Removed legacy cookie file {potential_pickle}. Using JSON file.[/yellow]")

        # Load cookies from JSON file
        try:
            with open(cookiefile, encoding='utf-8') as f:
                cookie_dict = json.load(f)

            # Convert dictionary back to session cookies
            for name, cookie_data in cookie_dict.items():
                # Prevent None domain values
                domain = cookie_data.get('domain')
                if domain is None:
                    domain = ''  # Use empty string instead of None

                session.cookies.set(
                    name=name,
                    value=cookie_data['value'],
                    domain=domain,
                    path=cookie_data.get('path', '/'),
                    secure=cookie_data.get('secure', False)
                )

        except OSError as e:
            console.print(f"[red]Error reading cookie file: {e}[/red]")
            raise
        except json.JSONDecodeError as e:
            console.print(f"[red]Error decoding JSON from cookie file: {e}[/red]")
            raise

    def _load_cookies_dict_secure(self, cookiefile: str) -> dict[str, Any]:
        """Securely load cookies as dictionary from JSON instead of pickle"""
        try:
            with open(cookiefile, encoding='utf-8') as f:
                cookie_dict = json.load(f)
            return cast(dict[str, Any], cookie_dict)
        except OSError as e:
            console.print(f"[red]Error reading cookie file: {e}[/red]")
            raise
        except json.JSONDecodeError as e:
            console.print(f"[red]Error decoding JSON from cookie file: {e}[/red]")
            raise


class CookieAuthUploader:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.common = COMMON(config)
        pass

    async def handle_upload(
        self,
        meta: dict[str, Any],
        tracker: str,
        source_flag: str,
        torrent_url: str,
        data: dict[str, Any],
        torrent_field_name: str,
        upload_cookies: Any,
        upload_url: str,
        default_announce: str = "",
        torrent_name: str = "",
        id_pattern: str = "",
        success_status_code: str = "",
        error_text: str = "",
        success_text: str = "",
        additional_files: Optional[dict[str, Any]] = None,
        hash_is_id: bool = False,
    ) -> bool:
        """
        Upload a torrent to a tracker using cookies for authentication.
        Return True if the upload is successful, False otherwise.

        1.  Create the [tracker].torrent file and set the source flag.
            Uses default_announce if provided as some trackers require it.

        2.  Load the torrent file into memory.
        3.  Post the torrent file and form data to the provided upload URL using the provided cookies.
        4.  Check the response for success indicators.
        5.  Handle success or failure accordingly.

        A successful upload will create a torrent entry with the announce URL and torrent ID (if applicable).
        A failed upload will save the response HTML for analysis and also create a torrent entry with the announce URL,
        as the upload may have partially succeeded.
        """
        values = [success_status_code, error_text, success_text]
        count = sum(bool(v) for v in values)

        if count == 0 or count > 1:
            if count == 0:
                error = "You must provide at least one of: success_status_code, error_text, or success_text."
            else:
                error = "Only one of success_status_code, error_text, or success_text should be provided."
            meta["tracker_status"][tracker]["status_message"] = error
            return False

        user_announce_url = self.config["TRACKERS"][tracker]["announce_url"]

        files = await self.load_torrent_file(
            meta,
            tracker,
            torrent_field_name,
            torrent_name,
            source_flag,
            default_announce,
        )
        if additional_files:
            files.update(additional_files)

        headers = {
            "User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"
        }

        if meta.get("debug", False):
            self.upload_debug(tracker, data)
            meta["tracker_status"][tracker]["status_message"] = "Debug mode enabled, not uploading"
            await self.common.create_torrent_for_upload(meta, f"{tracker}" + "_DEBUG", f"{tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True

        else:
            success = False
            try:
                async with httpx.AsyncClient(headers=headers, timeout=30.0, cookies=upload_cookies, follow_redirects=True) as session:
                    response = await session.post(upload_url, data=data, files=files)

                    if success_text and success_text in response.text:
                        success = True

                    elif success_status_code:
                        valid_codes = {
                            int(code.strip())
                            for code in str(success_status_code).split(",")
                            if code.strip().isdigit()
                        }

                        if int(response.status_code) in valid_codes:
                            success = True

                    elif error_text and error_text not in response.text:
                        success = True

                    if success:
                        await self.handle_successful_upload(
                            meta,
                            tracker,
                            response,
                            id_pattern,
                            hash_is_id,
                            source_flag,
                            user_announce_url,
                            torrent_url,
                        )
                        return True
                    else:
                        await self.handle_failed_upload(
                            meta,
                            tracker,
                            success_status_code,
                            success_text,
                            error_text,
                            response,
                        )
                        return False

            except httpx.ConnectTimeout:
                meta["tracker_status"][tracker]["status_message"] = "Connection timed out"
            except httpx.ReadTimeout:
                meta["tracker_status"][tracker]["status_message"] = "Read timed out"
            except httpx.ConnectError:
                meta["tracker_status"][tracker]["status_message"] = "Failed to connect to the server"
            except httpx.ProxyError:
                meta["tracker_status"][tracker]["status_message"] = "Proxy connection failed"
            except httpx.DecodingError:
                meta["tracker_status"][tracker]["status_message"] = "Response decoding failed"
            except httpx.TooManyRedirects:
                meta["tracker_status"][tracker]["status_message"] = "Too many redirects"
            except httpx.HTTPStatusError as e:
                meta["tracker_status"][tracker]["status_message"] = f"HTTP error {e.response.status_code}: {e}"
            except httpx.RequestError as e:
                meta["tracker_status"][tracker]["status_message"] = f"Request error: {e}"
            except Exception as e:
                meta["tracker_status"][tracker]["status_message"] = f"Unexpected upload error: {e}"

        await self.common.create_torrent_ready_to_seed(meta, tracker, source_flag, user_announce_url, torrent_url)
        return False

    def upload_debug(self, tracker: str, data: Any) -> None:
        try:
            if isinstance(data, dict):
                data_dict = cast(dict[str, Any], data)
                sensitive_keywords = ['password', 'passkey', 'auth', 'csrf', 'token']

                table_data = Table(
                    title=f"{tracker}: Form Data", show_header=True, header_style="bold cyan"
                )
                table_data.add_column("Key", style="cyan")
                table_data.add_column("Value", style="magenta")

                for k, v in data_dict.items():
                    key = str(k)
                    if any(keyword in key.lower() for keyword in sensitive_keywords):
                        table_data.add_row(key, "[REDACTED]")
                    else:
                        table_data.add_row(key, str(v))

                console.print(table_data, justify="center", markup=False)
            else:
                data_panel = Panel(str(data), title=f"{tracker}: Form Data - DO NOT SHARE THIS", border_style="blue")
                console.print(data_panel, justify="center")
        except Exception as e:
            console.print(f"Error displaying form data: {e}")
            raise

    async def load_torrent_file(
        self,
        meta: dict[str, Any],
        tracker: str,
        torrent_field_name: str,
        torrent_name: str,
        source_flag: str,
        default_announce: str,
    ) -> dict[str, tuple[str, bytes, str]]:
        """Load the torrent file into memory."""
        await self.common.create_torrent_for_upload(meta, tracker, source_flag, announce_url=default_announce)
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent"
        async with aiofiles.open(torrent_path, "rb") as f:
            file_bytes = await f.read()

        name = torrent_name if torrent_name else f"{tracker}.{meta.get('infohash', '')}.placeholder"

        return {
            torrent_field_name: (
                f"{name}.torrent",
                file_bytes,
                "application/x-bittorrent",
            )
        }

    async def handle_successful_upload(
        self,
        meta: dict[str, Any],
        tracker: str,
        response: httpx.Response,
        id_pattern: str,
        hash_is_id: bool,
        source_flag: str,
        user_announce_url: str,
        torrent_url: str,
    ) -> bool:
        torrent_id = ""
        if id_pattern:
            # First try to match the pattern in the response URL (for redirects)
            url_match = re.search(id_pattern, str(response.url))
            if url_match:
                torrent_id = url_match.group(1)
                meta["tracker_status"][tracker]["torrent_id"] = torrent_id
            else:
                # Fall back to searching in response text
                text_match = re.search(id_pattern, response.text)
                if text_match:
                    torrent_id = text_match.group(1)
                    meta["tracker_status"][tracker]["torrent_id"] = torrent_id

        torrent_hash = await self.common.create_torrent_ready_to_seed(
            meta, tracker, source_flag, user_announce_url, torrent_url + torrent_id, hash_is_id=hash_is_id
        )

        if hash_is_id and torrent_hash is not None:
            meta["tracker_status"][tracker]["torrent_id"] = torrent_hash

        meta["tracker_status"][tracker]["status_message"] = "Torrent uploaded successfully."

        return True

    async def handle_failed_upload(
        self,
        meta: dict[str, Any],
        tracker: str,
        success_status_code: str,
        success_text: str,
        error_text: str,
        response: httpx.Response,
    ) -> bool:
        message = ["data error: The upload appears to have failed. It may have uploaded, go check."]
        if success_text:
            message.append(f"Could not find the success text '{success_text}' in the response.")
        elif error_text:
            message.append(f"Found the error text '{error_text}' in the response.")
        elif success_status_code:
            message.append(f"Expected status code '{success_status_code}', got '{response.status_code}'.")
        else:
            message.append("Unknown upload error.")

        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]Failed_Upload.html"
        os.makedirs(os.path.dirname(failure_path), exist_ok=True)
        async with aiofiles.open(failure_path, "w", encoding="utf-8") as f:
            await f.write(response.text)

        message.append(
            f"The web page has been saved to [yellow]{failure_path}[/yellow] for analysis.\n"
            "[red]Do not share this file publicly[/red], as it may contain confidential information such as passkeys, IP address, e-mail, etc.\n"
            "You can open this file in a web browser to see what went wrong.\n"
        )

        meta["tracker_status"][tracker]["status_message"] = "\n".join(message)
        return False
