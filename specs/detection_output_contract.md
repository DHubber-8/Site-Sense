# Detection Output Contract (E2 Reference)

This is the exact structured output shape risk-scoring must consume. These are the live schema fields and representative payloads, not a design spec.

## 1) PPE detection output

### PpeDetection
- `item: str`
- `confidence: float`
- `bounding_box: { x_min: float, y_min: float, x_max: float, y_max: float }`
- `class_id: int | None`
- `raw_label: str | None`
- `metadata: dict[str, Any]`

### PpeDetectionBatch
- `detections: list[PpeDetection]`
- `source_image: str | None`
- `model_name: str | None`
- `model_path: str | None`
- `created_at: ISO datetime string`

Real output labels from the fine-tuned model are normalized values such as:
- `helmet`
- `no_helmet`
- `hard_hat` (when raw label is `"hard hat"` and normalized to slug form)

Example payload:
```json
{
  "detections": [
    {
      "item": "helmet",
      "confidence": 0.93,
      "bounding_box": {"x_min": 3.0, "y_min": 4.0, "x_max": 13.0, "y_max": 14.0},
      "class_id": 0,
      "raw_label": "helmet"
    },
    {
      "item": "no_helmet",
      "confidence": 0.87,
      "bounding_box": {"x_min": 5.0, "y_min": 6.0, "x_max": 15.0, "y_max": 16.0},
      "class_id": 1,
      "raw_label": "no_helmet"
    }
  ],
  "source_image": "data/sample_images/site_001.jpg",
  "model_name": "YOLO",
  "model_path": "runs/detect/train/weights/best.pt",
  "created_at": "2026-08-13T12:00:00+00:00"
}
```

## 2) Heat compliance alert output (Section 2)

### HeatComplianceAlert
- `city: str`
- `forecast_date: ISO date string`
- `forecast_max_temperature_c: float`
- `level: str`
- `title: str`
- `threshold_min_c: float`
- `threshold_max_c: float | null`
- `regulatory_actions: list[str]`
- `ai_actions: list[str]`
- `metadata: dict[str, Any]`

### HeatComplianceAlertBatch
- `site_city: str`
- `forecast_date: ISO date string`
- `forecast_max_temperature_c: float`
- `alerts: list[HeatComplianceAlert]`
- `weather_provider: str | None`
- `weather_source_url: str | None`
- `created_at: ISO datetime string`

`level` uses the Section 2 naming scheme: `Level 1`, `Level 2`, `Level 3`.

Example payload:
```json
{
  "site_city": "Singapore",
  "forecast_date": "2026-08-13",
  "forecast_max_temperature_c": 39.4,
  "alerts": [
    {
      "city": "Singapore",
      "forecast_date": "2026-08-13",
      "forecast_max_temperature_c": 39.4,
      "level": "Level 2",
      "title": "Severe Heat Alert",
      "threshold_min_c": 37.0,
      "threshold_max_c": 40.0,
      "regulatory_actions": [
        "Outdoor working hours must not exceed 6 hours per day",
        "Outdoor work shall not be arranged during the hottest 3 hours of the day",
        "Increase rest periods"
      ],
      "ai_actions": [
        "Alert site supervisor",
        "Record worker exposure to heat duration",
        "Increase hydration breaks"
      ]
    }
  ],
  "weather_provider": "Open-Meteo",
  "weather_source_url": "https://api.open-meteo.com/v1/forecast?...",
  "created_at": "2026-08-13T12:00:00+00:00"
}
```

## 3) WBGT risk output (Section 1)

### WBGTRiskAlert
- `city: str`
- `reading_at: ISO datetime string`
- `wbgt_c: float`
- `level: str`
- `title: str`
- `threshold_min_c: float`
- `threshold_max_c: float | null`
- `regulatory_actions: list[str]`
- `ai_actions: list[str]`
- `metadata: dict[str, Any]`

### WBGTRiskBatch
- `site_city: str`
- `reading_at: ISO datetime string`
- `wbgt_c: float`
- `alerts: list[WBGTRiskAlert]`
- `reading_source_name: str | None`
- `reading_source_url: str | None`
- `created_at: ISO datetime string`

`level` uses the Section 1 naming scheme: `Normal`, `Caution`, `High Risk`, `Extreme`.

Example payload:
```json
{
  "site_city": "Site A",
  "reading_at": "2026-08-13T12:00:00+00:00",
  "wbgt_c": 31.8,
  "alerts": [
    {
      "city": "Site A",
      "reading_at": "2026-08-13T12:00:00+00:00",
      "wbgt_c": 31.8,
      "level": "High Risk",
      "title": "High Heat Risk",
      "threshold_min_c": 30.0,
      "threshold_max_c": 32.0,
      "regulatory_actions": [
        "Reduce workload",
        "Increase rest frequency",
        "Monitor worker temperature closely"
      ],
      "ai_actions": [
        "Reduce work intensity",
        "Increase monitoring frequency"
      ]
    }
  ],
  "reading_source_name": "Simulated WBGT proxy",
  "reading_source_url": "simulated://wbgt",
  "created_at": "2026-08-13T12:00:00+00:00"
}
```

Important: Section 2 and Section 1 use different `level` naming schemes (`Level 1/2/3` vs `Normal/Caution/High Risk/Extreme`). Risk-scoring should normalize both to a common internal enum before downstream logic.
