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

    job_id = str(uuid.uuid4())
    output_dir = os.path.join(RUNS_DIR, job_id)

    os.makedirs(output_dir, exist_ok=True)

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

    try:
        subprocess.run(cmd, check=True)

        return render_template(
            "result.html",
            job_id=job_id,
            report_url=f"/results/{job_id}/dashboard.html"
        )

    except subprocess.CalledProcessError as e:
        return f"Pipeline failed: {e}"


@app.route("/results/<job_id>/<path:filename>")
def serve_results(job_id, filename):
    return send_from_directory(
        os.path.join(RUNS_DIR, job_id),
        filename
    )


if __name__ == "__main__":
    app.run(debug=True)