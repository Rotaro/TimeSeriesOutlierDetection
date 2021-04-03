import sys
import logging
import json

from dataclasses import dataclass, field
from typing import Dict, List, Any

import numpy as np
import fbprophet as fbp
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


def find_outliers_prophet(data):
    """Iteratively find outliers, marking new outliers as np.nan and refitting.

    Outliers are defined as lying outside interval_width of fitted model.
    """
    df = data.get_df()

    outliers = np.zeros(len(df), dtype=bool)
    for i in range(data.n_iterations):
        m = fbp.Prophet(**{"interval_width": 0.99, **data.method_kws})
        m.fit(df)

        df_pred = m.predict(df)
        new_outliers = ((df_pred.yhat_lower > df.y) | (df_pred.yhat_upper < df.y)).values

        if new_outliers.sum() == 0:
            break

        df.loc[outliers, "y"] = np.nan
        outliers |= new_outliers

    return m, df_pred, outliers


def find_outliers_lowess(data):
    """Iteratively find outliers, marking new outliers as np.nan and refitting.

    Outliers: Points which have large residuals compared to nearby (=rolling window) points.
    """
    frac = data.method_kws.get("frac", 1 / 5)
    rolling_window_size = data.method_kws.get("rolling_window_size")
    rolling_window_min_periods = data.method_kws.get("rolling_window_min_periods", 4)
    outlier_n_std = data.method_kws.get("outlier_n_std", 2.5)

    import statsmodels.api as sm
    lowess = sm.nonparametric.lowess

    df = data.get_df()
    df["y_orig"] = df.y
    outliers = np.zeros(len(df), dtype=bool)

    # Minimum requirements for window
    rolling_window_size = rolling_window_size or max(int(frac * len(df)), 2)
    rolling_window_min_periods = min(rolling_window_min_periods, rolling_window_size)

    for i in range(data.n_iterations):
        y_lowess = lowess(df.y, df.ds, frac=frac, return_sorted=False)
        df["res"] = (df.y_orig - y_lowess).abs()

        # Use rolling window to allow for changes in noise level over "time"
        rolling = df.res.rolling(rolling_window_size, min_periods=rolling_window_min_periods, center=True)
        df["res_ma"] = rolling.mean().bfill().ffill()
        df["res_mstd"] = rolling.std().bfill().ffill()

        # Classify datapoints far from rolling mean as outliers
        new_outliers = (df.res - df.res_ma).abs() > outlier_n_std * df.res_mstd

        if new_outliers.sum() == 0:
            break

        outliers |= new_outliers
        df["y"] = df.y_orig
        df.loc[outliers, "y"] = np.nan

    df["yhat"] = y_lowess
    df["yhat_upper"] = df.yhat + outlier_n_std * np.abs(df.res_mstd)
    df["yhat_lower"] = (df.yhat - outlier_n_std * np.abs(df.res_mstd))

    # Interpolation for outliers
    is_nan, is_not_nan = np.isnan(y_lowess), ~np.isnan(y_lowess)
    x = np.arange(len(df))
    for col in ("yhat", "yhat_upper", "yhat_lower"):
        df[col] = np.interp(x, x[is_not_nan], df[col][is_not_nan])

    # Cleanup
    df.drop(columns=["y_orig", "res", "res_ma", "res_mstd"], inplace=True)

    return None, df, outliers


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

    if data.method == "prophet":
        m, df_pred, outliers = find_outliers_prophet(data)
    elif data.method == "lowess":
        m, df_pred, outliers = find_outliers_lowess(data)
    else:
        raise ValueError("Invalid method (%s)!" % data.method)

    return prepare_response(
        {
            "dates": event["dates"],
            "prediction": df_pred.yhat.values.tolist(),
            "prediction_upper": df_pred.yhat_upper.values.tolist(),
            "prediction_lower": df_pred.yhat_lower.values.tolist(),
            "outliers": outliers.tolist(),
        },
        lambda_proxy
    )


def create_test_event(n_datapoints, outliers_frac=0.1, outlier_amplitude=[0.5, 1.3]):
    ds = pd.date_range("2020-01-01", periods=n_datapoints).strftime("%Y-%m-%d").values.tolist()
    target = \
        2 \
        + 0.5 * np.sin(np.arange(n_datapoints) * 2 * np.pi / 7) \
        + np.arange(n_datapoints) * 0.1 \
        + np.random.uniform(-0.35, 0.35, n_datapoints)

    n_outliers = int(n_datapoints * outliers_frac)
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


if __name__ == "__main__":
    n_datapoints = 360
    event, chosen_outliers = create_test_event(n_datapoints, 0.1, [0.5, 1.3])

    data = Data.from_event_obj(event)

    m, df_pred, outliers = find_outliers_prophet(data)
    _, df_pred_lowess, outliers_lowess = find_outliers_lowess(data)
    
    fig = m.plot(df_pred, uncertainty=True)
    data.get_df().iloc[chosen_outliers].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0], label="real outliers",
                                             marker="^", s=45)
    data.get_df().loc[outliers].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0], label="detected outliers",
                                     marker="x", alpha=0.3, color="red", s=145)
    data.get_df().loc[outliers_lowess].plot("ds", "y", kind="scatter", ax=fig.get_axes()[0], label="detected outliers 2",
                                            marker="<", alpha=0.3, color="green", s=186)