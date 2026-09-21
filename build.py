#!/usr/bin/env python3
"""Parker Engine 中文文档站构建脚本（MDUI v1 风格）

用法：
    python build.py                # 全量构建（默认）
    python build.py --no-clean     # 保留已生成的 docs/ 目录，仅覆盖文件

做什么：
    1. 读 _nav.json（导航 schema，见下）
    2. 把 _content/<src>.md 用 markdown 转换成 HTML，
       再套上 mdui 文档模板（顶栏 + mdui-drawer 侧边栏 + mdui-typo 正文 + 上一页/下一页）
    3. 输出 docs/<slug>/index.html、文档门户 docs/index.html、站点根 404.html
    4. 按 REDIRECTS 表给旧站路径写 <meta http-equiv="refresh"> 跳转 stub 页
       （旧维基链接不再 404），并把正文里的历史链接就地改写到新地址

_nav.json schema：
    {
      "title": "站点标题",
      "groups": [
        {
          "title": "分组名",
          "items": [
            {"title": "页面名", "slug": "url-slug", "src": "文件名.md",
             "badge": "可选徽标", "desc": "可选一句话简介"},
            {"title": "文档总览", "index": true, "badge": "...", "desc": "..."},
            {"title": "外部链接", "href": "https://..."}
          ]
        }
      ],
      "links": [{"title": "侧边栏底部链接", "href": "..."}]
    }

    * slug + src   → 生成 docs/<slug>/index.html
    * index: true  → 该条目指向文档门户页 docs/index.html（不生成独立页面）
    * href         → 纯外链条目（不生成页面）
    * badge / desc → 可选，仅用于门户卡片与侧边栏提示

REDIRECTS（脚本内常量）：{旧页面路径: 新站内地址}，键是相对仓库根的路径，
例如 "函数/Psych/GeneralFunctions/index.html"（目录名里的 & 是合法字符，原样书写即可）。

依赖：Python 3.11 + markdown（3.10.2）。无网络依赖。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import xml.etree.ElementTree as etree
from pathlib import Path
from urllib.parse import quote

import markdown
from markdown.extensions import Extension
from markdown.extensions.toc import slugify_unicode
from markdown.treeprocessors import Treeprocessor

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "_content"
NAV_FILE = ROOT / "_nav.json"
DOCS_DIR = ROOT / "docs"

SITE_NAME = "Parker Engine"
SITE_TAGLINE = "中文文档"
SITE_VERSION = "0.2.8"
REPO_URL = "https://github.com/FNF-Pk-Dev/FNF_Parker-Engine-new"
RELEASES_URL = REPO_URL + "/releases"
PSYCH_URL = "https://github.com/ShadowMario/FNF-PsychEngine"

# 旧站路径 → 新路径。键是相对仓库根的旧页面路径，值是新的站内绝对地址；
# 构建时每个键都会生成一个带 <meta http-equiv="refresh"> 的跳转 stub 页，
# 同时这些旧地址也会被注册进 LINK_REWRITES，正文里的历史链接会被就地改写。
REDIRECTS = {
    "LuaCodingDocs/index.html": "/docs/lua-tutorial/",
    "函数/Parker/ModchatFunctions/index.html": "/docs/modchart-functions/",
    "函数/Psych/CallbackTemplates/index.html": "/docs/callbacks/",
    "函数/Psych/CustomSprites&TextsFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/DepracatedLuaFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/GameControlFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/GeneralFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/HScript&Haxe/index.html": "/docs/hscript-haxe/",
    "函数/Psych/ObjectFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/ShaderFunctions/index.html": "/docs/lua-psych/",
    "函数/Psych/Tweens&TimersFunctions/index.html": "/docs/lua-psych/",
}


def redirect_url(old_path: str) -> str:
    """把 REDIRECTS 的键（…/index.html）转成旧站里的 URL 形式（/目录/）。"""
    return "/" + old_path[: -len("index.html")]


def build_link_rewrites() -> dict[str, str]:
    """旧站 URL → 新 URL。收录 /路径 与 /路径/ 两种写法，以及百分号编码形式
    （中文目录名在旧文档里常常是编码过的）。"""
    out: dict[str, str] = {}
    for old_path, new_url in REDIRECTS.items():
        dir_url = redirect_url(old_path)
        for variant in (dir_url, dir_url.rstrip("/")):
            out[variant] = new_url
            encoded = quote(variant, safe="/")
            if encoded != variant:
                out[encoded] = new_url
    return out


# 旧站路径 → 新路径（内容里的历史链接改写，避免 404），由 REDIRECTS 推导
LINK_REWRITES = build_link_rewrites()

# ---------------------------------------------------------------------------
# 图标（内联 SVG：不依赖 material-icons 字体，保持零外部请求）
# ---------------------------------------------------------------------------

ICON_MENU = (
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">'
    '<path d="M3 6h18v2H3zM3 11h18v2H3zM3 16h18v2H3z"/></svg>'
)
ICON_BOOK = (
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">'
    '<path d="M6 2h11a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3zm0 2a1 1 '
    '0 0 0-1 1v14a1 1 0 0 0 1 1h1V4H6zm3 0v16h8a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H9z"/></svg>'
)
ICON_HOME = (
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">'
    '<path d="M12 3 2 12h3v9h6v-6h2v6h6v-9h3z"/></svg>'
)
ICON_GITHUB = (
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">'
    '<path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37'
    '-3.88-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 '
    '1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47'
    '.11-3.06 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.77.12 3.06'
    '.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.4-5.26 5.69.41.36.78 1.06.78 2.14v3.17c0 .31.2.67.8.56A11.5 '
    '11.5 0 0 0 23.5 12A11.5 11.5 0 0 0 12 .5z"/></svg>'
)
ICON_ARROW_LEFT = (
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">'
    '<path d="M14.7 5.3 8 12l6.7 6.7 1.4-1.4L10.8 12l5.3-5.3z"/></svg>'
)
ICON_ARROW_RIGHT = (
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">'
    '<path d="M9.3 5.3 7.9 6.7 13.2 12l-5.3 5.3 1.4 1.4L16 12z"/></svg>'
)


# ---------------------------------------------------------------------------
# 导航模型
# ---------------------------------------------------------------------------


class NavItem:
    def __init__(self, raw: dict):
        self.title: str = raw.get("title", "")
        self.slug: str | None = raw.get("slug")
        self.src: str | None = raw.get("src")
        self.href: str | None = raw.get("href")
        self.index: bool = bool(raw.get("index"))
        self.badge: str = raw.get("badge", "")
        self.desc: str = raw.get("desc", "")

    @property
    def is_page(self) -> bool:
        return bool(self.slug and self.src)

    @property
    def url(self) -> str:
        if self.index:
            return "/docs/"
        if self.is_page:
            return f"/docs/{self.slug}/"
        return self.href or "#"


class NavGroup:
    def __init__(self, raw: dict):
        self.title: str = raw.get("title", "")
        self.items: list[NavItem] = [NavItem(i) for i in raw.get("items", [])]


class Nav:
    def __init__(self, raw: dict):
        self.title: str = raw.get("title", SITE_NAME)
        self.groups: list[NavGroup] = [NavGroup(g) for g in raw.get("groups", [])]
        self.links: list[dict] = raw.get("links", [])

    @property
    def pages(self) -> list[tuple[NavGroup, NavItem]]:
        """按导航顺序展开的全部真实页面。"""
        out: list[tuple[NavGroup, NavItem]] = []
        for group in self.groups:
            for item in group.items:
                if item.is_page:
                    out.append((group, item))
        return out

    def portal_url(self) -> str:
        for group in self.groups:
            for item in group.items:
                if item.index:
                    return item.url
        return "/docs/"

    def validate(self) -> list[str]:
        errors: list[str] = []
        seen_slugs: set[str] = set()
        if not self.groups:
            errors.append("_nav.json 没有任何分组")
        for group in self.groups:
            if not group.title:
                errors.append("存在没有 title 的分组")
            if not group.items:
                errors.append(f"分组「{group.title}」没有任何条目")
            has_page = False
            for item in group.items:
                if item.is_page:
                    has_page = True
                    if item.slug in seen_slugs:
                        errors.append(f"slug 重复：{item.slug}")
                    seen_slugs.add(item.slug)
                    src = CONTENT_DIR / item.src
                    if not src.is_file():
                        errors.append(f"缺文件：_content/{item.src}（页面「{item.title}」）")
                elif not item.index and not item.href:
                    errors.append(f"条目「{item.title}」缺少 slug/src、index 或 href")
            if not has_page and not any(i.index for i in group.items):
                errors.append(f"分组「{group.title}」既没有页面也没有门户条目")
        # 内容目录里应有但未进导航的文件（仅提示）
        return errors


def load_nav() -> Nav:
    if not NAV_FILE.is_file():
        sys.exit(f"找不到 {NAV_FILE}")
    try:
        raw = json.loads(NAV_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"_nav.json 解析失败：{exc}")
    return Nav(raw)


def unused_content_files(nav: Nav) -> list[str]:
    used = {item.src for _, item in nav.pages}
    return sorted(p.name for p in CONTENT_DIR.glob("*.md") if p.name not in used)


# ---------------------------------------------------------------------------
# Markdown 扩展：提示块 + 表格包装
# ---------------------------------------------------------------------------

CALLOUT_KEYWORDS = {
    "注意": "note",
    "提示": "note",
    "警告": "warn",
    "危险": "warn",
    "废弃": "deprecated",
}
CALLOUT_RE = re.compile(r"^(注意|提示|警告|危险|废弃)\s*[:：]?\s*(.*)$", re.S)
INLINE_MARKUP_RE = re.compile(r"[。！？!?，,；;.]")


class CalloutTreeprocessor(Treeprocessor):
    """把首行以「注意：/警告：/废弃：」开头的引用块变成醒目色块。

    识别依据是引用块第一个段落去掉强调标记后的纯文本；
    整段只有标记时标记会被提升为色块标题，否则原段落内容全部保留。
    """

    def run(self, root: etree.Element) -> etree.Element:
        for parent, node in list(_iter_with_parent(root)):
            if node.tag != "blockquote":
                continue
            transformed = self._transform(node)
            if transformed is None:
                continue
            idx = list(parent).index(node)
            transformed.tail = node.tail
            parent.remove(node)
            parent.insert(idx, transformed)
        return root

    def _transform(self, bq: etree.Element) -> etree.Element | None:
        first_p = bq.find("p")
        if first_p is None:
            return None
        plain = "".join(first_p.itertext()).strip()
        match = CALLOUT_RE.match(plain)
        if not match:
            return None
        keyword, rest = match.group(1), match.group(2).strip()
        short_suffix = bool(rest) and len(rest) <= 8 and not INLINE_MARKUP_RE.search(rest)
        title = f"{keyword}：{rest}" if short_suffix else keyword
        if short_suffix or not rest:
            # 整段就是标记本身，标记提升为标题后整段丢弃
            bq.remove(first_p)
        else:
            # 段落还有正文：只摘掉行首的「注意：」标记，其余原样保留
            _strip_marker(first_p)
            if not (first_p.text or "").strip() and len(first_p) == 0:
                bq.remove(first_p)

        div = etree.Element("div")
        div.set("class", f"pk-callout pk-callout-{CALLOUT_KEYWORDS[keyword]}")
        head = etree.SubElement(div, "div")
        head.set("class", "pk-callout-title")
        head.text = title
        body = etree.SubElement(div, "div")
        body.set("class", "pk-callout-body")
        for child in list(bq):
            bq.remove(child)
            body.append(child)
        if len(body) == 0:
            div.remove(body)
        return div


MARKER_PREFIX_RE = re.compile(r"^(?:注意|提示|警告|危险|废弃)\s*[:：]?\s*")


def _strip_marker(paragraph: etree.Element) -> None:
    """删掉段落行首的提示标记，可能位于纯文本，也可能被 <strong>/<em> 包着。"""
    text = paragraph.text or ""
    match = MARKER_PREFIX_RE.match(text)
    if match:
        paragraph.text = text[match.end():]
        return
    first = next(iter(paragraph), None)
    if first is None:
        return
    inner = "".join(first.itertext()).strip().rstrip("：:")
    if inner not in CALLOUT_KEYWORDS:
        return
    # 首个行内元素整个就是标记：元素本身去掉，把它后面的文字接回来
    tail = re.sub(r"^\s*[:：]?\s*", "", first.tail or "")
    paragraph.remove(first)
    paragraph.text = (paragraph.text or "") + tail


class TableTreeprocessor(Treeprocessor):
    """给 markdown 表格套上 MDUI 的 .mdui-table-fluid 横向滚动容器。"""

    def run(self, root: etree.Element) -> etree.Element:
        for parent, node in list(_iter_with_parent(root)):
            if node.tag != "table":
                continue
            if parent.tag == "div" and "mdui-table-fluid" in (parent.get("class") or ""):
                continue
            classes = set((node.get("class") or "").split())
            classes.update({"mdui-table", "mdui-table-hoverable"})
            node.set("class", " ".join(sorted(classes)))
            wrapper = etree.Element("div")
            wrapper.set("class", "mdui-table-fluid pk-table-wrap")
            idx = list(parent).index(node)
            wrapper.tail = node.tail
            node.tail = None
            parent.remove(node)
            wrapper.append(node)
            parent.insert(idx, wrapper)
        return root


def _iter_with_parent(elem: etree.Element):
    for child in list(elem):
        yield elem, child
        yield from _iter_with_parent(child)


class ParkerExtras(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(CalloutTreeprocessor(md), "pk-callout", 5)
        md.treeprocessors.register(TableTreeprocessor(md), "pk-tables", 4)


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

SOURCE_COMMENT_RE = re.compile(r"^[ \t]*<!--\s*(?:source|external):.*?-->[ \t]*$\n?", re.M)
HTML_COMMENT_RE = re.compile(r"^[ \t]*<!--.*?-->[ \t]*$\n?", re.M)
HREF_RE = re.compile(r'href="(/[^"#?]*)"')


def strip_source_comments(text: str) -> str:
    """丢弃 md 里的 <!-- source: ... --> / <!-- external: ... --> 溯源注释。"""
    text = SOURCE_COMMENT_RE.sub("", text)
    text = re.sub(r"\A\n+", "", text)
    return text


def rewrite_links(html_text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        path = match.group(1)
        if path in LINK_REWRITES:
            return f'href="{LINK_REWRITES[path]}"'
        return match.group(0)

    return HREF_RE.sub(repl, html_text)


# 允许透传的 HTML 标签：其余形如 <Dynamic> / <String> 的文本（签名里的泛型）
# 会被浏览器当成未知标签吞掉，必须先转义成 &lt;…&gt;
HTML_WHITELIST = {
    "a", "abbr", "b", "blockquote", "br", "code", "dd", "del", "details", "div", "dl", "dt",
    "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "input", "ins", "kbd", "li",
    "mark", "ol", "p", "pre", "s", "small", "span", "strong", "sub", "summary", "sup", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul", "var", "wbr",
}
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[^\n]*$", re.M | re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
STRAY_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)(?:\s[^<>]*?)?/?>")


def _escape_stray_tags(chunk: str) -> str:
    def repl(match: re.Match[str]) -> str:
        if match.group(1).lower() in HTML_WHITELIST:
            return match.group(0)
        return match.group(0).replace("<", "&lt;").replace(">", "&gt;")

    return STRAY_TAG_RE.sub(repl, chunk)


def escape_stray_tags(text: str) -> str:
    """转义签名里的 <Dynamic> / <Int> 等泛型标记（代码区原样保留）。"""
    store: list[str] = []

    def save(match: re.Match[str]) -> str:
        store.append(match.group(0))
        return f"\x00PKCODE{len(store) - 1}\x00"

    masked = FENCE_RE.sub(save, text)
    masked = INLINE_CODE_RE.sub(save, masked)
    masked = _escape_stray_tags(masked)
    for index, chunk in enumerate(store):
        masked = masked.replace(f"\x00PKCODE{index}\x00", chunk)
    return masked


def render_markdown(text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", ParkerExtras()],
        extension_configs={"toc": {"slugify": slugify_unicode}},
        output_format="html",
    )
    body = md.convert(escape_stray_tags(strip_source_comments(text)))
    return rewrite_links(body)


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def head(title: str, desc: str, *, noindex: bool = False) -> str:
    robots = '\n<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#e91e63">
<meta name="description" content="{esc(desc)}">{robots}
<title>{esc(title)}</title>
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<link rel="stylesheet" href="/assets/mdui/css/mdui.min.css">
<link rel="stylesheet" href="/assets/site.css">
</head>"""


def appbar(nav: Nav) -> str:
    return f"""<header class="mdui-appbar mdui-appbar-fixed mdui-color-theme">
	<div class="mdui-toolbar">
		<button type="button" class="mdui-btn mdui-btn-icon mdui-ripple pk-drawer-toggle" aria-label="打开导航">{ICON_MENU}</button>
		<a class="mdui-typo-title pk-brand" href="/">{esc(SITE_NAME)}</a>
		<span class="pk-brand-sub">{esc(SITE_TAGLINE)}</span>
		<div class="mdui-toolbar-spacer"></div>
		<a class="mdui-btn mdui-btn-icon mdui-ripple" href="{esc(nav.portal_url())}" aria-label="文档门户" mdui-tooltip="{{content:'文档门户'}}">{ICON_BOOK}</a>
		<a class="mdui-btn mdui-btn-icon mdui-ripple" href="{REPO_URL}" target="_blank" rel="noopener" aria-label="GitHub 仓库" mdui-tooltip="{{content:'GitHub 仓库'}}">{ICON_GITHUB}</a>
	</div>
</header>"""


def drawer(nav: Nav, current_url: str) -> str:
    parts = [f"""<aside class="mdui-drawer pk-drawer" id="pk-drawer">
	<div class="pk-drawer-scroll">
		<a class="pk-drawer-hero mdui-ripple" href="/">
			<span class="pk-drawer-hero-title">{esc(SITE_NAME)}</span>
			<span class="pk-drawer-hero-sub">v{esc(SITE_VERSION)} · {esc(SITE_TAGLINE)}</span>
		</a>"""]
    for group in nav.groups:
        parts.append(f'\t\t<div class="mdui-subheader pk-nav-group">{esc(group.title)}</div>')
        for item in group.items:
            if not item.is_page and not item.index:
                continue
            url = item.url
            active = " mdui-list-item-active" if url == current_url else ""
            icon = ICON_HOME if item.index else ""
            icon_html = f'<span class="pk-nav-icon">{icon}</span>' if icon else ""
            parts.append(
                f'\t\t<a class="mdui-list-item mdui-ripple pk-nav-item{active}" href="{esc(url)}">'
            )
            parts.append(
                f'\t\t\t<div class="mdui-list-item-content">{icon_html}{esc(item.title)}</div>'
            )
            if item.badge:
                parts.append(f'\t\t\t<span class="pk-badge">{esc(item.badge)}</span>')
            parts.append("\t\t</a>")
    if nav.links:
        parts.append('\t\t<div class="mdui-divider pk-nav-divider"></div>')
        parts.append('\t\t<div class="mdui-subheader pk-nav-group">相关链接</div>')
        for link in nav.links:
            href = link.get("href", "#")
            external = href.startswith("http")
            extra = ' target="_blank" rel="noopener"' if external else ""
            parts.append(
                f'\t\t<a class="mdui-list-item mdui-ripple pk-nav-item" href="{esc(href)}"{extra}>'
                f'<div class="mdui-list-item-content">{esc(link.get("title", href))}</div></a>'
            )
    parts.append("\t</div>\n</aside>")
    return "\n".join(parts)


def footer() -> str:
    return f"""<footer class="pk-footer">
	<div class="mdui-container">
		<div class="pk-footer-inner">
			<span>{esc(SITE_NAME)} v{esc(SITE_VERSION)} · 中文文档</span>
			<span class="pk-footer-links">
				<a href="{REPO_URL}" target="_blank" rel="noopener">GitHub 仓库</a>
				<a href="{RELEASES_URL}" target="_blank" rel="noopener">下载</a>
				<a href="/docs/">文档门户</a>
			</span>
		</div>
		<div class="pk-footer-note">
			基于 <a href="{PSYCH_URL}" target="_blank" rel="noopener">Psych Engine</a> 分支开发 · 本站静态托管于 GitHub Pages
		</div>
	</div>
</footer>"""


def scripts() -> str:
    return """<script src="/assets/mdui/js/mdui.min.js"></script>
<script src="/assets/site.js"></script>
</body>
</html>"""


def breadcrumb(group_title: str, page_title: str) -> str:
    return f"""<nav class="pk-breadcrumb" aria-label="面包屑">
	<a href="/">首页</a><span class="pk-breadcrumb-sep">/</span><a href="/docs/">文档</a><span class="pk-breadcrumb-sep">/</span><span>{esc(group_title)}</span><span class="pk-breadcrumb-sep">/</span><span class="pk-breadcrumb-current">{esc(page_title)}</span>
</nav>"""


def pager(prev: NavItem | None, nxt: NavItem | None) -> str:
    if not prev and not nxt:
        return ""
    out = ['<nav class="pk-pager" aria-label="翻页">']
    if prev:
        out.append(
            f'\t<a class="mdui-btn mdui-btn-raised mdui-ripple pk-pager-btn pk-pager-prev" href="{esc(prev.url)}">'
            f'{ICON_ARROW_LEFT}<span class="pk-pager-text"><span class="pk-pager-label">上一页</span>'
            f'<span class="pk-pager-title">{esc(prev.title)}</span></span></a>'
        )
    else:
        out.append('\t<span class="pk-pager-btn pk-pager-empty"></span>')
    if nxt:
        out.append(
            f'\t<a class="mdui-btn mdui-btn-raised mdui-ripple mdui-color-theme pk-pager-btn pk-pager-next" href="{esc(nxt.url)}">'
            f'<span class="pk-pager-text"><span class="pk-pager-label">下一页</span>'
            f'<span class="pk-pager-title">{esc(nxt.title)}</span></span>{ICON_ARROW_RIGHT}</a>'
        )
    out.append("</nav>")
    return "\n".join(out)


def page_shell(nav: Nav, title: str, desc: str, current_url: str, main: str, refresh: str | None = None) -> str:
    head_html = head(title, desc, noindex=refresh is not None)
    if refresh is not None:
        # <meta http-equiv> 必须早早出现在 <head> 里：插在 charset 之后
        head_html = head_html.replace(
            '<meta charset="utf-8">',
            f'<meta charset="utf-8">\n<meta http-equiv="refresh" content="0; url={esc(refresh)}">',
            1,
        )
    return "\n".join(
        [
            head_html,
            '<body class="mdui-theme-primary-pink mdui-theme-accent-cyan mdui-theme-layout-dark mdui-appbar-with-toolbar">',
            appbar(nav),
            drawer(nav, current_url),
            '<main class="pk-main">',
            main,
            "</main>",
            footer(),
            scripts(),
        ]
    )


def render_doc_page(nav: Nav, group: NavGroup, item: NavItem, prev: NavItem | None, nxt: NavItem | None) -> str:
    src = CONTENT_DIR / item.src
    body = render_markdown(src.read_text(encoding="utf-8"))
    desc = item.desc or f"{SITE_NAME} 中文文档 - {item.title}"
    main = "\n".join(
        [
            '<div class="mdui-container pk-container">',
            breadcrumb(group.title, item.title),
            f'<article class="mdui-typo mdui-card mdui-shadow-2 pk-doc">{body}</article>',
            pager(prev, nxt),
            "</div>",
        ]
    )
    title = f"{item.title} - {SITE_NAME} {SITE_TAGLINE}"
    return page_shell(nav, title, desc, item.url, main)


def render_portal(nav: Nav) -> str:
    cards: list[str] = []
    for group in nav.groups:
        entries: list[str] = []
        for item in group.items:
            external = not item.is_page and not item.index
            extra = ' target="_blank" rel="noopener"' if external else ""
            badge = f'<span class="pk-badge">{esc(item.badge)}</span>' if item.badge else ""
            desc = (
                f'<div class="mdui-list-item-text pk-card-desc">{esc(item.desc)}</div>'
                if item.desc
                else ""
            )
            entries.append(
                f"""<a class="mdui-list-item mdui-ripple pk-portal-item" href="{esc(item.url)}"{extra}>
						<div class="mdui-list-item-content">
							<div class="mdui-list-item-title pk-portal-title">{esc(item.title)}</div>
							{desc}
						</div>
						{badge}
					</a>"""
            )
        count = len([i for i in group.items if i.is_page or i.index])
        subtitle = f"{count} 个页面" if count else "外部链接"
        cards.append(
            f"""<div class="mdui-col-xs-12 mdui-col-sm-6 mdui-col-md-4 pk-col">
				<div class="mdui-card mdui-shadow-2 pk-portal-card">
					<div class="mdui-card-primary">
						<div class="mdui-card-primary-title">{esc(group.title)}</div>
						<div class="mdui-card-primary-subtitle">{esc(subtitle)}</div>
					</div>
					<div class="mdui-divider"></div>
					<div class="pk-portal-list">
					{chr(10).join(entries)}
					</div>
				</div>
			</div>"""
        )
    total = len(nav.pages)
    main = f"""<div class="mdui-container pk-container">
		<header class="pk-portal-hero mdui-color-theme">
			<h1 class="mdui-typo-display-1 pk-portal-hero-title">文档门户</h1>
			<p class="pk-portal-hero-desc">Parker Engine {esc(SITE_VERSION)} 中文文档：{total} 个页面，覆盖 Lua（含 ES 扩展方言）、HScript、LScript(Luau)、Python 四种脚本语言，以及 Modchart 修饰器系统。</p>
			<div class="pk-portal-hero-actions">
				<a class="mdui-btn mdui-btn-raised mdui-ripple pk-btn-on-theme" href="/docs/lua-tutorial/">从 Lua 编码基础开始</a>
				<a class="mdui-btn mdui-btn-flat mdui-ripple pk-btn-on-theme-flat" href="{RELEASES_URL}" target="_blank" rel="noopener">下载引擎</a>
			</div>
		</header>
		<div class="mdui-row pk-portal-grid">
			{chr(10).join(cards)}
		</div>
	</div>"""
    desc = f"{SITE_NAME} 中文文档门户：Lua、HScript、LScript、Python 脚本与 Modchart 修饰器系统全部页面索引。"
    return page_shell(nav, f"文档门户 - {SITE_NAME} {SITE_TAGLINE}", desc, "/docs/", main)


def render_404(nav: Nav) -> str:
    main = f"""<div class="mdui-container pk-container">
		<div class="mdui-card mdui-shadow-2 pk-404">
			<div class="mdui-card-primary">
				<div class="mdui-card-primary-title pk-404-code">404</div>
				<div class="mdui-card-primary-subtitle">找不到这个页面</div>
			</div>
			<div class="mdui-card-content">
				<p>你访问的地址不存在，可能已被移动或改名。可以从下面的入口继续浏览：</p>
				<ul class="pk-404-list">
					<li><a href="/">返回首页</a> — 引擎介绍、特色功能与下载</li>
					<li><a href="/docs/">文档门户</a> — 全部 {len(nav.pages)} 个文档页面的索引</li>
					<li><a href="/docs/lua-tutorial/">Lua 编码基础</a> — 新手从这里开始</li>
				</ul>
			</div>
			<div class="mdui-card-actions">
				<a class="mdui-btn mdui-btn-raised mdui-ripple mdui-color-theme" href="/">返回首页</a>
				<a class="mdui-btn mdui-btn-raised mdui-ripple" href="/docs/">前往文档门户</a>
			</div>
		</div>
	</div>"""
    desc = "页面不存在 - Parker Engine 中文文档"
    return page_shell(nav, f"404 - {SITE_NAME} {SITE_TAGLINE}", desc, "", main)


def render_redirect(nav: Nav, old_path: str, target: str) -> str:
    """旧站地址的跳转 stub：meta refresh + 手动跳转按钮。"""
    old_url = redirect_url(old_path)
    main = f"""<div class="mdui-container pk-container">
		<div class="mdui-card mdui-shadow-2 pk-redirect">
			<div class="mdui-card-primary">
				<div class="mdui-card-primary-title pk-redirect-title">页面已迁移</div>
				<div class="mdui-card-primary-subtitle">旧地址 <code>{esc(old_url)}</code>，新地址 <code>{esc(target)}</code></div>
			</div>
			<div class="mdui-card-content">
				<p>这个旧维基地址的内容已经搬到新版中文文档站，页面正在自动跳转。</p>
				<p>如果浏览器没有自动跳转，请点击下面的按钮。</p>
			</div>
			<div class="mdui-card-actions">
				<a class="mdui-btn mdui-btn-raised mdui-ripple mdui-color-theme" href="{esc(target)}">前往新页面</a>
				<a class="mdui-btn mdui-btn-flat mdui-ripple" href="/docs/">文档门户</a>
			</div>
		</div>
	</div>"""
    desc = f"旧地址 {old_url} 已迁移到 {target}，页面正在自动跳转。"
    return page_shell(
        nav,
        f"页面已迁移 - {SITE_NAME} {SITE_TAGLINE}",
        desc,
        target,
        main,
        refresh=target,
    )


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------


def build(clean: bool = True) -> int:
    nav = load_nav()
    errors = nav.validate()
    if errors:
        print("构建失败，_nav.json / _content 有问题：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if clean and DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    pages = nav.pages
    written: list[Path] = []
    for idx, (group, item) in enumerate(pages):
        prev = pages[idx - 1][1] if idx > 0 else None
        nxt = pages[idx + 1][1] if idx + 1 < len(pages) else None
        out_dir = DOCS_DIR / item.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.html"
        out_file.write_text(
            render_doc_page(nav, group, item, prev, nxt), encoding="utf-8", newline="\n"
        )
        written.append(out_file)

    portal = DOCS_DIR / "index.html"
    portal.write_text(render_portal(nav), encoding="utf-8", newline="\n")
    written.append(portal)

    err404 = ROOT / "404.html"
    err404.write_text(render_404(nav), encoding="utf-8", newline="\n")
    written.append(err404)

    stubs: list[tuple[Path, str]] = []
    for old_path, target in REDIRECTS.items():
        out_file = ROOT / old_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(render_redirect(nav, old_path, target), encoding="utf-8", newline="\n")
        stubs.append((out_file, target))

    print(f"构建完成：{len(pages)} 个文档页面 + 1 个门户页 + 1 个 404 页")
    for path in written:
        print(f"  {path.relative_to(ROOT).as_posix()}  ({path.stat().st_size} 字节)")

    print(f"\n旧地址跳转页：{len(stubs)} 个")
    for path, target in stubs:
        print(f"  /{path.relative_to(ROOT).as_posix()[: -len('index.html')]}  →  {target}")

    leftover = unused_content_files(nav)
    if leftover:
        print("\n提示：以下 _content 文件不在 _nav.json 中（未生成页面）：")
        for name in leftover:
            print(f"  - {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Parker Engine 中文文档站（MDUI v1 风格）")
    parser.add_argument("--no-clean", action="store_true", help="不删除已存在的 docs/ 目录")
    args = parser.parse_args()
    return build(clean=not args.no_clean)


if __name__ == "__main__":
    raise SystemExit(main())
