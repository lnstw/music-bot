import lava_lyra
import discord

# Set CustomQueue
class CustomQueue(lava_lyra.Queue):
    def __init__(self, max_size = None, max_history = 0, *, overflow = True):
        super().__init__(max_size, overflow=overflow)
        self._history: list = []
        self._max_history: int = max_history

    def put_history(self, track: lava_lyra.Track):
        if len(self._history) >= self._max_history and self._max_history > 0:
            if not self._overflow:
                raise lava_lyra.QueueFull('History is full.')
            
            self._history.pop(0)

        self._history.append(track)

    def clear_history(self):
        self._history.clear()
    
    def get_history(self) -> list:
        return self._history

# Set CustomPlayer
class CustomPlayer(lava_lyra.Player):
    def __init__(self, client, channel, *, node = None):
        super().__init__(client, channel, node=node)
        self.queue = CustomQueue()
        self._last_track: lava_lyra.Track = None
        self._last_channel: discord.TextChannel | discord.VoiceChannel | discord.StageChannel = None
        self._volume_initialized = False
    
    async def initialize_volume(self):
        if not self._volume_initialized:
            await self.set_volume(10)
            self._volume_initialized = True

    async def play_next(self) -> lava_lyra.Track:
        if self.is_playing:
            await self.stop()

        if self.queue.is_empty:
            return None

        track = self.queue.get()

        if track is None:
            return None

        if not self.queue.is_looping:
            self.queue.put_history(track)

        self._last_track = track

        await self.play(track)
        return track