from ultralytics import YOLO
import cv2
import os
import yaml

# -----------------------------
# 1. SET PATHS
# -----------------------------
project_folder = os.path.dirname(os.path.abspath(__file__))

# *** IMPORTANT: Put your Roboflow dataset in this folder ***
dataset_folder = os.path.join(project_folder, "TOYCAR_Dataset")

data_yaml_path = os.path.join(dataset_folder, "data.yaml")

if not os.path.exists(data_yaml_path):
    raise FileNotFoundError(
        f"Could not find data.yaml at: {data_yaml_path}\n"
        "Make sure your Roboflow dataset is in the 'Dataset' folder!"
    )

# Folder for saving annotated results
output_folder = os.path.join(project_folder, "results")
os.makedirs(output_folder, exist_ok=True)

# -----------------------------
# 2. TRAIN YOLOv8 WITH YOUR LABELS
# -----------------------------
print("\n==============================")
print(" TRAINING YOLOv8 ON TOY CAR DATA ")
print("==============================\n")

model = YOLO("yolov8n.pt")   # start from pretrained weights

model.train(
    data=data_yaml_path,
    epochs=100,
    imgsz=640,
    batch=16,
    name="toycar_model",
    augment = True
)

# -----------------------------
# 3. LOAD BEST MODEL FOR INFERENCE
# -----------------------------
trained_model_path = os.path.join(
    project_folder,
    "runs", "detect", "toycar_model", "weights", "best.pt"
)

if not os.path.exists(trained_model_path):
    raise FileNotFoundError("Training completed but best.pt not found.")

model = YOLO(trained_model_path)

# -----------------------------
# 4. OPTIONAL: Annotate training images for preview
# -----------------------------
print("\nAnnotating sample images from the training set...\n")

train_image_dir = os.path.join(dataset_folder, "train", "images")
all_images = [f for f in os.listdir(train_image_dir)
              if f.lower().endswith((".jpg", ".jpeg", ".png"))]

for img_name in all_images[:20]:  # only annotate first 20 images to save time
    img_path = os.path.join(train_image_dir, img_name)
    results = model(img_path)
    annotated = results[0].plot()
    cv2.imwrite(os.path.join(output_folder, img_name), annotated)

print("Annotated sample images saved in 'results' folder.")

# -----------------------------
# Validate trained model
# -----------------------------
print("\nValidating model on validation set...\n")
val_results = model.val()

accuracy = val_results.box.map50  # mAP@0.5
precision = val_results.box.mp
recall = val_results.box.mr

print("Detection accuracy (mAP50):", accuracy)
print("Precision:", precision)
print("Recall:", recall)

print("Training complete. Annotated samples saved in 'results' folder.")

