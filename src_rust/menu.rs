// src_rust/menu.rs
//
// Контекстное меню пони, нарисованное прямо в буфере оверлея: вложенные
// подменю ("Add Pony" -> тег -> пони), колонки для длинных списков,
// разделители, отключённые пункты. Полностью логика (раскладка, наведение,
// клики) отделена от окна, поэтому тестируется без графики.

use crate::math::RectI;
use crate::text::{fill_rect, stroke_rect, TextRenderer};

#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    RemovePony(u64),
    RemoveEvery(String),
    ToggleSleep(u64),
    ToggleSleepAll,
    AddPony(String),
    AddRandomPony,
    AddHouse(usize),
    RemoveHouse(u64),
    TakeControl(u64, u8),
    Talk(u64),
    /// Магия Луны: 0 — перенести окно, 1 — перенести иконку.
    LunaMagic(u64, u8),
    ShowOptions,
    ReturnToMenu,
    Exit,
}

#[derive(Clone, Debug)]
pub struct Item {
    pub label: String,
    pub action: Option<Action>,
    pub children: Vec<Item>,
    pub separator: bool,
    pub enabled: bool,
}

impl Item {
    pub fn action(label: &str, action: Action) -> Item {
        Item { label: label.to_string(), action: Some(action), children: Vec::new(), separator: false, enabled: true }
    }
    pub fn submenu(label: &str, children: Vec<Item>) -> Item {
        Item { label: label.to_string(), action: None, children, separator: false, enabled: true }
    }
    pub fn separator() -> Item {
        Item { label: String::new(), action: None, children: Vec::new(), separator: true, enabled: false }
    }
    pub fn disabled(label: &str) -> Item {
        Item { label: label.to_string(), action: None, children: Vec::new(), separator: false, enabled: false }
    }
}

const ITEM_H: i32 = 22;
const SEP_H: i32 = 8;
const PAD: i32 = 3;
const MIN_COL_W: i32 = 140;
const TEXT_PAD: i32 = 12;

struct Popup {
    items: Vec<Item>,
    x: i32,
    y: i32,
    col_w: i32,
    rows: usize,
    cols: usize,
    w: i32,
    h: i32,
    hover: Option<usize>,
    /// Пункт родительского попапа, раскрывший это подменю.
    parent_item: Option<usize>,
}

impl Popup {
    fn item_rect(&self, idx: usize) -> RectI {
        let col = idx / self.rows;
        let row = idx % self.rows;
        let y_off: i32 = self.items[col * self.rows..idx]
            .iter()
            .map(|i| if i.separator { SEP_H } else { ITEM_H })
            .sum();
        let _ = row;
        let h = if self.items[idx].separator { SEP_H } else { ITEM_H };
        RectI::new(self.x + PAD + col as i32 * self.col_w, self.y + PAD + y_off, self.col_w, h)
    }

    fn contains(&self, x: i32, y: i32) -> bool {
        x >= self.x && x < self.x + self.w && y >= self.y && y < self.y + self.h
    }

    fn item_at(&self, x: i32, y: i32) -> Option<usize> {
        if !self.contains(x, y) {
            return None;
        }
        (0..self.items.len()).find(|i| self.item_rect(*i).contains_point(x, y))
    }
}

pub struct Menu {
    popups: Vec<Popup>,
    bounds: RectI,
}

pub enum Click {
    /// Клик мимо меню — меню надо закрыть.
    Outside,
    /// Клик по пункту с подменю / разделителю / отключённому: ничего не делаем.
    Nothing,
    Action(Action),
}

impl Menu {
    pub fn open(items: Vec<Item>, x: i32, y: i32, bounds: RectI, tr: &mut TextRenderer) -> Menu {
        let mut m = Menu { popups: Vec::new(), bounds };
        m.push_popup(items, x, y, None, tr);
        m
    }

    fn layout(items: &[Item], bounds: RectI, tr: &mut TextRenderer) -> (i32, usize, usize, i32, i32) {
        let mut col_w = MIN_COL_W;
        for it in items {
            let arrow = if it.children.is_empty() { 0 } else { 14 };
            col_w = col_w.max(tr.measure(&it.label).ceil() as i32 + TEXT_PAD * 2 + arrow);
        }
        let max_h = (bounds.h - 16).max(ITEM_H * 4);
        let max_rows = (((max_h - 2 * PAD) / ITEM_H).max(4)) as usize;
        let rows = items.len().min(max_rows).max(1);
        let cols = items.len().div_ceil(rows);
        // Высота: самая высокая колонка.
        let h = (0..cols)
            .map(|c| {
                items[c * rows..((c + 1) * rows).min(items.len())]
                    .iter()
                    .map(|i| if i.separator { SEP_H } else { ITEM_H })
                    .sum::<i32>()
            })
            .max()
            .unwrap_or(ITEM_H)
            + PAD * 2;
        (col_w, rows, cols, cols as i32 * col_w + PAD * 2, h)
    }

    fn push_popup(&mut self, items: Vec<Item>, x: i32, y: i32, parent_item: Option<usize>, tr: &mut TextRenderer) {
        let (col_w, rows, cols, w, h) = Menu::layout(&items, self.bounds, tr);
        let mut px = x;
        let mut py = y;
        if px + w > self.bounds.right() {
            px = (self.bounds.right() - w).max(self.bounds.x);
        }
        if py + h > self.bounds.bottom() {
            py = (self.bounds.bottom() - h).max(self.bounds.y);
        }
        self.popups.push(Popup { items, x: px, y: py, col_w, rows, cols, w, h, hover: None, parent_item });
    }

    pub fn contains(&self, x: i32, y: i32) -> bool {
        self.popups.iter().any(|p| p.contains(x, y))
    }

    /// Обновляет подсветку и раскрывает/сворачивает подменю по положению курсора.
    pub fn hover(&mut self, x: i32, y: i32, tr: &mut TextRenderer) {
        // Самый глубокий попап под курсором.
        let Some(level) = (0..self.popups.len()).rev().find(|k| self.popups[*k].contains(x, y)) else {
            return;
        };
        let item = self.popups[level].item_at(x, y);
        self.popups[level].hover = item.filter(|i| self.popups[level].items[*i].enabled);
        // Закрываем более глубокие уровни.
        let keep_child = item
            .filter(|i| self.popups[level].items[*i].enabled && !self.popups[level].items[*i].children.is_empty());
        if self.popups.len() > level + 1 && self.popups[level + 1].parent_item != keep_child {
            self.popups.truncate(level + 1);
        }
        if let Some(i) = keep_child {
            if self.popups.len() == level + 1 {
                let r = self.popups[level].item_rect(i);
                let children = self.popups[level].items[i].children.clone();
                self.push_popup(children, r.x + r.w - 2, r.y - PAD, Some(i), tr);
                let last = self.popups.len() - 1;
                self.popups[last].hover = None;
            }
        }
    }

    pub fn click(&mut self, x: i32, y: i32) -> Click {
        let Some(level) = (0..self.popups.len()).rev().find(|k| self.popups[*k].contains(x, y)) else {
            return Click::Outside;
        };
        match self.popups[level].item_at(x, y) {
            Some(i) => {
                let it = &self.popups[level].items[i];
                if !it.enabled || it.separator {
                    return Click::Nothing;
                }
                match &it.action {
                    Some(a) => Click::Action(a.clone()),
                    None => Click::Nothing,
                }
            }
            None => Click::Nothing,
        }
    }

    pub fn draw(&self, buf: &mut [u32], bw: usize, bh: usize, origin: (i32, i32), tr: &mut TextRenderer) {
        let bg = 0xFFF3F3F3;
        let border = 0xFF8B8B8B;
        let hover_bg = 0xFFCCE4F7;
        let text_c = 0xFF1B1B1B;
        let dis_c = 0xFF9A9A9A;
        let sep_c = 0xFFD0D0D0;
        for p in &self.popups {
            let (px, py) = (p.x - origin.0, p.y - origin.1);
            fill_rect(buf, bw, bh, px, py, p.w, p.h, bg);
            stroke_rect(buf, bw, bh, px, py, p.w, p.h, border);
            for (i, it) in p.items.iter().enumerate() {
                let r = p.item_rect(i);
                let (rx, ry) = (r.x - origin.0, r.y - origin.1);
                if it.separator {
                    fill_rect(buf, bw, bh, rx + 6, ry + SEP_H / 2, r.w - 12, 1, sep_c);
                    continue;
                }
                if p.hover == Some(i) {
                    fill_rect(buf, bw, bh, rx + 1, ry, r.w - 2, r.h, hover_bg);
                }
                let color = if it.enabled { text_c } else { dis_c };
                let ty = ry as f32 + (r.h as f32 - tr.line_height()) / 2.0;
                tr.draw_line(buf, bw, bh, (rx + TEXT_PAD) as f32, ty, &it.label, color);
                if !it.children.is_empty() {
                    tr.draw_line(buf, bw, bh, (rx + r.w - 14) as f32, ty, "\u{25B8}", color);
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tr() -> Option<TextRenderer> {
        TextRenderer::load(12.0)
    }

    fn items() -> Vec<Item> {
        vec![
            Item::action("Remove", Action::RemovePony(1)),
            Item::separator(),
            Item::submenu(
                "Add Pony",
                vec![Item::submenu("Main", vec![Item::action("Twilight", Action::AddPony("Twilight".into()))])],
            ),
            Item::disabled("Nope"),
            Item::action("Exit", Action::Exit),
        ]
    }

    #[test]
    fn opens_submenus_on_hover_and_clicks_actions() {
        let Some(mut t) = tr() else { return };
        let bounds = RectI::new(0, 0, 1000, 800);
        let mut m = Menu::open(items(), 100, 100, bounds, &mut t);
        assert!(m.contains(105, 105));
        assert!(!m.contains(5, 5));
        // клик по "Remove"
        match m.click(110, 103 + 11) {
            Click::Action(Action::RemovePony(1)) => {}
            _ => panic!("expected Remove"),
        }
        // наведение на "Add Pony" (3-й элемент: Remove 22 + sep 8)
        let y_add = 100 + PAD + ITEM_H + SEP_H + ITEM_H / 2;
        m.hover(110, y_add, &mut t);
        assert_eq!(m.popups.len(), 2, "submenu opened");
        let sub = &m.popups[1];
        let (sx, sy) = (sub.x + 20, sub.y + PAD + 5);
        m.hover(sx, sy, &mut t);
        assert_eq!(m.popups.len(), 3, "nested submenu opened");
        let s3 = &m.popups[2];
        match m.click(s3.x + 20, s3.y + PAD + 5) {
            Click::Action(Action::AddPony(n)) => assert_eq!(n, "Twilight"),
            _ => panic!("expected AddPony"),
        }
        // возврат к корню закрывает подменю
        m.hover(110, 100 + PAD + 5, &mut t);
        assert_eq!(m.popups.len(), 1);
        // клик мимо
        assert!(matches!(m.click(900, 700), Click::Outside));
        // отключённый пункт
        let y_dis = 100 + PAD + ITEM_H + SEP_H + ITEM_H + ITEM_H / 2;
        assert!(matches!(m.click(110, y_dis), Click::Nothing));
    }

    #[test]
    fn long_lists_use_columns_and_stay_on_screen() {
        let Some(mut t) = tr() else { return };
        let bounds = RectI::new(0, 0, 1200, 600);
        let many: Vec<Item> = (0..120).map(|i| Item::action(&format!("Pony number {}", i), Action::AddPony(i.to_string()))).collect();
        let m = Menu::open(many, 1000, 500, bounds, &mut t);
        let p = &m.popups[0];
        assert!(p.cols > 1, "must use several columns, got {}", p.cols);
        assert!(p.x >= 0 && p.x + p.w <= 1200 && p.y >= 0 && p.y + p.h <= 600, "popup within bounds");
        // каждый пункт достижим кликом
        let mut m = m;
        for idx in [0usize, 60, 119] {
            let r = m.popups[0].item_rect(idx);
            match m.click(r.x + 10, r.y + 5) {
                Click::Action(Action::AddPony(n)) => assert_eq!(n, idx.to_string()),
                _ => panic!("item {} unreachable", idx),
            }
        }
    }
}
