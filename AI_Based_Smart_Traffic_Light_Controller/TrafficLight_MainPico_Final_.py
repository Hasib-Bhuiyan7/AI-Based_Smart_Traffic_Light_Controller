from ultralytics import YOLO
import cv2
import numpy as np
import time
import os
import serial
import serial.tools.list_ports
from datetime import datetime
import torch

from DecisionModel.decision_model import predict_green_time

# -------------------- USER TOGGLES --------------------
PRIVACY_MODE = False
SHOW_ROI_GRIDS = True
SHOW_NONROI_GRID = True
SHOW_UI_INFO = True  # Toggle for T key (FPS, green times, etc.)
USE_TRADITIONAL_FIXED_MODE = False
FIXED_GREEN_TIME = 15 # Can be changed to adjust with different standard traditional traffic lights with fixed timing
DETECTION_TRACKING_ENABLED = False
# -------------------- GPU / DEVICE SETUP --------------------
if torch.cuda.is_available():
    YOLO_DEVICE = 0
    YOLO_HALF = True
    print("CUDA is available. YOLO will run on GPU.")
    print(f"GPU name: {torch.cuda.get_device_name(0)}")
else:
    YOLO_DEVICE = "cpu"
    YOLO_HALF = False
    print("CUDA is NOT available. YOLO will run on CPU.")

# -------------------- AUTO-DETECT PICO --------------------
def find_pico():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        if "usb" in desc or "pico" in desc:
            return p.device
    return None

pico_port = find_pico()
if pico_port is None:
    print("Raspberry Pi Pico not found. Running in TEST MODE.")
    ser = None
else:
    ser = serial.Serial(pico_port, 9600, timeout=1)
    print(f"Connected to Pico on port: {pico_port}")

# -------------------- MODEL --------------------
model = YOLO("runs/detect/toycar_model6/weights/best.pt")

cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("Cannot access camera")
    raise SystemExit

FRAME_WIDTH, FRAME_HEIGHT = 640, 480
ORIG_WIDTH, ORIG_HEIGHT = 640, 480

# -------------------- TRAFFIC LIGHT PARAMETERS --------------------
MAX_GREEN = 40
MIN_GREEN = 10
YELLOW_TIME = 3
ALL_RED_TIME = 3
EXTENSION_STEP = 2
CHECK_INTERVAL = 2

signal_state = "ALL_RED"
current_phase = "NS"
pending_phase = "NS"

green_end_time = time.time() + 1.0
last_check_time = time.time()
totalInc = 0
totalDec = 0
prev_time = time.time()
fps_smooth = 0.0
violation_id = 0
last_saved_second = -1
last_red_capture_second = -1

# -------------------- PERFORMANCE METRICS --------------------
total_vehicles_passed = 0
total_wait_time_accum = 0.0
total_wait_samples = 0
cycle_start_time = time.time()
avg_wait=0

last_pass_update_time = time.time()
PASS_UPDATE_INTERVAL = 1.0  # seconds

# -------------------- SIMPLE TRACKING --------------------
tracked_objects = {}
next_object_id = 0

DIST_THRESHOLD = 50  # max pixel distance to match same car
#total_vehicles_passed = 0  # FINAL throughput metric: THIS ISBEING USED BY TRACKER AS WELL

# -------------------- SIMPLE WAIT ESTIMATION --------------------
wait_N = 0.0
wait_S = 0.0
wait_E = 0.0
wait_W = 0.0
last_wait_update_time = time.time()

# -------------------- REGIONS --------------------
'''
LEFT_poly = [[263, 161], [169, 96], [131, 122], [227, 194]] #West
RIGHT_poly = [[371, 236], [578, 371], [598, 305], [402, 193]] # East
UP_poly = [[358, 154], [402, 113], [368, 87], [317, 135]] # Noth
DOWN_poly = [[260, 241], [302, 278], [192, 392], [144, 351]] # South
'''

LEFT_poly = [[263, 161], [169, 96], [124, 125], [197, 194]]
RIGHT_poly = [[347, 246], [552, 396], [574, 323], [399, 199]]
UP_poly = [[340, 161], [384, 127], [342, 110], [304, 139]]
DOWN_poly = [[231, 249], [287, 295], [190, 381], [143, 321]]

CENTER_poly = [[293, 278], [369, 198], [289, 150], [216, 207]]

NONROI1_poly = [[396, 186], [580, 309], [628, 215], [454, 121]]
NONROI2_poly = [[288, 127], [370, 75], [279, 43], [224, 84]]
NONROI3_poly = [[179, 215], [112, 123], [38, 180], [110, 274]]
NONROI4_poly = [[307, 307], [206, 398], [230, 420], [451, 426]]

def scale_poly(poly):
    return np.array(
        [(int(x / ORIG_WIDTH * FRAME_WIDTH), int(y / ORIG_HEIGHT * FRAME_HEIGHT)) for x, y in poly],
        np.int32
    )

# -------------------- SCALED REGIONS --------------------
regions = {
    "WEST": scale_poly(LEFT_poly),
    "EAST": scale_poly(RIGHT_poly),
    "NORTH": scale_poly(UP_poly),
    "SOUTH": scale_poly(DOWN_poly),
    "CENTER": scale_poly(CENTER_poly)
}

NONROI_LIST = [
    scale_poly(NONROI1_poly),
    scale_poly(NONROI2_poly),
    scale_poly(NONROI3_poly),
    scale_poly(NONROI4_poly)
]

# -------------------- COLORS --------------------
colors = {
    "WEST": (0, 255, 0),
    "EAST": (255, 0, 0),
    "NORTH": (0, 0, 255),
    "SOUTH": (0, 165, 255),
    "CENTER": (255, 0, 255)
}

all_polygons = {
    **regions,
    "NONROI1": NONROI_LIST[0],
    "NONROI2": NONROI_LIST[1],
    "NONROI3": NONROI_LIST[2],
    "NONROI4": NONROI_LIST[3]
}

all_colors = {
    **colors,
    "NONROI1": (128, 0, 128),
    "NONROI2": (128, 0, 128),
    "NONROI3": (128, 0, 128),
    "NONROI4": (128, 0, 128)
}

direction_arrows = {"WEST": "<", "EAST": ">", "NORTH": "^", "SOUTH": "v", "CENTER": "o"}

# -------------------- OUTPUT FOLDERS --------------------
output_folder = "TrafficLight_MainPico_Final"
image_folder = os.path.join(output_folder, "images")
red_light_folder = os.path.join(output_folder, "red_light_camera")
os.makedirs(image_folder, exist_ok=True)
os.makedirs(red_light_folder, exist_ok=True)

video_path = os.path.join(output_folder, "traffic.mp4")
if USE_TRADITIONAL_FIXED_MODE == True:
    csv_path = os.path.join(output_folder, "TRADITIONAL_traffic_log.csv")
else:
    csv_path = os.path.join(output_folder, "MODERN_traffic_log.csv")


write_header = not os.path.exists(csv_path)
with open(csv_path, "a") as f:
    if write_header:
        f.write(
            "timestamp,WEST,EAST,NORTH,SOUTH,CENTER,"
            "wait_W,wait_E,wait_N,wait_S,"
            "current_phase,signal_state,remaining_time,predicted_green\n"
        )

video_writer = cv2.VideoWriter(
    video_path,
    cv2.VideoWriter_fourcc(*"mp4v"),
    25,
    (FRAME_WIDTH, FRAME_HEIGHT)
)

# -------------------- CYCLE LOGGER --------------------
class CycleLogger:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._ensure_csv()

    def _ensure_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w") as f:
                f.write(
                    "timestamp,phase,signal_state,green_duration,"
                    "WEST,EAST,NORTH,SOUTH,CENTER,"
                    "wait_W,wait_E,wait_N,wait_S,vehicles_passed,avg_wait\n"
                )

    def log_cycle(self, current_phase, signal_state, green_duration, counts, wait_times, vehicles_passed, avg_wait):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(self.csv_path, "a") as f:
            f.write(
                f"{ts},{current_phase},{signal_state},{green_duration},"
                f"{counts['WEST']},{counts['EAST']},{counts['NORTH']},{counts['SOUTH']},{counts['CENTER']},"
                f"{wait_times['W']:.2f},{wait_times['E']:.2f},{wait_times['N']:.2f},{wait_times['S']:.2f},"
                f"{vehicles_passed},{avg_wait:.2f}\n"
            )

if USE_TRADITIONAL_FIXED_MODE == True:
    cycle_logger = CycleLogger(csv_path=os.path.join(output_folder, "TRADITIONAL_cycle_log.csv"))
else:
    cycle_logger = CycleLogger(csv_path=os.path.join(output_folder, "MODERN_cycle_log.csv"))

# -------------------- EDIT MODE --------------------
edit_mode = False
selected_region = None
selected_vertex = None
drag_radius = 10

def mouse_drag(event, x, y, flags, param):
    global selected_region, selected_vertex, all_polygons
    if not edit_mode:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        for name, poly in all_polygons.items():
            for i, p in enumerate(poly):
                px, py = p
                if abs(x - px) < drag_radius and abs(y - py) < drag_radius:
                    selected_region = name
                    selected_vertex = i
                    return
    elif event == cv2.EVENT_MOUSEMOVE:
        if selected_region is not None:
            all_polygons[selected_region][selected_vertex] = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        selected_region = None
        selected_vertex = None

cv2.namedWindow("Smart Traffic Camera")
cv2.setMouseCallback("Smart Traffic Camera", mouse_drag)

# -------------------- HELPERS --------------------
def get_region(cx, cy):
    for name, poly in regions.items():
        if inside((cx, cy), poly):
            return name
    return None

def update_tracking(detections):
    global tracked_objects, next_object_id, total_vehicles_passed

    new_tracked = {}
    used_ids = set()

    for (cx, cy) in detections:
        matched_id = None
        min_dist = 9999

        # Find closest existing object
        for obj_id, data in tracked_objects.items():
            prev_cx, prev_cy, prev_region = data

            dist = ((cx - prev_cx)**2 + (cy - prev_cy)**2) ** 0.5

            if dist < DIST_THRESHOLD and dist < min_dist and obj_id not in used_ids:
                matched_id = obj_id
                min_dist = dist

        current_region = get_region(cx, cy)

        # -------------------- MATCH FOUND --------------------
        if matched_id is not None:
            prev_cx, prev_cy, prev_region = tracked_objects[matched_id]

            # THROUGH-PASS DETECTION
            if prev_region == "CENTER" and current_region != "CENTER":
                total_vehicles_passed += 1

            new_tracked[matched_id] = (cx, cy, current_region)
            used_ids.add(matched_id)

        # -------------------- NEW OBJECT --------------------
        else:
            new_tracked[next_object_id] = (cx, cy, current_region)
            next_object_id += 1

    tracked_objects = new_tracked

def draw_poly(img, pts, color, show_vertices=False):
    cv2.polylines(img, [pts.reshape((-1, 1, 2))], True, color, 2)
    if show_vertices:
        for x, y in pts:
            cv2.circle(img, (x, y), 5, (0, 255, 255), -1)

def inside(pt, poly):
    return cv2.pointPolygonTest(poly, pt, False) >= 0

def send_signal_to_pico(state, phase):
    msg = f"{state}:{phase}\n"
    if ser:
        ser.write(msg.encode())
    print(f"Sent to Pico: {msg.strip()}")

def not_current_phase(phase):
    return "NS" if phase == "EW" else "EW"

def reset_waits_for_green_phase(phase_name):
    global wait_N, wait_S, wait_E, wait_W
    if phase_name == "NS":
        wait_N = 0.0
        wait_S = 0.0
    else:
        wait_E = 0.0
        wait_W = 0.0

def update_wait_times(counts, dt):
    global wait_N, wait_S, wait_E, wait_W, current_phase, total_wait_time_accum, total_wait_samples

    if current_phase == "NS":
        wait_E += counts["EAST"] * dt
        wait_W += counts["WEST"] * dt
        #wait_N = max(0.0, wait_N - counts["NORTH"] * dt)
        #wait_S = max(0.0, wait_S - counts["SOUTH"] * dt)
    else:
        wait_N += counts["NORTH"] * dt
        wait_S += counts["SOUTH"] * dt
        #wait_E = max(0.0, wait_E - counts["EAST"] * dt)
        #wait_W = max(0.0, wait_W - counts["WEST"] * dt)
    # -------------------- PERFORMANCE UPDATE --------------------
    total_wait_time_accum += (wait_N + wait_S + wait_E + wait_W)
    total_wait_samples += 1

def get_phase_flag(phase_name):
    return 0 if phase_name == "NS" else 1

def get_model_green(cars_N, cars_S, cars_E, cars_W, wait_N, wait_S, wait_E, wait_W, current_phase):
    phase_flag = get_phase_flag(current_phase)
    ped_flag = 0
    hour = datetime.now().hour

    pred = predict_green_time(
        cars_N, cars_S, cars_E, cars_W,
        wait_N, wait_S, wait_E, wait_W,
        phase_flag, ped_flag, hour
    )

    try:
        pred = int(round(float(pred)))
    except Exception:
        pred = 10

    pred = max(MIN_GREEN, min(pred, MAX_GREEN))
    return pred

# -------------------- MAIN LOOP --------------------
print("Press E=Edit Mode, S=Save polygons, G=Toggle ROI grid, N=Toggle non-ROI grid, P=Toggle privacy, T=Toggle UI info, Q=Quit")

predicted_green_last = 10

adjustment_text = ""
adjustment_color = (255, 255, 255)
adjustment_until_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

    if edit_mode:
        display_frame = frame.copy()
        for name, poly in all_polygons.items():
            draw_poly(display_frame, poly, all_colors[name], show_vertices=True)
        cv2.putText(display_frame, "EDIT MODE - Drag vertices, S=Save, E=Exit", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (130,0,10), 2)
        cv2.imshow("Smart Traffic Camera", display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("e"):
            edit_mode = False
            print("Exited edit mode. Resuming detection.")
        elif key == ord("s"):
            with open("updated_polygons.py", "w") as f:
                for name, poly in all_polygons.items():
                    f.write(f"{name}_poly = {poly.tolist()}\n")
            print("Polygons saved to updated_polygons.py")
        elif key == ord("q"):
            break
        continue

    # ---------- NORMAL MODE ----------
    mask = np.ones(frame.shape[:2], dtype="uint8") * 255
    for nroi in NONROI_LIST:
        cv2.fillPoly(mask, [nroi], 0)
    masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

    results = model.predict(
        source=masked_frame,
        conf=0.5,
        device=YOLO_DEVICE,
        half=YOLO_HALF,
        verbose=False
    )

    image = results[0].plot(img=masked_frame.copy() if PRIVACY_MODE else frame.copy())

    # -------------------- COUNT VEHICLES --------------------
    counts = {k: 0 for k in regions.keys()}
    violated = False

    detections = []

    for box in results[0].boxes:
        cls = int(box.cls[0])
        if model.names[cls] != "car":
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        detections.append((cx, cy))

        for name, poly in regions.items():
            if inside((cx, cy), poly):
                counts[name] += 3    #scaling for cars
                if name == "CENTER" and signal_state == "ALL_RED":
                    violated = True
                    cv2.circle(image, (cx, cy), int(max(x2-x1,y2-y1)*0.9), (0,0,255),5)
                    cv2.rectangle(image,(x1,y1),(x2,y2),(0,0,255),3)
                    cv2.putText(image,"RED LIGHT VIOLATION",(x1,y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)
                break

    now = time.time()
    sec = int(now)

    #CARS PASSING METRIC EVALUATION
    if DETECTION_TRACKING_ENABLED == True:
        update_tracking(detections)
    else:
        if now - last_pass_update_time >= PASS_UPDATE_INTERVAL:
            last_pass_update_time = now

            if signal_state == "GREEN":
                if current_phase == "NS":
                    total_vehicles_passed += counts["NORTH"] + counts["SOUTH"]
                else:
                    total_vehicles_passed += counts["EAST"] + counts["WEST"]

    # -------------------- UPDATE SIMPLE WAITS --------------------
    dt = now - last_wait_update_time
    last_wait_update_time = now
    update_wait_times(counts, dt)

    cars_N = counts["NORTH"]
    cars_S = counts["SOUTH"]
    cars_E = counts["EAST"]
    cars_W = counts["WEST"]

    # -------------------- STATE MACHINE --------------------
    phase_changed = False
    if signal_state == "GREEN" and now >= green_end_time:
        signal_state = "YELLOW"
        green_end_time = now + YELLOW_TIME
        send_signal_to_pico("YELLOW", current_phase)
        phase_changed = True

    elif signal_state == "YELLOW" and now >= green_end_time:
        signal_state = "ALL_RED"
        green_end_time = now + ALL_RED_TIME
        pending_phase = not_current_phase(current_phase)
        send_signal_to_pico("RED", current_phase)
        phase_changed = True

    elif signal_state == "ALL_RED" and now >= green_end_time:
        signal_state = "GREEN"
        current_phase = pending_phase

        reset_waits_for_green_phase(current_phase)

        if USE_TRADITIONAL_FIXED_MODE:
            predicted_green_last = FIXED_GREEN_TIME
        else:
            predicted_green_last = get_model_green(
                cars_N, cars_S, cars_E, cars_W,
                wait_N, wait_S, wait_E, wait_W,
                current_phase
            )
        green_end_time = now + predicted_green_last
        totalInc = 0
        totalDec = 0
        last_check_time = now
        send_signal_to_pico("GREEN", current_phase)
        phase_changed = True

    # -------------------- LOG EVERY PHASE --------------------
    if phase_changed:
        counts_dict = counts.copy()
        wait_dict = {"N": wait_N, "S": wait_S, "E": wait_E, "W": wait_W}
        duration = int(green_end_time - now) if signal_state=="GREEN" else (YELLOW_TIME if signal_state=="YELLOW" else ALL_RED_TIME)
        avg_wait = total_wait_time_accum / max(1, total_wait_samples)
        cycle_logger.log_cycle(current_phase, signal_state, duration, counts_dict, wait_dict,total_vehicles_passed,avg_wait)

    # -------------------- DYNAMIC EXTENSION --------------------
    if signal_state == "GREEN" and now - last_check_time >= CHECK_INTERVAL:
        if current_phase == "NS":
            P = cars_N + cars_S
            O = cars_E + cars_W
        else:
            P = cars_E + cars_W
            O = cars_N + cars_S
        if P > O + 2 and totalInc <= 12:
            green_end_time += EXTENSION_STEP
            totalInc += EXTENSION_STEP

            adjustment_text = f"+{EXTENSION_STEP}s"
            adjustment_color = (255, 153, 255)
            adjustment_until_time = now + 1.5

        elif O > P + 2 and totalDec <= 12:
            green_end_time = max(now+1, green_end_time - EXTENSION_STEP)
            totalDec += EXTENSION_STEP

            adjustment_text = f"-{EXTENSION_STEP}s"
            adjustment_color = (102, 255, 255)
            adjustment_until_time = now + 1.5

        last_check_time = now

    if now < adjustment_until_time:
        cv2.putText(image, adjustment_text, (FRAME_WIDTH - 120, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, adjustment_color, 2)

    # -------------------- RED LIGHT CAPTURE --------------------
    if signal_state == "ALL_RED" and violated and sec != last_red_capture_second:
        last_red_capture_second = sec
        violation_id += 1
        now_dt = datetime.now()
        month_folder = os.path.join(red_light_folder, now_dt.strftime("%Y %b").upper())
        day_folder = os.path.join(month_folder, now_dt.strftime("%b %d").upper())
        os.makedirs(day_folder, exist_ok=True)
        cv2.putText(image, "RED LIGHT VIOLATION", (10, FRAME_HEIGHT-120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)   # change location of the text
        cv2.putText(image, f"Violation ID: {violation_id}", (10, FRAME_HEIGHT-80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255),2)
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_str_save = datetime.now().strftime("%Y-%m-%d %H_%M_%S")
        cv2.putText(image, time_str, (10, FRAME_HEIGHT - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(image, time_str, (10, FRAME_HEIGHT - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        save_path = os.path.join(day_folder,f"RED_{time_str_save}.jpg")
        cv2.imwrite(save_path, image)
        print(f"RED LIGHT VIOLATION SAVED: {save_path}")

    remaining = max(0, int(green_end_time - now))

    # -------------------- DRAW POLYGONS --------------------
    if SHOW_ROI_GRIDS:
        for name, poly in regions.items():
            draw_poly(image, poly, colors[name], show_vertices=False)
    if SHOW_NONROI_GRID:
        for nroi_poly in NONROI_LIST:
            draw_poly(image, nroi_poly, (128,0,128), show_vertices=False)

    # -------------------- UI TEXT --------------------
    if SHOW_UI_INFO:
        text_color_map = {"GREEN": (0,255,0), "YELLOW": (0,255,255), "ALL_RED": (0,0,255)}
        if signal_state == "GREEN":
            d = "NORTH/SOUTH" if current_phase == "NS" else "EAST/WEST"
            text = f"GREEN: {d}"
        elif signal_state == "YELLOW":
            d = "NORTH/SOUTH" if current_phase == "NS" else "EAST/WEST"
            text = f"YELLOW: {d}"
        else:
            text = "ALL RED"

        color = text_color_map[signal_state]
        cv2.putText(image,f"{text} | {remaining}s | Model={predicted_green_last}s",(10,30),
                    cv2.FONT_HERSHEY_SIMPLEX,0.7,color,2)

        y = 60
        for k in ["WEST","EAST","NORTH","SOUTH","CENTER"]:
            arrow = direction_arrows[k]
            cv2.putText(image,f"{arrow} {k}: {counts[k]}",(10,y),cv2.FONT_HERSHEY_SIMPLEX,0.7,colors[k],2)
            y += 30

        cv2.putText(image,f"Wait N:{wait_N:.1f} S:{wait_S:.1f} E:{wait_E:.1f} W:{wait_W:.1f}",(10,y+10),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)

        now2 = time.time()
        fps = 1 / (now2 - prev_time) if now2 - prev_time > 0 else 0
        fps_smooth = 0.9*fps_smooth + 0.1*fps
        prev_time = now2
        cv2.putText(image,f"FPS: {fps_smooth:.2f}",(FRAME_WIDTH-150,30),cv2.FONT_HERSHEY_SIMPLEX,0.7,(128,0,0),2)

    # -------------------- TIMESTAMP --------------------
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(image,time_str,(10,FRAME_HEIGHT-20),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,0),4)
    cv2.putText(image,time_str,(10,FRAME_HEIGHT-20),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)

    # -------------------- SAVE NORMAL IMAGE & CSV --------------------
    if sec != last_saved_second:
        last_saved_second = sec
        now_dt = datetime.now()
        ts = now_dt.strftime("%Y-%m-%d_%H-%M-%S")
        month_folder = os.path.join(image_folder, now_dt.strftime("%Y %b").upper())
        day_folder = os.path.join(month_folder, now_dt.strftime("%b %d").upper())
        os.makedirs(day_folder, exist_ok=True)
        save_path = os.path.join(day_folder,f"{ts}.jpg")
        cv2.imwrite(save_path,image)

        with open(csv_path,"a") as f:
            f.write(
                f"{ts},{counts['WEST']},{counts['EAST']},{counts['NORTH']},{counts['SOUTH']},{counts['CENTER']},"
                f"{wait_W:.2f},{wait_E:.2f},{wait_N:.2f},{wait_S:.2f},"
                f"{current_phase},{signal_state},{remaining},{predicted_green_last}\n"
            )

    video_writer.write(image)
    cv2.imshow("Smart Traffic Camera", image)

    # -------------------- KEYS --------------------
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("e"):
        edit_mode = True
        print("Entered edit mode. Traffic logic paused.")
    elif key == ord("g"):
        SHOW_ROI_GRIDS = not SHOW_ROI_GRIDS
    elif key == ord("n"):
        SHOW_NONROI_GRID = not SHOW_NONROI_GRID
    elif key == ord("p"):
        PRIVACY_MODE = not PRIVACY_MODE
    elif key == ord("t"):
        SHOW_UI_INFO = not SHOW_UI_INFO

# -------------------- CLEANUP --------------------
cap.release()
video_writer.release()
cv2.destroyAllWindows()
if ser:
    ser.close()

print("\n---------- Saved Output ----------")
print(f"Images saved in: {image_folder}")
print(f"Video saved: {video_path}")
print(f"CSV log saved: {csv_path}")
print(f"Cycle log saved: {os.path.join(output_folder, 'cycle_log.csv')}")
print("Done! Frames, video, CSV saved, and Pico disconnected.")