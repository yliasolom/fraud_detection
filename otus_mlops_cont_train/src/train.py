import logging
import os

import mlflow
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import month, dayofmonth, dayofweek, hour, minute
from pyspark.sql.types import FloatType

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logger = logging.getLogger()

import warnings
warnings.filterwarnings(action='ignore', category=DeprecationWarning)

from dotenv import load_dotenv
load_dotenv()

URI = os.environ['MLFLOW_TRACKING_URI']

EXPERIMENT_NAME = 'fraud-classification'
MODEL_NAME_MLFLOW = "fraud-detection_v1"


def clean_data(df):
    df = df.na.drop(how="all")
    df = df.filter(~df.value.startswith("#"))

    columns = ["transaction_id", "tx_datetime", "customer_id", "terminal_id",
               "tx_amount", "tx_time_seconds", "tx_time_days", "tx_fraud", "tx_fraud_scenario"]

    columns_to_cast = ["tx_amount", "tx_time_seconds", "tx_time_days", "tx_fraud"]

    df = df.selectExpr("split(value, ',') as columns")
    df = df.selectExpr(*[f"columns[{i}] as {col}" for i, col in enumerate(columns)])

    for column in columns_to_cast:
        df = df.withColumn(column, F.col(column).cast(FloatType()))

    columns_to_rename = {cl: cl.replace('tx_', '') for cl in df.columns if cl.startswith('tx_')}
    for old_col, new_col in columns_to_rename.items():
        df = df.withColumnRenamed(old_col, new_col)

    df = df.withColumn('month', month(F.col('datetime')).cast('float')) \
        .withColumn('day', dayofmonth(F.col('datetime')).cast('float')) \
        .withColumn('day_of_week', dayofweek(F.col('datetime')).cast('float')) \
        .withColumn('hour', hour(F.col('datetime')).cast('float')) \
        .withColumn('minute', minute(F.col('datetime')).cast('float'))

    df = df.na.drop()
    df = df.withColumn('fraud', F.col('fraud').cast('float'))

    return df


def data_prep_pipeline():
    TRAIN_COLUMNS = [
                'amount',
                'month',
                'day',
                'day_of_week',
                'minute'
    ]

    assembler = VectorAssembler(
        inputCols=TRAIN_COLUMNS,
        outputCol='Features'
    )

    scaler = StandardScaler(
        inputCol='Features',
        outputCol='ScaledFeatures'
    )

    dataproc = Pipeline(stages=[
        assembler, scaler
    ])

    return dataproc


def main(data_path):
    logger.info("Creating Spark Session ...")

    spark = SparkSession \
        .builder \
        .appName('Spark ML Research') \
        .config('spark.sql.repl.eagerEval.enabled', True) \
        .getOrCreate()

    mlflow.set_experiment(EXPERIMENT_NAME)
    mlflow.set_tracking_uri(URI)

    df = spark.read.text(f"{data_path}/*.txt")
    # todo
    df = df.sample(fraction=0.01)

    df = clean_data(df)

    dataproc = data_prep_pipeline()

    ready_data = dataproc.fit(df).transform(df)

    train_data, test_data = ready_data.randomSplit([.7, .3])

    lr = LogisticRegression() \
        .setMaxIter(10) \
        .setRegParam(1.5) \
        .setFeaturesCol('ScaledFeatures') \
        .setLabelCol('fraud')

    model = lr.fit(train_data)

    evaluator = BinaryClassificationEvaluator(labelCol="fraud", metricName="areaUnderROC")
    auc = evaluator.evaluate(model.transform(test_data))

    with mlflow.start_run() as run:
        mlflow.spark.log_model(model, artifact_path="models", registered_model_name=MODEL_NAME_MLFLOW)
        mlflow.log_metric("auc", auc)
        print(f"Saved/registered in Run ID: {run.info.run_id} with auc: {auc}")
        mlflow.end_run()

    spark.stop()


if __name__ == "__main__":
    main(data_path=os.environ['DATA_PATH'])