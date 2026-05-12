from vitraj.impl.view.gallery import (
	pick_overlay_layout, STACK_BREAKPOINT_PX, SPREAD, STACKED
)
from unittest import TestCase


class PickOverlayLayoutTest(TestCase):

	def test_breakpoint_is_140(self):
		# Anchor the breakpoint as part of the contract.
		self.assertEqual(140, STACK_BREAKPOINT_PX)

	def test_well_above_breakpoint_is_spread(self):
		self.assertEqual(SPREAD, pick_overlay_layout(200))

	def test_at_breakpoint_is_spread(self):
		# Boundary: tile_width == 140 → SPREAD (the rule is "< 140").
		self.assertEqual(SPREAD, pick_overlay_layout(140))

	def test_one_below_breakpoint_is_stacked(self):
		self.assertEqual(STACKED, pick_overlay_layout(139))

	def test_well_below_breakpoint_is_stacked(self):
		self.assertEqual(STACKED, pick_overlay_layout(80))

	def test_returns_strings(self):
		self.assertEqual('spread', SPREAD)
		self.assertEqual('stacked', STACKED)
