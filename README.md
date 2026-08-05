# Meeting App

Simple beginner-friendly Flask app with a short onboarding flow:

1. Login
2. Greeting
3. Profile photo upload
4. User preferences, including preferred gender and age range
5. Full profile view

## Run it locally

1. Install Python 3.
2. Open a terminal in this folder.
3. Run:

```bash
pip install -r requirements.txt
flask --app app run
```

or:

```bash
python app.py
```

The first time you run it, the SQLite database will be created automatically in:

`db/meeting_app.sqlite3`

## PythonAnywhere

1. Upload the project files.
2. Install the packages from `requirements.txt`.
3. Set the WSGI entry point to `wsgi.py`.
4. Make sure the app object is exposed as `application`.

The file `wsgi.py` already does that for you.
