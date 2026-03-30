import re
from urllib.parse import urlparse, parse_qs
from typing import Optional


YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[\w\-/?=&%]+",
    re.IGNORECASE,
)


def _extract_video_id(url: str) -> Optional[str]:
    """Extract the YouTube video ID from a URL.

    Supports typical YouTube URL formats such as:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtube.com/watch?v=VIDEO_ID&...
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    # youtu.be short links: /VIDEO_ID
    if "youtu.be" in host:
        parts = path.split("/")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
        return None

    if "youtube.com" not in host:
        return None

    # Standard watch URLs: /watch?v=VIDEO_ID
    if path.startswith("/watch"):
        query = parse_qs(parsed.query or "")
        video_ids = query.get("v")
        if video_ids:
            return video_ids[0]

    # Embedded URLs: /embed/VIDEO_ID
    if path.startswith("/embed/"):
        parts = path.split("/")
        if len(parts) >= 3 and parts[2]:
            return parts[2]

    # Shorts URLs: /shorts/VIDEO_ID
    if path.startswith("/shorts/"):
        parts = path.split("/")
        if len(parts) >= 3 and parts[2]:
            return parts[2]

    return None


def _build_embed_html(video_id: str) -> str:
    """Return a placeholder div with video ID that the frontend will render with svelte-youtube-embed."""
    if not video_id:
        return ""

    return f'<div class="youtube-embed-placeholder" data-youtube-id="{video_id}"></div>'


def convert_links_to_embeds(html_content: str) -> str:
    """Convert YouTube links in the given HTML content into embedded iframes.

    This function performs two passes:
    1. It replaces <a> tags whose href points to YouTube with an embedded iframe.
    2. It replaces bare YouTube URLs (not inside an <a> tag) with an embedded iframe.

    Non-YouTube links and malformed URLs are left untouched.
    """
    if not html_content:
        return html_content

    content = str(html_content)

    # First: replace anchor tags with YouTube hrefs
    anchor_pattern = re.compile(
        r'<a[^>]+href=["\"](?P<url>https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^"\']+)["\"][^>]*>.*?</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def _replace_anchor(match: re.Match) -> str:
        url = match.group("url")
        video_id = _extract_video_id(url)
        if not video_id:
            return match.group(0)
        return _build_embed_html(video_id)

    content = anchor_pattern.sub(_replace_anchor, content)

    # Second: replace bare YouTube URLs
    def _replace_url(match: re.Match) -> str:
        url = match.group(0)
        video_id = _extract_video_id(url)
        if not video_id:
            return match.group(0)
        return _build_embed_html(video_id)

    content = YOUTUBE_URL_PATTERN.sub(_replace_url, content)

    return content
