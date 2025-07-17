import cv2
import numpy as np
import time
import requests
import signal

from PIL import Image

try:
    import thread
except ImportError:
    import _thread as thread

from retico_core import abstract, UpdateMessage, UpdateType
from retico_vision import ImageIU

class MistyCameraStreamModule(abstract.AbstractProducingModule):
    @staticmethod
    def name():
        return "Misty II Camera Video Module"

    @staticmethod
    def description():
        return "A Module that tracks the Misty II Robot camera"

    @staticmethod
    def output_iu():
        return ImageIU

    def __init__(self, ip, rtsp_port=1936, res_width=1280, res_height=960, framerate=20, pil=True, **kwargs):
        super().__init__(**kwargs)
        self.cap = None
        self.pil = pil
        self.ip = ip
        self.rtsp_port = rtsp_port
        self.res_width = res_width
        self.res_height = res_height
        self.framerate = framerate
        self.next_container = None
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def enable_av_streaming(self):
        """
        Sends a POST request to enable AV streaming on the robot.
        Returns:
            dict: A dictionary containing the response status and message.
        """
        url = f"http://{self.ip}/api/services/avstreaming/enable"
        try:
            response = requests.post(url)
            response.raise_for_status()
            return {"status": "success", "message": response.json()}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def start_av_streaming(self, url, width=1280, height=960, frame_rate=30, video_bit_rate=5000000, audio_bit_rate=128000,
                           audio_sample_rate_hz=44100):
        """
        Sends a POST request to start AV streaming on the robot with the specified parameters.

        Args:
            url (string): The URL to stream the video to, using rtspd protocol.
            width (int): The width of the video stream.
            height (int): The height of the video stream.
            frame_rate (int): The frame rate of the video stream.
            video_bit_rate (int): The video bit rate.
            audio_bit_rate (int): The audio bit rate.
            audio_sample_rate_hz (int): The audio sample rate in Hz.
        Returns:
            dict: A dictionary containing the response status and message.
        """
        url = (f"http://{self.ip}/api/avstreaming/start?"
               f"url={url}&width={width}&height={height}&frameRate={frame_rate}&"
               f"videoBitRate={video_bit_rate}&audioBitRate={audio_bit_rate}&"
               f"audioSampleRateHz={audio_sample_rate_hz}")
        try:
            response = requests.post(url)
            response.raise_for_status()
            return {"status": "success", "message": response.json()}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def stop_av_streaming(self):
        """
        Sends a POST request to stop AV streaming on the robot.

        Returns:
            dict: A dictionary containing the response status and message.
        """
        url = f"http://{self.ip}/api/avstreaming/stop"
        try:
            response = requests.post(url)
            response.raise_for_status()
            return {"status": "success", "message": response.json()}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def setup(self):
        while self.enable_av_streaming()["status"] != "success":
            print("Waiting for AV streaming to be enabled...")
            time.sleep(1)
        print("AV streaming enabled successfully.")

        while self.start_av_streaming(f"rtspd:{self.rtsp_port}", width=1280, height=960)["status"] != "success":
            print("Waiting for AV streaming to start...")
            time.sleep(1)
        print("AV streaming started successfully.")

        self.cap = cv2.VideoCapture(f"rtsp://{self.ip}:{self.rtsp_port}/video")

    def process_update(self, _):
        um = UpdateMessage()
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)
            frame = frame.rotate(270)
            frame = frame.resize((self.res_width, self.res_height))
            if not self.pil:
                frame = np.asarray(frame)
            output_iu = self.create_iu()
            output_iu.set_image(frame, 1, self.framerate)
            um.add_iu(output_iu, UpdateType.ADD)
        return um

    def _handle_exit(self, signum, frame):
        """
        Handles termination signals and ensures cleanup.
        """
        print(f"Signal {signum} received. Cleaning up...")
        self.shutdown()

    def shutdown(self):
        """
        Stops the AV streaming and cleans up resources when the module is stopped.
        """
        print("Shutting down MistyCameraStreamModule...")
        self.stop_av_streaming()
        super().shutdown()
