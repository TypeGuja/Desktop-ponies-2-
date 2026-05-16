// src_rust/pony_interaction.rs
use crate::loader::{DesktopPoniesLoader, MovementType};

// Определяем InteractionState здесь, так как он используется в библиотеке
#[derive(Clone, Debug)]
pub enum InteractionState {
    Booped { timer: f32 },
    Fed { timer: f32, original_speed_mult: f32 },
    Petted { timer: f32 },
    Sleeping,
}

// Определяем структуру Pony здесь для использования в библиотеке
pub struct PonyInteractionData {
    pub x: f32,
    pub y: f32,
    pub vx: f32,
    pub vy: f32,
    pub frames: Vec<Vec<u32>>,
    pub frame_count: u32,
    pub width: u32,
    pub height: u32,
    pub current_frame: u32,
    pub frame_timer: f32,
    pub frame_duration: f32,
    pub facing_right: bool,
    pub config_name: String,
    pub current_behavior: String,
    pub movement_type: MovementType,
    pub behavior_timer: f32,
    pub interaction_state: Option<InteractionState>,
    pub original_frame_duration: Option<f32>,
    pub grabbed: bool,
}

pub struct PonyInteractionSystem;

impl PonyInteractionSystem {
    /// Бопнуть пони - подпрыгивает и ускоряется
    pub fn boop_pony(pony: &mut PonyInteractionData) {
        pony.vy = -250.0;
        pony.vx = if fastrand::bool() { 100.0 } else { -100.0 };
        pony.frame_timer = 0.0;
        pony.movement_type = MovementType::HorizontalOnly;

        pony.interaction_state = Some(InteractionState::Booped {
            timer: 2.0
        });

        pony.behavior_timer = 2.0;
    }

    /// Погладить пони - останавливается и замедляется
    pub fn pet_pony(pony: &mut PonyInteractionData) {
        pony.vx = 0.0;
        pony.vy = 0.0;
        pony.movement_type = MovementType::None;

        if pony.original_frame_duration.is_none() {
            pony.original_frame_duration = Some(pony.frame_duration);
        }
        pony.frame_duration *= 1.8;

        pony.interaction_state = Some(InteractionState::Petted {
            timer: 4.0
        });

        pony.behavior_timer = 5.0;
    }

    /// Покормить пони - ускоряется и радуется
    pub fn feed_pony(pony: &mut PonyInteractionData) {
        let speed_mult = 1.8;
        pony.vx *= speed_mult;
        pony.vy *= speed_mult;

        if pony.original_frame_duration.is_none() {
            pony.original_frame_duration = Some(pony.frame_duration);
        }
        pony.frame_duration *= 0.6;

        pony.interaction_state = Some(InteractionState::Fed {
            timer: 3.0,
            original_speed_mult: speed_mult,
        });

        pony.behavior_timer = 3.0;
    }

    /// Развернуть пони в другую сторону
    pub fn change_direction(pony: &mut PonyInteractionData) {
        pony.facing_right = !pony.facing_right;
        pony.vx *= -1.0;
    }

    /// Взять пони (drag) - переключает на drag-анимацию
    pub fn drag_pony(pony: &mut PonyInteractionData, loader: &mut DesktopPoniesLoader) {
        // Сохраняем оригинальную длительность
        if pony.original_frame_duration.is_none() {
            pony.original_frame_duration = Some(pony.frame_duration);
        }

        // Сначала получаем имя пони (чтобы не держать заимствование)
        let pony_name = pony.config_name.clone();

        // Теперь ищем drag-поведение
        let drag_info = if let Some(config) = loader.get_config(&pony_name) {
            config.behaviors.iter()
                .find(|b| b.name.to_lowercase().contains("drag"))
                .map(|behavior| {
                    let sprite_name = if !behavior.sprite_right.is_empty() {
                        behavior.sprite_right.clone()
                    } else {
                        behavior.sprite_left.clone()
                    };
                    (sprite_name, behavior.name.clone())
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name)) = drag_info {
            let (frames, fc, w, h, delay) = loader.load_pony_frames(&pony_name, &sprite_name);
            pony.frames = frames;
            pony.frame_count = fc;
            pony.width = w;
            pony.height = h;
            pony.frame_duration = delay;
            pony.current_frame = 0;
            pony.current_behavior = behavior_name;
            pony.movement_type = MovementType::Dragged;
        } else {
            pony.frame_duration *= 1.5;
        }

        pony.grabbed = true;
        println!("[Interaction] Drag pony '{}'", pony.config_name);
    }

    /// Отпустить пони - восстановить idle/stand
    pub fn release_pony(pony: &mut PonyInteractionData, loader: &mut DesktopPoniesLoader) {
        pony.grabbed = false;
        pony.movement_type = MovementType::None;
        pony.behavior_timer = 0.0;

        // Сначала получаем информацию об idle/stand поведении
        let pony_name = pony.config_name.clone();
        let idle_info = if let Some(config) = loader.get_config(&pony_name) {
            config.behaviors.iter()
                .find(|b| {
                    let name = b.name.to_lowercase();
                    name.contains("stand") || name.contains("idle") || name.contains("wake")
                })
                .map(|behavior| {
                    let sprite_name = if !behavior.sprite_right.is_empty() {
                        behavior.sprite_right.clone()
                    } else {
                        behavior.sprite_left.clone()
                    };
                    (sprite_name, behavior.name.clone())
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name)) = idle_info {
            let (frames, fc, w, h, delay) = loader.load_pony_frames(&pony_name, &sprite_name);
            pony.frames = frames;
            pony.frame_count = fc;
            pony.width = w;
            pony.height = h;
            pony.frame_duration = delay;
            pony.current_behavior = behavior_name;
        }

        // Восстанавливаем оригинальную скорость анимации
        if let Some(orig_dur) = pony.original_frame_duration {
            pony.frame_duration = orig_dur;
            pony.original_frame_duration = None;
        }

        println!("[Interaction] Released pony '{}'", pony.config_name);
    }

    /// Усыпить или разбудить пони
    pub fn toggle_sleep(pony: &mut PonyInteractionData, loader: &mut DesktopPoniesLoader) {
        if matches!(pony.interaction_state, Some(InteractionState::Sleeping)) {
            // Просыпаемся
            pony.interaction_state = None;
            pony.movement_type = MovementType::None;
            pony.behavior_timer = 0.0;

            // Сначала получаем имя спрайта, чтобы избежать конфликта заимствований
            let sprite_info = loader.get_config(&pony.config_name)
                .and_then(|config| {
                    config.behaviors.iter()
                        .find(|b| b.name.to_lowercase().contains("stand") ||
                            b.name.to_lowercase().contains("idle") ||
                            b.name.to_lowercase().contains("wake"))
                        .map(|behavior| {
                            let sprite_name = if !behavior.sprite_right.is_empty() {
                                behavior.sprite_right.clone()
                            } else {
                                behavior.sprite_left.clone()
                            };
                            (sprite_name, behavior.name.clone())
                        })
                });

            // Теперь загружаем спрайт, когда иммутабельная ссылка уже не нужна
            if let Some((sprite_name, behavior_name)) = sprite_info {
                let pony_name = pony.config_name.clone();
                let (frames, fc, w, h, delay) = loader.load_pony_frames(&pony_name, &sprite_name);
                pony.frames = frames;
                pony.frame_count = fc;
                pony.width = w;
                pony.height = h;
                pony.frame_duration = delay;
                pony.current_frame = 0;
                pony.current_behavior = behavior_name;
            }
        } else {
            // Засыпаем
            pony.vx = 0.0;
            pony.vy = 0.0;
            pony.movement_type = MovementType::Sleep;
            pony.interaction_state = Some(InteractionState::Sleeping);
            pony.behavior_timer = 999999.0;

            // Сначала получаем имя спрайта
            let sprite_info = loader.get_config(&pony.config_name)
                .and_then(|config| {
                    config.behaviors.iter()
                        .find(|b| b.name.to_lowercase().contains("sleep"))
                        .map(|behavior| {
                            let sprite_name = if !behavior.sprite_right.is_empty() {
                                behavior.sprite_right.clone()
                            } else {
                                behavior.sprite_left.clone()
                            };
                            (sprite_name, behavior.name.clone())
                        })
                });

            // Потом загружаем спрайт
            if let Some((sprite_name, behavior_name)) = sprite_info {
                let pony_name = pony.config_name.clone();
                let (frames, fc, w, h, delay) = loader.load_pony_frames(&pony_name, &sprite_name);
                pony.frames = frames;
                pony.frame_count = fc;
                pony.width = w;
                pony.height = h;
                pony.frame_duration = delay;
                pony.current_frame = 0;
                pony.current_behavior = behavior_name;
            }
        }
    }
}