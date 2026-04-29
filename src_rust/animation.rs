// src_rust/animation.rs
use glam::Quat;
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct Keyframe {
    pub time: f32,
    pub rotation: Quat,
}

#[derive(Clone, Debug)]
pub struct BoneTrack {
    pub bone_name: String,
    pub keyframes: Vec<Keyframe>,
}

#[derive(Clone)]
pub struct AnimationClip {
    pub name: String,
    pub duration: f32,
    pub tracks: HashMap<String, BoneTrack>,
    pub looped: bool,
}

impl AnimationClip {
    pub fn sample(&self, time: f32) -> HashMap<String, Quat> {
        let t = if self.looped && self.duration > 0.0 {
            time % self.duration
        } else {
            time.min(self.duration)
        };

        let mut pose = HashMap::new();
        for track in self.tracks.values() {
            let rot = Self::sample_track(track, t);
            pose.insert(track.bone_name.clone(), rot);
        }
        pose
    }

    fn sample_track(track: &BoneTrack, time: f32) -> Quat {
        if track.keyframes.is_empty() {
            return Quat::IDENTITY;
        }
        if track.keyframes.len() == 1 || time <= track.keyframes[0].time {
            return track.keyframes[0].rotation;
        }

        let last = track.keyframes.last().unwrap();
        if time >= last.time {
            return last.rotation;
        }

        let mut next_idx = 1;
        while next_idx < track.keyframes.len() && track.keyframes[next_idx].time < time {
            next_idx += 1;
        }

        let prev = &track.keyframes[next_idx - 1];
        let next = &track.keyframes[next_idx];
        let range = next.time - prev.time;
        let factor = if range > 0.0 { (time - prev.time) / range } else { 0.0 };

        prev.rotation.slerp(next.rotation, factor)
    }

    pub fn create_walk() -> Self {
        let mut tracks = HashMap::new();
        let half_pi = std::f32::consts::FRAC_PI_2;

        // Передняя левая нога (верх + низ)
        tracks.insert("front_left_upper".into(), BoneTrack {
            bone_name: "front_left_upper".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(0.5) },
                Keyframe { time: 0.25, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(-0.5) },
                Keyframe { time: 0.75, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(0.5) },
            ],
        });
        tracks.insert("front_left_lower".into(), BoneTrack {
            bone_name: "front_left_lower".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(0.15) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(-0.15) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(0.15) },
            ],
        });
        // Правая передняя (противофаза)
        tracks.insert("front_right_upper".into(), BoneTrack {
            bone_name: "front_right_upper".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(-0.5) },
                Keyframe { time: 0.25, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(0.5) },
                Keyframe { time: 0.75, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(-0.5) },
            ],
        });
        tracks.insert("front_right_lower".into(), BoneTrack {
            bone_name: "front_right_lower".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(-0.15) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(0.15) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(-0.15) },
            ],
        });
        // Задние ноги: левая в фазе с правой передней, правая в фазе с левой передней
        tracks.insert("back_left_upper".into(), BoneTrack {
            bone_name: "back_left_upper".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(-0.5) },
                Keyframe { time: 0.25, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(0.5) },
                Keyframe { time: 0.75, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(-0.5) },
            ],
        });
        tracks.insert("back_left_lower".into(), BoneTrack {
            bone_name: "back_left_lower".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(-0.2) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(0.2) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(-0.2) },
            ],
        });
        tracks.insert("back_right_upper".into(), BoneTrack {
            bone_name: "back_right_upper".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(0.5) },
                Keyframe { time: 0.25, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(-0.5) },
                Keyframe { time: 0.75, rotation: Quat::from_rotation_z(0.0) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(0.5) },
            ],
        });
        tracks.insert("back_right_lower".into(), BoneTrack {
            bone_name: "back_right_lower".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(0.2) },
                Keyframe { time: 0.5, rotation: Quat::from_rotation_z(-0.2) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_z(0.2) },
            ],
        });

        AnimationClip {
            name: "walk".into(),
            duration: 1.0,
            tracks,
            looped: true,
        }
    }

    pub fn create_idle() -> Self {
        let mut tracks = HashMap::new();
        // Лёгкое покачивание тела
        tracks.insert("body".into(), BoneTrack {
            bone_name: "body".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_z(0.02) },
                Keyframe { time: 1.5, rotation: Quat::from_rotation_z(-0.02) },
                Keyframe { time: 3.0, rotation: Quat::from_rotation_z(0.02) },
            ],
        });
        // Дыхание — лёгкое движение головы
        tracks.insert("head".into(), BoneTrack {
            bone_name: "head".into(),
            keyframes: vec![
                Keyframe { time: 0.0, rotation: Quat::from_rotation_x(0.03) },
                Keyframe { time: 1.0, rotation: Quat::from_rotation_x(-0.03) },
                Keyframe { time: 2.0, rotation: Quat::from_rotation_x(0.03) },
            ],
        });

        AnimationClip {
            name: "idle".into(),
            duration: 3.0,
            tracks,
            looped: true,
        }
    }
}