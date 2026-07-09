"""Tests for Supertrend ratchet."""

import pytest

from tradingagents.swing.trailing import ratchet_stop

pytestmark = pytest.mark.unit


def test_ratchet_never_lowers():
    assert ratchet_stop(100.0, 105.0) == 105.0
    assert ratchet_stop(105.0, 102.0) == 105.0
