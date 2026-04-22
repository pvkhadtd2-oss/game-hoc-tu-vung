from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import os
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_production'

DATA_DIR = 'data'
STUDENTS_FILE = os.path.join(DATA_DIR, 'students.xlsx')
QUESTIONS_FILE = os.path.join(DATA_DIR, 'questions.xlsx')
PROGRESS_FILE = os.path.join(DATA_DIR, 'progress.xlsx')   
# Đầu file app.py, thêm:
CAU_HOI_DIR = os.path.join(DATA_DIR, 'CauHoi')
DEFAULT_QUESTIONS_FILE = os.path.join(CAU_HOI_DIR, '01_dich_viet_anh.xlsx')

# Biến lưu file câu hỏi hiện tại (có thể thay đổi theo chủ đề)
current_questions_file = DEFAULT_QUESTIONS_FILE

# Tạo thư mục data nếu chưa có
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ---------- Khởi tạo file học sinh ----------
if not os.path.exists(STUDENTS_FILE):
    df_students = pd.DataFrame(columns=['name', 'level', 'xp', 'high_score'])
    df_students.to_excel(STUDENTS_FILE, index=False)
else:
    df_students = pd.read_excel(STUDENTS_FILE)
    if 'high_score' not in df_students.columns:
        df_students['high_score'] = 0
        df_students.to_excel(STUDENTS_FILE, index=False)

# ---------- Khởi tạo file câu hỏi (có thêm cột id) ----------
if not os.path.exists(QUESTIONS_FILE):
    df_questions = pd.DataFrame({
        'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'word': ['apple', 'dog', 'cat', 'car', 'house', 'book', 'pen', 'teacher', 'school', 'run'],
        'meaning': ['quả táo', 'con chó', 'con mèo', 'xe hơi', 'ngôi nhà', 'quyển sách', 'bút mực', 'giáo viên', 'trường học', 'chạy'],
        'wrong1': ['chuối', 'mèo', 'chuột', 'máy bay', 'căn hộ', 'vở', 'thước', 'học sinh', 'bệnh viện', 'đi'],
        'wrong2': ['cam', 'chim', 'cá', 'tàu hỏa', 'lâu đài', 'báo', 'tẩy', 'bác sĩ', 'công viên', 'nhảy'],
        'wrong3': ['nho', 'thỏ', 'hổ', 'xe đạp', 'biệt thự', 'tạp chí', 'kẹp giấy', 'công an', 'siêu thị', 'bơi']
    })
    df_questions.to_excel(QUESTIONS_FILE, index=False)
else:
    df_questions = pd.read_excel(QUESTIONS_FILE)
    # Thêm cột id nếu chưa có (cho file cũ)
    if 'id' not in df_questions.columns:
        df_questions.insert(0, 'id', range(1, len(df_questions)+1))
        df_questions.to_excel(QUESTIONS_FILE, index=False)

# ---------- Khởi tạo file tiến độ ----------
if not os.path.exists(PROGRESS_FILE):
    df_progress = pd.DataFrame(columns=['student_name', 'question_id', 'completed'])
    df_progress.to_excel(PROGRESS_FILE, index=False)

# ------------------ ROUTES ------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/students', methods=['GET', 'POST'])
def manage_students():
    df = pd.read_excel(STUDENTS_FILE)
    if request.method == 'GET':
        return jsonify(df.to_dict(orient='records'))
    else:  # POST
        data = request.json
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Tên không được để trống'}), 400
        if name not in df['name'].values:
            new_row = pd.DataFrame([{'name': name, 'level': 1, 'xp': 0, 'high_score': 0}])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_excel(STUDENTS_FILE, index=False)
        return jsonify({'status': 'ok'})

@app.route('/api/progress', methods=['GET', 'POST'])
def progress():
    df_students = pd.read_excel(STUDENTS_FILE)
    df_progress = pd.read_excel(PROGRESS_FILE)

    # ----- GET: Trả về thông tin học sinh (có high_score) -----
    if request.method == 'GET':
        name = request.args.get('name')
        if name in df_students['name'].values:
            student = df_students[df_students['name'] == name].iloc[0].to_dict()
            if 'high_score' not in student:
                student['high_score'] = 0
            return jsonify(student)
        return jsonify(None)

    # ----- POST: Cập nhật XP, Level, High Score (có điều kiện) và đánh dấu câu hỏi -----
    else:
        data = request.json
        name = data['name']
        xp_gain = data.get('xp_gain', 0)
        score = data.get('score')          # Có thể không có
        question_id = data.get('question_id')

        idx = df_students[df_students['name'] == name].index[0]

        # Cập nhật XP và Level
        df_students.at[idx, 'xp'] += xp_gain
        df_students.at[idx, 'level'] = 1 + df_students.at[idx, 'xp'] // 100

        # Chỉ cập nhật high_score nếu score được gửi lên
        if score is not None:
            if 'high_score' not in df_students.columns:
                df_students['high_score'] = 0
            current_high = df_students.at[idx, 'high_score']
            if score > current_high:
                df_students.at[idx, 'high_score'] = score

        df_students.to_excel(STUDENTS_FILE, index=False)

        # Đánh dấu câu hỏi đã hoàn thành
        if question_id is not None:
            mask = (df_progress['student_name'] == name) & (df_progress['question_id'] == question_id)
            if not mask.any():
                new_progress = pd.DataFrame([{
                    'student_name': name,
                    'question_id': question_id,
                    'completed': True
                }])
                df_progress = pd.concat([df_progress, new_progress], ignore_index=True)
            else:
                df_progress.loc[mask, 'completed'] = True
            df_progress.to_excel(PROGRESS_FILE, index=False)

        return jsonify({
            'status': 'ok',
            'level': int(df_students.at[idx, 'level']),
            'xp': int(df_students.at[idx, 'xp']),
            'high_score': int(df_students.at[idx, 'high_score']) if 'high_score' in df_students.columns else 0
        })

@app.route('/api/question')
def get_question():
    name = request.args.get('name')
    if not name:
        return jsonify({'error': 'Missing student name'}), 400

    # Dùng file câu hỏi hiện tại (có thể là tong_hop.xlsx hoặc chủ đề khác)
    df_q = pd.read_excel(current_questions_file)
    df_progress = pd.read_excel(PROGRESS_FILE)

    # Lấy danh sách ID câu hỏi đã hoàn thành của học sinh này
    completed_ids = df_progress[(df_progress['student_name'] == name) & (df_progress['completed'] == True)]['question_id'].tolist()

    # Lọc ra các câu hỏi chưa hoàn thành
    available_questions = df_q[~df_q['id'].isin(completed_ids)]

    if available_questions.empty:
        # Nếu không còn câu hỏi nào, trả về thông báo đặc biệt (client sẽ xử lý)
        return jsonify({'completed_all': True})

    # Chọn ngẫu nhiên một câu
    row = available_questions.sample(1).iloc[0]
    options = [row['meaning'], row['wrong1'], row['wrong2'], row['wrong3']]
    random.shuffle(options)

    return jsonify({
        'id': int(row['id']),   # <<< Trả về ID để client gửi lại khi trả lời đúng
        'word': row['word'],
        'correct': row['meaning'],
        'options': options
    })

@app.route('/api/set_topic', methods=['POST'])
def set_topic():
    """Đổi file câu hỏi theo chủ đề được chọn."""
    global current_questions_file
    
    data = request.json
    topic = data.get('topic', 'tong_hop')
    
    # Map tên chủ đề với tên file
    file_map = {
        'all': '08_Tong_hop_350_cau.xlsx',
        'dich_viet_anh': '01_dich_viet_anh.xlsx',
        'dich_anh_viet': '02_dich_anh_viet.xlsx',
        'dien_tu': '03_dien_tu_vao_cau.xlsx',
        'dong_nghia': '04_dong_nghia.xlsx',
        'trai_nghia': '05_trai_nghia.xlsx',
        'dang_dung': '06_dang_dung_cua_tu.xlsx',
        'gioi_tu': '07_gioi_t.xlsx'
    }
    
    filename = file_map.get(topic, 'tong_hop.xlsx')
    new_file = os.path.join(CAU_HOI_DIR, filename)
    
    if os.path.exists(new_file):
        current_questions_file = new_file
        return jsonify({'status': 'ok', 'topic': topic, 'file': filename})
    else:
        return jsonify({'error': f'Không tìm thấy file {filename}'}), 404
    
@app.route('/api/reset', methods=['POST'])
def reset_student():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Thiếu tên'}), 400

    df_students = pd.read_excel(STUDENTS_FILE)
    if name not in df_students['name'].values:
        return jsonify({'error': 'Học sinh không tồn tại'}), 404

    idx = df_students[df_students['name'] == name].index[0]
    # Reset level và xp, giữ nguyên high_score
    df_students.at[idx, 'level'] = 1
    df_students.at[idx, 'xp'] = 0
    # KHÔNG đụng đến high_score

    df_students.to_excel(STUDENTS_FILE, index=False)

    # Xóa toàn bộ tiến độ câu hỏi của học sinh (vẫn giữ)
    df_progress = pd.read_excel(PROGRESS_FILE)
    df_progress = df_progress[df_progress['student_name'] != name]
    df_progress.to_excel(PROGRESS_FILE, index=False)

    # Trả về high_score hiện tại
    current_high = int(df_students.at[idx, 'high_score']) if 'high_score' in df_students.columns else 0
    return jsonify({
        'status': 'ok',
        'level': 1,
        'xp': 0,
        'high_score': current_high
    })

@app.route('/runner')
def runner():
    return render_template('runner.html')

@app.route('/boss')
def boss():
    return render_template('boss.html')

import signal
import sys
import os

def signal_handler(sig, frame):
    print('\n🛑 Đang tắt server...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    # Render sẽ gán PORT qua biến môi trường
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server đang chạy tại port {port}")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)