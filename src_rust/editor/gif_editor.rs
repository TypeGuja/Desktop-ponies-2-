// src_rust/editor/gif_editor.rs
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use image::{ImageBuffer, Rgba, Frame, Delay};
use image::codecs::gif::{GifEncoder, Repeat};
use std::time::Duration;

#[derive(Clone, Debug)]
pub struct GifFrame {
    pub data: Vec<u8>,
    pub width: u32,
    pub height: u32,
    pub delay: u16,  // в сотых долях секунды
}

pub struct GifEditor {
    pub frames: Vec<GifFrame>,
    pub current_frame: usize,
    pub loop_count: Repeat,
    pub width: u32,
    pub height: u32,
}

impl GifEditor {
    pub fn new() -> Self {
        Self {
            frames: Vec::new(),
            current_frame: 0,
            loop_count: Repeat::Infinite,
            width: 0,
            height: 0,
        }
    }

    pub fn load_gif(&mut self, path: &Path) -> Result<(), String> {
        let file = fs::File::open(path).map_err(|e| e.to_string())?;
        let decoder = image::codecs::gif::GifDecoder::new(file).map_err(|e| e.to_string())?;

        let mut frames = Vec::new();
        for frame in decoder.into_frames() {
            let frame = frame.map_err(|e| e.to_string())?;
            let buffer = frame.buffer();
            let delay = frame.delay().numer_denom_ms().0 as u16;

            frames.push(GifFrame {
                data: buffer.to_vec(),
                width: buffer.width(),
                height: buffer.height(),
                delay,
            });
        }

        if let Some(first) = frames.first() {
            self.width = first.width;
            self.height = first.height;
        }
        self.frames = frames;
        Ok(())
    }

    pub fn save_gif(&self, path: &Path) -> Result<(), String> {
        let file = fs::File::create(path).map_err(|e| e.to_string())?;
        let mut encoder = GifEncoder::new(file);
        encoder.set_repeat(self.loop_count).map_err(|e| e.to_string())?;

        for frame in &self.frames {
            let img = ImageBuffer::<Rgba<u8>, _>::from_raw(
                frame.width, frame.height, frame.data.clone()
            ).ok_or("Invalid frame data")?;

            let delay = Delay::from_numer_denom_ms(frame.delay as u32, 100);
            let gif_frame = Frame::from_parts(img, 0, 0, delay);
            encoder.encode_frame(gif_frame).map_err(|e| e.to_string())?;
        }
        Ok(())
    }

    pub fn add_frame(&mut self, width: u32, height: u32) {
        let data = vec![0u8; (width * height * 4) as usize];
        self.frames.push(GifFrame {
            data,
            width,
            height,
            delay: 10,
        });
        self.width = width;
        self.height = height;
        self.current_frame = self.frames.len() - 1;
    }

    pub fn delete_frame(&mut self, index: usize) {
        if index < self.frames.len() {
            self.frames.remove(index);
            if self.current_frame >= self.frames.len() && !self.frames.is_empty() {
                self.current_frame = self.frames.len() - 1;
            }
        }
    }

    pub fn set_frame_delay(&mut self, index: usize, delay: u16) {
        if let Some(frame) = self.frames.get_mut(index) {
            frame.delay = delay;
        }
    }

    pub fn set_pixel(&mut self, frame_idx: usize, x: u32, y: u32, color: [u8; 4]) {
        if let Some(frame) = self.frames.get_mut(frame_idx) {
            let idx = ((y * frame.width + x) * 4) as usize;
            if idx + 3 < frame.data.len() {
                frame.data[idx] = color[0];
                frame.data[idx + 1] = color[1];
                frame.data[idx + 2] = color[2];
                frame.data[idx + 3] = color[3];
            }
        }
    }

    pub fn flood_fill(&mut self, frame_idx: usize, x: u32, y: u32, new_color: [u8; 4]) {
        if let Some(frame) = self.frames.get(frame_idx) {
            let target_color = self.get_pixel(frame_idx, x, y);
            if target_color == new_color { return; }

            let mut stack = vec![(x, y)];
            let width = frame.width;
            let height = frame.height;

            while let Some((px, py)) = stack.pop() {
                if px >= width || py >= height { continue; }
                let current = self.get_pixel(frame_idx, px, py);
                if current != target_color { continue; }

                self.set_pixel(frame_idx, px, py, new_color);

                stack.push((px + 1, py));
                stack.push((px.wrapping_sub(1), py));
                stack.push((px, py + 1));
                stack.push((px, py.wrapping_sub(1)));
            }
        }
    }

    fn get_pixel(&self, frame_idx: usize, x: u32, y: u32) -> [u8; 4] {
        if let Some(frame) = self.frames.get(frame_idx) {
            let idx = ((y * frame.width + x) * 4) as usize;
            if idx + 3 < frame.data.len() {
                return [
                    frame.data[idx],
                    frame.data[idx + 1],
                    frame.data[idx + 2],
                    frame.data[idx + 3],
                ];
            }
        }
        [0, 0, 0, 0]
    }
}