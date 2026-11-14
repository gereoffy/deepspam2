//! In-process batch=1 benchmark; data loading, warmup and output are not timed.
use deepspam_model::{DeepSpam, Workspace};
use std::{error::Error, fs, hint::black_box, path::Path, time::Instant};

fn measure(
    stage: &str,
    count: usize,
    repeats: usize,
    warmup: usize,
    output: &Path,
    mut predict: impl FnMut(usize) -> deepspam_model::Result<f64>,
) -> Result<(), Box<dyn Error>> {
    for i in 0..warmup {
        black_box(predict(i % count)?);
    }
    for pass in 0..repeats {
        let mut scores = Vec::with_capacity(count);
        let start = Instant::now();
        for i in 0..count {
            scores.push(black_box(predict(black_box(i))?));
        }
        let seconds = start.elapsed().as_secs_f64();
        println!(
            "{{\"runtime\":\"rust\",\"stage\":\"{stage}\",\"pass\":{pass},\"cases\":{count},\"seconds\":{seconds:.9},\"checksum\":{:.9}}}",
            scores.iter().sum::<f64>()
        );
        if pass == 0 {
            let text: String = scores.iter().map(|s| format!("{s:.12}\n")).collect();
            fs::write(output.join(format!("{stage}-rust.scores")), text)?;
        }
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 6 {
        return Err("benchmark MODEL_DIR INPUTS_TXT IDS_TXT OUTPUT_DIR REPEATS WARMUP".into());
    }
    let text = fs::read_to_string(&args[1])?;
    let texts: Vec<_> = text.split_terminator('\n').collect();
    let ids: Vec<Vec<i32>> = fs::read_to_string(&args[2])?
        .split_terminator('\n')
        .map(|line| line.split_whitespace().map(str::parse).collect())
        .collect::<Result<_, _>>()?;
    if texts.is_empty() || texts.len() != ids.len() {
        return Err("nonempty, matching text and ID datasets required".into());
    }
    let repeats: usize = args[4].parse()?;
    let warmup: usize = args[5].parse()?;
    let output = Path::new(&args[3]);
    fs::create_dir_all(output)?;
    let start = Instant::now();
    let model = DeepSpam::load(&args[0])?;
    println!(
        "{{\"runtime\":\"rust\",\"stage\":\"load\",\"seconds\":{:.9},\"warmup_cases\":{warmup}}}",
        start.elapsed().as_secs_f64()
    );
    let mut workspace = Workspace::default();
    measure("nn", texts.len(), repeats, warmup, output, |i| {
        model.network.score_tokens(&ids[i], &mut workspace)
    })?;
    measure("full", texts.len(), repeats, warmup, output, |i| {
        Ok(model.predict(texts[i], &mut workspace)?.percent)
    })?;
    Ok(())
}
