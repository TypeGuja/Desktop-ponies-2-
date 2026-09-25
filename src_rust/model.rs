// src_rust/model.rs
//
// Модель данных pony.ini — порт классов PonyBase / Behavior / Speech /
// EffectBase / InteractionBase / HouseBase из оригинального Desktop Ponies
// 1.69 (Pony.vb). Поля и их смысл соответствуют оригиналу; сериализация в .ini
// (get_pony_ini) записывает строки в том же формате, что и оригинальный
// редактор, поэтому файлы остаются совместимыми в обе стороны.

use crate::ini::{braced, quoted};
use crate::math::{round_half_even, V2};
use std::path::{Path, PathBuf};

/// Сравнение имён без учёта регистра (CaseInsensitiveString).
pub fn ci_eq(a: &str, b: &str) -> bool {
    a.eq_ignore_ascii_case(b)
}

pub const ANY_GROUP: i32 = 0;
pub const RANDOM_DIRECTORY: &str = "Random Pony";
pub const STANDARD_TAGS: [&str; 13] = [
    "Main Ponies", "Supporting Ponies", "Alternate Art", "Fillies", "Colts", "Pets",
    "Stallions", "Mares", "Alicorns", "Unicorns", "Pegasi", "Earth Ponies", "Non-Ponies",
];

// ------------------------------------------------------------------ enums

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum Direction {
    TopLeft = 0,
    TopCenter = 1,
    TopRight = 2,
    MiddleLeft = 3,
    MiddleCenter = 4,
    MiddleRight = 5,
    BottomLeft = 6,
    BottomCenter = 8,
    BottomRight = 9,
    Random = 10,
    RandomNotCenter = 11,
}

pub const DIRECTION_TABLE: [(&str, Direction); 11] = [
    ("top_left", Direction::TopLeft),
    ("top", Direction::TopCenter),
    ("top_right", Direction::TopRight),
    ("left", Direction::MiddleLeft),
    ("center", Direction::MiddleCenter),
    ("right", Direction::MiddleRight),
    ("bottom_left", Direction::BottomLeft),
    ("bottom", Direction::BottomCenter),
    ("bottom_right", Direction::BottomRight),
    ("any", Direction::Random),
    ("any-not_center", Direction::RandomNotCenter),
];

impl Direction {
    pub fn to_ini(self) -> &'static str {
        DIRECTION_TABLE.iter().find(|(_, d)| *d == self).map(|(k, _)| *k).unwrap_or("center")
    }
    /// Читаемое имя (для интерфейса редактора).
    pub fn display(self) -> &'static str {
        match self {
            Direction::TopLeft => "Top Left",
            Direction::TopCenter => "Top",
            Direction::TopRight => "Top Right",
            Direction::MiddleLeft => "Left",
            Direction::MiddleCenter => "Center",
            Direction::MiddleRight => "Right",
            Direction::BottomLeft => "Bottom Left",
            Direction::BottomCenter => "Bottom",
            Direction::BottomRight => "Bottom Right",
            Direction::Random => "Any",
            Direction::RandomNotCenter => "Any Except Center",
        }
    }
    pub fn from_any(s: &str) -> Option<Direction> {
        let norm = s.trim().to_ascii_lowercase().replace(' ', "_");
        if let Some((_, d)) = DIRECTION_TABLE.iter().find(|(k, _)| *k == norm) {
            return Some(*d);
        }
        // Имена вариантов enum (TopLeft, MiddleCenter, ...) — из JSON редактора.
        match norm.replace('_', "").as_str() {
            "topleft" => Some(Direction::TopLeft),
            "topcenter" => Some(Direction::TopCenter),
            "topright" => Some(Direction::TopRight),
            "middleleft" => Some(Direction::MiddleLeft),
            "middlecenter" => Some(Direction::MiddleCenter),
            "middleright" => Some(Direction::MiddleRight),
            "bottomleft" => Some(Direction::BottomLeft),
            "bottomcenter" => Some(Direction::BottomCenter),
            "bottomright" => Some(Direction::BottomRight),
            "anyexceptcenter" | "randomnotcenter" => Some(Direction::RandomNotCenter),
            "random" => Some(Direction::Random),
            _ => None,
        }
    }
}

/// AllowedMoves — набор флагов (как [Flags] enum в оригинале).
pub mod moves {
    pub const NONE: u8 = 0;
    pub const HORIZONTAL_ONLY: u8 = 1;
    pub const VERTICAL_ONLY: u8 = 2;
    pub const DIAGONAL_ONLY: u8 = 4;
    pub const HORIZONTAL_VERTICAL: u8 = HORIZONTAL_ONLY | VERTICAL_ONLY;
    pub const DIAGONAL_HORIZONTAL: u8 = DIAGONAL_ONLY | HORIZONTAL_ONLY;
    pub const DIAGONAL_VERTICAL: u8 = DIAGONAL_ONLY | VERTICAL_ONLY;
    pub const ALL: u8 = HORIZONTAL_ONLY | VERTICAL_ONLY | DIAGONAL_ONLY;
    pub const MOUSE_OVER: u8 = 8;
    pub const SLEEP: u8 = 16;
    pub const DRAGGED: u8 = 32;
}

pub const MOVES_TABLE: [(&str, u8); 11] = [
    ("none", moves::NONE),
    ("horizontal_only", moves::HORIZONTAL_ONLY),
    ("vertical_only", moves::VERTICAL_ONLY),
    ("horizontal_vertical", moves::HORIZONTAL_VERTICAL),
    ("diagonal_only", moves::DIAGONAL_ONLY),
    ("diagonal_horizontal", moves::DIAGONAL_HORIZONTAL),
    ("diagonal_vertical", moves::DIAGONAL_VERTICAL),
    ("all", moves::ALL),
    ("mouseover", moves::MOUSE_OVER),
    ("sleep", moves::SLEEP),
    ("dragged", moves::DRAGGED),
];

pub fn moves_to_ini(m: u8) -> &'static str {
    match m {
        moves::NONE => "None",
        moves::HORIZONTAL_ONLY => "Horizontal_Only",
        moves::VERTICAL_ONLY => "Vertical_Only",
        moves::HORIZONTAL_VERTICAL => "Horizontal_Vertical",
        moves::DIAGONAL_ONLY => "Diagonal_Only",
        moves::DIAGONAL_HORIZONTAL => "Diagonal_horizontal",
        moves::DIAGONAL_VERTICAL => "Diagonal_Vertical",
        moves::ALL => "All",
        moves::MOUSE_OVER => "MouseOver",
        moves::SLEEP => "Sleep",
        moves::DRAGGED => "Dragged",
        _ => "None",
    }
}

/// Мягкий разбор имени движения из любого написания (ini, UI, JSON).
pub fn moves_from_any(s: &str) -> Option<u8> {
    let norm = s.trim().to_ascii_lowercase().replace([' ', '/', '-'], "_");
    if let Some((_, m)) = MOVES_TABLE.iter().find(|(k, _)| *k == norm) {
        return Some(*m);
    }
    match norm.replace('_', "").as_str() {
        "horizontalonly" => Some(moves::HORIZONTAL_ONLY),
        "verticalonly" => Some(moves::VERTICAL_ONLY),
        "horizontalvertical" => Some(moves::HORIZONTAL_VERTICAL),
        "diagonalonly" => Some(moves::DIAGONAL_ONLY),
        "diagonalhorizontal" => Some(moves::DIAGONAL_HORIZONTAL),
        "diagonalvertical" => Some(moves::DIAGONAL_VERTICAL),
        _ => None,
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TargetActivation {
    One,
    Any,
    All,
}

impl TargetActivation {
    pub fn to_ini(self) -> &'static str {
        match self {
            TargetActivation::One => "One",
            TargetActivation::Any => "Any",
            TargetActivation::All => "All",
        }
    }
    /// TargetActivationFromIniString: помимо имён допускает "random"/"False" (=One)
    /// и "all"/"True" (=Any) из старых версий.
    pub fn from_ini(s: &str) -> Option<TargetActivation> {
        match s.trim().to_ascii_lowercase().as_str() {
            "one" | "false" | "random" => Some(TargetActivation::One),
            "any" | "true" => Some(TargetActivation::Any),
            "all" => Some(TargetActivation::All),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FollowOffsetType {
    Fixed,
    Mirror,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TargetMode {
    None,
    Point,
    Pony,
}

// ------------------------------------------------------------------ images

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoundingX {
    ToEven,
    Floor,
    Ceiling,
}

#[derive(Clone, Debug)]
pub struct SpriteImage {
    /// Полный путь к gif.
    pub path: String,
    /// Размер в пикселях (0,0, если файл недоступен).
    pub size: (u32, u32),
    /// Пользовательский центр (CustomCenter); None = центр по умолчанию.
    pub custom_center: Option<(i32, i32)>,
    pub rounding_x: RoundingX,
}

impl SpriteImage {
    pub fn new(rounding_x: RoundingX) -> SpriteImage {
        SpriteImage { path: String::new(), size: (0, 0), custom_center: None, rounding_x }
    }

    /// Центр изображения: заданный вручную либо середина ((размер-1)/2) с
    /// политикой округления по X (право — вверх, лево — вниз), по Y — к чётному.
    pub fn center(&self) -> V2 {
        if let Some((x, y)) = self.custom_center {
            return V2::new(x as f32, y as f32);
        }
        let x = (self.size.0 as f32 - 1.0) / 2.0;
        let y = (self.size.1 as f32 - 1.0) / 2.0;
        let rx = match self.rounding_x {
            RoundingX::Floor => x.floor() as i32,
            RoundingX::Ceiling => x.ceil() as i32,
            RoundingX::ToEven => round_half_even(x),
        };
        V2::new(rx as f32, round_half_even(y) as f32)
    }

    pub fn size_v(&self) -> V2 {
        V2::new(self.size.0 as f32, self.size.1 as f32)
    }

    pub fn file_name(&self) -> String {
        Path::new(&self.path).file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default()
    }

    pub fn update_size(&mut self) {
        self.size = (0, 0);
        if self.path.trim().is_empty() {
            return;
        }
        if let Ok((w, h)) = image::image_dimensions(&self.path) {
            self.size = (w, h);
        }
    }
}

// ------------------------------------------------------------------ items

#[derive(Clone, Debug)]
pub struct BehaviorGroup {
    pub name: String,
    pub number: i32,
}

impl BehaviorGroup {
    pub fn get_pony_ini(&self) -> String {
        format!("behaviorgroup,{},{}", self.number, self.name)
    }
}

#[derive(Clone, Debug)]
pub struct Behavior {
    pub name: String,
    pub group: i32,
    pub min_duration: f64,
    pub max_duration: f64,
    pub speed: f64,
    pub right_image: SpriteImage,
    pub left_image: SpriteImage,
    pub allowed_movement: u8,
    pub linked_behavior: String,
    pub start_line: String,
    pub end_line: String,
    pub target_vector: (i32, i32),
    pub follow_target: String,
    pub follow_offset: FollowOffsetType,
    pub auto_select_images_on_follow: bool,
    pub follow_stopped: String,
    pub follow_moving: String,
    pub chance: f64,
    pub skip: bool,
    pub do_not_repeat_image_animations: bool,
}

impl Behavior {
    pub fn new() -> Behavior {
        Behavior {
            name: String::new(),
            group: ANY_GROUP,
            min_duration: 5.0,
            max_duration: 15.0,
            speed: 3.0,
            right_image: SpriteImage::new(RoundingX::Ceiling),
            left_image: SpriteImage::new(RoundingX::Floor),
            allowed_movement: moves::ALL,
            linked_behavior: String::new(),
            start_line: String::new(),
            end_line: String::new(),
            target_vector: (0, 0),
            follow_target: String::new(),
            follow_offset: FollowOffsetType::Fixed,
            auto_select_images_on_follow: true,
            follow_stopped: String::new(),
            follow_moving: String::new(),
            chance: 0.0,
            skip: false,
            do_not_repeat_image_animations: false,
        }
    }

    /// Скорость в пикселях в секунду (Speed * 1000/30).
    pub fn speed_px_per_sec(&self) -> f64 {
        self.speed * (1000.0 / 30.0)
    }

    pub fn target_mode(&self) -> TargetMode {
        if !self.follow_target.is_empty() {
            TargetMode::Pony
        } else if self.target_vector != (0, 0) {
            TargetMode::Point
        } else {
            TargetMode::None
        }
    }

    pub fn get_pony_ini(&self) -> String {
        let rc = self.right_image.custom_center.unwrap_or((0, 0));
        let lc = self.left_image.custom_center.unwrap_or((0, 0));
        [
            "Behavior".to_string(),
            quoted(&self.name),
            fmt_f(self.chance),
            fmt_f(self.max_duration),
            fmt_f(self.min_duration),
            fmt_f(self.speed),
            quoted(&self.right_image.file_name()),
            quoted(&self.left_image.file_name()),
            moves_to_ini(self.allowed_movement).to_string(),
            quoted(&self.linked_behavior),
            quoted(&self.start_line),
            quoted(&self.end_line),
            cs_bool(self.skip),
            self.target_vector.0.to_string(),
            self.target_vector.1.to_string(),
            quoted(&self.follow_target),
            cs_bool(self.auto_select_images_on_follow),
            quoted(&self.follow_stopped),
            quoted(&self.follow_moving),
            quoted(&format!("{},{}", rc.0, rc.1)),
            quoted(&format!("{},{}", lc.0, lc.1)),
            cs_bool(self.do_not_repeat_image_animations),
            self.group.to_string(),
            match self.follow_offset {
                FollowOffsetType::Fixed => "Fixed".to_string(),
                FollowOffsetType::Mirror => "Mirror".to_string(),
            },
        ]
        .join(",")
    }
}

#[derive(Clone, Debug)]
pub struct Speech {
    pub name: String,
    pub text: String,
    /// Путь к звуковому файлу (mp3) или None.
    pub sound_file: Option<String>,
    pub skip: bool,
    pub group: i32,
}

pub const UNNAMED: &str = "Unnamed";

impl Speech {
    pub fn get_pony_ini(&self) -> String {
        let name = if self.name.is_empty() { UNNAMED } else { &self.name };
        match &self.sound_file {
            None => format!("Speak,{},{},,{},{}", quoted(name), quoted(&self.text), cs_bool(self.skip), self.group),
            Some(p) => {
                let file = Path::new(p).file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
                let ogg = Path::new(&file).with_extension("ogg").to_string_lossy().to_string();
                format!(
                    "Speak,{},{},{},{},{}",
                    quoted(name),
                    quoted(&self.text),
                    braced(&format!("{},{}", quoted(&file), quoted(&ogg))),
                    cs_bool(self.skip),
                    self.group
                )
            }
        }
    }
}

#[derive(Clone, Debug)]
pub struct EffectBase {
    pub name: String,
    pub behavior_name: String,
    pub right_image: SpriteImage,
    pub left_image: SpriteImage,
    pub duration: f64,
    pub repeat_delay: f64,
    pub placement_right: Direction,
    pub centering_right: Direction,
    pub placement_left: Direction,
    pub centering_left: Direction,
    pub follow: bool,
    pub do_not_repeat_image_animations: bool,
}

impl EffectBase {
    pub fn new() -> EffectBase {
        EffectBase {
            name: String::new(),
            behavior_name: String::new(),
            right_image: SpriteImage::new(RoundingX::Ceiling),
            left_image: SpriteImage::new(RoundingX::Floor),
            duration: 5.0,
            repeat_delay: 0.0,
            placement_right: Direction::Random,
            centering_right: Direction::Random,
            placement_left: Direction::Random,
            centering_left: Direction::Random,
            follow: false,
            do_not_repeat_image_animations: false,
        }
    }

    pub fn get_pony_ini(&self) -> String {
        [
            "Effect".to_string(),
            quoted(&self.name),
            quoted(&self.behavior_name),
            quoted(&self.right_image.file_name()),
            quoted(&self.left_image.file_name()),
            fmt_f(self.duration),
            fmt_f(self.repeat_delay),
            self.placement_right.to_ini().to_string(),
            self.centering_right.to_ini().to_string(),
            self.placement_left.to_ini().to_string(),
            self.centering_left.to_ini().to_string(),
            cs_bool(self.follow),
            cs_bool(self.do_not_repeat_image_animations),
        ]
        .join(",")
    }
}

#[derive(Clone, Debug)]
pub struct InteractionBase {
    pub name: String,
    pub initiator_name: String,
    pub chance: f64,
    pub proximity: f64,
    pub target_names: Vec<String>,
    pub activation: TargetActivation,
    pub behavior_names: Vec<String>,
    pub reactivation_delay: f64,
}

impl InteractionBase {
    pub fn get_pony_ini(&self) -> String {
        [
            "Interaction".to_string(),
            self.name.clone(),
            fmt_f(self.chance),
            fmt_f(self.proximity),
            braced(&self.target_names.iter().map(|n| quoted(n)).collect::<Vec<_>>().join(",")),
            self.activation.to_ini().to_string(),
            braced(&self.behavior_names.iter().map(|n| quoted(n)).collect::<Vec<_>>().join(",")),
            fmt_f(self.reactivation_delay),
        ]
        .join(",")
    }
}

// ------------------------------------------------------------------ pony base

#[derive(Clone, Debug)]
pub struct PonyBase {
    /// Имя папки внутри Ponies (идентификатор пони).
    pub directory: String,
    pub display_name: String,
    pub tags: Vec<String>,
    pub behavior_groups: Vec<BehaviorGroup>,
    pub behaviors: Vec<Behavior>,
    pub effects: Vec<EffectBase>,
    pub interactions: Vec<InteractionBase>,
    pub speeches: Vec<Speech>,
    pub comment_lines: Vec<String>,
    pub invalid_lines: Vec<String>,
    /// Полный путь к папке пони.
    pub path: PathBuf,
}

impl PonyBase {
    pub fn new(directory: &str, path: PathBuf) -> PonyBase {
        PonyBase {
            directory: directory.to_string(),
            display_name: directory.to_string(),
            tags: Vec::new(),
            behavior_groups: Vec::new(),
            behaviors: Vec::new(),
            effects: Vec::new(),
            interactions: Vec::new(),
            speeches: Vec::new(),
            comment_lines: Vec::new(),
            invalid_lines: Vec::new(),
            path,
        }
    }

    pub fn behavior_by_name(&self, name: &str) -> Option<usize> {
        if name.is_empty() {
            return None;
        }
        self.behaviors.iter().position(|b| ci_eq(&b.name, name))
    }

    pub fn speech_by_name(&self, name: &str) -> Option<usize> {
        if name.is_empty() {
            return None;
        }
        self.speeches.iter().position(|s| ci_eq(&s.name, name))
    }

    /// Речь, доступная для случайного выбора (не Skip).
    pub fn random_speeches(&self) -> impl Iterator<Item = &Speech> {
        self.speeches.iter().filter(|s| !s.skip)
    }

    pub fn behavior_group_name(&self, number: i32) -> Option<String> {
        if number == ANY_GROUP {
            return Some("Any".to_string());
        }
        self.behavior_groups.iter().find(|g| g.number == number).map(|g| g.name.clone())
    }

    pub fn has_tag(&self, tag: &str) -> bool {
        self.tags.iter().any(|t| ci_eq(t, tag))
    }

    /// Текст pony.ini в формате оригинала (порядок секций как у PonyBase.Save).
    pub fn to_ini_text(&self) -> String {
        let mut out = String::new();
        for c in &self.comment_lines {
            out.push_str(c);
            out.push('\n');
        }
        out.push_str(&format!("Name,{}\n", self.display_name));
        out.push_str(&format!(
            "Categories,{}\n",
            self.tags.iter().map(|t| quoted(t)).collect::<Vec<_>>().join(",")
        ));
        for g in &self.behavior_groups {
            out.push_str(&g.get_pony_ini());
            out.push('\n');
        }
        for b in &self.behaviors {
            out.push_str(&b.get_pony_ini());
            out.push('\n');
        }
        for e in &self.effects {
            out.push_str(&e.get_pony_ini());
            out.push('\n');
        }
        for s in &self.speeches {
            out.push_str(&s.get_pony_ini());
            out.push('\n');
        }
        for i in &self.interactions {
            out.push_str(&i.get_pony_ini());
            out.push('\n');
        }
        for l in &self.invalid_lines {
            out.push_str(l);
            out.push('\n');
        }
        out
    }

    /// Сохраняет pony.ini (UTF-8, атомарно через временный файл).
    pub fn save(&self) -> Result<(), String> {
        std::fs::create_dir_all(&self.path).map_err(|e| e.to_string())?;
        let target = self.path.join("pony.ini");
        let tmp = self.path.join("pony.ini.tmp");
        std::fs::write(&tmp, self.to_ini_text()).map_err(|e| format!("write: {}", e))?;
        std::fs::rename(&tmp, &target).or_else(|_| {
            // Windows не даёт rename поверх существующего файла в некоторых случаях.
            std::fs::remove_file(&target).ok();
            std::fs::rename(&tmp, &target)
        }).map_err(|e| format!("rename: {}", e))
    }
}

// ------------------------------------------------------------------ houses

#[derive(Clone, Debug)]
pub struct HouseBase {
    pub directory: String,
    pub name: String,
    pub image: SpriteImage,
    pub door_position: (i32, i32),
    pub cycle_interval: f64,
    pub minimum_ponies: i32,
    pub maximum_ponies: i32,
    pub bias: f64,
    pub visitors: Vec<String>,
}

// ------------------------------------------------------------------ format helpers

/// Число в инвариантном формате (как ToStringInvariant): без лишних нулей.
pub fn fmt_f(v: f64) -> String {
    if v == v.trunc() && v.abs() < 1e15 {
        format!("{}", v as i64)
    } else {
        format!("{}", v)
    }
}

/// Boolean.ToString() в .NET — "True"/"False".
pub fn cs_bool(b: bool) -> String {
    if b { "True".to_string() } else { "False".to_string() }
}
