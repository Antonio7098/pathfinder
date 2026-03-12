from flask import Flask, render_template, request, send_from_directory
import subprocess
import uuid
import os

app = Flask(__name__)

RUNS_DIR = "runs"
os.makedirs(RUNS_DIR, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_pipeline():
    repo = request.form["repo"]
    graph_mode = request.form.get("graph_mode", "service")
    pipeline_type = request.form.get("pipeline_type", "full")

    job_id = str(uuid.uuid4())
    output_dir = os.path.join(RUNS_DIR, job_id)

    if pipeline_type == "latency":

        cmd = [
            "python",
            "-m",
            "pathfinder.cli",
            "run-latency-optimized-pipeline",
            "--repo", repo,
            "--output-dir", output_dir,
            "--graph-mode", graph_mode,
            "--provider", "openrouter",
            "--model", "nvidia/nemotron-3-super-120b-a12b:free",
            "--timeout-seconds", "300",
            "--max-concurrent-security-tasks", "6"
        ]

    else:

        cmd = [
            "python",
            "-m",
            "pathfinder.cli",
            "run-full-pipeline",
            "--repo", repo,
            "--output-dir", output_dir,
            "--graph-mode", graph_mode,
            "--provider", "minimax",
            "--timeout-seconds", "600"
        ]

    subprocess.run(cmd, check=True)

    return render_template(
        "result.html",
        job_id=job_id,
        report_url=f"/results/{job_id}/dashboard.html"
    )


@app.route("/results/<job_id>/<path:filename>", methods=["GET"])
def serve_results(job_id, filename):
    return send_from_directory(
        os.path.join(RUNS_DIR, job_id),
        filename
    )


if __name__ == "__main__":
    app.run(debug=True)