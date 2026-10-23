# Downloads Tesseract OCR for Windows (UB Mannheim build, Apache-2.0) and extracts it
# into <repo>/tesseract so build_app.py bundles it inside Likhit.exe's folder.
# WHY: "Without AI" mode needs tesseract.exe; students should not install it by hand.
# Records version + SHA256 in tesseract/MANIFEST.json (provenance for the Store review).
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$gh = @{ "User-Agent"="likhit-ci"; "Authorization"="Bearer $env:GITHUB_TOKEN" }
$rel = Invoke-RestMethod "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" -Headers $gh
$asset = $rel.assets | Where-Object { $_.name -match 'w64-setup.*\.exe$' } | Select-Object -First 1
if (-not $asset) { throw "No Windows installer in UB-Mannheim/tesseract latest release" }
$exe = Join-Path $env:RUNNER_TEMP $asset.name
Invoke-WebRequest $asset.browser_download_url -OutFile $exe
$sha = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
if ($asset.digest -and ($asset.digest -replace '^sha256:','') -ne $sha) { throw "checksum mismatch" }
$dest = Join-Path $root "tesseract"
& 7z x $exe "-o$dest" -y | Out-Null          # NSIS installer → plain folder
if (-not (Test-Path "$dest\tesseract.exe")) { throw "tesseract.exe not found after extraction" }
Remove-Item -Recurse -Force "$dest\`$PLUGINSDIR" -ErrorAction SilentlyContinue
@{ name="tesseract-ub-mannheim"; version=$rel.tag_name; url=$asset.browser_download_url; sha256=$sha } |
  ConvertTo-Json | Set-Content "$dest\MANIFEST.json" -Encoding utf8
& "$dest\tesseract.exe" --version
