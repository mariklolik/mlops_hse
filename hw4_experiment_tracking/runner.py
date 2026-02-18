import mlflow

from constants import MLFLOW_TRACKING_URI, EXPERIMENT_NAME
from scripts import evaluate, process_data, train
from utils import load_params


def run():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    process_data_params = load_params('process_data')
    train_params = load_params('train')

    with mlflow.start_run():
        mlflow.log_params({
            'features': str(process_data_params['features']),
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

        mlflow.log_artifacts('/app/artifacts')

        mlflow.log_artifact('/app/data/X_train.csv', 'datasets')
        mlflow.log_artifact('/app/data/y_train.csv', 'datasets')

        mlflow.sklearn.log_model(
            sk_model=__import__('joblib').load('/app/model.joblib'),
            artifact_path='model',
        )


if __name__ == '__main__':
    run()
