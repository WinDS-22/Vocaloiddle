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
    private_key = os.getenv("MONGODB_ATLAS_PRIVATE_KEY")
    project_id = os.getenv("MONGODB_ATLAS_PROJECT_ID")  # ID del proyecto en MongoDB Atlas

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

    print(f"Payload being sent: {payload}")
    
    # Agregar la IP usando la API
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            atlas_api_url,
            auth=HTTPDigestAuth(public_key, private_key),
            json=[payload],
            headers=headers
        )
        response.raise_for_status()
        print("IP added successfully to MongoDB Atlas!")
    except Exception as e:
        print(f"Failed to add IP to MongoDB Atlas: {e}")
        print(f"Error response: {response.text}")

# Fetch all songs from MongoDB
def fetch_all_songs():
    # Asegúrate de incluir el campo "_id" en la proyección
    return list(songs_collection.find({}, {"_id": 1, "Artist": 1, "defaultName": 1, "name": 1, "links": 1, "snippetUrl": 1, "thumbUrl": 1}))

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

    # Renderiza la página del juego, pasando el modo como contexto
    return render_template("game.html", mode=mode)

@app.route("/guess", methods=["POST"])
def guess():
    data = request.json
    username = session.get("username")
    if not username:
        return {"error": "Usuario no autenticado"}

    song_id = data.get("answerId")
    mode = data.get("mode")

    # Verificar si la canción seleccionada es correcta
    if song_id == songData["_id"]:  # Verificamos por id
        correct = True
    else:
        correct = False

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

@app.route("/api/song/<mode>")
def get_song_data(mode):
    try:
        if mode == "daily":
            song = daily_mode()  # Obtener la canción diaria
        else:
            all_songs = fetch_all_songs()  # Obtener una canción aleatoria
            song = random.choice(all_songs)

        # Seleccionamos el primer enlace de la lista de links como el fragmento a reproducir
        snippet_url = song.get("links", [None])[0]  # Tomamos el primer link de la lista, si existe

        if not snippet_url:
            raise ValueError("No se encontró un enlace de reproducción para esta canción")

        return jsonify({
            "_id": str(song["_id"]),  # Convertimos el ObjectId a string
            "title": song["defaultName"],
            "artist": song["Artist"],
            "name": song["name"],
            "links": song["links"],  # Devolvemos los enlaces completos por si quieres usarlos en otro lugar
            "snippetUrl": snippet_url,  # Enviamos el primer enlace como fragmento
            "thumbUrl": song.get("thumbUrl", "")
        })
    except Exception as e:
        app.logger.error(f"Error al obtener los datos de la canción: {e}")
        return jsonify({"error": "No se pudo obtener la canción. Inténtalo de nuevo más tarde."}), 500

    return jsonify({
        "_id": str(song["_id"]),  # Convertimos el ObjectId a string
        "title": song["defaultName"],
        "artist": song["Artist"],
        "name": song["name"],
        "links": song["links"],  # Devolvemos los enlaces completos por si quieres usarlos en otro lugar
        "snippetUrl": snippet_url,  # Enviamos el primer enlace como fragmento
        "thumbUrl": song.get("thumbUrl", "")
    })

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    query = request.args.get("q", "").lower()
    if query:
        matching_songs = songs_collection.find(
            {"name": {"$regex": query, "$options": "i"}},
            {"_id": 1, "name": 1, "Artist": 1}
        )
        results = [{"id": str(song["_id"]), "name": song["name"], "artist": song["Artist"]} for song in matching_songs]
        return jsonify(results)
    return jsonify([])

if __name__ == "__main__":
    add_ip_to_mongodb_atlas()
    port = int(os.environ.get("PORT", 5000))  # Render asigna el puerto automáticamente
    app.run(host="0.0.0.0", port=port)
