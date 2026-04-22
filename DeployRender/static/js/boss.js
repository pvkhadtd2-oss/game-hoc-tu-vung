const studentName = localStorage.getItem('studentName');
if (!studentName) window.location.href = '/';
document.getElementById('student-name').textContent = studentName;

// ========== CẤU HÌNH GAME ==========
const PLAYER_MAX_HP = 500;
let playerHP = PLAYER_MAX_HP;
let bossLevel = 1;
const BOSS_BASE_HP = 500;
let bossMaxHP = BOSS_BASE_HP;      // Sẽ tính lại khi qua màn
let bossHP = BOSS_BASE_HP;

let currentQuestion = null;
let currentQuestionId = null;

// ========== LOAD THÔNG TIN HỌC SINH ==========
async function loadProgress() {
    try {
        const res = await fetch(`/api/progress?name=${encodeURIComponent(studentName)}`);
        const data = await res.json();
        if (data) {
            document.getElementById('level').textContent = data.level || 1;
            document.getElementById('xp').textContent = data.xp || 0;
        }
    } catch (e) {
        console.error('Lỗi load progress:', e);
    }
}
loadProgress();

// ========== CẬP NHẬT GIAO DIỆN ==========
function updateUI() {
    // Cập nhật thanh máu người chơi
    document.getElementById('player-hp').textContent = playerHP;
    document.getElementById('player-hp-bar').style.width = (playerHP / PLAYER_MAX_HP * 100) + '%';

    // Cập nhật thanh máu Boss
    bossMaxHP = BOSS_BASE_HP + (bossLevel - 1) * 200;
    // Chỉ hiển thị HP hiện tại (không có /max)
    document.getElementById('boss-hp-text').textContent = bossHP;
    document.getElementById('boss-hp-bar').style.width = (bossHP / bossMaxHP * 100) + '%';

    // Hiển thị cấp Boss
    const bossLevelSpan = document.getElementById('boss-level');
    if (bossLevelSpan) bossLevelSpan.textContent = bossLevel;

    // Kiểm tra thua
    if (playerHP <= 0) {
        document.getElementById('message').textContent = '💀 Bạn đã thua! Nhấn F5 để chơi lại.';
        document.getElementById('attack-btn').disabled = true;
        return;
    }

    // Kiểm tra thắng Boss (chuyển màn)
    if (bossHP <= 0) {
        bossLevel++;
        bossHP = BOSS_BASE_HP + (bossLevel - 1) * 200;
        playerHP = PLAYER_MAX_HP;   // Hồi đầy máu khi qua màn

        document.getElementById('message').textContent = 
            `🎉 Bạn đã đánh bại Boss cấp ${bossLevel-1}! Lên cấp ${bossLevel}. Máu đã hồi đầy! +50 XP thưởng.`;

        // Thưởng XP khi qua màn
        fetch('/api/progress', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: studentName, xp_gain: 50 })
        }).then(() => loadProgress());

        // Cập nhật lại giao diện sau khi tăng cấp (gọi lại updateUI để tính lại bossMaxHP)
        // Lưu ý: bossHP đã được gán ở trên, bossMaxHP sẽ được tính lại trong lần gọi updateUI tiếp theo
        updateUI();
    }
}

// ========== TẤN CÔNG (HIỂN THỊ CÂU HỎI) ==========
async function attack() {
    if (playerHP <= 0) return;
    if (bossHP <= 0) return; // Sẽ được xử lý trong updateUI

    try {
        const res = await fetch(`/api/question?name=${encodeURIComponent(studentName)}`);
        currentQuestion = await res.json();

        // Xử lý hết câu hỏi
        if (currentQuestion.completed_all) {
            const playAgain = confirm(
                '🎉 Chúc mừng! Bạn đã trả lời đúng tất cả câu hỏi!\n\n' +
                'Bạn có muốn chơi lại từ đầu không?'
            );
            if (playAgain) {
                await fetch('/api/reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name: studentName })
                });
                // Reset trạng thái game
                bossLevel = 1;
                bossHP = BOSS_BASE_HP;
                playerHP = PLAYER_MAX_HP;
                await loadProgress();
                updateUI();
                attack();
                return;
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
            btn.onclick = () => handleAnswer(opt);
            container.appendChild(btn);
        });
        document.getElementById('question-panel').classList.remove('hidden');
    } catch (e) {
        console.error('Lỗi lấy câu hỏi:', e);
        alert('Có lỗi xảy ra, vui lòng thử lại.');
    }
}

// ========== XỬ LÝ TRẢ LỜI ==========
async function handleAnswer(selected) {
    const correct = (selected === currentQuestion.correct);
    let xpGain = 0;
    const payload = { name: studentName };

    if (correct) {
        // Gây sát thương lên Boss
        const playerDamage = 25;
        bossHP = Math.max(0, bossHP - playerDamage);

        // Hồi phục HP cho người chơi (tăng theo cấp Boss)
        const healAmount = 5 * bossLevel;
        playerHP = Math.min(PLAYER_MAX_HP, playerHP + healAmount);

        document.getElementById('message').textContent = 
            `✅ Chính xác! Gây ${playerDamage} sát thương, hồi ${healAmount} HP.`;
        
        xpGain = 30;
        payload.question_id = currentQuestionId;
    } else {
        // Sai: Boss phản đòn
        const bossDamage = 20;
        playerHP = Math.max(0, playerHP - bossDamage);
        document.getElementById('message').textContent = 
            `❌ Sai! Đáp án: ${currentQuestion.correct}. Bạn mất ${bossDamage} HP.`;
        xpGain = 0;   // Không nhận XP khi sai
    }

    payload.xp_gain = xpGain;
    await fetch('/api/progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    await loadProgress();
    document.getElementById('question-panel').classList.add('hidden');
    updateUI();

    // Nếu boss bị đánh bại, updateUI đã tự động chuyển màn
}

// ========== GẮN SỰ KIỆN ==========
document.getElementById('attack-btn').addEventListener('click', attack);
updateUI();