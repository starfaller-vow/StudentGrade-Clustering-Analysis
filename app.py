from flask import Flask, render_template, request, send_file, redirect, session
from sklearn.cluster import KMeans
import pandas as pd
import os
import csv
import datetime

app = Flask(__name__)
app.secret_key = "my_login_key_123456"

# 多用户账号
users = {
    "admin": "123456",
    "student": "654321"
}

# ===========================
# 历史记录 - 永久保存到文件
# ===========================

HISTORY_DIR = "history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.csv")

# 自动创建文件夹（不存在就创建，存在就跳过）
os.makedirs(HISTORY_DIR, exist_ok=True)

# 如果文件不存在，创建表头
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user", "time", "action"])

# 加载历史记录
def load_history():
    data = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

history_list = load_history()

# 新增一条记录（同时写入文件 + 刷新内存）
def add_history(user, action):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 写入文件
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([user, now, action])
    # 重新加载
    global history_list
    history_list = load_history()

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
OUTPUT_FOLDER = os.path.join(os.getcwd(), "outputs")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    # ============== 这里加登录判断（复制这两行）==============
    if 'current_user' not in session:
        return redirect('/login')
    # ======================================================

    if request.method == 'POST':
        file = request.files['file']
        filename = file.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        # ========== 在这里加 历史记录 ==========
        add_history(session['current_user'], f"上传文件：{filename}")
        # =====================================

        df = pd.read_csv(save_path, encoding='utf-8')
        return render_template('index.html',
                               table_html=df.to_html(classes="table table-striped"),
                               filename=filename)
    return render_template('index.html')

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

@app.route('/clean/<filename>')
def clean_data(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_csv(file_path, encoding='utf-8')

    df.fillna(df.mean(numeric_only=True), inplace=True)
    score_cols = ['C语言', 'Java', 'Python', 'VB', 'C++']
    for col in score_cols:
        if col in df.columns:
            df = df[df[col] <= 100]

    clean_filename = f'clean_{filename}'
    clean_path = os.path.join(app.config['OUTPUT_FOLDER'], clean_filename)
    df.to_csv(clean_path, index=False, encoding='utf-8')

    return render_template('clean.html',
                           clean_table=df.to_html(classes="table table-striped"),
                           clean_filename=clean_filename)

@app.route('/download_clean/<clean_filename>')
def download_clean(clean_filename):
    clean_path = os.path.join(app.config['OUTPUT_FOLDER'], clean_filename)
    return send_file(clean_path, as_attachment=True)

@app.route('/visualize')
def visualize():
    return render_template('visualize.html')

@app.route('/clean')
def clean_page():
    return render_template('clean.html')

@app.route('/cluster')
def cluster_analysis():
    # 原始成绩数据
    data = [
        ["朱佳",75.2,93,66,85,88],
        ["李思",86,76,96,93,67],
        ["郑君",88.8,98,76,82.25,89],
        ["王雪",99,96,91,88,86],
        ["罗明",95,96,85,63,91]
    ]
    df = pd.DataFrame(data, columns=["姓名","C语言","Java","Python","VB","C++"])
    # 提取成绩用于聚类
    score_cols = ["C语言","Java","Python","VB","C++"]
    X = df[score_cols]

    # 真正运行K‑Means，分3类
    kmeans = KMeans(n_clusters=3, random_state=42)
    df['标签'] = kmeans.fit_predict(X)

    # 把数字标签转成等级（按总分匹配）
    total_score = df[score_cols].sum(axis=1)
    rank_map = {0:"后进生",1:"中等生",2:"优等生"}
    df['学生等级'] = df['标签'].map(rank_map)
    df = df.drop(columns=['标签'])

    table = df.to_html(index=False)
    return render_template('cluster.html', cluster_table=table)
# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # 校验账号密码
        if username in users and users[username] == password:
            session['current_user'] = username
            return redirect('/')
    return render_template('login.html')

# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# 查看个人历史记录
@app.route('/history')
def show_history():
    if 'current_user' not in session:
        return redirect('/login')
    current_user = session['current_user']
    my_history = [item for item in history_list if item['user'] == current_user]
    return render_template('history.html', records=my_history)

# 检索（搜索）功能
@app.route('/search', methods=['POST'])
def search_record():
    keyword = request.form['keyword']
    result = [item for item in history_list if keyword in item['user'] or keyword in item['action']]
    return render_template('history.html', records=result, search_tip=f"关键词：{keyword}")
if __name__ == '__main__':
    app.run(debug=True)