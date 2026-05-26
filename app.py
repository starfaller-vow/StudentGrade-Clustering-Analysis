# ==============================
# 交互式数据分析系统
# 项目结构清晰版
# ==============================

# 导入模块
from flask import Flask, render_template, request, send_file, redirect, session
from sklearn.cluster import KMeans
import pandas as pd
import os
import csv
import datetime
import io

# 初始化应用
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
# ==============================

# 用户账号配置
users = {
    "admin": "123456",
    "student": "654321"
}

# 初始化历史记录文件
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user", "time", "action"])

# 加载历史记录
def load_history():
    data = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

history_list = load_history()

# 记录操作历史
def add_history(user, action):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([user, now, action])
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

# 查看历史记录
@app.route('/history')
def show_history():
    if 'current_user' not in session:
        return redirect('/login')
    current_user = session['current_user']
    user_history = [item for item in history_list if item['user'] == current_user]
    return render_template('history.html', records=user_history)

# 搜索历史记录
@app.route('/search', methods=['POST'])
def search_record():
    keyword = request.form['keyword']
    results = [item for item in history_list if keyword in item['user'] or keyword in item['action']]
    return render_template('history.html', records=results, search_tip=f"关键词：{keyword}")


# ==============================
# 【同学B负责模块】
# 数据管理与清洗模块
# ==============================

# 首页：文件上传与预览
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'current_user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        file = request.files['file']
        filename = file.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        # 重置清洗状态
        session.pop('current_clean_df', None)
        session.pop('clean_config', None)

        # 记录操作
        add_history(session['current_user'], f"上传文件：{filename}")

        # 读取文件
        df = read_data_file(save_path, filename)
        if isinstance(df, str):
            return df

        return render_template('index.html',
                               table_html=df.to_html(classes="table table-striped", index=False),
                               filename=filename)
    return render_template('index.html')

# 读取数据文件
def read_data_file(file_path, filename):
    try:
        if filename.endswith('.csv'):
            try:
                return pd.read_csv(file_path, encoding='utf-8')
            except:
                return pd.read_csv(file_path, encoding='gbk')
        elif filename.endswith('.xlsx'):
            return pd.read_excel(file_path)
        else:
            return "不支持此文件类型！仅支持 CSV / Excel"
    except Exception as e:
        return f"读取文件失败：{str(e)}"

# 清洗规则配置页面
@app.route('/config/<filename>')
def clean_config(filename):
    if 'current_user' not in session:
        return redirect('/login')

    session['current_clean_filename'] = filename

    # 读取数据（优先使用上次清洗结果）
    if 'current_clean_df' in session:
        df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
    else:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = read_data_file(file_path, filename)
        if isinstance(df, str):
            return df

    return render_template('config.html',
                           filename=filename,
                           columns=df.columns.tolist())

# 保存清洗规则
@app.route('/save_config', methods=['POST'])
def save_config():
    filename = request.form.get('filename')
    session['clean_config'] = {
        'min_val': float(request.form.get('min_val')),
        'max_val': float(request.form.get('max_val')),
        'remove_outliers': request.form.get('remove_outliers') == 'on',
        'fill_missing': request.form.get('fill_missing') == 'on',
        'clean_cols': request.form.getlist('clean_cols')
    }
    return redirect(f'/clean/{filename}')

# 执行数据清洗
@app.route('/clean/<filename>')
def clean_data(filename):
    # 读取数据
    if 'current_clean_df' in session:
        df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
    else:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = read_data_file(file_path, filename)
        if isinstance(df, str):
            return df

    # 获取清洗配置
    config = session.get('clean_config', {
        'min_val': 0,
        'max_val': 100,
        'remove_outliers': True,
        'fill_missing': True,
        'clean_cols': df.select_dtypes(include=['number']).columns.tolist()
    })

    # 执行清洗
    df = apply_clean_rules(df, config)

    # 保存清洗结果
    session['current_clean_df'] = df.to_json(orient='split')

    return render_template('clean.html',
                           clean_table=df.to_html(classes="table table-striped", index=False),
                           clean_filename=f'clean_{filename}',
                           filename=filename)

# 应用清洗规则
def apply_clean_rules(df, config):
    min_val = config['min_val']
    max_val = config['max_val']
    remove_outliers = config['remove_outliers']
    fill_missing = config['fill_missing']
    clean_cols = config['clean_cols']

    # 删除异常值
    if remove_outliers:
        for col in clean_cols:
            if col in df.columns:
                df = df[~((df[col].notna()) & ((df[col] < min_val) | (df[col] > max_val)))]

    # 填充缺失值
    if fill_missing:
        df.fillna(df.mean(numeric_only=True), inplace=True)

    return df

# 下载原文件
@app.route('/download/<filename>')
def download_original(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "文件不存在！"
    return send_file(file_path, as_attachment=True, download_name=filename)

# 下载清洗后文件
@app.route('/download_clean/<clean_filename>')
def download_clean(clean_filename):
    # 优先使用会话中的清洗结果
    if 'current_clean_df' in session:
        df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
    else:
        # 重新执行清洗
        original_filename = clean_filename.replace("clean_", "")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
        df = read_data_file(file_path, original_filename)
        if isinstance(df, str):
            return df

        config = session.get('clean_config', {
            'min_val': 0,
            'max_val': 100,
            'remove_outliers': True,
            'fill_missing': True,
            'clean_cols': df.select_dtypes(include=['number']).columns.tolist()
        })
        df = apply_clean_rules(df, config)

    # 保存文件
    save_path = os.path.join(app.config['OUTPUT_FOLDER'], clean_filename)
    if clean_filename.endswith('.csv'):
        df.to_csv(save_path, index=False, encoding='utf-8')
    else:
        df.to_excel(save_path, index=False)

    return f'<h3>✅ 文件已成功保存</h3><p>路径：outputs/{clean_filename}</p><a href="/">返回首页</a>'


# ==============================
# 【同学C负责模块】
# 数据可视化模块
# ==============================
@app.route('/visualize')
def visualize():
    return render_template('visualize.html')


# ==============================
# 【同学D负责模块】
# 聚类分析模块
# ==============================
@app.route('/cluster')
def cluster_analysis():
    data = [
        ["朱佳", 75.2, 93, 66, 85, 88],
        ["李思", 86, 76, 96, 93, 67],
        ["郑君", 88.8, 98, 76, 82.25, 89],
        ["王雪", 99, 96, 91, 88, 86],
        ["罗明", 95, 96, 85, 63, 91]
    ]
    df = pd.DataFrame(data, columns=["姓名", "C语言", "Java", "Python", "VB", "C++"])
    score_cols = ["C语言", "Java", "Python", "VB", "C++"]

    # K-Means聚类
    kmeans = KMeans(n_clusters=3, random_state=42)
    df['标签'] = kmeans.fit_predict(df[score_cols])

    # 映射学生等级
    rank_map = {0: "后进生", 1: "中等生", 2: "优等生"}
    df['学生等级'] = df['标签'].map(rank_map)
    df = df.drop(columns=['标签'])

    return render_template('cluster.html', cluster_table=df.to_html(index=False))


# ==============================
# 【同学E负责模块】
# 页面美化、交互优化
# ==============================
# HTML模板文件：index.html, login.html, clean.html, visualize.html, cluster.html, history.html


# ==============================
# 项目启动入口
# ==============================
if __name__ == '__main__':
    app.run(debug=True)
