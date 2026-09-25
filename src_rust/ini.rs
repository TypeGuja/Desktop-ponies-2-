// src_rust/ini.rs
//
// Токенайзер и "терпимый" парсер строк pony.ini — порт IniLineParser.vb,
// StringExtensions.SplitQualified и StringCollectionParser.vb из оригинала
// Desktop Ponies 1.69. Важна не только разбивка, но и понятие результата
// разбора (Success / Fallback / Failed): PonyBase.Load с removeInvalidItems
// выкидывает элементы с Failed, поэтому поведения с отсутствующими картинками
// в игре не используются — как и в оригинале.

/// Разбивает строку по запятым вне "квалифицированных" фрагментов.
/// qualifiers — пары (открывающий, закрывающий). Сами квалификаторы из
/// результата удаляются, а содержимое внутри копируется как есть (без
/// вложенности) — как SplitQualified. Возвращает Err, если закрывающий
/// символ не найден.
pub fn split_qualified(source: &str, sep: char, qualifiers: &[(char, char)]) -> Result<Vec<String>, ()> {
    if source.is_empty() {
        return Ok(vec![String::new()]);
    }
    let chars: Vec<char> = source.chars().collect();
    let mut segments: Vec<String> = Vec::new();
    let mut segment = String::new();
    let mut i = 0usize;
    while i <= chars.len() {
        // ближайший разделитель / открывающий квалификатор начиная с i
        let mut sep_idx = chars.len();
        let mut q_idx = chars.len();
        for (k, c) in chars.iter().enumerate().skip(i) {
            if *c == sep {
                sep_idx = k;
                break;
            }
            if qualifiers.iter().any(|(o, _)| o == c) {
                q_idx = k;
                break;
            }
        }
        if sep_idx <= q_idx {
            segment.extend(chars[i.min(chars.len())..sep_idx].iter());
            i = sep_idx + 1;
            segments.push(std::mem::take(&mut segment));
        } else {
            let open = chars[q_idx];
            let close = qualifiers.iter().find(|(o, _)| *o == open).map(|(_, c)| *c).unwrap();
            segment.extend(chars[i..q_idx].iter());
            i = q_idx + 1;
            match chars[i.min(chars.len())..].iter().position(|c| *c == close) {
                None => return Err(()),
                Some(rel) => {
                    let end = i + rel;
                    segment.extend(chars[i..end].iter());
                    i = end + 1;
                }
            }
        }
    }
    Ok(segments)
}

const Q: char = '"';

pub fn comma_split_quote(source: &str) -> Vec<String> {
    split_qualified(source, ',', &[(Q, Q)])
        .or_else(|_| split_qualified(&format!("{}{}", source, Q), ',', &[(Q, Q)]))
        .unwrap_or_else(|_| vec![source.to_string()])
}

pub fn comma_split_quote_brace(source: &str) -> Vec<String> {
    let q = &[(Q, Q), ('{', '}')];
    split_qualified(source, ',', q)
        .or_else(|_| split_qualified(&format!("{}{}", source, Q), ',', q))
        .or_else(|_| split_qualified(&format!("{}}}", source), ',', q))
        .unwrap_or_else(|_| vec![source.to_string()])
}

/// Кавычит текст для записи в ini (в тексте кавычек быть не должно — как в
/// оригинале, поэтому они заменяются на апострофы).
pub fn quoted(text: &str) -> String {
    format!("\"{}\"", text.replace('"', "'"))
}

pub fn braced(text: &str) -> String {
    format!("{{{}}}", text.replace(['{', '}'], ""))
}

// ------------------------------------------------------------------
// Результат разбора
// ------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ParseResult {
    Success,
    Fallback,
    Failed,
}

impl ParseResult {
    pub fn combine(self, other: ParseResult) -> ParseResult {
        self.max(other)
    }
}

/// Последовательный разборщик колонок строки (StringCollectionParser).
pub struct Parser {
    items: Vec<Option<String>>,
    index: usize,
    pub result: ParseResult,
    pub issues: Vec<String>,
}

impl Parser {
    pub fn new(items: Vec<String>) -> Parser {
        Parser {
            items: items.into_iter().map(Some).collect(),
            index: 0,
            result: ParseResult::Success,
            issues: Vec::new(),
        }
    }

    pub fn from_optional(items: Vec<Option<String>>) -> Parser {
        Parser { items, index: 0, result: ParseResult::Success, issues: Vec::new() }
    }

    fn next_item(&mut self) -> Option<String> {
        let item = self.items.get(self.index).cloned().flatten();
        self.index += 1;
        item
    }

    fn note(&mut self, r: ParseResult, source_present: bool, reason: &str) {
        // Использование умолчания для отсутствующей колонки — не проблема.
        let default_used = r == ParseResult::Fallback && !source_present;
        let eff = if default_used { ParseResult::Success } else { r };
        self.result = self.result.combine(eff);
        if r != ParseResult::Success && !default_used {
            self.issues.push(format!("column {}: {}", self.index - 1, reason));
        }
    }

    pub fn no_parse(&mut self) -> Option<String> {
        self.next_item()
    }

    pub fn not_null(&mut self, fallback: Option<&str>) -> Option<String> {
        let s = self.next_item();
        match (&s, fallback) {
            (Some(_), _) => s,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, false, "missing");
                Some(f.to_string())
            }
            (None, None) => {
                self.note(ParseResult::Failed, false, "value is missing");
                None
            }
        }
    }

    pub fn not_null_or_ws(&mut self, fallback: Option<&str>) -> String {
        let s = self.next_item();
        match (&s, fallback) {
            (Some(v), _) if !v.trim().is_empty() => v.clone(),
            (_, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "value is empty");
                f.to_string()
            }
            _ => {
                self.note(ParseResult::Failed, s.is_some(), "value is missing or empty");
                String::new()
            }
        }
    }

    pub fn parse_bool(&mut self, fallback: Option<bool>) -> bool {
        let s = self.next_item();
        let parsed = s.as_deref().map(|v| v.trim().to_ascii_lowercase()).and_then(|v| match v.as_str() {
            "true" => Some(true),
            "false" => Some(false),
            _ => None,
        });
        match (parsed, fallback) {
            (Some(b), _) => b,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "not a boolean");
                f
            }
            (None, None) => {
                self.note(ParseResult::Failed, s.is_some(), "not a boolean");
                false
            }
        }
    }

    pub fn parse_i32(&mut self, fallback: Option<i32>, min: i32, max: i32) -> i32 {
        let s = self.next_item();
        let parsed = s.as_deref().and_then(|v| v.trim().parse::<i32>().ok());
        let valid = parsed.filter(|v| *v >= min && *v <= max);
        match (valid, fallback) {
            (Some(v), _) => v,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "invalid or out of range integer");
                f
            }
            (None, None) => {
                self.note(ParseResult::Failed, s.is_some(), "invalid or out of range integer");
                0
            }
        }
    }

    pub fn parse_f64(&mut self, fallback: Option<f64>, min: f64, max: f64) -> f64 {
        let s = self.next_item();
        let parsed = s.as_deref().and_then(|v| v.trim().parse::<f64>().ok()).filter(|v| v.is_finite());
        let valid = parsed.filter(|v| *v >= min && *v <= max);
        match (valid, fallback) {
            (Some(v), _) => v,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "invalid or out of range number");
                f
            }
            (None, None) => {
                self.note(ParseResult::Failed, s.is_some(), "invalid or out of range number");
                0.0
            }
        }
    }

    pub fn parse_f32(&mut self, fallback: Option<f32>, min: f32, max: f32) -> f32 {
        self.parse_f64(fallback.map(|f| f as f64), min as f64, max as f64) as f32
    }

    /// "x,y" (два целых). fallback=None => ошибка.
    pub fn parse_vec2(&mut self, fallback: Option<(i32, i32)>) -> (i32, i32) {
        let s = self.next_item();
        let parsed = s.as_deref().and_then(|v| {
            let parts: Vec<&str> = v.split(',').collect();
            if parts.len() == 2 {
                Some((parts[0].trim().parse::<i32>().ok()?, parts[1].trim().parse::<i32>().ok()?))
            } else {
                None
            }
        });
        match (parsed, fallback) {
            (Some(v), _) => v,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "not a point");
                f
            }
            (None, None) => {
                self.note(ParseResult::Failed, s.is_some(), "not a point");
                (0, 0)
            }
        }
    }

    /// Следующая колонка через отображение (без учёта регистра).
    pub fn map<T: Copy>(&mut self, table: &[(&str, T)], fallback: Option<T>, default: T) -> T {
        let s = self.next_item();
        let found = s.as_deref().and_then(|v| {
            table.iter().find(|(k, _)| k.eq_ignore_ascii_case(v.trim())).map(|(_, t)| *t)
        });
        match (found, fallback) {
            (Some(v), _) => v,
            (None, Some(f)) => {
                self.note(ParseResult::Fallback, s.is_some(), "unknown value");
                f
            }
            (None, None) => {
                self.note(ParseResult::Failed, s.is_some(), "unknown value");
                default
            }
        }
    }

    /// Проверка условия (Assert). true = условие выполнено.
    pub fn assert(&mut self, condition: bool, reason: &str, with_fallback: bool) -> bool {
        if condition {
            self.note(ParseResult::Success, true, "");
        } else if with_fallback {
            self.note(ParseResult::Fallback, true, reason);
        } else {
            self.note(ParseResult::Failed, true, reason);
        }
        condition
    }

    /// Проверка существования файла. Отсутствие — Failed (или Fallback).
    pub fn file_exists(&mut self, path: &std::path::Path, with_fallback: bool) -> bool {
        let ok = path.is_file();
        self.assert(ok, &format!("file not found: {}", path.display()), with_fallback)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splits_like_original() {
        let v = comma_split_quote("Behavior,\"stand, still\",0.15,\"\",True");
        assert_eq!(v, vec!["Behavior", "stand, still", "0.15", "", "True"]);
        let v = comma_split_quote_brace("Interaction,x,0.02,500,{\"Pinkie Pie\",\"Rarity\"},One");
        assert_eq!(v[4], "\"Pinkie Pie\",\"Rarity\"");
        assert_eq!(comma_split_quote(&v[4]), vec!["Pinkie Pie", "Rarity"]);
    }

    #[test]
    fn unbalanced_quote_is_repaired() {
        let v = comma_split_quote("a,\"b");
        assert_eq!(v, vec!["a", "b"]);
    }

    #[test]
    fn parser_tracks_failures() {
        let mut p = Parser::new(vec!["x".into(), "abc".into(), "0.5".into()]);
        p.no_parse();
        assert_eq!(p.parse_f64(Some(1.0), 0.0, 1.0), 1.0);
        assert_eq!(p.result, ParseResult::Fallback);
        assert_eq!(p.parse_f64(None, 0.0, 1.0), 0.5);
        // отсутствующая колонка с умолчанием — не ошибка
        let before = p.result;
        assert_eq!(p.parse_bool(Some(true)), true);
        assert_eq!(p.result, before);
        p.parse_i32(None, 0, 10);
        assert_eq!(p.result, ParseResult::Failed);
    }
}
