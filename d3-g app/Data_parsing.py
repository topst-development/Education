#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, time, http.client
from urllib.parse import urlparse

URL      = "http://192.168.137.1:25555/api/ets2/telemetry"
POLL_HZ  = 30                 
TIMEOUT  = 2.0                

def _get_num(obj, path):
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return float(cur) if isinstance(cur, (int, float)) else None

def _scale_payload(js):
    rpm     = _get_num(js, "truck.engineRpm")
    speed   = _get_num(js, "truck.speed")          
    fuel    = _get_num(js, "truck.fuel")
    steer   = _get_num(js, "truck.gameSteer")

    speed_kmh = int(speed) if isinstance(speed, (int, float)) else 0.0

    return {
        "rpm":       int(rpm) if isinstance(rpm, (int, float)) else 0,
        "speed_kmh": round(speed_kmh, 2),
        "fuel_l":    float(fuel) if isinstance(fuel, (int, float)) else 0.0,
        "steering":  float(steer) if isinstance(steer, (int, float)) else 0.0,
    }

def main():
    u = urlparse(URL)
    host = u.hostname
    port = u.port or 80
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    period = 1.0 / POLL_HZ

    conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)
    next_t = time.monotonic()

    print("[INFO] Start polling:", URL)
    print("[INFO] Press Ctrl+C to stop.")

    try:
        while True:
            try:
                conn.request("GET", path, headers={
                    "User-Agent": "ETS2-Client/1.0",
                    "Connection": "keep-alive",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                })
                resp = conn.getresponse()
                if resp.status == 200:
                    data = resp.read()
                    js = json.loads(data.decode("utf-8", "ignore"))
                    p = _scale_payload(js)
                    print(f"rpm={p['rpm']:5d} | speed_kmh={p['speed_kmh']:6.2f} | fuel_l={p['fuel_l']:7.2f} | steering={p['steering']:+.3f}")
                else:
                    print(f"[WARN] HTTP {resp.status} {resp.reason}")
                    try: conn.close()
                    except: pass
                    conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[ERR] {e}")
                time.sleep(0.3)
                try: conn.close()
                except: pass
                conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)

            next_t += period
            now = time.monotonic()
            if next_t > now:
                time.sleep(next_t - now)
            else:
                next_t = now
    finally:
        try: conn.close()
        except: pass
        print("\n[INFO] Stopped.")

if __name__ == "__main__":
    main()
 