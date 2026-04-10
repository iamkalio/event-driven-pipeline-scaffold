"""gRPC client shell for an external model server."""

import asyncio

import grpc
import structlog

from src.config import Settings


class ModelServerClient:
    """Manages a gRPC channel for future generated model stubs."""

    def __init__(self, settings: Settings) -> None:
        """Store settings for later channel initialization.

        Args:
            settings: Application settings.

        Returns:
            None.
        """
        self._target = settings.AI_MODEL_SERVER_URL.replace('dns:///', '')
        self._logger = structlog.get_logger(__name__)
        self._channel: grpc.aio.Channel | None = None

    async def start(self) -> None:
        """Open the gRPC channel to the model server.

        Args:
            None.

        Returns:
            None.
        """
        if self._channel is None:
            self._channel = grpc.aio.insecure_channel(self._target)

    async def close(self) -> None:
        """Close the gRPC channel if it exists.

        Args:
            None.

        Returns:
            None.
        """
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    async def healthcheck(self) -> bool:
        """Check whether the external model server is reachable.

        Args:
            None.

        Returns:
            True when the channel becomes ready in time.
        """
        if self._channel is None:
            await self.start()
        try:
            await asyncio.wait_for(self._channel.channel_ready(), timeout=1.0)
            return True
        except Exception as exc:
            self._logger.warning('model_client.unavailable', error=str(exc))
            return False
