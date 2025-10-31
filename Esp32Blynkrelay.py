//------------------------------------------------------------------------------
// Auth Token are provided by the Blynk.Cloud
// BOARD ESP32 DEVKIT V1 30 PINS
//------------------------------------------------------------------------------

#define BLYNK_TEMPLATE_ID "TMPL2b-PiE3H-"
#define BLYNK_TEMPLATE_NAME "Rastreamento"
#define BLYNK_AUTH_TOKEN "_Cm7fdhv3ndn2LobfQwCxsgn4cTNxO1d"

char auth[] = BLYNK_AUTH_TOKEN;


char ssid[64] = "WL_AUTOMAC";
char password[64] = "47018693";


#define BLYNK_PRINT Serial
//#include "soc/soc.h"
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
// Web/Storage
#include <WebServer.h>
#include <Preferences.h>


#define DEFAULT_RELE0 25
#define DEFAULT_RELE1 13
#define DEFAULT_RELE2 18
#define DEFAULT_RELE3 19
#define DEFAULT_RELE4 14
#define DHT_PIN 4
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// --- INÍCIO: pinos e variáveis para interruptores manuais ---
#define DEFAULT_SW0 23
#define DEFAULT_SW1 26
#define DEFAULT_SW2 32
#define DEFAULT_SW3 33
#define DEFAULT_SW4 27

// Arrays configuráveis (podem ser carregados/salvos em Preferences)
int switchPins[5] = { DEFAULT_SW0, DEFAULT_SW1, DEFAULT_SW2, DEFAULT_SW3, DEFAULT_SW4 };
int relayPins[5]  = { DEFAULT_RELE0, DEFAULT_RELE1, DEFAULT_RELE2, DEFAULT_RELE3, DEFAULT_RELE4 };
const int vPins[5] = { V3, V6, V7, V8, V9 };

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
  int newOut = !digitalRead(relayPins[0]);
  digitalWrite(relayPins[0], newOut);
  relay0State = (digitalRead(relayPins[0]) == LOW);
  blynkPending[0] = true;
}
IRAM_ATTR void isr_switch1() {
  unsigned long now = micros();
  if ((now - lastIsrTime[1]) < isrDebounceMicros) return;
  lastIsrTime[1] = now;
  int newOut = !digitalRead(relayPins[1]);
  digitalWrite(relayPins[1], newOut);
  relay1State = (digitalRead(relayPins[1]) == LOW);
  blynkPending[1] = true;
}
IRAM_ATTR void isr_switch2() {
  unsigned long now = micros();
  if ((now - lastIsrTime[2]) < isrDebounceMicros) return;
  lastIsrTime[2] = now;
  int newOut = !digitalRead(relayPins[2]);
  digitalWrite(relayPins[2], newOut);
  relay2State = (digitalRead(relayPins[2]) == LOW);
  blynkPending[2] = true;
}
IRAM_ATTR void isr_switch3() {
  unsigned long now = micros();
  if ((now - lastIsrTime[3]) < isrDebounceMicros) return;
  lastIsrTime[3] = now;
  int newOut = !digitalRead(relayPins[3]);
  digitalWrite(relayPins[3], newOut);
  relay3State = (digitalRead(relayPins[3]) == LOW);
  blynkPending[3] = true;
}
IRAM_ATTR void isr_switch4() {
  unsigned long now = micros();
  if ((now - lastIsrTime[4]) < isrDebounceMicros) return;
  lastIsrTime[4] = now;
  int newOut = !digitalRead(relayPins[4]);
  digitalWrite(relayPins[4], newOut);
  relay4State = (digitalRead(relayPins[4]) == LOW);
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

WebServer server(80);
Preferences prefs;

// Página HTML embutida (simples, responsiva)
const char index_html[] PROGMEM = R"rawliteral(
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Configuração WiFi / GPIO</title>
  <style>
    body{font-family:Inter,system-ui,Segoe UI,Roboto,Arial;margin:0;padding:0;background:#0f172a;color:#e6eef8}
    .card{max-width:720px;margin:24px auto;padding:20px;background:#0b1220;border-radius:12px;box-shadow:0 6px 20px rgba(2,6,23,.6)}
    h1{font-size:20px;margin:0 0 12px}
    label{display:block;margin-top:12px;font-size:13px}
    select,input{width:100%;padding:8px;border-radius:8px;border:1px solid #243044;background:#071022;color:#e6eef8}
    button{margin-top:14px;padding:10px 14px;border-radius:8px;border:none;background:#0ea5a4;color:#022;cursor:pointer}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .small{font-size:12px;color:#9fb0c8}
    footer{max-width:720px;margin:8px auto;text-align:center;color:#6f8aa3;font-size:12px}
    /* abas */
    .tab { background:#1b2b3a;color:#e6eef8;border-radius:8px;padding:8px;border:1px solid #243044;cursor:pointer }
    .tab.active { background:#0ea5a4;color:#022 }
  </style>
</head>
<body>
  <div class="card">
    <h1>Configurar Wi‑Fi e GPIOs</h1>
    <div class="small">Escolha a rede, informe a senha e remapeie pinos conforme necessário.</div>
    <div style="display:flex;gap:8px;margin:16px 0 12px 0;">
      <button id="tab-wifi" class="tab active" style="flex:1;">Wi-Fi</button>
      <button id="tab-gpio" class="tab" style="flex:1;">GPIOs</button>
    </div>
    <div id="tab-content-wifi">
      <label>Redes disponíveis</label>
      <select id="ssid"></select>
      <label>Senha</label>
      <input id="pass" type="password" placeholder="Senha da rede" />
      <div class="row"><button id="scan">Escanear redes</button><button id="save">Salvar e Conectar</button></div>
      <div id="status" class="small"></div>
    </div>
    <div id="tab-content-gpio" style="display:none;">
      <label>Mapeamento de relés</label>
      <div id="relays"></div>
      <label>Mapeamento de chaves</label>
      <div id="switches"></div>
      <div class="row"><button id="scan-gpio">Escanear redes</button><button id="save-gpio">Salvar e Conectar</button></div>
    </div>
  </div>
  <footer>Dispositivo ESP32 — configuração local</footer>
  <script>
    const pins = [2,4,5,12,13,14,15,16,17,18,19,21,22,23,25,26,27,32,33,34,35,36,39];
    function el(tag,html){const e=document.createElement(tag);if(html)e.innerHTML=html;return e}
    async function scan(){
      const statusEl = document.getElementById('status');
      statusEl.textContent='Escaneando...';
      try {
        const r = await fetch('/scan');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const list = await r.json();
        const sel = document.getElementById('ssid'); sel.innerHTML='';
        if (!Array.isArray(list) || list.length === 0) {
          statusEl.textContent = 'Nenhuma rede encontrada.';
          return [];
        }
        list.forEach(s=>{const o=document.createElement('option');o.value=s; o.textContent=s; sel.appendChild(o)});
        statusEl.textContent='Redes carregadas.';
        return list;
      } catch (err) {
        statusEl.textContent = 'Erro ao escanear: ' + err.message;
        return [];
      }
    }
    async function loadCurrent(){
      const r=await fetch('/current');
      const j=await r.json();
      if(j.ssid) document.getElementById('ssid').value=j.ssid;
      if(j.pass) document.getElementById('pass').value=j.pass;
      const relDiv=document.getElementById('relays'); relDiv.innerHTML='';
      j.relays.forEach((p,i)=>{const lbl=el('label','Relé '+(i+1)); const sel=document.createElement('select'); pins.forEach(pin=>{const o=document.createElement('option');o.value=pin;o.textContent=pin; if(pin==p) o.selected=true; sel.appendChild(o)}); relDiv.appendChild(lbl); relDiv.appendChild(sel)});
      const swDiv=document.getElementById('switches'); swDiv.innerHTML='';
      j.switches.forEach((p,i)=>{const lbl=el('label','Chave '+(i+1)); const sel=document.createElement('select'); pins.forEach(pin=>{const o=document.createElement('option');o.value=pin;o.textContent=pin; if(pin==p) o.selected=true; sel.appendChild(o)}); swDiv.appendChild(lbl); swDiv.appendChild(sel)});
    }
    // Abas
    document.getElementById('tab-wifi').addEventListener('click', function(){
      document.getElementById('tab-wifi').classList.add('active');
      document.getElementById('tab-gpio').classList.remove('active');
      document.getElementById('tab-content-wifi').style.display='block';
      document.getElementById('tab-content-gpio').style.display='none';
    });
    document.getElementById('tab-gpio').addEventListener('click', function(){
      document.getElementById('tab-gpio').classList.add('active');
      document.getElementById('tab-wifi').classList.remove('active');
      document.getElementById('tab-content-gpio').style.display='block';
      document.getElementById('tab-content-wifi').style.display='none';
    });
    // event listeners
    document.getElementById('scan').addEventListener('click', ()=>scan());
    document.getElementById('scan-gpio').addEventListener('click', ()=>{
      // foco para a aba wifi antes de exibir redes (opcional)
      document.getElementById('tab-wifi').click();
      scan();
    });

    async function doSave(){
      const ssid=document.getElementById('ssid').value; const pass=document.getElementById('pass').value;
      const rels=[...document.getElementById('relays').querySelectorAll('select')].map(s=>parseInt(s.value));
      const sws=[...document.getElementById('switches').querySelectorAll('select')].map(s=>parseInt(s.value));
      document.getElementById('status').textContent='Salvando...';
      try {
        const res=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid,pass,relays:rels,switches:sws})});
        const j=await res.json(); document.getElementById('status').textContent=j.status;
      } catch (err) {
        document.getElementById('status').textContent = 'Erro ao salvar: ' + err.message;
      }
    }
    document.getElementById('save').addEventListener('click', doSave);
    document.getElementById('save-gpio').addEventListener('click', doSave);
    // Carrega primeiro a configuração atual (para mostrar SSID salvo), não escaneia redes automaticamente
    window.addEventListener('load', async ()=>{ await loadCurrent(); });
  </script>
</body>
</html>
)rawliteral";

// forward declarations for functions defined below but used in setup()
String intsToCsv(const int *arr, int n);
int csvToInts(const String &csv, int *out, int maxOut);
void loadConfigFromPrefs();
void saveConfigToPrefs(const String &nssid, const String &npass);
void handleRoot();
void handleScan();
void handleCurrent();
void handleSave();

BlynkTimer timer;

// Flag para controlar se devemos rodar Blynk.run() (só quando conectado à internet)
bool blynkActive = false;

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
  relay0State = 0; digitalWrite(relayPins[0], HIGH); Blynk.virtualWrite(V5, relay0State); delay(1000);
  relay1State = 0; digitalWrite(relayPins[1], HIGH); Blynk.virtualWrite(V6, relay1State); delay(1000);
  relay2State = 0; digitalWrite(relayPins[2], HIGH); Blynk.virtualWrite(V7, relay2State); delay(1000);
  relay3State = 0; digitalWrite(relayPins[3], HIGH); Blynk.virtualWrite(V8, relay3State); delay(1000);
  relay4State = 0; digitalWrite(relayPins[4], HIGH); Blynk.virtualWrite(V9, relay4State); delay(1000);
}

BLYNK_WRITE(V3) {
  int pin0Value = param.asInt();
  if (pin0Value == 1) {
    digitalWrite(relayPins[0], LOW);
  } else {
    digitalWrite(relayPins[0], HIGH);
  }
}
BLYNK_WRITE(V6) {
  int pin1Value = param.asInt();
  if (pin1Value == 1) {
    digitalWrite(relayPins[1], LOW);
  } else {
    digitalWrite(relayPins[1], HIGH);
  }
}

BLYNK_WRITE(V7) {
  int pin2Value = param.asInt();
  if (pin2Value == 1) {
    digitalWrite(relayPins[2], LOW);
  } else {
    digitalWrite(relayPins[2], HIGH);
  }
}

BLYNK_WRITE(V8) {
  int pin3Value = param.asInt();
  if (pin3Value == 1) {
    digitalWrite(relayPins[3], LOW);
  } else {
    digitalWrite(relayPins[3], HIGH);
  }
}

BLYNK_WRITE(V9) {
  int pin4Value = param.asInt();
  if (pin4Value == 1) {
    digitalWrite(relayPins[4], LOW);
  } else {
    digitalWrite(relayPins[4], HIGH);
  }
}

BLYNK_WRITE(V10) {
  int mestreValue = param.asInt();
  if (mestreValue == 1) {
    // Ligar todos os relés
    digitalWrite(relayPins[0], LOW);
    digitalWrite(relayPins[1], LOW);
    digitalWrite(relayPins[2], LOW);
    digitalWrite(relayPins[3], LOW);
    digitalWrite(relayPins[4], LOW);
    Blynk.virtualWrite(V3, 1);
    Blynk.virtualWrite(V6, 1);
    Blynk.virtualWrite(V7, 1);
    Blynk.virtualWrite(V8, 1);
    Blynk.virtualWrite(V9, 1);
  } else {
    // Desligar todos os relés
    digitalWrite(relayPins[0], HIGH);
    digitalWrite(relayPins[1], HIGH);
    digitalWrite(relayPins[2], HIGH);
    digitalWrite(relayPins[3], HIGH);
    digitalWrite(relayPins[4], HIGH);
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

// ---------------------- Config storage and Web handlers ----------------------
// salva um array de inteiros como CSV
String intsToCsv(const int *arr, int n) {
  String s = "";
  for (int i=0;i<n;i++) {
    if (i) s += ',';
    s += String(arr[i]);
  }
  return s;
}

// preenche um array de inteiros a partir de CSV (retorna quantos lidos)
int csvToInts(const String &csv, int *out, int maxOut) {
  if (csv.length()==0) return 0;
  int idx = 0;
  int start = 0;
  while (start < (int)csv.length() && idx < maxOut) {
    int comma = csv.indexOf(',', start);
    if (comma == -1) comma = csv.length();
    String token = csv.substring(start, comma);
    token.trim();
    out[idx++] = token.toInt();
    start = comma + 1;
  }
  return idx;
}

void loadConfigFromPrefs() {
  prefs.begin("cfg", true);
  String s = prefs.getString("ssid", "");
  if (s.length()) {
    int c = ((int)s.length()+1 < (int)sizeof(ssid)) ? (int)s.length()+1 : (int)sizeof(ssid);
    s.toCharArray(ssid, c);
  }
  String p = prefs.getString("pass", "");
  if (p.length()) {
    int c2 = ((int)p.length()+1 < (int)sizeof(password)) ? (int)p.length()+1 : (int)sizeof(password);
    p.toCharArray(password, c2);
  }
  String rmap = prefs.getString("relaymap", "");
  if (rmap.length()) csvToInts(rmap, relayPins, 5);
  String smap = prefs.getString("switchmap", "");
  if (smap.length()) csvToInts(smap, switchPins, 5);
  prefs.end();
}

void saveConfigToPrefs(const String &nssid, const String &npass) {
  prefs.begin("cfg", false);
  prefs.putString("ssid", nssid);
  prefs.putString("pass", npass);
  prefs.putString("relaymap", intsToCsv(relayPins, 5));
  prefs.putString("switchmap", intsToCsv(switchPins, 5));
  prefs.end();
}

// Handlers
void handleRoot() {
  server.send_P(200, "text/html", index_html);
}

void handleScan() {
  Serial.println("[HTTP] /scan requested");
  // Alguns modos AP podem impedir scan; temporariamente garantir modo STA para scan
  wifi_mode_t curMode = WiFi.getMode();
  bool hadAP = (curMode & WIFI_AP) != 0;
  if (hadAP) {
    Serial.println("[WiFi] Temporarily ensuring STA available for scan (keeping AP)");
    // use AP+STA mode so we don't drop the AP and disconnect the web client
    WiFi.mode(WIFI_AP_STA);
    delay(100);
  }
  int n = WiFi.scanNetworks();
  Serial.printf("[WiFi] scanNetworks -> %d\n", n);
  String out = "[";
  for (int i=0;i<n;i++) {
    if (i) out += ',';
    out += '"';
    out += WiFi.SSID(i);
    out += '"';
  }
  out += "]";
  // restaurar modo AP+STA se necessário
  // restaurar modo WiFi anterior (evita forçar STA+AP se não estava assim)
  WiFi.mode(curMode);
  delay(50);
  server.send(200, "application/json", out);
}

void handleCurrent() {
  // retorna ssid, pass (curto), relays[], switches[]
  prefs.begin("cfg", true);
  String s = prefs.getString("ssid", String(ssid));
  String p = prefs.getString("pass", String(password));
  String r = prefs.getString("relaymap", intsToCsv(relayPins,5));
  String sw = prefs.getString("switchmap", intsToCsv(switchPins,5));
  prefs.end();
  String out = "{";
  out += "\"ssid\":\"" + s + "\",";
  out += "\"pass\":\"" + p + "\",";
  out += "\"relays\": [";
  for (int i=0;i<5;i++) { if (i) out += ','; out += String(relayPins[i]); }
  out += "],";
  out += "\"switches\": [";
  for (int i=0;i<5;i++) { if (i) out += ','; out += String(switchPins[i]); }
  out += "]}";
  server.send(200, "application/json", out);
}

void handleSave() {
  String body = server.arg("plain");
  // body é JSON: {ssid:"..",pass:"..",relays:[...],switches:[...]}
  // Extração simples (não usa ArduinoJson para manter dependências baixas)
  String nssid = "", npass = "";
  int nRelays[5]; int nSwitches[5];
  for (int i=0;i<5;i++){ nRelays[i]=relayPins[i]; nSwitches[i]=switchPins[i]; }
  int idx;
  idx = body.indexOf("\"ssid\"");
  if (idx!=-1) {
    int q1 = body.indexOf('"', idx+6);
    int q2 = body.indexOf('"', q1+1);
    if (q1!=-1 && q2!=-1) nssid = body.substring(q1+1,q2);
  }
  idx = body.indexOf("\"pass\"");
  if (idx!=-1) {
    int q1 = body.indexOf('"', idx+6);
    int q2 = body.indexOf('"', q1+1);
    if (q1!=-1 && q2!=-1) npass = body.substring(q1+1,q2);
  }
  // relays array
  idx = body.indexOf("\"relays\"");
  if (idx!=-1) {
    int b = body.indexOf('[', idx);
    int e = body.indexOf(']', b);
    if (b!=-1 && e!=-1) {
      String sub = body.substring(b+1,e);
      csvToInts(sub, nRelays, 5);
    }
  }
  idx = body.indexOf("\"switches\"");
  if (idx!=-1) {
    int b = body.indexOf('[', idx);
    int e = body.indexOf(']', b);
    if (b!=-1 && e!=-1) {
      String sub = body.substring(b+1,e);
      csvToInts(sub, nSwitches, 5);
    }
  }
  // Aplicar
  if (nssid.length()) { int c3 = ((int)nssid.length()+1 < (int)sizeof(ssid)) ? (int)nssid.length()+1 : (int)sizeof(ssid); nssid.toCharArray(ssid, c3); }
  if (npass.length()) { int c4 = ((int)npass.length()+1 < (int)sizeof(password)) ? (int)npass.length()+1 : (int)sizeof(password); npass.toCharArray(password, c4); }
  for (int i=0;i<5;i++){ relayPins[i]=nRelays[i]; switchPins[i]=nSwitches[i]; }
  saveConfigToPrefs(nssid, npass);
  // tenta conectar
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  bool ok=false;
  while (millis()-start < 8000) {
    if (WiFi.status()==WL_CONNECTED) { ok=true; break; }
    delay(200);
  }
  String resp = "{\"status\":\"" + String(ok?"connected":"saved") + "\"}";
  server.send(200, "application/json", resp);

  // Se conectou ao WiFi agora, tentar conectar Blynk e ativar blynkActive
  if (ok) {
    Serial.println("[Blynk] Tentando conectar após save...");
    if (Blynk.connect(5000)) {
      Serial.println("[Blynk] Conectado após save");
      blynkActive = true;
    } else {
      Serial.println("[Blynk] Falha ao conectar após save");
      blynkActive = false;
    }
  }
}


void setup()
{
  //WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  dht.begin();

  // Carrega configurações salvas (se existirem)
  loadConfigFromPrefs();

  // Conectar WiFi manualmente com timeout (debug no Serial)
  // Usamos modo AP+STA para permitir fallback a modo AP se a conexão STA falhar
  WiFi.mode(WIFI_AP_STA);
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
    // Se não conectou como STA, desativa reconexão automática e sobe um SoftAP para configuração
    // Isso evita que o ESP fique continuamente tentando reconectar ao STA e gere logs/reciclagem do AP.
    WiFi.disconnect(true);
    WiFi.setAutoReconnect(false);
    delay(100);
    WiFi.mode(WIFI_AP); // garante que ficamos apenas em modo AP
    String apName = String("ESP32-Setup-") + String((uint32_t)(ESP.getEfuseMac() & 0xFFFFFF), HEX);
    const char* apPass = "fssautomacao"; // senha do AP (mínimo 8 caracteres)
    bool ok = WiFi.softAP(apName.c_str(), apPass);
    if (ok) {
      Serial.print("[WiFi] Modo AP ativo: "); Serial.println(apName);
      Serial.print("[WiFi] AP IP: "); Serial.println(WiFi.softAPIP());
    } else {
      Serial.println("[WiFi] Falha ao iniciar SoftAP");
    }
  }

  // Configura e tenta conectar Blynk apenas se WiFi ok
  Blynk.config(auth);
  blynkActive = false;
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[Blynk] Tentando conectar...");
    if (Blynk.connect(5000)) {
      Serial.println("[Blynk] Conectado");
      blynkActive = true;
    } else {
      Serial.println("[Blynk] Falha ao conectar (timeout)");
      blynkActive = false;
    }
  } else {
    Serial.println("[Blynk] WiFi não conectado — pulando conexão com Blynk");
    blynkActive = false;
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

  for (int i = 0; i < 5; i++) {
    pinMode(relayPins[i], OUTPUT);
    // escreve estado inicial (HIGH = desligado no módulo active LOW)
    digitalWrite(relayPins[i], (i==0?relay0State:(i==1?relay1State:(i==2?relay2State:(i==3?relay3State:relay4State)))));
  }

  // configura os pinos dos interruptores como INPUT_PULLUP
  for (int i = 0; i < 5; i++) {
    pinMode(switchPins[i], INPUT_PULLUP);
    switchRawState[i] = digitalRead(switchPins[i]);
    switchStableState[i] = switchRawState[i];
    lastDebounceTime[i] = 0;
  }

  // configura ISRs para os interruptores (bordas de descida)
  attachInterrupt(digitalPinToInterrupt(switchPins[0]), isr_switch0, FALLING);
  attachInterrupt(digitalPinToInterrupt(switchPins[1]), isr_switch1, FALLING);
  attachInterrupt(digitalPinToInterrupt(switchPins[2]), isr_switch2, FALLING);
  attachInterrupt(digitalPinToInterrupt(switchPins[3]), isr_switch3, FALLING);
  attachInterrupt(digitalPinToInterrupt(switchPins[4]), isr_switch4, FALLING);

  timer.setInterval(INTERVAL, mSensores);

  // adiciona verificação periódica dos interruptores (50 ms recomendado)
  timer.setInterval(50L, readSwitches);

  // Inicia servidor web para configuração
  server.on("/", HTTP_GET, handleRoot);
  server.on("/scan", HTTP_GET, handleScan);
  server.on("/current", HTTP_GET, handleCurrent);
  server.on("/save", HTTP_POST, handleSave);
  // Se qualquer rota não for encontrada, retornar a página principal (simples captive behavior)
  server.onNotFound(handleRoot);
  server.begin();
}

void loop()
{
  // Atualizar data e hora do cliente NTP apenas quando conectado
  char formattedDate[20] = "--/--/----";
  char formattedTime[20] = "--:--:--";
  if (WiFi.status() == WL_CONNECTED) {
    // Atualiza o cliente NTP (pode bloquear internamente) e obtém hora
    timeClient.update();
    time_t rawTime = timeClient.getEpochTime();
    struct tm *timeInfo = gmtime(&rawTime);
    // Formata a data
    strftime(formattedDate, sizeof(formattedDate), "%d/%m/%Y", timeInfo);
    // Formata a hora
    strftime(formattedTime, sizeof(formattedTime), "%H:%M:%S", timeInfo);
  }

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
  // Executa Blynk apenas quando ativo (evita tentativas de DNS/conn quando estamos em AP sem internet)
  if (blynkActive) Blynk.run();
  timer.run();
  server.handleClient();

}
