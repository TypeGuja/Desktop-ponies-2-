// src_rust/skeleton.rs
use glam::{Mat4, Quat, Vec3};
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct Bone {
    pub name: String,
    pub parent: Option<usize>,
    pub bind_position: Vec3,
    pub bind_rotation: Quat,
    pub length: f32,
    pub children: Vec<usize>,
}

#[derive(Clone)]
pub struct Skeleton {
    pub bones: Vec<Bone>,
    pub bone_map: HashMap<String, usize>,
    pub local_poses: Vec<Mat4>,
    pub global_poses: Vec<Mat4>,
    pub bone_rotations: Vec<Quat>,
    pub bone_positions: Vec<Vec3>,
}

impl Skeleton {
    pub fn new() -> Self {
        Self {
            bones: Vec::new(),
            bone_map: HashMap::new(),
            local_poses: Vec::new(),
            global_poses: Vec::new(),
            bone_rotations: Vec::new(),
            bone_positions: Vec::new(),
        }
    }

    pub fn add_bone(&mut self, name: &str, parent: Option<usize>, length: f32, bind_pos: Vec3) -> usize {
        let idx = self.bones.len();
        if let Some(p) = parent {
            self.bones[p].children.push(idx);
        }
        self.bones.push(Bone {
            name: name.to_string(),
            parent,
            bind_position: bind_pos,
            bind_rotation: Quat::IDENTITY,
            length,
            children: Vec::new(),
        });
        self.bone_map.insert(name.to_string(), idx);
        self.local_poses.push(Mat4::IDENTITY);
        self.global_poses.push(Mat4::IDENTITY);
        self.bone_rotations.push(Quat::IDENTITY);
        self.bone_positions.push(bind_pos);
        idx
    }

    pub fn set_bone_rotation(&mut self, name: &str, rotation: Quat) {
        if let Some(&idx) = self.bone_map.get(name) {
            self.bone_rotations[idx] = rotation;
            let pos = self.bones[idx].bind_position;
            self.local_poses[idx] = Mat4::from_rotation_translation(rotation, pos);
        }
    }

    pub fn set_bone_position(&mut self, name: &str, position: Vec3) {
        if let Some(&idx) = self.bone_map.get(name) {
            self.bone_positions[idx] = position;
            let rot = self.bone_rotations[idx];
            self.local_poses[idx] = Mat4::from_rotation_translation(rot, position);
        }
    }

    pub fn update_global_poses(&mut self) {
        fn update_recursive(
            bones: &[Bone],
            local_poses: &[Mat4],
            globals: &mut [Mat4],
            idx: usize,
            parent_global: Mat4,
        ) {
            let global = parent_global * local_poses[idx];
            globals[idx] = global;
            for &child in &bones[idx].children {
                update_recursive(bones, local_poses, globals, child, global);
            }
        }

        for (i, bone) in self.bones.iter().enumerate() {
            if bone.parent.is_none() {
                update_recursive(&self.bones, &self.local_poses, &mut self.global_poses, i, Mat4::IDENTITY);
            }
        }
    }

    pub fn get_bone_world_position(&self, name: &str) -> Option<Vec3> {
        self.bone_map.get(name).map(|&idx| {
            let m = self.global_poses[idx];
            Vec3::new(m.w_axis.x, m.w_axis.y, m.w_axis.z)
        })
    }

    /// Создать стандартный скелет пони
    pub fn create_pony_skeleton() -> Self {
        let mut skel = Skeleton::new();
        let root = skel.add_bone("root", None, 0.0, Vec3::ZERO);
        let body = skel.add_bone("body", Some(root), 60.0, Vec3::new(0.0, 0.0, 0.0));
        let head = skel.add_bone("head", Some(body), 25.0, Vec3::new(0.0, 50.0, 0.0));
        skel.add_bone("ear_left", Some(head), 12.0, Vec3::new(-8.0, 22.0, 0.0));
        skel.add_bone("ear_right", Some(head), 12.0, Vec3::new(8.0, 22.0, 0.0));
        skel.add_bone("front_left_upper", Some(body), 20.0, Vec3::new(-14.0, -10.0, 0.0));
        skel.add_bone("front_left_lower", Some(5), 22.0, Vec3::new(0.0, -18.0, 0.0));
        skel.add_bone("front_right_upper", Some(body), 20.0, Vec3::new(14.0, -10.0, 0.0));
        skel.add_bone("front_right_lower", Some(7), 22.0, Vec3::new(0.0, -18.0, 0.0));
        skel.add_bone("back_left_upper", Some(body), 22.0, Vec3::new(-12.0, -40.0, 0.0));
        skel.add_bone("back_left_lower", Some(9), 24.0, Vec3::new(0.0, -20.0, 0.0));
        skel.add_bone("back_right_upper", Some(body), 22.0, Vec3::new(12.0, -40.0, 0.0));
        skel.add_bone("back_right_lower", Some(11), 24.0, Vec3::new(0.0, -20.0, 0.0));
        // Хвост — цепочка
        let mut parent = body;
        for i in 0..6 {
            parent = skel.add_bone(&format!("tail_{}", i), Some(parent), 10.0, Vec3::new(0.0, -55.0 - i as f32 * 9.0, 0.0));
        }
        // Грива — цепочка
        let mut parent = head;
        for i in 0..4 {
            parent = skel.add_bone(&format!("mane_{}", i), Some(parent), 8.0, Vec3::new(0.0, 18.0 - i as f32 * 7.0, 0.0));
        }
        skel.local_poses.resize(skel.bones.len(), Mat4::IDENTITY);
        skel.global_poses.resize(skel.bones.len(), Mat4::IDENTITY);
        skel.bone_rotations.resize(skel.bones.len(), Quat::IDENTITY);
        skel.bone_positions.resize(skel.bones.len(), Vec3::ZERO);
        skel
    }
}