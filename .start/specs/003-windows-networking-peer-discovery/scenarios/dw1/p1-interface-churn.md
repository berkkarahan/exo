---
unit: dw1
feature: Windows-compatible discovery socket bind
priority: P1
---
# Discovery recovers after Windows interface churn without restart

## Scenario
On a Windows machine already connected to a macOS peer (confirmed via `GET /state`), disable the Wi-Fi adapter used for that connection via Windows network settings, wait 5 seconds, then re-enable it. Do not restart the exo process. Wait up to 15 seconds and query `GET /state` again.

## Expected
Immediately after disabling the adapter (or shortly after), the peer connection may be lost (acceptable — not asserted here).
Within 15 seconds of re-enabling the adapter, `GET /state` again shows the macOS peer's node ID in `topology.nodes`, without the Windows exo process having been restarted.
</content>
