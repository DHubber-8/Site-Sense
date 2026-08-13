# PPE Detection Agent

This package provides the construction PPE detection entrypoint for Site-Sense.

## Contract

- Input: a site image provided as a file path or PIL image.
- Output: a `PpeDetectionBatch` containing structured detections.
- Each detection includes `item`, `confidence`, and `bounding_box` fields for downstream risk scoring.

## Usage

Instantiate `PpeDetectionAgent` with a configured YOLO checkpoint path, then call `detect(...)` on an image.

The agent loads the model lazily and raises a clear error if the checkpoint is missing or `ultralytics` is not installed.

Note: `no_boots` detection is inherently unreliable in this project because the training data is limited, so lower accuracy for boots.