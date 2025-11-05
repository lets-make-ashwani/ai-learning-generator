import os
import json
from io import BytesIO
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import database
import gemini_service

# --- Load environment variables ---
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_please_change")

# --- Initialize database ---
database.init_db()

def get_current_user():
    if 'user_id' in session:
        return database.get_user_by_id(session['user_id'])
    return None

# --- Routes ---
@app.route("/")
def index():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("index.html", email=user["email"])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]
        user = database.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        return render_template("auth.html", is_login=True, error="Invalid email or password.")
    return render_template("auth.html", is_login=True)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]
        if database.get_user_by_email(email):
            return render_template("auth.html", is_login=False, error="Email already in use.")
        if len(password) < 6:
            return render_template("auth.html", is_login=False, error="Password must be at least 6 characters.")
        password_hash = generate_password_hash(password)
        user_id = database.create_user(email, password_hash)
        session["user_id"] = user_id
        return redirect(url_for("index"))
    return render_template("auth.html", is_login=False)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/history")
def history():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    generations = database.get_generations_by_user(user["id"])
    return render_template("history.html", gens=generations)

# --- API: Generate flashcards or MCQs ---
@app.route("/api/generate", methods=["POST"])
def api_generate():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated."}), 401

    req = request.get_json() or {}
    topic = (req.get("topic") or "").strip()
    mode = (req.get("mode") or "flashcard").strip()
    try:
        num_items = int(req.get("numItems", 5))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numItems"}), 400
    difficulty = (req.get("difficulty") or "Intermediate").strip()
    include_explanations = bool(req.get("explanations", False))

    if not topic:
        return jsonify({"error": "Topic is required."}), 400
    if num_items < 1 or num_items > 20:
        return jsonify({"error": "numItems must be between 1 and 20."}), 400

    generated = gemini_service.generate_content(
        topic=topic,
        num_items=num_items,
        mode=mode,
        difficulty=difficulty,
        include_explanations=include_explanations
    )
    if not generated:
        return jsonify({"error": "Failed to generate content from AI service."}), 500

    try:
        gen_id = database.save_generation(
            user_id=user["id"], topic=topic, mode=mode,
            content_json=json.dumps(generated)
        )
    except Exception as e:
        print("DB save error:", e)
        gen_id = None

    return jsonify({"generation_id": gen_id, "items": generated})

# --- API: Download (PDF or CSV only) ---
@app.route("/api/download", methods=["POST"])
def api_download():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated."}), 401

    data = request.get_json() or {}
    gen_id = data.get("generation_id")
    fmt = (data.get("format") or "pdf").lower()  # default to PDF

    gen = database.get_generation_by_id(gen_id)
    if not gen or gen["user_id"] != user["id"]:
        return jsonify({"error": "Generation not found."}), 404

    items = json.loads(gen["content_json"])
    topic = gen["topic"] or "export"

    # --- CSV export ---
    if fmt == "csv":
        import csv
        output = BytesIO()
        writer = csv.writer(output)
        if gen["mode"] == "mcq":
            writer.writerow(["Question", "Option 1", "Option 2", "Option 3", "Option 4", "Answer"])
            for it in items:
                opts = it.get("options", [])
                opts = (opts + [""] * 4)[:4]
                writer.writerow([it.get("question", "")] + opts + [it.get("correct_answer", "")])
        else:
            writer.writerow(["Question", "Answer"])
            for it in items:
                writer.writerow([it.get("question", ""), it.get("answer", "")])
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"{topic}.csv",
                         mimetype="text/csv")

    # --- PDF export ---
    if fmt == "pdf":
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
        except Exception:
            return jsonify({"error": "reportlab not installed (PDF not available)."}), 500

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=50
        )
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 11
        styles["Normal"].leading = 15  # Better line spacing
        styles["Title"].fontSize = 16
        styles["Title"].leading = 22

        story = []
        story.append(Paragraph(f"<b>Topic:</b> {topic}", styles["Title"]))
        story.append(Spacer(1, 12))

        for idx, it in enumerate(items, start=1):
            if gen["mode"] == "mcq":
                q = it.get("question", "")
                opts = it.get("options", [])
                ans = it.get("answer", "") or it.get("correct_answer", "")
                story.append(Paragraph(f"<b>{idx}. Q:</b> {q}", styles["Normal"]))
                for o in opts:
                    story.append(Paragraph(f"- {o}", styles["Normal"]))
                story.append(Paragraph(f"<b>Answer:</b> {ans}", styles["Normal"]))
                story.append(Spacer(1, 10))
            else:
                q = it.get("question", "") or it.get("front", "")
                a = it.get("answer", "") or it.get("back", "")
                story.append(Paragraph(f"<b>{idx}. Q:</b> {q}", styles["Normal"]))
                story.append(Paragraph(f"<b>A:</b> {a}", styles["Normal"]))
                story.append(Spacer(1, 10))

        doc.build(story)
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True,
            download_name=f"{topic}.pdf",
            mimetype="application/pdf"
        )

    return jsonify({"error": "Invalid format"}), 400

# --- API: Delete a generation ---
@app.route("/api/delete_generation", methods=["POST"])
def api_delete_generation():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    gen_id = data.get("generation_id")
    gen = database.get_generation_by_id(gen_id)
    if not gen or gen["user_id"] != user["id"]:
        return jsonify({"error": "Not found"}), 404
    database.delete_generation(gen_id)
    return jsonify({"ok": True})

# --- Run app ---
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
