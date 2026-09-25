// src_rust/text.rs
//
// Текст в ARGB-буфер оверлея: системный TTF (fontdue) с кэшем глифов,
// измерение, перенос строк и облачко реплики в стиле оригинала (белый
// прямоугольник с чёрной рамкой над спрайтом). Шрифт берётся из системных
// шрифтов Windows (Segoe UI / Tahoma / Arial) — в них есть кириллица.

use std::collections::HashMap;

const FONT_CANDIDATES: &[&str] = &["segoeui.ttf", "tahoma.ttf", "arial.ttf"];

pub struct TextRenderer {
    font: fontdue::Font,
    size: f32,
    cache: HashMap<char, (fontdue::Metrics, Vec<u8>)>,
}

impl TextRenderer {
    pub fn load(size: f32) -> Option<TextRenderer> {
        let win_dir = std::env::var("WINDIR").unwrap_or_else(|_| "C:\\Windows".to_string());
        for name in FONT_CANDIDATES {
            let path = std::path::Path::new(&win_dir).join("Fonts").join(name);
            if let Ok(bytes) = std::fs::read(&path) {
                if let Ok(font) = fontdue::Font::from_bytes(bytes, fontdue::FontSettings::default()) {
                    return Some(TextRenderer { font, size, cache: HashMap::new() });
                }
            }
        }
        None
    }

    fn glyph(&mut self, ch: char) -> &(fontdue::Metrics, Vec<u8>) {
        let (font, size) = (&self.font, self.size);
        self.cache.entry(ch).or_insert_with(|| font.rasterize(ch, size))
    }

    pub fn advance(&mut self, ch: char) -> f32 {
        self.glyph(ch).0.advance_width
    }

    /// Ширина строки в пикселях.
    pub fn measure(&mut self, text: &str) -> f32 {
        text.chars().map(|c| self.advance(c)).sum()
    }

    pub fn line_height(&self) -> f32 {
        self.font.horizontal_line_metrics(self.size).map(|m| m.new_line_size).unwrap_or(self.size * 1.3)
    }

    pub fn ascent(&self) -> f32 {
        self.font.horizontal_line_metrics(self.size).map(|m| m.ascent).unwrap_or(self.size)
    }

    /// Разбивает текст на строки не шире max_w (перенос по словам).
    pub fn wrap(&mut self, text: &str, max_w: f32) -> Vec<String> {
        let mut lines: Vec<String> = Vec::new();
        let mut cur = String::new();
        let mut cur_w = 0.0f32;
        let space_w = self.advance(' ');
        for word in text.split_whitespace() {
            let word_w = self.measure(word);
            if word_w > max_w {
                if !cur.is_empty() {
                    lines.push(std::mem::take(&mut cur));
                    cur_w = 0.0;
                }
                for c in word.chars() {
                    let w = self.advance(c);
                    if cur_w + w > max_w && !cur.is_empty() {
                        lines.push(std::mem::take(&mut cur));
                        cur_w = 0.0;
                    }
                    cur.push(c);
                    cur_w += w;
                }
                continue;
            }
            let needed = if cur.is_empty() { word_w } else { cur_w + space_w + word_w };
            if needed > max_w && !cur.is_empty() {
                lines.push(std::mem::take(&mut cur));
                cur.push_str(word);
                cur_w = word_w;
            } else {
                if !cur.is_empty() {
                    cur.push(' ');
                }
                cur.push_str(word);
                cur_w = needed;
            }
        }
        if !cur.is_empty() {
            lines.push(cur);
        }
        lines
    }

    /// Рисует одну строку; (x, y) — левый верхний угол строки.
    pub fn draw_line(&mut self, buf: &mut [u32], bw: usize, bh: usize, x: f32, y: f32, text: &str, color: u32) {
        let baseline = y + self.ascent();
        let mut pen = x;
        for ch in text.chars() {
            let (metrics, bitmap) = self.glyph(ch).clone();
            let gx = pen as i32 + metrics.xmin;
            let gy = baseline as i32 - metrics.height as i32 - metrics.ymin;
            for row in 0..metrics.height {
                for col in 0..metrics.width {
                    let a = bitmap[row * metrics.width + col] as u32;
                    if a == 0 {
                        continue;
                    }
                    let px = gx + col as i32;
                    let py = gy + row as i32;
                    if px >= 0 && py >= 0 && (px as usize) < bw && (py as usize) < bh {
                        let idx = py as usize * bw + px as usize;
                        buf[idx] = blend(buf[idx], color, a);
                    }
                }
            }
            pen += metrics.advance_width;
        }
    }
}

fn blend(dst: u32, src: u32, alpha: u32) -> u32 {
    let mix = |d: u32, s: u32| (s * alpha + d * (255 - alpha)) / 255;
    0xFF000000
        | (mix((dst >> 16) & 0xFF, (src >> 16) & 0xFF) << 16)
        | (mix((dst >> 8) & 0xFF, (src >> 8) & 0xFF) << 8)
        | mix(dst & 0xFF, src & 0xFF)
}

pub fn fill_rect(buf: &mut [u32], bw: usize, bh: usize, x: i32, y: i32, w: i32, h: i32, color: u32) {
    let x0 = x.max(0);
    let y0 = y.max(0);
    let x1 = (x + w).min(bw as i32);
    let y1 = (y + h).min(bh as i32);
    for py in y0..y1 {
        for px in x0..x1 {
            buf[py as usize * bw + px as usize] = color;
        }
    }
}

pub fn stroke_rect(buf: &mut [u32], bw: usize, bh: usize, x: i32, y: i32, w: i32, h: i32, color: u32) {
    fill_rect(buf, bw, bh, x, y, w, 1, color);
    fill_rect(buf, bw, bh, x, y + h - 1, w, 1, color);
    fill_rect(buf, bw, bh, x, y, 1, h, color);
    fill_rect(buf, bw, bh, x + w - 1, y, 1, h, color);
}

/// Облачко реплики над спрайтом: белый прямоугольник, чёрная рамка, чёрный
/// текст (как DrawString/DrawRectangle в WinFormSpriteInterface). Реплики
/// длиннее max_w переносятся на несколько строк. sprite — регион спрайта в
/// координатах буфера, bounds — допустимая область (границы экрана).
pub fn draw_speech_bubble(
    buf: &mut [u32],
    bw: usize,
    bh: usize,
    tr: &mut TextRenderer,
    text: &str,
    sprite_x: i32,
    sprite_y: i32,
    sprite_w: i32,
) {
    const MAX_W: f32 = 320.0;
    let lines = tr.wrap(text, MAX_W);
    if lines.is_empty() {
        return;
    }
    let lh = tr.line_height();
    let text_w = lines.iter().map(|l| tr.measure(l)).fold(0.0f32, f32::max);
    let w = text_w.ceil() as i32 + 4;
    let h = (lh * lines.len() as f32).ceil() as i32 + 2;
    let mut x = sprite_x + sprite_w / 2 - w / 2 - 1;
    let mut y = sprite_y - h - 1;
    if x < 0 {
        x = 0;
    }
    if x + w > bw as i32 {
        x = bw as i32 - w;
    }
    if y < 0 {
        y = 0;
    }
    if y + h > bh as i32 {
        y = bh as i32 - h;
    }
    fill_rect(buf, bw, bh, x, y, w, h, 0xFFFFFFFF);
    stroke_rect(buf, bw, bh, x, y, w, h, 0xFF000000);
    for (i, line) in lines.iter().enumerate() {
        tr.draw_line(buf, bw, bh, (x + 2) as f32, y as f32 + 1.0 + lh * i as f32, line, 0xFF000000);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn measures_wraps_and_draws() {
        let Some(mut tr) = TextRenderer::load(12.0) else { return };
        assert!(tr.measure("Hello") > tr.measure("Hi"));
        let lines = tr.wrap("Привет! Это очень длинная реплика пони, которая должна перенестись на несколько строк.", 150.0);
        assert!(lines.len() >= 3);
        assert!(lines.iter().all(|l| tr.measure(l) <= 150.5));
        let (bw, bh) = (400usize, 200usize);
        let mut buf = vec![0u32; bw * bh];
        draw_speech_bubble(&mut buf, bw, bh, &mut tr, "Twilight Sparkle: \"Hello!\"", 200, 100, 60);
        assert!(buf.iter().filter(|p| **p == 0xFFFFFFFF).count() > 200, "white bubble body");
        assert!(buf.iter().any(|p| *p == 0xFF000000), "black border");
        // у границ не паникует
        draw_speech_bubble(&mut buf, bw, bh, &mut tr, "edge", -20, -5, 10);
    }
}
