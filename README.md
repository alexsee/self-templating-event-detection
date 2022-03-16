# A Framework for Inferring Missing Event Log Data in Production Processes

This repository contains additional material of the paper "A Framework for Inferring Missing Event Log Data in Production Processes". In particular, it contains example code for the different methods introduced in the paper.

The following methods can be found in the repository:

* Template generation
    * Segmentation: change point detection, binary segmentation
    * Data cleaning:
    * Merging: averaging, barycenter averaging
* Event Detection
    * MASS algorithm
    * DTW-based algorithm

## Example code
You can find all the above mentioned code in this repository with notebook examples in the `notebooks` folder.
We also included the original code but this requires to setup the environment with an InfluxDB and the corresponding dataset.

To run the example code, you'll need to follow these steps:

1. Install [Miniconda](https://conda.io/miniconda.html) (make sure to use a Python 3 version)
2. After setting up miniconda you can make use of the `conda` command in your command line (Powershell, CMD, Bash)
3. We suggest that you set up a dedicated environment for this project by running `conda env create -f environment.yml`
    * This will setup a virtual conda environment with all necessary dependencies.
4. Depending on your operating system you can activate the virtual environment with `conda activate replearn` on Linux and macOS, and `activate ad` on Windows (`cmd` only).
5. If you want to quickly install the `eventlog-inferrence` package, run `pip install -e .` inside the root directory.
6. Now you can run the notebooks (except the ones in the `production-setup` folder).

## Jupyter Notebooks
Check the `notebooks` directory for example Jupyter Notebooks.