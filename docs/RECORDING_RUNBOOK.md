# LotLine recording runbook: from a cold machine to an error-free 3:45–3:55 video

This is the operational companion to `docs/demo_script.md`, which holds the words. This file covers the clicks, the checks and the recovery steps. Every step below was walked through in Chrome at 1280×800 against the offline app on 2026-09-27 00:00–00:15 ET. All five views, the unknown-PIN path, Benezet and Centre rendered with no errors.

## 0. One-time setup (with internet, before recording day)

```bash
cd the repository root            # or wherever the repo is cloned
git pull --ff-only origin main
curl -LsSf https://astral.sh/uv/install.sh | sh   # only if `uv` is missing
export PATH="$HOME/.local/bin:$PATH"
uv sync                                 # installs Python 3.12 + locked deps into .venv
uv run pytest -q; echo "exit=$?"        # expect: all passed, exit=0
uv run python -m evaluation.run         # regenerates docs/validation/results.md; expect exit 0
```

## 1. Pre-flight (10 minutes before each take)

1. **Close everything noisy.** Turn on Do Not Disturb (Control Center → Focus). Quit Slack, mail and other notifiers. Hide the Dock (⌥⌘D).
2. **Start the main recording app with live AI enabled:**
   ```bash
   cd the repository root && export PATH="$HOME/.local/bin:$PATH"
   uv run streamlit run app.py --server.port 8501
   ```
   Wait for `URL: http://localhost:8501`. Before recording, click the Centre record reader and one scripted Benezet question. Confirm the result says **live · verified**; if it falls back, keep the **cached · re-verified now** label visible and do not describe it as live.
3. **Set up the browser.** Open Chrome in a fresh guest or incognito window with no extensions in the toolbar. Resize the window to **1280×800**, either with a window-sizer tool or with this from Chrome's JS console: `window.resizeTo(1280, 800)`. Zoom must be 100% (⌘0).
4. **Load and warm up** (the first load computes all 96 records):
   - Open `http://localhost:8501` and wait until the funnel shows **96 / 77 / 63 / 14**.
   - Click through each view once (Parcel packet, then Benezet, Centre, Compare and Integrity), then click **Sale pipeline** again.
   - Reload the page (⌘R) so the take starts from a clean session.
5. **Open the two slides in separate tabs:** `docs/fallback/title-card.html` and `docs/fallback/pilot-slide.html`. Use File → Open File, or drag them into Chrome. Put the title card tab **first** and the app tab second.
6. **Recorder:** press ⌘⇧5, choose *Record Selected Portion*, and select exactly the Chrome content area. Under Options, pick the microphone and set Timer to None. Or use OBS if you prefer: a 1280×800 canvas, 30 fps, audio at 48 kHz.
7. **Keep the script open** on a second screen or on paper. Use `docs/demo_script.md`, and never read from the recording window.

## 2. Scene-by-scene click path (times match `docs/demo_script.md`)

| Scene | Time | Do this | Make sure the frame shows |
|---|---|---|---|
| 0 | 0:00–0:10 | Title-card tab | "AI Horizons 2026 AI for Housing Hackathon · Challenge 1 · Nibedita Biswal". **Mandatory**: the rules require the hackathon name and team up front |
| 1 | 0:10–0:28 | Switch to the app tab (⌃Tab). **Sale pipeline** is selected | Header snapshot dates and the blue decision-support banner stay in frame |
| 2 | 0:28–1:08 | Click **Parcel packet**, then **Centre Ave (10-S-5)**. Show **AI record reader**, then scroll to the real aerial + County outline | Cached, re-verified evidence; the January 2025 demolition/withdrawal quote; then the `unclear` bounded visual read and explicit "does not resolve" result. State that all 96 parcels work and that vision never decides |
| 3 | 1:08–1:42 | Continue through Centre's conflict banners, score card, zoning tile and first checks | Red **Critical conflict**, amber **Material conflict**, "Not scorable" with no component values; Assessment 1,672 sf · County GIS 4,305 sf · minimum 2,400 sf; PLI close-out and deed checks |
| 4 | 1:42–2:07 | Click **Sale pipeline** and move from the funnel to the triage board/map | 96 → 77 (77/77 PIN and price) → 63 + 14; chips **Advance 7 · Defer site 3 · Defer records 3 · Do not advance 1**; "Triage, not ranking" |
| 5 | 2:07–2:42 | Return to **Parcel packet**, select **Benezet St**, scroll to **Ask LotLine**. Ask the scripted two-family question, then the investment question | First answer uses a fixed frame, engine facts, cited code and Zoning Administrator route; second is a clear decline. If running offline, use verified fallback capture rather than pretending a live answer |
| 6 | 2:42–3:18 | Click **Integrity** and show both AI-delta cards | 150-parcel text-reader result and the 96/96 multimodal audit: current run 36 visual–record review flags and 45 abstentions; exact categories agreed 93/96 across two runs and the same 29 structure-routed records were flagged. Say these are discrepancy signals, not accuracy or site truth |
| 7 | 3:18–3:52 | Switch to the pilot-slide tab | Blinded next-study design, pilot metrics and limitations; closing thesis: AI reads, rules abstain, people resolve. Stop recording 1 second after the last word |

**Ask LotLine (scene 5).** The 12 scripted live questions were verified before recording. Use the live action only after a rehearsal with the recording key; otherwise insert the verified fallback capture and keep its offline/cached state visible. A rejection is a valid safety result—never retry until a preferred answer appears.

## 3. Words: say these, never those

Say: "advertised for the October 2 sale" · "apparent lower-discretion zoning path" · "no overlap in the checked screening layers" · "refuses to score" · "not a recommendation to buy" · "named human checks".

Never: "buildable" · "clear" or "safe" · "will be sold" · "best lot" · "accurate" or "accuracy" (about the conformance set) · "the GIS number is right" · any claim of partnership with the City, URA, PLB or PHFA (it's a *proposed* pilot).

## 4. Separate offline-proof clip

Stop the live server, then run `LOTLINE_OFFLINE=1 uv run --offline streamlit run app.py --server.port 8501`. Turn Wi-Fi off, load the pipeline and Centre packet, and capture the cached/re-verified label plus deterministic score abstention. `env -u` is not sufficient because the app loads the git-ignored `.env`; `LOTLINE_OFFLINE=1` is the explicit network gate.

## 4. Recovery (if something goes wrong mid-take)

| Symptom | Fix |
|---|---|
| Page shows grey skeleton blocks for more than 3 s | Wait. The first compute takes a few seconds. If it's still grey, reload (⌘R) and restart the scene |
| "Connection error" or a blank page | Streamlit stopped. Restart with the command in §1.2 and warm up again |
| Wrong parcel in the packet | Use the quick-pick buttons (Benezet / Centre / Michigan). Don't type PINs on camera |
| A view looks different from this runbook | Stop. Use the matching `docs/fallback/*.png` frame for that scene in the edit, and note it in the rehearsal log |
| Overran 5:00 or under 3:00 | Retake. Hard limits are 3:00–5:00; aim for 3:45–3:55 |

## 5. After recording

1. Watch the whole export once, start to finish, with sound. Check that the title card names the hackathon and the team, the counts match (96/77/63/14; 7/3/3/1), no forbidden words are spoken, and the runtime is 3:00–5:00.
2. Log the take in the **Rehearsal log** in `docs/demo_script.md`: date/time, runtime and notes. Two timed spoken rehearsals are required before the final take.
3. Upload the video as public or unlisted (YouTube or Vimeo) and open the link in a logged-out or incognito window to confirm it plays.
4. Make the GitHub repo **public** (Settings → General → Danger Zone → Change visibility) and confirm `https://github.com/nbiswal-star/lotline` loads logged out.
5. Fill in the form with `docs/SUBMISSION_PAYLOAD.md`. The team owner confirms the roster and attestation and submits before **Sun Sep 27, 23:59 ET**. Screenshot the confirmation.
