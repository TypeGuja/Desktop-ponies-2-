// src_rust/render.rs
//
// Загрузка анимаций (GIF с индивидуальными задержками кадров), масштабирование
// (ScaleFactor) и наложение спрайтов в ARGB-буфер оверлея. Кадры хранятся с
// предумноженной альфой — так их принимает прозрачное окно.

use image::codecs::gif::GifDecoder;
use image::imageops::FilterType;
use image::AnimationDecoder;
use std::collections::HashMap;
use std::io::Cursor;
use std::rc::Rc;

pub struct Frame {
    /// ARGB с предумноженной альфой.
    pub pixels: Vec<u32>,
    pub delay_ms: u32,
}

pub struct Animation {
    pub w: u32,
    pub h: u32,
    pub frames: Vec<Frame>,
    pub total_ms: u32,
}

impl Animation {
    /// Кадр в момент t_ms от начала показа. prevent_loop — остановиться на
    /// последнем кадре (DoNotRepeatImageAnimations).
    pub fn frame_at(&self, t_ms: f64, prevent_loop: bool) -> &Frame {
        if self.frames.len() <= 1 || self.total_ms == 0 {
            return &self.frames[0];
        }
        let total = self.total_ms as f64;
        let mut t = t_ms.max(0.0);
        if prevent_loop {
            if t >= total {
                return self.frames.last().unwrap();
            }
        } else {
            t %= total;
        }
        let mut acc = 0.0;
        for f in &self.frames {
            acc += f.delay_ms as f64;
            if t < acc {
                return f;
            }
        }
        self.frames.last().unwrap()
    }
}

fn premultiply(r: u8, g: u8, b: u8, a: u8) -> u32 {
    let a32 = a as u32;
    let pm = |c: u8| ((c as u32 * a32 + 127) / 255) as u32;
    (a32 << 24) | (pm(r) << 16) | (pm(g) << 8) | pm(b)
}

/// Загружает GIF. scale != 1 масштабирует кадры (вверх — без сглаживания,
/// вниз — с усреднением, как "lossless downscale" в оригинале).
pub fn load_animation(path: &str, scale: f32) -> Option<Animation> {
    let bytes = std::fs::read(path).ok()?;
    let decoder = GifDecoder::new(Cursor::new(&bytes)).ok()?;
    let src_frames: Vec<image::Frame> = decoder.into_frames().filter_map(|f| f.ok()).collect();
    if src_frames.is_empty() {
        return None;
    }
    let (sw, sh) = (src_frames[0].buffer().width(), src_frames[0].buffer().height());
    let (w, h) = if (scale - 1.0).abs() < f32::EPSILON {
        (sw, sh)
    } else {
        (((sw as f32 * scale) as u32).max(1), ((sh as f32 * scale) as u32).max(1))
    };
    let mut frames: Vec<Frame> = Vec::new();
    for f in &src_frames {
        let (n, d) = f.delay().numer_denom_ms();
        let delay = if d > 0 { n / d } else { 0 };
        if delay == 0 {
            // В оригинале кадры нулевой длительности не показываются.
            continue;
        }
        let buf = if (w, h) == (sw, sh) {
            f.buffer().clone()
        } else {
            let filter = if scale > 1.0 { FilterType::Nearest } else { FilterType::Triangle };
            image::imageops::resize(f.buffer(), w, h, filter)
        };
        let pixels: Vec<u32> = buf.pixels().map(|p| premultiply(p.0[0], p.0[1], p.0[2], p.0[3])).collect();
        frames.push(Frame { pixels, delay_ms: delay });
    }
    if frames.is_empty() {
        let f = &src_frames[0];
        let buf = if (w, h) == (sw, sh) {
            f.buffer().clone()
        } else {
            image::imageops::resize(f.buffer(), w, h, FilterType::Nearest)
        };
        let pixels: Vec<u32> = buf.pixels().map(|p| premultiply(p.0[0], p.0[1], p.0[2], p.0[3])).collect();
        frames.push(Frame { pixels, delay_ms: 100 });
    }
    let total = frames.iter().map(|f| f.delay_ms).sum();
    Some(Animation { w, h, frames, total_ms: total })
}

/// Кэш загруженных анимаций (путь + масштаб).
pub struct SpriteCache {
    map: HashMap<(String, u32), Option<Rc<Animation>>>,
}

impl SpriteCache {
    pub fn new() -> SpriteCache {
        SpriteCache { map: HashMap::new() }
    }

    pub fn get(&mut self, path: &str, scale: f32) -> Option<Rc<Animation>> {
        if path.is_empty() {
            return None;
        }
        let key = (path.to_string(), (scale * 100.0).round() as u32);
        if let Some(v) = self.map.get(&key) {
            return v.clone();
        }
        if self.map.len() > 400 {
            self.map.clear();
        }
        let a = load_animation(path, scale).map(Rc::new);
        self.map.insert(key, a.clone());
        a
    }

    pub fn clear(&mut self) {
        self.map.clear();
    }
}

/// Накладывает кадр (x, y — левый верхний угол в координатах буфера).
pub fn blit(dst: &mut [u32], dw: usize, dh: usize, frame: &Frame, fw: usize, fh: usize, x: i32, y: i32) {
    if fw == 0 || fh == 0 {
        return;
    }
    let x0 = x.max(0);
    let y0 = y.max(0);
    let x1 = (x + fw as i32).min(dw as i32);
    let y1 = (y + fh as i32).min(dh as i32);
    if x0 >= x1 || y0 >= y1 {
        return;
    }
    for py in y0..y1 {
        let src_row = ((py - y) as usize) * fw;
        let dst_row = py as usize * dw;
        for px in x0..x1 {
            let s = frame.pixels[src_row + (px - x) as usize];
            let a = s >> 24;
            if a == 0 {
                continue;
            }
            let d = &mut dst[dst_row + px as usize];
            if a == 255 {
                *d = s;
            } else {
                let inv = 255 - a;
                let mix = |sc: u32, dc: u32| sc + (dc * inv + 127) / 255;
                let na = mix(a, *d >> 24);
                let nr = mix((s >> 16) & 0xFF, (*d >> 16) & 0xFF);
                let ng = mix((s >> 8) & 0xFF, (*d >> 8) & 0xFF);
                let nb = mix(s & 0xFF, *d & 0xFF);
                *d = (na.min(255) << 24) | (nr.min(255) << 16) | (ng.min(255) << 8) | nb.min(255);
            }
        }
    }
}

/// Непрозрачен ли пиксель кадра (для click-through над спрайтом).
pub fn pixel_opaque(frame: &Frame, fw: usize, fh: usize, x: i32, y: i32) -> bool {
    if x < 0 || y < 0 || x as usize >= fw || y as usize >= fh {
        return false;
    }
    (frame.pixels[y as usize * fw + x as usize] >> 24) > 8
}

#[cfg(test)]
mod tests {
    use super::*;

    fn anim(delays: &[u32]) -> Animation {
        Animation {
            w: 1,
            h: 1,
            frames: delays.iter().enumerate().map(|(i, d)| Frame { pixels: vec![i as u32], delay_ms: *d }).collect(),
            total_ms: delays.iter().sum(),
        }
    }

    #[test]
    fn frame_selection_uses_individual_delays() {
        let a = anim(&[100, 300, 100]);
        assert_eq!(a.frame_at(0.0, false).pixels[0], 0);
        assert_eq!(a.frame_at(99.0, false).pixels[0], 0);
        assert_eq!(a.frame_at(100.0, false).pixels[0], 1);
        assert_eq!(a.frame_at(399.0, false).pixels[0], 1);
        assert_eq!(a.frame_at(400.0, false).pixels[0], 2);
        assert_eq!(a.frame_at(500.0, false).pixels[0], 0, "loops");
        assert_eq!(a.frame_at(5000.0, true).pixels[0], 2, "prevent loop stops on last frame");
    }

    #[test]
    fn real_gif_loads_and_scales() {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/Ponies/Applejack/stand_aj_right.gif");
        let a = load_animation(path, 1.0).expect("gif");
        let b = load_animation(path, 2.0).expect("gif scaled");
        assert_eq!((b.w, b.h), (a.w * 2, a.h * 2));
        assert!(!a.frames.is_empty());
        assert!(a.frames.iter().any(|f| f.pixels.iter().any(|p| (p >> 24) == 255)), "has opaque pixels");
    }

    #[test]
    fn blit_blends_and_clips() {
        let f = Frame { pixels: vec![0xFF112233, 0x80000080, 0x00000000, 0xFFFFFFFF], delay_ms: 100 };
        let mut dst = vec![0u32; 16];
        blit(&mut dst, 4, 4, &f, 2, 2, 1, 1);
        assert_eq!(dst[5], 0xFF112233);
        assert_eq!(dst[6] >> 24, 0x80);
        assert_eq!(dst[9], 0, "transparent pixel is skipped");
        assert_eq!(dst[10], 0xFFFFFFFF);
        // выход за границы не паникует
        blit(&mut dst, 4, 4, &f, 2, 2, -1, -1);
        blit(&mut dst, 4, 4, &f, 2, 2, 3, 3);
    }
}
