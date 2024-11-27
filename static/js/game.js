let songData = {};
let gameMode = "{{ mode }}";
let selectedSongId = null;  // Guardamos el id de la canción seleccionada
let attemptsLeft = 6;

// Obtener los datos de la canción
function fetchSongData() {
    fetch(`/api/song/${gameMode}`)
        .then(res => res.json())
        .then(data => {
            songData = data;
            if (data.thumbUrl) {
                document.getElementById("thumb").src = data.thumbUrl;
                document.getElementById("thumb").style.display = "block";
            }
        });
}

function playSnippet() {
    if (songData.snippetUrl) {
        const audio = new Audio(songData.snippetUrl);
        const snippetDurations = [1, 2, 3, 4, 5, 6];
        audio.currentTime = 0;
        audio.play();
        setTimeout(() => audio.pause(), snippetDurations[6 - attemptsLeft] * 1000);
    } else {
        alert("No se encontró un fragmento para esta canción.");
    }
}

// Autocompletar con canción + artista y seleccionar por id
function autocompleteGuess() {
    const query = document.getElementById("guess").value;
    if (query.length > 1) {
        fetch(`/autocomplete?q=${query}`)
            .then(res => res.json())
            .then(songs => {
                const autocompleteContainer = document.getElementById("autocomplete-container");
                autocompleteContainer.innerHTML = "";  // Limpiar resultados anteriores
                songs.forEach(song => {
                    const suggestionDiv = document.createElement("div");
                    suggestionDiv.textContent = `${song.name} - ${song.artist}`;  // Mostrar nombre y artista
                    suggestionDiv.onclick = () => {
                        document.getElementById("guess").value = `${song.name} - ${song.artist}`;
                        selectedSongId = song.id;  // Guardamos el id de la canción seleccionada
                        autocompleteContainer.innerHTML = "";  // Limpiar después de seleccionar
                    };
                    autocompleteContainer.appendChild(suggestionDiv);
                });

                // Posicionar el contenedor debajo del input
                const input = document.getElementById("guess");
                const rect = input.getBoundingClientRect();
                autocompleteContainer.style.left = `${rect.left}px`;
                autocompleteContainer.style.top = `${rect.bottom + window.scrollY}px`;
                autocompleteContainer.style.width = `${rect.width}px`;
            });
    } else {
        document.getElementById("autocomplete-container").innerHTML = "";  // Limpiar si no hay query
    }
}

// Enviar el guess basado en el id
function submitGuess() {
    if (!selectedSongId) {
        alert("Selecciona una canción antes de enviar.");
        return;
    }

    fetch("/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            answerId: selectedSongId,  // Enviar el id en lugar del nombre
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
    });
}

fetchSongData();
