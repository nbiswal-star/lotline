# LotLine recording runbook: from a cold machine to an error-free 3:45–3:55 video

This is the operational companion to `docs/demo_script.md`, which holds the words. This file covers the clicks, the checks and the recovery steps. Every step below was walked through in Chrome at 1280×800 against the offline app on 2026-09-27 00:00–00:15 ET. All five views, the unknown-PIN path, Benezet and Centre rendered with no errors.

## 0. One-time setup (with internet, before recording day)

```bash
cd ~/Downloads/lotline-main            # or wherever the repo is cloned
git pull --ff-only origin main
curl -LsSf https://astral.sh/uv/install.sh | sh   # only if `uv` is missing
export PATH="$HOME/.local/bin:$PATH"
uv sync                                 # installs Python 3.12 + locked deps into .venv
uv run pytest -q; echo "exit=$?"        # expect: all passed, exit=0
uv run python -m evaluation.run         # regenerates docs/validation/results.md; expect exit 0
```

## 1. Pre-flight (10 minutes before each take)

1. **Close everything noisy.** Turn on Do Not Disturb (Control Center → Focus). Quit Slack, mail and other notifiers. Hide the Dock (⌥⌘D).
2. **Start the app offline, with no credentials in its environment:**
   ```bash
   cd ~/Downloads/lotline-main && export PATH="$HOME/.local/bin:$PATH"
   env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN uv run --offline streamlit run app.py --server.port 8501
   ```
   Wait for `URL: http://localhost:8501`. To prove the demo doesn't depend on the network, you can turn Wi-Fi off now. The app keeps working.
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
| 1 | 0:10–0:30 | Switch to the app tab (⌃Tab). **Sale pipeline** is selected | Header snapshot dates and the blue decision-support banner stay in frame |
| 2 | 0:30–0:50 | Point the cursor at 96 → 77 (PIN match 77/77 · price check 77/77) → 63 → 14. Scroll down 5 ticks to the **Triage board** | Outcome chips **Advance 7 · Defer site 3 · Defer records 3 · Do not advance 1**. Hover "Triage, not ranking" |
| 3 | 0:50–1:40 | Click **Parcel packet**, then the **Benezet St (131-N-31)** button. Pause on the score card, then scroll slowly through the four tiles to **Next checks: who resolves what** | "5-6 of 6"; components use 2 · dimensional 1-2 · environment 2; Evidence 5/5; "Before incurring costs" check; the corner check routed to a licensed surveyor / County plat. **Do not** open Saline or Kemper |
| 4 | 1:40–2:35 | Scroll to top, then click **Centre Ave (10-S-5)** | Red **Critical conflict** banner, amber **Material conflict** banner, "Not scorable" with no component values. Scroll to the Zoning tile line "Lot area (both sources): Assessment 1,672 sf · County GIS 4,305 sf · district minimum 2,400 sf". Scroll to **Next checks** and show the site-condition, deed and §921.04.A checks. Optionally open **Provenance: every fact behind this packet** for 2–3 seconds |
| 5 | 2:35–2:55 | Click **Compare** | Selectors read Benezet vs Michigan (15-S-66). Michigan: "3-4 of 6: Conditional", principal barrier "terrain and undermining screening overlaps", next check "slope and geotechnical review". Blue "What explains the difference" box |
| 6 | 2:55–3:35 | Click **Integrity** | "10/10 cases passed · no network needed"; the two PASS red-team blocks (conflict-resolution draft rejected; injection: engine unchanged, 5 of 5 injection drafts rejected). Then click **Parcel packet**, then **Benezet**, and scroll to **Screening memo**: "SHOWING: Deterministic cited memo · Claim checker: 0 violations" |
| 7 | 3:35–3:55 | Switch to the pilot-slide tab | Real / approximate / synthetic; pilot plan; the closing line "Every packet ends in a named next check, not just a score." Stop recording 1 second after the last word |

**Claude button (scene 6).** Click **Assemble with Claude (claim-checked)** on camera only if `ANTHROPIC_API_KEY` is set, and only after you have rehearsed it with that key and both Benezet and Centre came back *accepted*. Otherwise don't click it. The script's offline line ("On this offline run, the cited deterministic memo is shown") is the default. If you do click it and it falls back, keep going: the fallback is the designed behavior.

## 3. Words: say these, never those

Say: "advertised for the October 2 sale" · "apparent lower-discretion zoning path" · "no overlap in the checked screening layers" · "refuses to score" · "not a recommendation to buy" · "named human checks".

Never: "buildable" · "clear" or "safe" · "will be sold" · "best lot" · "accurate" or "accuracy" (about the conformance set) · "the GIS number is right" · any claim of partnership with the City, URA, PLB or PHFA (it's a *proposed* pilot).

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
4. Make the GitHub repo **public** (Settings → General → Danger Zone → Change visibility) and confirm `https://github.com/anitksahu/lotline` loads logged out.
5. Fill in the form with `docs/SUBMISSION_PAYLOAD.md`. The team owner confirms the roster and attestation and submits before **Sun Sep 27, 23:59 ET**. Screenshot the confirmation.
