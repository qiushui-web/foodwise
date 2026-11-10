$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$word=New-Object -ComObject Word.Application
$word.Visible=$false;$word.DisplayAlerts=0
$doc=$null
try {
 $doc=$word.Documents.Open('E:\食刻有数\计划书\计划书pro10.docx',$false,$true)
 $doc.ActiveWindow.View.Type=3;$doc.Repaginate()
 $count=$doc.ComputeStatistics(2);Write-Output "TEMPLATE_PAGES=$count"
 $heads=@();foreach($p in $doc.Paragraphs){if($p.OutlineLevel -le 2){$heads+=@{text=$p.Range.Text.Trim();page=$p.Range.Information(3)}}}
 $heads|ConvertTo-Json -Depth 4|Set-Content 'E:\食刻有数\项目代码\docs\plan_20261110_review\template_headings.json' -Encoding utf8
 $ps=$doc.ActiveWindow.Panes.Item(1).Pages
 foreach($i in @(1,2,4,5,6,10,15,20,25,35,45,55)) {
  if($i -gt $count){continue}
  $bytes=$ps.Item($i).EnhMetaFileBits;$ms=New-Object System.IO.MemoryStream(,$bytes);$meta=[System.Drawing.Image]::FromStream($ms)
  $bmp=New-Object System.Drawing.Bitmap(1100,1556);$g=[System.Drawing.Graphics]::FromImage($bmp);$g.Clear([System.Drawing.Color]::White);$g.DrawImage($meta,0,0,1100,1556)
  $bmp.Save(('E:\食刻有数\项目代码\docs\plan_20261110_review\template-{0:d3}.png' -f $i),[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$bmp.Dispose();$meta.Dispose();$ms.Dispose()
 }
 Write-Output 'READ_ONLY_PREVIEW_COMPLETE'
}finally{if($null -ne $doc){$doc.Close(0)};$word.Quit();[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
