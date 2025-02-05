import subprocess
import sys
import os
import json
import time

CONFIG_FILE = 'config.json'
SCREENSHOT_FOLDER = 'screenshots'
GENERATED_REPORTS_FOLDER = 'GeneratedReports'

dependencies = [
    'keyboard',
    'requests',
    'pillow',
    'pytz',
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
                sys.exit(1)  # Exit if installation fails

install_dependencies()

import keyboard
import pytz
from datetime import datetime
from PIL import ImageGrab
import requests

# Ensure required folders exist
for folder in [SCREENSHOT_FOLDER, GENERATED_REPORTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

class DutyTracker:
    def __init__(self):
        self.config = self.load_config()
        self.screenshots = []
        self.start_time = None
        self.end_time = None
        self.report_created = False  # To prevent multiple reports for same duty session

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
            response = requests.post(
                "https://api.imgur.com/3/upload", 
                headers=headers, 
                files={'image': image_file}
            )

        if response.status_code == 200:
            data = response.json()
            return data['data']['link']
        else:
            print(f"Upload failed: {response.text}")
            return None

    def take_screenshot(self, type):
        timestamp = datetime.now(pytz.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{SCREENSHOT_FOLDER}/{type}_{timestamp}.png"
        ImageGrab.grab().save(filename)
        return filename

    def on_start_end(self):
        if not self.start_time:
            # Start of duty
            self.start_time = datetime.now(pytz.utc)
            print("Duty START recorded")
            filename = self.take_screenshot('start')
            self.screenshots.append((filename, datetime.now(pytz.utc)))  # Store with creation time
        else:
            # End of duty
            self.end_time = datetime.now(pytz.utc)
            print("Duty END recorded")
            filename = self.take_screenshot('end')
            self.screenshots.append((filename, datetime.now(pytz.utc)))
            self.generate_report()

    def on_proof(self):
        if not self.start_time:
            print("Error: Start duty before taking proof!")
            return
            
        print("Proof screenshot taken")
        filename = self.take_screenshot('proof')
        self.screenshots.append((filename, datetime.now(pytz.utc)))

    def generate_report(self):
        if self.report_created:
            return

        # Sort screenshots by creation time
        sorted_screenshots = sorted(self.screenshots, key=lambda x: x[1])
        
        # Get relevant timestamps
        start_time = sorted_screenshots[0][1]
        proof_time = sorted_screenshots[1][1]
        end_time = sorted_screenshots[2][1]

        # Generate filename with start time timestamp
        report_filename = f"duty_report_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(GENERATED_REPORTS_FOLDER, report_filename)

        # Upload all screenshots and get links
        links = []
        for filename, _ in sorted_screenshots:
            link = self.upload_to_imgur(filename)
            if link:
                links.append(link)
            else:
                links.append("Upload Failed")

        # Format timezone display
        def format_time(dt):
            tz_offset = dt.strftime("%z")
            tz = "GMT" if tz_offset == "+0000" else f"GMT{int(tz_offset[:3])}"
            return f"{dt.strftime('%H:%M')} {tz}"

        # Write the report with the exact format requested
        with open(report_path, 'w') as f:
            f.write(f"Username: {self.config['username']}\n")
            f.write(f"Duty: {self.config['duty_reason']}\n")
            f.write(f"{links[1]}\n\n")  # Insert the duty proof link (second screenshot)

            f.write(f"Time Started: {format_time(start_time)}\n")
            f.write(f"Tablist Started: {links[0]}\n\n")

            f.write(f"Time Ended: {format_time(end_time)}\n")
            f.write(f"Tablist Ended: {links[2]}\n\n")

        print(f"Report generated: {report_path}")
        self.report_created = True

    def run(self):
        keyboard.add_hotkey(self.config['keybind_start_end'], self.on_start_end)
        keyboard.add_hotkey(self.config['keybind_proof'], self.on_proof)
        print("Program running. Press your configured keybinds to take screenshots.")
        keyboard.wait()

if __name__ == "__main__":
    DutyTracker().run()