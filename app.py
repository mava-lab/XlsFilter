import streamlit as st
import pandas as pd
import hashlib
import io

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具 (Web版)"
APP_VERSION = "v1.2"
BUILD_DATE = "2026-01-12"

# 设置页面标题
st.set_page_config(page_title=APP_TITLE, layout="centered")

def generate_excel_bytes(df):
    """将 DataFrame 转换为内存中的 Excel 字节流，用于下载"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def main():
    st.title(f"🛠 {APP_TITLE}")
    st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")
    st.markdown("---")

    # 1. 侧边栏：文件上传
    st.sidebar.header("1. 上传文件")
    uploaded_file = st.sidebar.file_uploader("选择 Excel 文件 (.xlsx)", type=['xlsx', 'xls'])

    # 2. 侧边栏：参数设置
    st.sidebar.header("2. 筛选参数 (Time)")
    # 使用 number_input 可以更精确控制数字
    min_time = st.sidebar.number_input("最小时间 (Min)", value=0.0, step=0.1, format="%.2f")
    max_time = st.sidebar.number_input("最大时间 (Max)", value=100.0, step=0.1, format="%.2f")

    # 3. 主界面逻辑
    if uploaded_file is not None:
        st.info(f"正在处理文件: {uploaded_file.name}")
        
        try:
            # 读取 Excel
            df = pd.read_excel(uploaded_file)
            
            # 检查 Time 列
            # 尝试自动兼容大小写
            cols_map = {c.upper(): c for c in df.columns}
            if 'TIME' not in cols_map:
                st.error("❌ 错误：Excel 中找不到 'Time' 列，请检查表头。")
                return
            
            time_col_real_name = cols_map['TIME']
            
            # 转换数据类型
            df[time_col_real_name] = pd.to_numeric(df[time_col_real_name], errors='coerce')
            
            # 执行筛选
            filtered_df = df[(df[time_col_real_name] >= min_time) & (df[time_col_real_name] <= max_time)].copy()
            
            if filtered_df.empty:
                st.warning("⚠️ 警告：在该时间范围内没有筛选到任何数据。")
            else:
                st.success(f"✅ 筛选成功！剩余行数: {len(filtered_df)}")
                
                # ==========================================
                # 核心逻辑 A: 生成 MD5 (全字段)
                # ==========================================
                def calculate_md5(row):
                    row_str = "".join(row.astype(str).values)
                    return hashlib.md5(row_str.encode('utf-8')).hexdigest()

                with st.spinner('正在生成 MD5 指纹...'):
                    md5_series = filtered_df.apply(calculate_md5, axis=1)

                # ==========================================
                # 核心逻辑 B: 生成 Batch_ID (平均值法 + 流水号)
                # ==========================================
                with st.spinner('正在生成 12位 Batch ID...'):
                    # 1. 计算前缀: ((Min + Max) / 2) * 100
                    avg_val = (min_time + max_time) / 2
                    prefix_int = int(round(avg_val * 100))
                    prefix_str = str(prefix_int).zfill(6)
                    
                    # 2. 生成 ID 序列
                    WIDTH_INDEX = 6
                    ids = []
                    for i in range(len(filtered_df)):
                        idx_str = str(i + 1).zfill(WIDTH_INDEX)
                        full_id = f"{prefix_str}{idx_str}"
                        ids.append(full_id)

                # 插入列 (插在最前面)
                filtered_df.insert(0, 'Batch_ID', ids)
                filtered_df.insert(1, 'Row_MD5', md5_series)

                # ==========================================
                # 结果展示与下载
                # ==========================================
                st.subheader("📊 结果预览 (前 10 行)")
                st.dataframe(filtered_df.head(10))
                
                # 生成下载按钮
                excel_data = generate_excel_bytes(filtered_df)
                
                file_name_default = f"Filtered_{min_time}_{max_time}.xlsx"
                
                st.download_button(
                    label="📥 下载处理后的 Excel",
                    data=excel_data,
                    file_name=file_name_default,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"发生错误: {str(e)}")
    else:
        st.write("👈 请在左侧上传 Excel 文件以开始。")

if __name__ == "__main__":
    main()