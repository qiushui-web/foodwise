[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('backup','restore')][string]$Action,
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Target
)
$ErrorActionPreference = 'Stop'
$timer = [Diagnostics.Stopwatch]::StartNew()
$sourcePath = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
$targetPath = [IO.Path]::GetFullPath($Target).TrimEnd('\')
if (Test-Path -LiteralPath $targetPath) { throw '目标已存在，必须选择新目录；不覆盖任何数据库。' }
if ($targetPath.StartsWith($sourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '目标不能位于源目录内部。' }
if (Get-ChildItem -LiteralPath $sourcePath -Filter '*.lock.db') { throw '检测到 H2 锁文件，请先正常停止应用。' }
$files = @(Get-ChildItem -LiteralPath $sourcePath -Filter '*.mv.db' -File)
if ($files.Count -ne 1) { throw '源目录须且只能包含一个 H2 .mv.db 文件。' }
$file = $files[0]
$expectedHash = $null
if ($Action -eq 'restore') {
  $manifestPath = Join-Path $sourcePath 'backup-manifest.json'
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.action -ne 'backup' -or $manifest.file -ne $file.Name) { throw '备份清单与数据库不匹配。' }
  if ($manifest.sha256 -notmatch '^[A-Fa-f0-9]{64}$') { throw '备份清单缺少有效 SHA-256，拒绝恢复。' }
  $expectedHash = $manifest.sha256
}
# 独占读锁持续到复制结束；运行中的 H2 不能获得该锁。
$stream = [IO.File]::Open($file.FullName, 'Open', 'Read', 'None')
try {
  $sha = [Security.Cryptography.SHA256]::Create()
  try { $sourceHash = [Convert]::ToHexString($sha.ComputeHash($stream)) } finally { $sha.Dispose() }
  if ($expectedHash -and $sourceHash -ne $expectedHash) { throw '源文件 SHA-256 与备份清单不一致，拒绝恢复。' }
  $stream.Position = 0
  New-Item -ItemType Directory -Path $targetPath | Out-Null
  $destination = Join-Path $targetPath $file.Name
  $out = [IO.File]::Open($destination, 'CreateNew', 'Write', 'None')
  try { $stream.CopyTo($out) } finally { $out.Dispose() }
} finally { $stream.Dispose() }
$copiedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
if ($copiedHash -ne $sourceHash) { throw '复制后哈希不一致，请保留目录排查。' }
$timer.Stop()
[PSCustomObject]@{
  action=$Action; file=$file.Name; sha256=$copiedHash; bytes=(Get-Item -LiteralPath $destination).Length
  completedAt=(Get-Date).ToUniversalTime().ToString('o'); elapsedMs=$timer.ElapsedMilliseconds
  verified=$true; scope='offline H2 copy; application restart/readback required'
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $targetPath ($Action + '-manifest.json')) -Encoding UTF8
Write-Output "$Action 完成，SHA-256 一致；还须启动隔离库验证业务读回。"
