Fails to activate, will finish s0n.

Feel free to contribute if your code works, we're all on the same team 


# iOS Activation Tool Suite

A complete, end-to-end solution for iOS device activation management. This repository contains both the client-side automation logic and the server-side infrastructure required to handle device activation payloads.

## Architecture Overview

The suite is divided into two core components:

- **Client Automation (`client/`)**: A Python-based utility that interacts directly with connected iOS devices via USB. It handles lifecycle management (reboots), system log analysis, and filesystem operations (AFC).

- **Server Backend (`server/`)**: A PHP application that dynamically generates device-specific activation payloads. It serves as the central authority for handling device requests and delivering the necessary configuration databases.

## Repository Structure

```
.
├── LICENSE
├── README.md
├── client/                # Python client application
│   ├── activator.py       # Main automation entry point
│   └── README.md          # Client-specific documentation
├── client.cs              # C# client source
├── client_windows.cs      # Windows C# client source
├── ios.exe                # Windows executable
├── offline_bypass.py      # Offline bypass script
└── server/                # PHP backend infrastructure
    ├── SETUP.md           # Server deployment guide
    ├── assets/            # Device configuration storage
    ├── cron/              # Cron job scripts
    ├── public/            # Web root
    └── templates/         # SQL templates for payload generation
```


## Prerequisites

### Client-Side (macOS/Linux)

- Python 3.6+

- `libimobiledevice` (via Homebrew on macOS)

- `pymobiledevice3` (via pip)

- `curl`

### Server-Side

- PHP 7.4 or newer

- SQLite3 extension enabled

- Write permissions for cache directories

## Quick Start
### 1. Server Deployment

Deploy the contents of the `server` directory from the release package to your web host. Ensure the `public` folder is set as the document root.

See [server/SETUP.md](server/SETUP.md) for detailed configuration steps.

### 2. Client Configuration

Update the `activator.py` script to point to your deployed server URL before running.

### 3. Run the client tool
```
sudo python3 client/activator.py
```


## Disclaimer

This tool is provided for educational and research purposes only. The authors are not responsible for any misuse of this software or damage to devices. Ensure you have authorization before performing operations on any device.
