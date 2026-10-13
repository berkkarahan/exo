# Requirements: Launcher Driver Version

## User Stories

### Story: See which driver the selected GPU is using

When the Windows launcher lists an AMD adapter, the row and the status line include the OpenCL driver version for that adapter name. CPU and an unmatched adapter stay unlabeled.

## Acceptance Criteria

1. [x] An adapter name with one OpenCL driver version stores that version on the device row.
2. [x] An adapter name with two different driver versions stores an empty version.
3. [x] The dropdown caption and the status device line include the version when it is present.
4. [x] A saved row still restores by the adapter label, without the driver version.
5. [x] Enumeration failure leaves the launcher with adapter names and empty driver versions.

## Out of Scope

- Windows firewall rules.
- Peer-discovery probes.
- Sleep, resume, disconnect, and rejoin.
