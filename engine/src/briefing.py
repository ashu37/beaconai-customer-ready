
from __future__ import annotations
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .utils import (
    detect_growth_stage, select_priority_charts, generate_growth_insights,
    generate_vertical_insights, select_priority_kpis, get_vertical_mode,
    organize_by_engine_tiers, get_confidence_display_data
)
from .storytelling import build_briefing_story
from .engine_run import EngineRun
from .storytelling_v2 import render_engine_run as _render_engine_run_v2


def render_briefing(
    template_dir: str,
    out_path: str,
    brand: str,
    aligned,
    outputs,
    *,
    engine_run: Optional[EngineRun] = None,
    use_v2: bool = False,
):
    """Render the merchant briefing.

    Default behavior (legacy): ``use_v2=False`` and ``engine_run=None`` ->
    render the legacy Jinja-based briefing template. This is the path
    that has shipped through M0-M7. M8 does NOT change this default.

    V2 behavior (T8.6): when ``use_v2=True`` AND a populated
    :class:`EngineRun` is passed in, render the new merchant-facing Play
    Thesis layout via :func:`src.storytelling_v2.render_engine_run`.
    The legacy template is bypassed entirely.

    The router's flag-on path is intentionally narrow: it does NOT touch
    the legacy ``actions_log.json`` writer, the legacy ``copykit``
    consumers, or any other downstream artifact. Callers wanting to
    flip the renderer behind ``ENGINE_V2_OUTPUT=true`` should also pass
    a legacy-shaped bundle to the downstream loggers via
    :func:`src.engine_run_adapter.legacy_actions_from_engine_run`.

    Args:
        template_dir: directory containing the legacy briefing template.
        out_path: HTML output path.
        brand: store / brand identifier (header text).
        aligned: KPI snapshot dict (used by the legacy template).
        outputs: outputs dict (used by the legacy template).
        engine_run: optional EngineRun. Required when ``use_v2`` is true.
        use_v2: when true, render the V2 layout instead of the legacy
            template. Default false to preserve M0-M7 behavior.

    Returns:
        The string ``out_path`` for chaining.
    """
    if use_v2 and engine_run is not None:
        html = _render_engine_run_v2(engine_run)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(html, encoding="utf-8")
        return out_path

    env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape())

    # Add Phase 1, 2 & 3 functions to template globals
    env.globals.update({
        'detect_growth_stage': detect_growth_stage,
        'select_priority_charts': select_priority_charts,
        'generate_growth_insights': generate_growth_insights,
        'generate_vertical_insights': generate_vertical_insights,
        'select_priority_kpis': select_priority_kpis,
        'get_vertical_mode': get_vertical_mode,
        'organize_by_engine_tiers': organize_by_engine_tiers,
        'get_confidence_display_data': get_confidence_display_data,
    })

    story = build_briefing_story(brand, aligned, outputs)

    tpl = env.get_template("briefing.html.j2")
    html = tpl.render(brand=brand, aligned=aligned, outputs=outputs, story=story)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
