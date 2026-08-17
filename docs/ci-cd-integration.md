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
          curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/main/install.sh | bash
      
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
  image: python:3.11-slim
  script:
    - curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
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
                sh 'curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash'
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
      - image: python:3.11
    steps:
      - run:
          name: Install gaet
          command: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
      - run:
          name: Run backup
          command: gaet push --json
```

---

## Airgapped Environments

For environments without internet access:

1. **Download installer:**
   ```bash
   curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh > install.sh
   curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/gaet.py > gaet.py
   ```

2. **Transfer to target machine** via USB, SCP, or internal package repository.

3. **Install locally:**
   ```bash
   chmod +x install.sh
   ./install.sh --offline
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

## Monitoring

### Prometheus Metrics

Export backup metrics via simple HTTP endpoint:

```bash
# Start metrics endpoint
python3 -m http.server 9100 &

# Or use gaet's built-in health check
gaet doctor --json | jq '.tools_found'
```

### Grafana Dashboard

Sample queries:
```promql
# Backup success rate
sum(rate(gaet_backup_success[24h])) / sum(rate(gaet_backup_total[24h]))

# Last backup size
gaet_backup_size_bytes

# Backup duration
gaet_backup_duration_seconds
```

---

## Troubleshooting

### "Cannot connect to GitHub raw content"

Your CI environment may block outbound requests. Use mirror:
```bash
curl -sSL https://gitlab.com/ghanirahmans/gaet/-/raw/master/install.sh | bash
```

Or clone repo directly:
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
go build -ldflags="-s -w" -o ~/.local/bin/gaet ./cmd/gaet
```

### "pg_dump not found in PATH"

Install PostgreSQL client tools:
```yaml
# GitHub Actions
- run: sudo apt-get install -y postgresql-client

# Dockerfile
RUN apt-get update && apt-get install -y postgresql-client
```

### "Permission denied writing to /usr/local/bin"

Use user-level install:
```bash
./install.sh --user
```
