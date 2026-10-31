# Snapshot the working tree (D:\DSHNESS\GNN) into this repo's cst/ folder.
# ASCII only: Windows PowerShell 5.1 mis-parses UTF-8 without BOM.
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\sync_cst.ps1
$ErrorActionPreference = 'Stop'
$src = 'D:\DSHNESS\GNN'
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) 'cst'

if (-not (Test-Path $src)) { throw "source not found: $src" }
New-Item -ItemType Directory -Force -Path $dst | Out-Null

$files = Get-ChildItem $src -File | Where-Object { $_.Extension -in '.py', '.md', '.docx', '.pptx' }
foreach ($f in $files) { Copy-Item $f.FullName (Join-Path $dst $f.Name) -Force }

# every fig*/ subdirectory (fig, fig_paper, ...)
Get-ChildItem $src -Directory -Filter 'fig*' | ForEach-Object {
    $sub = Join-Path $dst $_.Name
    New-Item -ItemType Directory -Force -Path $sub | Out-Null
    Get-ChildItem $_.FullName -File | Where-Object { $_.Extension -in '.png', '.jpg', '.jpeg' } |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $sub $_.Name) -Force }
}

# demo_out/ (figures, metrics, logs; binaries stay out)
if (Test-Path (Join-Path $src 'demo_out')) {
    $dd = Join-Path $dst 'demo_out'
    New-Item -ItemType Directory -Force -Path $dd | Out-Null
    Get-ChildItem (Join-Path $src 'demo_out') -File |
        Where-Object { $_.Extension -in '.png', '.csv', '.json', '.txt' } |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $dd $_.Name) -Force }
    if (Test-Path (Join-Path $src 'demo_out\eval')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $dd 'eval') | Out-Null
        Get-ChildItem (Join-Path $src 'demo_out\eval') -File |
            ForEach-Object { Copy-Item $_.FullName (Join-Path $dd ('eval\' + $_.Name)) -Force }
    }
}

"synced {0} top-level files -> {1}" -f $files.Count, $dst