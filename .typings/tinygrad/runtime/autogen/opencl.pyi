class _CData: ...

class _ArrayInstance:
    def __getitem__(self, index: int) -> _CData: ...

class _ArrayType:
    def __call__(self, item: _CData | None = None) -> _ArrayInstance: ...

class _CType:
    def __mul__(self, count: int) -> _ArrayType: ...

cl_platform_id: _CType
cl_device_id: _CType
CL_DEVICE_TYPE_GPU: int

def clGetPlatformIDs(
    num_entries: int,
    platforms: object,
    num_platforms: object,
) -> int: ...
def clGetDeviceIDs(
    platform: object,
    device_type: int,
    num_entries: int,
    devices: object,
    num_devices: object,
) -> int: ...
