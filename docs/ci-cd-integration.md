# CI/CD Integration — gaet

Integrate gaet into your continuous integration pipelines.

---

## GitHub Actions

```yaml
name: Database Backup

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:     # Manual trigger

jobs:
  backup:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      
      - name: Install gaet
        run: |
          curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
      
      - name: Configure
        run: |
          gaet set GAET_LOCAL_URL="${{ secrets.LOCAL_DB_URL }}"
          gaet set GAET_REMOTE_URL="${{ secrets.CLOUD_DB_URL }}"
      
      - name: Run backup
        run: |
          gaet push --json > backup-result.json
          
      - name: Check result
        run: |
          python3 -c "import json; d=json.load(open('backup-result.json')); exit(0 if d['ok'] else 1)"
```

### Using with Supabase

```yaml
- name: Push to Supabase
  run: |
    gaet push \
      --notify "${{ secrets.WEBHOOK_URL }}"
```

---

## GitLab CI

```yaml
backup:
  stage: deploy
  image: ubuntu-latest
  script:
    - curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
    - gaet set GAET_REMOTE_URL="$CLOUD_DB_URL"
    - gaet push --json
  only:
    - main
```

---

## Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Backup') {
            steps {
                sh 'curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash'
                sh 'gaet set GAET_REMOTE_URL=${CLOUD_DB_URL}'
                sh 'gaet push'
            }
        }
    }
    
    post {
        failure {
            sh 'gaet log 50 >> build-log.txt'
        }
    }
}
```

---

## CircleCI

```yaml
version: 2.1

jobs:
  backup:
    docker:
      - image: cgr.dev/chainguard/wolfi-base:latest
    steps:
      - run:
          name: Install gaet
          command: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
      - run:
          name: Run backup
          command: gaet push --json
```

---

## Airgapped Environments

For environments without internet access:

1. **Download installer + binary** (from a machine with internet):
   ```bash
   curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh > install.sh
   curl -sSL https://github.com/ghanirahmans/gaet/releases/latest/download/gaet-linux-amd64 > gaet
   chmod +x install.sh gaet
   ```

2. **Transfer to target machine** via USB, SCP, or internal package repository.

3. **Install locally:**
   ```bash
   chmod +x install.sh gaet
   cp gaet ~/.local/bin/gaet  # place binary on PATH
   ./install.sh  # creates ~/.gaet/.env config template
   ```

---

## Webhook Notifications

Get notified when backup completes:

```bash
gaet push --notify="https://hooks.slack.com/services/XXX/YYY/ZZZ"
gaet push --notify="https://discord.com/api/webhooks/XXX/YYY"
gaet push --notify="https://your-api.example.com/backup-webhook"
```

Payload format (JSON):
```json
{
  "event": "backup.complete",
  "status": "success",
  "database": "production",
  "size_mb": 37.7,
  "tables": 19,
  "duration_seconds": 45.2,
  "timestamp": "2024-08-15T10:30:00Z"
}
```

---

### Health Check via CI

Use `gaet doctor --json` to verify the backup environment in CI:

```bash
# Check that database tools are found and local DB is reachable
gaet doctor --json | jq '.checks.tools.ok and .checks.local_db.ok'
```

### Prometheus Metrics

> **Note**: Prometheus metrics are **not yet implemented** by the gaet Go engine. This is a future feature (see `docs/roadmap.md` → Phase 4: Observability). The `gaet doctor --json` command above is the supported health-check pathway for CI monitoring integrations.

---

## Troubleshooting

### "Cannot connect to GitHub raw content"

Your CI environment may block outbound requests. Clone the repo directly instead:
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
go build -ldflags="-s -w" -o ~/.local/bin/gaet ./cmd/gaet
```

Or use the GitHub releases binary asset directly:
```bash
curl -sSL https://github.com/ghanirahmans/gaet/releases/latest/download/gaet-linux-amd64 > gaet
chmod +x gaet && mv gaet ~/.local/bin/gaet
```

### "pg_dump not found in PATH"

Install database client tools:
```yaml
# GitHub Actions
- run: sudo apt-get install -y postgresql-client

# Dockerfile
RUN apt-get update && apt-get install -y postgresql-client
```

### "Permission denied writing to /usr/local/bin"

The installer (`install.sh`) writes to `~/.local/bin` by default (user-local bin, no sudo required). Ensure `~/.local/bin` is on your `PATH`:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
```
