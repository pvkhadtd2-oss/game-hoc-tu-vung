import os
import random
from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "a_default_secret_key_change_me")

DATA_DIR = 'data'
CAU_HOI_DIR = os.path.join(DATA_DIR, 'CauHoi')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ===================== KẾT NỐI DATABASE =====================
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ConnectionError("DATABASE_URL environment variable is not set.")
    conn = psycopg2.connect(db_url, sslmode="require")
    return conn

# ===================== KHỞI TẠO BẢNG & NẠP DỮ LIỆU =====================
def init_game_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Bảng học sinh
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_students (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    high_score INTEGER DEFAULT 0
                );
            """)
            cur.execute("""
                ALTER TABLE game_students ADD COLUMN IF NOT EXISTS current_topic TEXT DEFAULT 'all';
            """)
            # 2. Bảng câu hỏi từ vựng
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_vocab_questions (
                    id SERIAL PRIMARY KEY,
                    topic TEXT NOT NULL DEFAULT 'all',
                    word TEXT NOT NULL,
                    meaning TEXT NOT NULL,
                    wrong1 TEXT NOT NULL,
                    wrong2 TEXT NOT NULL,
                    wrong3 TEXT NOT NULL
                );
            """)

            # 3. Bảng tiến độ
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_progress (
                    id SERIAL PRIMARY KEY,
                    student_name TEXT NOT NULL REFERENCES game_students(name) ON DELETE CASCADE,
                    question_id INTEGER NOT NULL REFERENCES game_vocab_questions(id) ON DELETE CASCADE,
                    completed BOOLEAN DEFAULT FALSE,
                    UNIQUE(student_name, question_id)
                );
            """)

            conn.commit()

            # Nạp dữ liệu câu hỏi nếu bảng game_vocab_questions trống
            cur.execute("SELECT COUNT(*) FROM game_vocab_questions")
            if cur.fetchone()[0] == 0:
                import_vocab_from_excel(cur)
                conn.commit()
    finally:
        conn.close()

def import_vocab_from_excel(cur):
    file_topic_map = {
        '01_dich_viet_anh': 'dich_viet_anh',
        '02_dich_anh_viet': 'dich_anh_viet',
        '03_dien_tu_vao_cau': 'dien_tu',
        '04_dong_nghia': 'dong_nghia',
        '05_trai_nghia': 'trai_nghia',
        '06_dang_dung_cua_tu': 'dang_dung',
        '07_gioi_tu': 'gioi_tu',
        '08_Tong_hop_350_cau': 'all'
    }

    imported = 0
    if os.path.exists(CAU_HOI_DIR):
        for filename in os.listdir(CAU_HOI_DIR):
            if not filename.endswith('.xlsx'):
                continue
            filepath = os.path.join(CAU_HOI_DIR, filename)
            try:
                df = pd.read_excel(filepath, engine='openpyxl')
            except Exception as e:
                print(f"❌ Lỗi đọc {filename}: {e}")
                continue

            base_name = os.path.splitext(filename)[0]
            topic = file_topic_map.get(base_name, 'unknown')

            required_cols = ['word', 'meaning', 'wrong1', 'wrong2', 'wrong3']
            if not all(col in df.columns for col in required_cols):
                print(f"❌ {filename} thiếu cột, bỏ qua.")
                continue

            for _, row in df.iterrows():
                cur.execute(
                    """INSERT INTO game_vocab_questions (topic, word, meaning, wrong1, wrong2, wrong3)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (topic, row['word'], row['meaning'], row['wrong1'], row['wrong2'], row['wrong3'])
                )
                imported += 1

    if imported == 0:
        print("⚠️ Không import được Excel, dùng dữ liệu mẫu mặc định.")
        insert_default_questions(cur)
    else:
        print(f"✅ Đã import {imported} câu hỏi từ {CAU_HOI_DIR}")

def insert_default_questions(cur):
    defaults = [
        ('all', 'apple', 'quả táo', 'chuối', 'cam', 'nho'),
        ('all', 'dog', 'con chó', 'mèo', 'chim', 'thỏ'),
        ('all', 'cat', 'con mèo', 'chuột', 'cá', 'hổ'),
        ('all', 'car', 'xe hơi', 'máy bay', 'tàu hỏa', 'xe đạp'),
        ('all', 'house', 'ngôi nhà', 'căn hộ', 'lâu đài', 'biệt thự'),
        ('all', 'book', 'quyển sách', 'vở', 'báo', 'tạp chí'),
        ('all', 'pen', 'bút mực', 'thước', 'tẩy', 'kẹp giấy'),
        ('all', 'teacher', 'giáo viên', 'học sinh', 'bác sĩ', 'công an'),
        ('all', 'school', 'trường học', 'bệnh viện', 'công viên', 'siêu thị'),
        ('all', 'run', 'chạy', 'đi', 'nhảy', 'bơi')
    ]
    cur.executemany(
        "INSERT INTO game_vocab_questions (topic, word, meaning, wrong1, wrong2, wrong3) VALUES (%s, %s, %s, %s, %s, %s)",
        defaults
    )
    print("✅ Đã thêm 10 câu hỏi mẫu.")

# ===================== ROUTES =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/runner')
def runner():
    return render_template('runner.html')

@app.route('/boss')
def boss():
    return render_template('boss.html')

@app.route('/health')
@app.route('/ping')
def health_check():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db": "down", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()

# ---------- HỌC SINH ----------
@app.route('/api/students', methods=['GET', 'POST'])
def manage_students():
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT name, level, xp, high_score FROM game_students ORDER BY name")
                students = cur.fetchall()
            return jsonify(students)

        # POST: thêm học sinh mới
        data = request.json
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Tên không được để trống'}), 400

        with conn.cursor() as cur:
            cur.execute("SELECT name FROM game_students WHERE name = %s", (name,))
            if not cur.fetchone():
                cur.execute("INSERT INTO game_students (name) VALUES (%s)", (name,))
                conn.commit()
        return jsonify({'status': 'ok'})
    finally:
        conn.close()

# ---------- TIẾN ĐỘ ----------
@app.route('/api/progress', methods=['GET', 'POST'])
def progress():
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            name = request.args.get('name')
            if not name:
                return jsonify(None)
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT name, level, xp, high_score FROM game_students WHERE name = %s", (name,))
                student = cur.fetchone()
            return jsonify(student)

        # POST: cập nhật
        data = request.json
        name = data['name']
        xp_gain = data.get('xp_gain', 0)
        score = data.get('score')
        question_id = data.get('question_id')

        with conn.cursor() as cur:
            # Cập nhật XP, level, high_score (dùng CASE cho high_score)
            cur.execute("""
                UPDATE game_students
                SET xp = xp + %s,
                    level = 1 + ((xp + %s) / 100),
                    high_score = CASE
                        WHEN %s IS NOT NULL AND %s > high_score THEN %s
                        ELSE high_score
                    END
                WHERE name = %s
                RETURNING level, xp, high_score
            """, (xp_gain, xp_gain, score, score, score, name))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Học sinh không tồn tại'}), 404
            level, xp, high_score = row

            # Đánh dấu câu hỏi
            if question_id is not None:
                cur.execute("""
                    INSERT INTO game_progress (student_name, question_id, completed)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (student_name, question_id) DO UPDATE SET completed = TRUE
                """, (name, question_id))
            conn.commit()

        return jsonify({
            'status': 'ok',
            'level': level,
            'xp': xp,
            'high_score': high_score
        })
    finally:
        conn.close()

# ---------- LẤY CÂU HỎI ----------
@app.route('/api/question')
def get_question():
    name = request.args.get('name')
    if not name:
        return jsonify({'error': 'Missing student name'}), 400

    # Lấy topic: ưu tiên query string, nếu không có thì lấy từ bảng game_students
    topic = request.args.get('topic')
    conn = get_db_connection()
    try:
        # Nếu client không gửi topic, lấy current_topic của học sinh
        if not topic:
            with conn.cursor() as cur:
                cur.execute("SELECT current_topic FROM game_students WHERE name = %s", (name,))
                row = cur.fetchone()
                topic = row[0] if row else 'all'

        # Lấy danh sách câu hỏi chưa hoàn thành theo topic
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            # Lấy danh sách question_id đã hoàn thành của học sinh
            cur.execute("""
                SELECT question_id FROM game_progress
                WHERE student_name = %s AND completed = TRUE
            """, (name,))
            completed_ids = [row['question_id'] for row in cur.fetchall()]

            # Tìm câu hỏi ngẫu nhiên chưa hoàn thành
            if completed_ids:
                cur.execute("""
                    SELECT id, word, meaning, wrong1, wrong2, wrong3
                    FROM game_vocab_questions
                    WHERE topic = %s AND id NOT IN %s
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (topic, tuple(completed_ids)))
            else:
                cur.execute("""
                    SELECT id, word, meaning, wrong1, wrong2, wrong3
                    FROM game_vocab_questions
                    WHERE topic = %s
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (topic,))

            row = cur.fetchone()
            if not row:
                return jsonify({'completed_all': True})

            # Trộn các đáp án
            options = [row['meaning'], row['wrong1'], row['wrong2'], row['wrong3']]
            random.shuffle(options)

            return jsonify({
                'id': row['id'],
                'word': row['word'],
                'correct': row['meaning'],
                'options': options
            })
    finally:
        conn.close()

# ---------- ĐỔI CHỦ ĐỀ ----------
@app.route('/api/set_topic', methods=['POST'])
def set_topic():
    data = request.json
    topic = data.get('topic', 'all')
    name = data.get('name')          # <<< Cần tên học sinh

    if not name:
        return jsonify({'error': 'Missing student name'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE game_students SET current_topic = %s WHERE name = %s
            """, (topic, name))
            conn.commit()
        return jsonify({'status': 'ok', 'topic': topic})
    finally:
        conn.close()

# ---------- RESET HỌC SINH ----------
@app.route('/api/reset', methods=['POST'])
def reset_student():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Thiếu tên'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Reset level và xp, giữ nguyên high_score
            cur.execute("""
                UPDATE game_students
                SET level = 1, xp = 0
                WHERE name = %s
                RETURNING high_score
            """, (name,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Học sinh không tồn tại'}), 404
            high_score = row[0]

            # Xóa toàn bộ tiến độ của học sinh này
            cur.execute("DELETE FROM game_progress WHERE student_name = %s", (name,))
            conn.commit()

        return jsonify({
            'status': 'ok',
            'level': 1,
            'xp': 0,
            'high_score': high_score
        })
    finally:
        conn.close()
@app.route('/api/debug/topics')
def debug_topics():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            # Thông tin học sinh và current_topic
            cur.execute("SELECT id, name, current_topic FROM game_students ORDER BY id")
            students = cur.fetchall()

            # Thống kê câu hỏi theo topic
            cur.execute("SELECT topic, COUNT(*) as total FROM game_vocab_questions GROUP BY topic ORDER BY topic")
            topic_counts = cur.fetchall()

            # Vài câu hỏi mẫu (để kiểm tra nội dung)
            cur.execute("SELECT * FROM game_vocab_questions LIMIT 5")
            sample_questions = cur.fetchall()

        return jsonify({
            'students': students,
            'topic_counts': topic_counts,
            'sample_questions': sample_questions
        })
    finally:
        conn.close()

# ===================== KHỞI ĐỘNG =====================
if __name__ == '__main__':
    init_game_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Game server running on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)