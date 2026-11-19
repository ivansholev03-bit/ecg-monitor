"""Saves a recording as CSV, PNG and JSON."""
import csv
import json
import os
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt


class ECGStorage:
    def __init__(self, out_dir="ecg_recordings"):
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = f"{out_dir}/ECG_{ts}.csv"
        self.png_path = f"{out_dir}/ECG_{ts}.png"
        self.json_path = f"{out_dir}/ECG_{ts}.json"
        self.rows = []

    def append(self, n, t, raw, ecg_mv, hr, is_r):
        self.rows.append([n, t, raw, ecg_mv, hr, int(is_r)])

    def finalize(self, fs=256.0):
        # 1. CSV
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["sample_n", "timestamp_s", "raw_adc",
                        "filtered_mv", "hr_bpm", "r_peak"])
            w.writerows(self.rows)
        # 2. JSON metadata
        meta = {"samples": len(self.rows), "fs_hz": fs,
                "duration_s": self.rows[-1][1] if self.rows else 0,
                "filter_notch_hz": 50.0,
                "filter_hpf_hz": 0.16}
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        # 3. PNG plot
        if self.rows:
            arr = np.array(self.rows)
            plt.figure(figsize=(14, 4))
            plt.plot(arr[:, 1], arr[:, 3], color="#C62828", lw=0.8)
            plt.xlabel("Time [s]")
            plt.ylabel("ECG [mV]")
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(self.png_path, dpi=120)
            plt.close()
        print(f"[STORAGE] Saved: {self.csv_path}")
        print(f"[STORAGE] Saved: {self.png_path}")
        print(f"[STORAGE] Saved: {self.json_path}")

    @staticmethod
    def load_csv(path):
        arr = np.loadtxt(path, delimiter=",", skiprows=1)
        return {"n": arr[:, 0], "t": arr[:, 1], "raw": arr[:, 2],
                "filtered": arr[:, 3], "hr": arr[:, 4],
                "r_peaks": arr[:, 5].astype(bool)}
