import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import asyncio
import threading
from pathlib import Path
import json
import os
import sys
from pandastable import Table, TableModel

# 導入所需的模組
from main import process_wrapper, model_prompt_mapping, PDF_DIR


class FinancialReportParserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("財務報告解析器")
        self.root.geometry("900x700")  # 增加整體視窗大小
        self.root.minsize(900, 700)  # 增加最小視窗大小

        self.pdf_path = None
        self.selected_models = []
        self.results = {}
        self.current_df = None  # 儲存當前的DataFrame以供匯出使用

        # 檢查是否有安裝 pandastable
        try:
            import pandastable

            self.has_pandastable = True
        except ImportError:
            self.has_pandastable = False

        self.create_widgets()

        # 如果沒有 pandastable，顯示提示
        if not self.has_pandastable:
            messagebox.showinfo(
                "提示",
                "若要獲得更好的表格顯示效果，建議安裝 pandastable 庫:\n\n"
                "pip install pandastable\n\n"
                "安裝後重啟應用程式即可生效。",
            )

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 頂部區域 - 檔案選擇
        file_frame = ttk.LabelFrame(main_frame, text="PDF文件選擇", padding=10)
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        self.file_label = ttk.Label(file_frame, text="尚未選擇檔案")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.browse_button = ttk.Button(
            file_frame, text="瀏覽...", command=self.browse_file
        )
        self.browse_button.pack(side=tk.RIGHT, padx=5)

        # 使用PanedWindow來允許用戶調整區域大小
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 上半部分框架 - 包含模型選擇和狀態
        top_frame = ttk.Frame(paned)
        paned.add(top_frame, weight=30)  # 給上半部分30%的權重

        # 中間區域 - 模型選擇
        models_frame = ttk.LabelFrame(top_frame, text="選擇要使用的模型", padding=10)
        models_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 建立模型選擇的Checkbutton
        self.model_vars = {}
        model_frame_inner = ttk.Frame(models_frame)
        model_frame_inner.pack(fill=tk.BOTH, expand=True)

        for i, model_name in enumerate(model_prompt_mapping.keys()):
            var = tk.BooleanVar(value=True)  # 預設全選
            self.model_vars[model_name] = var

            friendly_name = model_name.replace("_", " ").title()
            cb = ttk.Checkbutton(model_frame_inner, text=friendly_name, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky=tk.W, padx=10, pady=5)

        # 底部區域 - 按鈕和狀態
        button_frame = ttk.Frame(top_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        self.process_button = ttk.Button(
            button_frame, text="開始處理", command=self.process_file, state=tk.DISABLED
        )
        self.process_button.pack(side=tk.RIGHT, padx=5)

        # 添加匯出Excel按鈕
        self.export_excel_button = ttk.Button(
            button_frame,
            text="匯出Excel",
            command=self.export_to_excel,
            state=tk.DISABLED,
        )
        self.export_excel_button.pack(side=tk.RIGHT, padx=5)

        # 狀態顯示
        status_frame = ttk.LabelFrame(top_frame, text="處理狀態", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        status_scroll = ttk.Scrollbar(status_frame)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_text = tk.Text(
            status_frame,
            height=6,
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=status_scroll.set,
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        status_scroll.config(command=self.status_text.yview)

        # 底部框架 - 結果顯示 (增加高度)
        bottom_frame = ttk.Frame(paned)
        paned.add(bottom_frame, weight=70)  # 給底部70%的權重

        # 結果區域
        self.results_frame = ttk.LabelFrame(bottom_frame, text="處理結果", padding=10)
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建一個框架來顯示結果，可以動態替換為文本或表格
        self.result_display_frame = ttk.Frame(self.results_frame)
        self.result_display_frame.pack(fill=tk.BOTH, expand=True)

        # 初始化文本顯示區域
        self.setup_text_display()

    def export_to_excel(self):
        """匯出當前DataFrame到Excel檔案"""
        if self.current_df is None or len(self.current_df) == 0:
            messagebox.showinfo("提示", "沒有可匯出的數據")
            return

        try:
            # 請求用戶選擇保存位置
            file_path = filedialog.asksaveasfilename(
                title="保存Excel檔案",
                defaultextension=".xlsx",
                filetypes=[("Excel檔案", "*.xlsx"), ("所有檔案", "*.*")],
            )

            if not file_path:  # 用戶取消了選擇
                return

            # 確保擴展名是.xlsx
            if not file_path.endswith(".xlsx"):
                file_path += ".xlsx"

            # 匯出到Excel
            self.log(f"正在匯出數據到Excel: {file_path}")

            # 檢查pandas是否已導入，否則導入
            import pandas as pd

            # 檢查是否安裝了openpyxl
            try:
                import openpyxl

                self.current_df.to_excel(file_path, index=False, engine="openpyxl")
                self.log(f"數據已成功匯出到: {file_path}")
                messagebox.showinfo("匯出成功", f"數據已成功匯出到:\n{file_path}")
            except ImportError:
                self.log("缺少openpyxl模組，嘗試使用xlsxwriter...")
                try:
                    import xlsxwriter

                    self.current_df.to_excel(
                        file_path, index=False, engine="xlsxwriter"
                    )
                    self.log(f"數據已成功匯出到: {file_path}")
                    messagebox.showinfo("匯出成功", f"數據已成功匯出到:\n{file_path}")
                except ImportError:
                    error_msg = "匯出Excel需要安裝openpyxl或xlsxwriter模組。\n請運行以下命令安裝:\npip install openpyxl"
                    self.log(error_msg)
                    messagebox.showerror("錯誤", error_msg)
        except Exception as e:
            error_msg = f"匯出Excel時發生錯誤: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("錯誤", error_msg)

    def setup_text_display(self):
        """設置文本顯示區域"""
        # 清除當前的顯示框架
        for widget in self.result_display_frame.winfo_children():
            widget.destroy()

        # 創建垂直捲軸
        result_scroll = ttk.Scrollbar(self.result_display_frame, orient="vertical")
        result_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 水平捲軸
        h_scroll = ttk.Scrollbar(self.result_display_frame, orient="horizontal")
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # 文本顯示區域
        self.result_text = tk.Text(
            self.result_display_frame,
            wrap=tk.NONE,  # 禁用自動換行，以便正確顯示長JSON
            state=tk.DISABLED,
            yscrollcommand=result_scroll.set,
            xscrollcommand=h_scroll.set,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        result_scroll.config(command=self.result_text.yview)
        h_scroll.config(command=self.result_text.xview)

        # 設置等寬字體，讓格式化顯示更清晰
        self.result_text.configure(font=("Consolas", 10))

    def setup_table_display(self, dataframe):
        """設置表格顯示區域"""
        # 清除當前的顯示框架
        for widget in self.result_display_frame.winfo_children():
            widget.destroy()

        # 如果已知沒有 pandastable，直接返回 False
        if hasattr(self, "has_pandastable") and not self.has_pandastable:
            self.log("pandastable 庫未安裝，使用傳統顯示方式")
            return False

        try:
            # 嘗試導入 pandastable
            from pandastable import Table, TableModel

            # 確保使用中文列標題顯示
            display_df = dataframe.copy()

            # 創建一個 Frame 來包含 pandastable
            table_frame = ttk.Frame(self.result_display_frame)
            table_frame.pack(fill=tk.BOTH, expand=True)

            # 創建表格並顯示 DataFrame
            pt = Table(
                table_frame, dataframe=display_df, showtoolbar=True, showstatusbar=True
            )
            pt.show()

            # 自定義表格樣式
            pt.autoResizeColumns()
            pt.setTheme("default")

            self.log("使用 pandastable 顯示表格")
            # 設置標記表示已成功載入 pandastable
            self.has_pandastable = True
            return True
        except Exception as e:
            self.log(f"pandastable 初始化失敗: {str(e)}")
            # 標記為沒有可用的 pandastable
            self.has_pandastable = False
            return False

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="選擇PDF檔案", filetypes=[("PDF檔案", "*.pdf"), ("所有檔案", "*.*")]
        )

        if file_path:
            self.pdf_path = Path(file_path)
            self.file_label.config(text=f"已選擇: {self.pdf_path.name}")
            self.process_button.config(state=tk.NORMAL)
            self.log(f"已選擇檔案: {self.pdf_path}")

    def log(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def process_file(self):
        if not self.pdf_path:
            messagebox.showerror("錯誤", "請先選擇一個PDF檔案")
            return

        # 獲取選擇的模型
        self.selected_models = [
            model_name for model_name, var in self.model_vars.items() if var.get()
        ]

        if not self.selected_models:
            messagebox.showerror("錯誤", "請至少選擇一個模型")
            return

        # 禁用處理按鈕避免重複點擊
        self.process_button.config(state=tk.DISABLED)
        # 禁用匯出按鈕直到處理完成
        self.export_excel_button.config(state=tk.DISABLED)

        # 確保PDF存放目錄存在
        PDF_DIR.mkdir(parents=True, exist_ok=True)

        # 複製檔案到指定目錄
        target_path = PDF_DIR / self.pdf_path.name

        # 避免路徑相同時出錯
        if str(target_path) != str(self.pdf_path):
            import shutil

            shutil.copy2(self.pdf_path, target_path)
            self.log(f"已複製檔案到: {target_path}")

        # 清空結果顯示
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)

        # 在新線程中運行處理任務
        self.log("開始處理檔案...")
        threading.Thread(target=self.run_processing, daemon=True).start()

    def run_processing(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 始終需要financial_report模型來確定頁面
            if "financial_report" not in self.selected_models:
                self.selected_models.insert(0, "financial_report")
                self.log("自動添加 financial_report 模型以確定頁面位置")

            results = loop.run_until_complete(self.process_models())
            loop.close()

            # 顯示結果
            self.display_results(results)

            self.log("處理完成")
            self.process_button.config(state=tk.NORMAL)

        except Exception as e:
            self.log(f"處理時發生錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"處理時發生錯誤:\n{str(e)}")
            self.process_button.config(state=tk.NORMAL)

    async def process_models(self):
        filename = self.pdf_path.name
        results = {}

        for model_name in self.selected_models:
            if model_name not in model_prompt_mapping:
                self.log(f"跳過未知模型: {model_name}")
                continue

            self.log(f"處理模型: {model_name}")
            try:
                if model_name == "financial_report":
                    filename, all_results, err = await process_wrapper(
                        filename, model_name
                    )
                    if err:
                        self.log(f"處理 {model_name} 時出錯: {err}")
                    else:
                        # 只保留所選的模型結果
                        for selected_model in self.selected_models:
                            if selected_model in all_results:
                                results[selected_model] = all_results[selected_model]
                else:
                    # 其他模型的處理已包含在 process_wrapper 中
                    pass
            except Exception as e:
                self.log(f"處理 {model_name} 時出錯: {str(e)}")

        return results

    def display_results(self, results):
        if not results:
            self.log("沒有獲得任何結果")
            return

        # 保存原始結果到文件（如果可能）
        try:
            # 嘗試將結果轉換為JSON格式
            json_results = {}
            for model_name, model_result in results.items():
                if hasattr(model_result, "model_dump"):  # Pydantic v2
                    json_results[model_name] = model_result.model_dump()
                elif hasattr(model_result, "dict"):  # Pydantic v1
                    json_results[model_name] = model_result.dict()
                else:
                    # 如果不是BaseModel實例，則嘗試直接使用
                    json_results[model_name] = model_result

            output_path = Path("gui_results.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(json_results, f, ensure_ascii=False, indent=4)
            self.log(f"原始結果已保存到: {output_path.absolute()}")
        except Exception as e:
            self.log(f"保存原始結果時出錯: {str(e)}")

        # 創建用於顯示的DataFrames
        all_dfs = []
        import pandas as pd

        # 處理所有模型結果
        for model_name, model_result in results.items():
            try:
                # 檢查模型是否具有to_df方法
                if hasattr(model_result, "to_df") and callable(
                    getattr(model_result, "to_df")
                ):
                    self.log(f"處理 {model_name} 模型...")

                    # 使用模型的to_df方法
                    df = model_result.to_df()

                    # 檢查DataFrame是否有效
                    if df is not None and len(df) > 0:
                        # 根據模型名稱美化顯示標題
                        model_title = model_name.replace("_", " ").title()

                        # 為每個模型添加分隔標題行
                        if all_dfs:
                            # 添加空行分隔不同模型
                            # 使用標準列名建立空行
                            empty_df = pd.DataFrame(
                                [[None] * 6],
                                columns=["項目", "電腦代號", "時間", "", "", ""],
                            )
                            all_dfs.append(empty_df)

                        # 添加標題行
                        title_df = pd.DataFrame(
                            [[model_title, None, None, None, None, None]],
                            columns=["項目", "電腦代號", "時間", "", "", ""],
                        )

                        # 確保當前df的列名與標準列名一致
                        if list(df.columns) != ["項目", "電腦代號", "時間", "", "", ""]:
                            if len(df.columns) == 6:  # 如果列數相同，只需重命名
                                df.columns = ["項目", "電腦代號", "時間", "", "", ""]
                            else:  # 列數不同，需要調整
                                # 處理列名不一致的情況
                                self.log(
                                    f"警告：{model_name} 模型的列數({len(df.columns)})與標準不一致(6)，嘗試調整"
                                )
                                # 如果列數少於6，添加缺少的列
                                if len(df.columns) < 6:
                                    # 建立新的 DataFrame，保留原有資料並添加缺少的欄位
                                    new_df = pd.DataFrame(
                                        columns=["項目", "電腦代號", "時間", "", "", ""]
                                    )
                                    # 複製原有資料
                                    for i, col_name in enumerate(df.columns):
                                        if i == 0:  # 第一列是項目
                                            new_df["項目"] = df[col_name]
                                        elif i == 1:  # 第二列是電腦代號
                                            new_df["電腦代號"] = df[col_name]
                                        elif i == 2:  # 第三列是時間
                                            new_df["時間"] = df[col_name]
                                        else:  # 其他列映射到空白欄位名
                                            new_df.iloc[:, i + 2] = df[col_name]
                                    df = new_df
                                elif len(df.columns) > 6:
                                    # 如果列數超過6，只保留前6列
                                    self.log(
                                        f"警告：{model_name} 模型的列數過多，只保留前6列"
                                    )
                                    df = df.iloc[:, :6]
                                    df.columns = [
                                        "項目",
                                        "電腦代號",
                                        "時間",
                                        "",
                                        "",
                                        "",
                                    ]

                        # 合併標題和數據
                        model_df = pd.concat([title_df, df], ignore_index=True)
                        all_dfs.append(model_df)

                        self.log(f"{model_name} 模型已處理完成")
                    else:
                        self.log(
                            f"{model_name} 模型的 to_df 方法返回的 DataFrame 為空或無效"
                        )
                else:
                    self.log(f"{model_name} 模型沒有 to_df 方法")
            except Exception as e:
                self.log(f"處理 {model_name} 模型時出錯: {str(e)}")
                import traceback

                self.log(f"錯誤詳情: {traceback.format_exc()}")

        # 如果有DataFrame結果，顯示垂直堆疊的DataFrame
        if all_dfs:
            try:
                # 確保所有DataFrame的列名一致
                standard_columns = ["項目", "電腦代號", "時間", "", "", ""]

                # 處理所有DataFrame，確保列名一致
                for i, df in enumerate(all_dfs):
                    # 如果列數不一致，需要調整
                    if len(df.columns) != len(standard_columns):
                        # 獲取現有列
                        existing_cols = df.columns.tolist()
                        # 建立新的列名映射
                        col_mapping = {}
                        for j, col in enumerate(existing_cols):
                            if j < len(standard_columns):
                                col_mapping[col] = standard_columns[j]

                        # 重命名列
                        if col_mapping:
                            df = df.rename(columns=col_mapping)

                    # 確保所有DataFrame使用相同的列名
                    df.columns = standard_columns
                    all_dfs[i] = df

                # 垂直堆疊所有DataFrame
                combined_df = pd.concat(all_dfs, ignore_index=True)

                # 儲存當前DataFrame以供匯出使用
                self.current_df = combined_df
                # 啟用匯出Excel按鈕
                self.export_excel_button.config(state=tk.NORMAL)

                # 設置表格的列名
                # 前兩列固定為「項目」和「電腦代號」，剩餘的列如果是空字串，則用「時間X」替代
                display_columns = ["項目", "電腦代號"]
                for i, col in enumerate(combined_df.columns[2:], 1):
                    if col == "時間":
                        display_columns.append("時間")
                    elif col == "" or col is None:
                        display_columns.append(f"時間{i}")
                    else:
                        display_columns.append(col)

                # 複製一份DataFrame以供顯示，避免修改原始數據
                display_df = combined_df.copy()
                display_df.columns = display_columns

                # 嘗試使用 pandastable 顯示表格
                if not self.setup_table_display(display_df):
                    # 如果 pandastable 不可用，則使用之前的文本顯示方法
                    self.setup_text_display()

                    # 顯示DataFrame - 使用tabulate添加隔線並左對齊
                    try:
                        # 嘗試導入tabulate庫以獲得更好的表格格式
                        from tabulate import tabulate

                        table_str = tabulate(
                            display_df,
                            headers=display_df.columns,
                            tablefmt="grid",
                            showindex=False,
                            numalign="left",
                            stralign="left",
                        )
                    except ImportError:
                        # 如果沒有tabulate，使用自定義格式化
                        def format_df_with_grid(df):
                            """為DataFrame添加隔線並靠左對齊"""
                            cols = df.columns.tolist()
                            # 確定每列最大寬度
                            col_widths = {}
                            for col in cols:
                                # 計算列標題和內容的最大寬度
                                max_width = max(
                                    len(str(col)), df[col].astype(str).map(len).max()
                                )
                                col_widths[col] = max_width + 2  # 添加一些填充

                            # 創建標題行
                            header = "|"
                            sep_line = "+"
                            for col in cols:
                                width = col_widths[col]
                                header += f" {str(col):<{width}} |"
                                sep_line += "-" * (width + 2) + "+"

                            # 創建數據行
                            rows = []
                            rows.append(sep_line)
                            rows.append(header)
                            rows.append(sep_line)

                            for _, row in df.iterrows():
                                row_str = "|"
                                for col in cols:
                                    width = col_widths[col]
                                    val = str(row[col]) if row[col] is not None else ""
                                    row_str += f" {val:<{width}} |"
                                rows.append(row_str)
                                rows.append(sep_line)

                            return "\n".join(rows)

                        table_str = format_df_with_grid(display_df)

                    self.result_text.config(state=tk.NORMAL)
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, table_str)
                    self.result_text.config(state=tk.DISABLED)

                # 將DataFrame也保存到CSV
                csv_path = Path("gui_results.csv")
                display_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                self.log(f"DataFrame結果已保存到: {csv_path.absolute()}")
                return
            except Exception as e:
                self.log(f"顯示DataFrame時出錯: {str(e)}")
                import traceback

                self.log(f"錯誤詳情: {traceback.format_exc()}")

                # 如果顯示表格出錯，回退到文本顯示
                self.setup_text_display()

        # 如果沒有可以顯示為DataFrame的模型，或者轉換過程出錯，則顯示格式化的JSON
        try:
            # 確保使用文本顯示
            self.setup_text_display()

            # 嘗試格式化顯示模型數據
            formatted_data = ""
            for model_name, model_result in results.items():
                formatted_data += f"======== {model_name} ========\n"
                if hasattr(model_result, "model_dump_json"):  # Pydantic v2
                    formatted_data += model_result.model_dump_json(indent=2) + "\n\n"
                elif hasattr(model_result, "json"):  # Pydantic v1
                    formatted_data += model_result.json(indent=2) + "\n\n"
                else:
                    # 嘗試使用標準JSON格式化
                    formatted_data += (
                        json.dumps(model_result, ensure_ascii=False, indent=2) + "\n\n"
                    )

            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, formatted_data)
            self.result_text.config(state=tk.DISABLED)
        except Exception as e:
            self.log(f"格式化顯示結果時出錯: {str(e)}")
            # 最後嘗試直接顯示
            self.setup_text_display()  # 確保使用文本顯示
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, str(results))
            self.result_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = FinancialReportParserGUI(root)
    root.mainloop()
