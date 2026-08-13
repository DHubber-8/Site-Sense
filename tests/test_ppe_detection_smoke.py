from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.ppe_detection import PPE_MODEL_PATH, PpeDetectionAgent
from agents.ppe_detection.config import is_base_checkpoint


class _FakeScalar:
    def __init__(self, value: float):
        self._value = value

    def item(self) -> float:
        return self._value


class _FakeBox:
    def __init__(self, class_id: int, confidence: float, xyxy: list[float]):
        self.cls = _FakeScalar(class_id)
        self.conf = _FakeScalar(confidence)
        self.xyxy = [xyxy]


class _FakePrediction:
    def __init__(self, names: dict[int, str], boxes: list[_FakeBox]):
        self.names = names
        self.boxes = boxes


class _FakeModel:
    def __init__(self, predictions: list[_FakePrediction]):
        self._predictions = predictions

    def predict(self, **_: object) -> list[_FakePrediction]:
        return self._predictions


class PpeDetectionSmokeTest(unittest.TestCase):
    def _sample_image_path(self) -> Path:
        sample_root = Path(__file__).resolve().parents[1] / "data" / "sample_images"
        sample_images = sorted(
            path
            for path in sample_root.iterdir()
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
        )
        self.assertTrue(
            sample_images,
            "expected at least one sample image in data/sample_images",
        )
        return sample_images[0]

    def test_detect_normalizes_detections(self) -> None:
        image_path = self._sample_image_path()
        agent = PpeDetectionAgent(
            model_path=PPE_MODEL_PATH,
            model_override=_FakeModel(
                [
                    _FakePrediction(
                        names={0: "hard hat"},
                        boxes=[_FakeBox(0, 0.91, [1.0, 2.0, 11.0, 12.0])],
                    )
                ]
            ),
        )

        batch = agent.detect(image_path)

        self.assertEqual(agent.model_path, PPE_MODEL_PATH)
        self.assertEqual(batch.source_image, str(image_path))
        self.assertEqual(len(batch.detections), 1)
        detection = batch.detections[0]
        detection_payload = detection.to_dict()
        self.assertEqual(detection_payload["item"], "hard_hat")
        self.assertIsInstance(detection_payload["confidence"], float)
        self.assertGreater(detection_payload["confidence"], 0.0)
        self.assertIn("bounding_box", detection_payload)
        self.assertEqual(
            detection_payload["bounding_box"],
            {"x_min": 1.0, "y_min": 2.0, "x_max": 11.0, "y_max": 12.0},
        )
        self.assertEqual(batch.model_path, PPE_MODEL_PATH)

    def test_detect_preserves_ppe_class_labels(self) -> None:
        image_path = self._sample_image_path()
        agent = PpeDetectionAgent(
            model_path=PPE_MODEL_PATH,
            model_override=_FakeModel(
                [
                    _FakePrediction(
                        names={0: "helmet", 1: "no_helmet"},
                        boxes=[
                            _FakeBox(0, 0.93, [3.0, 4.0, 13.0, 14.0]),
                            _FakeBox(1, 0.87, [5.0, 6.0, 15.0, 16.0]),
                        ],
                    )
                ]
            ),
        )

        batch = agent.detect(image_path)

        self.assertEqual([detection.item for detection in batch.detections], ["helmet", "no_helmet"])
        self.assertEqual([detection.raw_label for detection in batch.detections], ["helmet", "no_helmet"])

    def test_default_checkpoint_points_to_finetuned_weights(self) -> None:
        self.assertEqual(PPE_MODEL_PATH, "runs/detect/train/weights/best.pt")
        self.assertFalse(is_base_checkpoint(PPE_MODEL_PATH))
        self.assertTrue(is_base_checkpoint("yolo26n.pt"))

    def test_detect_returns_empty_batch_for_no_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = self._sample_image_path()

            agent = PpeDetectionAgent(
                model_path=temp_path / "dummy.pt",
                model_override=_FakeModel([_FakePrediction(names={}, boxes=[])]),
            )

            batch = agent.detect(image_path)

            self.assertEqual(batch.detections, [])

    def test_missing_model_path_fails_clearly(self) -> None:
        image_path = self._sample_image_path()
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.pt"
            agent = PpeDetectionAgent(model_path=missing_path)

            with self.assertRaisesRegex(
                FileNotFoundError,
                r"PPE model checkpoint not found: .*missing\.pt",
            ):
                agent.detect(image_path)

    def test_invalid_model_path_fails_clearly(self) -> None:
        image_path = self._sample_image_path()
        agent = PpeDetectionAgent(model_path="not-a-real-checkpoint.pt")

        with self.assertRaisesRegex(
            FileNotFoundError,
            r"PPE model checkpoint not found: not-a-real-checkpoint\.pt",
        ):
            agent.detect(image_path)


if __name__ == "__main__":
    unittest.main()
