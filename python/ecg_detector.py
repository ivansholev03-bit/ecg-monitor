"""Adaptive R-peak detector and heart rate.

The threshold adjusts itself to the current signal amplitude. It is a
simplified Pan-Tompkins approach built on running SPK/NPK estimates.
Run this file directly to test it on MIT-BIH record 100.
"""
from collections import deque
import numpy as np
import matplotlib.pyplot as plt


class RPeakDetector:
    """Adaptive R-peak detector.

    It keeps two running estimates:
      * SPK: the typical level of signal (R) peaks
      * NPK: the typical level of noise and the rest of the signal
    The threshold sits between them: threshold = NPK + k * (SPK - NPK).
    This way detection does not depend on the signal strength (different
    electrode contact or gain) and needs no hand-tuned fixed value.
    """

    def __init__(self, fs=256.0):
        self.fs = fs
        self.refractory = int(0.30 * fs)     # at least 300 ms between peaks
        self.warmup = int(2.0 * fs)          # first 2 s: learn the levels
        self.k = 0.6                         # threshold position between NPK and SPK

        self.spk = 0.0
        self.npk = 0.0
        self.threshold = 0.0

        self.n = 0                           # sample counter
        self.samples_since = self.refractory + 1
        self.last_r_n = None
        self.rr_buffer = deque(maxlen=8)
        self.prev = 0.0

    def update(self, value: float, timestamp: float = None) -> bool:
        # timestamp is accepted for compatibility, but time is measured by
        # counting samples (exact at fs), not by the computer clock.
        self.n += 1
        self.samples_since += 1

        # Warm-up: only estimate the levels, no detection yet.
        if self.n <= self.warmup:
            if value > self.spk:
                self.spk = value
            self.npk = 0.95 * self.npk + 0.05 * abs(value)
            self.threshold = self.npk + self.k * (self.spk - self.npk)
            self.prev = value
            return False

        is_r = False
        # An R-peak is a local maximum above the threshold: the previous
        # sample was the top and the current one is already falling.
        # The refractory period must have passed.
        if (self.prev >= self.threshold and value < self.prev
                and self.samples_since > self.refractory
                and self.prev > 0.4 * self.spk):
            peak = self.prev
            if self.last_r_n is not None:
                rr_ms = (self.n - self.last_r_n) / self.fs * 1000.0
                if 300 < rr_ms < 2000:               # 30..200 BPM
                    self.rr_buffer.append(rr_ms)
            self.last_r_n = self.n
            self.samples_since = 0
            self.spk = 0.875 * self.spk + 0.125 * peak   # update the signal level
            is_r = True
        elif value < self.threshold:
            self.npk = 0.98 * self.npk + 0.02 * abs(value)  # update the noise level

        self.threshold = self.npk + self.k * (self.spk - self.npk)
        self.prev = value
        return is_r

    @property
    def heart_rate(self) -> int:
        if len(self.rr_buffer) < 2:
            return 0
        return int(60000.0 / np.mean(self.rr_buffer))


# ============================================================
#  Test: runs only when this file is started directly
# ============================================================
if __name__ == "__main__":
    import wfdb
    print("Loading an ECG signal from the MIT-BIH database...")
    record = wfdb.rdrecord('100', pn_dir='mitdb', sampto=3600)

    fs = record.fs
    ecg_signal = record.p_signal[:, 0]
    time_axis = np.arange(len(ecg_signal)) / fs

    print(f"Sampling rate: {fs} Hz")
    print(f"Samples: {len(ecg_signal)}")
    print(f"Duration: {len(ecg_signal)/fs:.2f} s")

    ecg_scaled = ecg_signal * 500

    detector = RPeakDetector(fs=fs)
    r_peak_times = []
    r_peak_values = []

    for i, value in enumerate(ecg_scaled):
        t = i / fs
        if detector.update(value, t):
            r_peak_times.append((i - 1) / fs)
            r_peak_values.append(ecg_signal[i - 1])

    print(f"\nR-peaks found: {len(r_peak_times)}")
    print(f"Heart rate: {detector.heart_rate} BPM")

    plt.figure(figsize=(14, 5))
    plt.plot(time_axis, ecg_signal, label='ECG signal', linewidth=0.8)
    plt.plot(r_peak_times, r_peak_values, 'ro', markersize=8, label='R-peaks')
    plt.title(f'ECG R-peak detection, HR: {detector.heart_rate} BPM')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude (mV)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    print("\nDone.")
