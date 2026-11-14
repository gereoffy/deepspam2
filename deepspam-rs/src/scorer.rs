use deepspam_model::{DeepSpam, Workspace};
use std::{
    collections::{HashMap, VecDeque},
    fs::{File, OpenOptions},
    io::Write,
    path::Path,
    sync::{Arc, Mutex},
    time::Instant,
};
use tokio::sync::Semaphore;

type Key = (String, String);
struct Cache {
    values: HashMap<Arc<Key>, f64>,
    order: VecDeque<Arc<Key>>,
    capacity: usize,
}
impl Cache {
    fn new(capacity: usize) -> Self {
        Self {
            values: HashMap::new(),
            order: VecDeque::new(),
            capacity,
        }
    }
    fn insert(&mut self, key: Key, score: f64) {
        if self.capacity == 0 || self.values.contains_key(&key) {
            return;
        }
        while self.values.len() >= self.capacity {
            if let Some(old) = self.order.pop_front() {
                self.values.remove(&old);
            }
        }
        let key = Arc::new(key);
        self.order.push_back(Arc::clone(&key));
        self.values.insert(key, score);
    }
}

pub struct Scorer {
    model: DeepSpam,
    slots: Arc<Semaphore>,
    workspaces: Mutex<Vec<Workspace>>,
    cache: Mutex<Cache>,
    log: Option<Mutex<File>>,
}
pub struct Scored {
    pub percent: f64,
    pub cached: bool,
    pub cache_len: usize,
    pub milliseconds: f64,
}
impl Scorer {
    pub fn new(model: DeepSpam, workers: usize, cache_entries: usize, log: Option<&Path>) -> Self {
        // Logging is best effort, as in the Python do_eml(): an unavailable log
        // must not prevent mail classification.
        let log = log.and_then(
            |p| match OpenOptions::new().create(true).append(true).open(p) {
                Ok(file) => Some(Mutex::new(file)),
                Err(error) => {
                    eprintln!("result log {}: {error}", p.display());
                    None
                }
            },
        );
        Self {
            model,
            slots: Arc::new(Semaphore::new(workers)),
            workspaces: Mutex::new(Vec::new()),
            cache: Mutex::new(Cache::new(cache_entries)),
            log,
        }
    }
    pub async fn score(self: &Arc<Self>, message: Vec<u8>) -> Result<Scored, String> {
        let start = Instant::now();
        let permit = Arc::clone(&self.slots)
            .acquire_owned()
            .await
            .map_err(|e| e.to_string())?;
        let scorer = Arc::clone(self);
        tokio::task::spawn_blocking(move || {
            let _permit = permit;
            let key = eml2str::eml2str(&message).map_err(|e| format!("eml2str: {e}"))?;
            {
                let cache = scorer.cache.lock().map_err(|e| e.to_string())?;
                if let Some(&percent) = cache.values.get(&key) {
                    return Ok(Scored {
                        percent,
                        cached: true,
                        cache_len: cache.values.len(),
                        milliseconds: start.elapsed().as_secs_f64() * 1000.0,
                    });
                }
            }
            let mut ws = scorer
                .workspaces
                .lock()
                .map_err(|e| e.to_string())?
                .pop()
                .unwrap_or_default();
            let prediction = scorer.model.predict_mail(&key.0, &key.1, &mut ws);
            scorer
                .workspaces
                .lock()
                .map_err(|e| e.to_string())?
                .push(ws);
            let prediction = prediction.map_err(|e| e.to_string())?;
            if let Some(log) = &scorer.log {
                let tokens = scorer
                    .model
                    .text
                    .pieces(&prediction.log_tokens)
                    .map_err(|e| e.to_string())?;
                let line = format!("{:3}%: {tokens}\n", prediction.percent as i32);
                if let Err(e) = log
                    .lock()
                    .map_err(|e| e.to_string())?
                    .write_all(line.as_bytes())
                {
                    eprintln!("result log: {e}");
                }
            }
            let mut cache = scorer.cache.lock().map_err(|e| e.to_string())?;
            cache.insert(key, prediction.percent);
            Ok(Scored {
                percent: prediction.percent,
                cached: false,
                cache_len: cache.values.len(),
                milliseconds: start.elapsed().as_secs_f64() * 1000.0,
            })
        })
        .await
        .map_err(|e| e.to_string())?
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_cache_keeps_latest_entries_and_can_be_disabled() {
        let key = |s: &str| (String::new(), s.to_owned());
        let mut c = Cache::new(2);
        c.insert(key("a"), 1.0);
        c.insert(key("b"), 2.0);
        c.insert(key("a"), 1.0);
        c.insert(key("c"), 3.0);
        assert!(!c.values.contains_key(&key("a")));
        assert_eq!(c.values.get(&key("c")), Some(&3.0));
        assert_eq!(c.order.len(), 2);
        let mut c = Cache::new(0);
        c.insert(key("a"), 1.0);
        assert!(c.values.is_empty());
    }
}
