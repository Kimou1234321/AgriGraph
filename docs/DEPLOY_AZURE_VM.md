# Deploy AgriGraph on an Ubuntu Azure VM (beginner walkthrough)

This guide assumes:

- **VM OS:** Ubuntu 22.04 (e.g. `azureuser@...`)
- **Python:** 3.10 is fine (`python3 --version` → 3.10.x)
- You will **not** commit `.venv`, `node_modules`, or secrets to Git.

---

## Why “localhost” matters (read once)

The file `frontend/src/config.js` contains:

```js
export const API_BASE_URL = "http://localhost:8000/api";
```

- **`npm run dev`** (port 5173) uses the Vite proxy in `vite.config.js`; your browser still loads JS that calls `localhost:8000` for API requests in many cases.
- When your **client** opens your site using the VM’s **public IP**, their browser’s “localhost” is **their own PC**, not your server. So you **must** either:
  - **A (recommended):** Serve the built site and the API **under the same website** (e.g. nginx on port **80**: `/` = webpage, `/api` = FastAPI), and set `API_BASE_URL` to **`"/api"`** before building; or  
  - **B:** Set `API_BASE_URL` to `http://YOUR_PUBLIC_IP:8000/api` **and** relax backend CORS for your frontend origin (different ports = different origins).

Below uses **A** so the browser only talks to **one origin** (`http://YOUR_IP`) and you avoid CORS headaches.

**No pipeline/math/API route logic is changed** — only deployment-related URL configuration and server commands.

---

## Part 1 — Put the project on the VM

### Option 1a: GitHub (recommended)

**On your Windows PC (once):**

1. Create a repo on GitHub (empty or with this code).
2. In your project folder:

   ```powershell
   cd C:\Users\Akram kimou\Desktop\AgriGraph
   git status
   ```

3. If Git is not initialized: `git init`, add remote, etc.
4. Commit and push (do **not** add `.venv` or `node_modules`; `.gitignore` should already skip them).

**On the VM:**

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone https://github.com/YOUR_USER/YOUR_REPO.git AgriGraph
cd ~/AgriGraph
```

Use **HTTPS** URL from GitHub, or SSH if you’ve added a VM key to GitHub.

### Option 1b: No GitHub — copy the folder with `scp` (from Windows PowerShell)

Replace `azureuser` and the IP with yours.

```powershell
cd "C:\Users\Akram kimou\Desktop"
scp -r -i "D:\Dev\agrigraph1.pem" AgriGraph azureuser@YOUR_PUBLIC_IP:/home/azureuser/AgriGraph
```

---

## Part 2 — Backend (Python venv + install)

```bash
cd ~/AgriGraph/backend

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

If `pip install` fails (e.g. torch wheel), read the error; on a small VM, installs can take several minutes.

**Run pipeline/data:** On first API start, `backend/main.py` may run the pipeline if model weights / forecast CSV are missing. Ensure `backend/data/` and artifacts match what you use locally, or let the pipeline generate them (can be slow on a small VM).

**Deactivate** when done testing the venv (optional): `deactivate`

---

## Part 3 — Frontend: `npm install` and `npm run build`

You can build **on the VM** or **on your PC** and upload only `frontend/dist/`.

### 3a — Build on the VM

Install Node **20 LTS** (example using NodeSource):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
```

**Set the API base URL for production (same origin behind nginx):**

```bash
cd ~/AgriGraph/frontend
nano src/config.js
```

Change the line to **exactly** (quotes matter):

```js
export const API_BASE_URL = "/api";
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

Install dependencies and build:

```bash
cd ~/AgriGraph/frontend
npm install
npm run build
```

Expected result: folder **`~/AgriGraph/frontend/dist/`** with `index.html` and an `assets/` directory.

If the VM runs out of memory during `npm run build`, build on your PC (next section) or add swap.

### 3b — Build on your Windows PC, upload only `dist/`

**On Windows** (after installing Node if needed):

```powershell
cd C:\Users\Akram kimou\Desktop\AgriGraph\frontend
```

Edit `src\config.js` to use `"/api"` as above, then:

```powershell
npm install
npm run build
```

Upload **only** the contents of `dist` to the VM (example):

```powershell
scp -r -i "D:\Dev\agrigraph1.pem" dist\* azureuser@YOUR_PUBLIC_IP:/home/azureuser/AgriGraph/frontend/dist/
```

On the VM, check:

```bash
ls ~/AgriGraph/frontend/dist
# should show index.html and assets/
```

---

## Part 4 — nginx: one site for the page + `/api`

Install nginx:

```bash
sudo apt install -y nginx
```

Create a site file:

```bash
sudo nano /etc/nginx/sites-available/agrigraph
```

Paste (adjust `server_name` if you have a domain later):

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /home/azureuser/AgriGraph/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Enable it and remove default if it conflicts:

```bash
sudo ln -sf /etc/nginx/sites-available/agrigraph /etc/nginx/sites-enabled/agrigraph
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

**Azure NSG:** Allow inbound **TCP 80** (and **22** for SSH) to your client or for testing.

---

## Part 5 — Run the API (FastAPI / uvicorn)

The app module is `backend.main:app`. Run from the **repository root** so imports like `from backend.api...` work.

**Manual test (SSH session):**

```bash
cd ~/AgriGraph
source backend/.venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Leave it running, then on your PC open a browser:

- `http://YOUR_PUBLIC_IP/` → React app  
- `http://YOUR_PUBLIC_IP/health` might 404 at nginx if not proxied — API health is at **`http://YOUR_PUBLIC_IP/api/...`** through nginx, or directly if you expose 8000.

Actually **health** in `main.py` is `@app.get("/health")` — **not** under `/api`. So nginx only proxies `/api/`. Health check direct:

```bash
curl -s http://127.0.0.1:8000/health
```

From outside, either temporarily open port 8000 or add a small `location /health` in nginx proxying to uvicorn. For a prototype, testing with `curl` on the VM is enough.

---

## Part 6 — Keep the API running after you disconnect (systemd)

```bash
sudo nano /etc/systemd/system/agrigraph-api.service
```

Paste:

```ini
[Unit]
Description=AgriGraph FastAPI (uvicorn)
After=network.target

[Service]
User=azureuser
Group=azureuser
WorkingDirectory=/home/azureuser/AgriGraph
Environment="PATH=/home/azureuser/AgriGraph/backend/.venv/bin"
ExecStart=/home/azureuser/AgriGraph/backend/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable agrigraph-api
sudo systemctl start agrigraph-api
sudo systemctl status agrigraph-api
```

Logs:

```bash
journalctl -u agrigraph-api -f
```

---

## Quick checklist

| Step | Command / action |
|------|------------------|
| Code on VM | `git clone` or `scp` |
| Backend venv | `python3 -m venv .venv` → `pip install -r requirements.txt` |
| Production API URL in JS | `src/config.js` → `API_BASE_URL = "/api"` **before** `npm run build` |
| Build frontend | `npm install` → `npm run build` → `frontend/dist/` exists |
| nginx | Install, configure site, open port **80** |
| API | `uvicorn backend.main:app --host 127.0.0.1 --port 8000` (systemd for persistence) |
| Azure NSG | TCP **22**, **80** |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Blank page or 404 on `/` | `dist/` empty or wrong path in `root` |
| API calls fail / network error | Forgot to set `API_BASE_URL` to `/api` before build, or nginx not proxying `/api/` |
| 502 Bad Gateway from nginx | uvicorn not running or wrong port |
| CORS errors in browser | Usually fixed by same-origin (`/api`) + nginx; don’t mix `http://IP:8000` in JS if nginx serves on 80 |
| Out of memory | Build frontend on PC; add swap on VM |

---

## Reverting `config.js` for local dev

When developing on your PC again, set:

```js
export const API_BASE_URL = "http://localhost:8000/api";
```

Or keep two branches / env-based config later — not required for a first deploy.
