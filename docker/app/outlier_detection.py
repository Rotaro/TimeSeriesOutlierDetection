import numpy as np
import fbprophet as fbp
import statsmodels.api as sm


def find_outliers_prophet(data):
    """Iteratively find outliers, excluding new outliers and refitting.

    Outlier: point lying outside interval_width of fitted model.

    :param data: Data.
    """
    df = data.get_df()

    outlier = np.zeros(len(df), dtype=bool)
    for i in range(data.n_iterations):
        m = fbp.Prophet(**{"interval_width": 0.99, **data.method_kws})
        m.fit(df)

        df_pred = m.predict(df)
        new_outlier = ((df_pred.yhat_lower > df.y) | (df_pred.yhat_upper < df.y)).values

        if new_outlier.sum() == 0:
            break

        df.loc[outlier, "y"] = np.nan
        outlier |= new_outlier

    df_pred["outlier"] = outlier

    return m, df_pred


def find_outliers_lowess(data):
    """Iteratively find outliers, excluding new outliers and refitting.

    Outlier: Point which has large residual compared to nearby (=rolling window) points.

    :param data: Data.
    """
    frac = data.method_kws.get("frac", 1 / 5)

    rolling_window_size = data.method_kws.get("rolling_window_size")
    rolling_window_min_periods = data.method_kws.get("rolling_window_min_periods", 4)

    # Minimum requirements for window
    rolling_window_size = rolling_window_size or max(int(frac * len(data.y)), 2)
    rolling_window_min_periods = min(rolling_window_min_periods, rolling_window_size)

    outlier_n_std = data.method_kws.get("outlier_n_std", 2.5)


    lowess = sm.nonparametric.lowess

    df = data.get_df()
    df["y_orig"] = df.y
    outlier = np.zeros(len(df), dtype=bool)

    for i in range(data.n_iterations):
        y_lowess = lowess(df.y, df.ds, frac=frac, return_sorted=False)
        df["res"] = (df.y_orig - y_lowess).abs()

        # Use rolling window to allow for changes in noise level over "time"
        rolling = df.res.rolling(rolling_window_size, min_periods=rolling_window_min_periods, center=True)
        df["res_ma"] = rolling.mean().bfill().ffill()
        df["res_mstd"] = rolling.std().bfill().ffill()

        # Classify datapoints far from rolling mean as outliers
        new_outlier = (df.res - df.res_ma).abs() > outlier_n_std * df.res_mstd

        if new_outlier.sum() == 0:
            break

        outlier |= new_outlier
        df["y"] = df.y_orig
        df.loc[outlier, "y"] = np.nan

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

    df["outlier"] = outlier

    return None, df


def find_outliers(data):
    if data.method == "prophet":
        m, df_pred = find_outliers_prophet(data)
    elif data.method == "lowess":
        m, df_pred = find_outliers_lowess(data)
    else:
        raise ValueError("Invalid method (%s)!" % data.method)

    return m, df_pred
