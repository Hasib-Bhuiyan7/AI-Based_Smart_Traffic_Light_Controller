import cv2
import os

# Create output folders
auto_folder = "auto_capture"
manual_folder = "manual_capture"

if not os.path.exists(auto_folder):
    os.makedirs(auto_folder)
if not os.path.exists(manual_folder):
    os.makedirs(manual_folder)

# Open the default webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Cannot open webcam")
    exit()

print("Press 'c' to manually capture an image, 'q' to quit.")

# Counters
auto_counter = 1
manual_counter = 1
frame_counter = 0

# How often to automatically save a frame (every N frames)
save_every_n_frames = 30  # roughly every 1 second if webcam is 30 FPS

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    frame_counter += 1

    # Display the live webcam feed
    cv2.imshow("Webcam Feed", frame)

    # Automatic capture every N frames
    if frame_counter % save_every_n_frames == 0:
        auto_filename = f"{auto_folder}/auto_{auto_counter}.png"
        cv2.imwrite(auto_filename, frame)
        print(f"Automatic image saved as {auto_filename}")
        auto_counter += 1

    # Manual capture
    key = cv2.waitKey(1) & 0xFF
    if key == ord('c'):
        manual_filename = f"{manual_folder}/manual_{manual_counter}.png"
        cv2.imwrite(manual_filename, frame)
        print(f"Manual image saved as {manual_filename}")
        manual_counter += 1
    elif key == ord('q'):
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
