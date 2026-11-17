param([string]$Round="test",[int]$Threads=4,[int]$Seed=1,[int]$Games=20,[int]$GenNodes=5000,[int]$RelNodes=20000,[string]$Arch="v3",[int]$Epochs=8,[string]$Warm="")
$ErrorActionPreference="Stop"
$eng=".\bin\terranion.exe"; $d="rounds\$Round"; New-Item -ItemType Directory -Force "$d\data" | Out-Null
Write-Host "[1/4] generate selfplay data"
& $eng gen $Threads $Seed $Games $GenNodes "$d\data"
Get-Content "$d\data\gen_*.txt" | Set-Content "$d\raw.txt"
Write-Host "[2/4] relabel"
& $eng relabel "$d\raw.txt" "$d\labeled.txt" $RelNodes $Threads
Write-Host "[3/4] pack"
& $eng pack "$d\labeled.txt" "$d\train.bin"
Write-Host "[4/4] train"
if ($Arch -eq "v3") { python tools\nnue\train_v3.py "$d\train.bin" --out "$d\net" --epochs $Epochs }
elseif ($Warm) { python tools\nnue\train_v2.py "$d\train.bin" --warm $Warm --out "$d\net" --epochs $Epochs }
else { python tools\nnue\train_v2.py "$d\train.bin" --out "$d\net" --epochs $Epochs }
Write-Host "done: $d"
