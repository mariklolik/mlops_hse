# Analysis of Bondarenko's Experiments

MLflow: http://158.160.2.37:5000/#/experiments/21

Experiment: homework_bondarenko (25 runs total, 20 with metrics).

Dataset: Adult Census Income, binary classification (income >50K).

Features: race, sex, native.country, occupation, education, capital.gain (6 features, 5 categorical + 1 numeric).

---

## 1. Train Size Variation (Logistic Regression)

Model: LogisticRegression (L2, C=0.9, solver=lbfgs, max_iter=1000).

| Run | train_size | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| log_reg_train_size_100 | 100 | 0.792 | 0.309 | 0.693 |
| log_reg_train_size_500 | 500 | 0.794 | 0.312 | 0.709 |
| log_reg_train_size_1000 | 1000 | 0.794 | 0.314 | 0.709 |
| log_reg_train_size_2000 | 2000 | 0.796 | 0.315 | 0.714 |
| log_reg_train_size_full | full | 0.798 | 0.314 | 0.713 |

Increasing train size slightly improves accuracy (0.792 -> 0.798) and ROC-AUC (0.693 -> 0.713). F1 remains low (~0.31) across all sizes, indicating the model struggles with the minority class regardless of data volume. The biggest jump is from 100 to 500 samples.

---

## 2. Model Type Comparison

All models use full training set, same 6 features. Best run per model type:

| Run | model_type | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| log_reg_train_size_full | LogisticRegression | 0.798 | 0.314 | 0.713 |
| decision_tree_depth_10 | DecisionTree (depth=10) | 0.824 | 0.512 | 0.820 |
| random_forest_estimators_50 | RandomForest (n=50) | 0.822 | 0.534 | 0.821 |
| grad_boosting_lr_0.30 | GradientBoosting (lr=0.3) | 0.831 | 0.533 | 0.838 |

Ensemble methods (RandomForest, GradientBoosting) outperform simple models. GradientBoosting achieves the best ROC-AUC (0.838). LogisticRegression significantly underperforms with F1=0.314 vs 0.53 for tree-based models.

---

## 3. Decision Tree Depth Variation

| Run | max_depth | accuracy | f1 | roc_auc |
|-----|----------|----------|------|---------|
| decision_tree_depth_3 | 3 | 0.806 | 0.304 | 0.722 |
| decision_tree_depth_5 | 5 | 0.806 | 0.312 | 0.777 |
| decision_tree_depth_7 | 7 | 0.819 | 0.455 | 0.809 |
| decision_tree_depth_10 | 10 | 0.824 | 0.512 | 0.820 |

Deeper trees improve all metrics. The jump from depth=5 to depth=7 is the most significant (F1: 0.312 -> 0.455). Depth=3 behaves similarly to LogisticRegression (low recall).

---

## 4. Random Forest n_estimators Variation

| Run | n_estimators | accuracy | f1 | roc_auc |
|-----|-------------|----------|------|---------|
| random_forest_estimators_50 | 50 | 0.822 | 0.534 | 0.821 |
| random_forest_estimators_100 | 100 | 0.821 | 0.533 | 0.821 |
| random_forest_estimators_150 | 150 | 0.821 | 0.531 | 0.821 |
| random_forest_estimators_200 | 200 | 0.821 | 0.530 | 0.821 |

Increasing n_estimators from 50 to 200 has almost no effect. All metrics are stable. 50 trees are sufficient for this feature set.

---

## 5. Gradient Boosting Learning Rate Variation

| Run | learning_rate | accuracy | f1 | roc_auc |
|-----|--------------|----------|------|---------|
| grad_boosting_lr_0.01 | 0.01 | 0.806 | 0.304 | 0.772 |
| grad_boosting_lr_0.10 | 0.10 | 0.826 | 0.534 | 0.831 |
| grad_boosting_lr_0.20 | 0.20 | 0.831 | 0.531 | 0.837 |
| grad_boosting_lr_0.30 | 0.30 | 0.831 | 0.533 | 0.838 |

Learning rate 0.01 is too low (underfitting, similar to LogReg). Rates 0.1-0.3 perform similarly, with 0.3 being slightly best by ROC-AUC. The biggest jump is from 0.01 to 0.1.

---

## 6. Feature Set Variation (Logistic Regression)

| Run | num_features | accuracy | f1 | roc_auc |
|-----|-------------|----------|------|---------|
| log_reg_features_4_cols | 4 (race, sex, native.country, occupation) | 0.764 | 0.000 | 0.646 |
| log_reg_features_5_cols | 5 (+education) | 0.764 | 0.000 | 0.656 |
| log_reg_features_6_cols | 6 (+capital.gain) | 0.798 | 0.314 | 0.713 |

With 4 or 5 categorical features the model predicts only the majority class (F1=0.0). Adding capital.gain (the only numeric feature) enables the model to discriminate, boosting accuracy from 0.764 to 0.798 and ROC-AUC from 0.646 to 0.713. Capital.gain is the single most important feature.

---

## Best Run

**grad_boosting_lr_0.30**: GradientBoostingClassifier, learning_rate=0.3, full training set, 6 features.

Best ROC-AUC: **0.838**
