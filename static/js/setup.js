let playerCount = 1;

function addPlayer() {
    playerCount++;
    const container = document.getElementById('players-container');
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'player-name';
    input.placeholder = `Player ${playerCount}`;
    container.insertBefore(input, container.lastElementChild);
}

function startGame() {
    const gamePoints = document.getElementById('score').value;
    const legs = document.getElementById('legs').value;
    const players = Array.from(document.getElementsByClassName('player-name'))
        .map(input => ({
            name: input.value,
            score: gamePoints,
            average: 0,
            throws: [],
            legsWon: 0
        }));

    localStorage.setItem('gameState', JSON.stringify({
        gamePoints,
        legs,
        currentLeg: 1,
        players,
        currentPlayerIndex: 0
    }));

    window.location.href = '/game';
}
