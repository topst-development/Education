#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, time, socket, threading, http.client
from urllib.parse import urlparse
 
URL      = "http://192.168.137.1:25555/api/ets2/telemetry"
HOST,PORT= "0.0.0.0", 9999          
SEND_HZ  = 30                       
POLL_HZ  = 30                       
IDLE_RPM = 552

_latest = {"rpm":0.0,"speed_kmh":0.0,"fuel_l":0.0,"steering":0.0}
_lock   = threading.Lock()
_stop   = False
 
def _get_num(obj, path):
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return float(cur) if isinstance(cur, (int,float)) else None
 
def _scale_payload(js):
    rpm       = _get_num(js,"truck.engineRpm")
    speed     = _get_num(js,"truck.speed")            
    fuel      = _get_num(js,"truck.fuel")
    steer     = _get_num(js,"truck.gameSteer")
 
    speed_kmh = int(speed) if isinstance(speed,(int,float)) else 0.0
 
    return {
        "rpm": int(rpm) if isinstance(rpm,(int,float)) else 0,
        "speed_kmh": int(speed) if isinstance(speed,(int,float)) else 0.0,
        "fuel_l": float(fuel) if isinstance(fuel,(int,float)) else 0.0,
        "steering": float(steer) if isinstance(steer,(int,float)) else 0.0,
    }
 
def poller():
    global _latest, _stop
    u = urlparse(URL)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=2)
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
                # ------- 간단 EMA 스무딩 (옵션) -------
                alpha = 0.35
                with _lock:
                    for k,v in payload.items():
                        _latest[k] = _latest[k]* (1-alpha) + v*alpha
            else:
                time.sleep(0.2)
                conn.close()
                conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=2)
        except Exception:
            try: conn.close()
            except: pass
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=2)
            time.sleep(0.2)
 
        next_t += period
        now = time.monotonic()
        if next_t > now:
            time.sleep(next_t - now)
        else:
            next_t = now  
def serve():
    global _stop
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[NET] listening on {HOST}:{PORT}")
 
    while not _stop:
        conn, addr = srv.accept()
        print(f"[NET] client connected: {addr[0]}:{addr[1]}")
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            period = 1.0 / SEND_HZ
            next_t = time.monotonic()
            encoder = json.dumps  
            while True:
                with _lock:
                    payload = dict(_latest)
                line = encoder(payload, separators=(",",":")) + "\n"
                conn.sendall(line.encode("utf-8"))
 
                next_t += period
                now = time.monotonic()
                if next_t > now:
                    time.sleep(next_t - now)
                else:
                    next_t = now
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try: conn.close()
            except: pass
 
def main():
    t = threading.Thread(target=poller, daemon=True)
    t.start()
    try:
        serve()
    finally:
        global _stop
        _stop = True
        t.join(timeout=1.0)
 
if __name__ == "__main__":
    main() 