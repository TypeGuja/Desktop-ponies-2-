// src_rust/bubble.rs
//
// Отрисовка облачка с репликой над пони прямо в ARGB-буфере softbuffer.
// Растровый шрифт из bitmap_font.rs не покрывает всю кириллицу и знаки
// препинания, поэтому здесь используется настоящий TTF (fontdue) из системных
// шрифтов Windows. Если ни один шрифт не найден — облачка просто не рисуются.

use std::collections::HashMap;

const FONT_CANDIDATES: &[&str] = &["segoeui.ttf", "tahoma.ttf", "arial.ttf"];

pub struct TextRenderer {
    font: fontdue::Font,
    size: f32,
    cache: HashMap<char, (fontdue::Metrics, Vec<u8>)>,
}

impl TextRenderer {
    pub fn load(size: f32) -> Option<Self> {
        let win_dir = std::env::var("WINDIR").unwrap_or_else(|_| "C:\\Windows".to_string());
        for name in FONT_CANDIDATES {
            let path = std::path::Path::new(&win_dir).join("Fonts").join(name);
            if let Ok(bytes) = std::fs::read(&path) {
                if let Ok(font) = fontdue::Font::from_bytes(bytes, fontdue::FontSettings::default()) {
                    println!("[Bubble] Using font {:?}", path);
                    return Some(Self { font, size, cache: HashMap::new() });
                }
            }
        }
        eprintln!("[Bubble] No system font found, speech bubbles disabled");
        None
    }

    fn glyph(&mut self, ch: char) -> &(fontdue::Metrics, Vec<u8>) {
        let (font, size) = (&self.font, self.size);
        self.cache.entry(ch).or_insert_with(|| font.rasterize(ch, size))
    }

    fn advance(&mut self, ch: char) -> f32 {
        self.glyph(ch).0.advance_width
    }

    fn line_height(&self) -> f32 {
        self.font
            .horizontal_line_metrics(self.size)
            .map(|m| m.new_line_size)
            .unwrap_or(self.size * 1.3)
    }

    fn ascent(&self) -> f32 {
        self.font
            .horizontal_line_metrics(self.size)
            .map(|m| m.ascent)
            .unwrap_or(self.size)
    }

    /// Разбивает текст на строки шириной не более max_w (перенос по словам,
    /// слишком длинные слова режутся по символам).
    fn wrap(&mut self, text: &str, max_w: f32) -> Vec<String> {
        let mut lines: Vec<String> = Vec::new();
        let mut cur = String::new();
        let mut cur_w = 0.0f32;
        let space_w = self.advance(' ');

        for word in text.split_whitespace() {
            let word_w: f32 = word.chars().map(|c| self.advance(c)).sum();

            if word_w > max_w {
                // Длинное слово: сначала закрываем текущую строку, затем режем.
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
}

fn put_pixel(buf: &mut [u32], bw: usize, bh: usize, x: i32, y: i32, color: u32) {
    if x >= 0 && y >= 0 && (x as usize) < bw && (y as usize) < bh {
        buf[y as usize * bw + x as usize] = color;
    }
}

fn blend(dst: u32, src: u32, alpha: u32) -> u32 {
    let mix = |d: u32, s: u32| (s * alpha + d * (255 - alpha)) / 255;
    0xFF000000
        | (mix((dst >> 16) & 0xFF, (src >> 16) & 0xFF) << 16)
        | (mix((dst >> 8) & 0xFF, (src >> 8) & 0xFF) << 8)
        | mix(dst & 0xFF, src & 0xFF)
}

/// Рисует облачко над точкой (anchor_x, anchor_top) — центр верхней границы
/// спрайта пони. Если сверху не хватает места, облачко сдвигается в пределы
/// экрана.
pub fn draw_bubble(
    buf: &mut [u32],
    bw: usize,
    bh: usize,
    tr: &mut TextRenderer,
    text: &str,
    anchor_x: f32,
    anchor_top: f32,
) {
    const MAX_TEXT_W: f32 = 240.0;
    const PAD: i32 = 8;
    const TAIL: i32 = 8;

    let lines = tr.wrap(text, MAX_TEXT_W);
    if lines.is_empty() {
        return;
    }

    let line_h = tr.line_height();
    let ascent = tr.ascent();
    let text_w = lines
        .iter()
        .map(|l| l.chars().map(|c| tr.advance(c)).sum::<f32>())
        .fold(0.0f32, f32::max);

    let w = text_w.ceil() as i32 + PAD * 2;
    let h = (line_h * lines.len() as f32).ceil() as i32 + PAD * 2;

    let max_x = (bw as i32 - w).max(0);
    let x0 = ((anchor_x as i32) - w / 2).clamp(0, max_x);
    let y0 = ((anchor_top as i32) - h - TAIL).max(0);

    let fill = 0xFFFFFFFFu32;
    let border = 0xFF3A3A3Au32;
    let text_color = 0xFF1B1B1Bu32;

    // Тело с «срезанными» углами и рамкой.
    for y in 0..h {
        for x in 0..w {
            let corner = (x < 2 && y < 2 - x) || (x >= w - 2 && y < x - (w - 3))
                || (x < 2 && y >= h - 2 + x) || (x >= w - 2 && y >= h - 1 - (x - (w - 2)));
            if corner {
                continue;
            }
            let edge = x == 0 || y == 0 || x == w - 1 || y == h - 1;
            put_pixel(buf, bw, bh, x0 + x, y0 + y, if edge { border } else { fill });
        }
    }

    // Хвостик, указывающий на пони.
    let tail_cx = (anchor_x as i32).clamp(x0 + 8, x0 + w - 8);
    for row in 0..TAIL {
        let half = TAIL - row;
        for dx in -half..=half {
            let edge = dx.abs() == half || row == TAIL - 1;
            put_pixel(buf, bw, bh, tail_cx + dx, y0 + h + row, if edge { border } else { fill });
        }
    }
    // Стираем рамку в месте примыкания хвостика к телу.
    for dx in -(TAIL - 1)..=(TAIL - 1) {
        put_pixel(buf, bw, bh, tail_cx + dx, y0 + h - 1, fill);
    }

    // Текст.
    for (i, line) in lines.iter().enumerate() {
        let baseline = y0 + PAD + (line_h * i as f32 + ascent) as i32;
        let mut pen_x = (x0 + PAD) as f32;
        for ch in line.chars() {
            let (metrics, bitmap) = tr.glyph(ch).clone();
            let gx = pen_x as i32 + metrics.xmin;
            let gy = baseline - metrics.height as i32 - metrics.ymin;
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
                        buf[idx] = blend(buf[idx], text_color, a);
                    }
                }
            }
            pen_x += metrics.advance_width;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn draws_wrapped_cyrillic_bubble_inside_buffer() {
        let Some(mut tr) = TextRenderer::load(15.0) else { return; };
        let (bw, bh) = (400usize, 300usize);
        let mut buf = vec![0u32; bw * bh];
        draw_bubble(&mut buf, bw, bh, &mut tr,
            "Привет! Как дела? Это очень длинная реплика пони, которая должна перенестись на несколько строк.",
            200.0, 150.0);
        let painted = buf.iter().filter(|&&p| p != 0).count();
        assert!(painted > 500, "bubble not drawn: {}", painted);
        // Выше якоря есть пиксели, ниже хвостика — пусто.
        assert!(buf[..(150 * bw)].iter().any(|&p| p != 0));
        assert!(buf[(170 * bw)..].iter().all(|&p| p == 0));
        // Облачко у левого края не должно вылезать за буфер (нет паники).
        draw_bubble(&mut buf, bw, bh, &mut tr, "edge", 0.0, 5.0);
    }
}
