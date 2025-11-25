import sys
import os
import time
import subprocess
import re
import shutil
import tempfile
import uuid
import atexit
import signal
import threading

class Style:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'

class BypassAutomation:
    def __init__(self):
        # --- Configuration ---
        self.api_url = "http://localhost:8000/get.php" # As per gist
        self.timeouts = {'reconnect_wait': 120, 'syslog_collect': 180, 'log_parse': 120, 'live_monitor': 45}
        self.device_info = {}
        self.guid = None
        atexit.register(self._cleanup)

    def log(self, msg, level='info'):
        """Consistent logging throughout the script."""
        if level == 'info': print(f"{Style.GREEN}[✓]{Style.RESET} {msg}")
        elif level == 'error': print(f"{Style.RED}[✗]{Style.RESET} {msg}")
        elif level == 'warn': print(f"{Style.YELLOW}[⚠]{Style.RESET} {msg}")
        elif level == 'step':
            print(f"\n{Style.BOLD}{Style.CYAN}" + "━" * 50 + f"{Style.RESET}")
            print(f"{Style.BOLD}{Style.BLUE}▶ {msg}{Style.RESET}")
            print(f"{Style.CYAN}" + "━" * 50 + f"{Style.RESET}")
        elif level == 'detail': print(f"{Style.DIM}  ╰─▶{Style.RESET} {msg}")
        elif level == 'success': print(f"\n{Style.GREEN}{Style.BOLD}[🎉 SUCCESS] {msg}{Style.RESET}\n")

    def _run_cmd(self, cmd, timeout=None):
        """Executes a shell command and returns its output."""
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout.strip(), stderr.strip()
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()  # Clean up
            self.log(f"Command timed out after {timeout}s: {' '.join(cmd)}", "warn")
            return 124, "", "Timeout"
        except Exception as e:
            self.log(f"Error running command {' '.join(cmd)}: {e}", "error")
            return 1, "", str(e)

    def _get_udid(self):
        """Retrieves the device's UDID."""
        code, out, err = self._run_cmd(["ideviceinfo", "-k", "UniqueDeviceID"])
        if code == 0 and out:
            return out
        self.log(f"Could not get device UDID. Error: {err}", "error")
        return None

    def is_device_connected(self):
        """
        Checks for device connectivity and service readiness.
        This queries a specific service domain, which is a good indicator that the
        device is fully booted and not just visible on the USB bus.
        """
        code, _, _ = self._run_cmd(["ideviceinfo", "-q", "com.apple.mobile.battery"])
        return code == 0

    def wait_for_device_disconnect(self, timeout=30, poll_interval=1):
        """
        Poll until the device disappears (disconnects).
        Returns True if device disconnected, False if timeout reached.
        """
        self.log("Waiting for device to disconnect...", "detail")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_device_connected():
                self.log("Device disconnected.", "detail")
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_reconnect(self, timeout):
        """Waits for the device to reconnect after a reboot using polling."""
        self.log(f"Waiting for device to reconnect (up to {timeout}s)...", "step")
        
        # Wait for device to disconnect first using polling (not hard sleep)
        self.log("Waiting for device to disconnect first...", "detail")
        self.wait_for_device_disconnect(timeout=30, poll_interval=1)
        
        self.log("Now actively polling for reconnection...", "detail")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_device_connected():
                self.log("Device reconnected!", "info")
                # Verify services are ready by checking again after brief poll
                self.log("Verifying services are stable...", "detail")
                stable_checks = 0
                for _ in range(3):
                    time.sleep(2)
                    if self.is_device_connected():
                        stable_checks += 1
                if stable_checks >= 2:
                    self.log("Device services stable.", "success")
                    return True
            time.sleep(2)
            
        self.log("Device did not reconnect in time.", "error")
        return False

    def detect_device(self, quiet=False):
        """Gathers and displays information about the connected device."""
        if not quiet: self.log("Detecting Device...", "step")
        if not self.is_device_connected():
            if not quiet: self.log("No device found. Please connect your device.", "error")
            return False

        code, out, err = self._run_cmd(["ideviceinfo"])
        if code != 0:
            if not quiet: self.log(f"Could not get device info. Error: {err}", "error")
            return False
        
        info = {}
        for line in out.splitlines():
            if ": " in line:
                key, val = line.split(": ", 1)
                info[key.strip()] = val.strip()
        self.device_info = info
        
        if not quiet:
            self.log("Device Detected:", "success")
            print(f"  {Style.BOLD}Model:{Style.RESET}    {info.get('ProductType', 'N/A')}")
            print(f"  {Style.BOLD}Version:{Style.RESET}  {info.get('ProductVersion', 'N/A')}")
            print(f"  {Style.BOLD}Serial:{Style.RESET}   {info.get('SerialNumber', 'N/A')}")
            print(f"  {Style.BOLD}UDID:{Style.RESET}     {info.get('UniqueDeviceID', 'N/A')}")
            if info.get('ActivationState') == 'Activated':
                print(f"\n{Style.YELLOW}Warning: Device is already activated.{Style.RESET}")
        return True

    def _try_live_syslog_monitoring(self):
        """
        Try to extract GUID using live syslog monitoring.
        This was the successful method from extract_guid.py.
        """
        self.log("Method 1: Live syslog monitoring (proven method)...", "detail")
        self.log(f"Monitoring device logs for {self.timeouts['live_monitor']} seconds...", "detail")
        
        try:
            proc = subprocess.Popen(
                ["pymobiledevice3", "syslog", "live"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='ignore'
            )
            
            guid_pattern = re.compile(r'SystemGroup/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/')
            
            start_time = time.time()
            found_guid = None
            lines_checked = 0
            relevant_lines = 0
            
            while time.time() - start_time < self.timeouts['live_monitor']:
                try:
                    line = proc.stdout.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    
                    lines_checked += 1
                    
                    if "BLDatabaseManager" in line or "SystemGroup" in line:
                        relevant_lines += 1
                        match = guid_pattern.search(line)
                        if match:
                            found_guid = match.group(1).upper()
                            self.log(f"GUID found in live logs: {found_guid}", "info")
                            proc.terminate()
                            proc.wait(timeout=2)
                            return found_guid
                except:
                    continue
            
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except:
                proc.kill()
            
            self.log(f"Live monitoring: checked {lines_checked} lines, found {relevant_lines} relevant lines, no GUID", "detail")
            return None
            
        except Exception as e:
            self.log(f"Live syslog monitoring failed: {e}", "warn")
            return None

    def _get_guid_from_logs(self):
        """
        The core GUID extraction logic. This function tries multiple methods:
        1. Live syslog monitoring (the proven successful method)
        2. Archived log collection and parsing
        """
        udid = self.device_info.get('UniqueDeviceID')
        if not udid:
            self.log("Cannot extract GUID without a UDID.", "error")
            return None

        # Method 1: Try live syslog monitoring first (this worked in extract_guid.py)
        found_guid = self._try_live_syslog_monitoring()
        if found_guid:
            return found_guid
        
        self.log("Live monitoring didn't find GUID, trying archive collection...", "warn")
        
        # Method 2: Try archive collection (original method)
        temp_log_dir = tempfile.mkdtemp(prefix="ios_logs_")
        log_archive_path = os.path.join(temp_log_dir, f"{udid}.logarchive")
        
        self.log("Collecting system logs archive (this can take up to 3 minutes)...", "detail")
        code, out, err = self._run_cmd(
            ["pymobiledevice3", "syslog", "collect", log_archive_path],
            timeout=self.timeouts['syslog_collect']
        )
        
        if code != 0 and code != 124:
             self.log(f"Syslog collection failed. Stderr: {err}", "warn")

        if not os.path.exists(log_archive_path):
            self.log("Syslog archive was not created.", "error")
            shutil.rmtree(temp_log_dir, ignore_errors=True)
            return None

        self.log("Syslog collected. Parsing with `log show`...", "detail")
        
        # Try different log show methods with proper Python timeout
        logs = None
        parse_methods = [
            {
                'name': 'Log show last 30 minutes',
                'cmd': ["/usr/bin/log", "show", "--last", "30m", "--archive", log_archive_path],
                'timeout': 60
            },
            {
                'name': 'Log show with info filter',
                'cmd': ["/usr/bin/log", "show", "--info", "--archive", log_archive_path],
                'timeout': 90
            },
            {
                'name': 'Standard log show with syslog style',
                'cmd': ["/usr/bin/log", "show", "--style", "syslog", "--archive", log_archive_path],
                'timeout': 120
            },
        ]
        
        for i, method in enumerate(parse_methods):
            self.log(f"Attempting: {method['name']}...", "detail")
            
            parse_code, stdout, parse_err = self._run_cmd(method['cmd'], timeout=method['timeout'])
            
            if parse_code == 0 and stdout:
                logs = stdout
                self.log(f"Successfully parsed logs with: {method['name']}", "info")
                self.log(f"Retrieved {len(stdout.splitlines())} lines of logs", "detail")
                break
            else:
                if parse_code == 124:
                    self.log(f"Method timed out, trying next approach...", "warn")
                else:
                    self.log(f"Method failed (code {parse_code})", "warn")

        if not logs:
            self.log("All log parsing methods failed.", "error")
            shutil.rmtree(temp_log_dir, ignore_errors=True)
            return None

        # Search for GUID pattern
        guid_pattern = re.compile(r'SystemGroup/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/')
        
        self.log("Searching for GUID pattern in parsed logs...", "detail")
        
        bldatabase_mentions = 0
        systemgroup_mentions = 0
        guid_candidates = set()
        
        for line in logs.splitlines():
            if "BLDatabaseManager" in line:
                bldatabase_mentions += 1
                match = guid_pattern.search(line)
                if match:
                    guid_candidates.add(match.group(1).upper())
            
            if "SystemGroup" in line:
                systemgroup_mentions += 1
                match = guid_pattern.search(line)
                if match:
                    guid_candidates.add(match.group(1).upper())
        
        self.log(f"Log analysis: {len(logs.splitlines())} lines, {bldatabase_mentions} BLDatabaseManager mentions, {systemgroup_mentions} SystemGroup mentions", "detail")
        
        if guid_candidates:
            found_guid = list(guid_candidates)[0]
            self.log(f"GUID found: {found_guid} (found {len(guid_candidates)} total candidates)", "info")
            shutil.rmtree(temp_log_dir, ignore_errors=True)
            return found_guid
        
        self.log("GUID pattern not found in archived logs.", "warn")
        shutil.rmtree(temp_log_dir, ignore_errors=True)
        return None

    def run(self):
        """The main orchestration workflow."""
        os.system('clear')
        print(f"{Style.BOLD}{Style.MAGENTA}A12 Bypass OSS - GUID Extraction Tool{Style.RESET}\n")

        if not self.detect_device():
            sys.exit(1)

        input(f"{Style.YELLOW}Press Enter to begin the GUID extraction process...{Style.RESET}\nMake sure the device is on the Activation Lock screen with Wi-Fi connected.")

        max_attempts = 3
        for attempt in range(max_attempts):
            self.log(f"GUID Extraction Attempt {attempt + 1} of {max_attempts}", "step")

            self.log("Rebooting device to trigger services...", "detail")
            self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
            
            if not self.wait_for_reconnect(self.timeouts['reconnect_wait']):
                self.log(f"Attempt {attempt + 1} failed: Device did not reconnect.", "warn")
                if attempt < max_attempts - 1:
                    # Poll for device readiness instead of hard 10s wait
                    self.log("Verifying device state before retry...", "detail")
                    start_wait = time.time()
                    while time.time() - start_wait < 10:
                        if self.is_device_connected():
                            break
                        time.sleep(2)
                continue

            # Re-detect device to ensure info is fresh after reboot
            self.detect_device(quiet=True)
            
            found_guid = self._get_guid_from_logs()
            if found_guid:
                self.guid = found_guid
                self.log(f"GUID Extracted Successfully: {self.guid}", "success")
                break
            
            if attempt < max_attempts - 1:
                self.log(f"Attempt {attempt+1} failed. Will wait and retry.", "warn")
                # Poll for device readiness instead of hard 20s wait
                self.log("Waiting for device to stabilize before retry...", "detail")
                start_wait = time.time()
                while time.time() - start_wait < 20:
                    if self.is_device_connected():
                        break
                    time.sleep(2)

        if not self.guid:
            self.log("PROCESS FAILED: Could not find GUID after multiple attempts.", "error")
            print("Please try running the tool again. Ensure the device is properly connected and on the Hello screen.")
            sys.exit(1)

        # --- Placeholder for rest of the activation process ---
        self.log("Proceeding to activation payload generation...", "step")
        print(f"\n{Style.CYAN}The tool would now use this GUID to contact the server at:{Style.RESET}")
        print(f"{self.api_url}?prd={self.device_info['ProductType']}&guid={self.guid}&sn={self.device_info['SerialNumber']}")
        print(f"\n{Style.GREEN}This completes the GUID extraction part of the task.{Style.RESET}")

    def _cleanup(self):
        """Cleans up any temporary files or mounts."""
        pass

if __name__ == '__main__':
    if os.geteuid() != 0:
        print(f"{Style.RED}[error]{Style.RESET} This script requires sudo. Please run with 'sudo python3 {sys.argv[0]}'")
        sys.exit(1)
    BypassAutomation().run()