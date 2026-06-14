# AgriGraph — Complete deployment guide (beginner-friendly)

This is the **main walkthrough** for putting AgriGraph on your Azure VM.

**Reference docs (optional):**

- [`docs/DEPLOY_AZURE_VM.md`](DEPLOY_AZURE_VM.md) — extended nginx/systemd notes
- [`docs/VM_RUN_AND_CLIENT_ACCESS.md`](VM_RUN_AND_CLIENT_ACCESS.md) — day-2 cheat sheet

---

## Quick start — read this first

### After first-time setup is done (normal daily use)

You should only need to do **one thing**:

1. Open **Azure Portal** → **Virtual machines** → **testvm-austriaeast** → click **Start**
2. Wait **2–3 minutes** for the VM to boot (nginx, Docker/Postgres, and the API start automatically)
3. Open in a browser: `http://YOUR_PUBLIC_IP/`

**No SSH required** for normal use.

| Action | Where | How often |
|--------|--------|-----------|
| **Start the site** | Azure Portal (or `az vm start`) | Every time you want the site live |
| **Stop billing (compute)** | Azure Portal → **Stop** (deallocate) | When you are done for the day/week |
| **First-time VM setup** | SSH into VM | **Once** (Part D below) |
| **Push code to GitHub** | Your Windows PC | First time + whenever you change code |
| **Deploy updates on VM** | SSH into VM | **Only when** you pushed new code (Part G) |

### Command legend (used throughout this doc)

Every command block is labeled:

| Label | Meaning |
|-------|---------|
| **FIRST TIME ONLY** | Run once during initial setup. Skip on later days. |
| **EVERY TIME (normal use)** | What you do to turn the site on/off without SSH. |
| **WHEN UPDATING CODE** | Only after you change the project and push to GitHub. |
| **OPTIONAL / DEBUG** | Troubleshooting or verification — not part of daily routine. |

---

## Part A — What you are building

```mermaid
flowchart LR
  client[Browser] --> nginx[Nginx_port_80]
  nginx --> dist[React_dist]
  nginx --> api[FastAPI_127_0_0_1_8000]
  api --> pg[Postgres_Docker_5432]
```

| Piece | Role |
|-------|------|
| **Browser** | User opens `http://YOUR_PUBLIC_IP/` |
| **nginx (port 80)** | Serves React `dist/` and proxies `/api/*` to the backend |
| **FastAPI (127.0.0.1:8000)** | ML API, auth, saved simulations |
| **Postgres (Docker)** | Users and saved simulations |

**Your Azure VM:**

| Setting | Value |
|---------|--------|
| Resource group | `myVmRG` |
| VM name | `testvm-austriaeast` |
| Linux user | `azureuser` |
| SSH key (example) | `D:\Dev\agrigraph1.pem` |

**Client URL:** `http://YOUR_PUBLIC_IP/`  
(Find IP: Azure Portal → VM → **Overview** → **Primary NIC public IP**)

**Tip:** Assign a **Static** public IP in Azure if you do not want the address to change after Stop/Start. If the IP changes, update `FRONTEND_ORIGIN` in `~/AgriGraph/.env` once (see Part D.7).

---

## Part B — Prerequisites

**FIRST TIME ONLY** — before Part C or D:

- [ ] Windows PC with the project folder
- [ ] **Git** — [https://git-scm.com/download/win](https://git-scm.com/download/win)
- [ ] **GitHub** account
- [ ] **Azure VM** (Ubuntu 22.04) + SSH key (`.pem`)
- [ ] Azure NSG: inbound **TCP 22** (SSH) and **TCP 80** (website)

---

## Part C — Push this project to GitHub (Windows)

### FIRST TIME ONLY — connect repo to GitHub

**C.1** Open the project:

```powershell
cd "C:\Users\Akram kimou\Desktop\AgriGraph"
```

**C.2** Check status:

```powershell
git status
```

**C.3** Create an empty repo on GitHub: [https://github.com/new](https://github.com/new) — no README if code already exists locally.

**C.4** Connect remote (skip if `git remote -v` already shows `origin`):

```powershell
git init
```

```powershell
git remote add origin https://github.com/YOUR_USER/AgriGraph.git
```

**C.5** Never commit: `.env`, `.venv/`, `node_modules/`, `*.pem`, secrets.

---

### WHEN UPDATING CODE — commit and push (same every time you change the project)

```powershell
cd "C:\Users\Akram kimou\Desktop\AgriGraph"
```

```powershell
git status
```

```powershell
git add .
```

```powershell
git commit -m "Describe your change"
```

```powershell
git push
```

**FIRST TIME ONLY** for push (if branch not set yet):

```powershell
git branch -M main
```

```powershell
git push -u origin main
```

---

## Part D — First-time setup on the Azure VM (do this once)

Complete **all** of Part D **once**. After D.13 (auto-start), you should not need SSH for daily use.

You may SSH in for D.1–D.2, or start the VM from the portal first.

### D.1 FIRST TIME ONLY — Start VM (Azure Portal or CLI)

**Option A — Azure Portal (recommended):**  
Virtual machines → **testvm-austriaeast** → **Start** → wait until **Running**.

**Option B — PowerShell on PC:**

```powershell
az vm start --resource-group myVmRG --name testvm-austriaeast
```

---

### D.2 FIRST TIME ONLY — SSH into the VM

```powershell
ssh -i "D:\Dev\agrigraph1.pem" azureuser@YOUR_PUBLIC_IP
```

---

### D.3 FIRST TIME ONLY — Clone the project

```bash
cd ~
```

```bash
git clone https://github.com/YOUR_USER/AgriGraph.git AgriGraph
```

```bash
cd ~/AgriGraph
```

---

### D.4 FIRST TIME ONLY — Install system packages

```bash
sudo apt update
```

```bash
sudo apt install -y git python3 python3-venv python3-pip nginx docker.io docker-compose-v2
```

```bash
sudo usermod -aG docker azureuser
```

Log out of SSH and log back in once so the `docker` group applies:

```bash
exit
```

Then SSH in again (D.2), then continue D.5.

---

### D.5 FIRST TIME ONLY — Install Node.js 20

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
```

```bash
sudo apt install -y nodejs
```

---

### D.6 FIRST TIME ONLY — Create Postgres container (persists data)

```bash
cd ~/AgriGraph
```

```bash
docker compose up -d db
```

Postgres uses `restart: unless-stopped` in `docker-compose.yml` — it will come back when Docker starts after a reboot.

**OPTIONAL / DEBUG:**

```bash
docker ps
```

---

### D.7 FIRST TIME ONLY — Create `.env`

```bash
cd ~/AgriGraph
```

```bash
cp .env.example .env
```

```bash
nano .env
```

Example for HTTP:

```env
DATABASE_URL=postgresql+psycopg://agrigraph:agrigraph@localhost:5432/agrigraph
JWT_SECRET=PASTE_A_LONG_RANDOM_SECRET_HERE
JWT_EXPIRE_MINUTES=10080
FRONTEND_ORIGIN=http://YOUR_PUBLIC_IP
COOKIE_SECURE=false
```

Generate secret:

```bash
openssl rand -hex 32
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

---

### D.8 FIRST TIME ONLY — Python virtual environment

```bash
cd ~/AgriGraph
```

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install --upgrade pip
```

```bash
pip install -r backend/requirements.txt
```

**OPTIONAL / DEBUG** — run pipeline manually if models missing:

```bash
python -m backend.pipeline.run_pipeline
```

```bash
deactivate
```

---

### D.9 FIRST TIME ONLY — Build frontend for production

```bash
nano ~/AgriGraph/frontend/src/config.js
```

Set:

```js
export const API_BASE_URL = "/api";
```

```bash
cd ~/AgriGraph/frontend
```

```bash
npm install
```

```bash
npm run build
```

```bash
ls ~/AgriGraph/frontend/dist
```

---

### D.10 FIRST TIME ONLY — Configure nginx

```bash
sudo nano /etc/nginx/sites-available/agrigraph
```

Paste:

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

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/agrigraph /etc/nginx/sites-enabled/agrigraph
```

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

```bash
sudo nginx -t
```

```bash
chmod o+x /home/azureuser
```

```bash
chmod -R o+rX /home/azureuser/AgriGraph/frontend/dist
```

---

### D.11 FIRST TIME ONLY — Create systemd service for the API

```bash
sudo nano /etc/systemd/system/agrigraph-api.service
```

Paste:

```ini
[Unit]
Description=AgriGraph FastAPI (uvicorn)
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
User=azureuser
Group=azureuser
WorkingDirectory=/home/azureuser/AgriGraph
EnvironmentFile=/home/azureuser/AgriGraph/.env
Environment="PATH=/home/azureuser/AgriGraph/.venv/bin"
ExecStartPre=/usr/bin/docker compose -f /home/azureuser/AgriGraph/docker-compose.yml up -d db
ExecStart=/home/azureuser/AgriGraph/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`ExecStartPre` ensures Postgres is up before the API starts (including after reboot).

---

### D.12 FIRST TIME ONLY — Enable auto-start on boot (critical for “portal only” daily use)

These commands make **Docker, nginx, Postgres, and the API** start automatically when the VM boots. You only **Start the VM** in Azure afterward.

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl enable docker
```

```bash
sudo systemctl enable nginx
```

```bash
sudo systemctl enable agrigraph-api
```

Start everything now (first time):

```bash
sudo systemctl start docker
```

```bash
cd ~/AgriGraph && docker compose up -d db
```

```bash
sudo systemctl start nginx
```

```bash
sudo systemctl start agrigraph-api
```

Verify services are **enabled** (will show `enabled`):

```bash
systemctl is-enabled docker nginx agrigraph-api
```

**OPTIONAL / DEBUG** — check status:

```bash
sudo systemctl status nginx
```

```bash
sudo systemctl status agrigraph-api
```

```bash
docker ps
```

---

### D.13 FIRST TIME ONLY — Verify the site works

**On VM:**

```bash
curl -s http://127.0.0.1:8000/health
```

```bash
curl -s http://127.0.0.1/health
```

**On your PC browser:** `http://YOUR_PUBLIC_IP/` — sign up, sign in, load Atlas, save a simulation.

**You are done with first-time setup.** From now on, use Part E only for daily use.

---

## Part E — Every time you want the site live (no SSH)

### EVERY TIME — Turn the site ON

1. **Azure Portal** → Virtual machines → **testvm-austriaeast** → **Start**
2. Wait **2–3 minutes** (boot + auto-start services)
3. Open **`http://YOUR_PUBLIC_IP/`** in a browser

That is all for normal operation.

**Alternative (PowerShell on PC):**

```powershell
az vm start --resource-group myVmRG --name testvm-austriaeast
```

---

### EVERY TIME — Turn the site OFF (stop compute billing)

1. **Azure Portal** → VM → **Stop** (deallocate)
2. No SSH commands needed

**Alternative (PowerShell):**

```powershell
az vm deallocate --resource-group myVmRG --name testvm-austriaeast
```

While deallocated, the site is unreachable and you are not billed for VM compute. Disk and Postgres data are kept.

---

### OPTIONAL / DEBUG — If the site does not load after Start

Wait 3–5 minutes, then SSH in and check:

```bash
systemctl is-active nginx agrigraph-api docker
```

```bash
docker ps
```

```bash
curl -s http://127.0.0.1/health
```

If a service failed:

```bash
sudo systemctl restart docker
```

```bash
cd ~/AgriGraph && docker compose up -d db
```

```bash
sudo systemctl restart agrigraph-api
```

```bash
sudo systemctl restart nginx
```

---

## Part F — When updating code (not every day)

Only when you changed the project on your PC and pushed to GitHub.

### F.1 WHEN UPDATING CODE — On Windows PC

See Part C “WHEN UPDATING CODE” (`git add`, `commit`, `push`).

### F.2 WHEN UPDATING CODE — On the VM (SSH required)

Start VM if it is stopped, then SSH in.

```bash
cd ~/AgriGraph
```

```bash
git pull
```

**Only if `backend/requirements.txt` changed:**

```bash
source .venv/bin/activate
```

```bash
pip install -r backend/requirements.txt
```

```bash
deactivate
```

**Only if `frontend/` changed:**

```bash
grep API_BASE_URL ~/AgriGraph/frontend/src/config.js
```

Must show `"/api"`. Then:

```bash
cd ~/AgriGraph/frontend
```

```bash
npm install
```

```bash
npm run build
```

**Only if ML pipeline / models / CSVs changed:**

```bash
cd ~/AgriGraph
```

```bash
source .venv/bin/activate
```

```bash
python -m backend.pipeline.run_pipeline
```

```bash
deactivate
```

**Always after VM code updates:**

```bash
sudo systemctl restart agrigraph-api
```

**OPTIONAL:**

```bash
sudo systemctl reload nginx
```

Smoke test: `http://YOUR_PUBLIC_IP/` — login, load data, save simulation.

---

## Part G — Auth and saved simulations

| Topic | Detail |
|-------|--------|
| Login | Email + password (bcrypt hash in Postgres) |
| Session | httpOnly cookie `agrigraph_access_token` |
| CORS | `FRONTEND_ORIGIN` in `.env` must match browser URL exactly |
| DB tables | Created on API startup via `init_db()` |
| Saved sims | JSONB in `saved_simulations` |

---

## Part H — Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Site down after portal Start | Wait 3 min; see Part E optional debug; `systemctl is-enabled docker nginx agrigraph-api` |
| Blank page | `ls ~/AgriGraph/frontend/dist`; rebuild frontend (Part F) |
| 502 on `/api` | `sudo systemctl status agrigraph-api` |
| Login OK but 401 on data | `FRONTEND_ORIGIN` in `.env`; frontend built with `"/api"` |
| DB error | `docker ps`; `docker compose up -d db` |
| IP changed after deallocate | Update `.env` `FRONTEND_ORIGIN`; `sudo systemctl restart agrigraph-api` |
| nginx permission denied | `chmod o+x /home/azureuser`; `chmod -R o+rX .../dist` |

```bash
journalctl -u agrigraph-api -n 100 --no-pager
```

---

## Part I — Local development vs production

| | Local PC (dev) | Azure VM (production) |
|--|----------------|------------------------|
| Frontend | `npm run dev` :5173 | nginx `dist/` :80 |
| `config.js` | `http://localhost:8000/api` | `"/api"` before build |
| Backend | manual uvicorn | systemd `agrigraph-api` (auto on boot) |
| Postgres | `docker compose up -d db` | same (auto on boot) |
| Daily use | start dev servers | **Azure Portal → Start VM only** |

---

## Part J — Command cheat sheet

| When | What to do |
|------|------------|
| **First time ever** | Part C (GitHub) + Part D (full VM setup through D.13) |
| **Every day — site on** | Azure Portal → **Start** VM → open `http://YOUR_PUBLIC_IP/` |
| **Every day — site off** | Azure Portal → **Stop** (deallocate) VM |
| **After code changes** | PC: `git push` → VM: Part F |
| **Something broken** | Part E optional debug + Part H |

---

## Related documentation

- [`docs/DEPLOY_AZURE_VM.md`](DEPLOY_AZURE_VM.md)
- [`docs/VM_RUN_AND_CLIENT_ACCESS.md`](VM_RUN_AND_CLIENT_ACCESS.md)
