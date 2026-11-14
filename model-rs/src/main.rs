use deepspam_model::{Cnn, DeepSpam, Preprocessor, TextProcessor, Workspace, MAX_BLOCK};
use std::{
    error::Error,
    io::{self, BufRead, Write},
    path::PathBuf,
};

fn main() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args().skip(1);
    let mut dir = PathBuf::from("model");
    let mut weights = PathBuf::from("deepspam_weights.npz");
    let mut command = String::from("score");
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--model-dir" => dir = args.next().ok_or("missing model directory")?.into(),
            "--weights" => weights = args.next().ok_or("missing weights filename")?.into(),
            "preprocess" | "tokenize" | "score" | "score-ids" => command = arg,
            "--help" | "-h" => {
                println!("deepspam-model [--model-dir model] [--weights deepspam_weights.npz] [preprocess|tokenize|score|score-ids]\nReads one input per stdin line. score-ids: space-separated IDs -> percent, logit0, logit1 (tab separated).");
                return Ok(());
            }
            _ => return Err(format!("unknown argument: {arg}").into()),
        }
    }
    let mut out = io::BufWriter::new(io::stdout().lock());
    if command == "preprocess" {
        let prep = Preprocessor::load(dir.join("unicodes6x.map"))?;
        for line in io::stdin().lock().lines() {
            writeln!(out, "{}", prep.process(&line?))?;
        }
    } else if command == "tokenize" {
        let text = TextProcessor::load(&dir)?;
        for line in io::stdin().lock().lines() {
            writeln!(out, "{}", text.pieces(&text.tokenize(&line?)?)?)?;
        }
    } else if command == "score-ids" {
        let network = Cnn::load(dir.join(weights))?;
        let mut ws = Workspace::default();
        for line in io::stdin().lock().lines() {
            let mut ids = line?
                .split_whitespace()
                .map(str::parse)
                .collect::<Result<Vec<i32>, _>>()?;
            ids.truncate(MAX_BLOCK);
            ids.resize(MAX_BLOCK, 0);
            let logits = network.logits(&ids, &mut ws)?;
            writeln!(
                out,
                "{:.9}\t{:.9}\t{:.9}",
                Cnn::percent(logits)?,
                logits[0],
                logits[1]
            )?;
        }
    } else {
        let model = DeepSpam::load_with_weights(&dir, weights)?;
        let mut ws = Workspace::default();
        for line in io::stdin().lock().lines() {
            writeln!(out, "{:.9}", model.predict(&line?, &mut ws)?.percent)?;
        }
    }
    Ok(())
}
