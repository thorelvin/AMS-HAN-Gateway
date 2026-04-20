from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any


def parse_meter_dt(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def signed_grid_w(snapshot) -> float:
    return float(snapshot.export_w - snapshot.import_w)


def unified_overview(snapshot) -> dict[str, str]:
    if snapshot is None:
        return {'title':'Waiting for live data', 'value':'-', 'subtitle':'No valid HAN snapshot yet', 'accent':'blue'}
    signed = signed_grid_w(snapshot)
    if signed > 50:
        return {'title':'Exporting to grid', 'value':f'{signed:.1f} W', 'subtitle':f'Export {snapshot.export_w:.1f} W | Import {snapshot.import_w:.1f} W', 'accent':'green'}
    if signed < -50:
        return {'title':'Importing from grid', 'value':f'{abs(signed):.1f} W', 'subtitle':f'Import {snapshot.import_w:.1f} W | Export {snapshot.export_w:.1f} W', 'accent':'blue'}
    return {'title':'Near balanced', 'value':f'{signed:.1f} W', 'subtitle':'Import and export nearly balanced', 'accent':'amber'}


def import_export_bar(snapshot, records_desc) -> dict[str, str]:
    peak = 0.0
    for r in records_desc[:500]:
        peak = max(peak, r.snapshot.import_w, r.snapshot.export_w)
    peak = max(peak, 1.0)
    if snapshot is None:
        return {'import_width':'0%','export_width':'0%','import_text':'Import 0.0 W','export_text':'Export 0.0 W','scale_text':'No recent peak yet'}
    return {
        'import_width': f"{min(100.0, 100.0 * snapshot.import_w/peak):.1f}%",
        'export_width': f"{min(100.0, 100.0 * snapshot.export_w/peak):.1f}%",
        'import_text': f'Import {snapshot.import_w:.1f} W',
        'export_text': f'Export {snapshot.export_w:.1f} W',
        'scale_text': f'Relative to recent peak {peak:.0f} W',
    }


def history_rows(records_desc: list[Any]) -> list[dict[str, str]]:
    rows=[]
    for r in records_desc:
        s=r.snapshot
        rows.append({
            'received_at': r.received_at,
            'meter_time': s.timestamp,
            'meter': f'{s.meter_id} ({s.meter_type})',
            'import_w': f'{s.import_w:.1f}',
            'export_w': f'{s.export_w:.1f}',
            'signed_grid_w': f'{signed_grid_w(s):+.1f}',
            'avg_v': f'{s.avg_voltage_v:.1f}',
            'l1_a': f'{s.l1_a:.3f}',
            'l2_a': f'{s.l2_a:.3f}',
            'l3_a': f'{s.l3_a:.3f}',
            'pf': f'{s.estimated_power_factor:.2f}',
            'rx': str(s.frames_rx),
            'bad': str(s.frames_bad),
        })
    return rows


def analysis_summary(records_desc: list[Any]) -> dict[str, str]:
    if not records_desc:
        return {
            'signed_avg_text':'0.0 W signed avg', 'current_hour_text':'0.0 W current hour avg', 'projected_hour_text':'0.00 kWh projected hour',
            'import_peak_text':'0.0 W peak import', 'export_peak_text':'0.0 W peak export', 'import_samples_text':'0 import samples', 'export_samples_text':'0 export samples'
        }
    signed_vals=[signed_grid_w(r.snapshot) for r in records_desc]
    signed_avg = mean(signed_vals)
    latest_dt = parse_meter_dt(records_desc[0].snapshot.timestamp)
    current_hour_vals = [signed_grid_w(r.snapshot) for r in records_desc if latest_dt and parse_meter_dt(r.snapshot.timestamp) and parse_meter_dt(r.snapshot.timestamp).strftime('%Y-%m-%d %H') == latest_dt.strftime('%Y-%m-%d %H')]
    current_hour_avg = mean(current_hour_vals) if current_hour_vals else 0.0
    projected_kwh = abs(current_hour_avg)/1000.0
    import_peak=max((r.snapshot.import_w for r in records_desc), default=0.0)
    export_peak=max((r.snapshot.export_w for r in records_desc), default=0.0)
    return {
        'signed_avg_text': f'{signed_avg:.1f} W signed avg',
        'current_hour_text': f'{current_hour_avg:.1f} W current hour avg',
        'projected_hour_text': f'{projected_kwh:.2f} kWh projected hour',
        'import_peak_text': f'{import_peak:.1f} W peak import',
        'export_peak_text': f'{export_peak:.1f} W peak export',
        'import_samples_text': f"{sum(1 for r in records_desc if r.snapshot.import_w>0)} import samples",
        'export_samples_text': f"{sum(1 for r in records_desc if r.snapshot.export_w>0)} export samples",
    }


def phase_analysis(samples: list[dict[str, Any]], records_desc: list[Any]) -> dict[str, str]:
    if not samples:
        # try derive from records
        if not records_desc:
            return {k:'No phase data' for k in ['phase_latest_text','phase_avg_text','phase_dominant_text','phase_imbalance_text','voltage_latest_text','voltage_avg_text','voltage_min_text','voltage_spread_text']}
        samples=[]
        for r in records_desc[:200]:
            s=r.snapshot
            samples.append({'l1_a':s.l1_a,'l2_a':s.l2_a,'l3_a':s.l3_a,'l1_v':None,'l2_v':None,'l3_v':None})
    last=samples[-1]
    l1a=last.get('l1_a',0.0); l2a=last.get('l2_a',0.0); l3a=last.get('l3_a',0.0)
    avg_l1=mean([s.get('l1_a',0.0) for s in samples]); avg_l2=mean([s.get('l2_a',0.0) for s in samples]); avg_l3=mean([s.get('l3_a',0.0) for s in samples])
    dominant=max((('L1',avg_l1),('L2',avg_l2),('L3',avg_l3)), key=lambda x:x[1])[0]
    imbalance=max(avg_l1,avg_l2,avg_l3)-min(avg_l1,avg_l2,avg_l3)
    v_samples=[s for s in samples if s.get('l1_v') is not None]
    if v_samples:
        lv=v_samples[-1]
        latest_volt=f"L1 {lv['l1_v']:.1f} V | L2 {lv['l2_v']:.1f} V | L3 {lv['l3_v']:.1f} V"
        avg_v1=mean([s['l1_v'] for s in v_samples]); avg_v2=mean([s['l2_v'] for s in v_samples]); avg_v3=mean([s['l3_v'] for s in v_samples])
        min_v1=min(s['l1_v'] for s in v_samples); min_v2=min(s['l2_v'] for s in v_samples); min_v3=min(s['l3_v'] for s in v_samples)
        worst=max(max(s['l1_v'],s['l2_v'],s['l3_v'])-min(s['l1_v'],s['l2_v'],s['l3_v']) for s in v_samples)
        voltage_avg=f"Avg L1 {avg_v1:.1f} V | Avg L2 {avg_v2:.1f} V | Avg L3 {avg_v3:.1f} V"
        voltage_min=f"Min L1 {min_v1:.1f} V | Min L2 {min_v2:.1f} V | Min L3 {min_v3:.1f} V"
        spread=f"{worst:.1f} V worst phase spread"
    else:
        latest_volt='No voltage frame yet'; voltage_avg='No voltage averages yet'; voltage_min='No voltage minimums yet'; spread='0.0 V worst phase spread'
    return {
        'phase_latest_text': f'L1 {l1a:.3f} A | L2 {l2a:.3f} A | L3 {l3a:.3f} A',
        'phase_avg_text': f'Avg L1 {avg_l1:.3f} A | Avg L2 {avg_l2:.3f} A | Avg L3 {avg_l3:.3f} A',
        'phase_dominant_text': f'Dominant phase recently: {dominant}',
        'phase_imbalance_text': f'{imbalance:.3f} A recent max imbalance',
        'voltage_latest_text': latest_volt,
        'voltage_avg_text': voltage_avg,
        'voltage_min_text': voltage_min,
        'voltage_spread_text': spread,
    }


def top_hour_rows(records_desc: list[Any], top_n: int = 8) -> list[dict[str, str]]:
    buckets=defaultdict(list)
    for r in records_desc:
        dt=parse_meter_dt(r.snapshot.timestamp)
        if not dt: continue
        buckets[dt.strftime('%Y-%m-%d %H:00')].append(r.snapshot)
    rows=[]
    for hour,snaps in buckets.items():
        avg_import=mean([s.import_w for s in snaps])
        avg_export=mean([s.export_w for s in snaps])
        signed=avg_export-avg_import
        rows.append({'hour':hour,'avg_import':f'{avg_import:.1f}','avg_export':f'{avg_export:.1f}','avg_signed':f'{signed:+.1f}','avg_import_kw':avg_import/1000.0,'avg_export_kw':avg_export/1000.0,'signed_kw':signed/1000.0,'day':hour[:10]})
    rows.sort(key=lambda r: abs(float(r['avg_signed'])), reverse=True)
    return rows[:top_n]


def daily_graph_data(records_desc: list[Any]) -> dict[str, Any]:
    buckets={h:{'import':[],'export':[]} for h in range(24)}
    latest_date=None
    for r in records_desc:
        dt=parse_meter_dt(r.snapshot.timestamp)
        if dt:
            latest_date=max(latest_date, dt.date()) if latest_date else dt.date()
    if not latest_date:
        return {'rows':[],'date_text':'No daily data','hours_text':'0 populated hours','peak_text':'No daily peak yet'}
    for r in records_desc:
        dt=parse_meter_dt(r.snapshot.timestamp)
        if dt and dt.date()==latest_date:
            buckets[dt.hour]['import'].append(r.snapshot.import_w/1000.0)
            buckets[dt.hour]['export'].append(r.snapshot.export_w/1000.0)
    rows=[]
    peak=0.0; count=0
    for h in range(24):
        ik=mean(buckets[h]['import']) if buckets[h]['import'] else 0.0
        ek=mean(buckets[h]['export']) if buckets[h]['export'] else 0.0
        sk=ek-ik
        if ik or ek: count+=1
        peak=max(peak, ik, ek)
        rows.append({'hour':f'{h:02d}','import_kw':round(ik,3),'export_kw':round(ek,3),'signed_kw':round(sk,3)})
    peak_text = f"Peak export {peak:.2f} kW" if any(r['export_kw']>=r['import_kw'] for r in rows) else f"Peak import {peak:.2f} kW"
    return {'rows':rows,'date_text':str(latest_date),'hours_text':f'{count} populated hours','peak_text':peak_text}


def what_changed(snapshot, events):
    if not events:
        return 'No recent events'
    return events[0].get('summary','No recent events')


def health_rows(connection_status,wifi_state,mqtt_state,last_seq,last_len,latest_snapshot,event_count):
    return [
        {'label':'Connection','value':connection_status},
        {'label':'Wi‑Fi','value':wifi_state},
        {'label':'MQTT','value':mqtt_state},
        {'label':'Last frame','value':f'seq={last_seq}, len={last_len}'},
        {'label':'Event count','value':str(event_count)},
    ]


def diagnose_issues(events, phase, connection_status, wifi_state):
    issues=[]
    if connection_status.startswith('Disconnected'):
        issues.append('Gateway disconnected')
    if wifi_state == 'DISCONNECTED':
        issues.append('Wi‑Fi disconnected')
    for e in events[:5]:
        if e.get('severity') in ('high','critical'):
            issues.append(e.get('summary','Issue'))
    return issues[:8]
