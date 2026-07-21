# PharmaSUD Marketing Demo Deployment Runbook

No push or deployment is part of this release-preparation commit.

## 1. Neon

Create a dedicated Neon project/database for the marketing demo. Copy its pooled PostgreSQL URL with `sslmode=require`. Do not commit it.

## 2. External PostgreSQL gate (Windows PowerShell)

```powershell
Set-Location 'C:\pharmasud-work\pharmasud-api'
$env:DATABASE_URL = '<NEON_TEST_DATABASE_URL>'
$env:SECRET_KEY = '<FIXED_64_HEX_SECRET>'
$env:ENVIRONMENT = 'production'
$env:RUN_POSTGRES_INTEGRATION = '1'
& '.\.venv\Scripts\python.exe' -m pytest -vv -m postgres_integration
Remove-Item Env:RUN_POSTGRES_INTEGRATION
```

Use a dedicated empty/test Neon database for this gate.

## 3. Render Web Service

Connect the GitHub repository to a Render Web Service. The committed `render.yaml` supplies the command and non-secret values. In Render Dashboard set:

- `DATABASE_URL`: Neon pooled connection string
- `SECRET_KEY`: one fixed random secret, at least 64 hexadecimal characters
- `ALLOWED_ORIGINS`: the exact HTTPS application origin

Keep `ENVIRONMENT=production`. Do not add a Render PostgreSQL database.

## 4. Marketing demo bootstrap

Run once from Render Shell after the web service startup succeeds:

```bash
export PHARMASUD_DEMO_ADMIN_PASSWORD='<STRONG_OPERATOR_PASSWORD>'
python -m scripts.bootstrap_marketing_demo \
  --confirm-demo-bootstrap \
  --username marketing_admin \
  --demo-key PHARMASUD-MARKETING-DEMO \
  --pharmacy-name 'PharmaSUD Marketing Demo'
unset PHARMASUD_DEMO_ADMIN_PASSWORD
```

The command is safe to repeat: it preserves the existing administrator, password hash, role, role ID, username, and pharmacy ID. It never prints the password.

## 5. Validation

```powershell
Invoke-RestMethod -Uri 'https://<RENDER-SERVICE>/health'
$body = @{ username = 'marketing_admin'; password = '<PASSWORD>' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'https://<RENDER-SERVICE>/api/auth/login' -ContentType 'application/json' -Body $body
```

Expected health fields are `status`, `database`, `environment`, `schema_ready`, and `version`. No database URL, host, username, or password is returned.
