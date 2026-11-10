param([string]$target='E:\食刻有数\计划书\计划书版本\食刻有数_创新创业计划书_双赛融合版_20261109.docx',[string]$preview='E:\食刻有数\项目代码\docs\plan_20261109\pages')
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $preview | Out-Null
Add-Type -AssemblyName System.Drawing
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
$doc=$null
try {
 $doc=$word.Documents.Open($target,$false,$false)
 $doc.ActiveWindow.View.Type=3
 for ($pass=1;$pass -le 2;$pass++) {
  $doc.Repaginate()
  $heads=@{}
  foreach($p in $doc.Paragraphs) {
   if($p.OutlineLevel -le 2) {$txt=$p.Range.Text.Trim();if($txt){$heads[$txt]=$p.Range.Information(1)}}
  }
  foreach($p in $doc.Paragraphs) {
   if($p.Style.NameLocal -eq '目录条目') {
    $txt=$p.Range.Text.Trim()
    if($txt -match '^(.+)\t\d+$') {
     $name=$Matches[1]
     if(-not $heads.ContainsKey($name)){throw "Missing heading: $name"}
     $r=$p.Range.Duplicate;$r.End=$r.End-1;$r.Text=$name+"`t"+$heads[$name]
    }
   }
  }
 }
 $doc.Fields.Update() | Out-Null
 $doc.Repaginate();$doc.Save()
 $count=$doc.ComputeStatistics(2)
 Write-Output "PAGES=$count"
 $stats=@();$caps=@();$prev=$null;$explanations=@();$fontAudit=@()
 foreach($p in $doc.Paragraphs) {
  $txt=$p.Range.Text.Trim();$style=$p.Style.NameLocal
  if($p.OutlineLevel -le 2){$stats+=@{title=$txt;physical=$p.Range.Information(3);page=$p.Range.Information(1)}}
  if($style -eq '图题'){$caps+=@{caption=$txt;page=$p.Range.Information(3);imagePage=$prev.Range.Information(3)}}
  if($style -eq '图后说明'){$explanations+=@{text=$txt;page=$p.Range.Information(3);captionPage=$prev.Range.Information(3)}}
  if($style -match '^正文' -and $fontAudit.Count -lt 3){$fontAudit+=@{style=$style;bold=$p.Range.Font.Bold;eastAsia=$p.Range.Font.NameFarEast;size=$p.Range.Font.Size;line=$p.Range.ParagraphFormat.LineSpacing}}
  $prev=$p
 }
 $rowIssues=@();$ti=0
 foreach($t in $doc.Tables){$ti++;$ri=0;foreach($row in $t.Rows){$ri++;$r=$row.Range.Duplicate;$s=$r.Start;$e=$r.End;$r.SetRange($s,$s);$sp=$r.Information(3);$r.SetRange($e-1,$e-1);$ep=$r.Information(3);if($sp -ne $ep){$rowIssues+=@{table=$ti;row=$ri;start=$sp;end=$ep}}}}
 @{pages=$count;headings=$stats;captions=$caps;splitRows=$rowIssues;explanations=$explanations;bodyFonts=$fontAudit;pdfGenerated=$false} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path (Split-Path $preview) 'word_layout_audit.json') -Encoding utf8
 $pages=$doc.ActiveWindow.Panes.Item(1).Pages
 for($i=1;$i -le $count;$i++) {
  $bytes=$pages.Item($i).EnhMetaFileBits
  $ms=New-Object System.IO.MemoryStream(,$bytes)
  $meta=[System.Drawing.Image]::FromStream($ms)
  $bmp=New-Object System.Drawing.Bitmap(1100,1556)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.Clear([System.Drawing.Color]::White)
  $g.DrawImage($meta,0,0,1100,1556)
  $bmp.Save((Join-Path $preview ('page-{0:d3}.png' -f $i)),[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$bmp.Dispose();$meta.Dispose();$ms.Dispose()
  if($i % 10 -eq 0){Write-Output "RENDERED=$i"}
 }
 Write-Output "COMPLETE=$preview"
} finally {if($null -ne $doc){$doc.Close(0)};$word.Quit();[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
