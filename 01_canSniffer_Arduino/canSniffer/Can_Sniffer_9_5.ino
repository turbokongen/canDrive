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

MCP_CAN CAN(P_BUS_CS_PIN);

typedef struct {
  uint32_t id;
  uint8_t dlc;
  uint8_t dataArray[8];
  bool rtr;
  bool ide;
} packet_t;

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
    packet_t testPacket = {};
    testPacket.id = 0x430;
    testPacket.ide = 0;
    testPacket.rtr = 0;
    testPacket.dlc = 8;
    byte d[] = {0x80, 0x40, 0, 0, 0, 0, 0, 0};
    memcpy(testPacket.dataArray, d, 8);
    printPacket(&testPacket);
    sendPacketToCan(&testPacket);
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
  }
#endif
}
