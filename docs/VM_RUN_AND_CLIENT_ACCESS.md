# Azure VM: run, share the site, shut down, and deploy updates

> **Start here:** [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) is the main beginner-friendly guide (full command list).  
> This file is the **day-2 operations cheat sheet** (client URL, start/stop VM, quick updates).

Use this after the server is set up (nginx, NSG port **80**, `dist/` build, home-directory permissions for nginx — see `docs/DEPLOYMENT.md` Part D and `docs/DEPLOY_AZURE_VM.md` for first-time deployment).

---

## 1. Exact URL to send clients

Everyone opens the site in a browser using **HTTP on port 80** (no port in the address bar):

```text
http://YOUR_PUBLIC_IP/
```

**Example:** if Azure shows **Primary NIC public IP** = `68.210.227.68`, send:

```text
http://68.210.227.68/
```

- Use **`http://`**, not `https://`, unless you have configured TLS.
- **Do not** send `:8000` when nginx is in front; the API is reached as **`/api/...`** on the same host.
- **Bookmark / save this IP** from **Azure Portal → your VM → Overview → Primary NIC public IP** each time you start the VM. If the public IP is **dynamic**, it **may change** after the VM is stopped and started again (unless you attached a **static** public IP). Always confirm in the portal before sharing the link.

---

## 2. Turn everything on (so others can use the site)

### 2.1 Start the VM (Azure)

**Portal:** Virtual machines → select your VM → **Start**. Wait until **Status** is **Running**.

**Azure CLI (from your PC)** — this repo’s VM: resource group **`myVmRG`**, VM name **`testvm-austriaeast`**:

```powershell
az vm start --resource-group myVmRG --name testvm-austriaeast
```

### 2.2 SSH into the VM

```powershell
ssh -i ""D:\Dev\agrigraph1.pem"" azureuser@68.210.227.68
```

### 2.3 Start nginx (usually already running)

```bash
sudo systemctl status nginx
```

If it is not active:

```bash
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 2.4 Start the backend (FastAPI / uvicorn)

The API must be listening on **`127.0.0.1:8000`** so nginx can proxy **`/api`** to it.

**Manual (good for testing — stops when you close SSH or press Ctrl+C):**

```bash
cd ~/AgriGraph
source backend/.venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Leave this terminal open, **or** use **`tmux`** / **`screen`**, **or** install the **systemd** service from `docs/DEPLOY_AZURE_VM.md` (“Part 6”) so the API survives logout.

**Quick check on the VM:**

```bash
curl -s http://127.0.0.1:8000/health
```

Expect: `{"status":"ok"}`

### 2.5 Confirm from your PC

```powershell
Test-NetConnection -ComputerName YOUR_PUBLIC_IP -Port 80
```

`TcpTestSucceeded` should be **True** (Azure NSG must **Allow** inbound **TCP 80**).

Then open **`http://YOUR_PUBLIC_IP/`** in a browser.

---

## 3. Turn everything off (save money, stop access)

### 3.1 Stop the backend

If uvicorn is running in the foreground: **Ctrl+C**.

If you use systemd:

```bash
sudo systemctl stop agrigraph-api
```

(Only if you created that unit; name may differ.)

### 3.2 Optional: stop nginx

Usually unnecessary if the VM is being deallocated; nginx alone without uvicorn will serve static files but **API** calls will fail.

```bash
sudo systemctl stop nginx
```

### 3.3 Stop (deallocate) the VM — billing stops for compute

**Portal:** VM → **Stop** (this should **deallocate** the VM, not only “guest OS shutdown” — in Azure, use **Stop** from the VM blade so it releases compute).

**CLI:**

```powershell
az vm deallocate --resource-group myVmRG --name testvm-austriaeast
```

**Note:** While deallocated, **no one** can reach the website. When you start the VM again, repeat section 2 (and confirm **public IP** if it changed).

---

## 4. After you change the project — update the VM

Work on your PC, commit, push. Then on the VM:

### 4.1 Pull latest code

```bash
cd ~/AgriGraph
git pull
```

### 4.2 Backend dependencies (only if `requirements.txt` changed)

```bash
cd ~/AgriGraph/backend
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 4.3 Frontend (only if `frontend/` changed)

If you changed **`frontend/src/config.js`** (for example API base URL), or any React/CSS assets:

```bash
cd ~/AgriGraph/frontend
npm install
npm run build
```

Production builds use **`API_BASE_URL = "/api"`** when served behind nginx (same origin).

Reload nginx if you only changed static files (optional; often not required):

```bash
sudo systemctl reload nginx
```

### 4.4 Restart the API

Restart uvicorn (however you run it: foreground, **tmux**, or **systemd**):

```bash
# example: systemd
sudo systemctl restart agrigraph-api
```

If artifacts / pipeline inputs changed, the next startup may reload data; see `backend/main.py` lifespan behavior.

### 4.5 If nginx permissions break again

If you moved the project or recreated `dist/` under home, nginx (`www-data`) may need traverse permission on your home path again — see the troubleshooting section in `docs/DEPLOY_AZURE_VM.md` (`chmod o+x` on `/home/azureuser` and path to `dist/`).

---

## 5. Short checklist

| Goal | Action |
|------|--------|
| **Share link** | Send `http://<Primary NIC public IP>/` from Azure Overview |
| **Go live** | Start VM → SSH → start uvicorn on `127.0.0.1:8000` → nginx running → NSG allows **TCP 80** |
| **Go offline** | Stop uvicorn → **Stop/Deallocate** VM |
| **Ship code updates** | `git pull` → `pip install -r` if needed → `npm run build` if frontend changed → restart API |

---

## Related

- First-time server setup: **`docs/DEPLOY_AZURE_VM.md`**
