import os
import sys
import csv
from pathlib import Path

# -------------------- SUMO SETUP --------------------
os.environ["SUMO_HOME"] = r"C:\Program Files (x86)\Eclipse\Sumo"

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

import traci
import sumolib

from decision_model import predict_green_time

# -------------------- USER SETTINGS --------------------
USE_GUI = True

PRINT_DECISIONS = True
PRINT_FINAL_GREEN = True
PRINT_ADJUSTMENTS = False

CONFIG_FILE = "config_dundas.sumocfg"
TLS_ID = "clusterJ14_J16_J17"

# "all"      -> normal fixed, normal ai, pm fixed, pm ai
# "normal"   -> normal fixed, normal ai
# "pm_peak"  -> pm fixed, pm ai
RUN_EXPERIMENT = "pm_peak"

INCLUDE_PEDESTRIANS = True

# -------------------- INSERTION TEST MODE --------------------
# "baseline"
# "last_desired"
# "last_desired_halfstep"
# "last_desired_eager"
# "last_desired_eager_halfstep"
INSERTION_METHOD = "last_desired"

NORMAL_ROUTE_FILE = "simTraffic/dundas_church_normal.rou.xml"
PM_PEAK_ROUTE_FILE = "simTraffic/dundas_church_pm_peak.rou.xml"

NORMAL_ROUTE_FILE_INSERT = "simTraffic/dundas_church_normal_insert.rou.xml"
PM_PEAK_ROUTE_FILE_INSERT = "simTraffic/dundas_church_pm_peak_insert.rou.xml"

PEDESTRIAN_ROUTE_FILE = "simTraffic/dundas_church_pedestrian.rou.xml"

MAX_SIM_TIME = 3600
SEED = 42

# -------------------- EDGE MAPPING --------------------
N_EDGE = "E9"
S_EDGE = "-E8"
E_EDGE = "-E7"
W_EDGE = "E7"
APPROACH_EDGES = [N_EDGE, S_EDGE, E_EDGE, W_EDGE]

# -------------------- PHASE MAPPING --------------------
EW_GREEN_PHASE = 0
EW_CLEAR_PHASE = 1
EW_YELLOW_PHASE = 2
NS_GREEN_PHASE = 3
NS_CLEAR_PHASE = 4
NS_YELLOW_PHASE = 5
MAIN_GREEN_PHASES = [EW_GREEN_PHASE, NS_GREEN_PHASE]

# -------------------- FIXED DURATIONS --------------------
FIXED_PHASE_DURATIONS = {
    0: 19,  # EW green
    1: 6,   # EW clear / all-red
    2: 3,   # EW yellow
    3: 57,  # NS green
    4: 6,   # NS clear / all-red
    5: 3,   # NS yellow
}

# -------------------- AI LIMITS --------------------
MIN_GREEN = 10
MAX_GREEN = 40

# -------------------- HYBRID BACKLOG CONTROL --------------------
USE_HYBRID_BACKLOG = True

# Backlog only starts affecting the model when congestion is real
PENDING_TRIGGER = 8
QUEUE_TRIGGER = 10
WAIT_TRIGGER = 80.0

# Scale backlog instead of adding it 1:1
BACKLOG_COUNT_WEIGHT = 0.35
BACKLOG_WAIT_WEIGHT = 0.25

# Cap average pending wait contribution before blending
BACKLOG_WAIT_CAP = 60.0

# Dynamic adjustment behavior
NORMAL_EXT_STEP = 1
CONGESTED_EXT_STEP = 2

NORMAL_MAX_TOTAL_INC = 6
NORMAL_MAX_TOTAL_DEC = 6
CONGESTED_MAX_TOTAL_INC = 12
CONGESTED_MAX_TOTAL_DEC = 12

# Do not shorten below this amount from the base model green
MAX_SHORTEN_FROM_BASE = 4

CHECK_INTERVAL = 2

PROFILE_HOUR = {
    "normal": 13,
    "pm_peak": 17,
}

# -------------------- OUTPUT PATHS --------------------
BASE_DIR = Path(__file__).resolve().parent

GRAPHS_DIR = BASE_DIR / "Graphs"
GRAPHS_DIR.mkdir(exist_ok=True)

SIM_RESULTS_DIR = BASE_DIR / "sim_results"
SIM_RESULTS_DIR.mkdir(exist_ok=True)

DECISION_LOG_CSV = GRAPHS_DIR / "dundas_decision_log.csv"
STEP_LOG_CSV = GRAPHS_DIR / "dundas_step_metrics.csv"
SUMMARY_LOG_CSV = GRAPHS_DIR / "dundas_summary_metrics.csv"


# -------------------- HELPERS --------------------
def safe_halting(edge_id):
    return traci.edge.getLastStepHaltingNumber(edge_id)


def safe_wait(edge_id):
    return traci.edge.getWaitingTime(edge_id)


def get_counts():
    return (
        safe_halting(N_EDGE),
        safe_halting(S_EDGE),
        safe_halting(E_EDGE),
        safe_halting(W_EDGE),
    )


def get_waits():
    return (
        safe_wait(N_EDGE),
        safe_wait(S_EDGE),
        safe_wait(E_EDGE),
        safe_wait(W_EDGE),
    )


def get_phase_name(phase):
    names = {
        0: "EW_GREEN",
        1: "EW_CLEAR",
        2: "EW_YELLOW",
        3: "NS_GREEN",
        4: "NS_CLEAR",
        5: "NS_YELLOW",
    }
    return names.get(phase, f"OTHER({phase})")


def get_phase_flag_for_model(current_phase):
    # decision_model.py convention:
    # 0 = NS active
    # 1 = EW active
    if current_phase == EW_GREEN_PHASE:
        return 1
    if current_phase == NS_GREEN_PHASE:
        return 0
    raise ValueError(f"Unexpected phase for model decision: {current_phase}")


def is_pedestrian_waiting():
    try:
        for p_id in traci.person.getIDList():
            road_id = traci.person.getRoadID(p_id)

            if road_id in APPROACH_EDGES:
                return 1

            if road_id.startswith(f":{TLS_ID}_c") or road_id.startswith(f":{TLS_ID}_w"):
                return 1
    except Exception:
        pass
    return 0


def get_pending_vehicle_ids():
    try:
        pending = traci.simulation.getPendingVehicles()
        return list(pending)
    except Exception:
        return []


def get_pending_backlog_by_approach(sim_time, pending_first_seen):
    pending_ids = get_pending_vehicle_ids()
    pending_set = set(pending_ids)

    for vid in pending_ids:
        if vid not in pending_first_seen:
            pending_first_seen[vid] = sim_time

    stale_ids = [vid for vid in pending_first_seen if vid not in pending_set]
    for vid in stale_ids:
        del pending_first_seen[vid]

    backlog_counts = {"N": 0, "S": 0, "E": 0, "W": 0}
    backlog_wait_sums = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}

    for vid in pending_ids:
        pending_wait = max(0.0, sim_time - pending_first_seen.get(vid, sim_time))

        if vid.startswith("N_"):
            backlog_counts["N"] += 1
            backlog_wait_sums["N"] += pending_wait
        elif vid.startswith("S_"):
            backlog_counts["S"] += 1
            backlog_wait_sums["S"] += pending_wait
        elif vid.startswith("E_"):
            backlog_counts["E"] += 1
            backlog_wait_sums["E"] += pending_wait
        elif vid.startswith("W_"):
            backlog_counts["W"] += 1
            backlog_wait_sums["W"] += pending_wait

    backlog_wait_avg = {}
    for d in ["N", "S", "E", "W"]:
        if backlog_counts[d] > 0:
            backlog_wait_avg[d] = backlog_wait_sums[d] / backlog_counts[d]
        else:
            backlog_wait_avg[d] = 0.0

    return pending_ids, backlog_counts, backlog_wait_avg


def is_congested_state(cars_n, cars_s, cars_e, cars_w, wait_n, wait_s, wait_e, wait_w, pending_to_insert):
    total_queue = cars_n + cars_s + cars_e + cars_w
    total_wait = wait_n + wait_s + wait_e + wait_w

    return (
        pending_to_insert >= PENDING_TRIGGER
        or total_queue >= QUEUE_TRIGGER
        or total_wait >= WAIT_TRIGGER
    )


def get_effective_counts_scaled(cars_n, cars_s, cars_e, cars_w, backlog_counts, congested):
    if not USE_HYBRID_BACKLOG or not congested:
        return float(cars_n), float(cars_s), float(cars_e), float(cars_w)

    eff_n = cars_n + BACKLOG_COUNT_WEIGHT * backlog_counts["N"]
    eff_s = cars_s + BACKLOG_COUNT_WEIGHT * backlog_counts["S"]
    eff_e = cars_e + BACKLOG_COUNT_WEIGHT * backlog_counts["E"]
    eff_w = cars_w + BACKLOG_COUNT_WEIGHT * backlog_counts["W"]
    return eff_n, eff_s, eff_e, eff_w


def get_effective_waits_scaled(wait_n, wait_s, wait_e, wait_w, backlog_wait_avg, congested):
    if not USE_HYBRID_BACKLOG or not congested:
        return float(wait_n), float(wait_s), float(wait_e), float(wait_w)

    add_n = min(backlog_wait_avg["N"], BACKLOG_WAIT_CAP) * BACKLOG_WAIT_WEIGHT
    add_s = min(backlog_wait_avg["S"], BACKLOG_WAIT_CAP) * BACKLOG_WAIT_WEIGHT
    add_e = min(backlog_wait_avg["E"], BACKLOG_WAIT_CAP) * BACKLOG_WAIT_WEIGHT
    add_w = min(backlog_wait_avg["W"], BACKLOG_WAIT_CAP) * BACKLOG_WAIT_WEIGHT

    eff_wait_n = wait_n + add_n
    eff_wait_s = wait_s + add_s
    eff_wait_e = wait_e + add_e
    eff_wait_w = wait_w + add_w
    return eff_wait_n, eff_wait_s, eff_wait_e, eff_wait_w


def get_adjustment_params(congested):
    if congested:
        return CONGESTED_EXT_STEP, CONGESTED_MAX_TOTAL_INC, CONGESTED_MAX_TOTAL_DEC
    return NORMAL_EXT_STEP, NORMAL_MAX_TOTAL_INC, NORMAL_MAX_TOTAL_DEC


def route_file_for_profile(profile):
    if INSERTION_METHOD == "baseline":
        if profile == "normal":
            return NORMAL_ROUTE_FILE
        if profile == "pm_peak":
            return PM_PEAK_ROUTE_FILE
    else:
        if profile == "normal":
            return NORMAL_ROUTE_FILE_INSERT
        if profile == "pm_peak":
            return PM_PEAK_ROUTE_FILE_INSERT

    raise ValueError("profile must be 'normal' or 'pm_peak'")


def build_route_file_string(profile):
    files = [route_file_for_profile(profile)]
    if INCLUDE_PEDESTRIANS:
        files.append(PEDESTRIAN_ROUTE_FILE)
    return ",".join(files)


def get_active_and_opposing_load(current_phase, cars_n, cars_s, cars_e, cars_w):
    if current_phase == NS_GREEN_PHASE:
        active = cars_n + cars_s
        opposing = cars_e + cars_w
    elif current_phase == EW_GREEN_PHASE:
        active = cars_e + cars_w
        opposing = cars_n + cars_s
    else:
        active = 0.0
        opposing = 0.0
    return active, opposing


# -------------------- CSV SETUP --------------------
def prepare_csvs():
    with open(DECISION_LOG_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_name",
            "profile",
            "controller_mode",
            "green_phase_name",
            "green_phase_id",
            "phase_flag_model",
            "green_start_time",
            "green_end_time",
            "congested",
            "obs_cars_N", "obs_cars_S", "obs_cars_E", "obs_cars_W",
            "obs_wait_N", "obs_wait_S", "obs_wait_E", "obs_wait_W",
            "pending_N", "pending_S", "pending_E", "pending_W",
            "pending_wait_avg_N", "pending_wait_avg_S", "pending_wait_avg_E", "pending_wait_avg_W",
            "ctrl_cars_N", "ctrl_cars_S", "ctrl_cars_E", "ctrl_cars_W",
            "ctrl_wait_N", "ctrl_wait_S", "ctrl_wait_E", "ctrl_wait_W",
            "ped_flag",
            "base_green",
            "final_green",
            "total_inc",
            "total_dec",
        ])

    with open(STEP_LOG_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_name",
            "profile",
            "controller_mode",
            "sim_time",
            "phase_name",
            "cars_N", "cars_S", "cars_E", "cars_W",
            "wait_N", "wait_S", "wait_E", "wait_W",
            "pending_N", "pending_S", "pending_E", "pending_W",
            "pending_wait_avg_N", "pending_wait_avg_S", "pending_wait_avg_E", "pending_wait_avg_W",
            "ped_flag",
            "departed_step",
            "arrived_step",
            "active_vehicles",
            "pending_to_insert",
            "total_queue",
            "total_wait",
        ])

    with open(SUMMARY_LOG_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_name",
            "profile",
            "controller_mode",
            "sim_time_end",
            "vehicles_departed",
            "vehicles_arrived",
            "completion_ratio",
            "throughput_veh_per_hour",
            "avg_travel_time_s",
            "avg_depart_delay_s",
            "max_depart_delay_s",
            "avg_total_queue",
            "max_total_queue",
            "avg_total_wait_s",
            "avg_active_vehicles",
            "peak_active_vehicles",
            "avg_pending_insert",
            "max_pending_insert",
        ])


# -------------------- CSV APPENDS --------------------
def append_decision_log(
    run_name,
    profile,
    controller_mode,
    green_phase,
    phase_flag,
    green_start_time,
    green_end_time,
    congested,
    obs_cars_n, obs_cars_s, obs_cars_e, obs_cars_w,
    obs_wait_n, obs_wait_s, obs_wait_e, obs_wait_w,
    backlog_counts,
    backlog_wait_avg,
    ctrl_cars_n, ctrl_cars_s, ctrl_cars_e, ctrl_cars_w,
    ctrl_wait_n, ctrl_wait_s, ctrl_wait_e, ctrl_wait_w,
    ped_flag,
    base_green,
    final_green,
    total_inc,
    total_dec,
):
    with open(DECISION_LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            run_name,
            profile,
            controller_mode,
            get_phase_name(green_phase),
            green_phase,
            phase_flag,
            f"{green_start_time:.1f}",
            f"{green_end_time:.1f}",
            int(congested),
            obs_cars_n, obs_cars_s, obs_cars_e, obs_cars_w,
            f"{obs_wait_n:.2f}", f"{obs_wait_s:.2f}", f"{obs_wait_e:.2f}", f"{obs_wait_w:.2f}",
            backlog_counts["N"], backlog_counts["S"], backlog_counts["E"], backlog_counts["W"],
            f"{backlog_wait_avg['N']:.2f}", f"{backlog_wait_avg['S']:.2f}", f"{backlog_wait_avg['E']:.2f}", f"{backlog_wait_avg['W']:.2f}",
            f"{ctrl_cars_n:.2f}", f"{ctrl_cars_s:.2f}", f"{ctrl_cars_e:.2f}", f"{ctrl_cars_w:.2f}",
            f"{ctrl_wait_n:.2f}", f"{ctrl_wait_s:.2f}", f"{ctrl_wait_e:.2f}", f"{ctrl_wait_w:.2f}",
            ped_flag,
            int(round(base_green)),
            int(round(final_green)),
            total_inc,
            total_dec,
        ])


def append_step_log(
    run_name,
    profile,
    controller_mode,
    sim_time,
    current_phase,
    cars_n, cars_s, cars_e, cars_w,
    wait_n, wait_s, wait_e, wait_w,
    backlog_counts,
    backlog_wait_avg,
    ped_flag,
    departed_step,
    arrived_step,
    active_vehicles,
    pending_to_insert,
):
    total_queue = cars_n + cars_s + cars_e + cars_w
    total_wait = wait_n + wait_s + wait_e + wait_w

    with open(STEP_LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            run_name,
            profile,
            controller_mode,
            f"{sim_time:.1f}",
            get_phase_name(current_phase),
            cars_n, cars_s, cars_e, cars_w,
            f"{wait_n:.2f}", f"{wait_s:.2f}", f"{wait_e:.2f}", f"{wait_w:.2f}",
            backlog_counts["N"], backlog_counts["S"], backlog_counts["E"], backlog_counts["W"],
            f"{backlog_wait_avg['N']:.2f}", f"{backlog_wait_avg['S']:.2f}", f"{backlog_wait_avg['E']:.2f}", f"{backlog_wait_avg['W']:.2f}",
            ped_flag,
            departed_step,
            arrived_step,
            active_vehicles,
            pending_to_insert,
            total_queue,
            f"{total_wait:.2f}",
        ])


def append_summary(summary):
    with open(SUMMARY_LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            summary["run_name"],
            summary["profile"],
            summary["controller_mode"],
            f"{summary['sim_time_end']:.1f}",
            summary["vehicles_departed"],
            summary["vehicles_arrived"],
            f"{summary['completion_ratio']:.4f}",
            f"{summary['throughput_veh_per_hour']:.3f}",
            f"{summary['avg_travel_time_s']:.3f}",
            f"{summary['avg_depart_delay_s']:.3f}",
            f"{summary['max_depart_delay_s']:.3f}",
            f"{summary['avg_total_queue']:.3f}",
            summary["max_total_queue"],
            f"{summary['avg_total_wait_s']:.3f}",
            f"{summary['avg_active_vehicles']:.3f}",
            summary["peak_active_vehicles"],
            f"{summary['avg_pending_insert']:.3f}",
            summary["max_pending_insert"],
        ])


# -------------------- PRINT HELPERS --------------------
def print_decision_block(
    run_name,
    profile,
    controller_mode,
    sim_time,
    current_phase,
    congested,
    obs_cars_n, obs_cars_s, obs_cars_e, obs_cars_w,
    obs_wait_n, obs_wait_s, obs_wait_e, obs_wait_w,
    backlog_counts,
    backlog_wait_avg,
    ctrl_cars_n, ctrl_cars_s, ctrl_cars_e, ctrl_cars_w,
    ctrl_wait_n, ctrl_wait_s, ctrl_wait_e, ctrl_wait_w,
    ped_flag,
    base_green,
):
    if not PRINT_DECISIONS:
        return

    print("\n" + "=" * 95)
    print(f"[{run_name}] NEW MODEL DECISION at sim_time = {sim_time:.1f}s")
    print(f"Profile              : {profile}")
    print(f"Controller Mode      : {controller_mode}")
    print(f"Active Phase         : {get_phase_name(current_phase)} ({current_phase})")
    print(f"Congested State      : {int(congested)}")
    print(f"Observed Cars        : N={obs_cars_n}, S={obs_cars_s}, E={obs_cars_e}, W={obs_cars_w}")
    print(f"Observed Waits       : N={obs_wait_n:.1f}, S={obs_wait_s:.1f}, E={obs_wait_e:.1f}, W={obs_wait_w:.1f}")
    print(f"Pending Backlog      : N={backlog_counts['N']}, S={backlog_counts['S']}, E={backlog_counts['E']}, W={backlog_counts['W']}")
    print(f"Pending Avg Wait     : N={backlog_wait_avg['N']:.1f}, S={backlog_wait_avg['S']:.1f}, E={backlog_wait_avg['E']:.1f}, W={backlog_wait_avg['W']:.1f}")
    print(f"Control Cars         : N={ctrl_cars_n:.2f}, S={ctrl_cars_s:.2f}, E={ctrl_cars_e:.2f}, W={ctrl_cars_w:.2f}")
    print(f"Control Waits        : N={ctrl_wait_n:.2f}, S={ctrl_wait_s:.2f}, E={ctrl_wait_e:.2f}, W={ctrl_wait_w:.2f}")
    print(f"Pedestrian Flag      : {ped_flag}")
    print(f"Base Model Green     : {int(round(base_green))} seconds")
    print("=" * 95)


def print_final_green_result(
    run_name,
    profile,
    controller_mode,
    green_phase,
    green_start_time,
    green_end_time,
    base_green,
    final_green,
    total_inc,
    total_dec,
):
    if not PRINT_FINAL_GREEN:
        return

    print("-" * 95)
    print(f"[{run_name}] FINAL GREEN RESULT")
    print(f"Profile              : {profile}")
    print(f"Controller Mode      : {controller_mode}")
    print(f"Green Phase          : {get_phase_name(green_phase)} ({green_phase})")
    print(f"Green Start Time     : {green_start_time:.1f}s")
    print(f"Green End Time       : {green_end_time:.1f}s")
    print(f"Base Model Green     : {int(round(base_green))} seconds")
    print(f"Final Applied Green  : {int(round(final_green))} seconds")
    print(f"Total Increase       : +{total_inc} seconds")
    print(f"Total Decrease       : -{total_dec} seconds")
    print("-" * 95)


def print_adjustment(sim_time, phase_name, active_load, opposing_load, remaining, total_inc, total_dec, note):
    if not PRINT_ADJUSTMENTS:
        return

    print(
        f"[ADJUST] t={sim_time:.1f}s | phase={phase_name} | "
        f"active={active_load:.2f} | opposing={opposing_load:.2f} | "
        f"remaining={remaining:.1f}s | +{total_inc}/-{total_dec} | {note}"
    )


def print_summary(summary):
    print("\n" + "-" * 95)
    print(f"Run Name             : {summary['run_name']}")
    print(f"Profile              : {summary['profile']}")
    print(f"Controller Mode      : {summary['controller_mode']}")
    print(f"Vehicles Departed    : {summary['vehicles_departed']}")
    print(f"Vehicles Arrived     : {summary['vehicles_arrived']}")
    print(f"Completion Ratio     : {summary['completion_ratio']:.4f}")
    print(f"Throughput (veh/h)   : {summary['throughput_veh_per_hour']:.3f}")
    print(f"Avg Travel Time (s)  : {summary['avg_travel_time_s']:.3f}")
    print(f"Avg Depart Delay (s) : {summary['avg_depart_delay_s']:.3f}")
    print(f"Max Depart Delay (s) : {summary['max_depart_delay_s']:.3f}")
    print(f"Avg Total Queue      : {summary['avg_total_queue']:.3f}")
    print(f"Max Total Queue      : {summary['max_total_queue']}")
    print(f"Avg Total Wait (s)   : {summary['avg_total_wait_s']:.3f}")
    print(f"Avg Active Vehicles  : {summary['avg_active_vehicles']:.3f}")
    print(f"Peak Active Vehicles : {summary['peak_active_vehicles']}")
    print(f"Avg Pending Insert   : {summary['avg_pending_insert']:.3f}")
    print(f"Max Pending Insert   : {summary['max_pending_insert']}")
    print("-" * 95)


def percent_improvement(fixed_value, ai_value, higher_is_better):
    if fixed_value == 0:
        return None
    if higher_is_better:
        return ((ai_value - fixed_value) / fixed_value) * 100.0
    return ((fixed_value - ai_value) / fixed_value) * 100.0


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def print_comparison(profile, fixed_summary, ai_summary):
    arrived_pct = percent_improvement(
        fixed_summary["vehicles_arrived"],
        ai_summary["vehicles_arrived"],
        higher_is_better=True,
    )

    throughput_pct = percent_improvement(
        fixed_summary["throughput_veh_per_hour"],
        ai_summary["throughput_veh_per_hour"],
        higher_is_better=True,
    )

    travel_time_pct = percent_improvement(
        fixed_summary["avg_travel_time_s"],
        ai_summary["avg_travel_time_s"],
        higher_is_better=False,
    )

    depart_delay_pct = percent_improvement(
        fixed_summary["avg_depart_delay_s"],
        ai_summary["avg_depart_delay_s"],
        higher_is_better=False,
    )

    queue_pct = percent_improvement(
        fixed_summary["avg_total_queue"],
        ai_summary["avg_total_queue"],
        higher_is_better=False,
    )

    max_queue_pct = percent_improvement(
        fixed_summary["max_total_queue"],
        ai_summary["max_total_queue"],
        higher_is_better=False,
    )

    wait_pct = percent_improvement(
        fixed_summary["avg_total_wait_s"],
        ai_summary["avg_total_wait_s"],
        higher_is_better=False,
    )

    pending_pct = percent_improvement(
        fixed_summary["avg_pending_insert"],
        ai_summary["avg_pending_insert"],
        higher_is_better=False,
    )

    completion_pct = percent_improvement(
        fixed_summary["completion_ratio"],
        ai_summary["completion_ratio"],
        higher_is_better=True,
    )

    print("\n" + "#" * 95)
    print(f"COMPARISON FOR PROFILE = {profile} (AI vs FIXED)")
    print(f"Arrivals                : {ai_summary['vehicles_arrived']} vs {fixed_summary['vehicles_arrived']}   | Improvement = {format_percent(arrived_pct)}")
    print(f"Throughput (veh/h)      : {ai_summary['throughput_veh_per_hour']:.3f} vs {fixed_summary['throughput_veh_per_hour']:.3f}   | Improvement = {format_percent(throughput_pct)}")
    print(f"Avg travel time (s)     : {ai_summary['avg_travel_time_s']:.3f} vs {fixed_summary['avg_travel_time_s']:.3f}   | Improvement = {format_percent(travel_time_pct)}")
    print(f"Avg depart delay (s)    : {ai_summary['avg_depart_delay_s']:.3f} vs {fixed_summary['avg_depart_delay_s']:.3f}   | Improvement = {format_percent(depart_delay_pct)}")
    print(f"Avg total queue         : {ai_summary['avg_total_queue']:.3f} vs {fixed_summary['avg_total_queue']:.3f}   | Improvement = {format_percent(queue_pct)}")
    print(f"Max total queue         : {ai_summary['max_total_queue']} vs {fixed_summary['max_total_queue']}   | Improvement = {format_percent(max_queue_pct)}")
    print(f"Avg total wait (s)      : {ai_summary['avg_total_wait_s']:.3f} vs {fixed_summary['avg_total_wait_s']:.3f}   | Improvement = {format_percent(wait_pct)}")
    print(f"Avg pending insert      : {ai_summary['avg_pending_insert']:.3f} vs {fixed_summary['avg_pending_insert']:.3f}   | Improvement = {format_percent(pending_pct)}")
    print(f"Completion ratio        : {ai_summary['completion_ratio']:.4f} vs {fixed_summary['completion_ratio']:.4f}   | Improvement = {format_percent(completion_pct)}")
    print("#" * 95)


# -------------------- SUMO COMMAND --------------------
def build_sumo_cmd(profile, controller_mode):
    run_name = f"{profile}_{controller_mode}"
    route_files = build_route_file_string(profile)
    sumo_binary = sumolib.checkBinary("sumo-gui" if USE_GUI else "sumo")

    summary_xml = SIM_RESULTS_DIR / f"{run_name}_summary.xml"
    tripinfo_xml = SIM_RESULTS_DIR / f"{run_name}_tripinfo.xml"

    cmd = [
        sumo_binary,
        "-c", CONFIG_FILE,
        "--route-files", route_files,
        "--seed", str(SEED),
        "--max-depart-delay", "-1",
        "--duration-log.disable", "true",
        "--summary-output", str(summary_xml),
        "--tripinfo-output", str(tripinfo_xml),
        "--tripinfo-output.write-unfinished", "true",
    ]

    if INSERTION_METHOD in {"last_desired_eager", "last_desired_eager_halfstep"}:
        cmd.append("--eager-insert")

    if INSERTION_METHOD in {"last_desired_halfstep", "last_desired_eager_halfstep"}:
        cmd.extend(["--step-length", "0.5"])

    return cmd, route_files


# -------------------- MAIN RUN --------------------
def run_scenario(profile, controller_mode):
    run_name = f"{profile}_{controller_mode}"
    cmd, route_files = build_sumo_cmd(profile, controller_mode)

    traci.start(cmd)

    print(f"\nStarted SUMO run: {run_name}")
    print(f"Route files      : {route_files}")
    print(f"TLS ID           : {TLS_ID}")
    print(f"Insertion Method : {INSERTION_METHOD}")

    last_phase = -1
    vehicle_depart_times = {}
    pending_first_seen = {}

    vehicles_departed = 0
    vehicles_arrived = 0

    total_queue_sum = 0.0
    total_wait_sum = 0.0
    active_vehicle_sum = 0.0

    max_total_queue = 0
    peak_active_vehicles = 0

    pending_insert_sum = 0.0
    max_pending_insert = 0
    pending_samples = 0

    travel_times = []
    depart_delays = []

    sim_time = 0.0
    step_count = 0

    active_green_phase = None
    green_start_time = None
    green_start_state = None
    base_predicted_green = None
    final_applied_green = None
    total_inc = 0
    total_dec = 0
    next_adjust_check = None

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            sim_time = traci.simulation.getTime()

            if sim_time > MAX_SIM_TIME:
                print(f"Reached MAX_SIM_TIME = {MAX_SIM_TIME}. Stopping {run_name}.")
                break

            current_phase = traci.trafficlight.getPhase(TLS_ID)

            cars_n, cars_s, cars_e, cars_w = get_counts()
            wait_n, wait_s, wait_e, wait_w = get_waits()
            ped_flag = is_pedestrian_waiting()

            pending_ids, backlog_counts, backlog_wait_avg = get_pending_backlog_by_approach(
                sim_time, pending_first_seen
            )
            pending_to_insert = len(pending_ids)

            congested = is_congested_state(
                cars_n, cars_s, cars_e, cars_w,
                wait_n, wait_s, wait_e, wait_w,
                pending_to_insert
            )

            ctrl_cars_n, ctrl_cars_s, ctrl_cars_e, ctrl_cars_w = get_effective_counts_scaled(
                cars_n, cars_s, cars_e, cars_w, backlog_counts, congested
            )
            ctrl_wait_n, ctrl_wait_s, ctrl_wait_e, ctrl_wait_w = get_effective_waits_scaled(
                wait_n, wait_s, wait_e, wait_w, backlog_wait_avg, congested
            )

            departed_ids = traci.simulation.getDepartedIDList()
            arrived_ids = traci.simulation.getArrivedIDList()

            vehicles_departed += len(departed_ids)
            vehicles_arrived += len(arrived_ids)

            for veh_id in departed_ids:
                vehicle_depart_times[veh_id] = sim_time
                try:
                    depart_delays.append(float(traci.vehicle.getDepartDelay(veh_id)))
                except Exception:
                    pass

            for veh_id in arrived_ids:
                if veh_id in vehicle_depart_times:
                    travel_times.append(sim_time - vehicle_depart_times[veh_id])
                    del vehicle_depart_times[veh_id]

            active_vehicles = len(traci.vehicle.getIDList())
            total_queue = cars_n + cars_s + cars_e + cars_w
            total_wait = wait_n + wait_s + wait_e + wait_w

            pending_insert_sum += pending_to_insert
            pending_samples += 1
            max_pending_insert = max(max_pending_insert, pending_to_insert)

            total_queue_sum += total_queue
            total_wait_sum += total_wait
            active_vehicle_sum += active_vehicles

            max_total_queue = max(max_total_queue, total_queue)
            peak_active_vehicles = max(peak_active_vehicles, active_vehicles)

            step_count += 1

            append_step_log(
                run_name,
                profile,
                controller_mode,
                sim_time,
                current_phase,
                cars_n, cars_s, cars_e, cars_w,
                wait_n, wait_s, wait_e, wait_w,
                backlog_counts,
                backlog_wait_avg,
                ped_flag,
                len(departed_ids),
                len(arrived_ids),
                active_vehicles,
                pending_to_insert,
            )

            if active_green_phase in MAIN_GREEN_PHASES and current_phase != active_green_phase and green_start_state is not None:
                print_final_green_result(
                    run_name=run_name,
                    profile=profile,
                    controller_mode=controller_mode,
                    green_phase=active_green_phase,
                    green_start_time=green_start_time,
                    green_end_time=sim_time,
                    base_green=base_predicted_green,
                    final_green=final_applied_green,
                    total_inc=total_inc,
                    total_dec=total_dec,
                )

                append_decision_log(
                    run_name=run_name,
                    profile=profile,
                    controller_mode=controller_mode,
                    green_phase=active_green_phase,
                    phase_flag=green_start_state["phase_flag"],
                    green_start_time=green_start_time,
                    green_end_time=sim_time,
                    congested=green_start_state["congested"],
                    obs_cars_n=green_start_state["obs_cars_n"],
                    obs_cars_s=green_start_state["obs_cars_s"],
                    obs_cars_e=green_start_state["obs_cars_e"],
                    obs_cars_w=green_start_state["obs_cars_w"],
                    obs_wait_n=green_start_state["obs_wait_n"],
                    obs_wait_s=green_start_state["obs_wait_s"],
                    obs_wait_e=green_start_state["obs_wait_e"],
                    obs_wait_w=green_start_state["obs_wait_w"],
                    backlog_counts=green_start_state["backlog_counts"],
                    backlog_wait_avg=green_start_state["backlog_wait_avg"],
                    ctrl_cars_n=green_start_state["ctrl_cars_n"],
                    ctrl_cars_s=green_start_state["ctrl_cars_s"],
                    ctrl_cars_e=green_start_state["ctrl_cars_e"],
                    ctrl_cars_w=green_start_state["ctrl_cars_w"],
                    ctrl_wait_n=green_start_state["ctrl_wait_n"],
                    ctrl_wait_s=green_start_state["ctrl_wait_s"],
                    ctrl_wait_e=green_start_state["ctrl_wait_e"],
                    ctrl_wait_w=green_start_state["ctrl_wait_w"],
                    ped_flag=green_start_state["ped_flag"],
                    base_green=base_predicted_green,
                    final_green=final_applied_green,
                    total_inc=total_inc,
                    total_dec=total_dec,
                )

                active_green_phase = None
                green_start_time = None
                green_start_state = None
                base_predicted_green = None
                final_applied_green = None
                total_inc = 0
                total_dec = 0
                next_adjust_check = None

            if current_phase != last_phase:
                if current_phase in MAIN_GREEN_PHASES:
                    phase_flag = get_phase_flag_for_model(current_phase)

                    if controller_mode == "fixed":
                        base_green = FIXED_PHASE_DURATIONS[current_phase]
                    elif controller_mode == "ai":
                        base_green = predict_green_time(
                            ctrl_cars_n, ctrl_cars_s, ctrl_cars_e, ctrl_cars_w,
                            ctrl_wait_n, ctrl_wait_s, ctrl_wait_e, ctrl_wait_w,
                            phase_flag, ped_flag, PROFILE_HOUR[profile]
                        )
                        base_green = max(MIN_GREEN, min(float(base_green), MAX_GREEN))
                    else:
                        raise ValueError("controller_mode must be 'fixed' or 'ai'")

                    active_green_phase = current_phase
                    green_start_time = sim_time
                    green_start_state = {
                        "phase_flag": phase_flag,
                        "congested": congested,
                        "obs_cars_n": cars_n,
                        "obs_cars_s": cars_s,
                        "obs_cars_e": cars_e,
                        "obs_cars_w": cars_w,
                        "obs_wait_n": wait_n,
                        "obs_wait_s": wait_s,
                        "obs_wait_e": wait_e,
                        "obs_wait_w": wait_w,
                        "backlog_counts": dict(backlog_counts),
                        "backlog_wait_avg": dict(backlog_wait_avg),
                        "ctrl_cars_n": ctrl_cars_n,
                        "ctrl_cars_s": ctrl_cars_s,
                        "ctrl_cars_e": ctrl_cars_e,
                        "ctrl_cars_w": ctrl_cars_w,
                        "ctrl_wait_n": ctrl_wait_n,
                        "ctrl_wait_s": ctrl_wait_s,
                        "ctrl_wait_e": ctrl_wait_e,
                        "ctrl_wait_w": ctrl_wait_w,
                        "ped_flag": ped_flag,
                    }

                    base_predicted_green = float(base_green)
                    final_applied_green = float(base_green)
                    total_inc = 0
                    total_dec = 0
                    next_adjust_check = sim_time + CHECK_INTERVAL if controller_mode == "ai" else None

                    traci.trafficlight.setPhase(TLS_ID, current_phase)
                    traci.trafficlight.setPhaseDuration(TLS_ID, int(round(final_applied_green)))

                    print_decision_block(
                        run_name,
                        profile,
                        controller_mode,
                        sim_time,
                        current_phase,
                        congested,
                        cars_n, cars_s, cars_e, cars_w,
                        wait_n, wait_s, wait_e, wait_w,
                        backlog_counts,
                        backlog_wait_avg,
                        ctrl_cars_n, ctrl_cars_s, ctrl_cars_e, ctrl_cars_w,
                        ctrl_wait_n, ctrl_wait_s, ctrl_wait_e, ctrl_wait_w,
                        ped_flag,
                        base_predicted_green,
                    )

                else:
                    fixed_duration = FIXED_PHASE_DURATIONS.get(current_phase)
                    if fixed_duration is not None:
                        traci.trafficlight.setPhaseDuration(TLS_ID, int(round(fixed_duration)))

            if controller_mode == "ai" and active_green_phase in MAIN_GREEN_PHASES and current_phase == active_green_phase:
                if next_adjust_check is not None and sim_time >= next_adjust_check:
                    live_pending_ids, live_backlog_counts, live_backlog_wait_avg = get_pending_backlog_by_approach(
                        sim_time, pending_first_seen
                    )
                    live_pending_to_insert = len(live_pending_ids)

                    live_congested = is_congested_state(
                        cars_n, cars_s, cars_e, cars_w,
                        wait_n, wait_s, wait_e, wait_w,
                        live_pending_to_insert
                    )

                    adj_cars_n, adj_cars_s, adj_cars_e, adj_cars_w = get_effective_counts_scaled(
                        cars_n, cars_s, cars_e, cars_w, live_backlog_counts, live_congested
                    )

                    step_size, max_inc_limit, max_dec_limit = get_adjustment_params(live_congested)

                    active_load, opposing_load = get_active_and_opposing_load(
                        active_green_phase,
                        adj_cars_n, adj_cars_s, adj_cars_e, adj_cars_w
                    )

                    remaining = traci.trafficlight.getNextSwitch(TLS_ID) - sim_time
                    phase_name = get_phase_name(active_green_phase)

                    if active_load > opposing_load + 2 and total_inc < max_inc_limit:
                        proposed_final = min(final_applied_green + step_size, MAX_GREEN)
                        actual_delta = proposed_final - final_applied_green

                        if actual_delta > 0:
                            final_applied_green = proposed_final
                            new_remaining = max(1, int(round(remaining + actual_delta)))
                            traci.trafficlight.setPhaseDuration(TLS_ID, new_remaining)
                            total_inc += int(round(actual_delta))

                            print_adjustment(
                                sim_time, phase_name, active_load, opposing_load, remaining,
                                total_inc, total_dec, f"extended by {int(round(actual_delta))}s"
                            )

                    elif opposing_load > active_load + 2 and total_dec < max_dec_limit:
                        min_allowed_green = max(MIN_GREEN, base_predicted_green - MAX_SHORTEN_FROM_BASE)
                        proposed_final = max(final_applied_green - step_size, min_allowed_green)
                        actual_delta = final_applied_green - proposed_final

                        if actual_delta > 0:
                            final_applied_green = proposed_final
                            new_remaining = max(1, int(round(remaining - actual_delta)))
                            traci.trafficlight.setPhaseDuration(TLS_ID, new_remaining)
                            total_dec += int(round(actual_delta))

                            print_adjustment(
                                sim_time, phase_name, active_load, opposing_load, remaining,
                                total_inc, total_dec, f"shortened by {int(round(actual_delta))}s"
                            )
                    else:
                        print_adjustment(
                            sim_time, phase_name, active_load, opposing_load, remaining,
                            total_inc, total_dec, "no change"
                        )

                    next_adjust_check += CHECK_INTERVAL

            last_phase = current_phase

    finally:
        if active_green_phase in MAIN_GREEN_PHASES and green_start_state is not None:
            print_final_green_result(
                run_name=run_name,
                profile=profile,
                controller_mode=controller_mode,
                green_phase=active_green_phase,
                green_start_time=green_start_time,
                green_end_time=sim_time,
                base_green=base_predicted_green if base_predicted_green is not None else 0,
                final_green=final_applied_green if final_applied_green is not None else 0,
                total_inc=total_inc,
                total_dec=total_dec,
            )

            append_decision_log(
                run_name=run_name,
                profile=profile,
                controller_mode=controller_mode,
                green_phase=active_green_phase,
                phase_flag=green_start_state["phase_flag"],
                green_start_time=green_start_time,
                green_end_time=sim_time,
                congested=green_start_state["congested"],
                obs_cars_n=green_start_state["obs_cars_n"],
                obs_cars_s=green_start_state["obs_cars_s"],
                obs_cars_e=green_start_state["obs_cars_e"],
                obs_cars_w=green_start_state["obs_cars_w"],
                obs_wait_n=green_start_state["obs_wait_n"],
                obs_wait_s=green_start_state["obs_wait_s"],
                obs_wait_e=green_start_state["obs_wait_e"],
                obs_wait_w=green_start_state["obs_wait_w"],
                backlog_counts=green_start_state["backlog_counts"],
                backlog_wait_avg=green_start_state["backlog_wait_avg"],
                ctrl_cars_n=green_start_state["ctrl_cars_n"],
                ctrl_cars_s=green_start_state["ctrl_cars_s"],
                ctrl_cars_e=green_start_state["ctrl_cars_e"],
                ctrl_cars_w=green_start_state["ctrl_cars_w"],
                ctrl_wait_n=green_start_state["ctrl_wait_n"],
                ctrl_wait_s=green_start_state["ctrl_wait_s"],
                ctrl_wait_e=green_start_state["ctrl_wait_e"],
                ctrl_wait_w=green_start_state["ctrl_wait_w"],
                ped_flag=green_start_state["ped_flag"],
                base_green=base_predicted_green if base_predicted_green is not None else 0,
                final_green=final_applied_green if final_applied_green is not None else 0,
                total_inc=total_inc,
                total_dec=total_dec,
            )

        traci.close()
        print(f"Closed SUMO for run: {run_name}")

    avg_travel_time = sum(travel_times) / len(travel_times) if travel_times else 0.0
    avg_depart_delay = sum(depart_delays) / len(depart_delays) if depart_delays else 0.0
    max_depart_delay = max(depart_delays) if depart_delays else 0.0
    avg_total_queue = total_queue_sum / step_count if step_count else 0.0
    avg_total_wait = total_wait_sum / step_count if step_count else 0.0
    avg_active_vehicles = active_vehicle_sum / step_count if step_count else 0.0
    avg_pending_insert = pending_insert_sum / pending_samples if pending_samples else 0.0
    completion_ratio = vehicles_arrived / vehicles_departed if vehicles_departed else 0.0
    throughput_per_hour = vehicles_arrived * 3600.0 / MAX_SIM_TIME

    summary = {
        "run_name": run_name,
        "profile": profile,
        "controller_mode": controller_mode,
        "sim_time_end": sim_time,
        "vehicles_departed": vehicles_departed,
        "vehicles_arrived": vehicles_arrived,
        "completion_ratio": completion_ratio,
        "throughput_veh_per_hour": throughput_per_hour,
        "avg_travel_time_s": avg_travel_time,
        "avg_depart_delay_s": avg_depart_delay,
        "max_depart_delay_s": max_depart_delay,
        "avg_total_queue": avg_total_queue,
        "max_total_queue": max_total_queue,
        "avg_total_wait_s": avg_total_wait,
        "avg_active_vehicles": avg_active_vehicles,
        "peak_active_vehicles": peak_active_vehicles,
        "avg_pending_insert": avg_pending_insert,
        "max_pending_insert": max_pending_insert,
    }

    append_summary(summary)
    print_summary(summary)
    return summary


def run_profile_pair(profile):
    fixed_summary = run_scenario(profile, "fixed")
    ai_summary = run_scenario(profile, "ai")
    print_comparison(profile, fixed_summary, ai_summary)


def main():
    prepare_csvs()

    if RUN_EXPERIMENT == "normal":
        run_profile_pair("normal")
    elif RUN_EXPERIMENT == "pm_peak":
        run_profile_pair("pm_peak")
    elif RUN_EXPERIMENT == "all":
        run_profile_pair("normal")
        run_profile_pair("pm_peak")
    else:
        raise ValueError("RUN_EXPERIMENT must be 'normal', 'pm_peak', or 'all'")

print("\nDone.")
print("Main outputs:")
print(f"  CSV folder: {GRAPHS_DIR}")
print(f"  XML folder: {SIM_RESULTS_DIR}")


if __name__ == "__main__":
    main()