---
unit: svc1
feature: Windows Service Host & Process Supervisor
priority: P0
---
# Dashboard reachable after reboot with no one logged in

## Scenario
Install exo in Windows Service mode on a test machine. Reboot the machine and leave it sitting at the Windows lock screen — do not log in. Wait a reasonable startup window, then from a second device on the same network, open a browser (or `curl`) to `http://<test-machine-ip>:52415`.

## Expected
The dashboard HTML (or `/state` JSON) is returned successfully.
No terminal, console window, or any visible UI is required or present on the test machine for this to work.
The response arrives without any user having logged into the test machine at any point after boot.
