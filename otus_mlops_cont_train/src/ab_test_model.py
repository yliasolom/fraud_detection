import logging
import os
import warnings

import mlflow
import numpy as np
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import SparkSession
from scipy.stats import ttest_ind

from train import clean_data, data_prep_pipeline

warnings.filterwarnings(action='ignore', category=DeprecationWarning)

from dotenv import load_dotenv
load_dotenv()

EXPERIMENT_NAME = 'fraud-classification_AB'


def generate_bootstrap_samples(data, n_iterations=100, sample_fraction=0.5):
    samples = []
    for _ in range(n_iterations):
        samples.append(data.sample(withReplacement=True, fraction=sample_fraction))
    return samples


def calculate_metrics(model, samples):
    evaluator = BinaryClassificationEvaluator(labelCol="fraud", metricName="areaUnderROC")
    metrics = []

    for sample in samples:
        predictions = model.transform(sample)
        auc = evaluator.evaluate(predictions)
        metrics.append(auc)

    return metrics


def perform_ab_test(metrics_a, metrics_b, logger):
    # Это указывает на то, что гипотеза 𝐻1 предполагает, что метрика группы A лучше метрики группы B
    t_stat, p_value = ttest_ind(metrics_a, metrics_b, alternative='greater')
    alpha = 0.05

    if p_value > alpha:
        logger.info(
            f'Alpha = {alpha} - The performance of the model on Group A and Group B data is not significantly different.')
    else:
        logger.info(
            f'Alpha = {alpha} - There is a significant difference in the model performance on Group A and Group B data.')

    if np.mean(metrics_a) > np.mean(metrics_b):
        logger.info("The model performs better on Group A data (current test set).")
    else:
        logger.info("The model performs better on Group B data (new test set).")

    logger.info(f"A/B Test completed: t_stat={t_stat}, p_value={p_value}, "
                f"auc metrics_a: {np.mean(metrics_a)}, auc metrics_b: {np.mean(metrics_b)}")

    return t_stat, p_value


def load_model_from_mlflow(model_name):
    model_uri = f"models:/{model_name}/latest"
    model = mlflow.spark.load_model(model_uri)
    return model


def log_results_to_mlflow(ab_results, bootstrap_results, test_params):
    with mlflow.start_run():
        mlflow.log_params(test_params)
        mlflow.log_metrics({
            "t_stat": ab_results["t_stat"],
            "p_value": ab_results["p_value"]
        })
        mlflow.log_dict(bootstrap_results, "bootstrap_results.json")


def main(data_path_ab_test, mlflow_uri, model_name):
    logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
    logger = logging.getLogger()

    logger.info("Creating Spark Session ...")
    spark = SparkSession \
        .builder \
        .appName('Spark ML A/B test') \
        .config('spark.sql.repl.eagerEval.enabled', True) \
        .getOrCreate()

    mlflow.set_experiment(EXPERIMENT_NAME)
    mlflow.set_tracking_uri(mlflow_uri)

    logger.info(f"Loading model from MLflow: {model_name} ...")
    model = load_model_from_mlflow(model_name)

    logger.info(f"Reading data from {data_path_ab_test} ...")
    df = spark.read.text(f"{data_path_ab_test}/*.txt")

    df = df.sample(fraction=0.01)

    df = clean_data(df)

    dataproc = data_prep_pipeline()
    ready_data = dataproc.fit(df).transform(df)

    bootstrap_samples_a = generate_bootstrap_samples(ready_data)

    bootstrap_samples_b = generate_bootstrap_samples(ready_data)

    metrics_a = calculate_metrics(model, bootstrap_samples_a)

    metrics_b = calculate_metrics(model, bootstrap_samples_b)

    logger.info("Performing A/B testing ...")
    t_stat, p_value = perform_ab_test(metrics_a, metrics_b, logger)

    log_results_to_mlflow(
        ab_results={"t_stat": t_stat, "p_value": p_value},
        bootstrap_results={"metrics_a": metrics_a, "metrics_b": metrics_b},
        test_params={"model_name": "fraud_model"}
    )
    logger.info("Results successfully logged to MLflow.")

    spark.stop()


if __name__ == "__main__":
    main(data_path_ab_test=os.environ['DATA_PATH'],
         mlflow_uri=os.environ['MLFLOW_TRACKING_URI'],
         model_name=os.environ['MODEL_NAME_MLFLOW'])
