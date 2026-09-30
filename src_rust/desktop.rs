// src_rust/desktop.rs
//
// Доступ к чужим окнам, иконкам рабочего стола и курсору — для «магии» Луны
// (luna.rs). Окна: список обычных окон верхнего уровня сверху вниз по
// z-порядку и перемещение без активации. Иконки: SysListView32 рабочего
// стола живёт в процессе explorer, поэтому прямоугольники иконок читаются
// через буфер в памяти его процесса (VirtualAllocEx + Read/WriteProcessMemory).
// Всё спрятано за трейтом Desktop, чтобы логику Луны можно было тестировать
// без Win32. На других платформах — заглушка «ничего нет».

use crate::math::RectI;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct WinInfo {
    pub hwnd: isize,
    /// GetWindowRect — в этих координатах окно двигается (SetWindowPos).
    pub rect: RectI,
    /// Видимая рамка (без невидимых рамок изменения размера Windows 10+) — для подсветки.
    pub frame: RectI,
    /// Окно развёрнуто на весь экран — перед переносом его надо вернуть в обычный размер.
    pub maximized: bool,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct IconInfo {
    pub index: usize,
    /// Позиция элемента (экранные координаты) — её задаёт move_icon.
    pub pos: (i32, i32),
    /// Иконка с подписью (экранные координаты).
    pub rect: RectI,
}

pub trait Desktop {
    /// Видимые окна верхнего уровня, сверху вниз по z-порядку (без свёрнутых, скрытых,
    /// всплывающих подсказок и меню, панели задач, рабочего стола, полноэкранных приложений и своих).
    fn windows(&mut self, own: &[isize]) -> Vec<WinInfo>;
    /// Верхнее видимое окно под точкой экрана — по z-порядку, свои окна (оверлей с пони) пропускаются.
    fn window_at(&mut self, x: i32, y: i32, own: &[isize]) -> Option<isize>;
    /// Вернуть развёрнутое окно в обычный размер (без активации).
    fn restore_window(&mut self, hwnd: isize);
    /// Текущий прямоугольник окна; None — окно закрыто, свёрнуто или развёрнуто.
    fn window_rect(&mut self, hwnd: isize) -> Option<RectI>;
    fn move_window(&mut self, hwnd: isize, x: i32, y: i32);
    /// Иконки рабочего стола; None — недоступны или включено автоупорядочивание.
    fn icons(&mut self) -> Option<Vec<IconInfo>>;
    /// Видимая область списка иконок (экранные координаты).
    fn icon_area(&mut self) -> Option<RectI>;
    fn move_icon(&mut self, index: usize, pos: (i32, i32));
    /// Плавный перенос иконки: на время переноса выключает «Выровнять по сетке»
    /// (иначе иконка прыгала бы по клеткам), end_icon_move возвращает настройку.
    /// Уже поставленные иконки при этом к сетке не притягиваются.
    fn begin_icon_move(&mut self);
    fn end_icon_move(&mut self);
    fn set_cursor(&mut self, x: i32, y: i32);
    /// Открыть ссылку в браузере по умолчанию (как щелчок по ссылке). Только http/https.
    fn open_url(&mut self, url: &str) -> bool;
    /// Яндекс Музыка: приложение, если установлено, иначе сайт в браузере.
    fn open_music(&mut self) -> MusicOpened;
    /// Нажать медиа-клавишу (▶/⏸, следующий, предыдущий трек).
    fn media_key(&mut self, key: MediaKey);
}

/// Медиа-клавиши (как на мультимедийной клавиатуре): их понимают браузер и приложения-плееры.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MediaKey {
    PlayPause,
    Next,
    Prev,
}

/// Чем открылась Яндекс Музыка.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MusicOpened {
    App,
    Web,
    Failed,
}

/// Сайт Яндекс Музыки — если приложения на компьютере нет.
pub const MUSIC_WEB: &str = "https://music.yandex.ru/";

/// Ссылку можно открывать: только http/https, без пробелов и управляющих символов.
pub fn safe_url(url: &str) -> bool {
    (url.starts_with("https://") || url.starts_with("http://"))
        && url.len() < 2048
        && !url.chars().any(|c| c.is_whitespace() || c.is_control() || c == '"')
}

/// Реальный рабочий стол Windows.
pub fn system() -> Box<dyn Desktop> {
    Box::new(imp::SystemDesktop::new())
}

#[cfg(windows)]
mod imp {
    use super::*;
    use std::ffi::c_void;
    use windows_sys::Win32::Foundation::{CloseHandle, BOOL, HANDLE, HWND, LPARAM, POINT, RECT};
    use windows_sys::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_CLOAKED, DWMWA_EXTENDED_FRAME_BOUNDS};
    use windows_sys::Win32::Graphics::Gdi::ClientToScreen;
    use windows_sys::Win32::System::Diagnostics::Debug::{ReadProcessMemory, WriteProcessMemory};
    use windows_sys::Win32::System::Memory::{VirtualAllocEx, VirtualFreeEx, MEM_COMMIT, MEM_RELEASE, MEM_RESERVE, PAGE_READWRITE};
    use windows_sys::Win32::System::Threading::{
        GetCurrentProcessId, OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_OPERATION, PROCESS_VM_READ, PROCESS_VM_WRITE,
    };
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        EnumWindows, FindWindowExW, FindWindowW, GetClassNameW, GetClientRect, GetWindowLongPtrW, GetWindowRect,
        GetWindowTextLengthW, GetWindowThreadProcessId, IsHungAppWindow, IsIconic, IsWindow, IsWindowVisible, IsZoomed,
        SendMessageTimeoutW, SetCursorPos, SetWindowPos, ShowWindow, GWL_EXSTYLE, GWL_STYLE, SMTO_ABORTIFHUNG,
        SWP_ASYNCWINDOWPOS, SWP_NOACTIVATE, SWP_NOSIZE, SWP_NOZORDER, SW_SHOWNOACTIVATE,
    };

    const LVM_GETITEMCOUNT: u32 = 0x1004;
    const LVM_GETITEMRECT: u32 = 0x100E;
    const LVM_SETITEMPOSITION: u32 = 0x100F;
    const LVM_GETITEMPOSITION: u32 = 0x1010;
    const LVM_SETEXTENDEDLISTVIEWSTYLE: u32 = 0x1036;
    const LVM_GETEXTENDEDLISTVIEWSTYLE: u32 = 0x1037;
    const LVS_AUTOARRANGE: isize = 0x0100;
    const LVS_EX_SNAPTOGRID: usize = 0x0008_0000;
    const LVIR_BOUNDS: i32 = 0;
    const WS_CAPTION: isize = 0x00C0_0000;
    const WS_CHILD: isize = 0x4000_0000;
    const WS_EX_TOOLWINDOW: isize = 0x0000_0080;
    const WS_EX_NOACTIVATE: isize = 0x0800_0000;
    const WS_EX_TRANSPARENT: isize = 0x0000_0020;
    /// Больше иконок не читаем — чтение идёт по одному сообщению на иконку.
    const MAX_ICONS: usize = 400;

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn rect_i(r: &RECT) -> RectI {
        RectI::new(r.left, r.top, r.right - r.left, r.bottom - r.top)
    }

    fn h(x: isize) -> HWND {
        x as HWND
    }

    unsafe fn class_name(hwnd: HWND) -> String {
        let mut buf = [0u16; 128];
        let n = GetClassNameW(hwnd, buf.as_mut_ptr(), buf.len() as i32).max(0) as usize;
        String::from_utf16_lossy(&buf[..n.min(buf.len())])
    }

    unsafe extern "system" fn collect_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let list = &mut *(lparam as *mut Vec<isize>);
        list.push(hwnd as isize);
        1
    }

    /// Видимо на экране (не свёрнуто, не спрятано DWM).
    unsafe fn shown(hwnd: HWND) -> bool {
        if IsWindowVisible(hwnd) == 0 || IsIconic(hwnd) != 0 {
            return false;
        }
        // Скрытые DWM окна (приложения UWP в фоне, окна других рабочих столов).
        let mut cloaked: u32 = 0;
        !(DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED as u32, &mut cloaked as *mut u32 as *mut c_void, 4) == 0 && cloaked != 0)
    }

    /// Обычное окно приложения, которое можно двигать: с рамкой или без (Chrome, VS Code, Discord),
    /// развёрнутое, поверх всех — да; подсказки, меню, панель задач, рабочий стол и свои — нет.
    unsafe fn movable_window(hwnd: HWND, own_pid: u32) -> bool {
        if !shown(hwnd) || IsHungAppWindow(hwnd) != 0 {
            return false;
        }
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, &mut pid);
        if pid == own_pid {
            return false;
        }
        let style = GetWindowLongPtrW(hwnd, GWL_STYLE);
        let ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        if style & WS_CHILD != 0 || ex & WS_EX_NOACTIVATE != 0 {
            return false;
        }
        // окно без рамки и без заголовка — обычно служебное (подложки, всплывашки)
        if style & WS_CAPTION != WS_CAPTION && GetWindowTextLengthW(hwnd) == 0 {
            return false;
        }
        !matches!(
            class_name(hwnd).as_str(),
            "Progman" | "WorkerW" | "Shell_TrayWnd" | "Shell_SecondaryTrayWnd" | "Windows.UI.Core.CoreWindow"
                | "NotifyIconOverflowWindow" | "TopLevelWindowForOverflowXamlIsland"
                | "#32768" | "tooltips_class32" | "Xaml_WindowedPopupClass" | "SysShadow"
        )
    }

    unsafe fn frame_rect(hwnd: HWND, fallback: RectI) -> RectI {
        let mut r: RECT = std::mem::zeroed();
        let ok = DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS as u32,
            &mut r as *mut RECT as *mut c_void,
            std::mem::size_of::<RECT>() as u32,
        );
        if ok == 0 && r.right > r.left { rect_i(&r) } else { fallback }
    }

    unsafe extern "system" fn find_defview_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let out = &mut *(lparam as *mut isize);
        let cls = wide("SHELLDLL_DefView");
        let dv = FindWindowExW(hwnd, std::ptr::null_mut(), cls.as_ptr(), std::ptr::null());
        if !dv.is_null() {
            *out = dv as isize;
            return 0;
        }
        1
    }

    /// Список иконок рабочего стола: Progman → SHELLDLL_DefView → SysListView32
    /// (после смены обоев DefView бывает перенесён в одно из окон WorkerW).
    unsafe fn find_desktop_listview() -> isize {
        let progman_cls = wide("Progman");
        let defview_cls = wide("SHELLDLL_DefView");
        let lv_cls = wide("SysListView32");
        let progman = FindWindowW(progman_cls.as_ptr(), std::ptr::null());
        let mut defview = if progman.is_null() {
            std::ptr::null_mut()
        } else {
            FindWindowExW(progman, std::ptr::null_mut(), defview_cls.as_ptr(), std::ptr::null())
        };
        if defview.is_null() {
            let mut found: isize = 0;
            EnumWindows(Some(find_defview_proc), &mut found as *mut isize as LPARAM);
            defview = found as HWND;
        }
        if defview.is_null() {
            return 0;
        }
        FindWindowExW(defview, std::ptr::null_mut(), lv_cls.as_ptr(), std::ptr::null()) as isize
    }

    use std::os::windows::ffi::OsStrExt;

    /// Установленное приложение Яндекс Музыки: сначала по записи Windows для ссылок yandexmusic://,
    /// потом в стандартной папке установки.
    fn find_music_app() -> Option<std::path::PathBuf> {
        use windows_sys::Win32::System::Registry::{RegGetValueW, HKEY_CLASSES_ROOT, RRF_RT_REG_SZ};
        let key = wide("yandexmusic\\shell\\open\\command");
        let mut buf = vec![0u16; 1024];
        let mut size = (buf.len() * 2) as u32;
        let rc = unsafe {
            RegGetValueW(HKEY_CLASSES_ROOT, key.as_ptr(), std::ptr::null(), RRF_RT_REG_SZ, std::ptr::null_mut(),
                buf.as_mut_ptr() as *mut c_void, &mut size)
        };
        if rc == 0 {
            let s = String::from_utf16_lossy(&buf[..(size as usize / 2).saturating_sub(1)]);
            let s = s.trim();
            // "C:\...\Яндекс Музыка.exe" "%1"  ->  путь к программе
            let exe = if let Some(rest) = s.strip_prefix('"') { rest.split('"').next().unwrap_or("") } else { s.split(' ').next().unwrap_or("") };
            let p = std::path::PathBuf::from(exe);
            if p.extension().map(|e| e.eq_ignore_ascii_case("exe")).unwrap_or(false) && p.is_file() {
                return Some(p);
            }
        }
        let dir = std::path::PathBuf::from(std::env::var_os("LOCALAPPDATA")?).join("Programs").join("YandexMusic");
        std::fs::read_dir(dir).ok()?.flatten().map(|e| e.path()).find(|p| {
            let name = p.file_name().map(|n| n.to_string_lossy().to_lowercase()).unwrap_or_default();
            name.ends_with(".exe") && !name.starts_with("uninstall")
        })
    }

    pub struct SystemDesktop {
        own_pid: u32,
        monitors: Vec<crate::winapi::MonitorInfo>,
        lv: isize,
        process: HANDLE,
        remote: *mut c_void,
        /// Было ли включено «Выровнять по сетке» до begin_icon_move.
        snap_restore: bool,
    }

    impl SystemDesktop {
        pub fn new() -> SystemDesktop {
            SystemDesktop {
                own_pid: unsafe { GetCurrentProcessId() },
                monitors: crate::winapi::monitors(),
                lv: 0,
                process: std::ptr::null_mut(),
                remote: std::ptr::null_mut(),
                snap_restore: false,
            }
        }

        fn close(&mut self) {
            unsafe {
                if !self.remote.is_null() {
                    VirtualFreeEx(self.process, self.remote, 0, MEM_RELEASE);
                }
                if !self.process.is_null() {
                    CloseHandle(self.process);
                }
            }
            self.remote = std::ptr::null_mut();
            self.process = std::ptr::null_mut();
            self.lv = 0;
        }

        /// Находит список иконок и буфер в процессе explorer (заново — если
        /// explorer перезапускался).
        fn open(&mut self) -> bool {
            unsafe {
                if self.lv != 0 && IsWindow(h(self.lv)) != 0 && !self.remote.is_null() {
                    return true;
                }
                self.close();
                let lv = find_desktop_listview();
                if lv == 0 {
                    return false;
                }
                let mut pid = 0u32;
                GetWindowThreadProcessId(h(lv), &mut pid);
                let access = PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION;
                let process = OpenProcess(access, 0, pid);
                if process.is_null() {
                    return false;
                }
                let remote = VirtualAllocEx(process, std::ptr::null(), 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
                if remote.is_null() {
                    CloseHandle(process);
                    return false;
                }
                self.lv = lv;
                self.process = process;
                self.remote = remote;
                true
            }
        }

        /// Сообщение списку иконок с тайм-аутом: зависший explorer не должен вешать пони.
        fn send(&self, msg: u32, wparam: usize, lparam: isize) -> Option<usize> {
            let mut result: usize = 0;
            let ok = unsafe { SendMessageTimeoutW(h(self.lv), msg, wparam, lparam, SMTO_ABORTIFHUNG, 300, &mut result) };
            if ok == 0 { None } else { Some(result) }
        }

        fn write_remote<T: Copy>(&self, v: &T) -> bool {
            let mut n = 0usize;
            unsafe {
                WriteProcessMemory(self.process, self.remote, v as *const T as *const c_void, std::mem::size_of::<T>(), &mut n) != 0
            }
        }

        fn read_remote<T: Copy>(&self, v: &mut T) -> bool {
            let mut n = 0usize;
            unsafe { ReadProcessMemory(self.process, self.remote, v as *mut T as *mut c_void, std::mem::size_of::<T>(), &mut n) != 0 }
        }

        fn client_origin(&self) -> (i32, i32) {
            let mut p = POINT { x: 0, y: 0 };
            unsafe {
                ClientToScreen(h(self.lv), &mut p);
            }
            (p.x, p.y)
        }

        fn item(&self, index: usize, origin: (i32, i32)) -> Option<IconInfo> {
            let mut r = RECT { left: LVIR_BOUNDS, top: 0, right: 0, bottom: 0 };
            if !self.write_remote(&r) {
                return None;
            }
            self.send(LVM_GETITEMRECT, index, self.remote as isize)?;
            if !self.read_remote(&mut r) {
                return None;
            }
            self.send(LVM_GETITEMPOSITION, index, self.remote as isize)?;
            let mut p = POINT { x: 0, y: 0 };
            if !self.read_remote(&mut p) {
                return None;
            }
            let mut rect = rect_i(&r);
            rect.x += origin.0;
            rect.y += origin.1;
            Some(IconInfo { index, pos: (p.x + origin.0, p.y + origin.1), rect })
        }
    }

    pub fn find_music_app_for_probe() -> Option<std::path::PathBuf> {
        find_music_app()
    }

    impl Drop for SystemDesktop {
        fn drop(&mut self) {
            self.end_icon_move();
            self.close();
        }
    }

    impl Desktop for SystemDesktop {
        fn windows(&mut self, own: &[isize]) -> Vec<WinInfo> {
            let mut all: Vec<isize> = Vec::new();
            unsafe {
                EnumWindows(Some(collect_proc), &mut all as *mut Vec<isize> as LPARAM);
            }
            let mut out = Vec::new();
            for hw in all {
                if own.contains(&hw) {
                    continue;
                }
                unsafe {
                    if !movable_window(h(hw), self.own_pid) {
                        continue;
                    }
                    let mut r: RECT = std::mem::zeroed();
                    if GetWindowRect(h(hw), &mut r) == 0 {
                        continue;
                    }
                    let rect = rect_i(&r);
                    if rect.w < 160 || rect.h < 100 {
                        continue;
                    }
                    let maximized = IsZoomed(h(hw)) != 0;
                    // полноэкранное приложение (игра, видео на весь экран) — не трогаем
                    let covers_monitor = self.monitors.iter().any(|m| {
                        rect.x <= m.bounds.x && rect.y <= m.bounds.y && rect.right() >= m.bounds.right() && rect.bottom() >= m.bounds.bottom()
                    });
                    if !maximized && covers_monitor {
                        continue;
                    }
                    out.push(WinInfo { hwnd: hw, rect, frame: frame_rect(h(hw), rect), maximized });
                }
            }
            out
        }

        fn window_at(&mut self, x: i32, y: i32, own: &[isize]) -> Option<isize> {
            // По z-порядку, а не WindowFromPoint: пока открыто меню пони, прозрачный оверлей ловит
            // клики, и WindowFromPoint вернул бы его под любой точкой.
            let mut all: Vec<isize> = Vec::new();
            unsafe {
                EnumWindows(Some(collect_proc), &mut all as *mut Vec<isize> as LPARAM);
            }
            for hw in all {
                if own.contains(&hw) {
                    continue;
                }
                unsafe {
                    let mut pid = 0u32;
                    GetWindowThreadProcessId(h(hw), &mut pid);
                    if pid == self.own_pid || !shown(h(hw)) {
                        continue;
                    }
                    // прозрачные для кликов слои поверх экрана (оверлей NVIDIA, Discord и т.п.) окна не закрывают
                    if GetWindowLongPtrW(h(hw), GWL_EXSTYLE) & WS_EX_TRANSPARENT != 0 {
                        continue;
                    }
                    let mut r: RECT = std::mem::zeroed();
                    if GetWindowRect(h(hw), &mut r) == 0 {
                        continue;
                    }
                    if frame_rect(h(hw), rect_i(&r)).contains_point(x, y) {
                        return Some(hw);
                    }
                }
            }
            None
        }

        fn restore_window(&mut self, hwnd: isize) {
            unsafe {
                ShowWindow(h(hwnd), SW_SHOWNOACTIVATE);
            }
        }

        fn window_rect(&mut self, hwnd: isize) -> Option<RectI> {
            unsafe {
                let w = h(hwnd);
                if IsWindow(w) == 0 || IsWindowVisible(w) == 0 || IsIconic(w) != 0 || IsZoomed(w) != 0 {
                    return None;
                }
                let mut r: RECT = std::mem::zeroed();
                if GetWindowRect(w, &mut r) == 0 {
                    return None;
                }
                Some(rect_i(&r))
            }
        }

        fn move_window(&mut self, hwnd: isize, x: i32, y: i32) {
            // Асинхронно: если окно подвисло, пони не ждут его.
            unsafe {
                SetWindowPos(
                    h(hwnd),
                    std::ptr::null_mut(),
                    x,
                    y,
                    0,
                    0,
                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS,
                );
            }
        }

        fn icons(&mut self) -> Option<Vec<IconInfo>> {
            if !self.open() {
                return None;
            }
            let style = unsafe { GetWindowLongPtrW(h(self.lv), GWL_STYLE) };
            if style & LVS_AUTOARRANGE != 0 {
                return None;
            }
            let count = self.send(LVM_GETITEMCOUNT, 0, 0)?.min(MAX_ICONS);
            let origin = self.client_origin();
            let list: Vec<IconInfo> = (0..count).filter_map(|i| self.item(i, origin)).collect();
            Some(list)
        }

        fn icon_area(&mut self) -> Option<RectI> {
            if !self.open() {
                return None;
            }
            let mut r: RECT = unsafe { std::mem::zeroed() };
            if unsafe { GetClientRect(h(self.lv), &mut r) } == 0 {
                return None;
            }
            let (x, y) = self.client_origin();
            Some(RectI::new(x, y, r.right - r.left, r.bottom - r.top))
        }

        fn move_icon(&mut self, index: usize, pos: (i32, i32)) {
            if !self.open() {
                return;
            }
            let origin = self.client_origin();
            let x = (pos.0 - origin.0).clamp(0, 0x7FFF) as u16 as u32;
            let y = (pos.1 - origin.1).clamp(0, 0x7FFF) as u16 as u32;
            self.send(LVM_SETITEMPOSITION, index, ((y << 16) | x) as isize);
        }

        fn begin_icon_move(&mut self) {
            if !self.open() || self.snap_restore {
                return;
            }
            let ex = self.send(LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0).unwrap_or(0);
            if ex & LVS_EX_SNAPTOGRID != 0 {
                self.send(LVM_SETEXTENDEDLISTVIEWSTYLE, LVS_EX_SNAPTOGRID, 0);
                self.snap_restore = true;
            }
        }

        fn end_icon_move(&mut self) {
            if self.snap_restore && self.lv != 0 {
                self.send(LVM_SETEXTENDEDLISTVIEWSTYLE, LVS_EX_SNAPTOGRID, LVS_EX_SNAPTOGRID as isize);
            }
            self.snap_restore = false;
        }

        fn set_cursor(&mut self, x: i32, y: i32) {
            unsafe {
                SetCursorPos(x, y);
            }
        }

        fn open_music(&mut self) -> MusicOpened {
            if let Some(exe) = find_music_app() {
                use windows_sys::Win32::UI::Shell::ShellExecuteW;
                use windows_sys::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
                let verb = wide("open");
                let file: Vec<u16> = exe.as_os_str().encode_wide().chain(std::iter::once(0)).collect();
                let ok = unsafe {
                    ShellExecuteW(std::ptr::null_mut(), verb.as_ptr(), file.as_ptr(), std::ptr::null(), std::ptr::null(), SW_SHOWNORMAL)
                        as isize > 32
                };
                if ok {
                    return MusicOpened::App;
                }
            }
            if self.open_url(MUSIC_WEB) { MusicOpened::Web } else { MusicOpened::Failed }
        }

        fn media_key(&mut self, key: MediaKey) {
            use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP,
                VK_MEDIA_NEXT_TRACK, VK_MEDIA_PLAY_PAUSE, VK_MEDIA_PREV_TRACK,
            };
            let vk = match key {
                MediaKey::PlayPause => VK_MEDIA_PLAY_PAUSE,
                MediaKey::Next => VK_MEDIA_NEXT_TRACK,
                MediaKey::Prev => VK_MEDIA_PREV_TRACK,
            };
            let ev = |flags| INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 { ki: KEYBDINPUT { wVk: vk, wScan: 0, dwFlags: flags, time: 0, dwExtraInfo: 0 } },
            };
            let inputs = [ev(KEYEVENTF_EXTENDEDKEY), ev(KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)];
            unsafe {
                SendInput(inputs.len() as u32, inputs.as_ptr(), std::mem::size_of::<INPUT>() as i32);
            }
        }

        fn open_url(&mut self, url: &str) -> bool {
            if !safe_url(url) {
                return false;
            }
            use windows_sys::Win32::UI::Shell::ShellExecuteW;
            use windows_sys::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
            let verb = wide("open");
            let file = wide(url);
            // > 32 — успех (так устроен ShellExecute)
            unsafe {
                ShellExecuteW(std::ptr::null_mut(), verb.as_ptr(), file.as_ptr(), std::ptr::null(), std::ptr::null(), SW_SHOWNORMAL)
                    as isize > 32
            }
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use super::*;

    pub struct SystemDesktop;

    impl SystemDesktop {
        pub fn new() -> SystemDesktop {
            SystemDesktop
        }
    }

    impl Desktop for SystemDesktop {
        fn windows(&mut self, _own: &[isize]) -> Vec<WinInfo> {
            Vec::new()
        }
        fn window_at(&mut self, _x: i32, _y: i32, _own: &[isize]) -> Option<isize> {
            None
        }
        fn restore_window(&mut self, _hwnd: isize) {}
        fn window_rect(&mut self, _hwnd: isize) -> Option<RectI> {
            None
        }
        fn move_window(&mut self, _hwnd: isize, _x: i32, _y: i32) {}
        fn icons(&mut self) -> Option<Vec<IconInfo>> {
            None
        }
        fn icon_area(&mut self) -> Option<RectI> {
            None
        }
        fn move_icon(&mut self, _index: usize, _pos: (i32, i32)) {}
        fn begin_icon_move(&mut self) {}
        fn end_icon_move(&mut self) {}
        fn set_cursor(&mut self, _x: i32, _y: i32) {}
        fn open_url(&mut self, _url: &str) -> bool {
            false
        }
        fn open_music(&mut self) -> MusicOpened {
            MusicOpened::Failed
        }
        fn media_key(&mut self, _key: MediaKey) {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Только чтение реального рабочего стола: `cargo test --lib desktop_probe -- --ignored --nocapture`.
    #[test]
    #[ignore]
    fn desktop_probe() {
        let mons = crate::winapi::monitors();
        for m in &mons {
            println!("monitor {} bounds {:?} work {:?} primary {}", m.device_name, m.bounds, m.work, m.primary);
        }
        let sel: Vec<String> = mons.iter().map(|m| m.device_name.clone()).collect();
        let region = crate::winapi::allowed_area(&mons, &sel, None);
        let areas = crate::winapi::allowed_areas(&mons, &sel, None);
        println!("region {:?}
areas {:?}
dead {:?}", region, areas, crate::winapi::dead_zones(region, &areas));
        let mut d = system();
        let wins = d.windows(&[]);
        println!("windows: {}", wins.len());
        for w in wins.iter().take(8) {
            println!("  {:?} rect {:?} frame {:?} at-title {:?}", w.hwnd, w.rect, w.frame, d.window_at(w.frame.x + w.frame.w / 2, w.frame.y + 12, &[]));
        }
        #[cfg(windows)]
        println!("yandex music app: {:?}", imp::find_music_app_for_probe());
        println!("icon area: {:?}", d.icon_area());
        match d.icons() {
            Some(list) => {
                println!("icons: {}", list.len());
                for i in list.iter().take(5) {
                    println!("  {:?}", i);
                }
            }
            None => println!("icons: unavailable (auto-arrange or no access)"),
        }
    }
}
