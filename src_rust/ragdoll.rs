// src_rust/ragdoll.rs
//
// Кукольный скелет: спрайт пони режется на отдельные детали (голова, корпус,
// хвост из двух частей, передние и задние ноги). Каждая деталь привязана к
// двум точкам скелета; общие точки — суставы, поэтому детали "скреплены
// воедино". Схватив мышью любую деталь, вы тянете соответствующую точку, а
// остальное тело подтягивается по физике (Verlet + ограничения длины костей +
// слабые "мышцы", возвращающие части в естественную позу относительно корпуса).
// После отпускания пони плавно собирается обратно.
//
// В покое (все точки в исходных позициях) сборка деталей совпадает с исходным
// кадром попиксельно: детали не пересекаются, а "нахлёст" под соседей рисуется
// позади них и потому скрыт.

use crate::math::V2;

pub const NP: usize = 7;
// Индексы точек скелета.
const HIP: usize = 0;
const SHOULDER: usize = 1;
const HEAD: usize = 2;
const FHOOF: usize = 3;
const HHOOF: usize = 4;
const TMID: usize = 5;
const TTIP: usize = 6;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PartId {
    Tail2 = 0,
    Tail1 = 1,
    Hind = 2,
    Torso = 3,
    Front = 4,
    Head = 5,
}

const NPARTS: usize = 6;
/// Порядок отрисовки: ближайшее к зрителю — последним.
const DRAW_ORDER: [PartId; NPARTS] =
    [PartId::Tail2, PartId::Tail1, PartId::Hind, PartId::Torso, PartId::Front, PartId::Head];
/// Кость каждой детали: (начальная точка, конечная точка).
const BONES: [(usize, usize); NPARTS] = [
    (TMID, TTIP),     // Tail2
    (HIP, TMID),      // Tail1
    (HIP, HHOOF),     // Hind
    (HIP, SHOULDER),  // Torso
    (SHOULDER, FHOOF), // Front
    (SHOULDER, HEAD), // Head
];

#[derive(Clone, Copy, Debug)]
pub struct Ell {
    pub cx: f32,
    pub cy: f32,
    pub rx: f32,
    pub ry: f32,
}

#[derive(Clone, Copy, Debug)]
pub struct Rect {
    pub x0: f32,
    pub y0: f32,
    pub x1: f32,
    pub y1: f32,
}

/// Анатомия в долях рамки непрозрачных пикселей (для пони, смотрящей вправо).
#[derive(Clone, Copy, Debug)]
pub struct Anatomy {
    pub hip: (f32, f32),
    pub shoulder: (f32, f32),
    pub head_end: (f32, f32),
    pub front_hoof: (f32, f32),
    pub hind_hoof: (f32, f32),
    pub tail_mid: (f32, f32),
    pub tail_tip: (f32, f32),
    pub head: Ell,
    pub tail: Ell,
    pub front: Rect,
    pub hind: Rect,
}

impl Anatomy {
    pub fn default_pony() -> Anatomy {
        Anatomy {
            hip: (0.30, 0.48),
            shoulder: (0.66, 0.48),
            head_end: (0.88, 0.22),
            front_hoof: (0.68, 0.97),
            hind_hoof: (0.34, 0.97),
            tail_mid: (0.10, 0.58),
            tail_tip: (0.05, 0.88),
            head: Ell { cx: 0.80, cy: 0.27, rx: 0.24, ry: 0.36 },
            tail: Ell { cx: 0.09, cy: 0.50, rx: 0.19, ry: 0.46 },
            front: Rect { x0: 0.53, y0: 0.66, x1: 0.90, y1: 1.02 },
            hind: Rect { x0: 0.14, y0: 0.66, x1: 0.53, y1: 1.02 },
        }
    }
}

impl Anatomy {
    /// Зеркальное отражение (для картинок, где пони смотрит влево).
    pub fn mirrored(&self) -> Anatomy {
        let m = |p: (f32, f32)| (1.0 - p.0, p.1);
        let me = |e: Ell| Ell { cx: 1.0 - e.cx, ..e };
        let mr = |r: Rect| Rect { x0: 1.0 - r.x1, y0: r.y0, x1: 1.0 - r.x0, y1: r.y1 };
        Anatomy {
            hip: m(self.hip),
            shoulder: m(self.shoulder),
            head_end: m(self.head_end),
            front_hoof: m(self.front_hoof),
            hind_hoof: m(self.hind_hoof),
            tail_mid: m(self.tail_mid),
            tail_tip: m(self.tail_tip),
            head: me(self.head),
            tail: me(self.tail),
            front: mr(self.front),
            hind: mr(self.hind),
        }
    }
}

struct Bbox {
    x0: f32,
    y0: f32,
    w: f32,
    h: f32,
}

fn opaque_bbox(px: &[u32], w: usize, h: usize) -> Option<Bbox> {
    let (mut x0, mut y0, mut x1, mut y1) = (w, h, 0usize, 0usize);
    let mut any = false;
    for y in 0..h {
        for x in 0..w {
            if (px[y * w + x] >> 24) > 16 {
                any = true;
                x0 = x0.min(x);
                y0 = y0.min(y);
                x1 = x1.max(x);
                y1 = y1.max(y);
            }
        }
    }
    if !any || x1 <= x0 || y1 <= y0 {
        return None;
    }
    Some(Bbox { x0: x0 as f32, y0: y0 as f32, w: (x1 - x0 + 1) as f32, h: (y1 - y0 + 1) as f32 })
}

struct Part {
    /// Изображение детали (размер кадра), собственные пиксели + нахлёст.
    img: Vec<u32>,
    /// Рамка непрозрачных пикселей: x0, y0, x1, y1 (включительно).
    bb: (usize, usize, usize, usize),
}

pub struct Rig {
    w: usize,
    h: usize,
    parts: Vec<Part>,
    /// Какой детали принадлежит пиксель (для выбора при хвате мышью).
    owner: Vec<u8>,
    /// Исходные позиции точек в координатах кадра.
    rest: [V2; NP],
}

const NONE: u8 = 255;
const OVERLAP: i32 = 2;

impl Rig {
    pub fn build(px: &[u32], w: usize, h: usize, a: &Anatomy) -> Option<Rig> {
        let bb = opaque_bbox(px, w, h)?;
        let at = |f: (f32, f32)| V2::new(bb.x0 + f.0 * bb.w, bb.y0 + f.1 * bb.h);
        let rest = [
            at(a.hip),
            at(a.shoulder),
            at(a.head_end),
            at(a.front_hoof),
            at(a.hind_hoof),
            at(a.tail_mid),
            at(a.tail_tip),
        ];
        // --- разметка пикселей по деталям
        let mut owner = vec![NONE; w * h];
        let root = rest[HIP];
        let axis = rest[TTIP] - rest[HIP];
        let axis_len2 = (axis.x * axis.x + axis.y * axis.y).max(1.0);
        for y in 0..h {
            for x in 0..w {
                let p = px[y * w + x];
                if (p >> 24) <= 16 {
                    continue;
                }
                let fx = (x as f32 + 0.5 - bb.x0) / bb.w;
                let fy = (y as f32 + 0.5 - bb.y0) / bb.h;
                let in_ell = |e: &Ell| {
                    let dx = (fx - e.cx) / e.rx;
                    let dy = (fy - e.cy) / e.ry;
                    dx * dx + dy * dy <= 1.0
                };
                let in_rect = |r: &Rect| fx >= r.x0 && fx <= r.x1 && fy >= r.y0 && fy <= r.y1;
                let part = if in_ell(&a.head) {
                    PartId::Head
                } else if in_ell(&a.tail) {
                    // хвост делится вдоль своей оси
                    let d = V2::new(x as f32 + 0.5, y as f32 + 0.5) - root;
                    let t = (d.x * axis.x + d.y * axis.y) / axis_len2;
                    if t > 0.5 { PartId::Tail2 } else { PartId::Tail1 }
                } else if in_rect(&a.front) {
                    PartId::Front
                } else if in_rect(&a.hind) {
                    PartId::Hind
                } else {
                    PartId::Torso
                };
                owner[y * w + x] = part as u8;
            }
        }
        // --- изображения деталей: собственные пиксели + нахлёст (кроме корпуса)
        let mut parts: Vec<Part> = Vec::new();
        for pid in 0..NPARTS {
            let mut img = vec![0u32; w * h];
            let mut minx = w;
            let mut miny = h;
            let mut maxx = 0usize;
            let mut maxy = 0usize;
            for y in 0..h {
                for x in 0..w {
                    let i = y * w + x;
                    let mut take = owner[i] == pid as u8;
                    if !take && pid != PartId::Torso as usize && (px[i] >> 24) > 0 && owner[i] != NONE {
                        // нахлёст: пиксель соседа рядом с собственными пикселями детали
                        'n: for dy in -OVERLAP..=OVERLAP {
                            for dx in -OVERLAP..=OVERLAP {
                                let (nx, ny) = (x as i32 + dx, y as i32 + dy);
                                if nx >= 0 && ny >= 0 && (nx as usize) < w && (ny as usize) < h && owner[ny as usize * w + nx as usize] == pid as u8 {
                                    take = true;
                                    break 'n;
                                }
                            }
                        }
                    }
                    if take {
                        img[i] = px[i];
                        minx = minx.min(x);
                        miny = miny.min(y);
                        maxx = maxx.max(x);
                        maxy = maxy.max(y);
                    }
                }
            }
            let bbp = if maxx >= minx { (minx, miny, maxx, maxy) } else { (0, 0, 0, 0) };
            parts.push(Part { img, bb: bbp });
        }
        Some(Rig { w, h, parts, owner, rest })
    }

    pub fn part_at(&self, x: i32, y: i32) -> Option<PartId> {
        if x < 0 || y < 0 || x as usize >= self.w || y as usize >= self.h {
            return None;
        }
        match self.owner[y as usize * self.w + x as usize] {
            0 => Some(PartId::Tail2),
            1 => Some(PartId::Tail1),
            2 => Some(PartId::Hind),
            3 => Some(PartId::Torso),
            4 => Some(PartId::Front),
            5 => Some(PartId::Head),
            _ => None,
        }
    }

    pub fn rest_points(&self) -> [V2; NP] {
        self.rest
    }
}

// ------------------------------------------------------------------ физика

#[derive(Clone, Copy, Debug)]
struct Grab {
    pt: usize,
    offset: V2,
}

pub struct Ragdoll {
    rig: Rig,
    pts: [V2; NP],
    prev: [V2; NP],
    rest_len: [f32; NPARTS],
    grab: Option<Grab>,
    /// Экранная позиция левого верхнего угла кадра в состоянии покоя.
    home: V2,
    pub released: bool,
    pub done: bool,
    settle_t: f32,
}

fn ang(v: V2) -> f32 {
    v.y.atan2(v.x)
}

fn rot(v: V2, a: f32) -> V2 {
    let (s, c) = a.sin_cos();
    V2::new(v.x * c - v.y * s, v.x * s + v.y * c)
}

impl Ragdoll {
    /// px — кадр (premult ARGB) размера w x h; origin — экранная позиция его
    /// левого верхнего угла.
    pub fn new(px: &[u32], w: usize, h: usize, anatomy: &Anatomy, origin: V2) -> Option<Ragdoll> {
        let rig = Rig::build(px, w, h, anatomy)?;
        let rp = rig.rest_points();
        let mut pts = [V2::ZERO; NP];
        for i in 0..NP {
            pts[i] = origin + rp[i];
        }
        let mut rest_len = [0.0; NPARTS];
        for (k, (a, b)) in BONES.iter().enumerate() {
            rest_len[k] = (rp[*b] - rp[*a]).length().max(1.0);
        }
        Some(Ragdoll { rig, prev: pts, pts, rest_len, grab: None, home: origin, released: false, done: false, settle_t: 0.0 })
    }

    pub fn part_at(&self, fx: i32, fy: i32) -> Option<PartId> {
        self.rig.part_at(fx, fy)
    }

    /// Хватаем деталь в точке кадра (fx, fy); cursor — положение курсора на экране.
    pub fn grab(&mut self, part: PartId, fx: f32, fy: f32, cursor: V2) {
        let (a, b) = BONES[part as usize];
        let rest = self.rig.rest;
        // ближайшая из двух точек кости (к хватаемому пикселю)
        let g = V2::new(fx, fy);
        let da = V2::dist_sq(rest[a], g);
        let db = V2::dist_sq(rest[b], g);
        let pt = if da <= db { a } else { b };
        // Смещение сохраняем так, чтобы схваченный пиксель остался под курсором.
        self.grab = Some(Grab { pt, offset: self.pts[pt] - cursor });
        self.released = false;
        self.done = false;
    }

    pub fn release(&mut self) {
        self.grab = None;
        self.released = true;
        self.settle_t = 0.0;
    }

    pub fn is_grabbed(&self) -> bool {
        self.grab.is_some()
    }

    /// Куда должен переместиться "дом" пони (позиция кадра в покое).
    pub fn set_home(&mut self, origin: V2) {
        self.home = origin;
    }

    fn torso_transform(&self) -> (V2, f32, f32) {
        let rest = self.rig.rest;
        let cur = self.pts[SHOULDER] - self.pts[HIP];
        let r = rest[SHOULDER] - rest[HIP];
        let s = (cur.length() / r.length().max(1.0)).clamp(0.5, 2.0);
        (self.pts[HIP], ang(cur) - ang(r), s)
    }

    /// Экранная позиция левого верхнего угла кадра с учётом положения корпуса.
    pub fn origin_now(&self) -> V2 {
        let (hip, d, s) = self.torso_transform();
        hip + rot(V2::ZERO - self.rig.rest[HIP], d) * s
    }

    pub fn update(&mut self, dt: f32, cursor: V2) {
        let dt = dt.clamp(0.0, 0.05);
        if dt == 0.0 || self.done {
            return;
        }
        const SUB: usize = 4;
        let h = dt / SUB as f32;
        let dragging = self.grab.is_some();
        let relax = self.released;
        let gravity = if dragging { 1500.0 } else { 0.0 };
        let (k_muscle, k_torso_home) = if relax { (0.30, 0.20) } else { (0.10, 0.0) };
        for _ in 0..SUB {
            // интегрирование
            for i in 0..NP {
                let v = (self.pts[i] - self.prev[i]) * 0.985;
                self.prev[i] = self.pts[i];
                self.pts[i] = self.pts[i] + v + V2::new(0.0, gravity * h * h);
            }
            // схваченная точка
            if let Some(g) = self.grab {
                self.pts[g.pt] = cursor + g.offset;
                self.prev[g.pt] = self.pts[g.pt];
            }
            // возврат домой после отпускания
            if relax {
                let rest = self.rig.rest;
                for i in 0..NP {
                    let target = self.home + rest[i];
                    self.pts[i] = self.pts[i] + (target - self.pts[i]) * k_torso_home;
                }
            }
            // "мышцы": направление кости относительно корпуса стремится к исходному
            let rest = self.rig.rest;
            let torso_d = ang(self.pts[SHOULDER] - self.pts[HIP]) - ang(rest[SHOULDER] - rest[HIP]);
            for (k, (a, b)) in BONES.iter().enumerate() {
                if k == PartId::Torso as usize {
                    continue;
                }
                let (a, b) = (*a, *b);
                let rv = rest[b] - rest[a];
                // хвост слабее, голова и ноги сильнее
                let stiff = match k {
                    x if x == PartId::Head as usize => k_muscle * 1.2,
                    x if x == PartId::Front as usize || x == PartId::Hind as usize => k_muscle,
                    _ => k_muscle * 0.35,
                };
                let target = self.pts[a] + rot(rv, torso_d);
                let pinned_b = self.grab.map(|g| g.pt == b).unwrap_or(false);
                if !pinned_b {
                    self.pts[b] = self.pts[b] + (target - self.pts[b]) * stiff;
                }
            }
            // ограничения длины костей
            for _ in 0..5 {
                for (k, (a, b)) in BONES.iter().enumerate() {
                    let (a, b) = (*a, *b);
                    let d = self.pts[b] - self.pts[a];
                    let len = d.length().max(1e-4);
                    let diff = (len - self.rest_len[k]) / len;
                    let pa = self.grab.map(|g| g.pt == a).unwrap_or(false);
                    let pb = self.grab.map(|g| g.pt == b).unwrap_or(false);
                    let (wa, wb) = match (pa, pb) {
                        (true, true) => (0.0, 0.0),
                        (true, false) => (0.0, 1.0),
                        (false, true) => (1.0, 0.0),
                        (false, false) => (0.5, 0.5),
                    };
                    self.pts[a] = self.pts[a] + d * (diff * wa);
                    self.pts[b] = self.pts[b] - d * (diff * wb);
                }
            }
            if let Some(g) = self.grab {
                self.pts[g.pt] = cursor + g.offset;
            }
        }
        if relax {
            self.settle_t += dt;
            let rest = self.rig.rest;
            let mut err = 0.0f32;
            let mut vel = 0.0f32;
            for i in 0..NP {
                err = err.max((self.pts[i] - (self.home + rest[i])).length());
                vel = vel.max((self.pts[i] - self.prev[i]).length());
            }
            if (err < 0.6 && vel < 0.4) || self.settle_t > 2.5 {
                self.done = true;
            }
        }
    }

    /// Собирает кадр из деталей. Возвращает (пиксели, x, y, w, h) — прямоугольник
    /// в экранных координатах.
    pub fn render(&self) -> (Vec<u32>, i32, i32, usize, usize) {
        let rest = self.rig.rest;
        // экранный bbox всех деталей
        struct Tf {
            a0: V2,
            a: V2,
            d: f32,
            s: f32,
        }
        let mut tfs: Vec<Tf> = Vec::new();
        for (a, b) in BONES.iter() {
            let rv = rest[*b] - rest[*a];
            let cv = self.pts[*b] - self.pts[*a];
            let s = (cv.length() / rv.length().max(1.0)).clamp(0.7, 1.6);
            tfs.push(Tf { a0: rest[*a], a: self.pts[*a], d: ang(cv) - ang(rv), s });
        }
        let map = |t: &Tf, p: V2| t.a + rot(p - t.a0, t.d) * t.s;
        let (mut minx, mut miny, mut maxx, mut maxy) = (f32::MAX, f32::MAX, f32::MIN, f32::MIN);
        for (pid, p) in self.rig.parts.iter().enumerate() {
            let (x0, y0, x1, y1) = p.bb;
            for c in [(x0 as f32, y0 as f32), (x1 as f32 + 1.0, y0 as f32), (x0 as f32, y1 as f32 + 1.0), (x1 as f32 + 1.0, y1 as f32 + 1.0)] {
                let q = map(&tfs[pid], V2::new(c.0, c.1));
                minx = minx.min(q.x);
                miny = miny.min(q.y);
                maxx = maxx.max(q.x);
                maxy = maxy.max(q.y);
            }
        }
        let ox = minx.floor() as i32 - 1;
        let oy = miny.floor() as i32 - 1;
        let cw = ((maxx.ceil() as i32 + 1 - ox).max(1)) as usize;
        let ch = ((maxy.ceil() as i32 + 1 - oy).max(1)) as usize;
        let mut canvas = vec![0u32; cw * ch];
        const SS: usize = 2;
        for pid in DRAW_ORDER {
            let part = &self.rig.parts[pid as usize];
            let t = &tfs[pid as usize];
            // экранный bbox детали
            let (x0, y0, x1, y1) = part.bb;
            let mut bx0 = f32::MAX;
            let mut by0 = f32::MAX;
            let mut bx1 = f32::MIN;
            let mut by1 = f32::MIN;
            for c in [(x0 as f32, y0 as f32), (x1 as f32 + 1.0, y0 as f32), (x0 as f32, y1 as f32 + 1.0), (x1 as f32 + 1.0, y1 as f32 + 1.0)] {
                let q = map(t, V2::new(c.0, c.1));
                bx0 = bx0.min(q.x);
                by0 = by0.min(q.y);
                bx1 = bx1.max(q.x);
                by1 = by1.max(q.y);
            }
            let sx0 = (bx0.floor() as i32).max(ox);
            let sy0 = (by0.floor() as i32).max(oy);
            let sx1 = (bx1.ceil() as i32).min(ox + cw as i32);
            let sy1 = (by1.ceil() as i32).min(oy + ch as i32);
            let inv_s = 1.0 / t.s;
            for sy in sy0..sy1 {
                for sx in sx0..sx1 {
                    let (mut aa, mut rr, mut gg, mut bb) = (0u32, 0u32, 0u32, 0u32);
                    for j in 0..SS {
                        for i in 0..SS {
                            let sp = V2::new(sx as f32 + (i as f32 + 0.5) / SS as f32, sy as f32 + (j as f32 + 0.5) / SS as f32);
                            let local = t.a0 + rot(sp - t.a, -t.d) * inv_s;
                            let (ix, iy) = (local.x.floor() as i32, local.y.floor() as i32);
                            if ix >= 0 && iy >= 0 && (ix as usize) < self.rig.w && (iy as usize) < self.rig.h {
                                let p = part.img[iy as usize * self.rig.w + ix as usize];
                                aa += p >> 24;
                                rr += (p >> 16) & 0xFF;
                                gg += (p >> 8) & 0xFF;
                                bb += p & 0xFF;
                            }
                        }
                    }
                    if aa == 0 {
                        continue;
                    }
                    let n = (SS * SS) as u32;
                    let src = ((aa / n) << 24) | ((rr / n) << 16) | ((gg / n) << 8) | (bb / n);
                    let idx = (sy - oy) as usize * cw + (sx - ox) as usize;
                    canvas[idx] = over(canvas[idx], src);
                }
            }
        }
        (canvas, ox, oy, cw, ch)
    }
}

/// Композиция "src над dst" для предумноженной альфы.
fn over(dst: u32, src: u32) -> u32 {
    let sa = src >> 24;
    if sa == 255 {
        return src;
    }
    if sa == 0 {
        return dst;
    }
    let inv = 255 - sa;
    let mix = |s: u32, d: u32| (s + (d * inv + 127) / 255).min(255);
    (mix(sa, dst >> 24) << 24)
        | (mix((src >> 16) & 0xFF, (dst >> 16) & 0xFF) << 16)
        | (mix((src >> 8) & 0xFF, (dst >> 8) & 0xFF) << 8)
        | mix(src & 0xFF, dst & 0xFF)
}

// ------------------------------------------------------------------ tests

#[cfg(test)]
mod tests {
    use super::*;
    use crate::render::load_animation;
    use std::path::PathBuf;

    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
    }

    fn frame(dir: &str, file: &str) -> (Vec<u32>, usize, usize) {
        let p = root().join("Ponies").join(dir).join(file);
        let a = load_animation(p.to_str().unwrap(), 1.0).expect("gif");
        (a.frames[0].pixels.clone(), a.w as usize, a.h as usize)
    }

    #[test]
    fn rest_assembly_equals_original_frame() {
        for (dir, file) in [("Applejack", "stand_aj_right.gif"), ("Twilight Sparkle", "stand_twilight_right.gif"), ("Princess Celestia", "stand_right.gif")] {
            let (px, w, h) = frame(dir, file);
            let rd = Ragdoll::new(&px, w, h, &Anatomy::default_pony(), V2::new(100.0, 50.0)).unwrap();
            let (canvas, ox, oy, cw, _) = rd.render();
            for y in 0..h {
                for x in 0..w {
                    let (cx, cy) = (100 + x as i32 - ox, 50 + y as i32 - oy);
                    let got = if cx >= 0 && cy >= 0 && (cx as usize) < cw && (cy as usize) * cw + (cx as usize) < canvas.len() {
                        canvas[cy as usize * cw + cx as usize]
                    } else {
                        0
                    };
                    let want = if (px[y * w + x] >> 24) > 0 { px[y * w + x] } else { 0 };
                    assert_eq!(got & 0xFF00_0000 != 0, want & 0xFF00_0000 != 0, "{} coverage at ({},{})", dir, x, y);
                    if want != 0 {
                        assert_eq!(got, want, "{} pixel ({},{}) differs at rest", dir, x, y);
                    }
                }
            }
        }
    }

    #[test]
    fn dragging_head_pulls_the_body_and_keeps_bones_intact() {
        let (px, w, h) = frame("Applejack", "stand_aj_right.gif");
        let mut rd = Ragdoll::new(&px, w, h, &Anatomy::default_pony(), V2::new(300.0, 300.0)).unwrap();
        let head_rest = rd.rig.rest[HEAD];
        let part = rd.part_at((head_rest.x - 4.0) as i32, (head_rest.y + 4.0) as i32).unwrap_or(PartId::Head);
        rd.grab(part, head_rest.x, head_rest.y, V2::new(300.0, 300.0) + head_rest);
        // тянем курсор вверх и вправо на 150 px
        let start_hip = rd.pts[HIP];
        for i in 0..120 {
            let f = (i as f32 / 60.0).min(1.0);
            rd.update(0.016, V2::new(300.0, 300.0) + head_rest + V2::new(120.0 * f, -150.0 * f));
        }
        assert!(rd.pts[HIP].y < start_hip.y - 40.0, "body must be lifted: {:?} -> {:?}", start_hip, rd.pts[HIP]);
        assert!(rd.pts[HIP].x > start_hip.x + 40.0, "body follows horizontally");
        // длины костей сохраняются
        for (k, (a, b)) in BONES.iter().enumerate() {
            let l = (rd.pts[*b] - rd.pts[*a]).length();
            assert!((l - rd.rest_len[k]).abs() < rd.rest_len[k] * 0.08, "bone {} length {} vs {}", k, l, rd.rest_len[k]);
        }
        // после отпускания собирается обратно
        rd.release();
        rd.set_home(V2::new(500.0, 400.0));
        for _ in 0..400 {
            rd.update(0.016, V2::ZERO);
            if rd.done {
                break;
            }
        }
        assert!(rd.done, "ragdoll must settle after release");
        let expected = V2::new(500.0, 400.0) + rd.rig.rest[HIP];
        assert!((rd.pts[HIP] - expected).length() < 1.5, "returns home");
    }

    /// Лист для подбора разреза: SKEL_SHEET=out.png cargo test --lib ragdoll_debug_sheet -- --ignored
    #[test]
    #[ignore]
    fn ragdoll_debug_sheet() {
        let out_path = std::env::var("SKEL_SHEET").unwrap_or_else(|_| "ragdoll_sheet.png".into());
        let files: Vec<(String, String)> = std::env::var("SKEL_FILES")
            .unwrap_or_else(|_| "Twilight Sparkle:stand_twilight_right.gif;Applejack:stand_aj_right.gif".into())
            .split(';')
            .filter_map(|e| e.split_once(':').map(|(a, b)| (a.to_string(), b.to_string())))
            .collect();
        let scale: usize = std::env::var("SKEL_SCALE").ok().and_then(|s| s.parse().ok()).unwrap_or(2);
        let cell_w: usize = std::env::var("SKEL_CELLW").ok().and_then(|s| s.parse().ok()).unwrap_or(330);
        let cell_h: usize = std::env::var("SKEL_CELLH").ok().and_then(|s| s.parse().ok()).unwrap_or(330);
        let coll = crate::loader::PonyCollection::load(&root(), true);
        let mut sheet = image::RgbaImage::from_pixel((cell_w * 4) as u32, (cell_h * files.len()) as u32, image::Rgba([60, 60, 70, 255]));
        let tints: [[u8; 3]; NPARTS] = [[80, 200, 255], [80, 255, 120], [255, 200, 60], [255, 90, 200], [255, 140, 60], [255, 70, 70]];
        for (row, (dir, file)) in files.iter().enumerate() {
            let path = if file.is_empty() {
                coll.base_by_directory(dir).unwrap().behaviors.iter().find(|b| b.name.to_lowercase().contains("stand") && !b.right_image.path.is_empty()).map(|b| b.right_image.path.clone()).unwrap()
            } else {
                root().join("Ponies").join(dir).join(file).to_string_lossy().to_string()
            };
            let a = load_animation(&path, 1.0).unwrap();
            let (px, w, h) = (a.frames[0].pixels.clone(), a.w as usize, a.h as usize);
            let anat = Anatomy::default_pony();
            let origin = V2::new(70.0, 150.0);
            let rig = Rig::build(&px, w, h, &anat).unwrap();
            let put = |sheet: &mut image::RgbaImage, col: usize, x: i32, y: i32, rgb: [u8; 3], al: f32| {
                for dy in 0..scale as i32 {
                    for dx in 0..scale as i32 {
                        let (tx, ty) = ((x * scale as i32 + dx), (y * scale as i32 + dy));
                        if tx >= 0 && ty >= 0 && (tx as usize) < cell_w && (ty as usize) < cell_h {
                            let p = sheet.get_pixel_mut((col * cell_w) as u32 + tx as u32, (row * cell_h) as u32 + ty as u32);
                            for c in 0..3 {
                                p.0[c] = (rgb[c] as f32 * al + p.0[c] as f32 * (1.0 - al)) as u8;
                            }
                        }
                    }
                }
            };
            // колонка 0: части, окрашенные по деталям + точки скелета
            for y in 0..h {
                for x in 0..w {
                    let o = rig.owner[y * w + x];
                    if o != NONE {
                        put(&mut sheet, 0, 40 + x as i32, 40 + y as i32, tints[o as usize], 1.0);
                    }
                }
            }
            for (i, p) in rig.rest.iter().enumerate() {
                let c = if i == HIP || i == SHOULDER { [255, 255, 255] } else { [0, 0, 0] };
                for d in -1..=1 {
                    put(&mut sheet, 0, 40 + p.x as i32 + d, 40 + p.y as i32, c, 1.0);
                    put(&mut sheet, 0, 40 + p.x as i32, 40 + p.y as i32 + d, c, 1.0);
                }
            }
            // колонки 1..3: за голову, за копыто, за хвост
            let scenarios: [(usize, V2, &str); 3] = [(HEAD, V2::new(110.0, -60.0), "head"), (FHOOF, V2::new(40.0, -70.0), "hoof"), (TTIP, V2::new(-70.0, -50.0), "tail")];
            for (k, (pt, delta, _)) in scenarios.iter().enumerate() {
                let mut rd = Ragdoll::new(&px, w, h, &anat, origin).unwrap();
                let part = match *pt { HEAD => PartId::Head, FHOOF => PartId::Front, _ => PartId::Tail2 };
                let rp = rd.rig.rest[*pt];
                rd.grab(part, rp.x, rp.y, origin + rp);
                for i in 0..150 {
                    let f = (i as f32 / 70.0).min(1.0);
                    rd.update(0.016, origin + rp + *delta * f);
                }
                let (canvas, ox, oy, cw, ch) = rd.render();
                // центрируем результат в ячейке
                let shift_x = (cell_w / scale) as i32 / 2 - (ox + cw as i32 / 2);
                let shift_y = (cell_h / scale) as i32 / 2 - (oy + ch as i32 / 2);
                let (ox, oy) = (ox + shift_x, oy + shift_y);
                for y in 0..ch {
                    for x in 0..cw {
                        let p = canvas[y * cw + x];
                        let al = (p >> 24) as f32 / 255.0;
                        if al > 0.0 {
                            let un = |c: u32| ((c as f32) / al).min(255.0) as u8;
                            put(&mut sheet, k + 1, ox + x as i32, oy + y as i32, [un((p >> 16) & 0xFF), un((p >> 8) & 0xFF), un(p & 0xFF)], al);
                        }
                    }
                }
                // курсор
                for d in -3..=3 {
                    let c = origin + rp + *delta + V2::new(shift_x as f32, shift_y as f32);
                    put(&mut sheet, k + 1, c.x as i32 + d, c.y as i32, [255, 255, 0], 1.0);
                    put(&mut sheet, k + 1, c.x as i32, c.y as i32 + d, [255, 255, 0], 1.0);
                }
            }
        }
        sheet.save(&out_path).unwrap();
    }
}
