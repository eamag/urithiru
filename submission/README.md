# Submission package

This directory contains the public-facing material for the Urithiru demo.

- [`devpost.md`](devpost.md) — ready-to-paste project description and provenance disclosure.
- [`video-script.md`](video-script.md) — a four-minute narration and exact shot list.
- [`demo-tsb-context.md`](demo-tsb-context.md) — public metadata supplied to the demonstration run.
- [`assets/architecture.svg`](assets/architecture.svg) — editable 16:9 architecture visual.
- `assets/*.png` — screenshots captured from the real page and live Google backend.

Before publishing, replace the placeholders in `devpost.md` for the final demo-video and
repository links. Do not publish `configs/google.local.toml`, `.env`, bucket contents or
raw agent logs without a separate secrets review.
