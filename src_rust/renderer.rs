// src_rust/renderer.rs (полностью исправленный)
use wgpu::*;
use  tao::window::Window;
use glam::Mat4;
use std::sync::Arc;
use bytemuck::{Pod, Zeroable};
use crate::{
    mesh::{MeshManager, SkeletalVertex, SpriteVertex, SpriteInstance},
    texture::TextureManager,
    shaders,
    pony::{PonyEntity, PonyRenderType},
};

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct Uniforms {
    pub view_proj: [[f32; 4]; 4],
}

pub struct Renderer {
    pub device: Device,
    pub queue: Queue,
    pub surface: Surface<'static>,
    pub config: SurfaceConfiguration,
    pub size: (u32, u32),
    pub skeletal_pipeline: RenderPipeline,
    pub sprite_pipeline: RenderPipeline,
    pub skeletal_bind_group_layout: BindGroupLayout,
    pub sprite_bind_group_layout: BindGroupLayout,
    pub uniform_buffer: Buffer,
    pub bone_buffer: Buffer,
    pub mesh_manager: MeshManager,
    pub texture_manager: TextureManager,
}

impl Renderer {
    pub async fn new(window: Arc<Window>) -> Self {
        let size = window.inner_size();
        let instance = Instance::new(InstanceDescriptor {
            backends: Backends::all(),
            ..Default::default()
        });

        let surface = instance.create_surface(window.clone()).unwrap();

        let adapter = instance
            .request_adapter(&RequestAdapterOptions {
                power_preference: PowerPreference::LowPower,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            })
            .await
            .unwrap();

        let (device, queue) = adapter
            .request_device(
                &DeviceDescriptor {
                    required_features: Features::TEXTURE_ADAPTER_SPECIFIC_FORMAT_FEATURES,
                    required_limits: Limits {
                        max_bind_groups: 4,
                        max_storage_buffers_per_shader_stage: 4,
                        ..Default::default()
                    },
                    label: None,
                },
                None,
            )
            .await
            .unwrap();

        let surface_caps = surface.get_capabilities(&adapter);
        let surface_format = surface_caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .unwrap_or(surface_caps.formats[0]);

        let alpha_mode = if surface_caps.alpha_modes.contains(&CompositeAlphaMode::PreMultiplied) {
            CompositeAlphaMode::PreMultiplied
        } else if surface_caps.alpha_modes.contains(&CompositeAlphaMode::PostMultiplied) {
            CompositeAlphaMode::PostMultiplied
        } else {
            eprintln!("Warning: no alpha mode with transparency supported");
            CompositeAlphaMode::Opaque
        };

        let config = SurfaceConfiguration {
            usage: TextureUsages::RENDER_ATTACHMENT,
            format: surface_format,
            width: size.width,
            height: size.height,
            present_mode: PresentMode::AutoVsync,
            alpha_mode,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);

        let mesh_manager = MeshManager::new(&device);
        let texture_manager = TextureManager::new(&device);

        let uniform_buffer = device.create_buffer(&BufferDescriptor {
            label: Some("uniform buffer"),
            size: std::mem::size_of::<Uniforms>() as u64,
            usage: BufferUsages::UNIFORM | BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let bone_buffer = device.create_buffer(&BufferDescriptor {
            label: Some("bone buffer"),
            size: (128 * 64) as u64,
            usage: BufferUsages::UNIFORM | BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let skeletal_shader = device.create_shader_module(ShaderModuleDescriptor {
            label: Some("skeletal shader"),
            source: ShaderSource::Wgsl(shaders::SKELETAL_VERTEX_SHADER.into()),
        });

        let sprite_shader = device.create_shader_module(ShaderModuleDescriptor {
            label: Some("sprite shader"),
            source: ShaderSource::Wgsl(shaders::SPRITE_VERTEX_SHADER.into()),
        });

        let skeletal_bind_group_layout =
            device.create_bind_group_layout(&BindGroupLayoutDescriptor {
                label: Some("skeletal bind group layout"),
                entries: &[
                    BindGroupLayoutEntry {
                        binding: 0,
                        visibility: ShaderStages::VERTEX,
                        ty: BindingType::Buffer {
                            ty: BufferBindingType::Uniform,
                            has_dynamic_offset: false,
                            min_binding_size: None,
                        },
                        count: None,
                    },
                    BindGroupLayoutEntry {
                        binding: 1,
                        visibility: ShaderStages::VERTEX,
                        ty: BindingType::Buffer {
                            ty: BufferBindingType::Uniform,
                            has_dynamic_offset: false,
                            min_binding_size: None,
                        },
                        count: None,
                    },
                    BindGroupLayoutEntry {
                        binding: 2,
                        visibility: ShaderStages::FRAGMENT,
                        ty: BindingType::Sampler(SamplerBindingType::Filtering),
                        count: None,
                    },
                    BindGroupLayoutEntry {
                        binding: 3,
                        visibility: ShaderStages::FRAGMENT,
                        ty: BindingType::Texture {
                            sample_type: TextureSampleType::Float { filterable: true },
                            view_dimension: TextureViewDimension::D2,
                            multisampled: false,
                        },
                        count: None,
                    },
                ],
            });

        let sprite_bind_group_layout =
            device.create_bind_group_layout(&BindGroupLayoutDescriptor {
                label: Some("sprite bind group layout"),
                entries: &[
                    BindGroupLayoutEntry {
                        binding: 0,
                        visibility: ShaderStages::VERTEX,
                        ty: BindingType::Buffer {
                            ty: BufferBindingType::Uniform,
                            has_dynamic_offset: false,
                            min_binding_size: None,
                        },
                        count: None,
                    },
                    BindGroupLayoutEntry {
                        binding: 1,
                        visibility: ShaderStages::FRAGMENT,
                        ty: BindingType::Sampler(SamplerBindingType::Filtering),
                        count: None,
                    },
                    BindGroupLayoutEntry {
                        binding: 2,
                        visibility: ShaderStages::FRAGMENT,
                        ty: BindingType::Texture {
                            sample_type: TextureSampleType::Float { filterable: true },
                            view_dimension: TextureViewDimension::D2,
                            multisampled: false,
                        },
                        count: None,
                    },
                ],
            });

        let skeletal_pipeline_layout =
            device.create_pipeline_layout(&PipelineLayoutDescriptor {
                label: Some("skeletal pipeline layout"),
                bind_group_layouts: &[&skeletal_bind_group_layout],
                push_constant_ranges: &[],
            });

        let sprite_pipeline_layout =
            device.create_pipeline_layout(&PipelineLayoutDescriptor {
                label: Some("sprite pipeline layout"),
                bind_group_layouts: &[&sprite_bind_group_layout],
                push_constant_ranges: &[],
            });

        let skeletal_pipeline =
            device.create_render_pipeline(&RenderPipelineDescriptor {
                label: Some("skeletal pipeline"),
                layout: Some(&skeletal_pipeline_layout),
                vertex: VertexState {
                    module: &skeletal_shader,
                    entry_point: "vs_main",
                    buffers: &[VertexBufferLayout {
                        array_stride: std::mem::size_of::<SkeletalVertex>() as u64,
                        step_mode: VertexStepMode::Vertex,
                        attributes: &[
                            VertexAttribute {
                                format: VertexFormat::Float32x2,
                                offset: 0,
                                shader_location: 0,
                            },
                            VertexAttribute {
                                format: VertexFormat::Float32x2,
                                offset: 8,
                                shader_location: 1,
                            },
                            VertexAttribute {
                                format: VertexFormat::Uint32x4,
                                offset: 16,
                                shader_location: 2,
                            },
                            VertexAttribute {
                                format: VertexFormat::Float32x4,
                                offset: 32,
                                shader_location: 3,
                            },
                        ],
                    }],
                },
                fragment: Some(FragmentState {
                    module: &skeletal_shader,
                    entry_point: "fs_main",
                    targets: &[Some(ColorTargetState {
                        format: config.format,
                        blend: Some(BlendState::ALPHA_BLENDING),
                        write_mask: ColorWrites::ALL,
                    })],
                }),
                primitive: PrimitiveState {
                    topology: PrimitiveTopology::TriangleList,
                    ..Default::default()
                },
                depth_stencil: None,
                multisample: MultisampleState::default(),
                multiview: None,
            });

        let sprite_pipeline =
            device.create_render_pipeline(&RenderPipelineDescriptor {
                label: Some("sprite pipeline"),
                layout: Some(&sprite_pipeline_layout),
                vertex: VertexState {
                    module: &sprite_shader,
                    entry_point: "vs_main",
                    buffers: &[
                        VertexBufferLayout {
                            array_stride: std::mem::size_of::<SpriteVertex>() as u64,
                            step_mode: VertexStepMode::Vertex,
                            attributes: &[
                                VertexAttribute {
                                    format: VertexFormat::Float32x2,
                                    offset: 0,
                                    shader_location: 0,
                                },
                                VertexAttribute {
                                    format: VertexFormat::Float32x2,
                                    offset: 8,
                                    shader_location: 1,
                                },
                            ],
                        },
                        VertexBufferLayout {
                            array_stride: std::mem::size_of::<SpriteInstance>() as u64,
                            step_mode: VertexStepMode::Instance,
                            attributes: &[
                                VertexAttribute {
                                    format: VertexFormat::Float32x2,
                                    offset: 0,
                                    shader_location: 2,
                                },
                                VertexAttribute {
                                    format: VertexFormat::Float32x2,
                                    offset: 8,
                                    shader_location: 3,
                                },
                            ],
                        },
                    ],
                },
                fragment: Some(FragmentState {
                    module: &sprite_shader,
                    entry_point: "fs_main",
                    targets: &[Some(ColorTargetState {
                        format: config.format,
                        blend: Some(BlendState::ALPHA_BLENDING),
                        write_mask: ColorWrites::ALL,
                    })],
                }),
                primitive: PrimitiveState {
                    topology: PrimitiveTopology::TriangleList,
                    ..Default::default()
                },
                depth_stencil: None,
                multisample: MultisampleState::default(),
                multiview: None,
            });

        Self {
            device,
            queue,
            surface,
            config,
            size: (size.width, size.height),
            skeletal_pipeline,
            sprite_pipeline,
            skeletal_bind_group_layout,
            sprite_bind_group_layout,
            uniform_buffer,
            bone_buffer,
            mesh_manager,
            texture_manager,
        }
    }

    pub fn resize(&mut self, new_size: (u32, u32)) {
        if new_size.0 > 0 && new_size.1 > 0 {
            self.size = new_size;
            self.config.width = new_size.0;
            self.config.height = new_size.1;
            self.surface.configure(&self.device, &self.config);
        }
    }

    pub fn render(
        &mut self,
        ponies: &[&crate::pony::PonyEntity],
    ) -> Result<(), SurfaceError> {
        let output = self.surface.get_current_texture()?;
        let view = output
            .texture
            .create_view(&TextureViewDescriptor::default());

        let mut encoder = self
            .device
            .create_command_encoder(&CommandEncoderDescriptor {
                label: Some("render encoder"),
            });

        let (w, h) = (self.size.0 as f32, self.size.1 as f32);
        let view_proj = Mat4::orthographic_rh_gl(0.0, w, h, 0.0, -1.0, 1.0);
        let uniforms = Uniforms {
            view_proj: view_proj.to_cols_array_2d(),
        };
        self.queue.write_buffer(
            &self.uniform_buffer,
            0,
            bytemuck::cast_slice(&[uniforms]),
        );

        let skeletal_ponies: Vec<_> = ponies.iter().filter(|p| p.is_skeletal()).collect();
        let sprite_ponies: Vec<_> = ponies.iter().filter(|p| !p.is_skeletal()).collect();

        // Если текстур нет — создаём заглушку
        if self.texture_manager.textures.is_empty() {
            return Ok(());
        }

        let dummy_texture = &self.texture_manager.textures[0];

        let skeletal_bind_group = self.device.create_bind_group(&BindGroupDescriptor {
            label: Some("skeletal bind group"),
            layout: &self.skeletal_bind_group_layout,
            entries: &[
                BindGroupEntry {
                    binding: 0,
                    resource: self.uniform_buffer.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 1,
                    resource: self.bone_buffer.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 2,
                    resource: BindingResource::Sampler(&dummy_texture.sampler),
                },
                BindGroupEntry {
                    binding: 3,
                    resource: BindingResource::TextureView(&dummy_texture.view),
                },
            ],
        });

        let sprite_bind_group = self.device.create_bind_group(&BindGroupDescriptor {
            label: Some("sprite bind group"),
            layout: &self.sprite_bind_group_layout,
            entries: &[
                BindGroupEntry {
                    binding: 0,
                    resource: self.uniform_buffer.as_entire_binding(),
                },
                BindGroupEntry {
                    binding: 1,
                    resource: BindingResource::Sampler(&dummy_texture.sampler),
                },
                BindGroupEntry {
                    binding: 2,
                    resource: BindingResource::TextureView(&dummy_texture.view),
                },
            ],
        });

        let instances: Vec<SpriteInstance> = sprite_ponies.iter().map(|pony| {
            let (frame, frame_count) = match &pony.render_type {
                PonyRenderType::Sprite { current_frame, frame_count, .. } => {
                    (*current_frame as f32, *frame_count as f32)
                }
                _ => (0.0, 1.0),
            };
            SpriteInstance {
                position: [pony.position.x, pony.position.y],
                frame_and_scale: [frame, 100.0], // размер спрайта 100px
            }
        }).collect();

        if !instances.is_empty() {
            self.queue.write_buffer(
                &self.mesh_manager.sprite_instance_buffer,
                0,
                bytemuck::cast_slice(&instances),
            );
        }

        {
            let mut render_pass = encoder.begin_render_pass(&RenderPassDescriptor {
                label: Some("main render pass"),
                color_attachments: &[Some(RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: Operations {
                        load: LoadOp::Clear(Color {
                            r: 0.0,
                            g: 0.0,
                            b: 0.0,
                            a: 0.0,
                        }),
                        store: StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });

            // --- Скелетные пони ---
            render_pass.set_pipeline(&self.skeletal_pipeline);
            render_pass.set_bind_group(0, &skeletal_bind_group, &[]);

            for pony in &skeletal_ponies {
                if let PonyRenderType::Skeletal { skeleton, .. } = &pony.render_type {
                    let bone_matrices: Vec<[[f32; 4]; 4]> = skeleton
                        .global_poses
                        .iter()
                        .map(|m| m.to_cols_array_2d())
                        .collect();

                    self.queue.write_buffer(
                        &self.bone_buffer,
                        0,
                        bytemuck::cast_slice(&bone_matrices),
                    );

                    for part in &self.mesh_manager.skeletal_parts {
                        render_pass.set_vertex_buffer(0, part.vertex_buffer.slice(..));
                        render_pass.set_index_buffer(
                            part.index_buffer.slice(..),
                            IndexFormat::Uint16,
                        );
                        render_pass.draw_indexed(0..part.index_count, 0, 0..1);
                    }
                }
            }

            // --- Спрайтовые пони ---
            if !instances.is_empty() {
                render_pass.set_pipeline(&self.sprite_pipeline);
                render_pass.set_bind_group(0, &sprite_bind_group, &[]);
                render_pass.set_vertex_buffer(0, self.mesh_manager.quad_mesh.vertex_buffer.slice(..));
                render_pass.set_vertex_buffer(1, self.mesh_manager.sprite_instance_buffer.slice(..));
                render_pass.set_index_buffer(
                    self.mesh_manager.quad_mesh.index_buffer.slice(..),
                    IndexFormat::Uint16,
                );

                render_pass.draw_indexed(
                    0..self.mesh_manager.quad_mesh.index_count,
                    0,
                    0..instances.len() as u32,
                );
            }
        }

        self.queue.submit(std::iter::once(encoder.finish()));
        output.present();

        Ok(())
    }
}