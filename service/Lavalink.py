import wavelink
from typing import Any

class LavalinkPlayerCompat(wavelink.Player):
    """Compatibility layer for Lavalink v4 voice payload requirements."""

    def _ensure_channel_id(self) -> None:
        channel = getattr(self, "channel", None)
        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return

        voice_payload = getattr(self, "_voice_state", None)
        if not isinstance(voice_payload, dict):
            return

        voice_data = voice_payload.setdefault("voice", {})
        voice_data.setdefault("channel_id", str(channel_id))

    async def on_voice_state_update(self, data: Any, /) -> None:
        await super().on_voice_state_update(data)
        self._ensure_channel_id()

    async def on_voice_server_update(self, data: Any) -> None:
        self._ensure_channel_id()
        await super().on_voice_server_update(data)

    async def _dispatch_voice_update(self) -> None:
        assert self.guild is not None
        self._ensure_channel_id()

        data = self._voice_state.get("voice", {})
        session_id = data.get("session_id")
        token = data.get("token")
        endpoint = data.get("endpoint")
        channel_id = data.get("channel_id")

        if not session_id or not token or not endpoint or not channel_id:
            return

        request = {
            "voice": {
                "sessionId": session_id,
                "token": token,
                "endpoint": endpoint,
                "channelId": str(channel_id),
            }
        }

        try:
            await self.node._update_player(self.guild.id, data=request)
        except Exception:
            await self.disconnect()
        else:
            self._connection_event.set()

    async def connect(self, **kwargs: Any):
        self._ensure_channel_id()
        return await super().connect(**kwargs)