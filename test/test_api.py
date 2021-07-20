import sys
import argparse
import json

import pandas as pd
import requests
import matplotlib.pyplot as plt


if __name__ == "__main__":
    # "Tests" outlier detection api by plotting results. Uses requests, pandas and matplotlib libraries.
    parser = argparse.ArgumentParser()
    parser.add_argument("api_url", help="URL for outlier detection.")

    parsed = parser.parse_args()
    api_url = parsed.api_url

    with open("test_data.json", "r") as f:
        data = json.load(f)

    api_response = requests.post(api_url, json=data)

    if api_response.status_code != 200:
        raise Exception("No response from API!")

    api_response_json = api_response.json()

    dates = pd.to_datetime(data["dates"]).date
    outlier_date_target = [
        [date, target]
        for date, outlier, target in zip(dates, api_response_json["outliers"], data["target"])
        if outlier == 1
    ]

    plt.style.use("fivethirtyeight")
    plt.figure(figsize=(10, 8))
    plt.plot(dates, data["target"], "o--", label="Test Data")
    plt.plot(dates, api_response_json["prediction"], "o--", label="Model fit without outliers")
    plt.fill_between(dates, api_response_json["prediction_lower"], api_response_json["prediction_upper"],
                     alpha=0.3, label="Model outlier limits")
    plt.scatter([date for date, _ in outlier_date_target], [target for _, target in outlier_date_target],
                marker="X", s=150, c="black",
                label="Outlier")

    plt.xticks(rotation=45)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.show()
