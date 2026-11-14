mod protocol;
mod scorer;

use deepspam_model::DeepSpam;
use protocol::{read_packet, write_packet, Action, Session};
use scorer::Scorer;
use std::{error::Error, path::PathBuf, sync::Arc};
use tokio::{
    net::{TcpListener, TcpStream},
    task::JoinSet,
};

struct Config {
    listen: String,
    model_dir: PathBuf,
    weights: PathBuf,
    workers: usize,
    cache_entries: usize,
    res_log: Option<PathBuf>,
    max_message: usize,
    max_frame: usize,
    check: Option<PathBuf>,
}
impl Config {
    fn parse() -> Result<Option<Self>, Box<dyn Error>> {
        let mut c = Self {
            listen: "127.0.0.1:1081".into(),
            model_dir: "model".into(),
            weights: "deepspam_weights.npz".into(),
            workers: std::thread::available_parallelism()?.get(),
            cache_entries: 10000,
            res_log: Some("deepspam2.res".into()),
            max_message: 100 * 1024 * 1024,
            max_frame: 16 * 1024 * 1024,
            check: None,
        };
        let mut args = std::env::args().skip(1);
        while let Some(arg) = args.next() {
            if arg == "--help" || arg == "-h" {
                println!("deepspam4 [options]\n  --listen IP:PORT           default 127.0.0.1:1081\n  --model-dir DIR            default model\n  --weights FILE             relative to model-dir, or absolute\n  --workers N                concurrent CPU inference jobs (default CPU count)\n  --cache-entries N          default 10000, 0 disables cache\n  --res-log FILE             default deepspam2.res\n  --no-res-log               disable result/token log\n  --max-message-bytes N      default 104857600\n  --max-frame-bytes N        default 16777216\n  --check FILE               score one .eml file and exit");
                return Ok(None);
            }
            if arg == "--no-res-log" {
                c.res_log = None;
                continue;
            }
            let value = args
                .next()
                .ok_or_else(|| format!("missing value for {arg}"))?;
            match arg.as_str() {
                "--listen" => c.listen = value,
                "--model-dir" => c.model_dir = value.into(),
                "--weights" => c.weights = value.into(),
                "--workers" => c.workers = value.parse()?,
                "--cache-entries" => c.cache_entries = value.parse()?,
                "--res-log" => c.res_log = Some(value.into()),
                "--max-message-bytes" => c.max_message = value.parse()?,
                "--max-frame-bytes" => c.max_frame = value.parse()?,
                "--check" => c.check = Some(value.into()),
                _ => return Err(format!("unknown argument: {arg}").into()),
            }
        }
        if c.workers == 0 || c.max_message == 0 || c.max_frame == 0 {
            return Err("workers and size limits must be positive".into());
        }
        Ok(Some(c))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let Some(config) = Config::parse()? else {
        return Ok(());
    };
    let model = DeepSpam::load_with_weights(&config.model_dir, &config.weights)?;
    eprintln!(
        "MODEL: vocab={} embed={} params={} workers={}",
        model.network.vocab_size(),
        model.network.embedding_dim(),
        model.network.parameter_count(),
        config.workers
    );
    let scorer = Arc::new(Scorer::new(
        model,
        config.workers,
        config.cache_entries,
        config.res_log.as_deref(),
    ));
    if let Some(path) = config.check {
        let result = scorer
            .score(std::fs::read(path)?)
            .await
            .map_err(std::io::Error::other)?;
        println!("X-deepspam: {}", protocol::verdict(result.percent));
        return Ok(());
    }
    let listener = TcpListener::bind(&config.listen).await?;
    eprintln!("Serving on {}", listener.local_addr()?);
    let mut connections = JoinSet::new();
    let shutdown = shutdown_signal();
    tokio::pin!(shutdown);
    loop {
        tokio::select! {
            _ = &mut shutdown => break,
            accept = listener.accept() => {
                let (stream, addr) = accept?;
                let scorer = Arc::clone(&scorer);
                let (max_message, max_frame) = (config.max_message, config.max_frame);
                connections.spawn(async move {
                    if let Err(e) = connection(stream, scorer, max_message, max_frame).await { eprintln!("{addr}: {e}"); }
                });
            }
            Some(result) = connections.join_next(), if !connections.is_empty() => {
                if let Err(e) = result { eprintln!("connection task: {e}"); }
            }
        }
    }
    connections.abort_all();
    while connections.join_next().await.is_some() {}
    Ok(())
}

async fn connection(
    mut stream: TcpStream,
    scorer: Arc<Scorer>,
    max_message: usize,
    max_frame: usize,
) -> std::io::Result<()> {
    stream.set_nodelay(true)?;
    let addr = stream.peer_addr()?;
    let mut session = Session::new(max_message);
    while let Some(packet) = read_packet(&mut stream, max_frame).await? {
        match session.command(&packet)? {
            Action::Quit => break,
            Action::None => {}
            Action::Reply(reply) => write_packet(&mut stream, &reply).await?,
            Action::Scan(message) => match scorer.score(message).await {
                Ok(result) => {
                    eprintln!(
                        "{addr} result: {:.5} ({:.3} ms) cache={}{}",
                        result.percent,
                        result.milliseconds,
                        result.cache_len,
                        if result.cached { " hit" } else { "" }
                    );
                    let header = format!("hX-deepspam\0{}\0", protocol::verdict(result.percent));
                    write_packet(&mut stream, header.as_bytes()).await?;
                    write_packet(&mut stream, b"a").await?;
                }
                Err(error) => {
                    eprintln!("{addr} inference failed: {error}");
                    write_packet(&mut stream, b"t").await?;
                }
            },
        }
    }
    Ok(())
}

async fn shutdown_signal() {
    #[cfg(unix)]
    {
        if let Ok(mut term) =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            tokio::select! { _ = tokio::signal::ctrl_c() => {}, _ = term.recv() => {} }
            return;
        }
    }
    let _ = tokio::signal::ctrl_c().await;
}
