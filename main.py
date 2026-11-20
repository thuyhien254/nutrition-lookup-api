from contextlib import asynccontextmanager
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz
from unidecode import unidecode
from fastapi import FastAPI, HTTPException, Query

DATA_DIR = Path("data/usda_sr_legacy")
EXTRA_CSV = Path("data/additional_food.csv")

NUTRIENT_MAP = {
    "Calories": ("Energy", "kcal"),
    "Protein": ("Protein", "g"),
    "Total Fat": ("Total lipid (fat)", "g"),
    "Saturated Fat": ("Fatty acids, total saturated", "g"),
    "Trans Fat": ("Fatty acids, total trans", "g"),
    "Cholesterol": ("Cholesterol", "mg"),
    "Sodium": ("Sodium, Na", "mg"),
    "Total Carbohydrate": ("Carbohydrate, by difference", "g"),
    "Dietary Fiber": ("Fiber, total dietary", "g"),
    "Total Sugars": ("Sugars, total including NLEA", "g"),
    "Vitamin A": ("Vitamin A, RAE", "mcg RAE"),
    "Vitamin C": ("Vitamin C, total ascorbic acid", "mg"),
    "Vitamin D": ("Vitamin D (D2 + D3)", "mcg"),
    "Vitamin E": ("Vitamin E (alpha-tocopherol)", "mg"),
    "Vitamin K": ("Vitamin K (phylloquinone)", "mcg"),
    "Vitamin B1 (Thiamin)": ("Thiamin", "mg"),
    "Vitamin B2 (Riboflavin)": ("Riboflavin", "mg"),
    "Vitamin B3 (Niacin)": ("Niacin", "mg"),
    "Vitamin B6": ("Vitamin B-6", "mg"),
    "Folate": ("Folate, DFE", "mcg DFE"),
    "Vitamin B12": ("Vitamin B-12", "mcg"),
    "Calcium": ("Calcium, Ca", "mg"),
    "Iron": ("Iron, Fe", "mg"),
    "Potassium": ("Potassium, K", "mg"),
    "Magnesium": ("Magnesium, Mg", "mg"),
    "Zinc": ("Zinc, Zn", "mg"),
    "Phosphorus": ("Phosphorus, P", "mg"),
}

VIETNAMESE_TO_ENGLISH = {
    "chuoi": "Banana, raw",
    "tao": "Apples, raw",
    "cam": "Oranges, raw",
    "dua hau": "Watermelon, raw",
    "xoai": "Mangos, raw",
    "bo": "Avocados, raw",
    "trung ga": "Egg, whole, cooked",
    "thit ga": "Chicken, broilers or fryers, breast, meat only, cooked",
    "uc ga": "Chicken, broilers or fryers, breast, meat only, cooked",
    "thit bo": "Beef, ground, cooked",
    "thit heo": "Pork, fresh, cooked",
    "ca hoi": "Fish, salmon, cooked",
    "ca ngu": "Fish, tuna, cooked",
    "tom": "Crustaceans, shrimp, cooked",
    "com trang": "Rice, white, cooked",
    "com": "Rice, white, cooked",
    "banh mi": "Bread, white",
    "sua tuoi": "Milk, whole",
    "sua tuoi khong duong": "Milk, whole",
    "pho": "Rice noodles, cooked",
    "bun tuoi": "Rice noodles, cooked",
    "mi": "Noodles, cooked",
    "khoai lang": "Sweet potato, cooked",
    "khoai tay": "Potatoes, cooked",
    "ca rot": "Carrots, cooked",
    "bong cai xanh": "Broccoli, cooked",
    "rau bina": "Spinach, cooked",
    "dau hu": "Tofu",
    "dau phong": "Peanuts",
    "hanh tay": "Onions, raw",
    "toi": "Garlic, raw",
}

MIXED_DISHES = {
    "pho bo",
    "pho ga",
    "bun bo hue",
    "com tam",
    "banh mi thit",
    "mi xao",
    "hu tieu",
    "bun cha",
    "goi cuon",
    "banh xeo",
}

state: dict = {}


def normalize_vi(text: str) -> str:
    return " ".join(unidecode(str(text)).lower().strip().split())


def build_database() -> pd.DataFrame:
    csv_files = {p.name.lower(): p for p in DATA_DIR.rglob("*.csv")}
    foods = pd.read_csv(csv_files["food.csv"], encoding="latin1", low_memory=False)
    food_nutrients = pd.read_csv(csv_files["food_nutrient.csv"], encoding="latin1", low_memory=False)
    nutrients = pd.read_csv(csv_files["nutrient.csv"], encoding="latin1", low_memory=False)

    foods.columns = foods.columns.str.lower()
    food_nutrients.columns = food_nutrients.columns.str.lower()
    nutrients.columns = nutrients.columns.str.lower()
    foods["description"] = foods["description"].fillna("").astype(str)

    nutrients["name"] = nutrients["name"].fillna("").str.strip()
    name_to_id = {}
    for _, row in nutrients.iterrows():
        name_to_id.setdefault(row["name"].casefold(), row["id"])

    nutrient_lookup = {}
    for display_name, (usda_name, _) in NUTRIENT_MAP.items():
        nid = name_to_id.get(usda_name.casefold())
        if nid is not None:
            nutrient_lookup[nid] = display_name

    fn = food_nutrients[food_nutrients["nutrient_id"].isin(nutrient_lookup)].copy()
    fn["amount"] = pd.to_numeric(fn["amount"], errors="coerce")
    fn = fn.dropna(subset=["amount"])
    fn["nutrient_name"] = fn["nutrient_id"].map(nutrient_lookup)

    nutrition_table = fn.pivot_table(
        index="fdc_id",
        columns="nutrient_name",
        values="amount",
        aggfunc="first",
    ).reset_index()
    nutrition_table.columns.name = None

    db = foods[["fdc_id", "description"]].merge(nutrition_table, on="fdc_id", how="left")

    if EXTRA_CSV.exists():
        extra = pd.read_csv(EXTRA_CSV)
        nutr_cols = [c for c in NUTRIENT_MAP if c in extra.columns]
        cols = list(db.columns) + [c for c in nutr_cols if c not in db.columns]
        db = pd.concat([db, extra.reindex(columns=cols)], ignore_index=True)

        for name in extra["description"].dropna():
            key = normalize_vi(name)
            VIETNAMESE_TO_ENGLISH[key] = name
            MIXED_DISHES.discard(key)

    for short, full in {
        "com tam": "cơm tấm sườn bì chả",
        "bun cha": "bún chả Hà Nội",
        "goi cuon": "gỏi cuốn",
    }.items():
        VIETNAMESE_TO_ENGLISH[short] = full
        MIXED_DISHES.discard(short)

    for fruit in ["chuoi", "tao", "cam", "dua hau", "xoai", "bo"]:
        for prefix in ("trai ", "qua "):
            if fruit in VIETNAMESE_TO_ENGLISH:
                VIETNAMESE_TO_ENGLISH[prefix + fruit] = VIETNAMESE_TO_ENGLISH[fruit]

    return db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = build_database()
    state["db"] = db
    state["descriptions"] = db["description"].fillna("").astype(str).tolist()
    yield
    state.clear()


app = FastAPI(title="Nutrition Lookup API", lifespan=lifespan)


@app.get("/api/v1/nutrition")
def get_nutrition(
    food_name: str = Query(..., min_length=1, description="Tên món ăn hoặc nguyên liệu"),
    serving_g: float = Query(100.0, gt=0, description="Khối lượng khẩu phần (gram)"),
    min_score: int = Query(75, ge=0, le=100, description="Ngưỡng khớp tên tối thiểu"),
):
    query = normalize_vi(food_name)
    if query in MIXED_DISHES:
        raise HTTPException(
            status_code=422,
            detail=f"'{food_name}' là món hỗn hợp chưa có công thức chuẩn trong dữ liệu hiện tại.",
        )

    db: pd.DataFrame = state["db"]
    names: list[str] = state["descriptions"]
    english_query = VIETNAMESE_TO_ENGLISH.get(query, food_name)

    match = process.extractOne(english_query, names, scorer=fuzz.WRatio)
    if match is None or match[1] < min_score:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy thực phẩm phù hợp với '{food_name}'.",
        )

    matched_name, score, idx = match
    food_row = db.iloc[idx]

    nutrients_out = []
    for label, (_, unit) in NUTRIENT_MAP.items():
        if label not in db.columns:
            continue
        val = food_row[label]
        if pd.isna(val):
            continue
        nutrients_out.append({
            "name": label,
            "amount": round(float(val) * serving_g / 100.0, 2),
            "unit": unit,
        })

    return {
        "input_name": food_name,
        "search_query": english_query,
        "matched_description": matched_name,
        "similarity_score": round(float(score), 2),
        "serving_g": serving_g,
        "nutrients": nutrients_out,
    }