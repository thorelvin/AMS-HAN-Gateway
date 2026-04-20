# AMS HAN Reflex v10.3

Merged stable build based on the replay-capable baseline, with:
- replay + demo support
- replay upload/browse support
- corrected daily cost integration based on time between snapshots
- corrected Tensio-style capacity basis wording
- improved event engine with missing-voltage quality detection
- suppression of spread spam when a phase voltage is invalid
- baseline/session-based load detection
- start/end session events
- improved phase-specific appliance hints

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
reflex run
```

## Replay
Use **Show Advanced** and then the **Replay & Demo** panel.
You can:
- paste a path and click **Load Replay**
- click **Load Demo Replay**
- or use **Browse / Upload Replay File** and then **Use Uploaded File**

Bundled replay scenarios live in `fixtures/`:
- `demo_session.log`
- `replay_phase_loss_l2.log`
- `replay_load_switching.log`
- `replay_voltage_sag.log`
- `replay_solar_export_cycle.log`
