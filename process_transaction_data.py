import os
import findspark
import argparse
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import FloatType
from pyspark.sql.types import FloatType, DateType, IntegerType

findspark.init()


def create_spark_session(app_name="OTUS-PySpark-Notebook", executor_memory="4g", driver_memory="4g"):
    return (
        SparkSession
        .builder
        .appName(app_name)
        .config("spark.dynamicAllocation.enabled", "true")
        .config("spark.executor.memory", executor_memory)
        .config("spark.driver.memory", driver_memory)
        .getOrCreate()
    )


def load_data(data_path):
    all_files = [os.path.join(data_path, f) for f in os.listdir(data_path) if f.endswith(".txt")]
    return spark.read.text(all_files)


def preprocess_data(df):
    """
    Предобрабатывает данные транзакций, удаляя пустые строки и строки с комментариями,
    разбивая данные на колонки и заполняя пропуски медианами.

    Args:
        df (DataFrame): Входной DataFrame с данными транзакций.

    Returns:
        DataFrame: Обработанный DataFrame с заполненными пропусками.
    """
    print('============= preprocessing data =============')
    df = df.na.drop(how="all")
    df = df.filter(~df.value.startswith("#"))

    columns = ["transaction_id", "tx_datetime", "customer_id", "terminal_id",
               "tx_amount", "tx_time_seconds", "tx_time_days", "tx_fraud", "tx_fraud_scenario"]
    df = df.selectExpr("split(value, ',') as columns")
    df = df.selectExpr(*[f"columns[{i}] as {col}" for i, col in enumerate(columns)])

    df = df.withColumn("transaction_id", F.col("transaction_id").cast(IntegerType())) \
        .withColumn("customer_id", F.col("customer_id").cast(IntegerType())) \
        .withColumn("terminal_id", F.col("terminal_id").cast(IntegerType())) \
        .withColumn("tx_datetime", F.to_date("tx_datetime")) \
        .withColumn("tx_amount", F.col("tx_amount").cast(FloatType())) \
        .withColumn("tx_time_seconds", F.col("tx_time_seconds").cast(FloatType())) \
        .withColumn("tx_time_days", F.col("tx_time_days").cast(FloatType())) \
        .withColumn("tx_fraud", F.col("tx_fraud").cast(IntegerType())) \
        .withColumn("tx_fraud_scenario", F.col("tx_fraud_scenario").cast(IntegerType()))

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process transaction data.")
    parser.add_argument("--data_path", type=str, required=True, help="Путь к входной директории.")
    parser.add_argument("--output_path", type=str, required=True, help="Путь для сохранения предобработанного файла ")

    args = parser.parse_args()

    spark = create_spark_session()
    raw_data = load_data(args.data_path)
    cleaned_df = preprocess_data(raw_data)

    cleaned_df.coalesce(1).write.mode("overwrite").parquet(args.output_path)
    print('=============  preprocess data saved: ============= ', args.output_path)
    spark.stop()