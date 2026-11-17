# Keep generating labeled training chunks until the deadline. Safe to stop (Ctrl+C) and re-run: finished chunks are skipped.
# Usage: powershell -ExecutionPolicy Bypass -File .\tools\nnue\overnight.ps1 -Hours 8 -Threads 8 -Name big -SeedBase 100000
param([double]$Hours=8,[int]$Threads=8,[string]$Name="big",[int]$SeedBase=100000,[int]$Games=500,[int]$GenNodes=5000,[int]$RelNodes=20000,[string]$Net="")
$ErrorActionPreference="Stop"
$eng=".\bin\terranion.exe"; $root="rounds\$Name"; New-Item -ItemType Directory -Force $root | Out-Null
if ($Net) { $env:TERRANION_NET=$Net }
$deadline=(Get-Date).AddHours($Hours); $i=0
while ((Get-Date) -lt $deadline) {
  $c="$root\chunk_{0:D4}" -f $i; $bin="$c\train.bin"
  if ((Test-Path $bin) -and ((Get-Item $bin).Length -gt 0)) { $i++; continue }
  if (Test-Path $c) { Remove-Item -Recurse -Force $c }   # leftover of an interrupted chunk
  $seed=$SeedBase + $i*$Threads
  Write-Host ("=== chunk {0} seed {1} {2}" -f $i,$seed,(Get-Date))
  New-Item -ItemType Directory -Force "$c\data" | Out-Null
  & $eng gen $Threads $seed $Games $GenNodes "$c\data"
  Get-Content "$c\data\gen_*.txt" | Set-Content "$c\raw.txt"
  & $eng relabel "$c\raw.txt" "$c\labeled.txt" $RelNodes $Threads
  & $eng pack "$c\labeled.txt" "$c\train_tmp.bin"
  Move-Item "$c\train_tmp.bin" $bin
  Remove-Item -Recurse -Force "$c\data","$c\raw.txt","$c\labeled.txt"
  $i++
}
Write-Host "deadline reached. chunks: $i  -> now run train_big.ps1"
