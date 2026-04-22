const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const studentName = localStorage.getItem('studentName');
const COLLISION_PADDING = 15;

if (!studentName) {
    alert('Vui lòng chọn học sinh từ trang chủ!');
    window.location.href = '/';
}

document.getElementById('student-name').textContent = studentName;

// ========== LOAD ẢNH ==========
const playerImg = new Image();
playerImg.src = '/static/images/player.png';
playerImg.onerror = () => console.warn('Không tải được ảnh player.png');

const obstacleImg = new Image();
obstacleImg.src = '/static/images/obstacle.png';
obstacleImg.onerror = () => console.warn('Không tải được ảnh obstacle.png');

const bgImg = new Image();
bgImg.src = '/static/images/background.png';
bgImg.onerror = () => console.warn('Không tải được ảnh background.png');

// ========== GAME STATE ==========
let gameRunning = false;
let animationFrameId = null;
let currentLevel = 1;
let paused = false;

let invulnerable = false;
let invulnerableTimer = 0;
const INVULN_DURATION = 40;

let player = {
    x: 100, y: 600,
    width: 100, height: 100,
    vx: 0, vy: 0,
    grounded: true,
    speed: 7
};

let obstacles = [];
let score = 0;
let frame = 0;
let questionActive = false;
let currentQuestion = null;
let currentQuestionId = null;
let pendingObstacle = null;
let nextSpawnDelay = 0;

const GRAVITY = 0.8;
const JUMP_FORCE = -15;
const GROUND_Y = 600;

const keys = {
    ArrowLeft: false,
    ArrowRight: false,
    Space: false
};

const obstacleTypes = [
    { name: 'normal', width: 80, height: 60, yOffset: 0 },
    { name: 'tall',   width: 60, height: 120, yOffset: -20 },
    { name: 'wide',   width: 120, height: 50, yOffset: 10 },
    { name: 'small',  width: 50, height: 50, yOffset: 10 },
    { name: 'big',    width: 100, height: 80, yOffset: -10 }
];

let highScore = 0;

async function loadProgress() {
    try {
        const res = await fetch(`/api/progress?name=${encodeURIComponent(studentName)}`);
        const data = await res.json();
        if (data) {
            currentLevel = data.level || 1;
            document.getElementById('level').textContent = currentLevel;
            document.getElementById('xp').textContent = data.xp || 0;
            highScore = data.high_score || 0;
            document.getElementById('high-score').textContent = highScore;
        }
    } catch (e) {
        console.error('Lỗi load progress:', e);
    }
}
loadProgress();

const displayScore = () => Math.floor(score / 10);

/**
 * Lưu tiến độ (XP, câu hỏi đã làm) và tùy chọn cập nhật kỷ lục.
 * @param {number} xpGain - XP nhận được
 * @param {number|null} questionId - ID câu hỏi vừa trả lời đúng (nếu có)
 * @param {boolean} updateHighScore - Có gửi score để xét kỷ lục hay không
 */
async function saveScoreAndProgress(xpGain = 0, questionId = null, updateHighScore = false) {
    const payload = {
        name: studentName,
        xp_gain: xpGain
    };
    if (questionId !== null) {
        payload.question_id = questionId;
    }
    // Chỉ gửi score khi cần cập nhật kỷ lục (kết thúc game)
    if (updateHighScore) {
        payload.score = displayScore();
    }

    const res = await fetch('/api/progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data) {
        currentLevel = data.level;
        highScore = data.high_score;
        document.getElementById('level').textContent = currentLevel;
        document.getElementById('xp').textContent = data.xp;
        document.getElementById('high-score').textContent = highScore;
    }
    return data;
}

function getSpawnDelayRange() {
    const displayScore = Math.floor(score / 10);
    let minDelay = 70;
    let maxDelay = 130;
    minDelay = Math.max(50, minDelay - (currentLevel - 1) * 4);
    maxDelay = Math.max(70, maxDelay - (currentLevel - 1) * 4);
    const scoreReduction = Math.floor(displayScore / 150) * 8;
    minDelay = Math.max(45, minDelay - scoreReduction);
    maxDelay = Math.max(60, maxDelay - scoreReduction);
    return [minDelay, maxDelay];
}

function getObstacleSpeed() {
    return 7 + Math.floor(currentLevel / 2);
}

function spawnRandomObstacle() {
    const type = obstacleTypes[Math.floor(Math.random() * obstacleTypes.length)];
    obstacles.push({
        x: canvas.width,
        width: type.width,
        height: type.height,
        y: GROUND_Y + player.height - type.height + type.yOffset,
        type: type.name
    });
}

// ========== INPUT ==========
window.addEventListener('keydown', (e) => {
    if (e.code === 'Space') {
        e.preventDefault();
        if (gameRunning) paused = !paused;
        return;
    }
    if (!gameRunning || questionActive || paused) return;
    if (e.code === 'ArrowUp') {
        e.preventDefault();
        if (player.grounded) {
            player.vy = JUMP_FORCE;
            player.grounded = false;
        }
    }
    if (e.code === 'ArrowLeft') { e.preventDefault(); keys.ArrowLeft = true; }
    if (e.code === 'ArrowRight') { e.preventDefault(); keys.ArrowRight = true; }
});

window.addEventListener('keyup', (e) => {
    if (e.code === 'ArrowLeft') { e.preventDefault(); keys.ArrowLeft = false; }
    if (e.code === 'ArrowRight') { e.preventDefault(); keys.ArrowRight = false; }
    if (e.code === 'Space') e.preventDefault();
});

// ========== GAME LOOP ==========
function update() {
    if (!gameRunning) return;
    if (paused) {
        draw();
        animationFrameId = requestAnimationFrame(update);
        return;
    }

    if (invulnerable) {
        invulnerableTimer--;
        if (invulnerableTimer <= 0) invulnerable = false;
    }

    player.vx = 0;
    if (keys.ArrowLeft) player.vx = -player.speed;
    if (keys.ArrowRight) player.vx = player.speed;
    player.x += player.vx;
    player.x = Math.max(0, Math.min(canvas.width - player.width, player.x));

    player.vy += GRAVITY;
    player.y += player.vy;
    if (player.y >= GROUND_Y) {
        player.y = GROUND_Y;
        player.vy = 0;
        player.grounded = true;
    }

    if (!questionActive) {
        if (nextSpawnDelay <= 0) {
            spawnRandomObstacle();
            const [minDelay, maxDelay] = getSpawnDelayRange();
            nextSpawnDelay = minDelay + Math.floor(Math.random() * (maxDelay - minDelay + 1));
        } else {
            nextSpawnDelay--;
        }
    }

    const obsSpeed = getObstacleSpeed();
    for (let obs of obstacles) obs.x -= obsSpeed;
    obstacles = obstacles.filter(obs => obs.x + obs.width > 0);

    if (!questionActive && !invulnerable) {
        for (let obs of obstacles) {
            const playerHitbox = {
                x: player.x + COLLISION_PADDING,
                y: player.y + COLLISION_PADDING,
                w: player.width - COLLISION_PADDING * 2,
                h: player.height - COLLISION_PADDING * 2
            };
            const obsHitbox = {
                x: obs.x + COLLISION_PADDING,
                y: obs.y + COLLISION_PADDING,
                w: obs.width - COLLISION_PADDING * 2,
                h: obs.height - COLLISION_PADDING * 2
            };
            if (playerHitbox.x < obsHitbox.x + obsHitbox.w &&
                playerHitbox.x + playerHitbox.w > obsHitbox.x &&
                playerHitbox.y < obsHitbox.y + obsHitbox.h &&
                playerHitbox.y + playerHitbox.h > obsHitbox.y) {
                gameRunning = false;
                pendingObstacle = obs;
                showQuestion();
                break;
            }
        }
    }

    score++;
    draw();
    frame++;
    animationFrameId = requestAnimationFrame(update);
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (bgImg.complete && bgImg.naturalHeight > 0) {
        ctx.drawImage(bgImg, 0, 0, canvas.width, canvas.height);
    } else {
        ctx.fillStyle = '#87CEEB';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    if (playerImg.complete && playerImg.naturalHeight > 0) {
        ctx.drawImage(playerImg, player.x, player.y, player.width, player.height);
    } else {
        ctx.fillStyle = '#3366FF';
        ctx.fillRect(player.x, player.y, player.width, player.height);
    }
    obstacles.forEach(obs => {
        if (obstacleImg.complete && obstacleImg.naturalHeight > 0) {
            ctx.drawImage(obstacleImg, obs.x, obs.y, obs.width, obs.height);
        } else {
            if (obs.type === 'tall') ctx.fillStyle = '#8B0000';
            else if (obs.type === 'wide') ctx.fillStyle = '#FF8C00';
            else if (obs.type === 'small') ctx.fillStyle = '#2E8B57';
            else if (obs.type === 'big') ctx.fillStyle = '#800080';
            else ctx.fillStyle = '#FF3333';
            ctx.fillRect(obs.x, obs.y, obs.width, obs.height);
        }
    });
    ctx.fillStyle = '#000';
    ctx.font = 'bold 24px Arial';
    ctx.fillText('Score: ' + displayScore(), canvas.width - 200, 50);
    ctx.fillText('Cấp: ' + currentLevel, 30, 50);
    if (paused) {
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'white';
        ctx.font = 'bold 48px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('TẠM DỪNG', canvas.width/2, canvas.height/2);
        ctx.textAlign = 'left';
    }
}

// ========== QUESTION ==========
async function showQuestion() {
    questionActive = true;
    try {
        const res = await fetch(`/api/question?name=${encodeURIComponent(studentName)}`);
        currentQuestion = await res.json();

        if (currentQuestion.completed_all) {
            const playAgain = confirm(
                '🎉 Chúc mừng! Bạn đã trả lời đúng tất cả câu hỏi!\n\n' +
                'Bạn có muốn chơi lại từ đầu không?'
            );
            if (playAgain) {
                // Reset tiến độ
                await fetch('/api/reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name: studentName })
                });
                // Load lại câu hỏi mới
                const newRes = await fetch(`/api/question?name=${encodeURIComponent(studentName)}`);
                currentQuestion = await newRes.json();
                // Cập nhật giao diện level, xp (về 1 và 0)
                await loadProgress();
                // Reset trạng thái game (điểm vẫn giữ, có thể set score = 0 nếu muốn)
                // Ở đây không reset score để người chơi tiếp tục với điểm hiện tại (tùy ý)
            } else {
                window.location.href = '/';
                return;
            }
        }

        currentQuestionId = currentQuestion.id;
        document.getElementById('question-word').textContent = `"${currentQuestion.word}"`;
        const container = document.getElementById('options-container');
        container.innerHTML = '';
        currentQuestion.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.textContent = opt;
            btn.classList.add('option-btn');
            btn.onclick = () => answerQuestion(opt);
            container.appendChild(btn);
        });
        document.getElementById('question-modal').classList.remove('hidden');
    } catch (e) {
        console.error('Lỗi lấy câu hỏi:', e);
        questionActive = false;
        gameRunning = true;
        update();
    }
}

async function answerQuestion(selected) {
    const correct = (selected === currentQuestion.correct);
    if (correct) {
        if (pendingObstacle) {
            const index = obstacles.indexOf(pendingObstacle);
            if (index > -1) obstacles.splice(index, 1);
            pendingObstacle = null;
        }
        // Đúng: +20 XP, đánh dấu câu hỏi, KHÔNG cập nhật kỷ lục
        await saveScoreAndProgress(20, currentQuestionId, false);
        invulnerable = true;
        invulnerableTimer = INVULN_DURATION;
        document.getElementById('question-modal').classList.add('hidden');
        questionActive = false;
        gameRunning = true;
        update();
    } else {
        // Sai: đóng modal và hiển thị câu hỏi mới (không thay đổi)
        document.getElementById('question-modal').classList.add('hidden');
        showQuestion();
    }
}

async function endGame() {
    if (gameRunning || questionActive) {
        gameRunning = false;
        questionActive = false;
        paused = false;
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        document.getElementById('question-modal').classList.add('hidden');

        const finalScore = displayScore();
        const oldHighScore = highScore;
        // Kết thúc game: gửi score để cập nhật kỷ lục
        await saveScoreAndProgress(0, null, true);
        const isNewRecord = finalScore > oldHighScore;
        alert(`🏁 Game kết thúc!\nĐiểm của bạn: ${finalScore}\nKỷ lục: ${highScore}${isNewRecord ? ' (Kỷ lục mới!)' : ''}`);
    }
}

// ========== START GAME ==========
document.getElementById('start-btn').addEventListener('click', () => {
    if (!gameRunning) {
        gameRunning = true;
        obstacles = [];
        score = 0;
        frame = 0;
        player.x = 100;
        player.y = GROUND_Y;
        player.vy = 0;
        player.vx = 0;
        player.grounded = true;
        questionActive = false;
        pendingObstacle = null;
        paused = false;
        invulnerable = false;
        const [minDelay, maxDelay] = getSpawnDelayRange();
        nextSpawnDelay = minDelay + Math.floor(Math.random() * (maxDelay - minDelay + 1));
        keys.ArrowLeft = false;
        keys.ArrowRight = false;
        loadProgress().then(() => {
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            update();
        });
    }
});

document.getElementById('end-btn').addEventListener('click', endGame);

// ========== NÚT CHƠI TỪ ĐẦU (RESET CẤP & XP) ==========
async function restartGame() {
    if (gameRunning) {
        gameRunning = false;
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
    }
    document.getElementById('question-modal').classList.add('hidden');
    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: studentName })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            currentLevel = 1;
            // Không gán highScore = 0 nữa, lấy từ data trả về
            highScore = data.high_score;
            document.getElementById('level').textContent = '1';
            document.getElementById('xp').textContent = '0';
            document.getElementById('high-score').textContent = highScore;
        }
    } catch (e) {
        console.error('Lỗi reset:', e);
    }
    obstacles = [];
    score = 0;
    frame = 0;
    player.x = 100;
    player.y = GROUND_Y;
    player.vy = 0;
    player.vx = 0;
    player.grounded = true;
    questionActive = false;
    pendingObstacle = null;
    paused = false;
    invulnerable = false;
    keys.ArrowLeft = false;
    keys.ArrowRight = false;
    const [minDelay, maxDelay] = getSpawnDelayRange();
    nextSpawnDelay = minDelay + Math.floor(Math.random() * (maxDelay - minDelay + 1));
    gameRunning = true;
    update();
}

document.getElementById('restart-btn').addEventListener('click', restartGame);

const pauseBtn = document.getElementById('pause-btn');
if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
        if (gameRunning && !questionActive) paused = !paused;
    });
}

// Tự động resize canvas theo màn hình laptop
function resizeCanvas() {
    const canvas = document.getElementById('gameCanvas');
    const container = document.querySelector('.game-container');
    
    let maxW = Math.min(window.innerWidth - 40, 1280); // bớt viền 20px mỗi bên
    let scale = maxW / 1280;
    let newH = Math.floor(720 * scale);
    
    canvas.style.width = maxW + 'px';
    canvas.style.height = newH + 'px';
}

window.addEventListener('resize', resizeCanvas);
window.addEventListener('load', resizeCanvas);

console.log('Runner HD+ sẵn sàng (kỷ lục chỉ cập nhật khi kết thúc)');