# AMS HAN Reflex v10.3 Overview

## Goals
A stable local dashboard for ESP32 HAN gateway data with:
- live overview
- diagnostics and event tracking
- daily graph
- cost estimation
- replay mode for offline development

## Important notes
- Cost integration is based on time between snapshots, not raw sample counts.
- Capacity estimate uses top 3 hourly averages on different days this month (import only), Tensio-style.
- If a phase voltage is below 80 V, voltage spread spam is suppressed and a data-quality event is emitted instead.
- Load sessions are detected against a rolling baseline and produce start/end events.
