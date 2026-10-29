# econ_tutoring

Static backup of [econ-tutoring.com](https://www.econ-tutoring.com/) (Squarespace), mirrored
so the same design renders from GitHub Pages or any static host.

| File | Page |
| --- | --- |
| `index.html` | `/` |
| `home.html` | `/home` |
| `appointments.html` | `/appointments` |
| `contact.html` | `/contact` |

Images, CSS, fonts and scripts live under `assets/<cdn-host>/<path>`, and all links are relative,
so the site works at a domain root or under a `/<repo>/` project path.

## Refresh the backup

```sh
rm -rf assets *.html && python3 tools/mirror.py
```

## Preview locally

```sh
python3 -m http.server 8000   # then open http://localhost:8000
```

## Limits of a static copy

- The contact form and the Acuity/Calendly booking widgets still talk to Squarespace, Acuity and
  Calendly. The form only submits while the Squarespace site is live.
- Squarespace's JS loads some lazy chunks from its CDN at runtime. Pages and images render
  without them, but some animations may not run if that CDN goes away.
