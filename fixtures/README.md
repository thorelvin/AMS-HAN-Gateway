# Replay Fixtures

These fixture logs are meant for the **Replay & Demo** panel in the app.

Included scenarios:
- `demo_session.log`: small baseline capture from a normal session.
- `replay_phase_loss_l2.log`: L2 voltage disappears for two frames and then recovers.
- `replay_load_switching.log`: single-phase and three-phase load steps with returns to baseline.
- `replay_voltage_sag.log`: heavy import causes an L1 sag and phase spread, then recovery.
- `replay_solar_export_cycle.log`: import shifts into midday export and then back to import.

How to use them:
- Open **Show Advanced** in the app.
- In **Replay & Demo**, paste a full path to one of these files and click **Load Replay**.
- Start playback with **Start Replay**.

These logs intentionally keep the same meter ID and meter type as the bundled demo file so they behave like one consistent installation while exercising different event-engine paths.
