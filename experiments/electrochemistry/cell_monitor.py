#!/usr/bin/env python3
import time
import csv
from datetime import datetime

try:
    from ina219 import INA219
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

SHUNT_OHMS = 0.1
MAX_EXPECTED_AMPS = 5.0
FARADAY_FE2 = 1.0416
TARGET_ETA = 0.80

LOG_FILE = "cell_flight_log.csv"

class CellMonitor:
    def __init__(self):
        self.cumulative_ah = 0.0
        self.estimated_mass = 0.0
        self.last_timestamp = time.time()
        if HAS_HARDWARE:
            self.ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS)
            self.ina.configure(self.ina.RANGE_16V)
            print("[*] INA219 hardware linked.")
        else:
            print("[!] Simulation mode.")

    def read_metrics(self):
        if HAS_HARDWARE:
            v = self.ina.voltage()
            i = self.ina.current() / 1000.0
            return v, i
        else:
            import random
            return (1.35 + random.uniform(-0.03, 0.03), 2.50 + random.uniform(-0.08, 0.08))

    def update_integration(self, current):
        now = time.time()
        dt = (now - self.last_timestamp) / 3600.0
        self.last_timestamp = now
        self.cumulative_ah += current * dt
        self.estimated_mass = self.cumulative_ah * FARADAY_FE2 * TARGET_ETA

    def check_anomalies(self, voltage, current):
        if current > 0.1:
            if voltage < 0.8:
                return "SHORT_CIRCUIT_CRITICAL"
            if voltage > 2.2:
                return "HIGH_RESISTANCE_INSULATION"
        return "NOMINAL"

def run_telemetry_loop():
    monitor = CellMonitor()
    print(f"[*] Logging to {LOG_FILE}")
    print("Time     | V(V)   | I(A)   | Ah      | Mass(g) | Status")
    print("-----------------------------------------------------")
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Voltage_V", "Current_A", "Amp_Hours", "Est_Mass_G", "Status"])
        try:
            while True:
                v, i = monitor.read_metrics()
                monitor.update_integration(i)
                status = monitor.check_anomalies(v, i)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"{ts} | {v:6.3f} | {i:6.3f} | {monitor.cumulative_ah:7.4f} | {monitor.estimated_mass:7.2f} | {status}")
                writer.writerow([datetime.now().isoformat(), v, i, monitor.cumulative_ah, monitor.estimated_mass, status])
                f.flush()
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n[*] Stopped.")
            print(f"Final Ah: {monitor.cumulative_ah:.4f} | Est. Mass: {monitor.estimated_mass:.2f}g")

if __name__ == "__main__":
    run_telemetry_loop()