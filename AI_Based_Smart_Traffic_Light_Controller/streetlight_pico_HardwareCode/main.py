import machine
import time
import sys
import select

# # -------------------- LED PINS --------------------
# L1_on = machine.Pin(0, machine.Pin.OUT)
# #L2_on = machine.Pin(1, machine.Pin.OUT)
# print("STREET light running...")
# L1_on.value(1)
# #L2_on.value(1)
# time.sleep(5)
# print("STREET light OFF...")
# L1_on.value(0)
# #L2_on.value(0)

print("Streetlight Controller Started")

# -------------------- SETUP 12 LIGHTS --------------------
pins = [21,20,22,#SOUTHEAST: ORANGE & BROWN 
        18,17,16, #NORTHEAST: PURPLE AND WHITE
        12,14,15, #NORTHWEST: BLUE AND WHITE
        0,1,2]#SOUTHWEST: GREEN AND YELLOW

lights = []
for p in pins:
    lights.append(machine.Pin(p, machine.Pin.OUT))

# -------------------- HELPER FUNCTIONS --------------------
def all_off():
    for light in lights:
        light.value(0)

def all_on():
    for light in lights:
        light.value(1)
        
def all_SE_on():
    all_off()
    lights[0].value(1)
    lights[1].value(1)
    lights[2].value(1)
    
def all_NE_on():
    all_off()
    lights[3].value(1)
    lights[4].value(1)
    lights[5].value(1)
    
def all_NW_on():
    all_off()
    lights[6].value(1) #NORTHWEST CORNER(QUESTIONABLE)
    lights[7].value(1)
    lights[8].value(1)
    
def all_SW_on():
    all_off()
    lights[9].value(1)
    lights[10].value(1)
    lights[11].value(1)
        

def set_light(index, state):
    if 0 <= index < len(lights):
        lights[index].value(state)

# -------------------- MAIN LOOP --------------------
all_on()
time.sleep(10)
all_off()

while True:
    r = select.select([sys.stdin], [], [], 0)

    if r:
        try:
            line = sys.stdin.readline().strip()
            print("Received:", line)

            if not line:
                continue

            cmd = line.upper()

            # STOP everything
            if cmd == "STOP":
                all_off()
                print("All lights OFF")
                break

            # TURN ALL ON
            if cmd == "ALL_ON":
                all_on()
                print("All lights ON")
                continue

            # TURN ALL OFF
            if cmd == "ALL_OFF":
                all_off()
                print("All lights OFF")
                continue
            
            # TURN ALL SE_ON
            if cmd == "SE_ON":
                all_SE_on()
                print("SOUTHEAST lights ON")
                continue

            # TURN ALL SW_ON
            if cmd == "SW_ON":
                all_SW_on()
                print("SOUTHWEST lights ON")
                continue
            
            # TURN ALL NE_ON
            if cmd == "NE_ON":
                all_NE_on()
                print("NORTHEAST lights ON")
                continue

            # TURN ALL NW_ON
            if cmd == "NW_ON":
                all_NW_on()
                print("NORTHWEST lights ON")
                continue
            

            # INDIVIDUAL CONTROL
            # Format: L3:ON or L5:OFF
            if ":" in cmd:
                light_cmd, state_cmd = cmd.split(":")
                
                if light_cmd.startswith("L"):
                    index = int(light_cmd[1:]) - 1
                    state = 1 if state_cmd == "ON" else 0
                    set_light(index, state)
                    print(f"Light {index+1} set to {state_cmd}")

        except Exception as e:
            print("Error:", e)
            continue
            
        except KeyboardInterrupt:
            print("Recovered from interrupt")
            continue


'''import machine
import time
import sys
import select

# # -------------------- LED PINS --------------------
# L1_on = machine.Pin(0, machine.Pin.OUT)
# #L2_on = machine.Pin(1, machine.Pin.OUT)
# print("STREET light running...")
# L1_on.value(1)
# #L2_on.value(1)
# time.sleep(5)
# print("STREET light OFF...")
# L1_on.value(0)
# #L2_on.value(0)

print("Streetlight Controller Started")

# -------------------- SETUP 12 LIGHTS --------------------
pins = [21,20,22,#SOUTHEAST: ORANGE & BROWN 
        18,17,16, #NORTHEAST: PURPLE AND WHITE
        12,14,15, #NORTHWEST: BLUE AND WHITE
        0,1,2]#SOUTHWEST: GREEN AND YELLOW

lights = []
for p in pins:
    lights.append(machine.Pin(p, machine.Pin.OUT))

# -------------------- HELPER FUNCTIONS --------------------
def all_off():
    for light in lights:
        light.value(0)

def all_on():
    for light in lights:
        light.value(1)
        
def all_SE_on():
    all_off()
    lights[0].value(1)
    lights[1].value(1)
    lights[2].value(1)
    
def all_NE_on():
    all_off()
    lights[3].value(1)
    lights[4].value(1)
    lights[5].value(1)
    
def all_NW_on():
    all_off()
    lights[6].value(1) #NORTHWEST CORNER(QUESTIONABLE)
    lights[7].value(1)
    lights[8].value(1)
    
def all_SW_on():
    all_off()
    lights[9].value(1)
    lights[10].value(1)
    lights[11].value(1)
        

def set_light(index, state):
    if 0 <= index < len(lights):
        lights[index].value(state)

# -------------------- MAIN LOOP --------------------
all_on()
time.sleep(10)
all_off()

while True:
    r = select.select([sys.stdin], [], [], 0)

    if r:
        try:
            line = sys.stdin.readline().strip()
            print("Received:", line)

            if not line:
                continue

            cmd = line.upper()

            # STOP everything
            if cmd == "STOP":
                all_off()
                print("All lights OFF")
                break

            # TURN ALL ON
            if cmd == "ALL_ON":
                all_on()
                print("All lights ON")
                continue

            # TURN ALL OFF
            if cmd == "ALL_OFF":
                all_off()
                print("All lights OFF")
                continue
            
            # TURN ALL SE_ON
            if cmd == "SE_ON":
                all_SE_on()
                print("SOUTHEAST lights ON")
                continue

            # TURN ALL SW_ON
            if cmd == "SW_ON":
                all_SW_on()
                print("SOUTHWEST lights ON")
                continue
            
            # TURN ALL NE_ON
            if cmd == "NE_ON":
                all_NE_on()
                print("NORTHEAST lights ON")
                continue

            # TURN ALL NW_ON
            if cmd == "NW_ON":
                all_NW_on()
                print("NORTHWEST lights ON")
                continue
            

            # INDIVIDUAL CONTROL
            # Format: L3:ON or L5:OFF
            if ":" in cmd:
                light_cmd, state_cmd = cmd.split(":")
                
                if light_cmd.startswith("L"):
                    index = int(light_cmd[1:]) - 1
                    state = 1 if state_cmd == "ON" else 0
                    set_light(index, state)
                    print(f"Light {index+1} set to {state_cmd}")

        except Exception as e:
            print("Error:", e)
            continue
            
        except KeyboardInterrupt:
            print("Recovered from interrupt")
            continue

'''