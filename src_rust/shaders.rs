// src_rust/shaders.rs — полностью исправленный

pub const SKELETAL_VERTEX_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
}

struct BoneData {
    matrices: array<mat4x4<f32>, 128>,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(0) @binding(1) var<uniform> bones: BoneData;
@group(0) @binding(2) var tex_sampler: sampler;
@group(0) @binding(3) var tex: texture_2d<f32>;

struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) tex_coords: vec2<f32>,
    @location(2) bone_indices: vec4<u32>,
    @location(3) bone_weights: vec4<f32>,
}

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) tex_coords: vec2<f32>,
}

@vertex
fn vs_main(in: VertexInput) -> VertexOutput {
    var skin_matrix = mat4x4<f32>(
        vec4<f32>(0.0, 0.0, 0.0, 0.0),
        vec4<f32>(0.0, 0.0, 0.0, 0.0),
        vec4<f32>(0.0, 0.0, 0.0, 0.0),
        vec4<f32>(0.0, 0.0, 0.0, 0.0),
    );
    for (var i: u32 = 0u; i < 4u; i++) {
        let idx = in.bone_indices[i];
        let weight = in.bone_weights[i];
        if weight > 0.0 {
            skin_matrix = skin_matrix + bones.matrices[idx] * weight;
        }
    }

    let pos = vec4<f32>(in.position, 0.0, 1.0);
    let skinned = skin_matrix * pos;

    var out: VertexOutput;
    out.position = uniforms.view_proj * skinned;
    out.tex_coords = in.tex_coords;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let color = textureSample(tex, tex_sampler, in.tex_coords);
    if color.a < 0.1 {
        discard;
    }
    return color;
}
"#;

pub const SPRITE_VERTEX_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(0) @binding(1) var tex_sampler: sampler;
@group(0) @binding(2) var tex: texture_2d<f32>;

struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) tex_coords: vec2<f32>,
    @location(2) instance_data: vec4<f32>,
}

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) tex_coords: vec2<f32>,
    @location(1) @interpolate(flat) frame_index: u32,
}

@vertex
fn vs_main(in: VertexInput) -> VertexOutput {
    let world_pos = vec4<f32>(
        in.position * in.instance_data.w + in.instance_data.xy,
        0.0,
        1.0
    );

    var out: VertexOutput;
    out.position = uniforms.view_proj * world_pos;
    out.tex_coords = in.tex_coords + vec2<f32>(in.instance_data.z, 0.0);
    out.frame_index = u32(in.instance_data.z);
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let color = textureSample(tex, tex_sampler, in.tex_coords);
    if color.a < 0.1 {
        discard;
    }
    return color;
}
"#;