import av
import requests
import time
import threading
import logging
import tomllib
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_file: str = "config.toml") -> dict[str, Any]:
    """Load configuration from TOML file."""
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config


@dataclass
class Camera:
    number: int
    token: str
    fingerprint: str
    _container: Any = None  # av.InputContainer, lacks proper type stubs
    _decode_thread: threading.Thread | None = None
    _upload_thread: threading.Thread | None = None
    _frame_queue: queue.Queue[bytes] | None = None
    _stop_event: threading.Event | None = None
    
    def __post_init__(self) -> None:
        self._stop_event = threading.Event()
        self._frame_queue = queue.Queue[bytes](maxsize=1)  # Only keep the latest frame
        if not self.token or not self.fingerprint:
            raise ValueError(f"Camera {self.number}: token and fingerprint must be configured")
    
    def start(self) -> None:
        """Start the camera stream in background threads."""
        try:
            self._container = av.open(
                f'/dev/video{self.number}',
                format='mjpeg'
            )
            logger.info(f"Opened video device {self.number}")
            
            self._decode_thread = threading.Thread(
                target=self._decode_thread_fn,
                daemon=False,
                name=f"Camera-{self.number}-Decode"
            )
            self._decode_thread.start()
            logger.info(f"Started decode thread for camera {self.number}")
            
            self._upload_thread = threading.Thread(
                target=self._upload_thread_fn,
                daemon=False,
                name=f"Camera-{self.number}-Upload"
            )
            self._upload_thread.start()
            logger.info(f"Started upload thread for camera {self.number}")
        except Exception as e:
            logger.error(f"Failed to start camera {self.number}: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        """Stop the camera stream and clean up resources."""
        logger.info(f"Stopping camera {self.number}")
        if self._stop_event:
            self._stop_event.set()
        
        if self._decode_thread and self._decode_thread.is_alive():
            self._decode_thread.join(timeout=5)
            if self._decode_thread.is_alive():
                logger.warning(f"Decode thread for camera {self.number} did not stop gracefully")
        
        if self._upload_thread and self._upload_thread.is_alive():
            self._upload_thread.join(timeout=5)
            if self._upload_thread.is_alive():
                logger.warning(f"Upload thread for camera {self.number} did not stop gracefully")
        
        if self._container:
            try:
                self._container.close()  # type: ignore
            except Exception as e:
                logger.warning(f"Error closing container for camera {self.number}: {e}")
            logger.info(f"Closed video device {self.number}")

    def _decode_thread_fn(self) -> None:
        """Continuously decode frames from the camera."""
        if not self._container:
            logger.error(f"Container not initialized for camera {self.number}")
            return
        
        try:
            for packet in self._container.demux():  # type: ignore
                assert self._stop_event is not None
                if self._stop_event.is_set():
                    break
                
                try:
                    img_data = bytes(packet)  # type: ignore
                    # Put frame in queue, dropping old frame if queue is full
                    assert self._frame_queue is not None
                    try:
                        self._frame_queue.put_nowait(img_data)
                    except queue.Full:
                        # Queue is full, discard old frame and put new one
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self._frame_queue.put_nowait(img_data)
                except Exception as e:
                    logger.error(f"Error decoding packet from camera {self.number}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Decode thread crashed for camera {self.number}: {e}", exc_info=True)
        finally:
            logger.info(f"Decode thread ending for camera {self.number}")
    
    def _upload_thread_fn(self) -> None:
        """Continuously upload frames to Prusa Connect."""
        try:
            assert self._stop_event is not None
            while not self._stop_event.is_set():
                try:
                    # Wait for a frame with timeout to allow checking stop_event
                    assert self._frame_queue is not None
                    img_data = self._frame_queue.get(timeout=1)
                    
                    try:
                        headers = {
                            "Content-Type": "image/jpg",
                            "Token": self.token,
                            "Fingerprint": self.fingerprint,
                        }
                        response = requests.put(
                            "https://connect.prusa3d.com/c/snapshot",
                            headers=headers,
                            data=img_data,
                            timeout=10
                        )
                        response.raise_for_status()
                    except requests.RequestException as e:
                        logger.error(f"Failed to upload frame from camera {self.number}: {e}")
                    except Exception as e:
                        logger.error(f"Error uploading frame from camera {self.number}: {e}", exc_info=True)
                except queue.Empty:
                    # No frame available, continue waiting
                    continue
                except Exception as e:
                    logger.error(f"Upload thread error for camera {self.number}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Upload thread crashed for camera {self.number}: {e}", exc_info=True)
        finally:
            logger.info(f"Upload thread ending for camera {self.number}")


def main() -> None:
    """Main entry point."""
    try:
        config = load_config()
        logger.info("Configuration loaded")
        
        cameras: list[Camera] = []
        cam_configs: Any = config.get("cameras", [])
        for cam_config in cam_configs:  # type: ignore
            try:
                camera = Camera(
                    number=cam_config["number"],  # type: ignore
                    token=cam_config["token"],  # type: ignore
                    fingerprint=cam_config["fingerprint"],  # type: ignore
                )
                cameras.append(camera)
            except (KeyError, ValueError) as e:
                logger.error(f"Invalid camera configuration: {e}")
        
        if not cameras:
            logger.warning("No cameras configured")
            return
        
        # Start all cameras
        for camera in cameras:
            camera.start()
        
        logger.info(f"Started {len(cameras)} camera(s)")
        
        # Keep the application running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            for camera in cameras:
                camera.stop()
            logger.info("All cameras stopped")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()