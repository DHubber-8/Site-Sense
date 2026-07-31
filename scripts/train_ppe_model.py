from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.train(data="construction-ppe.yaml", epochs=30, imgsz=640)