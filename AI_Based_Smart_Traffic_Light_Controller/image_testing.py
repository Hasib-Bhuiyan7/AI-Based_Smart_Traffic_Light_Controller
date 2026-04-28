from ultralytics import YOLO
import cv2
import os
import matplotlib.pyplot as plt
import numpy as np

import re

# -----------------------------
# Load trained YOLO model
# -----------------------------

# toycar_model1-3 have 12 classes
# toycar_model4-7 have 3 classes [car, bus, truck]
# toycar_model8-10 has 1 class [vehicle]

trained_model_path = os.path.join("runs", "detect", "toycar_model6", "weights", "best.pt")
model = YOLO(trained_model_path)

# -----------------------------
# Prepare folders
# -----------------------------
image_folder = "images"
output_folder = "results"
os.makedirs(output_folder, exist_ok=True)

# -----------------------------
# Sort image files numerically
# -----------------------------
def sort_key(filename):
    numbers = re.findall(r'\d+', filename)
    return int(numbers[0]) if numbers else 0

image_files = sorted(
    [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))],
    key=sort_key
)

# -----------------------------
# Lists for graphs
# -----------------------------
image_names = []
car_counts = []
total_object_counts = []
car_percentages = []
region_UP = []
region_DOWN = []
region_LEFT = []
region_RIGHT = []
region_CENTER = []

# Traffic-light decision: 0=Equal/Default, 1=Vertical green, 2=Horizontal green
traffic_decision = []

# -----------------------------
# Process images
# -----------------------------

for filename in image_files:
    img_path = os.path.join(image_folder, filename)

    # Run YOLO detection
    results = model(img_path)
    annotated = results[0].plot()
    image = annotated.copy()
    h, w, _ = image.shape
    detections = results[0].boxes
    total_object_count = len(detections)

    LEFT_poly = [(222, 227), (289, 173), (132, 96), (67, 141)]
    RIGHT_poly = [(457, 249), (500, 192), (637, 249), (636, 332)]
    UP_poly = [(430, 150), (357, 124), (420, 62), (484, 79)]
    DOWN_poly = [(296, 283), (374, 325), (305, 418), (179, 405)]
    CENTER_poly = [(237, 237), (349, 138), (479, 185), (374, 308)]

    # Convert to NumPy arrays (IMPORTANT)
    LEFT_pts = np.array(LEFT_poly, np.int32)
    RIGHT_pts = np.array(RIGHT_poly, np.int32)
    UP_pts = np.array(UP_poly, np.int32)
    DOWN_pts = np.array(DOWN_poly, np.int32)
    CENTER_pts = np.array(CENTER_poly, np.int32)


    # ----------------------------------
    # Helper functions
    # ----------------------------------
    def draw_polygon(img, points, color, thickness=2):
        pts = points.reshape((-1, 1, 2))
        cv2.polylines(img, [pts], True, color, thickness)


    def point_in_poly(point, poly):
        return cv2.pointPolygonTest(poly, point, False) >= 0


    # ----------------------------------
    # Draw all regions
    # ----------------------------------
    draw_polygon(image, LEFT_pts, (0, 255, 0))  # LEFT
    draw_polygon(image, RIGHT_pts, (255, 0, 0))  # RIGHT
    draw_polygon(image, UP_pts, (0, 0, 255))  # UP
    draw_polygon(image, DOWN_pts, (0, 165, 255))  # DOWN
    draw_polygon(image, CENTER_pts, (255, 0, 255))  # CENTER

    # ----------------------------------
    # Initialize region counts
    # ----------------------------------
    region_counts = {
        "UP": 0,
        "DOWN": 0,
        "LEFT": 0,
        "RIGHT": 0,
        "CENTER": 0
    }

    total_cars = 0

    for box in detections:
        cls = int(box.cls[0])

        if model.names[cls] != "car":
            continue

        total_cars += 1

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        cx_car = (x1 + x2) // 2
        cy_car = (y1 + y2) // 2
        center_point = (cx_car, cy_car)


        # -------- REGION CHECK (POLYGON BASED) --------
        if point_in_poly(center_point, CENTER_pts):
            region_counts["CENTER"] += 1
        elif point_in_poly(center_point, UP_pts):
            region_counts["UP"] += 1
        elif point_in_poly(center_point, DOWN_pts):
            region_counts["DOWN"] += 1
        elif point_in_poly(center_point, LEFT_pts):
            region_counts["LEFT"] += 1
        elif point_in_poly(center_point, RIGHT_pts):
            region_counts["RIGHT"] += 1

    # -----------------------------
    # Draw counts on image (fixed positions)
    # -----------------------------
    cv2.putText(image, f"Total Cars: {total_cars}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    cv2.putText(image, f"UP: {region_counts['UP']}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    cv2.putText(image, f"LEFT: {region_counts['LEFT']}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.putText(image, f"RIGHT: {region_counts['RIGHT']}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    cv2.putText(image, f"DOWN: {region_counts['DOWN']}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255),2)
    cv2.putText(image, f"CENTER: {region_counts['CENTER']}", (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

    # -----------------------------
    #  Traffic-light Logic
    # -----------------------------
    vertical = region_counts["UP"] + region_counts["DOWN"]
    horizontal = region_counts["LEFT"] + region_counts["RIGHT"]

    if vertical > horizontal:
        traffic_signal = "🚦 GREEN:UP/DOWN   🔴 LEFT/RIGHT"
        traffic_decision.append(1)
    elif horizontal > vertical:
        traffic_signal = "🔴 UP/DOWN 🚦 GREEN: LEFT/RIGHT"
        traffic_decision.append(2)
    else:
        traffic_signal = " 🚦 GREEN: UP/DOWN   🚦 GREEN: LEFT/RIGHT (Equal traffic)"
        traffic_decision.append(0)

    print(f"{filename}: {traffic_signal}")

    # Save annotated output
    cv2.imwrite(os.path.join(output_folder, filename), image)

    # Calculate car percentage
    car_percentage = (total_cars / len(detections) * 100) if len(detections) > 0 else 0

    # Save data for graphs
    image_names.append(filename)
    car_counts.append(total_cars)
    total_object_counts.append(total_object_count)
    car_percentages.append(car_percentage)
    region_UP.append(region_counts["UP"])
    region_DOWN.append(region_counts["DOWN"])
    region_LEFT.append(region_counts["LEFT"])
    region_RIGHT.append(region_counts["RIGHT"])
    region_CENTER.append(region_counts["CENTER"])

# -----------------------------
# Graph 1 – Total Cars
# -----------------------------
plt.figure(figsize=(14,6))
plt.plot(car_counts, marker='o', markersize=5, linestyle='-', label="Total Cars", linewidth=2)
plt.ylabel("Number of Cars")
plt.xlabel("Image")
plt.title("Total Cars per Image")
plt.grid(True)
plt.xticks(range(len(image_names)), labels=image_names, rotation=90)
plt.tight_layout()
plt.savefig("graph_total_cars.png")
plt.show()
plt.close()

# -----------------------------
# Graph 2 – Car Percentage
# -----------------------------
plt.figure(figsize=(14,6))
plt.plot(car_percentages, marker='o', markersize=5, linestyle='-', label="Car %", linewidth=2)
plt.ylabel("Percentage (%)")
plt.xlabel("Image")
plt.title("Percentage of Detected Objects That Are Cars")
plt.grid(True)
plt.xticks(range(len(image_names)), labels=image_names, rotation=90)
plt.tight_layout()
plt.savefig("graph_car_percentages.png")
plt.show()
plt.close()

# -----------------------------
# Graph 3 – Total Objects vs Detected Cars
# -----------------------------
plt.figure(figsize=(14,6))
plt.plot(total_object_counts, marker='o', markersize=6, linestyle='-', label="Total Objects", color='red', linewidth=2)
plt.plot(car_counts, marker='s', markersize=3, linestyle='--', label="Detected Cars",  linewidth=1.5)
plt.ylabel("Number of Objects")
plt.xlabel("Image")
plt.title("Detected Cars vs Total Objects")
plt.grid(True)
plt.legend()
plt.xticks(range(len(image_names)), labels=image_names, rotation=90)
plt.tight_layout()
plt.savefig("graph_car_vs_total_objects.png")
plt.show()
plt.close()

# -----------------------------
# Graph 4 – Cars per Region
# -----------------------------
plt.figure(figsize=(14,6))
plt.plot(region_UP, marker='o', markersize=2, linestyle='-', label="UP", color='red', linewidth=1.5)
plt.plot(region_DOWN, marker='s', markersize=2, linestyle='-', label="DOWN", color='blue', linewidth=1.5)
plt.plot(region_LEFT, marker='^', markersize=2, linestyle='-', label="LEFT", color='green', linewidth=1.5)
plt.plot(region_RIGHT, marker='v', markersize=2, linestyle='-', label="RIGHT", color='orange', linewidth=1.5)
plt.plot(region_CENTER, marker='x', markersize=2, linestyle='-', label="CENTER", color='magenta', linewidth=1.5)
plt.ylabel("Number of Cars")
plt.xlabel("Image")
plt.title("Number of Cars per Region")
plt.grid(True)
plt.legend()
plt.xticks(range(len(image_names)), labels=image_names, rotation=90)
plt.tight_layout()
plt.savefig("graph_cars_per_region.png")
plt.show()
plt.close()

# -----------------------------
# Graph 5 – Traffic Light Decision - Vertical - means GREEN up/down, Horizontal - means RED left/right
# -----------------------------
plt.figure(figsize=(14,6))
plt.plot(traffic_decision, marker='o', markersize=5, linestyle='-', color='green', linewidth=2)
plt.yticks([0,1,2], ["Equal / Default", "Vertical (UP/DOWN)", "Horizontal (LEFT/RIGHT)"])
plt.xlabel("Image")
plt.ylabel("Traffic Light Decision")
plt.title("Traffic Light Decision per Image")
plt.grid(True)
plt.xticks(range(len(image_names)), labels=image_names, rotation=90)
plt.tight_layout()
plt.savefig("graph_traffic_decision.png")
plt.show()
plt.close()

print("Done! All annotated images and 5 graphs saved.")
