from typing import *
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
import csv
import os

import click
import pandas as pd

import tensorflow as tf
from tensorflow.python.data.ops.dataset_ops import Dataset as TFDataset

from assessors.core import ModelDefinition, TFDatasetWrapper, CustomDataset, PredictionRecord
from assessors.cli.shared import CommandArguments, get_model_def, get_assessor_def
from assessors.cli.cli import cli, CLIArgs
from assessors.core.datasets import AssessorPredictionRecord
from assessors.utils import dataset_extra as dse


@dataclass
class EvaluateBaseArgs(CommandArguments):
    parent: CLIArgs = CLIArgs()
    dataset: str = "mnist"
    model: str = "default"

    def validate(self):
        self.parent.validate()
        self.validate_option('dataset', ["mnist", "cifar10"])
        self.validate_option('model', ["default"])


@cli.command(name='eval-base')
@click.argument('dataset')
@click.option('-m', '--model', default='default', help="The model variant to train")
@click.pass_context
def evaluate_base(ctx, **kwargs):
    args = EvaluateBaseArgs(parent=ctx.obj, **kwargs).validated()
    dataset = TFDatasetWrapper(args.dataset)
    (_train, test) = itemgetter('train', 'test')(dataset.load())

    model_path = Path(f"artifacts/models/mnist/base")
    model_def: ModelDefinition = get_model_def(args.dataset, args.model)()
    model = model_def.try_restore_from(model_path)

    model.evaluate(test)

# ---------------------------------------------------------------------


@dataclass
class EvaluateAssessorArgs(CommandArguments):
    parent: CLIArgs = CLIArgs()
    dataset: Path = Path("artifacts/datasets/mnist/kfold/")
    test_size: int = 10000
    output_path: Path = Path("./results.csv")
    overwrite: bool = False
    model: str = "mnist_default"

    def validate(self):
        self.parent.validate()
        self.validate_option('model', ["mnist_default", "mnist_prob"])


@cli.command(name='eval-assessor')
@click.argument('dataset', type=click.Path(exists=True, file_okay=False))
@click.option('-o', '--output-path', default="./results.csv", help="The output path")
@click.option('--overwrite', is_flag=True, help="Overwrite the output file if it exists", default=False)
@click.option('-m', '--model', default='mnist_default', help="The model to evaluate")
@click.pass_context
def evaluate_assessor(ctx, **kwargs):
    # Handle CLI args
    args = EvaluateAssessorArgs(parent=ctx.obj, **kwargs).validated()
    if os.path.exists(args.output_path) and not args.overwrite:
        click.confirm(f"The file {args.output_path} already exists. Overwrite?", abort=True)

    # Load assessor model
    [dataset_name, model_name] = args.model.split('_')
    model_def: ModelDefinition = get_assessor_def(dataset_name, model_name)()
    model_path = Path(f"artifacts/models/{dataset_name}/{model_name}/assessor/")
    model = model_def.try_restore_from(model_path)
    if model is None:
        raise click.UsageError(f"Could not load model {args.model} at {model_path}")

    # Load & mangle dataset
    dataset: TFDataset[PredictionRecord] = CustomDataset(path=args.dataset).load_all()

    def to_supervised(record: PredictionRecord):
        return (record['inst_features'], record['syst_pred_score'])
    supervised = dataset.map(to_supervised)
    (_train, test) = dse.split_absolute(supervised, -args.test_size)

    # Evaluate and log
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    with open(args.output_path, "w") as f:
        fieldnames = list(AssessorPredictionRecord.__annotations__.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        asss_predictions = model.predict_all(test)

        for record, asss_pred in zip(dataset.as_numpy_iterator(), asss_predictions):
            record: PredictionRecord = record
            record.pop('inst_features')

            record: AssessorPredictionRecord = record
            record["asss_prediction"] = asss_pred
            record["asss_pred_loss"] = int(model.loss(record['syst_pred_score'], asss_pred))
            writer.writerow(record)
    print(f"Wrote results to {args.output_path}")

    # Print some simple results
    with open(args.output_path, 'r', newline='') as csvfile:
        df = pd.read_csv(csvfile)
        print(df.describe())