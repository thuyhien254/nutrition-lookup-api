# Nutrition Lookup API

A FastAPI-based REST API for searching foods and calculating their nutritional values. It combines the USDA SR Legacy dataset with optional local food data and uses RapidFuzz for fuzzy matching.

## Table of Contents

- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Data Setup](#1-data-setup)
- [Environment Setup](#2-environment-and-dependencies)
- [Run the Server](#3-run-the-server)
- [Test the API](#4-test-the-api)
- [API Reference](#5-api-reference)
- [HTTP Status Codes](#http-status-codes)

## Requirements

- **Python:** 3.9 or later
- **Memory:** At least 1–2 GB of available RAM to load the dataset

## Project Structure

Before getting started, organize the project as follows:

```text
nutrition_api/
├── main.py
├── requirements.txt
├── README.md
└── data/
    ├── usda_sr_legacy/
    │   ├── food.csv
    │   ├── food_nutrient.csv
    │   └── nutrient.csv
    └── additional_food.csv 
```

## 1. Data Setup

The API requires CSV files containing nutritional data.

### Download the USDA SR Legacy dataset

Download the **FoodData Central SR Legacy CSV** dataset, then extract the ZIP archive.

### Add the dataset files

From the extracted dataset, locate these files:

- `food.csv`
- `food_nutrient.csv`
- `nutrient.csv`

Place all three files in:

```text
data/usda_sr_legacy/
```

### Add supplementary data (optional)

If available, place `mon_bo_sung_per100g.csv` in the `data/` directory.

## 2. Environment and Dependencies

Open a terminal in the project root (`nutrition_api`).

### Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

Using `python -m pip` installs dependencies into the active Python environment:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Run the Server

Start the API in development mode:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

When startup is complete, the terminal will display:

```text
Application startup complete.
```

The API will be available at:

<http://localhost:8000>

## 4. Test the API

FastAPI provides interactive API documentation through Swagger UI:

1. Open <http://localhost:8000/docs>.
2. Expand **GET `/api/v1/nutrition`**.
3. Select **Try it out**.
4. Enter sample parameters, such as:
   - `food_name`: `trứng gà` or `cơm tấm`
   - `serving_g`: `100`
5. Select **Execute** to view the JSON response.

## 5. API Reference

### `GET /api/v1/nutrition`

Retrieve nutritional information for a food item.

#### Query parameters

| Parameter | Type | Required | Default | Description |
|---|---|---:|---:|---|
| `food_name` | string | Yes | — | Food or ingredient name, such as `thịt gà`, `banana`, or `cơm tấm`. |
| `serving_g` | float | No | `100.0` | Serving size in grams. Must be greater than `0`. |
| `min_score` | integer | No | `75` | Minimum fuzzy-match similarity threshold, from `0` to `100`. |

#### Example response

**`200 OK`**

```json
{
  "input_name": "trung ga",
  "search_query": "Egg, whole, cooked",
  "matched_description": "Egg, whole, cooked",
  "similarity_score": 100.0,
  "serving_g": 100.0,
  "nutrients": [
    {
      "name": "Calories",
      "amount": 155.0,
      "unit": "kcal"
    },
    {
      "name": "Protein",
      "amount": 12.58,
      "unit": "g"
    },
    {
      "name": "Total Fat",
      "amount": 10.61,
      "unit": "g"
    }
  ]
}
```

## HTTP Status Codes

| Status code | Description |
|---|---|
| `404 Not Found` | No food item matched the query above the `min_score` threshold. |
| `422 Unprocessable Entity` | The query matches a complex mixed dish without standardized formula data. |
