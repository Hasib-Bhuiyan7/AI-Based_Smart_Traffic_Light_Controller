\# Intelligent Adaptive Traffic Light System



\*\*Capstone Project\*\*



\## Project Overview:



Traditional traffic light systems operate using fixed timing intervals and do not adapt to real-time traffic conditions. This often leads to inefficient green time usage, increased queue lengths, and unnecessary delays, especially during peak hours.



This project focuses on the design and implementation of an adaptive traffic control system that dynamically adjusts signal timings based on real-time traffic demand. The system integrates computer vision, a machine learning–based decision model, and a physical hardware controller to form a complete end-to-end traffic management solution.



\---



\## System Design:



The system is built as a closed-loop pipeline consisting of three main components: detection, decision-making, and control.



\### Traffic Detection (Computer Vision):



A custom YOLO-based object detection model is used to detect vehicles from a live camera feed. The model was trained on a dataset of over 3,000 labeled images collected under different traffic and lighting conditions.



The intersection is divided into predefined regions (North, South, East, West, and Center), allowing the system to:



\* Count vehicles per direction

\* Estimate traffic density

\* Track vehicle movement through the intersection

\* Detect red-light violations



This information is continuously updated and used as input for the decision model.



\---



\### Decision Model (Adaptive Control):



The core of the system is a Random Forest regression model that predicts the optimal green-light duration. The model takes into account:



\* Directional vehicle counts

\* Accumulated waiting times

\* Current signal phase

\* Time-of-day information



Training data was generated using SUMO simulation, where multiple green time options were evaluated at each state and the best-performing option was selected. The final model was trained on 1962 samples and achieved:



\* MAE: 2.506 seconds

\* RMSE: 4.001 seconds

\* 98% accuracy within a 10-second tolerance



In addition to the predicted green time, the system applies real-time adjustments by extending or reducing the green phase depending on current traffic imbalance.



\---



\### Hardware Control (Physical Prototype):



The system is connected to a Raspberry Pi Pico, which controls a physical traffic light setup using LEDs. Communication between the main system and the Pico is handled through serial communication.



The Pico receives commands in the form of signal states and phases (e.g., GREEN:NS) and updates the lights accordingly. A fail-safe mechanism is implemented to switch to an all-red state in case of communication loss or system failure.



\---



\## Traffic Control Logic:



The traffic system operates using a finite state machine:



Green → Yellow → All Red → Phase Switch → Green



At each cycle:



\* The model predicts a base green time

\* The system adjusts this time dynamically

\* The next phase is selected based on demand



This allows the system to respond continuously to changing traffic conditions instead of relying on fixed cycles.



\---



\## Performance Evaluation:



\### Simulation Results:



The system was tested in the SUMO simulation environment using the Dundas and Church intersection. When compared to a traditional fixed-time controller, the adaptive system showed:



\* Increased throughput by 37.14%

\* Reduced average queue length by 73.98%

\* Reduced total waiting time by 93.74%



These improvements were most noticeable under high traffic conditions.



\---



\### Physical Prototype Results:



The system was also tested using a real-time hardware prototype. Performance data was collected and analyzed using custom scripts.



Across low, medium, and high traffic scenarios, the adaptive system consistently:



\* Improved vehicle flow

\* Reduced waiting time

\* Maintained shorter queues



The system also remained stable under different lighting conditions, with only minor performance degradation in low-light environments.



\---



\## Key Features:



\* Real-time vehicle detection using deep learning

\* Adaptive green-light prediction using machine learning

\* Dynamic adjustment of signal timing

\* Red-light violation detection and logging

\* CSV and video-based system logging

\* Hardware integration with Raspberry Pi Pico

\* Fail-safe safety mechanisms



\---



\## Technologies Used:



\* Python, OpenCV, NumPy

\* YOLO (Ultralytics / PyTorch)

\* Scikit-learn (Random Forest)

\* SUMO Traffic Simulator

\* PySerial

\* Raspberry Pi Pico (MicroPython)



\---



\## Conclusion:



This project demonstrates a complete adaptive traffic control system that integrates detection, decision-making, and physical implementation.



The results show that using real-time data and machine learning can significantly improve traffic efficiency compared to traditional fixed-time systems. The system performs especially well under congested conditions and provides a strong foundation for future work in intelligent traffic management and smart city applications.

