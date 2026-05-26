# ==============================
# 公共配置模块（所有人共用）
# ==============================
from flask import Flask, render_template, request, send_file, redirect, session
from sklearn.cluster import KMeans
import pandas as pd
import os
import csv
import datetime

app = Flask(__name__)
app.secret_key = "my_login_key_123456"

# 全局路径配置
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
OUTPUT_FOLDER = os.path.join(os.getcwd(), "outputs")
HISTORY_DIR = "history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.csv")

# 自动创建所需文件夹
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER


# ==============================
# 【同学A负责模块】
# 整体架构、登录权限、日志管理
# 对应：多用户登录、历史记录存储与检索
# ==============================
# 多用户账号
users = {
    "admin": "123456",
    "student": "654321"
}

# 初始化历史记录文件表头
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

# 新增操作历史
def add_history(user, action):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([user, now, action])
    global history_list
    history_list = load_history()

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['current_user'] = username
            return redirect('/')
    return render_template('login.html')

# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# 个人历史记录查看
@app.route('/history')
def show_history():
    if 'current_user' not in session:
        return redirect('/login')
    current_user = session['current_user']
    my_history = [item for item in history_list if item['user'] == current_user]
    return render_template('history.html', records=my_history)

# 历史记录检索功能
@app.route('/search', methods=['POST'])
def search_record():
    keyword = request.form['keyword']
    result = [item for item in history_list if keyword in item['user'] or keyword in item['action']]
    return render_template('history.html', records=result, search_tip=f"关键词：{keyword}")


# ==============================
# 【同学B负责模块】
# 数据管理与清洗模块
# 对应：数据上传、预览、下载、清洗、导出
# ==============================
# 首页：文件上传、预览
@app.route('/', methods=['GET', 'POST'])
def index():
    # 登录校验
    if 'current_user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        file = request.files['file']
        filename = file.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        # 记录上传操作
        add_history(session['current_user'], f"上传文件：{filename}")

        df = pd.read_csv(save_path, encoding='utf-8')
        return render_template('index.html',
                               table_html=df.to_html(classes="table table-striped"),
                               filename=filename)
    return render_template('index.html')

# 数据清洗逻辑（仅预览，不自动保存）
@app.route('/clean/<filename>')
def clean_data(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_csv(file_path, encoding='utf-8')

    # 缺失值填充 + 异常分数过滤
    df.fillna(df.mean(numeric_only=True), inplace=True)
    score_cols = ['C语言', 'Java', 'Python', 'VB', 'C++']
    for col in score_cols:
        if col in df.columns:
            df = df[df[col] <= 100]

    clean_filename = f'clean_{filename}'
    return render_template('clean.html',
                           clean_table=df.to_html(classes="table table-striped"),
                           clean_filename=clean_filename,
                           df_data=df.to_dict())

# 点击下载 → 才保存清洗后文件到outputs
@app.route('/download_clean/<clean_filename>')
def download_clean(clean_filename):
    original_filename = clean_filename.replace("clean_", "")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)

    df = pd.read_csv(file_path, encoding='utf-8')
    df.fillna(df.mean(numeric_only=True), inplace=True)
    score_cols = ['C语言', 'Java', 'Python', 'VB', 'C++']
    for col in score_cols:
        if col in df.columns:
            df = df[df[col] <= 100]

    save_path = os.path.join(app.config['OUTPUT_FOLDER'], clean_filename)
    df.to_csv(save_path, index=False, encoding='utf-8')

    return f'''
    <h3>文件已成功保存到项目文件夹</h3>
    <p>保存路径：outputs/{clean_filename}</p>
    <a href="/">返回首页</a>
    '''

# 清洗页面入口
@app.route('/clean')
def clean_page():
    return render_template('clean.html')


# ==============================
# 【同学C负责模块】
# 数据可视化模块
# 对应：可视化页面、动态图表
# ==============================
@app.route('/visualize')
def visualize():
    return render_template('visualize.html')


# ==============================
# 【同学D负责模块】
# 聚类分析模块
# 对应：K-Means聚类、学生等级划分
# ==============================
@app.route('/cluster')
def cluster_analysis():
    # 测试用学生成绩数据
    data = [
        ["朱佳",75.2,93,66,85,88],
        ["李思",86,76,96,93,67],
        ["郑君",88.8,98,76,82.25,89],
        ["王雪",99,96,91,88,86],
        ["罗明",95,96,85,63,91]
    ]
    df = pd.DataFrame(data, columns=["姓名","C语言","Java","Python","VB","C++"])
    score_cols = ["C语言","Java","Python","VB","C++"]
    X = df[score_cols]

    # K‑Means聚类，分为3类
    kmeans = KMeans(n_clusters=3, random_state=42)
    df['标签'] = kmeans.fit_predict(X)

    # 按总分映射学生等级
    total_score = df[score_cols].sum(axis=1)
    rank_map = {0:"后进生",1:"中等生",2:"优等生"}
    df['学生等级'] = df['标签'].map(rank_map)
    df = df.drop(columns=['标签'])

    table = df.to_html(index=False)
    return render_template('cluster.html', cluster_table=table)


# ==============================
# 【同学E负责模块】
# 页面美化、交互优化（代码无后端逻辑，负责HTML+CSS+JS+视频）
# ==============================
# 所有HTML页面：index.html、login.html、clean.html、visualize.html、cluster.html、history.html
# 由同学E设计美化、交互、响应式布局，录制项目介绍视频


# ==============================
# 项目启动入口
# ==============================
if __name__ == '__main__':
    app.run(debug=True)