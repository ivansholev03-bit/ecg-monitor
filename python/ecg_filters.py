"""Digital filters for the ECG signal.

A 50 Hz IIR notch, a 0.16 Hz IIR high-pass, and a check that rejects
corrupted samples (the 10-bit ADC only returns 0..1023).
"""
import numpy as np


class NotchFilter:
    """Second-order IIR notch filter that removes 50 Hz mains interference."""
    def __init__(self, f0=50.0, fs=256.0, r=0.975):
        w0 = 2 * np.pi * f0 / fs
        self.b1 = -2 * np.cos(w0)
        self.a1 = -2 * r * np.cos(w0)
        self.a2 = r ** 2
        self.x1 = self.x2 = 0.0
        self.y1 = self.y2 = 0.0

    def process(self, x: float) -> float:
        y = (x + self.b1 * self.x1 + self.x2
               - self.a1 * self.y1 - self.a2 * self.y2)
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class BaselineFilter:
    """First-order IIR high-pass filter that removes baseline drift."""
    def __init__(self, fc=0.16, fs=256.0):
        self.alpha = 1.0 / (1.0 + 2 * np.pi * fc / fs)
        self.x_prev = 0.0
        self.y_prev = 0.0

    def process(self, x: float) -> float:
        y = self.alpha * (self.y_prev + x - self.x_prev)
        self.x_prev = x
        self.y_prev = y
        return y


class ECGFilterChain:
    """High-pass, then notch, with the ADC value converted to mV."""
    ADC_MID = 512
    V_REF_MV = 3300.0
    ADC_RES = 1024

    def __init__(self, fs=256.0):
        self.hpf = BaselineFilter(fc=0.16, fs=fs)
        self.notch = NotchFilter(f0=50.0, fs=fs)
        # Last valid sample, used to replace corrupted ones.
        self.last_valid = self.ADC_MID

    def process(self, raw_adc: int) -> float:
        # The 10-bit ADC only returns 0..1023. Anything outside that range
        # is a serial transmission error (merged or lost bytes), so it is
        # replaced with the last valid sample. Otherwise it would send a
        # large transient through the filters.
        if 0 <= raw_adc <= 1023:
            self.last_valid = raw_adc
        else:
            raw_adc = self.last_valid

        mv = (raw_adc - self.ADC_MID) * (self.V_REF_MV / self.ADC_RES)
        mv = self.hpf.process(mv)
        mv = self.notch.process(mv)
        return mv

    def reset(self):
        self.hpf.x_prev = self.hpf.y_prev = 0.0
        self.notch.x1 = self.notch.x2 = 0.0
        self.notch.y1 = self.notch.y2 = 0.0
        self.last_valid = self.ADC_MID
