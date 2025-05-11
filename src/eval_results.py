import json
from pathlib import Path

# 在這裡定義哪些路徑是 optional（不需要嚴格比對），用完整路徑或通配 key
OPTIONAL_PATHS = {
    # 忽略所有 subtotal 的缺失或不同
    "*/subtotal",
    # 忽略所有 total 的缺失或不同
    "*/total",
    # 忽略所有 source_label 的缺失或不同
    "*/source_label",
    # 忽略所有 source_page 的缺失或不同
    "*/source_page",
}

# 在這裡定義貨幣的同義詞群組
CURRENCY_EQUIVALENTS = [
    {"其他", "其餘", "Other"},
    {"USD", "美金", "美元"},
    {"TWD", "新台幣", "NTD"},
    {"HKD", "港幣", "HKD"},
    {"CNY", "人民幣", "RMB"},
    {"JPY", "日圓", "日元"},
    {"EUR", "歐元", "Euro"},
    {"GBP", "英鎊", "英鎊"},
    {"AUD", "澳幣", "澳元"},
    {"CAD", "加幣", "加元"},
    {"SGD", "新加坡幣", "新加坡元"},
    {"CHF", "瑞士法郎", "瑞士法郎"},
    {"NZD", "紐西蘭幣", "紐西蘭元"},
    {"KRW", "韓元", "韓元"},
]


def is_optional(cur_path: str) -> bool:
    """
    判斷當前路徑是否為 optional
    支援 '*' 通配在開頭或結尾，以及 '[*]' 表示 list 中任意 index
    """
    for pat in OPTIONAL_PATHS:
        # 處理 [*] 通配 list index
        if "[*]" in pat:
            base = pat.replace("[*]", "")
            if (
                cur_path.startswith(base)
                and "/" not in cur_path[len(base) :].split("[", 1)[0]
            ):
                return True
        # 處理前綴或後綴通配
        elif pat.startswith("*") and cur_path.endswith(pat.lstrip("*")):
            return True
        elif pat.endswith("*") and cur_path.startswith(pat.rstrip("*")):
            return True
        elif pat == cur_path:
            return True
    return False


def is_equivalent_currency(a: str, b: str) -> bool:
    """
    判斷兩個貨幣是否為同義詞
    """
    for group in CURRENCY_EQUIVALENTS:
        if a in group and b in group:
            return True
    return False


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_dict(ans: dict, res: dict, path: str = "") -> list[str]:
    errors: list[str] = []

    for key, ans_val in ans.items():
        cur = f"{path}/{key}" if path else key
        if key not in res:
            if not is_optional(cur):
                errors.append(f"[MISSING] 必填欄位缺失: {cur}")
            continue

        rv = res[key]
        if isinstance(ans_val, dict) and isinstance(rv, dict):
            errors += compare_dict(ans_val, rv, cur)
        elif isinstance(ans_val, list) and isinstance(rv, list):
            if ans_val:
                for idx, (g_item, r_item) in enumerate(zip(ans_val, rv)):
                    errors += compare_dict(g_item, r_item, f"{cur}[{idx}]")
        else:
            if key == "currency" and isinstance(ans_val, str) and isinstance(rv, str):
                if not is_equivalent_currency(ans_val, rv) and not is_optional(cur):
                    errors.append(f"[DIFF] {cur}：預期貨幣={ans_val}，實際貨幣={rv}")
            elif ans_val != rv and not is_optional(cur):
                errors.append(f"[DIFF] {cur}：預期={ans_val}，實際={rv}")

    for key in res:
        cur = f"{path}/{key}" if path else key
        if key not in ans and not is_optional(cur):
            errors.append(f"[EXTRA] 多餘欄位: {cur}")

    return errors


def main():
    answers = load_json("answers.json")
    results = load_json("results.json")

    total = len(answers)
    passed = 0

    for fname, ans_struct in answers.items():
        print(f"\n=== {fname} ===")
        res_struct = results.get(fname)
        if res_struct is None:
            print(f"  [ERROR] 找不到解析結果：{fname}")
            continue

        diffs = compare_dict(ans_struct, res_struct, fname)
        if not diffs:
            print("✅ 必填欄位皆符合！")
            passed += 1
        else:
            for d in diffs:
                print("  ", d)

    print(f"\n總共 {total} 份，通過 {passed} 份，失敗 {total-passed} 份。")


if __name__ == "__main__":
    main()
