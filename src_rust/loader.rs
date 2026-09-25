// src_rust/loader.rs
//
// Загрузка pony.ini / house.ini — порт PonyBase.Load, Behavior.TryLoad,
// Speech.TryLoad, EffectBase.TryLoad, InteractionBase.TryLoad, HouseBase.Load и
// PonyCollection из оригинального Desktop Ponies 1.69.
//
// Порядок колонок строго как в оригинале (см. имена колонок
// StringCollectionParser в Pony.vb). Ошибочные (Failed) элементы при
// remove_invalid = true отбрасываются: например, поведение с отсутствующим
// gif-файлом в игре не используется — как и в оригинале.

use crate::ini::{comma_split_quote, comma_split_quote_brace, ParseResult, Parser};
use crate::model::*;
use std::path::{Path, PathBuf};

pub const PONY_ROOT: &str = "Ponies";
pub const HOUSE_ROOT: &str = "Houses";

pub fn read_text_file(path: &Path) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    let bytes = bytes.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(&bytes);
    Some(String::from_utf8_lossy(bytes).to_string())
}

fn combine_path(dir: &Path, name: &str) -> PathBuf {
    dir.join(name.trim())
}

fn parse_image(p: &mut Parser, dir: &Path, image: &mut SpriteImage) {
    let name = p.no_parse();
    let has = name.as_deref().map(|s| !s.is_empty()).unwrap_or(false);
    if p.assert(has, "An image path has not been set.", false) {
        let full = combine_path(dir, name.as_deref().unwrap());
        p.file_exists(&full, false);
        image.path = full.to_string_lossy().to_string();
    }
}

// ------------------------------------------------------------------ Behavior

pub fn parse_behavior(line: &str, dir: &Path) -> (Behavior, ParseResult) {
    let mut b = Behavior::new();
    let mut p = Parser::new(comma_split_quote(line));
    p.no_parse(); // Identifier
    b.name = p.not_null_or_ws(None);
    b.chance = p.parse_f64(Some(0.0), 0.0, 1.0);
    b.max_duration = p.parse_f64(Some(15.0), 0.0, 300.0);
    b.min_duration = p.parse_f64(Some(5.0), 0.0, 300.0);
    if b.max_duration < b.min_duration {
        p.assert(false, "The min duration exceeds the max duration.", true);
        std::mem::swap(&mut b.max_duration, &mut b.min_duration);
    } else {
        p.assert(true, "", true);
    }
    b.speed = p.parse_f64(Some(3.0), 0.0, 30.0);
    parse_image(&mut p, dir, &mut b.right_image);
    parse_image(&mut p, dir, &mut b.left_image);
    b.allowed_movement = p.map(&MOVES_TABLE, Some(moves::ALL), moves::ALL);
    b.linked_behavior = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    b.start_line = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    b.end_line = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    b.skip = p.parse_bool(Some(false));
    let tx = p.parse_i32(Some(0), i32::MIN, i32::MAX);
    let ty = p.parse_i32(Some(0), i32::MIN, i32::MAX);
    b.target_vector = (tx, ty);
    b.follow_target = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    b.auto_select_images_on_follow = p.parse_bool(Some(true));
    b.follow_stopped = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    b.follow_moving = p.not_null(Some("")).unwrap_or_default().trim().to_string();
    let rc = p.parse_vec2(Some((0, 0)));
    let lc = p.parse_vec2(Some((0, 0)));
    b.right_image.custom_center = if rc == (0, 0) { None } else { Some(rc) };
    b.left_image.custom_center = if lc == (0, 0) { None } else { Some(lc) };
    b.do_not_repeat_image_animations = p.parse_bool(Some(false));
    b.group = p.parse_i32(Some(ANY_GROUP), 0, 100);
    b.follow_offset = p.map(
        &[("fixed", FollowOffsetType::Fixed), ("mirror", FollowOffsetType::Mirror)],
        Some(FollowOffsetType::Fixed),
        FollowOffsetType::Fixed,
    );
    (b, p.result)
}

// ------------------------------------------------------------------ Speech

pub fn parse_speech(line: &str, dir: &Path) -> (Speech, ParseResult) {
    let mut comps: Vec<Option<String>> = comma_split_quote_brace(line).into_iter().map(Some).collect();
    let mut named = true;
    if comps.len() == 2 {
        named = false;
        comps = vec![comps[0].clone(), None, comps[1].clone()];
    }
    if comps.len() > 3 {
        let list = comma_split_quote(comps[3].as_deref().unwrap_or(""));
        // В оригинале воспроизводится только mp3; ogg/wav принимаем как запасной вариант.
        let pick = list
            .iter()
            .find(|f| f.to_ascii_lowercase().ends_with(".mp3"))
            .cloned()
            .or_else(|| {
                list.iter()
                    .find(|f| {
                        let l = f.to_ascii_lowercase();
                        l.ends_with(".ogg") || l.ends_with(".wav")
                    })
                    .cloned()
            });
        comps[3] = pick;
    }
    let mut p = Parser::from_optional(comps);
    p.no_parse();
    let name = if named { Some(p.not_null_or_ws(Some(UNNAMED))) } else { p.no_parse() };
    let text = p.not_null(None).unwrap_or_default();
    let mut sound = p.no_parse().filter(|s| !s.trim().is_empty());
    if let Some(s) = &sound {
        let full = combine_path(dir, s);
        p.file_exists(&full, true);
        sound = if full.is_file() { Some(full.to_string_lossy().to_string()) } else { None };
    }
    let skip = p.parse_bool(Some(false));
    let group = p.parse_i32(Some(ANY_GROUP), 0, 100);
    (Speech { name: name.unwrap_or_default(), text, sound_file: sound, skip, group }, p.result)
}

// ------------------------------------------------------------------ Effect

pub fn parse_effect(line: &str, dir: &Path) -> (EffectBase, ParseResult) {
    let mut e = EffectBase::new();
    let mut p = Parser::new(comma_split_quote(line));
    p.no_parse();
    e.name = p.not_null_or_ws(None);
    e.behavior_name = p.not_null_or_ws(None);
    parse_image(&mut p, dir, &mut e.right_image);
    parse_image(&mut p, dir, &mut e.left_image);
    e.duration = p.parse_f64(Some(5.0), 0.0, 300.0);
    e.repeat_delay = p.parse_f64(Some(0.0), 0.0, 300.0);
    e.placement_right = p.map(&DIRECTION_TABLE, Some(Direction::Random), Direction::Random);
    e.centering_right = p.map(&DIRECTION_TABLE, Some(Direction::Random), Direction::Random);
    e.placement_left = p.map(&DIRECTION_TABLE, Some(Direction::Random), Direction::Random);
    e.centering_left = p.map(&DIRECTION_TABLE, Some(Direction::Random), Direction::Random);
    e.follow = p.parse_bool(Some(false));
    e.do_not_repeat_image_animations = p.parse_bool(Some(false));
    (e, p.result)
}

// ------------------------------------------------------------------ Interaction

fn name_list(text: &str) -> Vec<String> {
    comma_split_quote(text).into_iter().filter(|s| !s.trim().is_empty()).collect()
}

pub fn parse_interaction(line: &str, initiator: &str) -> (InteractionBase, ParseResult) {
    let mut p = Parser::new(comma_split_quote_brace(line));
    p.no_parse(); // Identifier
    let name = p.not_null_or_ws(None);
    let chance = p.parse_f64(Some(0.0), 0.0, 1.0);
    let proximity = p.parse_f64(Some(125.0), 0.0, 10000.0);
    let targets = p.not_null(None).map(|t| name_list(&t)).unwrap_or_default();
    p.assert(!targets.is_empty(), "There must be one or more targets.", false);
    let act_text = p.no_parse();
    let activation = match act_text.as_deref().and_then(TargetActivation::from_ini) {
        Some(a) => a,
        None => {
            p.assert(act_text.is_none(), "invalid activation", true);
            TargetActivation::One
        }
    };
    let behaviors = p.not_null(None).map(|t| name_list(&t)).unwrap_or_default();
    p.assert(!behaviors.is_empty(), "There must be one or more behaviors.", false);
    let reactivation = p.parse_f64(Some(60.0), 0.0, 3600.0);
    (
        InteractionBase {
            name,
            initiator_name: initiator.to_string(),
            chance,
            proximity,
            target_names: targets,
            activation,
            behavior_names: behaviors,
            reactivation_delay: reactivation,
        },
        p.result,
    )
}

// ------------------------------------------------------------------ PonyBase

fn add_tag(tags: &mut Vec<String>, tag: String) {
    if !tag.is_empty() && !tags.iter().any(|t| ci_eq(t, &tag)) {
        tags.push(tag);
    }
}

/// Загружает одну пони. Возвращает None, если папки нет, либо (при
/// remove_invalid) не осталось ни одного корректного поведения.
pub fn load_pony_base(root: &Path, directory: &str, remove_invalid: bool) -> Option<PonyBase> {
    let full = root.join(directory);
    if !full.is_dir() {
        return None;
    }
    let mut pony = PonyBase::new(directory, full.clone());
    if let Some(text) = read_text_file(&full.join("pony.ini")) {
        parse_pony_config(&full, &text, &mut pony, remove_invalid);
    }
    if remove_invalid && pony.behaviors.is_empty() {
        return None;
    }
    for b in &mut pony.behaviors {
        b.right_image.update_size();
        b.left_image.update_size();
    }
    for e in &mut pony.effects {
        e.right_image.update_size();
        e.left_image.update_size();
    }
    Some(pony)
}

fn parse_pony_config(folder: &Path, text: &str, pony: &mut PonyBase, remove_invalid: bool) {
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        if line.starts_with('\'') {
            pony.comment_lines.push(line.to_string());
            continue;
        }
        let Some(first_comma) = line.find(',') else {
            pony.invalid_lines.push(line.to_string());
            continue;
        };
        match line[..first_comma].to_ascii_lowercase().as_str() {
            "name" => {
                let mut p = Parser::new(comma_split_quote_brace(line));
                p.no_parse();
                if let Some(n) = p.no_parse() {
                    pony.display_name = n;
                }
            }
            "scale" => pony.invalid_lines.push(line.to_string()),
            "behaviorgroup" => {
                let mut p = Parser::new(comma_split_quote_brace(line));
                p.no_parse();
                let number = p.parse_i32(None, 0, 100);
                let name = p.not_null_or_ws(Some(&number.to_string()));
                if p.result != ParseResult::Failed || !remove_invalid {
                    pony.behavior_groups.push(BehaviorGroup { name, number });
                }
            }
            "behavior" => {
                let (b, r) = parse_behavior(line, folder);
                if r != ParseResult::Failed || !remove_invalid {
                    pony.behaviors.push(b);
                }
            }
            "effect" => {
                let (e, r) = parse_effect(line, folder);
                if r != ParseResult::Failed || !remove_invalid {
                    pony.effects.push(e);
                }
            }
            "speak" => {
                let (s, r) = parse_speech(line, folder);
                if r != ParseResult::Failed || !remove_invalid {
                    pony.speeches.push(s);
                }
            }
            "interaction" => {
                let (i, r) = parse_interaction(line, &pony.directory);
                if r != ParseResult::Failed || !remove_invalid {
                    pony.interactions.push(i);
                }
            }
            "categories" => {
                for t in comma_split_quote(line).into_iter().skip(1) {
                    add_tag(&mut pony.tags, t);
                }
            }
            _ => pony.invalid_lines.push(line.to_string()),
        }
    }
}

// ------------------------------------------------------------------ Houses

pub fn load_house(root: &Path, directory: &str) -> Option<HouseBase> {
    let full = root.join(directory);
    if !full.is_dir() {
        return None;
    }
    let mut house = HouseBase {
        directory: directory.to_string(),
        name: directory.to_string(),
        image: SpriteImage::new(RoundingX::ToEven),
        door_position: (0, 0),
        cycle_interval: 300.0,
        minimum_ponies: 1,
        maximum_ponies: 50,
        bias: 0.5,
        visitors: Vec::new(),
    };
    let text = read_text_file(&full.join("house.ini")).unwrap_or_default();
    for line in text.lines() {
        if line.trim().is_empty() || line.starts_with('\'') {
            continue;
        }
        let Some(fc) = line.find(',') else {
            house.visitors.push(line.trim().to_string());
            continue;
        };
        let toks = comma_split_quote_brace(line);
        let get = |i: usize| toks.get(i).cloned().unwrap_or_default();
        match line[..fc].to_ascii_lowercase().as_str() {
            "name" => {
                if !get(1).trim().is_empty() {
                    house.name = get(1);
                }
            }
            "image" => {
                let path = full.join(get(1).trim());
                if path.is_file() {
                    house.image.path = path.to_string_lossy().to_string();
                }
            }
            "door" => {
                house.door_position = (get(1).trim().parse().unwrap_or(0), get(2).trim().parse().unwrap_or(0));
            }
            "cycletime" => house.cycle_interval = get(1).trim().parse::<f64>().unwrap_or(300.0).clamp(1.0, 3600.0),
            "minspawn" => house.minimum_ponies = get(1).trim().parse::<i32>().unwrap_or(1).max(1),
            "maxspawn" => house.maximum_ponies = get(1).trim().parse::<i32>().unwrap_or(50).max(1),
            "bias" => house.bias = get(1).trim().parse::<f64>().unwrap_or(0.5).clamp(0.0, 1.0),
            _ => house.visitors.push(line.trim().to_string()),
        }
    }
    house.image.update_size();
    if house.visitors.is_empty() || house.image.path.is_empty() {
        return None;
    }
    Some(house)
}

// ------------------------------------------------------------------ Collection

/// Все загруженные пони и дома (PonyCollection).
pub struct PonyCollection {
    pub root: PathBuf,
    pub bases: Vec<PonyBase>,
    pub random_base: Option<PonyBase>,
    pub houses: Vec<HouseBase>,
}

impl PonyCollection {
    pub fn empty(root: &Path) -> PonyCollection {
        PonyCollection { root: root.to_path_buf(), bases: Vec::new(), random_base: None, houses: Vec::new() }
    }

    /// root — папка, в которой лежат Ponies/ и Houses/.
    pub fn load(root: &Path, remove_invalid: bool) -> PonyCollection {
        let mut c = PonyCollection::empty(root);
        let ponies_dir = root.join(PONY_ROOT);
        let mut dirs: Vec<String> = std::fs::read_dir(&ponies_dir)
            .map(|rd| {
                rd.flatten()
                    .filter(|e| e.path().is_dir())
                    .filter_map(|e| e.file_name().to_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        dirs.sort_by_key(|d| d.to_lowercase());

        // Параллельная загрузка: чтение ini и заголовков gif — основная стоимость.
        let threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4).min(8);
        let chunk = dirs.len().div_ceil(threads.max(1)).max(1);
        let mut loaded: Vec<PonyBase> = Vec::new();
        std::thread::scope(|s| {
            let handles: Vec<_> = dirs
                .chunks(chunk)
                .map(|part| {
                    let ponies_dir = &ponies_dir;
                    s.spawn(move || {
                        part.iter().filter_map(|d| load_pony_base(ponies_dir, d, remove_invalid)).collect::<Vec<_>>()
                    })
                })
                .collect();
            for h in handles {
                loaded.extend(h.join().unwrap_or_default());
            }
        });
        loaded.sort_by_key(|b| b.directory.to_lowercase());
        if let Some(idx) = loaded.iter().position(|b| b.directory == RANDOM_DIRECTORY) {
            c.random_base = Some(loaded.remove(idx));
        }
        c.bases = loaded;

        let house_dir = root.join(HOUSE_ROOT);
        if let Ok(rd) = std::fs::read_dir(&house_dir) {
            for e in rd.flatten() {
                if let Some(name) = e.file_name().to_str() {
                    if let Some(h) = load_house(&house_dir, name) {
                        c.houses.push(h);
                    }
                }
            }
        }
        c.houses.sort_by_key(|h| h.name.to_lowercase());
        c
    }

    pub fn base_by_directory(&self, directory: &str) -> Option<&PonyBase> {
        self.bases.iter().find(|b| ci_eq(&b.directory, directory))
    }

    pub fn all_tags(&self) -> Vec<String> {
        let mut tags: Vec<String> = Vec::new();
        for b in &self.bases {
            for t in &b.tags {
                add_tag(&mut tags, t.clone());
            }
        }
        tags
    }
}

// ------------------------------------------------------------------ tests

#[cfg(test)]
mod tests {
    use super::*;

    fn project_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
    }

    #[test]
    fn behavior_columns_match_original_layout() {
        let dir = project_root().join("Ponies").join("Applejack");
        let line = r#"Behavior,"stand",0.35,10,2.2,0,"stand_aj_right.gif","stand_aj_left.gif",MouseOver,"walk","s1","s2",True,5,6,"Pinkie Pie",False,"a","b","44,46","43,46",True,3,Mirror"#;
        let (b, r) = parse_behavior(line, &dir);
        assert_eq!(r, ParseResult::Success, "images exist");
        assert_eq!(b.name, "stand");
        assert_eq!(b.chance, 0.35);
        assert_eq!(b.max_duration, 10.0);
        assert_eq!(b.min_duration, 2.2);
        assert_eq!(b.allowed_movement, moves::MOUSE_OVER);
        assert_eq!(b.linked_behavior, "walk");
        assert_eq!(b.start_line, "s1");
        assert!(b.skip);
        assert_eq!(b.target_vector, (5, 6));
        assert_eq!(b.follow_target, "Pinkie Pie");
        assert!(!b.auto_select_images_on_follow);
        assert_eq!(b.follow_stopped, "a");
        assert_eq!(b.right_image.custom_center, Some((44, 46)));
        assert!(b.do_not_repeat_image_animations);
        assert_eq!(b.group, 3);
        assert_eq!(b.follow_offset, FollowOffsetType::Mirror);
        assert_eq!(b.target_mode(), TargetMode::Pony);
    }

    #[test]
    fn effect_and_interaction_columns() {
        let dir = project_root().join("Ponies").join("Applejack");
        let (e, _) = parse_effect(
            r#"Effect,"Apple Drop","gallop","apple_drop.gif","apple_drop.gif",3.3,0.8,Top,Bottom_Left,Right,Center,True,False"#,
            &dir,
        );
        assert_eq!(e.behavior_name, "gallop");
        assert_eq!(e.duration, 3.3);
        assert_eq!(e.repeat_delay, 0.8);
        assert_eq!(e.placement_right, Direction::TopCenter);
        assert_eq!(e.centering_right, Direction::BottomLeft);
        assert_eq!(e.placement_left, Direction::MiddleRight);
        assert_eq!(e.centering_left, Direction::MiddleCenter);
        assert!(e.follow);

        let (i, r) = parse_interaction(
            r#"Interaction,pinkaport,0.02,500,{"Pinkie Pie","Rarity"},Any,{"pinkaport"},300"#,
            "Applejack",
        );
        assert_eq!(r, ParseResult::Success);
        assert_eq!(i.target_names, vec!["Pinkie Pie", "Rarity"]);
        assert_eq!(i.activation, TargetActivation::Any);
        assert_eq!(i.proximity, 500.0);
        assert_eq!(i.reactivation_delay, 300.0);
        assert_eq!(i.initiator_name, "Applejack");
    }

    #[test]
    fn speech_forms() {
        let dir = project_root().join("Ponies").join("Applejack");
        let (s, _) = parse_speech(r#"Speak,"Unnamed #1","Hey there, Sugarcube!",,False,0"#, &dir);
        assert_eq!(s.text, "Hey there, Sugarcube!");
        assert!(s.sound_file.is_none());
        let (s, _) = parse_speech(r#"Speak,"Only text""#, &dir);
        assert_eq!(s.text, "Only text");
    }

    /// Все pony.ini проекта загружаются, а запись -> чтение стабильна.
    #[test]
    fn all_ponies_load_and_roundtrip() {
        let root = project_root();
        let c = PonyCollection::load(&root, true);
        assert!(c.bases.len() > 250, "loaded {}", c.bases.len());
        let mut total_behaviors = 0;
        for base in &c.bases {
            total_behaviors += base.behaviors.len();
            for b in &base.behaviors {
                let ini = b.get_pony_ini();
                let (b2, _) = parse_behavior(&ini, &base.path);
                assert_eq!(b2.name, b.name, "{}", base.directory);
                assert_eq!(b2.allowed_movement, b.allowed_movement, "{}/{}", base.directory, b.name);
                assert_eq!(b2.group, b.group);
                assert_eq!(b2.chance, b.chance);
                assert_eq!(b2.speed, b.speed);
                assert_eq!(b2.right_image.custom_center, b.right_image.custom_center);
                assert_eq!(b2.follow_target, b.follow_target);
                assert_eq!(b2.do_not_repeat_image_animations, b.do_not_repeat_image_animations);
                assert_eq!(b2.get_pony_ini(), ini, "{}/{} unstable", base.directory, b.name);
            }
            for e in &base.effects {
                let (e2, _) = parse_effect(&e.get_pony_ini(), &base.path);
                assert_eq!(e2.get_pony_ini(), e.get_pony_ini());
            }
            for i in &base.interactions {
                let (i2, _) = parse_interaction(&i.get_pony_ini(), &base.directory);
                assert_eq!(i2.get_pony_ini(), i.get_pony_ini());
            }
        }
        assert!(total_behaviors > 1500, "behaviors: {}", total_behaviors);
    }

    #[test]
    fn houses_load() {
        let c = PonyCollection::load(&project_root(), true);
        assert!(c.houses.len() >= 8, "houses: {}", c.houses.len());
        let sc = c.houses.iter().find(|h| h.name == "Sugarcube Corner").expect("Sugarcube Corner");
        assert_eq!(sc.door_position, (201, 329));
        assert!(sc.visitors.iter().any(|v| v.eq_ignore_ascii_case("all")));
    }
}
