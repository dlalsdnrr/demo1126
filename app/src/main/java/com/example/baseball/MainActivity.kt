package com.example.baseball

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityCompat
import com.example.baseball.ui.theme.BaseballTheme
import java.util.*
import androidx.compose.ui.Alignment

class MainActivity : ComponentActivity() {

    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bluetoothLeScanner: BluetoothLeScanner? = null
    private var scanCallback: ScanCallback? = null

    // ✅ GATT 통신용 UUID (라즈베리파이와 동일해야 함)
    private val SERVICE_UUID = UUID.fromString("12345678-1234-5678-1234-56789abcdef0")
    private val CHAR_UUID = UUID.fromString("abcdef01-1234-5678-1234-56789abcdef0")

    private var connectedGatt: BluetoothGatt? = null

    @SuppressLint("MissingPermission")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // ✅ BluetoothManager / Adapter 초기화
        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        bluetoothAdapter = bluetoothManager.adapter

        // ✅ 권한 요청
        requestBtPermissions()

        setContent {
            BaseballTheme {
                var devices by remember { mutableStateOf(listOf<BluetoothDevice>()) }
                var scanning by remember { mutableStateOf(false) }

                Scaffold(modifier = Modifier.fillMaxSize()) { padding ->
                    Column(
                        modifier = Modifier
                            .padding(padding)
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.Top,              // ✅ 상단 정렬
                        horizontalAlignment = Alignment.CenterHorizontally  // ✅ 가로 중앙 정렬
                    ) {
                        Button(onClick = {
                            if (!scanning) {
                                startScan { found ->
                                    if (devices.none { it.address == found.address }) {
                                        devices = devices + found
                                    }
                                }
                                scanning = true
                            } else {
                                stopScan()
                                scanning = false
                            }
                        }) {
                            Text(if (scanning) "연결 중지" else "로봇과 연결하세요")  // ✅ 한글 텍스트
                        }

                        Spacer(modifier = Modifier.height(16.dp))
                        Text("발견된 기기", style = MaterialTheme.typography.titleMedium)

                        LazyColumn {
                            items(devices) { device ->
                                Text(
                                    text = "${device.name ?: "Unknown"} - ${device.address}",
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(8.dp)
                                        .clickable {
                                            connectToDevice(device)
                                        }
                                )
                            }
                        }
                    }
                }

            }
        }
    }

    // ✅ BLE GATT 연결 및 송수신 함수
    @SuppressLint("MissingPermission")
    private fun connectToDevice(device: BluetoothDevice) {
        Toast.makeText(this, "연결 시도: ${device.name ?: device.address}", Toast.LENGTH_SHORT).show()

        // ✅ BLE 전용 연결 강제 (TRANSPORT_LE)
        val gatt = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            device.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        } else {
            device.connectGatt(this, false, gattCallback)
        }

        connectedGatt = gatt
    }

    // ✅ GATT 콜백 정의
    private val gattCallback = object : BluetoothGattCallback() {

        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                Log.e("GATT", "Connection failed with status $status")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "연결 실패 (status=$status)", Toast.LENGTH_SHORT).show()
                }
                gatt.close()
                return
            }

            if (newState == BluetoothProfile.STATE_CONNECTED) {
                Log.d("GATT", "✅ Connected to ${gatt.device.name ?: gatt.device.address}")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "연결됨: ${gatt.device.name}", Toast.LENGTH_SHORT).show()
                }

                // ✅ GATT 서비스 검색 시작
                gatt.discoverServices()

                // ✅ 연결된 GATT 객체 전달 후 화면 전환
                ConnectedActivity.gatt = gatt
                val intent = Intent(this@MainActivity, ConnectedActivity::class.java)
                startActivity(intent)

            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                Log.w("GATT", "❌ Disconnected from ${gatt.device.name}")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "연결 끊김", Toast.LENGTH_SHORT).show()
                }
                connectedGatt = null
                gatt.close()
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                Log.d("GATT", "서비스 발견 완료 ✅")

                val service = gatt.getService(SERVICE_UUID)
                if (service == null) {
                    Log.e("GATT", "❌ 서비스 UUID $SERVICE_UUID 를 찾을 수 없음")
                    return
                }

                val characteristic = service.getCharacteristic(CHAR_UUID)
                if (characteristic == null) {
                    Log.e("GATT", "❌ 특성 UUID $CHAR_UUID 를 찾을 수 없음")
                    return
                }

                // ✅ 초기 메시지 전송 테스트
                characteristic.value = "Hi from Android".toByteArray()
                characteristic.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                val success = gatt.writeCharacteristic(characteristic)
                Log.d("GATT", if (success) "✅ 초기 메시지 전송 성공" else "❌ 초기 메시지 전송 실패")

                // ✅ Pi → Android 응답 요청
                gatt.readCharacteristic(characteristic)

            } else {
                Log.e("GATT", "서비스 검색 실패 (status=$status)")
            }
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val msg = characteristic.value.decodeToString()
                Log.d("GATT", "📩 Received from Pi: $msg")
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Pi 응답: $msg", Toast.LENGTH_SHORT).show()
                }
            } else {
                Log.e("GATT", "❌ Characteristic 읽기 실패 (status=$status)")
            }
        }
    }

    // ✅ 권한 요청
    private fun requestBtPermissions() {
        val permissions = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT
            )
        } else {
            arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION
            )
        }

        val launcher = registerForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { result ->
            if (result.values.any { !it }) {
                Toast.makeText(this, "권한이 필요합니다", Toast.LENGTH_LONG).show()
            }
        }

        launcher.launch(permissions)
    }

    private fun hasPermission(permission: String): Boolean {
        return ActivityCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
    }

    // ✅ BLE 스캔
    @SuppressLint("MissingPermission")
    private fun startScan(onDeviceFound: (BluetoothDevice) -> Unit) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (!hasPermission(Manifest.permission.BLUETOOTH_SCAN)) {
                Toast.makeText(this, "BLUETOOTH_SCAN 권한 필요", Toast.LENGTH_SHORT).show()
                return
            }
        } else {
            if (!hasPermission(Manifest.permission.ACCESS_FINE_LOCATION)) {
                Toast.makeText(this, "위치 권한 필요", Toast.LENGTH_SHORT).show()
                return
            }
        }

        bluetoothLeScanner = bluetoothAdapter?.bluetoothLeScanner

        scanCallback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                Log.d("SCAN", "🔍 발견: ${result.device.name} - ${result.device.address}")
                onDeviceFound(result.device)
            }
        }

        bluetoothLeScanner?.startScan(scanCallback)
    }

    @SuppressLint("MissingPermission")
    private fun stopScan() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (!hasPermission(Manifest.permission.BLUETOOTH_SCAN)) return
        }
        scanCallback?.let { bluetoothLeScanner?.stopScan(it) }
    }
}
