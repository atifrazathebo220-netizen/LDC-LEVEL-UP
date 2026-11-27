# LDC Cloud API Caller

The server makes the API calls itself, so you can close the page after pressing Start.

## Files
- `server.py` – Flask server that runs the jobs
- `index.html` – the page (served by the server at `/`)
- `requirements.txt`, `Procfile` – for hosting

## Host on Render (free)
1. New → Web Service → connect this GitHub repo.
2. Root Directory: `cloud`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn server:app --workers 1 --threads 8 --bind 0.0.0.0:$PORT`
5. (Optional) Environment → add `ADMIN_KEY` = your password.
6. Open `https://<your-app>.onrender.com`

Keep `--workers 1`: jobs are stored in memory of one process.

## Run locally / Termux / VPS
```
pip install -r requirements.txt
python server.py        # open http://localhost:8000
```

## HTML on a different host
You can upload `index.html` anywhere (GitHub Pages, Netlify…). Open it, go to
"Server settings" and put your server URL, e.g. `https://<your-app>.onrender.com`.
