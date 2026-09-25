// src_rust/winapi.rs
//
// Тонкая обёртка над Win32: глобальные координаты курсора и состояние
// кнопок/клавиш (оверлей — прозрачное окно, поэтому события мыши нельзя
// получать из самого окна), список мониторов с рабочими областями
// (Screen.WorkingArea), окно под точкой (избегание окон) и определение
// полноэкранного приложения. На других платформах — безопасные заглушки.

use crate::math::RectI;

#[derive(Clone, Debug)]
pub struct MonitorInfo {
    /// Имя устройства, как в System.Windows.Forms.Screen.DeviceName.
    pub device_name: String,
    pub bounds: RectI,
    pub work: RectI,
    pub primary: bool,
}

#[cfg(windows)]
mod imp {
    use super::*;
    use std::ffi::c_void;
    use windows_sys::Win32::Foundation::{BOOL, HWND, LPARAM, POINT, RECT};
    use windows_sys::Win32::Graphics::Gdi::{
        EnumDisplayMonitors, GetMonitorInfoW, HDC, HMONITOR, MONITORINFO, MONITORINFOEXW,
    };
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetAncestor, GetClassNameW, GetCursorPos, GetForegroundWindow, GetWindowRect, WindowFromPoint, GA_ROOT,
    };

    pub fn cursor_pos() -> (i32, i32) {
        let mut p = POINT { x: 0, y: 0 };
        unsafe {
            GetCursorPos(&mut p);
        }
        (p.x, p.y)
    }

    /// Состояние виртуальной клавиши (старший бит = нажата).
    pub fn key_down(vk: i32) -> bool {
        unsafe { (GetAsyncKeyState(vk) as u16 & 0x8000) != 0 }
    }

    fn rect_i(r: &RECT) -> RectI {
        RectI::new(r.left, r.top, r.right - r.left, r.bottom - r.top)
    }

    unsafe extern "system" fn enum_proc(hmon: HMONITOR, _hdc: HDC, _r: *mut RECT, lparam: LPARAM) -> BOOL {
        let list = &mut *(lparam as *mut Vec<MonitorInfo>);
        let mut info: MONITORINFOEXW = std::mem::zeroed();
        info.monitorInfo.cbSize = std::mem::size_of::<MONITORINFOEXW>() as u32;
        if GetMonitorInfoW(hmon, &mut info as *mut MONITORINFOEXW as *mut MONITORINFO) != 0 {
            let len = info.szDevice.iter().position(|c| *c == 0).unwrap_or(info.szDevice.len());
            let name = String::from_utf16_lossy(&info.szDevice[..len]);
            list.push(MonitorInfo {
                device_name: name,
                bounds: rect_i(&info.monitorInfo.rcMonitor),
                work: rect_i(&info.monitorInfo.rcWork),
                primary: info.monitorInfo.dwFlags & 1 != 0,
            });
        }
        1
    }

    pub fn monitors() -> Vec<MonitorInfo> {
        let mut list: Vec<MonitorInfo> = Vec::new();
        unsafe {
            EnumDisplayMonitors(
                std::ptr::null_mut(),
                std::ptr::null(),
                Some(enum_proc),
                &mut list as *mut Vec<MonitorInfo> as LPARAM,
            );
        }
        list.sort_by(|a, b| a.device_name.cmp(&b.device_name));
        list
    }

    /// Окно верхнего уровня под точкой; own — HWND собственных окон (игнорируются).
    pub fn window_rect_at_point(x: i32, y: i32, own: &[isize]) -> Option<RectI> {
        unsafe {
            let hwnd = WindowFromPoint(POINT { x, y });
            if hwnd.is_null() {
                return None;
            }
            let root = GetAncestor(hwnd, GA_ROOT);
            let target: HWND = if root.is_null() { hwnd } else { root };
            if own.contains(&(target as isize)) {
                return None;
            }
            let mut r: RECT = std::mem::zeroed();
            if GetWindowRect(target, &mut r) == 0 {
                return None;
            }
            Some(rect_i(&r))
        }
    }

    /// Активно ли полноэкранное приложение (не рабочий стол и не наши окна).
    pub fn fullscreen_app_active(own: &[isize], monitors: &[MonitorInfo]) -> bool {
        unsafe {
            let hwnd = GetForegroundWindow();
            if hwnd.is_null() || own.contains(&(hwnd as isize)) {
                return false;
            }
            let mut buf = [0u16; 64];
            let n = GetClassNameW(hwnd, buf.as_mut_ptr(), buf.len() as i32) as usize;
            let class = String::from_utf16_lossy(&buf[..n.min(buf.len())]);
            if matches!(class.as_str(), "Progman" | "WorkerW" | "Shell_TrayWnd" | "Shell_SecondaryTrayWnd") {
                return false;
            }
            let mut r: RECT = std::mem::zeroed();
            if GetWindowRect(hwnd, &mut r) == 0 {
                return false;
            }
            let rr = rect_i(&r);
            monitors.iter().any(|m| rr.x <= m.bounds.x && rr.y <= m.bounds.y && rr.right() >= m.bounds.right() && rr.bottom() >= m.bounds.bottom())
        }
    }

    #[allow(dead_code)]
    pub fn _unused(_: *mut c_void) {}
}

#[cfg(not(windows))]
mod imp {
    use super::*;
    pub fn cursor_pos() -> (i32, i32) {
        (i32::MIN, i32::MIN)
    }
    pub fn key_down(_vk: i32) -> bool {
        false
    }
    pub fn monitors() -> Vec<MonitorInfo> {
        vec![MonitorInfo {
            device_name: "DISPLAY1".to_string(),
            bounds: RectI::new(0, 0, 1920, 1080),
            work: RectI::new(0, 0, 1920, 1040),
            primary: true,
        }]
    }
    pub fn window_rect_at_point(_x: i32, _y: i32, _own: &[isize]) -> Option<RectI> {
        None
    }
    pub fn fullscreen_app_active(_own: &[isize], _m: &[MonitorInfo]) -> bool {
        false
    }
}

pub use imp::*;

pub const VK_LBUTTON: i32 = 0x01;
pub const VK_RBUTTON: i32 = 0x02;
pub const VK_SHIFT_L: i32 = 0xA0;
pub const VK_SHIFT_R: i32 = 0xA1;
pub const VK_CONTROL_L: i32 = 0xA2;
pub const VK_CONTROL_R: i32 = 0xA3;
pub const VK_LEFT: i32 = 0x25;
pub const VK_UP: i32 = 0x26;
pub const VK_RIGHT: i32 = 0x27;
pub const VK_DOWN: i32 = 0x28;
pub const VK_W: i32 = 0x57;
pub const VK_A: i32 = 0x41;
pub const VK_S: i32 = 0x53;
pub const VK_D: i32 = 0x44;
pub const VK_ESCAPE: i32 = 0x1B;

/// Объединение рабочих областей выбранных мониторов (Options.GetAllowedArea).
pub fn allowed_area(monitors: &[MonitorInfo], selected: &[String], allowed_region: Option<RectI>) -> RectI {
    let all_bounds = monitors.iter().map(|m| m.bounds).reduce(|a, b| a.union(&b)).unwrap_or(RectI::new(0, 0, 1920, 1080));
    match allowed_region {
        Some(r) => {
            let i = r.intersect(&all_bounds);
            if i.is_empty() { all_bounds } else { i }
        }
        None => {
            let chosen: Vec<&MonitorInfo> = monitors.iter().filter(|m| selected.iter().any(|s| s == &m.device_name)).collect();
            let list: Vec<&MonitorInfo> = if chosen.is_empty() {
                monitors.iter().filter(|m| m.primary).collect()
            } else {
                chosen
            };
            list.iter()
                .map(|m| if m.work.is_empty() { m.bounds } else { m.work })
                .reduce(|a, b| a.union(&b))
                .unwrap_or(all_bounds)
        }
    }
}

/// Окно не забирает фокус при клике (WS_EX_NOACTIVATE) — иначе клик по
/// пони отбирал бы фокус у игры/редактора.
#[cfg(windows)]
pub fn set_no_activate(hwnd: isize) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{GetWindowLongPtrW, SetWindowLongPtrW, GWL_EXSTYLE};
    const WS_EX_NOACTIVATE: isize = 0x0800_0000;
    unsafe {
        let h = hwnd as *mut std::ffi::c_void;
        let ex = GetWindowLongPtrW(h, GWL_EXSTYLE);
        SetWindowLongPtrW(h, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE);
    }
}

#[cfg(not(windows))]
pub fn set_no_activate(_hwnd: isize) {}
