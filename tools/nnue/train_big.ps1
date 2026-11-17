# Concatenate all finished chunks of a run and train v3 on them (resumable).
# Usage: powershell -ExecutionPolicy Bypass -File .\tools\nnue\train_big.ps1 -Name big -Epochs 6 -Threads 4
#        add -Resume to continue after a crash (keeps all.bin and the checkpoint rounds\<Name>\net_ckpt.pt)
param([string]$Name="big",[int]$Epochs=10,[int]$Bs=2048,[int]$Val=200000,[int]$Threads=4,[switch]$Resume)
$ErrorActionPreference="Stop"
$root="rounds\$Name"; $all="$root\all.bin"
if (-not ($Resume -and (Test-Path $all))) {
  $chunks=Get-ChildItem "$root\chunk_*\train.bin" | Where-Object { $_.Length -gt 0 } | Sort-Object FullName
  Write-Host ("chunks: {0}" -f $chunks.Count)
  if (Test-Path $all) { Remove-Item $all }
  $out=[System.IO.File]::Create((Join-Path (Get-Location) $all))
  foreach ($f in $chunks) { $s=[System.IO.File]::OpenRead($f.FullName); $s.CopyTo($out); $s.Close() }
  $out.Close()
}
Write-Host ("records: {0}" -f ((Get-Item $all).Length/80))
$extra=@(); if ($Resume) { $extra += "--resume" }
python tools\nnue\train_v3.py $all --out "$root\net" --epochs $Epochs --bs $Bs --val $Val --threads $Threads @extra
