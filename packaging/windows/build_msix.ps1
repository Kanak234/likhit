# Builds Likhit-<ver>.msix on Windows (CI or Kanak's Windows desktop):
#   pwsh packaging\windows\build_msix.ps1
# FLOW: icons → build_app.py (PyInstaller one-folder, Tesseract bundled)
#       → smoke test: Likhit.exe converts a generated image offline → MSIX → zip
$ErrorActionPreference = "Stop"
# Partner Center → Product identity values come from GitHub repo variables
# (MSIX_IDENTITY_NAME, MSIX_PUBLISHER, MSIX_PUBLISHER_DISPLAY) — never guessed.
foreach ($v in "MSIX_IDENTITY_NAME","MSIX_PUBLISHER","MSIX_PUBLISHER_DISPLAY") {
  if (-not (Get-Item "env:$v" -ErrorAction SilentlyContinue)) { throw "Set repo variable $v (Partner Center → Product identity)" }
}
$root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $root
$ver = (python -c "import likhit;print(likhit.__version__)").Trim()
$layout = Join-Path $root "dist\msix-layout"
Remove-Item -Recurse -Force $layout -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$layout\Assets" | Out-Null
python packaging\windows\make_icons.py assets\icon\likhit-icon-512.png "$layout\Assets"
python build_app.py
# real smoke test: printed text image → offline OCR (bundled Tesseract) → .docx
python -c "from PIL import Image,ImageDraw,ImageFont;i=Image.new('RGB',(900,200),'white');d=ImageDraw.Draw(i);d.text((30,60),'LIKHIT WINDOWS TEST',fill='black',font=ImageFont.load_default(size=56));i.save('smoke.png')"
$p = Start-Process -FilePath dist\Likhit\Likhit.exe -ArgumentList "smoke.png","-o","smoke.docx","--mode","offline" -Wait -PassThru
if ($p.ExitCode -ne 0 -or -not (Test-Path smoke.docx)) { throw "Likhit.exe offline conversion failed (exit $($p.ExitCode))" }
python -c "import docx;t=' '.join(p.text for p in docx.Document('smoke.docx').paragraphs);print('OCR text:',t);assert 'LIKHIT' in t.upper()"
Copy-Item -Recurse dist\Likhit "$layout\Likhit"
(Get-Content packaging\windows\AppxManifest.xml -Raw).Replace("__VERSION__", "$ver.0").Replace("__PARTNER_CENTER_IDENTITY_NAME__", $env:MSIX_IDENTITY_NAME).Replace("__PARTNER_CENTER_PUBLISHER_CN__", $env:MSIX_PUBLISHER).Replace("__PUBLISHER_DISPLAY_NAME__", $env:MSIX_PUBLISHER_DISPLAY) | Set-Content "$layout\AppxManifest.xml" -Encoding utf8
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" | Sort-Object FullName -Descending | Select-Object -First 1
& $makeappx.FullName pack /d $layout /p "dist\Likhit-$ver.msix" /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed" }
Compress-Archive -Path dist\Likhit -DestinationPath "dist\Likhit-$ver-portable.zip" -Force
Get-ChildItem dist\*.msix, dist\*.zip | ForEach-Object { "{0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB) }
