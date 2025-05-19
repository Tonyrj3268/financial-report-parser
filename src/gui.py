import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import asyncio
import threading
from pathlib import Path
import json
import os
import sys

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

        self.create_widgets()

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
        results_frame = ttk.LabelFrame(bottom_frame, text="處理結果", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        result_scroll = ttk.Scrollbar(results_frame, orient="vertical")
        result_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 水平捲軸
        h_scroll = ttk.Scrollbar(results_frame, orient="horizontal")
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.result_text = tk.Text(
            results_frame,
            wrap=tk.NONE,  # 禁用自動換行，以便正確顯示長JSON
            state=tk.DISABLED,
            yscrollcommand=result_scroll.set,
            xscrollcommand=h_scroll.set,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        result_scroll.config(command=self.result_text.yview)
        h_scroll.config(command=self.result_text.xview)

        # 設置等寬字體，讓JSON格式化顯示更清晰
        self.result_text.configure(font=("Consolas", 10))

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

        # 格式化 JSON 並顯示
        formatted_json = json.dumps(results, ensure_ascii=False, indent=2)

        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, formatted_json)
        self.result_text.config(state=tk.DISABLED)

        # 保存結果到文件
        output_path = Path("gui_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)

        self.log(f"結果已保存到: {output_path.absolute()}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FinancialReportParserGUI(root)
    root.mainloop()
