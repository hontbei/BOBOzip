<#
.SYNOPSIS
    Build an MSIX package for BOBOzip.

.DESCRIPTION
    Lays out a packaging folder containing the PyInstaller-built exe, generated
    logo assets and the AppxManifest, then calls makeappx.exe to produce an
    .msix.

    Two modes:
      * Default (sideload): signs the package with a generated self-signed
        certificate so you can install it locally for testing. The matching
        .cer is exported and must be imported into "Trusted People" first.
      * -Store: produces an UNSIGNED package intended for upload to the
        Microsoft Partner Center. The Store re-signs it, so do NOT sign it
        yourself. Identity Name/Publisher MUST match the values assigned to
        your app in Partner Center.

.PARAMETER IdentityName
    Package Identity/Name. For Store submission use the value shown under
    Partner Center > Product Identity (e.g. "1234Publisher.BOBOzip").

.PARAMETER Publisher
    Package Identity/Publisher. For Store submission use the exact Publisher
    value (e.g. "CN=ABCD1234-...") from Partner Center > Product Identity.

.PARAMETER PublisherDisplayName
    Human-readable publisher name shown to users.

.NOTES
    Designed to run on GitHub Actions windows-latest where the Windows SDK
    (makeappx / signtool) is on PATH or under Program Files.
#>
param(
    [string]$ExePath = "dist/BOBOzip.exe",
    [string]$OutputDir = "dist",
    [string]$Version = "1.0.0.0",
    [string]$IdentityName = "hontbei.BOBOzip",
    [string]$Publisher = "CN=BOBOzip",
    [string]$PublisherDisplayName = "hontbei",
    [switch]$Store
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

Write-Host "[msix] Writing manifest (Identity: $IdentityName / $Publisher)..."
$manifestSrc = Join-Path $PSScriptRoot "AppxManifest.xml"
$manifestDst = Join-Path $layout "AppxManifest.xml"
$utf8 = [System.Text.UTF8Encoding]::new($false)  # UTF-8 without BOM
$manifest = [System.IO.File]::ReadAllText($manifestSrc, $utf8)
$manifest = $manifest -replace '__IDENTITY_NAME__', $IdentityName
$manifest = $manifest -replace '__PUBLISHER__', $Publisher
$manifest = $manifest -replace '__PUBLISHER_DISPLAY_NAME__', $PublisherDisplayName
$manifest = $manifest -replace 'Version="1\.0\.0\.0"', "Version=`"$Version`""
[System.IO.File]::WriteAllText($manifestDst, $manifest, $utf8)

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

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

if ($Store) {
    # ---- Store submission package: UNSIGNED -----------------------------------
    $msixPath = Join-Path $OutputDir "BOBOzip-store.msix"
    Write-Host "[msix] Building STORE package (unsigned) -> $msixPath"
    & $makeappx pack /d $layout /p $msixPath /overwrite
    if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }
    Write-Host "[msix] Store package ready. Upload to Partner Center; do NOT sign it yourself."
    Write-Host "[msix] Done -> $msixPath"
    return
}

# ---- Sideload package: signed with a self-signed certificate -----------------
$msixPath = Join-Path $OutputDir "BOBOzip.msix"
Write-Host "[msix] Building sideload package -> $msixPath"
& $makeappx pack /d $layout /p $msixPath /overwrite
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }

$signtool = Find-SdkTool "signtool.exe"
if ($signtool) {
    Write-Host "[msix] Creating self-signed certificate (subject must match Publisher: $Publisher)..."
    $cert = New-SelfSignedCertificate `
        -Type Custom `
        -Subject $Publisher `
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
        Write-Host "[msix] Signed. Import $cerPath into 'Trusted People' before installing the MSIX."
    }
} else {
    Write-Warning "signtool.exe not found; producing unsigned MSIX."
}

Write-Host "[msix] Done -> $msixPath"
