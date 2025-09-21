#include <SPI.h>
#include <mcp_can.h>

#define SEPARATOR ','
#define TERMINATOR '\n'
#define RXBUF_LEN 100
#define RANDOM_CAN 0

const int I_BUS_SPEED = CAN_47K619BPS;
const int P_BUS_SPEED = CAN_500KBPS;
const int GMLAN_SPEED = CAN_33K3BPS;

const int SCK_PIN = 36;
const int MISO_PIN = 37;
const int MOSI_PIN = 35;
const int I_BUS_CS_PIN = 21;
const int P_BUS_CS_PIN = 39;

unsigned long previousMillis = 0;
const long interval = 3000;

// --- KWP2000 / ISO-TP (kun FC) ---
volatile bool kwp2000Enabled = false;   // GUI-bryter: OFF = kun logging, ON = send FC ved FF

// 11-bit standard-IDer (endre hvis bilen din bruker andre)
uint32_t TESTER_TX_ID = 0x7E0;  // Tester -> ECU
uint32_t ECU_RX_ID    = 0x7E8;  // ECU -> Tester

MCP_CAN CAN(P_BUS_CS_PIN);

typedef struct {
  uint32_t id;
  uint8_t dlc;
  uint8_t dataArray[8];
  bool rtr;
  bool ide;
} packet_t;

// Send én Flow Control (CTS, BS=0, STmin=0)
inline void sendFlowControlOnce() {
  uint8_t fc[8] = {0x30, 0x00, 0x00, 0,0,0,0,0};
  // MCP2515-libs (vanlig): sendMsgBuf(id, ext(0=std), len, data)
  CAN.sendMsgBuf(TESTER_TX_ID, 0 /*std 11-bit*/, 8, fc);
}

// Kall denne på ALLE mottatte CAN-rammer (etter at du har logget dem).
// Den gjør KUN én ting: hvis FF (0x10) fra ECU *og* bryter PÅ -> send FC.
inline void handleIsoTp_FCOnly(uint32_t canId, uint8_t dlc, const uint8_t *d) {
  if (!kwp2000Enabled) return;          // Av: aldri send noe
  if (canId != ECU_RX_ID || dlc < 2) return;  // bare fra ECU, og minst 2 byte

  uint8_t pciType = d[0] & 0xF0;        // ISO-TP PCI upper nibble
  if (pciType == 0x10) {                // First Frame (FF)
    // d[0] = 0x1L (L = high nibble av totallengde)
    // d[1] = low byte av totallengde
    sendFlowControlOnce();              // svar raskt (N_Bs ~75 ms typisk)
  }
}

void printPacket(const packet_t* packet) {
  Serial.print(packet->id, HEX);
  Serial.print(SEPARATOR);
  Serial.print(packet->rtr, HEX);
  Serial.print(SEPARATOR);
  Serial.print(packet->ide, HEX);
  Serial.print(SEPARATOR);
  for (int i = 0; i < packet->dlc; i++) {
    if (packet->dataArray[i] < 0x10) Serial.print("0");
    Serial.print(packet->dataArray[i], HEX);
  }
  Serial.print(TERMINATOR);
}

void sendPacketToCan(packet_t* packet) {
#if RANDOM_CAN == 0
  byte dataCopy[8];
  memcpy(dataCopy, packet->dataArray, packet->dlc);

  // MCP_CAN expects the extended and RTR bits inside the ID
  uint32_t can_id = packet->id;
  if (packet->ide) can_id |= 0x80000000;  // Extended frame
  if (packet->rtr) can_id |= 0x40000000;  // Remote request frame

  Serial.print("!SEND ID: 0x");
  Serial.print(can_id, HEX);
  Serial.print(" IDE: ");
  Serial.print(packet->ide);
  Serial.print(" RTR: ");
  Serial.print(packet->rtr);
  Serial.print(" DLC: ");
  Serial.print(packet->dlc);
  Serial.print(" DATA:");
  for (int i = 0; i < packet->dlc; i++) {
   if (dataCopy[i] < 0x10) Serial.print("0");  // fix leading 0
   Serial.print(dataCopy[i], HEX);
   Serial.print(" ");
  }
  Serial.println();

  for (int retries = 10; retries > 0; retries--) {
    byte result = CAN.sendMsgBuf(can_id, packet->dlc, dataCopy);
    if (result == CAN_OK) {
      Serial.println("!SEND OK");
      break;
    } else if (retries <= 1) {
      Serial.print("!SEND FAIL: ");
      Serial.println(result);
    }
  }
#endif
}

char getNum(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return 0;
}

char* strToHex(char* str, byte* hexArray, byte* len) {
  byte* ptr = hexArray;
  char* idx = str;
  *len = 0;

  while (*idx != SEPARATOR && *idx != TERMINATOR && *idx != '\0') {
    if (!isxdigit(*idx)) {
      idx++;
      continue;
    }
    char high = getNum(*idx++);
    if (!isxdigit(*idx)) {
      *ptr++ = (high << 4);
      (*len)++;
      break;
    }
    char low = getNum(*idx++);
    *ptr++ = (high << 4) + low;
    (*len)++;
  }
  return idx;
}

void rxParse(char* buf, int len) {
  // --- NYTT: håndter enkle tekst-kommandoer før CAN-linje ---
  // Stripp CR/LF og gjør en kopi i uppercase for enkel sjekk
  while (len > 0 && (buf[len-1] == '\r' || buf[len-1] == '\n')) len--;
  String s = String(buf).substring(0, len);
  String up = s; up.toUpperCase(); up.trim();

  if (up == "K1") { kwp2000Enabled = true;  Serial.println("!KWP FC: ON");  return; }
  if (up == "K0") { kwp2000Enabled = false; Serial.println("!KWP FC: OFF"); return; }

  if (up.startsWith("IDT ")) {  // f.eks. "IDT 7E0"
    uint32_t v = strtoul(s.c_str() + 4, nullptr, 16);
    TESTER_TX_ID = v; Serial.printf("!IDT=%03X\n", TESTER_TX_ID); return;
  }
  if (up.startsWith("IDE ")) {  // f.eks. "IDE 7E8"
    uint32_t v = strtoul(s.c_str() + 4, nullptr, 16);
    ECU_RX_ID = v;  Serial.printf("!IDE=%03X\n", ECU_RX_ID);     return;
  }
  if (up.startsWith("ID ")) {   // f.eks. "ID 7E0 7E8"
    uint32_t t=0, e=0;
    int n = sscanf(s.c_str()+3, "%x %x", &t, &e);
    if (n == 2) { TESTER_TX_ID = t; ECU_RX_ID = e; Serial.printf("!IDs set: T=%03X E=%03X\n", TESTER_TX_ID, ECU_RX_ID); }
    else        { Serial.println("!PARSE FAIL: ID"); }
    return;
  }
  // --- SLUTT på nye kommandoer, CAN-parsingen under forblir som før ---

  packet_t rxPacket = {};
  char* ptr = buf;
  byte temp[8], tempLen;

  char* endPtr;
  rxPacket.id = strtoul(ptr, &endPtr, 16);
  if (*endPtr != SEPARATOR) {
    Serial.println("!PARSE FAIL: ID");
    return;
  }
  ptr = endPtr + 1;

  ptr = strToHex(ptr, temp, &tempLen);
  rxPacket.rtr = temp[0];
  ptr++;

  ptr = strToHex(ptr, temp, &tempLen);
  rxPacket.ide = temp[0];
  ptr++;

  ptr = strToHex(ptr, rxPacket.dataArray, &rxPacket.dlc);
  if (rxPacket.dlc > 8) {
    Serial.println("!DATA TOO LONG");
    return;
  }

#if RANDOM_CAN == 0
  printPacket(&rxPacket);
  sendPacketToCan(&rxPacket);
#endif
}

void RXcallback(void) {
  static int rxPtr = 0;
  static char rxBuf[RXBUF_LEN];

  while (Serial.available() > 0) {
    if (rxPtr >= RXBUF_LEN) rxPtr = 0;
    char c = Serial.read();
    rxBuf[rxPtr++] = c;
    if (c == TERMINATOR) {
      rxParse(rxBuf, rxPtr);
      rxPtr = 0;
    }
  }
}

void setup() {
  Serial.begin(250000);
  while (!Serial);

#if RANDOM_CAN == 1
  randomSeed(12345);
  Serial.println("!randomCAN Started");
#else
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN);
  pinMode(P_BUS_CS_PIN, OUTPUT);

  if (CAN.begin(MCP_ANY, P_BUS_SPEED, MCP_8MHZ) == CAN_OK) {
    Serial.println("!CAN init OK!");
  } else {
    Serial.println("!CAN init FAILED!");
    while (1);
  }
  CAN.setMode(MCP_NORMAL);
#endif
}

void loop() {
  RXcallback();
#if RANDOM_CAN == 1
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
     // Anta definisjonen av packet_t slik:
  // struct packet_t { uint32_t id; uint8_t ide; uint8_t rtr; uint8_t dlc; uint8_t dataArray[8]; };

  packet_t p = {};

  // Bruk riktige typer (uint32_t for ID, ikke long)
  const uint32_t sampleIdList[] = {
    0x110, 0x18DAF111, 0x23A, 0x257, 0x412F1A1, 0x601, 0x18EA0C11
  };
  const int idCount = sizeof(sampleIdList) / sizeof(sampleIdList[0]);
  const int idIndex = random(idCount);

  p.id  = sampleIdList[idIndex];
  p.ide = (p.id > 0x7FF) ? 1 : 0;   // 29-bit = Extended
  p.rtr = 0;                        // Data frame
  p.dlc = 8;                        // Alltid 8 bytes

  // Fyll nye tilfeldige bytes hver gang (ingen “hengende” tilstand)
  for (int i = 0; i < 8; i++) {
    p.dataArray[i] = (uint8_t)random(256);
  }
  printPacket(&p);

  // Send til CAN
  sendPacketToCan(&p);
}

#else
  if (CAN_MSGAVAIL == CAN.checkReceive()) {
    packet_t rxPacket = {};
    unsigned long rxId;
    byte ext = 0;
    byte len = 0;
    byte buf[8];

    CAN.readMsgBuf(&rxId, &ext, &len, buf);
    rxPacket.id = rxId;
    rxPacket.dlc = len;
    rxPacket.rtr = (rxId & 0x40000000) == 0x40000000;
    rxPacket.ide = ext;

    for (byte i = 0; i < len; i++) {
      rxPacket.dataArray[i] = buf[i];
    }

    printPacket(&rxPacket);
    // 2) Kun dersom KWP-bryter er PÅ: send FC når vi ser FF fra ECU
    handleIsoTp_FCOnly((uint32_t)rxId, (uint8_t)len, buf);
  }
#endif
}
