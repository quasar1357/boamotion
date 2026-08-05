"""The analysis functions take explicit keyword arguments rather than a Params object,
so their defaults are written twice. These tests make any drift a CI failure."""

import inspect

import pytest

from boamotion import detect_reference_frame, motion_pixel_mask
from boamotion.params import Params

FUNCTIONS = [detect_reference_frame, motion_pixel_mask]


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
    unknown = set(defaults_of(function)) - {field for field in Params().to_dict()}
    assert not unknown, f"{function.__name__} takes arguments Params does not define: {unknown}"
