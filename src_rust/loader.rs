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
    pub speed: f32,
    pub duration_right: f32,
    pub duration_left: f32,
    pub delay: f32,
    pub sprite_right: String,
    pub sprite_left: String,
    pub movement_type: String,
    pub next_animation: String,
    pub effect: String,
    pub sound: String,
    pub repeat: bool,
    pub offset_x: f32,
    pub offset_y: f32,
    pub target_pony: String,
    pub draggable: bool,
    pub transition: String,
    pub next_after: String,
    pub location_right: (f32, f32),
    pub location_left: (f32, f32),
    pub freeze_time: bool,
    pub frequency: f32,
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
    let mut q = false;
    let mut b: i32 = 0;
    for c in line.chars() {
        match c {
            '"' if b == 0 => q = !q,
            '{' => b += 1,
            '}' => b = b.saturating_sub(1),
            ',' if !q && b == 0 => {
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
    if s.starts_with('"') && s.ends_with('"') { s[1..s.len()-1].into() } else { s.into() }
}

fn parse_f32(s: &str) -> f32 { unquote(s).parse().unwrap_or(0.0) }
fn parse_bool(s: &str) -> bool { matches!(unquote(s).to_lowercase().as_str(), "true" | "1" | "yes") }

fn parse_pair(s: &str) -> (f32, f32) {
    let s = unquote(s);
    let p: Vec<&str> = s.split(',').collect();
    if p.len() >= 2 {
        (p[0].trim().parse().unwrap_or(0.0), p[1].trim().parse().unwrap_or(0.0))
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
        Self {
            ponies_dir: base_path.as_ref().join("Content").join("Ponies"),
            configs: Vec::new(),
        }
    }

    pub fn load_all(&mut self) -> Result<(), String> {
        let dir = self.ponies_dir.clone(); // клонируем путь

        if !dir.exists() {
            return Err(format!("Ponies dir not found: {:?}", dir));
        }

        self.configs.clear();
        self.scan_dir(&dir)?; // передаём клон, а не self.ponies_dir

        if self.configs.is_empty() {
            return Err("No pony.ini files found".to_string());
        }

        self.configs.sort_by(|a, b| a.name.cmp(&b.name));
        Ok(())
    }

    fn scan_dir(&mut self, dir: &Path) -> Result<(), String> {
        let entries = fs::read_dir(dir).map_err(|e| format!("Read dir {}: {}", dir.display(), e))?;

        for entry in entries {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();

            if path.is_dir() {
                // Заходим в подпапку
                self.scan_dir(&path)?;
            } else if path.file_name().and_then(|n| n.to_str()) == Some("pony.ini") {
                // Нашли pony.ini — парсим папку, в которой он лежит
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
                "Name" => { /* name уже взят из папки */ }

                "Categories" => {
                    categories = fields[1..].iter().map(|f| unquote(f)).filter(|s| !s.is_empty()).collect();
                }

                "Behavior" if fields.len() >= 22 => {
                    behaviors.push(Behavior {
                        name: unquote(&fields[1]),
                        speed: parse_f32(&fields[2]),
                        duration_right: parse_f32(&fields[3]),
                        duration_left: parse_f32(&fields[4]),
                        delay: parse_f32(&fields[5]),
                        sprite_right: unquote(&fields[6]),
                        sprite_left: unquote(&fields[7]),
                        movement_type: unquote(&fields[8]),
                        next_animation: unquote(&fields[9]),
                        effect: unquote(&fields[10]),
                        sound: unquote(&fields[11]),
                        repeat: parse_bool(&fields[12]),
                        offset_x: parse_f32(&fields[13]),
                        offset_y: parse_f32(&fields[14]),
                        target_pony: unquote(&fields[15]),
                        draggable: parse_bool(&fields[16]),
                        transition: unquote(&fields[17]),
                        next_after: unquote(&fields[18]),
                        location_right: parse_pair(&fields[19]),
                        location_left: parse_pair(&fields[20]),
                        freeze_time: parse_bool(&fields[21]),
                        frequency: fields.get(22).map(|f| parse_f32(f)).unwrap_or(0.0),
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

        Ok(PonyConfig { name, categories, directory: dir.to_path_buf(), behaviors, speaks, interactions, effects })
    }
}