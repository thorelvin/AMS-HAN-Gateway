from __future__ import annotations

import reflex as rx

from .components import dual_bar_card, hero_card, hint_banner, kv, panel, stat_card, tiny_metric
from .domain.pricing import PRICE_AREAS
from .state import DashboardState

UPLOAD_ID = "replay_upload"


def replay_panel() -> rx.Component:
    return panel(
        "Replay & Demo",
        rx.vstack(
            rx.input(
                placeholder="Path to replay log file",
                value=DashboardState.replay_path,
                on_change=DashboardState.set_replay_path,
            ),
            rx.hstack(
                rx.button("Load Replay", on_click=DashboardState.load_replay, color_scheme="blue"),
                rx.button("Load Demo Replay", on_click=DashboardState.load_demo_replay, variant="soft"),
                spacing="2",
                width="100%",
                wrap="wrap",
            ),
            rx.upload(
                rx.button("Browse / Upload Replay File", variant="soft"),
                id=UPLOAD_ID,
                accept={"text/plain": [".log", ".txt"]},
                max_files=1,
            ),
            rx.button(
                "Use Uploaded File",
                on_click=DashboardState.handle_replay_upload(rx.upload_files(upload_id=UPLOAD_ID)),
                variant="soft",
            ),
            rx.hstack(
                rx.button("Start Replay", on_click=DashboardState.start_replay, color_scheme="green"),
                rx.button("Pause / Resume Replay", on_click=DashboardState.pause_or_resume_replay, variant="soft"),
                rx.button("Stop", on_click=DashboardState.stop_replay, color_scheme="tomato", variant="soft"),
                spacing="2",
                width="100%",
                wrap="wrap",
            ),
            rx.text(DashboardState.replay_status_text, size="2", color=rx.color("gray", 10)),
            rx.text(DashboardState.replay_progress_text, size="2", color=rx.color("gray", 10)),
            rx.text(DashboardState.replay_source_text, size="2", color=rx.color("gray", 10)),
            spacing="3",
            width="100%",
            align="stretch",
        ),
        icon="play",
    )


def simple_sidebar() -> rx.Component:
    return rx.vstack(
        panel(
            "Setup",
            rx.vstack(
                rx.text(
                    "The app finds the gateway automatically and remembers the last good COM port.",
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.button("Refresh Ports", on_click=DashboardState.refresh_ports, variant="soft"),
                rx.button("Auto-connect", on_click=DashboardState.auto_connect_now, color_scheme="blue"),
                rx.button("Open Advanced Tools", on_click=DashboardState.toggle_advanced, variant="soft"),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="sparkles",
        ),
        panel(
            "Wi-Fi",
            rx.vstack(
                rx.input(placeholder="SSID", value=DashboardState.wifi_ssid, on_change=DashboardState.set_wifi_ssid),
                rx.input(
                    placeholder="Password",
                    type="password",
                    value=DashboardState.wifi_password,
                    on_change=DashboardState.set_wifi_password,
                ),
                rx.hstack(
                    rx.button("Save Wi-Fi", on_click=DashboardState.send_set_wifi, color_scheme="blue"),
                    rx.button("Clear", on_click=DashboardState.send_clear_wifi, variant="soft"),
                    spacing="2",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="wifi",
        ),
        panel(
            "MQTT",
            rx.vstack(
                rx.input(placeholder="Broker host", value=DashboardState.mqtt_host, on_change=DashboardState.set_mqtt_host),
                rx.input(placeholder="Port", value=DashboardState.mqtt_port, on_change=DashboardState.set_mqtt_port),
                rx.input(placeholder="User", value=DashboardState.mqtt_user, on_change=DashboardState.set_mqtt_user),
                rx.input(
                    placeholder="Password",
                    type="password",
                    value=DashboardState.mqtt_password,
                    on_change=DashboardState.set_mqtt_password,
                ),
                rx.input(placeholder="Prefix", value=DashboardState.mqtt_prefix, on_change=DashboardState.set_mqtt_prefix),
                rx.hstack(
                    rx.button("Save MQTT", on_click=DashboardState.send_set_mqtt, color_scheme="blue"),
                    rx.button("Enable", on_click=DashboardState.mqtt_enable, color_scheme="green"),
                    spacing="2",
                    width="100%",
                ),
                rx.button("REPUBLISH_DISCOVERY", on_click=DashboardState.republish_discovery, variant="soft"),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="radio_tower",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def advanced_sidebar() -> rx.Component:
    return rx.vstack(
        panel(
            "Serial Connection",
            rx.vstack(
                rx.text("COM Port", size="2", color=rx.color("gray", 10)),
                rx.select(
                    DashboardState.ports,
                    value=DashboardState.selected_port,
                    on_change=DashboardState.set_selected_port,
                    placeholder="Select port",
                ),
                rx.text("Baudrate", size="2", color=rx.color("gray", 10)),
                rx.input(value=DashboardState.baudrate, is_read_only=True),
                rx.hstack(
                    rx.button("Connect", on_click=DashboardState.connect, color_scheme="indigo"),
                    rx.button("Disconnect", on_click=DashboardState.disconnect, variant="soft"),
                    spacing="2",
                    width="100%",
                ),
                rx.text(DashboardState.connection_status, size="2", color=rx.color("gray", 10)),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="plug",
        ),
        replay_panel(),
        simple_sidebar(),
        panel(
            "Project Tools",
            rx.vstack(
                rx.input(value=DashboardState.db_path, on_change=DashboardState.set_db_path),
                rx.hstack(
                    rx.button("Apply DB Path", on_click=DashboardState.apply_db_path),
                    rx.button("Refresh History", on_click=DashboardState.refresh_history, variant="soft"),
                    spacing="2",
                    width="100%",
                ),
                rx.button("Clear History", on_click=DashboardState.clear_history, color_scheme="tomato", variant="soft"),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="folder",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def overview_panel() -> rx.Component:
    return hero_card(
        DashboardState.overview_title,
        DashboardState.overview_value,
        DashboardState.overview_subtitle,
        DashboardState.overview_accent,
    )


def latest_snapshot_panel() -> rx.Component:
    return panel(
        "Latest Snapshot",
        rx.cond(
            DashboardState.has_snapshot,
            rx.vstack(
                kv("Meter", DashboardState.snapshot_meter),
                kv("Meter time", DashboardState.snapshot_meter_time),
                kv("Power", DashboardState.snapshot_power),
                kv("Grid flow", DashboardState.snapshot_grid_flow),
                kv("Reactive", DashboardState.snapshot_reactive),
                kv("Voltage", DashboardState.snapshot_voltage),
                kv("Current", DashboardState.snapshot_current),
                kv("Power factor", DashboardState.snapshot_power_factor),
                kv("Counters", DashboardState.snapshot_counters),
                kv("Stats", DashboardState.snapshot_stats),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            hint_banner(
                "No HAN snapshot yet. Check the HAN adapter wiring or wait for the next long KFM_001 frame."
            ),
        ),
        icon="gauge",
        opacity=DashboardState.live_opacity,
    )


def device_status_panel() -> rx.Component:
    return panel(
        "Device & Link Status",
        rx.vstack(
            kv("Device ID", DashboardState.device_id),
            kv("Firmware", DashboardState.firmware),
            kv("MAC", DashboardState.mac),
            kv("Wi-Fi", DashboardState.wifi_state),
            kv("IP", DashboardState.wifi_ip),
            kv("MQTT", DashboardState.mqtt_state),
            kv("Last frame", DashboardState.last_frame),
            spacing="3",
            width="100%",
            align="stretch",
        ),
        icon="cpu",
        opacity=DashboardState.live_opacity,
    )


def live_tab() -> rx.Component:
    return rx.vstack(
        hint_banner(DashboardState.onboarding_message, rx.cond(DashboardState.show_cached_banner, "amber", "blue")),
        overview_panel(),
        dual_bar_card(
            DashboardState.import_bar_width,
            DashboardState.export_bar_width,
            DashboardState.import_bar_text,
            DashboardState.export_bar_text,
            DashboardState.bar_scale_text,
        ),
        rx.grid(
            tiny_metric("Signed grid average", DashboardState.signed_avg_text, "blue"),
            tiny_metric("Current hour", DashboardState.current_hour_text, "indigo"),
            tiny_metric("Projected hour", DashboardState.projected_hour_text, "cyan"),
            tiny_metric(
                "Peak import/export",
                rx.hstack(
                    rx.text(DashboardState.import_peak_text),
                    rx.text("|"),
                    rx.text(DashboardState.export_peak_text),
                    spacing="2",
                ),
                "amber",
            ),
            columns="4",
            spacing="4",
            width="100%",
            opacity=DashboardState.live_opacity,
        ),
        rx.grid(
            latest_snapshot_panel(),
            device_status_panel(),
            columns="minmax(0,1.35fr) minmax(320px,0.95fr)",
            spacing="4",
            width="100%",
        ),
        panel(
            "Quick Actions",
            rx.hstack(
                rx.button("GET_INFO", on_click=DashboardState.send_get_info, color_scheme="indigo"),
                rx.button("GET_STATUS", on_click=DashboardState.send_get_status, color_scheme="indigo"),
                rx.button("REPUBLISH_DISCOVERY", on_click=DashboardState.republish_discovery, variant="soft"),
                spacing="3",
                width="100%",
                wrap="wrap",
            ),
            icon="zap",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def phase_analysis_panel() -> rx.Component:
    return panel(
        "Phase & Voltage Analysis",
        rx.vstack(
            kv("Latest currents", DashboardState.phase_latest_text),
            kv("Recent current avg", DashboardState.phase_avg_text),
            kv("Dominant phase", DashboardState.phase_dominant_text),
            kv("Imbalance", DashboardState.phase_imbalance_text),
            kv("Latest voltages", DashboardState.voltage_latest_text),
            kv("Recent voltage avg", DashboardState.voltage_avg_text),
            kv("Minimum voltages", DashboardState.voltage_min_text),
            kv("Worst spread", DashboardState.voltage_spread_text),
            spacing="3",
            width="100%",
            align="stretch",
        ),
        icon="activity",
    )


def top_hour_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["hour"]),
        rx.table.cell(row["avg_import"]),
        rx.table.cell(row["avg_export"]),
        rx.table.cell(row["avg_signed"]),
    )


def event_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["time"]),
        rx.table.cell(row["category"]),
        rx.table.cell(row["type"]),
        rx.table.cell(row["status"]),
        rx.table.cell(row["severity"]),
        rx.table.cell(row["confidence"]),
        rx.table.cell(row["delta_signed"]),
        rx.table.cell(row["phase"]),
        rx.table.cell(row["note"]),
    )


def signature_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["signature"]),
        rx.table.cell(row["phase"]),
        rx.table.cell(row["events"]),
        rx.table.cell(row["last_seen"]),
        rx.table.cell(row["confidence"]),
    )


def issue_line(item: str) -> rx.Component:
    return rx.hstack(
        rx.text("\u2022", color=rx.color("gray", 10)),
        rx.text(item),
        spacing="2",
        align="start",
        width="100%",
    )


def health_row(row: dict[str, str]) -> rx.Component:
    return rx.hstack(
        rx.text(row["label"], size="2", color=rx.color("gray", 10), width="132px"),
        rx.text(row["value"], size="3", weight="medium"),
    )


def analysis_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Signed Grid Average", DashboardState.signed_avg_text, "chart_line", "blue", DashboardState.import_samples_text),
            stat_card("Current Hour", DashboardState.current_hour_text, "clock_3", "cyan", DashboardState.projected_hour_text),
            stat_card("Peak Import", DashboardState.import_peak_text, "trending_up", "amber", DashboardState.export_peak_text),
            stat_card("Phase Focus", DashboardState.phase_dominant_text, "gauge", "violet", DashboardState.phase_imbalance_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        phase_analysis_panel(),
        panel(
            "Load Signatures",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Signature"),
                        rx.table.column_header_cell("Phase"),
                        rx.table.column_header_cell("Events"),
                        rx.table.column_header_cell("Last Seen"),
                        rx.table.column_header_cell("Confidence"),
                    )
                ),
                rx.table.body(rx.foreach(DashboardState.signature_rows, signature_row)),
                variant="surface",
                size="2",
                width="100%",
            ),
            icon="fingerprint",
        ),
        panel(
            "Top Hour Buckets",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Hour"),
                        rx.table.column_header_cell("Avg Import W"),
                        rx.table.column_header_cell("Avg Export W"),
                        rx.table.column_header_cell("Signed Grid W"),
                    )
                ),
                rx.table.body(rx.foreach(DashboardState.top_hour_rows, top_hour_row)),
                variant="surface",
                size="2",
                width="100%",
            ),
            icon="bar_chart_3",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def diagnostics_tab() -> rx.Component:
    return rx.vstack(
        panel(
            "Suspected Issues",
            rx.cond(
                DashboardState.has_diagnostics_issues,
                rx.vstack(rx.foreach(DashboardState.diagnostics_issues, issue_line), spacing="2", align="start", width="100%"),
                hint_banner("No major issues detected right now.", "green"),
            ),
            icon="triangle_alert",
        ),
        panel(
            "Health",
            rx.vstack(rx.foreach(DashboardState.health_rows, health_row), spacing="2", align="start", width="100%"),
            icon="shield",
        ),
        panel(
            "Event Tracker",
            rx.vstack(
                rx.hstack(
                    rx.button("All", on_click=DashboardState.set_event_filter("all"), variant="soft"),
                    rx.button("Open", on_click=DashboardState.set_event_filter("open"), variant="soft"),
                    rx.button("Resolved", on_click=DashboardState.set_event_filter("resolved"), variant="soft"),
                    rx.button("Severe", on_click=DashboardState.set_event_filter("severe"), variant="soft"),
                    rx.button("Power", on_click=DashboardState.set_event_filter("power"), variant="soft"),
                    rx.button("Voltage", on_click=DashboardState.set_event_filter("voltage"), variant="soft"),
                    rx.button("Phase", on_click=DashboardState.set_event_filter("phase"), variant="soft"),
                    rx.button("Quality", on_click=DashboardState.set_event_filter("data_quality"), variant="soft"),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Time"),
                                rx.table.column_header_cell("Category"),
                                rx.table.column_header_cell("Type"),
                                rx.table.column_header_cell("Status"),
                                rx.table.column_header_cell("Severity"),
                                rx.table.column_header_cell("Conf"),
                                rx.table.column_header_cell("Delta W"),
                                rx.table.column_header_cell("Phase"),
                                rx.table.column_header_cell("Note"),
                            )
                        ),
                        rx.table.body(rx.foreach(DashboardState.event_rows, event_row)),
                        variant="surface",
                        size="2",
                        width="100%",
                    ),
                    overflow_x="auto",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="search",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def daily_hour_row(row: dict[str, float | str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["hour"]),
        rx.table.cell(row["import_kw"]),
        rx.table.cell(row["export_kw"]),
        rx.table.cell(row["signed_kw"]),
    )


def daily_graph_panel() -> rx.Component:
    return panel(
        "Daily load graph",
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.text("Day", size="2", color=rx.color("gray", 10)),
                    rx.text(DashboardState.daily_date_text, size="2", color=rx.color("gray", 10)),
                    spacing="1",
                ),
                rx.spacer(),
                rx.text(DashboardState.daily_hours_text, size="2", color=rx.color("gray", 10)),
                rx.text(DashboardState.daily_peak_text, size="2", color=rx.color("amber", 10), weight="medium"),
                width="100%",
            ),
            rx.recharts.composed_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", vertical=False, stroke=rx.color("gray", 4)),
                rx.recharts.x_axis(data_key="hour", tick_line=False, axis_line=False),
                rx.recharts.y_axis(tick_line=False, axis_line=False, width=42),
                rx.recharts.tooltip(),
                rx.recharts.legend(),
                rx.recharts.bar(data_key="import_kw", name="Import kW", fill=rx.color("blue", 9), radius=4),
                rx.recharts.bar(data_key="export_kw", name="Export kW", fill=rx.color("green", 9), radius=4),
                rx.recharts.line(data_key="signed_kw", name="Signed kW", stroke=rx.color("amber", 9), stroke_width=2, dot=False),
                data=DashboardState.daily_graph_rows,
                width="100%",
                height=340,
                margin={"top": 12, "right": 16, "left": 0, "bottom": 0},
                bar_category_gap="15%",
            ),
            rx.text(
                "Hourly averages for the latest meter day. Import and export are shown as separate bars; the line shows signed grid flow.",
                size="2",
                color=rx.color("gray", 10),
            ),
            spacing="3",
            width="100%",
            align="stretch",
        ),
        icon="chart_column",
    )


def daily_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Latest meter day", DashboardState.daily_date_text, "calendar", "blue", DashboardState.daily_hours_text),
            stat_card("Daily peak", DashboardState.daily_peak_text, "chart_column", "amber", "Based on hourly average buckets"),
            stat_card("Signed average", DashboardState.signed_avg_text, "chart_line", "cyan", "Across stored snapshot history"),
            stat_card("Current hour", DashboardState.current_hour_text, "clock_3", "indigo", DashboardState.projected_hour_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        daily_graph_panel(),
        panel(
            "Daily hourly buckets",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Hour"),
                        rx.table.column_header_cell("Import kW"),
                        rx.table.column_header_cell("Export kW"),
                        rx.table.column_header_cell("Signed kW"),
                    )
                ),
                rx.table.body(rx.foreach(DashboardState.daily_graph_rows, daily_hour_row)),
                variant="surface",
                size="2",
                width="100%",
            ),
            icon="table_2",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def cost_row(row: dict[str, float | str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["hour"]),
        rx.table.cell(row["spot_nok_kwh"]),
        rx.table.cell(row["grid_nok_kwh"]),
        rx.table.cell(row["total_nok_kwh"]),
        rx.table.cell(row["import_kw"]),
        rx.table.cell(row["export_kw"]),
        rx.table.cell(row["import_cost_nok"]),
        rx.table.cell(row["export_value_nok"]),
        rx.table.cell(row["net_cost_nok"]),
    )


def cost_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Price area", DashboardState.price_area, "badge_cent", "violet", DashboardState.cost_source_text),
            stat_card("Spot now", DashboardState.spot_now_text, "clock_3", "blue", DashboardState.grid_now_text),
            stat_card("Total energy rate", DashboardState.total_now_text, "wallet", "green", DashboardState.current_hour_cost_text),
            stat_card("Capacity estimate", DashboardState.capacity_step_text, "gauge", "amber", DashboardState.capacity_price_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        panel(
            "Cost settings",
            rx.vstack(
                rx.select(PRICE_AREAS, value=DashboardState.price_area, on_change=DashboardState.set_price_area),
                rx.hstack(
                    rx.input(value=DashboardState.grid_day_rate, on_change=DashboardState.set_grid_day_rate, width="180px"),
                    rx.input(value=DashboardState.grid_night_rate, on_change=DashboardState.set_grid_night_rate, width="180px"),
                    rx.button("Apply cost settings", on_click=DashboardState.apply_cost_settings),
                    spacing="3",
                    wrap="wrap",
                ),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="wallet",
        ),
        panel(
            "Cost details",
            rx.vstack(
                kv("Import cost now", DashboardState.import_cost_now_text),
                kv("Export value now", DashboardState.export_value_now_text),
                kv("Daily import cost", DashboardState.daily_import_cost_text),
                kv("Daily export value", DashboardState.daily_export_value_text),
                kv("Daily net cost", DashboardState.daily_net_cost_text),
                kv("Capacity basis", DashboardState.capacity_basis_text),
                kv("Capacity note", DashboardState.capacity_warning_text),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="file_text",
        ),
        panel(
            "Hourly cost rows",
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Hour"),
                            rx.table.column_header_cell("Spot"),
                            rx.table.column_header_cell("Grid"),
                            rx.table.column_header_cell("Total"),
                            rx.table.column_header_cell("Import kW"),
                            rx.table.column_header_cell("Export kW"),
                            rx.table.column_header_cell("Import cost"),
                            rx.table.column_header_cell("Export value"),
                            rx.table.column_header_cell("Net cost"),
                        )
                    ),
                    rx.table.body(rx.foreach(DashboardState.cost_rows, cost_row)),
                    variant="surface",
                    size="2",
                    width="100%",
                ),
                overflow_x="auto",
                width="100%",
            ),
            icon="receipt",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def history_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["received_at"]),
        rx.table.cell(row["meter_time"]),
        rx.table.cell(row["meter"]),
        rx.table.cell(row["import_w"]),
        rx.table.cell(row["export_w"]),
        rx.table.cell(row["signed_grid_w"]),
        rx.table.cell(row["avg_v"]),
        rx.table.cell(row["l1_a"]),
        rx.table.cell(row["l2_a"]),
        rx.table.cell(row["l3_a"]),
        rx.table.cell(row["pf"]),
        rx.table.cell(row["rx"]),
        rx.table.cell(row["bad"]),
    )


def history_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Rows", DashboardState.db_summary, "database", "slate"),
            stat_card("Latest", DashboardState.latest_history_text, "clock_3", "blue"),
            stat_card(
                "Averages",
                rx.hstack(rx.text(DashboardState.avg_import_text), rx.text("|"), rx.text(DashboardState.avg_net_text), spacing="2"),
                "bar_chart_3",
                "cyan",
            ),
            stat_card("Peaks", DashboardState.peak_text, "chart_column", "amber"),
            columns="4",
            spacing="4",
            width="100%",
        ),
        panel(
            "Snapshot History",
            rx.vstack(
                rx.hstack(
                    rx.input(value=DashboardState.history_limit, on_change=DashboardState.set_history_limit, width="120px"),
                    rx.input(value=DashboardState.db_path, on_change=DashboardState.set_db_path),
                    rx.button(
                        "Refresh",
                        on_click=[
                            DashboardState.refresh_history,
                            DashboardState.refresh_analysis,
                            DashboardState.refresh_cost,
                            DashboardState.refresh_diagnostics,
                        ],
                    ),
                    rx.button("Apply DB", on_click=DashboardState.apply_db_path, variant="soft"),
                    spacing="3",
                    width="100%",
                    wrap="wrap",
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Received"),
                                rx.table.column_header_cell("Meter Time"),
                                rx.table.column_header_cell("Meter"),
                                rx.table.column_header_cell("Import W"),
                                rx.table.column_header_cell("Export W"),
                                rx.table.column_header_cell("Signed Grid W"),
                                rx.table.column_header_cell("Avg V"),
                                rx.table.column_header_cell("L1 A"),
                                rx.table.column_header_cell("L2 A"),
                                rx.table.column_header_cell("L3 A"),
                                rx.table.column_header_cell("PF"),
                                rx.table.column_header_cell("RX"),
                                rx.table.column_header_cell("Bad"),
                            )
                        ),
                        rx.table.body(rx.foreach(DashboardState.history_rows, history_row)),
                        variant="surface",
                        size="2",
                        width="100%",
                    ),
                    overflow_x="auto",
                    width="100%",
                ),
                spacing="4",
                width="100%",
                align="stretch",
            ),
            icon="history",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def log_line(line: str) -> rx.Component:
    return rx.text(line, font_family="monospace", size="2", white_space="pre-wrap")


def log_tab() -> rx.Component:
    return panel(
        "Serial / App Log",
        rx.box(
            rx.foreach(DashboardState.logs, log_line),
            bg=rx.color("slate", 2),
            border_radius="16px",
            padding="1em",
            min_height="520px",
            max_height="720px",
            overflow_y="auto",
            width="100%",
        ),
        icon="terminal",
    )


def index() -> rx.Component:
    return rx.theme(
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.heading("AMS HAN Gateway Tool", size="8"),
                        rx.text(
                            "Reflex dashboard with replay, cost, diagnostics and signature intelligence.",
                            color=rx.color("gray", 10),
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.button(
                            rx.color_mode_cond("Switch to dark mode", "Switch to light mode"),
                            on_click=rx.toggle_color_mode,
                            variant="soft",
                        ),
                        rx.button("Refresh Ports", on_click=DashboardState.refresh_ports, variant="soft"),
                        rx.button(
                            rx.cond(DashboardState.show_advanced, "Hide Advanced", "Show Advanced"),
                            on_click=DashboardState.toggle_advanced,
                            variant="soft",
                        ),
                        rx.button("Get Status", on_click=DashboardState.send_get_status, color_scheme="indigo"),
                        spacing="3",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.grid(
                    stat_card("Connection", DashboardState.connection_status, "plug", "blue"),
                    stat_card("Wi-Fi", DashboardState.wifi_summary, "wifi", "green"),
                    stat_card("MQTT", DashboardState.mqtt_state, "radio_tower", "violet"),
                    stat_card("Database", DashboardState.db_summary, "database", "slate"),
                    columns="repeat(4, minmax(0,1fr))",
                    spacing="4",
                    width="100%",
                ),
                rx.grid(
                    rx.cond(DashboardState.show_advanced, advanced_sidebar(), simple_sidebar()),
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Overview", value="live"),
                            rx.tabs.trigger("Analysis", value="analysis"),
                            rx.tabs.trigger("Diagnostics", value="diagnostics"),
                            rx.tabs.trigger("Daily", value="daily"),
                            rx.tabs.trigger("Cost", value="cost"),
                            rx.tabs.trigger("History", value="history"),
                            rx.tabs.trigger("Log", value="log"),
                        ),
                        rx.tabs.content(live_tab(), value="live"),
                        rx.tabs.content(analysis_tab(), value="analysis"),
                        rx.tabs.content(diagnostics_tab(), value="diagnostics"),
                        rx.tabs.content(daily_tab(), value="daily"),
                        rx.tabs.content(cost_tab(), value="cost"),
                        rx.tabs.content(history_tab(), value="history"),
                        rx.tabs.content(log_tab(), value="log"),
                        default_value="live",
                        width="100%",
                    ),
                    columns="300px minmax(0,1fr)",
                    spacing="4",
                    width="100%",
                    align="start",
                ),
                spacing="5",
                align="stretch",
                width="100%",
                max_width="1800px",
                margin="0 auto",
                padding="20px",
            ),
            bg=rx.color("gray", 1),
            min_height="100vh",
        ),
        accent_color="indigo",
        gray_color="slate",
        has_background=True,
    )


app = rx.App()
app.add_page(index, on_load=DashboardState.on_load)
