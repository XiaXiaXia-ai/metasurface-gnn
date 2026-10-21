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
