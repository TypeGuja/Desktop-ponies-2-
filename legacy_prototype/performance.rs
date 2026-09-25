// src_rust/performance.rs
use std::time::Instant;

pub struct PerformanceMonitor {
    frame_count: u64,
    last_check: Instant,
    pub fps: f64,
    pub pony_count: usize,
    pub cache_size: usize,
}

impl PerformanceMonitor {
    pub fn new() -> Self {
        Self {
            frame_count: 0,
            last_check: Instant::now(),
            fps: 0.0,
            pony_count: 0,
            cache_size: 0,
        }
    }

    pub fn update(&mut self, pony_count: usize, cache_size: usize) {
        self.frame_count += 1;
        self.pony_count = pony_count;
        self.cache_size = cache_size;

        let elapsed = self.last_check.elapsed().as_secs_f64();
        if elapsed >= 1.0 {
            self.fps = self.frame_count as f64 / elapsed;
            self.frame_count = 0;
            self.last_check = Instant::now();
        }
    }

    pub fn stats_string(&self) -> String {
        format!("{} ponies | {:.0} FPS | {} cached",
                self.pony_count, self.fps, self.cache_size)
    }
}