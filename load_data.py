import json
import os
from typing import Iterator

import polars as pl

DATASET_FILES = {
    'train': "data/QuALITY.v1.0.1/QuALITY.v1.0.1.htmlstripped.train",
    # 'test': "data/QuALITY.v1.0.1/QuALITY.v1.0.1.htmlstripped.test",
    'dev': "data/QuALITY.v1.0.1/QuALITY.v1.0.1.htmlstripped.dev",
}

PARSED_DATA_DIR = "data/parsed_data"


class Dataset:
    def __init__(self):
        if not os.path.exists(PARSED_DATA_DIR):
            os.makedirs(PARSED_DATA_DIR)
            article_data, question_data = load_data()
            article_data.write_csv(os.path.join(PARSED_DATA_DIR, "article_data.csv"))
            question_data.write_csv(os.path.join(PARSED_DATA_DIR, "question_data.csv"))
        else:
            article_data = pl.read_csv(os.path.join(PARSED_DATA_DIR, "article_data.csv"))
            question_data = pl.read_csv(os.path.join(PARSED_DATA_DIR, "question_data.csv"))

        self.article_data = article_data
        self.question_data = question_data

    def __iter__(self) -> Iterator[tuple[str, str, list[str]]]:
        for question in self.question_data.iter_rows():
            article = self.article_data.filter(pl.col("article_id") == question[0]).select(pl.col("article")).item()
            yield article, question[1], question[2], question[3]


def load_dataset(path: str | os.PathLike[str]) -> tuple[pl.DataFrame, pl.DataFrame]:
    # Questions filter from original paper:
    # 1. 100% of untimed annotators chose the correct answer
    # 2. Less than 50% of timed annotators chose the correct answer
    # 3. All untimed annotators agree that the question is answerable and unambiguous
    # 4. Average "context required" rating from untimed annotators is at least 1.5
    # 5. Writer label matches the gold label
    # 6. Compatible with 2-answer requirement

    # For each question, we used the correct answer and the best ”distractor” answer. We removed questions that were
    # incompatible with our 2-answer requirement, e.g. questions where one answer was ”all of the above”,
    # ”none of the above”, etc.

    with open(path, 'r') as f:
        data = list(map(json.loads, f.readlines()))
        data = pl.from_dicts(data)

    article_data = data.select(
        pl.col("article_id").cast(pl.Int64),
        pl.col("article"),
    ).unique()

    questions_data = data.select(
        pl.col("article_id").cast(pl.Int64),
        pl.col("questions").list.eval(
            pl.element().struct.field("question")
        ).alias("question"),
        *[pl.col("questions").list.eval(
            pl.element().struct.field("options").list.get(i),
            parallel=True
        ).alias(f"option_{i}") for i in range(4)],
        pl.col("questions").list.eval(
            pl.element().struct.field("gold_label"),
        ).alias("correct_answer_id"),
        pl.col("questions").list.eval(
            pl.element().struct.field("writer_label"),
        ).alias("writer_label"),
        pl.col("questions").list.eval(
            pl.element().struct.field("validation").list.eval(
                pl.element().struct.field("untimed_answer")
            )
        ).alias("untimed_answers"),
        pl.col("questions").list.eval(
            pl.element().struct.field("validation").list.eval(
                pl.element().struct.field("untimed_eval1_answerability")
            )
        ).alias("is_answerable"),
        pl.col("questions").list.eval(
            pl.element().struct.field("validation").list.eval(
                pl.element().struct.field("untimed_eval2_context")
            )
        ).alias("is_context_needed"),
        pl.col("questions").list.eval(
            pl.element().struct.field("validation").list.eval(
                pl.element().struct.field("untimed_best_distractor")
            )
        ).alias("best_distractor"),
        pl.col("questions").list.eval(
            pl.element().struct.field("speed_validation").list.eval(
                pl.element().struct.field("speed_answer")
            ),
        ).alias("speed_validation"),
    ).explode(pl.all().exclude("article_id"))

    # writer label matches the gold label
    questions_data = questions_data.filter(
        pl.col("correct_answer_id") == pl.col("writer_label"),
    ).drop("writer_label")

    # 100% of untimed annotators chose correct answer
    questions_data = questions_data.filter(
        pl.col("untimed_answers").list.unique().list.len() == 1
    ).drop("untimed_answers")

    # all untimed annotators agree that the question is unambiguous and answerable
    questions_data = questions_data.filter(
        pl.col("is_answerable").list.eval(
            pl.element() == 1
        ).list.sum() == 3
    ).drop("is_answerable")

    # avg "context required" rating from untimed annotators is at least 1.5
    questions_data = questions_data.filter(
        pl.col("is_context_needed").list.sum() >= 4.5
    ).drop("is_context_needed")

    # filter <50% chose correct answer for speed speed_validation
    questions_data = questions_data.filter(
        pl.col("speed_validation").list.concat(pl.col("correct_answer_id")).list.eval(
            pl.element() == pl.col("").last()
        ).list.sum() < 4,
    ).drop("speed_validation")

    # TODO: get the best distractor id from untimed answers
    questions_data = questions_data.with_columns(
        pl.col("best_distractor").list.eval(
            pl.element().value_counts().struct.rename_fields(["value", "count"])
        ).list.eval(
            pl.struct(
                pl.element().struct.field("count"),
                pl.element().struct.field("value")
            )
        ).list.sort(descending=True).list.first().struct.field("value").alias("best_distractor_id")
    ).drop("best_distractor")

    # get the best distractor id from timed answers
    # questions_data = questions_data.with_columns(
    #     pl.col("speed_validation").list.eval(
    #         pl.element().value_counts().struct.rename_fields(["value", "count"])
    #     ).list.concat(
    #         pl.col("correct_answer_id")
    #     ).list.eval(
    #         # filter correct answer
    #         pl.when(
    #             pl.element().struct.field("value") != pl.col("").last().struct.field("value")
    #         ).then(pl.element())
    #     ).list.drop_nulls().list.eval(
    #         # reorder as list gets sorted by first struct field
    #         pl.struct(
    #             pl.element().struct.field("count"),
    #             pl.element().struct.field("value"),
    #         )
    #     ).list.sort(descending=True).list.first().struct.field("value").alias("best_distractor_id"),
    # ).drop("speed_validation").drop_nulls()

    questions_data = questions_data.with_columns(
        pl.col("correct_answer_id") - 1,
        pl.col("best_distractor_id") - 1,
    )

    # filter for incompatible answers
    # t = pl.concat([questions_data.select(pl.col(f"option_{i}").alias("options")) for i in range(4)]).unique().filter(
    #     pl.col("options").str.to_lowercase().str.contains("above")
    # )

    # only return the options for best_distractor and correct_answer
    questions_data = questions_data.select(
        pl.col("article_id"),
        pl.col("question"),
        pl.concat_list(
            [pl.col(f"option_{i}") for i in range(4)]
        ).list.get(pl.col("correct_answer_id")).alias("correct_answer"),
        pl.concat_list(
            [pl.col(f"option_{i}") for i in range(4)]
        ).list.get(pl.col("best_distractor_id")).alias("false_answer"),
    )

    return article_data, questions_data


def load_data() -> tuple[pl.DataFrame, pl.DataFrame]:
    article_datasets = []
    question_datasets = []

    for dataset_type, dataset_path in DATASET_FILES.items():
        article_dataset, question_dataset = load_dataset(dataset_path)
        article_datasets.append(article_dataset)
        question_datasets.append(question_dataset)

    article_dataset = pl.concat(article_datasets).unique()
    question_dataset = pl.concat(question_datasets).unique()

    article_dataset = article_dataset.filter(
        pl.col("article_id").is_in(question_dataset.select(pl.col("article_id")).unique())
    )

    return article_dataset, question_dataset
