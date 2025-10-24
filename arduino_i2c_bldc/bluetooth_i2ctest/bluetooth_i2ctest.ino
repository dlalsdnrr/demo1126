#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// 명령 수신용
String command = "";

// BLDC 제어 핀 설정 (테스트 코드 기준)
#define LEFT_PWM   6   // 왼쪽 바퀴 PWM
#define LEFT_DIR   7   // 왼쪽 바퀴 방향
#define RIGHT_PWM  5   // 오른쪽 바퀴 PWM
#define RIGHT_DIR  4   // 오른쪽 바퀴 방향

int motorSpeed = 50; // 모터 속도 (0~255)

// 브레이크 설정: 역토크 유지 시간 및 강도
const int BRAKE_PWM = 200;   // 브레이크 시 인가할 PWM (역토크)
const int BRAKE_MS  = 150;   // 역토크 유지 시간(ms)

// 마지막 구동 명령 추적 (브레이크 방향 결정을 위함)
// 0: none, 1: front, 2: back, 3: left, 4: right
volatile int lastCommand = 0;

// ===================================================
// 🔹 센서 관련 변수
// ===================================================
int16_t accX_raw, accY_raw, accZ_raw;
int16_t gyroX_raw, gyroY_raw, gyroZ_raw;
float angleX = 0, angleY = 0, angleZ = 0;
unsigned long prevTime = 0;

// 🔹 자이로 오프셋
float gyroX_offset = 0;
float gyroY_offset = 0;
float gyroZ_offset = 0;

// 🔹 마지막 명령 수신 시각
unsigned long lastCommandTime = 0;
bool commandReceived = false;  // 명령 수신 여부

// ===================================================
// 🔹 자이로 오프셋 자동 보정
// ===================================================
void calibrateGyro() {
  Serial.println("Calibrating gyro... Keep sensor still!");

  long gx_sum = 0, gy_sum = 0, gz_sum = 0;
  const int samples = 1000;

  for (int i = 0; i < samples; i++) {
    mpu.getRotation(&gyroX_raw, &gyroY_raw, &gyroZ_raw);
    gx_sum += gyroX_raw;
    gy_sum += gyroY_raw;
    gz_sum += gyroZ_raw;
    delay(3);
  }

  gyroX_offset = gx_sum / (float)samples;
  gyroY_offset = gy_sum / (float)samples;
  gyroZ_offset = gz_sum / (float)samples;

  Serial.println("Gyro calibration complete!");
}

// ===================================================
// 🔹 초기 설정
// ===================================================
void setup() {
  Serial.begin(9600);

  // I2C 슬레이브 (라즈베리파이 통신용)
  Wire.begin(0x08);
  Wire.onReceive(receiveEvent);

  // MPU6050 초기화
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("MPU6050 connection failed!");
    while (1);
  }
  Serial.println("MPU6050 connected!");

  calibrateGyro();

  // 모터 핀 출력 설정
  pinMode(LEFT_PWM, OUTPUT);
  pinMode(LEFT_DIR, OUTPUT);
  pinMode(RIGHT_PWM, OUTPUT);
  pinMode(RIGHT_DIR, OUTPUT);

  prevTime = millis();

  Serial.println("System ready!");
}

// ===================================================
// 🔹 메인 루프
// ===================================================
void loop() {
  unsigned long currTime = millis();
  float dt = (currTime - prevTime) / 1000.0;
  prevTime = currTime;

  // MPU6050 데이터 읽기
  mpu.getMotion6(&accX_raw, &accY_raw, &accZ_raw, &gyroX_raw, &gyroY_raw, &gyroZ_raw);

  // 오프셋 적용
  float gyroX = (gyroX_raw - gyroX_offset) / 131.0;
  float gyroY = (gyroY_raw - gyroY_offset) / 131.0;
  float gyroZ = (gyroZ_raw - gyroZ_offset) / 131.0;

  // 각도 적분
  angleX += gyroX * dt;
  angleY += gyroY * dt;
  angleZ += gyroZ * dt;

  // 범위 조정
  if (angleX > 360) angleX -= 360;
  if (angleX < -360) angleX += 360;
  if (angleY > 360) angleY -= 360;
  if (angleY < -360) angleY += 360;
  if (angleZ > 360) angleZ -= 360;
  if (angleZ < -360) angleZ += 360;

  // 출력
  Serial.print("Angle X: "); Serial.print(angleX, 2);
  Serial.print("  Y: "); Serial.print(angleY, 2);
  Serial.print("  Z: "); Serial.println(angleZ, 2);

  // 🔹 명령이 들어오지 않으면 정지 유지
  if (commandReceived) {
    if (millis() - lastCommandTime > 200) {  // 0.2초 동안 새 명령이 없으면
      stopMotors();
      commandReceived = false;
      Serial.println("No command → Stop motors");
    }
  }

  delay(50);
}

// ===================================================
// 🔹 라즈베리파이 → I2C 명령 수신
// ===================================================
void receiveEvent(int howMany) {
  command = "";
  while (Wire.available()) {
    char c = Wire.read();
    command += c;
  }
  command.trim();

  Serial.print("Received command: ");
  Serial.println(command);

  lastCommandTime = millis();
  commandReceived = true;

  if (command == "front") {
    moveForward();
  } else if (command == "left") {
    turnLeft();
  } else if (command == "right") {
    turnRight();
  } else if (command == "back") {
    moveBackward();
  } else if (command == "stop") { // stop = brake
    applyBrake();
  } else {
    stopMotors();
  }
}

// ===================================================
// 🔹 BLDC 제어 함수들
// ===================================================
void moveForward() {
  Serial.println("Move Forward");
  digitalWrite(LEFT_DIR, HIGH);   // 방향 반전됨 (전진)
  digitalWrite(RIGHT_DIR, HIGH);  // 방향 반전됨 (전진)
  analogWrite(LEFT_PWM, motorSpeed);
  analogWrite(RIGHT_PWM, motorSpeed);
  lastCommand = 1;
}

void moveBackward() {
  Serial.println("Move Backward");
  digitalWrite(LEFT_DIR, LOW);    // 반대방향 (후진)
  digitalWrite(RIGHT_DIR, LOW);   // 반대방향 (후진)
  analogWrite(LEFT_PWM, motorSpeed);
  analogWrite(RIGHT_PWM, motorSpeed);
  lastCommand = 2;
}

void turnLeft() {
  Serial.println("Turn Left");
  digitalWrite(LEFT_DIR, LOW);
  digitalWrite(RIGHT_DIR, HIGH);
  analogWrite(LEFT_PWM, motorSpeed);
  analogWrite(RIGHT_PWM, motorSpeed);
  lastCommand = 3;
}

void turnRight() {
  Serial.println("Turn Right");
  digitalWrite(LEFT_DIR, HIGH);
  digitalWrite(RIGHT_DIR, LOW);
  analogWrite(LEFT_PWM, motorSpeed);
  analogWrite(RIGHT_PWM, motorSpeed);
  lastCommand = 4;
}

void stopMotors() {
  analogWrite(LEFT_PWM, 0);
  analogWrite(RIGHT_PWM, 0);
}

// 간이 브레이크: 직전 구동의 반대 토크를 짧게 인가한 뒤 정지
void applyBrake() {
  Serial.println("Brake");
  if (lastCommand == 1) { // forward → brief backward
    digitalWrite(LEFT_DIR, LOW);
    digitalWrite(RIGHT_DIR, LOW);
    analogWrite(LEFT_PWM, BRAKE_PWM);
    analogWrite(RIGHT_PWM, BRAKE_PWM);
    delay(BRAKE_MS);
  } else if (lastCommand == 2) { // backward → brief forward
    digitalWrite(LEFT_DIR, HIGH);
    digitalWrite(RIGHT_DIR, HIGH);
    analogWrite(LEFT_PWM, BRAKE_PWM);
    analogWrite(RIGHT_PWM, BRAKE_PWM);
    delay(BRAKE_MS);
  } else if (lastCommand == 3) { // left → brief right torque
    digitalWrite(LEFT_DIR, HIGH);
    digitalWrite(RIGHT_DIR, LOW);
    analogWrite(LEFT_PWM, BRAKE_PWM);
    analogWrite(RIGHT_PWM, BRAKE_PWM);
    delay(BRAKE_MS);
  } else if (lastCommand == 4) { // right → brief left torque
    digitalWrite(LEFT_DIR, LOW);
    digitalWrite(RIGHT_DIR, HIGH);
    analogWrite(LEFT_PWM, BRAKE_PWM);
    analogWrite(RIGHT_PWM, BRAKE_PWM);
    delay(BRAKE_MS);
  }
  stopMotors();
  lastCommand = 0;
}
