// src_rust/lib.rs
pub mod loader;
pub mod math;
pub mod skeleton;
pub mod animation;
pub mod verlet;
pub mod pony;
pub mod pony_factory;
pub mod pose_generator;
pub mod world;
pub mod interaction;
pub mod ai_controller;
pub mod python_bridge;
pub mod btcx;
pub mod texture;
pub mod monitor_manager;
pub mod settings;
pub mod performance;
pub mod editor;
pub mod context_menu;
pub mod pony_interaction;

// Re-export основных типов для удобства
pub use loader::{DesktopPoniesLoader, MovementType, Behavior};
pub use pony::PonyEntity;
pub use pony_interaction::{PonyInteractionSystem, PonyInteractionData, InteractionState};
pub use context_menu::{ContextMenu, PonyAction};