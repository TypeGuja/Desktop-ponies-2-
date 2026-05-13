// src_rust/context_menu.rs

#[derive(Clone, Debug, PartialEq)]
pub enum PonyAction {
    Drag,              // Взять и перетаскивать
    Boop,              // Бопнуть по носику
    Feed,              // Покормить
    Pet,               // Погладить
    ChangeDirection,   // Развернуть
    ToggleSleep,       // Усыпить/разбудить
    SendHome,          // Отправить домой
}

#[derive(Clone, Debug)]
pub struct MenuItem {
    pub label: String,
    pub action: PonyAction,
    pub enabled: bool,
}

impl MenuItem {
    pub fn new(label: &str, action: PonyAction) -> Self {
        Self {
            label: label.to_string(),
            action,
            enabled: true,
        }
    }
}

pub struct ContextMenu {
    pub visible: bool,
    pub x: f32,
    pub y: f32,
    pub pony_index: Option<usize>,
    pub pony_name: Option<String>,
    pub items: Vec<MenuItem>,
}

impl ContextMenu {
    pub fn new() -> Self {
        Self {
            visible: false,
            x: 0.0,
            y: 0.0,
            pony_index: None,
            pony_name: None,
            items: vec![
                MenuItem::new("👆 Взять", PonyAction::Drag),
                MenuItem::new("👃 Боп!", PonyAction::Boop),
                MenuItem::new("🍎 Покормить", PonyAction::Feed),
                MenuItem::new("✋ Погладить", PonyAction::Pet),
                MenuItem::new("↔ Развернуть", PonyAction::ChangeDirection),
                MenuItem::new("😴 Спать", PonyAction::ToggleSleep),
                MenuItem::new("🏠 Отправить домой", PonyAction::SendHome),
            ],
        }
    }

    pub fn show(&mut self, x: f32, y: f32, pony_index: usize, pony_name: &str) {
        self.visible = true;
        self.x = x;
        self.y = y;
        self.pony_index = Some(pony_index);
        self.pony_name = Some(pony_name.to_string());

        // Можно обновить пункт "Спать" в зависимости от состояния
        // если бы был доступ к состоянию пони
    }

    pub fn hide(&mut self) {
        self.visible = false;
        self.pony_index = None;
        self.pony_name = None;
    }

    pub fn hit_test(&self, mouse_x: f32, mouse_y: f32) -> Option<usize> {
        if !self.visible {
            return None;
        }

        let item_height = 28.0;
        let menu_width = 180.0;
        let padding = 4.0;

        let menu_height = self.items.len() as f32 * item_height + padding * 2.0;

        // Проверяем, что мышь в пределах меню
        if mouse_x >= self.x && mouse_x <= self.x + menu_width &&
            mouse_y >= self.y && mouse_y <= self.y + menu_height {
            let rel_y = mouse_y - self.y - padding;
            if rel_y >= 0.0 {
                let index = (rel_y / item_height) as usize;
                if index < self.items.len() && self.items[index].enabled {
                    return Some(index);
                }
            }
        }
        None
    }
}