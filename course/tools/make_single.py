#!/usr/bin/env python3
"""Stitch the course pages into one Markdown document with the original
heading levels (Part = ##, Chapter = ###), then build one self-contained HTML
file with the documentation skill's builder.

Usage: make_single.py [OUT.html]   (default: ../agent-harness-spring-ai.html)
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
PAGES = os.path.join(COURSE, 'pages', 'course')
BUILDER = os.path.expanduser('~/.claude/skills/documentation/scripts/build_site.py')
TITLE = 'Building an Agent Harness with Spring AI'


def slug(text):
    # Same rule as build_site.py, so contents links match heading ids.
    s = re.sub(r'<[^>]+>', '', text)
    s = html.unescape(s).lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    return re.sub(r'[\s-]+', '-', s).strip('-') or 'section'


def read(path):
    text = open(path, encoding='utf-8').read()
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    return meta, text.strip()


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(COURSE, '..', 'agent-harness-spring-ai.html'))
    parts, anchors = [], {}   # anchors: "group/page.html" -> heading id
    for group in sorted(os.listdir(PAGES)):
        gdir = os.path.join(PAGES, group)
        if not os.path.isdir(gdir):
            continue
        label = json.load(open(os.path.join(gdir, '_group.json')))['label']
        pages = []
        for name in sorted(os.listdir(gdir)):
            if not name.endswith('.md'):
                continue
            meta, body = read(os.path.join(gdir, name))
            pages.append((name, meta, body))
        parts.append((group, label, pages))

    chunks, toc = [], []
    for group, label, pages in parts:
        if group == '00-start':
            for name, meta, body in pages:
                anchors[f'{group}/{name[:-3]}.html'] = slug(meta['title'])
                lvl = '##' if name.startswith('01') else '###'
                chunks.append(f'{lvl} {meta["title"]}\n\n{body}')
                toc.append((lvl, meta['title']))
        elif group == '99-about':
            for name, meta, body in pages:
                chunks.append(body)
                toc.extend(('##', h) for h in re.findall(r'^## (.+)$', body, re.M))
        else:
            chunks.append(f'## {label}')
            toc.append(('##', label))
            for name, meta, body in pages:
                anchors[f'{group}/{name[:-3]}.html'] = slug(label if name.startswith('00') else meta['title'])
                if name.startswith('00'):      # a part's own intro text sits under the part heading
                    chunks.append(body)
                else:
                    chunks.append(f'### {meta["title"]}\n\n{body}')
                    toc.append(('###', meta['title']))

    doc = '\n\n'.join(chunks)
    # Cross-page links become in-document jumps.
    def relink(m):
        target = os.path.normpath(m.group(1)).replace(os.sep, '/')
        for key, hid in anchors.items():
            if target.endswith(key) or target == key.split('/', 1)[1]:
                return f'](#{hid})'
        return m.group(0)
    doc = re.sub(r'\]\((?:\.\./)?([\w./-]+\.html)\)', relink, doc)

    contents = '\n'.join(('- ' if lvl == '##' else '    - ') + f'[{t}](#{slug(t)})' for lvl, t in toc)
    md = (f'---\ntitle: {TITLE}\nsubtitle: The Log Incident Watcher, from the first model call to durable execution\n---\n\n'
          f'## Contents\n\n{contents}\n\n{doc}\n')
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(md)
        tmp = f.name
    try:
        subprocess.run([sys.executable, BUILDER, '--single', tmp, out], check=True)
    finally:
        os.unlink(tmp)
    # The builder inlines docs.js, whose header comment contains a literal
    # "</script>". Inside an inline <script> that ends the element early, so
    # escape it in the one place the inlined code starts.
    page = open(out, encoding='utf-8').read()
    start = page.rfind('<script>')
    end = page.rfind('</script>')
    page = page[:start] + '<script>' + page[start + 8:end].replace('</script', '<\\/script') + page[end:]
    open(out, 'w', encoding='utf-8').write(page)


if __name__ == '__main__':
    main()
