import streamlit as st
import pandas as pd
import io
import hashlib
import zipfile

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v2.3 (Default Rules)"
BUILD_DATE = "2026-01-12"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", layout="wide")
st.title(f"📊 {APP_TITLE} (工作流增强版)")
st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")

# ==========================================
# 0. Session State 初始化 (预置 5 组规则)
# ==========================================
if 'filter_rules' not in st.session_state:
    # 这里根据你的需求预设了 5 组常用条件
    # 逻辑：Min < x <= Max (Min设为-1以包含0)
    st.session_state.filter_rules = [
        # 1. Times 0 (0.0)
        {"id": 1, "min_t": -1.0, "max_t": 0.0, "min_l": -1, "max_l": 30},
        # 2. Times 0~1
        {"id": 2, "min_t": 0.0, "max_t": 1.0, "min_l": -1, "max_l": 30},
        # 3. Times 1~10
        {"id": 3, "min_t": 1.0, "max_t": 10.0, "min_l": -1, "max_l": 30},
        # 4. Times 10~100
        {"id": 4, "min_t": 10.0, "max_t": 100.0, "min_l": -1, "max_l": 30},
        # 5. Times 100~9999
        {"id": 5, "min_t": 100.0, "max_t": 9999.0, "min_l": -1, "max_l": 30},
    ]

def add_rule():
    new_id = len(st.session_state.filter_rules) + 1
    last_rule = st.session_state.filter_rules[-1]
    # 新增规则默认承接上一条的 max，Launcher 保持 0-30
    st.session_state.filter_rules.append(
        {"id": new_id, "min_t": last_rule['max_t'], "max_t": last_rule['max_t'] + 10.0, 
         "min_l": -1, "max_l": 30}
    )

def remove_rule():
    if len(st.session_state.filter_rules) > 1:
        st.session_state.filter_rules.pop()

# ==========================================
# 1. 侧边栏：批量筛选配置
# ==========================================
st.sidebar.header("1. 批量筛选配置")
st.sidebar.info("💡 默认已加载 5 组常用筛选条件。\n区间逻辑：左开右闭 (Min < x ≤ Max)。")

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("➕ 增加拆分规则", on_click=add_rule, type="primary")
col_btn2.button("➖ 删除最后一条", on_click=remove_rule)

st.sidebar.markdown("---")

# 动态渲染规则
for i, rule in enumerate(st.session_state.filter_rules):
    idx = i + 1
    with st.sidebar.expander(f"📂 任务 {idx} (Times: {rule['min_t']}~{rule['max_t']})", expanded=False): 
        # 默认折叠 expanded=False 避免侧边栏太长，你可以按需展开
        st.markdown(f"**区间逻辑：({rule['min_t']} < Times ≤ {rule['max_t']}]**")
        
        c1, c2 = st.columns(2)
        rule['min_t'] = c1.number_input(f"Times > (Min)", value=float(rule['min_t']), step=0.1, key=f"t_min_{idx}")
        rule['max_t'] = c2.number_input(f"Times ≤ (Max)", value=float(rule['max_t']), step=0.1, key=f"t_max_{idx}")
        
        c3, c4 = st.columns(2)
        rule['min_l'] = c3.number_input(f"Launch > (Min)", value=int(rule['min_l']), step=1, key=f"l_min_{idx}")
        rule['max_l'] = c4.number_input(f"Launch ≤ (Max)", value=int(rule['max_l']), step=1, key=f"l_max_{idx}")

# ==========================================
# 2. 核心逻辑：读取与处理
# ==========================================
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
        cols_to_drop = [c for c in df.columns if 'Unnamed' in c or c == '']
        if cols_to_drop: df.drop(columns=cols_to_drop, inplace=True)
            
    return df

@st.cache_data(show_spinner=False) 
def load_and_merge_files(files):
    """读取合并文件"""
    all_dfs = []
    for file in files:
        file.seek(0)
        df = super_reader(file)
        if df is not None and not df.empty:
            try:
                if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                    df['Times'] = (df['Amount'] + 10000) / 10000
                    all_dfs.append(df)
            except:
                continue     
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()

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
    with st.spinner("正在读取或从缓存加载数据..."):
        master_df = load_and_merge_files(uploaded_files)

    if not master_df.empty:
        # --- 统计面板 ---
        st.markdown("### 📈 数据全貌统计")
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        c2.metric("✖️ Times 范围", f"{master_df['Times'].min():.2f} ~ {master_df['Times'].max():.2f}")
        c3.metric("🚀 LauncherNum 范围", f"{master_df['LauncherNum'].min()} ~ {master_df['LauncherNum'].max()}")
        st.divider()

        # --- 批量处理逻辑 ---
        st.markdown(f"### 🚀 批量拆分处理 (共 {len(st.session_state.filter_rules)} 个任务)")
        
        if st.button("👉 开始批量拆分并打包下载", type="primary"):
            
            results_buffer = io.BytesIO()
            processed_logs = []
            total_files_generated = 0

            with zipfile.ZipFile(results_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                progress_bar = st.progress(0)
                
                for i, rule in enumerate(st.session_state.filter_rules):
                    idx = i + 1
                    t_min, t_max = rule['min_t'], rule['max_t']
                    l_min, l_max = rule['min_l'], rule['max_l']
                    
                    # 1. 筛选
                    filtered_df = master_df[
                        (master_df['Times'] > t_min) & 
                        (master_df['Times'] <= t_max) & 
                        (master_df['LauncherNum'] > l_min) & 
                        (master_df['LauncherNum'] <= l_max)
                    ].copy()
                    
                    # 文件名优化：显示 Times 范围
                    file_name = f"File{idx}_Times_{t_min}-{t_max}.csv"
                    
                    if not filtered_df.empty:
                        # 2. 生成 MD5
                        filtered_df['Row_MD5'] = filtered_df.apply(
                            lambda row: hashlib.md5("".join(row.astype(str).values).encode('utf-8')).hexdigest(), axis=1
                        )

                        # 3. 生成 Batch_ID (智能平均值逻辑)
                        real_data_mean = filtered_df['Times'].mean()
                        prefix_str = str(int(round(real_data_mean * 100))).zfill(6)
                        
                        WIDTH_INDEX = 6
                        filtered_df['Batch_ID'] = [f"{prefix_str}{str(k+1).zfill(WIDTH_INDEX)}" for k in range(len(filtered_df))]

                        # 4. 列重排
                        cols = list(filtered_df.columns)
                        priority = ['Batch_ID', 'Row_MD5']
                        others = [c for c in cols if c not in priority]
                        if 'Times' in others and 'Amount' in others:
                            others.remove('Times')
                            others.insert(others.index('Amount') + 1, 'Times')
                        
                        final_df = filtered_df[priority + others]
                        
                        # 5. 写入 ZIP
                        csv_data = final_df.to_csv(index=False).encode('utf-8-sig')
                        zf.writestr(file_name, csv_data)
                        
                        processed_logs.append({
                            "任务": f"任务 {idx}",
                            "文件名": file_name, 
                            "状态": "✅ 成功", 
                            "行数": len(final_df),
                            "ID前缀": prefix_str
                        })
                        total_files_generated += 1
                    else:
                        processed_logs.append({
                            "任务": f"任务 {idx}",
                            "文件名": file_name, 
                            "状态": "⚠️ 跳过 (无数据)", 
                            "行数": 0, 
                            "ID前缀": "-"
                        })
                    
                    progress_bar.progress((i + 1) / len(st.session_state.filter_rules))

            # 结果展示
            if total_files_generated > 0:
                st.success(f"🎉 处理完成！共生成 {total_files_generated} 个文件。")
                st.table(pd.DataFrame(processed_logs))
                
                st.download_button(
                    label="📦 点击下载所有文件 (ZIP)",
                    data=results_buffer.getvalue(),
                    file_name=f"Batch_Processed_{BUILD_DATE}.zip",
                    mime="application/zip"
                )
            else:
                st.error("所有筛选结果为空。")
                st.table(pd.DataFrame(processed_logs))

    else:
        st.error("未能读取到有效数据。")
else:
    st.info("👈 请上传文件。")