import os
import random
import sqlite3
from datetime import date
from uuid import uuid4

from flask import Flask, redirect, render_template_string, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "meeting_app.sqlite3")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "uploads")
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MATCH_MESSAGE_THRESHOLD = 80

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# =============================================================================
# Templates
# =============================================================================
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


# -----------------------------------------------------------------------------
# Onboarding Templates
# -----------------------------------------------------------------------------
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
    <a class="button" href="{{ url_for('preferences') }}">Continue to profile details</a>
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
    .photo-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); gap: 10px; margin-top: 18px; }
    .photo-tile { border-radius: 14px; overflow: hidden; border: 1px solid #dbe4ff; background: #eef2ff; aspect-ratio: 1 / 1; }
    .photo-tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .photo-tile.placeholder { display: grid; place-items: center; color: #6366f1; font-weight: 700; text-align: center; padding: 12px; box-sizing: border-box; }
    .upload-input { position: absolute; left: -9999px; }
    .error { background: #fee2e2; color: #991b1b; padding: 12px; border-radius: 10px; margin-top: 14px; }
    .summary { background: #ecfeff; padding: 14px; border-radius: 10px; margin-top: 18px; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Add profile photos</h1>
    <p class="small">You can upload one photo, several photos, or skip this step for now and continue to your full profile.</p>

    {% if photo_urls %}
      <div class="photo-grid">
        {% for url in photo_urls %}
          <div class="photo-tile">
            <img src="{{ url }}" alt="Your profile photo">
          </div>
        {% endfor %}
      </div>
    {% elif photo_url %}
      <div class="photo-preview">
        <img src="{{ photo_url }}" alt="Your profile photo">
      </div>
    {% endif %}

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
      <div class="upload-wrap">
        <input id="profile_photos" class="upload-input" name="profile_photos" type="file" accept="image/*" capture="environment" multiple>
        <label class="upload-label" for="profile_photos">Choose one or more photos</label>
        <button type="submit">Upload photos</button>
      </div>
    </form>

    {% if saved %}
      <div class="summary">
        <strong>Photo saved!</strong>
        <p>Your picture has been added to your profile.</p>
      </div>
    {% endif %}

    <div class="actions">
      <a class="button" href="{{ url_for('profile') }}">View full profile</a>
      <a class="button secondary" href="{{ url_for('profile') }}">Skip for now</a>
    </div>
    <a class="button secondary" href="{{ url_for('preferences') }}">Continue to preferences</a>
    <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
    <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
  </div>
</body>
</html>
"""


PHOTO_CONFIRM_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - More Photos</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; }
    .card { max-width: 640px; margin: 60px auto; background: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; color: #2c3e50; }
    .small { color: #667085; font-size: 14px; }
    .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; }
    .secondary { background: #e5e7eb; color: #111827; }
    .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(88px, 1fr)); gap: 10px; margin-top: 18px; }
    .tile { aspect-ratio: 1 / 1; border-radius: 14px; overflow: hidden; border: 1px solid #dbe4ff; background: #eef2ff; }
    .tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Do you want to add more photos?</h1>
    <p class="small">You uploaded {{ uploaded_count }} photo{{ "" if uploaded_count == 1 else "s" }}.</p>

    {% if photo_urls %}
      <div class="gallery">
        {% for url in photo_urls %}
          <div class="tile">
            <img src="{{ url }}" alt="Uploaded profile photo">
          </div>
        {% endfor %}
      </div>
    {% endif %}

    <div class="actions">
      <a class="button" href="{{ url_for('photo') }}">Yes, add more</a>
      <a class="button secondary" href="{{ url_for('profile') }}">No, show my profile</a>
    </div>
  </div>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# Profile Template
# -----------------------------------------------------------------------------
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
    .gallery { margin-top: 26px; }
    .gallery-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
    .gallery-item { border-radius: 16px; overflow: hidden; border: 1px solid #dbe4ff; background: #eef2ff; aspect-ratio: 1 / 1; }
    .gallery-item img { width: 100%; height: 100%; object-fit: cover; display: block; }
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
          <span class="label">Your city</span>
          <span class="value">{{ city }}</span>
        </div>
        <div class="detail">
          <span class="label">Your age</span>
          <span class="value">{{ user_age }}</span>
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
      <a class="button" href="{{ url_for('match') }}">Find a match</a>
      <a class="button" href="{{ url_for('photo') }}">Add more photos</a>
      <a class="button" href="{{ url_for('matches_page') }}">My matches</a>
      <a class="button secondary" href="{{ url_for('preferences') }}">Edit preferences</a>
      <a class="button secondary" href="{{ url_for('greeting') }}">Back to greeting</a>
      <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
    </div>

    <div class="gallery">
      <div class="gallery-head">
        <h2>Photo gallery</h2>
        <p class="small">{{ photos|length }} saved photo{{ "" if photos|length == 1 else "s" }}</p>
      </div>
      {% if photos %}
        <div class="gallery-grid">
          {% for photo in photos %}
            <div class="gallery-item">
              <img src="{{ photo.url }}" alt="Profile photo {{ loop.index }}">
            </div>
          {% endfor %}
        </div>
      {% else %}
        <p class="small">No photos yet. You can skip this step or add one later.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""


MATCHES_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Matches</title>
  <style>
    body { font-family: Arial, sans-serif; background: linear-gradient(180deg, #eef2ff 0%, #f5f7fb 100%); margin: 0; }
    .card { max-width: 1120px; margin: 40px auto; background: white; padding: 28px; border-radius: 22px; box-shadow: 0 18px 40px rgba(15,23,42,0.12); }
    h1 { margin-top: 0; color: #1f2937; }
    .small { color: #667085; font-size: 14px; }
    .layout { display: grid; grid-template-columns: 320px 1fr; gap: 18px; margin-top: 24px; }
    .sidebar, .conversation { border: 1px solid #e5e7eb; border-radius: 18px; background: #f8fafc; }
    .sidebar { padding: 16px; }
    .conversation { padding: 18px; min-height: 520px; }
    .match-link { display: block; text-decoration: none; color: inherit; padding: 12px; border-radius: 14px; border: 1px solid transparent; background: white; margin-bottom: 10px; transition: border-color 0.15s ease, transform 0.15s ease; }
    .match-link:hover { border-color: #c7d2fe; transform: translateY(-1px); }
    .match-link.active { border-color: #4f46e5; box-shadow: 0 8px 20px rgba(79,70,229,0.08); }
    .match-head { display: flex; gap: 12px; align-items: center; }
    .avatar { width: 52px; height: 52px; border-radius: 14px; object-fit: cover; background: #eef2ff; border: 1px solid #dbe4ff; flex: 0 0 auto; }
    .avatar-placeholder { width: 52px; height: 52px; border-radius: 14px; background: linear-gradient(135deg, #eef2ff, #f8fafc); border: 1px dashed #c7d2fe; display: grid; place-items: center; color: #6366f1; font-size: 11px; font-weight: 700; text-align: center; flex: 0 0 auto; }
    .match-name { font-weight: 700; color: #111827; }
    .match-meta { color: #6b7280; font-size: 13px; margin-top: 2px; }
    .match-snippet { color: #374151; font-size: 14px; margin-top: 8px; }
    .conversation-header { display: flex; gap: 14px; align-items: center; margin-bottom: 18px; }
    .conversation-title { margin: 0; }
    .conversation-tools { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }
    .button { display: inline-block; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; border: none; cursor: pointer; font-size: 15px; }
    .secondary { background: #e5e7eb; color: #111827; }
    .messages { display: grid; gap: 12px; margin-top: 18px; }
    .message { background: white; border: 1px solid #e5e7eb; border-radius: 16px; padding: 14px 16px; }
    .message.you { background: #eef2ff; border-color: #c7d2fe; }
    .message-meta { color: #6b7280; font-size: 13px; margin-bottom: 6px; }
    .message-body { color: #111827; white-space: pre-wrap; }
    .composer { margin-top: 22px; padding-top: 22px; border-top: 1px solid #e5e7eb; }
    .composer form { display: grid; gap: 12px; }
    textarea { width: 100%; min-height: 120px; padding: 12px; border: 1px solid #ccd3dd; border-radius: 12px; box-sizing: border-box; font: inherit; resize: vertical; }
    .notice { background: #ecfeff; color: #155e75; padding: 12px 14px; border-radius: 12px; margin-bottom: 16px; }
    .error { background: #fee2e2; color: #991b1b; padding: 12px 14px; border-radius: 12px; margin-bottom: 16px; }
    .empty { background: #fff7ed; color: #9a3412; padding: 14px; border-radius: 14px; border: 1px solid #fed7aa; }
    @media (max-width: 900px) {
      .card { margin: 18px; }
      .layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Matches & conversations</h1>
    <p class="small">Choose a match on the left to read the thread, send a message, and continue when you are ready.</p>

    <div class="layout">
      <aside class="sidebar">
        {% if matches %}
          {% for match in matches %}
            <a class="match-link {% if selected_match and match.id == selected_match.id %}active{% endif %}" href="{{ url_for('matches_page', match_id=match.id) }}">
              <div class="match-head">
                {% if match.partner_photo_url %}
                  <img class="avatar" src="{{ match.partner_photo_url }}" alt="{{ match.partner_name }} profile photo">
                {% else %}
                  <div class="avatar-placeholder">No photo</div>
                {% endif %}
                <div>
                  <div class="match-name">{{ match.partner_name }}</div>
                  <div class="match-meta">{{ match.message_count }} message{{ "" if match.message_count == 1 else "s" }}</div>
                </div>
              </div>
              {% if match.last_message_body %}
                <div class="match-snippet">
                  <strong>{{ match.last_sender_name }}:</strong>
                  {{ match.last_message_body }}
                </div>
              {% else %}
                <div class="match-snippet">No messages yet. Say hello first.</div>
              {% endif %}
            </a>
          {% endfor %}
        {% else %}
          <div class="empty">
            You do not have any matches yet.
            <div style="margin-top: 8px;">Once you match with someone, they will appear here with the full conversation.</div>
          </div>
        {% endif %}
      </aside>

      <main class="conversation">
        {% if selected_match %}
          <div class="conversation-header">
            {% if selected_match.partner_photo_url %}
              <img class="avatar" src="{{ selected_match.partner_photo_url }}" alt="{{ selected_match.partner_name }} profile photo">
            {% else %}
              <div class="avatar-placeholder">No photo</div>
            {% endif %}
            <div>
              <h2 class="conversation-title">{{ selected_match.partner_name }}</h2>
              <p class="small">Matched on {{ selected_match.matched_at }}</p>
            </div>
          </div>

          {% if message_error %}
            <div class="error">{{ message_error }}</div>
          {% endif %}
          {% if message_sent %}
            <div class="notice">Message sent successfully.</div>
          {% endif %}

          {% if selected_messages %}
            <div class="messages">
              {% for message in selected_messages %}
                <div class="message {% if message.sender_id == current_user_id %}you{% endif %}">
                  <div class="message-meta">{{ message.sender_name }} · {{ message.sent_at }}</div>
                  <div class="message-body">{{ message.body }}</div>
                </div>
              {% endfor %}
            </div>
          {% else %}
            <div class="empty">No messages in this conversation yet.</div>
          {% endif %}

          <div class="composer">
            <h3>Send a message</h3>
            <form method="post">
              <input type="hidden" name="match_id" value="{{ selected_match.id }}">
              <label for="message_body">Your message</label>
              <textarea id="message_body" name="message_body" placeholder="Write something friendly..." required>{{ message_body }}</textarea>
              <button class="button" type="submit">Send message</button>
            </form>
          </div>
        {% else %}
          <div class="empty">
            Select a match from the left to open the conversation.
          </div>
        {% endif %}

        <div class="conversation-tools">
          <a class="button" href="{{ url_for('profile') }}">Back to profile</a>
          <a class="button secondary" href="{{ url_for('match') }}">Find a new match</a>
          <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
        </div>
      </main>
    </div>
  </div>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# Matching / Conversation Templates
# -----------------------------------------------------------------------------
SUMMARY_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Summary</title>
  <style>
    body { font-family: Arial, sans-serif; background: linear-gradient(180deg, #eef2ff 0%, #f5f7fb 100%); margin: 0; }
    .card { max-width: 1100px; margin: 40px auto; background: white; padding: 28px; border-radius: 22px; box-shadow: 0 18px 40px rgba(15,23,42,0.12); }
    h1 { margin-top: 0; color: #1f2937; }
    .small { color: #667085; font-size: 14px; }
    .layout { display: grid; grid-template-columns: 320px 1fr; gap: 18px; margin-top: 24px; }
    .sidebar, .summary-panel { border: 1px solid #e5e7eb; border-radius: 18px; background: #f8fafc; }
    .sidebar { padding: 16px; }
    .summary-panel { padding: 18px; min-height: 480px; }
    .match-link { display: block; text-decoration: none; color: inherit; padding: 12px; border-radius: 14px; border: 1px solid transparent; background: white; margin-bottom: 10px; }
    .match-link:hover { border-color: #c7d2fe; }
    .match-link.active { border-color: #4f46e5; box-shadow: 0 8px 20px rgba(79,70,229,0.08); }
    .match-head { display: flex; gap: 12px; align-items: center; }
    .avatar { width: 52px; height: 52px; border-radius: 14px; object-fit: cover; background: #eef2ff; border: 1px solid #dbe4ff; flex: 0 0 auto; }
    .avatar-placeholder { width: 52px; height: 52px; border-radius: 14px; background: linear-gradient(135deg, #eef2ff, #f8fafc); border: 1px dashed #c7d2fe; display: grid; place-items: center; color: #6366f1; font-size: 11px; font-weight: 700; text-align: center; flex: 0 0 auto; }
    .match-name { font-weight: 700; color: #111827; }
    .match-meta { color: #6b7280; font-size: 13px; margin-top: 2px; }
    .match-snippet { color: #374151; font-size: 14px; margin-top: 8px; }
    .summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
    .summary-stat { background: white; border: 1px solid #e5e7eb; border-radius: 16px; padding: 14px 16px; }
    .stat-label { display: block; color: #6b7280; font-size: 13px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
    .stat-value { display: block; color: #111827; font-size: 16px; font-weight: 700; }
    .messages { display: grid; gap: 12px; margin-top: 18px; }
    .message { background: white; border: 1px solid #e5e7eb; border-radius: 16px; padding: 14px 16px; }
    .message-meta { color: #6b7280; font-size: 13px; margin-bottom: 6px; }
    .message-body { color: #111827; white-space: pre-wrap; }
    .conversation-tools { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
    .button { display: inline-block; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; border: none; cursor: pointer; font-size: 15px; }
    .secondary { background: #e5e7eb; color: #111827; }
    .empty { background: #fff7ed; color: #9a3412; padding: 14px; border-radius: 14px; border: 1px solid #fed7aa; }
    @media (max-width: 900px) {
      .card { margin: 18px; }
      .layout { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Conversation summary</h1>
    <p class="small">This is a read-only overview of your matches and the latest conversation snapshots.</p>

    <div class="layout">
      <aside class="sidebar">
        {% if matches %}
          {% for match in matches %}
            <a class="match-link {% if selected_match and match.id == selected_match.id %}active{% endif %}" href="{{ url_for('matches_page', match_id=match.id) }}">
              <div class="match-head">
                {% if match.partner_photo_url %}
                  <img class="avatar" src="{{ match.partner_photo_url }}" alt="{{ match.partner_name }} profile photo">
                {% else %}
                  <div class="avatar-placeholder">No photo</div>
                {% endif %}
                <div>
                  <div class="match-name">{{ match.partner_name }}</div>
                  <div class="match-meta">{{ match.message_count }} message{{ "" if match.message_count == 1 else "s" }}</div>
                </div>
              </div>
              {% if match.last_message_body %}
                <div class="match-snippet">
                  <strong>{{ match.last_sender_name }}:</strong>
                  {{ match.last_message_body }}
                </div>
              {% else %}
                <div class="match-snippet">No messages yet.</div>
              {% endif %}
            </a>
          {% endfor %}
        {% else %}
          <div class="empty">
            You have not chatted with any matches yet.
            <div style="margin-top: 8px;">Go to Matches to start a conversation, then come back here for the summary.</div>
          </div>
        {% endif %}
      </aside>

      <main class="summary-panel">
        {% if selected_match %}
          <h2>{{ selected_match.partner_name }}</h2>
          <p class="small">Matched on {{ selected_match.matched_at }}</p>

          <div class="summary-grid">
            <div class="summary-stat">
              <span class="stat-label">Messages</span>
              <span class="stat-value">{{ selected_match.message_count }}</span>
            </div>
            <div class="summary-stat">
              <span class="stat-label">Last sender</span>
              <span class="stat-value">{{ selected_match.last_sender_name or "No messages yet" }}</span>
            </div>
            <div class="summary-stat">
              <span class="stat-label">Status</span>
              <span class="stat-value">{{ "Active" if selected_match.is_active else "Inactive" }}</span>
            </div>
          </div>

          {% if selected_messages %}
            <div class="messages">
              {% for message in selected_messages %}
                <div class="message">
                  <div class="message-meta">{{ message.sender_name }} · {{ message.sent_at }}</div>
                  <div class="message-body">{{ message.body }}</div>
                </div>
              {% endfor %}
            </div>
          {% else %}
            <div class="empty" style="margin-top: 18px;">There are no messages in this conversation yet.</div>
          {% endif %}

          <div class="conversation-tools">
            {% if previous_match %}
              <a class="button secondary" href="{{ url_for('matches_page', match_id=previous_match.id) }}">Previous match</a>
            {% endif %}
            {% if next_match %}
              <a class="button secondary" href="{{ url_for('matches_page', match_id=next_match.id) }}">Next match</a>
            {% endif %}
            <a class="button" href="{{ url_for('match', candidate_id=selected_match.partner_id) }}">Open match</a>
            <a class="button secondary" href="{{ url_for('profile') }}">Back to profile</a>
            <a class="button secondary" href="{{ url_for('reset') }}">Start over</a>
          </div>
        {% else %}
          <div class="empty">
            Select a match from the left to see the summary.
          </div>
        {% endif %}
      </main>
    </div>
  </div>
</body>
</html>
"""


MATCH_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting App - Match</title>
  <style>
    body { font-family: Arial, sans-serif; background: linear-gradient(180deg, #eef2ff 0%, #f5f7fb 100%); margin: 0; }
    .card { max-width: 760px; margin: 48px auto; background: white; padding: 28px; border-radius: 20px; box-shadow: 0 18px 40px rgba(15,23,42,0.12); }
    h1 { margin-top: 0; color: #1f2937; }
    .small { color: #667085; font-size: 14px; }
    .score { display: inline-block; margin: 10px 0 18px; padding: 10px 14px; border-radius: 999px; font-weight: 700; }
    .strong-match { background: #dcfce7; color: #166534; }
    .good-candidate { background: #fef3c7; color: #92400e; }
    .no-strong-match { background: #fee2e2; color: #991b1b; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
    .panel { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px; }
    .avatar { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 18px; background: #eef2ff; border: 1px solid #dbe4ff; }
    .avatar-placeholder { width: 100%; aspect-ratio: 1 / 1; border-radius: 18px; background: linear-gradient(135deg, #eef2ff, #f8fafc); border: 1px dashed #c7d2fe; display: grid; place-items: center; color: #6366f1; font-weight: bold; text-align: center; padding: 18px; box-sizing: border-box; }
    .label { display: block; color: #6b7280; font-size: 13px; margin: 14px 0 4px; text-transform: uppercase; letter-spacing: 0.04em; }
    .value { display: block; color: #111827; font-size: 16px; font-weight: 600; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
    .button { display: inline-block; background: #4f46e5; color: white; padding: 12px 18px; border-radius: 10px; text-decoration: none; }
    .secondary { background: #e5e7eb; color: #111827; }
    .chat { margin-top: 22px; padding-top: 22px; border-top: 1px solid #e5e7eb; }
    .chat-form { display: grid; gap: 12px; margin-top: 14px; }
    .chat-form textarea { width: 100%; min-height: 110px; padding: 12px; border: 1px solid #ccd3dd; border-radius: 12px; box-sizing: border-box; font: inherit; resize: vertical; }
    .chat-form-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .message-list { display: grid; gap: 12px; margin-top: 18px; }
    .message-item { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 14px; padding: 14px 16px; }
    .message-meta { color: #6b7280; font-size: 13px; margin-bottom: 6px; }
    .message-body { color: #111827; white-space: pre-wrap; }
    .notice { background: #ecfeff; color: #155e75; padding: 12px 14px; border-radius: 12px; margin-top: 16px; }
    .error { background: #fee2e2; color: #991b1b; padding: 12px 14px; border-radius: 12px; margin-top: 16px; }
    .next-step { margin-top: 24px; padding: 18px; border: 1px solid #c7d2fe; border-radius: 16px; background: #eef2ff; }
    .next-step-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }
    @media (max-width: 720px) {
      .card { margin: 18px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Match result</h1>
    <p class="small">We compared your profile with the best available candidate.</p>

    {% if candidate %}
      <div class="score {{ match_class }}">
        Compatibility: {{ compatibility_score }}%
        - {{ match_label }}
      </div>

      <div class="grid">
        <div class="panel">
          <h2>Your profile</h2>
          {% if user_photo_url %}
            <img class="avatar" src="{{ user_photo_url }}" alt="Your profile photo">
          {% else %}
            <div class="avatar-placeholder">No profile photo</div>
          {% endif %}
          <span class="label">Username</span>
          <span class="value">{{ username }}</span>
          <span class="label">Gender</span>
          <span class="value">{{ user_gender }}</span>
          <span class="label">City</span>
          <span class="value">{{ city }}</span>
          <span class="label">Preference</span>
          <span class="value">{{ gender_preference }}</span>
          <span class="label">Age</span>
          <span class="value">{{ user_age }}</span>
          <span class="label">Preferred age range</span>
          <span class="value">{{ min_age }} - {{ max_age }}</span>
        </div>

        <div class="panel">
          <h2>Candidate</h2>
          {% if candidate_photo_url %}
            <img class="avatar" src="{{ candidate_photo_url }}" alt="Candidate profile photo">
          {% else %}
            <div class="avatar-placeholder">No profile photo</div>
          {% endif %}
          <span class="label">Username</span>
          <span class="value">{{ candidate_username }}</span>
          <span class="label">Gender</span>
          <span class="value">{{ candidate_gender }}</span>
          <span class="label">City</span>
          <span class="value">{{ candidate_city }}</span>
          <span class="label">Preference</span>
          <span class="value">{{ candidate_preference }}</span>
          <span class="label">Age</span>
          <span class="value">{{ candidate_age }}</span>
          <span class="label">Preferred age range</span>
          <span class="value">{{ candidate_min_age }} - {{ candidate_max_age }}</span>
        </div>
      </div>
    {% else %}
      <div class="score no-strong-match">No match candidates yet</div>
      <p class="small">We could not find another completed profile to compare with yet.</p>
    {% endif %}

    {% if candidate %}
      <div class="chat">
        <h2>Chat with {{ candidate_username }}</h2>
        <p class="small">Write a message below and keep the conversation in this match thread.</p>

        {% if message_error %}
          <div class="error">{{ message_error }}</div>
        {% endif %}

        {% if message_sent %}
          <div class="notice">Message sent successfully.</div>
        {% endif %}

        <form class="chat-form" method="post">
          <input type="hidden" name="candidate_id" value="{{ candidate_id }}">
          <label for="message_body">Your message</label>
          <textarea id="message_body" name="message_body" placeholder="Write something friendly..." required>{{ message_body }}</textarea>
          <div class="chat-form-actions">
            <button type="submit">Send message</button>
            <a class="button secondary" href="{{ url_for('matches_page') }}">My matches</a>
          </div>
        </form>

        {% if match_messages %}
          <div class="message-list">
            {% for message in match_messages %}
              <div class="message-item">
                <div class="message-meta">{{ message.sender_name }} · {{ message.sent_at }}</div>
                <div class="message-body">{{ message.body }}</div>
              </div>
            {% endfor %}
          </div>
        {% else %}
          <p class="small">No messages yet. Be the first one to say hello.</p>
        {% endif %}
      </div>
    {% endif %}

    <div class="actions">
      <a class="button" href="{{ url_for('profile') }}">Back to profile</a>
      <a class="button" href="{{ url_for('matches_page') }}">My matches</a>
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
    select, input[type="text"], input[type="range"] { width: 100%; }
    select, input[type="text"] { padding: 12px; border: 1px solid #ccd3dd; border-radius: 10px; box-sizing: border-box; }
    input[type="range"] { margin-top: 10px; }
    button, .button { display: inline-block; margin-top: 18px; background: #4f46e5; color: white; border: none; padding: 12px 18px; border-radius: 10px; text-decoration: none; cursor: pointer; }
    .summary { background: #ecfeff; padding: 14px; border-radius: 10px; margin-top: 18px; }
    .small { color: #667085; font-size: 14px; }
    .info-row { margin-top: 14px; }
    .info-box { padding: 12px; border: 1px solid #dbe4ff; border-radius: 10px; background: #f8fafc; }
    .info-label { display: block; color: #6b7280; font-size: 13px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
    .info-value { display: block; color: #111827; font-size: 16px; font-weight: 600; }
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
      <label for="city">Your city</label>
      <input id="city" name="city" type="text" placeholder="Enter your city" value="{{ city }}" required>

      <label for="current_age">Your age</label>
      <input id="current_age" name="current_age" type="number" min="18" max="99" step="1" placeholder="Enter your current age" value="{{ current_age }}">

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
        <p>City: {{ city }}</p>
        <p>Age: {{ current_age if current_age is not none else "Not set" }}</p>
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


# =============================================================================
# Helper Functions
# =============================================================================
def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def allowed_photo_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def calculate_age(birth_date_text: str) -> int | None:
    try:
        year, month, day = map(int, birth_date_text.split("-"))
        birth_date = date(year, month, day)
    except (ValueError, AttributeError):
        return None

    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def resolve_user_age(user) -> int | None:
    try:
        current_age = user["current_age"]
    except (KeyError, IndexError, TypeError):
        current_age = None

    if current_age is not None:
        return current_age

    return calculate_age(user["birth_date"])


def preference_allows_gender(preference: str | None, gender: str | None) -> bool:
    if not preference or preference in {"Everyone", "Prefer not to say"}:
        return True
    if not gender:
        return False

    matches = {
        "Women": {"Woman"},
        "Men": {"Man"},
        "Non-binary": {"Non-binary"},
    }
    return gender in matches.get(preference, {gender})


def has_uploaded_photo(user) -> bool:
    return bool(user["profile_photo_filename"])


def profile_is_complete(user) -> bool:
    return all(
        [
            user["gender"],
            user["city"],
            user["gender_preference"],
            user["min_age"] is not None,
            user["max_age"] is not None,
        ]
    )


def next_profile_step(user) -> str | None:
    if (
        not user["city"]
        or not user["gender"]
        or not user["gender_preference"]
        or user["min_age"] is None
        or user["max_age"] is None
    ):
        return "preferences"
    return None


def calculate_match_score(user_a, user_b) -> int:
    score = 0
    user_a_age = resolve_user_age(user_a)
    user_b_age = resolve_user_age(user_b)

    if preference_allows_gender(user_a["gender_preference"], user_b["gender"]):
        score += 25
    if preference_allows_gender(user_b["gender_preference"], user_a["gender"]):
        score += 25

    if user_b_age is not None and user_a["min_age"] <= user_b_age <= user_a["max_age"]:
        score += 25
    if user_a_age is not None and user_b["min_age"] <= user_a_age <= user_b["max_age"]:
        score += 25

    return score


def ordered_user_ids(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


def get_seen_match_candidate_ids() -> set[int]:
    return set(session.get("seen_match_candidate_ids", []))


def mark_match_candidate_seen(candidate_id: int):
    seen_ids = session.get("seen_match_candidate_ids", [])
    if candidate_id not in seen_ids:
        seen_ids.append(candidate_id)
        session["seen_match_candidate_ids"] = seen_ids


def fetch_scored_candidates(connection, current_user, excluded_ids: set[int] | None = None):
    excluded_ids = excluded_ids or set()

    candidate_rows = connection.execute(
        """
        SELECT users.*, preferences.gender_preference, preferences.current_age, preferences.min_age, preferences.max_age,
               (
                   SELECT p.url
                   FROM photos AS p
                   WHERE p.user_id = users.id
                   ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                   LIMIT 1
               ) AS profile_photo_filename
        FROM users
        JOIN preferences ON preferences.user_id = users.id
        WHERE users.id <> ?
          AND users.gender IS NOT NULL
          AND preferences.gender_preference IS NOT NULL
          AND preferences.min_age IS NOT NULL
          AND preferences.max_age IS NOT NULL
        """,
        (current_user["id"],),
    ).fetchall()

    scored_candidates = []
    for candidate in candidate_rows:
        if candidate["id"] in excluded_ids:
            continue
        if not has_uploaded_photo(candidate):
            continue
        scored_candidates.append((calculate_match_score(current_user, candidate), candidate))

    scored_candidates.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
    return scored_candidates


def fetch_match_candidate(connection, current_user_id: int, candidate_id: int):
    return connection.execute(
        """
        SELECT users.*, preferences.gender_preference, preferences.current_age, preferences.min_age, preferences.max_age,
               (
                   SELECT p.url
                   FROM photos AS p
                   WHERE p.user_id = users.id
                   ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                   LIMIT 1
               ) AS profile_photo_filename
        FROM users
        JOIN preferences ON preferences.user_id = users.id
        WHERE users.id = ?
          AND users.id <> ?
          AND users.gender IS NOT NULL
          AND preferences.gender_preference IS NOT NULL
          AND preferences.min_age IS NOT NULL
          AND preferences.max_age IS NOT NULL
        """,
        (candidate_id, current_user_id),
    ).fetchone()


def fetch_best_match_candidate(connection, current_user, excluded_ids: set[int] | None = None):
    scored_candidates = fetch_scored_candidates(connection, current_user, excluded_ids=excluded_ids)

    if not scored_candidates:
        return None, None

    best_score = max(score for score, _ in scored_candidates)
    top_candidates = [candidate for score, candidate in scored_candidates if score == best_score]
    return random.choice(top_candidates), best_score


def get_or_create_match(connection, user_a_id: int, user_b_id: int):
    user1_id, user2_id = ordered_user_ids(user_a_id, user_b_id)
    connection.execute(
        """
        INSERT OR IGNORE INTO matches (user1_id, user2_id)
        VALUES (?, ?)
        """,
        (user1_id, user2_id),
    )
    return connection.execute(
        """
        SELECT *
        FROM matches
        WHERE user1_id = ? AND user2_id = ?
        """,
        (user1_id, user2_id),
    ).fetchone()


def fetch_match_messages(connection, match_id: int):
    return connection.execute(
        """
        SELECT messages.id, messages.sender_id, messages.body, messages.sent_at, users.display_name AS sender_name
        FROM messages
        JOIN users ON users.id = messages.sender_id
        WHERE messages.match_id = ?
        ORDER BY messages.sent_at ASC, messages.id ASC
        """,
        (match_id,),
    ).fetchall()


def fetch_user_photos(connection, user_id: int):
    rows = connection.execute(
        """
        SELECT id, user_id, url, sort_order, is_primary, created_at
        FROM photos
        WHERE user_id = ?
        ORDER BY is_primary DESC, created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return rows


def fetch_user_matches(connection, user_id: int):
    rows = connection.execute(
        """
        SELECT
            matches.id,
            matches.user1_id,
            matches.user2_id,
            matches.matched_at,
            matches.is_active,
            u1.display_name AS user1_name,
            u1.gender AS user1_gender,
            u1.city AS user1_city,
            (
                SELECT p.url
                FROM photos AS p
                WHERE p.user_id = u1.id
                ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                LIMIT 1
            ) AS user1_photo_filename,
            u2.display_name AS user2_name,
            u2.gender AS user2_gender,
            u2.city AS user2_city,
            (
                SELECT p.url
                FROM photos AS p
                WHERE p.user_id = u2.id
                ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                LIMIT 1
            ) AS user2_photo_filename,
            (
                SELECT messages.body
                FROM messages
                WHERE messages.match_id = matches.id
                ORDER BY messages.sent_at DESC, messages.id DESC
                LIMIT 1
            ) AS last_message_body,
            (
                SELECT messages.sent_at
                FROM messages
                WHERE messages.match_id = matches.id
                ORDER BY messages.sent_at DESC, messages.id DESC
                LIMIT 1
            ) AS last_message_at,
            (
                SELECT users.display_name
                FROM messages
                JOIN users ON users.id = messages.sender_id
                WHERE messages.match_id = matches.id
                ORDER BY messages.sent_at DESC, messages.id DESC
                LIMIT 1
            ) AS last_sender_name,
            (
                SELECT COUNT(*)
                FROM messages
                WHERE messages.match_id = matches.id
            ) AS message_count
        FROM matches
        JOIN users AS u1 ON u1.id = matches.user1_id
        JOIN users AS u2 ON u2.id = matches.user2_id
        WHERE matches.user1_id = ? OR matches.user2_id = ?
        ORDER BY COALESCE(last_message_at, matches.matched_at) DESC, matches.id DESC
        """,
        (user_id, user_id),
    ).fetchall()
    return rows


def fetch_match_for_user(connection, user_id: int, match_id: int):
    return connection.execute(
        """
        SELECT
            matches.id,
            matches.user1_id,
            matches.user2_id,
            matches.matched_at,
            matches.is_active,
            u1.display_name AS user1_name,
            u1.gender AS user1_gender,
            u1.city AS user1_city,
            (
                SELECT p.url
                FROM photos AS p
                WHERE p.user_id = u1.id
                ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                LIMIT 1
            ) AS user1_photo_filename,
            u2.display_name AS user2_name,
            u2.gender AS user2_gender,
            u2.city AS user2_city,
            (
                SELECT p.url
                FROM photos AS p
                WHERE p.user_id = u2.id
                ORDER BY p.is_primary DESC, p.created_at DESC, p.id DESC
                LIMIT 1
            ) AS user2_photo_filename
        FROM matches
        JOIN users AS u1 ON u1.id = matches.user1_id
        JOIN users AS u2 ON u2.id = matches.user2_id
        WHERE matches.id = ? AND (matches.user1_id = ? OR matches.user2_id = ?)
        """,
        (match_id, user_id, user_id),
    ).fetchone()


def format_match_summary(match_row, user_id: int):
    if match_row is None:
        return None

    if match_row["user1_id"] == user_id:
        partner_id = match_row["user2_id"]
        partner_name = match_row["user2_name"]
        partner_gender = match_row["user2_gender"]
        partner_city = match_row["user2_city"]
        partner_photo_filename = match_row["user2_photo_filename"]
    else:
        partner_id = match_row["user1_id"]
        partner_name = match_row["user1_name"]
        partner_gender = match_row["user1_gender"]
        partner_city = match_row["user1_city"]
        partner_photo_filename = match_row["user1_photo_filename"]

    return {
        "id": match_row["id"],
        "partner_id": partner_id,
        "partner_name": partner_name,
        "partner_gender": partner_gender,
        "partner_city": partner_city,
        "partner_photo_url": get_photo_url(partner_photo_filename),
        "matched_at": match_row["matched_at"],
        "is_active": match_row["is_active"],
        "last_message_body": match_row["last_message_body"],
        "last_message_at": match_row["last_message_at"],
        "last_sender_name": match_row["last_sender_name"],
        "message_count": match_row["message_count"],
    }


def fetch_matches_page_state(connection, user_id: int, requested_match_id: int | None = None):
    matches = [format_match_summary(match_row, user_id) for match_row in fetch_user_matches(connection, user_id)]
    selected_match = None

    if requested_match_id is not None:
        selected_match = next((match for match in matches if match["id"] == requested_match_id), None)

    if selected_match is None and matches:
        selected_match = matches[0]

    selected_messages = fetch_match_messages(connection, selected_match["id"]) if selected_match else []
    previous_match = None
    next_match = None

    if selected_match and matches:
        selected_index = next((index for index, match in enumerate(matches) if match["id"] == selected_match["id"]), None)
        if selected_index is not None:
            if selected_index > 0:
                previous_match = matches[selected_index - 1]
            if selected_index < len(matches) - 1:
                next_match = matches[selected_index + 1]

    return matches, selected_match, selected_messages, previous_match, next_match


def save_profile_photos(user_id: int, uploaded_files) -> list[str]:
    saved_filenames: list[str] = []

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    with get_db_connection() as connection:
        existing_primary = connection.execute(
            "SELECT id FROM photos WHERE user_id = ? AND is_primary = 1 LIMIT 1",
            (user_id,),
        ).fetchone()

        make_first_new_primary = existing_primary is None

        for index, uploaded_file in enumerate(uploaded_files):
            original_name = secure_filename(uploaded_file.filename or "photo")
            extension = original_name.rsplit(".", 1)[1].lower() if "." in original_name else "jpg"
            filename = f"user-{user_id}-{uuid4().hex}.{extension}"
            uploaded_file.save(os.path.join(UPLOAD_FOLDER, filename))

            is_primary = 1 if make_first_new_primary and index == 0 else 0
            if is_primary:
                connection.execute(
                    "UPDATE photos SET is_primary = 0 WHERE user_id = ?",
                    (user_id,),
                )

            connection.execute(
                """
                INSERT INTO photos (user_id, url, sort_order, is_primary)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, filename, index, is_primary),
            )
            saved_filenames.append(filename)

        connection.commit()

    return saved_filenames


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
                current_age INTEGER,
                min_age INTEGER NOT NULL DEFAULT 18,
                max_age INTEGER NOT NULL DEFAULT 99,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                user2_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                matched_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                CHECK (user1_id < user2_id),
                UNIQUE (user1_id, user2_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
                sender_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT (datetime('now')),
                read_at TEXT
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
        if "current_age" not in preferences_columns:
            connection.execute(
                "ALTER TABLE preferences ADD COLUMN current_age INTEGER"
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
            SELECT users.*, preferences.gender_preference, preferences.current_age, preferences.min_age, preferences.max_age,
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


# =============================================================================
# App Initialization
# =============================================================================
init_db()


# =============================================================================
# Authentication and Onboarding Routes
# =============================================================================
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
    current_photos = []

    with get_db_connection() as connection:
        current_photos = fetch_user_photos(connection, user["id"])

    if request.method == "POST":
        uploaded_files = [
            uploaded_file
            for uploaded_file in request.files.getlist("profile_photos")
            if uploaded_file and uploaded_file.filename
        ]

        if not uploaded_files:
            return redirect(url_for("profile"))

        invalid_files = [file.filename for file in uploaded_files if not allowed_photo_file(file.filename)]
        if invalid_files:
            error = "Please upload only JPG, PNG, GIF, or WEBP images."
        else:
            saved_files = save_profile_photos(user["id"], uploaded_files)
            return redirect(url_for("photo_more", uploaded_count=len(saved_files)))

    photo_urls = [get_photo_url(photo["url"]) for photo in current_photos if photo["url"]]
    photo_url = photo_urls[0] if photo_urls else None
    return render_template_string(
        PHOTO_TEMPLATE,
        photo_url=photo_url,
        photo_urls=photo_urls,
        error=error,
        saved=False,
    )


@app.route("/photo/more")
def photo_more():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    uploaded_count = request.args.get("uploaded_count", type=int) or 0

    with get_db_connection() as connection:
        photos = fetch_user_photos(connection, user["id"])

    photo_urls = [get_photo_url(photo["url"]) for photo in photos if photo["url"]]
    return render_template_string(
        PHOTO_CONFIRM_TEMPLATE,
        uploaded_count=uploaded_count,
        photo_urls=photo_urls,
    )


@app.route("/uploads/<path:filename>")
def uploaded_photo(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/profile")
def profile():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    with get_db_connection() as connection:
        photos = fetch_user_photos(connection, user["id"])

    return render_template_string(
        PROFILE_TEMPLATE,
        username=user["display_name"],
        user_gender=user["gender"] or "Not set",
        city=user["city"] or "Not set",
        user_age=resolve_user_age(user) or "Not set",
        gender_preference=user["gender_preference"] or "Not set",
        min_age=user["min_age"] or "Not set",
        max_age=user["max_age"] or "Not set",
        photo_url=get_photo_url(user["profile_photo_filename"]),
        photos=[
            {
                "id": photo["id"],
                "url": get_photo_url(photo["url"]),
                "is_primary": photo["is_primary"],
            }
            for photo in photos
        ],
    )


# =============================================================================
# Match Engine and Conversation Data
# =============================================================================
@app.route("/match", methods=["GET", "POST"])
def match():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    if not profile_is_complete(user):
        return redirect(url_for("profile"))

    message_error = None
    message_body = ""
    message_sent = request.args.get("message_sent") == "1"
    requested_candidate_id = request.values.get("candidate_id", type=int)

    with get_db_connection() as connection:
        selected_candidate = None
        selected_score = None

        if requested_candidate_id is not None:
            selected_candidate = fetch_match_candidate(connection, user["id"], requested_candidate_id)
            if selected_candidate is not None:
                selected_score = calculate_match_score(user, selected_candidate)

        if selected_candidate is None:
            selected_candidate, selected_score = fetch_best_match_candidate(connection, user)

        if selected_candidate is None:
            return render_template_string(
                MATCH_TEMPLATE,
                candidate=None,
                match_ready=False,
                message_error=None,
                message_sent=message_sent,
                message_body="",
                match_messages=[],
            )

        match_ready = selected_score is not None and selected_score >= MATCH_MESSAGE_THRESHOLD
        active_match = None
        match_messages = []

        active_match = get_or_create_match(connection, user["id"], selected_candidate["id"])
        match_messages = fetch_match_messages(connection, active_match["id"])

        if request.method == "POST":
            message_body = request.form.get("message_body", "").strip()
            posted_candidate_id = request.form.get("candidate_id", type=int)

            if posted_candidate_id is None:
                message_error = "Please choose a match before sending a message."
            elif not message_body:
                message_error = "Please write a message before sending it."
            else:
                posted_candidate = fetch_match_candidate(connection, user["id"], posted_candidate_id)
                if posted_candidate is None:
                    message_error = "That match is no longer available."
                else:
                    match_row = get_or_create_match(connection, user["id"], posted_candidate["id"])
                    connection.execute(
                        """
                        INSERT INTO messages (match_id, sender_id, body)
                        VALUES (?, ?, ?)
                        """,
                        (match_row["id"], user["id"], message_body),
                    )
                    connection.commit()
                    return redirect(url_for("match", candidate_id=posted_candidate["id"], message_sent=1))

    if selected_score >= 80:
        match_label = "Strong match"
        match_class = "strong-match"
    elif selected_score >= 60:
        match_label = "Pretty good fit"
        match_class = "good-candidate"
    else:
        match_label = "No strong match yet"
        match_class = "no-strong-match"

    return render_template_string(
        MATCH_TEMPLATE,
        candidate=selected_candidate,
        match_label=match_label,
        match_class=match_class,
        compatibility_score=selected_score,
        username=user["display_name"],
        user_gender=user["gender"] or "Not set",
        city=user["city"] or "Not set",
        user_age=resolve_user_age(user) or "Not set",
        gender_preference=user["gender_preference"] or "Not set",
        min_age=user["min_age"] or "Not set",
        max_age=user["max_age"] or "Not set",
        user_photo_url=get_photo_url(user["profile_photo_filename"]),
        candidate_id=selected_candidate["id"],
        candidate_username=selected_candidate["display_name"],
        candidate_gender=selected_candidate["gender"] or "Not set",
        candidate_city=selected_candidate["city"] or "Not set",
        candidate_age=resolve_user_age(selected_candidate) or "Not set",
        candidate_preference=selected_candidate["gender_preference"] or "Not set",
        candidate_min_age=selected_candidate["min_age"] or "Not set",
        candidate_max_age=selected_candidate["max_age"] or "Not set",
        candidate_photo_url=get_photo_url(selected_candidate["profile_photo_filename"]),
        match_ready=match_ready,
        match_messages=match_messages,
        message_error=message_error,
        message_sent=message_sent,
        message_body=message_body,
    )


# =============================================================================
# Matches Page
# =============================================================================
def render_matches_page(user, requested_match_id: int | None = None):
    with get_db_connection() as connection:
        matches, selected_match, selected_messages, previous_match, next_match = fetch_matches_page_state(
            connection, user["id"], requested_match_id
        )

    return render_template_string(
        SUMMARY_TEMPLATE,
        matches=matches,
        selected_match=selected_match,
        selected_messages=selected_messages,
        previous_match=previous_match,
        next_match=next_match,
        current_user_id=user["id"],
    )


@app.route("/matches")
def matches_page():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    if not profile_is_complete(user):
        return redirect(url_for("profile"))

    requested_match_id = request.args.get("match_id", type=int)
    return render_matches_page(user, requested_match_id)


@app.route("/conclusion")
def conclusion():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    if not profile_is_complete(user):
        return redirect(url_for("profile"))

    requested_match_id = request.args.get("match_id", type=int)
    return render_matches_page(user, requested_match_id)


# =============================================================================
# Preferences Route
# =============================================================================
@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    gender_options = ["Woman", "Man", "Non-binary", "Prefer not to say"]
    preference_options = ["Women", "Men", "Everyone", "Prefer not to say"]

    current_city = user["city"] or ""
    current_age = user["current_age"] if user["current_age"] is not None else ""
    current_gender = user["gender"] or gender_options[0]
    current_preference = user["gender_preference"] or preference_options[2]
    current_min_age = user["min_age"] or 24
    current_max_age = user["max_age"] or 35
    saved = False

    if request.method == "POST":
        current_city = request.form.get("city", "").strip()
        current_age = request.form.get("current_age", current_age)
        current_gender = request.form.get("user_gender", gender_options[0])
        current_preference = request.form.get("gender_preference", preference_options[2])
        current_min_age = request.form.get("min_age", current_min_age)
        current_max_age = request.form.get("max_age", current_max_age)

        try:
            current_age = int(current_age) if current_age not in ("", None) else None
            current_min_age = int(current_min_age)
            current_max_age = int(current_max_age)
        except (TypeError, ValueError):
            current_age = user["current_age"]
            current_min_age = 24
            current_max_age = 35

        if current_age is not None:
            current_age = max(18, min(current_age, 99))
        current_min_age = max(18, min(current_min_age, 99))
        current_max_age = max(18, min(current_max_age, 99))
        if current_min_age > current_max_age:
            current_min_age, current_max_age = current_max_age, current_min_age

        with get_db_connection() as connection:
            connection.execute(
                "UPDATE users SET gender = ?, city = ?, updated_at = datetime('now') WHERE id = ?",
                (current_gender, current_city, user["id"]),
            )
            connection.execute(
                """
                INSERT INTO preferences (user_id, gender_preference, current_age, min_age, max_age)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    gender_preference = excluded.gender_preference,
                    current_age = excluded.current_age,
                    min_age = excluded.min_age,
                    max_age = excluded.max_age,
                    updated_at = datetime('now')
                """,
                (user["id"], current_preference, current_age, current_min_age, current_max_age),
            )
            connection.commit()
        return redirect(url_for("photo"))

    return render_template_string(
        PREFERENCES_TEMPLATE,
        username=user["display_name"],
        city=current_city,
        current_age=current_age,
        user_gender=current_gender,
        gender_preference=current_preference,
        min_age=current_min_age,
        max_age=current_max_age,
        gender_options=gender_options,
        preference_options=preference_options,
        saved=saved,
    )


# =============================================================================
# Session Reset
# =============================================================================
@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
