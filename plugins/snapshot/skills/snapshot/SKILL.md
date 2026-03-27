---
name: snapshot
description: "Docker Snapshot System - Time Machine per app PHP"
user-invocable: true
argument-hint: "<app-path> [--name slug] [--deploy local|cloudrun|none] [--framework laravel|wordpress|symfony|php]"
requires:
  capabilities: [docker]
---

# /snapshot - Docker Snapshot System

**Crea snapshot "frozen in time" di applicazioni PHP complete (codice + database) e deployale su Cloud Run o locale.**

Perfect per: demo clienti, testing, preview, time-machine debug.

## Usage

```bash
/snapshot /var/www/myapp --name myapp --deploy local
/snapshot ssh://user@server:/var/www/app --name app --deploy cloudrun
/snapshot cloudways://app-id --name app --db-backup latest
/snapshot ./app --name test --build-only
```

## Workflow - 5 Steps

### 1. DUMP - Database Backup
Da SSH, Cloudways API, o locale → `db-dump.sql.gz`

### 2. PREPARE - Directory Setup
```bash
mkdir -p snapshot-workspace/app
cp -r <APP_PATH>/* snapshot-workspace/app/
cp db-dump.sql.gz snapshot-workspace/
```

### 3. BUILD - Docker Image
Framework detection automatico:
- **Laravel**: artisan presente
- **WordPress**: wp-config.php presente
- **Symfony**: bin/console presente
- **Generic PHP**: index.php presente

Build immagine Docker multi-stage con PHP-FPM + Nginx + MySQL embedded.

### 4. PUSH - Container Registry (solo cloudrun)
Tag + push to Google Container Registry.

### 5. DEPLOY - Target Environment

**Cloud Run:**
```bash
gcloud run deploy <NAME>-snapshot \
  --image gcr.io/PROJECT_ID/<NAME>-snapshot:latest \
  --memory 2Gi --timeout 300s --allow-unauthenticated
```

**Local:**
- Run container su porta disponibile
- Configure nginx reverse proxy
- Get/renew SSL certificate (Let's Encrypt)
- Configure Cloudflare DNS

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--name` | Snapshot name (slug) | Auto from path |
| `--deploy` | `local`, `cloudrun`, `none` | `local` |
| `--db-source` | `ssh`, `cloudways`, `local`, `file` | Auto-detect |
| `--db-file` | Path to existing db-dump.sql.gz | Auto DUMP |
| `--framework` | Force: `laravel`, `wordpress`, `symfony`, `php` | Auto-detect |
| `--memory` | Cloud Run memory | `2Gi` |
| `--region` | Cloud Run region | `europe-west1` |
| `--port` | Container port (local) | Auto (8081+) |
| `--domain` | Custom domain (local) | `dockerN.giobi.com` |
| `--build-only` | Only build, skip deploy | `false` |

## Implementation

Location: `tools/snapshot/`

## Cost Estimate

### Cloud Run
~$0.11/mese per snapshot. 10 snapshot attivi → ~$1/mese.

### Local (docker1.giobi.com)
$0 (usa server esistente). Limite: ~10 container simultanei (RAM).

## Troubleshooting

- **Cold Start Timeout**: aumenta `--timeout` a 600s
- **MySQL Auth Error**: verifica entrypoint crei user 'webapp'
- **Redirect Loop**: verifica TrustProxies middleware + X-Forwarded-Proto
- **Port Already in Use**: `docker ps` + usa `--port` custom

## Args Provided:
```
$ARGUMENTS
```
