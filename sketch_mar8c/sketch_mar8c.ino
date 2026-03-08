// Arduino UNO R4 WiFi — GUI Test Interface
// A0 = DAC çıkışı | A1,A2,A3 = ADC girişi | Pin 2,3,4,5 = GPIO | Pin 9 = PWM

const int GPIO_PINS[] = {2, 3, 4, 5};
const int NUM_GPIO    = 4;
const int PWM_PIN     = 9;
const int DAC_PIN     = A0;

void setup() {
  Serial.begin(115200);
  analogReadResolution(14);   // 14-bit ADC → 0–16383
  analogWriteResolution(8);   // PWM/DAC    → 0–255

  for (int i = 0; i < NUM_GPIO; i++) {
    pinMode(GPIO_PINS[i], OUTPUT);
    digitalWrite(GPIO_PINS[i], LOW);
  }
  pinMode(PWM_PIN, OUTPUT);

  Serial.println("UNO_R4_READY");
}

void loop() {
  // ADC oku — A0 DAC olduğu için A1, A2, A3 kullan
  int a1 = analogRead(A1);
  int a2 = analogRead(A2);
  int a3 = analogRead(A3);

  Serial.print("ADC0:"); Serial.print(a1);
  Serial.print(",ADC1:"); Serial.print(a2);
  Serial.print(",ADC2:"); Serial.println(a3);

  // Gelen komutları işle
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    // GPIO:<pin>:<0|1>  →  ör: GPIO:3:1
    if (cmd.startsWith("GPIO:")) {
      int sep   = cmd.indexOf(':', 5);
      int pin   = cmd.substring(5, sep).toInt();
      int state = cmd.substring(sep + 1).toInt();
      digitalWrite(pin, state ? HIGH : LOW);
      Serial.print("ACK:GPIO:"); Serial.print(pin);
      Serial.print(":"); Serial.println(state);
    }

    // PWM:<pin>:<0-255>  →  ör: PWM:9:128
    else if (cmd.startsWith("PWM:")) {
      int sep = cmd.indexOf(':', 4);
      int pin = cmd.substring(4, sep).toInt();
      int val = constrain(cmd.substring(sep + 1).toInt(), 0, 255);
      analogWrite(pin, val);
      Serial.print("ACK:PWM:"); Serial.print(pin);
      Serial.print(":"); Serial.println(val);
    }

    // DAC:<0-255>  →  ör: DAC:200  (A0 pinine 0V–3.3V)
    else if (cmd.startsWith("DAC:")) {
      int val = constrain(cmd.substring(4).toInt(), 0, 255);
      analogWrite(DAC_PIN, val);
      Serial.print("ACK:DAC:"); Serial.println(val);
    }
  }

  delay(100);
}