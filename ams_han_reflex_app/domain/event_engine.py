from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .mains import DEFAULT_MAINS_NETWORK_TYPE, classify_phase_delta, normalize_mains_network_type
from .signatures import likely_device_hint

@dataclass
class EventRecord:
    time: str
    category: str
    event_type: str
    status: str
    severity: str
    confidence: float
    summary: str
    delta_signed: str
    phase: str
    voltages: str
    phase_delta: str
    note: str

    def as_row(self) -> dict[str, str]:
        d=asdict(self)
        d['confidence']=f"{self.confidence:.2f}"
        d['type']=d.pop('event_type')
        d['conf']=d.pop('confidence')
        d['dW']=d.pop('delta_signed')
        return {k:str(v) for k,v in d.items()}

class EventEngineV2:
    def __init__(self, mains_network_type: str = DEFAULT_MAINS_NETWORK_TYPE) -> None:
        self.active_quality: dict[str, dict[str, Any]] = {}
        self.active_sessions: dict[str, dict[str, Any]] = {}
        self.last_emit_by_key: dict[str, tuple[str, float]] = {}
        self.last_baseline_signed: float | None = None
        self.mains_network_type = normalize_mains_network_type(mains_network_type)

    def _should_emit(self, key: str, ts_dt: datetime, marker: float, cooldown_s: float = 10.0) -> bool:
        prev = self.last_emit_by_key.get(key)
        if prev is None:
            self.last_emit_by_key[key] = (ts_dt.isoformat(), marker)
            return True
        prev_dt = datetime.fromisoformat(prev[0])
        if abs((ts_dt-prev_dt).total_seconds()) >= cooldown_s or abs(marker-prev[1]) >= 1.0:
            self.last_emit_by_key[key] = (ts_dt.isoformat(), marker)
            return True
        return False

    def _make(self, **kwargs) -> EventRecord:
        return EventRecord(**kwargs)

    def process_sample(self, current: dict[str, Any], previous: dict[str, Any] | None, baseline: dict[str, Any] | None = None) -> list[EventRecord]:
        if previous is None:
            return []
        ts = str(current['timestamp'])
        ts_dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        events=[]
        volts = (float(current.get('l1_v',0.0)), float(current.get('l2_v',0.0)), float(current.get('l3_v',0.0)))
        prev_volts = (float(previous.get('l1_v',0.0)), float(previous.get('l2_v',0.0)), float(previous.get('l3_v',0.0)))
        labels=['L1','L2','L3']
        invalid_phases=[labels[i] for i,v in enumerate(volts) if v < 80.0]
        volt_text=f"{volts[0]:.1f}/{volts[1]:.1f}/{volts[2]:.1f} V"
        d1 = float(current['l1_a']-previous['l1_a']); d2=float(current['l2_a']-previous['l2_a']); d3=float(current['l3_a']-previous['l3_a'])
        phase_delta=f"L1 {d1:+.3f} | L2 {d2:+.3f} | L3 {d3:+.3f}"
        phase=classify_phase_delta(d1, d2, d3, self.mains_network_type)
        conf=0.95 if phase!='-' else 0.5

        # Quality events for invalid voltages
        for ph in invalid_phases:
            key=f'missing_voltage:{ph}'
            if key not in self.active_quality and self._should_emit(key, ts_dt, 1.0, cooldown_s=60.0):
                self.active_quality[key]={'start':ts}
                events.append(self._make(time=ts, category='data_quality', event_type='missing_voltage', status='open', severity='high', confidence=0.98,
                    summary=f'{ph} voltage missing/invalid', delta_signed='-', phase=ph, voltages=volt_text, phase_delta=phase_delta,
                    note='Voltage channel below 80 V; spread and sag diagnostics suppressed until recovery'))
        for ph in labels:
            key=f'missing_voltage:{ph}'
            if key in self.active_quality and ph not in invalid_phases and volts[labels.index(ph)] > 180.0:
                start=self.active_quality.pop(key)
                events.append(self._make(time=ts, category='data_quality', event_type='voltage_channel_recovery', status='resolved', severity='info', confidence=0.85,
                    summary=f'{ph} voltage channel recovered', delta_signed='-', phase=ph, voltages=volt_text, phase_delta=phase_delta,
                    note=f'Recovered after invalid voltage since {start.get("start","-")}'))

        # Only do spread/sag when all voltages valid
        if not invalid_phases:
            spread = max(volts) - min(volts)
            if spread >= 10.0 and self._should_emit('voltage_spread', ts_dt, spread, cooldown_s=30.0):
                events.append(self._make(time=ts, category='phase', event_type='voltage_spread', status='open', severity='high' if spread>=15 else 'medium', confidence=min(0.95,0.5+spread/25),
                    summary=f'Phase voltage spread {spread:.1f} V', delta_signed=f'{float(current.get("export_w",0)-current.get("import_w",0)):+.1f}', phase=phase,
                    voltages=volt_text, phase_delta=phase_delta, note='Phase voltages differ significantly'))
            for i,ph in enumerate(labels):
                drop = prev_volts[i]-volts[i]
                if drop >= 8.0 and self._should_emit(f'voltage_sag:{ph}', ts_dt, drop, cooldown_s=20.0):
                    events.append(self._make(time=ts, category='voltage', event_type='voltage_sag', status='open', severity='critical' if drop>=18 else 'high' if drop>=12 else 'medium', confidence=min(0.98,0.55+drop/25),
                        summary=f'{ph} sagged by {drop:.1f} V', delta_signed=f'{float(current.get("export_w",0)-current.get("import_w",0)):+.1f}', phase=ph, voltages=volt_text, phase_delta=phase_delta, note='Large voltage drop detected'))

        # Load session detection against baseline signed flow
        current_signed = float(current.get('export_w',0.0) - current.get('import_w',0.0))
        baseline_signed = current_signed if baseline is None else float(baseline.get('signed_grid_w', current_signed))
        if self.last_baseline_signed is None:
            self.last_baseline_signed = baseline_signed
        delta = current_signed - baseline_signed
        if abs(delta) >= 800.0:
            session_key = f'session:{phase}:{"export" if delta>0 else "import"}'
            if session_key not in self.active_sessions and self._should_emit(session_key, ts_dt, abs(delta), cooldown_s=20.0):
                signature_note = likely_device_hint(delta, phase, sustained=True, mains_network_type=self.mains_network_type)
                self.active_sessions[session_key]={'start':ts,'baseline':baseline_signed,'phase':phase,'direction':'export' if delta>0 else 'import','signature_note':signature_note}
                events.append(self._make(time=ts, category='power', event_type='load_session_start', status='open', severity='critical' if abs(delta)>=5000 else 'high' if abs(delta)>=2500 else 'medium', confidence=conf,
                    summary=f'Load session start {delta:+.0f} W on {phase}', delta_signed=delta, phase=phase, voltages=volt_text, phase_delta=phase_delta,
                    note=signature_note))
        # session end when current returns close to baseline
        for key, info in list(self.active_sessions.items()):
            if abs(current_signed - float(info['baseline'])) < 350.0:
                events.append(self._make(time=ts, category='power', event_type='load_session_end', status='resolved', severity='info', confidence=0.85,
                    summary=f"Load session ended on {info['phase']}", delta_signed=current_signed-float(info['baseline']), phase=str(info['phase']), voltages=volt_text, phase_delta=phase_delta,
                    note=f"Session started {info['start']} ({info.get('signature_note', likely_device_hint(current_signed-float(info['baseline']), str(info['phase']), mains_network_type=self.mains_network_type))})"))
                self.active_sessions.pop(key, None)

        # Fast sharp-edge events against previous sample
        sample_delta = current_signed - float(previous.get('export_w',0.0)-previous.get('import_w',0.0))
        if abs(sample_delta) >= 1000.0 and self._should_emit(f'power_step:{phase}', ts_dt, abs(sample_delta), cooldown_s=8.0):
            direction='Export step' if sample_delta>0 else 'Import step'
            events.append(self._make(time=ts, category='power', event_type='power_step', status='open', severity='critical' if abs(sample_delta)>=6000 else 'high' if abs(sample_delta)>=3000 else 'medium', confidence=conf,
                summary=f'{direction} {sample_delta:+.0f} W on {phase}', delta_signed=sample_delta, phase=phase, voltages=volt_text, phase_delta=phase_delta,
                note=likely_device_hint(sample_delta, phase, mains_network_type=self.mains_network_type)))
        return events
