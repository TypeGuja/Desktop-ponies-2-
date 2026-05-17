// src_rust/editor/ini_writer.rs

use std::fs;
use crate::loader::PonyConfig;

/// Записывает конфигурацию пони обратно в pony.ini
pub fn write_pony_config(config: &PonyConfig) -> Result<(), String> {
    let ini_path = config.directory.join("pony.ini");

    let mut content = String::new();

    // Name
    if !config.name.is_empty() {
        content.push_str(&format!("Name,\"{}\"\n", config.name));
    }

    // Categories
    if !config.categories.is_empty() {
        content.push_str("Categories");
        for cat in &config.categories {
            content.push_str(&format!(",\"{}\"", cat));
        }
        content.push('\n');
    }

    // Behaviors - 27 аргументов для 27 позиций
    for behavior in &config.behaviors {
        content.push_str(&format!(
            "Behavior,\"{}\",{},{},{},{},\"{}\",\"{}\",{},\"{}\",\"{}\",\"{}\",{},{},{},\"{}\",{},\"{}\",\"{}\",\"{}\",\"{}\",{},{},\"{}\",\"{}\",{:?},{:?},\n",
            behavior.name,
            behavior.probability,
            behavior.max_duration,
            behavior.min_duration,
            behavior.speed,
            behavior.sprite_right,
            behavior.sprite_left,
            behavior.movement,
            behavior.linked_behavior,
            behavior.start_speech,
            behavior.end_speech,
            behavior.skip,
            behavior.target_x,
            behavior.target_y,
            behavior.follow_target,
            behavior.auto_select_follow,
            behavior.follow_stopped,
            behavior.follow_moving,
            format!("{:.0},{:.0}", behavior.right_image_center.0, behavior.right_image_center.1),
            format!("{:.0},{:.0}", behavior.left_image_center.0, behavior.left_image_center.1),
            behavior.prevent_loop,
            behavior.group,
            behavior.follow_offset,
            behavior.set_animation_speed.unwrap_or(0.0),
            behavior.set_fps.unwrap_or(0.0),
            behavior.sound_files
        ));
    }

    // Speaks
    for speak in &config.speaks {
        let sound_files = if speak.sound_files.is_empty() {
            "".to_string()
        } else {
            format!("{{{}}}", speak.sound_files.iter().map(|s| format!("\"{}\"", s)).collect::<Vec<_>>().join(","))
        };
        content.push_str(&format!(
            "Speak,\"{}\",\"{}\",{},{},0\n",
            speak.name, speak.text, sound_files, speak.skip
        ));
    }

    // Interactions
    for interaction in &config.interactions {
        let targets = format!("{{{}}}", interaction.targets.iter().map(|t| format!("\"{}\"", t)).collect::<Vec<_>>().join(","));
        let behaviors = format!("{{{}}}", interaction.behaviors.iter().map(|b| format!("\"{}\"", b)).collect::<Vec<_>>().join(","));
        content.push_str(&format!(
            "Interaction,\"{}\",{},{},{},{},{},{}\n",
            interaction.name,
            interaction.probability,
            interaction.cooldown,
            targets,
            interaction.target_count,
            behaviors,
            interaction.duration
        ));
    }

    // Effects
    for effect in &config.effects {
        content.push_str(&format!(
            "Effect,\"{}\",\"{}\",\"{}\",\"{}\",{},{},Center,Center,Center,Center,False,False\n",
            effect.name,
            effect.linked,
            effect.sprite_right,
            effect.sprite_left,
            effect.duration,
            effect.delay
        ));
    }

    fs::write(&ini_path, content)
        .map_err(|e| format!("Failed to write pony.ini: {}", e))?;

    println!("[Editor] Saved config to: {:?}", ini_path);
    Ok(())
}