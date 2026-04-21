from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from .mains import (
    DEFAULT_MAINS_NETWORK_TYPE,
    classify_phase_delta,
    normalize_mains_network_type,
    switch_slot_labels,
    switch_slot_text,
)

WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


@dataclass
class HeatmapCell:
    hour: str
    primary: str
    secondary: str
    tertiary: str
    bg: str
    border: str
    text_color: str
    secondary_color: str
    duration_text: str
    tooltip: str


@dataclass
class HeatmapRow:
    label: str
    peak_text: str
    change_text: str
    cells: list[HeatmapCell]


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


def phase_analysis(
    samples: list[dict[str, Any]],
    records_desc: list[Any],
    mains_network_type: str = DEFAULT_MAINS_NETWORK_TYPE,
) -> dict[str, str]:
    network_type = normalize_mains_network_type(mains_network_type)
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
    dominant_text = 'Dominant conductor recently' if network_type == 'IT' else 'Dominant phase recently'
    imbalance_text = 'recent max conductor imbalance' if network_type == 'IT' else 'recent max imbalance'
    return {
        'phase_latest_text': f'L1 {l1a:.3f} A | L2 {l2a:.3f} A | L3 {l3a:.3f} A',
        'phase_avg_text': f'Avg L1 {avg_l1:.3f} A | Avg L2 {avg_l2:.3f} A | Avg L3 {avg_l3:.3f} A',
        'phase_dominant_text': f'{dominant_text}: {dominant}',
        'phase_imbalance_text': f'{imbalance:.3f} A {imbalance_text}',
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


def _sample_power(snapshot) -> dict[str, float]:
    signed_kw = signed_grid_w(snapshot) / 1000.0
    return {
        'signed_kw': signed_kw,
        'abs_kw': max(snapshot.import_w, snapshot.export_w) / 1000.0,
        'import_kw': snapshot.import_w / 1000.0,
        'export_kw': snapshot.export_w / 1000.0,
    }


def _empty_heat_bucket() -> dict[str, float]:
    return {
        'duration_h': 0.0,
        'abs_energy_kwh': 0.0,
        'signed_energy_kwh': 0.0,
        'import_energy_kwh': 0.0,
        'export_energy_kwh': 0.0,
        'step_sum_kw': 0.0,
        'step_count': 0.0,
        'peak_abs_kw': 0.0,
        'switch_l1': 0.0,
        'switch_l2': 0.0,
        'switch_l3': 0.0,
        'switch_3p': 0.0,
    }


def _next_hour_boundary(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _accumulate_interval(bucket: dict[str, float], sample: dict[str, float], duration_h: float) -> None:
    bucket['duration_h'] += duration_h
    bucket['abs_energy_kwh'] += sample['abs_kw'] * duration_h
    bucket['signed_energy_kwh'] += sample['signed_kw'] * duration_h
    bucket['import_energy_kwh'] += sample['import_kw'] * duration_h
    bucket['export_energy_kwh'] += sample['export_kw'] * duration_h
    bucket['peak_abs_kw'] = max(bucket['peak_abs_kw'], sample['abs_kw'])


def _bucket_stats(bucket: dict[str, float]) -> dict[str, float]:
    duration_h = bucket['duration_h']
    step_count = bucket['step_count']
    if duration_h <= 0:
        return {
            'avg_abs_kw': 0.0,
            'avg_signed_kw': 0.0,
            'avg_import_kw': 0.0,
            'avg_export_kw': 0.0,
            'avg_step_kw': 0.0,
            'peak_abs_kw': 0.0,
            'switch_l1': 0.0,
            'switch_l2': 0.0,
            'switch_l3': 0.0,
            'switch_3p': 0.0,
            'switch_total': 0.0,
        }
    return {
        'avg_abs_kw': bucket['abs_energy_kwh'] / duration_h,
        'avg_signed_kw': bucket['signed_energy_kwh'] / duration_h,
        'avg_import_kw': bucket['import_energy_kwh'] / duration_h,
        'avg_export_kw': bucket['export_energy_kwh'] / duration_h,
        'avg_step_kw': (bucket['step_sum_kw'] / step_count) if step_count else 0.0,
        'peak_abs_kw': bucket['peak_abs_kw'],
        'switch_l1': bucket['switch_l1'],
        'switch_l2': bucket['switch_l2'],
        'switch_l3': bucket['switch_l3'],
        'switch_3p': bucket['switch_3p'],
        'switch_total': bucket['switch_l1'] + bucket['switch_l2'] + bucket['switch_l3'] + bucket['switch_3p'],
    }


def _record_switch(bucket: dict[str, float], phase_label: str, mains_network_type: str) -> None:
    slot_labels = switch_slot_labels(mains_network_type)
    if phase_label == slot_labels[0]:
        bucket['switch_l1'] += 1.0
    elif phase_label == slot_labels[1]:
        bucket['switch_l2'] += 1.0
    elif phase_label == slot_labels[2]:
        bucket['switch_l3'] += 1.0
    elif phase_label == '3-phase':
        bucket['switch_3p'] += 1.0


def _format_cell_text(
    stats: dict[str, float],
    duration_h: float,
    mains_network_type: str,
) -> tuple[str, str, str]:
    if duration_h <= 0:
        return '-', 'No data', ''
    signed = stats['avg_signed_kw']
    primary = f"{signed:+.1f} kW"
    secondary_prefix = 'IT' if normalize_mains_network_type(mains_network_type) == 'IT' else 'L'
    secondary = f"{secondary_prefix} {int(stats['switch_l1'])}/{int(stats['switch_l2'])}/{int(stats['switch_l3'])}"
    tertiary = f"3P {int(stats['switch_3p'])}"
    return primary, secondary, tertiary


def _cell_style(load_norm: float, change_norm: float, signed_kw: float) -> tuple[str, str, str, str]:
    load_norm = max(0.0, min(load_norm, 1.0))
    change_norm = max(0.0, min(change_norm, 1.0))
    base_alpha = 0.22 + (0.54 * load_norm)
    if signed_kw > 0.12:
        base_rgb = (22, 163, 74)
    elif signed_kw < -0.12:
        base_rgb = (37, 99, 235)
    else:
        base_rgb = (100, 116, 139)
    base_bg = (
        f"linear-gradient(135deg, rgba({base_rgb[0]}, {base_rgb[1]}, {base_rgb[2]}, {base_alpha:.3f}) 0%, "
        f"rgba({base_rgb[0]}, {base_rgb[1]}, {base_rgb[2]}, {max(base_alpha * 0.92, 0.20):.3f}) 100%)"
    )
    if change_norm < 0.16:
        bg = base_bg
        border_rgb = (148, 163, 184)
        border_alpha = 0.24 + (0.24 * load_norm)
    else:
        if change_norm < 0.45:
            corner_rgb = (250, 204, 21)
            corner_alpha = 0.82
            border_rgb = (250, 204, 21)
        elif change_norm < 0.78:
            corner_rgb = (249, 115, 22)
            corner_alpha = 0.86
            border_rgb = (249, 115, 22)
        else:
            corner_rgb = (239, 68, 68)
            corner_alpha = 0.92
            border_rgb = (239, 68, 68)
        bg = (
            f"linear-gradient(135deg, rgba({base_rgb[0]}, {base_rgb[1]}, {base_rgb[2]}, {base_alpha:.3f}) 0%, "
            f"rgba({base_rgb[0]}, {base_rgb[1]}, {base_rgb[2]}, {max(base_alpha * 0.92, 0.20):.3f}) 74%, "
            f"rgba({corner_rgb[0]}, {corner_rgb[1]}, {corner_rgb[2]}, {corner_alpha * 0.22:.3f}) 84%, "
            f"rgba({corner_rgb[0]}, {corner_rgb[1]}, {corner_rgb[2]}, {corner_alpha:.3f}) 100%)"
        )
        border_alpha = 0.30 + (0.30 * max(load_norm, change_norm))
    border = f"1px solid rgba({border_rgb[0]}, {border_rgb[1]}, {border_rgb[2]}, {border_alpha:.3f})"
    text_color = '#f8fafc'
    secondary_color = '#cbd5e1'
    return bg, border, text_color, secondary_color


def build_load_heatmaps(
    records_desc: list[Any],
    recent_days: int = 7,
    switch_threshold_w: float = 300.0,
    mains_network_type: str = DEFAULT_MAINS_NETWORK_TYPE,
) -> dict[str, Any]:
    network_type = normalize_mains_network_type(mains_network_type)
    slot_labels_text = switch_slot_text(network_type)
    hourly_buckets: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_heat_bucket)
    if not records_desc:
        return {
            'recent_rows': [],
            'weekday_rows': [],
            'day_count_text': '0 days',
            'peak_hour_text': 'No hourly load peak yet',
            'change_peak_text': 'No load-change spikes yet',
            'weekday_focus_text': 'No weekday pattern yet',
        }

    records = list(reversed(records_desc))
    dated_records: list[tuple[datetime, Any]] = []
    for record in records:
        dt = parse_meter_dt(record.snapshot.timestamp)
        if dt is not None:
            dated_records.append((dt, record))
    if len(dated_records) < 2:
        return {
            'recent_rows': [],
            'weekday_rows': [],
            'day_count_text': '1 day' if dated_records else '0 days',
            'peak_hour_text': 'Need more history for heatmap',
            'change_peak_text': 'Need more history for change heatmap',
            'weekday_focus_text': 'Need more history for weekday pattern',
        }

    for idx in range(len(dated_records) - 1):
        start_dt, start_record = dated_records[idx]
        end_dt, end_record = dated_records[idx + 1]
        delta_h = (end_dt - start_dt).total_seconds() / 3600.0
        if delta_h <= 0 or delta_h > 0.5:
            continue
        sample = _sample_power(start_record.snapshot)
        cursor = start_dt
        while cursor < end_dt:
            segment_end = min(end_dt, _next_hour_boundary(cursor))
            segment_h = (segment_end - cursor).total_seconds() / 3600.0
            if segment_h > 0:
                key = (cursor.strftime('%Y-%m-%d'), cursor.hour)
                _accumulate_interval(hourly_buckets[key], sample, segment_h)
            cursor = segment_end

        current_signed_kw = signed_grid_w(end_record.snapshot) / 1000.0
        previous_signed_kw = sample['signed_kw']
        step_kw = abs(current_signed_kw - previous_signed_kw)
        end_key = (end_dt.strftime('%Y-%m-%d'), end_dt.hour)
        hourly_buckets[end_key]['step_sum_kw'] += step_kw
        hourly_buckets[end_key]['step_count'] += 1.0
        hourly_buckets[end_key]['peak_abs_kw'] = max(
            hourly_buckets[end_key]['peak_abs_kw'],
            _sample_power(end_record.snapshot)['abs_kw'],
        )
        if step_kw * 1000.0 >= switch_threshold_w:
            phase_label = classify_phase_delta(
                end_record.snapshot.l1_a - start_record.snapshot.l1_a,
                end_record.snapshot.l2_a - start_record.snapshot.l2_a,
                end_record.snapshot.l3_a - start_record.snapshot.l3_a,
                network_type,
            )
            _record_switch(hourly_buckets[end_key], phase_label, network_type)

    if not hourly_buckets:
        return {
            'recent_rows': [],
            'weekday_rows': [],
            'day_count_text': '0 days',
            'peak_hour_text': 'No hourly load peak yet',
            'change_peak_text': 'No load-change spikes yet',
            'weekday_focus_text': 'No weekday pattern yet',
        }

    unique_days = sorted({day for day, _hour in hourly_buckets.keys()})
    recent_day_labels = list(reversed(unique_days[-recent_days:]))
    all_stats = [_bucket_stats(bucket) for bucket in hourly_buckets.values() if bucket['duration_h'] > 0]
    max_abs_kw = max((stats['avg_abs_kw'] for stats in all_stats), default=1.0) or 1.0
    max_switch_total = max((stats['switch_total'] for stats in all_stats), default=1.0) or 1.0

    def make_cells(bucket_lookup, label_key: Any, label_text: str) -> HeatmapRow:
        cells: list[HeatmapCell] = []
        row_peak = 0.0
        row_change = 0.0
        for hour in range(24):
            bucket = bucket_lookup(label_key, hour)
            stats = _bucket_stats(bucket)
            primary, secondary, tertiary = _format_cell_text(stats, bucket['duration_h'], network_type)
            load_norm = stats['avg_abs_kw'] / max_abs_kw if max_abs_kw else 0.0
            change_norm = stats['switch_total'] / max_switch_total if max_switch_total else 0.0
            bg, border, text_color, secondary_color = _cell_style(load_norm, change_norm, stats['avg_signed_kw'])
            cells.append(HeatmapCell(
                hour=f'{hour:02d}',
                primary=primary,
                secondary=secondary,
                tertiary=tertiary,
                bg=bg,
                border=border,
                text_color=text_color,
                secondary_color=secondary_color,
                duration_text=f"{bucket['duration_h']:.2f} h",
                tooltip=(
                    f"{label_text} {hour:02d}:00 | Net {stats['avg_signed_kw']:+.2f} kW | "
                    f"Use {stats['avg_abs_kw']:.2f} kW | {slot_labels_text} switches {int(stats['switch_l1'])}/{int(stats['switch_l2'])}/{int(stats['switch_l3'])} | "
                    f"3P {int(stats['switch_3p'])} | Threshold {switch_threshold_w:.0f} W | "
                    f"Change {stats['avg_step_kw']:.2f} kW | Peak {stats['peak_abs_kw']:.2f} kW | Coverage {bucket['duration_h']:.2f} h"
                ),
            ))
            row_peak = max(row_peak, stats['avg_abs_kw'])
            row_change += stats['switch_total']
        return HeatmapRow(
            label=label_text,
            peak_text=f'{row_peak:.1f} kW peak use',
            change_text=f'{int(row_change)} switches >= {switch_threshold_w:.0f} W',
            cells=cells,
        )

    recent_rows = [
        make_cells(lambda day, hour: hourly_buckets[(day, hour)], day_label, day_label)
        for day_label in recent_day_labels
    ]

    weekday_buckets: dict[tuple[int, int], dict[str, float]] = defaultdict(_empty_heat_bucket)
    for (day_label, hour), bucket in hourly_buckets.items():
        day_dt = datetime.strptime(day_label, '%Y-%m-%d')
        key = (day_dt.weekday(), hour)
        merged = weekday_buckets[key]
        for field in (
            'duration_h', 'abs_energy_kwh', 'signed_energy_kwh', 'import_energy_kwh', 'export_energy_kwh',
            'step_sum_kw', 'step_count', 'switch_l1', 'switch_l2', 'switch_l3', 'switch_3p'
        ):
            merged[field] += bucket[field]
        merged['peak_abs_kw'] = max(merged['peak_abs_kw'], bucket['peak_abs_kw'])

    weekday_rows = [
        make_cells(lambda weekday_idx, hour: weekday_buckets[(weekday_idx, hour)], weekday_idx, WEEKDAY_LABELS[weekday_idx])
        for weekday_idx in range(7)
    ]

    peak_day_hour = max(
        ((day, hour, _bucket_stats(bucket)['avg_abs_kw']) for (day, hour), bucket in hourly_buckets.items() if bucket['duration_h'] > 0),
        key=lambda item: item[2],
        default=None,
    )
    change_day_hour = max(
        ((day, hour, _bucket_stats(bucket)['switch_total']) for (day, hour), bucket in hourly_buckets.items() if bucket['duration_h'] > 0),
        key=lambda item: item[2],
        default=None,
    )
    weekday_focus = max(
        (
            (
                WEEKDAY_LABELS[weekday_idx],
                mean([
                    _bucket_stats(weekday_buckets[(weekday_idx, hour)])['avg_abs_kw']
                    for hour in range(24)
                    if weekday_buckets[(weekday_idx, hour)]['duration_h'] > 0
                ]) if any(weekday_buckets[(weekday_idx, hour)]['duration_h'] > 0 for hour in range(24)) else 0.0,
            )
            for weekday_idx in range(7)
        ),
        key=lambda item: item[1],
        default=('Mon', 0.0),
    )

    return {
        'recent_rows': recent_rows,
        'weekday_rows': weekday_rows,
        'day_count_text': f'{len(unique_days)} days in heatmap',
        'peak_hour_text': (
            f"{peak_day_hour[0]} {peak_day_hour[1]:02d}:00 at {peak_day_hour[2]:.1f} kW"
            if peak_day_hour else 'No hourly load peak yet'
        ),
        'change_peak_text': (
            f"{change_day_hour[0]} {change_day_hour[1]:02d}:00 with {int(change_day_hour[2])} switches >= {switch_threshold_w:.0f} W"
            if change_day_hour else f'No switches >= {switch_threshold_w:.0f} W yet'
        ),
        'weekday_focus_text': f'{weekday_focus[0]} is busiest on average ({weekday_focus[1]:.1f} kW)',
    }


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
