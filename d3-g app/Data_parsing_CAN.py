#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, time, socket, threading, http.client
from urllib.parse import urlparse
import argparse
from Library.IPC_Library import IPC_SendPacketWithIPCHeader, IPC_ReceivePacketFromIPCHeader
from Library.IPC_Library import TCC_IPC_CMD_CA72_EDUCATION_CAN_DEMO, IPC_IPC_CMD_CA72_EDUCATION_CAN_DEMO_START
from Library.IPC_Library import parse_hex_data, parse_string_data, parse_channels, parse_hex16

# VCP IO 정의
class VCP_IO:
    # IO 타입
    BREAK_LIGHT = 0x101
    TURN_SIGNAL = 0x102
    EMER_SIGNAL = 0x103
    HEAD_LIGHT = 0x104
    FUEL_L = 0x105
    MOTOR_A = 0x106
    # 액션
    ACTION_ON = 0x01
    ACTION_OFF = 0x02
    
    # 서브타입 (턴 시그널용)
    SUB_LEFT = 0x01
    SUB_RIGHT = 0x02

sndfile = open("/dev/tcc_ipc_micom", 'wb')
URL      = "http://192.168.137.1:25555/api/ets2/telemetry"
HOST,PORT= "0.0.0.0", 9999          
SEND_HZ  = 60                       
POLL_HZ  = 60   
CAN_HZ = 60       
IDLE_RPM = 552
BLINK_INTERVAL = 0.5  # 깜빡이 간격 (0.5초)

TASK_HZ = {
    "break":     10,  
    "head":      10,   
    "turn":      10,      
    "speed":     10,   
    "fuel":      60,    
}
_latest = {"rpm":0.0,"speed_kmh":0.0,"fuel_l":0.0,"steering":0.0}
_can = {"park": False, "left_blinker": False, "right_blinker": False, 
        "emergency": False,"emergency_toggle": False, "headlights": False, "fuel_l": 0,"speed_kmh":0}
_lock   = threading.Lock()
_stop   = False
_prev_states = {}  # 이전 상태 추적용
 
def _get_num(obj, path):
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return float(cur) if isinstance(cur, (int,float)) else None

def _get_bool(obj, path):
    """Boolean 값을 안전하게 가져오는 함수"""
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return bool(cur) if cur is not None else None

def send_ipc_signal(io_type, action_or_value, subtype=None):
    """IPC 신호 전송 통합 함수"""
    try:
        if subtype is not None:
            payload = bytes([subtype, action_or_value])
        else:
            payload = bytes([action_or_value])
        
        IPC_SendPacketWithIPCHeader(sndfile, 1, 0, io_type, payload)
        return True
    except Exception as e:
        print(f"[IPC ERROR] {e} - io_type: 0x{io_type:X}, value: {action_or_value}")
        return False

def get_blink_state():
    """현재 시간 기준으로 깜빡이가 켜져있어야 하는지 판단"""
    current_time = time.time()
    cycle_position = current_time % (BLINK_INTERVAL * 2)  # 1초 주기 (0.5초 ON, 0.5초 OFF)
    return cycle_position < BLINK_INTERVAL

def process_brake_light(current_state):
    key = "park"
    if _prev_states.get(key) != current_state:
        action = VCP_IO.ACTION_ON if current_state else VCP_IO.ACTION_OFF
        if send_ipc_signal(VCP_IO.BREAK_LIGHT, action):
            print(f"[IPC] Brake light {'ON' if current_state else 'OFF'}")
            _prev_states[key] = current_state

def process_turn_signals(left_active, right_active):
    """수정된 깜빡이 처리 - 즉시 반응"""
    
    # 좌측 깜빡이 처리
    left_key = "left_blinker_active"
    left_state_key = "left_blinker_state"
    
    if left_active:
        # 깜빡이가 새로 활성화됨
        if _prev_states.get(left_key) != left_active:
            _prev_states[left_key] = left_active
            print("[IPC] Left turn signal activated")
        
        # 깜빡거리는 신호 처리
        blink_on = get_blink_state()
        if _prev_states.get(left_state_key) != blink_on:
            action = VCP_IO.ACTION_ON if blink_on else VCP_IO.ACTION_OFF
            if send_ipc_signal(VCP_IO.TURN_SIGNAL, action, VCP_IO.SUB_LEFT):
                print(f"[IPC] Left turn signal {'ON' if blink_on else 'OFF'} (Blink)")
                _prev_states[left_state_key] = blink_on
    else:
        # 깜빡이 비활성화 - 즉시 OFF
        if _prev_states.get(left_key) != left_active:
            if send_ipc_signal(VCP_IO.TURN_SIGNAL, VCP_IO.ACTION_OFF, VCP_IO.SUB_LEFT):
                print("[IPC] Left turn signal OFF (Deactivated)")
                _prev_states[left_key] = left_active
                _prev_states[left_state_key] = False  # 깜빡이 상태도 리셋
    
    # 우측 깜빡이 처리 (동일 로직)
    right_key = "right_blinker_active"
    right_state_key = "right_blinker_state"
    
    if right_active:
        # 깜빡이가 새로 활성화됨
        if _prev_states.get(right_key) != right_active:
            _prev_states[right_key] = right_active
            print("[IPC] Right turn signal activated")
        
        # 깜빡거리는 신호 처리
        blink_on = get_blink_state()
        if _prev_states.get(right_state_key) != blink_on:
            action = VCP_IO.ACTION_ON if blink_on else VCP_IO.ACTION_OFF
            if send_ipc_signal(VCP_IO.TURN_SIGNAL, action, VCP_IO.SUB_RIGHT):
                print(f"[IPC] Right turn signal {'ON' if blink_on else 'OFF'} (Blink)")
                _prev_states[right_state_key] = blink_on
    else:
        # 깜빡이 비활성화 - 즉시 OFF
        if _prev_states.get(right_key) != right_active:
            if send_ipc_signal(VCP_IO.TURN_SIGNAL, VCP_IO.ACTION_OFF, VCP_IO.SUB_RIGHT):
                print("[IPC] Right turn signal OFF (Deactivated)")
                _prev_states[right_key] = right_active
                _prev_states[right_state_key] = False  # 깜빡이 상태도 리셋

def process_emergency_signal(state_on: bool):
    """게임의 emergency(ON/OFF) 값을 그대로 따라감"""
    key = "emergency_state"
    if _prev_states.get(key) != state_on:
        action = VCP_IO.ACTION_ON if state_on else VCP_IO.ACTION_OFF
        send_ipc_signal(VCP_IO.EMER_SIGNAL, action)
        _prev_states[key] = state_on


def process_headlights(current_state):
    key = "headlights"
    if _prev_states.get(key) != current_state:
        action = VCP_IO.ACTION_ON if current_state else VCP_IO.ACTION_OFF
        if send_ipc_signal(VCP_IO.HEAD_LIGHT, action):
            print(f"[IPC] Headlights {'ON' if current_state else 'OFF'}")
            _prev_states[key] = current_state

def process_speed(current_speed):
    send_ipc_signal(VCP_IO.MOTOR_A, current_speed)

def process_fuel(fuel_l):
    fuel_pct = (float(fuel_l) / 1500.0) * 100.0
    fuel_pct = int(round(max(0.0, min(100.0, fuel_pct))))
    send_ipc_signal(VCP_IO.FUEL_L, fuel_pct)

def _scale_payload(js):
    rpm       = _get_num(js,"truck.engineRpm")
    speed     = _get_num(js,"truck.speed")            
    fuel      = _get_num(js,"truck.fuel")
    steer     = _get_num(js,"truck.gameSteer")
    park_brake = (_get_bool(js, "truck.parkBrakeOn"))
    left_blinker = (_get_bool(js, "truck.blinkerLeftActive"))
    right_blinker = (_get_bool(js, "truck.blinkerRightActive"))
    left_blinker_on = (_get_bool(js, "truck.blinkerLeftOn"))
    right_blinker_on = (_get_bool(js, "truck.blinkerRightOn"))
    headlights = (_get_bool(js, "truck.lightsBeamLowOn"))
    emergency = bool(left_blinker_on and right_blinker_on)
    
    return {
        "rpm": int(rpm) if isinstance(rpm,(int,float)) else 0,
        "speed_kmh": int(speed) if isinstance(speed,(int,float)) else 0.0,
        "fuel_l": float(fuel) if isinstance(fuel,(int,float)) else 0.0,
        "steering": float(steer) if isinstance(steer,(int,float)) else 0.0,
        "park": bool(park_brake) if park_brake is not None else False,
        "left_blinker": bool(left_blinker) if left_blinker is not None else False,
        "right_blinker": bool(right_blinker) if right_blinker is not None else False,
        "emergency": emergency,
        "headlights": bool(headlights) if headlights is not None else False,
    }
 
def poller():
    global _latest, _stop, _can
    u = urlparse(URL)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=1)
    path = u.path or "/"
    if u.query: path += "?" + u.query
 
    period = 1.0 / POLL_HZ
    next_t = time.monotonic()

    while not _stop:
        try:
            conn.request("GET", path, headers={
                "User-Agent":"ETS2-Client/1.0",
                "Connection":"keep-alive",
                "Cache-Control":"no-cache",
                "Pragma":"no-cache",
            })
            resp = conn.getresponse()
            if resp.status == 200:
                data = resp.read()
                js = json.loads(data.decode("utf-8","ignore"))
                payload = _scale_payload(js)

                # CAN 상태 업데이트
                with _lock:
                    for k,v in payload.items():
                        if k in _can:
                            _can[k] = v
                # 속도계 상태 업데이트
                with _lock:
                    for k,v in payload.items():
                        if k in _latest:
                            _latest[k] = v
            else:
                print(f"[ERROR] HTTP {resp.status}")
                time.sleep(0.1)
                conn.close()
                conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=1)
                
        except Exception as e:
            try: conn.close()
            except: pass
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=1)
            time.sleep(0.05)
 
        next_t += period
        now = time.monotonic()
        if next_t > now:
            time.sleep(next_t - now)
        else:
            next_t = now  

def can_worker():
    period = 1.0 / CAN_HZ
    count = 0
    while not _stop:
        count +=1
        # 각 기능별 처리               
        with _lock:
            can_snapshot = dict(_can)
        emergency_active = can_snapshot.get("emergency", False)
        left_blinker_active = can_snapshot.get("left_blinker", False)
        right_blinker_active = can_snapshot.get("right_blinker", False)
        

        if (count % TASK_HZ["break"])==0:
            process_brake_light(can_snapshot.get("park", False))
        
        # 비상등이 활성화되면 비상등만 처리, 아니면 개별 깜빡이 처리
        if (count % TASK_HZ["turn"])==0:
            if emergency_active:
                # 비상등 활성화 시 개별 깜빡이는 강제로 OFF
                force_turn_signals_off()
                process_emergency_signal(True)
            else:
                # 비상등 비활성화
                process_emergency_signal(False)
                # 개별 깜빡이 처리
            process_turn_signals(left_blinker_active, right_blinker_active)

        if (count % TASK_HZ["head"])==0:
            process_headlights(can_snapshot.get("headlights", False))
        if (count % TASK_HZ["speed"])==0:
            process_speed(can_snapshot.get("speed_kmh",False))
        if (count % TASK_HZ["fuel"])==0:
            process_fuel(can_snapshot.get("fuel_l",False))

        time.sleep(period)

def force_turn_signals_off():
    """비상등 활성화 시 개별 깜빡이 강제 OFF"""
    left_keys = ["left_blinker_active", "left_blinker_state"]
    right_keys = ["right_blinker_active", "right_blinker_state"]
    
    # 좌측 깜빡이 OFF
    if _prev_states.get("left_blinker_active") is not False:
        if send_ipc_signal(VCP_IO.TURN_SIGNAL, VCP_IO.ACTION_OFF, VCP_IO.SUB_LEFT):
            for key in left_keys:
                _prev_states[key] = False
    
    # 우측 깜빡이 OFF        
    if _prev_states.get("right_blinker_active") is not False:
        if send_ipc_signal(VCP_IO.TURN_SIGNAL, VCP_IO.ACTION_OFF, VCP_IO.SUB_RIGHT):
            for key in right_keys:
                _prev_states[key] = False
        
def serve():
    global _stop
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[NET] listening on {HOST}:{PORT}")
 
    qt_keys = {"rpm", "speed_kmh", "fuel_l", "steering"}
 
    while not _stop:
        try:
            conn, addr = srv.accept()
            print(f"[NET] client connected: {addr[0]}:{addr[1]}")
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            period = 1.0 / SEND_HZ
            next_t = time.monotonic()
            encoder = json.dumps  
            
            while not _stop:
                with _lock:
                    qt_payload = {k: v for k, v in _latest.items() if k in qt_keys}
                    
                line = encoder(qt_payload, separators=(",",":")) + "\n"
                conn.sendall(line.encode("utf-8"))
 
                next_t += period
                now = time.monotonic()
                if next_t > now:
                    time.sleep(next_t - now)
                else:
                    next_t = now
                    
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"[NET] Connection error: {e}")
        except Exception as e:
            print(f"[NET] Unexpected error: {e}")
        finally:
            try: conn.close()
            except: pass
 
def main():
    print("Starting ETS2 Telemetry Monitor...")
    # 텔레메트리 수집 스레드
    t = threading.Thread(target=poller, daemon=True)
    t.start()
    # CAN 전송 스레드
    t_can  = threading.Thread(target=can_worker, daemon=True, name="can_worker")
    t_can.start()

    try:
        serve()
    finally:
        global _stop
        _stop = True
        t.join(timeout=1.0)
        t_can.join(timeout=1.0)
        print("Shutdown complete.")
        sndfile.close()
 
if __name__ == "__main__":
    main()