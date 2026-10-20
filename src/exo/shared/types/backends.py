from enum import Enum


class Backend(str, Enum):
    Vllm = "Vllm"
    OnnxDirectMl = "OnnxDirectMl"
    OnnxCuda = "OnnxCuda"
    OnnxCpu = "OnnxCpu"
    TinygradAmd = "TinygradAmd"
    TinygradMetal = "TinygradMetal"
    TinygradCuda = "TinygradCuda"
    TinygradCpu = "TinygradCpu"
    # Windows join identities. These name tinygrad devices per Windows adapter class.
    WinAMD = "WinAMD"
    WinCUDA = "WinCUDA"
    WinCPU = "WinCPU"
