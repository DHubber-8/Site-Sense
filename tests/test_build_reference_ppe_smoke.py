from __future__ import annotations

import unittest

from PIL import Image

from scripts.build_reference_ppe import (
    MIN_CROP_PX,
    PREFERRED_SOURCES,
    REFERENCE_ITEMS,
    _content_bounds,
    _crop_box,
    _outranks,
)


class CropBoxSmokeTest(unittest.TestCase):
    def test_crop_is_square_and_stays_inside_the_frame(self) -> None:
        # A tiny detection near the top-left corner: the padded crop must slide inward
        # rather than run off the frame.
        box = {"x_min": 5.0, "y_min": 5.0, "x_max": 40.0, "y_max": 35.0}

        left, top, right, bottom = _crop_box(box, 640, 640)

        self.assertEqual(right - left, bottom - top)
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(right, 640)
        self.assertLessEqual(bottom, 640)

    def test_small_detections_are_padded_to_a_legible_minimum(self) -> None:
        box = {"x_min": 300.0, "y_min": 300.0, "x_max": 371.0, "y_max": 330.0}

        left, top, right, bottom = _crop_box(box, 640, 640)

        self.assertGreaterEqual(right - left, MIN_CROP_PX)

    def test_crop_never_exceeds_the_source_frame(self) -> None:
        # A detection filling most of a small frame must clamp to the frame, not upscale.
        box = {"x_min": 10.0, "y_min": 10.0, "x_max": 290.0, "y_max": 290.0}

        left, top, right, bottom = _crop_box(box, 300, 300)

        self.assertLessEqual(right - left, 300)
        self.assertLessEqual(bottom - top, 300)


class LetterboxSmokeTest(unittest.TestCase):
    def _letterboxed(self) -> Image.Image:
        # 200px of picture centred in a 640x640 frame, black bars above and below.
        frame = Image.new("RGB", (640, 640), (0, 0, 0))
        frame.paste(Image.new("RGB", (640, 200), (180, 170, 160)), (0, 220))
        return frame

    def test_content_bounds_finds_the_picture_inside_the_bars(self) -> None:
        left, top, right, bottom = _content_bounds(self._letterboxed())

        self.assertEqual((left, right), (0, 640))
        self.assertEqual((top, bottom), (220, 420))

    def test_crop_stays_out_of_the_letterbox_bars(self) -> None:
        frame = self._letterboxed()
        bounds = _content_bounds(frame)
        # A detection near the top of the picture band would otherwise pull the crop into a bar.
        box = {"x_min": 300.0, "y_min": 230.0, "x_max": 340.0, "y_max": 260.0}

        left, top, right, bottom = _crop_box(box, frame.width, frame.height, bounds)

        self.assertGreaterEqual(top, bounds[1])
        self.assertLessEqual(bottom, bounds[3])


class SelectionSmokeTest(unittest.TestCase):
    def test_curated_source_beats_a_larger_box(self) -> None:
        curated = {"area": 1_000.0, "preferred": True}
        larger = {"area": 90_000.0, "preferred": False}

        self.assertTrue(_outranks(curated, larger))
        self.assertFalse(_outranks(larger, curated))

    def test_largest_box_wins_when_neither_is_curated(self) -> None:
        small = {"area": 1_000.0, "preferred": False}
        large = {"area": 90_000.0, "preferred": False}

        self.assertTrue(_outranks(large, small))
        self.assertFalse(_outranks(small, large))

    def test_curated_sources_reference_known_ppe_items(self) -> None:
        for item in PREFERRED_SOURCES:
            self.assertIn(item, REFERENCE_ITEMS)


if __name__ == "__main__":
    unittest.main()
