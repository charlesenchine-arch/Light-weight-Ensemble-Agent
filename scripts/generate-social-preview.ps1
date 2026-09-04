param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "..\assets\social-preview.png")
)

Add-Type -AssemblyName System.Drawing

$width = 1280
$height = 640
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

try {
    $background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        [System.Drawing.Rectangle]::new(0, 0, $width, $height),
        [System.Drawing.ColorTranslator]::FromHtml("#090D18"),
        [System.Drawing.ColorTranslator]::FromHtml("#171C31"),
        22
    )
    $graphics.FillRectangle($background, 0, 0, $width, $height)

    $glow = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(35, 104, 86, 255))
    $graphics.FillEllipse($glow, 760, -260, 760, 760)

    $panelBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(210, 14, 20, 36))
    $panelPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#303B61"), 2)
    $panel = [System.Drawing.Rectangle]::new(610, 92, 570, 456)
    $graphics.FillRectangle($panelBrush, $panel)
    $graphics.DrawRectangle($panelPen, $panel)

    $accent = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#8B7CFF"))
    $white = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#F6F7FF"))
    $muted = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#A9B1CB"))
    $green = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#58D6A9"))
    $cyan = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#63C5FF"))

    $brandFont = [System.Drawing.Font]::new("Segoe UI", 82, [System.Drawing.FontStyle]::Bold)
    $titleFont = [System.Drawing.Font]::new("Segoe UI", 34, [System.Drawing.FontStyle]::Bold)
    $bodyFont = [System.Drawing.Font]::new("Segoe UI", 24, [System.Drawing.FontStyle]::Regular)
    $smallFont = [System.Drawing.Font]::new("Consolas", 18, [System.Drawing.FontStyle]::Regular)
    $monoBold = [System.Drawing.Font]::new("Consolas", 20, [System.Drawing.FontStyle]::Bold)
    $microFont = [System.Drawing.Font]::new("Consolas", 14, [System.Drawing.FontStyle]::Regular)

    $graphics.DrawString("LEA", $brandFont, $white, 86, 82)
    $graphics.FillRectangle($accent, 92, 194, 146, 8)
    $graphics.DrawString("Light-weight", $titleFont, $white, 88, 238)
    $graphics.DrawString("Ensemble Agent", $titleFont, $white, 88, 284)
    $graphics.DrawString("Spend intelligence", $bodyFont, $muted, 92, 375)
    $graphics.DrawString("where it matters.", $bodyFont, $muted, 92, 414)
    $graphics.DrawString("budget-native  •  multi-model  •  local-first", $microFont, $accent, 92, 504)

    $graphics.DrawString("$ lea route --budget 10cny", $monoBold, $white, 650, 126)
    $graphics.DrawString("plan", $smallFont, $accent, 654, 206)
    $graphics.DrawString("grok-4.6", $smallFont, $white, 790, 206)
    $graphics.DrawString("code", $smallFont, $cyan, 654, 261)
    $graphics.DrawString("deepseek-v4-flash", $smallFont, $white, 790, 261)
    $graphics.DrawString("review", $smallFont, $green, 654, 316)
    $graphics.DrawString("claude-sonnet-5", $smallFont, $white, 790, 316)
    $graphics.DrawString("fix", $smallFont, $cyan, 654, 371)
    $graphics.DrawString("deepseek-v4-flash", $smallFont, $white, 790, 371)
    $graphics.DrawString("estimated", $smallFont, $muted, 654, 452)
    $graphics.DrawString('$0.081', $monoBold, $green, 1000, 448)
    $graphics.DrawString("hard budget guard  •  independent review", $microFont, $muted, 654, 500)

    $target = [System.IO.Path]::GetFullPath($OutputPath)
    $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $target
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
