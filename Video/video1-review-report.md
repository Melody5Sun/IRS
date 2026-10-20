# Final review: promo.mp4 (IT CareerPilot promo)

Reviewer: independent, clean context. Input: `out/promo.mp4` (1920x1080, 30 fps, 6:55.9, AAC 48 kHz stereo, BGM + SFX, no narration).
Evidence frames are in `out/review/` (`fMMSS.png` = full frame at that timecode; `strip-*.png` = per-second or 0.2 s tiles).
Note: `sheet-01..04.png` look offset by about 5 s from their nominal 0:00/5 s grid, so every timecode below comes from frames I extracted myself.

## Pass/fail by checklist area

| Area | Result | Notes |
|---|---|---|
| P product goal (positioning, no false claims) | PASS with remark | Positioning is clear. The VO claims "Limited Match", which is never on screen (issue 4) |
| F feature completeness | PASS | Every pillar and every demo step in the script appears in order |
| B storyboard / VO anchor fit | PARTIAL | Most anchors land on the right visual. Mismatches at 2:47 (Limited Match), 3:06 (go↔Python in focus), 2:06 (history shows only one file) and 3:42 (comparison is not visibly different) |
| V visual direction (paper/ink/accent, Cormorant + Inter, calm motion) | PASS | Palette and type are consistent. No bounce. Tags are lower-left as specified |
| Q visual technical quality | FAIL | Black strip on the bottom edge, spotlight window cuts the gap labels, tailored-draft column cropped, demo text small in wide shots |
| D data safety | FAIL | The JD artefact "Before that, Clay led the product and design teams for Google Workspace." is sharp and readable at about 3:29.2–3:29.6 |
| R pacing | PARTIAL | The gaps and comparison stretch (3:30–3:56) is long, low-contrast and nearly static; the list scan at 2:55–3:01 is quick |
| A audio | FAIL | BGM fades to digital silence at 3:40–3:56 and restarts cold at 3:56. The end fade itself is fine |

Audio measurements: integrated loudness -19.8 LUFS, LRA 7.7 LU, true max -4.6 dB, mean -21.9 dB. `silencedetect` (-50 dB, 1 s) finds one silence, **3:48.6–3:56.5 (7.9 s)**. The per-second RMS falls from -24 dB at 3:20 to -inf at about 3:54–3:56, then jumps back to -35/-29 dB. The end fade (about 6:53→6:55.9, -inf on the last frame) is fine.

## Issues

### Must-fix

1. **BGM drops out in the middle of the key segment (3:20–3:56).**
   Evidence: RMS per 5 s is -22 dB at 3:15, -28.9 at 3:25, -36 at 3:35, -44 at 3:40, -55 at 3:45 and -72 at 3:50, with digital silence at 3:54–3:55 and a restart at 3:56. `silencedetect` gives 228.6–236.5 s.
   Cause: `src/Main.tsx` loops `bgm-your-breath.mp3` (236.08 s) twice back to back (`BGM_LEN = 236*FPS`). The track's own fade-out tail and silent end therefore play during the comparison VO (3:42.6–3:58), and the second copy restarts from its intro.
   Fix: loop on a musical phrase before the track's fade (for example around 3:20–3:30 of the source) and use a 2–4 s crossfade between two overlapping `<Audio>` copies. A simpler option is to trim the tail with `startFrom`/`endAt` and crossfade. Place the seam on a section boundary, ideally the cut to Tailor at about 4:03.

2. **The JD-parsing artefact is clearly readable at 3:29.2–3:29.6.**
   Evidence: `f03294-clay-crop.png` and `strip-0328-fine.png` (row 2). The Experience Gap row shows "Before that, Clay led the product and design teams for Google Workspace." in focus, and the Recommended next step paragraph next to it (also in focus at about 3:29.2) repeats "...design teams for Google Workspace". The same sentence is semi-legible under the veil at 3:10 and 3:17 (`f0310.png`, `f0317.png`, bottom-right).
   Fix: during the scroll into Gaps (about 3:28.8–3:30), keep the veil over the lower gap rows and the next-step panel, or cut that scroll so the camera lands directly on Transferable/Hard Gap. Raise the veil blur from its current level, where words can still be made out at 1080p, to one where no letters are legible, or add a solid paper-coloured mask over the Experience Gap rows.

3. **The spotlight window cuts the very labels the VO is about (3:30–3:42).**
   Evidence: `f0333.png`. The sharp area starts at about x=634, so the tags "Transferable" and "Hard Gap" and the first letters of each skill ("mach|ne learning", "analy|tics", "ab te|sting", "s|kill. Prioritize") are blurred. The VO at 3:29.7 is "what is transferable, what is a hard gap".
   Fix: move the spotlight left edge to about x=430 (left of the tag column, `cams.ts`/`SPOTS.match`) and lighten the veil wash. The whole frame currently looks greyed out.

### Should-fix

4. **"Limited Match" is never shown.** VO at 2:47.2: "Highly Recommended, Recommended, or Limited Match". Evidence: `strip-0246.png` and `f0257.png`. The list scan at 2:55–3:01 shows only Highly Recommended and Recommended on page 1.
   Fix: show page 2 or a red Limited Match card briefly, or drop "or Limited Match" from the VO.

5. **The weak evidence go ↔ Python (10%) is the in-focus first row at 3:06–3:12**, exactly while the VO says "The job asks for Python — here is Python". Evidence: `f0310.png` (top row) and `f0305.png`. The script itself warns not to dwell on it.
   Fix: start the spotlight at the python ↔ Python (100%) row and then jump to react ↔ Vue 3, or veil the go row.

6. **The upload-history beat does not support its VO (2:06–2:14).** Evidence: `f0210.png`. The history holds a single file ("1 files"). The push-in crops the left of the list ("oad history", "gentDeveloper_EN.pdf") and the right ("Preview" is cut and "Use this version" is off-frame). The VO says "an earlier version is always one click away".
   Fix: re-record with two or more uploads, or reframe to show the full row with Preview and Use this version. Or soften the VO to "Every upload is kept in the history."

7. **The comparison role does not visibly differ (3:44–3:56).** Evidence: `strip-0340.png`. AppLovin is shown in a wide, small-text frame. Its gaps are all "Transferable" (mongodb, postgresql, kafka, android, swift, kotlin), and the frame barely moves for about 8 s, during the music silence from issue 1. The VO claims "different evidence, different gaps — you can see exactly why it sits lower".
   Fix: push in on the AppLovin gaps, put the spotlight on the absent Hard Gap / weaker confidence values, or cut 3–4 s.

8. **Thin black strip, 3–5 px, along the bottom edge in rest-state demo frames.** Evidence: bottom-row luma ≈16–17 against ≈223 paper at 1:40, 1:47, 2:03, 2:57, 3:05, 3:44–3:52 and 4:37 (`f0140.png`, `f0305.png`, `f0344.png`). It looks like the bottom pixel rows of the OBS recordings.
   Fix: crop 6 px off the bottom of each clip in `DemoClip`, or scale the rest framing up by about 0.5%.

9. **The tailored draft is cut off at the right edge (4:05–4:12).** Evidence: `f0408.png`. The TAILORED DRAFT column is clipped at x=1920, so the "Participated in… → Co-designed…" change the script asks for is not readable side by side.
   Fix: pan or reframe so both the ORIGINAL and TAILORED DRAFT columns are fully in frame, then push in on one changed line.

10. **Small demo text in wide shots.** Evidence: `f0257.png`, `f0344.png`, `strip-0340.png` and the dashboard/targets frames at 5:25–5:50. Secondary UI text is about 12–15 px high at 1080p, below the aesthetic-rules Q11 threshold of ≥32 px for text meant to be read. This is acceptable where the text is texture. Where the VO depends on it (levels, comparison gaps, targets progress steps), push in further or hold longer.

### Nits

11. **The lower-left tag covers a line of content** at 3:17 (`f0317.png`, the next evidence line "…ADLC): You'll have complete" is hidden), at 3:22 (the "challenges, and build AI agents…" line) and at 4:08 (Suggestion block 04 "Skills"). Consider scrolling the content above y≈950 at those moments, or a slightly more transparent tag.
12. **Persona data:** the header shows "Chen Yuhang · Communication University of China" and the dashboard shows "Hello, Chen Yuhang" (5:40–5:50). Phone is the placeholder 138-0000-0000 and the email is hidden behind the tag at 2:10. This comes from the project's test resume. I could not verify whether the name is fictional (the reading of that file was blocked). Confirm it is not a real classmate before publishing.
13. **The minimum-recommendation dropdown is opened twice (2:46 and 2:52)**, which slightly pads the filter beat. Fine if the VO covers it.
14. **The 2:14–2:34 career-intent beat has 20 s for an 18-word line (47 wpm).** The 2.4x scroll is busy while the VO is sparse. Consider adding a line or trimming about 4 s.

### Verified OK

- The script order matches: Hook → Challenge (4 cards with Reddit quotes; card 03 is on screen at 0:45 for the "Scale" line at 0:38) → Intro + 4 pillars → workflow panel legible at 1:40 → profile → jobs → tailor (placeholders `[business outcome / adoption status]` and `[task success rate]` visible at 4:15–4:22, `f0415.png`/`f0422.png`) → interview with transcript and reference answer (`f0520.png`) → targets with Application stage Interview 1 (`f0540.png`) → Trust (385) → Pricing → CTA hold (`f0654.png`).
- No error toasts, secrets or localhost URLs appear in the frames I checked.
- Motion is calm with no bounce or shake, and the brand wordmark holds for more than 1 s at the start and end.
