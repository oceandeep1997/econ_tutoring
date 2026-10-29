"""Mirror econ-tutoring.com (Squarespace) into a self-contained static site.

Downloads every page, plus the CSS, JS, images, fonts and files they reference on the
Squarespace CDNs, into assets/<host>/<path>, and rewrites the URLs to relative paths so
the site renders from GitHub Pages (or any static host) without Squarespace.

Usage: python3 tools/mirror.py            (run from the repo root)
"""
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = "https://www.econ-tutoring.com"
PAGES = {"/": "index.html", "/home": "home.html", "/appointments": "appointments.html",
         "/contact": "contact.html"}
CDN_HOSTS = ["assets.squarespace.com", "static1.squarespace.com", "images.squarespace-cdn.com",
             "file.squarespace-cdn.com", "definitions.sqspcdn.com", "use.typekit.net",
             "p.typekit.net", "fonts.googleapis.com", "fonts.gstatic.com"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
OUT = os.getcwd()
HOSTS_RE = "|".join(re.escape(h) for h in CDN_HOSTS)
# Matches https://host/path, //host/path and the JSON-escaped https:\/\/host\/path forms.
URL_RE = re.compile(r'(?:https?:)?(?:\\?/){2}(' + HOSTS_RE + r')((?:\\?/[^\s"\'<>()\\,&]*)*)')
CSS_URL_RE = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)|@import\s+["\']([^"\']+)["\']')

done = {}


def fetch(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError:
            raise
        except Exception:  # flaky CDN edges (e.g. TLS hostname mismatch) - retry
            if i == tries - 1:
                raise
            time.sleep(1 + i)


def local_path(host, path):
    path = urllib.parse.unquote(path.split("?")[0].split("#")[0]) or "/"
    if path.endswith("/"):
        path += "index"
    return os.path.join("assets", host, path.lstrip("/"))


def download(host, path):
    """Download https://host/path once; returns the repo-relative local path or None."""
    key = (host, path.split("#")[0])
    if key in done:
        return done[key]
    rel = local_path(host, path)
    done[key] = rel
    dest = os.path.join(OUT, rel)
    try:
        if not os.path.exists(dest):
            data = fetch(f"https://{host}{path.split('#')[0]}")
            if rel.endswith(".css") or b"@font-face" in data[:2000]:
                data = rewrite_css(data.decode("utf-8", "replace"), host, path).encode()
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
    except Exception as e:  # keep going: a missing asset should not abort the backup
        print(f"  ! {host}{path}: {e}", file=sys.stderr)
        done[key] = None
    return done[key]


def rewrite_css(css, host, path):
    base = f"https://{host}{path}"
    own_dir = os.path.dirname(local_path(host, path))

    def sub(m):
        ref = m.group(1) or m.group(2)
        if ref.startswith("data:") or ref.startswith("#"):
            return m.group(0)
        u = urllib.parse.urlparse(urllib.parse.urljoin(base, ref))
        if u.netloc not in CDN_HOSTS:
            return m.group(0)
        rel = download(u.netloc, u.path + (f"?{u.query}" if u.query else ""))
        if not rel:
            return m.group(0)
        new = os.path.relpath(rel, own_dir) + (f"#{u.fragment}" if u.fragment else "")
        return m.group(0).replace(ref, new)

    return CSS_URL_RE.sub(sub, css)


def rewrite_html(html):
    found = {(m.group(1), m.group(2).replace("\\/", "/")) for m in URL_RE.finditer(html)}
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(lambda hp: download(*hp), [(h, p) for h, p in found if p]))

    def sub(m):
        host, raw = m.group(1), m.group(2)
        path = raw.replace("\\/", "/")
        rel = done.get((host, path.split("#")[0])) if path else None
        if not rel:
            return m.group(0)
        frag = "#" + path.split("#", 1)[1] if "#" in path else ""
        new = rel + frag
        return new.replace("/", "\\/") if "\\/" in m.group(0) else new

    html = URL_RE.sub(sub, html)
    # Site-relative assets (social icon sprite etc.) served from the site itself.
    for ref in set(re.findall(r'(?:href|src)="(/universal/[^"#]+)', html)):
        rel = os.path.join("assets", "site", ref.lstrip("/"))
        dest = os.path.join(OUT, rel)
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(fetch(SITE + ref))
        html = html.replace(f'"{ref}', f'"{rel}')
    # Internal navigation -> flat .html files so it works under a /<repo>/ project path too.
    for route, fname in PAGES.items():
        r = re.escape(route.rstrip("/"))
        html = re.sub(r'href="(?:' + re.escape(SITE) + r')?' + r + r'/?(#[^"]*)?"',
                      lambda m, f=fname: f'href="{f}{m.group(1) or ""}"', html)
    return html


def main():
    for route, fname in PAGES.items():
        print(f"page {route} -> {fname}")
        html = fetch(SITE + route).decode("utf-8")
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(rewrite_html(html))
    ok = sum(1 for v in done.values() if v)
    print(f"{ok} assets saved, {len(done) - ok} failed")


if __name__ == "__main__":
    main()
