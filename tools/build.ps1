param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Rom
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RomPath = (Resolve-Path $Rom).Path
if (-not (Test-Path $RomPath)) { throw "ROM not found: $RomPath" }

& (Join-Path $Root "setup.bat")
if ($LASTEXITCODE -ne 0) { throw "Setup failed with exit code $LASTEXITCODE" }

$CMakeBin = (Get-Content -Path (Join-Path $Root ".tools/cmake-path.txt") -Raw).Trim()
$PythonBin = (Get-Content -Path (Join-Path $Root ".tools/python-path.txt") -Raw).Trim()
$env:PATH = "$(Split-Path $PythonBin);$env:PATH"

& $CMakeBin -S $Root -B (Join-Path $Root "build") "-DNESRECOMP_ROM=$RomPath"
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed with exit code $LASTEXITCODE" }
& $CMakeBin --build (Join-Path $Root "build") --config Release --parallel 4
if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE" }

$Exe = Join-Path $Root "build/Release/ExcitebikeRecomp.exe"
if (-not (Test-Path $Exe)) { $Exe = Join-Path $Root "build/ExcitebikeRecomp.exe" }
if (-not (Test-Path $Exe)) { throw "Excitebike executable not found after successful build." }
& $Exe $RomPath
