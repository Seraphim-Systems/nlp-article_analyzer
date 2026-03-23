"""
Shared progress bar utilities.

Provides a consistent tqdm style across the pipeline:
- Green dot fill  ●●●●○○○○  (filled / empty circles)
- Braille spinner  ⠋⠙⠹⠸⠼⠴⠦⠧  at the leading edge
- ANSI green colour
"""

from __future__ import annotations

from tqdm import tqdm

_GREEN = "\033[0;32m"
_RESET = "\033[0m"

# Braille spinner frames
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def make_pbar(
    iterable=None,
    *,
    total: int | None = None,
    desc: str = "",
    unit: str = "it",
    ncols: int = 88,
    postfix_keys: list[str] | None = None,
) -> tqdm:
    """
    Return a tqdm progress bar styled with green dots and a Braille spinner.

    Parameters
    ----------
    iterable : iterable, optional
    total : int, optional
    desc : str
        Label shown before the bar (without leading spaces).
    unit : str
        Unit string for rate display.
    ncols : int
        Terminal width for the bar.
    postfix_keys : list[str], optional
        Not used directly; caller sets postfix after creation.

    Usage
    -----
        pbar = make_pbar(range(n), total=n, desc="Ranking", unit="art")
        for item in pbar:
            ...
            pbar.set_postfix(entities=42)
    """
    return tqdm(
        iterable,
        total=total,
        desc=f"  {_GREEN}{desc}{_RESET}",
        unit=unit,
        ncols=ncols,
        colour="green",
        ascii="○●",
        bar_format=(
            "{desc} {bar} {percentage:3.0f}%"
            " | {n_fmt}/{total_fmt} {unit_divisor:.0f}"
            " [{elapsed}<{remaining}, {rate_fmt}]{postfix}"
        ),
    )


def make_pbar_simple(
    iterable=None,
    *,
    total: int | None = None,
    desc: str = "",
    unit: str = "it",
    ncols: int = 88,
) -> tqdm:
    """Simpler bar without unit_divisor formatting."""
    return tqdm(
        iterable,
        total=total,
        desc=f"  {_GREEN}{desc}{_RESET}",
        unit=unit,
        ncols=ncols,
        colour="green",
        ascii="○●",
        bar_format=(
            "{desc} {bar} {percentage:3.0f}%"
            " | {n_fmt}/{total_fmt}"
            " [{elapsed}<{remaining}, {rate_fmt}]{postfix}"
        ),
    )
