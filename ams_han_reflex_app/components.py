from __future__ import annotations

import reflex as rx


def stat_card(title: str, value, icon: str, accent: str = 'indigo', subtitle=None) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=18),
                    bg=rx.color(accent, 3),
                    color=rx.color(accent, 11),
                    border_radius='12px',
                    padding='8px',
                ),
                rx.text(title, size='2', color=rx.color('gray', 10)),
                align='center',
                spacing='3',
            ),
            rx.text(value, size='5', weight='bold'),
            rx.cond(subtitle is not None, rx.text(subtitle, size='2', color=rx.color('gray', 10)), rx.fragment()),
            spacing='2',
            align='start',
            width='100%',
        ),
        size='3',
        border_radius='18px',
        width='100%',
        box_shadow='0 2px 12px rgba(15,23,42,0.04)',
    )


def hero_card(title, value, subtitle, accent: str = 'blue') -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag='zap', size=20, color=rx.color(accent, 10)),
                rx.text(title, size='3', color=rx.color('gray', 11), weight='medium'),
                align='center', spacing='2',
            ),
            rx.text(value, size='8', weight='bold'),
            rx.text(subtitle, size='3', color=rx.color('gray', 10)),
            spacing='2', align='start', width='100%',
        ),
        size='4', border_radius='22px', width='100%',
        bg=f"linear-gradient(135deg, {rx.color(accent, 2)}, {rx.color('gray', 1)})",
        border=f"1px solid {rx.color(accent, 4)}",
    )


def panel(title: str, *children, icon: str | None = None, opacity: str = '1.0') -> rx.Component:
    header = rx.hstack(
        rx.cond(bool(icon), rx.icon(tag=icon or 'circle', size=16), rx.fragment()),
        rx.heading(title, size='4'),
        align='center', spacing='2', width='100%',
    )
    return rx.card(
        rx.vstack(header, rx.box(*children, width='100%'), spacing='4', width='100%', align='stretch'),
        size='3', border_radius='20px', width='100%', opacity=opacity,
        box_shadow='0 2px 12px rgba(15,23,42,0.04)',
    )


def kv(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label, size='2', color=rx.color('gray', 10), width='136px', flex_shrink='0'),
        rx.text(value, size='3', weight='medium', text_align='right'),
        justify='between', width='100%', gap='3',
    )


def hint_banner(text, tone: str = 'blue') -> rx.Component:
    return rx.box(
        rx.text(text, size='3', color=rx.color('gray', 11)),
        bg=rx.color(tone, 2), border=f"1px solid {rx.color(tone, 5)}",
        border_radius='16px', padding='1em 1.2em', width='100%',
    )


def tiny_metric(title: str, value, accent: str = 'blue') -> rx.Component:
    return rx.box(
        rx.text(title, size='2', color=rx.color('gray', 10)),
        rx.text(value, size='5', weight='bold', color=rx.color(accent, 11)),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius='16px', padding='0.9em 1.1em', width='100%', bg=rx.color('gray', 2),
    )


def dual_bar_card(import_width, export_width, import_text, export_text, scale_text) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(rx.icon(tag='chart_column', size=18), rx.heading('Import / Export', size='4'), align='center', spacing='2'),
            rx.vstack(
                rx.hstack(rx.text('Import', size='2', color=rx.color('gray', 10)), rx.spacer(), rx.text(import_text, size='3', weight='medium'), width='100%'),
                rx.box(
                    rx.box(width=import_width, height='12px', bg=rx.color('blue', 9), border_radius='999px'),
                    bg=rx.color('blue', 3), width='100%', height='12px', border_radius='999px', overflow='hidden'
                ),
                rx.hstack(rx.text('Export', size='2', color=rx.color('gray', 10)), rx.spacer(), rx.text(export_text, size='3', weight='medium'), width='100%'),
                rx.box(
                    rx.box(width=export_width, height='12px', bg=rx.color('green', 9), border_radius='999px'),
                    bg=rx.color('green', 3), width='100%', height='12px', border_radius='999px', overflow='hidden'
                ),
                rx.text(scale_text, size='2', color=rx.color('gray', 10)),
                spacing='2', width='100%', align='stretch'
            ),
            spacing='3', align='stretch', width='100%'
        ),
        size='3', border_radius='20px', width='100%', box_shadow='0 2px 12px rgba(15,23,42,0.04)'
    )
