import os
import sys
import csv

# --- SETUP SUMO PATHS ---
os.environ['SUMO_HOME'] = r'C:\Program Files (x86)\Eclipse\Sumo'

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

import traci
import sumolib

# =========================
# CONFIGURATION
# =========================
TLS_ID = "clusterJ14_J16_J17"

# Edge mapping
N_EDGE = "E9"
S_EDGE = "-E8"
E_EDGE = "-E7"
W_EDGE = "E7"

ALL_APPROACH_EDGES = [N_EDGE, S_EDGE, E_EDGE, W_EDGE]

# Change before each run
SCENARIO_TYPE = "very_heavy"   # "light", "medium", "heavy", "rush", "very_heavy", "rush_heavy"
RUSH_FLAG = 0
CSV_PATH = "optimal_dataset.csv"

# Simulation controls
SKIP_EMPTY_ROWS = True
WARMUP_STEPS = 150
POST_APPLY_BUFFER = 5
MAX_SIM_TIME = 2500

# Candidate green times
NORMAL_TEST_RANGE = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
PED_TEST_RANGE = [20, 25, 30, 35, 40, 45, 50, 55, 60]

# 10s shortcuts
TEN_SHORTCUT_RELEASED_THRESHOLD = 0.75
TEN_SHORTCUT_CLEARED_THRESHOLD = 0.25

# Tiny queue shortcut
TINY_QUEUE_MAX_HALTED = 3
TINY_QUEUE_RELEASED_THRESHOLD = 0.33


# =========================
# BASIC HELPERS
# =========================
def safe_halting(edge_id):
    return traci.edge.getLastStepHaltingNumber(edge_id)


def safe_wait(edge_id):
    return traci.edge.getWaitingTime(edge_id)


def get_vehicle_ids_on_edge(edge_id):
    return set(traci.edge.getLastStepVehicleIDs(edge_id))


def get_vehicle_ids_on_edges(edge_ids):
    result = set()
    for edge_id in edge_ids:
        result.update(get_vehicle_ids_on_edge(edge_id))
    return result


def get_halted_vehicle_ids_on_edge(edge_id, speed_threshold=0.1):
    halted_ids = set()
    for vid in traci.edge.getLastStepVehicleIDs(edge_id):
        try:
            if traci.vehicle.getSpeed(vid) <= speed_threshold:
                halted_ids.add(vid)
        except:
            pass
    return halted_ids


def get_halted_vehicle_ids_on_edges(edge_ids, speed_threshold=0.1):
    result = set()
    for edge_id in edge_ids:
        result.update(get_halted_vehicle_ids_on_edge(edge_id, speed_threshold))
    return result


def get_separate_vehicle_counts():
    cars_n = safe_halting(N_EDGE)
    cars_s = safe_halting(S_EDGE)
    cars_e = safe_halting(E_EDGE)
    cars_w = safe_halting(W_EDGE)
    return cars_n, cars_s, cars_e, cars_w


def get_separate_wait_times():
    wait_n = safe_wait(N_EDGE)
    wait_s = safe_wait(S_EDGE)
    wait_e = safe_wait(E_EDGE)
    wait_w = safe_wait(W_EDGE)
    return wait_n, wait_s, wait_e, wait_w


def is_pedestrian_waiting():
    people_ids = traci.person.getIDList()
    for p_id in people_ids:
        if traci.person.getRoadID(p_id) in ALL_APPROACH_EDGES:
            return 1
    return 0


def get_active_and_opposing_edges(current_phase):
    # phase 0 = EW green
    # phase 3 = NS green
    if current_phase == 0:
        active_edges = [E_EDGE, W_EDGE]
        opposing_edges = [N_EDGE, S_EDGE]
    else:
        active_edges = [N_EDGE, S_EDGE]
        opposing_edges = [E_EDGE, W_EDGE]
    return active_edges, opposing_edges


def get_active_halted_queue_count(current_phase, cars_n, cars_s, cars_e, cars_w):
    if current_phase == 0:
        return cars_e + cars_w
    else:
        return cars_n + cars_s


def choose_test_range(current_phase, ped_flag, cars_n, cars_s, cars_e, cars_w):
    active_halted = get_active_halted_queue_count(current_phase, cars_n, cars_s, cars_e, cars_w)

    if ped_flag == 1:
        if active_halted <= 6:
            return [20, 25, 30]
        elif active_halted <= 12:
            return [20, 25, 30, 35, 40]
        elif active_halted <= 20:
            return [20, 25, 30, 35, 40, 45, 50]
        else:
            return [20, 25, 30, 35, 40, 45, 50, 55, 60]

    if active_halted <= 6:
        return [10]
    elif active_halted <= 8:
        return [10, 15]
    elif active_halted <= 12:
        return [10, 15, 20]
    elif active_halted <= 16:
        return [10, 15, 20, 25]
    elif active_halted <= 19:
        return [15, 20, 25, 30]
    elif active_halted <= 24:
        return [20, 25, 30, 35, 40, 45, 50]
    else:
        return [30, 35, 40, 45, 50, 55, 60]


def choose_clearance_margin(initial_halted_count):
    if initial_halted_count <= 4:
        return 0.05
    elif initial_halted_count <= 8:
        return 0.10
    elif initial_halted_count <= 12:
        return 0.15
    else:
        return 0.20


# =========================
# DEBUG PAIN SCORE
# =========================
def compute_pain_score_from_values(
    cars_n, cars_s, cars_e, cars_w,
    wait_n, wait_s, wait_e, wait_w
):
    queue_term = 3.0 * (
        (cars_n ** 2) +
        (cars_s ** 2) +
        (cars_e ** 2) +
        (cars_w ** 2)
    )

    wait_term = 0.03 * (
        wait_n + wait_s + wait_e + wait_w
    )

    return queue_term + wait_term


# =========================
# CANDIDATE EVALUATION
# =========================
def evaluate_candidate_duration(
    current_phase,
    test_duration,
    before_cars_n, before_cars_s, before_cars_e, before_cars_w,
    before_wait_n, before_wait_s, before_wait_e, before_wait_w
):
    active_edges, opposing_edges = get_active_and_opposing_edges(current_phase)

    before_active_halted_ids = get_halted_vehicle_ids_on_edges(active_edges)
    before_opp_halted_ids = get_halted_vehicle_ids_on_edges(opposing_edges)

    traci.trafficlight.setPhase(TLS_ID, current_phase)
    traci.trafficlight.setPhaseDuration(TLS_ID, test_duration)

    for _ in range(test_duration):
        traci.simulationStep()

    after_cars_n, after_cars_s, after_cars_e, after_cars_w = get_separate_vehicle_counts()
    after_wait_n, after_wait_s, after_wait_e, after_wait_w = get_separate_wait_times()

    after_active_ids = get_vehicle_ids_on_edges(active_edges)
    after_opposing_ids = get_vehicle_ids_on_edges(opposing_edges)
    after_all_vehicle_ids = set(traci.vehicle.getIDList())

    after_active_halted_ids = get_halted_vehicle_ids_on_edges(active_edges)
    after_opp_halted_ids = get_halted_vehicle_ids_on_edges(opposing_edges)

    if current_phase == 0:  # EW green
        active_queue_before = before_cars_e + before_cars_w
        active_queue_after = after_cars_e + after_cars_w

        active_wait_before = before_wait_e + before_wait_w
        active_wait_after = after_wait_e + after_wait_w

        opp_queue_before = before_cars_n + before_cars_s
        opp_queue_after = after_cars_n + after_cars_s

        opp_wait_before = before_wait_n + before_wait_s
        opp_wait_after = after_wait_n + after_wait_s
    else:  # NS green
        active_queue_before = before_cars_n + before_cars_s
        active_queue_after = after_cars_n + after_cars_s

        active_wait_before = before_wait_n + before_wait_s
        active_wait_after = after_wait_n + after_wait_s

        opp_queue_before = before_cars_e + before_cars_w
        opp_queue_after = after_cars_e + after_cars_w

        opp_wait_before = before_wait_e + before_wait_w
        opp_wait_after = after_wait_e + after_wait_w

    active_queue_reduction = active_queue_before - active_queue_after
    active_wait_reduction = active_wait_before - active_wait_after

    opp_queue_growth = max(0, opp_queue_after - opp_queue_before)
    opp_wait_growth = max(0, opp_wait_after - opp_wait_before)

    net_clearance = active_queue_reduction - opp_queue_growth

    initial_halted_count = len(before_active_halted_ids)

    initial_halted_released = 0
    for vid in before_active_halted_ids:
        if vid not in after_active_halted_ids:
            initial_halted_released += 1

    initial_halted_left_active_approach = 0
    for vid in before_active_halted_ids:
        if vid not in after_active_ids:
            initial_halted_left_active_approach += 1

    initial_halted_cleared_approach_zone = 0
    for vid in before_active_halted_ids:
        if vid not in after_active_ids and vid not in after_opposing_ids:
            initial_halted_cleared_approach_zone += 1

    initial_halted_exited_network = 0
    for vid in before_active_halted_ids:
        if vid not in after_all_vehicle_ids:
            initial_halted_exited_network += 1

    initial_opp_halted_count = len(before_opp_halted_ids)
    initial_opp_halted_growth = max(0, len(after_opp_halted_ids) - initial_opp_halted_count)

    if initial_halted_count > 0:
        released_fraction = initial_halted_released / initial_halted_count
        cleared_fraction = initial_halted_cleared_approach_zone / initial_halted_count
    else:
        released_fraction = 0.0
        cleared_fraction = 0.0

    after_total_pain = compute_pain_score_from_values(
        after_cars_n, after_cars_s, after_cars_e, after_cars_w,
        after_wait_n, after_wait_s, after_wait_e, after_wait_w
    )

    return {
        "duration": test_duration,
        "active_queue_before": active_queue_before,
        "active_queue_after": active_queue_after,
        "active_queue_reduction": active_queue_reduction,
        "active_wait_before": active_wait_before,
        "active_wait_after": active_wait_after,
        "active_wait_reduction": active_wait_reduction,
        "opp_queue_before": opp_queue_before,
        "opp_queue_after": opp_queue_after,
        "opp_queue_growth": opp_queue_growth,
        "opp_wait_before": opp_wait_before,
        "opp_wait_after": opp_wait_after,
        "opp_wait_growth": opp_wait_growth,
        "net_clearance": net_clearance,
        "after_total_pain": after_total_pain,
        "initial_halted_count": initial_halted_count,
        "initial_halted_released": initial_halted_released,
        "initial_halted_left_active_approach": initial_halted_left_active_approach,
        "initial_halted_cleared_approach_zone": initial_halted_cleared_approach_zone,
        "initial_halted_exited_network": initial_halted_exited_network,
        "initial_opp_halted_count": initial_opp_halted_count,
        "initial_opp_halted_growth": initial_opp_halted_growth,
        "released_fraction": released_fraction,
        "cleared_fraction": cleared_fraction,
        "after_cars_n": after_cars_n,
        "after_cars_s": after_cars_s,
        "after_cars_e": after_cars_e,
        "after_cars_w": after_cars_w,
        "after_wait_n": after_wait_n,
        "after_wait_s": after_wait_s,
        "after_wait_e": after_wait_e,
        "after_wait_w": after_wait_w,
    }


def choose_better_candidate(best, cand):
    if best is None:
        return cand

    eps = 1e-9
    keys = [
        ("opp_queue_growth", False),
        ("opp_wait_growth", False),
        ("after_total_pain", False),
        ("duration", False),
    ]

    for key, bigger_is_better in keys:
        a = cand[key]
        b = best[key]

        if abs(a - b) <= eps:
            continue

        if bigger_is_better:
            return cand if a > b else best
        else:
            return cand if a < b else best

    return best


def select_best_candidate_small_queue(results):
    best = None
    for cand in sorted(results, key=lambda r: r["duration"]):
        best = choose_better_candidate(best, cand)
    return best


def select_best_candidate_with_plateau(results):
    if not results:
        return None

    max_initial_halted = max(r["initial_halted_count"] for r in results)

    if max_initial_halted <= 4:
        best = select_best_candidate_small_queue(results)
        return best, None, None, sorted(results, key=lambda r: r["duration"]), None, True

    clearance_margin = choose_clearance_margin(max_initial_halted)
    best_cleared_fraction = max(r["cleared_fraction"] for r in results)
    threshold = max(0.0, best_cleared_fraction - clearance_margin)

    filtered = [r for r in results if r["cleared_fraction"] >= threshold]
    filtered = sorted(filtered, key=lambda r: r["duration"])

    best = None
    for cand in filtered:
        best = choose_better_candidate(best, cand)

    return best, best_cleared_fraction, threshold, filtered, clearance_margin, False


def try_choose_tiny_queue_10s(results):
    ten_result = None
    for r in results:
        if r["duration"] == 10:
            ten_result = r
            break

    if ten_result is None:
        return None

    if (
        ten_result["initial_halted_count"] <= TINY_QUEUE_MAX_HALTED
        and ten_result["released_fraction"] >= TINY_QUEUE_RELEASED_THRESHOLD
    ):
        return ten_result

    return None


def try_choose_10s_shortcut(results):
    ten_result = None
    for r in results:
        if r["duration"] == 10:
            ten_result = r
            break

    if ten_result is None:
        return None

    if (
        ten_result["released_fraction"] >= TEN_SHORTCUT_RELEASED_THRESHOLD
        and ten_result["cleared_fraction"] >= TEN_SHORTCUT_CLEARED_THRESHOLD
    ):
        return ten_result

    return None


# =========================
# MAIN DATA COLLECTION
# =========================
def run_trial_and_error():
    sumo_binary = sumolib.checkBinary("sumo-gui")
    traci.start([sumo_binary, "-c", "config.sumocfg"])

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)

        if f.tell() == 0:
            writer.writerow([
                "scenario_type",
                "cars_N", "cars_S", "cars_E", "cars_W",
                "wait_N", "wait_S", "wait_E", "wait_W",
                "phase_flag", "rush_flag", "ped_flag",
                "best_green_time"
            ])

        print(f"Starting scenario: {SCENARIO_TYPE}")
        print(f"Rush flag: {RUSH_FLAG}")
        print(f"Max simulation time: {MAX_SIM_TIME}")
        print("Warming up...")

        for _ in range(WARMUP_STEPS):
            traci.simulationStep()
            if traci.simulation.getTime() >= MAX_SIM_TIME:
                print("Stopped during warmup because MAX_SIM_TIME was reached.")
                traci.close()
                return

        last_phase = -1

        while traci.simulation.getMinExpectedNumber() > 0:
            if traci.simulation.getTime() >= MAX_SIM_TIME:
                print(f"\nReached MAX_SIM_TIME = {MAX_SIM_TIME}. Stopping data collection.")
                break

            traci.simulationStep()
            current_phase = traci.trafficlight.getPhase(TLS_ID)

            if current_phase != last_phase and current_phase in [0, 3]:
                cars_n, cars_s, cars_e, cars_w = get_separate_vehicle_counts()
                wait_n, wait_s, wait_e, wait_w = get_separate_wait_times()

                total_cars = cars_n + cars_s + cars_e + cars_w
                phase_flag = 1 if current_phase == 0 else 0
                phase_name = "East-West" if current_phase == 0 else "North-South"
                ped_flag = is_pedestrian_waiting()

                if SKIP_EMPTY_ROWS and total_cars == 0:
                    print("\n" + "=" * 78)
                    print(f"[Decision Point] Current Phase: {phase_name}")
                    print("No vehicles present. Skipping row.")
                    print("=" * 78)
                    last_phase = current_phase
                    continue

                current_pain_before = compute_pain_score_from_values(
                    cars_n, cars_s, cars_e, cars_w,
                    wait_n, wait_s, wait_e, wait_w
                )

                print("\n" + "=" * 78)
                print(f"[Decision Point] Scenario: {SCENARIO_TYPE}")
                print(f"[Decision Point] Current Phase: {phase_name}")
                print(f"Cars  -> N: {cars_n}, S: {cars_s}, E: {cars_e}, W: {cars_w}")
                print(f"Waits -> N: {wait_n:.2f}, S: {wait_s:.2f}, E: {wait_e:.2f}, W: {wait_w:.2f}")
                print(f"Pedestrian Waiting: {ped_flag}")
                print(f"Current Pain Before Testing: {current_pain_before:.2f}")

                traci.simulation.saveState("checkpoint.xml")

                test_range = choose_test_range(
                    current_phase, ped_flag, cars_n, cars_s, cars_e, cars_w
                )

                candidate_results = []

                print("\nTesting candidate green times:")
                print("Evaluation style: dynamic plateau + small-queue direct ranking + 10s shortcuts")
                print(f"Candidate range used: {test_range}")

                for test_duration in test_range:
                    result = evaluate_candidate_duration(
                        current_phase,
                        test_duration,
                        cars_n, cars_s, cars_e, cars_w,
                        wait_n, wait_s, wait_e, wait_w
                    )

                    candidate_results.append(result)

                    print(
                        f"  Green = {test_duration:2d}s | "
                        f"InitHalted = {result['initial_halted_count']} | "
                        f"Released = {result['initial_halted_released']} ({result['released_fraction']:.2f}) | "
                        f"ClearedZone = {result['initial_halted_cleared_approach_zone']} ({result['cleared_fraction']:.2f}) | "
                        f"OppQGrowth = {result['opp_queue_growth']:.2f} | "
                        f"OppWGrowth = {result['opp_wait_growth']:.2f} | "
                        f"AfterPain = {result['after_total_pain']:.2f} | "
                        f"NetClearance = {result['net_clearance']:.2f} | "
                        f"Cars(N,S,E,W)=({result['after_cars_n']},{result['after_cars_s']},{result['after_cars_e']},{result['after_cars_w']}) | "
                        f"Waits=({result['after_wait_n']:.1f},{result['after_wait_s']:.1f},{result['after_wait_e']:.1f},{result['after_wait_w']:.1f})"
                    )

                    traci.simulation.loadState("checkpoint.xml")

                tiny_queue_result = try_choose_tiny_queue_10s(candidate_results)

                if tiny_queue_result is not None:
                    best_result = tiny_queue_result
                    best_duration = best_result["duration"]

                    print("\nTiny-Queue 10s Shortcut Triggered:")
                    print(f"  Initial Halted Count = {best_result['initial_halted_count']}")
                    print(f"  Released Fraction    = {best_result['released_fraction']:.2f}")

                else:
                    shortcut_result = try_choose_10s_shortcut(candidate_results)

                    if shortcut_result is not None:
                        best_result = shortcut_result
                        best_duration = best_result["duration"]

                        print("\n10s Shortcut Triggered:")
                        print(f"  Released Fraction = {best_result['released_fraction']:.2f}")
                        print(f"  Cleared Fraction  = {best_result['cleared_fraction']:.2f}")
                    else:
                        best_result, best_cleared_fraction, threshold, filtered, clearance_margin, used_small_queue_direct = select_best_candidate_with_plateau(candidate_results)
                        best_duration = best_result["duration"]

                        if used_small_queue_direct:
                            print("\nSmall-Queue Direct Ranking Used:")
                            print(f"  Candidates kept = {[r['duration'] for r in filtered]}")
                        else:
                            print("\nPlateau Filtering:")
                            print(f"  Best cleared fraction = {best_cleared_fraction:.2f}")
                            print(f"  Clearance margin      = {clearance_margin:.2f}")
                            print(f"  Clearance threshold   = {threshold:.2f}")
                            print(f"  Candidates kept       = {[r['duration'] for r in filtered]}")

                print("\nSelected Result:")
                print(f"  Best Green Time        = {best_duration}s")
                print(f"  Initial Halted Count   = {best_result['initial_halted_count']}")
                print(f"  Released Fraction      = {best_result['released_fraction']:.2f}")
                print(f"  Cleared Fraction       = {best_result['cleared_fraction']:.2f}")
                print(f"  Opposing Q Growth      = {best_result['opp_queue_growth']:.2f}")
                print(f"  Opposing W Growth      = {best_result['opp_wait_growth']:.2f}")
                print(f"  After Pain             = {best_result['after_total_pain']:.2f}")
                print("=" * 78)

                writer.writerow([
                    SCENARIO_TYPE,
                    cars_n, cars_s, cars_e, cars_w,
                    wait_n, wait_s, wait_e, wait_w,
                    phase_flag, RUSH_FLAG, ped_flag,
                    best_duration
                ])
                f.flush()

                traci.trafficlight.setPhase(TLS_ID, current_phase)
                traci.trafficlight.setPhaseDuration(TLS_ID, best_duration)

                for _ in range(best_duration + POST_APPLY_BUFFER):
                    traci.simulationStep()
                    if traci.simulation.getTime() >= MAX_SIM_TIME:
                        print(f"\nReached MAX_SIM_TIME = {MAX_SIM_TIME} while applying best duration.")
                        traci.close()
                        return

            last_phase = current_phase

    traci.close()
    print(f"Data collection finished for scenario: {SCENARIO_TYPE}")


if __name__ == "__main__":
    run_trial_and_error()