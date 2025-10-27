//------------------------------------------------------------------------------
// Auth Token are provided by the Blynk.Cloud
// BOARD ESP32 DEVKIT V1 30 PINS
//------------------------------------------------------------------------------

#define BLYNK_TEMPLATE_ID "TMPL2b-PiE3H-"
#define BLYNK_TEMPLATE_NAME "Rastreamento"
#define BLYNK_AUTH_TOKEN "_Cm7fdhv3ndn2LobfQwCxsgn4cTNxO1d"

char auth[] = BLYNK_AUTH_TOKEN;


char ssid[] = "WL_AUTOMAC";
char password[] = "47018693";


#define BLYNK_PRINT Serial
#include "soc/rtc_cntl_reg.h"
#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>
#include <DHT.h>
#include <NTPClient.h>
#include <Timezone.h>
#include <TimeLib.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


#define rele0 25
#define rele1 22
#define rele2 18
#define rele3 19
#define rele4 21
#define DHT_PIN 4
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// --- INÍCIO: pinos e variáveis para interruptores manuais ---
#define SW0 23
#define SW1 26
#define SW2 32
#define SW3 33
#define SW4 27

const int switchPins[5] = { SW0, SW1, SW2, SW3, SW4 };
const int relayPins[5]  = { rele0, rele1, rele2, rele3, rele4 };
const int vPins[5]      = { V3, V6, V7, V8, V9 };

const unsigned long debounceDelay = 30;
int switchRawState[5];
int switchStableState[5];
unsigned long lastDebounceTime[5];

bool displayValues = true;

bool relay0State = HIGH; // Configura estado inicial do relé.
bool relay1State = HIGH; // Configura estado inicial do relé.
bool relay2State = HIGH; // Configura estado inicial do relé.
bool relay3State = HIGH; // Configura estado inicial do relé.
bool relay4State = HIGH; // Configura estado inicial do relé.

// --- ADICIONADO: flags e ISRs para resposta instantânea ---
volatile bool blynkPending[5] = { false, false, false, false, false };

// debounce por ISR
volatile unsigned long lastIsrTime[5] = {0,0,0,0,0};
const unsigned long isrDebounceMicros = 200000UL; // 200ms

IRAM_ATTR void isr_switch0() {
  unsigned long now = micros();
  if ((now - lastIsrTime[0]) < isrDebounceMicros) return;
  lastIsrTime[0] = now;
  int newOut = !digitalRead(rele0);
  digitalWrite(rele0, newOut);
  relay0State = (digitalRead(rele0) == LOW);
  blynkPending[0] = true;
}
IRAM_ATTR void isr_switch1() {
  unsigned long now = micros();
  if ((now - lastIsrTime[1]) < isrDebounceMicros) return;
  lastIsrTime[1] = now;
  int newOut = !digitalRead(rele1);
  digitalWrite(rele1, newOut);
  relay1State = (digitalRead(rele1) == LOW);
  blynkPending[1] = true;
}
IRAM_ATTR void isr_switch2() {
  unsigned long now = micros();
  if ((now - lastIsrTime[2]) < isrDebounceMicros) return;
  lastIsrTime[2] = now;
  int newOut = !digitalRead(rele2);
  digitalWrite(rele2, newOut);
  relay2State = (digitalRead(rele2) == LOW);
  blynkPending[2] = true;
}
IRAM_ATTR void isr_switch3() {
  unsigned long now = micros();
  if ((now - lastIsrTime[3]) < isrDebounceMicros) return;
  lastIsrTime[3] = now;
  int newOut = !digitalRead(rele3);
  digitalWrite(rele3, newOut);
  relay3State = (digitalRead(rele3) == LOW);
  blynkPending[3] = true;
}
IRAM_ATTR void isr_switch4() {
  unsigned long now = micros();
  if ((now - lastIsrTime[4]) < isrDebounceMicros) return;
  lastIsrTime[4] = now;
  int newOut = !digitalRead(rele4);
  digitalWrite(rele4, newOut);
  relay4State = (digitalRead(rele4) == LOW);
  blynkPending[4] = true;
}

void processPendingBlynkUpdates() {
  if (blynkPending[0]) { Blynk.virtualWrite(V3, relay0State ? 1 : 0); blynkPending[0] = false; }
  if (blynkPending[1]) { Blynk.virtualWrite(V6, relay1State ? 1 : 0); blynkPending[1] = false; }
  if (blynkPending[2]) { Blynk.virtualWrite(V7, relay2State ? 1 : 0); blynkPending[2] = false; }
  if (blynkPending[3]) { Blynk.virtualWrite(V8, relay3State ? 1 : 0); blynkPending[3] = false; }
  if (blynkPending[4]) { Blynk.virtualWrite(V9, relay4State ? 1 : 0); blynkPending[4] = false; }
}

//------------------------------------------------------------------------------
// Configuração dos pinos dos interruptores manuais:
// INPUT_PULLUP ativa uma resistência interna que puxa o pino para HIGH quando o interruptor está aberto.
// Ligar um lado do interruptor ao pino GPIO e o outro lado ao GND.
// Quando o interruptor é pressionado ele conecta o pino ao GND → leitura LOW (queda/falling edge).
// O código usa debounce e detecta a borda de descida (LOW estável) para gerar um evento de pressionamento e alternar o relé.
// Observação importante sobre relés ativos-LOW
// O módulo de relés está em active LOW (no código, Blynk liga com digitalWrite(rele, LOW)).
// Ao alternar o pino elétrico (HIGH/LOW) é preciso converter para um "estado lógico" (ON quando o pino está LOW) antes de enviar para o Blynk — caso contrário o UI ficará invertido.
//------------------------------------------------------------------------------
void readSwitches() {
  for (int i = 0; i < 5; i++) {
    int reading = digitalRead(switchPins[i]);
    if (reading != switchRawState[i]) {
      switchRawState[i] = reading;
      lastDebounceTime[i] = millis();
    }
    if ((millis() - lastDebounceTime[i]) > debounceDelay) {
      if (switchStableState[i] != switchRawState[i]) {
        switchStableState[i] = switchRawState[i];
        // borda de descida = botão pressionado (INPUT_PULLUP)
        if (switchStableState[i] == LOW) {
          // alterna o nível elétrico do relé (HIGH/LOW)
          int newOutput = !digitalRead(relayPins[i]);
          digitalWrite(relayPins[i], newOutput);
          // converte para estado lógico: true = ligado (ON) quando o módulo é ACTIVE LOW
          bool logicalState = (digitalRead(relayPins[i]) == LOW);
          // atualiza variáveis de estado de relé
          switch(i) {
            case 0: relay0State = logicalState; break;
            case 1: relay1State = logicalState; break;
            case 2: relay2State = logicalState; break;
            case 3: relay3State = logicalState; break;
            case 4: relay4State = logicalState; break;
          }
          // atualiza Blynk com 1 = ligado, 0 = desligado
          Blynk.virtualWrite(vPins[i], logicalState ? 1 : 0);
        }
      }
    }
  }
}
// --- FIM: pinos e variáveis para interruptores manuais ---

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

BlynkTimer timer;

DHT dht(DHT_PIN, DHT22);

#define INTERVAL 1000L

// Configuração do servidor NTP
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -4 * 3600; // GMT offset para Cuiabá, Mato Grosso
const int daylightOffset_sec = 0; // Horário de verão desativado
// Start cliente NTP
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, ntpServer, gmtOffset_sec, daylightOffset_sec);



void all_SwitchOff(){
  relay0State = 0; digitalWrite(rele0, HIGH); Blynk.virtualWrite(V5, relay0State); delay(1000);
  relay1State = 0; digitalWrite(rele1, HIGH); Blynk.virtualWrite(V6, relay1State); delay(1000);
  relay2State = 0; digitalWrite(rele2, HIGH); Blynk.virtualWrite(V7, relay2State); delay(1000);
  relay3State = 0; digitalWrite(rele3, HIGH); Blynk.virtualWrite(V8, relay3State); delay(1000);
  relay4State = 0; digitalWrite(rele4, HIGH); Blynk.virtualWrite(V9, relay4State); delay(1000);
}

BLYNK_WRITE(V3) {
  int pin0Value = param.asInt();
  if (pin0Value == 1) {
    digitalWrite(rele0, LOW);
  } else {
    digitalWrite(rele0, HIGH);
  }
}
BLYNK_WRITE(V6) {
  int pin1Value = param.asInt();
  if (pin1Value == 1) {
    digitalWrite(rele1, LOW);
  } else {
    digitalWrite(rele1, HIGH);
  }
}

BLYNK_WRITE(V7) {
  int pin2Value = param.asInt();
  if (pin2Value == 1) {
    digitalWrite(rele2, LOW);
  } else {
    digitalWrite(rele2, HIGH);
  }
}

BLYNK_WRITE(V8) {
  int pin3Value = param.asInt();
  if (pin3Value == 1) {
    digitalWrite(rele3, LOW);
  } else {
    digitalWrite(rele3, HIGH);
  }
}

BLYNK_WRITE(V9) {
  int pin4Value = param.asInt();
  if (pin4Value == 1) {
    digitalWrite(rele4, LOW);
  } else {
    digitalWrite(rele4, HIGH);
  }
}

BLYNK_WRITE(V10) {
  int mestreValue = param.asInt();
  if (mestreValue == 1) {
    // Ligar todos os relés
    digitalWrite(rele0, LOW);
    digitalWrite(rele1, LOW);
    digitalWrite(rele2, LOW);
    digitalWrite(rele3, LOW);
    digitalWrite(rele4, LOW);
    Blynk.virtualWrite(V3, 1);
    Blynk.virtualWrite(V6, 1);
    Blynk.virtualWrite(V7, 1);
    Blynk.virtualWrite(V8, 1);
    Blynk.virtualWrite(V9, 1);
  } else {
    // Desligar todos os relés
    digitalWrite(rele0, HIGH);
    digitalWrite(rele1, HIGH);
    digitalWrite(rele2, HIGH);
    digitalWrite(rele3, HIGH);
    digitalWrite(rele4, HIGH);
    Blynk.virtualWrite(V3, 0);
    Blynk.virtualWrite(V6, 0);
    Blynk.virtualWrite(V7, 0);
    Blynk.virtualWrite(V8, 0);
    Blynk.virtualWrite(V9, 0);
  }
}


void mSensores()
{
 
// Obter leituras do sensor DHT22
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  Blynk.virtualWrite(V4, String(temperature));
  Blynk.virtualWrite(V5, String(humidity));

}


void setup()
{
  //WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  dht.begin();

  // Conectar WiFi manualmente com timeout (debug no Serial)
  WiFi.mode(WIFI_STA);
  Serial.print("[WiFi] Conectando em: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  unsigned long wifiStart = millis();
  const unsigned long wifiTimeout = 20000UL; // 20 s
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < wifiTimeout) {
    Serial.print('.');
    delay(500);
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("[WiFi] Conectado, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("[WiFi] Falha ao conectar dentro do timeout.");
    // Faz scan para ajudar a diagnosticar (SSID visível?)
    Serial.println("[WiFi] Escaneando redes...");
    int n = WiFi.scanNetworks();
    Serial.printf("[WiFi] %d redes encontradas:\n", n);
    for (int i = 0; i < n; ++i) {
      Serial.printf("  %d: %s (RSSI %d) %s\n", i, WiFi.SSID(i).c_str(), WiFi.RSSI(i),
                    (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "[OPEN]" : "");
    }
  }

  // Configura e tenta conectar Blynk apenas se WiFi ok
  Blynk.config(auth);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[Blynk] Tentando conectar...");
    if (Blynk.connect(5000)) Serial.println("[Blynk] Conectado");
    else Serial.println("[Blynk] Falha ao conectar (timeout)");
  } else {
    Serial.println("[Blynk] WiFi não conectado — pulando conexão com Blynk");
  }

  // Inicializar o cliente NTP e sincroniza a data e hora (somente com WiFi)
  timeClient.begin();
  if (WiFi.status() == WL_CONNECTED) timeClient.update();

  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Endereço 0x3C para 128x64
    Serial.println(F("Falha na alocação do SSD1306"));
    for(;;);
  }

  display.display();
  delay(2000);
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  pinMode(rele0, OUTPUT);
  pinMode(rele1, OUTPUT);
  pinMode(rele2, OUTPUT);
  pinMode(rele3, OUTPUT);
  pinMode(rele4, OUTPUT);
  digitalWrite(rele0, relay0State);
  digitalWrite(rele1, relay1State);
  digitalWrite(rele2, relay2State);
  digitalWrite(rele3, relay3State);
  digitalWrite(rele4, relay4State);

  // configura os pinos dos interruptores como INPUT_PULLUP
  for (int i = 0; i < 5; i++) {
    pinMode(switchPins[i], INPUT_PULLUP);
    switchRawState[i] = digitalRead(switchPins[i]);
    switchStableState[i] = switchRawState[i];
    lastDebounceTime[i] = 0;
  }

  // configura ISRs para os interruptores (bordas de descida)
    // Anexar interrupções para resposta instantânea (queda = pressionado)
  attachInterrupt(digitalPinToInterrupt(SW0), isr_switch0, FALLING);
  attachInterrupt(digitalPinToInterrupt(SW1), isr_switch1, FALLING);
  attachInterrupt(digitalPinToInterrupt(SW2), isr_switch2, FALLING);
  attachInterrupt(digitalPinToInterrupt(SW3), isr_switch3, FALLING);
  attachInterrupt(digitalPinToInterrupt(SW4), isr_switch4, FALLING);

  timer.setInterval(INTERVAL, mSensores);

  // adiciona verificação periódica dos interruptores (50 ms recomendado)
  timer.setInterval(50L, readSwitches);
}

void loop()
{
  // Atualizar data e hora do cliente NTP a cada 60 segundos
  timeClient.update();
  // Obtem a data e hora local
  time_t rawTime = timeClient.getEpochTime();
  struct tm *timeInfo = gmtime(&rawTime);
  
  // Formata a data
  char formattedDate[20];
  strftime(formattedDate, sizeof(formattedDate), "%d/%m/%Y", timeInfo);

  // Formata a hora
  char formattedTime[20];
  strftime(formattedTime, sizeof(formattedTime), "%H:%M:%S", timeInfo);

    display.clearDisplay();
    display.setCursor(0, 0);
    display.print("FSS Automacao");
    display.setCursor(0, 9);
    display.println(formattedDate);
    display.setCursor(70, 9);
    display.println(formattedTime);
    display.setCursor(0, 19);
    display.print("Temp:");
    display.setCursor(0, 30);
    display.print(dht.readTemperature(), 2);
    display.print(" C");
    display.setCursor(64, 19);
    display.print("Umidade:");
    display.setCursor(64, 30);
    display.print(dht.readHumidity(), 2);
    display.display();
    delay(1000);

  processPendingBlynkUpdates();
  Blynk.run();
  timer.run();
}
