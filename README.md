# ECG monitor: acquisition, processing and visualization

A single-lead ECG monitor I built for my bachelor's thesis in Telecommunications at the Technical University of Sofia (2026). An Olimexino-328 board with an ECG shield samples the signal at 256 Hz and sends it over UART to a Python application. The application filters the signal, detects R-peaks, shows a scrolling trace in real time and saves the recording.

This is a student project and not a medical device.

## Results

| Test | Result |
| --- | --- |
| Sampling | 256 Hz, 10-bit ADC |
| 50 Hz notch filter (synthetic sine waves) | 50 Hz attenuated by 47 dB, 10 Hz by only 0.03 dB |
| 0.16 Hz high-pass filter (synthetic sine waves) | 0.1 Hz drift attenuated by 17 dB, 8 Hz by 0.01 dB |
| R-peak detector on MIT-BIH record 100 (10 s segment) | All 13 R-peaks found, 74 BPM |
| Full system, about 40 s recording from the prototype | No lost samples at 256 Hz, about 71 BPM |

## How it works

```
electrodes
    |
SHIELD-EKG-EMG (analog: instrumentation amplifier, right leg drive,
                high-pass 0.16 Hz, low-pass 40 Hz)
    |
Olimexino-328 (ATmega328P: 10-bit ADC, Timer1 interrupt at 256 Hz)
    |  UART, one ADC value per line
    v
Python on the PC
    sample validation -> high-pass 0.16 Hz -> notch 50 Hz -> R-peak detector
                                                         |
                                       live display and CSV/PNG/JSON storage
```

The firmware is small. A timer interrupt reads the ADC at 256 Hz and the main loop prints each value to the serial port. All the processing runs in Python.

### Digital filters

The analog shield already applies a 0.16 Hz high-pass and a 40 Hz low-pass. The Python side adds two IIR filters on top:

- A first-order high-pass at 0.16 Hz that removes baseline drift.
- A second-order notch at 50 Hz (pole radius 0.975) that removes mains interference.

Samples outside 0 to 1023 come from serial transmission errors. The filter chain replaces them with the last valid sample so they do not ring through the filters.

### R-peak detector

The detector keeps running estimates of the typical R-peak level (SPK) and the noise level (NPK) and places the threshold between them: `threshold = NPK + 0.6 * (SPK - NPK)`. This is a simplified version of the Pan-Tompkins idea. Because the threshold follows the signal, it works with different electrode contact and gain without manual tuning.

- The first 2 s are used to learn the levels.
- A peak is a local maximum above the threshold, at least 300 ms after the previous one.
- RR intervals outside 300 to 2000 ms are ignored.
- Heart rate is 60000 divided by the mean of the last 8 RR intervals.

### Reading the serial port

A background thread empties the serial port into a queue, so drawing the plot never blocks reading. Early versions lost about a third of the samples because plotting was too slow to keep up with 256 Hz. Reading in a separate thread fixed that.

## Hardware

- Olimexino-328 board
- SHIELD-EKG-EMG analog front-end
- SHIELD-EKG-EMG-PA passive electrode cable and electrodes

## Code

| File | What it does |
| --- | --- |
| `ecg_filters.py` | Sample validation, high-pass and notch filters |
| `ecg_detector.py` | Adaptive R-peak detector and heart rate. Run it directly to test on MIT-BIH record 100 |
| `ecg_visualizer.py` | Serial reader thread and real-time display on ECG grid paper |
| `ecg_storage.py` | Saves recordings as CSV, PNG and JSON |
| `ecg_verification.py` | Tests both filters with synthetic sine waves, no hardware needed |
| `main.py` | Command-line entry point for live and offline use |

The display applies a light Savitzky-Golay smoothing (window 9, order 3) for readability. The stored data and the detector use the unsmoothed filtered signal.

## Quick start

Python 3.10 or newer.

```
cd python
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

### Without hardware

```
python ecg_verification.py
```

This writes `verify_notch.png`, `verify_notch_fft.png` and `verify_hpf.png`, which show the filters on synthetic signals.

```
python ecg_detector.py
```

This downloads MIT-BIH record 100 with `wfdb` (needs internet) and plots the detected R-peaks.

### With the board

1. Open `firmware/ecg_olimex/ecg_olimex.ino` in the Arduino IDE and upload it to the Olimexino-328.
2. Find the serial port (for example `COM3` on Windows or `/dev/ttyUSB0` on Linux).
3. Start the live display:

```
python main.py --port COM3
```

The baud rate in the sketch must match `--baud` (default 57600). Close the Arduino Serial Monitor first, because it holds the port open. When you close the plot window, the recording is saved to `ecg_recordings/`.

### Analyze a saved recording

```
python main.py --analyze ecg_recordings/ECG_YYYYMMDD_HHMMSS.csv
```

This plots the raw signal, the filtered signal with R-peaks, and the FFT spectrum, and saves the figure next to the CSV.

## Thesis

The full design, the filter derivations and the test results are in my thesis, "A System for Acquisition, Processing and Visualization of ECG Signals" (in Bulgarian).
