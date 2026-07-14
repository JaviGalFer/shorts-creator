"""Tests for visual_asset_renderability_v2 — canonical v2 dimension contract."""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

from visual_asset_renderability_v2 import (
    MIN_V2_ASSET_WIDTH,
    MIN_V2_ASSET_HEIGHT,
    is_v2_asset_dimension_renderable,
)


class TestRenderabilityContract:
    def test_700x435_not_renderable(self):
        assert is_v2_asset_dimension_renderable(700, 435) is False

    def test_719x719_not_renderable(self):
        assert is_v2_asset_dimension_renderable(719, 719) is False

    def test_720x720_renderable(self):
        assert is_v2_asset_dimension_renderable(720, 720) is True

    def test_721x902_renderable(self):
        assert is_v2_asset_dimension_renderable(721, 902) is True

    def test_1200x600_not_renderable(self):
        assert is_v2_asset_dimension_renderable(1200, 600) is False

    def test_600x1200_not_renderable(self):
        assert is_v2_asset_dimension_renderable(600, 1200) is False

    def test_3872x2592_renderable(self):
        assert is_v2_asset_dimension_renderable(3872, 2592) is True

    def test_width_none_not_renderable(self):
        assert is_v2_asset_dimension_renderable(None, 800) is False

    def test_height_none_not_renderable(self):
        assert is_v2_asset_dimension_renderable(800, None) is False

    def test_both_none_not_renderable(self):
        assert is_v2_asset_dimension_renderable(None, None) is False

    def test_width_string_not_renderable(self):
        assert is_v2_asset_dimension_renderable("720", 800) is False

    def test_height_string_not_renderable(self):
        assert is_v2_asset_dimension_renderable(800, "720") is False

    def test_zero_width_not_renderable(self):
        assert is_v2_asset_dimension_renderable(0, 800) is False

    def test_zero_height_not_renderable(self):
        assert is_v2_asset_dimension_renderable(800, 0) is False

    def test_float_dimensions_renderable(self):
        assert is_v2_asset_dimension_renderable(720.0, 800.0) is True

    def test_float_below_minimum_not_renderable(self):
        assert is_v2_asset_dimension_renderable(719.9, 800.0) is False

    def test_constants_exist(self):
        assert MIN_V2_ASSET_WIDTH == 720
        assert MIN_V2_ASSET_HEIGHT == 720

    def test_nan_not_renderable(self):
        import math
        assert is_v2_asset_dimension_renderable(float("nan"), 800) is False

    def test_infinity_not_renderable(self):
        assert is_v2_asset_dimension_renderable(float("inf"), 800) is False

    def test_negative_infinity_not_renderable(self):
        assert is_v2_asset_dimension_renderable(float("-inf"), 800) is False

    def test_nan_both_dimensions_not_renderable(self):
        assert is_v2_asset_dimension_renderable(float("nan"), float("nan")) is False

    def test_bool_not_renderable(self):
        assert is_v2_asset_dimension_renderable(True, 800) is False

    def test_list_not_renderable(self):
        assert is_v2_asset_dimension_renderable([720], 800) is False

    def test_dict_not_renderable(self):
        assert is_v2_asset_dimension_renderable({"w": 720}, 800) is False

    def test_negative_width_not_renderable(self):
        assert is_v2_asset_dimension_renderable(-1, 800) is False

    def test_zero_dimensions_not_renderable(self):
        assert is_v2_asset_dimension_renderable(0, 0) is False
