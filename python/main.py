"""Entry point: live display with a serial port, or offline analysis of a CSV."""
import argparse
import numpy as np
import matplotlib.pyplot as plt

from ecg_visualizer import ECGVisualizer
from ecg_storage import ECGStorage

FS = 256.0
SKIP_S = 5.0   # seconds skipped at the start (the high-pass filter settles)


def offline_analysis(csv_path: str):
    """Loads a CSV and plots a three-panel analysis."""
    print(f"[MAIN] Loading: {csv_path}")
    d = ECGStorage.load_csv(csv_path)

    raw = d["raw"].astype(float)
    filt = d["filtered"].astype(float)
    rpk = d["r_peaks"]

    # --- Time axis from the sample count (exact at 256 Hz) ---
    # Computer timestamps are uneven because of buffering, so time is
    # taken from the sample index divided by fs.
    t = np.arange(len(raw)) / FS

    # --- Mark corrupted samples (for old recordings) ---
    # The 10-bit ADC returns 0..1023. Values outside that range are
    # transmission errors and are left out of the plot (replaced by NaN).
    valid = (raw >= 0) & (raw <= 1023)
    raw_plot = np.where(valid, raw, np.nan)

    # The filtered signal is hidden not only at the corrupted sample but
    # also for a few samples after it, where the high-pass filter still
    # rings from the hit. (New recordings do not have this problem because
    # the glitch never enters the filter. The guard only matters when
    # re-analysing old files.)
    invalid = ~valid
    guard = int(0.4 * FS)
    if invalid.any():
        bad = invalid.copy()
        for i in np.where(invalid)[0]:
            bad[i:min(len(bad), i + guard)] = True
        filt_plot = np.where(bad, np.nan, filt)
    else:
        filt_plot = filt.copy()

    # --- Skip the transient at the start ---
    skip = int(SKIP_S * FS)
    sl = slice(skip, None)

    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(f"Offline ECG analysis - {csv_path}", fontweight="bold")

    # 1) Raw signal
    axes[0].plot(t[sl], raw_plot[sl], color="gray", lw=0.7)
    finite_raw = raw_plot[sl][np.isfinite(raw_plot[sl])]
    if finite_raw.size:
        lo, hi = np.percentile(finite_raw, [0.5, 99.5])
        axes[0].set_ylim(lo - 10, hi + 10)
    axes[0].set_title("Raw ADC signal")
    axes[0].set_ylabel("ADC value")
    axes[0].grid(alpha=0.4)

    # 2) Filtered signal with R-peaks
    axes[1].plot(t[sl], filt_plot[sl], color="#C62828", lw=1.0)
    r_idx = np.where(rpk & valid)[0]
    r_idx = r_idx[r_idx >= skip]
    if len(r_idx) > 0:
        axes[1].scatter(t[r_idx], filt_plot[r_idx],
                        marker="v", color="#1565C0", s=60, label="R-peak")
        axes[1].legend()
    finite_f = filt_plot[sl][np.isfinite(filt_plot[sl])]
    if finite_f.size:
        lo, hi = np.percentile(finite_f, [0.5, 99.5])
        m = 0.15 * (hi - lo + 1)
        axes[1].set_ylim(lo - m, hi + m)
    axes[1].set_title("Filtered ECG (notch + high-pass)")
    axes[1].set_ylabel("Amplitude [mV]")
    axes[1].grid(alpha=0.4)

    # 3) FFT (of the cleaned filtered signal, after the transient)
    sig = filt_plot[sl].copy()
    sig[~np.isfinite(sig)] = 0.0   # fill any NaN with zero
    N = len(sig)
    xf = np.fft.rfftfreq(N, 1.0 / FS)
    yf = np.abs(np.fft.rfft(sig)) * 2 / N
    mask = xf < 80
    axes[2].semilogy(xf[mask], yf[mask], color="#0288D1", lw=0.9)
    axes[2].axvline(50, color="red", ls="--", alpha=0.7, label="50 Hz")
    axes[2].axvline(0.16, color="green", ls="--", alpha=0.7, label="0.16 Hz")
    axes[2].set_title("Amplitude spectrum (FFT)")
    axes[2].set_xlabel("Frequency [Hz]")
    axes[2].set_ylabel("Amplitude [mV]")
    axes[2].legend()
    axes[2].grid(alpha=0.4)

    plt.tight_layout()
    out = csv_path.replace(".csv", "_analysis.png")
    plt.savefig(out, dpi=150)
    plt.show()
    print(f"[MAIN] Saved: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ECG system for the Olimexino-328")
    parser.add_argument("--port", type=str,
                        help="Serial port (COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=57600)
    parser.add_argument("--analyze", type=str,
                        help="Offline analysis of a CSV file")
    args = parser.parse_args()

    if args.analyze:
        offline_analysis(args.analyze)
    else:
        ECGVisualizer(port=args.port, baud=args.baud).run()
