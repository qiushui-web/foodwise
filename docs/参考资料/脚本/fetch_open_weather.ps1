param(
    [double]$Latitude = 39.52,
    [double]$Longitude = 116.70,
    [string]$StartDate = "2026-07-07",
    [string]$EndDate = "2026-07-20"
)

$ErrorActionPreference = "Stop"
$dataRoot = Split-Path -Parent $PSScriptRoot
$publicDataDirectory = Get-ChildItem -LiteralPath $dataRoot -Directory | Where-Object { $_.Name -like "03_*" } | Select-Object -First 1
if (-not $publicDataDirectory) {
    throw "Public data directory (03_*) was not found under $dataRoot"
}
$target = Join-Path $publicDataDirectory.FullName "langfang_weather_2026-07-07_2026-07-20.json"
$uri = "https://archive-api.open-meteo.com/v1/archive?latitude=$Latitude&longitude=$Longitude&start_date=$StartDate&end_date=$EndDate&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=Asia%2FShanghai"

$response = Invoke-RestMethod -Uri $uri -Method Get
$response | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $target -Encoding utf8
Write-Output "Saved public weather data to $target"
