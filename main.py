import subprocess
import sys
import os
import json
import time
from threading import Timer

CONFIG_FILE = 'config.json'
SCREENSHOT_FOLDER = 'screenshots'
GENERATED_REPORTS_FOLDER = 'GeneratedReports'

dependencies = [
    'keyboard',
    'requests',
    'pillow',
    'pytz',
    'win10toast'
]

def install_dependencies():
    for package in dependencies:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e}")
                sys.exit(1)

install_dependencies()

import keyboard
import pytz
from datetime import datetime
from PIL import ImageGrab
import requests
from win10toast import ToastNotifier

for folder in [SCREENSHOT_FOLDER, GENERATED_REPORTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

class DutyTracker:
    def __init__(self):
        self.config = self.load_config()
        self.screenshots = []
        self.start_time = None
        self.end_time = None
        self.report_created = False
        self.notification_timer = None

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            return self.first_time_setup()

    def first_time_setup(self):
        print("First time setup:")
        config = {
            'username': input("Enter your Roblox username: "),
            'duty_reason': input("Enter your preferred duty state reason: "),
            'keybind_start_end': input("Enter keybind for duty state start/end (e.g., ctrl+shift+s): "),
            'keybind_proof': input("Enter keybind for duty proof screenshot (e.g., ctrl+shift+p): "),
            'imgur_client_id': input("Enter your Imgur Client ID (get from https://api.imgur.com/oauth2/addclient): ")
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Config saved to {CONFIG_FILE}. You can edit this file to change settings.")
        return config

    def upload_to_imgur(self, image_path):
        headers = {
            'Authorization': f'Client-ID {self.config["imgur_client_id"]}',
        }
        with open(image_path, 'rb') as image_file:
            response = requests.post("https://api.imgur.com/3/upload", headers=headers, files={'image': image_file})
        if response.status_code == 200:
            data = response.json()
            return data['data']['link']
        else:
            print(f"Upload failed: {response.text}")
            return None

    def take_screenshot(self, screenshot_type):
        timestamp = datetime.now(pytz.utc).strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SCREENSHOT_FOLDER, f"{screenshot_type}_{timestamp}.png")
        ImageGrab.grab().save(filename)
        return filename

    def send_notification(self):
        try:
            toaster = ToastNotifier()
            toaster.show_toast("Duty State Reminder", "30 minutes have passed. You can end your duty state now.", duration=10)
        except Exception as e:
            print(f"Error showing notification: {e}")
        return 0

    def on_start_end(self):
        if not self.start_time:
            self.start_time = datetime.now(pytz.utc)
            print(f"Duty START recorded at {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            filename = self.take_screenshot('start')
            self.screenshots.append((filename, datetime.now(pytz.utc)))
            self.notification_timer = Timer(1800, self.send_notification)
            self.notification_timer.start()
        else:
            if self.notification_timer:
                self.notification_timer.cancel()
            self.end_time = datetime.now(pytz.utc)
            print("Duty END recorded")
            filename = self.take_screenshot('end')
            self.screenshots.append((filename, datetime.now(pytz.utc)))
            self.generate_report()
        return 0

    def on_proof(self):
        if not self.start_time:
            print("Error: Start duty before taking proof!")
            return 0
        print("Proof screenshot taken")
        filename = self.take_screenshot('proof')
        self.screenshots.append((filename, datetime.now(pytz.utc)))
        return 0

    def generate_report(self):
        if self.report_created:
            return
        sorted_screenshots = sorted(self.screenshots, key=lambda x: x[1])
        start_time = self.start_time
        end_time = self.end_time
        start_img_url = self.upload_to_imgur(sorted_screenshots[0][0])
        end_img_url = self.upload_to_imgur(sorted_screenshots[-1][0])
        header_img_url = None
        if len(sorted_screenshots) >= 3:
            header_img_url = self.upload_to_imgur(sorted_screenshots[1][0])
        if not header_img_url:
            header_img_url = "https://i.imgur.com/jvuKKCd.jpeg"
        def format_time(dt):
            tz_offset = dt.strftime("%z")
            tz = "GMT" if tz_offset == "+0000" else f"GMT{int(tz_offset[:3])}"
            return f"{dt.strftime('%H:%M')} {tz}"
        formatted_start_time = format_time(start_time)
        formatted_end_time = format_time(end_time)
        report_text = (
            f"Username: {self.config['username']}\n"
            f"Duty: {self.config['duty_reason']}\n"
            f"{header_img_url}\n\n"
            f"Time Started: {formatted_start_time}\n"
            f"Tablist Started: {start_img_url}\n\n"
            f"Time Ended: {formatted_end_time}\n"
            f"Tablist Ended: {end_img_url}\n"
        )
        report_filename = f"duty_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(GENERATED_REPORTS_FOLDER, report_filename)
        with open(report_path, 'w') as f:
            f.write(report_text)
        print(f"Report generated: {report_path}")
        print(report_text)
        self.report_created = True

    def run(self):
        keyboard.add_hotkey(self.config['keybind_start_end'], self.on_start_end)
        keyboard.add_hotkey(self.config['keybind_proof'], self.on_proof)
        print("Program running. Use your configured keybinds to record duty state and take proof screenshots.")
        keyboard.wait()

if __name__ == "__main__":
    import sys
    class DevNull:
        def write(self, _):
            pass
        def flush(self):
            pass
    original_stderr = sys.stderr
    sys.stderr = DevNull()
    try:
        DutyTracker().run()
    finally:
        sys.stderr = original_stderr
