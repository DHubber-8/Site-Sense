# Reference PPE images

Correct-PPE reference images, **generated from the real detection pipeline** by:

```
uv run python scripts/build_reference_ppe.py
```

That script runs the PPE detection agent over `data/sample_images/`, asks the risk scoring
agent which detections are compliant (`Severity.NONE` and not flagged for review), and crops
the best compliant example of each item. `manifest.json` records the provenance — source frame,
detection confidence, and crop box — and the dashboard uses it to caption each image with the
confidence it was detected at.

Nothing here is fabricated or hand-drawn: every image is a crop of a frame the trained model
classified as correctly-worn PPE.

## Where they appear

- **Guidelines tab** — beside the response steps for each PPE protocol.
- **PPE response checklist** (the acknowledge/resolve dialog) — above the steps, so the
  responder sees the target state before working the list.
- **PPE incident details** — under the recommended actions.

These are *reference* images, never incident evidence. The logging schema does not persist a
detection's source frame, so no stored record can point at the image it was detected in.

## Item coverage

| File | Source frame | Notes |
|---|---|---|
| `helmet.jpg` | `image718.jpg` | Clear worn hard hat |
| `gloves.jpg` | `image771.jpg` | Curated — see below |
| `vest.jpg` | `image714.jpeg` | Curated — see below |
| `boots.jpg` | `image502.jpg` | Only strong candidate in the set |
| `goggles.jpg` | `image502.jpg` | Only frame in the set with goggles detected |

Heat has no reference image by design: heat detection runs on proxy/synthetic condition data,
not imagery, so there is nothing to illustrate from the pipeline.

## Curated picks

`PREFERRED_SOURCES` in the build script pins the source frame for `vest` and `gloves`. Those
pins only choose *between detections the scoring agent already accepted as compliant* — they
never promote a non-compliant detection. They exist because neither confidence nor box size
predicts legibility: the largest compliant vest box is a mirrored press screenshot, and the
most confident gloves box is an unreadable dark crop. Remove an entry to fall back to the
automatic largest-box pick.

## Regenerating

Safe to re-run at any time; it overwrites the five item files and `manifest.json`. Re-run after
retraining the PPE model or changing `data/sample_images/`. A missing file renders nothing in
the dashboard — no broken image, no placeholder.
