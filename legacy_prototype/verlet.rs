// src_rust/verlet.rs
use glam::Vec2;

#[derive(Clone, Debug)]
pub struct VerletPoint {
    pub position: Vec2,
    pub previous: Vec2,
    pub pinned: bool,
}

pub struct VerletChain {
    pub points: Vec<VerletPoint>,
    pub segment_lengths: Vec<f32>,
    pub stiffness: f32,
    pub damping: f32,
}

impl VerletChain {
    pub fn new(anchor: Vec2, segment_count: usize, segment_length: f32) -> Self {
        let mut points = Vec::with_capacity(segment_count + 1);
        let mut lengths = Vec::with_capacity(segment_count);

        points.push(VerletPoint {
            position: anchor,
            previous: anchor,
            pinned: true,
        });

        for i in 0..segment_count {
            let pos = anchor + Vec2::new(0.0, (i + 1) as f32 * segment_length);
            points.push(VerletPoint {
                position: pos,
                previous: pos,
                pinned: false,
            });
            lengths.push(segment_length);
        }

        Self {
            points,
            segment_lengths: lengths,
            stiffness: 8.0,
            damping: 0.96,
        }
    }

    pub fn update(&mut self, dt: f32, gravity: Vec2, anchor_pos: Vec2, anchor_velocity: Vec2) {
        if self.points.is_empty() { return; }

        // Обновляем позицию якоря
        self.points[0].position = anchor_pos;
        self.points[0].previous = anchor_pos - anchor_velocity * dt * 0.9;

        let dt_sq = dt * dt;

        // Verlet integration
        for i in 1..self.points.len() {
            let point = &mut self.points[i];
            if point.pinned { continue; }
            let velocity = (point.position - point.previous) * self.damping;
            point.previous = point.position;
            point.position += velocity + gravity * dt_sq;
        }

        // Ограничения расстояний (несколько итераций для стабильности)
        let iterations = 8;
        for _ in 0..iterations {
            for i in 0..self.points.len().saturating_sub(1) {
                let j = i + 1;
                let p1 = self.points[i].position;
                let p2 = self.points[j].position;
                let mut delta = p2 - p1;
                let dist = delta.length();
                let target = self.segment_lengths.get(i).copied().unwrap_or(10.0);

                if dist < 0.001 {
                    delta = Vec2::new(0.0, target);
                }

                let correction = delta * (dist - target) / dist.max(0.001) * 0.5;

                if !self.points[i].pinned {
                    self.points[i].position += correction;
                }
                if !self.points[j].pinned {
                    self.points[j].position -= correction;
                }
            }
        }
    }

    pub fn get_angles_relative_to_vertical(&self) -> Vec<f32> {
        let mut angles = Vec::new();
        for i in 0..self.points.len().saturating_sub(1) {
            let delta = self.points[i + 1].position - self.points[i].position;
            let angle = delta.x.atan2(delta.y);
            angles.push(angle);
        }
        angles
    }
}