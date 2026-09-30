// src_rust/luna.rs
//
// «Магия» принцессы Луны поверх обычной симуляции:
// * время от времени (или по пункту меню) она подходит к чужому окну или к
//   иконке рабочего стола, зависает в позе полёта и плавно переносит цель
//   магией — по дуге, с разгоном и торможением, в голубом сиянии с искрами;
// * так же поднимает магией других пони (они в drag-состоянии, как под
//   мышью) и переносит их к себе или в сторону;
// * если курсор долго не двигается, Луна идёт к нему и засыпает рядом;
//   если она уже спит — магией подтягивает курсор к себе.
// Любое действие пользователя (кнопка мыши, движение курсора, перетаскивание
// пони, меню) сразу прерывает колдовство. Доступ к окнам и иконкам — через
// трейт Desktop (desktop.rs), поэтому логика тестируется без Win32.

use crate::desktop::{Desktop, IconInfo, MediaKey, MusicOpened, WinInfo};
use crate::math::{RectI, V2};
use crate::sim::{Hold, Pony, PonyId, World};

/// Каталоги пони, которые умеют колдовать так.
const LUNA_DIRS: [&str; 1] = ["Princess Luna"];

/// Цвет магии Луны и цвет сердцевины искр.
const MAGIC: (u8, u8, u8) = (0x7C, 0xB8, 0xFF);
const SPARK: (u8, u8, u8) = (0xE4, 0xF0, 0xFF);

const APPROACH_MAX_SECS: f32 = 8.0;
const CHARGE_SECS: f32 = 0.55;
const RELEASE_SECS: f32 = 0.6;
const WALK_TO_CURSOR_MAX_SECS: f32 = 30.0;
/// Дальше этого Луна не идёт к цели, а телепортируется поближе.
const TELEPORT_APPROACH_PX: f32 = 300.0;
const TELEPORT_TO_CURSOR_PX: f32 = 450.0;
/// Пауза между самопроизвольными шалостями, секунды.
const AUTO_MIN_SECS: f32 = 45.0;
const AUTO_MAX_SECS: f32 = 110.0;
const FIRST_AUTO_SECS: f32 = 25.0;
const MAX_PARTICLES: usize = 600;

const WINDOW_LINES: [&str; 3] = [
    "This window displeases Us. It shall move!",
    "A little to the side, We think.",
    "Behold the power of the Princess of the Night!",
];
const ICON_LINES: [&str; 2] = ["Thou art out of place, little icon.", "We shall tidy this desktop Ourselves!"];
const PONY_LINES: [&str; 2] = ["Hold still. We shall move thee.", "Thou art in Our way, little pony."];
const PONY_BRING_LINE: &str = "Come hither, little pony!";
/// Дальше этого пони не относят в сторону, а приносят к Луне.
const BRING_PONY_PX: f32 = 350.0;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LunaSettings {
    pub move_windows: bool,
    pub move_icons: bool,
    pub sleep_by_cursor: bool,
    /// Сама открывает Яндекс Музыку (раз за запуск) и время от времени переключает треки.
    pub music: bool,
    /// Переносит магией других пони.
    pub move_ponies: bool,
    /// Сколько секунд курсор должен стоять, чтобы Луна пришла к нему.
    pub cursor_idle_secs: f32,
}

impl Default for LunaSettings {
    fn default() -> Self {
        LunaSettings {
            move_windows: true,
            move_icons: true,
            sleep_by_cursor: true,
            music: true,
            move_ponies: true,
            cursor_idle_secs: 20.0,
        }
    }
}

/// Состояние ввода на этом кадре.
pub struct FrameInput<'a> {
    pub cursor: (i32, i32),
    /// Нажата кнопка мыши — пользователь что-то делает, колдовство прерывается.
    pub buttons: bool,
    /// Открыто меню или что-то тащат мышью.
    pub blocked: bool,
    /// Пони под ручным управлением (Take Control).
    pub manual: &'a [PonyId],
    pub own_hwnds: &'a [isize],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Spell {
    Window,
    Icon,
    /// Перенести другую пони.
    Pony,
    /// Открыть видео (только по пункту меню).
    Video,
    /// Открыть Яндекс Музыку (приложение или сайт).
    Music,
    MusicPlayPause,
    MusicNext,
    MusicPrev,
}

/// Через сколько секунд после запуска Луна сама откроет музыку и как часто потом переключает треки.
const MUSIC_FIRST_MIN: f32 = 150.0;
const MUSIC_FIRST_MAX: f32 = 360.0;
const MUSIC_MIN_SECS: f32 = 180.0;
const MUSIC_MAX_SECS: f32 = 420.0;

/// Какое видео открывает Луна по «Magic: Play a video».
pub const VIDEO_URL: &str = "https://yandex.ru/video/preview/4004892201636270394";
/// Скорость «печати» ссылки в облачке, символов в секунду.
const TYPE_CHARS_PER_SEC: f32 = 18.0;

#[derive(Clone, Copy, Debug)]
enum Target {
    /// frame — видимая рамка относительно GetWindowRect (x, y, w, h).
    Window { hwnd: isize, size: (i32, i32), frame: RectI },
    /// rect — прямоугольник иконки относительно её позиции.
    Icon { index: usize, rect: RectI },
    /// rect — спрайт пони относительно её location.
    Pony { id: PonyId, rect: RectI },
    Cursor,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum Phase {
    Approach,
    Charge,
    Move,
    Release,
}

struct Cast {
    pony: PonyId,
    target: Target,
    from: V2,
    to: V2,
    cur: V2,
    phase: Phase,
    t: f32,
    move_secs: f32,
    lift: f32,
    spot: V2,
    last_set: Option<(i32, i32)>,
    icon_move_started: bool,
    line: Option<&'static str>,
}

struct GoSleep {
    pony: PonyId,
    spot: V2,
    facing_right: bool,
    t: f32,
    cursor: (i32, i32),
}

/// Что делает заклинание в конце.
#[derive(Clone, Copy, Debug, PartialEq)]
enum Act {
    OpenUrl(&'static str),
    OpenMusic,
    Key(MediaKey),
}

/// Заклинание «на месте»: видео, музыка, медиа-клавиши.
struct VideoJob {
    pony: PonyId,
    t: f32,
    act: Act,
    /// Что «печатается» в облачке перед действием (пусто — только фраза).
    text: String,
    line: &'static str,
    portal: V2,
    typed: usize,
    opened: bool,
}

enum Job {
    Cast(Cast),
    GoSleep(GoSleep),
    Video(VideoJob),
}

pub fn is_luna(p: &Pony) -> bool {
    LUNA_DIRS.iter().any(|d| p.base.directory.eq_ignore_ascii_case(d))
}

fn ease_in_out(t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    if t < 0.5 { 4.0 * t * t * t } else { 1.0 - (-2.0 * t + 2.0).powi(3) / 2.0 }
}

fn dist(a: (i32, i32), b: (i32, i32)) -> f32 {
    (((a.0 - b.0) as f32).powi(2) + ((a.1 - b.1) as f32).powi(2)).sqrt()
}

/// Положение отрезка [pos, pos+size] внутри [lo, hi]; если не помещается —
/// хотя бы не уезжает дальше, чем уже есть.
fn clamp_span(pos: i32, size: i32, lo: i32, hi: i32) -> i32 {
    if size <= hi - lo { pos.clamp(lo, hi - size) } else { pos.clamp(hi - size, lo) }
}

fn inflate(r: RectI, d: i32) -> RectI {
    RectI::new(r.x - d, r.y - d, r.w + 2 * d, r.h + 2 * d)
}

fn intersects(a: &RectI, b: &RectI) -> bool {
    a.x < b.right() && b.x < a.right() && a.y < b.bottom() && b.y < a.bottom()
}

/// Точка рога Луны на спрайте (доли ширины/высоты для взгляда вправо).
fn horn_point(p: &Pony) -> V2 {
    let r = p.region();
    let (fx, fy) = if p.is_sleeping() { (0.73, 0.22) } else { (0.71, 0.10) };
    let fx = if p.facing_right() { fx } else { 1.0 - fx };
    V2::new(r.x as f32 + r.w as f32 * fx, r.y as f32 + r.h as f32 * fy)
}

/// Позиция пони (location), при которой её спрайт стоит левым верхним углом
/// в tl, но не выходит за region.
fn location_for_top_left(p: &Pony, tl: (i32, i32), region: RectI) -> V2 {
    let r = p.region();
    let region = if region.is_empty() { p.region() } else { region };
    let loc = p.location();
    let x = clamp_span(tl.0, r.w, region.x, region.right());
    let y = clamp_span(tl.1, r.h, region.y, region.bottom());
    V2::new(x as f32 + (loc.x - r.x as f32), y as f32 + (loc.y - r.y as f32))
}

/// Поведение для «зависания» во время колдовства: полёт, иначе любое подвижное.
fn hover_behavior(p: &Pony) -> usize {
    let bs = &p.base.behaviors;
    let named = bs.iter().position(|b| {
        let n = b.name.to_ascii_lowercase();
        b.speed_px_per_sec() > 0.0 && (n.contains("flight") || n.contains("fly") || n.contains("hover"))
    });
    named
        .or_else(|| bs.iter().position(|b| b.speed_px_per_sec() > 0.0))
        .unwrap_or_else(|| p.current_behavior_index())
}

// ------------------------------------------------------------------ effects

struct Particle {
    p: V2,
    v: V2,
    life: f32,
    max: f32,
    big: bool,
}

#[derive(Clone, Copy)]
enum Glow {
    /// Прямоугольник цели и плотность заливки (иконки заливаются гуще окон).
    Rect(RectI, f32),
    /// Пони целиком в магии: силуэт в прямоугольнике её спрайта.
    Aura(RectI),
    Point(V2),
}
const FILL_WINDOW: f32 = 0.28;
const FILL_ICON: f32 = 0.6;

#[derive(Default)]
struct Fx {
    particles: Vec<Particle>,
    glow: Option<Glow>,
    glow_level: f32,
    glow_want: f32,
    horn: Option<V2>,
    horn_level: f32,
    horn_want: f32,
    time: f32,
    spawn_acc: f32,
    stream_acc: f32,
}

impl Fx {
    fn burst(&mut self, rng: &mut fastrand::Rng, at: V2, n: usize) {
        for _ in 0..n {
            let a = rng.f32() * std::f32::consts::TAU;
            let s = 40.0 + rng.f32() * 160.0;
            let max = 0.4 + rng.f32() * 0.5;
            self.particles.push(Particle { p: at, v: V2::new(a.cos() * s, a.sin() * s), life: max, max, big: rng.bool() });
        }
    }

    fn glow_center(&self) -> Option<V2> {
        match self.glow? {
            Glow::Rect(r, _) | Glow::Aura(r) => Some(V2::new(r.x as f32 + r.w as f32 / 2.0, r.y as f32 + r.h as f32 / 2.0)),
            Glow::Point(p) => Some(p),
        }
    }

    fn update(&mut self, rng: &mut fastrand::Rng, dt: f32) {
        self.time += dt;
        let k = (dt * 6.0).min(1.0);
        self.glow_level += (self.glow_want - self.glow_level) * k;
        self.horn_level += (self.horn_want - self.horn_level) * k;
        for p in &mut self.particles {
            p.p += p.v * dt;
            p.v = p.v * (1.0 - (dt * 1.5).min(1.0));
            p.v.y -= 25.0 * dt;
            p.life -= dt;
        }
        self.particles.retain(|p| p.life > 0.0);

        // Искры, осыпающиеся с подсвеченной цели.
        if self.glow_level > 0.05 {
            if let Some(g) = self.glow {
                let rate = match g {
                    Glow::Rect(r, _) | Glow::Aura(r) => ((r.w + r.h) as f32 / 12.0).clamp(20.0, 90.0) * 1.5,
                    Glow::Point(_) => 30.0,
                } * self.glow_level;
                self.spawn_acc += rate * dt;
                while self.spawn_acc >= 1.0 {
                    self.spawn_acc -= 1.0;
                    let at = match g {
                        // треть искр — по всей площади (цель целиком в магии), остальные — по краю
                        Glow::Rect(r, _) if rng.f32() < 0.34 => {
                            V2::new(r.x as f32 + rng.f32() * r.w as f32, r.y as f32 + rng.f32() * r.h as f32)
                        }
                        Glow::Rect(r, _) => {
                            let per = 2.0 * (r.w + r.h) as f32;
                            let mut u = rng.f32() * per;
                            let (x, y) = (r.x as f32, r.y as f32);
                            let (w, h) = (r.w as f32, r.h as f32);
                            if u < w {
                                V2::new(x + u, y)
                            } else {
                                u -= w;
                                if u < h {
                                    V2::new(x + w, y + u)
                                } else {
                                    u -= h;
                                    if u < w { V2::new(x + w - u, y + h) } else { V2::new(x, y + h - (u - w)) }
                                }
                            }
                        }
                        Glow::Aura(r) => {
                            // по телу пони — ближе к центру спрайта, где сам персонаж
                            let a = rng.f32() * std::f32::consts::TAU;
                            let k = rng.f32().sqrt() * 0.6;
                            let c = V2::new(r.x as f32 + r.w as f32 / 2.0, r.y as f32 + r.h as f32 / 2.0);
                            c + V2::new(a.cos() * r.w as f32 / 2.0, a.sin() * r.h as f32 / 2.0) * k
                        }
                        Glow::Point(p) => {
                            let a = rng.f32() * std::f32::consts::TAU;
                            p + V2::new(a.cos(), a.sin()) * 14.0
                        }
                    };
                    let max = 0.6 + rng.f32() * 0.7;
                    let v = V2::new((rng.f32() - 0.5) * 30.0, -15.0 - rng.f32() * 35.0);
                    self.particles.push(Particle { p: at, v, life: max, max, big: rng.f32() < 0.3 });
                }
            }
        }
        // Поток магии от рога к цели.
        if self.horn_level > 0.2 {
            if let (Some(h), Some(c)) = (self.horn, self.glow_center()) {
                self.stream_acc += 45.0 * self.horn_level * dt;
                while self.stream_acc >= 1.0 {
                    self.stream_acc -= 1.0;
                    let jitter = V2::new((rng.f32() - 0.5) * 30.0, (rng.f32() - 0.5) * 30.0);
                    let max = 0.45;
                    let v = (c + jitter - h) / max;
                    self.particles.push(Particle { p: h, v, life: max, max, big: false });
                }
            }
        }
        if self.particles.len() > MAX_PARTICLES {
            let extra = self.particles.len() - MAX_PARTICLES;
            self.particles.drain(..extra);
        }
    }
}

#[inline]
fn plot(buf: &mut [u32], bw: usize, bh: usize, x: i32, y: i32, c: (u8, u8, u8), a: f32) {
    if x < 0 || y < 0 || x as usize >= bw || y as usize >= bh {
        return;
    }
    let a8 = (a.clamp(0.0, 1.0) * 255.0) as u32;
    if a8 == 0 {
        return;
    }
    let d = &mut buf[y as usize * bw + x as usize];
    let inv = 255 - a8;
    let mix = |sc: u32, dc: u32| (sc * a8 / 255 + (dc * inv + 127) / 255).min(255);
    let na = (a8 + ((*d >> 24) * inv + 127) / 255).min(255);
    let nr = mix(c.0 as u32, (*d >> 16) & 0xFF);
    let ng = mix(c.1 as u32, (*d >> 8) & 0xFF);
    let nb = mix(c.2 as u32, *d & 0xFF);
    *d = (na << 24) | (nr << 16) | (ng << 8) | nb;
}

/// Заливка всей площади цели цветом магии: окно (иконка) целиком «взято» магией.
/// Полупрозрачная, с медленными диагональными переливами; содержимое видно сквозь неё.
/// Переливы считаются по диагоналям (x + y), а не по пикселям — большие окна не тормозят.
fn fill_rect_magic(buf: &mut [u32], bw: usize, bh: usize, r: RectI, level: f32, time: f32, density: f32) {
    let x0 = r.x.max(0);
    let x1 = r.right().min(bw as i32);
    let y0 = r.y.max(0);
    let y1 = r.bottom().min(bh as i32);
    if x0 >= x1 || y0 >= y1 {
        return;
    }
    // яркость по диагонали: две волны разной длины, бегут медленно (0..256 — доля в 1/256)
    let dlen = ((x1 - x0) + (y1 - y0)) as usize + 1;
    let diag: Vec<u32> = (0..dlen)
        .map(|k| {
            let k = k as f32;
            let v = 0.8 + 0.12 * (k * 0.025 - time * 1.6).sin() + 0.08 * (k * 0.061 + time * 2.3).sin();
            (v * 256.0) as u32
        })
        .collect();
    let base = density * level.clamp(0.0, 1.0);
    // готовый цвет для пустого пикселя оверлея — по каждой прозрачности (почти все пиксели под окном пустые)
    let premul: Vec<u32> = (0..256u32)
        .map(|a| (a << 24) | ((MAGIC.0 as u32 * a / 255) << 16) | ((MAGIC.1 as u32 * a / 255) << 8) | (MAGIC.2 as u32 * a / 255))
        .collect();
    #[inline(always)]
    fn div255(v: u32) -> u32 {
        (v + 1 + (v >> 8)) >> 8
    }
    for y in y0..y1 {
        // к краям чуть плотнее — магия «держит» окно
        let ty = (y - r.y) as f32 / r.h.max(1) as f32;
        let row = (base * (1.0 + 0.25 * (2.0 * ty - 1.0).powi(4)) * 255.0) as u32;
        let line = &mut buf[y as usize * bw + x0 as usize..y as usize * bw + x1 as usize];
        let dstart = (y - y0) as usize;
        for (i, d) in line.iter_mut().enumerate() {
            let a8 = ((row * diag[dstart + i]) >> 8).min(255);
            if a8 == 0 {
                continue;
            }
            let src = premul[a8 as usize];
            if *d == 0 {
                *d = src;
                continue;
            }
            let inv = 255 - a8;
            let na = ((src >> 24) + div255((*d >> 24) * inv)).min(255);
            let nr = (((src >> 16) & 0xFF) + div255(((*d >> 16) & 0xFF) * inv)).min(255);
            let ng = (((src >> 8) & 0xFF) + div255(((*d >> 8) & 0xFF) * inv)).min(255);
            let nb = ((src & 0xFF) + div255((*d & 0xFF) * inv)).min(255);
            *d = (na << 24) | (nr << 16) | (ng << 8) | nb;
        }
    }
}

/// Сияние вокруг прямоугольника: яркая кромка и мягкий ореол наружу, с мерцанием.
fn draw_rect_glow(buf: &mut [u32], bw: usize, bh: usize, r: RectI, level: f32, time: f32) {
    const OUT: i32 = 12;
    const IN: i32 = 3;
    for d in -IN..=OUT {
        let base = if d <= 0 {
            0.6 * (1.0 - (-d) as f32 / (IN + 1) as f32)
        } else {
            0.6 * (1.0 - d as f32 / (OUT + 1) as f32).powi(2)
        } * level;
        if base <= 0.01 {
            continue;
        }
        let rr = inflate(r, d);
        if rr.w <= 0 || rr.h <= 0 {
            continue;
        }
        let shimmer = |x: i32, y: i32| 0.7 + 0.3 * (time * 5.0 + (x + y) as f32 * 0.05).sin();
        // Видимая часть — чтобы огромные окна не рисовались за пределами буфера.
        let x0 = rr.x.max(0);
        let x1 = rr.right().min(bw as i32);
        for x in x0..x1 {
            plot(buf, bw, bh, x, rr.y, MAGIC, base * shimmer(x, rr.y));
            plot(buf, bw, bh, x, rr.bottom() - 1, MAGIC, base * shimmer(x, rr.bottom()));
        }
        let y0 = (rr.y + 1).max(0);
        let y1 = (rr.bottom() - 1).min(bh as i32);
        for y in y0..y1 {
            plot(buf, bw, bh, rr.x, y, MAGIC, base * shimmer(rr.x, y));
            plot(buf, bw, bh, rr.right() - 1, y, MAGIC, base * shimmer(rr.right(), y));
        }
    }
}

/// Пони целиком в магии: её силуэт (непрозрачные пиксели, уже нарисованные в буфере
/// в пределах r) подкрашивается голубым с переливами, а по контуру снаружи — сияние.
/// Форма берётся из буфера, поэтому совпадает с текущим кадром гифки.
fn draw_aura(buf: &mut [u32], bw: usize, bh: usize, r: RectI, level: f32, time: f32) {
    const PAD: i32 = 5;
    const SOLID: u32 = 60; // альфа, с которой пиксель считается частью пони
    let o = inflate(r, PAD);
    let (x0, x1) = (o.x.max(0), o.right().min(bw as i32));
    let (y0, y1) = (o.y.max(0), o.bottom().min(bh as i32));
    if x0 >= x1 || y0 >= y1 {
        return;
    }
    let (w, h) = ((x1 - x0) as usize, (y1 - y0) as usize);
    // Расстояние (в шагах 3/4 — шамфер) до ближайшего пикселя силуэта.
    const FAR: u16 = u16::MAX / 2;
    let mut dist = vec![FAR; w * h];
    for y in 0..h {
        for x in 0..w {
            let (gx, gy) = (x0 + x as i32, y0 + y as i32);
            let inside = gx >= r.x && gx < r.right() && gy >= r.y && gy < r.bottom();
            if inside && (buf[gy as usize * bw + gx as usize] >> 24) >= SOLID {
                dist[y * w + x] = 0;
            }
        }
    }
    for y in 0..h {
        for x in 0..w {
            let mut d = dist[y * w + x];
            if x > 0 { d = d.min(dist[y * w + x - 1] + 3); }
            if y > 0 {
                d = d.min(dist[(y - 1) * w + x] + 3);
                if x > 0 { d = d.min(dist[(y - 1) * w + x - 1] + 4); }
                if x + 1 < w { d = d.min(dist[(y - 1) * w + x + 1] + 4); }
            }
            dist[y * w + x] = d;
        }
    }
    for y in (0..h).rev() {
        for x in (0..w).rev() {
            let mut d = dist[y * w + x];
            if x + 1 < w { d = d.min(dist[y * w + x + 1] + 3); }
            if y + 1 < h {
                d = d.min(dist[(y + 1) * w + x] + 3);
                if x + 1 < w { d = d.min(dist[(y + 1) * w + x + 1] + 4); }
                if x > 0 { d = d.min(dist[(y + 1) * w + x - 1] + 4); }
            }
            dist[y * w + x] = d;
        }
    }
    for y in 0..h {
        for x in 0..w {
            let d = dist[y * w + x] as f32 / 3.0;
            let (gx, gy) = (x0 + x as i32, y0 + y as i32);
            let shimmer = 0.75 + 0.25 * (time * 5.0 + (gx + gy) as f32 * 0.07).sin();
            let a = if d == 0.0 {
                0.38 // сам персонаж — полупрозрачная голубая заливка, рисунок виден
            } else if d <= PAD as f32 {
                0.75 * (1.0 - (d - 1.0) / PAD as f32).powi(2)
            } else {
                continue;
            };
            plot(buf, bw, bh, gx, gy, MAGIC, a * shimmer * level);
        }
    }
}

fn draw_disc(buf: &mut [u32], bw: usize, bh: usize, c: V2, radius: f32, color: (u8, u8, u8), level: f32) {
    let ri = radius.ceil() as i32;
    let (cx, cy) = (c.x.round() as i32, c.y.round() as i32);
    for dy in -ri..=ri {
        for dx in -ri..=ri {
            let d = ((dx * dx + dy * dy) as f32).sqrt();
            if d <= radius {
                plot(buf, bw, bh, cx + dx, cy + dy, color, level * (1.0 - d / radius).powi(2));
            }
        }
    }
}

fn draw_ring(buf: &mut [u32], bw: usize, bh: usize, c: V2, radius: f32, level: f32) {
    let ri = (radius + 6.0).ceil() as i32;
    let (cx, cy) = (c.x.round() as i32, c.y.round() as i32);
    for dy in -ri..=ri {
        for dx in -ri..=ri {
            let d = ((dx * dx + dy * dy) as f32).sqrt();
            let k = 1.0 - ((d - radius).abs() / 6.0);
            if k > 0.0 {
                plot(buf, bw, bh, cx + dx, cy + dy, MAGIC, level * 0.7 * k * k);
            }
        }
    }
}

// ------------------------------------------------------------------ controller

pub struct Luna {
    job: Option<Job>,
    cooldown: f32,
    /// Таймер «музыкальных» шалостей и открыта ли уже музыка в этом запуске.
    music_timer: f32,
    music_opened: bool,
    still: f32,
    last_cursor: (i32, i32),
    /// Курсор уже «обслужен» здесь (Луна пришла или подтянула его) — ждём, пока его сдвинут.
    settled: Option<(i32, i32)>,
    /// Луна, которую уложили спать мы (а не пользователь) — её будим, когда курсор сдвинут.
    slept_by_us: Option<PonyId>,
    /// Кнопка мыши была нажата при запуске колдовства (клик по пункту меню) —
    /// до её отпускания нажатие не считается вмешательством.
    ignore_buttons: bool,
    rng: fastrand::Rng,
    fx: Fx,
}

impl Default for Luna {
    fn default() -> Self {
        Luna::new(None)
    }
}

impl Luna {
    pub fn new(seed: Option<u64>) -> Luna {
        Luna {
            job: None,
            cooldown: FIRST_AUTO_SECS,
            music_timer: -1.0,
            music_opened: false,
            still: 0.0,
            last_cursor: (i32::MIN, i32::MIN),
            settled: None,
            slept_by_us: None,
            ignore_buttons: false,
            rng: match seed {
                Some(s) => fastrand::Rng::with_seed(s),
                None => fastrand::Rng::new(),
            },
            fx: Fx::default(),
        }
    }

    pub fn is_busy(&self) -> bool {
        self.job.is_some()
    }

    /// Нужно ли перерисовывать эффекты (идёт колдовство или гаснут искры).
    pub fn has_effects(&self) -> bool {
        !self.fx.particles.is_empty() || self.fx.glow_level > 0.01 || self.fx.horn_level > 0.01
    }

    pub fn update(&mut self, world: &mut World, desk: &mut dyn Desktop, input: &FrameInput, s: &LunaSettings, dt: f32) {
        let dt = dt.clamp(0.0, 0.1);
        if !input.buttons {
            self.ignore_buttons = false;
        }
        let input = &FrameInput { buttons: input.buttons && !self.ignore_buttons, ..*input };
        if input.cursor != self.last_cursor {
            self.last_cursor = input.cursor;
            self.still = 0.0;
        } else {
            self.still += dt;
        }
        if let Some(at) = self.settled {
            if dist(input.cursor, at) > 12.0 || input.buttons {
                self.settled = None;
                self.wake_ours(world);
            }
        }

        match self.job.take() {
            Some(Job::Cast(c)) => self.job = self.step_cast(c, world, desk, input, dt),
            Some(Job::GoSleep(g)) => self.job = self.step_go_sleep(g, world, input, dt),
            Some(Job::Video(v)) => self.job = self.step_video(v, world, desk, input, dt),
            None => self.pick_job(world, desk, input, s, dt),
        }
        if self.job.is_none() {
            self.fx.glow_want = 0.0;
            self.fx.horn_want = 0.0;
        }
        self.fx.update(&mut self.rng, dt);
    }

    /// Колдовство по команде (пункт меню). false — подходящей цели нет.
    pub fn cast(&mut self, world: &mut World, desk: &mut dyn Desktop, id: PonyId, spell: Spell, own: &[isize]) -> bool {
        if let Some(job) = self.job.take() {
            self.cancel(job, world, desk);
        }
        // Спящую Луну команда будит.
        if let Some(p) = world.pony_mut(id) {
            p.sleep = false;
        }
        if self.slept_by_us == Some(id) {
            self.slept_by_us = None;
        }
        self.ignore_buttons = true;
        if !matches!(spell, Spell::Window | Spell::Icon | Spell::Pony) {
            return self.start_spell(world, id, spell);
        }
        let ok = self.try_cast(world, desk, id, spell, own);
        if !ok {
            let said = if spell == Spell::Pony { "There is no pony here for Us to carry." } else { "We see nothing here worth moving." };
            world.say_custom(id, said);
        }
        ok
    }

    fn wake_ours(&mut self, world: &mut World) {
        if let Some(id) = self.slept_by_us.take() {
            if let Some(p) = world.pony_mut(id) {
                p.sleep = false;
            }
        }
    }

    fn cancel(&mut self, job: Job, world: &mut World, desk: &mut dyn Desktop) {
        match job {
            Job::Cast(c) => self.finish_cast(&c, world, desk),
            Job::GoSleep(g) => {
                if let Some(p) = world.pony_mut(g.pony) {
                    p.destination_override = None;
                }
            }
            Job::Video(v) => {
                if let Some(p) = world.pony_mut(v.pony) {
                    p.hold = None;
                }
            }
        }
    }

    /// «Magic: Play a video»: Луна зависает, открывает перед собой магический круг, «печатает» ссылку
    /// в облачке и открывает видео в браузере. Любое вмешательство (кнопка мыши, перетаскивание) — отмена
    /// до открытия, и тогда ничего не открывается.
    fn start_video(&mut self, world: &mut World, id: PonyId) -> bool {
        self.start_spell(world, id, Spell::Video)
    }

    /// Заклинания «на месте»: видео, открыть музыку, ▶/⏸, следующий/предыдущий трек.
    fn start_spell(&mut self, world: &mut World, id: PonyId, spell: Spell) -> bool {
        let (act, text, line) = match spell {
            Spell::Video => (Act::OpenUrl(VIDEO_URL), VIDEO_URL.to_string(), ""),
            Spell::Music => (Act::OpenMusic, "Yandex Music...".to_string(), ""),
            Spell::MusicPlayPause => (Act::Key(MediaKey::PlayPause), String::new(), "Silence! ...or music. As We please."),
            Spell::MusicNext => (Act::Key(MediaKey::Next), String::new(), "This song displeases Us. Next!"),
            Spell::MusicPrev => (Act::Key(MediaKey::Prev), String::new(), "Play that once more!"),
            Spell::Window | Spell::Icon | Spell::Pony => return false,
        };
        let Some(p) = world.pony(id) else { return false };
        let r = p.region();
        let area = world.ctx.area_at(r.x + r.w / 2, r.y + r.h / 2);
        let right = p.facing_right();
        let px_ = if right { r.right() as f32 + 60.0 } else { r.x as f32 - 60.0 };
        let py_ = r.y as f32 + r.h as f32 * 0.25;
        let portal = V2::new(
            px_.clamp(area.x as f32 + 30.0, area.right() as f32 - 30.0),
            py_.clamp(area.y as f32 + 30.0, area.bottom() as f32 - 30.0),
        );
        let behavior = hover_behavior(p);
        let facing_right = portal.x > p.location().x;
        world.pony_mut(id).unwrap().hold = Some(Hold { behavior, facing_right });
        if !line.is_empty() {
            world.say_custom(id, line);
        }
        self.job = Some(Job::Video(VideoJob { pony: id, t: 0.0, act, text, line, portal, typed: 0, opened: false }));
        true
    }

    fn step_video(&mut self, mut v: VideoJob, world: &mut World, desk: &mut dyn Desktop, input: &FrameInput, dt: f32) -> Option<Job> {
        let alive = world.pony(v.pony).map(|p| !p.is_dragging()).unwrap_or(false);
        let interrupted = !alive || input.manual.contains(&v.pony) || (input.buttons && !v.opened);
        if interrupted {
            if let Some(p) = world.pony_mut(v.pony) {
                p.hold = None;
            }
            self.fx.glow_want = 0.0;
            self.fx.horn_want = 0.0;
            return None;
        }
        v.t += dt;
        const CHARGE: f32 = 0.6;
        let n_text = v.text.chars().count();
        let type_secs = n_text as f32 / TYPE_CHARS_PER_SEC;
        // печатаем текст в облачке по буквам
        if v.t >= CHARGE && v.typed < n_text {
            let n = (((v.t - CHARGE) * TYPE_CHARS_PER_SEC) as usize).min(n_text);
            if n != v.typed {
                v.typed = n;
                let shown: String = v.text.chars().take(n).collect();
                world.say_custom(v.pony, &format!("{}|", shown));
            }
        }
        // допечатали — действие (один раз)
        if !v.opened && v.t >= CHARGE + type_secs + 0.4 {
            v.opened = true;
            match v.act {
                Act::OpenUrl(url) => {
                    let ok = desk.open_url(url);
                    world.say_custom(v.pony, if ok { "Behold! A vision for thee." } else { "Alas, the portal would not open." });
                }
                Act::OpenMusic => {
                    self.music_opened = true;
                    let said = match desk.open_music() {
                        MusicOpened::App | MusicOpened::Web => "Let the music of the night begin!",
                        MusicOpened::Failed => "Alas, the music would not come.",
                    };
                    world.say_custom(v.pony, said);
                }
                Act::Key(k) => {
                    desk.media_key(k);
                    let _ = v.line;
                }
            }
        }
        let active = !v.opened || v.t < CHARGE + type_secs + 1.0;
        self.fx.glow = Some(Glow::Point(v.portal));
        self.fx.glow_want = if active { 1.0 } else { 0.0 };
        self.fx.horn_want = if active { 1.0 } else { 0.0 };
        self.fx.horn = world.pony(v.pony).map(horn_point);
        if v.t >= CHARGE + type_secs + 1.8 {
            if let Some(p) = world.pony_mut(v.pony) {
                p.hold = None;
            }
            return None;
        }
        Some(Job::Video(v))
    }

    fn finish_cast(&mut self, c: &Cast, world: &mut World, desk: &mut dyn Desktop) {
        if let Some(p) = world.pony_mut(c.pony) {
            p.hold = None;
            if c.phase == Phase::Approach {
                p.destination_override = None;
            }
        }
        if c.icon_move_started {
            desk.end_icon_move();
        }
        if let Target::Pony { id, .. } = c.target {
            // Пони, которую схватил пользователь, остаётся у него: drag не трогаем.
            if let Some(p) = world.pony_mut(id) {
                p.carry = None;
            }
        }
        self.fx.glow_want = 0.0;
        self.fx.horn_want = 0.0;
    }

    fn pick_job(&mut self, world: &mut World, desk: &mut dyn Desktop, input: &FrameInput, s: &LunaSettings, dt: f32) {
        if input.blocked {
            return;
        }
        let lunas: Vec<PonyId> = world
            .ponies
            .iter()
            .filter(|p| is_luna(p) && !p.expired && !p.is_dragging() && !input.manual.contains(&p.id))
            .map(|p| p.id)
            .collect();
        if lunas.is_empty() {
            return;
        }

        // Курсор давно стоит — идём к нему спать (или подтягиваем его к себе).
        let c = input.cursor;
        if s.sleep_by_cursor
            && self.still >= s.cursor_idle_secs
            && self.settled.is_none()
            && !input.buttons
            && world.ctx.region.contains_point(c.0, c.1)
            && !world.ctx.dead_zones.iter().any(|z| z.contains_point(c.0, c.1))
        {
            let cv = V2::new(c.0 as f32, c.1 as f32);
            let id = *lunas
                .iter()
                .min_by(|a, b| {
                    let da = V2::dist_sq(world.pony(**a).unwrap().location(), cv);
                    let db = V2::dist_sq(world.pony(**b).unwrap().location(), cv);
                    da.total_cmp(&db)
                })
                .unwrap();
            let p = world.pony(id).unwrap();
            if p.sleep || p.is_sleeping() {
                self.start_cursor_pull(world, id, c);
            } else if p.destination_override.is_none() && p.hold.is_none() {
                self.start_go_sleep(world, id, c);
            }
            return;
        }

        // Музыка: раз за запуск открыть, потом время от времени переключать треки.
        if s.music {
            if self.music_timer < 0.0 {
                self.music_timer = MUSIC_FIRST_MIN + self.rng.f32() * (MUSIC_FIRST_MAX - MUSIC_FIRST_MIN);
            }
            self.music_timer -= dt;
            if self.music_timer <= 0.0 {
                self.music_timer = MUSIC_MIN_SECS + self.rng.f32() * (MUSIC_MAX_SECS - MUSIC_MIN_SECS);
                let awake: Vec<PonyId> =
                    lunas.iter().copied().filter(|id| !world.pony(*id).map(|p| p.is_busy() || p.sleep).unwrap_or(true)).collect();
                if !awake.is_empty() {
                    let id = awake[self.rng.usize(0..awake.len())];
                    let spell = if !self.music_opened {
                        Spell::Music
                    } else {
                        let r = self.rng.f32();
                        if r < 0.6 { Spell::MusicNext } else if r < 0.85 { Spell::MusicPlayPause } else { Spell::MusicPrev }
                    };
                    self.start_spell(world, id, spell);
                    return;
                }
            }
        }

        self.cooldown -= dt;
        if self.cooldown > 0.0 {
            return;
        }
        self.cooldown = AUTO_MIN_SECS + self.rng.f32() * (AUTO_MAX_SECS - AUTO_MIN_SECS);
        let mut spells = Vec::new();
        if s.move_windows {
            spells.push(Spell::Window);
        }
        if s.move_icons {
            spells.push(Spell::Icon);
        }
        if s.move_ponies {
            spells.push(Spell::Pony);
        }
        let awake: Vec<PonyId> = lunas.into_iter().filter(|id| !world.pony(*id).map(|p| p.is_busy() || p.sleep).unwrap_or(true)).collect();
        if spells.is_empty() || awake.is_empty() {
            return;
        }
        let id = awake[self.rng.usize(0..awake.len())];
        let first = self.rng.usize(0..spells.len());
        // Если для выбранного заклинания цели нет — пробуем другое.
        for k in 0..spells.len() {
            if self.try_cast(world, desk, id, spells[(first + k) % spells.len()], input.own_hwnds) {
                break;
            }
        }
    }

    fn try_cast(&mut self, world: &mut World, desk: &mut dyn Desktop, id: PonyId, spell: Spell, own: &[isize]) -> bool {
        let region = world.ctx.region;
        let Some(p) = world.pony(id) else { return false };
        let pr = p.region();
        let loc = p.location();
        // stay — Луна никуда не идёт, а притягивает цель к себе.
        let mut stay = false;
        let (target, from, to, focus) = match spell {
            Spell::Video | Spell::Music | Spell::MusicPlayPause | Spell::MusicNext | Spell::MusicPrev => {
                return self.start_spell(world, id, spell) // своё задание, без цели на экране
            }
            Spell::Window => {
                let any_area = |f: &RectI| world.ctx.area_at(f.x + f.w / 2, f.y + f.h / 2);
                let mut visible: Vec<WinInfo> = Vec::new();
                for w in desk.windows(own) {
                    let f = w.frame;
                    let inter = f.intersect(&region);
                    if inter.w < 100 || inter.h < 60 {
                        continue;
                    }
                    // Заголовок должен быть виден — иначе перенос никто не заметит.
                    let (tx, ty) = (f.x + f.w / 2, f.y + 12);
                    if !region.contains_point(tx, ty) || desk.window_at(tx, ty, own) != Some(w.hwnd) {
                        continue;
                    }
                    visible.push(w);
                    if visible.len() >= 8 {
                        break;
                    }
                }
                if visible.is_empty() {
                    return false;
                }
                let mut w = visible[self.rng.usize(0..visible.len())];
                if w.maximized {
                    // развёрнутое окно — сначала в обычный размер, потом понесём
                    desk.restore_window(w.hwnd);
                    match desk.windows(own).into_iter().find(|x| x.hwnd == w.hwnd && !x.maximized) {
                        Some(nw) => w = nw,
                        None => return false,
                    }
                }
                let f = w.frame;
                let area = any_area(&f);                         // монитор, где стоит окно
                let mut dest = None;
                for _ in 0..16 {
                    let sign = if self.rng.bool() { 1 } else { -1 };
                    let dx = sign * self.rng.i32(120..320);
                    let dy = self.rng.i32(-110..110);
                    let nx = clamp_span(f.x + dx, f.w, area.x, area.right());
                    let ny = clamp_span(f.y + dy, f.h, area.y, area.bottom());
                    if dist((nx, ny), (f.x, f.y)) >= 60.0 {
                        dest = Some((nx - f.x, ny - f.y));
                        break;
                    }
                }
                let Some((dx, dy)) = dest else { return false };
                let frame = RectI::new(f.x - w.rect.x, f.y - w.rect.y, f.w, f.h);
                (
                    Target::Window { hwnd: w.hwnd, size: (w.rect.w, w.rect.h), frame },
                    V2::new(w.rect.x as f32, w.rect.y as f32),
                    V2::new((w.rect.x + dx) as f32, (w.rect.y + dy) as f32),
                    f,
                )
            }
            Spell::Pony => {
                if !world.ctx.dragging_enabled {
                    return false;
                }
                let area = world.ctx.area_at(pr.x + pr.w / 2, pr.y + pr.h / 2); // монитор Луны
                let others: Vec<&Pony> = world
                    .ponies
                    .iter()
                    .filter(|o| {
                        let r = o.region();
                        o.id != id
                            && !is_luna(o)
                            && !o.expired
                            && !o.sleep
                            && !o.drag
                            && o.carry.is_none()
                            && !o.is_busy()
                            && r.w > 0
                            && area.contains_point(r.x + r.w / 2, r.y + r.h / 2)
                    })
                    .collect();
                if others.is_empty() {
                    return false;
                }
                let t = others[self.rng.usize(0..others.len())];
                let tr = t.region();
                let tloc = t.location();
                let to = if (tloc - loc).length() > BRING_PONY_PX {
                    // далеко — приносим к себе и ставим рядом
                    stay = true;
                    let tl_x = if tloc.x < loc.x { pr.x - tr.w - 10 } else { pr.right() + 10 };
                    location_for_top_left(t, (tl_x, pr.bottom() - tr.h), area)
                } else {
                    let mut dest = None;
                    for _ in 0..16 {
                        let sign = if self.rng.bool() { 1 } else { -1 };
                        let tl = (tr.x + sign * self.rng.i32(120..300), tr.y + self.rng.i32(-90..90));
                        let nl = location_for_top_left(t, tl, area);
                        if (nl - tloc).length() >= 60.0 {
                            dest = Some(nl);
                            break;
                        }
                    }
                    let Some(nl) = dest else { return false };
                    nl
                };
                let rect = RectI::new(tr.x - tloc.x.round() as i32, tr.y - tloc.y.round() as i32, tr.w, tr.h);
                (Target::Pony { id: t.id, rect }, tloc, to, tr)
            }
            Spell::Icon => {
                let (Some(icons), Some(area)) = (desk.icons(), desk.icon_area()) else { return false };
                let area = area.intersect(&region);
                let inside: Vec<IconInfo> = icons
                    .iter()
                    .copied()
                    .filter(|i| i.rect.w > 0 && i.rect.x >= area.x && i.rect.y >= area.y && i.rect.right() <= area.right() && i.rect.bottom() <= area.bottom())
                    .collect();
                if inside.is_empty() {
                    return false;
                }
                let icon = inside[self.rng.usize(0..inside.len())];
                let r = icon.rect;
                let area = area.intersect(&world.ctx.area_at(r.x + r.w / 2, r.y + r.h / 2)); // монитор иконки
                let mut dest = None;
                for _ in 0..24 {
                    let sx = if self.rng.bool() { 1 } else { -1 };
                    let sy = if self.rng.bool() { 1 } else { -1 };
                    let nx = clamp_span(r.x + sx * self.rng.i32(80..260), r.w, area.x + 4, area.right() - 4);
                    let ny = clamp_span(r.y + sy * self.rng.i32(0..180), r.h, area.y + 4, area.bottom() - 4);
                    let nr = RectI::new(nx, ny, r.w, r.h);
                    let free = icons.iter().all(|o| o.index == icon.index || !intersects(&inflate(o.rect, 6), &nr));
                    if free && dist((nx, ny), (r.x, r.y)) >= 50.0 {
                        dest = Some((nx - r.x, ny - r.y));
                        break;
                    }
                }
                let Some((dx, dy)) = dest else { return false };
                let rel = RectI::new(r.x - icon.pos.0, r.y - icon.pos.1, r.w, r.h);
                (
                    Target::Icon { index: icon.index, rect: rel },
                    V2::new(icon.pos.0 as f32, icon.pos.1 as f32),
                    V2::new((icon.pos.0 + dx) as f32, (icon.pos.1 + dy) as f32),
                    r,
                )
            }
        };

        // Место рядом с целью, со стороны Луны, на уровне верха цели.
        let left_side = loc.x < (focus.x + focus.w / 2) as f32;
        let tl_x = if left_side { focus.x - pr.w - 8 } else { focus.right() + 8 };
        let tl_y = focus.y + focus.h.min(60) / 2 - pr.h / 2;
        let spot_area = world.ctx.area_at(tl_x + pr.w / 2, tl_y + pr.h / 2);
        let spot = if stay { loc } else { location_for_top_left(p, (tl_x, tl_y), spot_area) };
        let d = (to - from).length();
        let is_icon = matches!(target, Target::Icon { .. });
        let is_pony = matches!(target, Target::Pony { .. });
        let lines: &[&'static str] = match target {
            Target::Icon { .. } => &ICON_LINES,
            Target::Pony { .. } => &PONY_LINES,
            _ => &WINDOW_LINES,
        };
        let line = if stay {
            Some(PONY_BRING_LINE)
        } else if self.rng.f32() < if is_pony { 0.6 } else { 0.4 } {
            Some(lines[self.rng.usize(0..lines.len())])
        } else {
            None
        };
        let cast = Cast {
            pony: id,
            target,
            from,
            to,
            cur: from,
            phase: Phase::Approach,
            t: 0.0,
            move_secs: (0.9 + d / 260.0).clamp(1.2, 3.0),
            lift: if is_icon {
                (d * 0.15).min(25.0)
            } else if is_pony {
                (d * 0.2).min(60.0)
            } else {
                (d * 0.12).min(40.0)
            },
            spot,
            last_set: None,
            icon_move_started: false,
            line,
        };
        if (spot - loc).length() > TELEPORT_APPROACH_PX {
            self.teleport(world, id, spot);
        }
        self.job = Some(Job::Cast(cast));
        true
    }

    /// Телепорт с магической вспышкой в обеих точках.
    fn teleport(&mut self, world: &mut World, id: PonyId, to: V2) {
        let Some(p) = world.pony_mut(id) else { return };
        let r = p.region();
        let from_c = V2::new(r.x as f32 + r.w as f32 / 2.0, r.y as f32 + r.h as f32 / 2.0);
        let shift = to - p.location();
        p.set_location(to);
        self.fx.burst(&mut self.rng, from_c, 50);
        self.fx.burst(&mut self.rng, from_c + shift, 50);
    }

    fn start_cursor_pull(&mut self, world: &mut World, id: PonyId, c: (i32, i32)) {
        let Some(p) = world.pony(id) else { return };
        let r = p.region();
        let region = world.ctx.area_at(r.x + r.w / 2, r.y + r.h / 2);   // монитор, где спит Луна
        let fx = if p.facing_right() { 0.95 } else { 0.05 };
        let tx = ((r.x as f32 + r.w as f32 * fx) as i32).clamp(region.x + 2, region.right() - 3);
        let ty = ((r.y as f32 + r.h as f32 * 0.45) as i32).clamp(region.y + 2, region.bottom() - 3);
        let d = dist(c, (tx, ty));
        if d < 30.0 {
            self.settled = Some(c);
            return;
        }
        let from = V2::new(c.0 as f32, c.1 as f32);
        self.job = Some(Job::Cast(Cast {
            pony: id,
            target: Target::Cursor,
            from,
            to: V2::new(tx as f32, ty as f32),
            cur: from,
            phase: Phase::Charge,
            t: 0.0,
            move_secs: (0.8 + d / 400.0).clamp(1.0, 2.8),
            lift: (d * 0.15).min(30.0),
            spot: p.location(),
            last_set: None,
            icon_move_started: false,
            line: None,
        }));
    }

    fn start_go_sleep(&mut self, world: &mut World, id: PonyId, c: (i32, i32)) {
        let region = world.ctx.area_at(c.0, c.1);                   // монитор, где курсор
        let Some(p) = world.pony(id) else { return };
        let r = p.region();
        let loc = p.location();
        // Луна ложится сбоку от курсора так, чтобы он оказался у её головы.
        let facing_right = loc.x <= c.0 as f32;
        let tl_x = if facing_right { c.0 - (r.w as f32 * 0.88) as i32 } else { c.0 - (r.w as f32 * 0.12) as i32 };
        let tl_y = c.1 - (r.h as f32 * 0.42) as i32;
        let mut spot = location_for_top_left(p, (tl_x, tl_y), region);
        let far = (spot - loc).length();
        if far > TELEPORT_TO_CURSOR_PX {
            // Далеко: телепорт поближе, остаток пути — пешком.
            let near = spot + (loc - spot) * (200.0 / far);
            self.teleport(world, id, near);
        }
        spot.x = spot.x.round();
        spot.y = spot.y.round();
        if let Some(p) = world.pony_mut(id) {
            p.destination_override = Some(spot);
        }
        self.job = Some(Job::GoSleep(GoSleep { pony: id, spot, facing_right, t: 0.0, cursor: c }));
    }

    fn step_go_sleep(&mut self, mut g: GoSleep, world: &mut World, input: &FrameInput, dt: f32) -> Option<Job> {
        let Some(p) = world.pony_mut(g.pony) else { return None };
        let interrupted = p.is_dragging() || p.sleep || input.blocked || input.buttons || input.manual.contains(&g.pony)
            || dist(input.cursor, g.cursor) > 6.0;
        if interrupted {
            p.destination_override = None;
            return None;
        }
        g.t += dt;
        if V2::dist_sq(p.location(), g.spot) < 16.0 || g.t > WALK_TO_CURSOR_MAX_SECS {
            p.destination_override = None;
            p.set_facing_right(g.facing_right);
            p.sleep = true;
            self.slept_by_us = Some(g.pony);
            self.settled = Some(g.cursor);
            return None;
        }
        p.destination_override = Some(g.spot);
        Some(Job::GoSleep(g))
    }

    fn target_rect(c: &Cast) -> Option<RectI> {
        let (x, y) = (c.cur.x.round() as i32, c.cur.y.round() as i32);
        match c.target {
            Target::Window { frame, .. } => Some(RectI::new(x + frame.x, y + frame.y, frame.w, frame.h)),
            Target::Icon { rect, .. } | Target::Pony { rect, .. } => Some(RectI::new(x + rect.x, y + rect.y, rect.w, rect.h)),
            Target::Cursor => None,
        }
    }

    /// Цель ещё на месте и её не трогал пользователь.
    fn target_ok(c: &Cast, world: &World, desk: &mut dyn Desktop, input: &FrameInput) -> bool {
        match c.target {
            // Пони ещё здесь, её не схватил пользователь и не взял под управление.
            Target::Pony { id, .. } => {
                world.pony(id).map(|p| !p.expired && !p.drag && p.carry.is_some()).unwrap_or(false) && !input.manual.contains(&id)
            }
            Target::Window { hwnd, size, .. } => match desk.window_rect(hwnd) {
                None => false,
                Some(r) => {
                    if (r.w, r.h) != size {
                        return false;
                    }
                    // Перенос асинхронный — допускаем отставание на пару кадров.
                    let expect = c.last_set.unwrap_or((c.from.x as i32, c.from.y as i32));
                    dist((r.x, r.y), expect) < 80.0
                }
            },
            Target::Icon { .. } => true,
            Target::Cursor => {
                let expect = c.last_set.unwrap_or((c.from.x as i32, c.from.y as i32));
                dist(input.cursor, expect) <= 4.0
            }
        }
    }

    fn apply(c: &mut Cast, desk: &mut dyn Desktop) {
        let pos = (c.cur.x.round() as i32, c.cur.y.round() as i32);
        if c.last_set == Some(pos) {
            return;
        }
        match c.target {
            Target::Window { hwnd, .. } => desk.move_window(hwnd, pos.0, pos.1),
            Target::Icon { index, .. } => desk.move_icon(index, pos),
            Target::Cursor => desk.set_cursor(pos.0, pos.1),
            Target::Pony { .. } => {} // переносит step_cast через Pony::carry
        }
        c.last_set = Some(pos);
    }

    fn step_cast(&mut self, mut c: Cast, world: &mut World, desk: &mut dyn Desktop, input: &FrameInput, dt: f32) -> Option<Job> {
        let alive = world.pony(c.pony).map(|p| !p.is_dragging()).unwrap_or(false);
        let user_busy = input.blocked || input.manual.contains(&c.pony) || (input.buttons && c.phase != Phase::Release);
        if !alive || user_busy {
            self.finish_cast(&c, world, desk);
            return None;
        }
        c.t += dt;
        match c.phase {
            Phase::Approach => {
                let p = world.pony_mut(c.pony).unwrap();
                if V2::dist_sq(p.location(), c.spot) < 36.0 || c.t > APPROACH_MAX_SECS {
                    p.destination_override = None;
                    let focus = Self::target_rect(&c).unwrap_or_default();
                    let facing_right = (focus.x + focus.w / 2) as f32 > p.location().x;
                    let behavior = hover_behavior(p);
                    p.hold = Some(Hold { behavior, facing_right });
                    c.phase = Phase::Charge;
                    c.t = 0.0;
                    if let Target::Pony { id, .. } = c.target {
                        // Пока Луна шла, пони могла уйти или занять себя чем-то — берём
                        // её с того места, где она сейчас, и сразу «поднимаем» (drag).
                        let free = world.pony(id).map(|t| !t.expired && !t.sleep && !t.drag && !t.is_busy()).unwrap_or(false);
                        if !free || input.manual.contains(&id) {
                            self.finish_cast(&c, world, desk);
                            return None;
                        }
                        let t = world.pony_mut(id).unwrap();
                        let shift = t.location() - c.from;
                        c.from = t.location();
                        c.cur = c.from;
                        // принесённую к Луне ставим рядом с ней, остальных — с тем же сдвигом
                        if c.line != Some(PONY_BRING_LINE) {
                            c.to = c.to + shift;
                        }
                        t.carry = Some(c.from);
                    }
                    if let Some(line) = c.line {
                        world.say_custom(c.pony, line);
                    }
                } else {
                    p.destination_override = Some(c.spot);
                }
            }
            Phase::Charge => {
                if !Self::target_ok(&c, world, desk, input) {
                    self.finish_cast(&c, world, desk);
                    return None;
                }
                if c.t >= CHARGE_SECS {
                    c.phase = Phase::Move;
                    c.t = 0.0;
                    if matches!(c.target, Target::Icon { .. }) {
                        desk.begin_icon_move();
                        c.icon_move_started = true;
                    }
                }
            }
            Phase::Move => {
                if !Self::target_ok(&c, world, desk, input) {
                    self.finish_cast(&c, world, desk);
                    return None;
                }
                let k = (c.t / c.move_secs).min(1.0);
                let arc = V2::new(0.0, -c.lift * (k * std::f32::consts::PI).sin());
                c.cur = c.from + (c.to - c.from) * ease_in_out(k) + arc;
                if let Target::Pony { id, .. } = c.target {
                    if let Some(t) = world.pony_mut(id) {
                        t.carry = Some(c.cur);
                    }
                } else {
                    Self::apply(&mut c, desk);
                }
                if k >= 1.0 {
                    if c.icon_move_started {
                        // Иконка остаётся ровно там, куда её принесли: повторно
                        // позицию не задаём, чтобы explorer не притянул её к сетке.
                        desk.end_icon_move();
                        c.icon_move_started = false;
                    }
                    if matches!(c.target, Target::Cursor) {
                        self.settled = Some((c.to.x.round() as i32, c.to.y.round() as i32));
                    }
                    if let Target::Pony { id, .. } = c.target {
                        // поставили — пони выходит из drag и живёт дальше
                        if let Some(t) = world.pony_mut(id) {
                            t.carry = None;
                        }
                    }
                    c.phase = Phase::Release;
                    c.t = 0.0;
                }
            }
            Phase::Release => {
                if c.t >= RELEASE_SECS {
                    self.finish_cast(&c, world, desk);
                    return None;
                }
            }
        }

        // Эффекты: сияние цели и рога.
        let active = matches!(c.phase, Phase::Charge | Phase::Move);
        self.fx.glow_want = if active { 1.0 } else { 0.0 };
        self.fx.horn_want = if active { 1.0 } else { 0.0 };
        if let Target::Pony { id, ref mut rect } = c.target {
            // у drag-гифки свой размер — рамку берём с текущего кадра пони
            if let Some(t) = world.pony(id) {
                let (r, l) = (t.region(), t.location());
                *rect = RectI::new(r.x - l.x.round() as i32, r.y - l.y.round() as i32, r.w, r.h);
            }
        }
        if c.phase != Phase::Approach {
            let density = if matches!(c.target, Target::Icon { .. }) { FILL_ICON } else { FILL_WINDOW };
            self.fx.glow = Some(match Self::target_rect(&c) {
                Some(r) if matches!(c.target, Target::Pony { .. }) => Glow::Aura(r),
                Some(r) => Glow::Rect(r, density),
                None => Glow::Point(c.cur),
            });
            self.fx.horn = world.pony(c.pony).map(horn_point);
        }
        Some(Job::Cast(c))
    }

    /// Рисует магию в буфер оверлея (origin — экранные координаты его левого верхнего угла).
    pub fn draw(&self, buf: &mut [u32], bw: usize, bh: usize, origin: (i32, i32)) {
        let fx = &self.fx;
        let o = V2::new(origin.0 as f32, origin.1 as f32);
        if fx.glow_level > 0.01 {
            match fx.glow {
                Some(Glow::Rect(r, density)) => {
                    let local = RectI::new(r.x - origin.0, r.y - origin.1, r.w, r.h);
                    fill_rect_magic(buf, bw, bh, local, fx.glow_level, fx.time, density);
                    draw_rect_glow(buf, bw, bh, local, fx.glow_level, fx.time);
                }
                Some(Glow::Aura(r)) => {
                    let local = RectI::new(r.x - origin.0, r.y - origin.1, r.w, r.h);
                    draw_aura(buf, bw, bh, local, fx.glow_level, fx.time);
                }
                Some(Glow::Point(p)) => {
                    let pulse = 13.0 + 2.0 * (fx.time * 6.0).sin();
                    draw_disc(buf, bw, bh, p - o, pulse, MAGIC, fx.glow_level * 0.45);
                    draw_ring(buf, bw, bh, p - o, pulse, fx.glow_level);
                }
                None => {}
            }
        }
        for p in &fx.particles {
            let a = (p.life / p.max).clamp(0.0, 1.0);
            let (x, y) = ((p.p.x - o.x).round() as i32, (p.p.y - o.y).round() as i32);
            plot(buf, bw, bh, x, y, SPARK, a);
            let arm = a * if p.big { 0.8 } else { 0.45 };
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                plot(buf, bw, bh, x + dx, y + dy, MAGIC, arm);
            }
            if p.big {
                for (dx, dy) in [(2, 0), (-2, 0), (0, 2), (0, -2)] {
                    plot(buf, bw, bh, x + dx, y + dy, MAGIC, a * 0.35);
                }
            }
        }
        if fx.horn_level > 0.01 {
            if let Some(h) = fx.horn {
                let pulse = 1.0 + 0.15 * (fx.time * 9.0).sin();
                draw_disc(buf, bw, bh, h - o, 11.0 * pulse, MAGIC, fx.horn_level * 0.9);
                draw_disc(buf, bw, bh, h - o, 4.0, SPARK, fx.horn_level);
            }
        }
    }
}

// ------------------------------------------------------------------ tests

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::*;
    use crate::sim::{Context, STEP_SIZE};
    use std::path::PathBuf;
    use std::rc::Rc;

    #[derive(Default)]
    struct MockDesk {
        windows: Vec<WinInfo>,
        icons: Vec<IconInfo>,
        area: RectI,
        cursor_sets: Vec<(i32, i32)>,
        window_moves: Vec<(i32, i32)>,
        icon_moves: Vec<(usize, (i32, i32))>,
        snap_depth: i32,
        snap_calls: i32,
        restored: i32,
        opened: Vec<String>,
        music_opens: i32,
        has_music_app: bool,
        keys: Vec<MediaKey>,
        moves_with_grid_on: usize,
    }

    impl Desktop for MockDesk {
        fn windows(&mut self, own: &[isize]) -> Vec<WinInfo> {
            self.windows.iter().copied().filter(|w| !own.contains(&w.hwnd)).collect()
        }
        fn window_at(&mut self, x: i32, y: i32, own: &[isize]) -> Option<isize> {
            self.windows.iter().find(|w| !own.contains(&w.hwnd) && w.rect.contains_point(x, y)).map(|w| w.hwnd)
        }
        fn restore_window(&mut self, hwnd: isize) {
            if let Some(w) = self.windows.iter_mut().find(|w| w.hwnd == hwnd && w.maximized) {
                w.maximized = false;
                w.rect = RectI::new(300, 150, 800, 500);
                w.frame = w.rect;
                self.restored += 1;
            }
        }
        fn window_rect(&mut self, hwnd: isize) -> Option<RectI> {
            self.windows.iter().find(|w| w.hwnd == hwnd).map(|w| w.rect)
        }
        fn move_window(&mut self, hwnd: isize, x: i32, y: i32) {
            self.window_moves.push((x, y));
            if let Some(w) = self.windows.iter_mut().find(|w| w.hwnd == hwnd) {
                let (dx, dy) = (x - w.rect.x, y - w.rect.y);
                w.rect.x = x;
                w.rect.y = y;
                w.frame.x += dx;
                w.frame.y += dy;
            }
        }
        fn icons(&mut self) -> Option<Vec<IconInfo>> {
            Some(self.icons.clone())
        }
        fn icon_area(&mut self) -> Option<RectI> {
            Some(self.area)
        }
        fn move_icon(&mut self, index: usize, pos: (i32, i32)) {
            self.icon_moves.push((index, pos));
            if self.snap_depth == 0 {
                self.moves_with_grid_on += 1;
            }
            if let Some(i) = self.icons.iter_mut().find(|i| i.index == index) {
                i.rect.x += pos.0 - i.pos.0;
                i.rect.y += pos.1 - i.pos.1;
                i.pos = pos;
            }
        }
        fn begin_icon_move(&mut self) {
            self.snap_depth += 1;
            self.snap_calls += 1;
        }
        fn end_icon_move(&mut self) {
            self.snap_depth -= 1;
        }
        fn set_cursor(&mut self, x: i32, y: i32) {
            self.cursor_sets.push((x, y));
        }
        fn open_url(&mut self, url: &str) -> bool {
            self.opened.push(url.to_string());
            crate::desktop::safe_url(url)
        }
        fn open_music(&mut self) -> MusicOpened {
            self.music_opens += 1;
            if self.has_music_app { MusicOpened::App } else { MusicOpened::Web }
        }
        fn media_key(&mut self, key: MediaKey) {
            self.keys.push(key);
        }
    }

    fn beh(name: &str, speed: f64, mv: u8) -> Behavior {
        let mut b = Behavior::new();
        b.name = name.to_string();
        b.chance = 1.0;
        b.speed = speed;
        b.allowed_movement = mv;
        b.min_duration = 3.0;
        b.max_duration = 5.0;
        b.right_image.size = (144, 128);
        b.left_image.size = (144, 128);
        b
    }

    fn luna_world() -> (World, PonyId) {
        let mut base = PonyBase::new("Princess Luna", PathBuf::new());
        base.behaviors = vec![
            beh("stand", 0.0, moves::MOUSE_OVER),
            beh("walk", 3.0, moves::DIAGONAL_HORIZONTAL),
            beh("flight", 3.0, moves::ALL),
        ];
        let mut w = World::new(Context::new(RectI::new(0, 0, 1600, 900)), Some(7));
        w.ctx.random_speech_chance = 0.0;
        w.ctx.cursor_avoidance_enabled = false;
        let id = w.add_pony_at(Rc::new(base), V2::new(400.0, 500.0));
        (w, id)
    }

    struct Run {
        t: f64,
    }

    impl Run {
        /// Кадры по 1/60 с: Луна, затем симуляция — как в app.rs.
        fn frames(&mut self, luna: &mut Luna, w: &mut World, d: &mut MockDesk, cursor: &mut (i32, i32), secs: f32, buttons: bool) {
            let n = (secs * 60.0) as usize;
            for _ in 0..n {
                if let Some(c) = d.cursor_sets.last() {
                    *cursor = *c;
                }
                let input = FrameInput { cursor: *cursor, buttons, blocked: false, manual: &[], own_hwnds: &[] };
                luna.update(w, d, &input, &LunaSettings { move_windows: false, move_icons: false, music: false, ..Default::default() }, 1.0 / 60.0);
                self.t += 1000.0 / 60.0;
                w.update(self.t);
            }
        }
    }

    fn max_step(moves: &[(i32, i32)]) -> f32 {
        moves.windows(2).map(|m| dist(m[0], m[1])).fold(0.0, f32::max)
    }

    #[test]
    fn window_moves_smoothly_and_releases_luna() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        let rect = RectI::new(700, 200, 600, 400);
        d.windows.push(WinInfo { hwnd: 42, rect, frame: RectI::new(707, 200, 586, 393), maximized: false });
        let mut luna = Luna::new(Some(3));
        let mut cursor = (1500, 850);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Window, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 1.0, false);
        assert!(w.pony(id).unwrap().hold.is_some(), "Луна зависает и колдует");
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 12.0, false);
        assert!(!luna.is_busy());
        assert!(w.pony(id).unwrap().hold.is_none(), "после колдовства Луна свободна");
        assert!(d.window_moves.len() > 30, "перенос идёт много кадров, а не рывком: {}", d.window_moves.len());
        assert!(max_step(&d.window_moves) < 25.0, "шаги маленькие: {}", max_step(&d.window_moves));
        let end = d.windows[0].rect;
        assert!(dist((end.x, end.y), (rect.x, rect.y)) >= 60.0);
        let f = d.windows[0].frame;
        let reg = w.ctx.region;
        assert!(f.x >= reg.x && f.right() <= reg.right() && f.y >= reg.y && f.bottom() <= reg.bottom(), "окно не уехало за экран");
    }

    #[test]
    fn menu_cast_ignores_own_overlay_and_restores_maximized_window() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        // наш оверлей (hwnd 900) на весь экран поверх всего — как при открытом меню пони
        d.windows.push(WinInfo { hwnd: 900, rect: RectI::new(0, 0, 1600, 900), frame: RectI::new(0, 0, 1600, 900), maximized: false });
        let full = RectI::new(0, 0, 1600, 860);
        d.windows.push(WinInfo { hwnd: 7, rect: full, frame: full, maximized: true });
        let mut luna = Luna::new(Some(21));
        assert!(luna.cast(&mut w, &mut d, id, Spell::Window, &[900]), "окно найдено сквозь оверлей");
        assert_eq!(d.restored, 1, "развёрнутое окно вернули в обычный размер");
        let mut cursor = (1500, 850);
        let mut run = Run { t: STEP_SIZE };
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 12.0, false);
        assert!(!d.window_moves.is_empty(), "окно двигалось");
        let r = d.windows.iter().find(|x| x.hwnd == 7).unwrap().rect;
        assert!(r.x != 300 || r.y != 150, "окно на новом месте");
    }

    #[test]
    fn video_opens_once_after_typing_and_click_cancels_before_open() {
        let (mut w, id) = luna_world();
        w.ctx.speech_enabled = true;
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(3));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Video, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 1.5, false);
        assert!(d.opened.is_empty(), "пока печатает — не открывает");
        assert!(w.pony(id).unwrap().speech_text().unwrap_or("").contains("https://"), "ссылка печатается в облачке");
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 6.0, false);
        assert_eq!(d.opened, vec![VIDEO_URL.to_string()], "открыто ровно один раз");
        assert!(!luna.is_busy() && w.pony(id).unwrap().hold.is_none());

        // щелчок мышью до открытия — отмена, ничего не открывается
        let mut d2 = MockDesk::default();
        assert!(luna.cast(&mut w, &mut d2, id, Spell::Video, &[]));
        run.frames(&mut luna, &mut w, &mut d2, &mut cursor, 0.1, false); // отпустили кнопку после меню
        run.frames(&mut luna, &mut w, &mut d2, &mut cursor, 0.2, true);
        run.frames(&mut luna, &mut w, &mut d2, &mut cursor, 6.0, false);
        assert!(d2.opened.is_empty(), "после отмены видео не открывается");
    }

    #[test]
    fn menu_music_opens_app_then_media_keys_are_pressed() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk { has_music_app: true, ..Default::default() };
        let mut luna = Luna::new(Some(8));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Music, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 4.0, false);
        assert_eq!(d.music_opens, 1, "музыка открыта один раз");
        for (sp, key) in [(Spell::MusicNext, MediaKey::Next), (Spell::MusicPlayPause, MediaKey::PlayPause), (Spell::MusicPrev, MediaKey::Prev)] {
            assert!(luna.cast(&mut w, &mut d, id, sp, &[]));
            run.frames(&mut luna, &mut w, &mut d, &mut cursor, 0.2, false);
            assert!(d.keys.last() != Some(&key) || d.keys.len() > 3, "клавиша не раньше, чем Луна наколдует");
            run.frames(&mut luna, &mut w, &mut d, &mut cursor, 3.0, false);
            assert_eq!(d.keys.last(), Some(&key));
        }
        assert_eq!(d.keys.len(), 3, "каждое заклинание — ровно одно нажатие");
    }

    #[test]
    fn luna_opens_music_by_herself_once_then_switches_tracks() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(12));
        let s = LunaSettings { move_windows: false, move_icons: false, sleep_by_cursor: false, music: true, move_ponies: false, cursor_idle_secs: 20.0 };
        let mut t = STEP_SIZE;
        for k in 0..(60 * 60 * 25) {
            // курсор двигается — пользователь за компьютером
            let input = FrameInput { cursor: (100 + (k % 50) as i32, 100), buttons: false, blocked: false, manual: &[], own_hwnds: &[] };
            luna.update(&mut w, &mut d, &input, &s, 1.0 / 60.0);
            t += 1000.0 / 60.0;
            w.update(t);
        }
        assert_eq!(d.music_opens, 1, "сама открыла музыку ровно один раз");
        assert!(d.keys.len() >= 2, "потом переключала треки: {:?}", d.keys);
        let _ = id;
        // выключено — ничего
        let (mut w2, _) = luna_world();
        let mut d2 = MockDesk::default();
        let mut luna2 = Luna::new(Some(12));
        let off = LunaSettings { music: false, ..s };
        let mut t = STEP_SIZE;
        for k in 0..(60 * 60 * 10) {
            let input = FrameInput { cursor: (100 + (k % 50) as i32, 100), buttons: false, blocked: false, manual: &[], own_hwnds: &[] };
            luna2.update(&mut w2, &mut d2, &input, &off, 1.0 / 60.0);
            t += 1000.0 / 60.0;
            w2.update(t);
        }
        assert_eq!((d2.music_opens, d2.keys.len()), (0, 0), "выключено — музыку не трогает");
    }

    #[test]
    fn only_web_links_are_allowed() {
        assert!(crate::desktop::safe_url(VIDEO_URL));
        assert!(!crate::desktop::safe_url("file:///C:/Windows/System32/cmd.exe"));
        assert!(!crate::desktop::safe_url("cmd /c something"));
        assert!(!crate::desktop::safe_url("https://a.b/ \" && evil\""));
    }

    #[test]
    fn mouse_button_interrupts_window_move() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        d.windows.push(WinInfo { hwnd: 1, rect: RectI::new(700, 200, 600, 400), frame: RectI::new(700, 200, 600, 400), maximized: false });
        let mut luna = Luna::new(Some(5));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Window, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 1.5, false);
        let moved = d.window_moves.len();
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 0.1, true);
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 3.0, false);
        assert!(!luna.is_busy());
        assert!(w.pony(id).unwrap().hold.is_none());
        assert!(d.window_moves.len() <= moved + 1, "после нажатия окно больше не двигается");
    }

    #[test]
    fn icon_moves_to_free_spot_and_restores_grid() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk { area: RectI::new(0, 0, 1600, 860), ..Default::default() };
        for k in 0..6 {
            let pos = (10, 10 + k * 100);
            d.icons.push(IconInfo { index: k as usize, pos, rect: RectI::new(pos.0 + 2, pos.1, 76, 90) });
        }
        let mut luna = Luna::new(Some(11));
        let mut cursor = (1500, 850);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Icon, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 15.0, false);
        assert!(!luna.is_busy());
        assert_eq!((d.snap_calls, d.snap_depth), (1, 0), "сетка выключалась на время переноса и вернулась");
        assert_eq!(d.moves_with_grid_on, 0, "после возврата сетки иконку не двигали — к клетке не притянется");
        let moved: Vec<(i32, i32)> = d.icon_moves.iter().map(|m| m.1).collect();
        assert!(moved.len() > 20 && max_step(&moved) < 25.0, "плавно: {} шагов, макс {}", moved.len(), max_step(&moved));
        let idx = d.icon_moves[0].0;
        let me = d.icons.iter().find(|i| i.index == idx).unwrap().rect;
        for o in d.icons.iter().filter(|i| i.index != idx) {
            assert!(!intersects(&me, &o.rect), "иконка не легла на другую");
        }
    }

    #[test]
    fn luna_walks_to_idle_cursor_sleeps_and_wakes() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(1));
        let mut cursor = (700, 450);
        let mut run = Run { t: STEP_SIZE };
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 19.0, false);
        assert!(!w.pony(id).unwrap().sleep, "ещё рано");
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 45.0, false);
        let p = w.pony(id).unwrap();
        assert!(p.sleep && p.destination_override.is_none(), "пришла и спит");
        let r = p.region();
        assert!(dist((r.x + r.w / 2, r.y + r.h / 2), cursor) < 120.0, "спит рядом с курсором: {:?} {:?}", r, cursor);
        assert!(p.facing_right(), "лицом к курсору");
        assert!(d.cursor_sets.is_empty(), "курсор не трогали — Луна пришла сама");
        cursor = (200, 200);
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 0.5, false);
        assert!(!w.pony(id).unwrap().sleep, "курсор сдвинули — проснулась");
    }

    #[test]
    fn sleeping_luna_pulls_cursor_to_herself() {
        let (mut w, id) = luna_world();
        w.pony_mut(id).unwrap().sleep = true;
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(2));
        let mut cursor = (1300, 150);
        let mut run = Run { t: STEP_SIZE };
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 26.0, false);
        assert!(d.cursor_sets.len() > 30, "курсор тянется плавно: {}", d.cursor_sets.len());
        assert!(max_step(&d.cursor_sets) < 30.0);
        let r = w.pony(id).unwrap().region();
        let last = *d.cursor_sets.last().unwrap();
        assert!(inflate(r, 10).contains_point(last.0, last.1), "курсор у Луны: {:?} {:?}", last, r);
        let n = d.cursor_sets.len();
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 40.0, false);
        assert_eq!(d.cursor_sets.len(), n, "повторно не тянет, пока курсор не сдвинут");
        assert!(w.pony(id).unwrap().sleep, "сон пользователя не прерывается");
    }

    /// Кадр с магией для глаз: `LUNA_SHEET=out.png cargo test --lib luna_fx_sheet -- --ignored`.
    #[test]
    #[ignore]
    fn luna_fx_sheet() {
        let Ok(out) = std::env::var("LUNA_SHEET") else { return };
        let (bw, bh) = (720usize, 420usize);
        let mut buf = vec![0xFF20_2430u32; bw * bh];
        let dir = concat!(env!("CARGO_MANIFEST_DIR"), "/Ponies/Princess Luna/");
        let mut luna = Luna::new(Some(9));
        for (k, (file, right, sleeping)) in
            [("luna-flight-right.gif", true, false), ("luna-flight-left.gif", false, false), ("luna_idle_right.gif", true, true)]
                .iter()
                .enumerate()
        {
            let a = crate::render::load_animation(&format!("{}{}", dir, file), 1.0).expect("gif");
            let (x, y) = (20 + k as i32 * 160, 250);
            crate::render::blit(&mut buf, bw, bh, &a.frames[0], a.w as usize, a.h as usize, x, y);
            let (fx, fy) = if *sleeping { (0.73, 0.22) } else { (0.71, 0.10) };
            let fx = if *right { fx } else { 1.0 - fx };
            let h = V2::new(x as f32 + a.w as f32 * fx, y as f32 + a.h as f32 * fy);
            draw_disc(&mut buf, bw, bh, h, 11.0, MAGIC, 0.9);
            draw_disc(&mut buf, bw, bh, h, 4.0, SPARK, 1.0);
        }
        luna.fx.glow = Some(Glow::Rect(RectI::new(260, 40, 400, 170), FILL_WINDOW));
        luna.fx.glow_want = 1.0;
        luna.fx.horn = Some(V2::new(122.0, 262.0));
        luna.fx.horn_want = 1.0;
        for _ in 0..60 {
            luna.fx.update(&mut luna.rng, 1.0 / 60.0);
        }
        luna.draw(&mut buf, bw, bh, (0, 0));
        let mut img = image::RgbaImage::new(bw as u32, bh as u32);
        for (i, p) in buf.iter().enumerate() {
            img.put_pixel((i % bw) as u32, (i / bw) as u32, image::Rgba([(p >> 16) as u8, (p >> 8) as u8, *p as u8, 255]));
        }
        img.save(out).unwrap();
    }

    /// Скорость заливки окна на весь экран: `cargo test --release --lib magic_fill_speed -- --ignored --nocapture`.
    #[test]
    #[ignore]
    fn magic_fill_speed() {
        let (bw, bh) = (1920usize, 1080usize);
        let mut buf = vec![0u32; bw * bh];
        // как в приложении: буфер оверлея очищается каждый кадр
        let t0 = std::time::Instant::now();
        for _ in 0..60 {
            buf.fill(0);
            std::hint::black_box(&buf);
        }
        let clear = t0.elapsed().as_secs_f64() * 1000.0 / 60.0;
        let t = std::time::Instant::now();
        for k in 0..60 {
            buf.fill(0);
            fill_rect_magic(&mut buf, bw, bh, RectI::new(0, 0, 1920, 1080), 1.0, k as f32 / 60.0, FILL_WINDOW);
            std::hint::black_box(&buf);
        }
        let total = t.elapsed().as_secs_f64() * 1000.0 / 60.0;
        println!("fill 1920x1080: {:.2} ms/кадр (без очистки {:.2} ms)", total - clear, clear);
    }

    #[test]
    fn user_moving_cursor_stops_the_pull() {
        let (mut w, id) = luna_world();
        w.pony_mut(id).unwrap().sleep = true;
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(4));
        let mut cursor = (1300, 150);
        let mut run = Run { t: STEP_SIZE };
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 21.0, false);
        assert!(!d.cursor_sets.is_empty());
        let n = d.cursor_sets.len();
        d.cursor_sets.clear();
        // Пользователь схватил мышь: позиция расходится с той, что поставила Луна.
        let mut input_cursor = (5, 5);
        for _ in 0..30 {
            let input = FrameInput { cursor: input_cursor, buttons: false, blocked: false, manual: &[], own_hwnds: &[] };
            luna.update(&mut w, &mut d, &input, &LunaSettings::default(), 1.0 / 60.0);
            input_cursor.0 += 3;
        }
        assert!(n > 0 && d.cursor_sets.is_empty(), "после вмешательства курсор больше не двигается");
        assert!(!luna.is_busy());
    }

    /// Вторая пони (не Луна) с отдельной анимацией «тащат мышью».
    fn add_other(w: &mut World, at: V2) -> PonyId {
        let mut base = PonyBase::new("Twilight Sparkle", PathBuf::new());
        let mut drag = beh("drag", 0.0, moves::DRAGGED);
        drag.chance = 0.0; // только когда тащат
        base.behaviors = vec![beh("stand", 0.0, moves::MOUSE_OVER), beh("walk", 3.0, moves::HORIZONTAL_ONLY), drag];
        w.add_pony_at(Rc::new(base), at)
    }

    fn drag_behavior(w: &World, id: PonyId) -> bool {
        w.pony(id).unwrap().current_behavior().name == "drag"
    }

    #[test]
    fn pony_is_carried_in_drag_state_and_put_down() {
        let (mut w, id) = luna_world();
        let other = add_other(&mut w, V2::new(650.0, 500.0));
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(4));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        let start = w.pony(other).unwrap().location();
        assert!(luna.cast(&mut w, &mut d, id, Spell::Pony, &[]));
        let mut carried_frames = 0;
        let mut path = Vec::new();
        for _ in 0..(12 * 60) {
            run.frames(&mut luna, &mut w, &mut d, &mut cursor, 1.0 / 60.0, false);
            let p = w.pony(other).unwrap();
            assert!(!p.is_dragging(), "это не перетаскивание мышью");
            if p.is_carried() {
                carried_frames += 1;
                assert!(drag_behavior(&w, other), "в магии пони в drag-анимации");
                let c = p.carry.unwrap();
                path.push((c.x.round() as i32, c.y.round() as i32));
            }
        }
        assert!(carried_frames > 30, "перенос идёт много кадров: {}", carried_frames);
        assert!(max_step(&path) < 25.0, "плавно: {}", max_step(&path));
        assert!(!luna.is_busy());
        let p = w.pony(other).unwrap();
        assert!(p.carry.is_none() && !p.is_carried() && !drag_behavior(&w, other), "поставили — пони свободна");
        assert!((p.location() - start).length() >= 60.0, "пони на новом месте");
        let r = p.region();
        let reg = w.ctx.region;
        assert!(r.x >= reg.x && r.right() <= reg.right() && r.y >= reg.y && r.bottom() <= reg.bottom(), "не за экраном");
        assert!(w.pony(id).unwrap().hold.is_none(), "Луна тоже свободна");
    }

    #[test]
    fn far_pony_is_brought_to_luna() {
        let (mut w, id) = luna_world();
        let other = add_other(&mut w, V2::new(1350.0, 300.0));
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(9));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        let luna_at = w.pony(id).unwrap().location();
        assert!(luna.cast(&mut w, &mut d, id, Spell::Pony, &[]));
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 0.3, false);
        assert!((w.pony(id).unwrap().location() - luna_at).length() < 20.0, "Луна не идёт к пони, а колдует с места");
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 8.0, false);
        let d_after = (w.pony(other).unwrap().location() - w.pony(id).unwrap().location()).length();
        assert!(d_after < 250.0, "пони принесли к Луне: {}", d_after);
    }

    #[test]
    fn user_grab_takes_pony_from_luna() {
        let (mut w, id) = luna_world();
        let other = add_other(&mut w, V2::new(650.0, 500.0));
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(4));
        let mut cursor = (10, 10);
        let mut run = Run { t: STEP_SIZE };
        assert!(luna.cast(&mut w, &mut d, id, Spell::Pony, &[]));
        // Луна подходит и поднимает пони
        for _ in 0..(10 * 60) {
            if w.pony(other).unwrap().is_carried() {
                break;
            }
            run.frames(&mut luna, &mut w, &mut d, &mut cursor, 1.0 / 60.0, false);
        }
        assert!(w.pony(other).unwrap().is_carried());
        // пользователь схватил её мышью (кнопку держит — как в app.rs)
        cursor = (900, 300);
        w.ctx.cursor = cursor;
        w.pony_mut(other).unwrap().drag = true;
        run.frames(&mut luna, &mut w, &mut d, &mut cursor, 0.5, true);
        assert!(!luna.is_busy(), "колдовство прервано");
        let p = w.pony(other).unwrap();
        assert!(p.carry.is_none() && p.is_dragging(), "пони осталась у пользователя");
        assert!((p.location() - V2::new(900.0, 300.0)).length() < 1.0, "и висит под курсором");
    }

    #[test]
    fn no_other_pony_no_cast() {
        let (mut w, id) = luna_world();
        let mut d = MockDesk::default();
        let mut luna = Luna::new(Some(4));
        assert!(!luna.cast(&mut w, &mut d, id, Spell::Pony, &[]));
        let other = add_other(&mut w, V2::new(650.0, 500.0));
        w.ctx.dragging_enabled = false;
        assert!(!luna.cast(&mut w, &mut d, id, Spell::Pony, &[]), "перетаскивание выключено — пони не трогаем");
        let _ = other;
    }
}
