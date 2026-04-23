from __future__ import annotations

import reflex as rx

from .app_context import configure_default_app_context
from .app_meta import APP_AUTHOR, APP_NAME, APP_VERSION
from .components import brand_mark, capacity_step_card, dual_bar_card, hero_card, hint_banner, kv, panel, stat_card
from .domain.pricing import PRICE_AREAS

configure_default_app_context()

from .state import DashboardState

UPLOAD_ID = "replay_upload"
LIVE_SYNC_INTERVAL_MS = 2000
HEATMAP_HOURS = [f"{hour:02d}" for hour in range(24)]
HEATMAP_SWITCH_THRESHOLDS = [str(watts) for watts in range(100, 1600, 100)]
MAINS_NETWORK_TYPES = ["TN", "IT"]


def live_heartbeat() -> rx.Component:
    return rx.box(
        rx.moment(
            interval=LIVE_SYNC_INTERVAL_MS,
            on_change=DashboardState.live_tick.temporal,
        ),
        display="none",
    )


def replay_panel() -> rx.Component:
    return panel(
        "Replay or Demo Data",
        rx.vstack(
            rx.input(
                placeholder="Path to replay log file",
                value=DashboardState.replay_path,
                on_change=DashboardState.set_replay_path,
            ),
            rx.hstack(
                rx.button("Load Replay File", on_click=DashboardState.load_replay, color_scheme="blue"),
                rx.button("Load Demo Data", on_click=DashboardState.load_demo_replay, variant="soft"),
                spacing="2",
                width="100%",
                wrap="wrap",
            ),
            rx.upload(
                rx.button("Browse or Upload Replay File", variant="soft"),
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
                rx.button("Pause or Resume Replay", on_click=DashboardState.pause_or_resume_replay, variant="soft"),
                rx.button("Stop Replay", on_click=DashboardState.stop_replay, color_scheme="tomato", variant="soft"),
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
            "Connect Gateway",
            rx.vstack(
                rx.text(
                    "The app can scan for the gateway automatically and remembers the last working port.",
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.button("Rescan Ports", on_click=DashboardState.refresh_ports, variant="soft"),
                rx.button("Find Gateway Automatically", on_click=DashboardState.auto_connect_now, color_scheme="blue"),
                rx.button("Open Advanced Tools", on_click=DashboardState.toggle_advanced, variant="soft"),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="sparkles",
        ),
        panel(
            "Gateway Wi-Fi",
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
                    rx.button("Clear Wi-Fi", on_click=DashboardState.send_clear_wifi, variant="soft"),
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
            "MQTT Broker",
            rx.vstack(
                rx.input(placeholder="Broker address", value=DashboardState.mqtt_host, on_change=DashboardState.set_mqtt_host),
                rx.input(placeholder="Port", value=DashboardState.mqtt_port, on_change=DashboardState.set_mqtt_port),
                rx.input(placeholder="Username", value=DashboardState.mqtt_user, on_change=DashboardState.set_mqtt_user),
                rx.input(
                    placeholder="Password",
                    type="password",
                    value=DashboardState.mqtt_password,
                    on_change=DashboardState.set_mqtt_password,
                ),
                rx.input(placeholder="Topic prefix", value=DashboardState.mqtt_prefix, on_change=DashboardState.set_mqtt_prefix),
                rx.hstack(
                    rx.button("Save MQTT", on_click=DashboardState.send_set_mqtt, color_scheme="blue"),
                    rx.button("Enable MQTT", on_click=DashboardState.mqtt_enable, color_scheme="green"),
                    spacing="2",
                    width="100%",
                ),
                rx.button("Publish MQTT Discovery", on_click=DashboardState.republish_discovery, variant="soft"),
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
                rx.text("Serial port", size="2", color=rx.color("gray", 10)),
                rx.select(
                    DashboardState.ports,
                    value=DashboardState.selected_port,
                    on_change=DashboardState.set_selected_port,
                    placeholder="Choose a port",
                ),
                rx.text("Serial speed (baud)", size="2", color=rx.color("gray", 10)),
                rx.input(value=DashboardState.baudrate, read_only=True),
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
        panel(
            "Electrical Setup",
            rx.vstack(
                rx.text("Mains network type", size="2", color=rx.color("gray", 10)),
                rx.select(
                    MAINS_NETWORK_TYPES,
                    value=DashboardState.mains_network_type,
                    on_change=DashboardState.set_mains_network_type,
                    width="120px",
                ),
                rx.text(DashboardState.mains_network_note, size="2", color=rx.color("gray", 10)),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="circuit_board",
        ),
        replay_panel(),
        simple_sidebar(),
        panel(
            "Saved Data",
            rx.vstack(
                rx.input(value=DashboardState.db_path, on_change=DashboardState.set_db_path, placeholder="Database path"),
                rx.hstack(
                    rx.button("Use This Database", on_click=DashboardState.apply_db_path),
                    rx.button("Reload Saved Data", on_click=DashboardState.refresh_history, variant="soft"),
                    spacing="2",
                    width="100%",
                ),
                rx.button("Clear Saved History", on_click=DashboardState.clear_history, color_scheme="tomato", variant="soft"),
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
        "Latest Meter Reading",
        rx.cond(
            DashboardState.has_snapshot,
            rx.vstack(
                kv("Meter ID", DashboardState.snapshot_meter),
                kv("Meter timestamp", DashboardState.snapshot_meter_time),
                kv("Power now", DashboardState.snapshot_power),
                kv("Net grid flow", DashboardState.snapshot_grid_flow),
                kv("Reactive power", DashboardState.snapshot_reactive),
                kv("Voltage", DashboardState.snapshot_voltage),
                kv("Current", DashboardState.snapshot_current),
                kv("Power factor", DashboardState.snapshot_power_factor),
                kv("Internal counters", DashboardState.snapshot_counters),
                kv("Frame info", DashboardState.snapshot_stats),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            hint_banner(
                "No meter reading yet. Check the HAN adapter wiring or wait for the next long KFM_001 frame."
            ),
        ),
        icon="gauge",
        opacity=DashboardState.live_opacity,
    )


def device_status_panel() -> rx.Component:
    return panel(
        "Gateway Status",
        rx.vstack(
            kv("Gateway ID", DashboardState.device_id),
            kv("Firmware", DashboardState.firmware),
            kv("MAC address", DashboardState.mac),
            kv("Wi-Fi status", DashboardState.wifi_state),
            kv("IP address", DashboardState.wifi_ip),
            kv("MQTT status", DashboardState.mqtt_state),
            kv("Last telegram", DashboardState.last_frame),
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
        rx.grid(
            dual_bar_card(
                DashboardState.import_bar_width,
                DashboardState.export_bar_width,
                DashboardState.import_bar_text,
                DashboardState.export_bar_text,
                DashboardState.bar_scale_text,
                compact=True,
            ),
            capacity_step_card(
                DashboardState.capacity_step_text,
                DashboardState.capacity_price_text,
                DashboardState.capacity_basis_kw_text,
                DashboardState.capacity_basis_text,
                DashboardState.capacity_warning_text,
                DashboardState.capacity_steps,
            ),
            columns="minmax(0,1.15fr) minmax(320px,0.95fr)",
            spacing="4",
            width="100%",
            align="stretch",
        ),
        rx.grid(
            stat_card(
                "Usually buying or selling",
                DashboardState.signed_avg_text,
                "chart_line",
                "blue",
                "Based on recent meter readings.",
            ),
            stat_card(
                "Grid Energy This Hour",
                DashboardState.hour_energy_text,
                "clock_3",
                "indigo",
                DashboardState.hour_energy_detail_text,
            ),
            stat_card(
                "Grid Energy Today",
                DashboardState.day_energy_text,
                "calendar",
                "cyan",
                DashboardState.day_energy_detail_text,
            ),
            stat_card(
                "Grid Energy This Week",
                DashboardState.week_energy_text,
                "calendar_range",
                "amber",
                DashboardState.week_energy_detail_text,
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
                rx.button("Read Device Info", on_click=DashboardState.send_get_info, color_scheme="indigo"),
                rx.button("Refresh Status", on_click=DashboardState.send_get_status, color_scheme="indigo"),
                rx.button("Publish MQTT Discovery", on_click=DashboardState.republish_discovery, variant="soft"),
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
        "Phase and Voltage Details",
        rx.vstack(
            kv("Current right now", DashboardState.phase_latest_text),
            kv("Average current", DashboardState.phase_avg_text),
            kv("Most loaded line", DashboardState.phase_dominant_text),
            kv("Current imbalance", DashboardState.phase_imbalance_text),
            kv("Voltage right now", DashboardState.voltage_latest_text),
            kv("Average voltage", DashboardState.voltage_avg_text),
            kv("Lowest voltage seen", DashboardState.voltage_min_text),
            kv("Largest voltage spread", DashboardState.voltage_spread_text),
            spacing="3",
            width="100%",
            align="stretch",
        ),
        icon="activity",
    )


def top_hour_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row.hour),
        rx.table.cell(row.avg_import),
        rx.table.cell(row.avg_export),
        rx.table.cell(row.avg_signed),
    )


def event_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row.time),
        rx.table.cell(row.category),
        rx.table.cell(row.type),
        rx.table.cell(row.status),
        rx.table.cell(row.severity),
        rx.table.cell(row.confidence),
        rx.table.cell(row.delta_signed),
        rx.table.cell(row.phase),
        rx.table.cell(row.note),
    )


def signature_row(row: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row.signature),
        rx.table.cell(row.phase),
        rx.table.cell(row.typical_w),
        rx.table.cell(row.events),
        rx.table.cell(row.avg_runtime),
        rx.table.cell(row.starts_per_day),
        rx.table.cell(row.common_start_hour),
        rx.table.cell(row.weekday_weekend),
        rx.table.cell(row.last_seen),
        rx.table.cell(row.confidence),
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
            stat_card("Usually buying or selling", DashboardState.signed_avg_text, "chart_line", "blue", DashboardState.import_samples_text),
            stat_card("This hour so far", DashboardState.current_hour_text, "clock_3", "cyan", DashboardState.projected_hour_text),
            stat_card("Biggest import hour", DashboardState.import_peak_text, "trending_up", "amber", DashboardState.export_peak_text),
            stat_card("Most loaded line", DashboardState.phase_dominant_text, "gauge", "violet", DashboardState.phase_imbalance_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        phase_analysis_panel(),
        panel(
            "Detected Repeating Loads",
            rx.vstack(
                rx.text(
                    DashboardState.signature_assignment_text,
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Signature"),
                                rx.table.column_header_cell("Phase"),
                                rx.table.column_header_cell("Typical W"),
                                rx.table.column_header_cell("Detections"),
                                rx.table.column_header_cell("Avg runtime"),
                                rx.table.column_header_cell("Starts per day"),
                                rx.table.column_header_cell("Most common start"),
                                rx.table.column_header_cell("Weekday / Weekend"),
                                rx.table.column_header_cell("Last Seen"),
                                rx.table.column_header_cell("Confidence"),
                            )
                        ),
                        rx.table.body(rx.foreach(DashboardState.signature_rows, signature_row)),
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
            icon="fingerprint",
        ),
        panel(
            "Busiest Hours",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Hour"),
                        rx.table.column_header_cell("Avg import W"),
                        rx.table.column_header_cell("Avg export W"),
                        rx.table.column_header_cell("Net grid W"),
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
            "Current Warnings",
            rx.cond(
                DashboardState.has_diagnostics_issues,
                rx.vstack(rx.foreach(DashboardState.diagnostics_issues, issue_line), spacing="2", align="start", width="100%"),
                hint_banner("No active warnings right now.", "green"),
            ),
            icon="triangle_alert",
        ),
        panel(
            "System Health",
            rx.vstack(rx.foreach(DashboardState.health_rows, health_row), spacing="2", align="start", width="100%"),
            icon="shield",
        ),
        panel(
            "Event Timeline",
            rx.vstack(
                rx.hstack(
                    rx.button("All", on_click=DashboardState.set_event_filter("all"), variant="soft"),
                    rx.button("Active", on_click=DashboardState.set_event_filter("open"), variant="soft"),
                    rx.button("Resolved", on_click=DashboardState.set_event_filter("resolved"), variant="soft"),
                    rx.button("Severe", on_click=DashboardState.set_event_filter("severe"), variant="soft"),
                    rx.button("Power", on_click=DashboardState.set_event_filter("power"), variant="soft"),
                    rx.button("Voltage", on_click=DashboardState.set_event_filter("voltage"), variant="soft"),
                    rx.button("Phase", on_click=DashboardState.set_event_filter("phase"), variant="soft"),
                    rx.button("Data Quality", on_click=DashboardState.set_event_filter("data_quality"), variant="soft"),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Time"),
                                rx.table.column_header_cell("Category"),
                                rx.table.column_header_cell("Event"),
                                rx.table.column_header_cell("Status"),
                                rx.table.column_header_cell("Severity"),
                                rx.table.column_header_cell("Confidence"),
                                rx.table.column_header_cell("Power change"),
                                rx.table.column_header_cell("Phase"),
                                rx.table.column_header_cell("Explanation"),
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
        "Daily Usage Graph",
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
                "This graph shows the latest day with data. Blue bars show power bought from the grid, green bars show power sent back, and the line shows the net grid direction.",
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
            stat_card("Latest Day With Data", DashboardState.daily_date_text, "calendar", "blue", DashboardState.daily_hours_text),
            stat_card("Highest Hour", DashboardState.daily_peak_text, "chart_column", "amber", "Based on hourly averages"),
            stat_card("Usually buying or selling", DashboardState.signed_avg_text, "chart_line", "cyan", "Across the recent saved samples"),
            stat_card("This hour so far", DashboardState.current_hour_text, "clock_3", "indigo", DashboardState.projected_hour_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        daily_graph_panel(),
        panel(
            "Hour-By-Hour Summary",
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Hour"),
                        rx.table.column_header_cell("Avg import kW"),
                        rx.table.column_header_cell("Avg export kW"),
                        rx.table.column_header_cell("Net grid kW"),
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


def heatmap_hour_header(hour: str) -> rx.Component:
    return rx.box(
        rx.text(hour, size="2", weight="medium", color=rx.color("gray", 10), text_align="center"),
        width="68px",
        min_width="68px",
        padding="0.25em 0",
    )


def heatmap_cell(cell) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(
                cell.primary,
                size="2",
                weight="bold",
                color=rx.color_mode_cond(cell.light_text_color, cell.text_color),
                line_height="1.1",
            ),
            rx.text(
                cell.secondary,
                size="1",
                color=rx.color_mode_cond(cell.light_secondary_color, cell.secondary_color),
                line_height="1.15",
            ),
            rx.text(
                cell.tertiary,
                size="1",
                color=rx.color_mode_cond(cell.light_secondary_color, cell.secondary_color),
                line_height="1.15",
            ),
            spacing="1",
            align="start",
            width="100%",
        ),
        width="68px",
        min_width="68px",
        min_height="82px",
        padding="0.55em",
        border_radius="14px",
        bg=rx.color_mode_cond(cell.light_bg, cell.bg),
        border=rx.color_mode_cond(cell.light_border, cell.border),
        title=cell.tooltip,
        box_shadow=rx.color_mode_cond(
            "inset 0 1px 0 rgba(255,255,255,0.88), 0 1px 3px rgba(15,23,42,0.08)",
            "inset 0 1px 0 rgba(255,255,255,0.06)",
        ),
    )


def heatmap_row(row) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.vstack(
                rx.text(row.label, size="2", weight="bold"),
                rx.text(row.peak_text, size="1", color=rx.color("gray", 10)),
                rx.text(row.change_text, size="1", color=rx.color("gray", 10)),
                spacing="1",
                align="start",
            ),
            width="150px",
            min_width="150px",
            padding_right="0.5em",
        ),
        rx.foreach(row.cells, heatmap_cell),
        spacing="2",
        align="stretch",
        width="max-content",
    )


def heatmap_legend() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.box(width="18px", height="18px", border_radius="6px", bg="rgba(37, 99, 235, 0.55)", border="1px solid rgba(148, 163, 184, 0.28)"),
            rx.text("Mostly buying power from the grid", size="2", color=rx.color("gray", 10)),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.box(width="18px", height="18px", border_radius="6px", bg="rgba(22, 163, 74, 0.55)", border="1px solid rgba(148, 163, 184, 0.28)"),
            rx.text("Mostly sending power back", size="2", color=rx.color("gray", 10)),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.box(
                width="18px",
                height="18px",
                border_radius="6px",
                bg="linear-gradient(135deg, rgba(100, 116, 139, 0.18) 0%, rgba(100, 116, 139, 0.18) 74%, rgba(250, 204, 21, 0.82) 84%, rgba(249, 115, 22, 0.86) 92%, rgba(239, 68, 68, 0.92) 100%)",
                border="1px solid rgba(148, 163, 184, 0.28)",
            ),
            rx.text("Corner color shows switching: none = quiet, yellow = light, orange = medium, red = busiest hour.", size="2", color=rx.color("gray", 10)),
            spacing="2",
            align="center",
        ),
        spacing="4",
        wrap="wrap",
        width="100%",
    )


def heatmap_grid(rows, description: str) -> rx.Component:
    return rx.vstack(
        rx.text(description, size="2", color=rx.color("gray", 10)),
        heatmap_legend(),
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.box(width="150px", min_width="150px"),
                    rx.foreach(HEATMAP_HOURS, heatmap_hour_header),
                    spacing="2",
                    width="max-content",
                ),
                rx.foreach(rows, heatmap_row),
                spacing="2",
                width="max-content",
                align="stretch",
            ),
            overflow_x="auto",
            overflow_y="hidden",
            padding_bottom="14px",
            scrollbar_gutter="stable",
            width="100%",
        ),
        spacing="3",
        width="100%",
        align="stretch",
    )


def heatmap_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Days Included", DashboardState.heatmap_days_text, "calendar_range", "blue", "Built from time-weighted hourly buckets"),
            stat_card("Highest-Use Hour", DashboardState.heatmap_peak_text, "flame", "amber", "The hour with the highest average usage"),
            stat_card("Most Switching", DashboardState.heatmap_change_text, "activity", "violet", "The busiest hour for load changes at the chosen threshold"),
            stat_card("Busiest Weekday", DashboardState.heatmap_weekday_text, "chart_no_axes_combined", "green", "Average weekday profile with the highest use"),
            columns="4",
            spacing="4",
            width="100%",
        ),
        panel(
            "Usage Map Settings",
            rx.hstack(
                rx.vstack(
                    rx.text("Minimum load change to count", size="2", color=rx.color("gray", 10)),
                    rx.text(
                        DashboardState.heatmap_assignment_text,
                        size="2",
                        color=rx.color("gray", 10),
                    ),
                    align="start",
                    spacing="1",
                    width="100%",
                ),
                rx.hstack(
                    rx.select(
                        HEATMAP_SWITCH_THRESHOLDS,
                        value=DashboardState.heatmap_switch_threshold,
                        on_change=DashboardState.set_heatmap_switch_threshold,
                        width="120px",
                    ),
                    rx.text("W", size="3", weight="medium"),
                    spacing="2",
                    align="center",
                ),
                spacing="4",
                width="100%",
                justify="between",
                align="center",
                wrap="wrap",
            ),
            icon="sliders_horizontal",
        ),
        panel(
            "Recent Days By Hour",
            heatmap_grid(
                DashboardState.heatmap_recent_rows,
                DashboardState.heatmap_recent_description,
            ),
            icon="grid_3x3",
        ),
        panel(
            "Typical Weekday Pattern",
            heatmap_grid(
                DashboardState.heatmap_weekday_rows,
                "This view groups the same data by weekday, making repeated routines such as morning heating, cooking, or export windows easier to spot.",
            ),
            icon="calendar_days",
        ),
        spacing="4",
        width="100%",
        align="stretch",
    )


def cost_row(row: dict[str, float | str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row.hour),
        rx.table.cell(row.spot_nok_kwh),
        rx.table.cell(row.grid_nok_kwh),
        rx.table.cell(row.total_nok_kwh),
        rx.table.cell(row.import_kw),
        rx.table.cell(row.export_kw),
        rx.table.cell(row.import_cost_nok),
        rx.table.cell(row.export_value_nok),
        rx.table.cell(row.net_cost_nok),
    )


def cost_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Price Area", DashboardState.price_area, "badge_cent", "violet", DashboardState.cost_source_text),
            stat_card("Spot Price Now", DashboardState.spot_now_text, "clock_3", "blue", DashboardState.grid_now_text),
            stat_card("Total Price Now", DashboardState.total_now_text, "wallet", "green", DashboardState.current_hour_cost_text),
            stat_card("Current Tariff Step", DashboardState.capacity_step_text, "gauge", "amber", DashboardState.capacity_price_text),
            columns="4",
            spacing="4",
            width="100%",
        ),
        rx.cond(
            DashboardState.has_cost_warning,
            panel(
                "Price Warning",
                hint_banner(DashboardState.cost_warning_text, "amber"),
                icon="triangle_alert",
            ),
            rx.fragment(),
        ),
        panel(
            "Electricity Price Settings",
            rx.vstack(
                rx.select(PRICE_AREAS, value=DashboardState.price_area, on_change=DashboardState.set_price_area),
                rx.hstack(
                    rx.input(placeholder="Daytime grid tariff (NOK/kWh)", value=DashboardState.grid_day_rate, on_change=DashboardState.set_grid_day_rate, width="220px"),
                    rx.input(placeholder="Night grid tariff (NOK/kWh)", value=DashboardState.grid_night_rate, on_change=DashboardState.set_grid_night_rate, width="220px"),
                    rx.button("Save Electricity Prices", on_click=DashboardState.apply_cost_settings),
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
            "Today's Cost Summary",
            rx.vstack(
                kv("Import cost right now", DashboardState.import_cost_now_text),
                kv("Export value right now", DashboardState.export_value_now_text),
                kv("Import cost today", DashboardState.daily_import_cost_text),
                kv("Export value today", DashboardState.daily_export_value_text),
                kv("Net cost today", DashboardState.daily_net_cost_text),
                kv("Tariff based on", DashboardState.capacity_basis_text),
                kv("Tariff note", DashboardState.capacity_warning_text),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            icon="file_text",
        ),
        panel(
            "Hourly Cost Breakdown",
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Hour"),
                            rx.table.column_header_cell("Spot NOK/kWh"),
                            rx.table.column_header_cell("Grid NOK/kWh"),
                            rx.table.column_header_cell("Total NOK/kWh"),
                            rx.table.column_header_cell("Avg import kW"),
                            rx.table.column_header_cell("Avg export kW"),
                            rx.table.column_header_cell("Import cost NOK"),
                            rx.table.column_header_cell("Export value NOK"),
                            rx.table.column_header_cell("Net cost NOK"),
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
        rx.table.cell(row.received_at),
        rx.table.cell(row.meter_time),
        rx.table.cell(row.meter),
        rx.table.cell(row.import_w),
        rx.table.cell(row.export_w),
        rx.table.cell(row.signed_grid_w),
        rx.table.cell(row.avg_v),
        rx.table.cell(row.l1_a),
        rx.table.cell(row.l2_a),
        rx.table.cell(row.l3_a),
        rx.table.cell(row.pf),
        rx.table.cell(row.rx),
        rx.table.cell(row.bad),
    )


def history_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            stat_card("Stored Readings", DashboardState.db_summary, "database", "slate"),
            stat_card("Most Recent Reading", DashboardState.latest_history_text, "clock_3", "blue"),
            stat_card(
                "Average Power",
                rx.hstack(rx.text(DashboardState.avg_import_text), rx.text("|"), rx.text(DashboardState.avg_net_text), spacing="2"),
                "bar_chart_3",
                "cyan",
            ),
            stat_card("Peak Power", DashboardState.peak_text, "chart_column", "amber"),
            columns="4",
            spacing="4",
            width="100%",
        ),
        panel(
            "Saved Meter Readings",
            rx.vstack(
                rx.hstack(
                    rx.input(placeholder="How many rows to show", value=DashboardState.history_limit, on_change=DashboardState.set_history_limit, width="170px"),
                    rx.input(placeholder="Database path", value=DashboardState.db_path, on_change=DashboardState.set_db_path),
                    rx.button(
                        "Reload Saved Data",
                        on_click=[
                            DashboardState.refresh_history,
                            DashboardState.refresh_analysis,
                            DashboardState.refresh_cost,
                            DashboardState.refresh_diagnostics,
                        ],
                    ),
                    rx.button("Use This Database", on_click=DashboardState.apply_db_path, variant="soft"),
                    spacing="3",
                    width="100%",
                    wrap="wrap",
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Received"),
                                rx.table.column_header_cell("Meter timestamp"),
                                rx.table.column_header_cell("Meter ID"),
                                rx.table.column_header_cell("Import W"),
                                rx.table.column_header_cell("Export W"),
                                rx.table.column_header_cell("Net grid W"),
                                rx.table.column_header_cell("Avg voltage"),
                                rx.table.column_header_cell("L1 current"),
                                rx.table.column_header_cell("L2 current"),
                                rx.table.column_header_cell("L3 current"),
                                rx.table.column_header_cell("Power factor"),
                                rx.table.column_header_cell("Frames received"),
                                rx.table.column_header_cell("Bad frames"),
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
        "Connection Log",
        rx.vstack(
            rx.text(
                "Newest serial and app messages are shown first.",
                size="2",
                color=rx.color("gray", 10),
            ),
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
            spacing="3",
            width="100%",
        ),
        icon="terminal",
    )


def index() -> rx.Component:
    return rx.theme(
        rx.box(
            rx.vstack(
                live_heartbeat(),
                rx.hstack(
                    rx.hstack(
                        brand_mark(),
                        rx.vstack(
                            rx.heading(APP_NAME, size="8", line_height="1.0"),
                            rx.text(
                                "Live dashboard for current power, usage patterns, costs, warnings, load signatures and replay.",
                                color=rx.color("gray", 10),
                            ),
                            rx.hstack(
                                rx.badge(f"Dashboard {APP_VERSION}", variant="soft", color_scheme="blue"),
                                rx.badge(f"Author: {APP_AUTHOR}", variant="soft", color_scheme="gray"),
                                spacing="2",
                                wrap="wrap",
                            ),
                            spacing="1",
                            align="start",
                            justify="center",
                            min_height="82px",
                        ),
                        spacing="3",
                        align="center",
                        padding_left="12px",
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.button(
                            rx.color_mode_cond("Switch to dark mode", "Switch to light mode"),
                            on_click=rx.toggle_color_mode,
                            variant="soft",
                        ),
                        rx.button("Rescan Ports", on_click=DashboardState.refresh_ports, variant="soft"),
                        rx.button(
                            rx.cond(DashboardState.show_advanced, "Hide Advanced Tools", "Show Advanced Tools"),
                            on_click=DashboardState.toggle_advanced,
                            variant="soft",
                        ),
                        rx.button("Read Status Now", on_click=DashboardState.send_get_status, color_scheme="indigo"),
                        spacing="3",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.grid(
                    stat_card("Gateway Connection", DashboardState.connection_status, "plug", "blue"),
                    stat_card("Gateway Wi-Fi", DashboardState.wifi_summary, "wifi", "green"),
                    stat_card("MQTT Connection", DashboardState.mqtt_state, "radio_tower", "violet"),
                    stat_card("Saved Meter Readings", DashboardState.db_summary, "database", "slate"),
                    columns="repeat(4, minmax(0,1fr))",
                    spacing="4",
                    width="100%",
                ),
                rx.grid(
                    rx.cond(DashboardState.show_advanced, advanced_sidebar(), simple_sidebar()),
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Live View", value="live"),
                            rx.tabs.trigger("Power Patterns", value="analysis"),
                            rx.tabs.trigger("Warnings", value="diagnostics"),
                        rx.tabs.trigger("Daily Use", value="daily"),
                        rx.tabs.trigger("Usage Map", value="heatmap"),
                        rx.tabs.trigger("Costs", value="cost"),
                        rx.tabs.trigger("History", value="history"),
                        rx.tabs.trigger("Connection Log", value="log"),
                    ),
                    rx.tabs.content(live_tab(), value="live"),
                    rx.tabs.content(analysis_tab(), value="analysis"),
                    rx.tabs.content(diagnostics_tab(), value="diagnostics"),
                    rx.tabs.content(daily_tab(), value="daily"),
                        rx.tabs.content(heatmap_tab(), value="heatmap"),
                        rx.tabs.content(cost_tab(), value="cost"),
                        rx.tabs.content(history_tab(), value="history"),
                        rx.tabs.content(log_tab(), value="log"),
                        default_value="live",
                        value=DashboardState.current_tab,
                        on_change=DashboardState.set_current_tab,
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


app = rx.App(toaster=None)
app.add_page(index, on_load=DashboardState.on_load)
