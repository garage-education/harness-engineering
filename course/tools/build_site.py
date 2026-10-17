#!/usr/bin/env python3
"""Build the course site from course/pages into site/.

Needs only the Python 3 standard library.

Usage:
  build_site.py                 Build site/.
  build_site.py --serve         Build, serve on http://localhost:8000, and rebuild on every change.
  build_site.py --serve --port 9000

Inputs:
  course/site.json              Title, colors, footer, and print settings.
  course/index.html             The landing page body. Its first comment holds the page title.
  course/pages/<section>/<group>/*.md
                                One page per file. Front matter: title, sidebar_label, description.
  course/pages/<section>/<group>/_group.json
                                The group label, description, and color ("cat").
  course/assets/                docs.css and docs.js, copied to site/_assets/.
"""
import argparse
import functools
import html
import http.server
import json
import os
import re
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
ROOT = os.path.dirname(COURSE)
PAGES = os.path.join(COURSE, 'pages')
ASSETS = os.path.join(COURSE, 'assets')
OUT = os.path.join(ROOT, 'site')


# ---------- Markdown ----------

def esc(s):
    return html.escape(s, quote=True).replace('&#x27;', "'")


def slug(text):
    s = re.sub(r'<[^>]+>', '', text)
    s = html.unescape(s).lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    return re.sub(r'[\s-]+', '-', s).strip('-') or 'section'


def span(cls, text):
    return f'<span class="{cls}">{esc(text)}</span>'


JAVA_KW = {'public', 'class', 'private', 'protected', 'this', 'new', 'null', 'interface', 'extends',
           'implements', 'record', 'enum', 'throws', 'true', 'false', 'super'}
JAVA_DT = {'final', 'int', 'void', 'static', 'boolean', 'long', 'double', 'var'}
JAVA_CF = {'return', 'if', 'else', 'for', 'while', 'throw', 'try', 'catch', 'switch', 'case', 'break'}
JAVA_BU = {'String', 'Integer', 'Object', 'List', 'Map', 'Exception', 'Thread', 'Instant'}
SQL_KW = {'CREATE', 'TABLE', 'IF', 'NOT', 'EXISTS', 'PRIMARY', 'KEY', 'NULL', 'SELECT', 'FROM', 'WHERE',
          'INSERT', 'INTO', 'VALUES', 'ORDER', 'BY', 'LIMIT', 'INDEX', 'ON', 'USING', 'AS', 'AND', 'OR'}


def highlight_java(line, state):
    """Return (html, state). state['comment'] is True inside a /* ... */ block."""
    out, i = [], 0
    if state['comment']:
        end = line.find('*/')
        if end < 0:
            return (span('co', line) if line else ''), state
        out.append(span('co', line[:end + 2]))
        i, state['comment'] = end + 2, False
    m = re.match(r'(package|import)( .*)', line)
    if m:
        return span('kw', m.group(1)) + esc(m.group(2)), state
    prev_dot = False
    while i < len(line):
        ch = line[i]
        if line.startswith('/*', i):
            end = line.find('*/', i + 2)
            if end < 0:
                out.append(span('co', line[i:]))
                state['comment'] = True
                break
            out.append(span('co', line[i:end + 2]))
            i = end + 2
            continue
        if line.startswith('//', i):
            out.append(span('co', line[i:]))
            break
        if ch == '"':
            j = i + 1
            while j < len(line) and line[j] != '"':
                j += 2 if line[j] == '\\' else 1
            out.append(span('st', line[i:j + 1]))
            i, prev_dot = j + 1, False
            continue
        if ch == '@':
            w = re.match(r'@\w+', line[i:]).group()
            out.append(span('at', w))
            i += len(w)
            continue
        if ch.isdigit():
            w = re.match(r'\d+', line[i:]).group()
            out.append(span('dv', w))
            i += len(w)
            continue
        if ch.isalpha() or ch == '_':
            w = re.match(r'\w+', line[i:]).group()
            rest = line[i + len(w):]
            if w in JAVA_KW:
                out.append(span('kw', w))
            elif w in JAVA_DT:
                out.append(span('dt', w))
            elif w in JAVA_CF:
                out.append(span('cf', w))
            elif w in JAVA_BU and not prev_dot:
                out.append(span('bu', w))
            elif prev_dot or rest.startswith('('):
                out.append(span('fu', w))
            else:
                out.append(esc(w))
            i, prev_dot = i + len(w), False
            continue
        if ch in ' \t':
            out.append(ch)
            i += 1
            continue
        op = re.match(r'[^\w\s"@/]+|/', line[i:]).group()
        out.append(span('op', op))
        prev_dot = op.endswith('.')
        i += len(op)
    return ''.join(out), state


def highlight_simple(line, lang):
    """Comments, strings, and keywords for the other languages the course uses."""
    comment = {'yaml': '#', 'bash': '#', 'sql': '--', 'kotlin': '//', 'python': '#', 'toml': '#'}.get(lang)
    if lang == 'markdown':
        if line.startswith('#') or line == '---':
            return span('co' if line == '---' else 'fu', line)
        m = re.match(r'(\d+\. )(.*)', line)
        if m:
            return span('ss', m.group(1)) + esc(m.group(2))
        return esc(line)
    out, i = [], 0
    while i < len(line):
        if comment and line.startswith(comment, i):
            out.append(span('co', line[i:]))
            break
        ch = line[i]
        if ch == '"':
            j = line.find('"', i + 1)
            j = len(line) - 1 if j < 0 else j
            tok = line[i:j + 1]
            # A JSON key is a string followed by a colon.
            key = lang == 'json' and line[j + 1:].lstrip().startswith(':')
            out.append(span('dt' if key else 'st', tok))
            i = j + 1
            continue
        if ch.isalpha() or ch == '_':
            w = re.match(r'[\w-]+', line[i:]).group()
            if lang == 'sql' and w.upper() in SQL_KW and w.isupper():
                out.append(span('kw', w))
            elif lang == 'yaml' and line[i + len(w):].startswith(':') and not line[:i].strip('- '):
                out.append(span('fu', w))
            else:
                out.append(esc(w))
            i += len(w)
            continue
        if ch.isdigit():
            w = re.match(r'\d+', line[i:]).group()
            out.append(span('dv', w))
            i += len(w)
            continue
        out.append(esc(ch))
        i += 1
    return ''.join(out)


def code_block(lang, lines, cid):
    if lang in ('', 'text'):
        return '<pre><code>' + esc('\n'.join(lines)) + '</code></pre>'
    state, rows = {'comment': False}, []
    for n, line in enumerate(lines, 1):
        if lang == 'java':
            body, state = highlight_java(line, state)
        else:
            body = highlight_simple(line, lang)
        rows.append(f'<span id="{cid}-{n}"><a href="#{cid}-{n}" aria-hidden="true" tabindex="-1"></a>{body}</span>')
    return (f'<div class="sourceCode" id="{cid}"><pre class="sourceCode {lang}"><code class="sourceCode {lang}">'
            + '\n'.join(rows) + '</code></pre></div>')


def inline(text, link=None):
    # Swap code spans for placeholders first, so bold and links can wrap them.
    codes = []

    def hold(m):
        codes.append('<code>' + esc(m.group(1)) + '</code>')
        return '\x00%d\x00' % (len(codes) - 1)

    t = re.sub(r'`([^`]+)`', hold, text)
    # Keep inline HTML tags, escape the rest.
    pieces = re.split(r'(</?[a-zA-Z][^>]*>)', t)
    t = ''.join(p if re.match(r'</?[a-zA-Z][^>]*>$', p) else esc(p) for p in pieces)
    t = re.sub(r'\[(NEEDS INPUT:[^\]]*)\]', r'<span class="needs-input">\1</span>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)',
               lambda m: f'<a href="{link(m.group(2)) if link else m.group(2)}">{m.group(1)}</a>', t)
    return re.sub('\x00(\\d+)\x00', lambda m: codes[int(m.group(1))], t)


BLOCK_START = re.compile(r'(```|#{1,6} |<|\||- |\d+\. |> |:::)')


def read_tabs(lines, i):
    """Read a '::: tabs' block that starts at lines[i]. Returns ([(label, body lines)], next index)."""
    tabs, j = [], i + 1
    while j < len(lines) and lines[j].strip() != ':::':
        m = re.match(r'::: tab (.+)', lines[j].strip())
        if not m:
            j += 1
            continue
        k = j + 1
        while k < len(lines) and lines[k].strip() != ':::':
            k += 1
        tabs.append((m.group(1).strip(), lines[j + 1:k]))
        j = k + 1
    return tabs, j + 1


def tab_group(tabs, link, prefix):
    """One language tab group. Without JavaScript, every panel shows, each under its label."""
    bar, panels = [], []
    for n, (label, body) in enumerate(tabs):
        lang, pid = slug(label), f'{prefix}-{slug(label)}'
        selected = 'true' if n == 0 else 'false'
        bar.append(f'<button type="button" role="tab" class="lang-tab" id="{pid}-tab" data-lang="{lang}" '
                   f'aria-controls="{pid}" aria-selected="{selected}">{esc(label)}</button>')
        html = render('\n'.join(body), link, f'{prefix}{lang}')[0]
        panels.append(f'<div class="lang-panel" role="tabpanel" id="{pid}" data-lang="{lang}" '
                      f'data-label="{esc(label)}" aria-labelledby="{pid}-tab">\n{html}\n</div>')
    return ('<div class="lang-tabs">\n<div class="lang-tabs__bar" role="tablist" aria-label="Code language">'
            + ''.join(bar) + '</div>\n' + '\n'.join(panels) + '\n</div>')


def render(md, link=None, cb_prefix='cb'):
    """Render the Markdown subset the course uses. Returns (html, [(level, id, text)])."""
    lines = md.split('\n')
    out, heads, i, cb, tg = [], [], 0, 1, 1
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.strip() == '::: tabs':
            tabs, i = read_tabs(lines, i)
            out.append(tab_group(tabs, link, f'{cb_prefix}t{tg}'))
            tg += 1
            continue
        if line.startswith('```'):
            lang, j = line[3:].strip(), i + 1
            while j < len(lines) and not lines[j].startswith('```'):
                j += 1
            out.append(code_block(lang, lines[i + 1:j], f'{cb_prefix}{cb}'))
            cb, i = cb + 1, j + 1
            continue
        m = re.match(r'(#{2,6}) (.+)', line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            hid = slug(text)
            heads.append((level, hid, text))
            out.append(f'<h{level} id="{hid}">{inline(text, link)}'
                       f'<a class="anchor" href="#{hid}" aria-label="Link to this section">#</a></h{level}>')
            i += 1
            continue
        m = re.match(r'<(figure|svg|div|table)\b', line)
        if m:
            tag, j = m.group(1), i
            while j < len(lines) and f'</{tag}>' not in lines[j]:
                j += 1
            block = '\n'.join(lines[i:j + 1])
            block = re.sub(r'<figcaption>(.*?)</figcaption>',
                           lambda c: '<figcaption>\n' + inline(c.group(1).strip(), link) + '\n</figcaption>',
                           block, flags=re.S)
            out.append(block)
            i = j + 1
            continue
        if line.startswith('<'):
            out.append(line)
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            t = '<div class="table-wrap"><table>\n<thead>\n<tr>\n'
            t += ''.join(f'<th>{inline(c, link)}</th>\n' for c in rows[0]) + '</tr>\n</thead>\n<tbody>\n'
            for r in rows[2:]:
                t += '<tr>\n' + ''.join(f'<td>{inline(c, link)}</td>\n' for c in r) + '</tr>\n'
            out.append(t + '</tbody>\n</table></div>')
            continue
        if line.startswith('> '):
            quote = []
            while i < len(lines) and lines[i].startswith('>'):
                quote.append(lines[i][1:].lstrip())
                i += 1
            out.append('<blockquote>\n' + render('\n'.join(quote), link, cb_prefix + 'q')[0] + '\n</blockquote>')
            continue
        m = re.match(r'(- |\d+\. )', line)
        if m:
            ordered = m.group(1) != '- '
            items = []
            pattern = r'\d+\. ' if ordered else r'- '
            while i < len(lines) and re.match(pattern, lines[i]):
                items.append(re.sub('^' + pattern, '', lines[i]))
                i += 1
            if not ordered and all(re.match(r'\[[ x]\] ', it) for it in items):
                checked = lambda it: ' checked=""' if it[1] == 'x' else ''
                lis = ''.join(f'<li><label><input type="checkbox"{checked(it)} />'
                              f'{inline(it[4:], link)}</label></li>\n' for it in items)
                out.append('<ul class="task-list">\n' + lis + '</ul>')
            else:
                tag = 'ol' if ordered else 'ul'
                out.append(f'<{tag}>\n' + ''.join(f'<li>{inline(it, link)}</li>\n' for it in items) + f'</{tag}>')
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
            para.append(lines[i])
            i += 1
        out.append('<p>' + inline(' '.join(para), link) + '</p>')
    return '\n'.join(out), heads


# ---------- Course model ----------

def read_page(path):
    text = open(path, encoding='utf-8').read()
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    return meta, text.strip()


def load():
    config = json.load(open(os.path.join(COURSE, 'site.json'), encoding='utf-8'))
    sections = []
    for sec in config['sections']:
        sdir = os.path.join(PAGES, sec['dir'])
        groups = []
        for g in sorted(os.listdir(sdir)):
            gdir = os.path.join(sdir, g)
            if not os.path.isdir(gdir):
                continue
            info = json.load(open(os.path.join(gdir, '_group.json'), encoding='utf-8'))
            pages = []
            for name in sorted(os.listdir(gdir)):
                if name.endswith('.md'):
                    meta, body = read_page(os.path.join(gdir, name))
                    pages.append({'group': g, 'name': name[:-3], 'meta': meta, 'body': body,
                                  'url': f'{sec["dir"]}/{g}/{name[:-3]}.html'})
            groups.append({'dir': g, 'info': info, 'pages': pages})
        sections.append({**sec, 'groups': groups})
    return config, sections


# ---------- Page chrome ----------

def head(config, title, prefix, body_class=''):
    theme = ''.join(f'{k}:{v};' for k, v in config.get('theme', {}).items())
    cls = f' class="{body_class}"' if body_class else ''
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>'
            f'<link rel="stylesheet" href="{prefix}_assets/docs.css"><style>:root{{{theme}}}</style></head><body{cls}>')


def topbar(config, sections, prefix, active=None, menu=True, here=''):
    links = ''.join(
        f'<a class="topbar__link{" topbar__link--active" if s["dir"] == active else ""}" '
        f'href="{relative(s["dir"] + "/index.html", here)}">{esc(s["label"])}</a>' for s in sections)
    button = '<button class="topbar__menu" type="button" aria-label="Open navigation">Menu</button>' if menu else ''
    return (f'<header class="topbar"><div class="topbar__inner"><a class="topbar__brand" href="{prefix}index.html">'
            f'{esc(config["title"])}</a><span class="topbar__title">{esc(config["subtitle"])}</span>'
            f'<nav class="topbar__links">{links}</nav>{button}</div></header>')


def footer(config, prefix):
    return (f'<footer class="footer"><div class="wrap"><strong>{esc(config["title"])}</strong>'
            f'<span>{esc(config["footer"])}</span></div></footer>'
            f'<script src="{prefix}_assets/docs.js"></script></body></html>')


def sidebar(sections, sec, here, current=None):
    top = ''.join(f'<li><a href="{relative(s["dir"] + "/index.html", here)}">{esc(s["label"])}</a></li>'
                  for s in sections)
    active = lambda p: ' class="active"' if p is current else ''
    groups = ''
    for g in sec['groups']:
        cat = g['info'].get('cat')
        attr = f' data-cat style="--cat: var(--{cat})"' if cat else ''
        items = ''.join(
            f'<li><a{active(p)} href="{relative(p["url"], here)}">'
            f'{esc(p["meta"].get("sidebar_label", p["meta"]["title"]))}</a></li>' for p in g['pages'])
        groups += f'<li class="sidebar__group"{attr}><span>{esc(g["info"]["label"])}</span><ul>{items}</ul></li>'
    return (f'<aside class="sidebar"><div class="sidebar__links"><ul>{top}</ul></div>'
            f'<div class="sidebar__section"><span class="sidebar__name">{esc(sec["label"])}</span>'
            f'<span class="sidebar__hint">{esc(sec.get("hint", ""))}</span></div><ul>{groups}</ul></aside>')


def relative(target, page_dir):
    return os.path.relpath(target, page_dir or '.').replace(os.sep, '/')


# ---------- Builders ----------

def build_page(config, sections, sec, page, prev, nxt):
    prefix = '../../'
    here = f'{sec["dir"]}/{page["group"]}'
    body, heads = render(page['body'])
    label = lambda p: esc(p['meta'].get('sidebar_label', p['meta']['title']))
    group = next(g for g in sec['groups'] if g['dir'] == page['group'])
    pager = ''
    if prev:
        pager += f'<a class="prev" href="{relative(prev["url"], here)}"><small>Previous</small>{label(prev)}</a>'
    if nxt:
        pager += f'<a class="next" href="{relative(nxt["url"], here)}"><small>Next</small>{label(nxt)}</a>'
    toc = ''.join(f'<a class="lvl{lv}" href="#{hid}">{esc(re.sub(r"`", "", t))}</a>' for lv, hid, t in heads if lv <= 3)
    return (head(config, f'{page["meta"]["title"]} · {config["title"]}', prefix)
            + topbar(config, sections, prefix, sec['dir'], here=here)
            + '<div class="shell">' + sidebar(sections, sec, here, page)
            + f'<main class="content"><ol class="breadcrumbs"><li><a href="../index.html">{esc(sec["label"])}</a></li>'
            + f'<li><span>{esc(group["info"]["label"])}</span></li><li><span>{label(page)}</span></li></ol>'
            + f'<article class="doc"><h1>{esc(page["meta"]["title"])}</h1>\n{body}\n</article>'
            + f'<nav class="pager">{pager}</nav></main><nav class="toc" aria-label="On this page">{toc}</nav></div>'
            + footer(config, prefix))


def build_section_index(config, sections, sec):
    prefix = '../'
    parts = ''
    for g in sec['groups']:
        rows = ''.join(
            f'<li><a href="{p["group"]}/{p["name"]}.html"><strong>'
            f'{esc(p["meta"].get("sidebar_label", p["meta"]["title"]))}</strong>'
            f'<span>{esc(p["meta"].get("description", ""))}</span><em>Read →</em></a></li>' for p in g['pages'])
        parts += (f'<h2>{esc(g["info"]["label"])}</h2><p>{esc(g["info"].get("description", ""))}</p>'
                  f'<ul class="rows">{rows}</ul>')
    return (head(config, f'{sec["label"]} · {config["title"]}', prefix)
            + topbar(config, sections, prefix, sec['dir'], here=sec['dir'])
            + '<div class="shell">' + sidebar(sections, sec, sec['dir'])
            + f'<main class="content"><article class="doc"><h1>{esc(sec["label"])}</h1>'
            + f'<p class="lead">{esc(sec.get("hint", ""))}</p>{parts}</article></main><nav class="toc"></nav></div>'
            + footer(config, prefix))


def build_landing(config, sections):
    src = open(os.path.join(COURSE, 'index.html'), encoding='utf-8').read()
    m = re.match(r'\s*<!--(.*?)-->\s*', src, re.S)
    body = src[m.end():] if m else src
    return (head(config, config['title'], '', 'landing')
            + topbar(config, sections, '', menu=False) + '\n' + body.rstrip() + '\n'
            + footer(config, ''))


def build_print(config, sections):
    settings = config.get('print', {})
    skip_sections = set(settings.get('skip_sections', []))
    skip_pages = set(settings.get('skip_pages', []))
    pages = [p for s in sections if s['dir'] not in skip_sections
             for g in s['groups'] for p in g['pages'] if p['url'] not in skip_pages]
    anchor = lambda url: 'p-' + url[:-5].replace('/', '')

    out = [head(config, settings.get('title', config['title']), ''),
           '<main class="report"><section class="print-page">'
           f'<p class="hero__eyebrow">{esc(config["subtitle"])}</p>'
           f'<h1 class="report__title">{esc(settings.get("title", config["title"]))}</h1>'
           f'<p class="report__subtitle">{esc(settings.get("subtitle", ""))}</p></section>']
    for p in pages:
        here = os.path.dirname(p['url'])

        def link(target, here=here):
            if re.match(r'[a-z]+:', target) or target.startswith('#'):
                return target
            path, _, frag = target.partition('#')
            full = os.path.normpath(os.path.join(here, path)).replace(os.sep, '/')
            return '#' + (frag or anchor(full))

        body, _ = render(p['body'], link)
        out.append(f'<section class="print-page" id="{anchor(p["url"])}"><article class="doc">'
                   f'<h1>{esc(p["meta"]["title"])}</h1>\n{body}\n</article></section>')
    out.append('</main><script src="_assets/docs.js"></script></body></html>')
    return ''.join(out)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def build():
    config, sections = load()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(ASSETS, os.path.join(OUT, '_assets'))
    write(os.path.join(OUT, 'index.html'), build_landing(config, sections))
    count = 0
    for sec in sections:
        write(os.path.join(OUT, sec['dir'], 'index.html'), build_section_index(config, sections, sec))
        flat = [p for g in sec['groups'] for p in g['pages']]
        for i, p in enumerate(flat):
            prev = flat[i - 1] if i > 0 else None
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            write(os.path.join(OUT, p['url']), build_page(config, sections, sec, p, prev, nxt))
            count += 1
    write(os.path.join(OUT, 'print.html'), build_print(config, sections))
    return count


# ---------- Local server ----------

def snapshot():
    """Modification times of every source file, to detect edits."""
    stamps = {}
    for base in (PAGES, ASSETS):
        for d, _, files in os.walk(base):
            for f in files:
                p = os.path.join(d, f)
                stamps[p] = os.path.getmtime(p)
    for f in ('site.json', 'index.html'):
        p = os.path.join(COURSE, f)
        stamps[p] = os.path.getmtime(p)
    return stamps


def watch():
    last = snapshot()
    while True:
        time.sleep(1)
        now = snapshot()
        if now != last:
            last = now
            try:
                print(f'Rebuilt {build()} pages.', flush=True)
            except Exception as e:  # keep serving the last good build
                print(f'Build failed: {e}', flush=True)


def serve(port):
    threading.Thread(target=watch, daemon=True).start()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
    with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as httpd:
        print(f'Serving http://localhost:{port}/  (Ctrl+C to stop). Edits to course/ rebuild the site.', flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--serve', action='store_true', help='serve site/ and rebuild on changes')
    ap.add_argument('--port', type=int, default=8000)
    args = ap.parse_args()
    print(f'Built {build()} pages into {os.path.relpath(OUT)}', flush=True)
    if args.serve:
        serve(args.port)


if __name__ == '__main__':
    main()
