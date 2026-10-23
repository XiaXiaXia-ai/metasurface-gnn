<#
    把在用工作区 D:\DSHNESS\GNN 的脚本 / 文档 / 图，快照到本仓库的 cst/ 目录。
    用法：  ./scripts/sync_cst.ps1
    随后：  git add -A ; git commit -m "chore: sync" ; git push
#>
$ErrorActionPreference = 'Stop'
$src = 'D:\DSHNESS\GNN'
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) 'cst'

if (-not (Test-Path $src)) { throw "source not found: $src" }
New-Item -ItemType Directory -Force -Path $dst | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dst 'fig') | Out-Null

$files = Get-ChildItem $src -File | Where-Object { $_.Extension -in '.py', '.md', '.docx' }
foreach ($f in $files) { Copy-Item $f.FullName (Join-Path $dst $f.Name) -Force }

if (Test-Path (Join-Path $src 'fig')) {
    Get-ChildItem (Join-Path $src 'fig') -File -Filter *.png |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $dst ('fig\' + $_.Name)) -Force }
}

"synced {0} files -> {1}" -f $files.Count, $dst
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
# 任何 fig*/ 子目录下的 PNG 也一并快照（如 fig_paper/）
Get-ChildItem $src -Directory -Filter 'fig*' | ForEach-Object {
    $sub = Join-Path $dst $_.Name
    New-Item -ItemType Directory -Force -Path $sub | Out-Null
    Get-ChildItem $_.FullName -File -Filter *.png |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $sub $_.Name) -Force }
}
