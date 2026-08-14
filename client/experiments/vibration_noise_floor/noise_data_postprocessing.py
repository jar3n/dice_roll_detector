"""

    Script to load in an ods file
    and find the peaks in the data 
    collected from the noise floor testing

    @author James Englander

    steps:
    1. Import the file
    2. read the file data 
    3. run some peak detection algo on it
    4. get the average peak amplitude and standard deveiations of the peak amplitude

"""

from pandas.core.frame import DataFrame
from pathlib import Path

from pandas.core.arrays.base import ExtensionArray

from pandas.core.series import Series

from numpy import dtype, ndarray

from typing import Any

from pandas.core.frame import DataFrame

import numpy as np

import argparse
import os
import pandas as pd
from scipy.signal import find_peaks

def parse_args() -> str:
    """parse arguments"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser()

    _ = parser.add_argument("filepath", type=str, help="File path of csv data to process")

    inputs: argparse.Namespace = parser.parse_args()

    filepath = inputs.filepath

    if not os.path.exists(path=os.path.abspath(filepath)):
        raise FileNotFoundError(f"Could not find given file: {filepath}")

    return os.path.abspath(filepath)


def get_column_peak_data(s:Series) -> dict[str, Any]:
    """Get the peak indexes and their amplitudes"""

    m = s.mean()
    a: ndarray[_AnyShape, dtype[Any]] = s.to_numpy()


    peaks = find_peaks(a, height=m)
    num_peaks = len(peaks[0])
    sum_peaks = sum(peaks[1]['peak_heights'])

    mean_peak_height = sum_peaks/num_peaks

    std_peak_height = np.std(peaks[1]['peak_heights'])
    

    peak_data: dict[str, Any] = {
        "peaks" :peaks,
        "mean peak amplitude": mean_peak_height,
        "std peak amplitude": std_peak_height
        }

    return peak_data

def get_dataframe_peak_data(df:DataFrame) -> list[dict[str, str | float]]:
    """Get the peak data for each column in the given dataframe"""

    columns: ExtensionArray = df.columns.array

    #timestamp_col = Series()

    def stats_dict(name: str, mean: float, std: float) -> dict[str, str | float]:
        return {
            "Filtering Applied": name,
            "Average Peak Amplitude": mean,
            "Standard Deviation from Average Peak Amplitude": std
        }

    col_peak_stats: list[dict[str, str | float]] = []
    

    for column in columns: # pyright: ignore[reportAny]
        if column == "Timestamp":
            #timestamp_col = df[column]
            continue
        
        col_peak_data = get_column_peak_data(s=df[column]) # pyright: ignore[reportArgumentType]

        peak_mean = col_peak_data['mean peak amplitude'] # pyright: ignore[reportAny]
        peak_std = col_peak_data['std peak amplitude']  # pyright: ignore[reportAny]

        # can get more data later
        col_peak_stats.append(stats_dict(column, peak_mean, peak_std))   # pyright: ignore[reportAny]
    
    return col_peak_stats


if __name__ == "__main__":
    try:
        filepath: str = parse_args()
        df: DataFrame = pd.read_csv(filepath)
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(e)
        
    else:
        
        # start with basic statistics

        means: Series = df.mean(axis=0)  # pyright: ignore[reportUnknownMemberType]
        stds: Series = df.std(axis=0) # pyright: ignore[reportUnknownMemberType]
        maxs: Series = df.max(axis=0) # pyright: ignore[reportUnknownMemberType]

        means = means.drop(index='Timestamp')
        stds = stds.drop(index='Timestamp')
        maxs = maxs.drop(index='Timestamp')


        print("Averages")
        print(means)
        print("Standard Deviations")
        print(stds)
        print("Max values")
        print(maxs)

        # now do some peak finding and stats
        # then convert to dataframe for ease of export

        peaks_data: list[dict[str, str | float]] = get_dataframe_peak_data(df)

        df_peaks_data: DataFrame = pd.DataFrame(data=peaks_data)

        df_peaks_data['Average Signal Amplitude'] = means.values
        df_peaks_data['Standard Deviation from Average Signal Amplitude'] = stds.values
        df_peaks_data['Highest Peak Amplitude'] = maxs.values

        # make a new file with the same name as original
        # with suffix peaks

        path: Path = Path(filepath)
        parent: Path = path.absolute().parent
        name: str = path.stem
        type: str = path.suffix

        export_name: str = name + "_peaks" + type
        export_path: Path = parent.joinpath(export_name)

        print(filepath)
        print(export_path)

        df_peaks_data.to_csv(export_path, index=False)  # pyright: ignore[reportUnknownMemberType]


        print(df_peaks_data)






            



