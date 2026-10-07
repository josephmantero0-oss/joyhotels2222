import os
import subprocess

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
app_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(app_dir, "static", "app_icon.ico")
vbs_path = os.path.join(app_dir, "Launch_JoyHotels.vbs")
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell

# 1. Main Launcher Shortcut (JoyHotels.lnk)
$Shortcut1 = $WshShell.CreateShortcut("{desktop_path}\\JoyHotels.lnk")
$Shortcut1.TargetPath = "C:\\Windows\\System32\\wscript.exe"
$Shortcut1.Arguments = "`"{vbs_path}`""
$Shortcut1.WorkingDirectory = "{app_dir}"
$Shortcut1.Description = "Launch JoyHotels Application in Browser"
if (Test-Path "{icon_path}") {{
    $Shortcut1.IconLocation = "{icon_path}"
}}
$Shortcut1.Save()

# 2. Secondary Launcher Shortcut (Hotel Najuka.lnk)
$Shortcut2 = $WshShell.CreateShortcut("{desktop_path}\\Hotel Najuka.lnk")
$Shortcut2.TargetPath = "C:\\Windows\\System32\\wscript.exe"
$Shortcut2.Arguments = "`"{vbs_path}`""
$Shortcut2.WorkingDirectory = "{app_dir}"
$Shortcut2.Description = "Launch Hotel Najuka System in Browser"
if (Test-Path "{icon_path}") {{
    $Shortcut2.IconLocation = "{icon_path}"
}}
$Shortcut2.Save()

# 3. Delete old Chrome App Shortcut if it exists
if (Test-Path "{desktop_path}\\JoyHotels App.lnk") {{
    Remove-Item "{desktop_path}\\JoyHotels App.lnk" -Force
}}

Write-Host "All Desktop shortcuts created and verified!"
"""

ps_file = os.path.join(app_dir, "make_shortcuts.ps1")
with open(ps_file, "w", encoding="utf-8") as f:
    f.write(ps_script)

res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
