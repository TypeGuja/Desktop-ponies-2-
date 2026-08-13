// src_rust/loader.rs
use std::fs;
use std::path::{Path, PathBuf};
use std::collections::HashMap;
use image::AnimationDecoder;
use serde::{Serialize, Deserialize};

// ==================== НОВАЯ СТРУКТУРА ДЛЯ АНИМАЦИИ ====================

#[derive(Clone)]
pub struct GifFrameData {
    pub data: Vec<u32>,           // BGRA данные
    pub delay: f32,               // Индивидуальная задержка кадра в секундах
}

#[derive(Clone)]
pub struct GifAnimation {
    pub frames: Vec<GifFrameData>, // Все кадры с их задержками
    pub width: u32,
    pub height: u32,
    pub default_delay: f32,        // Запасная задержка
}

// ==================== ENUMS ====================

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum MovementType {
    None,
    All,
    HorizontalOnly,
    VerticalOnly,
    DiagonalOnly,
    DiagonalHorizontal,
    // ИСПРАВЛЕНО: в оригинале (Pony.vb, AllowedMoves) есть ещё два составных
    // типа движения — HorizontalVertical (горизонталь+вертикаль, без
    // диагонали) и DiagonalVertical (диагональ+вертикаль). Их не было в этом
    // enum'е вообще, из-за чего парсер (см. parse() ниже) не узнавал строки
    // "Horizontal_Vertical"/"Diagonal_Vertical" из pony.ini и тихо превращал
    // такое поведение в MovementType::None — пони с таким movement вообще
    // переставал двигаться (стоял на месте), хотя по .ini обязан был ходить.
    HorizontalVertical,
    DiagonalVertical,
    Sleep,
    Dragged,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum TargetMode {
    None,
    Pony,
    Point,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum FollowOffsetType {
    Fixed,
    Mirror,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum TargetActivation {
    One,
    Any,
    All,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum Direction {
    TopLeft,
    TopCenter,
    TopRight,
    MiddleLeft,
    MiddleCenter,
    MiddleRight,
    BottomLeft,
    BottomCenter,
    BottomRight,
}

impl Direction {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "topleft" | "top left" => Direction::TopLeft,
            "topcenter" | "top center" => Direction::TopCenter,
            "topright" | "top right" => Direction::TopRight,
            "middleleft" | "middle left" => Direction::MiddleLeft,
            "middlecenter" | "middle center" => Direction::MiddleCenter,
            "middleright" | "middle right" => Direction::MiddleRight,
            "bottomleft" | "bottom left" => Direction::BottomLeft,
            "bottomcenter" | "bottom center" => Direction::BottomCenter,
            "bottomright" | "bottom right" => Direction::BottomRight,
            _ => Direction::MiddleCenter,
        }
    }

    pub fn to_display_string(&self) -> String {
        match self {
            Direction::TopLeft => "Top Left".to_string(),
            Direction::TopCenter => "Top Center".to_string(),
            Direction::TopRight => "Top Right".to_string(),
            Direction::MiddleLeft => "Middle Left".to_string(),
            Direction::MiddleCenter => "Middle Center".to_string(),
            Direction::MiddleRight => "Middle Right".to_string(),
            Direction::BottomLeft => "Bottom Left".to_string(),
            Direction::BottomCenter => "Bottom Center".to_string(),
            Direction::BottomRight => "Bottom Right".to_string(),
        }
    }
}

// ==================== STRUCTS ====================

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
    pub set_animation_speed: Option<f32>,
    pub set_fps: Option<f32>,
    pub set_max_fps: Option<f32>,
    pub sound_files: Vec<String>,
    pub target_mode: TargetMode,
    pub target_vector: (i32, i32),
    pub follow_target_name: String,
    pub auto_select_images_on_follow: bool,
    pub follow_moving_behavior: String,
    pub follow_stopped_behavior: String,
    pub follow_offset_type: FollowOffsetType,
    pub do_not_repeat_animations: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct SpeakDef {
    pub name: String,
    pub text: String,
    pub sound_files: Vec<String>,
    pub skip: bool,
    pub frequency: f32,
    pub group: i32,
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
    pub activation: TargetActivation,
    pub reactivation_delay: f32,
    pub initiator_name: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct EffectDef {
    pub name: String,
    pub linked: String,
    pub sprite_right: String,
    pub sprite_left: String,
    pub duration: f32,
    pub delay: f32,
    pub placement_right: Direction,
    pub placement_left: Direction,
    pub centering_right: Direction,
    pub centering_left: Direction,
    pub follow: bool,
    pub repeat_delay: f32,
    pub do_not_repeat_animations: bool,
    pub behavior_name: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct PonyConfig {
    pub name: String,
    pub display_name: String,
    pub categories: Vec<String>,
    pub tags: Vec<String>,
    pub directory: PathBuf,
    pub behaviors: Vec<Behavior>,
    pub speaks: Vec<SpeakDef>,
    pub interactions: Vec<InteractionDef>,
    pub effects: Vec<EffectDef>,
    pub behavior_groups: HashMap<i32, String>,
}

// ==================== ПАРСИНГ CSV ====================

fn remove_bom(s: &str) -> &str {
    if s.starts_with('\u{FEFF}') {
        &s[3..]
    } else {
        s
    }
}

fn split_csv(line: &str) -> Vec<String> {
    let line = remove_bom(line);
    let mut fields = vec![];
    let mut cur = String::new();
    let mut in_quotes = false;
    let mut escape = false;
    let mut brace_depth: i32 = 0;

    let chars: Vec<char> = line.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let c = chars[i];

        match c {
            '\\' if in_quotes => {
                escape = true;
                cur.push(c);
                i += 1;
                continue;
            }
            '"' if !escape && brace_depth == 0 => {
                in_quotes = !in_quotes;
                cur.push(c);
                i += 1;
                continue;
            }
            '{' => {
                brace_depth += 1;
                cur.push(c);
            }
            '}' => {
                brace_depth = brace_depth.saturating_sub(1);
                cur.push(c);
            }
            ',' if !in_quotes && brace_depth == 0 => {
                fields.push(cur.trim().to_string());
                cur.clear();
                i += 1;
                continue;
            }
            _ => {
                escape = false;
                cur.push(c);
            }
        }
        i += 1;
    }

    fields.push(cur.trim().to_string());

    for field in &mut fields {
        if field.starts_with('"') && field.ends_with('"') && field.len() >= 2 {
            *field = field[1..field.len()-1].to_string();
        }
    }

    fields
}

fn unquote(s: &str) -> String {
    let s = s.trim();
    if s.starts_with('"') && s.ends_with('"') && s.len() >= 2 {
        s[1..s.len()-1].to_string()
    } else {
        s.to_string()
    }
}

fn parse_f32(s: &str) -> f32 {
    let cleaned = unquote(s);
    if cleaned.is_empty() {
        0.0
    } else {
        cleaned.parse().unwrap_or(0.0)
    }
}

fn parse_i32(s: &str) -> i32 {
    let cleaned = unquote(s);
    if cleaned.is_empty() {
        0
    } else {
        cleaned.parse().unwrap_or(0)
    }
}

fn parse_optional_f32(s: &str) -> Option<f32> {
    let cleaned = unquote(s);
    if cleaned.is_empty() {
        None
    } else {
        cleaned.parse().ok()
    }
}

fn parse_bool(s: &str) -> bool {
    let cleaned = unquote(s).to_lowercase();
    matches!(cleaned.as_str(), "true" | "1" | "yes" | "on")
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

fn parse_vector(s: &str) -> (i32, i32) {
    let s = unquote(s);
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() >= 2 {
        (parts[0].trim().parse().unwrap_or(0),
         parts[1].trim().parse().unwrap_or(0))
    } else {
        (0, 0)
    }
}

fn parse_list(s: &str) -> Vec<String> {
    let s = unquote(s);
    if s.starts_with('{') && s.ends_with('}') {
        s[1..s.len()-1]
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

fn parse_target_mode(s: &str) -> TargetMode {
    let cleaned = unquote(s).to_lowercase();
    if cleaned.contains("pony") {
        TargetMode::Pony
    } else if cleaned.contains("point") {
        TargetMode::Point
    } else {
        TargetMode::None
    }
}

fn parse_follow_offset(s: &str) -> FollowOffsetType {
    let cleaned = unquote(s).to_lowercase();
    if cleaned.contains("mirror") {
        FollowOffsetType::Mirror
    } else {
        FollowOffsetType::Fixed
    }
}

fn parse_target_activation(s: &str) -> TargetActivation {
    match s.to_lowercase().as_str() {
        "any" => TargetActivation::Any,
        "all" => TargetActivation::All,
        _ => TargetActivation::One,
    }
}

fn parse_direction(s: &str) -> Direction {
    Direction::from_str(s)
}

fn get_field(fields: &[String], idx: usize, default: &str) -> String {
    if idx < fields.len() {
        fields[idx].clone()
    } else {
        default.to_string()
    }
}

fn is_garbage_line(line: &str) -> bool {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return true;
    }
    if trimmed.starts_with('{') {
        return true;
    }
    if trimmed.contains("Identifier") && trimmed.contains("Name") && trimmed.contains("Chance") {
        return true;
    }
    let known_types = ["Behavior", "Speak", "Interaction", "Effect", "Categories", "Name", "Groups", "Tags"];
    let first_field = trimmed.split(',').next().unwrap_or("").trim().trim_matches('"');
    if !known_types.contains(&first_field) && !first_field.is_empty() {
        if first_field.chars().any(|c| c.is_digit(10) || c == '{' || c == '}') {
            return true;
        }
    }
    false
}

// ==================== ОСНОВНОЙ ЗАГРУЗЧИК ====================

pub struct DesktopPoniesLoader {
    pub ponies_dir: PathBuf,
    pub configs: Vec<PonyConfig>,
    pub sprite_cache: HashMap<String, GifAnimation>,
}

impl MovementType {
    pub fn parse(s: &str) -> Self {
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
            // ДОБАВЛЕНО: раньше эти два варианта проваливались в `_` (None)
            // — см. комментарий у enum MovementType выше.
            "horizontalvertical" | "verticalhorizontal" => MovementType::HorizontalVertical,
            "diagonalvertical" | "verticaldiagonal" => MovementType::DiagonalVertical,
            "sleep" => MovementType::Sleep,
            "dragged" => MovementType::Dragged,
            _ => {
                eprintln!("[Warning] Unknown movement type: '{}'", s);
                MovementType::None
            }
        }
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

        let ponies_dir_clone = self.ponies_dir.clone();
        self.scan_dir(&ponies_dir_clone)?;

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
                    Ok(cfg) => {
                        println!("[Loader] Loaded config for: {} ({} behaviors, {} speaks, {} interactions, {} effects)",
                                 cfg.name, cfg.behaviors.len(), cfg.speaks.len(), cfg.interactions.len(), cfg.effects.len());
                        self.configs.push(cfg);
                    }
                    Err(e) => eprintln!("Parse error {}: {}", parent.display(), e),
                }
            }
        }
        Ok(())
    }

    fn parse_config(dir: &Path, ini: &Path) -> Result<PonyConfig, String> {
        let content = fs::read_to_string(ini).map_err(|e| e.to_string())?;
        let content = remove_bom(&content);

        let name = dir.file_name().and_then(|n| n.to_str()).unwrap_or("??").to_string();
        let mut display_name = name.clone();
        let mut categories = Vec::new();
        let mut tags = Vec::new();
        let mut behaviors = Vec::new();
        let mut speaks = Vec::new();
        let mut interactions = Vec::new();
        let mut effects = Vec::new();
        let mut behavior_groups = HashMap::new();

        behavior_groups.insert(0, "Any".to_string());

        for (_line_num, raw_line) in content.lines().enumerate() {
            let line = raw_line.trim();
            if is_garbage_line(line) {
                continue;
            }

            let fields = split_csv(line);
            if fields.is_empty() {
                continue;
            }

            let row_type = fields[0].trim().trim_matches('"');

            match row_type {
                "Categories" => {
                    categories = fields[1..].iter()
                        .map(|f| unquote(f))
                        .filter(|s| !s.is_empty())
                        .collect();
                }
                "Name" => {
                    if fields.len() > 1 {
                        display_name = unquote(&fields[1]);
                    }
                }
                "Tags" => {
                    tags = fields[1..].iter()
                        .map(|f| unquote(f))
                        .filter(|s| !s.is_empty())
                        .collect();
                }
                "Groups" => {
                    for field in &fields[1..] {
                        let parts: Vec<&str> = field.split('=').collect();
                        if parts.len() >= 2 {
                            if let Ok(num) = parts[0].trim().parse::<i32>() {
                                let name_val = unquote(parts[1].trim());
                                behavior_groups.insert(num, name_val);
                            }
                        }
                    }
                }
                "Behavior" => {
                    if fields.len() >= 13 {
                        let behavior = Behavior {
                            name: get_field(&fields, 1, ""),
                            probability: if fields.len() > 2 { parse_f32(&fields[2]) } else { 1.0 },
                            max_duration: if fields.len() > 3 { parse_f32(&fields[3]) } else { 10.0 },
                            min_duration: if fields.len() > 4 { parse_f32(&fields[4]) } else { 5.0 },
                            speed: if fields.len() > 5 { parse_f32(&fields[5]) } else { 0.0 },
                            sprite_right: get_field(&fields, 6, ""),
                            sprite_left: get_field(&fields, 7, ""),
                            movement: get_field(&fields, 8, "None"),
                            linked_behavior: get_field(&fields, 9, ""),
                            start_speech: get_field(&fields, 10, ""),
                            end_speech: get_field(&fields, 11, ""),
                            skip: if fields.len() > 12 { parse_bool(&fields[12]) } else { false },
                            target_x: if fields.len() > 13 { parse_f32(&fields[13]) } else { 0.0 },
                            target_y: if fields.len() > 14 { parse_f32(&fields[14]) } else { 0.0 },
                            follow_target: if fields.len() > 15 { parse_bool(&fields[15]) } else { false },
                            auto_select_follow: if fields.len() > 16 { parse_bool(&fields[16]) } else { false },
                            follow_stopped: get_field(&fields, 17, ""),
                            follow_moving: get_field(&fields, 18, ""),
                            right_image_center: if fields.len() > 19 { parse_pair(&fields[19]) } else { (0.0, 0.0) },
                            left_image_center: if fields.len() > 20 { parse_pair(&fields[20]) } else { (0.0, 0.0) },
                            prevent_loop: if fields.len() > 21 { parse_bool(&fields[21]) } else { false },
                            group: get_field(&fields, 22, "0"),
                            follow_offset: get_field(&fields, 23, ""),
                            set_animation_speed: if fields.len() > 24 { parse_optional_f32(&fields[24]) } else { None },
                            set_fps: if fields.len() > 25 { parse_optional_f32(&fields[25]) } else { None },
                            set_max_fps: if fields.len() > 26 { parse_optional_f32(&fields[26]) } else { None },
                            sound_files: if fields.len() > 27 { parse_list(&fields[27]) } else { vec![] },
                            target_mode: if fields.len() > 28 { parse_target_mode(&fields[28]) } else { TargetMode::None },
                            target_vector: if fields.len() > 29 { parse_vector(&fields[29]) } else { (0, 0) },
                            follow_target_name: get_field(&fields, 30, ""),
                            auto_select_images_on_follow: if fields.len() > 31 { parse_bool(&fields[31]) } else { true },
                            follow_moving_behavior: get_field(&fields, 32, ""),
                            follow_stopped_behavior: get_field(&fields, 33, ""),
                            follow_offset_type: if fields.len() > 34 { parse_follow_offset(&fields[34]) } else { FollowOffsetType::Fixed },
                            do_not_repeat_animations: if fields.len() > 35 { parse_bool(&fields[35]) } else { false },
                        };
                        behaviors.push(behavior);
                    }
                }
                "Speak" => {
                    if fields.len() >= 3 {
                        speaks.push(SpeakDef {
                            name: get_field(&fields, 1, ""),
                            text: get_field(&fields, 2, ""),
                            sound_files: if fields.len() > 3 { parse_list(&fields[3]) } else { vec![] },
                            skip: if fields.len() > 4 { parse_bool(&fields[4]) } else { false },
                            frequency: if fields.len() > 5 { parse_f32(&fields[5]) } else { 0.0 },
                            group: if fields.len() > 6 { parse_i32(&fields[6]) } else { 0 },
                        });
                    }
                }
                "Interaction" => {
                    if fields.len() >= 3 {
                        interactions.push(InteractionDef {
                            name: get_field(&fields, 1, ""),
                            probability: if fields.len() > 2 { parse_f32(&fields[2]) } else { 0.0 },
                            cooldown: if fields.len() > 3 { parse_f32(&fields[3]) } else { 0.0 },
                            targets: if fields.len() > 4 { parse_list(&fields[4]) } else { vec![] },
                            target_count: get_field(&fields, 5, "One"),
                            behaviors: if fields.len() > 6 { parse_list(&fields[6]) } else { vec![] },
                            duration: if fields.len() > 7 { parse_f32(&fields[7]) } else { 300.0 },
                            activation: if fields.len() > 8 { parse_target_activation(&fields[8]) } else { TargetActivation::One },
                            reactivation_delay: if fields.len() > 9 { parse_f32(&fields[9]) } else { 0.0 },
                            initiator_name: get_field(&fields, 10, ""),
                        });
                    }
                }
                "Effect" => {
                    if fields.len() >= 3 {
                        effects.push(EffectDef {
                            name: get_field(&fields, 1, ""),
                            linked: get_field(&fields, 2, ""),
                            sprite_right: get_field(&fields, 3, ""),
                            sprite_left: get_field(&fields, 4, ""),
                            duration: if fields.len() > 5 { parse_f32(&fields[5]) } else { 0.0 },
                            delay: if fields.len() > 6 { parse_f32(&fields[6]) } else { 0.0 },
                            placement_right: if fields.len() > 7 { parse_direction(&fields[7]) } else { Direction::MiddleCenter },
                            placement_left: if fields.len() > 8 { parse_direction(&fields[8]) } else { Direction::MiddleCenter },
                            centering_right: if fields.len() > 9 { parse_direction(&fields[9]) } else { Direction::MiddleCenter },
                            centering_left: if fields.len() > 10 { parse_direction(&fields[10]) } else { Direction::MiddleCenter },
                            follow: if fields.len() > 11 { parse_bool(&fields[11]) } else { false },
                            repeat_delay: if fields.len() > 12 { parse_f32(&fields[12]) } else { 0.0 },
                            do_not_repeat_animations: if fields.len() > 13 { parse_bool(&fields[13]) } else { false },
                            behavior_name: get_field(&fields, 14, ""),
                        });
                    }
                }
                _ => {}
            }
        }

        Ok(PonyConfig {
            name,
            display_name,
            categories,
            tags,
            directory: dir.to_path_buf(),
            behaviors,
            speaks,
            interactions,
            effects,
            behavior_groups,
        })
    }

    // ==================== НОВАЯ ВЕРСИЯ ЗАГРУЗКИ GIF ====================

    fn load_gif_animation(&self, path: &Path) -> GifAnimation {
        let mut animation = GifAnimation {
            frames: Vec::new(),
            width: 0,
            height: 0,
            default_delay: 0.1,
        };

        if let Ok(bytes) = std::fs::read(path) {
            if let Ok(decoder) = image::codecs::gif::GifDecoder::new(std::io::Cursor::new(&bytes)) {
                let frames_data: Vec<_> = decoder.into_frames()
                    .filter_map(|f| f.ok())
                    .collect();

                if !frames_data.is_empty() {
                    let w = frames_data[0].buffer().width();
                    let h = frames_data[0].buffer().height();
                    let mut delays = Vec::new();

                    for frame in frames_data {
                        // Получаем задержку кадра из GIF
                        let (numer, denom) = frame.delay().numer_denom_ms();
                        let delay_secs = if numer > 0 && denom > 0 {
                            (numer as f32 / denom as f32) / 1000.0
                        } else {
                            0.1 // Задержка по умолчанию
                        };
                        let delay_secs = delay_secs.max(0.03).min(0.5); // Ограничиваем
                        delays.push(delay_secs);

                        // Получаем RGBA данные
                        let rgba = frame.into_buffer();
                        let rgba_data = rgba.into_raw();

                        // Конвертируем RGBA в ARGB (формат для softbuffer)
                        let argb: Vec<u32> = rgba_data.chunks(4).map(|p| {
                            let r = p[0] as u32;
                            let g = p[1] as u32;
                            let b = p[2] as u32;
                            let a = p[3] as u32;
                            // ARGB: alpha в старший байт
                            (a << 24) | (r << 16) | (g << 8) | b
                        }).collect();

                        animation.frames.push(GifFrameData {
                            data: argb,
                            delay: delay_secs,
                        });
                    }

                    animation.width = w;
                    animation.height = h;

                    // Устанавливаем задержку по умолчанию (средняя)
                    if !delays.is_empty() {
                        delays.sort_by(|a, b| a.partial_cmp(b).unwrap());
                        animation.default_delay = delays[delays.len() / 2];
                    }
                }
            }
        }

        // Фолбэк для отладки
        if animation.frames.is_empty() {
            let fallback_data = vec![0xFFFF0000u32; 64 * 64];
            animation.frames.push(GifFrameData {
                data: fallback_data,
                delay: 0.1,
            });
            animation.width = 64;
            animation.height = 64;
            animation.default_delay = 0.1;
            eprintln!("[Warning] Failed to load GIF: {:?}", path);
        }

        animation
    }
    pub fn load_pony_frames(&mut self, pony_name: &str, sprite_name: &str) -> GifAnimation {
        let cache_key = format!("{}/{}", pony_name, sprite_name);

        if let Some(cached) = self.sprite_cache.get(&cache_key) {
            return cached.clone();
        }

        let pony_dir = self.ponies_dir.join(pony_name);
        let animation = if pony_dir.exists() {
            let mut found = None;

            // Убираем расширение .gif для поиска
            let sprite_base = sprite_name
                .trim_end_matches(".gif")
                .trim_end_matches(".GIF");

            println!("[Loader] Looking for sprite: '{}' (base: '{}') in {:?}",
                     sprite_name, sprite_base, pony_dir);

            if let Ok(entries) = std::fs::read_dir(&pony_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.extension().and_then(|e| e.to_str()) == Some("gif") {
                        let filename = path.file_stem()
                            .and_then(|n| n.to_str())
                            .unwrap_or("")
                            .to_string();

                        let full_filename = path.file_name()
                            .and_then(|n| n.to_str())
                            .unwrap_or("")
                            .to_string();

                        println!("[Loader] Checking file: '{}' (stem: '{}')", full_filename, filename);

                        // Сравниваем:
                        // 1. По полному имени (с расширением)
                        // 2. По stem (без расширения)
                        // 3. По base (без учёта регистра)
                        if full_filename == sprite_name ||
                            filename == sprite_name ||
                            filename == sprite_base ||
                            filename.to_lowercase() == sprite_base.to_lowercase() {
                            println!("[Loader] ✓ Found match: {:?}", path);
                            found = Some(path.clone());  // ← clone() здесь!
                            break;
                        }
                    }
                }
            }

            if let Some(path) = found {
                self.load_gif_animation(&path)
            } else {
                // Пробуем найти файл напрямую
                let exact_path = pony_dir.join(&sprite_name);
                if exact_path.exists() {
                    println!("[Loader] ✓ Found exact path: {:?}", exact_path);
                    self.load_gif_animation(&exact_path)
                } else {
                    // Пробуем добавить .gif
                    let with_ext = pony_dir.join(format!("{}.gif", sprite_base));
                    if with_ext.exists() {
                        println!("[Loader] ✓ Found with .gif: {:?}", with_ext);
                        self.load_gif_animation(&with_ext)
                    } else {
                        eprintln!("[Loader] ✗ Sprite '{}' not found for pony '{}' in {:?}",
                                  sprite_name, pony_name, pony_dir);
                        self.create_fallback_animation()
                    }
                }
            }
        } else {
            eprintln!("[Loader] ✗ Pony directory not found: {:?}", pony_dir);
            self.create_fallback_animation()
        };

        self.sprite_cache.insert(cache_key, animation.clone());
        animation
    }

    fn create_fallback_animation(&self) -> GifAnimation {
        let fallback_data = vec![0xFFFF0000u32; 64 * 64];
        GifAnimation {
            frames: vec![GifFrameData {
                data: fallback_data,
                delay: 0.1,
            }],
            width: 64,
            height: 64,
            default_delay: 0.1,
        }
    }

    pub fn get_config(&self, name: &str) -> Option<&PonyConfig> {
        self.configs.iter().find(|c| c.name == name)
    }

    pub fn get_config_by_name_case_insensitive(&self, name: &str) -> Option<&PonyConfig> {
        let name_lower = name.to_lowercase();
        self.configs.iter().find(|c| c.name.to_lowercase() == name_lower)
    }

    pub fn get_random_pony_config(&self) -> Option<&PonyConfig> {
        if self.configs.is_empty() {
            None
        } else {
            let idx = fastrand::usize(0..self.configs.len());
            Some(&self.configs[idx])
        }
    }

    pub fn get_ponies_by_category(&self, category: &str) -> Vec<&PonyConfig> {
        let cat_lower = category.to_lowercase();
        self.configs.iter()
            .filter(|c| c.categories.iter().any(|cat| cat.to_lowercase() == cat_lower))
            .collect()
    }

    pub fn get_all_behavior_names(&self, pony_name: &str) -> Vec<String> {
        if let Some(config) = self.get_config(pony_name) {
            config.behaviors.iter()
                .filter(|b| !b.skip)
                .map(|b| b.name.clone())
                .collect()
        } else {
            vec![]
        }
    }

    pub fn get_random_behavior(&self, pony_name: &str, exclude: &[&str]) -> Option<Behavior> {
        let config = self.get_config(pony_name)?;
        let mut available: Vec<Behavior> = config.behaviors.iter()
            .filter(|b| !b.skip && !exclude.contains(&b.name.as_str()))
            .cloned()
            .collect();

        if available.is_empty() {
            available = config.behaviors.iter()
                .filter(|b| !b.skip)
                .cloned()
                .collect();
        }

        if available.is_empty() {
            None
        } else {
            let total_prob: f32 = available.iter().map(|b| b.probability).sum();
            if total_prob > 0.0 {
                let mut rand_val = fastrand::f32() * total_prob;
                for behavior in &available {
                    rand_val -= behavior.probability;
                    if rand_val <= 0.0 {
                        return Some(behavior.clone());
                    }
                }
            }
            Some(available[0].clone())
        }
    }

    pub fn get_speak_text(&self, pony_name: &str, speak_name: &str) -> Option<String> {
        let config = self.get_config(pony_name)?;
        config.speaks.iter()
            .find(|s| s.name == speak_name && !s.skip)
            .map(|s| s.text.clone())
    }

    pub fn get_random_speak(&self, pony_name: &str) -> Option<String> {
        let config = self.get_config(pony_name)?;
        let available: Vec<&SpeakDef> = config.speaks.iter()
            .filter(|s| !s.skip)
            .collect();

        if available.is_empty() {
            None
        } else {
            let idx = fastrand::usize(0..available.len());
            Some(available[idx].text.clone())
        }
    }
}