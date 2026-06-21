# Deploying Atlas Communities Standards to AWS Lightsail

This sets up the app on an Ubuntu Lightsail instance with **gunicorn + nginx +
systemd**, and a **GitHub Actions** workflow so that every `git push` to `main`
automatically deploys to the server.

Your workflow once this is set up:

```
edit  →  git commit  →  git push  →  (GitHub Actions)  →  live on the server
```

We start on **HTTP via the instance IP**. Adding a domain + HTTPS is a short
follow-up (see the last section).

---

## What's in the repo for deployment

| File | Purpose |
|------|---------|
| `deploy/atlas.service` | systemd unit that runs gunicorn |
| `deploy/nginx-atlas.conf` | nginx reverse-proxy config |
| `deploy/deploy.sh` | pull + install + restart (run on the server) |
| `.github/workflows/deploy.yml` | GitHub Action: SSH in and run `deploy.sh` on push |
| `.env.example` | the environment variables the app needs |
| `app_mantenimiento/data/seeds/` | seed data used to initialize a fresh server |

**Data safety:** live data (`data/*.json`, uploaded photos/avatars) is
**git-ignored**, so deploys never overwrite it. On a brand-new server the app
copies `data/seeds/*` into place on first run; after that your live data is
untouched by every future deploy.

---

## One-time server setup

### 1. Create the instance
- Lightsail → **Create instance** → Linux/Unix → **Ubuntu 22.04 LTS**.
- Smallest plan is fine to start ($5–$10/mo).
- After it boots: **Networking → IPv4 Firewall** → make sure **HTTP (80)** is
  allowed. (SSH 22 is allowed by default.)
- Note the instance's **public IP**.

### 2. Connect and install packages
SSH in (Lightsail browser SSH, or your terminal), then:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx git
```

### 3. Clone the repo and create a virtualenv
```bash
cd /home/ubuntu
git clone https://github.com/siregabriel/communitiesQualifier.git CommunitiesQualifier
cd CommunitiesQualifier
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Set the secret key (environment file)
```bash
sudo mkdir -p /etc/atlas
# generate a strong key and write the env file:
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" | sudo tee /etc/atlas/atlas.env
echo "FLASK_DEBUG=0" | sudo tee -a /etc/atlas/atlas.env
sudo chmod 600 /etc/atlas/atlas.env
```

### 5. Install the systemd service
```bash
sudo cp /home/ubuntu/CommunitiesQualifier/deploy/atlas.service /etc/systemd/system/atlas.service
sudo systemctl daemon-reload
sudo systemctl enable --now atlas
sudo systemctl status atlas        # should be "active (running)"
```

### 6. Configure nginx
```bash
sudo cp /home/ubuntu/CommunitiesQualifier/deploy/nginx-atlas.conf /etc/nginx/sites-available/atlas
sudo ln -sf /etc/nginx/sites-available/atlas /etc/nginx/sites-enabled/atlas
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

**Let nginx read the static files.** nginx runs as `www-data` and needs to
traverse the home directory to serve `/static/`. Without this, pages load but
images/CSS 404:
```bash
chmod o+x /home/ubuntu
```

Now visit `http://YOUR_INSTANCE_IP/` — the login page should load.

### 7. Allow the deploy script to restart the service without a password
`deploy.sh` runs `sudo systemctl restart atlas`. Allow just that command for the
`ubuntu` user:

```bash
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart atlas" | sudo tee /etc/sudoers.d/atlas-deploy
sudo chmod 440 /etc/sudoers.d/atlas-deploy
chmod +x /home/ubuntu/CommunitiesQualifier/deploy/deploy.sh
```

---

## Wire up auto-deploy (GitHub Actions)

### 1. Create an SSH key the Action will use
On your **local machine**:
```bash
ssh-keygen -t ed25519 -f atlas_deploy_key -N ""    # creates atlas_deploy_key (private) + atlas_deploy_key.pub
```
Add the **public** key to the server:
```bash
# copy the contents of atlas_deploy_key.pub, then on the server:
echo "PASTE_PUBLIC_KEY_HERE" >> /home/ubuntu/.ssh/authorized_keys
```

### 2. Add GitHub repository secrets
GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `LIGHTSAIL_HOST` | the instance's public IP |
| `LIGHTSAIL_USER` | `ubuntu` |
| `LIGHTSAIL_SSH_KEY` | the **private** key contents (the whole `atlas_deploy_key` file) |

### 3. Done
`.github/workflows/deploy.yml` is already in the repo. From now on, every push to
`main` runs the Action, which SSHes in and runs `deploy.sh` (fetch → reset to
`origin/main` → `pip install` → restart). Watch it under the repo's **Actions**
tab. You can also trigger it manually there ("Run workflow").

---

## Your day-to-day workflow

```bash
# make changes locally...
git add -A
git commit -m "your change"
git push origin main
# GitHub Actions deploys automatically; live in ~30–60s
```

If you ever need to deploy by hand on the server:
```bash
bash /home/ubuntu/CommunitiesQualifier/deploy/deploy.sh
```

Useful checks on the server:
```bash
sudo systemctl status atlas         # is it running?
sudo journalctl -u atlas -n 50      # recent app logs
```

---

## First-login accounts

These ship as seed defaults (change passwords after first login — change-password
is built into the profile, and it stores a secure hash):

- Admin: `admin` / `admin123`
- Community users: `user1`–`user39` / `test123`
- Regionals: `firstname.lastname` (e.g. `keith.martin`) / `atlas123`

---

## Later: add a domain + HTTPS

1. Point an A record for your domain at the instance IP.
2. In `deploy/nginx-atlas.conf`, set `server_name yourdomain.com;`, copy it over,
   reload nginx.
3. Install Certbot and get a free certificate:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```
   Certbot edits nginx to serve HTTPS and auto-renews.

> Until HTTPS is in place, the site runs over plain HTTP — fine for testing, but
> add the certificate before real users log in with real passwords.

---

## Notes / gotchas

- **Branch name:** the workflow and `deploy.sh` assume `main`. If your default
  branch is `master`, update both.
- **Data backups:** live data is JSON files under `app_mantenimiento/data/` plus
  uploads under `app_mantenimiento/static/{uploads,avatars,community_photos}`.
  Back these up periodically (e.g. a nightly `tar` to S3 or a Lightsail snapshot).
- **Multiple workers:** gunicorn runs 3 workers; the data layer reloads-from-disk
  before writes and writes atomically, so workers stay consistent.
- **Scaling later:** when JSON files become a bottleneck, the storage layer is
  isolated in `services/` and can be swapped for SQLite/Postgres without touching
  the routes.
