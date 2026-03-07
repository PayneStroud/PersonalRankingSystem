# Personal Ranking Web App (iPhone-ready)

## Quick Run On Your Mac

1. Start a local server:

```bash
cd "/Users/paynestroud/Documents/personal-ranking-web"
python3 -m http.server 8080 --bind 0.0.0.0
```

2. On your iPhone (same Wi-Fi), open:

`http://<your-mac-local-ip>:8080`

3. In Safari, tap Share -> **Add to Home Screen**.

## Deploy For Easy Sharing

Use GitHub Pages, Netlify, or Vercel and publish the folder as static files.

After deploy, open the URL on iPhone Safari and Add to Home Screen.

## Files

- `index.html` - UI shell
- `app.js` - ranking logic + interactions
- `styles.css` - mobile-first styling
- `manifest.webmanifest` - PWA metadata
- `sw.js` - offline cache
- `icon-192.png`, `icon-512.png` - app icons
