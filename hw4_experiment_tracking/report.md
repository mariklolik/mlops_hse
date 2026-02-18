# Experiment Tracking Report

## Experiment: homework_kashirskiy

MLflow: http://158.160.2.37:5000/#/experiments/22

Dataset: Adult Census Income (scikit-learn/adult-census-income), binary classification (income >50K).

---

## 1. Dataset Size Variation

**Hypothesis**: Increasing training set size improves model quality.

**Setup**: Logistic Regression (L2, C=1.0, solver=lbfgs), same feature set, train_size varies from 1000 to 10000.

| Run | train_size | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| logreg_l2_1k | 1000 | 0.814 | 0.557 | 0.826 |
| logreg_l2_3k | 3000 | 0.807 | 0.481 | 0.808 |
| logreg_l2_5k | 5000 | 0.817 | 0.510 | 0.827 |
| logreg_l2_10k | 10000 | 0.815 | 0.530 | 0.817 |

**Conclusion**: Results are mixed. Accuracy and ROC-AUC remain relatively stable across dataset sizes (~0.81-0.83). F1 score fluctuates without a clear upward trend, suggesting logistic regression has limited capacity for this task regardless of training data size.

---

## 2. Model Type Variation

**Hypothesis**: Ensemble methods (Random Forest, Gradient Boosting) outperform simple models (Logistic Regression, Decision Tree) on this task.

**Setup**: train_size=5000, same feature set, different model types.

| Run | model_type | accuracy | f1 | roc_auc |
|-----|-----------|----------|------|---------|
| logreg_l2_5k | logistic_regression | 0.817 | 0.510 | 0.827 |
| decision_tree_5k | decision_tree | 0.832 | 0.602 | 0.835 |
| random_forest_5k | random_forest | 0.842 | 0.597 | 0.873 |
| gradient_boosting_5k | gradient_boosting | 0.853 | 0.629 | 0.885 |

**Conclusion**: Hypothesis confirmed. Gradient Boosting achieves the best ROC-AUC (0.885) and accuracy (0.853). Ensemble methods clearly outperform logistic regression. Decision tree is competitive on F1 but lags on ROC-AUC.

---

## 3. Learning Rate Variation (Gradient Boosting)

**Hypothesis**: Moderate learning rate (0.05-0.1) provides best balance of quality and convergence.

**Setup**: Gradient Boosting, n_estimators=200, max_depth=5, train_size=5000, learning_rate varies.

| Run | learning_rate | accuracy | f1 | roc_auc |
|-----|--------------|----------|------|---------|
| gb_lr01_5k | 0.01 | 0.845 | 0.582 | 0.870 |
| gb_lr05_5k | 0.05 | 0.854 | 0.642 | 0.888 |
| gb_lr1_5k | 0.1 | 0.851 | 0.645 | 0.885 |

**Conclusion**: Learning rates 0.05 and 0.1 yield comparable results. ROC-AUC peaks at 0.888 with lr=0.05. Very low learning rate (0.01) underperforms with 200 estimators, showing underfitting.

---

## 4. Feature Set Variation

**Hypothesis**: Using more features improves prediction quality.

**Setup**: Gradient Boosting (n_estimators=200, max_depth=5, lr=0.1), train_size=5000, feature set varies.

| Run | num_features | accuracy | f1 | roc_auc |
|-----|-------------|----------|------|---------|
| gb_few_features | 4 (numeric only) | 0.826 | 0.561 | 0.844 |
| gb_lr1_5k | 10 (mixed) | 0.851 | 0.645 | 0.885 |
| gb_all_features | 13 (all) | 0.863 | 0.684 | 0.918 |

**Conclusion**: Hypothesis confirmed. Adding categorical features significantly improves all metrics. Full feature set (13 features) gives the best ROC-AUC of 0.918.

---

## Best Run

**gb_all_features** with Gradient Boosting (n_estimators=200, max_depth=5, learning_rate=0.1), all 13 features, train_size=5000.

Best ROC-AUC: **0.918**

Link: http://158.160.2.37:5000/#/experiments/22/runs/1c984ce8fe694354bb45c1ebc3c407eb
