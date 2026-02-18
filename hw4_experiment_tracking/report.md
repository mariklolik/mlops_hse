# Experiment Tracking Report

## Experiment: homework_kashirskiy

MLflow: http://158.160.2.37:5000/

Dataset: Adult Census Income (scikit-learn/adult-census-income), binary classification (income >50K).

---

## 1. Dataset Size Variation

**Hypothesis**: Increasing training set size improves model quality.

**Setup**: Logistic Regression (L2, C=1.0, solver=lbfgs), same feature set, train_size varies from 1000 to 10000.

| Run | train_size | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| logreg_l2_1k | 1000 | 0.793 | 0.528 | 0.832 |
| logreg_l2_3k | 3000 | 0.812 | 0.575 | 0.856 |
| logreg_l2_5k | 5000 | 0.821 | 0.598 | 0.870 |
| logreg_l2_10k | 10000 | 0.829 | 0.617 | 0.880 |

**Conclusion**: Hypothesis confirmed. All metrics improve with dataset size. ROC-AUC grows from ~0.83 to ~0.88. Diminishing returns observed beyond 5k samples.

---

## 2. Model Type Variation

**Hypothesis**: Ensemble methods (Random Forest, Gradient Boosting) outperform simple models (Logistic Regression, Decision Tree) on this task.

**Setup**: train_size=5000, same feature set, different model types.

| Run | model_type | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| logreg_l2_5k | logistic_regression | 0.821 | 0.598 | 0.870 |
| decision_tree_5k | decision_tree | 0.805 | 0.560 | 0.780 |
| random_forest_5k | random_forest | 0.842 | 0.639 | 0.900 |
| gradient_boosting_5k | gradient_boosting | 0.851 | 0.658 | 0.912 |

**Conclusion**: Hypothesis confirmed. Gradient Boosting achieves the best ROC-AUC (0.912). Decision Tree performs worst. Ensemble methods clearly outperform single models.

---

## 3. Learning Rate Variation (Gradient Boosting)

**Hypothesis**: Moderate learning rate (0.05-0.1) provides best balance of quality and convergence.

**Setup**: Gradient Boosting, n_estimators=200, max_depth=5, train_size=5000, learning_rate varies.

| Run | learning_rate | accuracy | f1 | roc_auc |
|-----|--------------|----------|------|---------|
| gb_lr01_5k | 0.01 | 0.830 | 0.620 | 0.890 |
| gb_lr05_5k | 0.05 | 0.848 | 0.652 | 0.910 |
| gb_lr1_5k | 0.1 | 0.854 | 0.662 | 0.916 |

**Conclusion**: Higher learning rate (0.1) yields best results with 200 estimators. Very low learning rate (0.01) underfits with this number of trees.

---

## 4. Feature Set Variation

**Hypothesis**: Using more features improves prediction quality.

**Setup**: Gradient Boosting (n_estimators=200, max_depth=5, lr=0.1), train_size=5000, feature set varies.

| Run | num_features | accuracy | f1 | roc_auc |
|-----|-------------|----------|------|---------|
| gb_few_features | 4 (numeric only) | 0.810 | 0.555 | 0.860 |
| gb_lr1_5k | 10 (mixed) | 0.854 | 0.662 | 0.916 |
| gb_all_features | 13 (all) | 0.858 | 0.670 | 0.920 |

**Conclusion**: Hypothesis confirmed. Adding categorical features significantly improves quality. Full feature set gives marginal improvement over 10 features.

---

## Best Run

**gb_all_features** with Gradient Boosting (n_estimators=200, max_depth=5, learning_rate=0.1), all 13 features, train_size=5000.

Best ROC-AUC: **0.920**
