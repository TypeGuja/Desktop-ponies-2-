// src_rust/ui_state.rs
//
// Данные для панели управления (WebView): список пони с тегами и превью,
// настройки в JSON и применение частичных изменений настроек обратно в
// Options. Вынесено из оболочки приложения, чтобы тестироваться без окон.

use crate::loader::PonyCollection;
use crate::math::{RectF, RectI};
use crate::model::*;
use crate::options::Options;
use crate::winapi::MonitorInfo;
use serde_json::{json, Value};

/// Путь (относительно корня) к картинке-превью пони: стоящее изображение
/// вправо, если есть (behavior со "stand"/"idle" в имени), иначе первое доступное.
pub fn preview_path(base: &PonyBase, root: &std::path::Path) -> Option<String> {
    let pick = base
        .behaviors
        .iter()
        .find(|b| {
            let n = b.name.to_lowercase();
            (n.contains("stand") || n.contains("idle")) && !b.right_image.path.is_empty()
        })
        .or_else(|| base.behaviors.iter().find(|b| !b.right_image.path.is_empty()))?;
    let full = std::path::Path::new(&pick.right_image.path);
    let rel = full.strip_prefix(root).ok()?;
    Some(rel.to_string_lossy().replace('\\', "/"))
}

pub fn ponies_json(c: &PonyCollection) -> Value {
    let list: Vec<Value> = c
        .bases
        .iter()
        .map(|b| {
            json!({
                "d": b.directory,
                "n": b.display_name,
                "t": b.tags,
                "p": preview_path(b, &c.root),
            })
        })
        .collect();
    Value::Array(list)
}

pub fn houses_json(c: &PonyCollection) -> Value {
    Value::Array(
        c.houses
            .iter()
            .enumerate()
            .map(|(i, h)| {
                let rel = std::path::Path::new(&h.image.path)
                    .strip_prefix(&c.root)
                    .ok()
                    .map(|p| p.to_string_lossy().replace('\\', "/"));
                json!({"i": i, "n": h.name, "p": rel})
            })
            .collect(),
    )
}

pub fn monitors_json(monitors: &[MonitorInfo]) -> Value {
    Value::Array(
        monitors
            .iter()
            .map(|m| json!({"name": m.device_name, "x": m.bounds.x, "y": m.bounds.y, "w": m.bounds.w, "h": m.bounds.h, "primary": m.primary}))
            .collect(),
    )
}

/// Все теги: стандартные, пользовательские и найденные у пони.
pub fn all_tags(c: &PonyCollection, custom: &[String]) -> Vec<String> {
    let mut tags: Vec<String> = STANDARD_TAGS.iter().map(|s| s.to_string()).collect();
    for t in custom.iter().cloned().chain(c.all_tags()) {
        if !tags.iter().any(|x| ci_eq(x, &t)) {
            tags.push(t);
        }
    }
    tags
}

pub fn options_to_json(o: &Options) -> Value {
    let region = o.allowed_region.map(|r| json!([r.x, r.y, r.w, r.h]));
    json!({
        "suspend_for_fullscreen_application": o.suspend_for_fullscreen_application,
        "show_in_taskbar": o.show_in_taskbar,
        "always_on_top": o.always_on_top,
        "window_avoidance_enabled": o.window_avoidance_enabled,
        "cursor_avoidance_enabled": o.cursor_avoidance_enabled,
        "cursor_avoidance_size": o.cursor_avoidance_size,
        "sound_enabled": o.sound_enabled,
        "sound_volume": o.sound_volume,
        "sound_single_channel_only": o.sound_single_channel_only,
        "pony_avoids_ponies": o.pony_avoids_ponies,
        "window_containment": o.window_containment,
        "pony_effects_enabled": o.pony_effects_enabled,
        "pony_dragging_enabled": o.pony_dragging_enabled,
        "pony_teleport_enabled": o.pony_teleport_enabled,
        "pony_speech_enabled": o.pony_speech_enabled,
        "pony_speech_chance": o.pony_speech_chance,
        "pony_interactions_enabled": o.pony_interactions_enabled,
        "no_random_duplicates": o.no_random_duplicates,
        "skeletal_animation": o.skeletal_animation,
        "fps_limit": o.fps_limit,
        "luna_moves_windows": o.luna_moves_windows,
        "luna_moves_icons": o.luna_moves_icons,
        "luna_sleeps_by_cursor": o.luna_sleeps_by_cursor,
        "luna_cursor_idle_secs": o.luna_cursor_idle_secs,
        "luna_music": o.luna_music,
        "luna_moves_ponies": o.luna_moves_ponies,
        "max_pony_count": o.max_pony_count,
        "time_factor": o.time_factor,
        "scale_factor": o.scale_factor,
        "exclusion_zone": [o.exclusion_zone.x, o.exclusion_zone.y, o.exclusion_zone.w, o.exclusion_zone.h],
        "screens": o.screens,
        "allowed_region": region,
    })
}

fn b(v: &Value, k: &str, cur: &mut bool) {
    if let Some(x) = v.get(k).and_then(|x| x.as_bool()) {
        *cur = x;
    }
}
fn f(v: &Value, k: &str, cur: &mut f32, min: f32, max: f32) {
    if let Some(x) = v.get(k).and_then(|x| x.as_f64()) {
        *cur = (x as f32).clamp(min, max);
    }
}

/// Применяет присланные из UI значения (частичный объект допустим).
pub fn apply_options_json(o: &mut Options, v: &Value) {
    b(v, "suspend_for_fullscreen_application", &mut o.suspend_for_fullscreen_application);
    b(v, "show_in_taskbar", &mut o.show_in_taskbar);
    b(v, "always_on_top", &mut o.always_on_top);
    b(v, "window_avoidance_enabled", &mut o.window_avoidance_enabled);
    b(v, "cursor_avoidance_enabled", &mut o.cursor_avoidance_enabled);
    f(v, "cursor_avoidance_size", &mut o.cursor_avoidance_size, 0.0, 10000.0);
    b(v, "sound_enabled", &mut o.sound_enabled);
    f(v, "sound_volume", &mut o.sound_volume, 0.0, 1.0);
    b(v, "sound_single_channel_only", &mut o.sound_single_channel_only);
    b(v, "pony_avoids_ponies", &mut o.pony_avoids_ponies);
    b(v, "window_containment", &mut o.window_containment);
    b(v, "pony_effects_enabled", &mut o.pony_effects_enabled);
    b(v, "pony_dragging_enabled", &mut o.pony_dragging_enabled);
    b(v, "pony_teleport_enabled", &mut o.pony_teleport_enabled);
    b(v, "pony_speech_enabled", &mut o.pony_speech_enabled);
    f(v, "pony_speech_chance", &mut o.pony_speech_chance, 0.0, 1.0);
    b(v, "pony_interactions_enabled", &mut o.pony_interactions_enabled);
    b(v, "no_random_duplicates", &mut o.no_random_duplicates);
    b(v, "skeletal_animation", &mut o.skeletal_animation);
    if let Some(x) = v.get("fps_limit").and_then(|x| x.as_f64()) {
        o.fps_limit = (x as u32).clamp(crate::options::MIN_FPS_LIMIT, crate::options::MAX_FPS_LIMIT);
    }
    b(v, "luna_moves_windows", &mut o.luna_moves_windows);
    b(v, "luna_moves_icons", &mut o.luna_moves_icons);
    b(v, "luna_sleeps_by_cursor", &mut o.luna_sleeps_by_cursor);
    b(v, "luna_music", &mut o.luna_music);
    b(v, "luna_moves_ponies", &mut o.luna_moves_ponies);
    if let Some(x) = v.get("luna_cursor_idle_secs").and_then(|x| x.as_f64()) {
        o.luna_cursor_idle_secs = (x as u32).clamp(crate::options::MIN_LUNA_IDLE_SECS, crate::options::MAX_LUNA_IDLE_SECS);
    }
    if let Some(x) = v.get("max_pony_count").and_then(|x| x.as_f64()) {
        o.max_pony_count = (x as i32).clamp(0, 10000);
    }
    f(v, "time_factor", &mut o.time_factor, 0.1, 10.0);
    f(v, "scale_factor", &mut o.scale_factor, 0.25, 4.0);
    if let Some(z) = v.get("exclusion_zone").and_then(|x| x.as_array()) {
        if z.len() == 4 {
            let g = |i: usize| z[i].as_f64().unwrap_or(0.0).clamp(0.0, 1.0) as f32;
            let mut r = RectF::new(g(0), g(1), g(2), g(3));
            if r.x + r.w > 1.0 {
                r.w = 1.0 - r.x;
            }
            if r.y + r.h > 1.0 {
                r.h = 1.0 - r.y;
            }
            o.exclusion_zone = r;
        }
    }
    if let Some(s) = v.get("screens").and_then(|x| x.as_array()) {
        o.screens = s.iter().filter_map(|x| x.as_str().map(String::from)).collect();
    }
    if let Some(r) = v.get("allowed_region") {
        o.allowed_region = match r.as_array() {
            Some(a) if a.len() == 4 => {
                let g = |i: usize| a[i].as_i64().unwrap_or(0) as i32;
                let rr = RectI::new(g(0), g(1), g(2), g(3));
                if rr.w > 0 && rr.h > 0 { Some(rr) } else { None }
            }
            _ => None,
        };
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn options_json_roundtrip() {
        let mut o = Options::default();
        o.scale_factor = 2.0;
        o.screens = vec!["\\\\.\\DISPLAY1".into()];
        o.allowed_region = Some(RectI::new(1, 2, 300, 400));
        let j = options_to_json(&o);
        let mut o2 = Options::default();
        apply_options_json(&mut o2, &j);
        assert_eq!(o2.scale_factor, 2.0);
        assert_eq!(o2.screens, o.screens);
        assert_eq!(o2.allowed_region, o.allowed_region);
        // частичный объект с выходом за диапазон
        apply_options_json(&mut o2, &json!({"scale_factor": 99, "pony_speech_chance": -3, "allowed_region": null}));
        assert_eq!(o2.scale_factor, 4.0);
        assert_eq!(o2.pony_speech_chance, 0.0);
        assert!(o2.allowed_region.is_none());
    }

    #[test]
    fn ponies_have_previews_and_tags() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let c = PonyCollection::load(&root, true);
        let j = ponies_json(&c);
        let arr = j.as_array().unwrap();
        assert!(arr.len() > 250);
        let with_preview = arr.iter().filter(|p| p["p"].is_string()).count();
        assert!(with_preview as f64 > arr.len() as f64 * 0.95, "previews: {}/{}", with_preview, arr.len());
        let tj = all_tags(&c, &["Faves".to_string()]);
        assert!(tj.iter().any(|t| t == "Main Ponies") && tj.iter().any(|t| t == "Faves"));
        let tw = arr.iter().find(|p| p["d"] == "Twilight Sparkle").unwrap();
        assert!(tw["p"].as_str().unwrap().starts_with("Ponies/Twilight Sparkle/"));
        assert!(houses_json(&c).as_array().unwrap().len() >= 8);
    }
}
