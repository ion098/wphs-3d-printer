import av
import requests
import time
import threading
import logging
import tomllib
import queue
from pathlib import Path
from typing import Annotated
from av.container import InputContainer
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='\x1b[7m%(asctime)s\x1b[0m - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CameraConfig(BaseModel):
    """Configuration for a single camera."""
    number: int = Field(..., ge=0, description="Camera device number")
    token: str = Field(..., min_length=1, description="Prusa Connect API token")


class AppConfig(BaseModel):
    """Application configuration."""
    cameras: Annotated[list[CameraConfig], Field(description="List of cameras")] = []


def load_config(config_file: str = "config.toml") -> AppConfig:
    """Load and validate configuration from TOML file."""
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_path, "rb") as f:
        config_dict = tomllib.load(f)
    return AppConfig(**config_dict)


class Camera:
    """Manages a single camera stream and upload to Prusa Connect."""
    
    def __init__(self, config: CameraConfig) -> None:
        self.number = config.number
        self.token = config.token
        self._container: InputContainer | None = None
        self._decode_thread: threading.Thread | None = None
        self._upload_thread: threading.Thread | None = None
        self._frame_queue: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._stop_event: threading.Event = threading.Event()
    
    def start(self) -> None:
        """Start the camera stream in background threads."""
        try:
            self._container = av.open(
                f'/dev/video{self.number}',
                format='v4l2',
                options={
                    'input_format': 'mjpeg'
                }
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
                self._container.close()
            except Exception as e:
                logger.warning(f"Error closing container for camera {self.number}: {e}")
            logger.info(f"Closed video device {self.number}")

    def _decode_thread_fn(self) -> None:
        """Continuously decode frames from the camera."""
        if not self._container:
            logger.error(f"Container not initialized for camera {self.number}")
            return
        
        try:
            for packet in self._container.demux():
                if self._stop_event.is_set():
                    break
                
                try:
                    img_data = bytes(packet)  # type: ignore
                    # Put frame in queue, replacing old frame if full
                    try:
                        self._frame_queue.put_nowait(img_data)
                    except queue.Full:
                        self._frame_queue.get_nowait()
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
            while not self._stop_event.is_set():
                try:
                    img_data = self._frame_queue.get(timeout=1)
                    self._upload_frame(img_data)
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Upload thread error for camera {self.number}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Upload thread crashed for camera {self.number}: {e}", exc_info=True)
        finally:
            logger.info(f"Upload thread ending for camera {self.number}")
    
    def _upload_frame(self, img_data: bytes) -> None:
        """Upload a single frame to Prusa Connect."""
        headers = {
            "Content-Type": "image/jpg",
            "Token": self.token,
            "Fingerprint": self.token,
        }
        for i in range(5):
            try:
                response = requests.put(
                    "https://connect.prusa3d.com/c/snapshot",
                    headers=headers,
                    data=img_data,
                    timeout=100
                )
                response.raise_for_status()
                logger.info("\x1b[32mUploaded frame!\x1b[0m")
                time.sleep(1)
                break
            except requests.RequestException as e:
                logger.error(f"\x1b[33mFailed to upload frame from camera {self.number}: {e}\x1b[0m")
                for j in range(2 ** i):
                    if self._stop_event.is_set():
                        return
                    time.sleep(1)


def main() -> None:
    """Main entry point."""
    try:
        config = load_config()
        logger.info("Configuration loaded")
        
        if not config.cameras:
            logger.warning("No cameras configured")
            return
        
        cameras = [Camera(cam_config) for cam_config in config.cameras]
        
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
