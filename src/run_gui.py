#!/usr/bin/env python
"""
財務報告解析器 GUI 啟動程式
這個程式用於啟動財務報告解析器的圖形用戶界面
"""

import tkinter as tk
from gui import FinancialReportParserGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = FinancialReportParserGUI(root)
    root.mainloop()
