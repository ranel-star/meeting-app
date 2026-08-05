import os
import sqlite3

from flask import Flask, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "meeting_app.sqlite3")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")


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
    <p class="small">A simple learning project with three screens.</p>
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
  </style>
</head>
<body>
  <div class="card">
    <h1>Welcome, {{ username }}!</h1>
    <p>We are happy to have you here.</p>
    <a class="button" href="{{ url_for('preferences') }}">Continue to preferences</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
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
    select { width: 100%; padding: 12px; border: 1px solid #ccd3dd; border-radius: 10px; box-sizing: border-box; }
    button, .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; border: none; padding: 12px 18px; border-radius: 10px; text-decoration: none; cursor: pointer; }
    .summary { background: #ecfeff; padding: 14px; border-radius: 10px; margin-top: 18px; }
    .small { color: #667085; font-size: 14px; }
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

      <button type="submit">Save preferences</button>
    </form>

    {% if saved %}
      <div class="summary">
        <strong>Saved!</strong>
        <p>Username: {{ username }}</p>
        <p>Gender: {{ user_gender }}</p>
        <p>Preference: {{ gender_preference }}</p>
      </div>
    {% endif %}

    <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
  </div>
</body>
</html>
"""


def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
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
            SELECT users.*, preferences.gender_preference
            FROM users
            LEFT JOIN preferences ON preferences.user_id = users.id
            WHERE users.id = ?
            """,
            (session["user_id"],),
        ).fetchone()


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

    return render_template_string(GREETING_TEMPLATE, username=user["display_name"])


@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    gender_options = ["Woman", "Man", "Non-binary", "Prefer not to say"]
    preference_options = ["Women", "Men", "Everyone", "Prefer not to say"]

    current_gender = user["gender"] or gender_options[0]
    current_preference = user["gender_preference"] or preference_options[2]
    saved = False

    if request.method == "POST":
        current_gender = request.form.get("user_gender", gender_options[0])
        current_preference = request.form.get("gender_preference", preference_options[2])

        with get_db_connection() as connection:
            connection.execute(
                "UPDATE users SET gender = ?, updated_at = datetime('now') WHERE id = ?",
                (current_gender, user["id"]),
            )
            connection.execute(
                """
                INSERT INTO preferences (user_id, gender_preference)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    gender_preference = excluded.gender_preference,
                    updated_at = datetime('now')
                """,
                (user["id"], current_preference),
            )
            connection.commit()
        saved = True

    return render_template_string(
        PREFERENCES_TEMPLATE,
        username=user["display_name"],
        user_gender=current_gender,
        gender_preference=current_preference,
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
