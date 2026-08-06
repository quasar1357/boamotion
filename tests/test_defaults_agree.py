"""The analysis functions take explicit keyword arguments rather than a Params object,
so their defaults are written twice. These tests make any drift a CI failure."""

import inspect

import pytest

from boamotion import (
    build_motion_pixel_mask,
    detect_reference_frame,
    find_baselines,
    find_peaks,
    measure_contraction,
    measure_speed,
    measure_transients,
)
from boamotion.params import Params

FUNCTIONS = [
    detect_reference_frame,
    build_motion_pixel_mask,
    measure_contraction,
    measure_speed,
    find_peaks,
    find_baselines,
    measure_transients,
]

# Arguments that carry data rather than a setting, so Params does not define them.
DATA_ARGUMENTS = {"mask"}


def defaults_of(function):
    return {
        name: parameter.default
        for name, parameter in inspect.signature(function).parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }


@pytest.mark.parametrize("function", FUNCTIONS, ids=lambda f: f.__name__)
def test_defaults_match_params(function):
    params = Params()
    mismatched = {
        name: (value, getattr(params, name))
        for name, value in defaults_of(function).items()
        if hasattr(params, name) and value != getattr(params, name)
    }
    assert not mismatched, f"{function.__name__} disagrees with Params on {mismatched}"


@pytest.mark.parametrize("function", FUNCTIONS, ids=lambda f: f.__name__)
def test_argument_names_exist_on_params(function):
    unknown = set(defaults_of(function)) - set(Params().to_dict()) - DATA_ARGUMENTS
    assert not unknown, f"{function.__name__} takes arguments Params does not define: {unknown}"
