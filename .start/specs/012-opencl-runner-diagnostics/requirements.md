# Requirements: OpenCL Runner Diagnostics

## User Stories

### Story: See why a Tinygrad runner stopped

When a Windows Tinygrad runner stops because OpenCL could not compile a kernel, allocate device memory, or lost the device, the shutdown report names that cause.

## Acceptance Criteria

1. [x] A stderr line containing `OpenCL Compile Error` is a compile diagnostic.
2. [x] `OpenCL Error` lines whose name is `CL_MEM_OBJECT_ALLOCATION_FAILURE`, `CL_OUT_OF_RESOURCES`, or `CL_OUT_OF_HOST_MEMORY` are allocation diagnostics.
3. [x] `OpenCL Error` lines whose name is `CL_DEVICE_NOT_FOUND` or `CL_DEVICE_NOT_AVAILABLE`, and lines that say device lost, are device-loss diagnostics.
4. [x] Any other `OpenCL Error` name stays unclassified.
5. [x] Metal GPU timeout and MLX ring diagnostics still classify as they do today.

## Out of Scope

- Progress deadlines for compile, prefill, decode, and transport.
- Handshake identity, request sequencing, sleep/resume, and disconnect/rejoin.
- Launcher stop, restart, and accelerator status.
