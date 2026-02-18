import os
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from joblib import load
from sklearn.metrics import (
    get_scorer,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    average_precision_score,
)

from constants import DATASET_PATH_PATTERN, MODEL_FILEPATH
from utils import get_logger, load_params

STAGE_NAME = 'evaluate'


def evaluate():
    logger = get_logger(logger_name=STAGE_NAME)
    params = load_params(stage_name=STAGE_NAME)

    logger.info('Reading datasets')
    splits = [None, None, None, None]
    for i, split_name in enumerate(['X_train', 'X_test', 'y_train', 'y_test']):
        splits[i] = pd.read_csv(DATASET_PATH_PATTERN.format(split_name=split_name))
    X_train, X_test, y_train, y_test = splits
    logger.info('Datasets loaded')

    logger.info('Loading model')
    if not os.path.exists(MODEL_FILEPATH):
        raise FileNotFoundError('Model file not found')
    model = load(MODEL_FILEPATH)

    logger.info('Computing predictions')
    y_pred = model.predict(X_test)
    y_proba = None
    if hasattr(model, 'predict_proba'):
        y_proba = model.predict_proba(X_test)[:, 1]

    logger.info('Computing metrics')
    metrics = {}
    for metric_name in params['metrics']:
        scorer = get_scorer(metric_name)
        score = scorer(model, X_test, y_test)
        metrics[metric_name] = score
    if y_proba is not None:
        metrics['pr_auc'] = average_precision_score(y_test, y_proba)
    logger.info(f'Metrics: {metrics}')

    artifacts_dir = '/app/artifacts'
    os.makedirs(artifacts_dir, exist_ok=True)

    report = classification_report(y_test, y_pred, output_dict=True)
    with open(f'{artifacts_dir}/classification_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots()
    ax.matshow(cm, cmap=plt.cm.Blues)
    for (i, j), val in np.ndenumerate(cm):
        ax.text(j, i, str(val), ha='center', va='center')
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    fig.savefig(f'{artifacts_dir}/confusion_matrix.png')
    plt.close(fig)

    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        fig, ax = plt.subplots()
        ax.barh(range(len(importances)), importances)
        ax.set_xlabel('Importance')
        fig.savefig(f'{artifacts_dir}/feature_importances.png')
        plt.close(fig)
    elif hasattr(model, 'coef_'):
        coefs = np.abs(model.coef_[0])
        fig, ax = plt.subplots()
        ax.barh(range(len(coefs)), coefs)
        ax.set_xlabel('Coefficient (abs)')
        fig.savefig(f'{artifacts_dir}/feature_importances.png')
        plt.close(fig)

    errors_mask = y_pred != y_test.values.ravel()
    errors_df = pd.DataFrame(X_test[errors_mask])
    errors_df['y_true'] = y_test.values.ravel()[errors_mask]
    errors_df['y_pred'] = y_pred[errors_mask]
    errors_df.to_csv(f'{artifacts_dir}/errors.csv', index=False)

    if y_proba is not None:
        precision, recall, _ = precision_recall_curve(y_test, y_proba)
        fig, ax = plt.subplots()
        ax.plot(recall, precision)
        ax.set_xlabel('Recall')
        ax.set_ylabel('Precision')
        ax.set_title('PR Curve')
        fig.savefig(f'{artifacts_dir}/pr_curve.png')
        plt.close(fig)

    logger.info('Evaluation done')
    return metrics


if __name__ == '__main__':
    evaluate()
