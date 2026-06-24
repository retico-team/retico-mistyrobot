import io
import os
import wave
import uuid
import tempfile
import requests
import time

from retico_core import AbstractConsumingModule, UpdateType
from retico_core.audio import AudioIU


class MistySpeakerModule(AbstractConsumingModule):

    @staticmethod
    def name():
        return "Misty Speaker Module"

    @staticmethod
    def description():
        return "Uploads audio to Misty and plays it."

    @staticmethod
    def input_ius():
        return AudioIU

    @staticmethod
    def output_iu():
        return None

    def __init__(
        self,
        ip,
        sample_rate=16000,
        sample_width=2,
        channels=1,
        volume=100,
        autoplay=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.ip = ip
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.volume = volume
        self.autoplay = autoplay

        self.audio_buffer = bytearray()

    def process_update(self, update_message):
        if not update_message:
            return

        final = False

        for iu, ut in update_message:

            if ut == UpdateType.ADD:

                 
                if hasattr(iu, "payload") and iu.payload is not None:
                    self.audio_buffer.extend(iu.payload)
                elif hasattr(iu, "raw_audio"):
                    self.audio_buffer.extend(iu.raw_audio)
                elif hasattr(iu, "audio"):
                    self.audio_buffer.extend(iu.audio)

            if len(self.audio_buffer) >= 32000:
                self._play_buffer()
                self.audio_buffer = bytearray()

        if final and len(self.audio_buffer) > 0:
            self._play_buffer()
            self.audio_buffer = bytearray()

    def _play_buffer(self):

        filename = f"retico_{uuid.uuid4().hex}.wav"

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as tmp:

            wav_path = tmp.name

        try:

            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.sample_width)
                wf.setframerate(self.sample_rate)
                wf.writeframes(bytes(self.audio_buffer))

            self._upload_audio(filename, wav_path)

            if self.autoplay:
                self._play_audio(filename)

        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def _upload_audio(self, filename, filepath):

        url = f"http://{self.ip}/api/audio"

        with open(filepath, "rb") as f:

            files = {
                "File": (filename, f, "audio/wav")
            }

            data = {
                "FileName": filename,
                "ImmediatelyApply": False,
                "OverwriteExisting": True,
            }

            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=30,
            )

            response.raise_for_status()

    def _play_audio(self, filename):

        url = f"http://{self.ip}/api/audio/play"

        payload = {
            "FileName": filename,
            "Volume": self.volume,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=10,
        )

        response.raise_for_status()