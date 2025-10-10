import aiofiles
import http.cookiejar
import httpx
import os
import re
from src.console import console
from src.trackers.COMMON import COMMON
from rich.panel import Panel
from rich.table import Table


class CookieValidator:
    def __init__(self):
        pass

    async def load_session_cookies(self, meta, tracker):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{tracker}.txt")
        cookie_jar = http.cookiejar.MozillaCookieJar(cookie_file)

        try:
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except http.cookiejar.LoadError as e:
            console.print(f"{tracker}: Failed to load the cookie file: {e}")
            console.print(f"{tracker}: Please ensure the cookie file is in the correct format (Netscape).")
            return False
        except FileNotFoundError:
            console.print(
                f"{tracker}: [red]Cookie file not found.[/red]\n"
                f"{tracker}: You must first log in through your usual browser and export the cookies to: [yellow]{cookie_file}[/yellow]\n"
                f'{tracker}: Cookies can be exported using browser extensions like "cookies.txt" (Firefox) or "Get cookies.txt LOCALLY" (Chrome).'
            )
            return False

        return cookie_jar

    async def save_session_cookies(self, tracker, cookie_jar):
        """Save updated cookies after a successful validation."""
        if not cookie_jar:
            console.print(f"{tracker}: Cookie jar not initialized, cannot save cookies.")
            return

        try:
            cookie_jar.save(ignore_discard=True, ignore_expires=True)
        except Exception as e:
            console.print(f"{tracker}: Failed to update the cookie file: {e}")

    async def cookie_validation(
        self,
        meta,
        tracker,
        test_url="",
        status_code="",
        error_text="",
        success_text="",
        token_pattern="",
    ):
        """
        Validate login cookies for a tracker by checking specific indicators on a test page.
        Return False to skip the upload if credentials are invalid.
        """
        cookie_jar = await self.load_session_cookies(meta, tracker)
        if not cookie_jar:
            return False

        headers = {"User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"}

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
                token = ""
                if token_pattern:
                    match = re.search(token_pattern, text)
                    if not match:
                        await self.handle_validation_failure(meta, tracker, text)
                        return False
                    token = str(match.group(1))

                # Save cookies only after a confirmed valid login
                await self.save_session_cookies(tracker, cookie_jar)
                return token or True

        except httpx.ConnectTimeout:
            console.print(f"{tracker}: Connection timed out")
        except httpx.ReadTimeout:
            console.print(f"{tracker}: Read timed out")
        except httpx.ConnectError:
            console.print(f"{tracker}: Failed to connect to the server")
        except httpx.ProxyError:
            console.print(f"{tracker}: Proxy connection failed")
        except httpx.DecodingError:
            console.print(f"{tracker}: Response decoding failed")
        except httpx.TooManyRedirects:
            console.print(f"{tracker}: Too many redirects")
        except httpx.HTTPStatusError as e:
            console.print(f"{tracker}: HTTP error {e.response.status_code}: {e}")
        except httpx.RequestError as e:
            console.print(f"{tracker}: Request error: {e}")
        except Exception as e:
            console.print(f"{tracker}: Unexpected error: {e}")

        return False

    async def handle_validation_failure(self, meta, tracker, text):
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

    async def find_html_token(self, tracker, token_pattern, response):
        auth_match = re.search(token_pattern, response)
        if not auth_match:
            console.print(
                f"{tracker}: The required token could not be found in the page's HTML.\n"
                f"{tracker}: This can happen if the site HTML has changed or if the login failed silently."
            )
            return False
        else:
            return str(auth_match.group(1))


class CookieUploader:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        pass

    async def handle_upload(
        self,
        meta,
        tracker,
        source_flag,
        torrent_url,
        data,
        torrent_field_name,
        upload_cookies,
        upload_url,
        default_announce="",
        torrent_name="",
        id_pattern="",
        success_status_code="",
        error_text="",
        success_text="",
        additional_files={},
    ):
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

        status_message = ""
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

        headers = {"User-Agent": f"Upload Assistant {meta.get('current_version', 'github.com/Audionut/Upload-Assistant')}"}

        try:
            async with httpx.AsyncClient(headers=headers, timeout=30.0, cookies=upload_cookies) as session:

                if not meta.get("debug", False):
                    success = False
                    response = await session.post(upload_url, data=data, files=files)

                    if success_text and success_text in response.text:
                        success = True

                    elif success_status_code:
                        valid_codes = {int(code.strip()) for code in str(success_status_code).split(",") if code.strip().isdigit()}

                        if int(response.status_code) in valid_codes:
                            success = True

                    elif error_text and error_text not in response.text:
                        success = True

                    if success:
                        return await self.handle_successful_upload(
                            meta,
                            tracker,
                            response,
                            id_pattern,
                            source_flag,
                            user_announce_url,
                            torrent_url,
                        )
                    else:
                        await self.handle_failed_upload(
                            meta,
                            tracker,
                            success_status_code,
                            success_text,
                            error_text,
                            response,
                        )

                else:
                    self.upload_debug(tracker, data, session)
                    status_message = "Debug mode enabled, not uploading"

        except httpx.ConnectTimeout:
            status_message = f"{tracker}: Connection timed out"
        except httpx.ReadTimeout:
            status_message += f"{tracker}: Read timed out"
        except httpx.ConnectError:
            status_message += f"{tracker}: Failed to connect to the server"
        except httpx.ProxyError:
            status_message += f"{tracker}: Proxy connection failed"
        except httpx.DecodingError:
            status_message += f"{tracker}: Response decoding failed"
        except httpx.TooManyRedirects:
            status_message += f"{tracker}: Too many redirects"
        except httpx.HTTPStatusError as e:
            status_message += f"{tracker}: HTTP error {e.response.status_code}: {e}"
        except httpx.RequestError as e:
            status_message += f"{tracker}: Request error: {e}"
        except Exception as e:
            status_message += f"{tracker}: Unexpected error: {e}"

        await self.common.add_tracker_torrent(meta, tracker, source_flag, user_announce_url, torrent_url)
        meta["tracker_status"][tracker]["status_message"] = status_message
        return False

    def upload_debug(self, tracker, data, session):
        """Print debug information about the upload session."""
        # Headers
        table_headers = Table(title=f"{tracker}: Headers", show_header=True, header_style="bold cyan")
        table_headers.add_column("Key", style="cyan")
        table_headers.add_column("Value", style="magenta")
        for k, v in session.headers.items():
            table_headers.add_row(k, str(v))
        console.print(table_headers, justify="center")

        # Cookies
        cookies_panel = Panel(str(session.cookies), title=f"{tracker}: Cookies - DO NOT SHARE THIS", border_style="green")
        console.print(cookies_panel, justify="center")

        # Form data
        if isinstance(data, dict):
            table_data = Table(title=f"{tracker}: Form Data - DO NOT SHARE THIS", show_header=True, header_style="bold cyan")
            table_data.add_column("Key", style="cyan")
            table_data.add_column("Value", style="magenta")
            for k, v in data.items():
                table_data.add_row(k, str(v))
            console.print(table_data, justify="center")
        else:
            data_panel = Panel(str(data), title=f"{tracker}: Form Data", border_style="blue")
            console.print(data_panel, justify="center")

    async def load_torrent_file(self, meta, tracker, torrent_field_name, torrent_name, source_flag, default_announce):
        """Load the torrent file into memory."""
        await self.common.edit_torrent(meta, tracker, source_flag, announce_url=default_announce)
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

    async def handle_successful_upload(self, meta, tracker, response, id_pattern, source_flag, user_announce_url, torrent_url):
        torrent_id = ""
        if id_pattern:
            match = re.search(id_pattern, response.text)
            if match:
                torrent_id = match.group(1)
                meta["tracker_status"][tracker]["torrent_id"] = torrent_id

        meta["tracker_status"][tracker]["status_message"] = "Torrent uploaded successfully."
        await self.common.add_tracker_torrent(meta, tracker, source_flag, user_announce_url, torrent_url + torrent_id)

        return True

    async def handle_failed_upload(self, meta, tracker, status_code, success_text, error_text, response):
        message = ["data error: The upload appears to have failed. It may have uploaded, go check."]
        if success_text:
            message.append(f"Could not find the success text '{success_text}' in the response.")
        elif error_text in response.text:
            message.append(f"Found the error text '{error_text}' in the response.")
        elif status_code and response.status_code != int(status_code):
            message.append(f"Expected status code '{status_code}', got '{response.status_code}'.")
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
