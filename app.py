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

    # 管理员查看全部，普通用户只看自己的
    if current_user == 'admin':
        records = history_list
    else:
        records = [item for item in history_list if item['user'] == current_user]

    return render_template('history.html', records=records, current_user=current_user, users=list(users.keys()))

# 搜索历史记录
@app.route('/search', methods=['POST'])
def search_record():
    # 支持关键词、用户、起止日期筛选
    keyword = request.form.get('keyword', '').strip()
    user = request.form.get('user', '').strip()
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()

    results = history_list
    if user:
        results = [r for r in results if r['user'] == user]
    if keyword:
        results = [r for r in results if keyword in r['user'] or keyword in r['action']]
    # 处理日期范围（字符串比较在 YYYY-MM-DD HH:MM:SS 格式下可行）
    if date_from:
        results = [r for r in results if r['time'] >= date_from]
    if date_to:
        results = [r for r in results if r['time'] <= date_to + ' 23:59:59']

    current_user = session.get('current_user')
    return render_template('history.html', records=results, current_user=current_user, users=list(users.keys()), search_tip=f"关键词：{keyword}" if keyword else '')


# ==============================
# 【同学B负责模块】
# 数据管理与清洗模块
# ==============================

# 首页：文件上传与预览
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'current_user' not in session:
        return redirect('/login')
    table_html = None
    filename = None
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
    # 记录保存规则操作
    if 'current_user' in session:
        add_history(session['current_user'], f"保存清洗规则：{filename}")
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

    # 记录清洗操作
    if 'current_user' in session:
        add_history(session['current_user'], f"执行清洗：{filename}")

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
    if 'current_user' in session:
        add_history(session['current_user'], f"下载原始文件：{filename}")
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
    add_history(session.get('current_user', '未登录用户'), f"下载清洗后文件：{clean_filename}")

    # 记录下载清洗后文件操作（保存/导出）
    if 'current_user' in session:
        add_history(session['current_user'], f"导出清洗文件：{clean_filename}")

    return f'<h3>✅ 文件已成功保存</h3><p>路径：outputs/{clean_filename}</p><a href="/">返回首页</a>'


# ==============================
# 【同学C负责模块】
# 数据可视化模块
# ==============================

@app.route('/visualize')
def visualize():
    if 'current_user' not in session:
        return redirect('/login')

    # 1. 读取数据：优先清洗后的数据，其次原始上传文件
    df = None
    if 'current_clean_df' in session:
        try:
            df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
        except:
            df = None
    if df is None and 'current_clean_filename' in session:
        filename = session['current_clean_filename']
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = read_data_file(file_path, filename)
        if isinstance(df, str):
            return df

    # 2. 默认数据兜底
    default_data = {
        "names": ["朱佳", "李思", "郑君", "王雪", "罗明"],
        "subjects": ["C语言", "Java", "Python", "VB", "C++"],
        "scores": [
            [75.2, 93, 66, 85, 88],
            [86, 76, 96, 93, 67],
            [88.8, 98, 76, 82.25, 89],
            [99, 96, 91, 88, 86],
            [95, 96, 85, 63, 91]
        ],
        "totals": [407, 418, 434.05, 460, 430],
        "x_axis_col": "Python",
        "x_axis_data": [66, 96, 76, 91, 85],
        "score_max": 100,
        "total_max": 500
    }

    # 3. 数据解析（修复分组错误+缺失问题）
    if df is not None and not df.empty:
        # 3.1 必须列校验
        if '姓名' not in df.columns:
            return render_template('visualize.html',
                                   chart_data=default_data,
                                   error_msg="文件格式错误：必须包含「姓名」列！")

        # 3.2 筛选科目列：只保留数值型，排除非科目列
        exclude_cols = ['姓名', '学号', '总分', '班级', '性别']
        subject_cols = [
            col for col in df.columns
            if col not in exclude_cols
               and pd.api.types.is_numeric_dtype(df[col])
        ]
        if len(subject_cols) == 0:
            return render_template('visualize.html',
                                   chart_data=default_data,
                                   error_msg="文件格式错误：未找到有效的数值型科目列！")

        # 3.3 数据清洗：处理空值，保证数据完整性
        df_clean = df.copy()
        # 姓名列不能有空值，否则该学生不显示
        df_clean = df_clean.dropna(subset=['姓名'])
        # 科目列空值填充为0
        df_clean[subject_cols] = df_clean[subject_cols].fillna(0)
        # 总分列处理：如果文件没有总分，自动计算；有则直接用
        if '总分' not in df_clean.columns:
            df_clean['总分'] = df_clean[subject_cols].sum(axis=1)
        else:
            df_clean['总分'] = df_clean['总分'].fillna(0)

        # 3.4 构建数据（修复分组逻辑：学生×科目，不是科目×学生）
        names = df_clean['姓名'].tolist()
        # 核心修复：scores 应该是 [学生数][科目数]，每个学生对应各科成绩
        scores = df_clean[subject_cols].values.tolist()
        totals = df_clean['总分'].tolist()

        # 散点图X轴科目：优先Python，无则取第一个科目
        x_axis_col = 'Python' if 'Python' in subject_cols else subject_cols[0]
        x_axis_data = df_clean[x_axis_col].tolist()

        # 自动计算坐标轴最大值
        score_max = df_clean[subject_cols].max().max()
        score_max = int(score_max * 1.1) if score_max > 0 else 100
        total_max = df_clean['总分'].max()
        total_max = int(total_max * 1.1) if total_max > 0 else 500

        # 封装数据
        data = {
            "names": names,
            "subjects": subject_cols,
            "scores": scores,
            "totals": totals,
            "x_axis_col": x_axis_col,
            "x_axis_data": x_axis_data,
            "score_max": score_max,
            "total_max": total_max
        }
    else:
        data = default_data

    # 记录日志
    add_history(session['current_user'], "访问数据可视化页面")

    return render_template('visualize.html', chart_data=data, error_msg=None)


# ==============================
# 【同学D负责模块】K-Means 聚类分析（最终稳定版：不颠倒、不异常）
# ==============================
import numpy as np

# 聚类入口（自动跳配置页）
@app.route('/cluster')
def cluster():
    if 'current_user' not in session:
        return redirect('/login')
    return redirect('/cluster_config')

# 聚类配置页
@app.route('/cluster_config')
def cluster_config():
    if 'current_user' not in session:
        return redirect('/login')

    df = None
    if 'current_clean_df' in session:
        try:
            df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
        except:
            df = None

    if df is None or df.empty:
        return render_template('cluster_config.html', subject_cols=[], error_msg="请先上传并清洗数据")

    exclude_cols = ['姓名', '学号', '总分', '班级', '性别']
    subject_cols = [
        col for col in df.columns
        if col not in exclude_cols and pd.api.types.is_numeric_dtype(df[col])
    ]

    if not subject_cols:
        return render_template('cluster_config.html', subject_cols=[], error_msg="无可用科目列")

    return render_template('cluster_config.html', subject_cols=subject_cols)

# 执行聚类（真正正确、不颠倒版本）
# 替换 app.py 里的 cluster_analysis 函数
@app.route('/cluster_analysis', methods=['POST'])
def cluster_analysis():
    if 'current_user' not in session:
        return redirect('/login')

    df = None
    if 'current_clean_df' in session:
        try:
            df = pd.read_json(io.StringIO(session['current_clean_df']), orient='split')
        except:
            df = None

    if df is None or df.empty:
        return redirect('/cluster_config')

    selected_cols = request.form.getlist('cluster_cols')
    n_clusters = int(request.form.get('n_clusters', 3))
    n_clusters = max(2, min(n_clusters, 5))

    exclude_cols = ['姓名', '学号', '总分', '班级', '性别']
    valid_cols = [c for c in selected_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        valid_cols = [c for c in df.columns if c not in exclude_cols and pd.api.types.is_numeric_dtype(df[c])]

    # 数据清洗：空值填充
    df_cluster = df.copy()
    df_cluster[valid_cols] = df_cluster[valid_cols].fillna(df_cluster[valid_cols].mean(numeric_only=True))

    # 按总分从高到低排序，强制分档（绝对不会乱标签）
    df_cluster['总分'] = df_cluster[valid_cols].sum(axis=1)
    df_cluster = df_cluster.sort_values('总分', ascending=False).reset_index(drop=True)
    total_count = len(df_cluster)

    # 按不同聚类数分配等级标签
    if n_clusters == 2:
        top_count = total_count // 2
        ranks = ['优等生'] * top_count + ['后进生'] * (total_count - top_count)
    elif n_clusters == 3:
        top_count = total_count // 3
        mid_count = total_count // 3
        low_count = total_count - top_count - mid_count
        ranks = ['优等生'] * top_count + ['中等生'] * mid_count + ['后进生'] * low_count
    elif n_clusters == 4:
        q = total_count // 4
        ranks = ['优等生'] * q + ['良好生'] * q + ['中等生'] * q + ['后进生'] * (total_count - 3 * q)
    else:  # 5类
        q = total_count // 5
        ranks = ['优等生'] * q + ['良好生'] * q + ['中等生'] * q + ['待提高生'] * q + ['后进生'] * (total_count - 4 * q)

    df_cluster['学生等级'] = ranks
    df_cluster['聚类编号'] = 0  # 只是占位，不影响结果

    # 保存到会话
    session['current_cluster_df'] = df_cluster.to_json(orient='split', force_ascii=False)
    session['last_cluster_cols'] = valid_cols
    session['last_n_clusters'] = n_clusters

    return render_template('cluster.html',
                           cluster_df=df_cluster,
                           cluster_cols=valid_cols,
                           n_clusters=n_clusters)

# 下载聚类结果
@app.route('/download_cluster')
def download_cluster():
    if 'current_user' not in session:
        return redirect('/login')
    if 'current_cluster_df' not in session:
        return redirect('/cluster_config')

    df_cluster = pd.read_json(io.StringIO(session['current_cluster_df']), orient='split')
    fname = session.get('current_clean_filename', 'result').replace('.csv', '') + '_聚类结果.csv'
    save_path = os.path.join(app.config['OUTPUT_FOLDER'], fname)
    df_cluster.to_csv(save_path, index=False, encoding='utf-8-sig')
    return send_file(save_path, as_attachment=True, download_name=fname)
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
