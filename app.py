import os
import sqlite3
from uuid import uuid4

from flask import Flask, redirect, render_template_string, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "meeting_app.sqlite3")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "uploads")
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Login</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; }
    .card { max-width: 420px; margin: 60px auto; background: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; color: #2c3e50; }
    label { display: block; margin: 14px 0 6px; font-weight: bold; }
    input, select { width: 100%; padding: 12px; border: 1px solid #ccd3dd; border-radius: 10px; box-sizing: border-box; }
    button, .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; border: none; padding: 12px 18px; border-radius: 10px; text-decoration: none; cursor: pointer; }
    .error { background: #fee2e2; color: #991b1b; padding: 12px; border-radius: 10px; margin-bottom: 14px; }
    .small { color: #667085; font-size: 14px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Meeting App</h1>
    <p class="small">A simple learning project with a short onboarding flow.</p>
    <p class="small">If this is your first time, we will create your account.</p>
    <h2>Login</h2>
    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}
    <form method="post">
      <label for="username">Username</label>
      <input id="username" name="username" type="text" placeholder="Enter your username" required>

      <label for="password">Password</label>
      <input id="password" name="password" type="password" placeholder="Enter your password" required>

      <button type="submit">Sign in</button>
    </form>
  </div>
</body>
</html>
"""


GREETING_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Greeting</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; }
    .card { max-width: 520px; margin: 60px auto; background: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; color: #2c3e50; }
    .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; }
    .secondary { background: #e5e7eb; color: #111827; }
    .avatar { width: 100%; max-width: 260px; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 24px; display: block; margin-top: 18px; border: 1px solid #dbe4ff; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Welcome, {{ username }}!</h1>
    <p>We are happy to have you here.</p>
    {% if photo_url %}
      <img class="avatar" src="{{ photo_url }}" alt="Your profile photo">
    {% endif %}
    <a class="button" href="{{ url_for('profile') }}">View full profile</a>
    <a class="button" href="{{ url_for('photo') }}">Add profile photo</a>
    <a class="button secondary" href="{{ url_for('preferences') }}">Continue to preferences</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
  </div>
</body>
</html>
"""


PHOTO_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Profile Photo</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; }
    .card { max-width: 520px; margin: 60px auto; background: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; color: #2c3e50; }
    .small { color: #667085; font-size: 14px; }
    .button, .upload-label { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; border: none; padding: 12px 18px; border-radius: 10px; text-decoration: none; cursor: pointer; font-size: 16px; }
    .secondary { background: #e5e7eb; color: #111827; }
    .photo-preview { margin-top: 20px; border-radius: 18px; overflow: hidden; background: #eef2ff; border: 1px solid #dbe4ff; }
    .photo-preview img { display: block; width: 100%; max-width: 100%; height: auto; }
    .upload-wrap { display: grid; gap: 12px; margin-top: 18px; }
    .upload-input { position: absolute; left: -9999px; }
    .error { background: #fee2e2; color: #991b1b; padding: 12px; border-radius: 10px; margin-top: 14px; }
    .summary { background: #ecfeff; padding: 14px; border-radius: 10px; margin-top: 18px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Add a profile photo</h1>
    <p class="small">Upload a photo from your phone or desktop so other people can recognize you.</p>

    {% if photo_url %}
      <div class="photo-preview">
        <img src="{{ photo_url }}" alt="Your profile photo">
      </div>
    {% endif %}

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
      <div class="upload-wrap">
        <input id="profile_photo" class="upload-input" name="profile_photo" type="file" accept="image/*" capture="environment" required>
        <label class="upload-label" for="profile_photo">Choose photo from phone or computer</label>
        <button type="submit">Upload photo</button>
      </div>
    </form>

    {% if saved %}
      <div class="summary">
        <strong>Photo uploaded!</strong>
        <p>Your picture is now saved in the app.</p>
      </div>
    {% endif %}

    <a class="button" href="{{ url_for('profile') }}">View full profile</a>
    <a class="button secondary" href="{{ url_for('preferences') }}">Continue to preferences</a>
    <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
  </div>
</body>
</html>
"""


PROFILE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Profile</title>
  <style>
    body { font-family: Arial, sans-serif; background: linear-gradient(180deg, #eef2ff 0%, #f5f7fb 100%); margin: 0; }
    .card { max-width: 640px; margin: 48px auto; background: white; padding: 28px; border-radius: 20px; box-shadow: 0 18px 40px rgba(15,23,42,0.12); }
    h1 { margin-top: 0; color: #1f2937; }
    .small { color: #667085; font-size: 14px; }
    .profile-grid { display: grid; grid-template-columns: 220px 1fr; gap: 24px; align-items: start; margin-top: 22px; }
    .avatar { width: 220px; height: 220px; object-fit: cover; border-radius: 24px; background: #eef2ff; border: 1px solid #dbe4ff; }
    .avatar-placeholder { width: 220px; height: 220px; border-radius: 24px; background: linear-gradient(135deg, #eef2ff, #f8fafc); border: 1px dashed #c7d2fe; display: grid; place-items: center; color: #6366f1; font-weight: bold; text-align: center; padding: 18px; box-sizing: border-box; }
    .details { display: grid; gap: 12px; }
    .detail { padding: 14px 16px; border-radius: 14px; background: #f8fafc; border: 1px solid #e5e7eb; }
    .label { display: block; color: #6b7280; font-size: 13px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
    .value { display: block; color: #111827; font-size: 16px; font-weight: 600; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
    .button { display: inline-block; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; }
    .secondary { background: #e5e7eb; color: #111827; }
    @media (max-width: 640px) {
      .card { margin: 18px; }
      .profile-grid { grid-template-columns: 1fr; }
      .avatar, .avatar-placeholder { width: 100%; height: auto; aspect-ratio: 1 / 1; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Your Profile</h1>
    <p class="small">Here is everything you have shared so far.</p>

    <div class="profile-grid">
      {% if photo_url %}
        <img class="avatar" src="{{ photo_url }}" alt="Your profile photo">
      {% else %}
        <div class="avatar-placeholder">No profile photo yet</div>
      {% endif %}

      <div class="details">
        <div class="detail">
          <span class="label">Username</span>
          <span class="value">{{ username }}</span>
        </div>
        <div class="detail">
          <span class="label">Your gender</span>
          <span class="value">{{ user_gender }}</span>
        </div>
        <div class="detail">
          <span class="label">Gender preference</span>
          <span class="value">{{ gender_preference }}</span>
        </div>
        <div class="detail">
          <span class="label">Preferred age range</span>
          <span class="value">{{ min_age }} - {{ max_age }}</span>
        </div>
      </div>
    </div>

    <div class="actions">
      <a class="button" href="{{ url_for('photo') }}">Update photo</a>
      <a class="button secondary" href="{{ url_for('preferences') }}">Edit preferences</a>
      <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
      <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
    </div>
  </div>
</body>
</html>
"""


PREFERENCES_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Preferences</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; }
    .card { max-width: 520px; margin: 60px auto; background: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; color: #2c3e50; }
    label { display: block; margin: 14px 0 6px; font-weight: bold; }
    select, input[type="range"] { width: 100%; }
    select { padding: 12px; border: 1px solid #ccd3dd; border-radius: 10px; box-sizing: border-box; }
    input[type="range"] { margin-top: 10px; }
    button, .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; border: none; padding: 12px 18px; border-radius: 10px; text-decoration: none; cursor: pointer; }
    .summary { background: #ecfeff; padding: 14px; border-radius: 10px; margin-top: 18px; }
    .small { color: #667085; font-size: 14px; }
    .range-row { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }
    .value-pill { background: #eef2ff; color: #3730a3; padding: 6px 10px; border-radius: 999px; font-size: 14px; font-weight: bold; min-width: 64px; text-align: center; }
    .secondary { background: #e5e7eb; color: #111827; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Preferences</h1>
    <p class="small">Tell us a little about yourself.</p>

    <form method="post">
      <label for="user_gender">Your gender</label>
      <select id="user_gender" name="user_gender">
        {% for option in gender_options %}
          <option value="{{ option }}" {% if option == user_gender %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>

      <label for="gender_preference">Gender preference</label>
      <select id="gender_preference" name="gender_preference">
        {% for option in preference_options %}
          <option value="{{ option }}" {% if option == gender_preference %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>

      <label for="min_age">Minimum age</label>
      <div class="range-row">
        <input id="min_age" name="min_age" type="range" min="18" max="99" step="1" value="{{ min_age }}" oninput="syncAgeRange()">
        <span id="min_age_value" class="value-pill">{{ min_age }}</span>
      </div>

      <label for="max_age">Maximum age</label>
      <div class="range-row">
        <input id="max_age" name="max_age" type="range" min="18" max="99" step="1" value="{{ max_age }}" oninput="syncAgeRange()">
        <span id="max_age_value" class="value-pill">{{ max_age }}</span>
      </div>

      <button type="submit">Save preferences</button>
    </form>

    {% if saved %}
      <div class="summary">
        <strong>Saved!</strong>
        <p>Username: {{ username }}</p>
        <p>Gender: {{ user_gender }}</p>
        <p>Preference: {{ gender_preference }}</p>
        <p>Age range: {{ min_age }} - {{ max_age }}</p>
      </div>
    {% endif %}

    <a class="button" href="{{ url_for('profile') }}">View full profile</a>
    <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
  </div>
  <script>
    function syncAgeRange() {
      const minAgeInput = document.getElementById("min_age");
      const maxAgeInput = document.getElementById("max_age");
      let minAge = parseInt(minAgeInput.value, 10);
      let maxAge = parseInt(maxAgeInput.value, 10);

      if (minAge > maxAge) {
        if (document.activeElement === minAgeInput) {
          maxAge = minAge;
          maxAgeInput.value = String(maxAge);
        } else {
          minAge = maxAge;
          minAgeInput.value = String(minAge);
        }
      }

      document.getElementById("min_age_value").textContent = String(minAgeInput.value);
      document.getElementById("max_age_value").textContent = String(maxAgeInput.value);
    }

    syncAgeRange();
  </script>
</body>
</html>
"""


def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def allowed_photo_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def save_profile_photo(user_id: int, uploaded_file) -> str:
    original_name = secure_filename(uploaded_file.filename or "photo")
    extension = original_name.rsplit(".", 1)[1].lower() if "." in original_name else "jpg"
    filename = f"user-{user_id}-{uuid4().hex}.{extension}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    uploaded_file.save(os.path.join(UPLOAD_FOLDER, filename))

    with get_db_connection() as connection:
        connection.execute(
            "UPDATE photos SET is_primary = 0 WHERE user_id = ?",
            (user_id,),
        )
        connection.execute(
            """
            INSERT INTO photos (user_id, url, sort_order, is_primary)
            VALUES (?, ?, 0, 1)
            """,
            (user_id, filename),
        )
        connection.commit()

    return filename


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    new_database = not os.path.exists(DB_PATH)

    with get_db_connection() as connection:
        if new_database:
            with open(os.path.join(BASE_DIR, "db", "schema.sql"), "r", encoding="utf-8") as file:
                schema_sql = file.read()
            connection.executescript(schema_sql)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
                gender_preference TEXT NOT NULL,
                min_age INTEGER NOT NULL DEFAULT 18,
                max_age INTEGER NOT NULL DEFAULT 99,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        preferences_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(preferences)").fetchall()
        }
        if "min_age" not in preferences_columns:
            connection.execute(
                "ALTER TABLE preferences ADD COLUMN min_age INTEGER NOT NULL DEFAULT 18"
            )
        if "max_age" not in preferences_columns:
            connection.execute(
                "ALTER TABLE preferences ADD COLUMN max_age INTEGER NOT NULL DEFAULT 99"
            )
        connection.commit()


def login_user(username: str, password: str):
    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE display_name = ?",
            (username,),
        ).fetchone()

        if user is None:
            email = f"{username.lower().replace(' ', '_')}@meeting.local"
            password_hash = generate_password_hash(password)
            connection.execute(
                """
                INSERT INTO users (email, password_hash, display_name, birth_date, gender, bio, city)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (email, password_hash, username, "2000-01-01", None, None, None),
            )
            connection.commit()
            user = connection.execute(
                "SELECT * FROM users WHERE display_name = ?",
                (username,),
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            return user

    return None


def get_current_user():
    if "user_id" not in session:
        return None

    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT users.*, preferences.gender_preference, preferences.min_age, preferences.max_age,
                   (
                       SELECT p.url
                       FROM photos AS p
                       WHERE p.user_id = users.id
                       ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                       LIMIT 1
                   ) AS profile_photo_filename
            FROM users
            LEFT JOIN preferences ON preferences.user_id = users.id
            WHERE users.id = ?
            """,
            (session["user_id"],),
        ).fetchone()


def get_photo_url(photo_filename):
    return url_for("uploaded_photo", filename=photo_filename) if photo_filename else None


init_db()


@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please enter both a username and a password."
        else:
            user = login_user(username, password)
            if user is None:
                error = "That password does not match this username."
            else:
                session["user_id"] = user["id"]
                session["username"] = user["display_name"]
                return redirect(url_for("greeting"))

    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/greeting")
def greeting():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    photo_url = get_photo_url(user["profile_photo_filename"])
    return render_template_string(
        GREETING_TEMPLATE,
        username=user["display_name"],
        photo_url=photo_url,
    )


@app.route("/photo", methods=["GET", "POST"])
def photo():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    error = None
    saved = request.args.get("saved") == "1"
    current_photo = user["profile_photo_filename"]

    if request.method == "POST":
        uploaded_file = request.files.get("profile_photo")

        if uploaded_file is None or uploaded_file.filename == "":
            error = "Please choose a photo to upload."
        elif not allowed_photo_file(uploaded_file.filename):
            error = "Please upload a JPG, PNG, GIF, or WEBP image."
        else:
            save_profile_photo(user["id"], uploaded_file)
            return redirect(url_for("photo", saved="1"))

    photo_url = get_photo_url(current_photo)
    return render_template_string(
        PHOTO_TEMPLATE,
        photo_url=photo_url,
        error=error,
        saved=saved,
    )


@app.route("/uploads/<path:filename>")
def uploaded_photo(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/profile")
def profile():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    return render_template_string(
        PROFILE_TEMPLATE,
        username=user["display_name"],
        user_gender=user["gender"] or "Not set",
        gender_preference=user["gender_preference"] or "Not set",
        min_age=user["min_age"] or "Not set",
        max_age=user["max_age"] or "Not set",
        photo_url=get_photo_url(user["profile_photo_filename"]),
    )


@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    gender_options = ["Woman", "Man", "Non-binary", "Prefer not to say"]
    preference_options = ["Women", "Men", "Everyone", "Prefer not to say"]

    current_gender = user["gender"] or gender_options[0]
    current_preference = user["gender_preference"] or preference_options[2]
    current_min_age = user["min_age"] or 24
    current_max_age = user["max_age"] or 35
    saved = False

    if request.method == "POST":
        current_gender = request.form.get("user_gender", gender_options[0])
        current_preference = request.form.get("gender_preference", preference_options[2])
        current_min_age = request.form.get("min_age", current_min_age)
        current_max_age = request.form.get("max_age", current_max_age)

        try:
            current_min_age = int(current_min_age)
            current_max_age = int(current_max_age)
        except (TypeError, ValueError):
            current_min_age = 24
            current_max_age = 35

        current_min_age = max(18, min(current_min_age, 99))
        current_max_age = max(18, min(current_max_age, 99))
        if current_min_age > current_max_age:
            current_min_age, current_max_age = current_max_age, current_min_age

        with get_db_connection() as connection:
            connection.execute(
                "UPDATE users SET gender = ?, updated_at = datetime('now') WHERE id = ?",
                (current_gender, user["id"]),
            )
            connection.execute(
                """
                INSERT INTO preferences (user_id, gender_preference, min_age, max_age)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    gender_preference = excluded.gender_preference,
                    min_age = excluded.min_age,
                    max_age = excluded.max_age,
                    updated_at = datetime('now')
                """,
                (user["id"], current_preference, current_min_age, current_max_age),
            )
            connection.commit()
        saved = True

    return render_template_string(
        PREFERENCES_TEMPLATE,
        username=user["display_name"],
        user_gender=current_gender,
        gender_preference=current_preference,
        min_age=current_min_age,
        max_age=current_max_age,
        gender_options=gender_options,
        preference_options=preference_options,
        saved=saved,
    )


@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
