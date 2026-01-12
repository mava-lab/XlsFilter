import streamlit as st
import pandas as pd
import io
import hashlib
import zipfile
import gc  # 引入垃圾回收机制，强制释放内存

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v3.0 (Memory Safe)"
BUILD_DATE = "2026-01-12"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", layout="wide")
st.title(f"📊 {APP_TITLE} (大文件防崩溃版)")
st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")
st.info("💡 此版本采用**流式处理**技术：文件逐个读取、处理并释放内存，不再合并大表。适合处理数百兆甚至 GB 级数据。")

# ==========================================
# 0. Session State 初始化 (默认 5 组规则)
# ==========================================
if 'filter_rules' not in st.session_state:
    st.session_state.filter_rules = [
        {"id": 1, "min_t": -1.0, "max_t": 0.0, "min_l": -1, "max_l": 30},
        {"id": 2, "min_t": 0.0, "max_t": 1.0, "min_l": -1, "max_l": 30},
        {"id": 3, "min_t": 1.0, "max_t": 10.0, "min_l": -1, "max_l": 30},
        {"id": 4, "min_t": 10.0, "max_t": 100.0, "min_l": -1, "max_l": 30},
        {"id": 5, "min_t": 100.0, "max_t": 9999.0, "min_l": -1, "max_l": 30},
    ]

def add_rule():
    new_id = len(st.session_state.filter_rules) + 1
    last_rule = st.session_state.filter_rules[-1]
    st.session_state.filter_rules.append(
        {"id": new_id, "min_t": last_rule['max_t'], "max_t": last_rule['max_t'] + 10.0, 
         "min_l": -1, "max_l": 30}
    )

def remove_rule():
    if len(st.session_state.filter_rules) > 1:
        st.session_state.filter_rules.pop()

# ==========================================
# 1. 侧边栏配置
# ==========================================
st.sidebar.header("1. 批量筛选配置")
col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("➕ 增加拆分规则", on_click=add_rule, type="primary")
col_btn2.button("➖ 删除最后一条", on_click=remove_rule)
st.sidebar.markdown("---")

for i, rule in enumerate(st.session_state.filter_rules):
    idx = i + 1
    with st.sidebar.expander(f"📂 任务 {idx} (Times: {rule['min_t']}~{rule['max_t']})", expanded=False): 
        st.markdown(f"**区间: ({rule['min_t']} < Times ≤ {rule['max_t']}]**")
        c1, c2 = st.columns(2)
        rule['min_t'] = c1.number_input(f"Times Min", value=float(rule['min_t']), step=0.1, key=f"t_min_{idx}")
        rule['max_t'] = c2.number_input(f"Times Max", value=float(rule['max_t']), step=0.1, key=f"t_max_{idx}")
        c3, c4 = st.columns(2)
        rule['min_l'] = c3.number_input(f"Launch Min", value=int(rule['min_l']), step=1, key=f"l_min_{idx}")
        rule['max_l'] = c4.number_input(f"Launch Max", value=int(rule['max_l']), step=1, key=f"l_max_{idx}")

# ==========================================
# 2. 核心逻辑：单文件读取 (不缓存，省内存)
# ==========================================
def read_single_file(file):
    """读取单个文件，清洗列名，计算Times，然后返回DF"""
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
        methods = [(pd.read_csv, {}), (pd.read_csv, {'encoding': 'utf-8'}), (pd.read_csv, {'encoding': 'gbk'}), (pd.read_csv, {'on_bad_lines': 'skip'})]
        for reader, kwargs in methods:
            file.seek(0)
            try:
                temp_df = reader(file, **kwargs)
                if not temp_df.empty: 
                    df = temp_df
                    break
            except: continue

    if df is not None and not df.empty:
        # 清洗
        df.columns = df.columns.astype(str).str.strip()
        cols_to_drop = [c for c in df.columns if 'Unnamed' in c or c == '']
        if cols_to_drop: df.drop(columns=cols_to_drop, inplace=True)
        
        # 计算 Times
        if 'Amount' in df.columns:
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
            df['Times'] = (df['Amount'] + 10000) / 10000
        else:
            return None # 缺少关键列
            
    return df

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.header("2. 上传数据文件")
# 注意：这里我们增加了 file_uploader 的提示，建议用户修改 config 允许大文件
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件 (支持多文件，建议总大小 < 500MB)", 
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"已接收 {len(uploaded_files)} 个文件。准备就绪。")
    
    # 移除原本的“预读取”统计步骤，因为这会消耗大量内存
    # 直接进入处理环节
    
    if st.button("👉 开始流式处理并打包 (Memory Safe)", type="primary"):
        
        # 结果容器：我们用一个字典来暂存每个规则筛选出的数据片段
        # key = rule_id, value = list of dataframes
        rule_results = {rule['id']: [] for rule in st.session_state.filter_rules}
        
        # 进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_files = len(uploaded_files)
        
        # === 核心循环：文件逐个处理 ===
        for i, file in enumerate(uploaded_files):
            status_text.text(f"正在处理第 {i+1}/{total_files} 个文件: {file.name} ...")
            
            # 1. 读入内存
            current_df = read_single_file(file)
            
            if current_df is not None and not current_df.empty and 'LauncherNum' in current_df.columns:
                
                # 2. 遍历所有规则，对当前这个文件进行“切分”
                for rule in st.session_state.filter_rules:
                    t_min, t_max = rule['min_t'], rule['max_t']
                    l_min, l_max = rule['min_l'], rule['max_l']
                    
                    # 筛选片段
                    subset = current_df[
                        (current_df['Times'] > t_min) & 
                        (current_df['Times'] <= t_max) & 
                        (current_df['LauncherNum'] > l_min) & 
                        (current_df['LauncherNum'] <= l_max)
                    ].copy()
                    
                    if not subset.empty:
                        # 将片段存入对应规则的列表中
                        rule_results[rule['id']].append(subset)
            
            # 3. 【关键】释放内存
            del current_df
            gc.collect() # 强制通知 Python 回收内存
            
            progress_bar.progress((i + 1) / total_files)

        status_text.text("文件遍历完成，正在合并结果并生成 ID...")
        
        # === 合并结果并生成 ZIP ===
        results_buffer = io.BytesIO()
        processed_logs = []
        files_count = 0
        
        with zipfile.ZipFile(results_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            
            # 遍历每个规则的收集结果
            for i, rule in enumerate(st.session_state.filter_rules):
                rule_id = rule['id']
                df_list = rule_results[rule_id]
                
                # 文件名
                file_name = f"File{i+1}_Times_{rule['min_t']}-{rule['max_t']}.csv"
                
                if df_list:
                    # 合并该规则下的所有碎片
                    final_df = pd.concat(df_list, ignore_index=True)
                    
                    # --- 生成列逻辑 (与之前一致) ---
                    # MD5
                    final_df['Row_MD5'] = final_df.apply(
                        lambda row: hashlib.md5("".join(row.astype(str).values).encode('utf-8')).hexdigest(), axis=1
                    )
                    
                    # Batch_ID (智能均值)
                    real_mean = final_df['Times'].mean()
                    prefix = str(int(round(real_mean * 100))).zfill(6)
                    final_df['Batch_ID'] = [f"{prefix}{str(k+1).zfill(6)}" for k in range(len(final_df))]
                    
                    # 排序
                    cols = list(final_df.columns)
                    prio = ['Batch_ID', 'Row_MD5']
                    others = [c for c in cols if c not in prio]
                    if 'Times' in others and 'Amount' in others:
                        others.remove('Times')
                        others.insert(others.index('Amount')+1, 'Times')
                    final_df = final_df[prio + others]
                    
                    # 写入 ZIP
                    zf.writestr(file_name, final_df.to_csv(index=False).encode('utf-8-sig'))
                    
                    processed_logs.append({
                        "任务": f"任务 {i+1}", 
                        "文件名": file_name, 
                        "状态": "✅ 成功", 
                        "行数": len(final_df),
                        "ID前缀": prefix
                    })
                    files_count += 1
                    
                    # 再次释放内存
                    del final_df
                    del df_list
                    gc.collect()
                else:
                    processed_logs.append({
                        "任务": f"任务 {i+1}", 
                        "文件名": file_name, 
                        "状态": "⚠️ 无数据", 
                        "行数": 0,
                        "ID前缀": "-"
                    })

        st.success("全部处理完成！")
        st.table(pd.DataFrame(processed_logs))
        
        if files_count > 0:
            st.download_button(
                label="📦 下载所有结果 (ZIP)",
                data=results_buffer.getvalue(),
                file_name=f"Batch_Results_{BUILD_DATE}.zip",
                mime="application/zip"
            )

else:
    st.info("👈 请上传文件。建议单个文件不要超过 200MB。")