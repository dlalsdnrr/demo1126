#include <Dynamixel2Arduino.h>

// Control table item 이름을 사용하기 위한 네임스페이스
using namespace ControlTableItem;

// 사용하는 포트에 맞게 설정해주세요.
#define DXL_SERIAL    Serial3
const int DXL_DIR_PIN = 22;

// PC와 통신할 시리얼 포트 (USB)
#define PC_SERIAL Serial

// 제어할 다이나믹셀 ID들을 배열로 관리
// 수정됨: 6개의 모터 ID (25, 50, 75, 100, 125, 150)
const uint8_t DXL_IDS[] = {25, 50, 75, 100, 125, 150};
// 수정됨: 모터 개수 (6개)
const int NUM_MOTORS = sizeof(DXL_IDS) / sizeof(DXL_IDS[0]);
const float DXL_PROTOCOL_VERSION = 2.0;

Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);

char command_buffer[50];
bool command_received = false;

void setup() {
  PC_SERIAL.begin(115200);
  while(!PC_SERIAL);
  PC_SERIAL.println("Arduino is ready. Waiting for commands from Flask API...");

  dxl.begin(57600);
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);

  // 배열에 있는 모든 모터 초기화
  for (int i = 0; i < NUM_MOTORS; i++) {
    uint8_t motor_id = DXL_IDS[i];
    
    // 모터가 실제로 연결되어 있는지 확인
    if (dxl.ping(motor_id)) {
        dxl.setOperatingMode(motor_id, OP_POSITION);
        dxl.torqueOn(motor_id);
        PC_SERIAL.print("Motor ID ");
        PC_SERIAL.print(motor_id);
        PC_SERIAL.println(" initialized successfully.");
    } else {
        PC_SERIAL.print("Error: Could not ping Motor ID ");
        PC_SERIAL.print(motor_id);
        PC_SERIAL.println(". Check connection and power.");
    }
  }
}

void loop() {
  if (command_received) {
    parseAndExecuteCommand();
    command_received = false;
  }
}

// 시리얼 이벤트는 변경할 필요 없이 그대로 사용합니다.
void serialEvent() {
  static byte index = 0;
  while (PC_SERIAL.available() > 0) {
    char received_char = PC_SERIAL.read();
    if (received_char == '\n') {
      command_buffer[index] = '\0';
      index = 0;
      command_received = true;
    } else {
      command_buffer[index] = received_char;
      if (index < sizeof(command_buffer) - 1) {
        index++;
      }
    }
  }
}

// 수신된 "ID,위치,속도" 문자열을 분석하고 실행하는 함수
void parseAndExecuteCommand() {
  // strtok는 내부적으로 버퍼를 수정하므로, 복사본을 만들어 사용 (안정성 향상)
  char temp_buffer[50];
  strncpy(temp_buffer, command_buffer, sizeof(temp_buffer) - 1);
  temp_buffer[sizeof(temp_buffer) - 1] = '\0'; // 안전을 위해 null 종료

  // 첫 번째 토큰(ID) 분리
  char* id_token = strtok(temp_buffer, ",");
  if (id_token == NULL) return;
  int motor_id = atoi(id_token);

  // 두 번째 토큰(위치) 분리
  char* pos_token = strtok(NULL, ",");
  if (pos_token == NULL) return;
  int position = atoi(pos_token);

  // 세 번째 토큰(속도) 분리
  char* speed_token = strtok(NULL, ",");
  if (speed_token == NULL) return;
  int speed = atoi(speed_token);

  // ID가 유효한지 확인
  bool is_valid_id = false;
  for (int i = 0; i < NUM_MOTORS; i++) {
    if (motor_id == DXL_IDS[i]) {
      is_valid_id = true;
      break;
    }
  }

  if (!is_valid_id) {
    PC_SERIAL.print("Error: Unknown Motor ID (");
    PC_SERIAL.print(motor_id);
    PC_SERIAL.println(").");
    return;
  }
  
  // 먼저 속도를 설정한 후, 목표 위치로 이동 명령을 내립니다.
  PC_SERIAL.print("Command Received -> ID: ");
  PC_SERIAL.print(motor_id);
  PC_SERIAL.print(", Position: ");
  PC_SERIAL.print(position);
  PC_SERIAL.print(", Speed: ");
  PC_SERIAL.println(speed);

  // 프로파일 속도 설정
  if (!dxl.writeControlTableItem(PROFILE_VELOCITY, motor_id, speed)) {
     PC_SERIAL.print("Error: Failed to set PROFILE_VELOCITY for ID ");
     PC_SERIAL.println(motor_id);
     return;
  }
  
  // 목표 위치 설정
  if (!dxl.setGoalPosition(motor_id, position)) {
     PC_SERIAL.print("Error: Failed to set GoalPosition for ID ");
     PC_SERIAL.println(motor_id);
     return;
  }
}