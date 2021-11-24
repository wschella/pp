import colorsys
from typing import *

from matplotlib.figure import Figure
import pandas as pd
import numpy as np
import sklearn.metrics as metrics
import matplotlib.pyplot as plt


def prediction_to_label(prediction) -> int:
    return np.argmax(prediction, axis=1)[0]


def lighten(rgb, scale):
    # convert rgb to hls
    h, l, s = colorsys.rgb_to_hls(*rgb[:-1])
    # manipulate h, l, s values and return as rgb
    return colorsys.hls_to_rgb(h, min(1, l * scale), s=s)


def plot_assessor_class_wise_aggregation(df: pd.DataFrame) -> Figure:
    fig, ax = plt.subplots()

    asss_acc = metrics.accuracy_score(df.syst_pred_score, df.asss_prediction.map(lambda p: p > 0.5))
    syst_acc = metrics.accuracy_score(df.inst_target, df.syst_prediction.map(prediction_to_label))

    asss_class_accs = []
    syst_class_accs = []
    class_support = []
    for target in np.sort(df.inst_target.unique()):
        selected = df.loc[df.inst_target == target]
        asss_class_accs.append(
            metrics.accuracy_score(
                selected.syst_pred_score,
                selected.asss_prediction.map(lambda p: p > 0.5)))

        syst_class_accs.append(
            metrics.accuracy_score(
                selected.inst_target,
                selected.syst_prediction.map(prediction_to_label)))

        class_support.append(len(selected))

    labels = np.sort(df.inst_target.unique())
    x = np.arange(len(labels))
    width = 0.35

    syst_bar = ax.bar(x - width / 2, syst_class_accs, width, label="System Avg.")
    asss_bar = ax.bar(x + width / 2, asss_class_accs, width, label="Assessor")

    ax.axhline(y=syst_acc, ls="dashed", lw=3, c=lighten(syst_bar.patches[0].get_facecolor(), 0.8))
    ax.axhline(y=asss_acc, ls="dashed", lw=3, c=lighten(asss_bar.patches[0].get_facecolor(), 0.8))

    ax.set_title("Class Wise Aggregation")
    ax.set_xlabel("Class")
    ax.set_ylabel("Accuracy")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    return fig


class CalibrationInfo(TypedDict):
    bins: Any


class CalibrationBin(TypedDict):
    avg_prob: float
    avg_acc: float
    count: int


def assessor_calibration_info(df: pd.DataFrame, n_bins: int = 10) -> Dict[str, Any]:
    # report threshold bigger than 0
    probabilities = df.asss_prediction
    y_true = df.syst_pred_score
    y_pred = probabilities.map(lambda p: p[0] > 0.5)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.digitize(probabilities, bins, right=True)

    bins = []
    for b in range(n_bins):
        selected = np.where(indices == b + 1)[0]
        if len(selected) > 0:
            bins.append({
                "avg_prob": np.mean(probabilities[selected]),
                "avg_acc": np.mean(y_true[selected] == y_pred[selected]),
                "count": len(selected)
            })

    return {
        "bins": bins,
    }


def plot_assessor_prob_histogram(df: pd.DataFrame, n_bins: int = 20, draw_averages: bool = True) -> Figure:
    # render average confidence
    # render average accuracy
    # render bin
    probabilities = df.asss_prediction

    bin_size = 1.0 / n_bins
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.digitize(probabilities, bins, right=True)

    counts = np.zeros(n_bins)
    for b in range(n_bins):
        selected = np.where(indices == b + 1)[0]
        if len(selected) > 0:
            counts[b] = len(selected)

    fig = plt.figure()
    ax = fig.add_subplot()
    ax.set_title("Probability Histogram")
    ax.set_xlabel("Probability")
    ax.set_ylabel("Count")
    ax.bar(
        x=bins[:-1] + bin_size / 2.0,  # type: ignore
        height=counts,
        width=bin_size,
    )
    if draw_averages:
        avg_conf = np.mean(probabilities)
        conf_plt = ax.axvline(x=avg_conf, ls="dotted", lw=3,
                              c="#444", label="Avg. probability")
        ax.legend(handles=[conf_plt])

    return fig
