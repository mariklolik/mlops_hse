import pandas as pd
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

from constants import DATASET_PATH_PATTERN, MODEL_FILEPATH, RANDOM_STATE
from utils import get_logger, load_params

STAGE_NAME = 'train'

MODEL_CLASSES = {
    'logistic_regression': LogisticRegression,
    'decision_tree': DecisionTreeClassifier,
    'random_forest': RandomForestClassifier,
    'gradient_boosting': GradientBoostingClassifier,
}


def train():
    logger = get_logger(logger_name=STAGE_NAME)
    params = load_params(stage_name=STAGE_NAME)

    logger.info('Reading datasets')
    splits = [None, None, None, None]
    for i, split_name in enumerate(['X_train', 'X_test', 'y_train', 'y_test']):
        splits[i] = pd.read_csv(DATASET_PATH_PATTERN.format(split_name=split_name))
    X_train, X_test, y_train, y_test = splits
    logger.info('Datasets loaded')

    model_type = params.pop('model_type', 'logistic_regression')
    model_class = MODEL_CLASSES[model_type]

    logger.info(f'Creating model: {model_type}')
    params['random_state'] = RANDOM_STATE
    logger.info(f'    Model params: {params}')
    model = model_class(**params)

    logger.info('Training model')
    model.fit(X_train, y_train.values.ravel())

    logger.info('Saving model')
    dump(model, MODEL_FILEPATH)
    logger.info('Done')


if __name__ == '__main__':
    train()
