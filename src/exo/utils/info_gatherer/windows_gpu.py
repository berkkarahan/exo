"""Windows-only DXGI/D3D12 GPU adapter probe.

Cheaply detects a real, non-software DirectX 12 adapter (i.e. a DirectML-capable
GPU) using raw ctypes COM calls. Deliberately avoids importing onnxruntime or any
ML runtime so the probe stays fast (well under 50ms) and side-effect free.
"""

import ctypes
import sys

_IID_IDXGI_FACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"
_IID_ID3D12_DEVICE = "189819f1-1db6-4b57-be54-1821339b85f7"

_DXGI_ERROR_NOT_FOUND = 0x887A0002
_DXGI_ADAPTER_FLAG_SOFTWARE = 0x2
_DXGI_ADAPTER_FLAG_REMOTE = 0x4
_MS_BASIC_RENDER_VENDOR_ID = 0x1414
_MS_BASIC_RENDER_DEVICE_ID = 0x008C
_D3D_FEATURE_LEVEL_11_0 = 0xB000

_ENUM_ADAPTERS1_SLOT = 12
_GET_DESC1_SLOT = 10
_RELEASE_SLOT = 2


class _Luid(ctypes.Structure):
    LowPart: int
    HighPart: int
    _fields_ = (
        ("LowPart", ctypes.c_uint32),
        ("HighPart", ctypes.c_int32),
    )


class _DxgiAdapterDesc1(ctypes.Structure):
    Description: str
    VendorId: int
    DeviceId: int
    SubSysId: int
    Revision: int
    DedicatedVideoMemory: int
    DedicatedSystemMemory: int
    SharedSystemMemory: int
    AdapterLuid: _Luid
    Flags: int
    _fields_ = (
        ("Description", ctypes.c_wchar * 128),
        ("VendorId", ctypes.c_uint32),
        ("DeviceId", ctypes.c_uint32),
        ("SubSysId", ctypes.c_uint32),
        ("Revision", ctypes.c_uint32),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _Luid),
        ("Flags", ctypes.c_uint32),
    )


class _Guid(ctypes.Structure):
    Data1: int
    Data2: int
    Data3: int
    Data4: ctypes.Array[ctypes.c_ubyte]
    _fields_ = (
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    )


def _guid_from_str(guid: str) -> _Guid:
    data1_hex, data2_hex, data3_hex, data4a_hex, data4b_hex = guid.split("-")
    data4_bytes = bytes.fromhex(data4a_hex + data4b_hex)
    return _Guid(
        int(data1_hex, 16),
        int(data2_hex, 16),
        int(data3_hex, 16),
        (ctypes.c_ubyte * 8)(*data4_bytes),
    )


def has_directml_adapter() -> bool:
    """Cheaply probe for a usable, non-software DirectX 12 adapter.

    Pure ctypes, no ML runtime imports. Returns False immediately off Windows
    and False on any probe failure - a failed probe must never crash node
    startup.
    """
    if sys.platform != "win32":
        return False
    try:
        return _probe_directml_adapter()
    except Exception:
        return False


def _probe_directml_adapter() -> bool:
    if sys.platform != "win32":
        return False

    dxgi = ctypes.WinDLL("dxgi.dll")
    d3d12 = ctypes.WinDLL("d3d12.dll")

    create_factory = dxgi.CreateDXGIFactory1
    create_factory.argtypes = (
        ctypes.POINTER(_Guid),
        ctypes.POINTER(ctypes.c_void_p),
    )
    create_factory.restype = ctypes.HRESULT

    create_device = d3d12.D3D12CreateDevice
    create_device.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_Guid),
        ctypes.c_void_p,
    )
    create_device.restype = ctypes.HRESULT

    def com_call(
        interface: ctypes.c_void_p,
        slot: int,
        restype: type[ctypes.c_ulong],
        argtypes: tuple[type, ...],
        *args: object,
    ) -> int:
        # ctypes vtable/function-pointer plumbing is untyped at the FFI boundary;
        # every value below is parsed straight into the declared `int` result.
        void_pp = ctypes.POINTER(ctypes.c_void_p)
        vtable_ptr = ctypes.cast(interface, void_pp)[0]  # pyright: ignore[reportAny]
        vtable = ctypes.cast(vtable_ptr, void_pp)  # pyright: ignore[reportAny]
        func_ptr = vtable[slot]  # pyright: ignore[reportAny]
        func_type = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        func = ctypes.cast(func_ptr, func_type)  # pyright: ignore[reportAny]
        result: int = func(interface, *args)  # pyright: ignore[reportAny]
        return result

    def release(interface: ctypes.c_void_p) -> None:
        com_call(interface, _RELEASE_SLOT, ctypes.c_ulong, ())

    factory_iid = _guid_from_str(_IID_IDXGI_FACTORY1)
    factory_ptr = ctypes.c_void_p()
    hresult: int = create_factory(  # pyright: ignore[reportAny]
        ctypes.byref(factory_iid), ctypes.byref(factory_ptr)
    )
    if hresult != 0 or factory_ptr.value is None:
        return False

    try:
        index = 0
        while True:
            adapter_ptr = ctypes.c_void_p()
            enum_result = com_call(
                factory_ptr,
                _ENUM_ADAPTERS1_SLOT,
                ctypes.c_ulong,
                (ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)),
                index,
                ctypes.byref(adapter_ptr),
            )
            index += 1
            if enum_result == _DXGI_ERROR_NOT_FOUND or adapter_ptr.value is None:
                return False
            if enum_result != 0:
                continue

            try:
                desc = _DxgiAdapterDesc1()
                desc_result = com_call(
                    adapter_ptr,
                    _GET_DESC1_SLOT,
                    ctypes.c_ulong,
                    (ctypes.POINTER(_DxgiAdapterDesc1),),
                    ctypes.byref(desc),
                )
                if desc_result != 0:
                    continue
                if desc.Flags & (
                    _DXGI_ADAPTER_FLAG_SOFTWARE | _DXGI_ADAPTER_FLAG_REMOTE
                ):
                    continue
                if (
                    desc.VendorId == _MS_BASIC_RENDER_VENDOR_ID
                    and desc.DeviceId == _MS_BASIC_RENDER_DEVICE_ID
                ):
                    continue

                device_iid = _guid_from_str(_IID_ID3D12_DEVICE)
                device_result: int = create_device(  # pyright: ignore[reportAny]
                    adapter_ptr,
                    _D3D_FEATURE_LEVEL_11_0,
                    ctypes.byref(device_iid),
                    None,
                )
                # With ppDevice=NULL, D3D12CreateDevice returns S_FALSE (1) on
                # success (would-create) rather than S_OK (0); both mean "supported".
                if device_result in (0, 1):
                    return True
            finally:
                release(adapter_ptr)
    finally:
        release(factory_ptr)
