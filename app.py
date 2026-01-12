import streamlit as st
import pandas as pd
import io
import hashlib  # 新增：用于计算 MD5

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(page_title="Zuma表格工具", layout="wide")
st.title("📊 Zuma表格数据筛选与合并工具 (统计增强 + ID生成版)")

# ==========================================
# 1. 侧边栏：设置筛选条件
# ==========================================
st.sidebar.header("1. 设置筛选条件")

# Times 筛选
st.sidebar.subheader("Times (倍数) 范围")
st.sidebar.info("计算公式: Times = (Amount + 10000) / 10000")
min_times = st.sidebar.number_input("Times 最小值", value=0.0, step=0.1, format="%.2f")
max_times = st.sidebar.number_input("Times 最大值", value=1000.0, step=0.1, format="%.2f")

# LauncherNum 筛选
st.sidebar.subheader("LauncherNum (发射数) 范围")
min_launcher = st.sidebar.number_input("LauncherNum 最小值", value=0)
max_launcher = st.sidebar.number_input("LauncherNum 最大值", value=100)

# ==========================================
# 2. 全能读取函数
# ==========================================
def super_reader(file):
    """尝试多种方式读取 Excel 或 CSV"""
    # 策略 1: Excel
    try:
        all_sheets = pd.read_excel(file, sheet_name=None)
        best_df = pd.DataFrame()
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                best_df = sheet_df
        if not best_df.empty:
            return best_df
    except:
        pass
    
    # 策略 2: CSV (尝试不同编码和容错)
    methods = [
        (pd.read_csv, {}),
        (pd.read_csv, {'encoding': 'gbk'}),
        (pd.read_csv, {'on_bad_lines': 'skip'}),
    ]
    
    for reader, kwargs in methods:
        file.seek(0)
        try:
            df = reader(file, **kwargs)
            if not df.empty: return df
        except:
            continue
            
    return None

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件 (支持多文件)", 
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    all_data_frames = []
    
    # 显示处理进度
    with st.spinner(f"正在读取并预处理 {len(uploaded_files)} 个文件..."):
        for file in uploaded_files:
            # 读取
            df = super_reader(file)
            
            if df is not None and not df.empty:
                try:
                    # 清洗列名
                    df.columns = df.columns.astype(str).str.strip()
                    
                    # 检查必要列
                    if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                        # 计算 Times
                        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                        df['Times'] = (df['Amount'] + 10000) / 10000
                        all_data_frames.append(df)
                except Exception as e:
                    st.error(f"处理文件 {file.name} 时出错: {e}")

    if all_data_frames:
        # 合并所有数据用于统计
        master_df = pd.concat(all_data_frames, ignore_index=True)
        
        # ==========================================
        # 统计信息模块 (Statistics)
        # ==========================================
        st.markdown("### 📈 数据全貌统计")
        st.info("这里展示的是**所有上传文件**合并后的原始数据统计，供您参考以设置筛选条件。")
        
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        stat_col1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        
        t_min_val = master_df['Times'].min()
        t_max_val = master_df['Times'].max()
        stat_col2.metric("✖️ Times (倍数) 范围", f"{t_min_val:.2f} ~ {t_max_val:.2f}")
        
        l_min_val = master_df['LauncherNum'].min()
        l_max_val = master_df['LauncherNum'].max()
        stat_col3.metric("🚀 LauncherNum (发射) 范围", f"{l_min_val} ~ {l_max_val}")
        
        st.divider()

        # ==========================================
        # 筛选与导出模块
        # ==========================================
        st.markdown("### 🔍 数据筛选与生成")
        
        if st.button("👉 按左侧条件开始筛选并导出", type="primary"):
            
            # 1. 执行筛选
            filtered_df = master_df[
                (master_df['Times'] >= min_times) & 
                (master_df['Times'] <= max_times) & 
                (master_df['LauncherNum'] >= min_launcher) & 
                (master_df['LauncherNum'] <= max_launcher)
            ].copy() # copy很重要，避免SettingWithCopyWarning
            
            if not filtered_df.empty:
                # 2. 调整列顺序 (Times 放在 Amount 后面)
                cols = list(filtered_df.columns)
                if 'Times' in cols and 'Amount' in cols:
                    cols.remove('Times')
                    amount_idx = cols.index('Amount')
                    cols.insert(amount_idx + 1, 'Times')
                    filtered_df = filtered_df[cols]

                # ==========================================
                # 【新增功能】 MD5 和 ID 生成
                # ==========================================
                with st.spinner('正在生成 MD5 和 Batch ID...'):
                    # A. 生成 MD5 (对全行内容)
                    def calculate_md5(row):
                        row_str = "".join(row.astype(str).values)
                        return hashlib.md5(row_str.encode('utf-8')).hexdigest()
                    
                    md5_series = filtered_df.apply(calculate_md5, axis=1)

                    # B. 生成 Batch_ID (平均值法)
                    # 逻辑：((Min + Max) / 2) * 100 格式化为6位 + 行号6位
                    avg_val = (min_times + max_times) / 2
                    prefix_int = int(round(avg_val * 100))
                    prefix_str = str(prefix_int).zfill(6)
                    
                    # 生成 ID 列表
                    ids = []
                    WIDTH_INDEX = 6
                    # 重置 index 以便于生成连续流水号，但不改变原始数据顺序
                    for i in range(len(filtered_df)):
                        idx_str = str(i + 1).zfill(WIDTH_INDEX)
                        full_id = f"{prefix_str}{idx_str}"
                        ids.append(full_id)

                    # 插入新列到最前面
                    filtered_df.insert(0, 'Batch_ID', ids)
                    filtered_df