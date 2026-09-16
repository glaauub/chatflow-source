"""Validated, opt-in promotion settings and a deterministic HTML postprocessor.

This module does not contact outside services or modify a database. Call
``validate_settings`` before saving, then ``apply_promotions`` on generated HTML.
Hidden experiments are disabled by default. Internal links affect visible body
text only and add at most three links to a page.
"""

import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit


_VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_BLOCKED = frozenset("head title script style textarea a noscript code pre select option button svg math iframe template".split())
_EXPERIMENTS = frozenset(("hidden-keywords", "hidden-links"))
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalize_keyword_lines(text):
    """Split newline/comma/semicolon-separated text into unique keyword strings."""
    if not isinstance(text, str):
        raise ValueError("关键词必须是文字")
    result = []
    seen = set()
    for part in re.split(r"[\r\n,，;；]+", text):
        value = part.strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result


def _boolean(raw, key):
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise ValueError("%s 必须是开关值" % key)
    return value


def _text(value, name, maximum=120):
    if not isinstance(value, str):
        raise ValueError("%s 必须是文字" % name)
    value = value.strip()
    if not value or len(value) > maximum or _CONTROL.search(value):
        raise ValueError("%s 不能为空，最多 %d 个字，不能包含控制字符" % (name, maximum))
    return value


def _safe_url(value):
    value = _text(value, "链接", 2048)
    # Decode solely for validation, never for output. Backslashes, control
    # characters and protocol-relative addresses are ambiguous in browsers.
    decoded = value
    for _ in range(3):
        expanded = unquote(decoded)
        if expanded == decoded:
            break
        decoded = expanded
    if any(ch.isspace() for ch in decoded) or any(ch in decoded for ch in "\\<>\"'") or _CONTROL.search(decoded):
        raise ValueError("链接不能包含空格、引号或控制字符")
    if value.startswith("//") or decoded.startswith("//"):
        raise ValueError("外部链接请填写完整的 https 网址")
    try:
        parsed = urlsplit(value)
        checked = urlsplit(decoded)
        if checked.scheme and checked.scheme.lower() != "https":
            raise ValueError("外部链接只支持 https 网址")
        if parsed.scheme:
            if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("外部链接必须是无账号密码的 https 网址")
            # Accessing port validates malformed/non-numeric ports.
            parsed.port
        elif parsed.netloc or checked.netloc or checked.scheme:
            raise ValueError("链接格式不正确")
        elif ":" in parsed.path.split("/", 1)[0]:
            raise ValueError("链接格式不正确")
    except (ValueError, TypeError) as error:
        raise ValueError("链接格式不正确：只支持 https 或本站相对地址") from error
    return value


def _rows(raw, key, maximum=100):
    value = raw.get(key, [])
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("%s 必须是列表，最多 %d 条" % (key, maximum))
    return value


def validate_settings(raw):
    """Return a normalized settings dict; raise ValueError for invalid input.

    Missing switches are false; max_links_per_page defaults to 3 (range 1–3).
    Duplicate hidden keywords and identical link rows are collapsed. A keyword
    cannot point to two different destinations, avoiding unpredictable matches.
    """
    if not isinstance(raw, dict):
        raise ValueError("推广设置必须是对象")
    limit = raw.get("max_links_per_page", 3)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 3:
        raise ValueError("每页自动内链数量只能填写 1、2 或 3")
    result = {
        "hidden_keywords_enabled": _boolean(raw, "hidden_keywords_enabled"),
        "hidden_keywords": [],
        "hidden_links_enabled": _boolean(raw, "hidden_links_enabled"),
        "hidden_links": [],
        "internal_links_enabled": _boolean(raw, "internal_links_enabled"),
        "internal_links": [],
        "max_links_per_page": limit,
    }
    keywords = raw.get("hidden_keywords", [])
    if isinstance(keywords, str):
        keywords = normalize_keyword_lines(keywords)
    if not isinstance(keywords, list) or len(keywords) > 100:
        raise ValueError("隐藏关键词最多 100 条")
    seen = set()
    for item in keywords:
        item = _text(item, "隐藏关键词")
        if item.casefold() not in seen:
            seen.add(item.casefold())
            result["hidden_keywords"].append(item)
    seen = set()
    for row in _rows(raw, "hidden_links"):
        if not isinstance(row, dict):
            raise ValueError("每条隐藏链接必须包含名称和网址")
        name, url = _text(row.get("name"), "链接名称"), _safe_url(row.get("url"))
        rel = row.get("rel", "nofollow")
        if rel not in ("follow", "nofollow", "sponsored"):
            raise ValueError("链接关系只能选 follow、nofollow 或 sponsored")
        identity = (name, url, rel)
        if identity not in seen:
            seen.add(identity)
            result["hidden_links"].append({"name": name, "url": url, "rel": rel})
    seen = {}
    for row in _rows(raw, "internal_links"):
        if not isinstance(row, dict):
            raise ValueError("每条自动内链必须包含关键词和网址")
        keyword, url = _text(row.get("keyword"), "内链关键词"), _safe_url(row.get("url"))
        identity = keyword.casefold()
        if identity in seen and seen[identity] != url:
            raise ValueError("同一个内链关键词不能填写两个不同网址：%s" % keyword)
        if identity not in seen:
            seen[identity] = url
            result["internal_links"].append({"keyword": keyword, "url": url})
    return result


class _Document(HTMLParser):
    """Record source positions, preserving original HTML outside actual edits."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        self.lines.extend(match.end() for match in re.finditer("\n", source))
        self.stack = []
        self.text_nodes = []
        self.cleanup = []
        self.body_end = None
        self.html_end = None
        self.has_body = False
        self.has_html = False
        self.feed(source)
        self.close()

    def _offset(self):
        row, col = self.getpos()
        return self.lines[row - 1] + col

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        start = self._offset()
        end = start + len(self.get_starttag_text())
        own_experiment = tag == "div" and attrs.get("data-cf-experiment") in _EXPERIMENTS
        own_link = tag == "a" and attrs.get("data-cf-promotion") == "internal"
        style = attrs.get("style") or ""
        hidden = (
            "hidden" in attrs
            or (attrs.get("aria-hidden") or "").lower() == "true"
            or "data-cf-experiment" in attrs
            or "spider-pool" in (attrs.get("class") or "").split()
            or re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", style, re.I)
        )
        if tag == "body":
            self.has_body = True
        if tag == "html":
            self.has_html = True
        if tag not in _VOID:
            self.stack.append((tag, bool(hidden) or tag in _BLOCKED, start, end, own_experiment, own_link))

    def handle_startendtag(self, tag, attributes):
        # A self-closing element contains no text and needs no stack entry.
        pass

    def handle_endtag(self, tag):
        start = self._offset()
        closing = self.source.find(">", start)
        end = closing + 1 if closing >= 0 else start
        if tag == "body":
            self.body_end = start
        if tag == "html":
            self.html_end = start
        for index in range(len(self.stack) - 1, -1, -1):
            item = self.stack[index]
            if item[0] == tag:
                if item[4]:
                    self.cleanup.append((item[2], end, ""))
                elif item[5]:
                    self.cleanup.extend(((item[2], item[3], ""), (start, end, "")))
                del self.stack[index:]
                break

    def handle_data(self, data):
        if data and not any(item[1] for item in self.stack):
            self.text_nodes.append((self._offset(), data, any(item[0] == "body" for item in self.stack)))


def _patch(source, patches):
    # A removed experiment can contain generated links. Keep the outer removal
    # only, so overlapping source ranges cannot corrupt the resulting document.
    selected = []
    for start, end, replacement in sorted(patches, key=lambda item: (item[0], -item[1])):
        if selected and start < selected[-1][1]:
            continue
        selected.append((start, end, replacement))
    for start, end, replacement in reversed(selected):
        source = source[:start] + replacement + source[end:]
    return source


def _canonical_page(url):
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if path.endswith("/index.html"):
        path = path[:-10]
    return (parsed.hostname or "").lower(), parsed.port, path.rstrip("/") or "/"


def _is_destination(url, page_url):
    if url.startswith(("#", "?")):
        return False
    if not page_url:
        return True
    base = urljoin("https://chatflow-relative.invalid/", page_url)
    target = urljoin(base, url)
    current_key, target_key = _canonical_page(base), _canonical_page(target)
    if current_key == target_key:
        return False
    # Absolute internal-link rules must stay on the current site's host. Hidden
    # links have a separate setting and are permitted to point outside the site.
    if urlsplit(page_url).netloc and target_key[:2] != current_key[:2]:
        return False
    return True


def _keyword_pattern(keyword):
    left = r"(?<![A-Za-z0-9_])" if re.match(r"[A-Za-z0-9_]", keyword[0]) else ""
    right = r"(?![A-Za-z0-9_])" if re.match(r"[A-Za-z0-9_]", keyword[-1]) else ""
    return left + re.escape(keyword) + right


def apply_promotions(html_text, settings, page_url=""):
    """Return generated HTML with selected experiments and automatic links.

    Scripts, styles, head, existing links, form controls, code blocks, and hidden
    text are untouched. Existing output from this function is refreshed, making
    repeated calls deterministic and allowing switches to remove old output.
    ``page_url`` should be the current absolute page URL to prevent self/external
    links; a relative current page path also prevents relative self-links.
    """
    if not isinstance(html_text, str):
        raise ValueError("网页内容必须是文字")
    settings = validate_settings(settings)
    document = _Document(html_text)
    if document.cleanup:
        html_text = _patch(html_text, document.cleanup)
        document = _Document(html_text)
    patches = []
    if settings["internal_links_enabled"]:
        rules = [row for row in settings["internal_links"] if _is_destination(row["url"], page_url)]
        rules.sort(key=lambda row: len(row["keyword"]), reverse=True)
        if rules:
            matcher = re.compile("|".join("(%s)" % _keyword_pattern(row["keyword"]) for row in rules), re.I)
            count = 0
            for offset, data, in_body in document.text_nodes:
                if document.has_body and not in_body:
                    continue
                if document.has_html and not document.has_body:
                    continue
                for match in matcher.finditer(data):
                    if count >= settings["max_links_per_page"]:
                        break
                    row = rules[match.lastindex - 1]
                    # The matched substring is already an HTMLParser text node
                    # from the original source. Keep it verbatim: escaping it
                    # would alter entities/source text on repeated processing.
                    # User-provided labels used outside this source context are
                    # always escaped separately below.
                    replacement = '<a href="%s" data-cf-promotion="internal">%s</a>' % (
                        html.escape(row["url"], quote=True), match.group()
                    )
                    patches.append((offset + match.start(), offset + match.end(), replacement))
                    count += 1
                if count >= settings["max_links_per_page"]:
                    break
    experiments = []
    if settings["hidden_keywords_enabled"] and settings["hidden_keywords"]:
        experiments.append('<div data-cf-experiment="hidden-keywords" style="display:none" aria-hidden="true">%s</div>' %
                           " ".join(html.escape(item) for item in settings["hidden_keywords"]))
    if settings["hidden_links_enabled"] and settings["hidden_links"]:
        links = []
        for row in settings["hidden_links"]:
            rel = "" if row["rel"] == "follow" else ' rel="%s"' % row["rel"]
            links.append('<a href="%s"%s>%s</a>' % (html.escape(row["url"], quote=True), rel, html.escape(row["name"])))
        experiments.append('<div data-cf-experiment="hidden-links" style="display:none" aria-hidden="true">%s</div>' % " ".join(links))
    if experiments:
        insert_at = document.body_end if document.body_end is not None else document.html_end
        if insert_at is None:
            insert_at = len(html_text)
        patches.append((insert_at, insert_at, "".join(experiments)))
    return _patch(html_text, patches)
