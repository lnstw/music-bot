import asyncio
import random
import lava_lyra
import discord

# Set CustomQueue
class CustomQueue(lava_lyra.Queue):
    def __init__(self, max_size = None, max_history = 100, *, overflow = True):
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

    def _current_index(self) -> int:
        for i, t in enumerate(self._queue):
            if t is self._current_item:
                return i
        return -1

    def disable_loop(self) -> None:
        if self._loop_mode == lava_lyra.LoopMode.QUEUE:
            index = self._current_index()
            if index >= 0:
                del self._queue[:index + 1]
        self._loop_mode = None

    def upcoming(self) -> list[lava_lyra.Track]:
        """依實際播放順序回傳待播歌曲（不含正在播放的歌曲）"""
        if self._loop_mode == lava_lyra.LoopMode.QUEUE:
            index = self._current_index()
            if index >= 0:
                return self._queue[index + 1:] + self._queue[:index]
        return list(self._queue)

    def peek_upcoming(self) -> lava_lyra.Track | None:
        upcoming = self.upcoming()
        if upcoming:
            return upcoming[0]
        if self._loop_mode == lava_lyra.LoopMode.QUEUE and self._current_index() >= 0:
            return self._current_item
        return None

    def shuffle_upcoming(self) -> None:
        """打亂待播歌曲；循環模式下把目前歌曲放到最前面，其餘打亂接在後面"""
        if self._loop_mode == lava_lyra.LoopMode.QUEUE and self._current_index() >= 0:
            rest = self.upcoming()
            random.shuffle(rest)
            self._queue[:] = [self._current_item] + rest
        else:
            random.shuffle(self._queue)

    def clear_upcoming(self) -> None:
        if self._loop_mode == lava_lyra.LoopMode.QUEUE and self._current_index() >= 0:
            self._queue[:] = [self._current_item]
        else:
            self._queue.clear()

    def remove_upcoming(self, position: int) -> lava_lyra.Track:
        """移除待播清單中第 position 首（1 起算），回傳被移除的歌曲"""
        track = self.upcoming()[position - 1]
        for i, t in enumerate(self._queue):
            if t is track:
                del self._queue[i]
                break
        return track

    def insert_next(self, track: lava_lyra.Track, offset: int = 0) -> None:
        """插入到下一首（offset 為已插入的數量，用來保持多首插播的順序）"""
        if self._loop_mode == lava_lyra.LoopMode.QUEUE:
            index = self._current_index()
            if index >= 0:
                self.put_at_index(index + 1 + offset, track)
                return
        self.put_at_index(offset, track)

# Set CustomPlayer
class CustomPlayer(lava_lyra.Player):
    def __init__(self, client, channel, *, node = None):
        super().__init__(client, channel, node=node)
        self.queue = CustomQueue()
        self._last_track: lava_lyra.Track = None
        self._last_channel: discord.TextChannel | discord.VoiceChannel | discord.StageChannel = None
        self._volume_initialized = False
        self._advance_lock = asyncio.Lock()

    async def initialize_volume(self):
        if not self._volume_initialized:
            await self.set_volume(10)
            self._volume_initialized = True

    async def play_next(self) -> lava_lyra.Track:
        async with self._advance_lock:
            return await self._play_next()

    async def play_if_idle(self) -> lava_lyra.Track | None:
        """只有在目前沒有歌曲時才開始播放（給 /播放、播放清單用）"""
        async with self._advance_lock:
            if self.current is not None:
                return None
            return await self._play_next()

    async def on_track_finished(self, ended_track: lava_lyra.Track | None) -> lava_lyra.Track | None:
        async with self._advance_lock:
            if ended_track is not None and self.current is not None and self.current is not ended_track:
                return None
            return await self._play_next()

    async def _play_next(self) -> lava_lyra.Track:
        if self.queue.is_empty:
            return None

        try:
            track = self.queue.get()
        except lava_lyra.QueueEmpty:
            return None

        if track is None:
            return None

        if not self.queue.is_looping:
            self.queue.put_history(track)

        self._last_track = track

        await self.play(track)
        return track

    async def skip(self) -> lava_lyra.Track | None:
        async with self._advance_lock:
            track = await self._play_next()
            if track is None and self.current:
                await self.stop()
            return track

    def toggle_loop(self) -> bool:
        """切換佇列循環，回傳切換後是否為開啟"""
        if self.queue.loop_mode:
            self.queue.disable_loop()
            return False
        self.queue.set_loop_mode(lava_lyra.LoopMode.QUEUE)
        return True

    async def stop_and_clear(self):
        if self.queue.loop_mode:
            self.queue.disable_loop()
        self.queue.clear()
        if self.is_paused:
            await self.set_pause(False)
        if self.current:
            await self.stop()
