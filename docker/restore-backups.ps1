<#
.SYNOPSIS
    Copies SQLite backups out of the `app_data` Docker volume onto the host.

.DESCRIPTION
    Since /data lives in a named Docker volume (not a host bind mount), the
    rotating backup files written by the `backup` service are not directly
    visible from Windows Explorer. Run this script to materialise them under
    `..\data\backups\` whenever you want a host-side copy.

    Default behaviour:
      - Locates the running `docker-backend-1` container.
      - Falls back to the `docker_app_data` volume via a throwaway alpine
        container if the backend isn't running.
      - Writes everything into `<repo>\data\backups\`.

.EXAMPLE
    PS> .\restore-backups.ps1
    Copies all *.db files in /data/backups onto the host.

.EXAMPLE
    PS> .\restore-backups.ps1 -Destination 'D:\sqlite-snapshots'
    Same, but into an explicit destination folder.
#>
[CmdletBinding()]
param(
    [string] $Destination
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Resolve-Path (Join-Path $scriptDir '..')

if (-not $Destination) {
    $Destination = Join-Path $repoRoot 'data\backups'
}

if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

Write-Host "Destination: $Destination"

# Prefer copying out of the live backend container so we get the freshest view
# of the volume without spinning anything up.
$container = (docker ps --filter "name=docker-backend-1" --format "{{.Names}}" 2>$null | Select-Object -First 1)

if ($container) {
    Write-Host "Copying /data/backups from container '$container'..."
    docker cp "${container}:/data/backups/." $Destination
} else {
    Write-Host "Backend container not running; mounting volume 'docker_app_data' via temporary alpine..."
    $volume = 'docker_app_data'
    $abs    = (Resolve-Path $Destination).Path
    docker run --rm `
        -v "${volume}:/data:ro" `
        -v "${abs}:/out" `
        alpine:3.20 sh -c 'cp -r /data/backups/. /out/ 2>/dev/null || true'
}

$count = (Get-ChildItem -Path $Destination -Filter 'sqlite-*.db' -ErrorAction SilentlyContinue).Count
Write-Host "Done. $count backup file(s) now under $Destination"
