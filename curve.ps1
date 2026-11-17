$ErrorActionPreference="Continue"
Get-ChildItem rounds\r1\sub_*k.bin | Sort-Object Length | ForEach-Object {
  Write-Host "=== $($_.Name)"
  python tools\nnue\train_v3.py $_.FullName --out "rounds\r1\curve_$($_.BaseName)" --epochs 10 --bs 1024 --val 20000 | Select-Object -Last 3
}
