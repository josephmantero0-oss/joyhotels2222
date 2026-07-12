# JoyHotels Local Setup Guide

Follow these instructions to set up and run the JoyHotels application on a new Windows computer.

## 1. Prerequisites
Before starting, ensure the new computer has the following installed:
*   **Python 3.12 or higher**: Download from [python.org](https://www.python.org/downloads/). 
    *   **IMPORTANT**: During installation, check the box that says **"Add Python to PATH"**.
*   **Web Browser**: Chrome, Edge, or Firefox.

## 2. Transferring the Project
1.  Copy the `joyhotels` folder from your current PC to the new PC (e.g., to the Desktop).
2.  **Note**: You do NOT need to copy the `.venv` folder. We will create a fresh one.

## 3. Initial Setup (One-time only)
Open a terminal (PowerShell or Command Prompt) inside the `joyhotels` folder and run these commands:

1.  **Create a Virtual Environment**:
    ```powershell
    python -m venv .venv
    ```

2.  **Activate the Environment**:
    ```powershell
    .venv\Scripts\activate
    ```

3.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

## 4. How to Run the App (Automated)
The easiest way for staff to run the system:
1.  Go to the **Desktop**.
2.  Double-click the **"JoyHotels - Start System"** shortcut.
3.  This will automatically:
    *   Open the terminal.
    *   Start the hotel server.
    *   Open the Dashboard in your web browser.

**Note**: Keep the terminal window open while you are using the system. You can minimize it, but do not close it until you are finished for the day.

## 5. Manual Startup (For Developers)
Every time you want to start the hotel system manually:
1.  Open the folder in Terminal.
2.  Activate the environment: `.venv\Scripts\activate`
3.  Run the application:
    ```powershell
    python app.py
    ```
4.  The terminal will show something like `Running on http://0.0.0.0:5000`.

## 6. Accessing the Dashboard
*   **On the same PC**: Open your browser and go to `http://localhost:5000`.
*   **On a Mobile Phone (for QR Scanning)**:
    1.  Find your PC's IP address: Type `ipconfig` in a new CMD window. Look for `IPv4 Address` (e.g., `192.168.1.10`).
    2.  Ensure your phone and PC are on the **SAME WiFi network**.
    3.  Open the browser on your phone and go to `http://192.168.1.10:5000`.

## 7. Troubleshooting
*   **"Site can't be reached" on phone**: 
    *   Check if Windows Firewall is blocking the connection. You may need to allow `python.exe` through the firewall or open Port 5000.
*   **Missing Data**: Ensure the `hotel.db` file was copied over correctly. This file stores all your hotel settings, rooms, and guest history.
