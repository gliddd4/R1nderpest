<?php
// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Function to generate random directory name
function generateRandomName($length = 16) {
    return bin2hex(random_bytes($length / 2));
}

// Function to read SQL dump from .png file
function readSQLDump($filename) {
    if (!file_exists($filename)) {
        die("Error: File $filename not found");
    }
    return file_get_contents($filename);
}

// Function to create SQLite database from SQL dump
function createSQLiteFromDump($sqlDump, $outputFile) {
    try {
        // Remove or replace ALL unistr() functions - more aggressive approach
        // Match unistr with single or double quotes, with or without spaces
        $sqlDump = preg_replace_callback(
            "/unistr\s*\(\s*['\"]([^'\"]*)['\"]\\s*\)/i",
            function($matches) {
                $str = $matches[1];
                // Convert \XXXX to actual unicode characters
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
        
        // Alternative: If still failing, just remove unistr entirely and keep the string
        $sqlDump = preg_replace("/unistr\s*\(\s*(['\"][^'\"]*['\"])\s*\)/i", "$1", $sqlDump);
        
        // Create SQLite database
        $db = new SQLite3($outputFile);
        
        // Split SQL dump into individual statements
        $statements = explode(';', $sqlDump);
        
        foreach ($statements as $statement) {
            $statement = trim($statement);
            if (!empty($statement) && strlen($statement) > 5) {
                // Execute statement, suppress errors
                @$db->exec($statement . ';');
            }
        }
        
        $db->close();
        return true;
    } catch (Exception $e) {
        die("Error creating SQLite database: " . $e->getMessage());
    }
}

// Стало:
$basePath = __DIR__;  // ← ВСЕГДА текущая папка скрипта

// Get parameters from URL
$prd = isset($_GET['prd']) ? $_GET['prd'] : '';
$guid = isset($_GET['guid']) ? $_GET['guid'] : '';
$sn = isset($_GET['sn']) ? $_GET['sn'] : '';

if (empty($prd) || empty($guid) || empty($sn)) {
    die("Error: Missing required parameters (prd, guid, sn)");
}

// Replace comma with dash in prd
$prdFormatted = str_replace(',', '-', $prd);

// Step 1: Get the plist file
$plistPath = "$basePath/Maker/$prdFormatted/com.apple.MobileGestalt.plist";

// Debug: Check actual file system
if (!file_exists($plistPath)) {
    // Try alternative paths
    $altPath1 = __DIR__ . "/Maker/$prdFormatted/com.apple.MobileGestalt.plist";
    $altPath2 = $_SERVER['DOCUMENT_ROOT'] . "/bee33/Maker/$prdFormatted/com.apple.MobileGestalt.plist";
    
    if (file_exists($altPath1)) {
        $plistPath = $altPath1;
        $basePath = __DIR__;
    } elseif (file_exists($altPath2)) {
        $plistPath = $altPath2;
        $basePath = $_SERVER['DOCUMENT_ROOT'] . "/bee33";
    } else {
        die("Error: Plist file not found. Tried:\n" . 
            "1. $plistPath\n" . 
            "2. $altPath1\n" . 
            "3. $altPath2\n" .
            "Script Dir: " . __DIR__ . "\n" .
            "Document Root: " . $_SERVER['DOCUMENT_ROOT']);
    }
}

// Step 2: Create ZIP file with Caches folder
$randomName1 = generateRandomName();
$firstStepDir = "$basePath/firststp/$randomName1";
if (!is_dir($firstStepDir)) {
    mkdir($firstStepDir, 0755, true);
}

$zipPath = "$firstStepDir/temp.zip";
$zip = new ZipArchive();

if ($zip->open($zipPath, ZipArchive::CREATE) !== TRUE) {
    die("Error: Cannot create ZIP file");
}

// Add plist to Caches folder in zip
$zip->addFile($plistPath, "Caches/com.apple.MobileGestalt.plist");
$zip->close();

// Rename zip to fixedfile
$fixedFilePath = "$firstStepDir/fixedfile";
rename($zipPath, $fixedFilePath);

// Get the URL for fixedfile
$protocol = isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http";
$host = $_SERVER['HTTP_HOST'];
$baseUrl = "$protocol://$host";
$fixedFileUrl = "$baseUrl/firststp/$randomName1/fixedfile";

// Step 3: Process BLDatabaseManager.png
$blDatabaseDump = readSQLDump("$basePath/BLDatabaseManager.png");

// Replace the URL in the dump
$blDatabaseDump = str_replace(
    'KEYOOOOOO',
    $fixedFileUrl,
    $blDatabaseDump
);

// Create SQLite database
$randomName2 = generateRandomName();
$secondStepDir = "$basePath/2ndd/$randomName2";
if (!is_dir($secondStepDir)) {
    mkdir($secondStepDir, 0755, true);
}

$blSqlitePath = "$secondStepDir/BLDatabaseManager.sqlite";
createSQLiteFromDump($blDatabaseDump, $blSqlitePath);

// Rename to BLDatabaseM.png
$blFinalPath = "$secondStepDir/belliloveu.png";
rename($blSqlitePath, $blFinalPath);

// Get the URL for BLDatabaseM.png
$blDatabaseUrl = "$baseUrl/2ndd/$randomName2/belliloveu.png";

// Step 4: Process downloads.28.png
$downloadsDump = readSQLDump("$basePath/downloads.28.png");

// Replace URLs and GOODKEY
$downloadsDump = str_replace('https://google.com', $blDatabaseUrl, $downloadsDump);
$downloadsDump = str_replace('GOODKEY', "$guid", $downloadsDump);

// Create final SQLite database
$randomName3 = generateRandomName();
$lastStepDir = "$basePath/last/$randomName3";
if (!is_dir($lastStepDir)) {
    mkdir($lastStepDir, 0755, true);
}

$finalSqlitePath = "$lastStepDir/downloads.sqlitedb";
createSQLiteFromDump($downloadsDump, $finalSqlitePath);

// Rename to filework.png
$finalPath = "$lastStepDir/apllefuckedhhh.png";
rename($finalSqlitePath, $finalPath);

// Get the URL for final file
$finalUrl = "$baseUrl/last/$randomName3/apllefuckedhhh.png";
function encryptAES($data, $key) {
    $method = 'aes-256-cbc';
    $iv = openssl_random_pseudo_bytes(openssl_cipher_iv_length($method));
    $encrypted = openssl_encrypt($data, $method, $key, 0, $iv);
    return base64_encode($encrypted . '::' . $iv);
}

$secretKey = 'E9454909B48F46B4904D34F79761BF4F'; // Keep this secure!

// ENCRYPT THE URL, NOT THE PATH!
//$finalUrl = "https://example.com";

// Вместо echo $finalUrl;
echo json_encode([
    'success' => true,
    'parameters' => [
        'prd' => $prd,
        'guid' => $guid,
        'sn' => $sn
    ],
    'links' => [
        'step1_fixedfile' => $fixedFileUrl,
        'step2_bldatabase' => $blDatabaseUrl,
        'step3_final' => $finalUrl
    ],
    'paths' => [
        'step1' => $fixedFilePath,
        'step2' => $blFinalPath,
        'step3' => $finalPath
    ]
], JSON_PRETTY_PRINT);// يظهر الرابط

//$fileContent = @file_get_contents($finalUrl);
//if ($fileContent === false) {
  //  http_response_code(500);
//    exit('File not found');
//}

// تشفير الملف - CRITICAL: استخدم OPENSSL_RAW_DATA
//$key = "YourSecretKey123";
//$key = str_pad($key, 32, "\0"); // تأكد أن المفتاح 32 بايت بالضبط
//$iv = openssl_random_pseudo_bytes(16);

// استخدم OPENSSL_RAW_DATA بدلاً من 0
//$encrypted = openssl_encrypt($fileContent, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);

// دمج IV مع الملف المشفر
//$finalData = base64_encode($iv . $encrypted);

// إرسال Headers
//header('Content-Type: text/plain');
//header('Content-Length: ' . strlen($finalData));
//header('Cache-Control: no-cache, no-store, must-revalidate');
//header('Pragma: no-cache');
//header('Expires: 0');

// إرسال البيانات
//echo $finalData;
//exit();










//echo $fileContent;
//exit();

// echo json_encode([
    // 'success' => true,
    // 'parameters' => [
        // 'prd' => $prd,
        // 'guid' => $guid,
        // 'sn' => $sn
    // ],
    // 'links' => [
        // 'step1_fixedfile' => $fixedFileUrl,
        // 'step2_bldatabase' => $blDatabaseUrl,
        // 'step3_final' => $finalUrl
    // ],
    // 'paths' => [
        // 'step1' => $fixedFilePath,
        // 'step2' => $blFinalPath,
        // 'step3' => $finalPath
    // ]
// ], JSON_PRETTY_PRINT);
?>