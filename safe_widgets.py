"""Crash-proof wrappers around Streamlit input widgets.

`st.number_input(value=...)` raises (and the whole page dies) when `value` lies outside
`min_value`/`max_value`, or when int and float arguments are mixed. Settings pages feed these
widgets from stored (database) values, so an old/edited/corrupt stored value must never be able to
take a settings page down — the value is clamped into range and the numeric types are unified.
"""
import math

import streamlit as st


def clamp_number(value, min_value=None, max_value=None, default=None):
    """Return `value` as a number clamped into [min_value, max_value].

    None / NaN / non-numeric -> `default` (or `min_value`, or 0) first, then clamped.
    """
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            raise ValueError
    except (TypeError, ValueError):
        number = default if default is not None else (min_value if min_value is not None else 0)
    if min_value is not None and number < min_value:
        number = min_value
    if max_value is not None and number > max_value:
        number = max_value
    return number


def safe_number_input(label, *, value=None, min_value=None, max_value=None, step=None, **kwargs):
    """`st.number_input` that cannot raise on an out-of-range or mixed-type `value`."""
    numbers = [n for n in (value, min_value, max_value, step) if n is not None]
    use_float = any(isinstance(n, float) for n in numbers)
    clamped = clamp_number(value, min_value, max_value, default=min_value)
    if use_float:
        clamped = float(clamped)
        min_value = None if min_value is None else float(min_value)
        max_value = None if max_value is None else float(max_value)
        step = None if step is None else float(step)
    else:
        clamped = int(clamped)
    if step is not None:
        kwargs["step"] = step
    if min_value is not None:
        kwargs["min_value"] = min_value
    if max_value is not None:
        kwargs["max_value"] = max_value
    return st.number_input(label, value=clamped, **kwargs)
