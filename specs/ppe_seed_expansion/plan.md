# Plan: expand PPE seeding across the real sample set

## Goal

Broaden the seeded PPE evaluation in `scripts/seed_demo_data.py` from the four hardcoded images to the full real sample set in `data/sample_images/`, while preserving the actual model behavior and exposing raw detections for easy review.

## Why this change

The current seed script only evaluates a tiny subset of the sample corpus. That can skew the recorded compliance percentages and hide whether the model genuinely detects worn PPE across the representative image mix. The script also needs clearer raw-detection output so it is obvious which images produce true direct `worn` detections for the five core PPE items, including vest.

## Scope

- Update `SAMPLE_IMAGES` in `scripts/seed_demo_data.py` to enumerate images from `data/sample_images/` instead of a fixed list of four files.
- Preserve the existing downstream risk-scoring and alert-routing behavior.
- Print each image’s raw detection list during seeding so reviewers can identify confident worn detections versus missing/unaccounted coverage items.
- Keep the model’s honest behavior: do not fabricate or override detections to force percentages.

## Validation

- Add a smoke test checking that the seed script references more than the original four-image sample set.
- Run the focused seed-data test and the seeding script itself to confirm the broader image set runs and the output remains truthful about actual detections.
