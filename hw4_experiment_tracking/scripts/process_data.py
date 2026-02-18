import os

import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

from constants import DATASET_NAME, DATASET_PATH_PATTERN, TEST_SIZE, RANDOM_STATE
from utils import get_logger, load_params

STAGE_NAME = 'process_data'


def process_data():
    logger = get_logger(logger_name=STAGE_NAME)
    params = load_params(stage_name=STAGE_NAME)

    logger.info('Downloading data')
    dataset = load_dataset(DATASET_NAME)
    logger.info('Data downloaded')

    logger.info('Preprocessing data')
    df = dataset['train'].to_pandas()
    columns = params['features']
    target_column = 'income'
    X, y = df[columns], df[target_column]
    logger.info(f'    Features: {columns}')

    all_cat_features = [
        'workclass', 'education', 'marital.status', 'occupation', 'relationship',
        'race', 'sex', 'native.country',
    ]
    cat_features = [c for c in columns if c in all_cat_features]
    num_features = [c for c in columns if c not in all_cat_features]

    preprocessor = OrdinalEncoder()
    feature_names = num_features + cat_features
    X_transformed = np.hstack([X[num_features], preprocessor.fit_transform(X[cat_features])])
    y_transformed: pd.Series = (y == '>50K').astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X_transformed, y_transformed, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    train_size = params.get('train_size')
    if train_size and train_size < len(X_train):
        X_train = X_train[:train_size]
        y_train = y_train.iloc[:train_size] if hasattr(y_train, 'iloc') else y_train[:train_size]

    logger.info(f'    Train size: {len(y_train)}')
    logger.info(f'    Test size: {len(y_test)}')

    logger.info('Saving datasets')
    os.makedirs(os.path.dirname(DATASET_PATH_PATTERN), exist_ok=True)
    for split, split_name in zip(
        (X_train, X_test, y_train, y_test),
        ('X_train', 'X_test', 'y_train', 'y_test'),
    ):
        df = pd.DataFrame(split, columns=feature_names if 'X' in split_name else None)
        df.to_csv(DATASET_PATH_PATTERN.format(split_name=split_name), index=False)
    logger.info('Datasets saved')


if __name__ == '__main__':
    process_data()
