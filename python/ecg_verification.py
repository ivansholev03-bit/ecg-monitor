"""Checks the digital filters with synthetic sine waves and plots the result.

Needs no hardware. Run: python ecg_verification.py
"""
import numpy as np
import matplotlib.pyplot as plt
from ecg_filters import NotchFilter, BaselineFilter

# --- Test parameters ---
FS = 256.0                   # sampling rate [Hz]
DUR = 4.0                    # test duration [s]
N = int(FS * DUR)
t = np.arange(N) / FS        # time vector


def plot_4panels(signals, titles, fname):
    """Plots four signals on separate panels."""
    fig, ax = plt.subplots(4, 1, figsize=(12, 9))
    colors = ['#1565C0', '#C62828', '#6A1B9A', '#2E7D32']
    for i, (s, title, c) in enumerate(zip(signals, titles, colors)):
        ax[i].plot(t, s, color=c, lw=1.0)
        ax[i].set_title(title, fontweight='bold', fontsize=11)
        ax[i].set_ylabel('Amplitude [mV]')
        ax[i].grid(alpha=0.3)
    ax[-1].set_xlabel('Time [s]')
    plt.tight_layout()
    plt.savefig(fname, dpi=120)
    plt.show()


def plot_fft(sig_in, sig_out, marker_hz, title, fname):
    """FFT spectrum, showing the sine components before and after the filter."""
    xf = np.fft.rfftfreq(N, 1.0 / FS)
    yi = np.abs(np.fft.rfft(sig_in)) * 2.0 / N
    yo = np.abs(np.fft.rfft(sig_out)) * 2.0 / N

    plt.figure(figsize=(12, 5))
    plt.plot(xf, yi, color='#C62828', lw=1.3, label='Before the filter')
    plt.plot(xf, yo, color='#2E7D32', lw=1.3, label='After the filter')
    plt.axvline(marker_hz, color='k', ls='--', alpha=0.6,
                label=f'{marker_hz} Hz (target frequency)')
    plt.xlim(0, 80)
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Amplitude [mV]')
    plt.title(title, fontweight='bold')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(fname, dpi=120)
    plt.show()


def verify_notch_50hz():
    """Test 1: notch filter with an ECG-like sine wave plus 50 Hz interference."""
    ecg_sin = 500 * np.sin(2 * np.pi * 10 * t)    # ECG-like 10 Hz
    pli_sin = 500 * np.sin(2 * np.pi * 50 * t)    # mains interference
    mixed = ecg_sin + pli_sin                     # filter input

    notch = NotchFilter(f0=50.0, fs=FS)
    out = np.array([notch.process(x) for x in mixed])

    plot_4panels(
        [ecg_sin, pli_sin, mixed, out],
        ['ECG-like sine wave, 10 Hz',
         'Mains interference, 50 Hz',
         'Sum (filter input)',
         'Notch filter output, recovered signal'],
        'verify_notch.png'
    )
    plot_fft(mixed, out, marker_hz=50,
             title='Notch filter amplitude spectrum',
             fname='verify_notch_fft.png')
    print('[VERIFY] Notch 50 Hz: saved verify_notch.png and verify_notch_fft.png')


def verify_hpf_drift():
    """Test 2: high-pass filter with breathing drift and an ECG-like sine wave."""
    drift = 300 * np.sin(2 * np.pi * 0.1 * t)     # breathing drift
    ecg_sin = 600 * np.sin(2 * np.pi * 8.0 * t)   # ECG-like 8 Hz
    mixed = drift + ecg_sin

    hpf = BaselineFilter(fc=0.16, fs=FS)
    out = np.array([hpf.process(x) for x in mixed])

    plot_4panels(
        [drift, ecg_sin, mixed, out],
        ['Drift, 0.1 Hz (simulated breathing)',
         'ECG-like sine wave, 8 Hz',
         'Sum (filter input)',
         'High-pass filter output, drift removed'],
        'verify_hpf.png'
    )
    print('[VERIFY] HPF 0.16 Hz: saved verify_hpf.png')


if __name__ == '__main__':
    print('[VERIFY] Starting digital filter verification')
    verify_notch_50hz()
    verify_hpf_drift()
    print('[VERIFY] Done.')
