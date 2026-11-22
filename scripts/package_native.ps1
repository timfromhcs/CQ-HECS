# Build and package the two native configurations on Windows (MSVC, Release).
#
#   powershell -ExecutionPolicy Bypass -File scripts/package_native.ps1 -OutDir C:\tmp\native-out -WorkDir C:\tmp\native-work
#
# Artifacts (names are exact; the version comes from scripts/version.py):
#   cq-hecs-cpu-<version>-windows-x64.zip     CPU-only C-ABI library (cq_hecs_core.dll). No CLI, no
#                                             Vulkan code, no Vulkan loader import. A LIBRARY, not an app.
#   cq-hecs-vulkan-<version>-windows-x64.zip  Vulkan build: cq_hecs.exe (VRTS-300 CLI), cq_hecs.dll,
#                                             cq_hecs_core.dll. Needs a Vulkan loader/driver at run time.
#
# Own build directories (-WorkDir) so parallel builds cannot collide. Nothing is installed or
# published. Tests (ctest) run in each build tree unless -SkipTests.

param(
  [string]$OutDir = "",
  [string]$WorkDir = "",
  [string]$Generator = "",
  [string]$Python = "python",
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

# CMake generator for the installed Visual Studio. Order of precedence:
#   1. -Generator            (explicit argument)
#   2. $env:CQ_CMAKE_GENERATOR
#   3. the Visual Studio found by vswhere (17 -> "Visual Studio 17 2022", 18 -> "Visual Studio 18 2026"),
#      only if this CMake lists that generator
#   4. "Visual Studio 17 2022" (the previous fixed behaviour, unchanged on machines that have VS 2022)
# A hosted "windows-latest" image moves to a newer Visual Studio over time; a hard-coded generator
# then fails with "could not find any instance of Visual Studio".
function Resolve-CMakeGenerator([string]$Requested) {
  if ($Requested) { return $Requested }
  if ($env:CQ_CMAKE_GENERATOR) { return $env:CQ_CMAKE_GENERATOR }
  $default = "Visual Studio 17 2022"
  $known = @{ "17" = "Visual Studio 17 2022"; "18" = "Visual Studio 18 2026" }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (-not (Test-Path $vswhere)) { return $default }
  $ver = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationVersion 2>$null | Select-Object -First 1)
  if (-not $ver) { return $default }
  $major = ([string]$ver).Split(".")[0]
  if (-not $known.ContainsKey($major)) { return $default }
  $help = (cmake --help 2>&1 | Out-String)
  if ($help.Contains($known[$major])) { return $known[$major] }
  return $default
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not $OutDir) { $OutDir = Join-Path $Root "dist" }
if (-not $WorkDir) { $WorkDir = Join-Path $Root "build\native-package" }
New-Item -ItemType Directory -Force -Path $OutDir, $WorkDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$WorkDir = (Resolve-Path $WorkDir).Path
$Version = (& $Python "$Root\scripts\version.py").Trim()
$Generator = Resolve-CMakeGenerator $Generator
Write-Host "CMake generator: $Generator"

function Build-Lane([string]$Name, [string]$VulkanFlag) {
  $bd = Join-Path $WorkDir $Name
  cmake -S $Root -B $bd -G $Generator -A x64 "-DCQ_ENABLE_VULKAN=$VulkanFlag" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "cmake configure failed for $Name" }
  cmake --build $bd --config Release --parallel | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "cmake build failed for $Name" }
  if (-not $SkipTests) {
    Push-Location $bd
    try {
      ctest -C Release --output-on-failure --timeout 300 | Out-Host
      if ($LASTEXITCODE -ne 0) { throw "ctest failed for $Name" }
    } finally { Pop-Location }
  }
  # Only the path may reach the pipeline: every native command above is piped to Out-Host.
  return (Join-Path $bd "bin\Release")
}

function Stage([string]$Pkg, [string]$BinDir, [string[]]$Files, [string]$Note) {
  $stage = Join-Path $WorkDir ("stage-" + $Pkg)
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
  $top = Join-Path $stage $Pkg
  New-Item -ItemType Directory -Force -Path (Join-Path $top "bin"), (Join-Path $top "include") | Out-Null
  foreach ($f in $Files) { Copy-Item (Join-Path $BinDir $f) (Join-Path $top "bin\$f") }
  Copy-Item "$Root\include\cq" (Join-Path $top "include\cq") -Recurse
  Copy-Item "$Root\include\cq_hecs_api.h" (Join-Path $top "include\")
  Copy-Item "$Root\LICENSE" $top
  Set-Content -Path (Join-Path $top "README.txt") -Value $Note -Encoding ascii
  $zip = Join-Path $OutDir "$Pkg-$Version-windows-x64.zip"
  if (Test-Path $zip) { Remove-Item $zip }
  & $Python "$Root\scripts\package_archive.py" --src $top --out $zip --root-name $Pkg | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "archive failed for $Pkg" }
  return $zip
}

$cpuBin = Build-Lane "cpu" "OFF"
$vkBin = Build-Lane "vulkan" "ON"

$cpuNote = @"
cq-hecs-cpu $Version (Windows x64, MSVC Release, dynamic CRT)
CPU-only native C-ABI library: bin\cq_hecs_core.dll. There is no command-line program in this
package. It contains no Vulkan code and does not import the Vulkan loader
(cq_core_build_capabilities() reports {"cpu_core": true, "vulkan_linked": false}).
Requires the Microsoft Visual C++ 2015-2022 x64 runtime (VCRUNTIME140.dll, MSVCP140.dll).
Not verified on a clean machine.
"@
$vkNote = @"
cq-hecs-vulkan $Version (Windows x64, MSVC Release, dynamic CRT)
Vulkan native build: bin\cq_hecs.exe (VRTS-300 command line), bin\cq_hecs.dll, bin\cq_hecs_core.dll.
Needs a Vulkan loader (vulkan-1.dll) and driver at run time. Without a usable Vulkan device the
program's behaviour is documented in docs\PACKAGING.md of the source tree, not guaranteed here.
Requires the Microsoft Visual C++ 2015-2022 x64 runtime. Not verified on a clean machine.
"@

$z1 = Stage "cq-hecs-cpu" $cpuBin @("cq_hecs_core.dll", "cq_hecs_core.lib") $cpuNote
$z2 = Stage "cq-hecs-vulkan" $vkBin @("cq_hecs.exe", "cq_hecs.dll", "cq_hecs.lib", "cq_hecs_core.dll", "cq_hecs_core.lib") $vkNote
Write-Host "Built: $z1"
Write-Host "Built: $z2"
