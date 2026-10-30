if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example. Edit SECRET_KEY and ENCRYPTION_SECRET before using integrations." -ForegroundColor Yellow
}
docker compose up --build
