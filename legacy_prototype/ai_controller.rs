// src_rust/ai_controller.rs
use std::collections::HashMap;
use crate::pony::PonyEntity;
use crate::python_bridge::{PythonBridge, AIRequest, AIResponse};

#[derive(Clone, Debug)]
pub struct AIState {
    pub pony_id: u64,
    pub conversation_history: Vec<String>,
    pub last_emotion: String,
    pub last_action: Option<String>,
    pub speech_cooldown: f32,
    pub interaction_cooldown: f32,
}

pub struct AIController {
    bridge: PythonBridge,
    pub states: HashMap<u64, AIState>,
    pub global_history: Vec<String>,
    python_path: String,
    script_path: String,
}

impl AIController {
    pub fn new(python_path: &str, script_path: &str) -> Self {
        Self {
            bridge: PythonBridge::new(),
            states: HashMap::new(),
            global_history: Vec::new(),
            python_path: python_path.to_string(),
            script_path: script_path.to_string(),
        }
    }

    pub fn start(&mut self) -> Result<(), String> {
        self.bridge.start(&self.python_path, &self.script_path)
    }

    pub fn register_pony(&mut self, pony: &PonyEntity) {
        self.states.insert(
            pony.id,
            AIState {
                pony_id: pony.id,
                conversation_history: Vec::new(),
                last_emotion: "neutral".to_string(),
                last_action: None,
                speech_cooldown: 0.0,
                interaction_cooldown: 0.0,
            },
        );
    }

    pub fn unregister_pony(&mut self, pony_id: u64) {
        self.states.remove(&pony_id);
    }

    pub fn update(&mut self, dt: f32) {
        for state in self.states.values_mut() {
            state.speech_cooldown = (state.speech_cooldown - dt).max(0.0);
            state.interaction_cooldown = (state.interaction_cooldown - dt).max(0.0);
        }
    }

    pub fn request_pony_speech(
        &mut self,
        pony: &PonyEntity,
        pony_name: &str,
        personality: &str,
    ) -> Result<Option<AIResponse>, String> {
        let state = match self.states.get(&pony.id) {
            Some(s) => s,
            None => return Ok(None),
        };

        if state.speech_cooldown > 0.0 {
            return Ok(None);
        }

        if fastrand::f32() > 0.001 {
            return Ok(None);
        }

        let request = AIRequest {
            request_id: 0,
            request_type: "spontaneous_speech".to_string(),
            text: String::new(),
            pony_name: pony_name.to_string(),
            pony_personality: Some(personality.to_string()),
            context: state.conversation_history.clone(),
            available_actions: vec![
                "idle".into(),
                "walk".into(),
                "buck".into(),
                "rear".into(),
                "pose".into(),
                "sleep".into(),
            ],
            language: "en".to_string(),
        };

        match self.bridge.send_request(request) {
            Ok(response) => {
                if let Some(state) = self.states.get_mut(&pony.id) {
                    state.conversation_history.push(response.text.clone());
                    state.last_emotion = response.emotion.clone().unwrap_or("neutral".into());
                    state.last_action = response.action.clone();
                    state.speech_cooldown = 5.0 + fastrand::f32() * 15.0;
                    if state.conversation_history.len() > 20 {
                        state.conversation_history.remove(0);
                    }
                }
                Ok(Some(response))
            }
            Err(e) => {
                eprintln!("[AI] Speech request failed: {}", e);
                Ok(None)
            }
        }
    }

    pub fn request_interaction(
        &mut self,
        pony_a: &PonyEntity,
        pony_a_name: &str,
        _pony_b: &PonyEntity,
        pony_b_name: &str,
    ) -> Result<Option<AIResponse>, String> {
        let state_a = match self.states.get(&pony_a.id) {
            Some(s) => s,
            None => return Ok(None),
        };

        if state_a.interaction_cooldown > 0.0 {
            return Ok(None);
        }

        let request = AIRequest {
            request_id: 0,
            request_type: "interaction".to_string(),
            text: format!("{} sees {}", pony_a_name, pony_b_name),
            pony_name: pony_a_name.to_string(),
            pony_personality: None,
            context: self.global_history.clone(),
            available_actions: vec![
                "walk".into(),
                "buck".into(),
                "rear".into(),
                "pose".into(),
                "conga".into(),
            ],
            language: "en".to_string(),
        };

        match self.bridge.send_request(request) {
            Ok(response) => {
                if let Some(state) = self.states.get_mut(&pony_a.id) {
                    state.interaction_cooldown = 10.0;
                }
                Ok(Some(response))
            }
            Err(e) => {
                eprintln!("[AI] Interaction request failed: {}", e);
                Ok(None)
            }
        }
    }

    pub fn is_running(&self) -> bool {
        self.bridge.is_running()
    }

    pub fn shutdown(&mut self) {
        self.bridge.shutdown();
    }
}

impl Drop for AIController {
    fn drop(&mut self) {
        self.shutdown();
    }
}