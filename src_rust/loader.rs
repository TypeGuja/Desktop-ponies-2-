// src_rust/loader.rs
use std::fs;
use std::path::{Path, PathBuf};
use std::collections::HashMap;
use image::AnimationDecoder;
use serde::Serialize;

#[derive(Clone, Debug, PartialEq)]
pub enum MovementType {
    None,
    All,
    HorizontalOnly,
    VerticalOnly,
    DiagonalOnly,
    DiagonalHorizontal,
    Sleep,
    Dragged,
}

#[derive(Clone, Debug, Serialize)]
pub struct Behavior {
    pub name: String,
    pub probability: f32,
    pub max_duration: f32,
    pub min_duration: f32,
    pub speed: f32,
    pub sprite_right: String,
    pub sprite_left: String,
    pub movement: String,
    pub linked_behavior: String,
    pub start_speech: String,
    pub end_speech: String,
    pub skip: bool,
    pub target_x: f32,
    pub target_y: f32,
    pub follow_target: bool,
    pub auto_select_follow: bool,
    pub follow_stopped: String,
    pub follow_moving: String,
    pub right_image_center: (f32, f32),
    pub left_image_center: (f32, f32),
    pub prevent_loop: bool,
    pub group: String,
    pub follow_offset: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct SpeakDef {
    pub name: String,
    pub text: String,
    pub sound_files: Vec<String>,
    pub skip: bool,
    pub frequency: f32,
}

#[derive(Clone, Debug, Serialize)]
pub struct InteractionDef {
    pub name: String,
    pub probability: f32,
    pub cooldown: f32,
    pub targets: Vec<String>,
    pub target_count: String,
    pub behaviors: Vec<String>,
    pub duration: f32,
}

#[derive(Clone, Debug, Serialize)]
pub struct EffectDef {
    pub name: String,
    pub linked: String,
    pub sprite_right: String,
    pub sprite_left: String,
    pub duration: f32,
    pub delay: f32,
}

#[derive(Clone, Debug, Serialize)]
pub struct PonyConfig {
    pub name: String,
    pub categories: Vec<String>,
    pub directory: PathBuf,
    pub behaviors: Vec<Behavior>,
    pub speaks: Vec<SpeakDef>,
    pub interactions: Vec<InteractionDef>,
    pub effects: Vec<EffectDef>,
}

pub struct DesktopPoniesLoader {
    pub ponies_dir: PathBuf,
    pub configs: Vec<PonyConfig>,
    pub sprite_cache: HashMap<String, (Vec<Vec<u32>>, u32, u32, u32, f32)>,
}

impl MovementType {
    pub fn parse(s: &str) -> Self {
        // Убираем кавычки, пробелы, приводим к нижнему регистру
        let s = s.trim()
            .trim_matches('"')
            .to_lowercase()
            .replace('_', "")
            .replace('-', "")
            .replace(' ', "");

        match s.as_str() {
            "" | "none" => MovementType::None,
            "all" => MovementType::All,
            "horizontalonly" | "horizontal" | "onlyhorizontal" => MovementType::HorizontalOnly,
            "verticalonly" | "vertical" | "onlyvertical" => MovementType::VerticalOnly,
            "diagonalonly" | "diagonal" | "onlydiagonal" => MovementType::DiagonalOnly,
            "diagonalhorizontal" | "horizontaldiagonal" => MovementType::DiagonalHorizontal,
            "sleep" => MovementType::Sleep,
            "dragged" => MovementType::Dragged,
            _ => {
                eprintln!("[Warning] Unknown movement type: '{}'", s);
                MovementType::None
            }
        }
    }
}

fn split_csv(line: &str) -> Vec<String> {
    let mut fields = vec![];
    let mut cur = String::new();
    let mut in_quotes = false;
    let mut brace_depth: i32 = 0;

    for c in line.chars() {
        match c {
            '"' if brace_depth == 0 => in_quotes = !in_quotes,
            '{' => brace_depth += 1,
            '}' => brace_depth = brace_depth.saturating_sub(1),
            ',' if !in_quotes && brace_depth == 0 => {
                fields.push(cur.trim().to_string());
                cur.clear();
                continue;
            }
            _ => {}
        }
        cur.push(c);
    }
    fields.push(cur.trim().to_string());
    fields
}

fn unquote(s: &str) -> String {
    let s = s.trim();
    if s.starts_with('"') && s.ends_with('"') {
        s[1..s.len()-1].to_string()
    } else {
        s.to_string()
    }
}

fn parse_f32(s: &str) -> f32 {
    unquote(s).parse().unwrap_or(0.0)
}

fn parse_bool(s: &str) -> bool {
    matches!(unquote(s).to_lowercase().as_str(), "true" | "1" | "yes")
}

fn parse_pair(s: &str) -> (f32, f32) {
    let s = unquote(s);
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() >= 2 {
        (parts[0].trim().parse().unwrap_or(0.0),
         parts[1].trim().parse().unwrap_or(0.0))
    } else {
        (0.0, 0.0)
    }
}

fn parse_list(s: &str) -> Vec<String> {
    let s = unquote(s);
    if s.starts_with('{') {
        s.trim_matches(&['{', '}'][..])
            .split(',')
            .map(|x| x.trim().trim_matches('"').to_string())
            .filter(|x| !x.is_empty())
            .collect()
    } else if s.is_empty() {
        vec![]
    } else {
        vec![s]
    }
}

impl DesktopPoniesLoader {
    pub fn new<P: AsRef<Path>>(base_path: P) -> Self {
        let base = base_path.as_ref();

        let current_dir = if base == Path::new(".") || base == Path::new("") {
            std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
        } else {
            base.to_path_buf()
        };

        let candidates = vec![
            current_dir.join("..").join("Ponies"),
            current_dir.join("Ponies"),
            PathBuf::from("../Ponies"),
            PathBuf::from("./Ponies"),
        ];

        let ponies_dir = candidates
            .into_iter()
            .find(|p| p.exists())
            .unwrap_or_else(|| {
                eprintln!("WARNING: No Ponies folder found, using ../Ponies as fallback");
                current_dir.join("..").join("Ponies")
            });

        println!("Ponies folder: {:?}", ponies_dir);

        Self {
            ponies_dir,
            configs: Vec::new(),
            sprite_cache: HashMap::new(),
        }
    }

    pub fn load_all(&mut self) -> Result<(), String> {
        if !self.ponies_dir.exists() {
            return Err(format!("Ponies dir not found: {:?}", self.ponies_dir));
        }
        if !self.ponies_dir.is_dir() {
            return Err(format!("Path is not a directory: {:?}", self.ponies_dir));
        }

        self.configs.clear();
        self.scan_dir(&self.ponies_dir.clone())?;

        if self.configs.is_empty() {
            return Err(format!("No pony.ini files found in {:?}", self.ponies_dir));
        }

        self.configs.sort_by(|a, b| a.name.cmp(&b.name));
        println!("Successfully loaded {} ponies", self.configs.len());
        Ok(())
    }

    fn scan_dir(&mut self, dir: &Path) -> Result<(), String> {
        let entries = fs::read_dir(dir).map_err(|e| format!("Read dir {}: {}", dir.display(), e))?;
        for entry in entries {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_dir() {
                self.scan_dir(&path)?;
            } else if path.file_name().and_then(|n| n.to_str()) == Some("pony.ini") {
                let parent = path.parent().unwrap();
                match Self::parse_config(parent, &path) {
                    Ok(cfg) => self.configs.push(cfg),
                    Err(e) => eprintln!("Parse error {}: {}", parent.display(), e),
                }
            }
        }
        Ok(())
    }

    fn parse_config(dir: &Path, ini: &Path) -> Result<PonyConfig, String> {
        let content = fs::read_to_string(ini).map_err(|e| e.to_string())?;
        let name = dir.file_name().and_then(|n| n.to_str()).unwrap_or("??").to_string();
        let mut categories = Vec::new();
        let mut behaviors = Vec::new();
        let mut speaks = Vec::new();
        let mut interactions = Vec::new();
        let mut effects = Vec::new();

        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') || line.starts_with(';') {
                continue;
            }
            let row_type = line.find(',').map(|i| &line[..i]).unwrap_or("");
            let fields = split_csv(line);

            match row_type {
                "Categories" => {
                    categories = fields[1..].iter()
                        .map(|f| unquote(f))
                        .filter(|s| !s.is_empty())
                        .collect();
                }
                "Behavior" if fields.len() >= 24 => {
                    behaviors.push(Behavior {
                        name: unquote(&fields[1]),
                        probability: parse_f32(&fields[2]),
                        max_duration: parse_f32(&fields[3]),
                        min_duration: parse_f32(&fields[4]),
                        speed: parse_f32(&fields[5]),
                        sprite_right: unquote(&fields[6]),
                        sprite_left: unquote(&fields[7]),
                        movement: unquote(&fields[8]),
                        linked_behavior: unquote(&fields[9]),
                        start_speech: unquote(&fields[10]),
                        end_speech: unquote(&fields[11]),
                        skip: parse_bool(&fields[12]),
                        target_x: parse_f32(&fields[13]),
                        target_y: parse_f32(&fields[14]),
                        follow_target: parse_bool(&fields[15]),
                        auto_select_follow: parse_bool(&fields[16]),
                        follow_stopped: unquote(&fields[17]),
                        follow_moving: unquote(&fields[18]),
                        right_image_center: parse_pair(&fields[19]),
                        left_image_center: parse_pair(&fields[20]),
                        prevent_loop: parse_bool(&fields[21]),
                        group: unquote(&fields[22]),
                        follow_offset: unquote(&fields[23]),
                    });
                }
                "Speak" if fields.len() >= 5 => {
                    speaks.push(SpeakDef {
                        name: unquote(&fields[1]),
                        text: unquote(&fields[2]),
                        sound_files: parse_list(&fields[3]),
                        skip: parse_bool(&fields[4]),
                        frequency: fields.get(5).map(|f| parse_f32(f)).unwrap_or(0.0),
                    });
                }
                "Interaction" if fields.len() >= 7 => {
                    interactions.push(InteractionDef {
                        name: unquote(&fields[1]),
                        probability: parse_f32(&fields[2]),
                        cooldown: parse_f32(&fields[3]),
                        targets: parse_list(&fields[4]),
                        target_count: unquote(&fields[5]),
                        behaviors: parse_list(&fields[6]),
                        duration: fields.get(7).map(|f| parse_f32(f)).unwrap_or(300.0),
                    });
                }
                "Effect" if fields.len() >= 7 => {
                    effects.push(EffectDef {
                        name: unquote(&fields[1]),
                        linked: unquote(&fields[2]),
                        sprite_right: unquote(&fields[3]),
                        sprite_left: unquote(&fields[4]),
                        duration: parse_f32(&fields[5]),
                        delay: parse_f32(&fields[6]),
                    });
                }
                _ => {}
            }
        }

        Ok(PonyConfig {
            name,
            categories,
            directory: dir.to_path_buf(),
            behaviors,
            speaks,
            interactions,
            effects,
        })
    }

    fn load_gif_file(&self, path: &Path) -> (Vec<Vec<u32>>, u32, u32, u32, f32) {
        if let Ok(bytes) = std::fs::read(path) {
            if let Ok(decoder) = image::codecs::gif::GifDecoder::new(std::io::Cursor::new(&bytes)) {
                let frames: Vec<_> = decoder.into_frames()
                    .filter_map(|f: Result<image::Frame, _>| f.ok())
                    .collect();

                if !frames.is_empty() {
                    let w = frames[0].buffer().width();
                    let h = frames[0].buffer().height();
                    let fc = frames.len() as u32;
                    let mut delays = Vec::new();

                    let bgra: Vec<Vec<u32>> = frames.iter().map(|f: &image::Frame| {
                        let (d, _) = f.delay().numer_denom_ms();
                        delays.push(d as f32);
                        f.buffer().chunks(4).map(|p| {
                            ((p[3] as u32) << 24) | ((p[0] as u32) << 16) | ((p[1] as u32) << 8) | (p[2] as u32)
                        }).collect()
                    }).collect();

                    delays.sort_by(|a, b| a.partial_cmp(b).unwrap());
                    let median_delay = if !delays.is_empty() {
                        delays[delays.len() / 2] / 1000.0
                    } else {
                        0.1
                    };

                    let frame_duration = median_delay.max(0.03).min(0.15);

                    return (bgra, fc, w, h, frame_duration);
                }
            }
        }
        Self::fallback_sprite()
    }

    pub fn load_pony_frames(&mut self, pony_name: &str, sprite_name: &str) -> (Vec<Vec<u32>>, u32, u32, u32, f32) {
        let pony_dir = self.ponies_dir.join(pony_name);
        if !pony_dir.exists() {
            return Self::fallback_sprite();
        }

        let exact_path = pony_dir.join(sprite_name);
        if exact_path.exists() {
            return self.load_gif_file(&exact_path);
        }

        let with_ext = pony_dir.join(format!("{}.gif", sprite_name));
        if with_ext.exists() {
            return self.load_gif_file(&with_ext);
        }

        if let Ok(entries) = std::fs::read_dir(&pony_dir) {
            let sprite_lower = sprite_name.to_lowercase();
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) == Some("gif") {
                    let filename = path.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
                    if filename.contains(&sprite_lower) {
                        return self.load_gif_file(&path);
                    }
                }
            }
        }

        Self::fallback_sprite()
    }

    fn fallback_sprite() -> (Vec<Vec<u32>>, u32, u32, u32, f32) {
        (vec![vec![0xFFFF0000u32; 32 * 32]], 1, 32, 32, 0.1)
    }

    pub fn get_config(&self, name: &str) -> Option<&PonyConfig> {
        self.configs.iter().find(|c| c.name == name)
    }
}