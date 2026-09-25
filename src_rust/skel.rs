// src_rust/skel.rs
//
// Скелетная анимация поверх готовых GIF-ов пони.
//
// Ноги и общий цикл шага рисуют сами GIF-ы (это работа художников, и она
// лучше любой процедурной ходьбы). Скелет добавляет то, чего в GIF нет:
//   * голова с гривой поворачивается за курсором / направлением движения;
//   * хвост (две кости: основание и кончик) и грива живут по физике —
//     пружины реагируют на разгон, торможение, перетаскивание;
//   * корпус слегка наклоняется в сторону ускорения и «дышит».
//
// Деформация — обратное отображение с мягкими весами костей (эллиптические
// маски с плавным краем), с 3-кратной передискретизацией и усреднением: пиксель-
// арт при повороте не рассыпается на «лесенку». В покое (все углы ≈ 0)
// результат в точности совпадает с исходным кадром.

use std::collections::HashMap;

pub const PAD: usize = 8;
const SS: usize = 3; // передискретизация

#[derive(Clone, Copy, Debug)]
pub struct Ell {
    pub cx: f32,
    pub cy: f32,
    pub rx: f32,
    pub ry: f32,
}

/// Описание скелета в долях рамки непрозрачных пикселей кадра (для пони,
/// смотрящей вправо; для левой картинки кадр отражается).
#[derive(Clone, Copy, Debug)]
pub struct RigSpec {
    pub head: Ell,
    pub head_pivot: (f32, f32),
    pub tail: Ell,
    pub tail_pivot: (f32, f32),
    pub tip: Ell,
    pub tip_pivot: (f32, f32),
    /// Точка опоры (между копытами): вокруг неё наклоняется корпус.
    pub foot: (f32, f32),
    /// Множители амплитуды.
    pub head_gain: f32,
    pub tail_gain: f32,
    /// Скелет применяется только к gif-файлам, в имени которых есть одна из
    /// подстрок (пусто — к любым подходящим по имени поведения).
    pub files: &'static [&'static str],
}

impl RigSpec {
    pub fn default_pony() -> RigSpec {
        RigSpec {
            head: Ell { cx: 0.80, cy: 0.28, rx: 0.22, ry: 0.32 },
            head_pivot: (0.66, 0.42),
            tail: Ell { cx: 0.10, cy: 0.42, rx: 0.16, ry: 0.36 },
            tail_pivot: (0.22, 0.30),
            tip: Ell { cx: 0.05, cy: 0.62, rx: 0.10, ry: 0.30 },
            tip_pivot: (0.10, 0.45),
            foot: (0.5, 1.0),
            head_gain: 1.0,
            tail_gain: 1.0,
            files: &[],
        }
    }

    /// Можно ли применить скелет к этому поведению и файлу картинки.
    pub fn allows(&self, behavior: &str, file: &str) -> bool {
        if !behavior_allows_rig(behavior) {
            return false;
        }
        if self.files.is_empty() {
            return true;
        }
        let f = file.to_lowercase();
        self.files.iter().any(|s| f.contains(s))
    }
}

/// Скелет для конкретной пони (по имени каталога). None — без скелета.
pub fn rig_for(directory: &str) -> Option<RigSpec> {
    let d = directory.to_lowercase();
    let mut s = RigSpec::default_pony();
    match d.as_str() {
        "twilight sparkle" | "applejack" | "rainbow dash" | "pinkie pie" | "rarity" | "fluttershy" => {}
        // Огромные гривы: амплитуда в пикселях и так велика (спрайт 192x140).
        "princess celestia" => {
            s.head_gain = 0.7;
            s.tail_gain = 0.9;
            s.files = &["stand", "walk", "fly"];
        }
        // Стоячая поза Луны в ini — свёрнутая спящая: скелет только для ходьбы и полёта.
        "princess luna" => {
            s.head_gain = 0.75;
            s.tail_gain = 0.9;
            s.files = &["walk", "flight"];
        }
        _ => return None,
    }
    Some(s)
}

/// Подходит ли поведение для скелета (боковая поза стоя/шага/полёта).
pub fn behavior_allows_rig(name: &str) -> bool {
    let n = name.to_lowercase();
    const YES: [&str; 8] = ["stand", "walk", "trot", "gallop", "run", "idle", "fly", "hover"];
    const NO: [&str; 22] = [
        "sit", "sleep", "lay", "lie", "rear", "dance", "read", "eat", "drink", "fall", "tumble", "boop", "magic",
        "cast", "nap", "cry", "hug", "kiss", "bow", "drag", "swim", "party",
    ];
    YES.iter().any(|y| n.contains(y)) && !NO.iter().any(|x| n.contains(x))
}

// ------------------------------------------------------------------ affine

#[derive(Clone, Copy, Debug)]
struct Aff {
    a: f32,
    b: f32,
    tx: f32,
    c: f32,
    d: f32,
    ty: f32,
}

impl Aff {
    const ID: Aff = Aff { a: 1.0, b: 0.0, tx: 0.0, c: 0.0, d: 1.0, ty: 0.0 };

    fn rot_about(deg: f32, px: f32, py: f32) -> Aff {
        let (s, c) = deg.to_radians().sin_cos();
        Aff { a: c, b: -s, tx: px - c * px + s * py, c: s, d: c, ty: py - s * px - c * py }
    }
    fn apply(&self, x: f32, y: f32) -> (f32, f32) {
        (self.a * x + self.b * y + self.tx, self.c * x + self.d * y + self.ty)
    }
    /// self ∘ other (сначала other, затем self).
    fn compose(&self, o: &Aff) -> Aff {
        Aff {
            a: self.a * o.a + self.b * o.c,
            b: self.a * o.b + self.b * o.d,
            tx: self.a * o.tx + self.b * o.ty + self.tx,
            c: self.c * o.a + self.d * o.c,
            d: self.c * o.b + self.d * o.d,
            ty: self.c * o.tx + self.d * o.ty + self.ty,
        }
    }
    fn inverse(&self) -> Aff {
        let det = self.a * self.d - self.b * self.c;
        let det = if det.abs() < 1e-6 { 1e-6 } else { det };
        let (ia, ib, ic, id) = (self.d / det, -self.b / det, -self.c / det, self.a / det);
        Aff { a: ia, b: ib, tx: -(ia * self.tx + ib * self.ty), c: ic, d: id, ty: -(ic * self.tx + id * self.ty) }
    }
}

fn smooth(t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Вес эллиптической маски: 1 внутри ядра, плавно до 0 к краю.
fn ell_weight(e: &Ell, x: f32, y: f32) -> f32 {
    let dx = (x - e.cx) / e.rx;
    let dy = (y - e.cy) / e.ry;
    let d = (dx * dx + dy * dy).sqrt();
    1.0 - smooth((d - 0.55) / 0.45)
}

// ------------------------------------------------------------------ pose

#[derive(Clone, Copy, Debug, Default)]
pub struct Pose {
    /// Углы в градусах (по часовой стрелке > 0, ось Y вниз).
    pub head: f32,
    pub tail: f32,
    pub tip: f32,
    pub root_rot: f32,
    /// Смещение корпуса по вертикали, пикселей (вниз > 0).
    pub bob: f32,
    /// Масштаб по вертикали относительно опоры (1.0 = без изменений).
    pub squash: f32,
}

impl Pose {
    pub fn rest() -> Pose {
        Pose { squash: 1.0, ..Default::default() }
    }
    fn is_rest(&self) -> bool {
        self.head.abs() < 0.05
            && self.tail.abs() < 0.05
            && self.tip.abs() < 0.05
            && self.root_rot.abs() < 0.05
            && self.bob.abs() < 0.05
            && (self.squash - 1.0).abs() < 0.001
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

fn abs_ell(e: &Ell, b: &Bbox) -> Ell {
    Ell { cx: b.x0 + e.cx * b.w, cy: b.y0 + e.cy * b.h, rx: e.rx * b.w, ry: e.ry * b.h }
}

/// Деформирует кадр (ARGB с предумноженной альфой). Возвращает кадр размера
/// (w + 2*PAD) x (h + 2*PAD) — запас под размах хвоста и головы.
pub fn deform(src: &[u32], w: usize, h: usize, spec: &RigSpec, pose: &Pose, flip: bool) -> Option<(Vec<u32>, usize, usize)> {
    let (ow, oh) = (w + 2 * PAD, h + 2 * PAD);
    let mut work: Vec<u32>;
    let src: &[u32] = if flip {
        work = vec![0; w * h];
        for y in 0..h {
            for x in 0..w {
                work[y * w + x] = src[y * w + (w - 1 - x)];
            }
        }
        &work
    } else {
        src
    };

    let mut out = vec![0u32; ow * oh];
    let bb = opaque_bbox(src, w, h)?;
    if pose.is_rest() {
        for y in 0..h {
            for x in 0..w {
                out[(y + PAD) * ow + x + PAD] = src[y * w + x];
            }
        }
        return Some((if flip { flip_x(&out, ow, oh) } else { out }, ow, oh));
    }

    let head = abs_ell(&spec.head, &bb);
    let tail = abs_ell(&spec.tail, &bb);
    let tip = abs_ell(&spec.tip, &bb);
    let hp = (bb.x0 + spec.head_pivot.0 * bb.w, bb.y0 + spec.head_pivot.1 * bb.h);
    let tp = (bb.x0 + spec.tail_pivot.0 * bb.w, bb.y0 + spec.tail_pivot.1 * bb.h);
    let ip = (bb.x0 + spec.tip_pivot.0 * bb.w, bb.y0 + spec.tip_pivot.1 * bb.h);
    let foot = (bb.x0 + spec.foot.0 * bb.w, bb.y0 + spec.foot.1 * bb.h);

    // Корневое преобразование: наклон вокруг опоры, масштаб по Y, смещение.
    let root_rot = Aff::rot_about(pose.root_rot, foot.0, foot.1);
    let scale = Aff { a: 1.0, b: 0.0, tx: 0.0, c: 0.0, d: pose.squash, ty: foot.1 * (1.0 - pose.squash) };
    let shift = Aff { tx: 0.0, ty: pose.bob, ..Aff::ID };
    let root = shift.compose(&root_rot).compose(&scale);
    let root_inv = root.inverse();

    // Кости в состоянии покоя -> позе. Кончик хвоста — потомок хвоста.
    let f_head = Aff::rot_about(pose.head * spec.head_gain, hp.0, hp.1);
    let f_tail = Aff::rot_about(pose.tail * spec.tail_gain, tp.0, tp.1);
    let f_tip = f_tail.compose(&Aff::rot_about(pose.tip * spec.tail_gain, ip.0, ip.1));
    let (i_head, i_tail, i_tip) = (f_head.inverse(), f_tail.inverse(), f_tip.inverse());

    let inv_ss = 1.0 / SS as f32;
    let (sw, sh) = (ow * SS, oh * SS);
    // Аккумуляторы по строкам блока SS x SS.
    for oy in 0..oh {
        for ox in 0..ow {
            let (mut sa, mut sr, mut sg, mut sb) = (0u32, 0u32, 0u32, 0u32);
            for sy in 0..SS {
                for sx in 0..SS {
                    let px = ((ox * SS + sx) as f32 + 0.5) * inv_ss - PAD as f32;
                    let py = ((oy * SS + sy) as f32 + 0.5) * inv_ss - PAD as f32;
                    let (qx, qy) = root_inv.apply(px, py);
                    let wh = ell_weight(&head, qx, qy);
                    let wt = ell_weight(&tail, qx, qy);
                    let wi = ell_weight(&tip, qx, qy);
                    // Хвост целиком, внутри него — кончик.
                    let (tx_, ty_) = i_tail.apply(qx, qy);
                    let (ix_, iy_) = i_tip.apply(qx, qy);
                    let tail_x = (1.0 - wi) * tx_ + wi * ix_;
                    let tail_y = (1.0 - wi) * ty_ + wi * iy_;
                    let (hx, hy) = i_head.apply(qx, qy);
                    // Голова перекрывает хвост при пересечении масок (голова важнее).
                    let wh_e = wh;
                    let wt_e = wt * (1.0 - wh_e);
                    let wb = (1.0 - wh_e - wt_e).max(0.0);
                    let srcx = wb * qx + wt_e * tail_x + wh_e * hx;
                    let srcy = wb * qy + wt_e * tail_y + wh_e * hy;
                    let ix = srcx.floor() as i32;
                    let iy = srcy.floor() as i32;
                    if ix >= 0 && iy >= 0 && (ix as usize) < w && (iy as usize) < h {
                        let p = src[iy as usize * w + ix as usize];
                        sa += p >> 24;
                        sr += (p >> 16) & 0xFF;
                        sg += (p >> 8) & 0xFF;
                        sb += p & 0xFF;
                    }
                }
            }
            let n = (SS * SS) as u32;
            out[oy * ow + ox] = ((sa / n) << 24) | ((sr / n) << 16) | ((sg / n) << 8) | (sb / n);
        }
    }
    let _ = (sw, sh);
    Some((if flip { flip_x(&out, ow, oh) } else { out }, ow, oh))
}

fn flip_x(px: &[u32], w: usize, h: usize) -> Vec<u32> {
    let mut o = vec![0u32; w * h];
    for y in 0..h {
        for x in 0..w {
            o[y * w + x] = px[y * w + (w - 1 - x)];
        }
    }
    o
}

// ------------------------------------------------------------------ dynamics

/// Что известно о движении пони в этом кадре.
#[derive(Clone, Copy, Debug, Default)]
pub struct Motion {
    /// Скорость, пикселей/с (вправо и вниз > 0), в мировых координатах.
    pub vx: f32,
    pub vy: f32,
    pub facing_right: bool,
    pub dragged: bool,
    /// Курсор относительно центра пони (мировые координаты, пиксели) или None.
    pub cursor_rel: Option<(f32, f32)>,
    pub sleeping: bool,
}

#[derive(Clone, Copy, Debug, Default)]
struct Spring {
    x: f32,
    v: f32,
}

impl Spring {
    /// Полунеявный Эйлер: x'' = k (target - x) - c x'.
    fn step(&mut self, target: f32, k: f32, c: f32, dt: f32) {
        let a = k * (target - self.x) - c * self.v;
        self.v += a * dt;
        self.x += self.v * dt;
    }
}

/// Состояние динамики одной пони.
#[derive(Clone, Debug, Default)]
pub struct Puppet {
    head: Spring,
    tail: Spring,
    tip: Spring,
    lean: Spring,
    t: f32,
    prev_vx: f32,
    prev_vy: f32,
    ax_smooth: f32,
    ay_smooth: f32,
    phase: f32,
    pub pose: Pose,
    started: bool,
}

impl Puppet {
    pub fn new() -> Puppet {
        Puppet { pose: Pose::rest(), ..Default::default() }
    }

    pub fn update(&mut self, dt: f32, m: &Motion) {
        let dt = dt.clamp(0.0, 0.05);
        if dt == 0.0 {
            return;
        }
        // Работаем в системе координат «пони смотрит вправо»: для левой
        // картинки скорости по X отражаются.
        let dir = if m.facing_right { 1.0 } else { -1.0 };
        let vx = m.vx * dir;
        let vy = m.vy;
        if !self.started {
            self.prev_vx = vx;
            self.prev_vy = vy;
            self.started = true;
        }
        let ax = (vx - self.prev_vx) / dt;
        let ay = (vy - self.prev_vy) / dt;
        self.prev_vx = vx;
        self.prev_vy = vy;
        // Сглаживаем ускорение, иначе ступеньки скорости дают рывки.
        let k = 1.0 - (-dt * 12.0).exp();
        self.ax_smooth += (ax - self.ax_smooth) * k;
        self.ay_smooth += (ay - self.ay_smooth) * k;

        self.t += dt;
        let speed = (vx * vx + vy * vy).sqrt();
        self.phase += speed * dt * 0.055;

        let calm = if m.sleeping { 0.25 } else { 1.0 };
        // --- хвост: ветер + инерция (при разгоне вперёд хвост отстаёт вверх/назад)
        let idle_wave = (self.t * 1.7).sin() * 2.2 + (self.t * 0.9 + 1.3).sin() * 1.4;
        let gait = (self.phase * std::f32::consts::TAU).sin() * (speed / 260.0).min(1.0) * 4.0;
        let mut tail_target = idle_wave * calm + gait - (self.ax_smooth * 0.020).clamp(-16.0, 16.0)
            + (self.ay_smooth * 0.010).clamp(-8.0, 8.0);
        if m.dragged {
            tail_target += (self.t * 5.0).sin() * 6.0;
        }
        self.tail.step(tail_target.clamp(-28.0, 28.0), 55.0, 6.5, dt);
        // кончик хвоста запаздывает и усиливает движение основания
        let tip_target = (self.tail.x * 0.9 + (self.t * 2.3 + 0.7).sin() * 2.6 * calm).clamp(-34.0, 34.0);
        self.tip.step(tip_target, 42.0, 4.5, dt);

        // --- голова: смотрит на курсор, иначе слегка кивает в такт шагу
        let mut head_target = 0.0;
        if let Some((rx, ry)) = m.cursor_rel {
            let rx = rx * dir;
            let dist = (rx * rx + ry * ry).sqrt().max(1.0);
            if dist < 420.0 && rx > -60.0 {
                // вверх (ry < 0) — голова поднимается (угол отрицательный)
                head_target = (ry / dist * 11.0).clamp(-10.0, 10.0);
            }
        }
        head_target += (self.phase * std::f32::consts::TAU).sin() * (speed / 260.0).min(1.0) * 1.6;
        head_target += (self.t * 0.6).sin() * 0.6 * calm;
        if m.sleeping {
            head_target = 4.0;
        }
        if m.dragged {
            head_target = -6.0 + (self.t * 4.0).sin() * 3.0;
        }
        self.head.step(head_target, 70.0, 11.0, dt);

        // --- корпус: наклон навстречу разгону, дыхание
        let lean_target = (-self.ax_smooth * 0.0035).clamp(-2.5, 2.5) + if m.dragged { 3.0 } else { 0.0 };
        self.lean.step(lean_target, 50.0, 9.0, dt);
        let breath = (self.t * 1.6).sin();
        let bob = ((self.phase * std::f32::consts::TAU * 2.0).sin().abs() * -1.0) * (speed / 260.0).min(1.0) * 0.9;

        self.pose = Pose {
            head: self.head.x,
            tail: self.tail.x,
            tip: self.tip.x,
            root_rot: self.lean.x,
            bob,
            squash: 1.0 + 0.006 * breath * calm,
        };
    }
}

/// Хранилище динамики по пони.
pub struct PuppetSet {
    map: HashMap<u64, Puppet>,
}

impl PuppetSet {
    pub fn new() -> PuppetSet {
        PuppetSet { map: HashMap::new() }
    }
    pub fn get(&mut self, id: u64) -> &mut Puppet {
        self.map.entry(id).or_insert_with(Puppet::new)
    }
    /// Убирает динамику исчезнувших пони.
    pub fn retain(&mut self, alive: &[u64]) {
        self.map.retain(|k, _| alive.contains(k));
    }
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

    fn sample_frame(dir: &str, file: &str) -> Option<(Vec<u32>, usize, usize)> {
        let p = root().join("Ponies").join(dir).join(file);
        let a = load_animation(p.to_str()?, 1.0)?;
        Some((a.frames[0].pixels.clone(), a.w as usize, a.h as usize))
    }

    #[test]
    fn rest_pose_is_pixel_identical() {
        let (px, w, h) = sample_frame("Applejack", "stand_aj_right.gif").expect("gif");
        let spec = rig_for("Applejack").unwrap();
        let (out, ow, _) = deform(&px, w, h, &spec, &Pose::rest(), false).unwrap();
        for y in 0..h {
            for x in 0..w {
                assert_eq!(out[(y + PAD) * ow + x + PAD], px[y * w + x]);
            }
        }
        // Микро-поза (ниже порога) тоже точная копия.
        let mut p = Pose::rest();
        p.head = 0.01;
        let (out2, _, _) = deform(&px, w, h, &spec, &p, false).unwrap();
        assert_eq!(out, out2);
    }

    #[test]
    fn posed_frame_changes_only_near_bones() {
        let (px, w, h) = sample_frame("Applejack", "stand_aj_right.gif").expect("gif");
        let spec = rig_for("Applejack").unwrap();
        let mut pose = Pose::rest();
        pose.head = 8.0;
        let (out, ow, _) = deform(&px, w, h, &spec, &pose, false).unwrap();
        let mut changed_bottom = 0;
        let mut changed_top = 0;
        for y in 0..h {
            for x in 0..w {
                if out[(y + PAD) * ow + x + PAD] != px[y * w + x] {
                    if y > h * 3 / 4 { changed_bottom += 1 } else { changed_top += 1 }
                }
            }
        }
        assert!(changed_top > 20, "head rotation must change pixels");
        assert_eq!(changed_bottom, 0, "hooves must stay untouched");
    }

    #[test]
    fn flip_matches_mirror_of_right_facing() {
        let (px, w, h) = sample_frame("Applejack", "stand_aj_right.gif").expect("gif");
        let spec = rig_for("Applejack").unwrap();
        let mut pose = Pose::rest();
        pose.tail = 12.0;
        let (a, ow, oh) = deform(&px, w, h, &spec, &pose, false).unwrap();
        // отражённый вход с flip=true даёт отражённый результат
        let mirrored: Vec<u32> = (0..w * h).map(|i| px[(i / w) * w + (w - 1 - i % w)]).collect();
        let (b, _, _) = deform(&mirrored, w, h, &spec, &pose, true).unwrap();
        for y in 0..oh {
            for x in 0..ow {
                assert_eq!(b[y * ow + x], a[y * ow + (ow - 1 - x)]);
            }
        }
    }

    #[test]
    fn dynamics_settle_and_respond() {
        let mut p = Puppet::new();
        let still = Motion { facing_right: true, ..Default::default() };
        for _ in 0..200 {
            p.update(0.02, &still);
        }
        assert!(p.pose.tail.abs() < 4.0 && p.pose.head.abs() < 2.0, "idle stays subtle: {:?}", p.pose);
        // резкий разгон вправо отклоняет хвост назад (отрицательный угол)
        let mut min_tail = 0.0f32;
        for i in 0..40 {
            let m = Motion { vx: (i as f32 * 12.0).min(200.0), facing_right: true, ..Default::default() };
            p.update(0.02, &m);
            min_tail = min_tail.min(p.pose.tail);
        }
        assert!(min_tail < -2.0, "tail should lag behind acceleration: {}", min_tail);
        // курсор выше — голова поднимается
        let mut q = Puppet::new();
        for _ in 0..100 {
            q.update(0.02, &Motion { facing_right: true, cursor_rel: Some((100.0, -150.0)), ..Default::default() });
        }
        assert!(q.pose.head < -3.0, "head looks up at the cursor: {}", q.pose.head);
        // все углы ограничены
        for _ in 0..200 {
            q.update(0.02, &Motion { vx: 900.0, dragged: true, facing_right: false, ..Default::default() });
        }
        assert!(q.pose.tail.abs() <= 40.0 && q.pose.tip.abs() <= 40.0 && q.pose.head.abs() <= 20.0);
    }

    #[test]
    fn behavior_filter() {
        assert!(behavior_allows_rig("stand"));
        assert!(behavior_allows_rig("Trot right"));
        assert!(!behavior_allows_rig("sit down"));
        assert!(!behavior_allows_rig("sleep"));
        assert!(!behavior_allows_rig("dance stand"));
    }

    /// Контрольный лист для подбора масок (запуск вручную):
    /// SKEL_SHEET=out.png cargo test --lib skel_debug_sheet -- --ignored
    #[test]
    #[ignore]
    fn skel_debug_sheet() {
        let out_path = std::env::var("SKEL_SHEET").unwrap_or_else(|_| "skel_sheet.png".into());
        let list = [
            ("Twilight Sparkle", "stand_twilight_right.gif"),
            ("Applejack", "stand_aj_right.gif"),
            ("Rainbow Dash", ""),
            ("Pinkie Pie", ""),
            ("Rarity", ""),
            ("Fluttershy", ""),
            ("Princess Celestia", "stand_right.gif"),
            ("Princess Luna", "luna_idle_right.gif"),
        ];
        let list: Vec<(String, String)> = match std::env::var("SKEL_FILES") {
            Ok(s) => s
                .split(';')
                .filter_map(|e| e.split_once(':').map(|(a, b)| (a.to_string(), b.to_string())))
                .collect(),
            Err(_) => list.iter().map(|(a, b)| (a.to_string(), b.to_string())).collect(),
        };
        let coll = crate::loader::PonyCollection::load(&root(), true);
        let scale: usize = std::env::var("SKEL_SCALE").ok().and_then(|s| s.parse().ok()).unwrap_or(2);
        let cell: usize = std::env::var("SKEL_CELL").ok().and_then(|s| s.parse().ok()).unwrap_or(210);
        let sel: Vec<usize> = std::env::var("SKEL_ROWS")
            .map(|s| s.split(',').filter_map(|x| x.parse().ok()).collect())
            .unwrap_or_else(|_| vec![0, 1, 2, 3]);
        let mut sheet = image::RgbaImage::from_pixel((cell * 3) as u32, (cell * sel.len()) as u32, image::Rgba([60, 60, 70, 255]));
        for (row, idx) in sel.iter().enumerate() {
            let (dir, file) = (list[*idx].0.as_str(), list[*idx].1.as_str());
            let base = coll.base_by_directory(dir).unwrap();
            let path = if file.is_empty() {
                base.behaviors
                    .iter()
                    .find(|b| b.name.to_lowercase().contains("stand") && !b.right_image.path.is_empty())
                    .map(|b| b.right_image.path.clone())
                    .unwrap()
            } else {
                root().join("Ponies").join(dir).join(file).to_string_lossy().to_string()
            };
            let a = load_animation(&path, 1.0).unwrap();
            let (px, w, h) = (a.frames[0].pixels.clone(), a.w as usize, a.h as usize);
            let spec = rig_for(dir).unwrap();
            let poses = [Pose::rest(), Pose { head: -9.0, tail: 16.0, tip: 22.0, root_rot: 1.5, squash: 1.0, bob: 0.0 }, Pose { head: 9.0, tail: -16.0, tip: -22.0, root_rot: -1.5, squash: 1.0, bob: 0.0 }];
            for (col, pose) in poses.iter().enumerate() {
                let (o, ow, oh) = deform(&px, w, h, &spec, pose, false).unwrap();
                let (ox0, oy0) = ((col * cell) as i64, (row * cell) as i64);
                for y in 0..oh * scale {
                    for x in 0..ow * scale {
                        let p = o[(y / scale) * ow + x / scale];
                        let al = (p >> 24) as f32 / 255.0;
                        if al > 0.0 {
                            let (tx, ty) = (ox0 + x as i64, oy0 + y as i64);
                            if tx < (col * cell + cell) as i64 && ty < (row * cell + cell) as i64 {
                                let px_out = sheet.get_pixel_mut(tx as u32, ty as u32);
                                let un = |c: u32| if al > 0.0 { ((c as f32) / al).min(255.0) } else { 0.0 };
                                let (r, g, b) = (un((p >> 16) & 0xFF), un((p >> 8) & 0xFF), un(p & 0xFF));
                                px_out.0 = [
                                    (r * al + px_out.0[0] as f32 * (1.0 - al)) as u8,
                                    (g * al + px_out.0[1] as f32 * (1.0 - al)) as u8,
                                    (b * al + px_out.0[2] as f32 * (1.0 - al)) as u8,
                                    255,
                                ];
                            }
                        }
                    }
                }
                // контуры масок на первой колонке
                if col == 0 {
                    let bb = opaque_bbox(&px, w, h).unwrap();
                    for (e, colr) in [(&spec.head, [255u8, 60, 60]), (&spec.tail, [60, 255, 60]), (&spec.tip, [80, 160, 255])] {
                        let ae = abs_ell(e, &bb);
                        for k in 0..360 {
                            let t = (k as f32).to_radians();
                            let x = ((ae.cx + ae.rx * t.cos() + PAD as f32) * scale as f32) as i64;
                            let y = ((ae.cy + ae.ry * t.sin() + PAD as f32) * scale as f32) as i64;
                            if x >= 0 && y >= 0 && x < cell as i64 && y < cell as i64 {
                                sheet.put_pixel(x as u32, (row * cell) as u32 + y as u32, image::Rgba([colr[0], colr[1], colr[2], 255]));
                            }
                        }
                    }
                }
            }
        }
        sheet.save(&out_path).unwrap();
    }
}
