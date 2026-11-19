/* ============================================================
 * File:     ecg_olimex.ino
 * Board:    OLIMEXINO-328 + SHIELD-EKG-EMG
 * Purpose:  Sample the ECG with Timer1 at f_s = 256 Hz and send
 *           each ADC value over UART, one value per line
 * ============================================================ */

#define ECG_PIN   A0
#define BAUD      57600

volatile uint16_t adc_val  = 0;
volatile bool     new_data = false;

ISR(TIMER1_COMPA_vect) {
  adc_val  = analogRead(ECG_PIN);
  new_data = true;
}

void setup() {
  Serial.begin(BAUD);
  // Timer1 in CTC mode, f_s = 256 Hz at 16 MHz, prescaler = 64
  // OCR1A = (16e6 / (64 * 256)) - 1 ≈ 976
  cli();
  TCCR1A = 0;
  TCCR1B = 0;
  OCR1A  = 975;
  TCCR1B = (1 << WGM12) | (1 << CS11) | (1 << CS10);
  TIMSK1 = (1 << OCIE1A);
  sei();
}

void loop() {
  if (!new_data) return;
  new_data = false;
  Serial.println(adc_val);
}
