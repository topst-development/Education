#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import socket
import threading
import argparse
import cv2
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import IntEnum
import logging

# =============================================================================
# IPC Library Import (Optional)
# =============================================================================
try:
    from Library.IPC_Library import IPC_SendPacketWithIPCHeader
except ImportError:
    def IPC_SendPacketWithIPCHeader(*args, **kwargs):
        """Fallback stub for missing IPC library"""
        pass


# =============================================================================
# Logging Configuration
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Enums & Constants
# =============================================================================

class VehicleControlCommand(IntEnum):
    """VCP (Vehicle Control Protocol) IO type identifiers"""
    BREAK_LIGHT = 0x101
    MOTOR_A     = 0x102
    WHEEL       = 0x103
    EMER_SIGNAL = 0x104
    FUEL_L      = 0x105
    TURN_SIGNAL = 0x106
    HEAD_LIGHT  = 0x107


class ControlAction(IntEnum):
    """VCP control action values"""
    ON  = 0x01
    OFF = 0x02


class TurnSignalDirection(IntEnum):
    """Turn signal direction subtypes"""
    LEFT  = 0x01
    RIGHT = 0x02


class DetectedZone(str):
    """5-Zone detection (3x2 grid)"""
    LEFT_UPPER = "LEFT_UPPER"       # Zone 1 (좌상단)
    LEFT_LOWER = "LEFT_LOWER"       # Zone 2 (좌하단)
    RIGHT_UPPER = "RIGHT_LOWER"     # Zone 3 (우상단)
    RIGHT_LOWER = "RIGHT_UPPER"     # Zone 4 (우하단)
    CENTER = "CENTER"               # Zone 5 (중앙)


# Zone ID Mapping for UI
class ZoneID(IntEnum):
    """Zone IDs for UI display"""
    LEFT_UPPER  = 1
    LEFT_LOWER  = 2
    RIGHT_LOWER = 3
    RIGHT_UPPER = 4
    CENTER      = 5


# Network Configuration
class NetworkConfig:
    """Network constants for AI-G communication"""
    SERVER_IP = "192.168.0.100"
    FRAME_PORT = 5000  # AI-G video input
    RESULT_PORT = 6000  # AI-G result output
    QT_DASHBOARD_PORT = 9998  # Qt Dashboard
    QT_LANE_PORT = 9999  # Qt Lane Visualization


# Video Configuration
class VideoConfig:
    """Video processing constants"""
    MODEL_W = 640
    MODEL_H = 640
    OUTPUT_W = 1280
    OUTPUT_H = 720
    FRAME_BYTES = OUTPUT_W * OUTPUT_H * 3
    FPS = 30.0
    FRAME_PERIOD = 1.0 / FPS


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AppConfig:
    """Application configuration"""
    video_path: str
    scenario_json: str
    ipc_path: str = "/dev/tcc_ipc_micom"
    ai_g_host: str = NetworkConfig.SERVER_IP
    ai_g_frame_port: int = NetworkConfig.FRAME_PORT
    ai_g_result_port: int = NetworkConfig.RESULT_PORT
    qt_dashboard_port: int = NetworkConfig.QT_DASHBOARD_PORT
    qt_lane_port: int = NetworkConfig.QT_LANE_PORT

    def validate(self) -> bool:
        """Validate configuration paths exist"""
        if not Path(self.video_path).exists():
            logger.error(f"Video file not found: {self.video_path}")
            return False
        if not Path(self.scenario_json).exists():
            logger.error(f"Scenario file not found: {self.scenario_json}")
            return False
        return True


@dataclass
class VehicleState:
    """Current vehicle state"""
    frame: int = 0
    speed_kmh: float = 0.0
    rpm: float = 552.0
    steer: float = 65.0
    headlights: bool = False
    left_blinker: bool = False
    right_blinker: bool = False
    brake_light: bool = False
    emergency_light: bool = False
    fuel_level: float = 100
    zone: str = DetectedZone.CENTER

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization"""
        return {
            "frame": self.frame,
            "speed_kmh": self.speed_kmh,
            "rpm": self.rpm,
            "steer": self.steer,
            "headlights": self.headlights,
            "left_blinker": self.left_blinker,
            "right_blinker": self.right_blinker,
            "brake_light": self.brake_light,
            "fuel_level": self.fuel_level,
            "emergency_light": self.emergency_light,
            "zone": self.zone
        }


@dataclass
class ObjectDetectionResult:
    """AI-G object detection result with 5-zone support"""
    zone: str
    center_x: int
    center_y: int
    box_x: int
    box_y: int
    box_w: int
    box_h: int
    detected: bool = True

    @staticmethod
    def determine_zone_5division(
        center_x: int, 
        center_y: int,
        screen_width: int = VideoConfig.OUTPUT_W,
        screen_height: int = VideoConfig.OUTPUT_H
    ) -> str:
        # X-axis boundaries (3등분)
        x_third1 = int(screen_width * 1/3)    # 427px (33%)
        x_third2 = int(screen_width * 2/3)    # 853px (67%)
        
        # Y-axis boundary (2등분)
        y_half = int(screen_height * 0.5)     # 360px (50%)
        
        # Determine X-axis position
        if center_x < x_third1:
            x_zone = "LEFT"
        elif center_x < x_third2:
            x_zone = "CENTER"
        else:
            x_zone = "RIGHT"
        
        # Determine Y-axis position
        if center_y < y_half:
            y_zone = "UPPER"
        else:
            y_zone = "LOWER"
        
        # Combine zones
        if x_zone == "CENTER":
            return DetectedZone.CENTER  # CENTER는 Y축 무관
        else:
            zone_name = f"{x_zone}_{y_zone}"
            return zone_name

    @staticmethod
    def get_zone_id(zone: str) -> int:
        """Get zone ID for UI display"""
        zone_map = {
            DetectedZone.LEFT_UPPER: ZoneID.LEFT_UPPER,
            DetectedZone.LEFT_LOWER: ZoneID.LEFT_LOWER,
            DetectedZone.CENTER: ZoneID.CENTER,
            DetectedZone.RIGHT_UPPER: ZoneID.RIGHT_UPPER,
            DetectedZone.RIGHT_LOWER: ZoneID.RIGHT_LOWER,
        }
        return zone_map.get(zone, ZoneID.CENTER)


# =============================================================================
# Communication Handlers
# =============================================================================

class IPCController:
    """Handles IPC/CAN communication with vehicle"""

    def __init__(self, ipc_path: str):
        self.ipc_path = ipc_path
        self.ipc_file: Optional[object] = None
        self.enabled = False
        self._initialize()

    def _initialize(self) -> None:
        """Initialize IPC connection"""
        try:
            self.ipc_file = open(self.ipc_path, "wb")
            self.enabled = True
            logger.info(f"IPC device opened: {self.ipc_path}")
        except FileNotFoundError:
            logger.warning(f"IPC device not found: {self.ipc_path} → Simulation mode")
            self.enabled = False
        except Exception as e:
            logger.error(f"IPC initialization failed: {e} → Simulation mode")
            self.enabled = False

    def send_command(
        self,
        command_type: int,
        value: int,
        subtype: Optional[int] = None
    ) -> None:
        """Send control command via IPC"""
        if not self.enabled or not self.ipc_file:
            return

        try:
            payload = (
                bytes([subtype, value]) if subtype is not None
                else value.to_bytes(1, "big", signed=True)
            )
            IPC_SendPacketWithIPCHeader(self.ipc_file, 1, 0, command_type, payload)
        except Exception as e:
            logger.error(f"IPC send failed: {e}")

    def close(self) -> None:
        """Close IPC connection"""
        if self.ipc_file:
            try:
                self.ipc_file.close()
            except Exception as e:
                logger.warning(f"Error closing IPC file: {e}")
            finally:
                self.ipc_file = None
                self.enabled = False


class VehicleCommandHandler:
    """Handles vehicle control commands"""

    def __init__(self, ipc_controller: IPCController):
        self.ipc = ipc_controller

    def set_speed(self, speed_kmh: float) -> None:
        """Send speed control command"""
        self.ipc.send_command(VehicleControlCommand.MOTOR_A, int(speed_kmh))
        logger.info(f"Speed command: {speed_kmh:.1f} km/h")

    def set_steering(self, steer: float) -> None:
        """Send steering angle command"""
        val = int((steer - 1.0) * 127 / -2.0)
        val = max(0, min(127, val))
        self.ipc.send_command(VehicleControlCommand.WHEEL, val)
        logger.info(f"Steering command: {steer:.2f} → {val}")

    def set_fuel_level(self, level: float) -> None:
        """Send fuel level control command (0-100)"""
        val = int(level)
        val = max(0, min(100, val)) # 0~100 사이로 제한
        self.ipc.send_command(VehicleControlCommand.FUEL_L, val)
        logger.info(f"Fuel Level Command: {val}%")

    def set_brake_light(self, enabled: bool) -> None:
        """Send brake light control command"""
        action = ControlAction.ON if enabled else ControlAction.OFF
        self.ipc.send_command(VehicleControlCommand.BREAK_LIGHT, action)
        logger.info(f"Brake Light: {'ON' if enabled else 'OFF'}")

    def set_headlights(self, enabled: bool) -> None:
        """Send headlight control command"""
        action = ControlAction.ON if enabled else ControlAction.OFF
        self.ipc.send_command(VehicleControlCommand.HEAD_LIGHT, action)
        logger.info(f"Headlights: {'ON' if enabled else 'OFF'}")

    def set_emergency_light(self, enabled: bool) -> None:
        """Send emergency_light control command"""
        action = ControlAction.ON if enabled else ControlAction.OFF
        self.ipc.send_command(VehicleControlCommand.EMER_SIGNAL, action)
        logger.info(f"Emergency Light: {'ON' if enabled else 'OFF'}")


    def set_turn_signal(self, direction: str, enabled: bool) -> None:
        """Send turn signal control command"""
        subtype = (
            TurnSignalDirection.LEFT if direction == "left"
            else TurnSignalDirection.RIGHT
        )
        action = ControlAction.ON if enabled else ControlAction.OFF
        self.ipc.send_command(VehicleControlCommand.TURN_SIGNAL, action, subtype)
        logger.info(f"Turn signal {direction.upper()}: {'ON' if enabled else 'OFF'}")


class SocketManager:
    """Manages socket connections"""

    def __init__(self):
        self.sockets: Dict[str, socket.socket] = {}

    def create_client_socket(self, name: str, host: str, port: int) -> socket.socket:
        """Create and connect a client socket with retry logic"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        while True:
            try:
                sock.connect((host, port))
                logger.info(f"Socket '{name}' connected to {host}:{port}")
                self.sockets[name] = sock
                return sock
            except ConnectionRefusedError:
                logger.warning(f"Socket '{name}' connection refused, retrying...")
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Socket '{name}' connection error: {e}")
                raise

    def create_server_socket(self, name: str, port: int, listen_backlog: int = 1) -> socket.socket:
        """Create and bind a server socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(("0.0.0.0", port))
            sock.listen(listen_backlog)
            logger.info(f"Server socket '{name}' listening on port {port}")
            self.sockets[name] = sock
            return sock
        except Exception as e:
            logger.error(f"Server socket '{name}' bind error: {e}")
            raise

    def close_all(self) -> None:
        """Close all managed sockets"""
        for name, sock in self.sockets.items():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, BrokenPipeError):
                pass
            try:
                sock.close()
            except Exception as e:
                logger.warning(f"Error closing socket '{name}': {e}")
        self.sockets.clear()


# =============================================================================
# Scenario Player
# =============================================================================

class ScenarioPlayer:
    """Main scenario player orchestrating all components"""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

        # Thread management
        self.running = threading.Event()
        self.video_ready = threading.Event()
        self.lock = threading.RLock()
        self.threads: List[threading.Thread] = []

        # State management
        self.vehicle_state = VehicleState()
        self.frame_idx = 0
        self.ai_result: Optional[ObjectDetectionResult] = None
        self.scenario_events: Dict[int, Dict[str, Any]] = {}

        # Controllers
        self.ipc = IPCController(cfg.ipc_path)
        self.vehicle_cmd = VehicleCommandHandler(self.ipc)
        self.socket_mgr = SocketManager()

    def __enter__(self):
        """Context manager entry"""
        self._load_scenario()
        self.running.set()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

    def _load_scenario(self) -> None:
        """Load scenario events from JSON file"""
        try:
            with open(self.cfg.scenario_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.scenario_events = {
                int(event["frame"]): event["signals"]
                for event in data.get("events", [])
            }
            logger.info(f"Scenario loaded: {len(self.scenario_events)} events")
        except Exception as e:
            logger.error(f"Failed to load scenario: {e}")
            self.scenario_events = {}

    def _apply_scenario_signals(self, signals: Dict[str, Any]) -> None:
        """Apply scenario control signals to vehicle"""
        if "speed" in signals:
            speed = float(signals["speed"])
            self.vehicle_cmd.set_speed(speed)
            self.vehicle_state.speed_kmh = speed
            self.vehicle_state.rpm = 552.0 + abs(speed) * 40

        if "steer" in signals:
            steer_val = float(signals["steer"])
            self.vehicle_cmd.set_steering(steer_val)
            self.vehicle_state.steer = steer_val

        if "headlights" in signals:
            is_on = bool(signals["headlights"])
            self.vehicle_cmd.set_headlights(is_on)
            self.vehicle_state.headlights = is_on

        if "left_blinker" in signals:
            is_on = bool(signals["left_blinker"])
            self.vehicle_cmd.set_turn_signal("left", is_on)
            self.vehicle_state.left_blinker = is_on
                
        if "right_blinker" in signals:
            is_on = bool(signals["right_blinker"])
            self.vehicle_cmd.set_turn_signal("right", is_on)
            self.vehicle_state.right_blinker = is_on

        if "break_light" in signals:
            is_on = bool(signals["break_light"])
            self.vehicle_cmd.set_brake_light(is_on)
            self.vehicle_state.brake_light = is_on
                
        if "fuel_level" in signals:
            fuel = float(signals["fuel_level"])
            self.vehicle_cmd.set_fuel_level(fuel)
            self.vehicle_state.fuel_level = fuel

        if "emergency_light" in signals:
            is_on = bool(signals["emergency_light"])
            self.vehicle_cmd.set_emergency_light(is_on)
            self.vehicle_state.emergency_light = is_on


    def _worker_video(self) -> None:
        """Stream video frames to AI-G (port 5000)"""
        logger.info("Connecting to AI-G video port (5000)...")
        video_sock = self.socket_mgr.create_client_socket(
            "video", self.cfg.ai_g_host, self.cfg.ai_g_frame_port
        )
        self.video_ready.set()

        cap = cv2.VideoCapture(self.cfg.video_path)
        logger.info("Video streaming started")

        try:
            while self.running.is_set():
                start_time = time.monotonic()

                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                frame = cv2.resize(frame, (VideoConfig.OUTPUT_W, VideoConfig.OUTPUT_H))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                payload = frame.tobytes()

                if len(payload) != VideoConfig.FRAME_BYTES:
                    logger.warning("Invalid frame size")
                    continue

                try:
                    video_sock.sendall(payload)
                except Exception as e:
                    logger.error(f"Video send error: {e}")
                    break

                with self.lock:
                    self.frame_idx += 1
                    current_frame = self.frame_idx

                if current_frame % 30 == 0:
                    logger.debug(f"Video frame: {current_frame}")

                elapsed = time.monotonic() - start_time
                if elapsed < VideoConfig.FRAME_PERIOD:
                    time.sleep(VideoConfig.FRAME_PERIOD - elapsed)

        finally:
            cap.release()
            logger.info("Video thread ended")

    def _worker_result(self) -> None:
        """Receive AI-G results (port 6000)"""
        logger.info("Waiting for video port to be ready...")
        self.video_ready.wait()

        logger.info("Connecting to AI-G result port (6000)...")
        result_sock = self.socket_mgr.create_client_socket(
            "result", self.cfg.ai_g_host, self.cfg.ai_g_result_port
        )

        buffer = b""
        try:
            while self.running.is_set():
                data = result_sock.recv(1024)
                if not data:
                    break

                buffer += data

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        msg = line.decode("utf-8").strip()
                        if msg:
                            self._handle_detection_result(msg)
                    except Exception as e:
                        logger.warning(f"Result decode error: {e}")
        except Exception as e:
            logger.error(f"Result recv error: {e}")
        finally:
            logger.info("Result thread ended")

    def _handle_detection_result(self, json_str: str) -> None:
        """Parse and process AI-G detection result"""
        try:
            data = json.loads(json_str)
            
            x, y, w, h = data["x"], data["y"], data["w"], data["h"]

            scale_x = VideoConfig.OUTPUT_W / VideoConfig.MODEL_W
            scale_y = VideoConfig.OUTPUT_H / VideoConfig.MODEL_H

            x = int(x * scale_x)
            y = int(y * scale_y)
            w = int(w * scale_x)
            h = int(h * scale_y)

            center_x = x + w // 2
            center_y = y + h // 2

            # 5-zone detection (X축 3등분 + Y축 2등분)
            zone = ObjectDetectionResult.determine_zone_5division(center_x, center_y)

            with self.lock:
                self.ai_result = ObjectDetectionResult(
                    zone=zone,
                    center_x=center_x,
                    center_y=center_y,
                    box_x=x,
                    box_y=y,
                    box_w=w,
                    box_h=h,
                    detected=True
                )
                self.vehicle_state.zone = zone

            logger.info(f"Detection: zone={zone} center=({center_x}, {center_y})")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
        except KeyError as e:
            logger.error(f"Missing required field: {e}")
        except Exception as e:
            logger.error(f"Result processing error: {e}")

    def _worker_dashboard(self) -> None:
        """Server for Qt Dashboard (port 9998)"""
        dashboard_sock = self.socket_mgr.create_server_socket(
            "dashboard", self.cfg.qt_dashboard_port
        )
        dashboard_sock.settimeout(1.0)

        try:
            while self.running.is_set():
                try:
                    conn, addr = dashboard_sock.accept()
                    logger.info(f"Dashboard connected: {addr}")
                    self._handle_dashboard_client(conn)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Dashboard accept error: {e}")
                    break
        finally:
            logger.info("Dashboard server ended")

    def _handle_dashboard_client(self, conn: socket.socket) -> None:
        """Handle individual dashboard client connection"""
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            while self.running.is_set():
                with self.lock:
                    payload = self.vehicle_state.to_dict()

                line = json.dumps(payload) + "\n"
                conn.sendall(line.encode("utf-8"))
                time.sleep(1.0 / 30.0)

        except (BrokenPipeError, ConnectionResetError):
            logger.info("Dashboard client disconnected")
        except Exception as e:
            logger.error(f"Dashboard send error: {e}")
        finally:
            try:
                conn.close()
            except:
                pass

    def _worker_zone_visualization(self) -> None:
        """Server for Qt Zone visualization (port 9999)"""
        zone_sock = self.socket_mgr.create_server_socket(
            "zone", self.cfg.qt_lane_port, listen_backlog=5
        )
        zone_sock.settimeout(1.0)

        try:
            while self.running.is_set():
                try:
                    conn, addr = zone_sock.accept()
                    logger.info(f"Zone client connected: {addr}")
                    t = threading.Thread(
                        target=self._handle_zone_client,
                        args=(conn,),
                        daemon=True
                    )
                    t.start()
                    self.threads.append(t)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Zone accept error: {e}")
                    break
        finally:
            logger.info("Zone visualization server ended")

    def _handle_zone_client(self, conn: socket.socket) -> None:
        """Handle individual zone client connection"""
        zone_to_id = {
            DetectedZone.LEFT_UPPER: 1,
            DetectedZone.LEFT_LOWER: 2,
            DetectedZone.RIGHT_LOWER: 3,
            DetectedZone.RIGHT_UPPER: 4,
            DetectedZone.CENTER: 5,
        }

        try:
            logger.info("Zone client: starting data stream (5-zone)")
            while self.running.is_set():
                with self.lock:
                    if self.ai_result and self.ai_result.detected:
                        zone_id = zone_to_id.get(self.ai_result.zone, 3)
                        msg = f"object_detected_lane_{zone_id}\n"
                        conn.sendall(msg.encode("utf-8"))

                time.sleep(1.0 / 20.0)

        except (BrokenPipeError, ConnectionResetError):
            logger.info("Zone client disconnected")
        except Exception as e:
            logger.error(f"Zone send error: {e}")
        finally:
            try:
                conn.close()
            except:
                pass

    def _worker_scenario(self) -> None:
        """Process scenario events and apply control signals"""
        last_frame = -1
        logger.info("Scenario processor started")

        try:
            while self.running.is_set():
                with self.lock:
                    current_frame = self.frame_idx
                    ai_result = self.ai_result

                if current_frame != last_frame and current_frame in self.scenario_events:
                    signals = self.scenario_events[current_frame]
                    self._apply_scenario_signals(signals)
                    logger.info(f"Scenario frame {current_frame}: {signals}")
                    last_frame = current_frame

                time.sleep(0.001)

        finally:
            logger.info("Scenario processor ended")

    def start(self) -> None:
        """Start all worker threads"""
        worker_functions = [
            self._worker_dashboard,
            self._worker_zone_visualization,
            self._worker_video,
            self._worker_result,
            self._worker_scenario,
        ]

        for worker_func in worker_functions:
            thread = threading.Thread(target=worker_func, daemon=False)
            thread.start()
            self.threads.append(thread)

        logger.info("Scenario player started (5-Zone Mode: X축 3등분 + Y축 2등분)")

    def stop(self) -> None:
        """Stop all threads and clean up resources"""
        if not self.running.is_set():
            return

        logger.info("Stopping scenario player...")
        self.running.clear()

        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1.0)

        self.socket_mgr.close_all()
        self.ipc.close()

        logger.info("Cleanup complete")

    def run(self) -> None:
        """Run the scenario player main loop"""
        self.start()

        try:
            while self.running.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()


# =============================================================================
# Main
# =============================================================================

def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description="Vehicle Scenario Player for AI-G Integration (5-Zone: X축 3등분 + Y축 2등분)"
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON file")
    parser.add_argument(
        "--ai-ip", default=NetworkConfig.SERVER_IP, help="AI-G server IP address"
    )
    parser.add_argument(
        "--ai-frame-port",
        type=int,
        default=NetworkConfig.FRAME_PORT,
        help="AI-G frame input port"
    )
    parser.add_argument(
        "--ai-result-port",
        type=int,
        default=NetworkConfig.RESULT_PORT,
        help="AI-G result output port"
    )
    parser.add_argument(
        "--ipc-path",
        default="/dev/tcc_ipc_micom",
        help="Path to IPC device"
    )

    args = parser.parse_args()

    cfg = AppConfig(
        video_path=args.video,
        scenario_json=args.scenario,
        ai_g_host=args.ai_ip,
        ai_g_frame_port=args.ai_frame_port,
        ai_g_result_port=args.ai_result_port,
        ipc_path=args.ipc_path
    )

    if not cfg.validate():
        return 1

    with ScenarioPlayer(cfg) as player:
        player.run()

    return 0


if __name__ == "__main__":
    exit(main())