Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the folder where this .vbs file lives
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = appDir

pythonPath = appDir & "\.venv\Scripts\python.exe"
appPath    = appDir & "\app.py"

' Check python.exe exists
If Not fso.FileExists(pythonPath) Then
    MsgBox "ERROR: .venv\Scripts\python.exe not found in:" & vbCrLf & appDir & vbCrLf & _
           "Please contact support.", 16, "JoyHotels Error"
    WScript.Quit
End If

' Check app.py exists
If Not fso.FileExists(appPath) Then
    MsgBox "ERROR: app.py not found in:" & vbCrLf & appDir, 16, "JoyHotels Error"
    WScript.Quit
End If

Function IsPortListening()
    IsPortListening = False
    Set checkExec = WshShell.Exec("cmd /c netstat -ano | findstr /R /C:""LISTENING.*:5000"" /C:"":5000 .*LISTENING""")
    Do While checkExec.Status = 0
        WScript.Sleep 50
    Loop
    If checkExec.ExitCode = 0 Then IsPortListening = True
End Function

' -------------------------------------------------------
' Check if port 5000 is already listening
' -------------------------------------------------------
portActive = IsPortListening()

' -------------------------------------------------------
' Start server if not running
' -------------------------------------------------------
If Not portActive Then
    ' Run Python directly in the background without opening a console window.
    WshShell.Run """" & pythonPath & """ """ & appPath & """", 0, False

    ' Wait up to 10 seconds polling for port 5000 to become active
    Dim waited : waited = 0
    Do While waited < 10000
        WScript.Sleep 600
        waited = waited + 600
        If IsPortListening() Then
            Exit Do
        End If
    Loop
End If

If Not IsPortListening() Then
    MsgBox "JoyHotels could not start on port 5000." & vbCrLf & _
           "Run Launch_JoyHotels.bat to see the startup error.", 16, "JoyHotels Error"
    WScript.Quit 1
End If

' -------------------------------------------------------
' Open in the default browser
' -------------------------------------------------------
WshShell.Run "cmd /c start http://localhost:5000", 0, False
