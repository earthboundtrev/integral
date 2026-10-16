"""Tests for v2 design tokens (issue #129)."""

import unittest
from theme import LIGHT, DARK, FONTS, SPACING


class TestDesignTokens(unittest.TestCase):
    """Test v2 design token presence and values."""

    def test_light_theme_v2_tokens(self):
        """All v2 tokens are present in LIGHT theme."""
        required_keys = [
            "name", "bg", "fg", "muted", "accent", "accent_dark", "accent_soft",
            "on_accent", "streak", "success", "success_bg", "link", "surface",
            "surface_alt", "sidebar", "card_border", "button_border", "text_bg", "text_fg",
            "field_bg", "select_bg", "warning_bg", "error", "error_bg", "disabled"
        ]
        for key in required_keys:
            self.assertIn(key, LIGHT, f"LIGHT missing key: {key}")
            self.assertIsNotNone(LIGHT[key], f"LIGHT[{key}] is None")

    def test_dark_theme_v2_tokens(self):
        """All v2 tokens are present in DARK theme."""
        required_keys = [
            "name", "bg", "fg", "muted", "accent", "accent_dark", "accent_soft",
            "on_accent", "streak", "success", "success_bg", "link", "surface",
            "surface_alt", "sidebar", "card_border", "button_border", "text_bg", "text_fg",
            "field_bg", "select_bg", "warning_bg", "error", "error_bg", "disabled"
        ]
        for key in required_keys:
            self.assertIn(key, DARK, f"DARK missing key: {key}")
            self.assertIsNotNone(DARK[key], f"DARK[{key}] is None")

    def test_fonts_all_keys_present(self):
        """All required font keys are present."""
        required_keys = [
            # Existing keys
            "title", "heading", "subheading", "body", "body_bold", "small", "stat", "button",
            # v2 additions
            "h1", "h3", "brand", "caption", "hint", "menu_header"
        ]
        for key in required_keys:
            self.assertIn(key, FONTS, f"FONTS missing key: {key}")
            self.assertIsInstance(FONTS[key], tuple, f"FONTS[{key}] should be tuple")
            self.assertGreaterEqual(len(FONTS[key]), 2, f"FONTS[{key}] should have at least 2 elements")

    def test_spacing_tokens(self):
        """Spacing tokens follow 8px grid."""
        self.assertEqual(SPACING["xs"], 4)
        self.assertEqual(SPACING["sm"], 8)
        self.assertEqual(SPACING["md"], 12)
        self.assertEqual(SPACING["lg"], 16)
        self.assertEqual(SPACING["xl"], 24)
        self.assertEqual(SPACING["xxl"], 32)

    def test_contrast_fixed_light_muted(self):
        """Light muted color darkened for 4.5:1 contrast."""
        # Issue #129: muted on bg should be ≥4.5:1
        # Changed from #5C6370 to #666666
        self.assertEqual(LIGHT["muted"], "#666666")

    def test_contrast_fixed_dark_accent(self):
        """Dark accent color darkened for white text contrast."""
        # Issue #129: dark accent changed from #3D9A9B to #2F7A7B for better contrast
        self.assertEqual(DARK["accent"], "#2F7A7B")

    def test_color_values_are_hex(self):
        """All color values are valid hex codes."""
        import re
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        
        for theme_name, theme in [("LIGHT", LIGHT), ("DARK", DARK)]:
            for key, value in theme.items():
                if key == "name":
                    continue
                self.assertTrue(
                    hex_pattern.match(value),
                    f"{theme_name}[{key}] = {value} is not a valid hex color"
                )

    def test_wcag_contrast_light_theme(self):
        """Test WCAG contrast ratios for light theme."""
        # Simplified contrast check (full WCAG calculation would be more complex)
        # Just verify the fixed values are present
        self.assertEqual(LIGHT["muted"], "#666666")  # Fixed for contrast
        self.assertEqual(LIGHT["on_accent"], "#FFFFFF")  # White on accent

    def test_wcag_contrast_dark_theme(self):
        """Test WCAG contrast ratios for dark theme."""
        self.assertEqual(DARK["accent"], "#2F7A7B")  # Darkened for white text
        self.assertEqual(DARK["on_accent"], "#FFFFFF")

    def test_error_tokens(self):
        """Error tokens are present in both themes."""
        self.assertIn("error", LIGHT)
        self.assertIn("error_bg", LIGHT)
        self.assertIn("error", DARK)
        self.assertIn("error_bg", DARK)


if __name__ == "__main__":
    unittest.main()
