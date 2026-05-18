import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch

import requests


av_module = types.ModuleType("av")
container_module = types.ModuleType("av.container")


class _InputContainer:
    pass


container_module.InputContainer = _InputContainer
av_module.container = container_module
sys.modules.setdefault("av", av_module)
sys.modules.setdefault("av.container", container_module)

import main


class UploadFrameRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        config = main.CameraConfig(number=0, token="token", fingerprint="fingerprint")
        self.camera = main.Camera(config)

    @patch("main.time.sleep")
    @patch("main.requests.put")
    def test_retries_429_with_retry_after_header(self, mock_put: MagicMock, mock_sleep: MagicMock) -> None:
        rate_limited = MagicMock(status_code=429, headers={"Retry-After": "3"})
        successful = MagicMock(status_code=200, headers={})
        successful.raise_for_status = MagicMock()
        mock_put.side_effect = [rate_limited, successful]

        self.camera._upload_frame(b"frame")

        self.assertEqual(mock_put.call_count, 2)
        mock_sleep.assert_called_once_with(3)
        successful.raise_for_status.assert_called_once()

    @patch("main.logger")
    @patch("main.time.sleep")
    @patch("main.requests.put")
    def test_retries_429_with_exponential_backoff_until_limit(
        self, mock_put: MagicMock, mock_sleep: MagicMock, mock_logger: MagicMock
    ) -> None:
        mock_put.side_effect = [MagicMock(status_code=429, headers={}) for _ in range(5)]

        self.camera._upload_frame(b"frame")

        self.assertEqual(mock_put.call_count, 5)
        mock_sleep.assert_has_calls([call(1), call(2), call(4), call(8)])
        self.assertEqual(mock_sleep.call_count, 4)
        mock_logger.error.assert_called_once()

    @patch("main.time.sleep")
    @patch("main.requests.put")
    def test_retries_request_exception_with_exponential_backoff(
        self, mock_put: MagicMock, mock_sleep: MagicMock
    ) -> None:
        successful = MagicMock(status_code=200, headers={})
        successful.raise_for_status = MagicMock()
        mock_put.side_effect = [requests.RequestException("network error"), successful]

        self.camera._upload_frame(b"frame")

        self.assertEqual(mock_put.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        successful.raise_for_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
