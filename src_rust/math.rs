// src_rust/math.rs
//
// Небольшие геометрические типы, повторяющие семантику System.Drawing из
// оригинального Desktop Ponies (Vector2F / RectangleF / Rectangle): границы
// прямоугольников и проверки пересечения ведут себя так же, как в оригинале,
// поэтому симуляция (отскоки, зоны, взаимодействия) совпадает.

use std::ops::{Add, AddAssign, Div, Mul, Neg, Sub, SubAssign};

#[derive(Clone, Copy, Debug, PartialEq, Default)]
pub struct V2 {
    pub x: f32,
    pub y: f32,
}

impl V2 {
    pub const ZERO: V2 = V2 { x: 0.0, y: 0.0 };
    pub const NAN: V2 = V2 { x: f32::NAN, y: f32::NAN };

    pub fn new(x: f32, y: f32) -> V2 {
        V2 { x, y }
    }
    pub fn length(self) -> f32 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
    pub fn dist_sq(a: V2, b: V2) -> f32 {
        let d = a - b;
        d.x * d.x + d.y * d.y
    }
    pub fn is_nan(self) -> bool {
        self.x.is_nan() || self.y.is_nan()
    }
    pub fn round(self) -> (i32, i32) {
        (round_half_even(self.x), round_half_even(self.y))
    }
}

/// Banker's rounding (MidpointRounding.ToEven) — как Math.Round в .NET.
pub fn round_half_even(x: f32) -> i32 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 {
        let f = x.floor();
        if (f as i64) % 2 == 0 { f as i32 } else { (f + 1.0) as i32 }
    } else {
        r as i32
    }
}

impl Add for V2 {
    type Output = V2;
    fn add(self, o: V2) -> V2 { V2::new(self.x + o.x, self.y + o.y) }
}
impl Sub for V2 {
    type Output = V2;
    fn sub(self, o: V2) -> V2 { V2::new(self.x - o.x, self.y - o.y) }
}
impl Mul<f32> for V2 {
    type Output = V2;
    fn mul(self, s: f32) -> V2 { V2::new(self.x * s, self.y * s) }
}
impl Div<f32> for V2 {
    type Output = V2;
    fn div(self, s: f32) -> V2 { V2::new(self.x / s, self.y / s) }
}
impl Neg for V2 {
    type Output = V2;
    fn neg(self) -> V2 { V2::new(-self.x, -self.y) }
}
impl AddAssign for V2 {
    fn add_assign(&mut self, o: V2) { self.x += o.x; self.y += o.y; }
}
impl SubAssign for V2 {
    fn sub_assign(&mut self, o: V2) { self.x -= o.x; self.y -= o.y; }
}

#[derive(Clone, Copy, Debug, PartialEq, Default)]
pub struct RectF {
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
}

impl RectF {
    pub const EMPTY: RectF = RectF { x: 0.0, y: 0.0, w: 0.0, h: 0.0 };

    pub fn new(x: f32, y: f32, w: f32, h: f32) -> RectF {
        RectF { x, y, w, h }
    }
    pub fn left(&self) -> f32 { self.x }
    pub fn top(&self) -> f32 { self.y }
    pub fn right(&self) -> f32 { self.x + self.w }
    pub fn bottom(&self) -> f32 { self.y + self.h }
    pub fn center(&self) -> V2 { V2::new(self.x + self.w / 2.0, self.y + self.h / 2.0) }
    pub fn is_empty(&self) -> bool { self.w <= 0.0 || self.h <= 0.0 }
    pub fn size_is_zero(&self) -> bool { self.w == 0.0 && self.h == 0.0 }

    /// RectangleF.Contains(x, y): правая/нижняя граница не включается.
    pub fn contains_point(&self, p: V2) -> bool {
        self.x <= p.x && p.x < self.right() && self.y <= p.y && p.y < self.bottom()
    }
    /// RectangleF.Contains(RectangleF): включительно.
    pub fn contains_rect(&self, r: &RectF) -> bool {
        self.x <= r.x && r.right() <= self.right() && self.y <= r.y && r.bottom() <= self.bottom()
    }
    /// RectangleF.IntersectsWith: строгие неравенства.
    pub fn intersects(&self, r: &RectF) -> bool {
        r.x < self.right() && self.x < r.right() && r.y < self.bottom() && self.y < r.bottom()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct RectI {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

impl RectI {
    pub fn new(x: i32, y: i32, w: i32, h: i32) -> RectI {
        RectI { x, y, w, h }
    }
    pub fn left(&self) -> i32 { self.x }
    pub fn top(&self) -> i32 { self.y }
    pub fn right(&self) -> i32 { self.x + self.w }
    pub fn bottom(&self) -> i32 { self.y + self.h }
    pub fn is_empty(&self) -> bool { self.w <= 0 || self.h <= 0 }
    pub fn to_f(&self) -> RectF { RectF::new(self.x as f32, self.y as f32, self.w as f32, self.h as f32) }

    pub fn contains_point(&self, x: i32, y: i32) -> bool {
        self.x <= x && x < self.right() && self.y <= y && y < self.bottom()
    }
    pub fn union(&self, o: &RectI) -> RectI {
        let l = self.x.min(o.x);
        let t = self.y.min(o.y);
        let r = self.right().max(o.right());
        let b = self.bottom().max(o.bottom());
        RectI::new(l, t, r - l, b - t)
    }
    pub fn intersect(&self, o: &RectI) -> RectI {
        let l = self.x.max(o.x);
        let t = self.y.max(o.y);
        let r = self.right().min(o.right());
        let b = self.bottom().min(o.bottom());
        if r >= l && b >= t { RectI::new(l, t, r - l, b - t) } else { RectI::default() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bankers_rounding() {
        assert_eq!(round_half_even(0.5), 0);
        assert_eq!(round_half_even(1.5), 2);
        assert_eq!(round_half_even(2.5), 2);
        assert_eq!(round_half_even(-0.5), 0);
        assert_eq!(round_half_even(2.4), 2);
        assert_eq!(round_half_even(2.6), 3);
    }

    #[test]
    fn rect_semantics() {
        let a = RectF::new(0.0, 0.0, 10.0, 10.0);
        assert!(a.contains_rect(&RectF::new(0.0, 0.0, 10.0, 10.0)));
        assert!(!a.intersects(&RectF::new(10.0, 0.0, 5.0, 5.0)), "touching edges do not intersect");
        assert!(a.intersects(&RectF::new(9.9, 0.0, 5.0, 5.0)));
        assert!(!a.contains_point(V2::new(10.0, 5.0)));
    }
}
