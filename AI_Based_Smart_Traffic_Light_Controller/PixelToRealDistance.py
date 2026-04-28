import cv2
import numpy as np

points = []

real_distance = float(input("Enter real distance between clicks (cm): "))

def mouse_click(event, x, y, flags, param):
    global points, image

    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print("Point:", x, y)

        # draw point
        cv2.circle(image, (x, y), 5, (0, 0, 255), -1)

        # if 2 points selected -> compute distance
        if len(points) == 2:
            x1, y1 = points[0]
            x2, y2 = points[1]

            pixel_distance = np.sqrt((x2-x1)**2 + (y2-y1)**2)

            scale = pixel_distance / real_distance

            print("Pixel Distance:", pixel_distance)
            print("Scale =", scale, "pixels per cm\n")

            # draw line
            cv2.line(image, points[0], points[1], (255,0,0), 2)

            points.clear()   # reset for next measurement

        cv2.imshow("Image", image)


image = cv2.imread("images/imagetest(4).jpg")

cv2.imshow("Image", image)
cv2.setMouseCallback("Image", mouse_click)

cv2.waitKey(0)
cv2.destroyAllWindows()