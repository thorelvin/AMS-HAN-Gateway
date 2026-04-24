"""Reusable Reflex UI building blocks shared across the dashboard."""

from __future__ import annotations

import reflex as rx


def stat_card(title: str, value, icon: str, accent: str = "indigo", subtitle=None) -> rx.Component:
    value_node = value if isinstance(value, rx.Component) else rx.text(value, size="5", weight="bold")
    subtitle_node = (
        subtitle if isinstance(subtitle, rx.Component) else rx.text(subtitle, size="2", color=rx.color("gray", 10))
    )
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=18),
                    bg=rx.color(accent, 3),
                    color=rx.color(accent, 11),
                    border_radius="12px",
                    padding="8px",
                ),
                rx.text(title, size="2", color=rx.color("gray", 10)),
                align="center",
                spacing="3",
            ),
            value_node,
            rx.cond(subtitle is not None, subtitle_node, rx.fragment()),
            spacing="2",
            align="start",
            width="100%",
        ),
        size="3",
        border_radius="18px",
        width="100%",
        box_shadow="0 2px 12px rgba(15,23,42,0.04)",
    )


def hero_card(title, value, subtitle, accent: str = "blue") -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="zap", size=20, color=rx.color(accent, 10)),
                rx.text(title, size="3", color=rx.color("gray", 11), weight="medium"),
                align="center",
                spacing="2",
            ),
            rx.text(value, size="8", weight="bold"),
            rx.text(subtitle, size="3", color=rx.color("gray", 10)),
            spacing="2",
            align="start",
            width="100%",
        ),
        size="4",
        border_radius="22px",
        width="100%",
        bg=f"linear-gradient(135deg, {rx.color(accent, 2)}, {rx.color('gray', 1)})",
        border=f"1px solid {rx.color(accent, 4)}",
    )


def brand_mark() -> rx.Component:
    return rx.box(
        rx.icon(tag="zap", size=36),
        width="82px",
        height="82px",
        border_radius="22px",
        display="flex",
        align_items="center",
        justify_content="center",
        color="white",
        bg="linear-gradient(145deg, #1d4ed8 0%, #0f766e 58%, #f59e0b 100%)",
        flex_shrink="0",
    )


def panel(title: str, *children, icon: str | None = None, opacity: str = "1.0") -> rx.Component:
    header = rx.hstack(
        rx.cond(bool(icon), rx.icon(tag=icon or "circle", size=16), rx.fragment()),
        rx.heading(title, size="4"),
        align="center",
        spacing="2",
        width="100%",
    )
    return rx.card(
        rx.vstack(header, rx.box(*children, width="100%"), spacing="4", width="100%", align="stretch"),
        size="3",
        border_radius="20px",
        width="100%",
        opacity=opacity,
        box_shadow="0 2px 12px rgba(15,23,42,0.04)",
    )


def kv(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="2", color=rx.color("gray", 10), width="136px", flex_shrink="0"),
        rx.text(value, size="3", weight="medium", text_align="right"),
        justify="between",
        width="100%",
        gap="3",
    )


def hint_banner(text, tone: str = "blue") -> rx.Component:
    return rx.box(
        rx.text(text, size="3", color=rx.color("gray", 11)),
        bg=rx.color(tone, 2),
        border=f"1px solid {rx.color(tone, 5)}",
        border_radius="16px",
        padding="1em 1.2em",
        width="100%",
    )


def tiny_metric(title: str, value, accent: str = "blue") -> rx.Component:
    return rx.box(
        rx.text(title, size="2", color=rx.color("gray", 10)),
        rx.text(value, size="5", weight="bold", color=rx.color(accent, 11)),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="16px",
        padding="0.9em 1.1em",
        width="100%",
        bg=rx.color("gray", 2),
    )


def dual_bar_card(
    import_width, export_width, import_text, export_text, scale_text, compact: bool = False
) -> rx.Component:
    bar_height = "34px" if compact else "40px"
    size = "2" if compact else "3"
    inner_spacing = "4" if compact else "4"
    body_padding = "1.1em 1.1em" if compact else None
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="chart_column", size=18),
                rx.heading("Power Flow Now", size="4"),
                align="center",
                spacing="2",
            ),
            rx.vstack(
                rx.vstack(
                    rx.hstack(
                        rx.text("From grid", size="2", color=rx.color("gray", 10)),
                        rx.spacer(),
                        rx.text(import_text, size="3", weight="medium"),
                        width="100%",
                    ),
                    rx.box(
                        rx.box(width=import_width, height=bar_height, bg=rx.color("blue", 9), border_radius="999px"),
                        bg=rx.color("blue", 3),
                        width="100%",
                        height=bar_height,
                        border_radius="999px",
                        overflow="hidden",
                    ),
                    rx.hstack(
                        rx.text("To grid", size="2", color=rx.color("gray", 10)),
                        rx.spacer(),
                        rx.text(export_text, size="3", weight="medium"),
                        width="100%",
                    ),
                    rx.box(
                        rx.box(width=export_width, height=bar_height, bg=rx.color("green", 9), border_radius="999px"),
                        bg=rx.color("green", 3),
                        width="100%",
                        height=bar_height,
                        border_radius="999px",
                        overflow="hidden",
                    ),
                    spacing="3",
                    width="100%",
                    align="stretch",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(scale_text, size="2", color=rx.color("gray", 10)),
                    rx.hstack(
                        rx.hstack(
                            rx.box(width="10px", height="10px", border_radius="999px", bg=rx.color("blue", 9)),
                            rx.text("Blue means power bought from the grid", size="2", color=rx.color("gray", 10)),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.box(width="10px", height="10px", border_radius="999px", bg=rx.color("green", 9)),
                            rx.text("Green means power sent back to the grid", size="2", color=rx.color("gray", 10)),
                            spacing="2",
                            align="center",
                        ),
                        spacing="4",
                        wrap="wrap",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                    align="stretch",
                ),
                spacing="4",
                width="100%",
                align="stretch",
                height="100%",
            ),
            spacing=inner_spacing,
            align="stretch",
            justify="start",
            width="100%",
            height="100%",
        ),
        size=size,
        padding=body_padding,
        border_radius="20px",
        width="100%",
        height="100%",
        align_self="stretch",
        box_shadow="0 2px 12px rgba(15,23,42,0.04)",
    )


def _capacity_step_block(step) -> rx.Component:
    border = rx.cond(
        step.status == "passed",
        f"1px solid {rx.color('green', 6)}",
        rx.cond(
            step.status == "active",
            f"1px solid {rx.color('amber', 7)}",
            f"1px solid {rx.color('gray', 5)}",
        ),
    )
    bg = rx.cond(
        step.status == "passed",
        rx.color("green", 3),
        rx.cond(
            step.status == "active",
            rx.color("amber", 3),
            rx.color("gray", 3),
        ),
    )
    fill_bg = rx.cond(
        step.status == "passed",
        rx.color("green", 9),
        rx.cond(
            step.status == "active",
            "linear-gradient(180deg, var(--amber-9), #f97316)",
            rx.color("gray", 6),
        ),
    )
    label_color = rx.cond(
        step.status == "future",
        rx.color("gray", 10),
        rx.color("gray", 12),
    )
    price_color = rx.cond(
        step.status == "future",
        rx.color("gray", 9),
        rx.color("gray", 11),
    )
    label_weight = rx.cond(step.status == "active", "bold", "medium")
    badge = rx.cond(
        step.status == "active",
        rx.badge("Now", variant="soft", color_scheme="amber"),
        rx.fragment(),
    )
    return rx.hstack(
        rx.box(
            rx.box(
                width="100%",
                height=step.fill_percent,
                bg=fill_bg,
                border_radius="8px",
            ),
            bg=bg,
            border=border,
            border_radius="10px",
            height="34px",
            width="52px",
            overflow="hidden",
            display="flex",
            align_items="end",
            justify_content="end",
            box_shadow="inset 0 1px 0 rgba(255,255,255,0.06)",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.hstack(
                rx.text(step.label, size="2", color=label_color, weight=label_weight),
                badge,
                spacing="2",
                width="100%",
                wrap="wrap",
            ),
            rx.text(step.price_text, size="1", color=price_color),
            spacing="1",
            align="start",
            width="100%",
        ),
        spacing="3",
        align="center",
        width="100%",
    )


def capacity_step_card(step_label, step_price_text, basis_kw_text, basis_text, warning_text, steps) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="gauge", size=18),
                    rx.heading("Capacity Step Estimate", size="4"),
                    align="center",
                    spacing="2",
                ),
                rx.text(
                    "Built-in utility tiers are reference defaults. Compare them with your local tariff.",
                    size="1",
                    color=rx.color("gray", 10),
                ),
                spacing="1",
                align="start",
                width="100%",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text(step_label, size="6", weight="bold"),
                    rx.text(step_price_text, size="2", color=rx.color("amber", 10), weight="medium"),
                    rx.text(basis_kw_text, size="3", color=rx.color("gray", 11), weight="medium"),
                    rx.text(basis_text, size="2", color=rx.color("gray", 10)),
                    rx.text(warning_text, size="2", color=rx.color("gray", 10)),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
                rx.box(
                    rx.vstack(
                        rx.foreach(steps, _capacity_step_block),
                        spacing="2",
                        align="stretch",
                        width="100%",
                    ),
                    min_width="182px",
                    width="100%",
                ),
                spacing="4",
                align="start",
                width="100%",
            ),
            spacing="3",
            align="stretch",
            width="100%",
        ),
        size="3",
        border_radius="20px",
        width="100%",
        box_shadow="0 2px 12px rgba(15,23,42,0.04)",
    )
