PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE asset (
    pid INTEGER, 
    download_id INTEGER, 
    asset_order INTEGER DEFAULT 0, 
    asset_type TEXT, 
    bytes_total INTEGER, 
    url TEXT, 
    local_path TEXT, 
    destination_url TEXT, 
    path_extension TEXT, 
    retry_count INTEGER, 
    http_method TEXT, 
    initial_odr_size INTEGER, 
    is_discretionary INTEGER DEFAULT 0, 
    is_downloaded INTEGER DEFAULT 0, 
    is_drm_free INTEGER DEFAULT 0, 
    is_external INTEGER DEFAULT 0, 
    is_hls INTEGER DEFAULT 0, 
    is_local_cache_server INTEGER DEFAULT 0, 
    is_zip_streamable INTEGER DEFAULT 0, 
    processing_types INTEGER DEFAULT 0, 
    video_dimensions TEXT, 
    timeout_interval REAL, 
    store_flavor TEXT, 
    download_token INTEGER DEFAULT 0, 
    blocked_reason INTEGER DEFAULT 0, 
    avfoundation_blocked INTEGER DEFAULT 0, 
    service_type INTEGER DEFAULT 0, 
    protection_type INTEGER DEFAULT 0,
    store_download_key TEXT, 
    etag TEXT, 
    bytes_to_hash INTEGER, 
    hash_type INTEGER DEFAULT 0, 
    server_guid TEXT, 
    file_protection TEXT, 
    variant_id TEXT, 
    hash_array BLOB, 
    http_headers BLOB, 
    request_parameters BLOB, 
    body_data BLOB, 
    body_data_file_path TEXT,
    sinfs_data BLOB, 
    dpinfo_data BLOB, 
    uncompressed_size INTEGER DEFAULT 0, 
    url_session_task_id INTEGER DEFAULT -1, 
    PRIMARY KEY (pid)
);
INSERT INTO asset VALUES(1,1,0,'media',0,'https://google.com',NULL,'/private/var/mobile/Media/iTunes_Control/iTunes/iTunesMetadata.plist','plist',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(2,1,0,'media',0,'https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite-wal','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(3,1,0,'media',0,'https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite-shm','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(4,1,0,'media',0,'https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
COMMIT;
