# **SmartBite**

**AI System to Predict Daily Cafeteria Food Demand & Student Preferences**

SmartBite is a complete Machine Learning & Data Analysis pipeline designed to help college cafeterias **reduce food wastage**, **avoid shortages**, and **plan menus intelligently**.
It uses **time-series forecasting, preference mining, clustering**, and **event modeling** to understand and predict demand patterns.

This repository contains the entire implementation from **synthetic dataset generation** to **final ML models**, **EDA**, **SHAP explainability**, and **7-day ahead forecasting**.

---

# **1. Project Objectives**

SmartBite is built to fulfill four major goals:

1. **Predict daily food demand** for every dish across Breakfast, Lunch, Snacks, and Dinner.
2. **Capture traffic patterns & event-based spikes** (festivals, exams, vacations).
3. **Understand student preferences** using association rules & clustering.
4. **Provide actionable insights** (forecasting, menu suggestions, demand profiles).

---

# **2. Repository Structure**

```
.
├── data/                   # Raw, cleaned, and featured datasets
├── docs/                   # Proposal, dataset logic, full IEEE report, Project Presentation
├── figures/                # All visualizations (EDA, SHAP, clustering, model comparisons)
├── logs/                   # Runtime logs
├── models/                 # Saved baseline & tuned ML models + encoders
├── notebooks/              # Main project notebooks
├── reports/                # CSV outputs (rules, clusters, forecasts, model metrics)
└── project_structure.txt   # Repo overview
```

---

# **3. Project Workflow (End-to-End Pipeline)**

SmartBite follows a clean, modular ML workflow:

### **1. Synthetic Dataset Generation**

* Dataset logic defined in `/docs/Smartbite_dataset_generation_doc.pdf`
* Dataset script in `/notebooks/Smartbite_dataset.ipynb`
* 2022–2025 data, 33k+ rows, 144 vegetarian dishes
* Includes **events, vacations, student count changes, weekly patterns**, and realistic noise

### **2. Loading & Preprocessing**

* Remove duplicates
* Validate date fields
* Create time features: Year, Month, Week, DayOfYear, Is_Weekend
* Encode categorical features (Meal, Dish, Day)
* Add lag & rolling features:

  * **Servings_Lag_1** → previous occurrences
  * **Dish_Avg_3** → moving average over last 3 occurrences

### **3. Exploratory Data Analysis (EDA)**

Visuals stored in `/figures/`:

* Event & Vacation effects
* Average servings per meal type
* Daily demand timeline
* Top 20 dishes
* Correlation heatmap
* Lag vs Servings scatter

### **4. Baseline Machine Learning Models**

Trained & evaluated using: **MAE, RMSE, MAPE**

Models:

* Linear Regression
* Random Forest
* Gradient Boosting
* XGBoost

📌 **Best Baseline:** Random Forest (RMSE ~727)

### **5. Hyperparameter Tuning**

Using `RandomizedSearchCV + TimeSeriesSplit (3 folds)`:

* Tuned Random Forest
* Tuned XGBoost

📌 **Final Best Model:** **Tuned XGBoost (RMSE ~705)**
Saved as: `/models/final_best_model.pkl`

### **6. Model Explainability (SHAP)**

Plots in `/figures/shap_summary_final_model.png`

Key predictors:

* **Servings_Lag_1** (strongest)
* Dish_Code
* Student_Count
* Meal_Type_Code
* Event/Vacation flags

### **7. Future Forecasting (Next 7 Days)**

Generates dish level forecast for **every meal × dish × date**.
Outputs saved to:
`/reports/forecast_next7days.csv`

### **8. Preference Analysis (Association Rules)**

Using Apriori for each meal-type.
Outputs:

* `association_rules_report_all_meals.csv`
* `menu_recommendations_from_rules.csv`
* Visualization: `/figures/association_rules_by_meal.png`

### **9. Daily Demand Clustering**

KMeans clustering (k=4) to identify day-types:

* Normal-Low
* Normal-High
* Event-Heavy High
* Vacation-Like Low

Outputs:

* `/reports/cluster_profiles_report.csv`
* `/reports/cluster_strategy_recommendations.csv`
* `/figures/clustering_03_pca_scatter.png`

### **10. Prophet-Based Aggregate Forecasting**

Models total daily servings with seasonality.
Visuals:

* `prophet_01_forecast_plot.png`
* `prophet_02_components_plot.png`

---

# **4. How to Run This Project**

### **Option 1: Run in Google Colab (Recommended)**

Upload the repo → open the main notebook:

```
/notebooks/SmartBite.ipynb
```

This notebook contains **Cells 1–12**, covering the entire SmartBite pipeline.

### **Option 2: Run Locally**

#### 1. Clone the repo:

```bash
git clone https://github.com/yourusername/SmartBite.git
cd SmartBite
```

#### 2. Install dependencies:

(You may create a requirement.txt or install manually)

```bash
pip install pandas numpy scikit-learn xgboost prophet shap mlxtend matplotlib seaborn
```

#### 3. Run the notebooks:

```bash
jupyter notebook notebooks/SmartBite.ipynb
```

The notebook auto-loads datasets and saves outputs into `/models`, `/reports`, and `/figures`.

---

# **5. Key Results**

### **Final Best Model:** Tuned XGBoost

* **RMSE ~705**
* Most accurate for dish-level predictions
* Captures lag behavior, trends, event/vacation effects

### **Insightful EDA**

* Breakfast dishes have highest avg servings (per dish)
* Strong weekly & event-driven patterns

### **7-Day Forecast**

* Predicts demand for every dish × meal combination
* Snacks showed highest projected demand for the predicted week

### **Menu Intelligence**

* 30k+ association rules found
* High-lift combos for Breakfast & Lunch
* Helps plan menu layout & combo offers

### **Daily Demand Clusters**

* 4 demand types found
* Lunch always dominates total daily consumption
* Cluster insights usable for daily batch planning

---

# **6. Limitations**

* Synthetic dataset (not yet validated with real POS logs)
* No LSTM/Deep Learning models (planned for future)
* Forecasting assumes constant student count + no new events
* Student preferences simplified during generation

---

# **7. Future Enhancements**

* Replace synthetic data with **real cafeteria POS logs**
* Add **LSTM / Temporal CNN models**
* Deploy a **Streamlit dashboard**
* Enable **online learning** and demand drift detection
* Add dietary tags, price sensitivity, and real-time feedback

---

# **8. Documentation**

Additional project documents are available in `/docs`:

* Proposal
* Dataset Generation Logic
* Full IEEE-style Project Report
* Smartbite Project Presentation

---

# **9. Team & Contribution**

SmartBite is developed as part of an academic AI/ML project focusing on real-world operational optimization using data-driven methods.

---

# **Thank You for Exploring SmartBite!**

If you use this repository or find it helpful, consider starring ⭐ the repo.

---

