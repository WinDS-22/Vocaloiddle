let songData = {};
let gameMode = document.getElementById("gameMode").value;  // Obtener el valor del modo desde el HTML
let attemptsLeft = 6;

// Obtener los datos de la canción usando el modo de juego
function fetchSongData() {
    fetch(`/api/song/${gameMode}`)
        .then(res => {
            if (!res.ok) {
                throw new Error("Error en la respuesta del servidor: " + res.status);
            }
            return res.json();
        })
        .then(data => {
            songData = data;
            if (data.thumbUrl) {
                document.getElementById("thumb").src = data.thumbUrl;
                document.getElementById("thumb").style.display = "block";
            }
        })
        .catch(error => {
            console.error('Error al obtener los datos de la canción:', error);
            alert("No se pudo cargar la canción. Inténtalo de nuevo más tarde.");
        });
}


// Reproducir fragmento usando el primer enlace de "links"
function playSnippet() {
    if (songData.snippetUrl) {
        const audio = new Audio(songData.snippetUrl);  // Usamos el snippetUrl proporcionado por el servidor
        const snippetDurations = [1, 2, 3, 4, 5, 6];  // Duraciones de fragmentos crecientes según los intentos restantes
        audio.currentTime = 0;
        audio.play().catch(error => console.error("Error al reproducir el fragmento:", error));
        setTimeout(() => audio.pause(), snippetDurations[6 - attemptsLeft] * 1000);  // Ajustamos la duración según los intentos
    } else {
        alert("No se encontró un fragmento para esta canción.");
    }
}

function submitGuess() {
    const guess = document.getElementById("guess").value;

    fetch("/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            answer: guess,
            mode: gameMode,
            ...songData
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.correct) {
            alert("¡Correcto!");
        } else {
            attemptsLeft--;
            if (attemptsLeft > 0) {
                alert(`Incorrecto, te quedan ${attemptsLeft} intentos.`);
            } else {
                alert("No te quedan más intentos.");
            }
        }
    })
    .catch(error => console.error('Error al enviar la respuesta:', error));
}

fetchSongData();  // Llamamos para obtener los datos de la canción al cargar la página
