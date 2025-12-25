import json
import os
from typing import Any

from utils.util import get_path_for_write

# 默认配置来源：constants.py（只读）
from constants import CATEGORIES as DEFAULT_CATEGORIES
from constants import CATEGORY_FIELDS as DEFAULT_CATEGORY_FIELDS
from constants import MAX_DYNAMIC_FIELDS

CONFIG_FILE_NAME = "category_config.json"

def _config_path() -> str:
    return get_path_for_write(CONFIG_FILE_NAME)

def _normalize_field(field: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(field, dict):
        return None

    key = str(field.get("key", "")).strip()
    label = str(field.get("label", "")).strip()
    required = bool(field.get("required", False))

    if not key or not label:
        return None

    return {"key": key, "label": label, "required": required}

def _validate_config(categories: Any, category_fields: Any) -> tuple[bool, str]:
    if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
        return False, "categories 必须是字符串数组"

    categories = [c.strip() for c in categories if str(c).strip()]
    if len(categories) != len(set(categories)):
        return False, "categories 存在重复项"

    if not isinstance(category_fields, dict):
        return False, "category_fields 必须是字典"

    for cat, fields in category_fields.items():
        if not isinstance(cat, str) or not cat.strip():
            return False, "category_fields 的键必须是非空字符串"
        if not isinstance(fields, list):
            return False, f"{cat} 的字段定义必须是数组"
        if len(fields) > MAX_DYNAMIC_FIELDS:
            return False, f"{cat} 的字段数量超过上限 {MAX_DYNAMIC_FIELDS}"

        seen_keys: set[str] = set()
        for f in fields:
            nf = _normalize_field(f)
            if not nf:
                return False, f"{cat} 的字段定义格式不正确（需要 key/label/required）"
            if nf["key"] in seen_keys:
                return False, f"{cat} 的字段 key 重复：{nf['key']}"
            seen_keys.add(nf["key"])

    # category_fields 里的类别不强制必须都在 categories 中（允许残留）；但保存时会同步
    return True, "OK"

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _atomic_write_json(path: str, payload: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_config() -> dict[str, Any]:
    """加载类别配置。

    优先级：
    1) 可写目录下的 category_config.json（管理员修改后生成）
    2) constants.py 的默认值
    """
    path = _config_path()

    if os.path.exists(path):
        try:
            data = _read_json(path)
            categories = data.get("categories")
            category_fields = data.get("category_fields")
            ok, _ = _validate_config(categories, category_fields)
            if ok:
                return {"categories": categories, "category_fields": category_fields}
        except Exception:
            # 配置文件损坏/格式不对：回退默认
            pass

    return {
        "categories": list(DEFAULT_CATEGORIES),
        "category_fields": json.loads(json.dumps(DEFAULT_CATEGORY_FIELDS, ensure_ascii=False)),
    }

def save_config(categories: list[str], category_fields: dict[str, list[dict[str, Any]]]) -> tuple[bool, str]:
    ok, msg = _validate_config(categories, category_fields)
    if not ok:
        return False, msg

    # 保存时做一次同步与清理：
    categories = [c.strip() for c in categories if str(c).strip()]
    category_fields = {str(k).strip(): v for k, v in category_fields.items() if str(k).strip()}

    # 确保每个类别都有字段列表
    for c in categories:
        category_fields.setdefault(c, [])

    payload = {"categories": categories, "category_fields": category_fields}
    _atomic_write_json(_config_path(), payload)
    return True, "已保存类别配置"

def get_categories() -> list[str]:
    cfg = load_config()
    categories: list[str] = [str(c).strip() for c in cfg.get("categories", []) if str(c).strip()]
    if "其他" not in categories:
        categories.append("其他")
    # 去重但保序
    seen: set[str] = set()
    out: list[str] = []
    for c in categories:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out

def get_category_fields() -> dict[str, list[dict[str, Any]]]:
    cfg = load_config()
    raw = cfg.get("category_fields") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    if isinstance(raw, dict):
        for cat, fields in raw.items():
            if not isinstance(cat, str) or not cat.strip() or not isinstance(fields, list):
                continue
            normalized: list[dict[str, Any]] = []
            for f in fields:
                nf = _normalize_field(f)
                if nf:
                    normalized.append(nf)
            out[cat.strip()] = normalized[:MAX_DYNAMIC_FIELDS]

    # 确保所有 categories 都有 key
    for c in get_categories():
        out.setdefault(c, [])
    return out

def get_fields_json_for_category(category: str) -> str:
    category = (category or "").strip()
    fields = get_category_fields().get(category, [])
    return json.dumps(fields, ensure_ascii=False, indent=2)

def upsert_category(
    old_name: str | None,
    new_name: str,
    fields_json: str,
) -> tuple[bool, str]:
    """新增/更新/改名一个类别。"""
    old_name = (old_name or "").strip() or None
    new_name = (new_name or "").strip()

    if not new_name:
        return False, "类型名称不能为空"
    if len(new_name) > 20:
        return False, "类型名称过长（建议 ≤ 20 字符）"

    try:
        fields_raw = json.loads(fields_json or "[]")
    except Exception:
        return False, "属性定义 JSON 解析失败"

    if not isinstance(fields_raw, list):
        return False, "属性定义必须是 JSON 数组"

    normalized_fields: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for f in fields_raw:
        nf = _normalize_field(f)
        if not nf:
            return False, "属性定义项必须包含 key/label，required 可选"
        if nf["key"] in seen_keys:
            return False, f"属性 key 重复：{nf['key']}"
        seen_keys.add(nf["key"])
        normalized_fields.append(nf)

    if len(normalized_fields) > MAX_DYNAMIC_FIELDS:
        return False, f"属性数量超过上限 {MAX_DYNAMIC_FIELDS}"

    categories = get_categories()
    fields_map = get_category_fields()

    # --- 核心逻辑：互斥分支 (if - elif - else) ---
    # 三种情况：
    # A) old_name 为空，new_name不为空：新增类别
    if not old_name:
        if new_name in categories:
            # 新增一个已存在的名字，视为更新
            fields_map[new_name] = normalized_fields
        else:
            categories.append(new_name)
            fields_map[new_name] = normalized_fields

    # B) old_name 不为空，new_name 不为空且 old_name 不等于 new_name：改名类别
    elif old_name != new_name:
        if new_name in categories:
            return False, "新类型名称已存在，不能改名为已有名称"
        if old_name not in categories:
            return False, "旧类型名称不存在，无法改名"
        # 替换列表项 (保序)
        categories = [new_name if c == old_name else c for c in categories]
        
        # 迁移字段定义
        fields_map[new_name] = normalized_fields
        fields_map.pop(old_name, None)

    # C) old_name 不为空，new_name 不为空且 old_name 等于 new_name：仅更新属性
    else:
        fields_map[old_name] = normalized_fields

    # 兜底：确保“其他”存在
    if "其他" not in categories:
        categories.append("其他")

    ok, msg = save_config(categories, fields_map)
    return ok, msg

def delete_category(name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "请选择要删除的类型"
    if name == "其他":
        return False, "不能删除“其他”类型"

    categories = get_categories()
    if name not in categories:
        return False, "类型不存在"

    categories = [c for c in categories if c != name]
    fields_map = get_category_fields()
    fields_map.pop(name, None)

    ok, msg = save_config(categories, fields_map)
    return ok, msg
