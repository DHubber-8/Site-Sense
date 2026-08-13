from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest

class TrainPpeModelEntryPointTest(unittest.TestCase):
    def test_module_exposes_main_entrypoint_and_defers_training(self) -> None:
        module_path = Path(__file__).resolve().parents[1] / "scripts" / "train_ppe_model.py"
        spec = importlib.util.spec_from_file_location("site_sense_train_ppe", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)

        module = importlib.util.module_from_spec(spec)

        with patch("torch.cuda.is_available", return_value=True), patch(
            "torch.cuda.get_device_name", return_value="RTX 5050"
        ), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            spec.loader.exec_module(module)

        self.assertTrue(hasattr(module, "main"))
        self.assertFalse(module.__dict__.get("_ran_training_on_import"))

        module.main()

        mock_model.train.assert_called_once()


if __name__ == "__main__":
    unittest.main()
