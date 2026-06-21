param(
  [string]$ObNamespace = "default",
  [string]$OutDir = "fluxev_data",
  [string]$LoadgeneratorDeployment = "loadgenerator",
  [string]$Pattern = "1:low,2:mid,4:high,2:mid,1:low",
  [string]$EndAtIso = ""
)

$ErrorActionPreference = "Stop"
$metadataDir = Join-Path $OutDir "metadata"
New-Item -ItemType Directory -Force -Path $metadataDir | Out-Null
$loadLog = Join-Path $metadataDir "load_profile.csv"
if (-not (Test-Path $loadLog)) {
  "timestamp_iso,replicas,phase" | Out-File -Encoding utf8 $loadLog
}

$endAt = $null
if ($EndAtIso) {
  $endAt = [DateTime]::Parse($EndAtIso).ToUniversalTime()
}

while (($null -eq $endAt) -or ((Get-Date).ToUniversalTime() -lt $endAt)) {
  foreach ($step in $Pattern.Split(",")) {
    if (($null -ne $endAt) -and ((Get-Date).ToUniversalTime() -ge $endAt)) {
      break
    }
    $parts = $step.Split(":")
    $replicas = $parts[0]
    $phase = $parts[1]
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    kubectl scale "deployment/$LoadgeneratorDeployment" -n $ObNamespace "--replicas=$replicas"
    "$ts,$replicas,$phase" | Add-Content -Encoding utf8 $loadLog
    Write-Output "$ts,$replicas,$phase"
    Start-Sleep -Seconds 60
  }
}
