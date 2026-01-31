# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import contextlib

from rich.console import Console
from rich.text import Text


def ansi_to_html(ansi_chunk: str, width: int = 120) -> str:
    """Convert an ANSI-containing text chunk to an HTML fragment using Rich.

    This creates a short-lived Console in record mode, renders the ANSI
    content into it (via Text.from_ansi) and exports an HTML fragment
    with inline styles so it can be embedded directly into the web UI.
    """
    try:
        c = Console(record=True, force_terminal=True, width=width)
        # Try parsing ANSI sequences first. If there are no style spans and
        # the chunk looks like Rich markup (e.g. contains [bold] tags),
        # parse as markup so styled output is preserved.
        text = Text.from_ansi(ansi_chunk)
        try:
            if (not getattr(text, "spans", None) or len(text.spans) == 0) and "[" in ansi_chunk and "]" in ansi_chunk:
                # Parse Rich markup into a Text instance
                with contextlib.suppress(Exception):
                    text = Text.from_markup(ansi_chunk)
        except Exception:
            # If introspecting spans fails for any reason, proceed with the original text
            pass
        c.print(text, end="")
        # inline_styles keeps the fragment self-contained
        # export the recorded renderable as HTML with inline styles
        html = c.export_html(inline_styles=True)
        # Rich returns a full HTML document; extract the body contents so the
        # web UI can embed the fragment directly.
        try:
            import re

            m = re.search(r"<body[^>]*>(.*?)</body>", html, re.S | re.I)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return html
    except Exception:
        # Fallback: escape HTML to avoid breaking the page
        import html as _html

        return f"<div>{_html.escape(ansi_chunk)}</div>"


# Create a shared Console instance used throughout the project.
# Force terminal mode so that when other processes import `src.console.console`
# they will emit ANSI color codes to stdout even when not attached to a real TTY.
console = Console(force_terminal=True)
