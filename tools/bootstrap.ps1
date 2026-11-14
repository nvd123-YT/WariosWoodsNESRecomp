$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tools = Join-Path $Root ".tools"
$Downloads = Join-Path $Tools "downloads"
$CMakeVersion = "4.4.5"
$UvVersion = "0.6.14"
$PythonVersion = "3.12.9"

function Download-ReleaseAsset([string]$Uri, [string]$Destination, [string]$Label) {
    $Curl = Get-Command curl.exe -ErrorAction Stop
    Write-Host "Downloading $Label..."
    & $Curl.Source --fail --location --retry 3 --retry-delay 2 --connect-timeout 30 --max-time 420 --progress-bar --output $Destination $Uri
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed for $Label (curl exit code $LASTEXITCODE)."
    }
    if (-not (Test-Path $Destination) -or (Get-Item $Destination).Length -le 0) {
        throw "Download produced an empty file: $Label"
    }
    $SizeMiB = (Get-Item $Destination).Length / 1MB
    Write-Host ("Downloaded {0}: {1:N1} MiB" -f $Label, $SizeMiB)
}

New-Item -ItemType Directory -Force -Path $Tools, $Downloads, (Join-Path $Tools "cmake"), (Join-Path $Tools "uv"), (Join-Path $Tools "python"), (Join-Path $Tools "bin") | Out-Null

function Get-FirstFile([string]$Path, [string]$Name) {
    $item = Get-ChildItem -Path $Path -Filter $Name -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $item) { return $null }
    return $item.FullName
}

Write-Host "[1/4] Preparing portable CMake $CMakeVersion..."
$CMakeBin = Get-FirstFile (Join-Path $Tools "cmake") "cmake.exe"
if ($CMakeBin) {
    $InstalledCMake = (& $CMakeBin --version 2>$null | Select-Object -First 1)
    if ($InstalledCMake -ne "cmake version $CMakeVersion") {
        Write-Host "Replacing stale bundled CMake with $CMakeVersion..."
        Remove-Item -Recurse -Force (Join-Path $Tools "cmake")
        New-Item -ItemType Directory -Force -Path (Join-Path $Tools "cmake") | Out-Null
        $CMakeBin = $null
    }
}
if (-not $CMakeBin) {
    $CMakeArchive = "cmake-$CMakeVersion-windows-x86_64.zip"
    $CMakeUrl = "https://github.com/Kitware/CMake/releases/download/v$CMakeVersion/$CMakeArchive"
    $CMakeChecksUrl = "https://github.com/Kitware/CMake/releases/download/v$CMakeVersion/cmake-$CMakeVersion-SHA-256.txt"
    $ArchivePath = Join-Path $Downloads $CMakeArchive
    $ChecksPath = Join-Path $Downloads "cmake-checksums.txt"
    Download-ReleaseAsset $CMakeUrl $ArchivePath "CMake archive"
    Download-ReleaseAsset $CMakeChecksUrl $ChecksPath "CMake SHA-256 checksums"
    $Line = Get-Content $ChecksPath | Where-Object { $_ -match ("\s\*?" + [regex]::Escape($CMakeArchive) + "$") } | Select-Object -First 1
    if (-not $Line) { throw "CMake checksum entry not found." }
    $Expected = ($Line -split "\s+")[0].ToLowerInvariant()
    $Actual = (Get-FileHash -Algorithm SHA256 $ArchivePath).Hash.ToLowerInvariant()
    if ($Expected -ne $Actual) { throw "CMake archive checksum mismatch." }
    Expand-Archive -Path $ArchivePath -DestinationPath (Join-Path $Tools "cmake") -Force
    $CMakeBin = Get-FirstFile (Join-Path $Tools "cmake") "cmake.exe"
}
if (-not $CMakeBin) { throw "Portable CMake was not found after extraction." }
Set-Content -NoNewline -Path (Join-Path $Tools "cmake-path.txt") -Value $CMakeBin
& $CMakeBin --version | Select-Object -First 1

Write-Host "[2/4] Preparing portable uv $UvVersion..."
$UvBin = Get-FirstFile (Join-Path $Tools "uv") "uv.exe"
if (-not $UvBin) {
    $UvArchive = "uv-x86_64-pc-windows-msvc.zip"
    $UvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/$UvArchive"
    $ArchivePath = Join-Path $Downloads $UvArchive
    Download-ReleaseAsset $UvUrl $ArchivePath "uv archive"
    Download-ReleaseAsset "$UvUrl.sha256" "$ArchivePath.sha256" "uv SHA-256 checksum"
    $Expected = ((Get-Content "$ArchivePath.sha256" -Raw) -split "\s+")[0].ToLowerInvariant()
    $Actual = (Get-FileHash -Algorithm SHA256 $ArchivePath).Hash.ToLowerInvariant()
    if ($Expected -ne $Actual) { throw "uv archive checksum mismatch." }
    Expand-Archive -Path $ArchivePath -DestinationPath (Join-Path $Tools "uv") -Force
    $UvBin = Get-FirstFile (Join-Path $Tools "uv") "uv.exe"
}
if (-not $UvBin) { throw "Portable uv was not found after extraction." }
Set-Content -NoNewline -Path (Join-Path $Tools "uv-path.txt") -Value $UvBin

Write-Host "[3/4] Installing managed Python $PythonVersion into .tools..."
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Tools "python"
$env:UV_PYTHON_BIN_DIR = Join-Path $Tools "bin"
& $UvBin python install $PythonVersion
if ($LASTEXITCODE -ne 0) { throw "uv Python installation failed with exit code $LASTEXITCODE" }
$PythonBin = (& $UvBin python find $PythonVersion | Select-Object -Last 1).Trim()
if (-not (Test-Path $PythonBin)) { throw "Managed Python executable was not found: $PythonBin" }
Set-Content -NoNewline -Path (Join-Path $Tools "python-path.txt") -Value $PythonBin
& $PythonBin --version

Write-Host "[4/4] Checking pinned source dependencies..."
$Required = @(
    "nesrecomp/runner/cyc/project.cmake",
    "recomp-ui/recomp_ui.cmake",
    "SDL2/CMakeLists.txt",
    "cmake/bundled-sdl2/SDL2Config.cmake"
)
foreach ($Path in $Required) {
    if (-not (Test-Path (Join-Path $Root $Path))) {
        throw "Missing $Path. Run git submodule update --init --recursive."
    }
}

$ProgramFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$VsWhere = Join-Path $ProgramFilesX86 "Microsoft Visual Studio/Installer/vswhere.exe"
if (-not (Test-Path $VsWhere)) {
    throw "Visual Studio 2022 or 2026 C++ Build Tools are required. Install the Desktop development with C++ workload."
}
$Vs = & $VsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $Vs) {
    throw "Visual Studio 2022 or 2026 C++ x64 tools were not found. Install the Desktop development with C++ workload."
}

Write-Host "Bootstrap complete."
Write-Host "Portable CMake: $CMakeBin"
Write-Host "Managed Python: $PythonBin"
Write-Host "SDL2, NESRecomp and recomp-ui source are pinned in the repository."
Write-Host "Visual Studio C++ compiler is detected."
