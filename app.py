import streamlit as st
import pandas as pd
import io
import hashlib

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v1.4 (Performance)"
BUILD_DATE = "2026-01-12"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", layout="wide")
st.title(f"📊 {APP_TITLE} (极速缓存版)")
st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")

# ==========================================
# 1. 侧边栏：设置筛选条件
# ==========================================
st.sidebar.header("1. 设置筛选条件")

st.sidebar.subheader("Times (倍数) 范围")
min_times = st.sidebar.number_input("Times 最小值", value=0.0, step=0.1, format="%.2f")
max_times = st.sidebar.number_input("Times 最大值", value=1000.0, step=0.1, format="%.2f")

st.sidebar.subheader("LauncherNum (发射数) 范围")
min_launcher = st.sidebar.number_input("LauncherNum 最小值", value=0)
max_launcher = st.sidebar.number_input("LauncherNum 最大值", value=100)

# ==========================================
# 2. 核心逻辑：读取与处理 (带缓存)
# ==========================================

# 辅助读取函数 (不需要缓存，它是被调用的)
def super_reader(file):
    """底层读取逻辑"""
    df = None
    try:
        all_sheets = pd.read_excel(file, sheet_name=None)
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                df = sheet_df
    except:
        pass
    
    if df is None:
        methods = [(pd.read_csv, {}), (pd.read_csv, {'encoding': 'utf-8'}), 
                   (pd.read_csv, {'encoding': 'gbk'}), (pd.read_csv, {'on_bad_lines': 'skip'})]
        for reader, kwargs in methods:
            file.seek(0)
            try:
                temp_df = reader(file, **kwargs)
                if not temp_df.empty: 
                    df = temp_df
                    break
            except: continue

    if df is not None and not df.empty:
        df.columns = df.columns.astype(str).str.strip()
        cols_to_drop = [c for c in df.columns if 'Unnamed' in c]
        if cols_to_drop: df.drop(columns=cols_to_drop, inplace=True)
            
    return df

# 【核心优化】使用 st.cache_data 缓存这个耗时函数
# 只有当 uploaded_files 内容发生变化时，这个函数才会真正执行
@st.cache_data(show_spinner=False) 
def load_and_merge_files(files):
    all_dfs = []
    
    for file in files:
        # 因为缓存机制，这里需要重置文件指针
        file.seek(0)
        df = super_reader(file)
        
        if df is not None and not df.empty:
            try:
                if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                    # 预处理计算必须放在缓存函数里，这样计算一次就够了
                    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                    df['Times'] = (df['Amount'] + 10000) / 10000
                    all_dfs.append(df)
            except:
                continue
                
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame() # 返回空表

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件", 
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    # 这一步现在非常快！只要文件没变，直接从内存拿结果
    with st.spinner("正在读取或从缓存加载数据..."):
        master_df = load_and_merge_files(uploaded_files)

    if not master_df.empty:
        # --- 统计面板 (每次调整筛选框，这里瞬间刷新) ---
        st.markdown("### 📈 数据全貌统计")
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        c2.metric("✖️ Times 范围", f"{master_df['Times'].min():.2f} ~ {master_df['Times'].max():.2f}")
        c3.metric("🚀 LauncherNum 范围", f"{master_df['LauncherNum'].min()} ~ {master_df['LauncherNum'].max()}")
        st.divider()

        # --- 筛选与生成 (保持原有逻辑) ---
        st.markdown("### 🔍 数据筛选与生成")
        
        if st.button("👉 按左侧条件开始筛选并导出", type="primary"):
            
            # 这里的筛选也是基于缓存好的 master_df 进行的，速度极快
            filtered_df = master_df[
                (master_df['Times'] >= min_times) & 
                (master_df['Times'] <= max_times) & 
                (master_df['LauncherNum'] >= min_launcher) & 
                (master_df['LauncherNum'] <= max_launcher)
            ].copy()
            
            if not filtered_df.empty:
                with st.spinner('正在生成 MD5 和 Batch ID...'):
                    # MD5
                    def calculate_md5(row):
                        row_str = "".join(row.astype(str).values)
                        return hashlib.md5(row_str.encode('utf-8')).hexdigest()
                    filtered_df['Row_MD5'] = filtered_df.apply(calculate_md5, axis=1)

                    # ID
                    avg_val = (min_times + max_times) / 2
                    prefix_str = str(int(round(avg_val * 100))).zfill(6)
                    WIDTH_INDEX = 6
                    # 列表推导式比循环更快
                    filtered_df['Batch_ID'] = [f"{prefix_str}{str(i+1).zfill(WIDTH_INDEX)}" for i in range(len(filtered_df))]

                    # 排序
                    all_cols = list(filtered_df.columns)
                    priority = ['Batch_ID', 'Row_MD5']
                    others = [c for c in all_cols if c not in priority]
                    if 'Times' in others and 'Amount' in others:
                        others.remove('Times')
                        others.insert(others.index('Amount') + 1, 'Times')
                    filtered_df = filtered_df[priority + others]

                # 展示与下载
                st.success(f"✅ 完成！生成 {len(filtered_df)} 行。")
                st.dataframe(filtered_df.head(100), height=400)
                st.download_button(
                    "📥 下载结果 (CSV)",
                    filtered_df.to_csv(index=False).encode('utf-8-sig'),
                    f"Filtered_{min_times}_{max_times}.csv",
                    "text/csv"
                )
            else:
                st.warning("⚠️ 筛选结果为空。")
    else:
        st.error("未能读取到有效数据。")
else:
    st.info("👈 请上传文件。")