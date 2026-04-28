import os
import sys
import csv
from datetime import datetime

# -------------------- SUMO SETUP --------------------
os.environ["SUMO_HOME"] = r"C:\Program Files (x86)\Eclipse\Sumo"

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

import traci
import sumolib

from decision_model import predict_green_time

# -------------------- CONFIG --------------------
TLS_ID = "clusterJ14_J16_J17"

# Edge mapping
N_EDGE = "E9"
S_EDGE = "-E8"
E_EDGE = "-E7"
W_EDGE = "E7"

CONFIG_FILE = "config.sumocfg"
USE_GUI = True
MAX_SIM_TIME = 2500
WARMUP_STEPS = 150

CSV_LOG = "decision_model_live_adjusted_log.csv"

# -------------------- ADJUSTMENT SETTINGS --------------------
MAX_GREEN = 40
MIN_GREEN = 5
EXTENSION_STEP = 2
CHECK_INTERVAL = 2

# same logic style as your live camera controller
MAX_TOTAL_INC = 15
MAX_TOTAL_DEC = 15

# -------------------- HELPERS --------------------
def safe_halting(edge_id):
    return traci.edge.getLastStepHaltingNumber(edge_id)

def safe_wait(edge_id):
    return traci.edge.getWaitingTime(edge_id)

def get_counts():
    cars_n = safe_halting(N_EDGE)
    cars_s = safe_halting(S_EDGE)
    cars_e = safe_halting(E_EDGE)
    cars_w = safe_halting(W_EDGE)
    return cars_n, cars_s, cars_e, cars_w

def get_waits():
    wait_n = safe_wait(N_EDGE)
    wait_s = safe_wait(S_EDGE)
    wait_e = safe_wait(E_EDGE)
    wait_w = safe_wait(W_EDGE)
    return wait_n, wait_s, wait_e, wait_w

def is_pedestrian_waiting():
    try:
        people_ids = traci.person.getIDList()
        for p_id in people_ids:
            road_id = traci.person.getRoadID(p_id)
            if road_id in [N_EDGE, S_EDGE, E_EDGE, W_EDGE]:
                return 1
    except Exception:
        pass
    return 0

def get_phase_name(current_phase):
    if current_phase == 0:
        return "EW"
    elif current_phase == 3:
        return "NS"
    else:
        return f"OTHER({current_phase})"

def get_phase_flag_for_model(current_phase):
    """
    decision_model.py convention:
    0 = NS active
    1 = EW active
    """
    if current_phase == 0:   # SUMO phase 0 = EW green
        return 1
    elif current_phase == 3: # SUMO phase 3 = NS green
        return 0
    else:
        raise ValueError(f"Unexpected phase for model decision: {current_phase}")

def get_active_and_opposing_load(current_phase, cars_n, cars_s, cars_e, cars_w):
    if current_phase == 3:  # NS green
        active = cars_n + cars_s
        opposing = cars_e + cars_w
    elif current_phase == 0:  # EW green
        active = cars_e + cars_w
        opposing = cars_n + cars_s
    else:
        active = 0
        opposing = 0
    return active, opposing

def write_log_header_if_needed(csv_path):
    need_header = not os.path.exists(csv_path)
    if need_header:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "sim_time",
                "phase_name",
                "sumo_phase",
                "phase_flag_model",
                "cars_N", "cars_S", "cars_E", "cars_W",
                "wait_N", "wait_S", "wait_E", "wait_W",
                "ped_flag",
                "base_predicted_green",
                "final_applied_green",
                "total_inc",
                "total_dec"
            ])

def append_log(
    csv_path,
    sim_time,
    current_phase,
    phase_flag,
    cars_n, cars_s, cars_e, cars_w,
    wait_n, wait_s, wait_e, wait_w,
    ped_flag,
    base_predicted_green,
    final_applied_green,
    total_inc,
    total_dec
):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            ts,
            f"{sim_time:.1f}",
            get_phase_name(current_phase),
            current_phase,
            phase_flag,
            cars_n, cars_s, cars_e, cars_w,
            f"{wait_n:.2f}", f"{wait_s:.2f}", f"{wait_e:.2f}", f"{wait_w:.2f}",
            ped_flag,
            base_predicted_green,
            final_applied_green,
            total_inc,
            total_dec
        ])

def print_decision_block(
    sim_time,
    current_phase,
    cars_n, cars_s, cars_e, cars_w,
    wait_n, wait_s, wait_e, wait_w,
    ped_flag,
    base_green
):
    phase_name = get_phase_name(current_phase)

    print("\n" + "=" * 90)
    print(f"[NEW MODEL DECISION] sim_time = {sim_time:.1f}s")
    print(f"Active Phase         : {phase_name} green (SUMO phase {current_phase})")
    print(f"Cars                 : N={cars_n}, S={cars_s}, E={cars_e}, W={cars_w}")
    print(f"Waits                : N={wait_n:.1f}, S={wait_s:.1f}, E={wait_e:.1f}, W={wait_w:.1f}")
    print(f"Pedestrian Flag      : {ped_flag}")
    print(f"Base Model Green     : {base_green} seconds")
    print("=" * 90)

def print_adjustment(sim_time, phase_name, active_load, opposing_load, remaining, total_inc, total_dec, note):
    print(
        f"[ADJUST] t={sim_time:.1f}s | phase={phase_name} | "
        f"active={active_load} | opposing={opposing_load} | "
        f"remaining={remaining:.1f}s | +{total_inc}/-{total_dec} | {note}"
    )

# -------------------- MAIN --------------------
def run_live_model_with_adjustment():
    sumo_binary = sumolib.checkBinary("sumo-gui" if USE_GUI else "sumo")
    traci.start([sumo_binary, "-c", CONFIG_FILE])

    write_log_header_if_needed(CSV_LOG)

    print(f"Started SUMO with config: {CONFIG_FILE}")
    print(f"Traffic light ID: {TLS_ID}")
    print("Using trained decision model + dynamic adjustment logic.")
    print("Watching only main green phases: 0 (EW) and 3 (NS).")

    # Warmup
    for _ in range(WARMUP_STEPS):
        traci.simulationStep()
        if traci.simulation.getTime() >= MAX_SIM_TIME:
            print("Stopped during warmup because MAX_SIM_TIME was reached.")
            traci.close()
            return

    last_phase = -1

    # Current green-cycle control variables
    active_green_phase = None
    green_start_time = None
    next_adjust_check = None
    base_predicted_green = None
    final_applied_green = None
    total_inc = 0
    total_dec = 0

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        sim_time = traci.simulation.getTime()

        if sim_time >= MAX_SIM_TIME:
            print(f"Reached MAX_SIM_TIME = {MAX_SIM_TIME}. Stopping.")
            break

        current_phase = traci.trafficlight.getPhase(TLS_ID)

        # -------------------- NEW MAIN GREEN PHASE --------------------
        if current_phase != last_phase and current_phase in [0, 3]:
            cars_n, cars_s, cars_e, cars_w = get_counts()
            wait_n, wait_s, wait_e, wait_w = get_waits()
            ped_flag = is_pedestrian_waiting()
            phase_flag = get_phase_flag_for_model(current_phase)
            hour = datetime.now().hour

            base_predicted_green = predict_green_time(
                cars_n, cars_s, cars_e, cars_w,
                wait_n, wait_s, wait_e, wait_w,
                phase_flag, ped_flag, hour
            )

            # extra runtime clamp layer, matching your controller style
            base_predicted_green = max(MIN_GREEN, min(base_predicted_green, MAX_GREEN))
            final_applied_green = float(base_predicted_green)

            total_inc = 0
            total_dec = 0
            active_green_phase = current_phase
            green_start_time = sim_time
            next_adjust_check = sim_time + CHECK_INTERVAL

            print_decision_block(
                sim_time,
                current_phase,
                cars_n, cars_s, cars_e, cars_w,
                wait_n, wait_s, wait_e, wait_w,
                ped_flag,
                base_predicted_green
            )

            # force the active green phase and apply the base duration
            traci.trafficlight.setPhase(TLS_ID, current_phase)
            traci.trafficlight.setPhaseDuration(TLS_ID, int(round(final_applied_green)))

        # -------------------- DURING GREEN: APPLY ADJUSTMENTS --------------------
        if active_green_phase in [0, 3] and current_phase == active_green_phase:
            if next_adjust_check is not None and sim_time >= next_adjust_check:
                cars_n, cars_s, cars_e, cars_w = get_counts()
                active_load, opposing_load = get_active_and_opposing_load(
                    active_green_phase, cars_n, cars_s, cars_e, cars_w
                )

                remaining = traci.trafficlight.getNextSwitch(TLS_ID) - sim_time
                phase_name = get_phase_name(active_green_phase)

                if active_load > opposing_load + 2 and total_inc <= MAX_TOTAL_INC:
                    final_applied_green += EXTENSION_STEP
                    final_applied_green = min(final_applied_green, MAX_GREEN)

                    new_remaining = max(1, int(round(remaining + EXTENSION_STEP)))
                    traci.trafficlight.setPhaseDuration(TLS_ID, new_remaining)

                    total_inc += EXTENSION_STEP
                    print_adjustment(
                        sim_time, phase_name, active_load, opposing_load, remaining,
                        total_inc, total_dec,
                        f"extended by {EXTENSION_STEP}s"
                    )

                elif opposing_load > active_load + 2 and total_dec <= MAX_TOTAL_DEC:
                    final_applied_green -= EXTENSION_STEP
                    final_applied_green = max(final_applied_green, MIN_GREEN)

                    new_remaining = max(1, int(round(remaining - EXTENSION_STEP)))
                    traci.trafficlight.setPhaseDuration(TLS_ID, new_remaining)

                    total_dec += EXTENSION_STEP
                    print_adjustment(
                        sim_time, phase_name, active_load, opposing_load, remaining,
                        total_inc, total_dec,
                        f"shortened by {EXTENSION_STEP}s"
                    )

                else:
                    print_adjustment(
                        sim_time, phase_name, active_load, opposing_load, remaining,
                        total_inc, total_dec,
                        "no change"
                    )

                next_adjust_check += CHECK_INTERVAL

        # -------------------- GREEN ENDED: LOG FINAL RESULT --------------------
        if last_phase in [0, 3] and current_phase != last_phase:
            if active_green_phase == last_phase and base_predicted_green is not None:
                cars_n, cars_s, cars_e, cars_w = get_counts()
                wait_n, wait_s, wait_e, wait_w = get_waits()
                ped_flag = is_pedestrian_waiting()
                phase_flag = get_phase_flag_for_model(last_phase)

                append_log(
                    CSV_LOG,
                    sim_time,
                    last_phase,
                    phase_flag,
                    cars_n, cars_s, cars_e, cars_w,
                    wait_n, wait_s, wait_e, wait_w,
                    ped_flag,
                    int(round(base_predicted_green)),
                    int(round(final_applied_green)),
                    total_inc,
                    total_dec
                )

                print(
                    f"[GREEN FINISHED] phase={get_phase_name(last_phase)} | "
                    f"base={int(round(base_predicted_green))}s | "
                    f"final={int(round(final_applied_green))}s | "
                    f"+{total_inc}/-{total_dec}"
                )

                active_green_phase = None
                green_start_time = None
                next_adjust_check = None
                base_predicted_green = None
                final_applied_green = None
                total_inc = 0
                total_dec = 0

        last_phase = current_phase

    traci.close()
    print(f"\nDone. Log saved to: {CSV_LOG}")

if __name__ == "__main__":
    run_live_model_with_adjustment()