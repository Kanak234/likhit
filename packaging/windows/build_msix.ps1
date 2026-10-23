# Builds Likhit-<ver>.msix on Windows (CI or Kanak's Windows desktop):
#   pwsh packaging\windows\build_msix.ps1
# FLOW: icons → build_app.py (PyInstaller one-folder, Tesseract bundled)
#       → smoke test: Likhit.exe converts a generated image offline → MSIX → zip
$ErrorActionPreference = "Stop"
# CI visibility: any failure becomes a GitHub annotation (readable on the run page
# without signing in), including the last lines of output collected in $global:Tail.
$global:Tail = New-Object System.Collections.Generic.List[string]
function Run($step, [scriptblock]$cmd) {
  Write-Host "::group::$step"
  & $cmd 2>&1 | ForEach-Object { $l = "$_"; Write-Host $l; $global:Tail.Add($l); if ($global:Tail.Count -gt 25) { $global:Tail.RemoveAt(0) } }
  $code = $LASTEXITCODE
  Write-Host "::endgroup::"
  if ($code -ne 0) { throw "STEP FAILED: $step (exit $code)" }
}
trap {
  $msg = ($_ | Out-String) + "`n--- last output ---`n" + ($global:Tail -join "`n")
  Write-Host ("::error title=MSIX build failed::" + ($msg -replace "`r?`n", "%0A"))
  exit 1
}
# Identity values are in AppxManifest.xml (copied from Partner Center → Product identity).
# Native programs (python, makeappx) do not stop the script on failure by
# themselves — Check stops with the step name so the CI log shows the real cause.
function Check($step) { if ($LASTEXITCODE -ne 0) { throw "STEP FAILED: $step (exit $LASTEXITCODE)" } }
$root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $root
$ver = (python -c "import likhit;print(likhit.__version__)").Trim()
$layout = Join-Path $root "dist\msix-layout"
Remove-Item -Recurse -Force $layout -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$layout\Assets" | Out-Null
Run "icons" { python packaging\windows\make_icons.py assets\icon\likhit-icon-512.png "$layout\Assets" }
Run "PyInstaller build" { python build_app.py }
if (-not (Test-Path dist\Likhit\Likhit.exe)) { Get-ChildItem dist -Recurse -Depth 1; throw "STEP FAILED: dist\Likhit\Likhit.exe not produced" }
# real smoke test: printed text image → offline OCR (bundled Tesseract) → .docx
python -c "from PIL import Image,ImageDraw,ImageFont;i=Image.new('RGB',(900,200),'white');d=ImageDraw.Draw(i);d.text((30,60),'LIKHIT WINDOWS TEST',fill='black',font=ImageFont.load_default(size=56));i.save('smoke.png')"; Check "smoke image"
$p = Start-Process -FilePath dist\Likhit\Likhit.exe -ArgumentList "smoke.png","-o","smoke.docx","--mode","offline" -Wait -PassThru
if ($p.ExitCode -ne 0 -or -not (Test-Path smoke.docx)) { Get-Content "$HOME\likhit-cli.log" -Tail 40 -ErrorAction SilentlyContinue; throw "Likhit.exe offline conversion failed (exit $($p.ExitCode))" }
python -c "import docx;t=' '.join(p.text for p in docx.Document('smoke.docx').paragraphs);print('OCR text:',t);assert 'LIKHIT' in t.upper()"; Check "OCR result check"
Copy-Item -Recurse dist\Likhit "$layout\Likhit"
(Get-Content packaging\windows\AppxManifest.xml -Raw).Replace("__VERSION__", "$ver.0") | Set-Content "$layout\AppxManifest.xml" -Encoding utf8
# MSIX rejects some file names (makeappx error 0x8007007b). Drop NSIS/7z leftovers
# whose names start with '$', then report any remaining name outside the safe set.
# python-docx ships an unpacked copy of its template (default-docx-template/ with
# _rels/ and [Content_Types].xml). "_rels" is a RESERVED folder name in MSIX/OPC
# packages (makeappx 0x8007007b). The app only uses templates/default.docx, so the
# unpacked copy is removed from the package (tests pass without it).
Get-ChildItem $layout -Recurse -Directory -Force | Where-Object { $_.Name -eq 'default-docx-template' } | Remove-Item -Recurse -Force
Get-ChildItem $layout -Recurse -Directory -Force | Where-Object { $_.Name -eq '_rels' } | Remove-Item -Recurse -Force
# '[' and ']' are not allowed in MSIX/OPC part names — 7-Zip leaves "[NSIS].nsi"
# when it unpacks the Tesseract installer; it is only the installer script.
Get-ChildItem $layout -Recurse -Force | Where-Object { $_.Name -like '$*' -or $_.Name -match '[\[\]%#]' } | ForEach-Object { Write-Host "removing from package: $($_.FullName)"; Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
$bad = Get-ChildItem $layout -Recurse -Force | Where-Object { $_.Name -notmatch '^[A-Za-z0-9_.\- ()+~@,=]+$' -or $_.Name -match '[. ]$' -or $_.Name -match '^(CON|PRN|AUX|NUL|COM\d|LPT\d)(\..*)?$' }
if ($bad) { Write-Host ("::warning title=Unusual file names in package::" + (($bad | ForEach-Object { $_.FullName.Substring($layout.Length) }) -join "%0A")) }
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" | Sort-Object FullName -Descending | Select-Object -First 1
& $makeappx.FullName pack /d $layout /p "dist\Likhit-$ver.msix" /o | Out-Null
if ($LASTEXITCODE -ne 0) {
  # Diagnose: pack each folder of the app separately to find the one makeappx rejects.
  $bad = @()
  $dirs = @(Get-ChildItem "$layout\Likhit" -Directory) + @(Get-ChildItem "$layout\Likhit\_internal" -Directory)
  foreach ($d in $dirs) {
    $probe = Join-Path $env:RUNNER_TEMP ("probe-" + $d.Name); Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $probe | Out-Null
    Copy-Item "$layout\AppxManifest.xml", "$layout\Assets" $probe -Recurse
    Copy-Item $d.FullName (Join-Path $probe $d.Name) -Recurse
    & $makeappx.FullName pack /d $probe /p "$probe.msix" /o /nv 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      $files = Get-ChildItem $d.FullName -Recurse -File | Select-Object -First 400
      $badFile = $null
      foreach ($f in $files) {  # narrow to the first single file that fails
        $p2 = "$probe-f"; Remove-Item -Recurse -Force $p2 -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force $p2 | Out-Null
        Copy-Item "$layout\AppxManifest.xml", "$layout\Assets" $p2 -Recurse; Copy-Item $f.FullName $p2
        & $makeappx.FullName pack /d $p2 /p "$p2.msix" /o /nv 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $badFile = $f.FullName.Substring($layout.Length); break }
      }
      $bad += "$($d.FullName.Substring($layout.Length))  first bad file: $badFile"
    }
  }
  throw ("makeappx rejected these folders:`n" + ($bad -join "`n"))
}
Compress-Archive -Path dist\Likhit -DestinationPath "dist\Likhit-$ver-portable.zip" -Force
Get-ChildItem dist\*.msix, dist\*.zip | ForEach-Object { "{0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB) }
