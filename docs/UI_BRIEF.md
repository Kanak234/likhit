# Likhit: UI and UX Brief

## Feel

It should feel like a calm desk with paper on it, not a dashboard. The background is a warm cream (`#f6f1e7`), panels are off-white, and text is a deep ink blue (`#1f2a44`). The one strong colour is a burnt orange (`#d9531e`) taken from the KP logo gradient, and it's used only for the two main actions: Read and Save. Everything else stays quiet.

## Layout

```
┌───────────────────────────────────────────────────────────────┐
│ [KP] Likhit                       status of engines  [Settings]│
│      Turn handwritten pages into a Word document               │
├──────────┬─────────────────────────┬───────────────────────────┤
│ PAGES    │ PHOTO                   │ TEXT      [Read this page]│
│ ✓ 1. ... │                         │ Read by ...               │
│ · 2. ... │     selected photo      │ ┌───────────────────────┐ │
│          │                         │ │ editable text          │ │
│          │                         │ └───────────────────────┘ │
│[+ Add]   │                         │ hint about [?]            │
│[↑][↓][Remove]                      │                           │
├──────────┴─────────────────────────┴───────────────────────────┤
│ Read with [Auto ▾] [Read handwriting] ▓▓▓░ status  □ photos [Save as Word] │
└───────────────────────────────────────────────────────────────┘
```

The three panels sit in a resizable split view, so the user can widen the photo or the text as needed. The bottom bar is packed first, so it never gets cut off in a small window.

## Main flow

Add photos → check the order → Read handwriting → fix anything highlighted → Save as Word → open it.

## States

| State | What the user sees |
|---|---|
| Empty | The photo area says "No pages yet" with a one-line hint. The text box is disabled. Read and Save are disabled. |
| Pages added, not read | List items show a dot (·). Text panel says "Not read yet". |
| Reading | Progress bar and "Reading 2 of 5: name". All buttons are disabled, so nothing changes under the worker. |
| Read | List items show a tick (✓). Text panel shows which engine read the page. `[?]` is highlighted yellow. |
| Page failed | One warning at the end listing each failed page and the reason. Other pages keep their text. |
| No engine | A dialog listing all three reasons and the fix for each. |
| Saved | "Saved to … Open it now?" |
| Status bar | Green when at least one method is ready, amber when none is. |

## Details that matter

- Words are plain and friendly: "Read handwriting", not "Run OCR pipeline".
- The API key field is masked, and a hint says it's stored only on this computer.
- Keyboard: Ctrl/Cmd + O, R, S.
- Each system gets its own UI font (Segoe UI, Helvetica Neue, DejaVu Sans).
- On high-DPI Windows screens, DPI awareness is switched on so text isn't blurry.
- The window and taskbar icon use the KP logo. The logo version with a darker orbit line is used on light backgrounds, because the original light-grey line disappears on cream or white.

## Accessibility

- All actions are real buttons, reachable with Tab.
- Text contrast (ink on cream) is well above 7:1.
- Status is shown with words ("Tesseract ✓", "No local model"), not colour alone.
