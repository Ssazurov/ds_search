"""Встроенные видео (iframe/video) -> гиперссылки в тексте статьи.

Crawl4AI/html2text теряют <iframe>; заменяем его на <p><a href>▶ Видео (host)</a></p>
до конвертации в markdown, чтобы ссылка попала в .md, RAG-индекс и скачивание.
"""
import html as _html
import re
from urllib.parse import parse_qs, urlsplit

_IFRAME_RE = re.compile(r'<iframe\b[^>]*?\bsrc\s*=\s*["\']([^"\']+)["\'][^>]*>(?:\s*</iframe>)?', re.I | re.S)
_VIDEO_RE = re.compile(r'<video\b([^>]*)>(.*?)</video>', re.I | re.S)
_SRC_RE = re.compile(r'\bsrc\s*=\s*["\']([^"\']+)["\']', re.I)
_VIDEO_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be", "rutube.ru",
                "vk.com", "vkvideo.ru", "vimeo.com", "ok.ru", "dzen.ru")


def normalize_video_url(src: str) -> str:
    src = _html.unescape(src.strip())
    if src.startswith("//"):
        src = "https:" + src
    u = urlsplit(src)
    host = (u.hostname or "").removeprefix("www.")
    path = u.path
    if host in ("youtube.com", "youtube-nocookie.com"):
        m = re.match(r"/embed/([\w-]+)", path)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    elif host == "rutube.ru":
        m = re.match(r"/play/embed/([\w]+)", path)
        if m:
            return f"https://rutube.ru/video/{m.group(1)}/"
    elif host in ("vk.com", "vkvideo.ru") and "video_ext.php" in path:
        q = parse_qs(u.query)
        if "oid" in q and "id" in q:
            return f"https://vk.com/video{q['oid'][0]}_{q['id'][0]}"
    elif host == "player.vimeo.com":
        m = re.match(r"/video/(\d+)", path)
        if m:
            return f"https://vimeo.com/{m.group(1)}"
    return src


def _link(src: str) -> str:
    url = normalize_video_url(src)
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return f'<p><a href="{_html.escape(url, quote=True)}">▶ Видео ({host})</a></p>'


def _iframe_sub(m: re.Match) -> str:
    src = m.group(1)
    host = (urlsplit(_html.unescape(src) if not src.startswith("//") else "https:" + src).hostname or "")
    return _link(src) if any(host.endswith(h) for h in _VIDEO_HOSTS) else m.group(0)


def _video_sub(m: re.Match) -> str:
    s = _SRC_RE.search(m.group(1)) or _SRC_RE.search(m.group(2))
    return _link(s.group(1)) if s else m.group(0)


def embeds_to_links(html: str) -> str:
    if not html:
        return html
    html = _IFRAME_RE.sub(_iframe_sub, html)
    html = _MARKED_RE.sub(_marked_sub, html)
    return _VIDEO_RE.sub(_video_sub, html)


# crawl4ai вырезает <iframe>/<video> до генератора markdown, поэтому в браузере (js_code,
# до снятия HTML) заменяем их на маркерную ссылку "▶ Видео"; embeds_to_links
# нормализует её href (embed -> обычная ссылка) и подставляет хост.
VIDEO_EMBED_JS = """
document.querySelectorAll('iframe[src], video').forEach(function (el) {
  var src = el.getAttribute('src') || (el.querySelector('source') && el.querySelector('source').getAttribute('src'));
  if (!src) return;
  if (el.tagName === 'IFRAME' && !/youtube|youtu\\.be|rutube|vk\\.com|vkvideo|vimeo|ok\\.ru|dzen/i.test(src)) return;
  var p = document.createElement('p'), a = document.createElement('a');
  a.href = src; a.textContent = '\\u25B6 \\u0412\\u0438\\u0434\\u0435\\u043e'; p.appendChild(a);
  el.replaceWith(p);
});
"""

_MARKED_RE = re.compile(r'<a\b[^>]*?href="([^"]+)"[^>]*>\s*▶ Видео\s*</a>', re.I)


def _marked_sub(m: re.Match) -> str:
    return _link(m.group(1))[3:-4]  # без внешнего <p>…</p>
