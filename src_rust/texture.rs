// src_rust/texture.rs
use wgpu::*;
use std::collections::HashMap;

pub struct TextureData {
    pub texture: wgpu::Texture,
    pub view: TextureView,
    pub sampler: Sampler,
    pub width: u32,
    pub height: u32,
    pub frame_count: u32,
    pub frame_width: u32,
}

pub struct TextureManager {
    pub textures: Vec<TextureData>,
    default_sampler: Sampler,
    name_to_id: HashMap<String, usize>,
}

impl TextureManager {
    pub fn new(device: &Device) -> Self {
        let default_sampler = device.create_sampler(&SamplerDescriptor {
            address_mode_u: AddressMode::ClampToEdge,
            address_mode_v: AddressMode::ClampToEdge,
            address_mode_w: AddressMode::ClampToEdge,
            mag_filter: FilterMode::Nearest,
            min_filter: FilterMode::Nearest,
            mipmap_filter: FilterMode::Nearest,
            ..Default::default()
        });

        Self {
            textures: Vec::new(),
            default_sampler,
            name_to_id: HashMap::new(),
        }
    }

    pub fn load_texture(
        &mut self,
        device: &Device,
        queue: &Queue,
        name: &str,
        bytes: &[u8],
        frame_count: u32,
    ) -> usize {
        let img = match image::load_from_memory(bytes) {
            Ok(img) => img.to_rgba8(),
            Err(_) => {
                eprintln!("Warning: failed to decode '{}', creating white fallback", name);
                image::RgbaImage::from_pixel(2, 2, image::Rgba([255, 255, 255, 255]))
            }
        };

        let (width, height) = img.dimensions();
        let rgba_data = img.into_raw();

        self.load_texture_raw(device, queue, name, &rgba_data, width, height, frame_count)
    }

    pub fn load_texture_raw(
        &mut self,
        device: &Device,
        queue: &Queue,
        name: &str,
        rgba_data: &[u8],
        width: u32,
        height: u32,
        frame_count: u32,
    ) -> usize {
        let frame_width = width / frame_count.max(1);

        let size = Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        };

        let texture = device.create_texture(&TextureDescriptor {
            label: Some(name),
            size,
            mip_level_count: 1,
            sample_count: 1,
            dimension: TextureDimension::D2,
            format: TextureFormat::Rgba8UnormSrgb,
            usage: TextureUsages::TEXTURE_BINDING | TextureUsages::COPY_DST,
            view_formats: &[],
        });

        queue.write_texture(
            ImageCopyTexture {
                texture: &texture,
                mip_level: 0,
                origin: Origin3d::ZERO,
                aspect: TextureAspect::All,
            },
            rgba_data,
            ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(4 * width),
                rows_per_image: Some(height),
            },
            size,
        );

        let view = texture.create_view(&TextureViewDescriptor::default());

        let sampler = device.create_sampler(&SamplerDescriptor {
            address_mode_u: AddressMode::ClampToEdge,
            address_mode_v: AddressMode::ClampToEdge,
            address_mode_w: AddressMode::ClampToEdge,
            mag_filter: FilterMode::Nearest,
            min_filter: FilterMode::Nearest,
            mipmap_filter: FilterMode::Nearest,
            ..Default::default()
        });

        let id = self.textures.len();
        self.textures.push(TextureData {
            texture,
            view,
            sampler,
            width,
            height,
            frame_count,
            frame_width,
        });
        self.name_to_id.insert(name.to_string(), id);

        println!("Texture '{}' loaded (id={}, {}x{}, frames={}, frame_w={})",
                 name, id, width, height, frame_count, frame_width);
        id
    }

    pub fn get(&self, id: usize) -> Option<&TextureData> {
        self.textures.get(id)
    }

    pub fn get_by_name(&self, name: &str) -> Option<&TextureData> {
        self.name_to_id.get(name).and_then(|&id| self.textures.get(id))
    }
}