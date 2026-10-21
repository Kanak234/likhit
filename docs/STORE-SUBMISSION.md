# Store Submission Guide for Likhit

This guide covers submitting **Likhit** to the **Snap Store** and **Flathub** using web UIs only — no CLI required beyond the initial setup done in this repo.

---

## App Identity

- **App ID:** `io.github.Kanak234.Likhit` (Flathub requires `io.github.<user>.<app>` for GitHub-hosted apps)
- **Snap name:** `likhit` (to be registered on snapcraft.io)
- **Developer:** Kanak Prabhakar (@Kanak234 on GitHub)
- **Homepage:** https://github.com/Kanak234/likhit
- **License:** MIT (placeholder — add a LICENSE file to the repo root with the actual license)
- **Current version:** 1.1.0 (tagged 2026-10-21)

---

## 1. Snap Store Submission (via Web UI)

### Prerequisites (one-time)
1. Create a **Snapcraft account** at https://snapcraft.io/account
2. Register the snap name **`likhit`**:
   - Go to https://snapcraft.io/register-snap
   - Enter `likhit` → click **Register**
   - This reserves the name for you.

### Build & Release via GitHub Integration (no local `snapcraft` needed)
1. Go to https://snapcraft.io/build
2. Click **“Add a new snap”** → choose **“Build from GitHub”**
3. Connect your GitHub account if prompted.
4. Select repository: **`Kanak234/likhit`**
5. Branch: **`store-packaging`** (this branch contains `snap/snapcraft.yaml`)
6. Click **“Build”** — Snapcraft will build on their infrastructure for amd64 & arm64.
7. When build succeeds, go to the **Releases** tab → click **“Release”** → choose **stable** channel.

### Store Listing Page (fill in on https://snapcraft.io/snaps/likhit)
| Field | What to enter |
|-------|---------------|
| **Summary** | Turn handwritten pages into a Word document |
| **Description** | Copy the long description from `packaging/io.github.Kanak234.Likhit.metainfo.xml` (the `<description>` section). |
| **Icon** | Upload `assets/icon/likhit-icon-512.png` (512×512 PNG). |
| **Screenshots** | Upload **at least 2** screenshots (see **TODO** below). Suggested: main window with recognized text; Settings window showing the three modes. |
| **License** | MIT (or whatever you put in the LICENSE file). |
| **Contact** | Your GitHub profile: https://github.com/Kanak234 |
| **Website** | https://github.com/Kanak234/likhit |
| **Categories** | Office, Utilities |
| **Keywords** | handwriting, OCR, Word, docx |

### Confinement & Plugs (already declared in `snapcraft.yaml`)
- `strict` confinement
- Plugs: `home`, `removable-media`, `network`, `desktop`, `desktop-legacy`
- The `gnome` extension handles `x11`, `wayland`, `opengl` automatically.

### What reviewers may ask for
- If the build fails on arm64: check that all Python wheels are available for aarch64 (most are; `onnxruntime` has platform wheels).
- If `tesseract-ocr` language data is missing: the `stage-packages` include `tesseract-ocr-eng`; for Hindi add `tesseract-ocr-hin` to `stage-packages` and rebuild.

---

## 2. Flathub Submission (via Web UI)

### Prerequisites (one-time)
1. Fork **Flathub's repo** in your browser:
   - Go to https://github.com/flathub/flathub → click **Fork** → your account.
2. Clone your fork locally (optional, for testing) or do everything in the browser.

### Prepare the Manifest Files
The following files are already in this repo under `packaging/flatpak/`:
- `io.github.Kanak234.Likhit.yml` — main manifest
- `python-deps.json` — Python dependencies (generated with `flatpak-pip-generator`)
- `io.github.Kanak234.Likhit.desktop` — desktop entry
- `io.github.Kanak234.Likhit.metainfo.xml` — AppStream metadata

### Open the PR (entirely in the browser)
1. In your fork (https://github.com/`<your-user>`/flathub), create a new branch from **`new-pr`** (not `main`!):
   - Go to **Code** → **Branch: new-pr** → click branch dropdown → type `add-likhit` → **Create branch: add-likhit from new-pr**
2. In the branch, create folder `io.github.Kanak234.Likhit/` and upload these 4 files:
   - `io.github.Kanak234.Likhit.yml`
   - `python-deps.json`
   - `io.github.Kanak234.Likhit.desktop`
   - `io.github.Kanak234.Likhit.metainfo.xml`
3. Commit → **Open a pull request** against `flathub/flathub` **base: `new-pr`**
   - Title: **`Add io.github.Kanak234.Likhit`**
   - Description: Brief summary of the app (handwriting → Word, three reading modes, offline-first).

### Domain / ID Verification (required for `io.github` IDs)
Flathub requires proof you control the GitHub namespace:
1. In the PR, a bot will ask you to verify ownership.
2. Add a **GitHub Pages site** or a **TXT record** to `kanak234.github.io` (or create the repo `Kanak234/kanak234.github.io` and add a file).
3. Easiest: create a file `flathub-verification.txt` in a public repo under your account (e.g., `Kanak234/flathub-verification`) with content:
   ```
   io.github.Kanak234.Likhit
   ```
4. Link that file in the PR comment. The bot will verify and approve.

### What reviewers usually ask for
| Issue | Fix |
|-------|-----|
| **Missing LICENSE file** | Add a `LICENSE` file to your app repo root (MIT, GPL-3.0, etc.) and update `project_license` in metainfo. |
| **Screenshots missing** | Replace the placeholder URLs in `metainfo.xml` with real screenshots hosted on GitHub (raw.githubusercontent.com) or elsewhere. |
| **`filesystem=home` too broad** | Justify in PR: “Users store handwritten notes anywhere in home; file dialog must browse freely. `xdg-documents` + `xdg-download` is insufficient.” |
| **Tesseract traineddata not found** | The manifest downloads `eng.traineddata` and `osd.traineddata` at build time. Verify the URLs still work. |
| **Python version mismatch** | The manifest uses `org.freedesktop.Platform//25.08` (Python 3.12). If your `requirements.txt` needs newer Python, bump the runtime version. |
| **Build fails on aarch64** | Ensure all Python deps have aarch64 wheels (most do; `onnxruntime` does). |

### After merge
- Flathub's CI builds and publishes to the **Beta** channel first.
- Test the Beta flatpak: `flatpak install --user --from https://flathub.org/repo/appstream/io.github.Kanak234.Likhit.flatpakref`
- Once verified, Flathub maintainers move it to **Stable**.

---

## 3. Screenshots (Required for Both Stores)

**TODO (manual):** Create and upload at least 2 screenshots per store.
- **Screenshot 1:** Main window with a handwritten photo loaded and recognized text visible.
- **Screenshot 2:** Settings window showing Cloud AI / Local LLM / Offline OCR options.
- **Optional:** The generated Word document open in LibreOffice/Word.

Host screenshots in the app repo (e.g., `assets/screenshots/main-window.png`, `assets/screenshots/settings.png`) and update the `metainfo.xml` URLs to point to `https://raw.githubusercontent.com/Kanak234/likhit/main/assets/screenshots/...`.

---

## 4. Checklist Before Submitting

- [ ] Add a `LICENSE` file to the repo root (MIT recommended).
- [ ] Create `assets/screenshots/` with 2+ real screenshots.
- [ ] Update `packaging/io.github.Kanak234.Likhit.metainfo.xml` screenshot URLs.
- [ ] Verify `project_license` in metainfo matches the LICENSE file SPDX ID.
- [ ] Register snap name `likhit` on snapcraft.io.
- [ ] Fork flathub/flathub and prepare PR from `new-pr` branch.
- [ ] Complete Flathub domain verification for `io.github.Kanak234`.

---

## 5. Useful Links

- Snapcraft build service: https://snapcraft.io/build
- Snap listing: https://snapcraft.io/snaps/likhit
- Flathub new PR process: https://github.com/flathub/flathub/blob/main/docs/for-app-authors/requirements.md
- Flathub manifest guidelines: https://flatpak-builder-flatpak.readthedocs.io/
- AppStream metadata spec: https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html