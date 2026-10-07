
$WshShell = New-Object -ComObject WScript.Shell

# 1. Main Launcher Shortcut (JoyHotels.lnk)
$Shortcut1 = $WshShell.CreateShortcut("C:\Users\NAJUKA\Desktop\JoyHotels.lnk")
$Shortcut1.TargetPath = "C:\Windows\System32\wscript.exe"
$Shortcut1.Arguments = "`"C:\Users\NAJUKA\Desktop\joyhotels\Launch_JoyHotels.vbs`""
$Shortcut1.WorkingDirectory = "C:\Users\NAJUKA\Desktop\joyhotels"
$Shortcut1.Description = "Launch JoyHotels Application in Browser"
if (Test-Path "C:\Users\NAJUKA\Desktop\joyhotels\static\app_icon.ico") {
    $Shortcut1.IconLocation = "C:\Users\NAJUKA\Desktop\joyhotels\static\app_icon.ico"
}
$Shortcut1.Save()

# 2. Secondary Launcher Shortcut (Hotel Najuka.lnk)
$Shortcut2 = $WshShell.CreateShortcut("C:\Users\NAJUKA\Desktop\Hotel Najuka.lnk")
$Shortcut2.TargetPath = "C:\Windows\System32\wscript.exe"
$Shortcut2.Arguments = "`"C:\Users\NAJUKA\Desktop\joyhotels\Launch_JoyHotels.vbs`""
$Shortcut2.WorkingDirectory = "C:\Users\NAJUKA\Desktop\joyhotels"
$Shortcut2.Description = "Launch Hotel Najuka System in Browser"
if (Test-Path "C:\Users\NAJUKA\Desktop\joyhotels\static\app_icon.ico") {
    $Shortcut2.IconLocation = "C:\Users\NAJUKA\Desktop\joyhotels\static\app_icon.ico"
}
$Shortcut2.Save()

# 3. Delete old Chrome App Shortcut if it exists
if (Test-Path "C:\Users\NAJUKA\Desktop\JoyHotels App.lnk") {
    Remove-Item "C:\Users\NAJUKA\Desktop\JoyHotels App.lnk" -Force
}

Write-Host "All Desktop shortcuts created and verified!"
