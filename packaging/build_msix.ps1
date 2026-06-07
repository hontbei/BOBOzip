<#
.SYNOPSIS
    Build an MSIX package for BOBOzip.

.DESCRIPTION
    Lays out a packaging folder containing the PyInstaller-built exe, generated
    logo assets and the AppxManifest, then calls makeappx.exe to produce an
    .msix. If a signing certificate is available the package is signed with
    signtool.exe; otherwise an unsigned package is produced (users must install
    a trusted cert / use the self-signed cert that is also exported).

.NOTES
    Designed to run on GitHub Actions windows-latest where the Windows SDK
    (makeappx / signtool) is on PATH or under Program Files.
#>
param(
    [string]$ExePath = "dist/BOBOzip.exe",
    [string]$OutputDir = "dist",
    [string]$Version = "1.0.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$layout = Join-Path $root "build/msix_layout"
$assets = Join-Path $layout "Assets"
if (Test-Path $layout) { Remove-Item -Recurse -Force $layout }
New-Item -ItemType Directory -Force -Path $assets | Out-Null

Write-Host "[msix] Copying executable..."
Copy-Item $ExePath (Join-Path $layout "BOBOzip.exe")

Write-Host "[msix] Copying manifest..."
$manifestSrc = Join-Path $PSScriptRoot "AppxManifest.xml"
$manifestDst = Join-Path $layout "AppxManifest.xml"
(Get-Content $manifestSrc -Raw) -replace 'Version="1\.0\.0\.0"', "Version=`"$Version`"" |
    Set-Content $manifestDst -Encoding UTF8

Write-Host "[msix] Generating logo assets..."
python (Join-Path $PSScriptRoot "make_assets.py") $assets

# --- Locate Windows SDK tools -------------------------------------------------
function Find-SdkTool($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $bases = @(
        "C:/Program Files (x86)/Windows Kits/10/bin",
        "C:/Program Files/Windows Kits/10/bin"
    )
    foreach ($base in $bases) {
        if (Test-Path $base) {
            $found = Get-ChildItem -Path $base -Recurse -Filter $name -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match "x64" } |
                Sort-Object FullName -Descending |
                Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    return $null
}

$makeappx = Find-SdkTool "makeappx.exe"
if (-not $makeappx) { throw "makeappx.exe not found. Windows SDK is required." }
Write-Host "[msix] makeappx: $makeappx"

$msixPath = Join-Path $OutputDir "BOBOzip.msix"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "[msix] Building package..."
& $makeappx pack /d $layout /p $msixPath /overwrite
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }

# --- Sign with a self-signed certificate -------------------------------------
$signtool = Find-SdkTool "signtool.exe"
if ($signtool) {
    Write-Host "[msix] Creating self-signed certificate..."
    $cert = New-SelfSignedCertificate `
        -Type Custom `
        -Subject "CN=BOBOzip" `
        -KeyUsage DigitalSignature `
        -FriendlyName "BOBOzip Self Signed" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")

    $pfxPassword = ConvertTo-SecureString -String "bobozip" -Force -AsPlainText
    $pfxPath = Join-Path $OutputDir "BOBOzip-selfsigned.pfx"
    $cerPath = Join-Path $OutputDir "BOBOzip-selfsigned.cer"
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPassword | Out-Null
    Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null

    Write-Host "[msix] Signing package..."
    & $signtool sign /fd SHA256 /a /f $pfxPath /p "bobozip" $msixPath
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "signtool failed; leaving package unsigned."
    } else {
        Write-Host "[msix] Signed. Install $cerPath into 'Trusted People' before installing the MSIX."
    }
} else {
    Write-Warning "signtool.exe not found; producing unsigned MSIX."
}

Write-Host "[msix] Done -> $msixPath"
