import os
import shutil
import yaml

import mlflow
from joblib import load as joblib_load

from constants import MLFLOW_TRACKING_URI, EXPERIMENT_NAME
from scripts.process_data import process_data
from scripts.train import train
from scripts.evaluate import evaluate
from utils import get_logger

logger = get_logger('run_experiments')


EXPERIMENTS = [
    {
        'name': 'logreg_l2_1k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 1000,
        },
        'train': {
            'model_type': 'logistic_regression',
            'penalty': 'l2',
            'C': 1.0,
            'solver': 'lbfgs',
            'max_iter': 1000,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'logreg_l2_3k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 3000,
        },
        'train': {
            'model_type': 'logistic_regression',
            'penalty': 'l2',
            'C': 1.0,
            'solver': 'lbfgs',
            'max_iter': 1000,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'logreg_l2_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'logistic_regression',
            'penalty': 'l2',
            'C': 1.0,
            'solver': 'lbfgs',
            'max_iter': 1000,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'logreg_l2_10k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 10000,
        },
        'train': {
            'model_type': 'logistic_regression',
            'penalty': 'l2',
            'C': 1.0,
            'solver': 'lbfgs',
            'max_iter': 1000,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'decision_tree_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'decision_tree',
            'max_depth': 5,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'random_forest_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'random_forest',
            'n_estimators': 100,
            'max_depth': 10,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gradient_boosting_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 100,
            'max_depth': 3,
            'learning_rate': 0.1,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gb_lr01_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.01,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gb_lr05_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.05,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gb_lr1_5k',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'occupation',
                         'race', 'sex'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.1,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gb_few_features',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'hours.per.week'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.1,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
    {
        'name': 'gb_all_features',
        'process_data': {
            'features': ['age', 'education.num', 'capital.gain', 'capital.loss',
                         'hours.per.week', 'workclass', 'education', 'marital.status',
                         'occupation', 'relationship', 'race', 'sex', 'native.country'],
            'train_size': 5000,
        },
        'train': {
            'model_type': 'gradient_boosting',
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.1,
        },
        'evaluate': {'metrics': ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']},
    },
]


def write_params(stage_name, params):
    filepath = f'/app/params/{stage_name}.yaml'
    with open(filepath, 'w') as f:
        yaml.dump({'params': params}, f, default_flow_style=False, allow_unicode=True)


def run_single(exp_config):
    write_params('process_data', exp_config['process_data'])
    write_params('train', exp_config['train'])
    write_params('evaluate', exp_config['evaluate'])

    process_data_params = exp_config['process_data']
    train_params = exp_config['train']

    with mlflow.start_run(run_name=exp_config['name']):
        mlflow.log_params({
            'features': str(process_data_params['features']),
            'num_features': len(process_data_params['features']),
            'train_size': process_data_params.get('train_size', 'full'),
            'model_type': train_params.get('model_type', 'logistic_regression'),
        })
        for k, v in train_params.items():
            if k != 'model_type':
                mlflow.log_param(f'model_{k}', v)

        process_data()
        train()
        metrics = evaluate()

        if metrics:
            mlflow.log_metrics(metrics)

        artifacts_dir = '/app/artifacts'
        if os.path.isdir(artifacts_dir):
            mlflow.log_artifacts(artifacts_dir)

        mlflow.log_artifact('/app/data/X_train.csv', 'datasets')
        mlflow.log_artifact('/app/data/y_train.csv', 'datasets')

        model = joblib_load('/app/model.joblib')
        mlflow.sklearn.log_model(model, artifact_path='model')

    for d in ['/app/artifacts', '/app/data']:
        if os.path.isdir(d):
            shutil.rmtree(d)
    if os.path.exists('/app/model.joblib'):
        os.remove('/app/model.joblib')


def main():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    for i, exp in enumerate(EXPERIMENTS):
        logger.info(f'Running experiment {i+1}/{len(EXPERIMENTS)}: {exp["name"]}')
        run_single(exp)
        logger.info(f'Experiment {exp["name"]} done')


if __name__ == '__main__':
    main()
