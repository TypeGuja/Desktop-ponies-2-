// src_rust/loader.rs
// src_rust/loader.rs
// src_rust/loader.rs

use std::fs;
use std::path::{Path, PathBuf};
use serde::Serialize;

#[derive(Clone, Debug)]
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
    pub probability: f32,          // "Chance"
    pub max_duration: f32,         // "Max Duration"
    pub min_duration: f32,         // "Min Duration"
    pub speed: f32,                // "Speed"
    pub sprite_right: String,      // "Right Image"
    pub sprite_left: String,       // "Left Image"
    pub movement: String,          // "Movement"
    pub linked_behavior: String,   // "Linked Behavior"
    pub start_speech: String,      // "Start Speech"
    pub end_speech: String,        // "End Speech"
    pub skip: bool,                // "Skip"
    pub target_x: f32,             // "Target X"
    pub target_y: f32,             // "Target Y"
    pub follow_target: bool,       // "Follow Target"
    pub auto_select_follow: bool,  // "Auto Select Follow Images"
    pub follow_stopped: String,    // "Follow Stopped Behavior"
    pub follow_moving: String,     // "Follow Moving Behavior"
    pub right_image_center: (f32, f32), // "Right Image Center"
    pub left_image_center: (f32, f32),  // "Left Image Center"
    pub prevent_loop: bool,        // "Prevent Animation Loop"
    pub group: String,             // "Group"
    pub follow_offset: String,     // "Follow Offset Type"
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
}

impl MovementType {
    pub fn parse(s: &str) -> Self {
        match s.trim().to_lowercase().as_str() {
            "" | "none" => MovementType::None,
            "all" => MovementType::All,
            "horizontal_only" | "horizontalonly" => MovementType::HorizontalOnly,
            "vertical_only" | "verticalonly" => MovementType::VerticalOnly,
            "diagonal_only" | "diagonalonly" => MovementType::DiagonalOnly,
            "diagonal_horizontal" | "diagonalhorizontal" => MovementType::DiagonalHorizontal,
            "sleep" => MovementType::Sleep,
            "dragged" => MovementType::Dragged,
            _ => MovementType::None,
        }
    }
}

// ── CSV splitter ────────────────────────────────────────────
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

// ── Loader ──────────────────────────────────────────────────
impl DesktopPoniesLoader {
    pub fn new<P: AsRef<Path>>(base_path: P) -> Self {
        let base = base_path.as_ref();

        // Нормализуем базовый путь
        let current_dir = if base == Path::new(".") || base == Path::new("") {
            std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
        } else {
            base.to_path_buf()
        };

        // Список папок для проверки (по порядку)
        let candidates = vec![
            current_dir.join("..").join("Ponies"),
            current_dir.join("Ponies"),
            PathBuf::from("../Ponies"),
            PathBuf::from("./Ponies"),
        ];

        // Ищем первую существующую папку
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
        println!("Scanning for ponies in: {:?}", self.ponies_dir);
        self.scan_dir(&self.ponies_dir.clone())?;

        if self.configs.is_empty() {
            return Err(format!("No pony.ini files found in {:?}", self.ponies_dir));
        }

        self.configs.sort_by(|a, b| a.name.cmp(&b.name));
        println!("Successfully loaded {} ponies:", self.configs.len());
        for pony in &self.configs {
            println!("  - {} ({} behaviors, {} speaks)",
                     pony.name, pony.behaviors.len(), pony.speaks.len());
        }
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

                // Новый формат Behavior с 24 полями
                "Behavior" if fields.len() >= 24 => {
                    behaviors.push(Behavior {
                        name: unquote(&fields[1]),                    // "Identifier"
                        probability: parse_f32(&fields[2]),           // "Chance"
                        max_duration: parse_f32(&fields[3]),          // "Max Duration"
                        min_duration: parse_f32(&fields[4]),          // "Min Duration"
                        speed: parse_f32(&fields[5]),                 // "Speed"
                        sprite_right: unquote(&fields[6]),            // "Right Image"
                        sprite_left: unquote(&fields[7]),             // "Left Image"
                        movement: unquote(&fields[8]),                // "Movement"
                        linked_behavior: unquote(&fields[9]),         // "Linked Behavior"
                        start_speech: unquote(&fields[10]),           // "Start Speech"
                        end_speech: unquote(&fields[11]),             // "End Speech"
                        skip: parse_bool(&fields[12]),                // "Skip"
                        target_x: parse_f32(&fields[13]),             // "Target X"
                        target_y: parse_f32(&fields[14]),             // "Target Y"
                        follow_target: parse_bool(&fields[15]),       // "Follow Target"
                        auto_select_follow: parse_bool(&fields[16]),  // "Auto Select Follow Images"
                        follow_stopped: unquote(&fields[17]),         // "Follow Stopped Behavior"
                        follow_moving: unquote(&fields[18]),          // "Follow Moving Behavior"
                        right_image_center: parse_pair(&fields[19]),  // "Right Image Center"
                        left_image_center: parse_pair(&fields[20]),   // "Left Image Center"
                        prevent_loop: parse_bool(&fields[21]),        // "Prevent Animation Loop"
                        group: unquote(&fields[22]),                  // "Group"
                        follow_offset: unquote(&fields[23]),          // "Follow Offset Type"
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
}