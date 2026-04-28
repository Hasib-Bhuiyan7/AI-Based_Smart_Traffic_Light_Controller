import machine
import time
import sys
import select
#PICO CODE STORED WITHIN PICO BOARD
print("BOOT START")

# -------------------- LED PINS --------------------
red_led_North = machine.Pin(18, machine.Pin.OUT)
yellow_led_North = machine.Pin(19, machine.Pin.OUT)
green_led_North = machine.Pin(20, machine.Pin.OUT)

red_led_South = machine.Pin(2, machine.Pin.OUT)
yellow_led_South = machine.Pin(3, machine.Pin.OUT)
green_led_South = machine.Pin(4, machine.Pin.OUT)

red_led_West = machine.Pin(13, machine.Pin.OUT)
yellow_led_West = machine.Pin(12, machine.Pin.OUT)
green_led_West = machine.Pin(11, machine.Pin.OUT)

red_led_East = machine.Pin(6, machine.Pin.OUT)
yellow_led_East = machine.Pin(7, machine.Pin.OUT)
green_led_East = machine.Pin(8, machine.Pin.OUT)

# -------------------- GLOBAL STATE --------------------
last_command_time = time.time()
TIMEOUT_LIMIT = 40   # seconds before fail-safe triggers

# -------------------- HELPER FUNCTIONS --------------------
def all_NS_off():
    red_led_North.value(0)
    yellow_led_North.value(0)
    green_led_North.value(0)

    red_led_South.value(0)
    yellow_led_South.value(0)
    green_led_South.value(0)

def all_EW_off():
    red_led_East.value(0)
    yellow_led_East.value(0)
    green_led_East.value(0)

    red_led_West.value(0)
    yellow_led_West.value(0)
    green_led_West.value(0)

def all_on():
    red_led_North.value(1)
    red_led_South.value(1)
    red_led_East.value(1)
    red_led_West.value(1)
    yellow_led_North.value(1)
    yellow_led_South.value(1)
    yellow_led_East.value(1)
    yellow_led_West.value(1)
    green_led_North.value(1)
    green_led_South.value(1)
    green_led_East.value(1)
    green_led_West.value(1)
    

def all_off():
    all_NS_off()
    all_EW_off()

def all_red():
    all_off()
    red_led_North.value(1)
    red_led_South.value(1)
    red_led_East.value(1)
    red_led_West.value(1)
    
def light_show():
    for i in range(1):
        for k in range (5):
            red_led_North.value(1)
            red_led_South.value(1)
            red_led_East.value(1)
            red_led_West.value(1)
            time.sleep(1)
            all_off()
            yellow_led_North.value(1)
            yellow_led_South.value(1)
            yellow_led_East.value(1)
            yellow_led_West.value(1)
            time.sleep(1)
            all_off()
            green_led_North.value(1)
            green_led_South.value(1)
            green_led_East.value(1)
            green_led_West.value(1)
            time.sleep(1)
            all_off()
        for j in range(5):
            all_on()
            time.sleep(1)
            all_off()
            time.sleep(1)


        
        

# -------------------- EMERGENCY MODE --------------------
def emergency_mode(reason="UNKNOWN"):
    print(f"!!! EMERGENCY MODE ACTIVATED: {reason} !!!")

    # Flash ALL RED
    for _ in range(6):
        all_red()
        time.sleep(0.5)
        all_off()
        time.sleep(0.5)

    # Stay in safe state
    all_red()

# -------------------- SET LIGHTS --------------------
def set_lights(state, phase):
    
    if phase == 'NS':
        all_NS_off()
        if state == 'GREEN':
            green_led_North.value(1)
            green_led_South.value(1)

        elif state == 'YELLOW':
            yellow_led_North.value(1)
            yellow_led_South.value(1)

        elif state == 'RED':
            red_led_North.value(1)
            red_led_South.value(1)

    elif phase == 'EW':
        all_EW_off()
        if state == 'GREEN':
            green_led_East.value(1)
            green_led_West.value(1)

        elif state == 'YELLOW':
            yellow_led_East.value(1)
            yellow_led_West.value(1)

        elif state == 'RED':
            red_led_East.value(1)
            red_led_West.value(1)

# -------------------- INITIAL SAFE STATE --------------------
light_show()
emergency_mode("WAITING TO START THE PROCESS")
print("System initialized: ALL RED")

print("Traffic light controller running...")

# -------------------- MAIN LOOP --------------------
while True:
    try:
        r = select.select([sys.stdin], [], [], 0)

        if r[0]:
            all_red()
            line = sys.stdin.readline().strip()
            print("Received:", line)

            if line:
                last_command_time = time.time()

                if line.upper() == "STOP":
                    all_off()
                    print("System halted - ALL OFF")
                    break

                elif line.upper() == "EMERGENCY":
                    emergency_mode("Manual Trigger")

                else:
                    state, phase = line.split(":")
                    set_lights(state.upper(), phase.upper())
                    print(f"Set {state.upper()} for {phase.upper()}")

        # ---------- FAIL-SAFE TIMEOUT ----------
        if time.time() - last_command_time > TIMEOUT_LIMIT:
            emergency_mode("Lost Communication")
            last_command_time = time.time()

    except KeyboardInterrupt:
        print("Recovered from interrupt")
        continue

    except Exception as e:
        print("Error:", e)
        emergency_mode("Runtime Error")
        
# import machine
# import time
# import sys
# import select
# 
# print("BOOT START")
# 
# # -------------------- LED PINS --------------------
# red_led_North = machine.Pin(18, machine.Pin.OUT)
# yellow_led_North = machine.Pin(19, machine.Pin.OUT)
# green_led_North = machine.Pin(20, machine.Pin.OUT)
# 
# red_led_South = machine.Pin(2, machine.Pin.OUT)
# yellow_led_South = machine.Pin(3, machine.Pin.OUT)
# green_led_South = machine.Pin(4, machine.Pin.OUT)
# 
# red_led_West = machine.Pin(13, machine.Pin.OUT)
# yellow_led_West = machine.Pin(12, machine.Pin.OUT)
# green_led_West = machine.Pin(11, machine.Pin.OUT)
# 
# red_led_East = machine.Pin(9, machine.Pin.OUT)
# yellow_led_East = machine.Pin(8, machine.Pin.OUT)
# green_led_East = machine.Pin(7, machine.Pin.OUT)
# 
# # -------------------- HELPER FUNCTIONS --------------------
# def all_NS_off():
#     red_led_North.value(0)
#     yellow_led_North.value(0)
#     green_led_North.value(0)
# 
#     red_led_South.value(0)
#     yellow_led_South.value(0)
#     green_led_South.value(0)
# 
# def all_EW_off():
#     red_led_East.value(0)
#     yellow_led_East.value(0)
#     green_led_East.value(0)
# 
#     red_led_West.value(0)
#     yellow_led_West.value(0)
#     green_led_West.value(0)
# 
# def set_lights(state, phase):
#     if phase == 'NS':
#         all_NS_off()
#         if state == 'GREEN':
#             green_led_North.value(1)
#             green_led_South.value(1)
#         elif state == 'YELLOW':
#             yellow_led_North.value(1)
#             yellow_led_South.value(1)
#         elif state == 'RED':
#             red_led_North.value(1)
#             red_led_South.value(1)
# 
#     elif phase == 'EW':
#         all_EW_off()
#         if state == 'GREEN':
#             green_led_East.value(1)
#             green_led_West.value(1)
#         elif state == 'YELLOW':
#             yellow_led_East.value(1)
#             yellow_led_West.value(1)
#         elif state == 'RED':
#             red_led_East.value(1)
#             red_led_West.value(1)
# 
# print("Traffic light controller running...")
# 
# # -------------------- MAIN LOOP --------------------
# while True:
#     print("RUNNING")
#     r = select.select([sys.stdin], [], [], 0)
# 
#     if r:
#         try:
#             line = sys.stdin.readline().strip()
#             print("Received:", line)
# 
#             if not line:
#                 continue
# 
#             if line.upper() == "STOP":
#                 all_NS_off()
#                 all_EW_off()
#                 print("System halted")
#                 break
# 
#             state, phase = line.split(":")
#             set_lights(state.upper(), phase.upper())
#             print(f"Set {state.upper()} for {phase.upper()}")
# 
#         except KeyboardInterrupt:
#             print("Recovered from interrupt")
#             continue
#         except Exception as e:
#             print("Error:", e)
