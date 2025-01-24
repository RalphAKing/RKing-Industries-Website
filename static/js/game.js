let gameState = JSON.parse(localStorage.getItem('gameState'));
let currentScore = '';

function initializeGame() {
    updateGameHeader();
    renderPlayers();
    setupNumberPad();
}

function updateGameHeader() {
    document.getElementById('game-type').textContent = gameState.gamePoints;
    document.getElementById('current-leg').textContent = gameState.currentLeg;
    document.getElementById('total-legs').textContent = gameState.legs;
}

function renderPlayers() {
    const container = document.getElementById('players-scores');
    container.innerHTML = '<div class="players-carousel"></div>';
    const carousel = container.querySelector('.players-carousel');
    
    const prevIndex = (gameState.currentPlayerIndex - 1 + gameState.players.length) % gameState.players.length;
    const nextIndex = (gameState.currentPlayerIndex + 1) % gameState.players.length;
    
    [prevIndex, gameState.currentPlayerIndex, nextIndex].forEach((playerIndex) => {
        const player = gameState.players[playerIndex];
        const playerCard = document.createElement('div');
        playerCard.className = `player-card ${playerIndex === gameState.currentPlayerIndex ? 'active-player' : ''}`;
        
        const finishes = calculateFinishes(player.score);
        const finishDisplay = finishes.length > 0 ? finishes[0] : 'No finish';
        
        playerCard.innerHTML = `
            <div class="player-header">
                <h2 class="player-name">${player.name}</h2>
                <div class="player-score">${player.score}</div>
            </div>
            <div class="player-stats">
                <div class="stat-row">
                    <span class="stat-label">Legs Won:</span>
                    <span class="stat-value">${player.legsWon || 0}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Average:</span>
                    <span class="stat-value">${calculateAverage(player.throws)}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Finish:</span>
                    <span class="stat-value">${finishDisplay}</span>
                </div>
            </div>
        `;
        
        carousel.appendChild(playerCard);
    });
}


function calculateFinishes(score) {
    if (score > 170 || score < 2) return [];

    const singles = Array.from({length: 20}, (_, i) => i + 1);
    const doubles = singles.map(x => x * 2).reverse(); 
    const triples = singles.map(x => x * 3).reverse(); 
    
    let finishes = [];
    
    const bull = 25;
    const dBull = 50;

    for (let double of doubles) {
        if (double <= score) {
            let remaining = score - double;

            if (remaining === 0) {
                finishes.push(`D${double / 2}`); 
                return finishes; 
            }

            for (let first of [...triples, ...singles, bull]) {
                remaining = score - first - double;

                if (doubles.includes(remaining) || remaining === dBull) {
                    const firstStr = first > 25 ? `T${Math.floor(first/3)}` : first === 25 ? 'Bull' : first.toString();
                    const remainingStr = remaining === 50 ? 'Bull' : `D${remaining/2}`;
                    
                    finishes.push(`${firstStr} D${double / 2} ${remainingStr}`);
                    if (finishes.length >= 3) return finishes; 
                }
            }
        }
    }

    for (let first of [...triples, ...singles, bull]) {
        for (let second of [...singles, ...doubles, ...triples, bull]) {
            let remaining = score - first - second;

            if (doubles.includes(remaining) || remaining === dBull) {
                const firstStr = first > 25 ? `T${Math.floor(first/3)}` : first === 25 ? 'Bull' : first.toString();
                const secondStr = second > 25 ? `T${Math.floor(second/3)}` : second === 25 ? 'Bull' : second.toString();
                const remainingStr = remaining === 50 ? 'Bull' : `D${remaining/2}`;
                
                finishes.push(`${firstStr} ${secondStr} ${remainingStr}`);
                if (finishes.length >= 3) return finishes; 
            }
        }
    }
    
    return finishes;
}






function scrollCarousel(direction) {
    const carousel = document.querySelector('.players-carousel');
    const cardWidth = carousel.querySelector('.player-card').offsetWidth;
    carousel.scrollBy({ left: cardWidth * direction, behavior: 'smooth' });
}

function scrollToActivePlayer() {
    const carousel = document.querySelector('.players-carousel');
    const activeCard = carousel.children[gameState.currentPlayerIndex];
    carousel.scrollTo({
        left: activeCard.offsetLeft - (carousel.offsetWidth - activeCard.offsetWidth) / 2,
        behavior: 'smooth'
    });
}


function setupNumberPad() {
    document.querySelectorAll('#number-pad button').forEach(button => {
        button.addEventListener('click', () => {
            if (button.classList.contains('clear')) {
                currentScore = '';
            } else if (button.classList.contains('submit')) {
                submitScore();
            } else {
                currentScore += button.textContent;
            }
            updateScoreDisplay();
        });
    });
}

function calculateAverage(throws) {
    if (throws.length === 0) return 0;
    return (throws.reduce((a, b) => a + b, 0) / throws.length).toFixed(1);
}

function submitScore() {
    const score = parseInt(currentScore);
    if (isValidScore(score)) {
        const currentPlayer = gameState.players[gameState.currentPlayerIndex];
        currentPlayer.throws.push(score);
        currentPlayer.score -= score;
        
        if (currentPlayer.score === 0) {
            handleLegWin();
        } else {
            nextPlayer();
        }
        
        currentScore = '';
        saveAndUpdateGame();
    }
}

function isValidScore(score) {
    return score >= 0 && 
           score <= 180 && 
           score <= gameState.players[gameState.currentPlayerIndex].score;
}

function nextPlayer() {
    gameState.currentPlayerIndex = 
        (gameState.currentPlayerIndex + 1) % gameState.players.length;
}

function handleLegWin() {
    const currentPlayer = gameState.players[gameState.currentPlayerIndex];
    
    currentPlayer.legsWon = (currentPlayer.legsWon || 0) + 1;

    if (gameState.currentLeg < gameState.legs) {
        gameState.currentLeg++;
        resetScores();
    } else {
        const legsWon = gameState.players.map(player => player.legsWon || 0);
        const maxLegsWon = Math.max(...legsWon);
        const winners = legsWon.filter(legs => legs === maxLegsWon);

        if (winners.length > 1) {
            alert(`Game Over! It's a draw! Both players won ${maxLegsWon} legs.`);
        } else {
            const winner = gameState.players[gameState.currentPlayerIndex];
            alert(`Game Over! ${winner.name} wins!`);
        }
        window.location.href = '/dartsgame';
    }
}


function resetScores() {
    gameState.players.forEach(player => {
        player.score = parseInt(gameState.gamePoints);
    });
    nextPlayer();
}

function endGame() {
    const winner = gameState.players[gameState.currentPlayerIndex];
    alert(`Game Over! ${winner.name} wins!`);
    window.location.href = '/dartsgame';
}

function saveAndUpdateGame() {
    localStorage.setItem('gameState', JSON.stringify(gameState));
    renderPlayers();
    updateGameHeader();
}

function updateScoreDisplay() {
    const display = document.querySelector('.typed-score-box');
    display.textContent = currentScore || '0';
}

function renderGameInterface() {
    const container = document.querySelector('.game-container');
    container.innerHTML = `
        <div class="typed-score-box">0</div> <!-- Added Typed Score Box -->
        <div class="players-carousel"></div>
        <div class="input-section">
            <div id="number-pad">
                <div class="num-row">
                    <button>7</button>
                    <button>8</button>
                    <button>9</button>
                </div>
                <div class="num-row">
                    <button>4</button>
                    <button>5</button>
                    <button>6</button>
                </div>
                <div class="num-row">
                    <button>1</button>
                    <button>2</button>
                    <button>3</button>
                </div>
                <div class="num-row">
                    <button>0</button>
                    <button class="clear">C</button>
                    <button class="submit">✓</button>
                </div>
            </div>
        </div>
    `;
    
    renderPlayers();
    setupNumberPad();
}


document.addEventListener('DOMContentLoaded', () => {
    renderGameInterface();
    updateGameHeader();
});
