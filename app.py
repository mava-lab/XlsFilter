import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd
import hashlib
import os
import datetime

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v1.2"
BUILD_DATE = "2026-01-12"

class ExcelFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} - {APP_VERSION} ({BUILD_DATE})")
        self.root.geometry("600x550")
        
        # 变量存储
        self.file_path = tk.StringVar()
        self.min_time = tk.StringVar(value="0.0")
        self.max_time = tk.StringVar(value="100.0")
        self.columns_to_keep = tk.StringVar(value="") # 默认为空，表示保留所有
        
        self.create_widgets()

    def create_widgets(self):
        # 1. 文件选择区域
        file_frame = tk.LabelFrame(self.root, text="文件操作", padx=10, pady=10)
        file_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(file_frame, text="选择 Excel 文件", command=self.select_file).grid(row=0, column=0, padx=5)
        tk.Entry(file_frame, textvariable=self.file_path, width=50, state='readonly').grid(row=0, column=1, padx=5)

        # 2. 筛选参数区域
        param_frame = tk.LabelFrame(self.root, text="筛选参数 (Time)", padx=10, pady=10)
        param_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(param_frame, text="最小时间 (Min):").grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(param_frame, textvariable=self.min_time, width=15).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(param_frame, text="最大时间 (Max):").grid(row=0, column=2, padx=5, pady=5)
        tk.Entry(param_frame, textvariable=self.max_time, width=15).grid(row=0, column=3, padx=5, pady=5)

        # 3. 列筛选区域
        col_frame = tk.LabelFrame(self.root, text="高级设置", padx=10, pady=10)
        col_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(col_frame, text="保留列 (用逗号分隔，留空则保留所有):").pack(anchor='w')
        tk.Entry(col_frame, textvariable=self.columns_to_keep, width=60).pack(fill='x', pady=5)
        tk.Label(col_frame, text="* 提示: 程序会自动生成 'Batch_ID' 和 'Row_MD5' 两列", fg="gray").pack(anchor='w')

        # 4. 执行按钮
        action_frame = tk.Frame(self.root, padx=10, pady=10)
        action_frame.pack(fill="x")
        
        btn_process = tk.Button(action_frame, text="开始处理并导出", command=self.process_data, 
                                bg="#007AFF", fg="black", font=("Arial", 11, "bold"), height=2)
        btn_process.pack(fill="x")

        # 5. 日志输出
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill="both", expand=True, padx=10, pady=10)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self.root.update()

    def select_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if filename:
            self.file_path.set(filename)
            self.log(f"已加载文件: {os.path.basename(filename)}")

    def process_data(self):
        # --- 校验输入 ---
        src_file = self.file_path.get()
        if not src_file:
            messagebox.showerror("错误", "请先选择 Excel 文件")
            return

        try:
            t_min = float(self.min_time.get())
            t_max = float(self.max_time.get())
        except ValueError:
            messagebox.showerror("错误", "时间范围必须是数字")
            return

        # --- 开始处理 ---
        self.log("-" * 30)
        self.log(f"开始处理... 范围: {t_min} ~ {t_max}")
        
        try:
            # 1. 读取数据
            df = pd.read_excel(src_file)
            
            # 检查 Time 列
            if 'Time' not in df.columns:
                # 尝试不区分大小写查找
                cols_upper = {c.upper(): c for c in df.columns}
                if 'TIME' in cols_upper:
                    df.rename(columns={cols_upper['TIME']: 'Time'}, inplace=True)
                else:
                    messagebox.showerror("错误", "Excel 中找不到 'Time' 列")
                    return

            # 2. 筛选 Time
            df['Time'] = pd.to_numeric(df['Time'], errors='coerce')
            filtered_df = df[(df['Time'] >= t_min) & (df['Time'] <= t_max)].copy()
            
            if filtered_df.empty:
                self.log("警告: 该筛选范围内没有数据，操作终止。")
                messagebox.showwarning("空结果", "该范围内没有数据")
                return

            self.log(f"筛选完成，剩余行数: {len(filtered_df)}")

            # 3. 列裁剪 (如果用户指定了列)
            user_cols_str = self.columns_to_keep.get().strip()
            if user_cols_str:
                keep_cols = [c.strip() for c in user_cols_str.split(',')]
                # 确保 Time 存在以便核对，或者如果用户没写Time就不保留Time
                # 但为了逻辑稳健，只保留存在的列
                valid_cols = [c for c in keep_cols if c in filtered_df.columns]
                if valid_cols:
                    filtered_df = filtered_df[valid_cols]
                    self.log(f"已保留指定列: {valid_cols}")

            # ========================================================
            # 核心逻辑 A: 生成 MD5 (对当前行所有内容计算)
            # ========================================================
            self.log("正在生成 MD5 指纹...")
            def calculate_md5(row):
                row_str = "".join(row.astype(str).values)
                return hashlib.md5(row_str.encode('utf-8')).hexdigest()

            md5_series = filtered_df.apply(calculate_md5, axis=1)

            # ========================================================
            # 核心逻辑 B: 生成 Batch_ID (平均值法压缩 + 流水号)
            # ========================================================
            self.log("正在生成 12位 Batch ID...")
            
            # 1. 计算前缀: ((Min + Max) / 2) * 100
            avg_val = (t_min + t_max) / 2
            prefix_int = int(round(avg_val * 100))
            # 格式化为 6位 (最大支持 1000.00 -> 100000)
            prefix_str = str(prefix_int).zfill(6)
            
            # 2. 生成 ID 序列
            # 行流水号: 6位 (支持 999,999 行)
            WIDTH_INDEX = 6
            ids = []
            
            # 重置索引以保证从 0 开始遍历，但这不影响原始数据顺序
            # 实际上直接使用 range(len) 即可
            for i in range(len(filtered_df)):
                idx_str = str(i + 1).zfill(WIDTH_INDEX)
                full_id = f"{prefix_str}{idx_str}"
                ids.append(full_id)

            # ========================================================
            # 4. 插入新列 & 导出
            # ========================================================
            # 插入到最前面
            filtered_df.insert(0, 'Batch_ID', ids)
            filtered_df.insert(1, 'Row_MD5', md5_series)

            # 弹出保存对话框
            default_out = f"Filtered_{t_min}_{t_max}.xlsx"
            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                                     initialfile=default_out,
                                                     filetypes=[("Excel Files", "*.xlsx")])
            
            if save_path:
                filtered_df.to_excel(save_path, index=False)
                self.log(f"成功保存至: {save_path}")
                messagebox.showinfo("成功", f"处理完成！\n已生成: {os.path.basename(save_path)}")
            else:
                self.log("用户取消保存。")

        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            messagebox.showerror("运行错误", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = ExcelFilterApp(root)
    root.mainloop()