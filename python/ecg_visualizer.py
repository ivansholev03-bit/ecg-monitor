"""Real-time ECG display (matplotlib).

Serial reading runs in a separate thread so that no samples are lost while
the plot is being drawn (the buffer never overflows).
"""
import time
import threading
import queue
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.signal import savgol_filter

from ecg_filters import ECGFilterChain
from ecg_detector import RPeakDetector
from ecg_storage import ECGStorage

try:
    import serial
except ImportError:
    serial = None


class SerialReader(threading.Thread):
    """Background thread that keeps emptying the serial port into a queue.

    Reading does not depend on how fast the plot is drawn. The operating
    system buffer does not overflow, no samples are lost, and lines are not
    glued together (which used to produce corrupted samples outside 0..1023).
    """
    def __init__(self, ser):
        super().__init__(daemon=True)
        self.ser = ser
        self.q = queue.Queue()
        self._stop_event = threading.Event()

    def run(self):
        buf = bytearray()
        while not self._stop_event.is_set():
            try:
                # Read everything that is available at once, not byte by byte.
                chunk = self.ser.read(self.ser.in_waiting or 1)
            except Exception:
                break
            if not chunk:
                continue
            buf.extend(chunk)
            # Split into whole lines at the newline character.
            while b"\n" in buf:
                line, _, rest = buf.partition(b"\n")
                buf = bytearray(rest)
                try:
                    self.q.put_nowait(int(line.strip()))
                except ValueError:
                    pass  # skip a broken or incomplete line

    def stop(self):
        self._stop_event.set()


class ECGVisualizer:
    WINDOW_S = 6
    FS = 256.0

    # --- R-peak markers (display only) ---
    MARK_FLOOR = 60.0   # no marker below this height, to avoid false ones

    # --- Smoothing for the display only (detection is not affected) ---
    SMOOTH_WIN = 9      # window length (odd, about 35 ms at 256 Hz)
    SMOOTH_POLY = 3     # polynomial order (must be < SMOOTH_WIN)

    def __init__(self, port=None, baud=57600):
        if port and serial:
            # timeout=0 means non-blocking reads; the thread sets the pace.
            self.ser = serial.Serial(port, baud, timeout=0)
            self.reader = SerialReader(self.ser)
        else:
            self.ser = None
            self.reader = None

        self.chain = ECGFilterChain(fs=self.FS)
        self.det = RPeakDetector(fs=self.FS)
        self.store = ECGStorage()
        self.N = int(self.WINDOW_S * self.FS)
        self.t = np.linspace(-self.WINDOW_S, 0, self.N)
        self.ecg = np.zeros(self.N)

        self.fig, self.ax = plt.subplots(figsize=(14, 5))
        self.line, = self.ax.plot(self.t, self.ecg, color="#C62828", lw=1.1)
        # dots on the tops of the detected R-peaks
        self.peaks, = self.ax.plot([], [], "o", color="#1565C0",
                                   markersize=7, linestyle="none", label="R-peak")
        self.ax.set_xlim(-self.WINDOW_S, 0)
        self.ax.set_ylim(-200, 300)
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("ECG [mV]")
        self.ax.grid(True, alpha=0.4)
        self.ax.legend(loc="upper right", fontsize=11)
        self.hr_text = self.ax.text(0.02, 0.95, "", transform=self.ax.transAxes,
                                    fontsize=14, weight="bold")
        self.sample_n = 0

    def _find_peaks(self):
        """Finds the R-peaks in the current window for the markers.
        Puts a dot on the local maximum of each large wave."""
        d = self.ecg
        thr = max(self.MARK_FLOOR, np.percentile(d, 96) * 0.6)
        refr = int(0.33 * self.FS)
        cand = np.where((d[1:-1] > d[:-2]) &
                        (d[1:-1] >= d[2:]) &
                        (d[1:-1] > thr))[0] + 1
        peaks = []
        last = -10 ** 9
        for c in cand:
            if c - last >= refr:
                peaks.append(c); last = c
            elif peaks and d[c] > d[peaks[-1]]:
                peaks[-1] = c; last = c
        # Fine tuning: move each marker to the exact local maximum (the top of the wave).
        refined = []
        for c in peaks:
            lo = max(0, c - 8); hi = min(self.N, c + 9)
            refined.append(lo + int(np.argmax(d[lo:hi])))
        return np.array(refined, dtype=int)

    def update(self, frame):
        # Empty everything the thread has collected since the last frame.
        # This keeps up with the data and loses no samples, however slowly
        # the plot is drawn.
        if self.reader is not None:
            while True:
                try:
                    raw = self.reader.q.get_nowait()
                except queue.Empty:
                    break
                self.sample_n += 1
                # Time comes from the NUMBER of samples (exact at 256 Hz),
                # not from the computer clock, which is uneven because of
                # buffering. This gives a correct HR and time axis.
                t_sample = self.sample_n / self.FS
                mv = self.chain.process(raw)
                is_r = self.det.update(mv, t_sample)
                self.store.append(self.sample_n, t_sample, raw, mv,
                                  self.det.heart_rate, is_r)
                self.ecg = np.roll(self.ecg, -1)
                self.ecg[-1] = mv

        # Smoothing for the display only. It removes small muscle noise but
        # keeps the height of the QRS complex (unlike a plain moving average).
        # R-peak detection still runs on the real signal in self.ecg.
        if self.N >= self.SMOOTH_WIN:
            disp = savgol_filter(self.ecg, self.SMOOTH_WIN, self.SMOOTH_POLY)
        else:
            disp = self.ecg
        self.line.set_ydata(disp)

        # R-peak markers: found on the real signal, but drawn on the
        # smoothed line so that they sit on it.
        pk = self._find_peaks()
        if len(pk):
            self.peaks.set_data(self.t[pk], disp[pk])
        else:
            self.peaks.set_data([], [])

        self.hr_text.set_text(f"HR: {self.det.heart_rate} bpm")
        return self.line, self.peaks, self.hr_text

    def run(self):
        if self.ser is None:
            print("[WARNING] No serial port given. To use the hardware, run:")
            print("python main.py --port COM3 (or /dev/ttyUSB0)")
            print("For a test without hardware: python ecg_verification.py")
            return
        try:
            self.reader.start()             # start reading in the background
            self.ani = FuncAnimation(self.fig, self.update,
                                     interval=50, blit=True)
            plt.show()
        finally:
            if self.reader is not None:
                self.reader.stop()
            self.store.finalize(fs=self.FS)
