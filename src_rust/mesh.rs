// src_rust/mesh.rs (исправленный)
use bytemuck::{Pod, Zeroable};
use wgpu::*;
use wgpu::util::DeviceExt; // <-- ВОТ ЧЕГО НЕ ХВАТАЛО
use std::mem;

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct SkeletalVertex {
    pub position: [f32; 2],
    pub tex_coords: [f32; 2],
    pub bone_indices: [u32; 4],
    pub bone_weights: [f32; 4],
}

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct SpriteVertex {
    pub position: [f32; 2],
    pub tex_coords: [f32; 2],
}

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct SpriteInstance {
    pub position: [f32; 2],
    pub frame_and_scale: [f32; 2],
}

pub struct Mesh {
    pub vertex_buffer: Buffer,
    pub index_buffer: Buffer,
    pub index_count: u32,
}

pub struct MeshManager {
    pub quad_mesh: Mesh,
    pub skeletal_parts: Vec<Mesh>,
    pub sprite_instance_buffer: Buffer,
}

impl MeshManager {
    pub fn new(device: &Device) -> Self {
        let sprite_verts: Vec<SpriteVertex> = vec![
            SpriteVertex { position: [0.0, 0.0], tex_coords: [0.0, 0.0] },
            SpriteVertex { position: [1.0, 0.0], tex_coords: [1.0, 0.0] },
            SpriteVertex { position: [0.0, 1.0], tex_coords: [0.0, 1.0] },
            SpriteVertex { position: [1.0, 1.0], tex_coords: [1.0, 1.0] },
        ];

        let quad_indices: Vec<u16> = vec![0, 1, 2, 1, 3, 2];

        let vertex_buffer = device.create_buffer_init(&util::BufferInitDescriptor {
            label: Some("quad vertex buffer"),
            contents: bytemuck::cast_slice(&sprite_verts),
            usage: BufferUsages::VERTEX,
        });

        let index_buffer = device.create_buffer_init(&util::BufferInitDescriptor {
            label: Some("quad index buffer"),
            contents: bytemuck::cast_slice(&quad_indices),
            usage: BufferUsages::INDEX,
        });

        let quad_mesh = Mesh {
            vertex_buffer,
            index_buffer,
            index_count: quad_indices.len() as u32,
        };

        let sprite_instance_buffer = device.create_buffer(&BufferDescriptor {
            label: Some("sprite instance buffer"),
            size: (mem::size_of::<SpriteInstance>() * 1024) as u64,
            usage: BufferUsages::VERTEX | BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let mut skeletal_parts = Vec::new();

        skeletal_parts.push(Self::create_skeletal_part(device, 48.0, 60.0, 1)); // body
        skeletal_parts.push(Self::create_skeletal_part(device, 32.0, 25.0, 2)); // head
        skeletal_parts.push(Self::create_skeletal_part(device, 10.0, 12.0, 3)); // ear_left
        skeletal_parts.push(Self::create_skeletal_part(device, 10.0, 12.0, 4)); // ear_right
        for &bone_idx in &[5, 7, 9, 11] {
            skeletal_parts.push(Self::create_skeletal_part(device, 14.0, 20.0, bone_idx));
        }
        for &bone_idx in &[6, 8, 10, 12] {
            skeletal_parts.push(Self::create_skeletal_part(device, 12.0, 22.0, bone_idx));
        }
        for i in 13..19 {
            skeletal_parts.push(Self::create_skeletal_part(device, 8.0, 9.0, i));
        }
        for i in 19..23 {
            skeletal_parts.push(Self::create_skeletal_part(device, 10.0, 7.0, i));
        }

        Self {
            quad_mesh,
            skeletal_parts,
            sprite_instance_buffer,
        }
    }

    fn create_skeletal_part(device: &Device, width: f32, height: f32, bone_idx: u32) -> Mesh {
        let hw = width / 2.0;
        let hh = height / 2.0;

        let vertices: Vec<SkeletalVertex> = vec![
            SkeletalVertex {
                position: [-hw, -hh],
                tex_coords: [0.0, 1.0],
                bone_indices: [bone_idx, 0, 0, 0],
                bone_weights: [1.0, 0.0, 0.0, 0.0],
            },
            SkeletalVertex {
                position: [hw, -hh],
                tex_coords: [1.0, 1.0],
                bone_indices: [bone_idx, 0, 0, 0],
                bone_weights: [1.0, 0.0, 0.0, 0.0],
            },
            SkeletalVertex {
                position: [hw, hh],
                tex_coords: [1.0, 0.0],
                bone_indices: [bone_idx, 0, 0, 0],
                bone_weights: [1.0, 0.0, 0.0, 0.0],
            },
            SkeletalVertex {
                position: [-hw, hh],
                tex_coords: [0.0, 0.0],
                bone_indices: [bone_idx, 0, 0, 0],
                bone_weights: [1.0, 0.0, 0.0, 0.0],
            },
        ];

        let indices: Vec<u16> = vec![0, 1, 2, 0, 2, 3];

        let vertex_buffer = device.create_buffer_init(&util::BufferInitDescriptor {
            label: Some(&format!("skeletal part bone {}", bone_idx)),
            contents: bytemuck::cast_slice(&vertices),
            usage: BufferUsages::VERTEX,
        });

        let index_buffer = device.create_buffer_init(&util::BufferInitDescriptor {
            label: Some(&format!("skeletal part index bone {}", bone_idx)),
            contents: bytemuck::cast_slice(&indices),
            usage: BufferUsages::INDEX,
        });

        Mesh {
            vertex_buffer,
            index_buffer,
            index_count: indices.len() as u32,
        }
    }
}