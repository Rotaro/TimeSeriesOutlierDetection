import logging
import json

from dataclasses import dataclass, field
from typing import Dict, List, Any

import outlier_detection as out_det

import numpy as np
import pandas as pd


@dataclass
class Data:
    """Python class for request passed to lambda function."""
    dates: List[str]
    y: List[float]

    ds_format: str
    target_dtype: str

    method: str = "prophet"
    n_iterations: int = 10
    method_kws: Dict[str, Any] = field(default_factory=dict)

    df: pd.DataFrame = None

    @classmethod
    def from_event_obj(cls, event):
        ds_format = event.get("dates_format") or "%Y-%m-%d"
        target_dtype = event.get("target_dtype") or "float"

        return cls(event["dates"], event["target"], ds_format, target_dtype,
                   **({"method": event.get("method")} if "method" in event else {}),
                   method_kws=event.get("method_kws", {}))

    def get_df(self):
        df = pd.DataFrame({"ds": pd.to_datetime(self.dates, format=self.ds_format), "y": self.y})
        df["y"] = df["y"].astype(self.target_dtype)

        return df


def create_test_event(n_datapoints, outlier_frac=0.1, outlier_amplitude=[0.5, 1.3]):
    ds = pd.date_range("2020-01-01", periods=n_datapoints).strftime("%Y-%m-%d").values.tolist()
    target = \
        2 \
        + 0.5 * np.sin(np.arange(n_datapoints) * 2 * np.pi / 7) \
        + np.arange(n_datapoints) * 0.1 \
        + np.random.uniform(-0.35, 0.35, n_datapoints)

    n_outliers = int(n_datapoints * outlier_frac)
    chosen_outliers = np.random.choice(np.arange(n_datapoints), size=n_outliers, replace=False)
    target[chosen_outliers] *= np.random.choice(outlier_amplitude, size=n_outliers)

    return {
        "dates": ds,
        "dates_format": None,
        "target": target.tolist(),
        "target_dtype": None,
        "prophet_kws": {},
        "n_rounds_max": 10
    }, chosen_outliers


def prepare_event(event):
    """Parses event if using lambda proxy integration (=actual payload in event["body"])"""
    lambda_proxy = False
    if "body" in event:
        event = json.loads(event["body"])
        lambda_proxy = True

    return event, lambda_proxy


def prepare_response(response, lambda_proxy):
    """Convert response to proper lambda proxy format.

    https://aws.amazon.com/premiumsupport/knowledge-center/malformed-502-api-gateway/
    """
    if lambda_proxy:
        return {"statusCode": 200, "body": json.dumps(response)}
    else:
        return response


def handler(event, context):
    event, lambda_proxy = prepare_event(event)

    data = Data.from_event_obj(event)
    m, df_pred = out_det.find_outliers(data)

    return prepare_response(
        {
            "dates": event["dates"],
            "prediction": df_pred.yhat.values.tolist(),
            "prediction_upper": df_pred.yhat_upper.values.tolist(),
            "prediction_lower": df_pred.yhat_lower.values.tolist(),
            "outliers": df_pred["outlier"].tolist(),
        },
        lambda_proxy
    )


if __name__ == "__main__":
    event, chosen_outlier = create_test_event(n_datapoints=360, outlier_frac=0.1, outlier_amplitude=[0.5, 1.3])

    data = Data.from_event_obj(event)

    m, df_pred = out_det.find_outliers_prophet(data)
    _, df_pred_lowess = out_det.find_outliers_lowess(data)

    fig = m.plot(df_pred, uncertainty=True)
    data.get_df().iloc[chosen_outlier].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0], label="real outliers",
                                            marker="^", s=45)
    data.get_df().loc[df_pred.outlier].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0],
                                            label="detected outliers - prophet",
                                            marker="x", alpha=0.3, color="red", s=145)
    data.get_df().loc[df_pred_lowess.outlier].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0],
                                                   label="detected outliers - lowess",
                                                   marker="<", alpha=0.3, color="green", s=186)
