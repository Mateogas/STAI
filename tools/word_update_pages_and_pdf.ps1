param(
    [Parameter(Mandatory=$true)][string]$DocxPath,
    [Parameter(Mandatory=$true)][string]$PageMapPath,
    [string]$PdfPath = ""
)

$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $fullDocx = (Resolve-Path -LiteralPath $DocxPath).Path
    $doc = $word.Documents.Open($fullDocx)
    $doc.Fields.Update() | Out-Null

    $map = [ordered]@{}
    foreach ($p in $doc.Paragraphs) {
        $text = $p.Range.Text
        $text = $text -replace "[`r`a]", ""
        $text = $text.Trim()
        if ($p.OutlineLevel -eq 1 -and $text -and $text -ne "Table of Contents") {
            $page = $p.Range.Information(3)
            $map[$text] = [string]$page
        }
    }

    $json = $map | ConvertTo-Json -Depth 3
    Set-Content -LiteralPath $PageMapPath -Value $json -Encoding UTF8

    if ($PdfPath -and $PdfPath.Trim().Length -gt 0) {
        $fullPdf = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PdfPath)
        $doc.ExportAsFixedFormat($fullPdf, 17)
    }

    $doc.Save()
    $doc.Close($false)
}
finally {
    $word.Quit()
}
