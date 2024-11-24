from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import os
import requests
from requests.auth import HTTPDigestAuth
import logging


app = Flask(__name__)

# Configuración de la sesión
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

logging.basicConfig(level=logging.INFO)

# Conexión a MongoDB
MONGO_URI = "mongodb+srv://windscraft22:QQIv872Rw6QfIMsq@cluster0.g6a8d.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["vocaloid_game"]
songs_collection = db["songs"]
daily_collection = db["daily_song"]
scores_collection = db["scores"]
users_collection = db["users"]

def add_ip_to_mongodb_atlas():
    # Credenciales de la API de MongoDB Atlas
    public_key = os.getenv("MONGODB_ATLAS_PUBLIC_KEY")
    print("Obtained Public Key")
    private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
    print("Obtained Private Key")
    project_id = os.getenv("MONGODB_ATLAS_PROJECT_ID")  # ID del proyecto en MongoDB Atlas
    print("Obtained ProjectID Key")

    # Obtén la IP pública del servidor
    try:
        response = requests.get("https://api64.ipify.org?format=json")
        response.raise_for_status()
        public_ip = response.json()["ip"]
        print(f"Detected public IP: {public_ip}")
    except Exception as e:
        print(f"Failed to fetch public IP: {e}")
        return

    # URL de la API de MongoDB Atlas
    atlas_api_url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/67428001a871207f7633112e/accessList"

    # Configuración de la IP a agregar
    payload = {
        "ipAddress": public_ip,
        "comment": "Added by Render deployment script"
    }

    # Agregar la IP usando la API
    try:
        response = requests.post(
            atlas_api_url,
            auth=HTTPDigestAuth(public_key, private_key),
            json=payload
        )
        response.raise_for_status()
        print("IP added successfully to MongoDB Atlas!")
    except Exception as e:
        print(f"Failed to add IP to MongoDB Atlas: {e}")

# Fetch all songs from MongoDB
def fetch_all_songs():
    return list(songs_collection.find({}, {"_id": 0, "Artist": 1, "defaultName": 1, "name": 1, "links": 1}))

# Select the daily song
def daily_mode():
    today = datetime.now().strftime("%Y-%m-%d")
    daily_song = daily_collection.find_one({"date": today})

    if daily_song:
        return daily_song["song"]

    all_songs = fetch_all_songs()
    song = random.choice(all_songs)
    daily_collection.insert_one({"date": today, "song": song})
    return song

# Update daily streak
def update_daily_streak(username, correct):
    today = datetime.now().strftime("%Y-%m-%d")
    user_score = scores_collection.find_one({"username": username})

    if not user_score:
        scores_collection.insert_one({
            "username": username,
            "daily_streak": 1 if correct else 0,
            "last_played_date": today,
            "max_unlimited_streak": 0,
            "current_unlimited_streak": 0
        })
    else:
        if user_score.get("last_played_date") == today:
            return
        new_streak = user_score.get("daily_streak", 0) + 1 if correct else 0
        scores_collection.update_one(
            {"username": username},
            {"$set": {"daily_streak": new_streak, "last_played_date": today}}
        )

# Update unlimited streak
def update_unlimited_streak(username, correct):
    user_score = scores_collection.find_one({"username": username})

    if not user_score:
        scores_collection.insert_one({
            "username": username,
            "daily_streak": 0,
            "last_played_date": "",
            "max_unlimited_streak": 1 if correct else 0,
            "current_unlimited_streak": 1 if correct else 0
        })
    else:
        current_streak = user_score.get("current_unlimited_streak", 0)
        max_streak = user_score.get("max_unlimited_streak", 0)
        current_streak = current_streak + 1 if correct else 0
        max_streak = max(max_streak, current_streak)
        scores_collection.update_one(
            {"username": username},
            {"$set": {
                "current_unlimited_streak": current_streak,
                "max_unlimited_streak": max_streak
            }}
        )

# Authenticate users
def authenticate_user(username, password):
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user["password"], password):
        return True
    return False

# Routes for Flask
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if users_collection.find_one({"username": username}):
            return "Usuario ya existe."
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({"username": username, "password": hashed_password})
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if authenticate_user(username, password):
            session["username"] = username
            return redirect("/")
        return "Usuario o contraseña incorrectos."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

@app.route("/")
def index():
    username = session.get("username")
    return render_template("index.html", username=username)

@app.route("/start/<mode>")
def start_game(mode):
    username = session.get("username")
    if not username:
        return redirect("/login")
    if mode == "daily":
        song = daily_mode()
    else:
        all_songs = fetch_all_songs()
        song = random.choice(all_songs)
    return jsonify({
        "title": song["defaultName"],
        "artist": song["Artist"],
        "name": song["name"],
        "links": song["links"]
    })

@app.route("/guess", methods=["POST"])
def guess():
    data = request.json
    username = session.get("username")
    if not username:
        return {"error": "Usuario no autenticado"}
    answer = data.get("answer", "").lower()
    mode = data.get("mode")
    correct = data.get("title", "").lower() in answer or any(
        artist.lower() in answer for artist in data.get("artist", "").split(", ")
    )
    if mode == "daily":
        update_daily_streak(username, correct)
    elif mode == "unlimited":
        update_unlimited_streak(username, correct)
    return jsonify({"correct": correct})

@app.route("/leaderboard")
def leaderboard():
    scores = list(scores_collection.find({}, {"_id": 0, "username": 1, "daily_streak": 1, "max_unlimited_streak": 1}))
    scores.sort(key=lambda x: x.get("max_unlimited_streak", 0), reverse=True)
    return render_template("leaderboard.html", scores=scores)

if __name__ == "__main__":
    add_ip_to_mongodb_atlas()
    port = int(os.environ.get("PORT", 5000))  # Render asigna el puerto automáticamente
    app.run(host="0.0.0.0", port=port)
